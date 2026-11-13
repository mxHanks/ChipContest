#!/usr/bin/env python3
"""Capture exact-profile production N2 GPIO CPU activity after baseline PASS.

Only the copied testbench gains a read-only monitor; production RTL, adapters,
firmware and checker remain the exact frozen bytes of the GPIO functional run.
"""
import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
sys.dont_write_bytecode = True

from activity_profile import validate as validate_profile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPECTED_DEFINITIONS = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA',
                        'XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM']


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def files(directory):
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def write(path, value):
    temp = path.with_suffix(path.suffix + '.new')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def execute(command, directory, log, timeout=21600):
    with log.open('w') as stream:
        stream.write(json.dumps(dict(command=[str(x) for x in command], cwd=str(directory))) + '\n')
        stream.flush()
        child = subprocess.Popen([str(x) for x in command], cwd=directory,
                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        state = dict(status='RUNNING', pid=child.pid, command=[str(x) for x in command],
                     started_at=datetime.now(timezone.utc).isoformat())
        write(log.with_suffix('.process.json'), state)
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            state.update(status='TIMEOUT_OWN_CHILD_TERMINATED', finished_at=datetime.now(timezone.utc).isoformat())
            write(log.with_suffix('.process.json'), state)
            raise
        state.update(status='PASS' if code == 0 else 'FAIL', returncode=code,
                     finished_at=datetime.now(timezone.utc).isoformat())
        write(log.with_suffix('.process.json'), state)
    if code:
        raise RuntimeError('command exit %s: %s' % (code, log))
    return log.read_text(errors='replace').split('\n', 1)[1]


def check_configuration(previous, profile=None):
    actual = 353 if profile is None else profile['actual_macro_count']
    definitions = EXPECTED_DEFINITIONS if profile is None else profile['definitions']
    if (previous.get('schema') != 's3-final-production-gpio-cpu-v1' or previous.get('status') != 'PASS' or
            previous.get('definitions') != definitions or
            previous.get('actual_generic_macro_instances') != actual or
            previous.get('production_topology') != dict(ingress_sources=2, pointer_bits=1, cpu_macros=64,
                shared_macros=256, internal_macros=actual - 320, total_macros=actual)):
        raise ValueError('base must be exact sealed production N2 GPIO CPU PASS for the selected explicit profile')
    if previous.get('ppa_binding', {}).get('definitions_exact') != definitions:
        raise ValueError('production PPA definitions do not match GPIO CPU configuration')
    if profile is not None:
        validate_profile(profile, previous)


def prepare(args, out, report):
    base = args.base.resolve()
    previous = json.loads((base / 'result.json').read_text())
    profile = json.loads(args.profile.read_text()) if args.profile else None
    check_configuration(previous, profile)
    actual = 353 if profile is None else profile['actual_macro_count']
    if files(base / 'source') != previous['source_sha256']:
        raise ValueError('sealed GPIO baseline source drift')
    source = out / 'source'
    shutil.copytree(base / 'source', source)
    shutil.copytree(base / 'firmware', out / 'firmware')
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(out / 'firmware' / name) != previous['firmware'][key]:
            raise ValueError('sealed GPIO firmware drift')
    tb = source / 'tests/tb_sysbus32_soc.sv'
    original = tb.read_text()
    if (original.count('\nendmodule\n') != 1 or
            any(token in original for token in ('$dumpfile', '$dumpvars', '$dumpon', '$dumpoff'))):
        raise ValueError('unsupported GPIO TB observation seam')
    tb.write_text(original.replace('\nendmodule\n', '\n  `include "activity_gpio_monitor.svh"\nendmodule\n'))
    shutil.copy2(HERE / 'gpio_monitor.svh', source / 'tests/activity_gpio_monitor.svh')
    shutil.copy2(HERE / 'gpio_trace_main.cpp', source / 'gpio_trace_main.cpp')
    patch = ''.join(difflib.unified_diff(original.splitlines(True), tb.read_text().splitlines(True),
        fromfile='sealed/tests/tb_sysbus32_soc.sv', tofile='observed/tests/tb_sysbus32_soc.sv'))
    (out / 'tb-observer-only.patch').write_text(patch)
    changed = {name for name, digest in files(source).items() if previous['source_sha256'].get(name) != digest}
    if changed != {'tests/tb_sysbus32_soc.sv', 'tests/activity_gpio_monitor.svh', 'gpio_trace_main.cpp'}:
        raise ValueError('unexpected GPIO observed-source modification: ' + repr(changed))
    production = previous['ppa_binding']['production_rtl_files']
    for name, digest in production.items():
        if sha(out / name) != digest:
            raise ValueError('observed production RTL changed: ' + name)
    ordered = [out / Path(name).relative_to(base) for name in (base / 'rtl.f').read_text().splitlines() if name]
    (out / 'rtl.f').write_text(''.join(str(path) + '\n' for path in ordered))
    binary = out / 'simulator/sysbus32_gpio_activity'
    rtl = source / 'rtl'
    includes = [rtl / 'core', rtl / 'perips', rtl / 'perips/apb_i2c', source / 'tests']
    command = ['verilator', '--cc', '--exe', '--build', '--timing', '--assert', '--trace-fst',
        '--trace-threads', '1', '--trace-underscore', '--trace-max-width', '65536',
        '-CFLAGS', '-std=gnu++20', '-j', str(args.jobs), '-Wno-fatal', '--top-module', 'tb_sysbus32_soc',
        '-Mdir', str(binary.parent), '-o', binary.name,
        *['-D' + name for name in previous['definitions']], *['-I' + str(path) for path in includes],
        '-f', str(out / 'rtl.f'), str(source / 'gpio_trace_main.cpp')]
    report.update(base=dict(path=str(base), result_sha256=sha(base / 'result.json'),
                           original_simulator_sha256=previous['simulator_sha256']),
        ppa_binding=previous['ppa_binding'], definitions=previous['definitions'],
        firmware=previous['firmware'], source_sha256=files(source),
        tb_patch_sha256=sha(out / 'tb-observer-only.patch'), build_command=command,
        macro_scope=dict(actual_ramsp_instances=actual, actual_internal=actual - 320, actual_shared=256,
            actual_itcm=32, actual_dtcm=32,
            cpu_physical_macro_pin_activity='ACTUAL_GENERIC_MODEL_PORTS_CAPTURED_VENDOR_MODEL_NOT_USED'),
        trace_policy=dict(timeprecision_fs=1, trace_depth_limit=None, registration_levels=99,
            trace_max_width=65536, trace_max_array_default=32, macro_arrays_omitted=True,
            window='HF falling edge before clear request acceptance through HF falling edge after last Y write response retirement',
            duration='inclusive_task_cycles * measured_HF_period_fs',
            gpio_subwindow='actual first GPIO data-pad presentation through last Y write response; exact fs and counted inclusive cycles separately',
            warmup='separate functional warmup preserved, excluded from traces', poison_and_readback=False,
            selected_window=args.window,
            gpio_raw_trace='Same binary serial replay with independent full initial snapshot at actual first GPIO data through finalY response; no concurrent trace-object dumps',
            gate='C++ open/dump/close; no SV dump controls'))
    if profile:
        report['activity_profile'] = dict(path=str(args.profile), sha256=sha(args.profile),
            name=profile['name'], macro_groups=profile['group_counts'], actual_macro_count=actual)
        if previous.get('storage_binding'):
            report['storage_binding'] = previous['storage_binding']
    write(out / 'source-manifest.json', report['source_sha256'])
    return binary, previous


def replay(args, out, report):
    origin = args.replay_from.resolve()
    previous = json.loads((origin / 'result.json').read_text())
    if (previous.get('schema') != 's3-final-production-gpio-fullsoc-rtl-activity-v1' or
            previous.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY' or
            any('XU_SYSBUS_TEST_LOADER' in name for name in previous.get('definitions', [])) or
            previous.get('macro_scope', {}).get('actual_ramsp_instances', 0) < 353):
        raise ValueError('replay requires completed exact-profile production GPIO activity PASS')
    if previous.get('activity_profile'):
        if not args.profile or sha(args.profile) != previous['activity_profile']['sha256']:
            raise ValueError('replay requires the same exact source-reviewed activity profile')
        validate_profile(json.loads(args.profile.read_text()), previous)
        report['activity_profile'] = previous['activity_profile']
        if previous.get('storage_binding'):
            report['storage_binding'] = previous['storage_binding']
    elif previous['macro_scope']['actual_ramsp_instances'] != 353 or args.profile:
        raise ValueError('nonlegacy macro layout requires a bound explicit profile')
    elif previous['definitions'] != EXPECTED_DEFINITIONS:
        raise ValueError('legacy353 profile definitions differ')
    if files(origin / 'source') != previous['source_sha256']:
        raise ValueError('observed replay source drift')
    if files(args.vectors) != previous['vector_byte_sha256']:
        raise ValueError('GPIO observed replay vector identity differs')
    for name, frozen in [('gpio_monitor.svh', 'tests/activity_gpio_monitor.svh'),
                         ('gpio_trace_main.cpp', 'gpio_trace_main.cpp')]:
        if sha(HERE / name) != previous['source_sha256'][frozen]:
            raise ValueError('GPIO instrumentation changed since proven task0')
    binary = origin / 'simulator/sysbus32_gpio_activity'
    if sha(binary) != previous['simulator_sha256']:
        raise ValueError('GPIO observed replay binary drift')
    shutil.copytree(origin / 'source', out / 'source')
    shutil.copytree(origin / 'firmware', out / 'firmware')
    shutil.copy2(origin / 'tb-observer-only.patch', out / 'tb-observer-only.patch')
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(out / 'firmware' / name) != previous['firmware'][key]:
            raise ValueError('GPIO observed replay firmware drift')
    for name in ('base', 'ppa_binding', 'definitions', 'firmware', 'source_sha256', 'tb_patch_sha256',
                 'macro_scope', 'trace_policy'):
        report[name] = previous[name]
    report['replay'] = dict(path=str(origin), result_sha256=sha(origin / 'result.json'),
                            simulator_path=str(binary), compilation='NOT_REPEATED_IDENTICAL_BINARY')
    write(out / 'source-manifest.json', report['source_sha256'])
    return binary, previous['functional']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base', type=Path)
    parser.add_argument('--replay-from', type=Path)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True, help='Explicit source-reviewed macro instance inventory bound to the production PPA package')
    parser.add_argument('--window', choices=('clear','gpio'), default='clear')
    parser.add_argument('--tasks', type=int, default=1, choices=range(1, 13))
    parser.add_argument('--jobs', type=int, choices=(1,), default=1)
    parser.add_argument('--disk-limit-bytes', type=int, default=12 * 1024**3)
    parser.add_argument('--max-cycles', type=int, default=200000000)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    if bool(args.base) == bool(args.replay_from):
        parser.error('provide exactly one frozen --base or proven --replay-from')
    if args.replay_from and (args.prepare_only or args.build_only):
        parser.error('replay cannot prepare/build a replacement simulator')
    out = args.out.resolve()
    args.vectors = args.vectors.resolve()
    if args.profile:
        args.profile = args.profile.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cpus = sorted(os.sched_getaffinity(0))[:args.jobs]
    os.sched_setaffinity(0, cpus)
    report = dict(schema='s3-final-production-gpio-fullsoc-rtl-activity-v1', status='RUNNING',
        started_at=datetime.now(timezone.utc).isoformat(),
        arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        local_cpu_affinity=cpus,
        tool_sources={str(HERE / name): sha(HERE / name) for name in
            ('run_gpio_activity.py', 'gpio_monitor.svh', 'gpio_trace_main.cpp', 'activity_profile.py')},
        scope='Exact selected production N2 RTL and source-reviewed complete macro profile; existing GPIO pads and CPU original SystemBus tensor loading. Generic RTL activity only.')
    write(out / 'result.json', report)
    try:
        verifier = module('gpio_activity_vectors', ROOT / 'experiments/s3-y32-compliant32/numeric/verify_vectors.py')
        report['vector_audit'] = verifier.verify(args.vectors)
        report['vector_byte_sha256'] = files(args.vectors)
        binary, previous = replay(args, out, report) if args.replay_from else prepare(args, out, report)
        if previous.get('vector_byte_sha256') and previous['vector_byte_sha256'] != report['vector_byte_sha256']:
            raise ValueError('vectors differ from no-trace baseline')
        warmup = bool(previous.get('arguments', {}).get('warmup', previous.get('warmup')))
        if args.replay_from:
            warmup = 'warmup' in previous
        report['warmup_enabled'] = warmup
        report['capture_window']=args.window
        report['trace_policy'].update(selected_window=args.window,window=('HF falling edge before accepted clear through HF falling edge after lastY response' if args.window=='clear' else 'Actual first GPIO data presentation through actual lastY response timestamp'),duration=('inclusive clear-toY cycles times HF period' if args.window=='clear' else 'actual lastY response fs minus actual first GPIO data fs'))
        report['status'] = 'PREPARED_NOT_EXECUTED'
        write(out / 'result.json', report)
        if args.prepare_only:
            return 0
        if not args.replay_from:
            execute(report['build_command'], out, out / 'build.log', 7200)
        report.update(simulator_sha256=sha(binary), status='BUILD_PASS_ONLY')
        write(out / 'result.json', report)
        if args.build_only:
            return 0
        os.sched_setaffinity(0, {cpus[0]})
        command = [binary, '+TESTCASE=' + str(out / 'firmware/dma_day_soc'), '+VECTORS=' + str(args.vectors),
            '+TASKS=' + str(args.tasks), '+ROWS=8', '+WARMUP=' + str(int(warmup)),
            '+MAX_CYCLES=' + str(args.max_cycles), '+FIRST_SOURCE_STALL=0', '+FIRST_LOAD_STALL=0',
            '+ACTIVITY_WINDOW='+args.window, '+ACTIVITY_DIR=' + str(out / 'activity'), '+ACTIVITY_LIMIT=' + str(args.disk_limit_bytes)]
        report.update(run_command=[str(x) for x in command], status='SIMULATING')
        write(out / 'result.json', report)
        log = execute(command, out, out / 'simulation.log')
        checker = module('frozen_gpio_activity_checker', out / 'source/check_results.py')
        selected = dict(storage_configuration=report['storage_binding']) if report.get('storage_binding') else {}
        checked = checker.check_log(log, args.tasks, 8, warmup, x_macros=True, **selected)
        windows = [json.loads(line) for line in (out / 'activity/windows.jsonl').read_text().splitlines()]
        if len(windows) != args.tasks:
            raise ValueError('missing GPIO per-task activity window')
        for window, task in zip(windows, checked['layers']):
            if (window['layer'] != task['layer'] or window['inclusive_task_cycles'] != task['total'] or
                    window['clear_request_cycle'] != task['window']['clear_request'] or
                    window['last_y_response_cycle'] != task['window']['last_y_response'] or
                    window['trace_window'] != args.window or
                    window['duration_fs'] != (task['total'] * checked['measured_clock']['measured_hf_period_fs'] if args.window=='clear' else window['last_y_response_fs']-task['gpio']['first_data_fs']) or
                    window['gpio_first_data_fs'] != task['gpio']['first_data_fs'] or
                    window['gpio_first_data_cycle'] != task['gpio']['first_data'] or
                    window['gpio_first_data_inclusive_cycles'] != task['load_to_y'] or
                    window['gpio_first_data_to_last_y_response_fs'] != window['last_y_response_fs'] - task['gpio']['first_data_fs']):
                raise ValueError('GPIO original checker / independent activity timestamps differ')
        compared = ('total', 'load_to_y', 'loading', 'clear', 'dma_payload')
        if any(checked['layers'][0][key] != previous['layers'][0][key] for key in compared):
            raise ValueError('GPIO first-task cycles differ from sealed no-trace baseline')
        if files(out / 'source') != report['source_sha256'] or files(args.vectors) != report['vector_byte_sha256']:
            raise ValueError('GPIO source or vector drift during activity capture')
        if sha(binary) != report['simulator_sha256']:
            raise ValueError('GPIO simulator drift during activity capture')
        report.update(status='PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY', functional=checked, windows=windows,
            activity_files={str(p.relative_to(out)): dict(sha256=sha(p), bytes=p.stat().st_size)
                for p in sorted((out / 'activity').iterdir()) if p.is_file()},
            limitations=['Generic RTL activity only; vendor SRAM power and timing model not used.',
                'Verilator is a two-state functional backend; measured FST unknown dwell cannot prove silicon unknown coverage.',
                'Every exact-profile physical macro pin/time audit is a separate mandatory step.',
                'Mapped annotation coverage, valid timing, characterized SRAM power and full-SoC energy remain unproven.'])
        write(out / 'result.json', report)
        print('G32_ACTIVITY_RESULT ' + json.dumps(dict(status=report['status'], outputs=checked['outputs'], cycles=checked['total_cycles'])), flush=True)
        return 0
    except Exception as error:
        report.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        write(out / 'result.json', report)


if __name__ == '__main__':
    raise SystemExit(main())
