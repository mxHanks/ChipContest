#!/usr/bin/env python3
"""Isolated full-SoC RTL FST capture from a sealed, functionally PASS CPU source.

Only a copied TB gains read-only observation hooks; original RTL/runner/ELF stay
unchanged. This is RTL activity, not mapped coverage, official SRAM power or PPA.
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

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def files(directory):
    return {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def execute(command, directory, log, timeout):
    with log.open('w') as stream:
        stream.write(json.dumps(dict(command=[str(x) for x in command], cwd=str(directory))) + '\n')
        stream.flush()
        result = subprocess.run([str(x) for x in command], cwd=directory, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError('command exit %s: %s' % (result.returncode, log))
    return log.read_text(errors='replace').split('\n', 1)[1]


def prepare(args, out, report):
    base = args.base.resolve()
    previous = json.loads((base / 'result.json').read_text())
    if (previous.get('status') != 'PASS' or previous.get('x_sram_configuration', {}).get('x_macros') != 16 or
            previous.get('x_sram_configuration', {}).get('clear_total16bit') != 33536):
        raise ValueError('base must be sealed PASS16-X-macro CPU configuration')
    if files(base / 'source') != previous['source_sha256']:
        raise ValueError('sealed CPU source drift')
    source = out / 'source'
    shutil.copytree(base / 'source', source)
    shutil.copytree(base / 'firmware', out / 'firmware')
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(out / 'firmware' / name) != previous['firmware'][key]:
            raise ValueError('sealed firmware drift')
    tb = source / 'tests/tb_sysbus32_soc.sv'
    original = tb.read_text()
    if original.count('\nendmodule\n') != 1 or any(x in original for x in ('$dumpfile', '$dumpvars', '$dumpon', '$dumpoff')):
        raise ValueError('unsupported TB seam or competing SV trace control')
    updated = original
    extra_changed = set()
    if args.cpu_macro_package:
        package = args.cpu_macro_package.resolve()
        manifest = json.loads((package / 'manifest.json').read_text())
        pinned = json.loads((package / 'package-files.json').read_text())
        adapter_name = 'source/rtl/general/sirv_sim_ram.v'
        adapter = package / adapter_name
        if (manifest.get('expected_geometry', {}).get('total_macros') != 353 or
                sha(adapter) != pinned[adapter_name]):
            raise ValueError('CPU macro adapter is not sealed 353-macro PPA input')
        anchor = '    for(i=0;i<8192;i++)`ITCM.mem_r[i]={program_bytes[8*i+7],program_bytes[8*i+6],program_bytes[8*i+5],program_bytes[8*i+4],program_bytes[8*i+3],program_bytes[8*i+2],program_bytes[8*i+1],program_bytes[8*i]};'
        if updated.count(anchor) != 1:
            raise ValueError('boot firmware initialization seam differs')
        updated = updated.replace(anchor, '    activity_firmware_loaded=1;wait(&activity_boot_macro_done);')
        updated = updated.replace('\nendmodule\n', '\n  `include "activity_boot_cpu_macros.svh"\nendmodule\n')
        shutil.copy2(HERE / 'boot_cpu_macros.svh', source / 'tests/activity_boot_cpu_macros.svh')
        shutil.copy2(adapter, source / 'rtl/general/sirv_sim_ram.v')
        extra_changed = {'rtl/general/sirv_sim_ram.v', 'tests/activity_boot_cpu_macros.svh'}
        report['cpu_macro_adapter'] = dict(package=str(package), manifest_sha256=sha(package / 'manifest.json'),
                package_files_sha256=sha(package / 'package-files.json'), adapter_sha256=sha(adapter),
                boot_initializer_sha256=sha(HERE / 'boot_cpu_macros.svh'),
                scope='exact PPA CPU memory adapter with actual generic macro models; firmware-only physical initialization')
    tb.write_text(updated.replace('\nendmodule\n', '\n  `include "activity_monitor.svh"\nendmodule\n'))
    shutil.copy2(HERE / 'monitor.svh', source / 'tests/activity_monitor.svh')
    shutil.copy2(HERE / 'trace_main.cpp', source / 'trace_main.cpp')
    patch = ''.join(difflib.unified_diff(original.splitlines(True), tb.read_text().splitlines(True),
                                        fromfile='sealed/tests/tb_sysbus32_soc.sv', tofile='activity/tests/tb_sysbus32_soc.sv'))
    (out / 'tb-observer-only.patch').write_text(patch)
    changed = {name for name, digest in files(source).items() if previous['source_sha256'].get(name) != digest}
    if changed != {'tests/tb_sysbus32_soc.sv', 'tests/activity_monitor.svh', 'trace_main.cpp'} | extra_changed:
        raise ValueError('unexpected sealed source modification: ' + str(changed))
    rtl = source / 'rtl'
    sources = sorted(p for p in rtl.rglob('*') if p.suffix in ('.v', '.sv')) + [tb]
    (out / 'rtl.f').write_text(''.join(str(p) + '\n' for p in sources))
    defines = ['DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA', 'XU_MATRIX_DMA_SYSBUS32',
               'XU_SYSBUS_TEST_LOADER', 'XU_MATRIX_X_SRAM']
    includes = [rtl / 'core', rtl / 'perips', rtl / 'perips/apb_i2c', source / 'tests']
    binary = out / 'simulator/sysbus32_activity'
    command = ['verilator', '--cc', '--exe', '--build', '--timing', '--assert', '--trace-fst',
               '--trace-threads', '1', '--trace-underscore', '--trace-max-width', '65536',
               '-CFLAGS', '-std=gnu++20', '-j', str(args.jobs), '-Wno-fatal',
               '--top-module', 'tb_sysbus32_soc', '-Mdir', str(binary.parent), '-o', binary.name,
               *['-D' + value for value in defines], *['-I' + str(p) for p in includes],
               '-f', str(out / 'rtl.f'), str(source / 'trace_main.cpp')]
    report.update(base=dict(path=str(base), result_sha256=sha(base / 'result.json'),
                           original_simulator_sha256=previous['simulator_sha256']),
                  source_sha256=files(source), tb_patch_sha256=sha(out / 'tb-observer-only.patch'),
                  definitions=defines, firmware=previous['firmware'], build_command=command,
                  trace_policy=dict(timeprecision_fs=1, trace_depth_limit=None,
                    registration_levels=99, trace_max_width=65536, trace_max_array_default=32,
                    macro_arrays_omitted=True, per_task_files=True,
                    window='HF falling edge before clear request acceptance through HF falling edge after last Y response retirement',
                    duration='inclusive_task_cycles * measured_HF_period_fs', warmup=False,
                    poison_and_readback=False, gate='C++ open/dump/close; no SV dump controls'),
                  macro_scope=dict(actual_ramsp_instances=289, actual_internal=33, actual_shared=256,
                    cpu_itcm_dtcm_model='original behavioral sirv_sim_ram, logical interfaces only',
                    cpu_physical_macros_in_PPA=64, ppa_total_macros=353,
                    cpu_physical_macro_pin_activity='NOT_CAPTURED_OR_INFERRED',
                    qualification='NOT_POWER_READY_NO_MAPPED_COVERAGE_OR_VENDOR_MACRO_POWER'))
    write(out / 'source-manifest.json', report['source_sha256'])
    if args.cpu_macro_package:
        report['macro_scope'].update(actual_ramsp_instances=353,
            cpu_itcm_dtcm_model='exact sealed PPA adapter, 32 ITCM plus32 DTCM generic macros',
            cpu_physical_macro_pin_activity='ACTUAL_GENERIC_MACRO_PORTS_CAPTURED_VENDOR_MODEL_NOT_USED')
    return binary, previous


def replay(args, out, report):
    """Reuse exact proven simulator/source/firmware; never compile a replacement."""
    origin = args.replay_from.resolve()
    previous = json.loads((origin / 'result.json').read_text())
    if previous.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY':
        raise ValueError('replay origin must be a completed PASS activity run')
    if files(origin / 'source') != previous['source_sha256']:
        raise ValueError('activity replay source drift')
    binary = origin / 'simulator/sysbus32_activity'
    if sha(binary) != previous['simulator_sha256']:
        raise ValueError('activity replay simulator drift')
    for local, frozen in [('monitor.svh', 'tests/activity_monitor.svh'), ('trace_main.cpp', 'trace_main.cpp')]:
        if sha(HERE / local) != previous['source_sha256'][frozen]:
            raise ValueError('current activity instrumentation differs from proven simulator')
    if previous.get('macro_scope', {}).get('actual_ramsp_instances') not in (289, 353):
        raise ValueError('unsupported replay macro configuration')
    if previous.get('cpu_macro_adapter'):
        if sha(HERE / 'boot_cpu_macros.svh') != previous['source_sha256']['tests/activity_boot_cpu_macros.svh']:
            raise ValueError('macro boot initializer differs from proven simulator')
        report['cpu_macro_adapter'] = previous['cpu_macro_adapter']
    shutil.copytree(origin / 'source', out / 'source')
    shutil.copytree(origin / 'firmware', out / 'firmware')
    shutil.copy2(origin / 'tb-observer-only.patch', out / 'tb-observer-only.patch')
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(out / 'firmware' / name) != previous['firmware'][key]:
            raise ValueError('activity replay firmware drift')
    for name in ('base', 'source_sha256', 'tb_patch_sha256', 'definitions', 'firmware', 'trace_policy', 'macro_scope'):
        report[name] = previous[name]
    report.update(simulator_sha256=previous['simulator_sha256'],
                  replay=dict(path=str(origin), result_sha256=sha(origin / 'result.json'),
                              simulator_path=str(binary), compilation='NOT_REPEATED_IDENTICAL_BINARY'))
    write(out / 'source-manifest.json', report['source_sha256'])
    return binary, previous['functional']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=ROOT / 'build/compliant32-20261113/cpu-xmacro-task0-r1')
    parser.add_argument('--replay-from', type=Path, help='Reuse exactly a sealed PASS activity simulator; no compilation')
    parser.add_argument('--cpu-macro-package', type=Path, help='Isolated actual353 generic-macro activity using exact sealed PPA CPU adapter')
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--tasks', type=int, default=1, choices=range(1, 13))
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=2)
    parser.add_argument('--disk-limit-bytes', type=int, default=12 * 1024**3)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    if args.replay_from and (args.prepare_only or args.build_only):
        parser.error('replay cannot be combined with prepare-only/build-only')
    if args.replay_from and args.cpu_macro_package:
        parser.error('replay reuses its already selected CPU memory model')
    out = args.out.resolve()
    if out.exists():
        parser.error('evidence directory must be new')
    args.vectors = args.vectors.resolve()
    out.mkdir(parents=True)
    report = dict(schema='compliant32-local-fullsoc-rtl-activity-v1', status='RUNNING',
                  started_at=datetime.now(timezone.utc).isoformat(), arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                  scope='Full existing functional SoC RTL model plus external shared endpoint; no EDA, mapped coverage or power qualification.',
                  tool_sources={str(p): sha(p) for p in [HERE / 'run_activity.py', HERE / 'monitor.svh', HERE / 'trace_main.cpp']})
    write(out / 'result.json', report)
    try:
        verify = module('activity_vectors', ROOT / 'experiments/s3-y32-compliant32/numeric/verify_vectors.py')
        report['vector_audit'] = verify.verify(args.vectors)
        report['vector_byte_sha256'] = files(args.vectors)
        binary, previous = replay(args, out, report) if args.replay_from else prepare(args, out, report)
        report['status'] = 'PREPARED_NOT_EXECUTED'
        write(out / 'result.json', report)
        if args.prepare_only:
            return 0
        if not args.replay_from:
            execute(report['build_command'], out, out / 'build.log', 7200)
        report['simulator_sha256'] = sha(binary)
        report['status'] = 'BUILD_PASS_ONLY'
        write(out / 'result.json', report)
        if args.build_only:
            return 0
        cpus = sorted(os.sched_getaffinity(0))
        command = ['taskset', '-c', str(cpus[0]), str(binary),
                   '+TESTCASE=' + str(out / 'firmware/dma_day_soc'), '+VECTORS=' + str(args.vectors),
                   '+TASKS=' + str(args.tasks), '+ROWS=8', '+WARMUP=1', '+MAX_CYCLES=20000000',
                   '+FIRST_SOURCE_STALL=0', '+FIRST_LOAD_STALL=0',
                   '+ACTIVITY_DIR=' + str(out / 'activity'), '+ACTIVITY_LIMIT=' + str(args.disk_limit_bytes)]
        report['run_command'] = command
        report['status'] = 'SIMULATING'
        write(out / 'result.json', report)
        log = execute(command, out, out / 'simulation.log', 7200)
        checker = module('activity_frozen_checker', out / 'source/check_results.py')
        checked = checker.check_log(log, args.tasks, 8, True, x_macros=True)
        windows = [json.loads(line) for line in (out / 'activity/windows.jsonl').read_text().splitlines()]
        if len(windows) != args.tasks:
            raise ValueError('missing per-task activity window')
        for window, task in zip(windows, checked['layers']):
            if (window['layer'] != task['layer'] or window['inclusive_task_cycles'] != task['total'] or
                    window['clear_request_cycle'] != task['window']['clear_request'] or
                    window['last_y_response_cycle'] != task['window']['last_y_response'] or
                    window['duration_fs'] != task['total'] * checked['measured_clock']['measured_hf_period_fs']):
                raise ValueError('activity/independent original TB window mismatch')
        if checked['layers'][0]['total'] != previous['layers'][0]['total']:
            raise ValueError('first-task cycles differ from sealed no-trace baseline')
        if files(out / 'source') != report['source_sha256'] or files(args.vectors) != report['vector_byte_sha256']:
            raise ValueError('source/vector drift during activity run')
        if sha(binary) != report['simulator_sha256']:
            raise ValueError('simulator drift during activity run')
        macro_limitation = ('Actual353 generic macro ports are instantiated; exact vendor timing/power model is not used.'
            if report['macro_scope']['actual_ramsp_instances'] == 353 else
            'Only289 RAMSP ports exist in this frozen CPU functional model;64 PPA CPU macros are not physically instantiated.')
        report.update(status='PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY', functional=checked,
                      windows=windows, activity_files={str(p.relative_to(out)): dict(sha256=sha(p), bytes=p.stat().st_size) for p in sorted((out / 'activity').iterdir()) if p.is_file()},
                      limitations=[macro_limitation,
                        'Macro memory arrays and large TB/reference arrays are omitted; macro pins must pass a separate declaration inventory.',
                        'RTL activity needs final-netlist mapping, coverage, original PPA adapter validation and characterized SRAM power before use for contest power.'])
        write(out / 'result.json', report)
        print('C32_ACTIVITY_RESULT ' + json.dumps(dict(status=report['status'], outputs=checked['outputs'], cycles=checked['total_cycles'])))
        return 0
    except Exception as error:
        report.update(status='FAIL', error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        write(out / 'result.json', report)


if __name__ == '__main__':
    raise SystemExit(main())
