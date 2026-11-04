"""xu cleanup73: one independent pass over exact actual63's 53 unloaded pins.

No recursion, RTL edits, sequential removal, optimizer, or constraint changes.
Run on the original server: python ~/Desktop/launch_min_cell_cleanup73.py
"""
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
PARENT = B / 'full-soc-unloaded-cell-cleanup-20261104-63'
OUT = B / 'full-soc-unloaded-cell-cleanup-20261104-73'
R = B / 'ChipContest-clear-alias-20261103'
SDC = B / 'full-soc-pt-compatible-05/constraints.sdc'
SCOPE = Path.home() / 'Desktop/xu-ts16.tcl'
MAPPED_SHA = '58af01a6448a6dc79ff7afb488ffd9588114d32706d1b8fd3f10ff6ae09173f2'
STATE_SHA = 'b321edb63b16b5b9c1afd2d02b8633cf4f524b76f13bf2c67cd103ce9a62d323'
PINSET_SHA = '1af008c9ba3d8f0062beed6767092949bea353cff0d1900f587ff73b0482bad3'
PINREF_SHA = 'c38b41f4ac1adf22aea4f08ba0b52e59117b5954f91aab54e411bbdf93edbffa'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q(value):
    value = str(value)
    if any(c in value for c in '{}\t\r\n'):
        raise ValueError('unquotable Tcl value')
    return '{' + value + '}'


def rows(path):
    csv.field_size_limit(16 * 1024 * 1024)
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def actual_plan(parent):
    """Read only exact actual63 receipts; never discover another deletion wave."""
    if sha(parent / 'state.json') != STATE_SHA:
        raise ValueError('only exact actual63 terminal state is permitted')
    state = json.loads((parent / 'state.json').read_text())
    if state['status'] != 'EXECUTED_NOT_QUALIFIED' or state['mapped_netlist_sha256'] != MAPPED_SHA:
        raise ValueError('actual63 terminal mapped identity differs')
    if len(state['runs']) != 2:
        raise ValueError('actual63 DC/PT runs missing')
    for label, run in zip(('dc', 'pt'), state['runs']):
        if run['tool'] != label + '_shell' or run['returncode'] or run['errors'] or run['marker_count'] != 1:
            raise ValueError('actual63 execution incomplete')
        if sha(parent / (label + '.log')) != run['log_sha256']:
            raise ValueError('actual63 actual log differs')
        script = 'repair.tcl' if label == 'dc' else 'sta.tcl'
        if sha(parent / script) != run['script_sha256']:
            raise ValueError('actual63 executed Tcl differs')
    for name in ('constraints.rpt', 'analysis-coverage.rpt'):
        receipt = state['reports'][name]
        path = parent / name
        if path.stat().st_size != receipt['bytes'] or sha(path) != receipt['sha256']:
            raise ValueError('actual63 report differs: ' + name)
    for name in ('post-cleanup-upstream.tsv', 'removed-cells.tsv', 'removal-preflight.tsv'):
        receipt = state['audits'][name]
        path = parent / name
        if path.stat().st_size != receipt['bytes'] or sha(path) != receipt['sha256']:
            raise ValueError('actual63 audit differs: ' + name)
    upstream = rows(parent / 'post-cleanup-upstream.tsv')
    if len(upstream) != 329 or len({r['driver'] for r in upstream}) != 329:
        raise ValueError('exact actual63 upstream inventory differs')
    unloaded = sorted((r for r in upstream if r['source_only'] == '1'), key=lambda r: r['driver'])
    pins = [r['driver'] for r in unloaded]
    if len(pins) != 53 or any(r['net_count'] != '1' or r['leaf_connections'] != r['driver'] for r in unloaded):
        raise ValueError('exact53 actual63 source-only proof differs')
    if hashlib.sha256(('\n'.join(pins) + '\n').encode()).hexdigest() != PINSET_SHA:
        raise ValueError('exact53 pin set differs')
    pairs = [(r['driver'], r['owner_ref']) for r in unloaded]
    if hashlib.sha256(json.dumps(pairs, separators=(',', ':')).encode()).hexdigest() != PINREF_SHA:
        raise ValueError('exact53 pin/reference binding differs')
    cap_pins = []
    for block in (parent / 'constraints.rpt').read_text().split('    Pin: ')[1:]:
        if not re.search(r'^\s*-\s+min_capacitance\s+[\d.Ee+-]+', block, re.M) or re.search(r'^\s*max_capacitance\s', block, re.M):
            raise ValueError('actual63 capacitance kind differs')
        cap_pins.append(block.splitlines()[0])
    if len(cap_pins) != 53 or set(cap_pins) != set(pins):
        raise ValueError('actual63 min-cap pins must exactly equal the53 source-only drivers')
    removed = rows(parent / 'removed-cells.tsv')
    removed_names = {r['cell'] for r in removed}
    cells = [dict(cell=r['driver'].rsplit('/', 1)[0], ref=r['owner_ref'], outputs=[r['driver']]) for r in unloaded]
    if len(removed_names) != 187 or any(r['removed'] != '1' for r in removed) or len({r['cell'] for r in cells}) != 53 or removed_names & {r['cell'] for r in cells}:
        raise ValueError('candidate/previous-removal membership differs')
    return state, cells


def cleanup_tcl(candidates):
    s = r'''
set xu_before_cells [sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]
set xu_parent_counts [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr xu_parent_counts [get_attribute $h ref_name]}
set xu_remove {}
set xu_upstream [dict create]
set f [open removal-preflight.tsv w]
puts $f "cell\tref\tis_sequential\toutput\tleaf_connections\tparent_ref_instance_count"
'''
    for proposed in candidates:
        cell, ref = proposed['cell'], proposed['ref']
        owner = cell.rsplit('/', 1)[0]
        s += 'set c [get_cells -quiet ' + q(cell) + ']\n'
        s += 'if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne ' + q(ref) + ' || [get_attribute $c is_hierarchical]} {error {cleanup73 exact leaf/reference differs}}\n'
        s += r'''# No new sequential cell has a source-level unused-state proof.
# Missing native classification is a refusal, never an assumed false value.
set seq [get_attribute -quiet $c is_sequential]
if {![string is boolean -strict $seq]} {error {cleanup73 cannot prove combinational cell classification}}
if {$seq} {error {cleanup73 sequential removal has no RTL unused-state proof}}
'''
        s += 'set owner [get_cells -quiet ' + q(owner) + ']\n'
        s += r'''if {[sizeof_collection $owner]!=1} {error {cleanup73 owner missing}}
set parent_ref [get_attribute $owner ref_name]
if {![dict exists $xu_parent_counts $parent_ref] || [dict get $xu_parent_counts $parent_ref]!=1} {error {cleanup73 parent design is shared}}
set actual_outputs [get_pins -of_objects $c -filter {direction == out}]
if {[sizeof_collection [get_pins -of_objects $c -filter {direction == inout}]]!=0} {error {cleanup73 inout cannot be removed}}
'''
        s += 'set expected [list ' + ' '.join(q(p) for p in proposed['outputs']) + ']\n'
        s += r'''if {[lsort [get_object_name $actual_outputs]] ne [lsort $expected]} {error {cleanup73 whole-cell output set differs}}
foreach_in_collection p $actual_outputs {
 set n [get_nets -of_objects $p]
 if {[sizeof_collection $n]!=1} {error {cleanup73 output net count differs}}
 set con [all_connected -leaf $n]
 if {[sizeof_collection $con]!=1 || [get_object_name $con] ne [get_object_name $p] || [get_attribute $con object_class] ne "pin" || [get_attribute $con direction] ne "out"} {error {cleanup73 cross-hierarchy receiver appeared}}
 puts $f [join [list [get_object_name $c] [get_attribute $c ref_name] $seq [get_object_name $p] [get_object_name $con] [dict get $xu_parent_counts $parent_ref]] "\t"]
}
foreach_in_collection ip [get_pins -of_objects $c -filter {direction == in}] {
 foreach_in_collection n [get_nets -of_objects $ip] {
  foreach_in_collection driver [all_connected -leaf $n] {
   if {[get_attribute $driver object_class] eq "pin" && [get_attribute $driver direction] eq "out"} {dict set xu_upstream [get_object_name $driver] 1}
  }
 }
}
lappend xu_remove [get_object_name $c]
'''
    s += r'''
close $f
if {[llength $xu_remove]!=53 || [llength [lsort -unique $xu_remove]]!=53} {error {cleanup73 must remove exact53 cells}}
# All187 candidates have passed before the first deletion. No remove_port or
# hierarchy cleanup, and no recursive deletion of newly dangling upstream logic.
set f [open removed-cells.tsv w]
puts $f "cell\tremoved"
foreach name $xu_remove {
 set c [get_cells -quiet $name]
 if {[sizeof_collection $c]!=1} {error {cleanup73 preflight cell vanished}}
 remove_cell $c
 if {[sizeof_collection [get_cells -quiet $name]]!=0} {error {cleanup73 exact removal did not apply}}
 puts $f [join [list $name 1] "\t"]
}
close $f
if {[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]!=$xu_before_cells-53} {error {cleanup73 unexpected leaf-cell change}}
set f [open post-cleanup-upstream.tsv w]
puts $f "driver\towner_ref\tnet_count\tleaf_connections\tsource_only"
foreach name [lsort [dict keys $xu_upstream]] {
 set p [get_pins -quiet $name]
 if {[sizeof_collection $p]==0} {continue}
 if {[sizeof_collection $p]!=1} {error {cleanup73 upstream pin ambiguous}}
 set n [get_nets -of_objects $p]
 if {[sizeof_collection $n]>1} {error {cleanup73 upstream output net ambiguous}}
 set con {}
 if {[sizeof_collection $n]==1} {set con [all_connected -leaf $n]}
 set source_only [expr {[sizeof_collection $n]==0 || ([sizeof_collection $con]==1 && [get_object_name $con] eq [get_object_name $p])}]
 puts $f [join [list $name [get_attribute [get_cells -of_objects $p] ref_name] [sizeof_collection $n] [get_object_name $con] $source_only] "\t"]
}
close $f
'''
    return s


def main():
    worker = len(sys.argv) == 2 and sys.argv[1] == 'run'
    if not worker:
        if len(sys.argv) != 1:
            raise ValueError('no arguments, or internal worker run')
        OUT.mkdir(exist_ok=False)
        with (OUT / 'driver.log').open('x') as stream:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        print('XU_CLEANUP73_STARTED', proc.pid)
        return
    def save(state):
        (OUT / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    state = dict(status='RUNNING_NOT_QUALIFIED', started_epoch=time.time(), pid=os.getpid(), experiment='one exact53 actual63 combinational source-only cleanup pass; no recursion')
    save(state)
    try:
        parent, candidates = actual_plan(PARENT)
        net = PARENT / 'mapped.v'
        if sha(net) != MAPPED_SHA:
            raise ValueError('exact actual63 mapped bytes differ')
        if sha(SDC) != '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98' or sha(SCOPE) != '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e':
            raise ValueError('original constraints/scope differ')
        producer = R / 'tools/scripts/xu_soc_ppa.py'
        impl_path = B / 'clear-power-campaign-20261103-01/implementation/implementation.json'
        spec = importlib.util.spec_from_file_location('ppa', producer)
        ppa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ppa)
        impl = json.loads(impl_path.read_text())
        libs = [x['path'] for x in impl['libraries']]
        target = [x['path'] for x in impl['libraries'] if x['role'] == 'standard_cell']
        if len(libs) != 2 or len(target) != 1 or {sha(Path(x)) for x in libs} != {'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723', 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}:
            raise ValueError('exact original two SS libraries differ')
        manual = B / 'dc-electrical-docs-20261103-40/remove_cell.txt'
        if sha(manual) != '3ca9f9c21a64ecc388004669b6b52d45cb6115fd010e3356187d5e2ab0b0ab82':
            raise ValueError('actual installed remove_cell documentation differs')
        plan = dict(status='EXACT53_SOURCE_ONLY_CANDIDATES_NOT_EXECUTED_NOT_QUALIFIED', parent_mapped_sha256=MAPPED_SHA, pinset_sha256=PINSET_SHA, pin_reference_sha256=PINREF_SHA, candidates=candidates, sequential_policy='Reject every native is_sequential true or absent/non-boolean value; no new sequential unused-state proof supplied', qualification='Complete post-edit DC/PT/FM and all remaining electrical/reset/untested checks pending')
        (OUT / 'cleanup-plan.json').write_text(json.dumps(plan, sort_keys=True, indent=2) + '\n')
        inputs = [Path(__file__).resolve(), producer, impl_path, net, SDC, SCOPE, manual, OUT / 'cleanup-plan.json'] + [PARENT / n for n in ('state.json', 'repair.tcl', 'repair.svf', 'sta.tcl', 'dc.log', 'pt.log', 'constraints.rpt', 'analysis-coverage.rpt', 'post-cleanup-upstream.tsv', 'removed-cells.tsv', 'removal-preflight.tsv')] + [Path(x) for x in libs]
        state.update(input_sha256={str(p): sha(p) for p in inputs}, parent_mapped_sha256=MAPPED_SHA, candidate_count=53, pinset_sha256=PINSET_SHA, clock_scope='unchanged original70firstDcuts+6forwarded clocks, pre-CTS ideal; original0.1ns; no reset/gating/SRAM/UART waiver; no recursive cleanup')
        save(state)
        source = 'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + ppa.tcl(SDC) + '\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' + ppa.tcl(SCOPE) + '\n'
        dc = 'set_host_options -max_cores 2\nset_app_var target_library [list ' + ' '.join(ppa.tcl(x) for x in target) + ']\nset_app_var link_library [list * ' + ' '.join(ppa.tcl(x) for x in libs) + ']\nset_svf repair.svf\nread_verilog ' + ppa.tcl(net) + '\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n' + source
        dc += 'set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n' + cleanup_tcl(candidates) + ppa.memory_checks(impl)
        dc += 'report_constraint -all_violators -verbose > dc-all-constraints.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_timing -delay_type max -max_paths 50 > dc-setup.rpt\nreport_timing -delay_type min -max_paths 50 > dc-hold.rpt\nreport_constraint -all_violators > dc-violations.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'
        (OUT / 'repair.tcl').write_text(ppa.guarded_tcl(dc, 'XU_CLEANUP73_DC_DONE_NOT_QUALIFIED'))
        pt = 'set_app_var link_path [list * ' + ' '.join(ppa.tcl(x) for x in libs) + ']\nread_verilog mapped.v\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n' + source + ppa.memory_checks(impl)
        pt += 'redirect -file units.rpt {report_units}\nredirect -file check-timing.rpt {check_timing -verbose}\nredirect -file setup.rpt {report_timing -delay_type max -max_paths 50 -significant_digits 8}\nredirect -file hold.rpt {report_timing -delay_type min -max_paths 50 -significant_digits 8}\nredirect -file constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8}\nredirect -file exceptions.rpt {report_exceptions}\nredirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\nredirect -file clocks.rpt {report_clock -attributes}\n'
        pt += 'set f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -max_paths 1];if {[sizeof_collection $paths]!=1} {error {timing path missing}};puts $f [join [list $type [sizeof_collection $paths] [get_attribute $paths slack]] "\\t"]}\nclose $f\n'
        (OUT / 'sta.tcl').write_text(ppa.guarded_tcl(pt, 'XU_CLEANUP73_PT_DONE_NOT_QUALIFIED'))
        env = os.environ.copy()
        env['SYNOPSYS_LC_ROOT'] = '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'
        env['PATH'] = env['SYNOPSYS_LC_ROOT'] + '/bin:' + env.get('PATH', '')
        state['runs'] = []
        for label, tool, script, marker in [('dc', 'dc_shell', 'repair.tcl', 'XU_CLEANUP73_DC_DONE_NOT_QUALIFIED'), ('pt', 'pt_shell', 'sta.tcl', 'XU_CLEANUP73_PT_DONE_NOT_QUALIFIED')]:
            with (OUT / (label + '.log')).open('x') as stream:
                run = subprocess.run([tool, '-f', script], cwd=str(OUT), env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=21600)
            log = (OUT / (label + '.log')).read_text(errors='replace')
            errors = [line for line in log.splitlines() if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)', line)]
            state['runs'].append(dict(tool=tool, returncode=run.returncode, marker_count=log.splitlines().count(marker), errors=errors, log_sha256=sha(OUT / (label + '.log')), script_sha256=sha(OUT / script)))
            save(state)
            if run.returncode or errors or log.splitlines().count(marker) != 1:
                raise ValueError(label + ' failed')
        if any(sha(path) != state['input_sha256'][str(path)] for path in inputs):
            raise ValueError('frozen input changed')
        state.update(status='EXECUTED_NOT_QUALIFIED', mapped_netlist_sha256=sha(OUT / 'mapped.v'), reports={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in OUT.glob('*.rpt')}, audits={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in OUT.glob('*.tsv')}, timing=(OUT / 'timing-slack.tsv').read_text())
    except Exception as error:
        state.update(status='FAIL', error=str(error))
        raise
    finally:
        state['finished_epoch'] = time.time()
        save(state)
    print('XU_CLEANUP73_DONE', state['status'])


if __name__ == '__main__':
    main()
