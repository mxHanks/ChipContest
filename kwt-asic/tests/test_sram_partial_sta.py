"""Reference STA completion is separate from setup/hold/removal acceptance."""
import importlib.util
from pathlib import Path
import sys
import unittest

SYNTH=Path(__file__).resolve().parents[1]/'scripts/synth'
sys.path.insert(0,str(SYNTH))
spec=importlib.util.spec_from_file_location('sram_partial_sta',SYNTH/'run_memory_partial_sta.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


def minimum(kind,slack,endpoint='reg2'):
    return f'Startpoint: reg1\nEndpoint: {endpoint}\nPath Type: min\n0.1 library {kind} time\n{slack:.6f} slack (VIOLATED)\n'


class SRAMPartialSTAGates(unittest.TestCase):
    def test_default_library_wire_load_must_be_recorded_not_claimed_absent(self):
        self.assertTrue(hasattr(S,'reference_wire_load'),'Liberty default wire load is not audited')
        text='wire_load("actual_model") { capacitance : 0.1; } default_wire_load : "actual_model";'
        self.assertEqual(S.reference_wire_load(text),'actual_model')
        with self.assertRaises(ValueError):S.reference_wire_load('default_wire_load : "missing";')

    def metrics(self,setup=1.0,min_text=None,data_text=None):
        self.assertTrue(hasattr(S,'timing_metrics'),'explicit minimum-check classification is missing')
        log=f'wns {min(setup,0):.6f}\ntns {min(setup,0):.6f}\nworst slack {setup:.6f}\n'
        return S.timing_metrics(log,min_text or minimum('hold',0.01),data_text or minimum('hold',0.01))

    def test_positive_setup_does_not_hide_removal_violation(self):
        result=self.metrics(min_text=minimum('removal',-0.255385))
        self.assertEqual(result['covered_path_status'],'FAIL')
        self.assertEqual(result['minimum_check_categories']['removal']['worst_slack_ns'],-0.255385)
        self.assertEqual(result['reference_data_hold_worst_slack_ns'],0.01)

    def test_setup_or_data_hold_failure_rejects_local_timing(self):
        self.assertEqual(self.metrics(setup=-0.1)['covered_path_status'],'FAIL')
        self.assertEqual(self.metrics(data_text=minimum('hold',-0.1))['covered_path_status'],'FAIL')

    def test_positive_local_paths_still_only_reference_assumptions(self):
        self.assertEqual(self.metrics()['covered_path_status'],'PASS_UNDER_REFERENCE_ASSUMPTIONS')

    def test_missing_truncated_or_unrecognized_metrics_rejected(self):
        for bad in ('','Startpoint: a\nEndpoint: b\n'):
            self.assertTrue(hasattr(S,'timing_metrics'))
            with self.assertRaises(ValueError):S.timing_metrics('wns 0\ntns 0\nworst slack 1\n',bad,bad)
        with self.assertRaises(ValueError):S.timing_metrics('wns nan\n',minimum('hold',1),minimum('hold',1))

    def test_error_or_duplicate_marker_rejected_even_with_zero_exit(self):
        self.assertTrue(hasattr(S,'accept_sta_log'),'native STA completion gate is missing')
        command={'exit_code':0,'timed_out':False}
        S.accept_sta_log(command,S.MARKER+'\n')
        for text in (S.MARKER+'\nError: missing clock\n',S.MARKER+'\n'+S.MARKER+'\n'):
            with self.assertRaises(RuntimeError):S.accept_sta_log(command,text)


if __name__=='__main__':unittest.main()
