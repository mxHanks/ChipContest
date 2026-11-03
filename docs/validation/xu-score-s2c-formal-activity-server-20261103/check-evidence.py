#!/usr/bin/env python3
"""xu exact task00 clear/REQUEST/RETIRE evidence, not SAIF/power qualification."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,lzma,sys
H=Path(__file__).resolve().parent

def need(v,m):
 if not v:raise ValueError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def audit(tool,source):
 m=json.loads((H/'selected-manifest.json').read_text());orig=json.loads((H/'original-export-manifest.json').read_text());raw={}
 for x in m:
  p=H/x['path'];b=p.read_bytes();need(p.is_file()and not p.is_symlink()and len(b)==x['stored_bytes']and sha(b)==x['stored_sha256'],'stored raw differs');b=lzma.decompress(b)if x['compression']=='xz'else b;o=x['original'];need(o in orig and len(b)==o['bytes']and sha(b)==o['sha256'],'original raw differs');need(o['path']not in raw,'duplicate raw');raw[o['path']]=b
 g='s2c-formal-activity-task00-20261103-02/'
 def data(n):return raw[g+n]
 def read(n):return json.loads(data(n))
 j=read('result.json');need(j['status']=='PARTIAL_COLLECTED_REVIEW_PENDING'and not j['taskset_complete']and j['requested_task_ids']==[0]and len(j['tasks'])==1,'single task scope differs');need(j['tool_context']['main_commit']=='5e75581319f926642ee7dc214ad825f3564a8e39','actual producer commit differs')
 sys.path.insert(0,str(tool/'tools/ppa'));import xu_candidate_activity_context as context
 spec=importlib.util.spec_from_file_location('actual_s2c_collector',tool/'tools/ppa/xu_candidate_task_activity.py');collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector);ctx=context.Context(source)
 for key in ['main_commit','main_tree','main_worktree_manifest_sha256','main_tracked_entries','source_profile']:need(ctx.source[key]==j['source_context'][key],'local complete frozen source differs: '+key)
 need(ctx.tool['main_commit']==j['tool_context']['main_commit'],'local actual producer checkout differs')
 for record in j['tool_context']['frozen_common_tools']:
  relative=record['path'].split('/ChipContest-candidate-activity-tools-20261103-02/',1)[1];need(sha((tool/relative).read_bytes())==record['sha256'],'actual common helper differs')
 for record in j['configuration']['producer_sources']:
  relative=record['path'].split('/ChipContest-candidate-activity-tools-20261103-02/',1)[1];need(sha((tool/relative).read_bytes())==record['sha256'],'actual producer source differs')
 log=data('task_00/simulation.log').decode().split('\n',1)[1];layer,window,auto=collector.checked_log(ctx,log,0);t=j['tasks'][0];need(t==read('task_00/result.json')and layer==t['layer']and window==t['activity_window']and auto==t['autogroup'],'actual original source log replay differs');need(sha(data('task_00/simulation.log'))==t['boundary_log']['sha256'],'boundary log hash differs');need(window['formal_elapsed_cycles']==990656 and window['formal_inclusive_cycles']==990657 and window['duration_ticks']==6604373333334,'formal interval differs');need(sha(data('firmware/firmware-build.json'))==j['configuration']['firmware_build']['sha256'],'actual firmware receipt differs')
 n=read('task_00/task-normalization.json');need(n==t['normalization']and n['macro_count']==336 and n['alias_bit_count']==22512,'actual normalization scope differs');need(n['duration_ticks']==window['duration_ticks']and t['saif']['duration_ticks']==window['duration_ticks'],'reported activity duration differs');need(j['configuration']['netlist']['sha256']=='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892','target mapping differs');need(j['configuration']['constraints']['sha256']=='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98','target analysis SDC differs');ctx.recheck()
 return dict(status='ACTUAL_S2C_TASK00_FORMAL_WINDOW_REPLAYED_NOT_ENERGY_QUALIFIED',raw_files=len(m),producer_commit=j['tool_context']['main_commit'],source_context=j['source_context'],activity_window=window,layer=layer,autogroup=auto,saif_receipt=t['saif'],normalization_receipt=n,limitations=['Only task00; full12 separate new campaign','Raw and normalized large SAIF not returned locally: receipts are not a fresh local byte normalization proof','Target netlist/SDC identity alone does not establish functional/timing/power mapping eligibility','No joint-condition capture in this revision, no fullSoC task energy or contest score computed'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--tool-root',type=Path,default=Path('/home/mxhanks/Projects/ChipContest-xu-candidate-activity'));p.add_argument('--source-root',type=Path,default=Path('/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup'));a=p.parse_args();print(json.dumps(audit(a.tool_root.resolve(),a.source_root.resolve()),sort_keys=True,indent=2))
