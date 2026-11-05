#!/usr/bin/env python3
"""Focused scheduler boundary checks; fake files/processes only, no EDA."""
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('batch138',str(HERE/'batch138.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Guards(unittest.TestCase):
 def setUp(self):
  self.plan=m.validate_plan(m.read(HERE/'queue-plan138.json'));self.g=copy.deepcopy(self.plan['guards']);self.res={'mem_available_bytes':10**15,'disk_available_bytes':10**15,'native_processes':[]};self.ext=[]
 def test_exact_eight(self):
  p=copy.deepcopy(self.plan);p['candidates'].pop()
  with self.assertRaises(ValueError):m.validate_plan(p)
 def test_malformed_phase_command(self):
  p=copy.deepcopy(self.plan);p['candidates'][0]['phases'][2]['argv']='pt_shell -f file'
  with self.assertRaises(ValueError):m.validate_plan(p)
 def test_command_requires_inputs_marker(self):
  p=copy.deepcopy(self.plan);p['candidates'][0]['phases'][2]['argv']=['pt_shell']
  with self.assertRaises(ValueError):m.validate_plan(p)
 def test_phase_dependency_order(self):
  p=copy.deepcopy(self.plan);p['candidates'][0]['phases'][0]['depends']=['formal_activity12']
  with self.assertRaises(ValueError):m.validate_plan(p)
 def test_native_cap_cannot_expand(self):
  p=copy.deepcopy(self.plan);p['guards']['max_native_jobs']=2
  with self.assertRaises(ValueError):m.validate_plan(p)
 def test_unknown_wait_policy(self):
  self.g['unknown_license_policy']='wait';self.assertEqual(m.native_guard(self.g,self.res,self.ext,{'status':'UNKNOWN'}),'WAIT_LICENSE_KNOWN')
 def test_unknown_exclusive_single_explicit(self):self.assertEqual(m.native_guard(self.g,self.res,self.ext,{'status':'UNKNOWN'}),'ALLOW_UNKNOWN_LICENSE_EXCLUSIVE_SINGLE_DIAGNOSTIC_ONLY')
 def test_existing_native_blocks(self):
  self.res['native_processes']=[{'pid':1}];self.assertEqual(m.native_guard(self.g,self.res,self.ext,{'status':'KNOWN_FREE'}),'WAIT_EXISTING_NATIVE_OR_ADOPTED_JOB')
 def test_adopted_worker_reserves_slot_between_native_calls(self):self.assertEqual(m.native_guard(self.g,self.res,[{'live_process_present':True}],{'status':'UNKNOWN'}),'WAIT_EXISTING_NATIVE_OR_ADOPTED_JOB')
 def test_low_memory_blocks(self):
  self.res['mem_available_bytes']=0;self.assertEqual(m.native_guard(self.g,self.res,self.ext,{'status':'KNOWN_FREE'}),'WAIT_MEMORY')
 def test_low_disk_blocks(self):
  self.res['disk_available_bytes']=0;self.assertEqual(m.native_guard(self.g,self.res,self.ext,{'status':'KNOWN_FREE'}),'WAIT_DISK')
 def test_known_license_in_use_blocks(self):self.assertEqual(m.native_guard(self.g,self.res,self.ext,{'status':'NO_FREE_LICENSE'}),'WAIT_LICENSE_FREE')
 def test_parse_real_total_and_use_only(self):
  x=m.parse_license('Users of PT:  (Total of 2 licenses issued;  Total of 1 license in use)',['PT']);self.assertEqual(x['status'],'KNOWN_FREE');self.assertEqual(x['features']['PT']['free'],1)
 def test_checkout_count_is_not_license_availability(self):self.assertEqual(m.parse_license('PT 1 checked out',['PT'])['status'],'UNKNOWN')
 def test_missing_feature_unknown(self):self.assertEqual(m.parse_license('Users of PT: (Total of 2 licenses issued; Total of 1 license in use)',['DC'])['status'],'UNKNOWN')
 def test_no_license_query_is_unknown(self):self.assertEqual(m.license_snapshot(self.g,[])['status'],'UNKNOWN')
 def test_duplicate_license_feature_rejected(self):
  with self.assertRaises(ValueError):m.parse_license('Users of PT: (Total of 2 licenses issued; Total of 1 license in use)\nUsers of PT: (Total of 2 licenses issued; Total of 1 license in use)',['PT'])
 def test_hash_changed_or_missing_pending(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x';p.write_text('old');expected=m.ident(p);p.write_text('new');actual,errors=m.checked([expected,{'path':str(Path(t)/'absent'),'sha256':'0'*64}]);self.assertFalse(actual);self.assertEqual(len(errors),2)
 def test_freeze_fail_does_not_adopt(self):
  with tempfile.TemporaryDirectory() as t:
   c=copy.deepcopy(self.plan['candidates'][0]);c['freeze_inputs']=[{'path':str(Path(t)/'absent'),'sha256':'0'*64}]
   with patch.object(m,'git_identity',return_value={'main_commit':'fixed'}):r=m.freeze_candidate(c,Path(t))
   self.assertEqual(r['status'],'PENDING_INPUT_OR_SOURCE_VERIFY')
   with self.assertRaises(ValueError):m.adopt_fm(c,Path(t))
 def test_fm_own_log_and_target_bound(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/'fm.log';p.write_text('Verification SUCCEEDED\n 23 Passing compare points\n')
   r=m.ident(p);c={'id':'fixture','freeze_inputs':[r],'formal_log':r,'formal_expected_passing':23,'selected_mapped':{'sha256':'1'*64},'original_mapped':{'sha256':'2'*64},'ordered_svf_inputs':[{'sha256':'3'*64}]}
   c.update(source={},tool={});m.write(d/'freeze.json',{'status':'FROZEN_REVIEW_PENDING_NOT_QUALIFIED','after':[r],'source':{},'tool':{}})
   with patch.object(m,'git_identity',return_value={}),patch.object(m,'tool_git_identity',return_value={}):v=m.adopt_fm(c,d)
   self.assertFalse(v['same_original_area_mapping']);self.assertEqual(v['qualification'],'NOT_QUALIFIED')
   p.write_text('Verification SUCCEEDED\nVerification SUCCEEDED\n 23 Passing compare points\n')
   with self.assertRaises(ValueError):m.adopt_fm(c,d)
 def test_plan_mutation_refused_before_any_job(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'q';m.initialize(HERE/'queue-plan138.json',d);p=m.read(d/'plan.json');p['guards']['min_disk_available_bytes']+=1;m.write(d/'plan.json',p)
   with self.assertRaises(ValueError):m.tick(d,True)
 def test_preview_no_eda_no_freeze_despite_unknown_license(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'q';m.initialize(HERE/'queue-plan138.json',d)
   with patch.object(m,'proc_snapshot',return_value=[]),patch.object(m,'freeze_candidate',side_effect=AssertionError('preview must not freeze')),patch.object(m.subprocess,'Popen',side_effect=AssertionError('preview must not launch')):r=m.tick(d,False)
   self.assertTrue(all(v['freeze']['status']=='READY_FREEZE_NO_LICENSE_REQUIRED' for v in r['candidates'].values()))
 def test_running_orphan_never_automatic_restart(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'q';m.initialize(HERE/'queue-plan138.json',d);st=m.read(d/'state.json');cid=self.plan['candidates'][0]['id'];st['candidates'][cid]['freeze']={'status':'RUNNING','pid':-1,'token':'dead','run_dir':str(d/'missing')};m.write(d/'state.json',st)
   with patch.object(m,'proc_snapshot',return_value=[]),patch.object(m.subprocess,'Popen',side_effect=AssertionError('orphan must not launch')):r=m.tick(d,False)
   self.assertEqual(r['candidates'][cid]['freeze']['status'],'ORPHAN_REVIEW_REQUIRED_NO_RESTART')
 def test_completed_freeze_and_adopt_not_restarted(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/'q';m.initialize(HERE/'queue-plan138.json',d);st=m.read(d/'state.json')
   for cid,v in st['candidates'].items():v['freeze']['status']='FROZEN_REVIEW_PENDING_NOT_QUALIFIED';v['adopt_own_fm']['status']='OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING'
   m.write(d/'state.json',st)
   with patch.object(m,'proc_snapshot',return_value=[]),patch.object(m,'freeze_candidate',side_effect=AssertionError('no repeat freeze')),patch.object(m,'adopt_fm',side_effect=AssertionError('no repeat adopt')),patch.object(m.subprocess,'Popen',side_effect=AssertionError('missing adapter must not execute')):r=m.tick(d,True)
   self.assertTrue(all(v['formal_activity12']['status']=='PENDING_IMPLEMENTATION' for v in r['candidates'].values()))
if __name__=='__main__':unittest.main()
