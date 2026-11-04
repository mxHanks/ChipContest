"""Actual returned native log parser tests; no local server/EDA proof claim."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('xu_s2e_formal109_tests',ROOT/'tools/ppa/xu_s2e_formality_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
LOG=Path(os.environ['XU_S2E_NATIVE_FM_LOG']) if os.environ.get('XU_S2E_NATIVE_FM_LOG') else None
EVIDENCE=Path(os.environ['XU_S2E_FORMAL_AUDIT_EVIDENCE']) if os.environ.get('XU_S2E_FORMAL_AUDIT_EVIDENCE') else None


def save(name,value):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        (EVIDENCE/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


class SyntaxAndFreeze(unittest.TestCase):
    def test_python36_syntax(self):
        ast.parse((ROOT/'tools/ppa/xu_s2e_formality_audit.py').read_text(),feature_version=(3,6))

    def test_actual159_file_rehash_rejects_changed_bytes_and_receipts(self):
        with tempfile.TemporaryDirectory(prefix='xu-fm109-host-freeze-') as temporary:
            root=Path(temporary);records={}
            for index in range(159):
                path=root/('host-fixture-%03d'%index);path.write_bytes(b'explicit host file, not original EDA evidence\n')
                records[str(path)]=audit.identity(path)
            audit.checked_records(records,'host159')
            path=Path(sorted(records)[37]);data=path.read_bytes();path.write_bytes(b'X'+data[1:])
            with self.assertRaisesRegex(ValueError,'actual file changed'):audit.checked_records(records,'host159')
            path.write_bytes(data);audit.checked_records(records,'host159')
            key=str(path);records[key]=dict(records[key],sha256='0'*64)
            with self.assertRaisesRegex(ValueError,'actual file changed'):audit.checked_records(records,'host159')
            save('host-frozen-mutants.json',dict(status='HOST159_INITIAL_AND_RESTORED_PASS_BYTE_AND_RECEIPT_MUTANTS_REJECTED',
                 limitations='Host fixture only; actual159 original EDA inputs require server109 rehash.'))


@unittest.skipUnless(LOG,'explicit actual returned XU_S2E_NATIVE_FM_LOG required')
class NativeOriginalLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=LOG.read_bytes()
        if hashlib.sha256(cls.raw).hexdigest()!=audit.LOG_SHA:raise ValueError('actual returned original log hash differs')
        cls.text=cls.raw.decode()

    def test_actual_native_success_and_exact_old_newline_false_failure(self):
        old=re.findall(r'^XU_S2E_FULL_SOC_FORMALITY_PASS\s*$',self.text,re.M)
        self.assertEqual(old,['XU_S2E_FULL_SOC_FORMALITY_PASS\n'])
        result=audit.native_result(self.text,0)
        self.assertEqual(result['passing'],42338)
        self.assertEqual((result['unread_dff'],result['unmatched_reference_dff']),(511,17))
        save('actual-native-parser.json',dict(status='RETURNED_NATIVE_LOG_PARSED_NOT_SERVER_REHASH',log_sha256=audit.LOG_SHA,
             old_regex_result=old,native=result))

    def test_terminal_newlines_and_horizontal_spaces_never_change_capture(self):
        marker='XU_S2E_FULL_SOC_FORMALITY_PASS'
        for suffix in ['','\n','\n\n',' \t\n',' \t\n\n']:
            text=re.sub(r'^'+marker+r'[ \t]*\n?',marker+suffix,self.text,flags=re.M)
            self.assertEqual(audit.native_result(text)['passing'],42338)
        save('marker-horizontal-whitespace.json',dict(status='FIVE_TERMINAL_WHITESPACE_CASES_PASS'))

    def test_native_markers_failures_counts_and_full_scope_mutants_are_rejected(self):
        variants={
            'duplicate_terminal':self.text+'\nXU_S2E_FULL_SOC_FORMALITY_PASS\n',
            'missing_terminal':self.text.replace('\nXU_S2E_FULL_SOC_FORMALITY_PASS\n','\n'),
            'explicit_fail':self.text+'\nXU_S2E_FULL_SOC_FORMALITY_FAIL\n',
            'script_error':self.text+'\nXU_S2E_FULL_SOC_FORMALITY_SCRIPT_ERROR host mutant\n',
            'native_error':self.text+'\nError: host mutant\n',
            'native_fatal':self.text+'\nFatal: host mutant\n',
            'native_failure':self.text.replace('Verification SUCCEEDED','Verification FAILED'),
            'duplicate_success':self.text+'\nVerification SUCCEEDED\n',
            'missing_success':self.text.replace('Verification SUCCEEDED','host removed success'),
            'wrong_count':self.text.replace('42338 Passing compare points','42337 Passing compare points'),
            'wrong_reference':self.text.replace(' Reference design: r:/WORK/xu_soc_ppa_top',' Reference design: r:/WORK/other_top'),
            'wrong_impl':self.text.replace(' Implementation design: i:/WORK/xu_soc_ppa_top',' Implementation design: i:/WORK/other_top'),
            'wrong_passing_breakdown':self.text.replace('17136       0','17135       0'),
            'aborted':self.text+'\n1 Aborted compare points\n',
            'unverified':self.text+'\n1 Unverified compare points\n',
        }
        rejected=[]
        for name,text in variants.items():
            self.assertNotEqual(text,self.text,name)
            with self.assertRaises(ValueError,msg=name):audit.native_result(text)
            rejected.append(name)
        with self.assertRaisesRegex(ValueError,'return code'):audit.native_result(self.text,1)
        save('actual-native-mutants.json',dict(status='ALL16_NATIVE_MUTANTS_REJECTED',rejected=rejected+['returncode']))

    def test_unrelated_mutated_native_bytes_are_rejected_by_original_hash_binding(self):
        with tempfile.TemporaryDirectory(prefix='xu-fm109-native-binding-') as temporary:
            path=Path(temporary)/'native.log';path.write_bytes(self.raw)
            record=audit.identity(path);audit.checked_records({str(path):record},'native host copy')
            path.write_bytes(self.raw+b'\n// unrelated changed byte must not reuse original receipt\n')
            self.assertEqual(audit.native_result(path.read_text())['passing'],42338)
            with self.assertRaisesRegex(ValueError,'actual file changed'):
                audit.checked_records({str(path):record},'native host copy')
            save('actual-native-byte-binding.json',dict(status='UNCHANGED_HASH_PASS_UNRELATED_CHANGED_BYTES_REJECTED',
                 limitations='Copy of original native log; actual originals were not edited.'))


if __name__=='__main__':unittest.main()
