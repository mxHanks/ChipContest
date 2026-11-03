#!/usr/bin/env python3
"""Recheck actual TC515 conversion counterexamples; never qualify task power."""
import argparse
from collections import Counter
from decimal import Decimal
import gzip
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PRIOR=HERE.parent/'pt-conversion-probes-server-20261103'
NAME='pt-activity-conversion-515-probe-20261103-03'

def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=module('xu_conversion_probe_prior',PRIOR/'check-evidence.py')
need,load,same,ident=base.need,base.load,base.same,base.ident

def review():
 for filename,record in load(HERE/'prior-archive-identity.json').items():same(PRIOR/filename,record)
 oldfrozen=load(PRIOR/'sha256.json')
 oldset={str(p.relative_to(PRIOR))for p in PRIOR.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name!='sha256.json'}
 need(set(oldfrozen)==oldset,'prior archive frozen file set differs')
 for filename,record in oldfrozen.items():same(PRIOR/filename,record)
 base.review()
 prepared,macro,prefix=base.frozen_inputs()
 original=load(HERE/'original-export-manifest.json');selected=load(HERE/'selected-manifest.json')
 need(len(original)==174 and len({r['path']for r in original})==174,'original export scope/uniqueness differs')
 expected={r['path']:r for r in original if r['path'].startswith(NAME+'/')}
 need(len(selected)==len(expected)==12 and {r['path']for r in selected}==set(expected),'selected actual export scope differs')
 for rec in selected:
  need({k:rec[k]for k in('path','bytes','sha256')}==expected[rec['path']]and rec['archive_path']=='raw/'+rec['path'],'selected/original raw identity differs')
  path=HERE/rec['archive_path'];need(path.resolve()==path and path.is_relative_to(HERE),'raw path traversal/symlink');same(path,rec)
 D=HERE/'raw'/NAME;state=load(D/'result.json')
 need(state['status']=='PROBES_EXECUTED_REVIEW_PENDING_NOT_QUALIFIED'and len(state['groups'])==1,'probe did not finish uniquely')
 same(HERE/'recorded-producers/probe_pt_activity_conversion515_03.py',state['probe'])
 need(state['netlist']==prepared['netlist']and state['analysis_sdc']==prepared['analysis_sdc']and state['inventory']==prepared['mapped_sram_inventory'],'actual design/SDC/inventory differs')
 same(PRIOR/'recorded-frozen-inputs/original-power-prepared.json',state['original_prepared'])
 need(len(state['frozen_inputs'])==4,'frozen server input set differs')
 for path,rec in state['frozen_inputs'].items():
  need(path==rec['path'],'frozen server path differs')
  if path==state['probe']['path']:need(rec==state['probe'],'frozen producer differs')
  elif path==state['inventory']['path']:need(rec==state['inventory'],'frozen inventory differs')
  elif path.endswith('/prepared.json'):same(PRIOR/'recorded-frozen-inputs/original-power-prepared.json',rec)
  elif path.endswith('/power.tcl'):same(PRIOR/'recorded-frozen-inputs/original-power.tcl',rec)
  else:raise ValueError('unexpected frozen server input')
 group=state['groups'][0];G=D/'tc515-witness-fs'
 need(group['label']=='tc515-witness-fs'and group['timescale_unit']=='fs'and group['case_count']==12,'probe group scope differs')
 need(group['status']=='EXPORTED_REVIEW_PENDING_NOT_QUALIFIED'and group['execution']['returncode']==0 and group['execution']['command']==['pt_shell','-f','probe.tcl'],'actual PT invocation/exit differs')
 need(set(group['artifacts'])=={'cases.json','synthetic.saif','probe.tcl','pt.log','pt_shell_command.log','pins.tsv','read-saif.rpt','inconsistent.rpt','units.rpt','tool-version.rpt'},'actual artifact scope differs')
 for filename,record in group['artifacts'].items():same(G/filename,record)
 same(G/'pt.log',group['execution']['log'])
 lines=(G/'pt.log').read_text().splitlines()
 need(lines.count('XU_ACTIVITY_CONVERSION_PROBE_COMPLETE')==1 and lines.count('XU_ACTIVITY_CONVERSION_EXPORTED_REVIEW_PENDING')==1 and not any(base.BAD.search(line)for line in lines),'actual PT marker/fatal differs')
 need((G/'tool-version.rpt').read_text().strip()=='T-2022.03-SP5-1','actual PT version differs')
 reader=module('xu_tc515_saif_reader',base.ROOT/'tools/scripts/xu_soc_activity.py')
 audit=module('xu_tc515_compact_review',base.ROOT/'tools/ppa/xu_soc_pin_activity_audit.py')
 cases=load(G/'cases.json');records=cases['records'];need(cases['synthetic']is True and cases['qualification']=='NOT_QUALIFIED'and len(records)==12,'synthetic case scope differs')
 duration,timescale,signals=base.extract_saif(reader,G/'synthetic.saif')
 need(duration==cases['duration_ticks']==9139040000000 and timescale==cases['timescale_unit']=='fs','actual duration/unit differs')
 need(len(reader.read_saif(G/'synthetic.saif')['signals'])==12,'strict synthetic dwell/signal scope differs')
 need(len({r['label']for r in records})==12 and {r['mapped_path']for r in records}=={p[len('probe/dut/'):]for p in signals},'synthetic object/query set differs')
 actual={p['name']:p for p in macro['pins']}
 expected_pins=['A[0]','Q[0]','A[1]','Q[1]','A[2]','Q[2]','A[3]','Q[3]','Q[4]','Q[5]','Q[6]','Q[7]']
 need([r['probe_pin']for r in records]==expected_pins,'actual input/output contrast pin order differs')
 expected_labels=[direction+'_known_tc'+str(tc)for tc in(514,515,516)for direction in('input','output')]+['input_partial_x_tc515','output_partial_x_tc515']+['actual_unknown_q_witness_'+str(i)for i in range(4)]
 need([r['label']for r in records]==expected_labels,'contrast/witness label order differs')
 for index,rec in enumerate(records[:8]):
  tc=(514,515,516)[index//2]if index<6 else 515;tx=0 if index<6 else 1000
  need(rec['stats']==dict(T0=6092693333334-tx,T1=3046346666666,TC=tc,TX=tx,IG=0),'known/partial-X contrast stats differ')
 for rec in records:
  pin=actual[rec['probe_pin']]
  need(rec['pin_name']==pin['name']and rec['mapped_path']==pin['full_name']and pin['direction']==('in'if pin['name'].startswith('A[')else'out'),'actual pin direction/identity differs')
  need(signals['probe/dut/'+rec['mapped_path']]==dict(kind='PORT',stats=rec['stats']),'actual synthetic SAIF/case stats differ')
 rows=audit.parse_compact(G/'pins.tsv','before',{r['mapped_path']for r in records})
 need(all(row[k]=='file'for row in rows.values()for k in('toggle_source','glitch_source','static_source')),'actual query source is not file')
 unit=audit.unit_seconds((G/'units.rpt').read_bytes());need(unit==Decimal('1e-9'),'actual library time unit differs')
 tcl=(G/'probe.tcl').read_text();commands=[line.strip()for line in tcl.splitlines()if line.strip()and not line.lstrip().startswith('#')]
 need(tcl.startswith('if {[catch {\n'+prefix+'\nredirect -file units.rpt {report_units}\n'),'actual original link prefix differs')
 need(not any(base.re.search(r'(?<![A-Za-z0-9_])'+command+r'[ \t]+',line)for command in('create_clock','set_case_analysis','set_switching_activity','update_power')for line in commands),'probe included override/clock/power command')
 expected_read='redirect -file read-saif.rpt {if {![read_saif '+base.brace(group['execution']['cwd']+'/synthetic.saif')+' -strip_path {probe/dut} -report_inconsistent_annotation inconsistent.rpt]} {error {synthetic SAIF read failed}}}'
 need([line for line in commands if 'read_saif 'in line]==[expected_read],'actual synthetic read/strip differs')
 need([line for line in commands if line.startswith('set xu_p [get_pins -quiet ')]==['set xu_p [get_pins -quiet '+base.brace(r['mapped_path'])+']'for r in records],'actual ordered query differs')
 raw=gzip.decompress((HERE/'recorded-frozen-inputs/measured-sram-pins.json.gz').read_bytes())
 identity=dict(bytes=len(raw),sha256=base.hashlib.sha256(raw).hexdigest())
 need(identity=={k:prepared['tasks'][0]['measured_sram_pin_states'][k]for k in('bytes','sha256')},'actual task measured pin source differs')
 source=load(HERE/'recorded-frozen-inputs/original-measured-manifest.json')
 need(source==dict(path='saif-power-task00-20261103-06/power/task_00/measured-sram-pins.json',**identity),'actual measured source manifest differs')
 measured=base.decode_json(raw);pins=measured['pins'];need(len(pins)==22512 and len({p['mapped_path']for p in pins})==22512,'measured pin source scope differs')
 by_path={p['mapped_path']:p for p in pins};witnesses=[]
 for rec in records:
  if not rec['label'].startswith('actual_unknown_q_witness_'):continue
  original=by_path[rec['original_measured_path']]
  need(original['kind']=='PORT'and {k:original[k]for k in rec['stats']}==rec['stats']and original['TX']>0,'actual partial-X Q witness stats differ')
  witnesses.append(dict(label=rec['label'],original_measured_path=rec['original_measured_path'],replay_pin=rec['mapped_path'],stats=rec['stats']))
 need(len(witnesses)==4 and len({w['original_measured_path']for w in witnesses})==4,'partial-X Q witness scope differs')
 comparisons=[base.compare_case(r,rows[r['mapped_path']],duration,Decimal('1e-15'),unit)for r in records]
 matches={field:dict(Counter(key for rec in comparisons for key,model in rec[field].items()if model['agrees']))for field in('toggle_models','static_models','glitch_models')}
 contrast=[]
 for tc in(514,515,516):
  pair=[r for r in comparisons if r['label']in('input_known_tc'+str(tc),'output_known_tc'+str(tc))]
  need(len(pair)==2,'known input/output contrast missing')
  contrast.append(dict(TC=tc,input=pair[0]['observed'],output=pair[1]['observed'],identical=pair[0]['observed']==pair[1]['observed']))
 return dict(schema='xu-pt-tc515-conversion-review-v1',status='ACTUAL_COUNTEREXAMPLES_REVIEWED_POLICY_UNRESOLVED',qualification='NOT_QUALIFIED',selected_file_count=12,selected_bytes=sum(r['bytes']for r in selected),case_count=12,all_three_fields_file=True,model_agreement_counts=matches,input_output_contrasts=contrast,partial_x_q_witnesses=witnesses,cases=comparisons,limitations=['All annotations are synthetic replay on one actual linked macro, not a new task measurement.','The four Q witnesses have positive TX and positive known dwell; they are not full-X pins.','The measured witness source is independently rechecked locally against the original prepared SHA; the server probe hard-coded these stats and did not freeze/read that source itself.','The staged binary32 model that matched probes 01/02 is contradicted by TC515 cases; no new tolerance or conversion policy is accepted.','No conditional Liberty activity, full-SoC energy, complete 150MHz timing or contest score is established.'])

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-summary',action='store_true');args=parser.parse_args();summary=review()
 if args.write_summary:
  need(not(HERE/'summary.json').exists(),'summary must be new');(HERE/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 else:
  need(load(HERE/'summary.json')==summary,'saved TC515 summary differs')
  frozen=load(HERE/'sha256.json');actual={str(p.relative_to(HERE))for p in HERE.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name!='sha256.json'};need(set(frozen)==actual,'frozen TC515 archive set differs')
  for filename,record in frozen.items():
   path=HERE/filename;need(path.resolve()==path and path.is_relative_to(HERE),'frozen TC515 path traversal/symlink');same(path,record)
 print('XU_TC515_CONVERSION_RECHECKED cases=12 qualification=NOT_QUALIFIED')
 print(json.dumps(summary['model_agreement_counts'],sort_keys=True))
if __name__=='__main__':main()
