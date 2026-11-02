"""Synthetic collector/normalizer handoff; these are not VCS capture tests."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_task_alias_collector', ROOT / 'tools/ppa/xu_soc_task_activity.py')
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)
alias = collector.sram_alias
EVIDENCE = Path(os.environ['XU_TASK_ALIAS_TEST_EVIDENCE']) if os.environ.get('XU_TASK_ALIAS_TEST_EVIDENCE') else None
DURATION = 40000000


def evidence(name, value):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / name).write_text(value)


def synthetic_raw(path, configuration, omit=None):
    """Write all mapped alias bits, with explicitly synthetic known/unknown dwell."""
    mapping, pairs = alias.validate_mapping(configuration['mapping_file']['path'])
    root = ['SAIFILE', ['DESIGN', '"xu synthetic collector handoff, not measured activity"'],
            ['TIMESCALE', '1', 'fs'], ['DURATION', str(DURATION)]]
    branches = {}

    def append(name, values):
        parts = name.split('/')
        for index in range(1, len(parts)):
            scope = '/'.join(parts[:index])
            if scope not in branches:
                node = ['INSTANCE', alias.atom(parts[index - 1])]
                (root if index == 1 else branches['/'.join(parts[:index - 1])]).append(node)
                branches[scope] = node
        scope = branches['/'.join(parts[:-1])]
        section = next((node for node in scope[2:] if node[0] == 'NET'), None)
        if section is None:
            section = ['NET']
            scope.append(section)
        section.append([alias.atom(parts[-1])] + [[key, str(value)] for key, value in values.items()])

    for source, target in pairs.items():
        if source == omit:
            continue
        dtcm = '/u_e203_dtcm_ram/' in target
        pin = target.rsplit('/', 1)[1]
        values = dict(T0=DURATION, T1=0, TX=0, TC=0)
        if dtcm and pin in ('CEN', 'RET1N'):
            values.update(T0=0, T1=DURATION)
        elif dtcm and pin == 'Q[0]':
            values.update(T0=0, TX=DURATION)
        elif not dtcm and pin == 'CLK':
            values.update(T0=DURATION // 2, T1=DURATION // 2, TC=12)
        elif not dtcm and pin == 'D[0]':
            values.update(T0=DURATION - 3, TX=1, TZ=1, TB=1, TC=2)
        append(source, values)
    prefix = collector.SCOPE.replace('.', '/')
    append(prefix + '/hfextclk', dict(T0=DURATION // 2, T1=DURATION // 2, TX=0, TC=12))
    for name in ('cmd', 'rsp'):
        append(prefix + '/u_soc/u_e203_cpu_top/u_e203_biu/' + name,
               dict(T0=DURATION - 3, T1=0, TX=1, TZ=1, TB=1, TC=1, IG=2))
    with path.open('w') as output:
        alias.write_sexpr(output, root)
    return mapping, pairs


class CollectorAliasTests(unittest.TestCase):
    def prepare(self, directory):
        build = directory / 'simulator'
        build.mkdir()
        return collector.prepare_sram_pin_alias(build, collector.HERE / 'xu_weight_sram_adapter.sv')

    def test_synthetic_full_336_handoff_preserves_raw_unknowns_and_strict_idle_dtcm(self):
        with tempfile.TemporaryDirectory(prefix='xu-alias-handoff-') as temporary:
            directory = Path(temporary)
            configuration = self.prepare(directory)
            raw = directory / 'task.saif'
            _, pairs = synthetic_raw(raw, configuration)
            before = raw.read_bytes()
            result = collector.inspect_task_activity(directory, dict(duration_ticks=DURATION),
                                                       collector.STATIC_SCOPE_DECLARATIONS, configuration)
            capture = result['sram_pin_alias_capture']
            receipt = capture['normalization']
            self.assertEqual(raw.read_bytes(), before)
            self.assertEqual(result['saif']['path'], str(directory / 'task-normalized.saif'))
            self.assertEqual(capture['status'], 'NORMALIZED_REVIEW_PENDING')
            self.assertEqual(receipt['alias_bit_count'], 22512)
            self.assertEqual(receipt['mapped_pin_bits_added_as_port'], 22512)
            self.assertEqual(receipt['macro_count'], 336)
            self.assertEqual(receipt['raw_saif']['sha256'], collector.base.sha(raw))
            self.assertEqual(capture['normalization_receipt']['sha256'], collector.base.sha(directory / 'task-normalization.json'))
            self.assertEqual(sum(group['observed_count'] for group in result['saif']['macro_inventory'].values()), 336)
            dtcm = result['saif']['scope_presence']['dtcm']
            self.assertEqual(dtcm['state'], 'OBSERVED_KNOWN_STATIC_DISABLED')
            self.assertEqual(dtcm['unknown_bit_ticks'], 32 * DURATION)
            normalized = collector.activity.read_saif(directory / 'task-normalized.saif')
            measured = collector.activity.read_saif(raw)
            sources = {signal['path']: signal for signal in measured['signals']}
            targets = {signal['path']: signal for signal in normalized['signals']}
            for source, target in pairs.items():
                self.assertEqual(alias.stats(sources[source]), alias.stats(targets[target]), target)
            self.assertFalse(any('/xu_sram_activity_alias/' in path for path in targets))
            self.assertEqual(capture['mapping_file'], configuration['mapping_file'])
            self.assertEqual(capture['observer_source'], configuration['observer_source'])
            evidence('synthetic-handoff-result.json', json.dumps(
                dict(scope='SYNTHETIC_HOST_HANDOFF_NOT_VCS_CAPTURE', result=result), indent=2, sort_keys=True) + '\n')
            evidence('synthetic-handoff-receipt.json', (directory / 'task-normalization.json').read_text())

    def test_missing_measured_alias_fails_without_normalized_output_or_raw_changes(self):
        with tempfile.TemporaryDirectory(prefix='xu-alias-missing-') as temporary:
            directory = Path(temporary)
            configuration = self.prepare(directory)
            _, pairs = alias.validate_mapping(configuration['mapping_file']['path'])
            raw = directory / 'task.saif'
            synthetic_raw(raw, configuration, omit=next(iter(pairs)))
            before = raw.read_bytes()
            with self.assertRaisesRegex(ValueError, 'missing or unexpected alias bits'):
                collector.inspect_task_activity(directory, dict(duration_ticks=DURATION),
                                                  collector.STATIC_SCOPE_DECLARATIONS, configuration)
            self.assertEqual(raw.read_bytes(), before)
            self.assertFalse((directory / 'task-normalized.saif').exists())
            self.assertFalse((directory / 'task-normalization.json').exists())

    def test_observer_mapping_source_tampering_and_custom_adapter_rejected(self):
        with tempfile.TemporaryDirectory(prefix='xu-alias-source-') as temporary:
            directory = Path(temporary)
            configuration = self.prepare(directory)
            for key in ('observer_source', 'mapping_file'):
                path = Path(configuration[key]['path'])
                before = path.read_bytes()
                path.write_bytes(before + b'\n')
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'frozen input changed'):
                    collector.check_sram_pin_alias(configuration)
                path.write_bytes(before)
            collector.check_sram_pin_alias(configuration)
            custom = directory / 'custom-adapter.sv'
            shutil.copyfile(str(collector.HERE / 'xu_weight_sram_adapter.sv'), str(custom))
            with self.assertRaisesRegex(ValueError, 'only the default weight adapter'):
                collector.prepare_sram_pin_alias(directory / 'other-build', custom)
            self.assertFalse((directory / 'other-build').exists())

    @unittest.skipUnless(shutil.which('riscv64-unknown-elf-gcc') and os.environ.get('XU_TASK_ACTIVITY_VENDOR_MODEL'),
                         'RISC-V compiler and explicit private vendor-model path required')
    def test_real_prepare_only_records_alias_source_and_preserves_default_source_list(self):
        with tempfile.TemporaryDirectory(prefix='xu-alias-prepare-') as temporary:
            directory = Path(temporary)
            netlist = directory / 'identity-only-not-simulated.v'
            netlist.write_text('// synthetic identity for prepare-only; never simulated\n')
            destination = directory / 'prepared'
            command = [sys.executable, str(collector.HERE / 'xu_soc_task_activity.py'),
                       '--out', str(destination), '--vendor-model', os.environ['XU_TASK_ACTIVITY_VENDOR_MODEL'],
                       '--netlist', str(netlist), '--constraints', str(collector.HERE / 'xu_full_soc.sdc'),
                       '--sram-pin-alias', '--clear-task-before-window', '--task-ids', '0', '--prepare-only']
            run = subprocess.run(command, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True, timeout=180)
            evidence('alias-prepare.log', json.dumps(dict(command=command, returncode=run.returncode)) + '\n' + run.stdout)
            self.assertEqual(run.returncode, 0, run.stdout)
            report = json.loads((destination / 'result.json').read_text())
            self.assertEqual(report['status'], 'PARTIAL_PREPARED_NOT_SIMULATED')
            self.assertTrue(report['sram_pin_alias'])
            self.assertTrue(report['clear_task_before_window'])
            self.assertEqual(report['requested_task_ids'], [0])
            configuration = report['configuration']['sram_pin_alias']
            source = configuration['observer_source']
            collector.check_sram_pin_alias(configuration)
            self.assertEqual(report['configuration']['rtl_sources_sha256'][source['path']], source['sha256'])
            filelist = (destination / 'simulator/rtl.f').read_text().splitlines()
            self.assertEqual(filelist.count(source['path']), 1)
            default_sources = collector.collect_sources(destination / 'simulator/tb_xu_soc_task_activity.sv',
                                                         Path(os.environ['XU_TASK_ACTIVITY_VENDOR_MODEL']).resolve(),
                                                         collector.HERE / 'xu_weight_sram_adapter.sv')
            self.assertNotIn(source['path'], [str(path) for path in default_sources])
            self.assertEqual(filelist[:-1], [str(path) for path in default_sources])
            self.assertNotIn('SYNTHESIS', ' '.join(report['build_command']))
            self.assertEqual(report['build_command'].count('-debug_region+cell'), 1)
            self.assertEqual(report['configuration']['activity_scope'], collector.SCOPE)
            self.assertEqual(configuration['mapping']['placement'], 'bind')
            self.assertEqual(configuration['mapping']['observer_scope'], collector.SCOPE + '.xu_sram_activity_alias')
            evidence('alias-prepare-result.json', json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    unittest.main()
