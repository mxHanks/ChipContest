#!/usr/bin/env python3
"""Read existing immutable sources; inventories candidates, not mapped proof."""
from pathlib import Path
import hashlib,json,re,collections
ROOT=Path('/home/mxhanks/Projects/ChipContest-xu-score-opt')
S2C=Path('/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup')
OUT=Path(__file__).resolve().parent
TB=ROOT/'build/xu-score-resume-20261103/next-results-export-53/s2c-formal-activity12-20261103-23/simulator/tb_xu_s2c_task_activity.sv'
PLAN=ROOT/'build/xu-mapped-task00-111/prepared-local-v3/private-reference-adapter-plan.json'
CHILD=S2C/'third-party/e203_hbirdv2'
PPA=ROOT/'docs/validation/xu-score-s0-soc-20261102/s2bc-area-formality-server-20261103/raw/s2c-ppa-campaign-20261103-01/s2c/ppa/prepared.json'
ALIASES={
 'bias_regs':('u_linear_compute_core.io_bias_{0..7}',40,8),
 'cache_addr_reg':('u_linear_compute_core.io_cacheWriteAddr',8,1),
 'cache_enable':('u_linear_compute_core.io_cacheEnable',1,1),
 'compute_start':('u_linear_compute_core.io_computeStart',1,1),
 'core_done':('u_linear_compute_core.io_done',1,1),
 'core_start':('u_linear_compute_core.io_start',1,1),
 'row_active':('u_linear_compute_core.io_rowActive',1,1),
 'row_count':('u_linear_compute_core.io_rowCount',2,1),
 'row_group':('u_linear_compute_core.io_rowGroup',5,1),
 'row_pop':('u_linear_compute_core.io_rowPop',1,1),
 'row_produced':('u_linear_compute_core.io_rowProduced',6,1),
 'row_result':('u_linear_compute_core.io_rowResult_{0..7}',48,8),
 'row_retired':('u_linear_compute_core.io_rowRetired',6,1),
 'row_running':('u_linear_compute_core.io_rowRunning',1,1),
 'row_start':('u_linear_compute_core.io_rowStart',1,1),
 'row_valid':('u_linear_compute_core.io_rowValid',1,1),
}
DIRECT={'u_linear_compute_core.core.io_group':5,'u_linear_compute_core.core.engine.peArray.io_enable':1}
for k,w in {'io_cacheWriteAddr':8,'io_cacheWriteData':40,'io_cacheWriteEnable':1,'io_cacheWriteMask':5,'io_wLoadAddr':11,'io_wLoadBank':3,'io_wLoadData':16,'io_wLoadWen':1,'io_xLoadAddr':6,'io_xLoadData':16,'io_xLoadWen':1}.items():DIRECT['u_linear_compute_core.'+k]=w
STATE={'bias_index_reg':3,'manual_busy':1,'stream_cursor':15,'stream_error':1,'stream_is_w':1,'stream_pair':1,'stream_pending':1,'stream_second':1,'w_addr_reg':11,'w_bank_reg':3,'w_cursor':15,'w_load_wen':1,'x_addr_reg':6,'x_cursor':7,'x_load_wen':1,'u_linear_compute_core.head':1,'u_linear_compute_core.tail':1}
CLOCK={'pll_ASLEEP':1,'pll_M':8,'pll_N':5,'pll_OD':2,'pll_RESET':1,'pllbypass':1,'plloutdiv':6,'plloutdivby1':1,'test_mode':1}
plan=json.loads(PLAN.read_text());text=TB.read_text();rows=[]
for original in plan['original_references']:
 macro=original['original_macro'];name=original['original_path'];row=dict(original_macro=macro,original_path=name,original_tb_lines=[i for i,s in enumerate(text.splitlines(),1)if '`'+macro+'.'+name in s],mapped_runtime_status='NOT_INSPECTED_IN_THIS_SOURCE_ONLY_REVIEW')
 if 'pending'not in original['handling']:row.update(category='already111_public_port',candidate=name)
 elif macro=='ACCEL':
  if name in ALIASES:
   target,width,lanes=ALIASES[name];row.update(category='existing_core_port_alias',candidate=target,width_each=width,lanes=lanes)
  elif name in DIRECT:row.update(category='existing_nested_module_port',candidate=name,width_each=DIRECT[name],lanes=1)
  elif name in STATE:row.update(category='mapped_private_state_or_equivalent_endpoint_needed',candidate=name,width_each=STATE[name],lanes=1)
  else:
   assert name in ['busy','row_start_accept'];row.update(category='literal_wrapper_combinational_expression',candidate=name,width_each=1,lanes=1)
 elif macro=='XU_HCLK':row.update(category='existing_hclkgen_input_port',candidate=name,width_each=CLOCK[name],lanes=1)
 else:
  assert macro=='EXU'
  if name.endswith('rf_r'):row.update(category='existing_rf3_dff_output_candidate',candidate='u_e203_exu_regfile.regfile[3].rfno0.rf_dffl.qout',width_each=32,lanes=1,only_original_referenced_element=3,condition='source config E203_CFG_REGFILE_LATCH_BASED is disabled; actual mapped hierarchy still must be inspected')
  else:row.update(category='existing_commit_input_port',candidate=name,width_each=32 if name.endswith('_pc')else 1,lanes=1)
 rows.append(row)
assert len(rows)==72 and sum(r['category']!='already111_public_port'for r in rows)==60
counts=dict(collections.Counter(r['category']for r in rows))
files=[TB,PLAN,PPA,CHILD/'rtl/e203/perips/accel_icb_slave.v',CHILD/'rtl/e203/perips/LinearAutoGroupCore.sv',CHILD/'rtl/e203/subsys/e203_subsys_hclkgen.v',CHILD/'rtl/e203/core/e203_exu_regfile.v',CHILD/'rtl/e203/core/e203_exu_commit.v',CHILD/'rtl/e203/general/sirv_gnrl_dffs.v',CHILD/'rtl/e203/core/config.v',CHILD/'rtl/e203/core/e203_defines.v']
identities=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for p in files]
ppa=json.loads(PPA.read_text());source_binding=[]
for rel in ['rtl/e203/perips/accel_icb_slave.v','rtl/e203/perips/LinearAutoGroupCore.sv']:
 p=CHILD/rel;key='third-party/e203_hbirdv2/'+rel
 def find_key(tree,wanted,prefix=''):
  found=[]
  if isinstance(tree,dict):
   for k,v in tree.items():
    if k==wanted and isinstance(v,dict)and'sha256'in v:found.append((prefix+'/'+k,v))
    found+=find_key(v,wanted,prefix+'/'+k)
  elif isinstance(tree,list):
   for i,v in enumerate(tree):found+=find_key(v,wanted,prefix+'/'+str(i))
  return found
 frozen=find_key(ppa,key);local=hashlib.sha256(p.read_bytes()).hexdigest()
 assert frozen and all(v['sha256']==local for _,v in frozen)
 source_binding.append(dict(local_path=str(p),local_sha256=local,manifest_key=key,matching_actual_ppa_manifest_locations=[k for k,_ in frozen],source_matches_actual_ppa_manifest=True))
(OUT/'reference-candidates115.json').write_text(json.dumps(dict(scope='SOURCE_ONLY_MAPPED_HANDLES_NOT_VERIFIED',counts=counts,references=rows,source_identities=identities,production_source_candidates=source_binding),sort_keys=True,indent=2)+'\n')
print(json.dumps(counts,sort_keys=True))
