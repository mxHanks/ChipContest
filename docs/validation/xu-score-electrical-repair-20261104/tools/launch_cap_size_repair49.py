from pathlib import Path
import subprocess,json,hashlib,sys,time,os,importlib.util,re
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';O=B/'full-soc-cap-size-repair-20261103-49';R=B/'ChipContest-clear-alias-20261103';P=B/'full-soc-campaign-03-ppa/ppa-ss-01';S=B/'full-soc-pt-compatible-05/constraints.sdc';T=D/'xu-ts16.tcl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if len(sys.argv)==1:
 if O.exists():raise ValueError('output exists')
 O.mkdir()
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('FULL_SOC_CAP_SIZE_REPAIR_STARTED',p.pid);sys.exit(0)
j=dict(experiment='max-capacitance same-family/pin drive sizing with actual DC native equivalence gating',status='RUNNING_NOT_QUALIFIED',started_epoch=time.time(),pid=os.getpid());save(j)
try:
 spec=importlib.util.spec_from_file_location('ppa',R/'tools/scripts/xu_soc_ppa.py');ppa=importlib.util.module_from_spec(spec);spec.loader.exec_module(ppa)
 impl=json.loads((B/'clear-power-campaign-20261103-01/implementation/implementation.json').read_text());libs=[x['path']for x in impl['libraries']];target=[x['path']for x in impl['libraries']if x['role']=='standard_cell'];net=B/'full-soc-gating-margin-repair-20261103-09/mapped.v'
 previous=json.loads((B/'full-soc-gating-margin-repair-20261103-09/state.json').read_text())
 if previous['status']!='EXECUTED_NOT_QUALIFIED':raise ValueError('prior exact hold repair must be terminal')
 if sha(net)!='5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca'or sha(net)!=previous['mapped_netlist_sha256']or sha(S)!='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'or sha(T)!='45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e':raise ValueError('original input identity')
 manual=B/'dc-electrical-docs-20261103-40'
 manuals={'size_cell.txt':'328fc134158b991dbc5ccb91eec7b3b8d925ff7e8b5abbfd3d4651581592be52','get_alternative_lib_cells.txt':'656dd83a5bdb2e81c17f1f2095c1804d69dd12f122c272f775a73de5408a401e'}
 if any(sha(manual/n)!=expected for n,expected in manuals.items()):raise ValueError('actual installed command documentation changed')
 if set(sha(Path(x))for x in libs)!={'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}:raise ValueError('actual two original SS libraries changed')
 palette=B/'full-soc-cap-cell-palette-20261103-41'
 analyzer=Path(__file__).with_name('analyze_cap_palette41_v2.py')
 with (O/'proposal.log').open('x') as f:
  proposal_run=subprocess.run([sys.executable,str(analyzer),'--precision',str(B/'full-soc-gating-drc-precision-20261103-14'),'--palette',str(palette),'--out',str(O/'size-plan.json')],stdout=f,stderr=subprocess.STDOUT,timeout=120)
 if proposal_run.returncode:raise ValueError('actual library proposal generation failed')
 plan=json.loads((O/'size-plan.json').read_text())
 if len(plan['max_cap_size_proposals'])!=56 or plan['max_cap_no_legal_candidate']:raise ValueError('all56max pins require same-family/pin sized candidates, with native DC equivalence still mandatory; inspect partial proposal')
 palette_state=json.loads((palette/'state.json').read_text())
 inputs=[net,S,T,analyzer,O/'size-plan.json',palette/'state.json',B/'full-soc-gating-drc-precision-20261103-14/constraints.rpt']+[manual/n for n in manuals]+[palette/n for n in palette_state['outputs']]+[Path(x)for x in libs];j['input_sha256']={str(p):sha(p)for p in inputs};j['clock_scope']='pre-CTS ideal clocks; exact70firstDcuts and6forwarded output clocks; no reset/gate/SRAM/UART waiver; size only56actual maxcap drivers to actual same-family/pin candidates only after DC native logical/pin-number equivalence approval; no optimizer; finalPT original0.1ns unchanged; mincap/removal/untested are still pending';save(j)
 src='set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource '+ppa.tcl(S)+'\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource '+ppa.tcl(T)+'\n'
 dc='set_host_options -max_cores 2\nset_app_var target_library [list '+' '.join(ppa.tcl(x)for x in target)+']\nset_app_var link_library [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nset_svf repair.svf\nread_verilog '+ppa.tcl(net)+'\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n'+src
 dc+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n'
 dc+=r'''
proc xu_lib_logic_signature {c} {
 set signature {}
 foreach_in_collection p [get_lib_pins -of_objects $c] {
  set function [get_attribute -quiet $p function]
  lappend signature [list [lindex [split [get_object_name $p] /] end] [get_attribute $p direction] $function]
 }
 return [lsort $signature]
}
set f [open sized-cells.tsv w]
puts $f "cell\tbefore_ref\tafter_ref\tnew_max_capacitance"
'''
 seen=set()
 for proposed in plan['max_cap_size_proposals']:
  cell=proposed['cell'];oldref=proposed['ref'];newlib=proposed['selected']['libcell'];pin=proposed['pin'].rsplit('/',1)[1]
  if cell in seen:raise ValueError('one resize per exact cell required')
  seen.add(cell)
  for value in [cell,oldref,newlib,pin]:
   if any(c in value for c in '{}\t\r\n'):raise ValueError('unquotable proposal')
  dc+='set c [get_cells -quiet {'+cell+'}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {'+oldref+'}} {error {source driver identity changed}}\n'
  dc+='set old [get_lib_cells -quiet {'+proposed['current_libcell']+'}]\nset new [get_lib_cells -quiet {'+newlib+'}]\nif {[sizeof_collection $old]!=1 || [sizeof_collection $new]!=1 || [xu_lib_logic_signature $old] ne [xu_lib_logic_signature $new]} {error {runtime library pin/function mismatch}}\nset allowed [get_alternative_lib_cells -quiet $c]\nif {[lsearch -exact [get_object_name $allowed] {'+newlib+'}]<0} {error {DC native logical/pin-number compatibility rejected candidate}}\n'
  dc+='set lp [get_lib_pins -quiet {'+newlib+'/'+pin+'}]\nif {[sizeof_collection $lp]!=1 || [get_attribute $lp max_capacitance]<'+repr(proposed['measured_load']*1.05)+'} {error {runtime library maxcap insufficient}}\n'
  dc+='set sized [size_cell $c {'+newlib+'}]\nif {[sizeof_collection $sized]!=1 || [get_object_name $sized] ne [get_object_name $c] || [get_attribute $c ref_name] ne {'+newlib.rsplit('/',1)[1]+'}} {error {size_cell did not apply exact candidate}}\n'
  dc+='puts $f [join [list [get_object_name $c] {'+oldref+'} [get_attribute $c ref_name] [get_attribute $lp max_capacitance]] "\\t"]\n'
 dc+='close $f\n'+ppa.memory_checks(impl)
 dc+='report_constraint -all_violators -verbose > dc-all-constraints.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_timing -delay_type max -max_paths 50 > dc-setup.rpt\nreport_timing -delay_type min -max_paths 50 > dc-hold.rpt\nreport_constraint -all_violators > dc-violations.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'
 (O/'repair.tcl').write_text(ppa.guarded_tcl(dc,'XU_FULL_SOC_CAP_SIZE_REPAIR_DC_DONE_NOT_QUALIFIED'))
 pt='set_app_var link_path [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nread_verilog mapped.v\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n'+src+ppa.memory_checks(impl)
 pt+='redirect -file units.rpt {report_units}\nredirect -file check-timing.rpt {check_timing -verbose}\nredirect -file setup.rpt {report_timing -delay_type max -max_paths 50 -significant_digits 8}\nredirect -file hold.rpt {report_timing -delay_type min -max_paths 50 -significant_digits 8}\nredirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}\nredirect -file exceptions.rpt {report_exceptions}\nredirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\nredirect -file clocks.rpt {report_clock -attributes}\n'
 pt+='set f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -max_paths 1];if {[sizeof_collection $paths]!=1} {error {timing path missing}};puts $f "$type\\t[sizeof_collection $paths]\\t[get_attribute $paths slack]"}\nclose $f\n'
 (O/'sta.tcl').write_text(ppa.guarded_tcl(pt,'XU_FULL_SOC_CAP_SIZE_REPAIR_PT_DONE_NOT_QUALIFIED'))
 env=os.environ.copy();env['SYNOPSYS_LC_ROOT']='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env['PATH']=env['SYNOPSYS_LC_ROOT']+'/bin:'+env.get('PATH','');j['runs']=[]
 for label,tool,script,marker in [('dc','dc_shell','repair.tcl','XU_FULL_SOC_CAP_SIZE_REPAIR_DC_DONE_NOT_QUALIFIED'),('pt','pt_shell','sta.tcl','XU_FULL_SOC_CAP_SIZE_REPAIR_PT_DONE_NOT_QUALIFIED')]:
  with(O/(label+'.log')).open('x')as f:r=subprocess.run([tool,'-f',script],cwd=str(O),env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=21600)
  log=(O/(label+'.log')).read_text(errors='replace');errors=[l for l in log.splitlines()if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)',l)]
  j['runs'].append(dict(tool=tool,returncode=r.returncode,marker_count=log.splitlines().count(marker),errors=errors,log_sha256=sha(O/(label+'.log')),script_sha256=sha(O/script)));save(j)
  if r.returncode or errors or log.splitlines().count(marker)!=1:raise ValueError(label+' failed')
 if any(sha(p)!=j['input_sha256'][str(p)]for p in inputs):raise ValueError('original inputs changed')
 j.update(status='EXECUTED_NOT_QUALIFIED',mapped_netlist_sha256=sha(O/'mapped.v'),reports={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.rpt')},timing=(O/'timing-slack.tsv').read_text())
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
print('CAP_SIZE_REPAIR_DONE',j['status'])
