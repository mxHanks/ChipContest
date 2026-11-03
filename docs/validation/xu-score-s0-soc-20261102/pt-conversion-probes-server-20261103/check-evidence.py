#!/usr/bin/env python3
"""Recheck frozen actual PT conversion probes; never a qualification result."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
import gzip
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
UNITS={'fs':Decimal('1e-15'),'ps':Decimal('1e-12'),'ns':Decimal('1e-9')}
BAD=re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b',re.I)
PROBES={
 'pt-activity-conversion-probe-20261103-01':'probe_pt_activity_conversion.py',
 'pt-activity-conversion-tb-probe-20261103-02':'probe_pt_activity_tb02.py',
}

def need(value,message):
 if not value:raise ValueError(message)
def decode_json(raw):
 def unique(items):
  d={}
  for k,v in items:need(k not in d,'duplicate JSON key');d[k]=v
  return d
 return json.loads(raw,object_pairs_hook=unique)
def load(path):return decode_json(path.read_text())
def ident(path):
 raw=path.read_bytes();return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def same(path,record):
 need(path.is_file() and not path.is_symlink(),'missing/nonregular archived file '+str(path))
 need(ident(path)=={k:record[k]for k in ('bytes','sha256')},'archived input identity differs '+str(path))
def f32(x):return struct.unpack('!f',struct.pack('!f',float(x)))[0]
def printed(value):return Decimal(format(value,'.6g'))
def decode(token):return re.sub(r'\\(.)',r'\1',token)
def brace(text):
 need(not any(c in text for c in '{}\r\n'),'unsupported Tcl path')
 return '{'+text+'}'

def frozen_inputs():
 D=HERE/'recorded-frozen-inputs'
 prepared=load(D/'original-power-prepared.json')
 raw=gzip.decompress((D/'inventory.json.gz').read_bytes())
 inventory=decode_json(raw)
 need(dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())=={k:prepared['mapped_sram_inventory'][k]for k in('bytes','sha256')},'decompressed actual inventory differs')
 need(inventory['macro_count']==len(inventory['macros'])==336 and inventory['pin_bit_count']==22512,'actual inventory geometry differs')
 need(inventory['netlist']==prepared['netlist'],'actual inventory/prepared netlist differs')
 original=load(D/'original-power-detail-selected-manifest.json')
 need(next(r for r in original if r['path'].endswith('/inventory.json'))==dict(path='pt-macro-pin-inventory-20261103-01/inventory.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),'actual inventory original-manifest identity differs')
 need([{k:r[k]for k in('path','sha256')}for r in inventory['libraries']]==[{k:r[k]for k in('path','sha256')}for r in prepared['implementation']['libraries']],'actual inventory/prepared libraries differ')
 macro=inventory['macros'][0]
 need(macro['ref_name']=='RAMSP1024X16'and len(macro['pins'])==67,'actual probed macro differs')
 original=(D/'original-power.tcl').read_text()
 need(original.count('set XU_CLOCK_MODE')==1,'unexpected original power Tcl')
 prefix=original[original.index('set_app_var'):original.index('set XU_CLOCK_MODE')]
 return prepared,macro,prefix

def review_observer_plan():
 report=HERE/'recorded-frozen-inputs/sram-library.rpt';plan=load(HERE/'liberty-arc-observer-plan.json')
 need(ident(report)['sha256']==plan['report_sha256'],'actual library report identity differs')
 original=load(HERE/'recorded-frozen-inputs/original-power-detail-selected-manifest.json')
 need(len(original)==2 and len({r['path']for r in original})==2,'power-detail selected source scope differs')
 need(next(r for r in original if r['path'].endswith('/sram-library.rpt'))==dict(path='saif-power-task00-20261103-06/power/task_00/sram-library.rpt',**ident(report)),'library report original-manifest identity differs')
 rows=[]
 for line in report.read_text().splitlines():
  match=re.fullmatch(r'\s*(?:RAMSP1024X16\s+)?(l|i,rf,pg)\s+(\d+)\s*(.*?)\s*',line)
  if not match:continue
  kind,index,body=match.groups();pin=None
  if kind=='i,rf,pg':pin,_,body=body.partition(' ')
  rows.append(dict(arc_id=int(index),kind='leakage'if kind=='l'else'internal',toggling_pin=pin,when=' '.join(body.split())or'default'))
 need(rows==plan['arcs']and [r['arc_id']for r in rows]==list(range(121)),'actual power arc ledger differs')
 counts=Counter(r['kind']for r in rows);clock=[r for r in rows if r['toggling_pin']=='CLK']
 need(counts==dict(leakage=2,internal=119)and len(clock)==42,'actual power arc counts differ')
 need(sum(bool(r['toggling_pin']and r['toggling_pin'].startswith('D['))for r in rows)==32,'data conditional arc count differs')
 need(sum(bool(r['toggling_pin']and r['toggling_pin'].startswith('Q['))for r in rows)==16,'output conditional arc count differs')
 # This is a Boolean completeness check of the *known* control modes, not
 # measured activity or an excuse to collapse four-state controls to Boolean.
 def holds(expr,bits):
  return all((not bits[term[1:]]if term.startswith('!')else bits[term])for term in expr.split(' & '))
 names=plan['control_vector_order']
 need(names==['RET1N','CEN','GWEN','EMA[2]','EMA[1]','EMA[0]','EMAW[1]','EMAW[0]'],'joint control order differs')
 for values in itertools.product((False,True),repeat=8):
  need(sum(holds(r['when'],dict(zip(names,values)))for r in clock)==1,'known clock modes do not partition control domain')
 need(plan['status']=='SPECIFICATION_ONLY_NOT_MEASURED'and plan['qualification']=='NOT_QUALIFIED','observer specification claimed measured qualification')
 return dict(source_report_sha256=ident(report)['sha256'],arc_count=121,internal_arc_count=119,clock_arc_count=42,known_control_combinations_checked=256,status='SPECIFICATION_ONLY_NOT_MEASURED')

def extract_saif(reader,path):
 tree=reader.parse_sexpr(path.read_text());headers={};signals={}
 for node in tree[1:]:
  if isinstance(node,list)and node[0]!='INSTANCE':
   need(node[0]not in headers,'duplicate SAIF header');headers[node[0]]=node[1:]
 need(headers['TIMESCALE'][0]=='1'and headers['TIMESCALE'][1]in UNITS,'unexpected actual probe time unit')
 duration=int(headers['DURATION'][0]);need(duration>0,'duration invalid')
 def visit(node,parts):
  if not isinstance(node,list)or not node:return
  if node[0]=='INSTANCE':
   for child in node[2:]:visit(child,parts+[decode(node[1])])
  elif node[0]in('PORT','NET'):
   for signal in node[1:]:
    name='/'.join(parts+[decode(signal[0])]);need(name not in signals,'duplicate synthetic signal')
    stats={}
    for stat in signal[1:]:
     need(len(stat)==2 and stat[0]not in stats and re.fullmatch(r'[0-9]+',stat[1]),'malformed synthetic stat')
     stats[stat[0]]=int(stat[1])
    signals[name]=dict(kind=node[0],stats=stats)
  else:
   for child in node[1:]:visit(child,parts)
 for node in tree[1:]:visit(node,[])
 return duration,headers['TIMESCALE'][1],signals

def compare_case(rec,row,duration,tick,unit):
 p=rec['stats'];elapsed=Decimal(duration)*tick
 with localcontext()as ctx:
  ctx.prec=70
  tr=Decimal(p['TC'])*unit/elapsed
  models={
   'decimal_exact_then_6g':printed(tr),
   'binary32_counts_divide_ticks_then_scale_binary32_6g':printed(f32(f32(f32(p['TC'])/f32(duration))*float(unit/tick))),
   'binary32_divide_physical_duration_in_library_units_6g':printed(f32(f32(p['TC'])/f32(Decimal(duration)*tick/unit))),
   'binary32_exact_rate_then_6g':printed(f32(tr)),
  }
  known=p['T0']+p['T1'];sp=Decimal(p['T1'])/known if known else Decimal('.5')
  spmodels={
   't1_over_total_duration_6g':printed(Decimal(p['T1'])/duration),
   'known_dwell_ratio_or_half_6g':printed(sp),
   'binary32_known_dwell_ratio_or_half_6g':printed(f32(sp)),
  }
  ig=Decimal(p.get('IG',0));gm={
   'ig_over_duration_6g':printed(ig*unit/elapsed),
   'ig_half_over_duration_6g':printed(ig*unit/(2*elapsed)),
  }
  # These model comparisons are observations, not a validated numeric policy.
  return dict(label=rec['label'],mapped_path=rec['mapped_path'],stats=p,
   dwell_sum_ticks=sum(p.get(k,0)for k in('T0','T1','TX','TZ','TB')),
   dwell_matches_duration=sum(p.get(k,0)for k in('T0','T1','TX','TZ','TB'))==duration,
   observed={field:dict(raw=row[field],source=row[{'toggle_rate':'toggle_source','glitch_rate':'glitch_source','static_probability':'static_source'}[field]])for field in('toggle_rate','glitch_rate','static_probability')},
   exact_simple_toggle_rate=str(tr),
   toggle_models={key:dict(expected=str(value),agrees=value==row['toggle_rate_value'])for key,value in models.items()},
   static_models={key:dict(expected=str(value),agrees=value==row['static_probability_value'])for key,value in spmodels.items()},
   glitch_models={key:dict(expected=str(value),agrees=value==row['glitch_rate_value'])for key,value in gm.items()})

def review():
 original=load(HERE/'original-export-manifest.json');selected=load(HERE/'selected-manifest.json')
 need(isinstance(original,list)and len(original)==196 and len({x['path']for x in original})==len(original),'original manifest duplicate/malformed')
 indexed={x['path']:x for x in original}
 expected={x['path']for x in original if any(x['path'].startswith(name+'/')for name in PROBES)}
 need(len(selected)==74 and {x['path']for x in selected}==expected,'selected archive scope differs')
 for rec in selected:
  need({k:rec[k]for k in('path','bytes','sha256')}==indexed[rec['path']],'selected/original manifest differs')
  need(rec['archive_path']=='raw/'+rec['path'],'archive relative path differs')
  path=HERE/rec['archive_path'];need(path.resolve()==path,'archive symlink/traversal');same(path,rec)
 # Shared project parsers do syntax/numeric checks; they do not supply an
 # acceptable conversion tolerance or silently repair malformed dwell.
 spec=importlib.util.spec_from_file_location('xu_saif_reader',ROOT/'tools/scripts/xu_soc_activity.py');reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
 spec=importlib.util.spec_from_file_location('xu_compact_review',ROOT/'tools/ppa/xu_soc_pin_activity_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 prepared,actual_macro,actual_prefix=frozen_inputs()
 output=dict(schema='xu-pt-synthetic-conversion-review-v1',status='ACTUAL_PROBES_REVIEWED_POLICY_UNRESOLVED',qualification='NOT_QUALIFIED',
  selected_file_count=len(selected),selected_bytes=sum(r['bytes']for r in selected),groups=[],
  limitations=['These are synthetic SAIF counts on actual linked library objects, not measured task activity.',
   'All queried pins are on one actually linked RAMSP1024X16; input direction/macro diversity is not established by probes 01/02.',
   'Model agreement at six printed digits does not prove integer count fidelity or a unique internal conversion algorithm.',
   'The invalid TB input remains raw evidence of tool acceptance; acceptance does not validate its interpretation.',
   'No Liberty conditional power, joint SRAM mode, standard-cell annotation coverage, task energy or 150MHz qualification is established.'])
 output['observer_plan_review']=review_observer_plan()
 for name,producer in PROBES.items():
  directory=HERE/'raw'/name;state=load(directory/'result.json')
  need(state['status']=='PROBES_EXECUTED_REVIEW_PENDING_NOT_QUALIFIED','probe is not terminal')
  same(HERE/'recorded-producers'/producer,state['probe'])
  need(state.get('frozen_inputs')and state['original_prepared']['sha256'],'probe original input freeze absent')
  need(state['netlist']==prepared['netlist']and state['analysis_sdc']==prepared['analysis_sdc']and state['inventory']==prepared['mapped_sram_inventory'],'actual frozen design/SDC/inventory differs')
  same(HERE/'recorded-frozen-inputs/original-power-prepared.json',state['original_prepared'])
  small={'/prepared.json':HERE/'recorded-frozen-inputs/original-power-prepared.json','/power.tcl':HERE/'recorded-frozen-inputs/original-power.tcl'}
  need(len(state['frozen_inputs'])==4,'frozen server input scope differs')
  for path,record in state['frozen_inputs'].items():
   need(record['path']==path,'frozen server input path differs')
   if path==state['probe']['path']:need(record==state['probe'],'frozen producer identity differs')
   elif path==state['inventory']['path']:need(record==state['inventory'],'frozen inventory identity differs')
   else:
    matched=[local for suffix,local in small.items()if path.endswith(suffix)]
    need(len(matched)==1,'unexpected frozen server input');same(matched[0],record)
  labels=[g['label']for g in state['groups']];need(len(set(labels))==len(labels),'duplicate group')
  need(set(labels)==({'known-fs','known-ps','known-ns','tz','tb','ig'}if name.endswith('-01')else{'tb'}),'unexpected group scope')
  for group in state['groups']:
   label=group['label'];D=directory/label
   need(group['status']=='EXPORTED_REVIEW_PENDING_NOT_QUALIFIED'and group['execution']['returncode']==0,'PT group failed')
   need(group['execution']['command']==['pt_shell','-f','probe.tcl'],'unexpected actual tool invocation')
   need(set(group['artifacts'])=={'cases.json','synthetic.saif','probe.tcl','pt.log','pt_shell_command.log','pins.tsv','read-saif.rpt','inconsistent.rpt','units.rpt','tool-version.rpt'},'actual artifact set differs')
   for filename,record in group['artifacts'].items():same(D/filename,record)
   same(D/'pt.log',group['execution']['log'])
   lines=(D/'pt.log').read_text().splitlines()
   need(lines.count('XU_ACTIVITY_CONVERSION_PROBE_COMPLETE')==1 and lines.count('XU_ACTIVITY_CONVERSION_EXPORTED_REVIEW_PENDING')==1,'completion marker differs')
   need(not any(BAD.search(line)for line in lines),'PT fatal diagnostic')
   need((D/'tool-version.rpt').read_text().strip()=='T-2022.03-SP5-1','different actual PT version')
   cases=load(D/'cases.json');records=cases['records']
   need(cases['synthetic']is True and cases['qualification']=='NOT_QUALIFIED'and len(records)==group['case_count'],'case identity differs')
   duration,timescale,signals=extract_saif(reader,D/'synthetic.saif')
   need(duration==cases['duration_ticks']==9139040000000 and timescale==cases['timescale_unit']==group['timescale_unit'],'actual synthetic units/duration differ')
   need(len(records)==len(signals)and len({r['label']for r in records})==len(records),'duplicate/missing record')
   need({r['mapped_path']for r in records}=={p[len('probe/dut/'):]for p in signals},'synthetic/query object sets differ')
   need(len(records)<=len(actual_macro['pins']),'too many actual pin queries')
   for rec,pin in zip(records,actual_macro['pins']):
    need(rec['pin_name']==pin['name']and rec['mapped_path']==pin['full_name']and pin['direction']=='in','actual probe pin inventory/order/direction differs')
   for rec in records:
    need(signals['probe/dut/'+rec['mapped_path']]==dict(kind='PORT',stats=rec['stats']),'SAIF/case exact stats differ')
   rows=audit.parse_compact(D/'pins.tsv','before',{r['mapped_path']for r in records})
   need(all(row[key]=='file'for row in rows.values()for key in('toggle_source','glitch_source','static_source')),'actual query is not all file sourced')
   tcl=(D/'probe.tcl').read_text();commands=[line.strip()for line in tcl.splitlines()if line.strip()and not line.lstrip().startswith('#')]
   need(tcl.startswith('if {[catch {\n'+actual_prefix+'\nredirect -file units.rpt {report_units}\n'),'actual original design/library link prefix differs')
   libs=prepared['implementation']['libraries']
   need([line for line in commands if line.startswith('set_app_var link_path ')]==['set_app_var link_path [list * '+' '.join(brace(r['path'])for r in libs)+']'],'actual linked library command differs')
   need(commands.count('read_verilog '+brace(state['netlist']['path']))==1,'actual mapped design read differs')
   need(not any(re.search(r'(?<![A-Za-z0-9_])'+command+r'[ \t]+',line)for command in('create_clock','set_case_analysis','set_switching_activity','update_power')for line in commands),'probe includes an annotation override or power update')
   expected_read='redirect -file read-saif.rpt {if {![read_saif '+brace(group['execution']['cwd']+'/synthetic.saif')+' -strip_path {probe/dut} -report_inconsistent_annotation inconsistent.rpt]} {error {synthetic SAIF read failed}}}'
   need([line for line in commands if 'read_saif 'in line]==[expected_read],'actual synthetic SAIF path/strip command differs')
   need([line for line in commands if line.startswith('set xu_p [get_pins -quiet ')]==['set xu_p [get_pins -quiet '+brace(r['mapped_path'])+']'for r in records],'actual object query command sequence differs')
   unit=audit.unit_seconds((D/'units.rpt').read_bytes());need(unit==Decimal('1e-9'),'actual linked library time unit differs')
   comparisons=[compare_case(r,rows[r['mapped_path']],duration,UNITS[timescale],unit)for r in records]
   malformed=[r['label']for r in comparisons if not r['dwell_matches_duration']]
   need(malformed==(['tb']if name.endswith('-01')and label=='tb'else[]),'unexpected invalid synthetic dwell')
   try:
    parsed=reader.read_saif(D/'synthetic.saif');need(not malformed and len(parsed['signals'])==len(records),'strict reader accepted malformed dwell')
   except ValueError as error:
    need(bool(malformed)and 'dwell' in str(error),'strict reader failed a valid group')
   collapsed=defaultdict(list)
   for rec in comparisons:
    if rec['label'].startswith('tc_'):collapsed[rec['observed']['toggle_rate']['raw']].append(dict(label=rec['label'],TC=rec['stats']['TC']))
   matches={field:dict(Counter(key for rec in comparisons for key,model in rec[field].items()if model['agrees']))for field in('toggle_models','static_models','glitch_models')}
   output['groups'].append(dict(probe=name,label=label,case_count=len(records),duration_ticks=duration,timescale_seconds=str(UNITS[timescale]),library_time_unit_seconds=str(unit),
     all_three_fields_file=True,malformed_dwell_cases=malformed,model_agreement_counts=matches,
     different_counts_with_identical_printed_rate={k:v for k,v in collapsed.items()if len(v)>1},cases=comparisons))
 output['group_count']=len(output['groups']);output['case_count']=sum(g['case_count']for g in output['groups'])
 return output


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-summary',action='store_true');args=parser.parse_args()
 summary=review();path=HERE/'summary.json'
 if args.write_summary:
  need(not path.exists(),'summary must be a new artifact');path.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
 else:
  need(load(path)==summary,'saved summary differs from recomputation')
  frozen=load(HERE/'sha256.json')
  actual={str(p.relative_to(HERE))for p in HERE.rglob('*')if p.is_file()and '__pycache__'not in p.parts and p.name!='sha256.json'}
  need(set(frozen)==actual,'archive frozen file set differs')
  for filename,record in frozen.items():
   path=HERE/filename
   need(path.resolve()==path and path.is_relative_to(HERE),'archive frozen path traversal/symlink')
   same(path,record)
 print('XU_CONVERSION_EVIDENCE_RECHECKED groups=%d cases=%d qualification=NOT_QUALIFIED'%(summary['group_count'],summary['case_count']))
 for g in summary['groups']:
  print(g['probe'],g['label'],g['case_count'],g['model_agreement_counts']['toggle_models'],g['malformed_dwell_cases'])
if __name__=='__main__':main()
