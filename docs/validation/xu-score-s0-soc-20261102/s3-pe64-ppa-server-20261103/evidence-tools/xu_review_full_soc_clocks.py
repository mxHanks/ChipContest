#!/usr/bin/env python3
"""xu source/SDC clock review and optional actual-RTL replay; never an STA pass.

Python 3.6+, Tcl 8.5+, and (for --run-rtl) Icarus Verilog are sufficient. The
Tcl mock checks SDC execution/branch logic only, not Synopsys timing semantics.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = ROOT
RTL = 'third-party/e203_hbirdv2/rtl/e203/'
SOURCES = [
    RTL+'soc/e203_soc_top.v', RTL+'subsys/e203_subsys_top.v',
    RTL+'subsys/e203_subsys_main.v', RTL+'subsys/e203_subsys_perips.v', RTL+'subsys/e203_subsys_hclkgen.v',
    RTL+'subsys/e203_subsys_pll.v', RTL+'subsys/e203_subsys_pllclkdiv.v',
    RTL+'subsys/e203_subsys_gfcm.v', RTL+'subsys/e203_subsys_hclkgen_rstsync.v',
    RTL+'core/e203_clkgate.v', RTL+'core/e203_clk_ctrl.v', RTL+'core/e203_cpu_top.v',
    RTL+'core/e203_reset_ctrl.v', RTL+'core/e203_defines.v', RTL+'core/config.v',
    RTL+'general/sirv_gnrl_dffs.v', RTL+'perips/sirv_hclkgen_regs.v',
    RTL+'perips/sirv_aon.v', RTL+'perips/sirv_aon_top.v',
    RTL+'perips/sirv_aon_wrapper.v', RTL+'perips/sirv_aon_porrst.v',
    RTL+'perips/sirv_ResetCatchAndSync.v', RTL+'perips/sirv_ResetCatchAndSync_2.v',
    RTL+'perips/sirv_DeglitchShiftRegister.v',
    RTL+'debug/sirv_jtag_dtm.v', RTL+'debug/sirv_debug_module.v',
    'tests/e203/tb_accel_soc.sv', 'tests/e203/firmware/start.S',
    'tests/e203/firmware/main.c', 'tests/e203/firmware/accel.c', 'tests/e203/firmware/accel.h',
    'tools/ppa/xu_soc_ppa_top.sv', 'tools/ppa/xu_shared_icb_sram.sv',
    'tools/ppa/xu_full_soc.sdc', 'tools/ppa/xu_full_soc_clock_review.tcl',
    'tools/ppa/tb_xu_full_soc_clocks.sv', 'tools/ppa/xu_review_full_soc_clocks.py',
]


def source_path(relative):
    return (TOOL_ROOT if relative.startswith('tools/') else ROOT)/relative


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, out, label):
    result = subprocess.run(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True,
                            timeout=60)
    log = out/(label+'.log')
    log.write_text(json.dumps(command)+'\n'+result.stdout)
    if result.returncode:
        raise RuntimeError('{} failed; see {}'.format(label, log))
    return dict(status='PASS', command=command, log=dict(path=str(log), sha256=sha(log)),
                returncode=result.returncode)


def tcl_mock(out):
    # Names are parsed from the actual PPA top. The mock deliberately does not
    # pretend that its list operations validate mapped Synopsys collections.
    top = re.sub(r'/\*.*?\*/|//[^\n]*', '', source_path('tools/ppa/xu_soc_ppa_top.sv').read_text(), flags=re.S)
    header = top.split(');', 1)[0]
    ports = re.findall(r'\b(input|output)\s*(?:\[[^\]]+\]\s*)?(\w+)', header)
    inputs = [name for direction, name in ports if direction == 'input']
    outputs = [name for direction, name in ports if direction == 'output']
    base = 'u_soc/u_e203_subsys_top/u_e203_subsys_main'
    h = base+'/u_e203_subsys_hclkgen/u_e203_subsys_pllclkdiv'
    g = base+'/u_e203_subsys_perips/u_sirv_hclkgen_regs'
    pins = [h+'/clk', h+'/clkout', g+'/pllbypass', g+'/plloutdivby1']
    pins += [g+'/plloutdiv[{}]'.format(i) for i in range(6)]
    script = '''
proc get_ports {args} {
  set result {}
  foreach q [lindex $args end] {
    if {[lsearch -exact $::ports $q] >= 0} { lappend result $q }
  }
  return $result
}
proc get_pins {args} {
  set q [lindex $args end]
  if {$q eq $::missing} { return {} }
  if {[lsearch -exact $::pins $q] >= 0} { return [list $q] }
  return {}
}
proc all_inputs {} { return $::inputs }
proc all_outputs {} { return $::outputs }
proc sizeof_collection {c} { return [llength $c] }
proc remove_from_collection {a b} {
  set result {}
  foreach q $a { if {[lsearch -exact $b $q] < 0} { lappend result $q } }
  return $result
}
proc create_clock {args} {
  set name [lindex $args [expr {[lsearch -exact $args -name]+1}]]
  dict set ::clocks $name $args
}
proc create_generated_clock {args} { set ::generated $args }
proc all_clocks {} { return [dict keys $::clocks] }
proc set_case_analysis {value pins} { foreach p $pins { dict set ::cases $p $value } }
foreach command {set_clock_uncertainty set_clock_transition set_clock_gating_check
                 set_input_delay set_output_delay set_input_transition set_load set_propagated_clock} {
  proc $command {args} {}
}
'''
    def literal(value):
        if any(c in value for c in '{}\n\r'):
            raise ValueError('unsupported Tcl literal')
        return '{'+value+'}'
    script += '\nset inputs [list '+ ' '.join(literal(x) for x in inputs)+']\n'
    script += 'set outputs [list '+ ' '.join(literal(x) for x in outputs)+']\n'
    script += 'set ports [concat $inputs $outputs]\n'
    script += 'set pins [list '+ ' '.join(literal(x) for x in pins)+']\n'
    script += 'set missing {}\n'
    script += 'set sdc '+literal(str(source_path('tools/ppa/xu_full_soc.sdc')))+'\n'
    script += '''
foreach mode {envelope reset_bypass divider} {
  for {set divisor 0} {$divisor < 64} {incr divisor} {
    set XU_CLOCK_MODE $mode
    set XU_PLL_DIV $divisor
    set clocks {}; set cases {}; set generated {}
    source $sdc
    if {[dict size $clocks] != 3} { error "primary clocks missing" }
    set expected [expr {$mode eq "envelope" ? 0 : 8}]
    if {[dict size $cases] != $expected} { error "unexpected case-analysis scope" }
    if {$mode eq "divider"} {
      set edges [lindex $generated [expr {[lsearch -exact $generated -edges]+1}]]
      if {$edges ne [list 1 2 [expr {4*($divisor+1)+1}]]} { error "wrong pulse edges" }
    }
  }
}
set XU_CLOCK_MODE envelope
set missing [lindex $pins 1]
if {![catch {source $sdc} message] || ![string match {*expected one pin*} $message]} {
  error "missing clock pin did not fail closed"
}
set f [open '''+literal(str(source_path('tools/ppa/xu_full_soc_clock_review.tcl')))+''']
set review [read $f]; close $f
if {![info complete $review]} { error "review Tcl is incomplete" }
puts "XU_SDC_MOCK_PASS 192_mode_divisor_combinations; missing_pin_rejected; review_Tcl_complete"
'''
    path = out/'sdc-mock.tcl'
    path.write_text(script)
    receipt = run(['tclsh', str(path)], out, 'sdc-mock')
    receipt['scope'] = 'Tcl syntax and control flow with mock collections; no DC/PT selector, timing, or library validation'
    return receipt


def rtl_test(out):
    sources = ['tools/ppa/tb_xu_full_soc_clocks.sv', RTL+'general/sirv_gnrl_dffs.v',
               RTL+'core/e203_clkgate.v', RTL+'subsys/e203_subsys_pll.v',
               RTL+'subsys/e203_subsys_pllclkdiv.v', RTL+'subsys/e203_subsys_gfcm.v',
               RTL+'subsys/e203_subsys_hclkgen_rstsync.v', RTL+'subsys/e203_subsys_hclkgen.v',
               RTL+'perips/sirv_hclkgen_regs.v']
    exe = out/'clock.vvp'
    compile_result = run(['iverilog', '-g2012', '-DDISABLE_SV_ASSERTION', '-I', str(ROOT/(RTL+'core')),
                          '-s', 'tb_xu_full_soc_clocks', '-o', str(exe)]+[str(source_path(name)) for name in sources],
                         out, 'rtl-compile')
    result = run(['vvp', str(exe)], out, 'rtl-clock')
    if 'XU_CLOCK_RTL_PASS' not in (out/'rtl-clock.log').read_text():
        raise RuntimeError('actual RTL completion marker missing')
    result['compile'] = compile_result
    result['scope'] = 'actual non-FPGA divider all64 settings, by1, reset-register defaults, and five PLL/GFCM steady modes; not CDC/metastability or mode-transition proof'
    return result


def main():
    global ROOT, TOOL_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT,help='platform/test source root')
    parser.add_argument('--tool-root',type=Path,default=TOOL_ROOT,help='PPA top/SDC/reviewer assets root')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run-rtl', action='store_true')
    args = parser.parse_args()
    ROOT=args.root.resolve();TOOL_ROOT=args.tool_root.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sdc = source_path('tools/ppa/xu_full_soc.sdc')
    body = '\n'.join(line for line in sdc.read_text().splitlines() if not line.lstrip().startswith('#'))
    for command in ['set_false_path', 'set_multicycle_path', 'set_clock_groups', 'set_ideal_network', 'set_disable_timing']:
        if re.search(r'\b'+command+r'\b', body):
            raise RuntimeError('review required: unexpected exception command '+command)
    tests = dict(sdc_mock=tcl_mock(out))
    tests['rtl_clock'] = rtl_test(out) if args.run_rtl else dict(status='NOT_RUN')
    review = dict(
        schema='xu-full-soc-clock-review-v1', status='REVIEWED',
        review_scope='source-derived digital constraints and local lightweight checks only',
        sta_status='NOT_RUN_NO_DC_PT_RESULT',
        created_utc=datetime.now(timezone.utc).isoformat(),
        constraints_sha256=sha(sdc),
        source_roots=dict(platform=str(ROOT),tools=str(TOOL_ROOT)),
        source_files={name:dict(path=str(source_path(name)), sha256=sha(source_path(name))) for name in SOURCES},
        primary_clocks=[dict(name='xu_hfextclk', period_ns=6.666666667, purpose='150MHz digital target'),
                        dict(name='xu_lfextclk', period_ns=30517.578125, purpose='32.768kHz platform LF reference'),
                        dict(name='xu_jtag_tck', period_ns=100, purpose='10MHz engineering assumption')],
        generated_clock_policy=dict(default='150MHz conservative pulse envelope; no register cases',
                                    modes=['envelope', 'reset_bypass', 'divider'],
                                    divider='by1 or period=2*(div+1)*Tsource, high=Tsource/2; edges=1,2,4*(div+1)+1',
                                    pll='actual RTL assign-through; no analog PLL claim',
                                    gates='latch+AND clock propagation and clock-gating checks remain enabled'),
        reset_exceptions=dict(false_paths=[], case_on_reset=[], recovery_removal='retained; async external release/CDC must be reviewed; no blanket waiver'),
        clock_domain_crossings=dict(clock_groups=[], false_paths=[], policy='report all HF/LF/JTAG crossings and review synchronizer inputs, handshakes and resets individually'),
        untested_check_policy='retain check_timing + PT analysis coverage, endpoint clocks, SRAM CLK clocks, recovery/removal/gating/pulse-width and all command failures; every untested check requires explicit classification',
        io_contract=dict(status='PROVISIONAL_ENGINEERING_ASSUMPTION', max_delay_ns=.5,
                         min_delay_ns=0, jtag_max_delay_ns=5, transition_ns=.1,
                         output_load_in_library_units=.01, clock_uncertainty_ns=.1,
                         note='Not official board/pad/SRAM timing qualification; no async reset-release guarantee'),
        lf_clock_scope=dict(development_tb_period_ns=66, target_period_ns=30517.578125,
                            ratio=30517.578125/66,
                            note='AON boot/deglitch/reset delay changes; actual twelve-task window comparison is required, not inferred from this unit test'),
        tests=tests, tools={tool:shutil.which(tool) for tool in ['dc_shell','pt_shell','tclsh','iverilog','vvp']},
        pending=['real DC/PT execution and mapped selector/clock coverage audit',
                 'setup, hold, recovery, removal, gating and minimum pulse-width closure',
                 'all untested paths and HF/LF/JTAG CDC/reset review',
                 '32.768kHz actual full-SoC startup and measured task-window replay',
                 'official external I/O timing and same-corner SRAM PVT/EMA timing eligibility'])
    target = out/'clock-review.json'
    target.write_text(json.dumps(review, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(path=str(target), status=review['status'], sta_status=review['sta_status'],
                          tests={name:value['status'] for name,value in tests.items()}), sort_keys=True))


if __name__ == '__main__':
    main()
