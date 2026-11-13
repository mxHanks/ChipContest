#!/usr/bin/env python3
"""Normalize only actual native collector rows; unknown shapes stay failures."""
import argparse,json,re,sys
from collections import defaultdict
from pathlib import Path
sys.dont_write_bytecode=True
from common import *
from review_native import REVIEWED

def read_native(path):
 rows=[]
 for number,line in enumerate(path.read_text().splitlines(),1):
  fields=line.split('\t');need(fields[0] in {'META','RESOURCE','ASSUMPTION','QUERY','PAIR','SINGLE','COUNT','MACRO','PIN','REPORT','COMPLETE'},'unknown collector row '+str(number))
  try:values=[bytes.fromhex(s).decode('utf-8') for s in fields[1:]]
  except (ValueError,UnicodeDecodeError) as e:raise ValueError('invalid native row hex/utf8 '+str(number)) from e
  rows.append((fields[0],values))
 need(rows and rows[0]==('META',['schema','final374-fm-native-tsv-v1']),'native collector schema missing')
 need(sum(kind=='COMPLETE' for kind,_ in rows)==1 and rows[-1]==('COMPLETE',['verified']),'native collector did not complete verified phase')
 return rows

def group(path):
 patterns={'itcm':'/u_e203_itcm_ram/','dtcm':'/u_e203_dtcm_ram/','shared':'/u_shared/storage/','weights':'/u_core/weights/','bias':'/u_core/biasMemory/','x':'/u_core/xSets','result':'/u_core/resultSlices'}
 matches=[k for k,v in patterns.items() if v in path];need(len(matches)==1,'unclassified/overlapping SRAM '+path);return matches[0]

def normalize(run,contract_path):
 rows=read_native(run/'coverage-native.tsv');pairs=defaultdict(list);single=defaultdict(list);count={};macros={'r':{},'i':{}};pins={'r':defaultdict(dict),'i':defaultdict(dict)};assumptions=[];provenance=defaultdict(list);resources={}
 for kind,v in rows:
  if kind=='PAIR':need(len(v)==3,'pair row width');pairs[v[0]].append((v[1],v[2]))
  elif kind=='SINGLE':need(len(v)==3,'single row width');single[v[0]].append(v[2])
  elif kind=='COUNT':need(len(v)==2 and v[0] not in count,'duplicate/native count row');count[v[0]]=int(v[1])
  elif kind=='MACRO':
   need(len(v)==3 and v[0] in macros and v[1] not in macros[v[0]],'duplicate/malformed macro row');macros[v[0]][v[1]]=v[2]
  elif kind=='PIN':
   need(len(v)==4 and v[0] in pins and v[2] not in pins[v[0]][v[1]],'duplicate/malformed pin row');pins[v[0]][v[1]][v[2]]=v[3]
  elif kind=='ASSUMPTION':
   need(len(v)==3,'assumption row width');assumptions.append(v)
  elif kind=='REPORT':need(len(v)==3 and v[0] in REPORTS,'native report role');provenance[v[0]].append(v[1:])
  elif kind=='RESOURCE':need(len(v)==2,'resource row width');resources[v[0]]=int(v[1])
 for name,n in count.items():
  expected=len(macros[name[-1]]) if name in ['inventory_r','inventory_i'] else len(pairs.get(name,single.get(name,[])))
  need(n==expected,'native list/count disagreement:'+name)
 required_pairs=['passing','passing_pgpin','matched_pgpin','matched','bbox','bbox_input','bbox_output','const','dont_verify','unread','not_compared','cuts','matched_cuts','failing','aborted','unverified']
 required_singles=['unmatched_r','unmatched_i','primary_r','primary_i','bbox_output_r','bbox_output_i','match_unread_r','match_unread_i','const_r','const_i','dont_verify_r','dont_verify_i','guidance_unaccepted']
 need(set(required_pairs+required_singles)<=set(count),'missing native point enumeration categories')
 for k in required_pairs:need(count[k]==len(pairs[k]),'missing paired category:'+k)
 for k in required_singles:need(count[k]==len(single[k]),'missing single category:'+k)
 point_lists={k:[] for k in REVIEWED+['failing','aborted','unverified']}
 def add(category,identifier,roles,**details):
  point_lists[category].append(dict(id=identifier,evidence_reports=roles,**details))
 for container,name in [('r','reference'),('i','implementation')]:
  primary=set(single['primary_'+container])|set(single['bbox_output_'+container])
  for value in sorted(set(single['unmatched_'+container])-primary):add('unmatched_'+name,value,['unmatched'])
  for value in sorted(primary):add('unmatched_primary_'+name,value,['unmatched'])
  for value in sorted(set(single['match_unread_'+container])):add('match_unread_'+name,value,['unmatched','unread'])
 def pair_id(pair):return pair[0]+'\t'+pair[1]
 for kind in ['failing','aborted','unverified','unread']:
  for pair in pairs[kind]:add(kind,pair_id(pair),['matched' if kind=='cuts' else kind],reference=pair[0],implementation=pair[1])
 for pair in pairs['matched_pgpin']:
  add('power_points',pair_id(pair),['matched'],reference=pair[0],implementation=pair[1],verify_status='PASSING' if pair in set(pairs['passing_pgpin']) else 'NOT_PASSING')
 for pair in pairs['matched_cuts']:
  add('cuts',pair_id(pair),['matched'],reference=pair[0],implementation=pair[1],verify_status='PASSING' if pair in set(pairs['cuts']) else 'NOT_PASSING')
 accounted=set(pairs['unread'])|set(pairs['const'])|set(pairs['dont_verify'])
 for pair in pairs['not_compared']:
  if pair not in accounted:add('not_compared_other',pair_id(pair),['unread'],reference=pair[0],implementation=pair[1])
 for category in ['const','dont_verify']:
  role='constants' if category=='const' else 'dont_verify';seen=set()
  for pair in pairs[category]:
   identifier=pair_id(pair);add(role,identifier,[role],reference=pair[0],implementation=pair[1]);seen|=set(pair)
  for container in ['r','i']:
   for value in single[category+'_'+container]:
    if value not in seen:add(role,value,[role]);seen.add(value)
 # Raw user-defined constants are separate from constant-register reports.
 constants=(run/'reports/constants.rpt').read_text()
 for value,typ,name in re.findall(r'^\s*(\S+)\s+(net|port)\s+([ri]:/\S+)[ \t]*$',constants,re.M):
  add('constants','user-defined:'+name,['constants'],actual_value=value,object_type=typ)
 for phase,name,value in assumptions:
  add('assumptions',name if phase=='verified' else phase+'/'+name,['assumptions'],actual_value=value)
 # Never infer a mismatch/guidance exemption from an old log or a missing row.
 mismatches=(run/'reports/hdlin_mismatches.rpt').read_text()
 # The detailed native mismatch report is always separately reviewed even if
 # its formatting has no known diagnostic IDs. This avoids treating an
 # unfamiliar/missing summary as zero mismatches.
 add('hdlin_mismatches','complete-native-hdlin-report',['hdlin_mismatches'],report_sha256=sha(run/'reports/hdlin_mismatches.rpt'))
 guidance=(run/'reports/guidance.rpt').read_text()
 table=re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)(?:\s*:)?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)[ \t]*$',guidance,re.M)
 need(table,'unrecognized/missing native SVF guidance counters')
 totals=[values for name,*values in table if name.lower()=='total'];entries=[list(map(int,values)) for name,*values in table if name.lower()!='total']
 if totals:
  need(len(totals)==1,'duplicate native SVF total row');values=list(map(int,totals[0]))
  if entries:need(values==[sum(row[i] for row in entries) for i in range(5)],'native SVF total/per-command disagreement')
 else:
  need(entries,'no native SVF command counters');values=[sum(row[i] for row in entries) for i in range(5)]
 gc=dict(zip(['accepted','rejected','unsupported','unprocessed','total'],values))
 need(sum(gc[k] for k in ['accepted','rejected','unsupported','unprocessed'])==gc['total'],'native guidance totals inconsistent')
 # Detailed unaccepted guidance must be exported by the documented SVF
 # operation API before this collector can claim completeness.
 ids=single['guidance_unaccepted']
 need(len(ids)==gc['rejected']+gc['unsupported']+gc['unprocessed'],'native SVF unaccepted ID list/count mismatch')
 for identifier in ids:add('guidance_not_accepted',identifier,['guidance'])
 passed=set(pairs['passing'])|set(pairs['passing_pgpin']);qmatched=set(pairs['bbox_output']);inputmatched=set(pairs['bbox_input']);constpairs=set(pairs['const']);physical=[];seen_impl=set()
 need(len(macros['r'])==len(macros['i'])==374,'native SRAM inventory does not pair all374; record omissions for separate review')
 for ref,impl in pairs['bbox']:
  need(ref in macros['r'] and impl in macros['i'],'non-SRAM/uninventoried opaque pair')
  need(macros['r'][ref]==macros['i'][impl]=='RAMSP1024X16' and impl not in seen_impl,'opaque cell reference or pairing mismatch');seen_impl.add(impl)
  ps={}
  for name,(direction,width) in PORTS.items():
   bits=[]
   for bit in range(width):
    suffix=name if width==1 else name+'['+str(bit)+']';rp=ref+'/'+suffix;ip=impl+'/'+suffix
    need(rp in pins['r'][ref] and ip in pins['i'][impl],'native opaque pin missing:'+rp)
    expected_native='out' if direction=='output' else 'in';need(pins['r'][ref][rp]==pins['i'][impl][ip]==expected_native,'native opaque direction mismatch:'+rp)
    pair=(rp,ip)
    if direction=='output':need(pair in qmatched,'opaque Q pair not matched:'+rp);status='MATCHED_OPAQUE_OUTPUT'
    elif pair in passed and pair in inputmatched:status='VERIFIED_COMPARE_POINT'
    elif pair in constpairs and pair in inputmatched:status='VERIFIED_CONSTANT'
    else:raise ValueError('opaque input neither passed nor proved-constant:'+rp)
    bits.append(dict(reference_pin=rp,implementation_pin=ip,evidence_id=pair_id(pair),status=status))
   ps[name]=dict(direction=direction,width=width,bits=bits)
  need(len(pins['r'][ref])==len(pins['i'][impl])==67,'extra/missing opaque pins outside contract')
  canonical=ref.removeprefix('r:/WORK/'+TOP+'/');physical.append(dict(canonical_path=canonical,group=group(ref),cell_ref='RAMSP1024X16',disposition='PAIRED_OPAQUE',reference_path=ref,implementation_path=impl,ports=ps))
 need(len(physical)==374 and len(seen_impl)==374,'native bbox matching omitted SRAM instances')
 # Parse actual blackbox instance report, not available library definitions.
 report=(run/'reports/black_boxes.rpt').read_text();actual=set(re.findall(r'^\s*([ri]:/WORK/'+TOP+r'/\S+)[ \t]*$',report,re.M));need(actual==set(macros['r'])|set(macros['i']),'raw blackbox report contains missing/extra instance scopes')
 unresolved=(run/'reports/unresolved-black-boxes.rpt').read_text();need(not re.findall(r'^\s*[ri]:/\S+[ \t]*$',unresolved,re.M),'unresolved blackbox instances present')
 for role in REPORTS:need(role in provenance,'actual native report provenance missing:'+role)
 commands={role:sorted({re.match(r'\w+',cmd)[0] for _,cmd in provenance[role]}) for role in REPORTS}
 output=dict(schema='final374-fm-native-coverage-v1',collector_complete=True,api_contract_sha256=sha(contract_path),raw_reports={role:record(run/'reports'/(role+'.rpt')) for role in REPORTS},
  report_provenance={role:dict(returncode=0,phase='verified',commands=commands[role]) for role in REPORTS},unresolved_modules=[],unexpected_black_boxes=[],
  compare_counts=dict(passing=len(set(pairs['passing'])|set(pairs['passing_pgpin'])),failing=len(pairs['failing']),aborted=len(pairs['aborted']),unverified=len(pairs['unverified']),unread=len(pairs['unread'])),
  point_lists=point_lists,physical_macro_boundaries=physical,resource_limit=dict(max_cores=resources['max_cores'],native_report_role='resources'),guidance_counts=gc,
  native_collector=record(run/'coverage-native.tsv'),normalizer_sha256=sha(Path(__file__).resolve()),notes='Only actual enumerated native lists/pins; unknown formats fail, never become zero. Every HDL mismatch raw report still requires explicit review.')
 return output

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--api-contract',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'new normalized coverage output required');dump(a.out,normalize(a.run,a.api_contract));print('ACTUAL_NATIVE_COVERAGE_NORMALIZED_NOT_ACCEPTED')
if __name__=='__main__':
 try:main()
 except (ValueError,KeyError,OSError) as e:print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
