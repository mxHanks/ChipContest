"""Meaningful negative checks for the independent saved-evidence verifier.

No campaigns are rewritten. Conditions are mutated only in loaded Python values,
and raw-marker checks receive deliberately damaged in-memory strings.
"""
from pathlib import Path
import copy
import importlib.util
import json
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('postflow_compare',HERE/'postflow_compare.py')
verify=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class PostflowVerifierNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins=verify.read_json(HERE/'baseline8-sourcepins.json')
        cls.pairs=verify.read_json(HERE/'stream8-task0-sourcepairs.json')
        cls.base=verify.load_campaign(ROOT/'build/writeback-v2-20261108/direct-task0-phase/result.json',
                                    'direct-pe8',cls.pins)
        cls.candidate_path=HERE/'stream8-task0/result.json'
        cls.candidate_pins=verify.pinned_candidate_sources(cls.pins,cls.pairs)
        cls.candidate=verify.load_campaign(cls.candidate_path,'stream32-pe8',cls.candidate_pins)
        cls.raw_report=verify.read_json(cls.candidate_path)
        cls.raw_log=(cls.candidate_path.parent/'task-00/simulation.log').read_text()
        cls.task=cls.raw_report['task_results'][0]
        cls.parser=verify.load_pinned_parser(cls.candidate_path.parent,cls.candidate_pins)

    def test_real_stream_evidence_and_final_response_marker_pass(self):
        result=verify.compare(self.base,self.candidate,self.pairs)
        self.assertEqual(result['totals']['delta']['payload_cycles'],-21483)
        self.assertTrue(result['firmware_identity']['independent_load_verification']['candidate']['verified'])

    def test_unpinned_source_is_rejected_before_parser_import(self):
        pins=dict(self.candidate_pins);pins['rtl/subsys/xu_nice_drain8.v']='0'*64
        with self.assertRaisesRegex(ValueError,'externally pinned'):
            verify.load_campaign(self.candidate_path,'stream32-pe8',pins)

    def test_wrong_explicit_instruction_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'schedule differs'):
            verify.load_campaign(self.candidate_path,'batch16-pe8',self.candidate_pins)

    def test_wrong_physical_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'physical core source SHA'):
            verify.load_campaign(self.candidate_path,'stream32-pe16',self.candidate_pins)

    def test_undeclared_source_pair_rejected(self):
        pairs=dict(self.pairs);pairs.pop('rtl/subsys/xu_nice_drain8.v')
        with self.assertRaisesRegex(ValueError,'exact reviewed SHA pairs'):
            verify.compare(self.base,self.candidate,pairs)

    def test_extra_macro_or_selector_rejected(self):
        for step_name,arg in [('firmware-build','-DXU_NICE_DRAIN16=1'),
                              ('task-00/simulation','+NICE_BATCH16=1')]:
            value=copy.deepcopy(self.candidate)
            step=next(x for x in value['conditions']['commands'] if x['name']==step_name)
            step['command'].append(arg)
            with self.assertRaisesRegex(ValueError,'exact transport'):
                verify.compare(self.base,value,self.pairs)

    def test_clock_or_clear_recipe_change_rejected(self):
        for key in ['clock_configuration','clear_recipe_configuration']:
            value=copy.deepcopy(self.candidate)
            value['conditions'][key]['unexpected-change']=1
            with self.assertRaisesRegex(ValueError,'conditions differ'):
                verify.compare(self.base,value,self.pairs)

    def test_clear_generated_program_change_rejected(self):
        value=copy.deepcopy(self.candidate)
        value['generated_clear_c_identity']['normalized_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'generated clear C'):
            verify.compare(self.base,value,self.pairs)

    def test_bad_final_response_count_and_duplicate_marker_rejected(self):
        marker=next(x for x in self.raw_log.splitlines() if x.startswith('STREAM_TASK '))
        for malformed in [self.raw_log.replace('final_response_before_completion=1',
                                                'final_response_before_completion=0'),
                          self.raw_log+'\n'+marker+'\n',
                          self.raw_log.replace('groups=3168','groups=3167')]:
            with self.assertRaises(ValueError):
                verify.profile_markers(malformed,self.task,verify.STREAM_SCHEDULE,
                                       verify.PROFILES['stream32-pe8'],self.parser)


if __name__=='__main__':
    unittest.main()
