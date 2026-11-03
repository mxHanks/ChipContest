from pathlib import Path
import subprocess,json,hashlib,sys,time,os,importlib.util,re
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';O=B/'full-soc-gating-margin-repair-20261103-09';R=B/'ChipContest-clear-alias-20261103';P=B/'full-soc-campaign-03-ppa/ppa-ss-01';S=B/'full-soc-pt-compatible-05/constraints.sdc';T=D/'xu-ts16.tcl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if len(sys.argv)==1:
 if O.exists():raise ValueError('output exists')
 O.mkdir()
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('FULL_SOC_HOLD_REPAIR_STARTED',p.pid);sys.exit(0)
j=dict(status='RUNNING_NOT_QUALIFIED',started_epoch=time.time(),pid=os.getpid());save(j)
try:
 spec=importlib.util.spec_from_file_location('ppa',R/'tools/scripts/xu_soc_ppa.py');ppa=importlib.util.module_from_spec(spec);spec.loader.exec_module(ppa)
 impl=json.loads((B/'clear-power-campaign-20261103-01/implementation/implementation.json').read_text());libs=[x['path']for x in impl['libraries']];target=[x['path']for x in impl['libraries']if x['role']=='standard_cell'];net=B/'full-soc-hold-repair-20261103-08/mapped.v'
 previous=json.loads((B/'full-soc-hold-repair-20261103-08/state.json').read_text())
 if previous['status']!='EXECUTED_NOT_QUALIFIED':raise ValueError('prior exact hold repair must be terminal')
 if sha(net)!=previous['mapped_netlist_sha256']or sha(S)!='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98':raise ValueError('original input identity')
 inputs=[net,S,T]+[Path(x)for x in libs];j['input_sha256']={str(p):sha(p)for p in inputs};j['clock_scope']='pre-CTS ideal clocks; exact70firstDcuts and6forwarded output clocks; no reset/gate/SRAM/UART waiver; DC gating hold target0.12ns conservative margin; final PT uses original0.1ns unchanged';save(j)
 src='set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource '+ppa.tcl(S)+'\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource '+ppa.tcl(T)+'\n'
 dc='set_host_options -max_cores 2\nset_app_var target_library [list '+' '.join(ppa.tcl(x)for x in target)+']\nset_app_var link_library [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nset_svf repair.svf\nread_verilog '+ppa.tcl(net)+'\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n'+src
 dc+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\nset_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false\nset_clock_gating_check -hold 0.12 [all_clocks]\nset_fix_hold [all_clocks]\ncompile -incremental_mapping -only_hold_time\n'+ppa.memory_checks(impl)
 dc+='report_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_timing -delay_type max -max_paths 50 > dc-setup.rpt\nreport_timing -delay_type min -max_paths 50 > dc-hold.rpt\nreport_constraint -all_violators > dc-violations.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'
 (O/'repair.tcl').write_text(ppa.guarded_tcl(dc,'XU_FULL_SOC_HOLD_REPAIR_DC_DONE_NOT_QUALIFIED'))
 pt='set_app_var link_path [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nread_verilog mapped.v\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n'+src+ppa.memory_checks(impl)
 pt+='redirect -file units.rpt {report_units}\nredirect -file check-timing.rpt {check_timing -verbose}\nredirect -file setup.rpt {report_timing -delay_type max -max_paths 50 -significant_digits 8}\nredirect -file hold.rpt {report_timing -delay_type min -max_paths 50 -significant_digits 8}\nredirect -file constraints.rpt {report_constraint -all_violators -verbose}\nredirect -file exceptions.rpt {report_exceptions}\nredirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\nredirect -file clocks.rpt {report_clock -attributes}\n'
 pt+='set f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -max_paths 1];if {[sizeof_collection $paths]!=1} {error {timing path missing}};puts $f "$type\\t[sizeof_collection $paths]\\t[get_attribute $paths slack]"}\nclose $f\n'
 (O/'sta.tcl').write_text(ppa.guarded_tcl(pt,'XU_FULL_SOC_HOLD_REPAIR_PT_DONE_NOT_QUALIFIED'))
 env=os.environ.copy();env['SYNOPSYS_LC_ROOT']='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env['PATH']=env['SYNOPSYS_LC_ROOT']+'/bin:'+env.get('PATH','');j['runs']=[]
 for label,tool,script,marker in [('dc','dc_shell','repair.tcl','XU_FULL_SOC_HOLD_REPAIR_DC_DONE_NOT_QUALIFIED'),('pt','pt_shell','sta.tcl','XU_FULL_SOC_HOLD_REPAIR_PT_DONE_NOT_QUALIFIED')]:
  with(O/(label+'.log')).open('x')as f:r=subprocess.run([tool,'-f',script],cwd=str(O),env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=21600)
  log=(O/(label+'.log')).read_text(errors='replace');errors=[l for l in log.splitlines()if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)',l)]
  j['runs'].append(dict(tool=tool,returncode=r.returncode,marker_count=log.splitlines().count(marker),errors=errors,log_sha256=sha(O/(label+'.log')),script_sha256=sha(O/script)));save(j)
  if r.returncode or errors or log.splitlines().count(marker)!=1:raise ValueError(label+' failed')
 if any(sha(p)!=j['input_sha256'][str(p)]for p in inputs):raise ValueError('original inputs changed')
 j.update(status='EXECUTED_NOT_QUALIFIED',mapped_netlist_sha256=sha(O/'mapped.v'),reports={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.rpt')},timing=(O/'timing-slack.tsv').read_text())
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
print('HOLD_REPAIR_DONE',j['status'])
