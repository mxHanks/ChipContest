#!/usr/bin/env python3
"""Pure synthetic native-row fixture for serialization/opaque-pin gate checks."""
import argparse,copy,json,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
from common import *
from normalize import normalize
from review_native import review_coverage

def build(folder,contract):
 (folder/'reports').mkdir();rows=[]
 def row(kind,*values):rows.append(kind+'\t'+'\t'.join(str(v).encode().hex() for v in values))
 row('META','schema','final374-fm-native-tsv-v1');row('RESOURCE','max_cores',2)
 req=['verification_timeout_limit','synopsys_auto_setup','hdlin_unresolved_modules','verification_set_undriven_signals','verification_verify_directly_undriven_output','hdlin_ignore_parallel_case','hdlin_ignore_full_case','hdlin_error_on_mismatch_message']
 for name in req:row('ASSUMPTION','verified',name,'error' if name=='hdlin_unresolved_modules' else '2:0:0' if name=='verification_timeout_limit' else 'SYNTHETIC_VALUE')
 for role in REPORTS:
  (folder/'reports'/(role+'.rpt')).write_text('SYNTHETIC FORMAT TEST ONLY '+role+'\n')
  row('REPORT',role,'verified','report_matched_points')
 (folder/'reports/guidance.rpt').write_text('SYNTHETIC FORMAT TEST ONLY\nchange_names : 2 0 0 0 2\nTotal : 2 0 0 0 2\n')
 paths={
  'itcm':'u_soc/u_e203_itcm_ram/m', 'dtcm':'u_soc/u_e203_dtcm_ram/m','shared':'u_shared/storage/m',
  'weights':'u_soc/u_dma/u_core/weights/m','bias':'u_soc/u_dma/u_core/biasMemory/m','x':'u_soc/u_dma/u_core/xSets0/m','result':'u_soc/u_dma/u_core/resultSlices0/m'}
 boxes=[];inputs=[];outputs=[];all_names=[]
 for g,n in GEOMETRY.items():
  for i in range(n):
   names={k:k+':/WORK/'+TOP+'/'+paths[g]+str(i) for k in ['r','i']};boxes.append((names['r'],names['i']));all_names+=list(names.values())
   for container,name in names.items():
    row('MACRO',container,name,'RAMSP1024X16')
    for pin,(direction,width) in PORTS.items():
     for b in range(width):row('PIN',container,name,name+'/'+(pin if width==1 else pin+'['+str(b)+']'),'out' if direction=='output' else 'in')
   for pin,(direction,width) in PORTS.items():
    for b in range(width):
     suffix=pin if width==1 else pin+'['+str(b)+']';pair=names['r']+'/'+suffix,names['i']+'/'+suffix
     (outputs if direction=='output' else inputs).append(pair)
 for k in ['r','i']:row('COUNT','inventory_'+k,374)
 categories=dict(passing=inputs,passing_pgpin=[],matched_pgpin=[],matched=inputs+outputs,bbox=boxes,bbox_input=inputs,bbox_output=outputs,const=[],dont_verify=[],unread=[],not_compared=[],cuts=[],matched_cuts=[],failing=[],aborted=[],unverified=[])
 for cat,pairs in categories.items():
  row('QUERY',cat,'report_matched_points -list','SYNTHETIC_ONLY')
  for ref,impl in pairs:row('PAIR',cat,ref,impl)
  row('COUNT',cat,len(pairs))
 for cat in ['unmatched_r','unmatched_i','primary_r','primary_i','bbox_output_r','bbox_output_i','match_unread_r','match_unread_i','const_r','const_i','dont_verify_r','dont_verify_i','guidance_unaccepted']:row('COUNT',cat,0)
 (folder/'reports/black_boxes.rpt').write_text('SYNTHETIC FORMAT TEST ONLY\n'+'\n'.join(all_names)+'\n')
 (folder/'reports/unresolved-black-boxes.rpt').write_text('SYNTHETIC NO UNRESOLVED OBJECTS\n')
 row('COMPLETE','verified');(folder/'coverage-native.tsv').write_text('\n'.join(rows)+'\n')
 return len(inputs)

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'new fixture result required');results=[]
 with tempfile.TemporaryDirectory(prefix='final-fm-normalizer-fixture-') as td:
  folder=Path(td);contract=folder/'api-contract.json';dump(contract,{'SYNTHETIC_ONLY':True});passing=build(folder,contract)
  c=normalize(folder,contract);dump(folder/'coverage.json',c)
  decisions=dict(schema='final374-fm-coverage-decisions-v1',coverage_sha256=sha(folder/'coverage.json'),decisions=[])
  for cat,objects in c['point_lists'].items():
   if cat in ['failing','aborted','unverified']:continue
   for obj in objects:decisions['decisions'].append(dict(category=cat,id=obj['id'],decision='ACCEPTED_WITH_REASON',reason='Synthetic fixture checks parser and gate only, not real equivalence.',reviewer='offline-synthetic-test',evidence_reports=obj['evidence_reports']))
  s=review_coverage(c,folder,decisions,sha(contract),['report_matched_points']);need(s['paired_opaque_macros']==374 and s['accounted_boundary_bits']==25058 and passing==19074,'synthetic normalized pin accounting')
  results.append(dict(case='synthetic-native-rows-through-normalizer-and-gate',status='PASS',passing_pins=passing,boundary_bits=25058,native_eda_run=False))
  original=(folder/'coverage-native.tsv').read_text()
  mutations={
   'missing-collector-terminal':original.rsplit('\nCOMPLETE\t',1)[0]+'\n',
   'count-mismatch':original.replace('COUNT\t'+b'bbox'.hex()+'\t'+b'374'.hex(),'COUNT\t'+b'bbox'.hex()+'\t'+b'373'.hex(),1),
   'unknown-native-row':original.replace('META\t','BADROW\t',1),
  }
  for name,text in mutations.items():
   (folder/'coverage-native.tsv').write_text(text)
   try:normalize(folder,contract)
   except ValueError as e:results.append(dict(case=name,status='PASS',rejection=str(e)))
   else:raise ValueError('mutation incorrectly accepted:'+name)
 a.out.parent.mkdir(parents=True,exist_ok=True);dump(a.out,dict(schema='final374-formal-normalizer-synthetic-tests-v1',status='PASS',tests=results,native_eda_run=False,scope='Pure generated synthetic TSV/pins and reports. No library, actual map or vendor process involved.'))
 print('SYNTHETIC_NATIVE_ROW_NORMALIZER_TEST_PASS cases='+str(len(results)))
if __name__=='__main__':main()
