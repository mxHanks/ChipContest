#!/usr/bin/env python3
"""xu: exact actual PE32 PPA/geometry/area audit, explicitly not STA qualification."""
from pathlib import Path
import hashlib,json,lzma,re
H=Path(__file__).resolve().parent

def need(v,m):
 if not v:raise ValueError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def audit():
 m=json.loads((H/'selected-manifest.json').read_text());orig=json.loads((H/'original-export-manifest.json').read_text());raw={}
 for x in m:
  p=H/x['path'];b=p.read_bytes();need(p.is_file()and not p.is_symlink()and len(b)==x['stored_bytes']and sha(b)==x['stored_sha256'],'stored identity differs');b=lzma.decompress(b)if x['compression']=='xz'else b;o=x['original'];need(o in orig and len(b)==o['bytes']and sha(b)==o['sha256'],'original bytes differ');need(o['path']not in raw,'duplicate raw');raw[o['path']]=b
 g='s3-pe32-ppa-campaign-20261103-01/'
 def data(n):return raw[g+n]
 def text(n):return data(n).decode()
 def read(n):return json.loads(text(n))
 j=read('state.json');e=read('ppa/execution.json');i=read('implementation/implementation.json');p=read('ppa/prepared.json');need(j['status']==e['status']=='EXECUTED_NOT_QUALIFIED'and all(x['status']=='PASS'and x['returncode']==0 for x in j['steps'])and len(j['steps'])==3,'actual PPA execution differs');need(e['dc']['returncode']==e['pt']['returncode']==0,'tool exit differs')
 main='94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114';child='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5';need(i['source_freeze']['main_commit']==p['inventory']['main_commit']==main and i['source_freeze']['e203_commit']==p['inventory']['e203_commit']==child,'source freeze differs');need(i['defines']==['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_ACCEL_PE32=1'],'physical variant define differs');need(i['accelerator_configuration']==p['inventory']['accelerator_configuration'],'physical geometry differs');c=i['accelerator_configuration'];need([c[k]for k in ['physical_pes','weight_macros','full_soc_macros','logical_weight_bytes','physical_weight_bytes','weight_padding_bytes']]==[32,32,352,32768,65536,32768],'macro/padding geometry differs');need(sum(x['count']for x in i['memory_groups'])==352,'macro total differs')
 need([x['sha256']for x in i['libraries']]==['f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'],'same-server libraries differ')
 need(sha(data('ppa/dc.log'))==e['dc']['log_sha256']and text('ppa/dc.log').splitlines().count('XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED')==1,'actual DC log differs')
 for group,n in [('itcm',32),('dtcm',32),('shared',256),('accelerator_weights',32)]:need(len(re.findall(r'^XU_SRAM_GROUP '+group+' count='+str(n)+r' macro_ref=RAMSP1024X16 ',text('ppa/dc.log'),re.M))==2,'pre/post macro check differs')
 checked=[];unreturned=[]
 for n,x in e['reports'].items():
  if g+'ppa/'+n in raw:need(sha(data('ppa/'+n))==x['sha256']and len(data('ppa/'+n))==x['bytes'],'actual report differs');checked.append(n)
  else:unreturned.append(dict(path=n,receipt=x))
 for n,h in p['generated_sha256'].items():
  if g+'ppa/'+n in raw:need(sha(data('ppa/'+n))==h,'generated script differs')
 need(p['producer_sha256']==j['tool_sha256']['tools/scripts/xu_soc_ppa.py']=='ffe6076833a97058cb9d345eee175ec5988c12c801dfb50621b059608545e698','actual producer differs')
 lines=text('ppa/area.rpt').splitlines();indices=[k for k,x in enumerate(lines)if x.endswith('/u_accel_icb_slave')];need(len(indices)==1,'accelerator scope not unique');parts=lines[indices[0]+1].split();need(parts[0]=='518603.3811'and parts[-1]=='xu_pe32_icb_slave','actual mapped accelerator area differs');whole=re.findall(r'^Total cell area:\s*([\d.]+)$',text('ppa/area.rpt'),re.M);need(whole==['3589560.839551'],'wholeSoC area differs')
 cov=text('ppa/analysis-coverage.rpt');need(re.search(r'^All Checks\s+342065\s+216444\s+\([^)]*\)\s+97285\s+\([^)]*\)\s+28336\s+\([^)]*\)',cov,re.M)is not None,'actual initial timing coverage differs');need(text('ppa/timing-slack.tsv')=='delay_type\tpath_count\tworst_slack\nmax\t1\t-21.954998\nmin\t1\t-25.257580\n','original propagated diagnostic differs')
 net=e['netlist_sha256'];need(net=='ca1d17a9adcd1a15e7b69758754e68d962c7535d8f2b31407c47d9bd136014c8'and e['analysis_sdc_sha256']=='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98','measured implementation differs')
 need(j['acceptance']['measured_total_cycles']==dict(real12=11376501,**{'pe32-autogroup-control-real12':11842200,'pe8-autogroup-control-real12':11842200}),'actual VCS prerequisites differ')
 return dict(status='ACTUAL_PE32_SAME_LIBRARY_AREA_REVIEWED_NOT_QUALIFIED',raw_files=len(m),locally_checked_reports=checked,unreturned_report_receipts=unreturned,unreturned_pt_log=e['pt'],main_commit=main,e203_commit=child,producer_commit='6798c492136db3f1f944b8d2eb19d940bb85e64a',accelerator_area_mm2=.5186033811,whole_soc_area_mm2=3.589560839551,area_limit_mm2=2.25,limit_percent=.5186033811/2.25*100,relative_s2c_area_increase_percent=(.5186033811/.2948018380-1)*100,netlist_sha256=net,configuration=c,actual_vcs_cycles=j['acceptance']['measured_total_cycles'],initial_timing=dict(total_checks=342065,met=216444,violated=97285,untested=28336),not_qualified=['Original unbuffered propagated preCTS clock diagnostic is not closed150MHz timing','Actual PT log and listed large reports not downloaded; do not pretend full local log replay','FM17 is separate pending proof, macro internals require separate functional mapping evidence','No same-configuration formal-clear/request capture or qualified fullSoC task energy for PE32 yet','Sourceguard strengthening ba9d89a is later tool identity, not retroactively assigned to this actual run'])
if __name__=='__main__':print(json.dumps(audit(),sort_keys=True,indent=2))
