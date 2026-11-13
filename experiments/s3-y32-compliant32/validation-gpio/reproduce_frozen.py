#!/usr/bin/env python3
"""Verify or replay a compact frozen production GPIO evidence bundle."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--case', choices=['task0', 'full12', 'dma-first-wait31', 'load-first-wait31'], default='task0')
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    expected = json.loads((bundle / 'files.json').read_text())
    actual_names = {str(path.relative_to(bundle)) for path in bundle.rglob('*')
                    if path.is_file() and path != bundle / 'files.json'}
    if actual_names != set(expected):
        raise ValueError('bundle file inventory differs')
    for name, digest in expected.items():
        path = bundle / name
        if path.is_symlink() or not path.is_file() or sha(path) != digest:
            raise ValueError('bundle drift: ' + name)
    base = json.loads((bundle / 'evidence/result.json').read_text())
    if base['status'] != 'PASS' or base['outputs'] != 25344:
        raise ValueError('not original completed GPIO single-task evidence')
    evidence = bundle / 'evidence'
    if args.case != 'task0':
        evidence = evidence / 'followups' / args.case
    original = json.loads((evidence / 'result.json').read_text())
    tasks = original['arguments']['tasks']
    if original['status'] != 'PASS' or original['outputs'] != tasks * 25344:
        raise ValueError('not completed selected GPIO case evidence')
    if (original['source_sha256'] != base['source_sha256'] or
            original['simulator_sha256'] != base['simulator_sha256']):
        raise ValueError('selected case did not use the frozen source and simulator')
    for name, digest in base['source_sha256'].items():
        if sha(bundle / 'source' / name) != digest:
            raise ValueError('frozen source mismatch: ' + name)
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(bundle / 'firmware' / name) != original['firmware'][key]:
            raise ValueError('frozen firmware mismatch')
    for path in sorted((bundle / 'vectors').rglob('*.mem')):
        name = str(path.relative_to(bundle / 'vectors'))
        if sha(path) != original['vector_byte_sha256'][name]:
            raise ValueError('selected task0 vector mismatch')
    helper = load('frozen_gpio_math', bundle / 'source/firmware_helpers.py')
    audit = helper.check_vectors(bundle / 'vectors', tasks)
    checker = load('frozen_gpio_checker', bundle / 'source/check_results.py')
    selected = dict(storage_configuration=original['storage_binding']) if original.get('storage_binding') else {}
    checked = checker.check_log((evidence / 'simulation.log').read_text(), tasks, 8, True, x_macros=True, **selected)
    if checked['total_cycles'] != original['total_cycles']:
        raise ValueError('original raw log and result differ')
    if args.verify_only:
        print(json.dumps(dict(status='PASS_FROZEN_CONTENT_AND_RAW_LOG_REPLAY_NO_NEW_SIMULATION',
                             source_files=len(original['source_sha256']), outputs=checked['outputs'],
                             total_cycles=checked['total_cycles'], vector_integer_MAC_RNE=audit)))
        return 0
    if args.out is None:
        parser.error('--out is required for a new simulation')
    out = args.out.resolve()
    if out.exists():
        parser.error('output must be new')
    out.mkdir(parents=True)
    shutil.copytree(bundle / 'source', out / 'source')
    shutil.copytree(bundle / 'firmware', out / 'firmware')
    old_out = str(Path(base['firmware']['elf']).parent.parent)
    (out / 'rtl.f').write_text((bundle / 'evidence/rtl.f').read_text().replace(old_out, str(out)))
    command = [str(item).replace(old_out, str(out)) for item in base['build_command']]
    with (out / 'build.log').open('w') as stream:
        subprocess.run(command, cwd=out, stdout=stream, stderr=subprocess.STDOUT, check=True)
    runtime = [str(item) for item in original['run_command']]
    runtime[0] = str(out / 'simulator/sysbus32_gpio_soc')
    runtime = ['+VECTORS=' + str(bundle / 'vectors') if item.startswith('+VECTORS=')
               else '+TESTCASE=' + str(out / 'firmware/dma_day_soc') if item.startswith('+TESTCASE=')
               else item for item in runtime]
    with (out / 'simulation.log').open('w') as stream:
        subprocess.run(runtime, cwd=out, stdout=stream, stderr=subprocess.STDOUT, check=True)
    actual = checker.check_log((out / 'simulation.log').read_text(), tasks, 8, True, x_macros=True, **selected)
    if actual['layers'] != checked['layers'] or actual['warmup'] != checked['warmup']:
        raise ValueError('new CPU simulation differs from frozen functional/cycle evidence')
    result = dict(status='PASS_NEW_SIMULATION_SAME_SELECTED_CASE_COUNTS_AND_CYCLES', selected_case=args.case, functional=actual,
                  simulator_sha256=sha(Path(runtime[0])), build_command=command, run_command=runtime,
                  selected_configuration=original['x_sram_configuration'],
                  limitation='Generic functional evidence for the selected frozen case and macro profile; no STA, area, mapped equivalence, power or formal contest qualification.')
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], outputs=actual['outputs'], total_cycles=actual['total_cycles'])))
    return 0


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    raise SystemExit(main())
