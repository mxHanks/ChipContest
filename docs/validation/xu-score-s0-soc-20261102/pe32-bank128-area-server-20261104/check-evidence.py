#!/usr/bin/env python3
"""xu actual mixed448 macro PPA review; never qualifies timing or energy."""
from decimal import Decimal
import hashlib,importlib.util,json,lzma,re
from pathlib import Path
H=Path(__file__).resolve().parent
G='s3-pe32-bank128-ppa-campaign-20261103-01/'
MAIN='f75880d4f06ccb7f1c16115bee501f53d9a2abb7';CHILD='52cfbea1f79f10e44f7d1696f54015797f886b96'
SDC='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
NET='7a69a1219561ca7a2e162ac84007f9fb32f34264132d1e6999e34c990cabe628'
LIBS={'standard_cell':'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','sram':'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f','weight_sram128':'821c9344b787ecaae7ce222b9c5ab339b223759411dc20812f06210448a71bbe'}
SCOPE='u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def digest(obj):return sha(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())
def audit():
 original=json.loads((H/'original-export-manifest.json').read_bytes());transport=json.loads((H/'transport.json').read_text());need(len(original)==168 and transport['manifest_sha256']==sha((H/'original-export-manifest.json').read_bytes()),'original export identity')
 expected={r['path']:r for r in original if r['path'].startswith(G)};selected=json.loads((H/'selected-manifest.json').read_text());need(len(expected)==len(selected)==81,'complete81raw')
 raw={}
 for r in selected:
  p=H/r['path'];need(not Path(r['path']).is_absolute()and '..'not in Path(r['path']).parts and p.is_file()and not p.is_symlink(),'stored path')
  data=p.read_bytes();need(len(data)==r['stored_bytes']and sha(data)==r['stored_sha256'],'stored raw')
  need(r['compression']in ['none','xz'],'compression')
  if r['compression']=='xz':data=lzma.decompress(data)
  o=r['original'];need(expected[o['path']]==o and len(data)==o['bytes']and sha(data)==o['sha256']and o['path']not in raw,'raw origin/hash')
  raw[o['path']]=data
 need(set(raw)==set(expected),'raw completeness')
 def b(n):return raw[G+n]
 def j(n):return json.loads(b(n))
 def t(n):return b(n).decode('utf8')
 state,e,i,p,g=[j(n)for n in ['state.json','ppa/execution.json','implementation/implementation.json','ppa/prepared.json','implementation/generation.json']]
 need(state['status']==e['status']=='EXECUTED_NOT_QUALIFIED'and state['profile']=='s3-pe32-bank128','execution scope')
 need(len(state['steps'])==3 and [x['index']for x in state['steps']]==[0,1,2]and all(x['status']=='PASS'and x['returncode']==0 for x in state['steps']),'three actual commands')
 need(sha(b('ppa/execution.json'))==state['execution_sha256']and e['dc']['returncode']==e['pt']['returncode']==0,'DC/PT execution')
 need(e['netlist_sha256']==NET and e['analysis_sdc_sha256']==SDC,'actual net/SDC identity')
 need(i==p['implementation']and i['source_profile']=='s3-pe32-bank128','implementation binding')
 f=i['source_freeze'];profile=f['profile'];need(f['main_commit']==MAIN and f['e203_commit']==CHILD and state['acceptance']['source_profile']==profile,'full source pin/profile')
 source=json.loads((H/'context/source-files.json').read_text());records={};groups={'main':{},'child':{}}
 for name,v in source.items():
  e2=dict(mode=v['git_mode'],sha256=v['sha256']);label='child'if name.startswith('third-party/e203_hbirdv2/')else'main';local=name[len('third-party/e203_hbirdv2/'):]if label=='child'else name;groups[label][local]=e2
 groups['main']['third-party/e203_hbirdv2']=dict(mode='160000',commit=CHILD)
 need(len(source)==2637 and len(groups['main'])==1561 and digest(groups['main'])==profile['main_source_freeze']['actual_main_tree_manifest_sha256']and digest(groups['child'])==profile['actual_child_tree_manifest_sha256'],'actual full source bytes/modes/gitlink digest')
 verifier=json.loads((H/'context/verification.json').read_text());need(verifier['immutable_git_rechecked']and verifier['main_commit']==MAIN and verifier['e203_commit']==CHILD and verifier['integer_golden_outputs']==304128,'prior actual source/VCS proof scope')
 sp=importlib.util.spec_from_file_location('xu_frozen_mixed448',H/'evidence-tools/xu_soc_ppa.py');prod=importlib.util.module_from_spec(sp);sp.loader.exec_module(prod)
 need(i['defines']==prod.BANK128_DEFINES and i['accelerator_configuration']==prod.BANK128_CONFIGURATION,'physicalPE32bank128 config')
 need(sum(x['count']for x in i['memory_groups'])==448 and i['memory_groups']==prod.template(p['inventory'],'s3-pe32-bank128')['memory_groups'],'448mixed topology')
 need({x['role']:x['sha256']for x in i['libraries']}==LIBS,'three same-server real DB roles')
 for key,obj in [('defines_sha256',i['defines']),('accelerator_configuration_sha256',i['accelerator_configuration']),('memory_groups_sha256',i['memory_groups']),('libraries_sha256',i['libraries'])]:need(f[key]==digest(obj),'freeze identity '+key)
 for path,want in state['tool_sha256'].items():need(sha((H/'evidence-tools'/Path(path).name).read_bytes())==want,'actual frozen producer')
 need(len(p['source_files'])==164,'164 prepared sources')
 returned=0
 for n,r in p['source_files'].items():
  if G+'ppa/'+n in raw:need(sha(b('ppa/'+n))==r['sha256'],'actual prepared source');returned+=1
 missing_reports=[]
 for n,r in e['reports'].items():
  if G+'ppa/'+n in raw:need(len(b('ppa/'+n))==r['bytes']and sha(b('ppa/'+n))==r['sha256'],'report receipt '+n)
  else:missing_reports.append(n)
 for key,name,version,marker,repeats in [('dc','ppa/dc.log','T-2022.03-SP5-5','XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED',2),('pt','ppa/pt-sta.log','T-2022.03-SP5-1','XU_SOC_STA_COMPLETE_NOT_QUALIFIED',1)]:
  text=t(name);need(sha(b(name))==e[key]['log_sha256']and version in text and text.splitlines().count(marker)==1,'actualtool/version/done')
  need(not re.search(r'^\s*(?:Error:|Fatal:|XU_FATAL:)',text,re.M),'actualfatal')
  for group in i['memory_groups']:
   count=group['count'];depth=group['depth'];width=group['width'];physical=count*depth*width;logical=group['logical_bits'];line='XU_SRAM_GROUP %s count=%d macro_ref=%s logical_bits=%d physical_bits=%d padding_bits=%d'%(group['name'],count,group['macro_ref'],logical,physical,physical-logical)
   need(text.splitlines().count(line)==repeats,'actualpre/post/PT exactmacrogroup')
 need(t('ppa/synth.tcl').count(prod.memory_checks(i))==2 and t('ppa/sta.tcl').count(prod.memory_checks(i))==1,'macro guard in actual Tcl')
 unit=json.loads((H/'context/prior-area-compliance.json').read_text());need(unit['status']=='PASS'and unit['conversion']=='1 mm2 = 1000000 um2','sameDB physical area unit proof')
 lines=t('ppa/area.rpt').splitlines();matches=[k for k,x in enumerate(lines)if x.strip()==SCOPE];need(len(matches)==1,'unique full accelerator scope')
 row=lines[matches[0]+1];area=Decimal(row.split()[0]);need(area==Decimal('575203.5631')and row.split()[-1]=='xu_pe32_bank128_icb_slave','actual accelerator area/wrapper')
 whole=re.findall(r'^Total cell area:\s*([0-9.]+)$',t('ppa/area.rpt'),re.M);need(whole==['3646156.552727'],'wholeSoCarea')
 mm=area/1000000;prior=Decimal('0.5186033811');limit=Decimal('2.25');coverage=re.search(r'^All Checks\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)',t('ppa/analysis-coverage.rpt'),re.M);need(coverage and list(map(int,coverage.groups()))==[364509,235855,96510,32144],'complete actualSTAcoverage')
 need(t('ppa/timing-slack.tsv').splitlines()[1:]==['max\t1\t-22.328501','min\t1\t-26.211073'],'original unclosedSTA')
 need(any(b'CMD-010'in value for name,value in raw.items()if name.endswith(('.log','.rpt'))),'retained unsupported command diagnostic')
 return dict(status='ACTUAL_LIBRARY_AREA_REVIEW_NOT_TIMING_EQUIVALENCE_OR_ENERGY_QUALIFIED',raw_files=81,raw_bytes=sum(len(x)for x in raw.values()),mapped_netlist_sha256=NET,full_source_manifest_blobs=2637,prepared_source_count=164,returned_prepared_sources=returned,missing_report_bodies=missing_reports,accelerator_mm2=str(mm),whole_soc_mm2=str(Decimal(whole[0])/1000000),limit_mm2=str(limit),limit_percent=str(mm/limit*100),increase_vs_original32_percent=str((mm/prior-1)*100),macro_total=448,macro_counts={'RAMSP1024X16':320,'RAMSP128X16':128},whole_weight_logical_bytes=32768,whole_weight_physical_bytes=32768,real12_cycles=11376501,coverage=dict(zip(['total','met','violated','untested'],map(int,coverage.groups()))),original_propagated_preCTS_slack_ns={'max':'-22.328501','min':'-26.211073'},not_run=['candidate mapped formal equivalence','complete150MHz timing qualification','fullSoC task energy qualification'])
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);a=parser.parse_args();v=audit()
 if a.out:a.out.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
 print(json.dumps(v,indent=2))
