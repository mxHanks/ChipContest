import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xu206', str(HERE / 'diagnose206.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ActualFailureReplay(unittest.TestCase):
    def test_actual177_required_report_guard(self):
        root = HERE / 'original191' / m.ROOTS['177']
        state = m.read(root / 'state.json')
        result = m.replay(m.load('frozen177.py'), '177', root, state)
        self.assertEqual(result['stage'], 'review_reports')
        self.assertEqual(result['exception'], 'required read-only report is unavailable')

    def test_actual186_native_abort_guard(self):
        root = HERE / 'original191' / m.ROOTS['186']
        state = m.read(root / 'state.json')
        result = m.replay(m.load('frozen186.py'), '186', root, state)
        self.assertEqual(result['stage'], 'inspect_log')
        self.assertEqual(result['exception'], 'native returncode/unique actual marker differs')

    def test_bad_native_returncode_cannot_pass(self):
        api = m.load('frozen177.py')
        original = HERE / 'original191' / m.ROOTS['177'] / 'pt.log'
        with self.assertRaisesRegex(ValueError, 'returncode'):
            api.inspect_log(original.read_text(), 1)

    def test_missing_completion_marker_cannot_pass(self):
        api = m.load('frozen177.py')
        original = HERE / 'original191' / m.ROOTS['177'] / 'pt.log'
        text = original.read_text().replace(api.MARKER, 'MISSING_COMPLETION_MARKER')
        with self.assertRaisesRegex(ValueError, 'completion marker'):
            api.inspect_log(text, 0)

    def test_empty_partial_status_is_retained(self):
        root = HERE / 'original191' / m.ROOTS['186']
        self.assertEqual((root / 'query-status.tsv').stat().st_size, 0)
        self.assertEqual(m.status_rows(root / 'query-status.tsv'), [])

    def test_malformed_status_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'status.tsv'
            p.write_text('report\tcatch_code\tmessage\na\t0\n')
            with self.assertRaisesRegex(ValueError, 'malformed'):
                m.status_rows(p)


if __name__ == '__main__':
    unittest.main()
