"""xu reset61: fix actual55 empty DC dont_use without changing proof gates.
Independent mapped reset-delay experiment using actual-library inverter pairs.
Usage on server: python launch_reset_buffer61.py 49 4 (or 50 4).
No RTL, constraints, library edits, optimizer, or electrical load fabrication.
"""
from pathlib import Path
import subprocess,json,hashlib,sys,time,os,importlib.util,re,csv
B=Path.home()/'Desktop/xu-score-optimization-20261102';D=Path.home()/'Desktop'
P=B/'full-soc-campaign-03-ppa/ppa-ss-01';R=B/'ChipContest-clear-alias-20261103';S=B/'full-soc-pt-compatible-05/constraints.sdc';T=D/'xu-ts16.tcl'
ACTUAL49='5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c'
LIB='scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40'
BASE='u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
ENDPOINTS=[(BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg','SDN','DSNQV0_12TR40'),(BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg','SDN','DSNQNV0_12TR40')]+[(BASE+'aonrst_catch/reset_n_catch_reg/reg_'+str(i)+'/q_reg','RDN','DRNQV0_12TR40')for i in range(3)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def q(s):
 if any(c in str(s)for c in '{}\r\n\t'):raise ValueError('unquotable value')
 return '{'+str(s)+'}'
def insert_tcl(pairs):
 s=r'''
set xu_before_cells [sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]
set xu_parent_counts [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr xu_parent_counts [get_attribute $h ref_name]}
set xu_original_driver [dict create]
set f [open reset-preflight.tsv w]
puts $f "reset_pin\tref\tleaf_connections\tunique_owner_ref\toriginal_driver"
'''
 for cell,pin,ref in ENDPOINTS:
  name=cell+'/'+pin;owner=cell.rsplit('/',1)[0]
  s+='set c [get_cells -quiet '+q(cell)+']\nset p [get_pins -quiet '+q(name)+']\nset owner [get_cells -quiet '+q(owner)+']\n'
  s+='if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne '+q(ref)+' || [sizeof_collection $p]!=1 || [get_attribute $p direction] ne "in" || [sizeof_collection $owner]!=1} {error {exact reset endpoint identity changed}}\n'
  s+='set owner_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $owner_ref] || [dict get $xu_parent_counts $owner_ref]!=1} {error {reset owner design is shared}}\n'
  s+=r'''set n [get_nets -of_objects $p]
if {[sizeof_collection $n]!=1} {error {reset endpoint net missing or ambiguous}}
set con [all_connected -leaf $n]
set drivers {}
foreach_in_collection o $con {
 if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend drivers [get_object_name $o]}
}
if {[llength $drivers]!=1} {error {reset endpoint original driver ambiguous}}
dict set xu_original_driver [get_object_name $p] [lindex $drivers 0]
puts $f [join [list [get_object_name $p] [get_attribute $c ref_name] [get_object_name $con] $owner_ref [lindex $drivers 0]] "\t"]
'''
 s+='close $f\nset lc [get_lib_cells -quiet '+q(LIB)+']\nif {[sizeof_collection $lc]!=1} {error {actual library candidate missing}}\n'
 s+=r'''
# Actual55 stopped here: an unset DC dont_use attribute returns the empty
# string, which is not a Tcl boolean. Preserve the raw value; do not invent
# or set a library attribute. The exact same DB and actual41 false palette
# record are frozen by the Python preflight, and native insertion must accept.
set xu_dont_use [get_attribute -quiet $lc dont_use]
set xu_dont_use_basis dc_explicit_false
if {$xu_dont_use eq ""} {
 set xu_dont_use_basis dc_absent_with_frozen_PT_palette_false_native_validation_required
} elseif {![string is boolean -strict $xu_dont_use]} {
 error {DC dont_use attribute is not a valid boolean}
} elseif {$xu_dont_use} {
 error {actual library candidate prohibited in DC}
}
set f [open reset-library-preflight.tsv w]
puts $f "libcell\tdc_dont_use_raw\tacceptance_basis"
puts $f [join [list [get_object_name $lc] $xu_dont_use $xu_dont_use_basis] "\t"]
close $f
'''

 s+=r'''set li [get_lib_pins -of_objects $lc -filter {direction == in}]
set lo [get_lib_pins -of_objects $lc -filter {direction == out}]
if {[sizeof_collection $li]!=1 || [sizeof_collection $lo]!=1 || [get_object_name $li] ne "scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40/I" || [get_object_name $lo] ne "scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40/ZN"} {error {actual library topology changed}}
# insert_buffer -inverter_pair performs the native inverter-function check.
# A name or absent PT function attribute is never taken as a logic proof.
set f [open inserted-reset-cells.tsv w]
puts $f "endpoint\tcell\tref"
'''
 for i,(cell,pin,ref)in enumerate(ENDPOINTS):
  owner=cell.rsplit('/',1)[0];local=cell.rsplit('/',1)[1]+'/'+pin;name=cell+'/'+pin
  s+='current_instance '+q(owner)+'\nset p [get_pins -quiet '+q(local)+']\nif {[sizeof_collection $p]!=1} {error {scoped exact reset pin missing}}\n'
  s+='set added [insert_buffer -inverter_pair -no_of_cells '+str(pairs)+' -new_cell_names {xu_reset61_'+str(i)+'} -new_net_names {xu_reset61_net_'+str(i)+'} $p $lc]\n'
  s+='if {[sizeof_collection $added]!='+str(2*pairs)+'} {error {native inverter-pair insertion failed}}\ncurrent_instance\nset names [get_object_name $added]\n'
  s+='foreach_in_collection c $added {if {[get_attribute $c ref_name] ne {CLKINV0_12TR40}} {error {inserted cell identity differs}};puts $f [join [list '+q(name)+' [get_object_name $c] [get_attribute $c ref_name]] "\\t"]}\n'
  s+='set cursor [get_pins -quiet '+q(name)+']\nset seen {}\n'
  s+='for {set k 0} {$k<'+str(2*pairs)+'} {incr k} {\n'+r''' set n [get_nets -of_objects $cursor]
 if {[sizeof_collection $n]!=1} {error {new reset chain net missing}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=2} {error {new reset buffer branch gained another receiver}}
 set dp {}
 foreach_in_collection o $con {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
 if {[llength $dp]!=1} {error {new reset chain driver ambiguous}}
 set driver [get_pins -quiet [lindex $dp 0]]
 set c [get_cells -of_objects $driver]
 set cn [get_object_name $c]
 if {[lsearch -exact $names $cn]<0 || [lsearch -exact $seen $cn]>=0 || [get_attribute $c ref_name] ne "CLKINV0_12TR40"} {error {new reset chain topology differs}}
 lappend seen $cn
 set cursor [get_pins -of_objects $c -filter {direction == in}]
 if {[sizeof_collection $cursor]!=1} {error {new reset buffer input differs}}
}
if {[lsort $seen] ne [lsort $names]} {error {inserted reset chain has unvisited cells}}
set dp {}
foreach_in_collection o [all_connected -leaf [get_nets -of_objects $cursor]] {if {[get_attribute $o object_class] eq "pin" && [get_attribute $o direction] eq "out"} {lappend dp [get_object_name $o]}}
'''
  s+='if {$dp ne [list [dict get $xu_original_driver '+q(name)+']]} {error {reset chain did not retain original driver}}\n'
 s+='close $f\nif {[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]!=$xu_before_cells+'+str(10*pairs)+'} {error {unexpected reset insertion cell count}}\n'
 return s

def main():
 worker=len(sys.argv)==4 and sys.argv[1]=='run'
 parent_stage=sys.argv[2]if worker else (sys.argv[1]if len(sys.argv)>1 else '49')
 pairs=int(sys.argv[3]if worker else (sys.argv[2]if len(sys.argv)>2 else '4'))
 if parent_stage not in ('49','50')or not 1<=pairs<=32:raise ValueError('parent49/50;1<=pairs<=32')
 parent=B/('full-soc-cap-size-repair-20261103-49'if parent_stage=='49'else 'full-soc-unloaded-cell-cleanup-20261103-50')
 O=B/('full-soc-reset-buffer-20261104-61-from'+parent_stage+'-n'+str(pairs))
 def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
 if not worker:
  O.mkdir(exist_ok=False)
  with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run',parent_stage,str(pairs)],stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
  print('XU_RESET_BUFFER_EXPERIMENT_STARTED',parent_stage,pairs,p.pid);return
 j=dict(status='RUNNING_NOT_QUALIFIED',started_epoch=time.time(),pid=os.getpid(),parent_stage=parent_stage,pairs_per_sink=pairs,experiment='actual-library native-validated inverter pairs at exact5 reset sinks; no optimizer or constraint change');save(j)
 try:
  spec=importlib.util.spec_from_file_location('ppa',R/'tools/scripts/xu_soc_ppa.py');ppa=importlib.util.module_from_spec(spec);spec.loader.exec_module(ppa)
  impl=json.loads((B/'clear-power-campaign-20261103-01/implementation/implementation.json').read_text());libs=[x['path']for x in impl['libraries']];target=[x['path']for x in impl['libraries']if x['role']=='standard_cell']
  actual49=B/'full-soc-cap-size-repair-20261103-49'
  if sha(actual49/'mapped.v')!=ACTUAL49 or sha(actual49/'state.json')!='3d9f222369a19b48eeec69ab63405d6aea579aa3f99d2b7a16ef2458f8cbaf28':raise ValueError('original actual49 identity differs')
  previous=json.loads((parent/'state.json').read_text());net=parent/'mapped.v'
  if previous['status']!='EXECUTED_NOT_QUALIFIED'or sha(net)!=previous['mapped_netlist_sha256']or len(previous['runs'])!=2 or any(r['returncode']or r['errors']or r['marker_count']!=1 for r in previous['runs']):raise ValueError('parent mapped DC/PT execution incomplete')
  for label,run in zip(('dc','pt'),previous['runs']):
   if sha(parent/(label+'.log'))!=run['log_sha256']:raise ValueError('parent execution log differs')
  for name in ('hold.rpt','constraints.rpt'):
   if sha(parent/name)!=previous['reports'][name]['sha256']:raise ValueError('parent exact timing report identity differs')
  if parent_stage=='50'and previous['input_sha256'].get(str(actual49/'mapped.v'))!=ACTUAL49:raise ValueError('50 did not use actual49')
  if sha(S)!='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'or sha(T)!='45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e':raise ValueError('original constraints changed')
  if {sha(Path(p))for p in libs}!={'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}:raise ValueError('original SS libraries changed')
  manual=B/'dc-electrical-docs-20261103-40/insert_buffer.txt';palette=B/'full-soc-cap-cell-palette-20261103-41/library-palette.tsv'
  if sha(manual)!='777ce2124be6bdcfa10755b912218bb61564f4090d778aefb2725fa0279fc96c'or sha(palette)!='10eaa10e2485bba64be08d078907016eed2ff13f73799efeecfd5a4afc6e29d1':raise ValueError('actual installed native command docs/library palette changed')
  rs=[r for r in csv.DictReader(palette.open(),delimiter='\t')if r['libcell']==LIB]
  if len(rs)!=2 or {(r['libpin'].rsplit('/',1)[1],r['direction'])for r in rs}!={('I','in'),('ZN','out')}or any(r['dont_use']!='false'for r in rs):raise ValueError('actual palette candidate topology differs')
  report=(parent/'hold.rpt').read_text();blocks=report.split('  Startpoint: ')[1:]
  if len(blocks)!=5 or any('removal check against rising-edge clock xu_lfextclk'not in b or b.splitlines()[0].strip()!='io_pads_aon_erst_n_i_ival'for b in blocks):raise ValueError('parent exact5 reset removal failures changed; inspect new actual report first')
  found={}
  for b in blocks:
   ep=re.search(r'^  Endpoint: (\S+)',b,re.M);assert ep
   pins=re.findall(r'^  (\S+/(?:RDN|SDN)) \((\S+)\)',b,re.M);assert len(pins)==1
   found[ep[1]]=pins[0]
  if found!={c:(c+'/'+p,r)for c,p,r in ENDPOINTS}:raise ValueError('actual parent reset sinks differ')
  inputs=[Path(__file__).resolve(),net,parent/'state.json',parent/'repair.tcl',parent/'repair.svf',parent/'dc.log',parent/'pt.log',parent/'hold.rpt',parent/'constraints.rpt',actual49/'state.json',actual49/'mapped.v',S,T,manual,palette]+[Path(x)for x in libs]
  j.update(input_sha256={str(p):sha(p)for p in inputs},reset_sinks=[dict(cell=c,pin=p,ref=r)for c,p,r in ENDPOINTS],candidate=dict(libcell=LIB,selection='actual41 one-input/one-output non-prohibited topology; native DC insert_buffer -inverter_pair must validate inverter function; full FM pending'),clock_scope='original70firstDcuts+6forwarded clocks; no reset waiver; original0.1ns unchanged',scope_limit='Only the existing SDC scenario is checked: all5 start at raw asynchronous io_pads_aon_erst_n_i_ival, with existing0 input delay relative to HF and LF recovery/removal checks. Added mapped delay and full FM do not prove safe asynchronous release at every phase, reset protocol, or MTBF. Original PMU asynchronous-set2stage and AON3stage catch RTL remain unchanged.');save(j)
  src='set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource '+ppa.tcl(S)+'\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource '+ppa.tcl(T)+'\n'
  dc='set_host_options -max_cores 2\nset_app_var target_library [list '+' '.join(ppa.tcl(x)for x in target)+']\nset_app_var link_library [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nset_svf repair.svf\nread_verilog '+ppa.tcl(net)+'\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n'+src
  dc+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n'+insert_tcl(pairs)+ppa.memory_checks(impl)
  dc+='report_constraint -all_violators -verbose > dc-all-constraints.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_timing -delay_type max -max_paths 50 > dc-setup.rpt\nreport_timing -delay_type min -max_paths 50 > dc-hold.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'
  (O/'repair.tcl').write_text(ppa.guarded_tcl(dc,'XU_RESET_BUFFER61_DC_DONE_NOT_QUALIFIED'))
  pt='set_app_var link_path [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nread_verilog mapped.v\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n'+src+ppa.memory_checks(impl)
  pt+='redirect -file units.rpt {report_units}\nredirect -file check-timing.rpt {check_timing -verbose}\nredirect -file setup.rpt {report_timing -delay_type max -slack_lesser_than 1000000 -max_paths 50 -significant_digits 8}\nredirect -file hold.rpt {report_timing -delay_type min -slack_lesser_than 1000000 -max_paths 50 -significant_digits 8}\nredirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}\nredirect -file exceptions.rpt {report_exceptions}\nredirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\nredirect -file clocks.rpt {report_clock -attributes}\n'
  pt+='set f [open reset-slack.tsv w]\nputs $f "reset_pin\\tdelay_type\\tpath_count\\tworst_slack"\n'
  for i,(c,p,r)in enumerate(ENDPOINTS):
   pt+='set p [get_pins -quiet '+q(c+'/'+p)+']\nif {[sizeof_collection $p]!=1} {error {post-edit reset endpoint missing}}\n'
   for typ,label in [('max','recovery'),('min','removal')]:
    pt+='set paths [get_timing_paths -delay_type '+typ+' -to $p -slack_lesser_than 1000000 -max_paths 1]\nif {[sizeof_collection $paths]!=1} {error {reset '+label+' path missing; cannot claim analysis}}\nputs $f [join [list [get_object_name $p] '+typ+' [sizeof_collection $paths] [get_attribute $paths slack]] "\\t"]\n'
    pt+='redirect -file reset-'+str(i)+'-'+label+'.rpt {report_timing -delay_type '+typ+' -to $p -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8}\n'
  pt+='close $f\nset f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -slack_lesser_than 1000000 -max_paths 1];if {[sizeof_collection $paths]!=1} {error {timing path missing}};puts $f [join [list $type [sizeof_collection $paths] [get_attribute $paths slack]] "\\t"]}\nclose $f\n'
  (O/'sta.tcl').write_text(ppa.guarded_tcl(pt,'XU_RESET_BUFFER61_PT_DONE_NOT_QUALIFIED'))
  env=os.environ.copy();env['SYNOPSYS_LC_ROOT']='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env['PATH']=env['SYNOPSYS_LC_ROOT']+'/bin:'+env.get('PATH','');j['runs']=[]
  for label,tool,script,marker in [('dc','dc_shell','repair.tcl','XU_RESET_BUFFER61_DC_DONE_NOT_QUALIFIED'),('pt','pt_shell','sta.tcl','XU_RESET_BUFFER61_PT_DONE_NOT_QUALIFIED')]:
   with(O/(label+'.log')).open('x')as f:r=subprocess.run([tool,'-f',script],cwd=str(O),env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=21600)
   log=(O/(label+'.log')).read_text(errors='replace');errors=[l for l in log.splitlines()if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)',l)]
   j['runs'].append(dict(tool=tool,returncode=r.returncode,marker_count=log.splitlines().count(marker),errors=errors,log_sha256=sha(O/(label+'.log')),script_sha256=sha(O/script)));save(j)
   if r.returncode or errors or log.splitlines().count(marker)!=1:raise ValueError(label+' failed')
  if any(sha(p)!=j['input_sha256'][str(p)]for p in inputs):raise ValueError('frozen input changed')
  j.update(status='EXECUTED_NOT_QUALIFIED',mapped_netlist_sha256=sha(O/'mapped.v'),reports={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.rpt')},audits={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.tsv')},timing=(O/'timing-slack.tsv').read_text(),reset_timing=(O/'reset-slack.tsv').read_text())
 except Exception as e:j.update(status='FAIL',error=str(e));raise
 finally:j['finished_epoch']=time.time();save(j)
if __name__=='__main__':main()
