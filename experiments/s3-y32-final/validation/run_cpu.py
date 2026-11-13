#!/usr/bin/env python3
"""Run the exact sealed production N2 SoC with a CPU GPIO/SystemBus loader.

Every production source byte and definition comes from the final sealed PPA input. Testbench tensors are
driven onto existing GPIO pads; only boot firmware initializes physical ITCM.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
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
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}


def write(path, value):
    temp = path.with_suffix(path.suffix + '.new')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def execute(command, cwd, logfile, timeout=14400):
    with logfile.open('w') as stream:
        stream.write(json.dumps(dict(command=[str(x) for x in command], cwd=str(cwd))) + '\n')
        stream.flush()
        child = subprocess.Popen([str(x) for x in command], cwd=cwd,
                                 stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        write(logfile.with_suffix('.process.json'), dict(pid=child.pid, command=[str(x) for x in command],
              started_at=datetime.now(timezone.utc).isoformat(), status='RUNNING'))
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            raise
    write(logfile.with_suffix('.process.json'), dict(pid=child.pid, command=[str(x) for x in command],
          finished_at=datetime.now(timezone.utc).isoformat(), status='PASS' if code == 0 else 'FAIL', returncode=code))
    if code:
        raise RuntimeError('command exit %s: %s' % (code, logfile))
    return logfile.read_text(errors='replace').split('\n', 1)[1]


def prepare(args, out, report):
    package = args.ppa_package.resolve()
    pinned = json.loads((package / 'package-files.json').read_text())
    for name, digest in pinned.items():
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('unsafe sealed package member path')
        item = package / name
        if item.is_symlink() or not item.is_file() or sha(item) != digest:
            raise ValueError('sealed PPA input drift: ' + name)
    manifest = json.loads((package / 'manifest.json').read_text())
    definitions = json.loads((package / 'defines.json').read_text())
    expected_geometry = dict(itcm=32, dtcm=32, shared=256, weights=16, bias=1, x=16,
                             result=21, total_macros=374, engines=0, mac_pe=64)
    expected_defines = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA',
                        'XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM', 'XU_MATRIX_STORAGE_SRAM']
    if (manifest.get('production_test_loader') is not False or
            manifest.get('hardware_profile') != 'sysbus32-dma4-storage-sram-374-final' or
            manifest.get('expected_geometry') != expected_geometry or definitions != expected_defines):
        raise ValueError('required exact final production N2/DMA4/374-macro configuration differs')
    compile_names = (package / 'rtl.f').read_text().splitlines()
    staged = json.loads((package / 'source-manifest.json').read_text())
    if (sha(package / 'rtl.f') != manifest['rtl_f_sha256'] or
            len(compile_names) != manifest['source_count'] or
            compile_names != [item['path'] for item in staged['ordered_compile_sources']]):
        raise ValueError('sealed compile order/source count differs')
    if any(Path(name).is_absolute() or '..' in Path(name).parts for name in pinned):
        raise ValueError('unsafe sealed package member path')
    source = out / 'source'
    shutil.copytree(package / 'source', source)
    tests = source / 'tests'
    tests.mkdir()
    fw = tests / 'firmware'
    fw.mkdir()
    for name in ('start.S', 'link.ld'):
        shutil.copy2(ROOT / 'tests/e203/firmware' / name, fw / name)
    for original, name in [('gpio_main.c', 'dma_day_main.c'),
                           ('tb_sysbus32_gpio_soc.sv', 'tb_sysbus32_soc.sv'),
                           ('boot_cpu_macros.svh', 'boot_cpu_macros.svh')]:
        shutil.copy2(HERE / original, tests / name)
    shutil.copy2(HERE / 'check_results.py', source / 'check_results.py')
    shutil.copy2(HERE / 'run_cpu.py', source / 'run_cpu.py')
    shutil.copy2(ROOT / 'experiments/s3-y32-compliant32/validation/run_cpu_xmacro.py', source / 'firmware_helpers.py')
    shutil.copy2(HERE / 'generate_observer.py', source / 'generate_observer.py')
    generator = module('final_gpio_storage_generator', source / 'generate_observer.py')
    observer = tests / 'sysbus32_physical_observer.svh'
    generator.generate(observer, core='`CORE', clock='shared_mem_clk', result_macros=21,
                       dma='`DMA', reset='!shared_mem_rst_n')
    generic = tests / 'generic_ramsp_non_ppa.sv'
    shutil.copy2(package / 'local-only/generic_ramsp_non_ppa.sv', generic)
    production = {name: digest for name, digest in pinned.items()
                  if name.startswith('source/') and name.endswith(('.v', '.sv'))}
    for name, digest in production.items():
        if sha(out / name) != digest:
            raise ValueError('production RTL changed: ' + name)
    if not all(name in production for name in compile_names):
        raise ValueError('compile SET contains an unsealed production source')
    geometry = dict(x_macros=16, x_physical_bytes=32768, total_internal_macros=54,
                    full_soc_macros=374, clear_total16bit=55040, result_macros=21)
    source_identity = 'ALL_SEALED_FINAL_PRODUCTION_RTL_EXACT_NO_STORAGE_OVERLAY'
    report['storage_binding'] = dict(storage=dict(result_macros=21, internal_macros=54,
        full_soc_macros=374), clear=dict(total16bit_writes=55040, W=16384, BIAS=768,
        X=16384, RESULT=21504), observer_generator_sha256=sha(HERE / 'generate_observer.py'))
    (tests / 'gpio_profile.svh').write_text(''.join('`define %s %d\n' % (name, value) for name, value in [
        ('G32_INTERNAL_MACROS', geometry['total_internal_macros']), ('G32_TOTAL_MACROS', geometry['full_soc_macros']),
        ('G32_RESULT_MACROS', geometry['result_macros'])]))
    ordered = [out / name for name in (package / 'rtl.f').read_text().splitlines() if name]
    ordered += [generic, tests / 'StorageMacroObserver.sv', tests / 'tb_sysbus32_soc.sv']
    filelist = out / 'rtl.f'
    filelist.write_text(''.join(str(path) + '\n' for path in ordered))
    binary = out / 'simulator/sysbus32_gpio_soc'
    includes = [source / 'rtl/core', source / 'rtl/perips', source / 'rtl/perips/apb_i2c', tests]
    command = ['verilator', '--binary', '--timing', '--assert', '-CFLAGS', '-std=gnu++20',
        '-j', str(args.jobs), '-Wno-fatal', '--top-module', 'tb_sysbus32_soc',
        '-Mdir', str(binary.parent), '-o', binary.name,
        *['-D' + name for name in definitions], *['-I' + str(path) for path in includes], '-f', str(filelist)]
    helper = module('gpio_firmware_helper', source / 'firmware_helpers.py')
    report['firmware'] = helper.compile_firmware(tests, out / 'firmware', args.cross_prefix)
    report.update(ppa_binding=dict(path=str(package), package_files_sha256=sha(package / 'package-files.json'),
        manifest_sha256=sha(package / 'manifest.json'), production_rtl_files=production,
        source_byte_identity=source_identity, definitions_exact=definitions,
        source_manifest_sha256=sha(package / 'source-manifest.json'),
        ordered_compile_sources=[dict(path=name, sha256=production[name]) for name in compile_names],
        hardware_profile=manifest['hardware_profile']),
        definitions=definitions, source_sha256=files(source), build_command=command,
        x_sram_configuration=geometry)
    write(out / 'source-manifest.json', report['source_sha256'])
    return binary


def replay(args, out, report):
    origin = args.replay_from.resolve()
    previous = json.loads((origin / 'result.json').read_text())
    if previous.get('status') != 'PASS' or previous.get('schema') != 's3-final-production-gpio-cpu-v1':
        raise ValueError('replay requires completed production GPIO CPU PASS')
    if files(origin / 'source') != previous['source_sha256']:
        raise ValueError('replay source drift')
    if sha(HERE / 'check_results.py') != previous['source_sha256']['check_results.py']:
        raise ValueError('checker changed since proven replay simulator')
    shutil.copytree(origin / 'source', out / 'source')
    shutil.copytree(origin / 'firmware', out / 'firmware')
    binary = origin / 'simulator/sysbus32_gpio_soc'
    if sha(binary) != previous['simulator_sha256']:
        raise ValueError('replay simulator drift')
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(out / 'firmware' / name) != previous['firmware'][key]:
            raise ValueError('replay firmware drift')
    for name in ('ppa_binding', 'definitions', 'firmware', 'source_sha256', 'x_sram_configuration'):
        report[name] = previous[name]
    if previous.get('storage_binding'):
        report['storage_binding'] = previous['storage_binding']
    report['replay'] = dict(path=str(origin), result_sha256=sha(origin / 'result.json'),
                            compilation='NOT_REPEATED_IDENTICAL_BINARY')
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--ppa-package', type=Path)
    parser.add_argument('--replay-from', type=Path)
    parser.add_argument('--tasks', type=int, choices=range(1, 13), default=1)
    parser.add_argument('--rows', type=int, choices=(1, 8), default=8)
    parser.add_argument('--jobs', type=int, choices=(1,), default=1)
    parser.add_argument('--warmup', action='store_true')
    parser.add_argument('--first-source-stall', type=int, default=0)
    parser.add_argument('--first-load-stall', type=int, default=0)
    parser.add_argument('--max-cycles', type=int, default=200000000)
    parser.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if bool(args.ppa_package) == bool(args.replay_from):
        parser.error('provide exactly one sealed --ppa-package or proven --replay-from')
    if args.replay_from and args.prepare_only:
        parser.error('replay inherits exact already proven storage/source configuration')
    if min(args.first_source_stall, args.first_load_stall) < 0:
        parser.error('stall counts must be nonnegative')
    out = args.out.resolve()
    if out.exists():
        parser.error('evidence directory must be new')
    out.mkdir(parents=True)
    report = dict(schema='s3-final-production-gpio-cpu-v1', status='RUNNING',
        started_at=datetime.now(timezone.utc).isoformat(),
        arguments={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        runner_sha256=sha(HERE / 'run_cpu.py'),
        qualification='LOCAL_GENERIC_MACRO_FUNCTIONAL_EVIDENCE_NOT_STA_AREA_POWER_OR_OFFICIAL_PRECISION',
        stimulus='Only existing GPIO pads drive tensors; CPU original LSU/BIU/SystemBus loads shared SRAM; no third ingress source',
        clock=dict(hf_period_fs=6666666, lf_period_fs=30517578126, throughput_conversion_hz=150000000,
            scope='clock stimulus only; no achieved STA frequency'))
    write(out / 'result.json', report)
    try:
        cpus = sorted(os.sched_getaffinity(0))[:args.jobs]
        os.sched_setaffinity(0, cpus)
        report['local_cpu_affinity'] = cpus
        report['tools'] = {}
        for name in ('verilator', 'g++', args.cross_prefix + 'gcc', args.cross_prefix + 'objcopy', args.cross_prefix + 'objdump'):
            executable = Path(shutil.which(name) or name)
            version = subprocess.run([str(executable), '--version'], capture_output=True, text=True, check=True)
            report['tools'][name] = dict(path=str(executable), resolved_path=str(executable.resolve()),
                sha256=sha(executable), version=(version.stdout + version.stderr).splitlines()[:4])
        vectors = args.vectors.resolve()
        verifier = module('gpio_vector_verifier', ROOT / 'experiments/s3-y32-compliant32/numeric/verify_vectors.py')
        report['vector_verifier_sha256'] = sha(ROOT / 'experiments/s3-y32-compliant32/numeric/verify_vectors.py')
        report['vector_audit'] = verifier.verify(vectors)
        report['vectors_manifest_sha256'] = sha(vectors / 'vectors-manifest.json')
        report['vector_byte_sha256'] = files(vectors)
        binary = replay(args, out, report) if args.replay_from else prepare(args, out, report)
        report['status'] = 'PREPARED_NOT_EXECUTED'
        write(out / 'result.json', report)
        if args.prepare_only:
            return 0
        if not args.replay_from:
            execute(report['build_command'], out, out / 'simulator-build.log')
        report.update(simulator_sha256=sha(binary), status='BUILD_PASS_ONLY')
        write(out / 'result.json', report)
        if args.build_only:
            return 0
        command = [binary, '+TESTCASE=' + str(out / 'firmware/dma_day_soc'),
            '+VECTORS=' + str(vectors), '+TASKS=' + str(args.tasks), '+ROWS=' + str(args.rows),
            '+WARMUP=' + str(int(args.warmup)), '+FIRST_SOURCE_STALL=' + str(args.first_source_stall),
            '+FIRST_LOAD_STALL=' + str(args.first_load_stall), '+MAX_CYCLES=' + str(args.max_cycles)]
        report.update(run_command=[str(x) for x in command], status='SIMULATING')
        write(out / 'result.json', report)
        log = execute(command, out, out / 'simulation.log')
        checker = module('gpio_frozen_checker', out / 'source/check_results.py')
        selected = dict(storage_configuration=report['storage_binding']) if report.get('storage_binding') else {}
        report.update(checker.check_log(log, args.tasks, args.rows, args.warmup, x_macros=True, **selected))
        for task in report['layers'] + report.get('warmup', {}).get('layers', []):
            if (task['channel']['forced_wait'] != args.first_source_stall or
                    task['channel']['forced_load_wait'] != args.first_load_stall):
                raise ValueError('requested versus measured endpoint stalls differ')
        if files(out / 'source') != report['source_sha256'] or files(vectors) != report['vector_byte_sha256']:
            raise ValueError('source or vector drift during execution')
        if sha(binary) != report['simulator_sha256']:
            raise ValueError('simulator drift during execution')
        report.update(status='PASS', source_drift=[], performance_scope='complete12' if args.tasks == 12 else 'partial task scope')
        print('G32_CPU_PASS ' + json.dumps(dict(tasks=args.tasks, outputs=report['outputs'], total_cycles=report['total_cycles'])), flush=True)
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
