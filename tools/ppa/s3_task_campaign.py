#!/usr/bin/env python3
"""Fresh-reset S3 CPU/RTL tasks with physical preclear and request timing.

This is development evidence, not mapped/PPA or official policy acceptance.
Each native process executes one original layer, remapped to TB layer_00.
All original payload, NICE, FIFO and final-response assertions remain enabled.
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clock_configuration(profile):
    if profile not in ['development', '150mhz']:
        raise ValueError('unknown platform clock profile')
    requested = {'hf':'3.333333333', 'lf':'15258.7890625'} if profile=='150mhz' else {'hf':'2','lf':'33'}
    result = dict(profile=profile, requested_half_period_ns=requested,
                  scope='testbench clock stimulus, not STA or mapped-clock qualification')
    if profile=='150mhz':
        result['timescale'] = '1ns/1fs'
        result['quantized_expected'] = {}
        for name,value in requested.items():
            half_fs = int((Decimal(value)*1000000).to_integral_value(rounding=ROUND_HALF_UP))
            result['quantized_expected'][name] = dict(half_period_fs=half_fs,
                period_fs=2*half_fs, frequency_hz=str(Decimal(10)**15/(2*half_fs)))
    else:
        result['timescale'] = 'historical tool/source inheritance; unchanged'
    return result


def apply_platform_clocks(tb, profile):
    """One explicit clock/precision seam; development is byte-for-byte unchanged."""
    configuration = clock_configuration(profile)
    if profile=='development':
        return tb
    for old in ['  always #2 clk = ~clk;', '  always #33 lfclk = ~lfclk;']:
        assert tb.count(old)==1, 'unexpected frozen TB clock declaration'
    assert not re.search(r'^\s*`timescale\b',tb,re.M), 'unexpected existing TB timescale'
    tb = '`timescale 1ns/1fs\n'+tb.replace('  always #2 clk = ~clk;',
        '  always #3.333333333 clk = ~clk;',1).replace('  always #33 lfclk = ~lfclk;',
        '  always #15258.7890625 lfclk = ~lfclk;',1)
    # Measure actual simulation rounding, rather than presenting real literals
    # or the desired nominal frequency as an observed clock.
    declarations = []
    for name, signal in [('hf','clk'), ('lf','lfclk')]:
        declarations.append('''  initial begin : s3_measure_%s_clock
    realtime first_edge, period_ns;
    @(posedge %s); first_edge=$realtime;
    @(posedge %s); period_ns=$realtime-first_edge;
    if (period_ns<=0) $fatal(1,"S3 clock profile has a nonpositive period");
    $display("S3_CLOCK_PROFILE domain=%s requested_half_ns=%s measured_half_ns=%%.9f period_ns=%%.9f frequency_hz=%%.9f precision_fs=1",
      period_ns/2.0,period_ns,1.0e9/period_ns);
  end
''' % (name,signal,signal,name,configuration['requested_half_period_ns'][name]))
    anchor = '  reg clk = 0, lfclk = 0, rst_n = 0;'
    assert tb.count(anchor)==1, 'unexpected frozen TB clock state'
    return tb.replace(anchor,anchor+'\n'+''.join(declarations),1)


def check_clock_observations(log, profile):
    configuration = clock_configuration(profile)
    matches = re.findall(r'^S3_CLOCK_PROFILE domain=(hf|lf) requested_half_ns=([0-9.]+) '
        r'measured_half_ns=([0-9.]+) period_ns=([0-9.]+) frequency_hz=([0-9.]+) precision_fs=1$',log,re.M)
    markers = len(re.findall(r'^S3_CLOCK_PROFILE\b',log,re.M))
    if profile=='development':
        if markers:
            raise ValueError('unexpected clock profile records in historical development mode')
        return []
    if len(matches)!=2 or markers!=2 or {row[0] for row in matches}!={'hf','lf'}:
        raise ValueError('missing, duplicate or malformed measured platform clocks')
    records = []
    for name,requested,half,period,frequency in matches:
        expected = configuration['quantized_expected'][name]
        if (requested!=configuration['requested_half_period_ns'][name] or
                Decimal(half)*1000000!=expected['half_period_fs'] or
                Decimal(period)*1000000!=expected['period_fs'] or
                abs(Decimal(frequency)-Decimal(expected['frequency_hz']))>Decimal('0.00001')):
            raise ValueError('actual platform clock rounding/frequency differs')
        records.append(dict(domain=name,requested_half_period_ns=requested,
                            measured_half_period_ns=half,measured_period_ns=period,
                            measured_frequency_hz=frequency,precision_fs=1))
    return records


def vcs_assertion_command(command, enabled):
    """Keep historical defaults explicit; enabled VCS never defines the waiver."""
    command = list(command)
    macro = '+define+DISABLE_SV_ASSERTION=1'
    if enabled:
        if command.count(macro)!=1:
            raise ValueError('unexpected VCS platform-assertion macro configuration')
        command.remove(macro)
    return command


def instrument_tb(original, observer, platform_clocks='development'):
    """Add passive clear checks without replacing any payload assertion."""
    anchor = '  integer nice_requests=0, nice_responses=0, nice_retired=0;'
    assert original.count(anchor) == 1, 'unexpected frozen TB declarations'
    result = original.replace(anchor, observer+'\n  reg s3_payload_phase=0, s3_clear_armed=0;\n'+anchor, 1)
    anchor = '      if (nice_drain8) observe_nice();\n      observe_performance();'
    assert result.count(anchor) == 1, 'unexpected frozen payload observer invocation'
    replacement = '''      // The chip-level reset releases before the peripheral clock/reset.
      // Arm on a real request, never on an idle/busy value becoming favorable.
      // A source request arriving first still arms and fails incomplete clear.
      if (!s3_clear_armed && ((`ACCEL.cmd_valid===1'b1) || source_request)) begin
        s3_clear_armed=1;
        if (`ACCEL.rst_n!==1'b1)
          $fatal(1,"S3 clear request before actual accelerator reset release");
        $display("S3_CLEAR_OBSERVER_ARM cycle=%0d actual_accel_reset_n=%b",cycles,`ACCEL.rst_n);
      end
      if (s3_clear_armed) s3_observe_task_clear(source_request,
        !`NICE.nice_active && !`NICE.nice_req_valid &&
        !`NICE.nice_icb_cmd_valid && !`NICE.nice_icb_rsp_valid &&
        !`NICE.nice_rsp_valid && !`NICE.nice_mem_holdup,
        s3_payload_phase);
      if (s3_payload_phase) begin
        if (nice_drain8) observe_nice();
        observe_performance();
      end'''
    result = result.replace(anchor, replacement, 1)
    anchor = '    if (tasks < 1 || tasks > 12) $fatal(1,"invalid task count");'
    assert result.count(anchor) == 1
    result = result.replace(anchor, anchor+'\n    if (tasks!=1) $fatal(1,"S3 clear campaign requires fresh-reset TASKS=1");', 1)
    # Every preexisting fatal is retained, and all original TB text outside the
    # three declared insertion seams is byte-identical by construction.
    assert result.count('$fatal(') >= original.count('$fatal(')
    return apply_platform_clocks(result,platform_clocks)


def snapshot_inputs(repo, source):
    """One frozen firmware/observer/RTL seam shared by optional activity adapters."""
    selected = ['model/__init__.py','model/fixed16_acc48.py','model/s3_y32.py',
                'tools/model/export_s3_vectors.py','tools/scripts/e203_soc.py',
                'tools/scripts/xu_firmware_contract.py','tools/ppa/s3_task_clear_protocol.py',
                'tools/ppa/xu_task_clear_protocol.py','tests/e203/tb_accel_soc.sv',
                'tests/e203/vectors/kwt-silence-v1.json','tests/e203/vectors/kwt-silence-v1.tar.gz']
    selected += [str(p.relative_to(repo)) for p in (repo/'tests/e203/firmware').iterdir() if p.is_file()]
    for rel in selected:
        target = source/rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo/rel, target)
    shutil.copytree(repo/'third-party/e203_hbirdv2/rtl/e203', source/'rtl')
    shutil.copy2(__file__, source/'campaign.py')


def main(argv=None, extension=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--schedule', default='bias-hw-autogroup-y32-packed16-nice-window')
    parser.add_argument('--layers', default=','.join(map(str, range(12))))
    parser.add_argument('--simulator', choices=['vcs','iverilog'], default='vcs')
    parser.add_argument('--bias-kind', choices=['sram','registers'], required=True)
    parser.add_argument('--cross-prefix', default='/opt/eda/xilinx/2025.2/Vitis/gnu/riscv/lin/bin/riscv64-unknown-elf-')
    parser.add_argument('--first-source-stall', type=int, default=0)
    parser.add_argument('--max-cycles', type=int, default=3000000)
    parser.add_argument('--waves', action='store_true', help='full TB, including separate preclear; not macro power qualification')
    parser.add_argument('--platform-clocks', choices=['development','150mhz'], default='development',
                        help='explicit 150MHz/32.768kHz stimulus, or unchanged historical development clocks')
    parser.add_argument('--platform-assertions', action='store_true',
                        help='enable original vendor SVA in VCS; preserve Chisel/procedural assertions in both modes')
    args = parser.parse_args(argv)
    if args.platform_assertions and args.simulator!='vcs':
        parser.error('--platform-assertions requires VCS')
    layers = [int(x) for x in args.layers.split(',')]
    if not layers or len(set(layers)) != len(layers) or any(x not in range(12) for x in layers):
        parser.error('--layers must contain distinct indices from 0..11')
    if not 0 <= args.first_source_stall <= 1000 or args.max_cycles < 1:
        parser.error('invalid wait or cycle limit')
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out/'source'
    source.mkdir()
    snapshot_inputs(repo, source)
    if extension is not None:
        extension.snapshot(repo, source)
    sys.path.insert(0, str(source/'tools/scripts'))
    sys.path.insert(0, str(source))
    soc = load('s3_campaign_soc', source/'tools/scripts/e203_soc.py')
    clear = load('s3_campaign_clear', source/'tools/ppa/s3_task_clear_protocol.py')
    config = soc.contract.configuration(args.schedule, '-O2', 'both-unroll-no-masks')
    pins = {str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    report = dict(status='RUNNING', scope='fresh-process CPU/RTL, physical parameter preclear; no mapped/PPA or official acceptance',
                  configuration=config, bias_kind=args.bias_kind, original_layers=layers,
                  clock_configuration=clock_configuration(args.platform_clocks),
                  platform_assertions='enabled' if args.platform_assertions else 'historical_DISABLED_SV_ASSERTION_define',
                  chisel_procedural_assertions='retained',
                  original_source_sha256=pins, steps=[], task_results=[],
                  cache_policy='REVIEW_PENDING', fifo_payload_physical_zero='UNPROVEN',
                  area_energy_sta='NOT_MEASURED')
    if extension is not None:
        report['activity_extension'] = extension.metadata(source)
        report['clock_configuration'] = report['activity_extension']['clock_configuration']
    write(out/'plan.json', dict(**report, arguments=dict(vars(args),repo=str(repo),out=str(out)),
                               simulator=args.simulator, affinity=sorted(os.sched_getaffinity(0))))

    def step(name, command, cwd=out, timeout=7200):
        logfile = out/(name+'.log')
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open('x') as log:
            log.write(json.dumps([str(x) for x in command])+'\n')
            log.flush()
            result = subprocess.run(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=timeout,
                                    env=dict(os.environ, PWD=str(Path(cwd).resolve())))
        report['steps'].append(dict(name=name, native_exit=result.returncode, waitpid_completed=True,
                                    command=[str(x) for x in command], log_sha256=sha(logfile)))
        write(out/'result.json', report)
        if result.returncode:
            raise RuntimeError('native exit '+str(result.returncode)+': '+str(logfile))
        return logfile.read_text(errors='replace').split('\n',1)[1]

    try:
        report['versions'] = {}
        for tool, flag in [(args.cross_prefix+'gcc','--version'), ('gcc','--version'),
                           ('vcs','-ID') if args.simulator=='vcs' else ('iverilog','-V')]:
            report['versions'][tool] = step('version-'+Path(tool).name, [tool,flag], timeout=120)
        firmware = source/'tests/e203/firmware'
        (out/'s3_clear_main.c').write_text(clear.firmware_wrapper(firmware/'main.c', sha(firmware/'main.c')))
        observer = clear.observer_declarations()
        (out/'s3_clear_observer.svh').write_text(observer)
        original_tb = (source/'tests/e203/tb_accel_soc.sv').read_text()
        generated_tb = instrument_tb(original_tb, observer,args.platform_clocks)
        if extension is not None:
            generated_tb = extension.testbench(generated_tb, source, out, args)
        (out/'tb.sv').write_text(generated_tb)
        write(out/'clear-recipe.json', dict(frozen_main_sha256=sha(firmware/'main.c'),
            helper_sha256=sha(source/'tools/ppa/s3_task_clear_protocol.py'),
            generated_c_sha256=sha(out/'s3_clear_main.c'), generated_tb_sha256=sha(out/'tb.sv'),
            clear_counts=clear.CLEAR_COUNTS, tasks_per_process=1, reset='fresh native process',
            policy='REVIEW_PENDING', fifo_payload_physical_zero='UNPROVEN'))
        elf = out/'accel_soc'
        command = [args.cross_prefix+'gcc','-march=rv32imac_zicsr2p0_zifencei2p0','-mabi=ilp32',
            '-O2',*soc.contract.compiler_defines(config),'-fstack-usage','-ffreestanding','-fno-builtin',
            '-msmall-data-limit=0','-nostdlib','-nostartfiles','-static','-mcmodel=medany',
            '-Wl,--no-relax','-Wl,--build-id=none','-T',str(firmware/'link.ld'),
            str(firmware/'start.S'),str(out/'s3_clear_main.c'),str(firmware/'accel.c'),'-o',str(elf)]
        step('firmware-build', command)
        step('objcopy', [args.cross_prefix+'objcopy','-O','verilog',str(elf),str(elf)+'.verilog'])
        image = out/'accel_soc.verilog'
        image.write_text(image.read_text().replace('@800','@000'))
        disassembly = step('firmware-disassembly',[args.cross_prefix+'objdump','--disassemble-all',str(elf)])
        if '80000086 <write_tohost>' not in disassembly:
            raise ValueError('tohost PC identity differs from frozen TB')
        report['firmware_elf_sha256'], report['firmware_image_sha256'] = sha(elf), sha(image)
        sources = sorted(p for p in (source/'rtl').rglob('*') if p.suffix in ['.v','.sv'])+[out/'tb.sv']
        if extension is not None:
            sources = extension.sources(sources, source, out)
        includes = [str(source/'rtl'/p) for p in ['core','perips','perips/apb_i2c']]
        (out/'rtl.f').write_text(''.join(str(p)+'\n' for p in sources))
        if args.simulator=='vcs':
            build = vcs_assertion_command(soc.vcs_build_command(out, out/'rtl.f', includes, args.waves),
                                          args.platform_assertions)
            if args.platform_assertions:
                xchecker = source/'rtl/general/sirv_gnrl_xchecker.v'
                if xchecker not in sources:
                    raise ValueError('vendor xchecker missing from full platform RTL')
                report['platform_xchecker_sha256'] = sha(xchecker)
            binary, program = out/'accel_soc', [str(out/'accel_soc')]
            # Keep executable simulator and RISC-V ELF identities separate.
            build[build.index('-o')+1] = str(out/'simv')
            binary, program = out/'simv', [str(out/'simv')]
        else:
            binary, program = out/'soc.vvp', ['vvp',str(out/'soc.vvp')]
            build = ['iverilog','-g2012','-s','tb_accel_soc','-DDISABLE_SV_ASSERTION=1',
                     *['-I'+p for p in includes],'-o',str(binary),'-f',str(out/'rtl.f')]
        if extension is not None:
            build = extension.build_command(build)
        step('simulator-build', build)
        report['simulator_sha256'] = sha(binary)
        vectors = out/'original-vectors'
        report['fixture'] = soc.load_fixture(vectors,12)
        # Verify every original tensor and its exact unbounded integer result.
        report['integer_reference'] = soc.check_vectors(vectors,12)
        for layer in layers:
            task = out/('task-%02d'%layer)
            view = task/'vectors'
            (view/'layer_00').mkdir(parents=True)
            for p in (vectors/('layer_%02d'%layer)).iterdir():
                shutil.copy2(p,view/'layer_00'/p.name)
            identity = soc.vector_identity(view,1,args.schedule)
            log = step('task-%02d/simulation'%layer, program+[
                '+TESTCASE='+str(elf),'+VECTORS='+str(view),'+TASKS=1',
                '+DUMPWAVE='+str(int(args.waves)),'+MAX_CYCLES='+str(args.max_cycles),
                '+FIRST_SOURCE_STALL='+str(args.first_source_stall),
                *soc.contract.simulator_arguments(args.schedule)], cwd=task)
            native_layers = soc.check_log(log,1,args.schedule)
            clocks = check_clock_observations(log,args.platform_clocks)
            counters = soc.check_performance(log,native_layers,args.schedule)
            windows = soc.check_task_windows(log,native_layers)
            clear_lines = re.findall(r'^S3_TASK_CLEAR_OBSERVED .*$',log,re.M)
            if len(clear_lines)!=1 or len(windows)!=1:
                raise ValueError('missing clear or request-window proof')
            if windows[0]['first_request_wait'] < args.first_source_stall:
                raise ValueError('first-request injected wait was omitted')
            clear_record = dict(item.split('=',1) for item in clear_lines[0].split()[1:])
            if (int(clear_record['mode_sram']) != int(args.bias_kind=='sram') or
                    int(clear_record['writes']) != clear.CLEAR_COUNTS[args.bias_kind]['accepted_writes']):
                raise ValueError('physical bias kind or clear work differs')
            item = dict(original_layer=layer,native_layer=0,cycles=native_layers[0]['cycles'],
                        performance=counters[0],window=windows[0],clear=clear_record,
                        measured_clocks=clocks,**identity)
            if args.schedule in soc.contract.NICE_SCHEDULES:
                item['nice_activity'] = soc.check_nice_activity(log,native_layers,args.schedule)[0]
            if extension is not None:
                item['activity'] = extension.inspect_task(log, task, item)
            report['task_results'].append(item)
            write(out/'result.json',report)
            print('S3_CLEAR_TASK_PASS original_layer=%d cycles=%d first_wait=%d clear_cycles=%s'%(
                layer,item['cycles'],windows[0]['first_request_wait'],clear_record['clear_cycles']),flush=True)
        report['status'] = 'DEVELOPMENT_PASS_POLICY_PENDING'
        report['cycles'] = sum(x['cycles'] for x in report['task_results'])
        report['outputs'] = len(layers)*25344
    except Exception as exc:
        report['status'], report['error'] = 'FAIL', str(exc)
        print('S3_CLEAR_CAMPAIGN_FAIL',str(exc),file=sys.stderr,flush=True)
    report['source_drift'] = [name for name,h in pins.items() if sha(source/name)!=h]
    if extension is not None:
        report['source_drift'] += extension.input_drift()
    if report['source_drift']:
        report['status'] = 'FAIL'
    write(out/'result.json',report)
    print(report['status'],str(out/'result.json'),flush=True)
    return int(report['status']=='FAIL')


if __name__=='__main__':
    raise SystemExit(main())
