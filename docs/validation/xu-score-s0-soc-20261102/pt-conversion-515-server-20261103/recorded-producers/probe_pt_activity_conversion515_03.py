#!/usr/bin/env python3
"""Fresh actual PT probes only. No credentials, no mutation of prior evidence.

Run without args to fork a driver. Each group links the original mapped design
in a fresh PT process and annotates synthetic SAIF on one *actual* SRAM's pins.
The synthetic records establish conversion behavior, never task energy.
"""
from pathlib import Path
import hashlib, importlib.util, json, os, re, subprocess, sys, time
B = Path.home() / 'Desktop/xu-score-optimization-20261102'
R = B / 'ChipContest-clear-alias-20261103'
P = B / 'saif-power-task00-20261103-06/power'
I = B / 'pt-macro-pin-inventory-20261103-01/inventory.json'
O = B / 'pt-activity-conversion-515-probe-20261103-03'
MARK = 'XU_ACTIVITY_CONVERSION_PROBE_COMPLETE'
BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)

def ident(p):
 p = Path(p); raw = p.read_bytes()
 return dict(path=str(p.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
def save(j): (O/'result.json').write_text(json.dumps(j, indent=2, sort_keys=True)+'\n')
def atom(s): return re.sub(r'([\\()\s\[\]".])', r'\\\1', s)
def tcl(s):
 if any(c in s for c in '{}\r\n'): raise ValueError('unsafe Tcl literal')
 return '{'+s+'}'
def cases(d):
 out = []
 def add(label, TC=0, T1=None, TX=0, TZ=0, TB=None, IG=None):
  known = d-TX-TZ; T1 = known//3 if T1 is None else T1
  stats=dict(T0=known-T1,T1=T1,TX=TX,TC=TC)
  if TZ: stats['TZ']=TZ
  if TB is not None: stats['TB']=TB
  if IG is not None: stats['IG']=IG
  out.append(dict(label=label,stats=stats))
 for tc in (0,1,2,3,7,31,255,1023,8156,8157,8158,73919,73920,73921,2741713,2741714,2741715,16777215,16777216,16777217,33554431,33554432,33554433): add('tc_'+str(tc),TC=tc)
 add('static_zero',T1=0); add('static_one',T1=d)
 add('static_half',T1=d//2); add('static_one_tick',T1=1)
 add('static_last_tick',T1=d-1); add('static_ratio_2_3',T1=2*d//3)
 add('x_partial',TC=101,TX=d//7); add('x_all',TX=d,T1=0)
 return out

def saif(macro, records, duration, unit):
 lines=['(SAIFILE',' (SAIFVERSION "2.0")',' (DIRECTION "backward")',' (DESIGN "xu_soc_ppa_top")',
        ' (DATE "synthetic conversion probe")',' (VENDOR "xu synthetic evidence")',
        ' (PROGRAM_NAME "xu_pt_activity_conversion_probe")',' (VERSION "1")',
        ' (DIVIDER /)',' (TIMESCALE 1 '+unit+')',' (DURATION '+str(duration)+')',
        ' (INSTANCE probe','  (INSTANCE dut']
 parts=macro.split('/')
 for part in parts: lines.append('   (INSTANCE '+atom(part))
 lines.append('    (PORT')
 for rec in records:
  fields=' '.join('('+key+' '+str(value)+')' for key,value in rec['stats'].items())
  lines.append('     ('+atom(rec['pin_name'])+' '+fields+')')
 lines.append('    )');lines.extend('   )' for _ in parts);lines.extend(['  )',' )',')'])
 return '\n'.join(lines)+'\n'

if len(sys.argv)==1:
 O.mkdir(exist_ok=False)
 with (O/'driver.log').open('x') as f:
  child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
 print('PT_ACTIVITY_CONVERSION_PROBE_STARTED',child.pid);sys.exit(0)
j=dict(status='RUNNING_REVIEW_PENDING_NOT_QUALIFIED',started_epoch=time.time(),probe=ident(__file__),groups=[]);save(j)
try:
 spec=importlib.util.spec_from_file_location('xu_original_power',R/'tools/scripts/xu_soc_saif_power.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 prepared=m.read_json(P/'prepared.json');m.verify_prepared(P,prepared)
 inventory=json.loads(I.read_text());macro=inventory['macros'][0]
 if macro['ref_name']!='RAMSP1024X16' or len(macro['pins'])!=67: raise ValueError('unexpected actual macro')
 original=(P/'task_00/power.tcl').read_text()
 if original.count('set XU_CLOCK_MODE')!=1: raise ValueError('unknown frozen original PT script')
 prefix=original[original.index('set_app_var'):original.index('set XU_CLOCK_MODE')]
 frozen={str(x):ident(x) for x in [Path(__file__).resolve(),I,P/'prepared.json',P/'task_00/power.tcl']}
 duration=9139040000000
 groups=[('tc515-witness-fs','fs',[{'label': 'input_known_tc514', 'probe_pin': 'A[0]', 'stats': {'T0': 6092693333334, 'T1': 3046346666666, 'TX': 0, 'TC': 514, 'IG': 0}}, {'label': 'output_known_tc514', 'probe_pin': 'Q[0]', 'stats': {'T0': 6092693333334, 'T1': 3046346666666, 'TX': 0, 'TC': 514, 'IG': 0}}, {'label': 'input_known_tc515', 'probe_pin': 'A[1]', 'stats': {'T0': 6092693333334, 'T1': 3046346666666, 'TX': 0, 'TC': 515, 'IG': 0}}, {'label': 'output_known_tc515', 'probe_pin': 'Q[1]', 'stats': {'T0': 6092693333334, 'T1': 3046346666666, 'TX': 0, 'TC': 515, 'IG': 0}}, {'label': 'input_known_tc516', 'probe_pin': 'A[2]', 'stats': {'T0': 6092693333334, 'T1': 3046346666666, 'TX': 0, 'TC': 516, 'IG': 0}}, {'label': 'output_known_tc516', 'probe_pin': 'Q[2]', 'stats': {'T0': 6092693333334, 'T1': 3046346666666, 'TX': 0, 'TC': 516, 'IG': 0}}, {'label': 'input_partial_x_tc515', 'probe_pin': 'A[3]', 'stats': {'T0': 6092693332334, 'T1': 3046346666666, 'TX': 1000, 'TC': 515, 'IG': 0}}, {'label': 'output_partial_x_tc515', 'probe_pin': 'Q[3]', 'stats': {'T0': 6092693332334, 'T1': 3046346666666, 'TX': 1000, 'TC': 515, 'IG': 0}}, {'label': 'actual_unknown_q_witness_0', 'probe_pin': 'Q[4]', 'original_measured_path': 'u_shared/storage/macro_storage.depth_bank[0].width_lane[0].macro/Q[2]', 'stats': {'T0': 506873333337, 'T1': 6584719989997, 'TX': 2047446676666, 'TC': 515, 'IG': 0}}, {'label': 'actual_unknown_q_witness_1', 'probe_pin': 'Q[5]', 'original_measured_path': 'u_shared/storage/macro_storage.depth_bank[12].width_lane[0].macro/Q[10]', 'stats': {'T0': 887233333340, 'T1': 8249866656660, 'TX': 1940010000, 'TC': 515, 'IG': 0}}, {'label': 'actual_unknown_q_witness_2', 'probe_pin': 'Q[6]', 'original_measured_path': 'u_shared/storage/macro_storage.depth_bank[16].width_lane[0].macro/Q[6]', 'stats': {'T0': 977960000006, 'T1': 8157199989994, 'TX': 3880010000, 'TC': 515, 'IG': 0}}, {'label': 'actual_unknown_q_witness_3', 'probe_pin': 'Q[7]', 'original_measured_path': 'u_shared/storage/macro_storage.depth_bank[8].width_lane[0].macro/Q[5]', 'stats': {'T0': 1060686666665, 'T1': 8078353323335, 'TX': 10000, 'TC': 515, 'IG': 0}}])]
 for label,unit,records in groups:
  D=O/label;D.mkdir(exist_ok=False)
  by_pin={pin['name']:pin for pin in macro['pins']}
  for rec in records:
   pin=by_pin[rec['probe_pin']]
   rec.update(pin_name=pin['name'],mapped_path=pin['full_name'])
  (D/'synthetic.saif').write_text(saif(macro['instance'],records,duration,unit))
  (D/'cases.json').write_text(json.dumps(dict(synthetic=True,qualification='NOT_QUALIFIED',duration_ticks=duration,timescale_unit=unit,records=records),indent=2,sort_keys=True)+'\n')
  body=prefix+'\nredirect -file units.rpt {report_units}\n'
  body+='redirect -file read-saif.rpt {if {![read_saif '+tcl(str(D/'synthetic.saif'))+' -strip_path {probe/dut} -report_inconsistent_annotation inconsistent.rpt]} {error {synthetic SAIF read failed}}}\n'
  body+='set xu_f [open pins.tsv {WRONLY CREAT EXCL}]\nputs $xu_f "phase\\tdesired_name\\treported_name\\ttoggle_rate\\ttoggle_source\\tglitch_rate\\tglitch_source\\tstatic_probability\\tstatic_source"\n'
  for rec in records:
   body+='set xu_p [get_pins -quiet '+tcl(rec['mapped_path'])+']\nif {[sizeof_collection $xu_p] != 1} {error {actual probe pin absent}}\n'
   body+='set xu_name [get_object_name $xu_p]\nset xu_a [get_switching_activity -toggle_rate -glitch_rate -static_probability $xu_p]\nif {[llength $xu_a] != 1 || [llength [lindex $xu_a 0]] != 7} {error {unexpected actual query tuple}}\nset xu_row [linsert [lindex $xu_a 0] 0 before $xu_name]\nforeach xu_field $xu_row {if {[regexp {[\\t\\r\\n]} $xu_field]} {error {TSV control in actual query}}}\nputs $xu_f [join $xu_row "\\t"]\n'
  body+='close $xu_f\nputs {XU_ACTIVITY_CONVERSION_EXPORTED_REVIEW_PENDING}\n'
  (D/'probe.tcl').write_text(m.ppa.guarded_tcl(body,MARK))
  execution=m.execute(['pt_shell','-f','probe.tcl'],D,D/'pt.log',1200,m.execution_environment('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
  log=(D/'pt.log').read_text(errors='replace')
  state=dict(label=label,timescale_unit=unit,case_count=len(records),execution=execution,
   status=('EXPORTED_REVIEW_PENDING_NOT_QUALIFIED' if execution['returncode']==0 and log.splitlines().count(MARK)==1 and not any(BAD.search(line) for line in log.splitlines()) else 'PROBE_FAILED_REVIEW_REQUIRED'),
   artifacts={p.name:ident(p) for p in D.iterdir() if p.is_file()})
  j['groups'].append(state);save(j)
 for path,expected in frozen.items():
  if ident(path)!=expected: raise ValueError('probe input mutated')
 m.verify_prepared(P,prepared)
 j.update(status='PROBES_EXECUTED_REVIEW_PENDING_NOT_QUALIFIED',original_prepared=ident(P/'prepared.json'),inventory=ident(I),netlist=prepared['netlist'],analysis_sdc=prepared['analysis_sdc'],frozen_inputs=frozen)
except Exception as error:
 j.update(status='FAIL',error=str(error));raise
finally:
 j['finished_epoch']=time.time();save(j)
print(j['status'])
