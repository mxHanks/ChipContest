from pathlib import Path
import subprocess,json,hashlib,sys,time,os,importlib.util,re
D=Path.home()/'Desktop';B=D/'xu-score-optimization-20261102';O=B/'full-soc-unloaded-cell-cleanup-20261103-50';R=B/'ChipContest-clear-alias-20261103';P=B/'full-soc-campaign-03-ppa/ppa-ss-01';S=B/'full-soc-pt-compatible-05/constraints.sdc';T=D/'xu-ts16.tcl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(j):(O/'state.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
if len(sys.argv)==1:
 if O.exists():raise ValueError('output exists')
 O.mkdir()
 with(O/'driver.log').open('x')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('FULL_SOC_UNLOADED_CELL_CLEANUP_STARTED',p.pid);sys.exit(0)
j=dict(experiment='only full-output-set proven unloaded cell cleanup, preserving RTL and all constraints',status='RUNNING_NOT_QUALIFIED',started_epoch=time.time(),pid=os.getpid());save(j)
try:
 spec=importlib.util.spec_from_file_location('ppa',R/'tools/scripts/xu_soc_ppa.py');ppa=importlib.util.module_from_spec(spec);spec.loader.exec_module(ppa)
 impl=json.loads((B/'clear-power-campaign-20261103-01/implementation/implementation.json').read_text());libs=[x['path']for x in impl['libraries']];target=[x['path']for x in impl['libraries']if x['role']=='standard_cell'];net=B/'full-soc-cap-size-repair-20261103-49/mapped.v'
 parent=B/'full-soc-cap-size-repair-20261103-49'
 previous=json.loads((parent/'state.json').read_text())
 if previous['status']!='EXECUTED_NOT_QUALIFIED':raise ValueError('actual49 same-family sizing must be terminal')
 if previous['mapped_netlist_sha256']!='5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c' or sha(net)!='5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c':raise ValueError('only exact actual49 mapped netlist is permitted')
 if sha(parent/'repair.tcl')!='9681a4ddbc6b3d327b95e06cd9b598c05592d86e15b09ef728712cfca86c136b' or sha(parent/'dc.log')!='7e73cd597f835fc947dff5198ff1b8b467904e989d4b221c0bb472f63aafae87':raise ValueError('actual49 execution evidence differs')
 if previous['input_sha256'].get(str(B/'full-soc-gating-margin-repair-20261103-09/mapped.v'))!='5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca'or sha(net)!=previous['mapped_netlist_sha256']or sha(S)!='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'or sha(T)!='45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e':raise ValueError('original input identity')
 manual=B/'dc-electrical-docs-20261103-40'
 manuals={'remove_cell.txt':'3ca9f9c21a64ecc388004669b6b52d45cb6115fd010e3356187d5e2ab0b0ab82'}
 if any(sha(manual/n)!=expected for n,expected in manuals.items()):raise ValueError('actual installed command documentation changed')
 if set(sha(Path(x))for x in libs)!={'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}:raise ValueError('actual two original SS libraries changed')
 palette=B/'full-soc-cap-cell-palette-20261103-41'
 analyzer=Path(__file__).with_name('analyze_cap_palette41_v2.py')
 with (O/'proposal.log').open('x') as f:
  proposal_run=subprocess.run([sys.executable,str(analyzer),'--precision',str(B/'full-soc-gating-drc-precision-20261103-14'),'--palette',str(palette),'--hier',str(B/'full-soc-cap-hier-topology-20261103-35'),'--out',str(O/'size-plan.json')],stdout=f,stderr=subprocess.STDOUT,timeout=120)
 if proposal_run.returncode:raise ValueError('actual library proposal generation failed')
 plan=json.loads((O/'size-plan.json').read_text())
 cleanup=plan['cross_hierarchy_min_cap']
 if len(cleanup['whole_cell_removal_candidates'])!=1404 or cleanup['whole_cell_removal_not_proven']:raise ValueError('full-output-set unloaded proof must cover exactly1404original cells')
 child=R/'third-party/e203_hbirdv2'
 fixed_rtl={child/'rtl/e203/perips/sirv_plic_man.v':'b7b8022f306eb7a93f20fda6d131feaa725aa04315bae87d3154572ab052c028',child/'rtl/e203/perips/sirv_plic_top.v':'b9770b38590371538154eacfe139660ab4b680fa2794d8d710256316c227c0bc',child/'rtl/e203/general/sirv_gnrl_dffs.v':'cd903d78882040cc17b6fb8bec3862f8d440726d7027ba9c61310d18801f8d83'}
 if any(sha(p)!=expected for p,expected in fixed_rtl.items()):raise ValueError('original PLIC/dff RTL identity differs')
 rtl=json.loads((O/'size-plan.json').read_text())
 # The source-only Q registers are specifically the three unused registered
 # priority bits. The live irq_id/irq_o and unregistered priority comparison
 # remain untouched; complete formal proof is still required.
 dff=[x for x in cleanup['whole_cell_removal_candidates']if x['libcell'].endswith('/DRNQV0_12TR40')]
 if len(dff)!=3 or any(not re.search(r'/flop_o_irq\.plic_irq_prio_dffr/qout_r_reg\[[012]\]$',x['cell'])for x in dff):raise ValueError('only exact3 PLIC unused priority flop removal is permitted')
 palette_state=json.loads((palette/'state.json').read_text())
 inputs=[Path(__file__).resolve(),net,S,T,analyzer,O/'size-plan.json',palette/'state.json',B/'full-soc-gating-drc-precision-20261103-14/constraints.rpt']+list(fixed_rtl)+[parent/'state.json',parent/'repair.tcl',parent/'repair.svf',parent/'dc.log',parent/'sized-cells.tsv']+[manual/n for n in manuals]+[B/'full-soc-cap-hier-topology-20261103-35'/n for n in ['state.json','query.tcl','topology.tsv','pt.log','pt_shell_command.log']]+[palette/n for n in palette_state['outputs']]+[Path(x)for x in libs];j['input_sha256']={str(p):sha(p)for p in inputs};j['clock_scope']='pre-CTS ideal clocks; exact70firstDcuts and6forwarded output clocks; no reset/gate/SRAM/UART waiver; remove only1404current fully unloaded cells after all outputs across hierarchy rechecked and unique owners; includes only3RTL-proven PLIC unused priority flops; no optimizer; finalPT original0.1ns unchanged; new upstream dangling pins/removal/untested/FM remain pending';save(j)
 src='set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource '+ppa.tcl(S)+'\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource '+ppa.tcl(T)+'\n'
 dc='set_host_options -max_cores 2\nset_app_var target_library [list '+' '.join(ppa.tcl(x)for x in target)+']\nset_app_var link_library [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nset_svf repair.svf\nread_verilog '+ppa.tcl(net)+'\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n'+src
 dc+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n'
 dc+=r'''
# Check all candidates before deleting any cell. No hierarchical port removal,
# no load fabrication, no changing library electrical limits.
set f [open removal-preflight.tsv w]
puts $f "cell\tref\toutput\tleaf_connections\tparent_ref_instance_count"
set xu_parent_counts [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {
 dict incr xu_parent_counts [get_attribute $h ref_name]
}
set xu_remove {}
set xu_upstream [dict create]
'''
 for proposed in cleanup['whole_cell_removal_candidates']:
  cell=proposed['cell'];libcell=proposed['libcell'];ref=libcell.rsplit('/',1)[1];outputs=proposed['outputs'];par=cell.rsplit('/',1)[0]
  for value in [cell,libcell,ref,par]+outputs:
   if any(c in value for c in '{}\t\r\n'):raise ValueError('unquotable cleanup proposal')
  dc+='set c [get_cells -quiet {'+cell+'}]\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne {'+ref+'} || [get_attribute $c is_hierarchical]} {error {cleanup source cell identity changed}}\n'
  dc+='set owner [get_cells -quiet {'+par+'}]\nif {[sizeof_collection $owner]!=1} {error {cleanup owner missing}}\nset parent_ref [get_attribute $owner ref_name]\nif {![dict exists $xu_parent_counts $parent_ref] || [dict get $xu_parent_counts $parent_ref]!=1} {error {cleanup parent design must be unique before removal}}\n'
  dc+='set actual_outputs [get_pins -of_objects $c -filter {direction == out}]\nset expected [list '+' '.join('{'+p+'}'for p in outputs)+']\nif {[lsort [get_object_name $actual_outputs]] ne [lsort $expected]} {error {whole-cell output set differs from actual35/41proof}}\n'
  dc+=r'''foreach_in_collection p $actual_outputs {
 set n [get_nets -of_objects $p]
 if {[sizeof_collection $n]!=1} {error {unloaded output net count differs}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=1 || [get_object_name $con] ne [get_object_name $p] || [get_attribute $con object_class] ne "pin" || [get_attribute $con direction] ne "out"} {error {full-output-set receiver appeared; refuse removal}}
 puts $f [join [list [get_object_name $c] [get_attribute $c ref_name] [get_object_name $p] [get_object_name $con] [dict get $xu_parent_counts $parent_ref]] "\t"]
}
'''
  dc+=r'''foreach_in_collection ip [get_pins -of_objects $c -filter {direction == in}] {
 foreach_in_collection innet [get_nets -of_objects $ip] {
  foreach_in_collection driver [all_connected -leaf $innet] {
   if {[get_attribute $driver object_class] eq "pin" && [get_attribute $driver direction] eq "out"} {
    dict set xu_upstream [get_object_name $driver] 1
   }
  }
 }
}
'''
  dc+='lappend xu_remove [get_object_name $c]\n'
 dc+='close $f\nif {[llength $xu_remove]!=1404 || [llength [lsort -unique $xu_remove]]!=1404} {error {cleanup cardinality must exactly1404}}\nset f [open removed-cells.tsv w]\nputs $f "cell\tremoved"\nforeach name $xu_remove {\nset c [get_cells -quiet $name]\nif {[sizeof_collection $c]!=1} {error {preflight cell vanished}}\nremove_cell $c\nif {[sizeof_collection [get_cells -quiet $name]]!=0} {error {remove_cell did not remove exact cell}}\nputs $f [join [list $name 1] "\\t"]\n}\nclose $f\n'
 dc+=r'''
# Audit every surviving leaf driver which fed an input of a removed cell.
# A newly unloaded driver is evidence for a future experiment, never a request
# to recurse into removal. This is real post-edit cross-hierarchy connectivity.
set f [open post-cleanup-upstream.tsv w]
puts $f "driver\towner_ref\tnet_count\tleaf_connections\tsource_only"
foreach name [lsort [dict keys $xu_upstream]] {
 set p [get_pins -quiet $name]
 if {[sizeof_collection $p]==0} {continue}
 if {[sizeof_collection $p]!=1} {error {upstream pin became ambiguous}}
 set n [get_nets -of_objects $p]
 if {[sizeof_collection $n]>1} {error {upstream output net became ambiguous}}
 set con {}
 if {[sizeof_collection $n]==1} {set con [all_connected -leaf $n]}
 set source_only [expr {[sizeof_collection $n]==0 || ([sizeof_collection $con]==1 && [get_object_name $con] eq [get_object_name $p])}]
 puts $f [join [list $name [get_attribute [get_cells -of_objects $p] ref_name] [sizeof_collection $n] [get_object_name $con] $source_only] "\t"]
}
close $f
'''+ppa.memory_checks(impl)
 dc+='report_constraint -all_violators -verbose > dc-all-constraints.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_timing -delay_type max -max_paths 50 > dc-setup.rpt\nreport_timing -delay_type min -max_paths 50 > dc-hold.rpt\nreport_constraint -all_violators > dc-violations.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'
 (O/'repair.tcl').write_text(ppa.guarded_tcl(dc,'XU_FULL_SOC_UNLOADED_CELL_CLEANUP_DC_DONE_NOT_QUALIFIED'))
 pt='set_app_var link_path [list * '+' '.join(ppa.tcl(x)for x in libs)+']\nread_verilog mapped.v\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n'+src+ppa.memory_checks(impl)
 pt+='redirect -file units.rpt {report_units}\nredirect -file check-timing.rpt {check_timing -verbose}\nredirect -file setup.rpt {report_timing -delay_type max -max_paths 50 -significant_digits 8}\nredirect -file hold.rpt {report_timing -delay_type min -max_paths 50 -significant_digits 8}\nredirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}\nredirect -file exceptions.rpt {report_exceptions}\nredirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\nredirect -file clocks.rpt {report_clock -attributes}\n'
 pt+='set f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -max_paths 1];if {[sizeof_collection $paths]!=1} {error {timing path missing}};puts $f "$type\\t[sizeof_collection $paths]\\t[get_attribute $paths slack]"}\nclose $f\n'
 (O/'sta.tcl').write_text(ppa.guarded_tcl(pt,'XU_FULL_SOC_UNLOADED_CELL_CLEANUP_PT_DONE_NOT_QUALIFIED'))
 env=os.environ.copy();env['SYNOPSYS_LC_ROOT']='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env['PATH']=env['SYNOPSYS_LC_ROOT']+'/bin:'+env.get('PATH','');j['runs']=[]
 for label,tool,script,marker in [('dc','dc_shell','repair.tcl','XU_FULL_SOC_UNLOADED_CELL_CLEANUP_DC_DONE_NOT_QUALIFIED'),('pt','pt_shell','sta.tcl','XU_FULL_SOC_UNLOADED_CELL_CLEANUP_PT_DONE_NOT_QUALIFIED')]:
  with(O/(label+'.log')).open('x')as f:r=subprocess.run([tool,'-f',script],cwd=str(O),env=env,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=21600)
  log=(O/(label+'.log')).read_text(errors='replace');errors=[l for l in log.splitlines()if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)',l)]
  j['runs'].append(dict(tool=tool,returncode=r.returncode,marker_count=log.splitlines().count(marker),errors=errors,log_sha256=sha(O/(label+'.log')),script_sha256=sha(O/script)));save(j)
  if r.returncode or errors or log.splitlines().count(marker)!=1:raise ValueError(label+' failed')
 if any(sha(p)!=j['input_sha256'][str(p)]for p in inputs):raise ValueError('original inputs changed')
 j.update(status='EXECUTED_NOT_QUALIFIED',mapped_netlist_sha256=sha(O/'mapped.v'),reports={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.rpt')},audits={p.name:dict(bytes=p.stat().st_size,sha256=sha(p))for p in O.glob('*.tsv')},timing=(O/'timing-slack.tsv').read_text())
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:j['finished_epoch']=time.time();save(j)
print('UNLOADED_CELL_CLEANUP_DONE',j['status'])
