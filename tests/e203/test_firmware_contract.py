"""xu optimization identities must survive compilation, acceptance and reporting."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import e203_soc as soc
import server_accept as accept
import xu_firmware_contract as contract
import xu_perf_report as perf


class FirmwareContractTests(unittest.TestCase):
    def source(self, schedule='baseline'):
        counters = dict.fromkeys(set(contract.PERFORMANCE_FIELDS) - {'layer', 'cycles'}, 0)
        counters.update(w_load=300000, x_load=100000, bias_load=600000,
                        compute_wait=250000, writeback=1118078, busy=215424,
                        mac_fire=202752, mmio_reads=69696, mmio_writes=156326,
                        shared_reads=contract.task_contract(schedule)['shared_reads'],
                        shared_writes=50688, starts=3168, dones=3168)
        return dict(status='PASS', mode='real', tasks=1, firmware_schedule=schedule,
                    outputs=25344, write_words=50688,
                    layers=[dict(layer=0, cycles=2368078, firmware_cycles=2368150,
                                 performance=counters)])

    def test_each_schedule_enforces_its_transaction_contract_in_both_readers(self):
        for schedule, reads in [('baseline', 73408), ('bias-dtcm', 23232)]:
            with self.subTest(schedule=schedule):
                source = self.source(schedule)
                row = source['layers'][0]
                log = 'PERF_TASK ' + ' '.join(f'{key}={row[key] if key in row else row["performance"][key]}'
                                             for key in contract.PERFORMANCE_FIELDS) + '\n'
                self.assertEqual(soc.check_performance(log, [row], schedule)[0]['shared_reads'], reads)
                self.assertEqual(perf.summarize(source, 150)['aggregate']['counters']['shared_reads'], reads)
                self.assertEqual(contract.task_contract(schedule)['bias_mmio_writes'], 76032)
                for wrong in ['baseline' if schedule == 'bias-dtcm' else 'bias-dtcm', 'unknown']:
                    with self.assertRaises(ValueError): soc.check_performance(log, [row], wrong)
                    bad = copy.deepcopy(source)
                    bad['firmware_schedule'] = wrong
                    with self.assertRaises(ValueError): perf.summarize(bad, 150)

    def test_report_rejects_wrong_work_layers_phases_or_identity(self):
        source = self.source('bias-dtcm')
        mutations = [lambda x: x['layers'].append(copy.deepcopy(x['layers'][0])),
                     lambda x: x.update(tasks=2),
                     lambda x: x['layers'][0].update(layer=1),
                     lambda x: x['layers'][0]['performance'].update(mac_fire=202751),
                     lambda x: x['layers'][0]['performance'].update(shared_writes=50687),
                     lambda x: x['layers'][0]['performance'].update(mmio_writes=156325),
                     lambda x: x['layers'][0]['performance'].update(other=1),
                     lambda x: x['layers'][0]['performance'].pop('other'),
                     lambda x: x['layers'][0].pop('performance'),
                     lambda x: x.update(outputs=25343),
                     lambda x: x.update(write_words=50687),
                     lambda x: x.pop('outputs'),
                     lambda x: x.pop('write_words'),
                     lambda x: x.update(firmware_opt='-Ofast'),
                     lambda x: x.update(firmware_experiment='unknown'),
                     lambda x: x.update(firmware_build={'configuration':contract.configuration()}),
                     lambda x: x.update(transaction_contract=contract.task_contract())]
        for mutation in mutations:
            bad = copy.deepcopy(source)
            mutation(bad)
            with self.subTest(bad=bad), self.assertRaises(ValueError): perf.summarize(bad, 150)
        # Poll count remains measured, rather than locked to the historic compiler.
        source['layers'][0]['performance']['mmio_reads'] = 60000
        self.assertEqual(perf.summarize(source, 150)['aggregate']['counters']['mmio_reads'], 60000)

    def test_legacy_baseline_and_complete_12_layer_cycles_remain_compatible(self):
        source = self.source()
        del source['firmware_schedule']
        source['tasks'] = 12
        source['outputs'] = 304128
        source['write_words'] = 608256
        source['layers'] = [dict(layer=i, cycles=2368078 if i == 0 else 2368074,
                                 firmware_cycles=2368150 if i == 0 else 2368146)
                            for i in range(12)]
        report = perf.summarize(source, 150)
        self.assertEqual(report['aggregate']['cycles'], 28416892)
        self.assertEqual(report['firmware_schedule'], 'baseline')
        self.assertEqual(report['firmware_opt'], '-Os')

    def test_explicit_baseline_requires_observer_records(self):
        source = self.source()
        source['layers'][0].pop('performance')
        with self.assertRaises(ValueError):
            perf.summarize(source, 150)

    def test_historical_observed_receipt_still_recomputes(self):
        path = soc.ROOT/'docs/validation/xu-performance-20261102/observed-receipt.json'
        receipt = json.loads(path.read_text())
        source = dict(status='PASS', mode='real', tasks=receipt['tasks'],
                      outputs=receipt['outputs'], write_words=receipt['write_words'], layers=[])
        for group in receipt['groups']:
            for layer in group['layers']:
                source['layers'].append(dict(layer=layer, cycles=group['cycles'],
                    firmware_cycles=group['firmware_cycles'], performance=group['performance']))
        self.assertEqual(perf.summarize(source, 150)['aggregate']['cycles'], 28416892)

    def test_cli_and_acceptance_propagate_configuration_to_every_soc_step(self):
        parser = argparse.ArgumentParser()
        contract.add_arguments(parser)
        args = parser.parse_args(['--firmware-schedule', 'bias-dtcm', '--firmware-opt=-O3',
                                  '--firmware-experiment', 'both-unroll-no-masks'])
        config = contract.configuration(args.firmware_schedule, args.firmware_opt, args.firmware_experiment)
        self.assertTrue(all(flag.endswith('=1') for flag in contract.compiler_defines(config)))
        for sim, full in [('vcs', False), ('verilator', True)]:
            steps = accept.acceptance_steps(Path('/unused-xu'), 'rv-', sim, full=full,
                                            firmware_schedule=config['schedule'],
                                            firmware_opt=config['optimization'],
                                            firmware_experiment=config['experiment'])
            names = [step[0] for step in steps]
            self.assertTrue({'host', 'numeric', 'vectors', 'doctor', 'baseline',
                             'synthetic1', 'synthetic2', 'real12'}.issubset(names))
            for name, command, _ in steps:
                if name in ['host', 'numeric', 'chisel']: continue
                self.assertEqual(command[command.index('--firmware-schedule') + 1], 'bias-dtcm')
                self.assertIn('--firmware-opt=-O3', command)
                self.assertEqual(command[command.index('--firmware-experiment') + 1], 'both-unroll-no-masks')
            synthetic2 = next(command for name, command, _ in steps if name == 'synthetic2')
            self.assertEqual(synthetic2[synthetic2.index('--tasks') + 1], '2')

    def test_compiler_command_and_memory_identity_are_saved(self):
        for opt in contract.OPTIMIZATIONS:
            with self.subTest(opt=opt), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)
                commands = []
                def run(command, cwd, log):
                    commands.append(command)
                    if command[0] == 'rv-gcc':
                        self.assertEqual(cwd, out)
                        Path(command[-1]).write_bytes(b'ELF')
                        (out/'accel.su').write_text('accel.c:7:5:accel_linear\t80\tstatic\n')
                    elif command[0] == 'rv-objcopy':
                        Path(command[-1]).write_text('@80000000\n00\n')
                    elif '--disassemble-all' in command:
                        return '80000086 <write_tohost>:\n'
                    elif '-h' in command:
                        return '  0 .text 00000400 80000000\n  1 .bss 00000800 90000000\n'
                    elif '-t' in command:
                        return ('90000000 g .bss 00000000 __bss_start\n'
                                '90000800 g .bss 00000000 __bss_end\n'
                                '9000fff0 g *ABS* 00000000 __stack_top\n')
                    return ''
                report = {}
                with patch.object(soc, 'run', side_effect=run):
                    target = soc.compile_firmware(out, 'rv-', 'bias-dtcm', opt, 'none', report)
                command = commands[0]
                self.assertEqual([arg for arg in command if arg in contract.OPTIMIZATIONS], [opt])
                self.assertIn('-DXU_FIRMWARE_BIAS_DTCM=1', command)
                self.assertIn('-DXU_FIRMWARE_BIAS_UNROLL=0', command)
                saved = json.loads((out/'firmware-build.json').read_text())
                self.assertEqual(saved, report['firmware_build'])
                self.assertEqual(saved['command'], command)
                self.assertEqual(saved['elf_sha256'], soc.sha(target))
                self.assertEqual(saved['image_sha256'], soc.sha(Path(str(target)+'.verilog')))
                self.assertEqual(saved['memory']['bss_bytes'], 2048)
                self.assertEqual(saved['memory']['stack_capacity_after_bss_bytes'], 63472)
                self.assertEqual(saved['memory']['max_static_stack_frame_bytes'], 80)


if __name__ == '__main__':
    unittest.main()
