"""S3 conversion preserves frozen bytes and covers every output/source position."""
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model import fixed16_acc48 as legacy
from model import s3_y32 as s3

SPEC = importlib.util.spec_from_file_location('s3_vector_export', ROOT/'tools/model/export_s3_vectors.py')
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic(directory, tasks=2):
    """Exercise signed endpoints, both tie parities, rows, groups and lanes."""
    for layer in range(tasks):
        target = directory/('layer_%02d' % layer)
        weights = [((i*40503 + layer*193) & 65535)-32768 for i in range(16384)]
        ties = [s3.Y48_MIN, s3.Y48_MAX, -1280, -768, -256, 256, 768, 1280,
                -513, -511, 511, 513]
        outputs = [ties[(i+layer) % len(ties)] if i % 3 else
                   ((i*12037+layer*31)-150000000)*512 + (i % 513)
                   for i in range(25344)]
        legacy.write_hex_mem(target/'x.mem', [((i*17) & 65535)-32768 for i in range(6336)], 16)
        legacy.write_hex_mem(target/'w.mem', weights, 16)
        legacy.write_hex_mem(target/'bias.mem', [-(1 << 39) if i % 2 else (1 << 39)-1
                                                for i in range(256)], 40)
        legacy.write_hex_mem(target/'y.mem', outputs, 48)


class S3VectorExportTests(unittest.TestCase):
    def test_real_cli_all_12_tasks_and_every_derived_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'s3'
            result = subprocess.run([sys.executable, '-B', str(ROOT/'tools/model/export_s3_vectors.py'),
                                     '--out', str(output), '--shared-w-packed16'],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn('S3_VECTOR_EXPORT_PASS tasks=12', result.stdout)
            frozen = json.loads(export.FIXTURE.read_text())
            for name, expected in frozen['files'].items():
                self.assertEqual(digest(output/name), expected, name)
            profile = json.loads((output/'profile.json').read_text())
            self.assertEqual(profile['tasks'], 12)
            self.assertEqual(profile['y_exp'], -18)
            self.assertEqual(profile['rounding'], 'nearest_ties_even')
            self.assertFalse(profile['saturation'])
            self.assertEqual(profile['w']['bytes'], 32768)
            self.assertEqual(profile['y']['bytes'], 25344*4)
            for record in profile['layers']:
                layer = output/('layer_%02d' % record['layer'])
                old_y = legacy.read_hex_mem(layer/'y.mem', 48, 25344)
                actual_y = legacy.read_hex_mem(layer/'y32.mem', 32, 25344)
                self.assertEqual(actual_y, [round(Fraction(v, 512)) for v in old_y])
                old_w = legacy.read_hex_mem(layer/'w.mem', 16, 16384)
                raw = [int(word, 16) for word in (layer/'w_packed16.mem').read_text().splitlines()]
                self.assertEqual(len(raw), 8192)
                unpacked = [field-65536 if field & 32768 else field
                            for word in raw for field in [word & 65535, word >> 16]]
                self.assertEqual(unpacked, old_w)
                for name, identity in record['files'].items():
                    self.assertEqual(digest(layer/name), identity['sha256'])
                    self.assertEqual((layer/name).stat().st_size, identity['bytes'])
            receipt = json.loads((output/'export-manifest.json').read_text())
            self.assertEqual(receipt['source']['verified_tasks'], 12)
            self.assertEqual(receipt['source']['verified_files'], 48)
            self.assertEqual(receipt['profile_sha256'], digest(output/'profile.json'))
            # The extracted-directory entry point is real and preserves the same
            # frozen originals, even when a one-task output is requested.
            selected = Path(tmp)/'selected'
            export.export_vectors(output, selected, tasks=1)
            self.assertEqual((selected/'layer_00/y.mem').read_bytes(),
                             (output/'layer_00/y.mem').read_bytes())
            self.assertEqual(json.loads((selected/'profile.json').read_text())['w']['bytes'], 65536)

    def test_helper_covers_signed_ties_all_positions_and_task_boundaries_without_mac(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            synthetic(root)
            originals = {p: p.read_bytes() for p in root.glob('layer_*/*.mem')}
            with patch.object(s3, 'linear99x64x256', side_effect=AssertionError('inference called')), \
                 patch.object(legacy, 'linear99x64x256', side_effect=AssertionError('MAC called')):
                profile = export.add_s3_files(root, 2)
            self.assertEqual(profile['w']['layout'], 'row_major_signed16_in_32bit_slot')
            for layer in range(2):
                target = root/('layer_%02d' % layer)
                old = legacy.read_hex_mem(target/'y.mem', 48)
                self.assertEqual(legacy.read_hex_mem(target/'y32.mem', 32),
                                 [round(Fraction(value, 512)) for value in old])
                flat = legacy.read_hex_mem(target/'w.mem', 16)
                actual = [int(v, 16) for v in (target/'w_packed16.mem').read_text().splitlines()]
                self.assertEqual(actual, [(flat[i] & 65535) | ((flat[i+1] & 65535) << 16)
                                          for i in range(0, 16384, 2)])
                self.assertTrue(all(len(line)==8 for line in (target/'y32.mem').read_text().splitlines()))
            for path, original in originals.items():
                self.assertEqual(path.read_bytes(), original)
            before = {p: p.stat().st_mtime_ns for p in root.rglob('*') if p.is_file()}
            self.assertEqual(export.add_s3_files(root, 2), profile)
            self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_existing_artifact_or_profile_conflict_is_rejected_without_overwrite(self):
        for artifact in ['layer_00/y32.mem', 'layer_00/w_packed16.mem', 'profile.json']:
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                synthetic(root, 1)
                export.add_s3_files(root, 1)
                path = root/artifact
                path.write_bytes(b'conflict\n')
                with self.assertRaisesRegex(ValueError, 'existing S3 artifact differs'):
                    export.add_s3_files(root, 1)
                self.assertEqual(path.read_bytes(), b'conflict\n')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            synthetic(root, 1)
            export.add_s3_files(root, 1)
            with self.assertRaises(ValueError):
                export.add_s3_files(root, 1, True)

    def test_unknown_wrong_shape_and_unreachable_y_reject_before_generated_writes(self):
        for kind in ['count', 'unknown', 'domain']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                synthetic(root, 1)
                path = root/'layer_00/y.mem'
                lines = path.read_text().splitlines()
                if kind == 'count':
                    lines.pop()
                elif kind == 'unknown':
                    lines[0] = 'xxxxxxxxxxxx'
                else:
                    lines[0] = '%012x' % (s3.Y48_MAX+1)
                path.write_text('\n'.join(lines)+'\n')
                with self.assertRaises(ValueError):
                    export.add_s3_files(root, 1)
                self.assertFalse((root/'layer_00/y32.mem').exists())
                self.assertFalse((root/'profile.json').exists())

    def test_cli_validates_all_frozen_tasks_even_for_one_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root/'old'
            export.export_vectors(export.ARCHIVE, old)
            (old/'layer_11/w.mem').write_bytes(b'changed\n')
            target = root/'new'
            with self.assertRaisesRegex(ValueError, 'layer_11/w.mem'):
                export.export_vectors(old, target, tasks=1)
            self.assertFalse(target.exists())
            archive = root/'bad.tar.gz'
            archive.write_bytes(export.ARCHIVE.read_bytes()+b'changed')
            with self.assertRaisesRegex(ValueError, 'frozen 12-task archive'):
                export.export_vectors(archive, target, tasks=1)

    def test_parameters_and_existing_output_are_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for tasks in [0, 13, True, 1.0]:
                with self.assertRaises(ValueError):
                    export.add_s3_files(root, tasks)
            with self.assertRaises(TypeError):
                export.add_s3_files(root, 1, 1)
            with self.assertRaisesRegex(ValueError, 'already exists'):
                export.export_vectors(export.ARCHIVE, root, 1)


if __name__ == '__main__':
    unittest.main()
