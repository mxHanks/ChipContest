#!/usr/bin/env python3
"""Regression of actual native empty-source reports, without any EDA launch."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common164 import identity, read
import primary164 as primary


class Source164(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='xu164-source-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'source.rpt'
        self.pins = {'u_ram/Q[0]', 'u_ram/CLK'}

    def parse(self, text, source='propagated'):
        self.path.write_bytes(text)
        return primary.source_membership(self.path, identity(self.path), self.pins, source)

    def test_minimal_fixture_reproduces_frozen156_failure_but164_proves_empty(self):
        text = b'No nets found with activity info from propagated\n1'
        self.path.write_bytes(text)
        frozen = HERE/'frozen156'
        sys.path.insert(0, str(frozen))
        try:
            spec = importlib.util.spec_from_file_location('frozen_primary156', str(frozen/'primary156.py'))
            legacy = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy)
        finally:
            sys.path.remove(str(frozen))
        with self.assertRaisesRegex(ValueError, 'complete source-report streaming identity differs'):
            legacy.source_membership(self.path, identity(self.path), self.pins)
        result, matches = primary.source_membership(self.path, identity(self.path), self.pins, 'propagated')
        self.assertEqual(matches, {})
        self.assertEqual(result['native_declaration']['mode'], 'NATIVE_EXPLICIT_EMPTY_LIST')
        self.assertEqual(result['complete_source_bytes_streamed'], len(text))
        self.assertEqual(result['stream_sha256'], hashlib.sha256(text).hexdigest())
        self.assertEqual(result['original_before'], result['original_after'])

    def test_actual_archived_own130_empty_native_report_bytes(self):
        report = HERE/'fixtures/source-propagated-before.rpt'
        actual = identity(report)
        self.assertEqual(actual['bytes'], 6204)
        self.assertEqual(actual['sha256'], 'ee0cabb0db67061edc197cc1e69241e591f888154bf272ba1093c309f9c54efd')
        result, matches = primary.source_membership(report, actual, self.pins, 'propagated')
        self.assertEqual(matches, {})
        self.assertEqual(result['native_row_count'], 0)
        self.assertEqual(result['native_declaration']['raw_text'], 'No nets found with activity info from propagated\n')
        self.assertEqual(result['complete_source_bytes_streamed'], actual['bytes'])
        self.assertEqual(result['stream_sha256'], actual['sha256'])

    def test_every_original_empty_source_label_is_precisely_bound(self):
        for selector, label in primary.SOURCE_LABELS.items():
            result, matches = self.parse(('No nets found with activity info from '+label+'\n1').encode(), selector)
            self.assertEqual(result['requested_source'], selector)
            self.assertEqual(matches, {})
        with self.assertRaisesRegex(ValueError, 'requested selector'):
            self.parse(b'No nets found with activity info from file\n1', 'propagated')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            self.parse(b'No nets found with activity info from file\n1', 'unknown')

    def test_nonempty_count_footer_and_saved_driver_column(self):
        text = (b'header\nList of nets with activity from file\n'
                b'\tu_ram/Q[0] \tunrelated\n\tnet \tu_ram/Q[0]\n'
                b'\n2 nets with activity info from file\n1')
        result, matches = self.parse(text, 'file')
        self.assertEqual(set(matches), {'u_ram/Q[0]'})
        self.assertEqual(result['native_row_count'], 2)
        raw = matches['u_ram/Q[0]'][0]
        self.assertEqual(text[raw['report_byte_start']:raw['report_byte_end']], raw['raw_text'].encode())
        self.assertEqual(result['native_footer']['row_count'], 2)

    def test_missing_empty_or_nonempty_completeness_is_not_accepted(self):
        variants = [b'header only\n1',
                    b'List of nets with activity from propagated\n1',
                    b'List of nets with activity from propagated\n\tnet\tu_ram/Q[0]\n',
                    b'List of nets with activity from propagated\n\tnet\tu_ram/Q[0]\n2 nets with activity info from propagated\n1',
                    b'No nets found with activity info from propagated\n\tnet\tu_ram/Q[0]\n1',
                    b'No nets found with activity info from propagated\nList of nets with activity from propagated\n1',
                    b'No nets found with activity info from propagated\nNo nets found with activity info from propagated\n1',
                    b'Error: native source command failed\nNo nets found with activity info from propagated\n1']
        for text in variants:
            with self.subTest(text=text):
                with self.assertRaises(ValueError): self.parse(text)

    def test_stream_digest_covers_headers_and_tail_without_whole_report_reads(self):
        original = b'opaque native header\nNo nets found with activity info from propagated\n1'
        self.path.write_bytes(original); expected = identity(self.path)
        # Defeat only the redundant before/after helper, leaving the independent
        # line-stream SHA to prove that header and tail bytes cannot be omitted.
        for text in (b'changed header\n'+original, original+b'changed tail'):
            self.path.write_bytes(text)
            with patch.object(primary, 'check', return_value=expected):
                with self.assertRaisesRegex(ValueError, 'streaming identity'):
                    primary.source_membership(self.path, expected, self.pins, 'propagated')
        self.path.write_bytes(original)
        orig_text, orig_bytes = Path.read_text, Path.read_bytes
        def no_text(path, *args, **kwargs):
            if path == self.path: raise AssertionError('whole source-report text read')
            return orig_text(path, *args, **kwargs)
        def no_bytes(path, *args, **kwargs):
            if path == self.path: raise AssertionError('whole source-report byte read')
            return orig_bytes(path, *args, **kwargs)
        with patch.object(Path, 'read_text', no_text), patch.object(Path, 'read_bytes', no_bytes):
            result, _ = primary.source_membership(self.path, expected, self.pins, 'propagated')
        self.assertEqual(result['stream_sha256'], expected['sha256'])

    def test_actual_archived_own130_nonempty_sources_have_all_rows_counted(self):
        base = HERE.parent/'xu-score-resume-20261103'
        root = base/'progress135/s2e-full-soc-power12-20261105-130/task_00'
        receipt = base/'terminal151/s2e-full-soc-power12-20261105-130/execution.json'
        if not receipt.exists() or not root.exists():
            self.skipTest('actual own130 local archive unavailable')
        task = read(receipt)['tasks'][0]
        for source in ('file', 'default', 'propagated'):
            path = root/('source-'+source+'-before.rpt')
            original = task['reports'][path.name]; local = identity(path)
            self.assertEqual((local['bytes'],local['sha256']), (original['bytes'],original['sha256']))
            result, matches = primary.source_membership(path, local, self.pins, source)
            self.assertEqual(result['complete_source_bytes_streamed'], original['bytes'])
            self.assertEqual(result['native_row_count'], {'file':49759,'default':1100,'propagated':0}[source])
            self.assertEqual(matches, {})


if __name__ == '__main__': unittest.main()
