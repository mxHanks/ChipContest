"""Protocol/count/physical-time guards; no fixture is a physical PPA result."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from fractions import Fraction

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('s3_activity_ppa',ROOT/'tools/scripts/xu_soc_ppa.py')
ppa=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(ppa)
SPEC=importlib.util.spec_from_file_location('s3_activity_adapter',ROOT/'tools/ppa/s3_soc_activity_profile.py')
adapter=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(adapter)
SPEC=importlib.util.spec_from_file_location('s3_activity_convert',ROOT/'tools/ppa/s3_activity_convert.py')
convert=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(convert)


class S3ActivityContractTests(unittest.TestCase):
    def test_y48_control_and_y32_contract_are_selected_by_explicit_schedule(self):
        baseline=ppa.s3_transaction_contract(ROOT,'bias-hw-autogroup-paired-hi-window')
        new=ppa.s3_transaction_contract(ROOT,'bias-hw-autogroup-y32-packed16-nice-window')
        self.assertEqual(baseline['shared_writes'],50688)
        self.assertEqual(new['shared_writes'],25344)
        self.assertEqual(baseline['macs'],new['macs'])
        self.assertEqual(baseline['w_shared_reads'],16384)
        self.assertEqual(new['w_shared_reads'],8192)
        self.assertEqual(new['nice_oitf_retired'],3168)
        with self.assertRaises(ValueError):ppa.s3_transaction_contract(ROOT,None)

    def test_long_quantized_window_requires_exact_declared_period_budget(self):
        cycles=586991
        for name in ppa.S3_CLOCK_PROFILES:
            policy=ppa.S3_CLOCK_PROFILES[name]
            period=Fraction(policy['period_fs_numerator'],policy['period_fs_denominator'])
            span=(cycles-1)*period
            duration=span.numerator//span.denominator
            ticks=[100000000000,100000000000+duration]
            record=dict(clock_profile=policy,clock_period_ns=float(period/1000000),
                        windows_fs=[ticks],windows_ns=[[value/1000000 for value in ticks]])
            impl=dict(activity_clock_profile=name)
            ppa.s3_activity_windows(impl,record,[dict(cycles=cycles)])
            bad=copy.deepcopy(record);bad['windows_fs'][0][1]+=3;bad['windows_ns'][0][1]+=3e-6
            with self.assertRaisesRegex(ValueError,'bounded actual clock phase'):
                ppa.s3_activity_windows(impl,bad,[dict(cycles=cycles)])
            if 'quantized' in name:
                nominal=(cycles-1)*Fraction(20000000,3)
                self.assertGreater(abs(Fraction(duration)-nominal)/1000000,Fraction(3,100))
                with self.assertRaisesRegex(ValueError,'profile/budget differs'):
                    ppa.s3_activity_windows(dict(activity_clock_profile='nominal150-balanced-v1'),record,[dict(cycles=cycles)])

    def test_native_zero_vendor_error_with_space_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError,'EDA execution failed'):
                ppa.run_tool(Path(temporary),[sys.executable,'-c',
                    'print("Error vendor_sva_assertion"); print("XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED")'],
                    'dc',dict(os.environ))

    def test_snapshot_binds_actual_copied_bytes_and_rejects_source_races(self):
        for changed in (None,'repo','copied-stage'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as temporary:
                base=Path(temporary);repo=base/'repo';stage=base/'stage'
                (repo/'tools/ppa').mkdir(parents=True);stage.mkdir()
                (repo/'runtime.py').write_text('frozen runtime\n')
                (repo/'tools/ppa/s3_task_campaign.py').write_text('frozen campaign\n')
                (stage/'campaign.py').write_text('frozen campaign\n')
                model=base/'external-model.sv';model.write_text('generic non-PPA\n')
                def freeze(_):
                    return dict(source_files={p.relative_to(repo).as_posix():dict(sha256=ppa.sha(p))
                                for p in repo.rglob('*') if p.is_file()})
                extension=adapter.S3ActivityExtension.__new__(adapter.S3ActivityExtension)
                extension.EXTRA=['runtime.py'];extension.model=model
                extension.model_kind='generic-prototype';extension.model_sha=ppa.sha(model)
                extension.ppa=mock.Mock(sha=ppa.sha,s3_worktree_sources=freeze)
                extension.freeze=freeze(repo)
                if changed=='repo':(repo/'runtime.py').write_text('changed during copy\n')
                if changed=='copied-stage':(stage/'campaign.py').write_text('unbound copied bytes\n')
                if changed is None:
                    extension.snapshot(repo,stage)
                    self.assertEqual(json_load(stage/'s3-full-source-freeze.json'),extension.freeze)
                else:
                    with self.assertRaisesRegex(ValueError,'source changed|input differs'):
                        extension.snapshot(repo,stage)

    def test_native_generate_scope_is_normalized_without_rewriting_other_identifiers(self):
        raw='tb_accel_soc/dut/u_shared/storage/macro_storage.depth_bank[100].width_lane[1].macro/CLK'
        expected='tb_accel_soc/dut/u_shared/storage/macro_storage/depth_bank[100]/width_lane[1]/macro/CLK'
        self.assertEqual(convert.canonical_macro_path(raw),expected)
        self.assertEqual(convert.canonical_macro_path(expected),expected)
        self.assertEqual(convert.canonical_macro_path('dut/user.dotted_identifier/Q'),'dut/user.dotted_identifier/Q')

    def test_clear_gap_payload_partition_matches_original_observer_and_clock(self):
        item=dict(clear=dict(gap_to_source_request='102'),activity=dict(windows=dict(
            clear=dict(begin=dict(cycle=1201688,tick_fs=8011256666667),
                       end=dict(cycle=1400103,tick_fs=9334023333333)),
            payload=dict(begin=dict(cycle=1400205,tick_fs=9334703333333),
                         end=dict(cycle=1987195,tick_fs=13247970000000)))))
        windows,continuous=convert.phase_windows(item)
        self.assertEqual(windows['abi_control_gap']['duration_fs'],680000000)
        self.assertEqual(continuous['period_intervals'],785507)
        self.assertEqual(continuous['duration_fs'],5236713333333)
        bad=copy.deepcopy(item);bad['clear']['gap_to_source_request']='103'
        with self.assertRaisesRegex(ValueError,'gap differs'):convert.phase_windows(bad)
        bad=copy.deepcopy(item);bad['activity']['windows']['payload']['end']['tick_fs']+=3
        with self.assertRaisesRegex(ValueError,'one-fs budget'):convert.phase_windows(bad)


def json_load(path):
    import json
    return json.loads(path.read_text())


if __name__=='__main__':unittest.main()
