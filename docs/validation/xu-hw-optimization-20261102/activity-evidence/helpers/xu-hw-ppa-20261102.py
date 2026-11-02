#!/usr/bin/env python3
"""Independent exploratory SS wrapper PPA baseline; never modifies old sources/results."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

desktop = Path.home() / 'Desktop'
base = desktop / 'xu-hw-optimization-20261102/ppa'
source_repo = desktop / 'xu-fw-optimization-20261102/ChipContest'
old_libs = desktop / 'xu-work/xu-libs'
cell = old_libs / 'xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db'
ram = old_libs / 'xu-ramsp1024x16-ss-0p99v-125c.db'
ram_lib = Path('/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/lib/RAMSP1024X16_ss_0p99v_0p99v_125c.lib')
adapter = desktop / 'xu-work/ChipContest/third-party/e203_hbirdv2/vsim/run/xu-vcs-compile/xu-sram-adapter.sv'
rtl = base / 'frozen-fw-rtl'
out = base / 'baseline-ss-01'


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def save(name, data):
    (out / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def command(arguments, logfile, timeout):
    with (out / logfile).open('x') as stream:
        result = subprocess.run(arguments, cwd=str(out), stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    return result.returncode


def setup():
    if not all(path.is_file() for path in [cell, ram, ram_lib, adapter]):
        raise ValueError('required SS cell/SRAM library or existing adapter is unavailable')
    base.mkdir(parents=True, exist_ok=True)
    rtl.mkdir(exist_ok=False)
    out.mkdir(exist_ok=False)
    names = ['XRowBuffer.sv','WeightBankArray.sv','WeightBank.sv','Sram1024x16.sv',
             'LinearComputeCore.sv','DotProductEngine.sv','MacController.sv','MacPEArray.sv','MacPE.sv','accel_icb_slave.v']
    for name in names:
        shutil.copyfile(str(source_repo / 'third-party/e203_hbirdv2/rtl/e203/perips' / name), str(rtl / name))
    shutil.copyfile(str(adapter), str(rtl / 'xu-sram-adapter.sv'))
    manifest = dict(schema='xu-wrapper-ppa-baseline-v1', status='PREPARED',
        top='accel_icb_slave', scope='exploratory accelerator wrapper pre-layout only; excludes CPU/interconnect/shared RAM; no official signoff',
        provenance='existing SS standard-cell/SRAM DB and experimental macro adapter; EMA/EMAW PVT qualification not established',
        source_repository=str(source_repo),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(source_repo)).decode().strip(),
        source_sha256={p.name:sha(p) for p in sorted(rtl.iterdir())},
        libraries={str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in [cell,ram,ram_lib]},
        constraints=dict(clock_period_ns=6.666666667,clock_uncertainty_ns=0.1,clock_transition_ns=0.1,
                         input_delay_ns=0.5,input_transition_ns=0.1,output_delay_ns=0.5,output_load_pf=0.01,
                         reset='rst_n asynchronous; false path from reset input',
                         interconnect='pre-layout tool/library wire-load estimate; no SPEF or physical routing'),
        not_measured=['physical timing closure','full SoC area/power','activity-based task power'])
    save('manifest.json',manifest)
    (out/'constraints.sdc').write_text('''create_clock -name xu_clk -period 6.666666667 [get_ports clk]
set_clock_uncertainty 0.1 [get_clocks xu_clk]
set_clock_transition 0.1 [get_clocks xu_clk]
set xu_data_inputs [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay 0.5 -clock xu_clk $xu_data_inputs
set_input_transition 0.1 $xu_data_inputs
set_output_delay 0.5 -clock xu_clk [all_outputs]
set_load 0.01 [all_outputs]
set_false_path -from [get_ports rst_n]
''')
    analyze='\n'.join('if {![analyze -format sverilog {'+str(rtl/name)+'}]} {error {analysis failed: '+name+'}}'
                      for name in names+['xu-sram-adapter.sv'])
    (out/'synth.tcl').write_text('''set_host_options -max_cores 2
set_app_var target_library [list {%s}]
set_app_var link_library [list * {%s} {%s}]
set_app_var synthetic_library [list dw_foundation.sldb]
if {[catch {
%s
if {![elaborate accel_icb_slave]} {error {elaboration failed}}
current_design accel_icb_slave
if {![link]} {error {link failed}}
check_design > precheck.rpt
source constraints.sdc
report_units > units.rpt
compile
check_design > postcheck.rpt
check_timing > check-timing.rpt
report_area -hierarchy > area.rpt
report_reference -hierarchy > references.rpt
report_timing -delay_type max -max_paths 10 > setup.rpt
report_timing -delay_type min -max_paths 10 > hold.rpt
report_constraint -all_violators > violations.rpt
report_qor > qor.rpt
write -format verilog -hierarchy -output mapped.v
write -format ddc -hierarchy -output mapped.ddc
write_sdc mapped.sdc
puts "XU_DC_BASELINE_PASS"
} message]} {puts stderr "XU_DC_BASELINE_FAIL $message"; exit 1}
exit 0
''' % (cell,cell,ram,analyze))
    (out/'pt.tcl').write_text('''set_app_var link_path [list * {%s} {%s}]
if {[catch {set_app_var power_enable_analysis true} message]} {puts "XU_PT_POWER_ENABLE_FAIL $message"}
if {[catch {
read_verilog mapped.v
if {![link_design accel_icb_slave]} {error {link_design failed}}
read_sdc mapped.sdc
update_timing
check_timing -verbose > pt-check-timing.rpt
report_timing -delay_type max -max_paths 10 > pt-setup.rpt
report_timing -delay_type min -max_paths 10 > pt-hold.rpt
report_constraint -all_violators > pt-violations.rpt
report_units > pt-units.rpt
help read_vcd > pt-help-read-vcd.txt
help read_saif > pt-help-read-saif.txt
puts "XU_PT_STA_PASS"
} message]} {puts stderr "XU_PT_STA_FAIL $message"; exit 1}
if {[catch {
set_app_var power_analysis_mode averaged
update_power
report_power -hierarchy > pt-vectorless-power-capability.rpt
report_switching_activity > pt-switching-activity.rpt
puts "XU_PT_POWER_API_PASS_VECTORLESS_ONLY"
} message]} {puts "XU_PT_POWER_API_FAIL $message"}
exit 0
''' % (cell,ram))
    print('PREPARED '+str(out),flush=True)


def execute():
    manifest=json.loads((out/'manifest.json').read_text())
    for name,digest in manifest['source_sha256'].items():
        if sha(rtl/name)!=digest: raise ValueError('frozen source changed')
    for name,value in manifest['libraries'].items():
        if sha(Path(name))!=value['sha256']: raise ValueError('library changed')
    state=dict(status='RUNNING',started_epoch=time.time(),stage='dc')
    save('job-state.json',state)
    try:
        rc=command(['dc_shell','-64bit','-f','synth.tcl'],'dc.log',7200)
        state['dc_returncode']=rc
        if rc or 'XU_DC_BASELINE_PASS' not in (out/'dc.log').read_text(errors='replace'):
            raise RuntimeError('DC baseline failed; inspect dc.log')
        state['stage']='pt'
        save('job-state.json',state)
        rc=command(['pt_shell','-f','pt.tcl'],'pt.log',1800)
        state['pt_returncode']=rc
        log=(out/'pt.log').read_text(errors='replace')
        state['pt_sta_pass']='XU_PT_STA_PASS' in log and rc==0
        state['pt_power_api_pass']='XU_PT_POWER_API_PASS_VECTORLESS_ONLY' in log
        if not state['pt_sta_pass']: raise RuntimeError('PT STA failed; inspect pt.log')
        state.update(status='PASS',stage='complete')
    except Exception as error:
        state.update(status='FAIL',error=str(error))
    state['finished_epoch']=time.time()
    state['log_sha256']={p.name:sha(p) for p in sorted(out.glob('*.log'))}
    state['report_sha256']={p.name:sha(p) for p in sorted(out.glob('*.rpt'))}
    save('job-state.json',state)
    print(json.dumps(state,sort_keys=True),flush=True)


action=sys.argv[1]
if action=='setup': setup()
elif action=='start':
    if (out/'driver.log').exists() or (out/'job-state.json').exists(): raise ValueError('baseline already started')
    with (out/'driver.log').open('x') as stream:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'execute'],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    print('STARTED baseline pid='+str(process.pid),flush=True)
elif action=='execute': execute()
elif action=='status':
    if (out/'job-state.json').exists(): print((out/'job-state.json').read_text())
    for name in ['dc.log','pt.log']:
        if (out/name).exists(): print(name+' TAIL\n'+(out/name).read_text(errors='replace')[-2000:])
else: raise ValueError('unknown action')
