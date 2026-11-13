"""Protocol/numeric regression tests. Synthetic WAV headers are parser-only fixtures."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest
import wave

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import export_audio_manifest as audio
import import_integer_vectors as integer
import verify_vectors


def make_manifest(root):
    data = root / 'audio'
    target = data / 'yes'
    target.mkdir(parents=True)
    name = next('speaker_%d_nohash_0.wav' % i for i in range(1000)
                if audio.original_split('speaker_%d_nohash_0.wav' % i) == 'validation')
    wav = target / name
    with wave.open(str(wav), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(struct.pack('<hhhh', 1, -2, 3, -4))
    manifest = dict(schema=audio.MANIFEST_SCHEMA, purpose='development_validation', dataset_root=str(data),
        samples=[dict(sample_id='parser-only', kind='wav', label='yes', split='validation',
                      path='yes/' + name, sha256=audio.digest(wav))],
        tasks=[dict(task_id=0, sample_id='parser-only', layer_id=0)])
    path = root / 'manifest.json'
    audio.write_json(path, manifest)
    return path, manifest, wav


class NumericEntryTests(unittest.TestCase):
    def test_parser_records_sha_label_split_and_original_crop_input_length(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, _, _ = make_manifest(Path(temporary))
            _, _, samples = audio.validate_manifest(path)
            self.assertEqual(samples[0]['original_frames'], 4)
            self.assertEqual(samples[0]['label_index'], 2)

    def test_changed_wav_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, _, wav = make_manifest(Path(temporary))
            wav.write_bytes(wav.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                audio.validate_manifest(path)

    def test_symlink_and_traversal_rejected_even_when_expected_sha_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, manifest, wav = make_manifest(root)
            payload = wav.read_bytes()
            outside = root / 'outside.wav'
            outside.write_bytes(payload)
            wav.unlink()
            wav.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                audio.validate_manifest(path)
            manifest['samples'][0]['path'] = '../outside.wav'
            audio.write_json(path, manifest)
            with self.assertRaises(ValueError):
                audio.validate_manifest(path)

    def test_no_test_split_for_development_and_no_faked_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, manifest, _ = make_manifest(Path(temporary))
            for key, value in [('split', 'testing'), ('label', 'go'), ('kind', 'silence_zero')]:
                broken = copy.deepcopy(manifest)
                broken['samples'][0][key] = value
                audio.write_json(path, broken)
                with self.assertRaises(ValueError):
                    audio.validate_manifest(path)

    def test_no_silence_only_cpu_test_or_duplicate_task_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, manifest, _ = make_manifest(Path(temporary))
            manifest['samples'].append(dict(sample_id='silence', kind='silence_zero', label='_silence_',
                                            split='synthetic_silence'))
            manifest['tasks'][0]['sample_id'] = 'silence'
            audio.write_json(path, manifest)
            with self.assertRaisesRegex(ValueError, 'only of silence'):
                audio.validate_manifest(path)
            manifest['tasks'][0]['sample_id'] = 'parser-only'
            manifest['tasks'].append(copy.deepcopy(manifest['tasks'][0]))
            audio.write_json(path, manifest)
            with self.assertRaisesRegex(ValueError, 'consecutive'):
                audio.validate_manifest(path)

    def test_twelve_tasks_require_each_model_layer_and_allow_one_sample_many_layers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, manifest, _ = make_manifest(Path(temporary))
            manifest['tasks'] = [dict(task_id=i, sample_id='parser-only', layer_id=i) for i in range(12)]
            audio.write_json(path, manifest)
            audio.validate_manifest(path)
            manifest['tasks'][-1]['layer_id'] = 0
            audio.write_json(path, manifest)
            with self.assertRaisesRegex(ValueError, 'all 12 layer'):
                audio.validate_manifest(path)

    def test_declared_official_source_does_not_create_formal_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            path, manifest, _ = make_manifest(Path(temporary))
            manifest['purpose'] = 'official_evaluation'
            audio.write_json(path, manifest)
            data, _, _ = audio.validate_manifest(path)
            self.assertEqual(data['purpose'], 'official_evaluation')
            self.assertNotIn('official_acceptance', data)

    def test_s3_exact_ties_extrema_and_numpy_vector_path(self):
        result = audio.check_rne_without_dependencies()
        self.assertEqual(result['values'], 92)
        import numpy as np
        rng = random.Random(20261113)
        values = [audio.s3.Y48_MIN, audio.s3.Y48_MAX, -1280, -768, -256, 256, 768, 1280]
        values += [rng.randrange(audio.s3.Y48_MIN, audio.s3.Y48_MAX + 1) for _ in range(2000)]
        actual = audio.integer_y32(np.asarray(values, dtype=np.int64), np).tolist()
        self.assertEqual(actual, [audio.s3.quantize_result(value) for value in values])
        decoded = np.ldexp(np.asarray(actual, dtype=np.float64), -18).tolist()
        self.assertEqual(decoded, [float(audio.s3.decode_result(value)) for value in actual])
        with self.assertRaises(ValueError):
            audio.integer_y32(np.asarray([audio.s3.Y48_MAX + 1], dtype=np.int64), np)

    def test_integer_dev_acknowledgement_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, '--dev'):
                integer.convert(Path(temporary) / 'missing', Path(temporary) / 'out', 12, False)

    def test_speaker_grouping_matches_original_hash_formula(self):
        self.assertEqual(audio.original_split('yes/a_nohash_0.wav'), audio.original_split('no/a_nohash_9.wav'))
        self.assertEqual(audio.original_split('a_nohash_0.wav'), audio.original_split('a_nohash_100.wav'))

    def test_entry_syntax_is_python38_compatible(self):
        for path in HERE.glob('*.py'):
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 8))


if __name__ == '__main__':
    unittest.main()
