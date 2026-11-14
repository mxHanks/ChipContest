"""Submission contract: current selection, published evidence, safe extraction."""
import argparse
from contextlib import redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('current', ROOT / 'tools/current.py')
current = importlib.util.module_from_spec(spec)
spec.loader.exec_module(current)


class CurrentSubmissionTests(unittest.TestCase):
    def test_published_evidence_and_selected_rtl(self):
        result = current.verify(submodule=True)
        self.assertEqual(result['status'], 'EVIDENCE_VERIFIED_NOT_SIGNOFF')
        self.assertEqual(result['unknown_checks'], 4)
        self.assertEqual(result['archive_payload_files'], 80)

    def test_wrong_rtl_selection_is_rejected(self):
        selected = current.candidate()
        selected['rtl']['commit'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'gitlink'):
            current.check_submodule(ROOT, selected)

    def test_reported_performance_and_area_cannot_disagree_with_raw_evidence(self):
        altered = {'rtl_cycles': 1, 'rtl_tasks': 1, 'exact_y32_outputs': 1,
                   'assumed_frequency_hz': 1, 'conditional_tasks_per_second': 123,
                   'standard_cell_area_native_library_units': '1',
                   'internal_33_sram_area_native_library_units': '1',
                   'conservative_area_upper_bound_native_library_units': '1'}
        for field, value in altered.items():
            with self.subTest(field=field):
                selected = current.candidate()
                selected['results'][field] = value
                with self.assertRaisesRegex(ValueError, 'Performance|Area'):
                    current.verify(ROOT, selected)

    def test_performance_original_bytes_are_required(self):
        for name in ('result', 'simulation_log', 'checker'):
            with self.subTest(name=name):
                selected = current.candidate()
                selected['performance'][name]['sha256'] = '0' * 64
                with self.assertRaisesRegex(ValueError, 'Byte/hash mismatch: performance'):
                    current.verify(ROOT, selected)

    def test_cpu_command_selects_current_runner_and_pipelined_full_twelve(self):
        args = argparse.Namespace(action='cpu', vectors=Path('vectors'), out=Path('result'),
                                  tasks=12, jobs=2, cross_prefix='riscv64-unknown-elf-')
        command = current.execution_command(ROOT, current.candidate(), args)
        self.assertEqual(Path(command[2]), ROOT / 'experiments/s3-y32-ingress-perf/run_cpu.py')
        self.assertIn('--warmup', command)
        for option, value in [('--tasks', '12'), ('--load-pipeline', '1'), ('--jobs', '2')]:
            self.assertEqual(command[command.index(option) + 1], value)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            current.main(['cpu', '--vectors', 'vectors', '--out', 'result', '--load-pipeline', '0'])

    def test_extraction_is_exact_and_refuses_overwrite(self):
        selected = current.candidate()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'mapped'
            current.unpack(ROOT, selected, out)
            files = {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
            self.assertEqual(files, set(selected['evidence']['delivery']))
            self.assertEqual(hashlib.sha256((out / 'apply/mapped.v').read_bytes()).hexdigest(),
                             'd83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                current.unpack(ROOT, selected, out)

    def test_archive_hash_failure_creates_no_output(self):
        selected = current.candidate()
        selected['evidence']['archive']['sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'mapped'
            with self.assertRaisesRegex(ValueError, 'Byte/hash mismatch'):
                current.unpack(ROOT, selected, out)
            self.assertFalse(out.exists())

    def test_hostile_tar_members_never_create_output(self):
        # Rebind the synthetic archive's outer SHA to exercise tar safety itself.
        for scenario in ('traversal', 'absolute', 'symlink', 'duplicate'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                archive = root / 'hostile.tar.xz'
                with tarfile.open(archive, 'w:xz') as tar:
                    name = {'traversal': '../escaped', 'absolute': '/escaped'}.get(scenario, 'payload')
                    member = tarfile.TarInfo(name)
                    if scenario == 'symlink':
                        member.type = tarfile.SYMTYPE
                        member.linkname = '../escaped'
                    else:
                        member.size = 1
                    tar.addfile(member, io.BytesIO(b'x') if member.isfile() else None)
                    if scenario == 'duplicate':
                        tar.addfile(member, io.BytesIO(b'x'))
                blob = archive.read_bytes()
                selected = {'evidence': {'archive': {'path': archive.name, 'bytes': len(blob),
                                                      'sha256': hashlib.sha256(blob).hexdigest()}}}
                out = root / 'out'
                with self.assertRaisesRegex(ValueError, 'Unsafe path|Non-regular|Duplicate'):
                    current.unpack(root, selected, out)
                self.assertFalse(out.exists())
                self.assertFalse((root.parent / 'escaped').exists())

    def test_vectors_are_bound_and_command_uses_independent_checker(self):
        selected = current.candidate()
        data = current.vector_delivery(ROOT, selected)
        self.assertEqual(len(data), 86)
        self.assertEqual(hashlib.sha256(data['vectors-manifest.json']).hexdigest(),
                         '4552d7f31cf8307e7440a8385b3ba83c1b67de7fdae975d23d38815c01b77d6b')
        # The independent checker receives the selected vectors without invoking EDA.
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'vectors'
            current.write_delivery(data, out)
            with patch.object(current.subprocess, 'run') as run:
                run.return_value.returncode = 0
                self.assertEqual(current.main(['check-vectors', '--vectors', str(out)]), 0)
                command = run.call_args.args[0]
                self.assertEqual(Path(command[2]), ROOT / 'experiments/s3-y32-compliant32/numeric/verify_vectors.py')
                self.assertEqual(command[-2:], ['--vectors', str(out)])


if __name__ == '__main__':
    unittest.main()
