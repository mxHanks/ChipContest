"""Hardware campaign contracts with isolated fake execution and source fixtures."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import xu_hw_experiments as hw


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


class FakeProcesses:
    def __init__(self, root, totals=None, failed=None, corrupt=None):
        self.root, self.failed, self.corrupt = root, failed, corrupt
        self.commands = []
        self.totals = dict({'B0-new-RTL': 25251416, 'H1-bias-cache': 20000000,
                            'H2-result-window': 19000000, 'H1H2-combined': 18000000}, **(totals or {}))
        self.config_totals = {}
        self.vector_bytes = {'layer_{:02d}/{}.mem'.format(i, name): (name + str(i)).encode()
                             for i in range(12) for name in ['x', 'w', 'bias', 'y']}
        fixture = root / 'tests/e203/vectors/kwt-silence-v1.json'
        fixture.parent.mkdir(parents=True)
        fixture.write_text(json.dumps(dict(files={k: sha_bytes(v) for k, v in self.vector_bytes.items()})))
        runtime = {'tools/scripts/e203_soc.py': 'runner', 'tools/scripts/xu_firmware_contract.py': 'contract',
                   'tests/e203/tb_accel_soc.sv': 'tb',
                   'third-party/e203_hbirdv2/rtl/e203/perips/cache.sv': 'rtl'}
        runtime.update({'tests/e203/firmware/' + name: name for name in ['start.S', 'main.c', 'accel.c', 'accel.h', 'link.ld']})
        self.source = dict(commit='unit-hardware-commit', parent_commits=['unit-parent'],
                           e203_commit='unit-e203-commit', fixed_baseline_commit=hw.BASELINE_COMMIT,
                           fixed_sha256={}, source_sha256=runtime)
        self.image = b'unit firmware image'
        self.history = dict(layers=[dict(layer=i, cycles=2104281 if i == 0 else 2104285,
                                        firmware_cycles=2104360 if i == 0 else 2104364) for i in range(12)],
                            firmware_image_sha256=sha_bytes(self.image))

    @staticmethod
    def value(command, name):
        return command[command.index(name) + 1]

    def config(self, command):
        return dict(schedule=self.value(command, '--firmware-schedule'),
                    optimization=next(arg.split('=', 1)[1] for arg in command if arg.startswith('--firmware-opt=')),
                    experiment=self.value(command, '--firmware-experiment'))

    def result(self, directory, mode, tasks, config, total, sim):
        directory.mkdir()
        layers, lines = [], []
        for layer in range(tasks):
            cycles = total // 12 + (total % 12 if layer == 0 else 0)
            if config['schedule'] == 'bias-dtcm' and total == hw.BASELINE_CYCLES:
                cycles = self.history['layers'][layer]['cycles']
            counts = dict(w_load=cycles - 202752, x_load=0, bias_load=0, compute_wait=202752,
                          writeback=0, other=0, busy=202752, mac_fire=202752,
                          mmio_reads=76032, mmio_writes=hw.contract.task_contract(config['schedule'])['mmio_writes'],
                          shared_reads=23232, shared_writes=50688, shared_stall=0, mmio_stall=0,
                          starts=3168, dones=3168)
            row = dict(layer=layer, cycles=cycles, firmware_cycles=cycles + 79, performance=counts)
            layers.append(row)
            lines.append('TASK_PASS layer={} outputs=25344 writes=50688 cycles={} firmware_cycles={}'.format(layer, cycles, cycles + 79))
            all_counts = dict(counts, layer=layer, cycles=cycles)
            lines.append('PERF_TASK ' + ' '.join(key + '=' + str(all_counts[key]) for key in hw.contract.PERFORMANCE_FIELDS))
        lines.append('SOC_PASS tasks={} outputs={} writes={}'.format(tasks, tasks * 25344, tasks * 50688))
        log = directory / 'simulation.log'
        log.write_text('\n'.join(lines) + '\n')
        (directory / 'accel_soc').write_bytes(b'ELF temporary FILE symbols can differ')
        (directory / 'accel_soc.verilog').write_bytes(self.image)
        fw_sources = {Path(name).name: digest for name, digest in self.source['source_sha256'].items()
                      if name.startswith('tests/e203/firmware/')}
        identities = dict(elf_sha256=hw.sha(directory / 'accel_soc'), image_sha256=hw.sha(directory / 'accel_soc.verilog'))
        vector_dir = directory / 'vectors'
        vectors = {}
        for name, data in self.vector_bytes.items():
            if int(name[6:8]) >= tasks:
                continue
            dest = vector_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            vectors[name] = sha_bytes(data)
        record = dict(status='PASS', mode=mode, tasks=tasks, simulator=sim,
                      firmware_schedule=config['schedule'], firmware_opt=config['optimization'],
                      firmware_experiment=config['experiment'], transaction_contract=hw.contract.task_contract(config['schedule']),
                      main_commit=self.source['commit'], e203_commit=self.source['e203_commit'],
                      source_sha256={'tests/e203/tb_accel_soc.sv': 'tb',
                          'third-party/e203_hbirdv2/vsim/install/rtl/perips/cache.sv': 'rtl'},
                      runner_sha256='runner', contract_sha256='contract', simulator_sha256='simulator',
                      firmware_build=dict(configuration=config, source_sha256=fw_sources, **identities),
                      firmware_sha256=fw_sources, firmware_elf_sha256=identities['elf_sha256'],
                      firmware_image_sha256=identities['image_sha256'],
                      versions={'test-gcc': ['SiFive GCC-Metal 10.2.0-2020.12.8'], 'vcs': ['Q-2020.03-SP2-6']},
                      tools={'test-gcc': sys.executable}, vectors=vectors,
                      layers=layers, outputs=tasks * 25344, write_words=tasks * 50688,
                      log_sha256={'simulation.log': hw.sha(log)})
        (directory / 'result.json').write_text(json.dumps(record))
        return record

    def __call__(self, command, logfile, timeout):
        self.commands.append(command)
        logfile.write_text(json.dumps(command) + '\n')
        name = Path(command[1]).name
        directory = Path(self.value(command, '--out'))
        if name == 'xu_perf_report.py':
            directory.write_text(json.dumps(hw.perf.summarize(json.loads(Path(self.value(command, '--result')).read_text()), 150)))
            return
        config, sim = self.config(command), self.value(command, '--sim')
        if name == 'server_accept.py':
            directory.mkdir()
            steps = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']
            (directory / 'acceptance.json').write_text(json.dumps(dict(status='PASS', firmware_configuration=config,
                steps=[dict(name=step, status='PASS') for step in steps])))
            total = self.config_totals[json.dumps(config, sort_keys=True)]
            for label, mode, tasks in [('synthetic2', 'synthetic', 2), ('real12', 'real', 12)]:
                self.result(directory / label, mode, tasks, config, total, sim)
            return
        mode, tasks = self.value(command, '--mode'), int(self.value(command, '--tasks'))
        trial = directory.name.rsplit('-', 1)[0]
        total = self.totals[trial]
        self.config_totals[json.dumps(config, sort_keys=True)] = total
        record = self.result(directory, mode, tasks, config, total, sim)
        if self.corrupt:
            self.corrupt(trial, record, directory)
            (directory / 'result.json').write_text(json.dumps(record))
        if trial == self.failed:
            raise RuntimeError('fake correctness failure')


class HardwareExperimentTests(unittest.TestCase):
    def campaign(self, totals=None, failed=None, corrupt=None, sim='vcs', accept=False, runner=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        fake = FakeProcesses(base / 'source', totals, failed, corrupt)
        out = base / 'output'
        out.mkdir()
        with patch.object(hw, 'ROOT', fake.root), patch.object(hw, 'source_identity', return_value=fake.source), \
             patch.object(hw, 'git_output', return_value=json.dumps(fake.history).encode()):
            result = hw.Campaign(out, sim, 'test-', accept, runner=runner(fake) if runner else fake).run()
        return result, fake

    def test_independent_cases_combination_and_full_acceptance(self):
        result, fake = self.campaign(accept=True)
        self.assertEqual(result['status'], 'PASS', result.get('error'))
        self.assertEqual([e['name'] for e in result['experiments']],
                         ['B0-new-RTL', 'H1-bias-cache', 'H2-result-window', 'H1H2-combined'])
        self.assertEqual([e['parent'] for e in result['experiments']], [None, 'B0-new-RTL', 'B0-new-RTL', 'H2-result-window'])
        self.assertTrue(all([c['workload'] for c in e['cases']] == ['synthetic2', 'real12'] for e in result['experiments']))
        self.assertEqual(result['selected']['configuration'], hw.contract.configuration('bias-hw-window', '-O2', 'both-unroll-no-masks'))
        self.assertEqual(result['retention_status'], 'retained')
        self.assertTrue(result['retained_optimization'])
        self.assertEqual(result['acceptance']['status'], 'PASS')
        self.assertEqual(len(fake.commands), 10)

    def test_tie_or_regression_keeps_baseline(self):
        totals = {'H1-bias-cache': hw.BASELINE_CYCLES + 1, 'H2-result-window': hw.BASELINE_CYCLES,
                  'H1H2-combined': hw.BASELINE_CYCLES}
        result, unused = self.campaign(totals=totals, accept=True)
        self.assertEqual(result['status'], 'PASS', result.get('error'))
        self.assertEqual(result['selected']['experiment'], 'B0-new-RTL')
        self.assertEqual(result['retention_status'], 'baseline-retained')
        self.assertFalse(result['retained_optimization'])

    def test_local_and_unaccepted_vcs_never_claim_retained(self):
        for sim, accept, expected in [('verilator', True, 'provisional'), ('vcs', False, 'pending-acceptance')]:
            with self.subTest(sim=sim):
                result, unused = self.campaign(sim=sim, accept=accept)
                self.assertEqual(result['status'], 'PASS', result.get('error'))
                self.assertEqual(result['retention_status'], expected)
                self.assertFalse(result['retained_optimization'])

    def test_failed_independent_candidate_skips_combination_and_keeps_hashes(self):
        result, unused = self.campaign(failed='H1-bias-cache')
        self.assertEqual(result['status'], 'PASS', result.get('error'))
        self.assertEqual(result['selected']['experiment'], 'H2-result-window')
        self.assertEqual(len(result['experiments']), 3)
        case = result['experiments'][1]['cases'][0]
        self.assertEqual(case['status'], 'FAIL')
        self.assertEqual(len(case['result_sha256']), 64)
        self.assertEqual(len(case['driver_log_sha256']), 64)

    def test_baseline_requires_exact_layers_and_image_but_not_elf_bytes(self):
        for kind in ['cycles', 'image']:
            def corrupt(trial, record, directory):
                if trial != 'B0-new-RTL':
                    return
                if kind == 'cycles':
                    record['layers'][0]['cycles'] += 1
                else:
                    (directory / 'accel_soc.verilog').write_bytes(b'wrong image')
                    digest = hw.sha(directory / 'accel_soc.verilog')
                    record['firmware_image_sha256'] = record['firmware_build']['image_sha256'] = digest
            result, unused = self.campaign(corrupt=corrupt)
            self.assertEqual(result['status'], 'FAIL')
            self.assertEqual(len(result['experiments']), 1)
        # The fake baseline ELF has unrelated bytes; only exact load image is a performance gate.
        result, unused = self.campaign()
        self.assertEqual(result['status'], 'PASS', result.get('error'))

    def test_source_tool_vector_transaction_or_log_changes_reject_candidate(self):
        for kind in ['rtl', 'rtl-missing', 'runner', 'submodule', 'vectors', 'transaction', 'log', 'tool-version']:
            def corrupt(trial, record, directory):
                if trial != 'H1-bias-cache':
                    return
                if kind == 'rtl': record['source_sha256']['tests/e203/tb_accel_soc.sv'] = 'changed'
                elif kind == 'rtl-missing': record['source_sha256'].pop('tests/e203/tb_accel_soc.sv')
                elif kind == 'runner': record['runner_sha256'] = 'changed'
                elif kind == 'submodule': record['e203_commit'] = 'changed'
                elif kind == 'vectors':
                    key = next(iter(record['vectors']))
                    (directory / 'vectors' / key).write_bytes(b'changed')
                elif kind == 'transaction': record['layers'][0]['performance']['mmio_writes'] = 156326
                elif kind == 'tool-version': record['versions']['test-gcc'] = ['wrong compiler']
                else: (directory / 'simulation.log').write_text('TEST_FAIL\n')
            result, unused = self.campaign(corrupt=corrupt)
            self.assertEqual(result['experiments'][1]['status'], 'FAIL', kind)
            self.assertFalse(result['retained_optimization'])

    def test_failed_acceptance_preserves_available_evidence(self):
        def runner(fake):
            def fail(command, logfile, timeout):
                fake(command, logfile, timeout)
                if Path(command[1]).name == 'server_accept.py': raise RuntimeError('acceptance failed')
            return fail
        result, unused = self.campaign(accept=True, runner=runner)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['acceptance']['status'], 'FAIL')
        self.assertIn('acceptance.log', result['acceptance']['driver_log_sha256'])
        self.assertIn('acceptance.json', result['acceptance']['result_sha256'])
        self.assertFalse(result['retained_optimization'])

    def test_source_guard_uses_isolated_clean_git_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=str(root), stderr=subprocess.DEVNULL)
            git('init', '-q')
            git('config', 'user.name', 'xu-test')
            git('config', 'user.email', 'xu-test@example.invalid')
            (root / 'src').mkdir()
            file = root / 'src/core.scala'
            file.write_text('fixed')
            git('add', 'src')
            git('commit', '-qm', 'source fixture')
            self.assertEqual(hw.tracked_sources(root, ['src']), {'src/core.scala': sha_bytes(b'fixed')})
            file.write_text('dirty')
            with self.assertRaisesRegex(ValueError, 'dirty'): hw.tracked_sources(root, ['src'])
            file.write_text('fixed')
            (root / 'src/new.scala').write_text('untracked')
            with self.assertRaisesRegex(ValueError, 'untracked'): hw.tracked_sources(root, ['src'])


if __name__ == '__main__':
    unittest.main()
