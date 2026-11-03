#!/usr/bin/env python3
"""Replay frozen xu64 development evidence. No timing/PPA/energy qualification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

MAIN = '286b95a4e0b05b78f39ef4d648d1f922e684d7fc'
CHILD = '7aae96776e116d5e95d6ebb49d29a5fccce04ab9'
CASES = [('wide64-real1-02', 'pe64', 'bias-hw-pe64-autogroup-window'),
         ('compat32-real1-01', 'pe64', 'bias-hw-pe32-autogroup-window'),
         ('compat8-real1-01', 'pe64', 'bias-hw-autogroup-window'),
         ('physical32-real1-01', 'pe32', 'bias-hw-pe32-autogroup-window'),
         ('physical8-real1-01', 'pe8', 'bias-hw-autogroup-window')]


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root, raw):
    sys.path.insert(0, str(root / 'tools/scripts'))
    import e203_soc as soc
    manifest = json.loads((raw / 'manifest.json').read_text())
    for name, record in manifest.items():
        path = raw / name
        require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'raw changed: ' + name)
    source = json.loads((raw / 'source-final.json').read_text())
    checked = 0
    for key, repo, commit in [('main', root, MAIN), ('child', root / 'third-party/e203_hbirdv2', CHILD)]:
        require(source[key]['commit'] == commit, 'frozen commit differs')
        for record in source[key]['files']:
            name, mode = record['path'], record['mode']
            git_entry = subprocess.check_output(['git', 'ls-tree', commit, '--', name], cwd=repo, text=True).split()
            require(git_entry[:3] == [mode, 'commit' if mode == '160000' else 'blob', record['git_oid']], 'git entry differs: ' + name)
            if mode == '160000':
                require(record['git_oid'] == CHILD, 'gitlink differs')
                continue
            path = repo / name
            if mode == '120000':
                require(path.is_symlink(), 'symlink type differs: ' + name)
                data = os.readlink(path).encode()
            else:
                require(path.is_file() and not path.is_symlink(), 'file type differs: ' + name)
                require(bool(path.stat().st_mode & stat.S_IXUSR) == (mode == '100755'), 'file mode differs: ' + name)
                data = path.read_bytes()
            require(len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'], 'frozen bytes differ: ' + name)
            original = subprocess.check_output(['git', 'show', commit + ':' + name], cwd=repo)
            require(original == data, 'frozen working bytes differ from commit: ' + name)
            checked += 1
    child = root / 'third-party/e203_hbirdv2'
    delta = subprocess.check_output(['git', 'diff', '--name-status', 'fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5', CHILD], cwd=child, text=True).splitlines()
    expected_delta = ['A\trtl/e203/perips/' + name for name in
                      ['XuParallelAutoGroupCore64.sv', 'XuParallelBiasCache64.sv', 'XuParallelComputeCore64.sv',
                       'XuParallelWeightBank64.sv', 'xu_pe64_icb_slave.v']]
    expected_delta += ['M\trtl/e203/subsys/e203_subsys_perips.v', 'M\tvsim/bin/run.makefile']
    require(delta == expected_delta, 'child changed outside explicit 64PE insertion')
    require(subprocess.check_output(['git', 'show', '94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114:src/main/scala/linear/XuParallelCore.scala'], cwd=root) ==
            (root / 'src/main/scala/linear/XuParallelCore.scala').read_bytes(), 'original32 Chisel changed')
    state = json.loads((raw / 'screen-state.json').read_text())
    require(state['status'] == 'COMPLETED_LOCAL_NOT_QUALIFIED' and len(state['cases']) == 6, 'driver not completed')
    require(all(case['returncode'] == 0 and case['finished'] >= case['started'] for case in state['cases']), 'driver failed')
    runs = []
    for name, variant, schedule in CASES:
        directory = raw / name
        report = json.loads((directory / 'result.json').read_text())
        text = (directory / 'simulation.log').read_text().split('\n', 1)[1]
        layers = soc.check_log(text, 1)
        for layer, performance in zip(layers, soc.check_performance(text, layers, schedule, variant)):
            layer['performance'] = performance
        require(report['status'] == 'PASS' and report['main_commit'] == MAIN and report['e203_commit'] == CHILD and
                report['accel_variant'] == variant and report['firmware_schedule'] == schedule and report['simulator'] == 'verilator' and
                report['layers'] == layers, 'run identity/counters differ: ' + name)
        require(report['pe_activity'] == soc.check_pe_activity(text, layers, schedule, variant), 'physical work differs: ' + name)
        require(report['autogroup_activity'] == soc.check_autogroup_activity(text, layers, schedule), 'row work differs: ' + name)
        require(report['firmware_opt'] == '-O2' and report['firmware_experiment'] == 'both-unroll-no-masks', 'flags differ')
        for path, digest in report['log_sha256'].items():
            require(sha(directory / path) == digest, 'run log changed: ' + path)
        require(sha(directory / 'accel_soc') == report['firmware_elf_sha256'] and sha(directory / 'accel_soc.verilog') == report['firmware_image_sha256'], 'firmware outputs changed')
        for path, digest in report['vectors'].items():
            require(sha(directory / 'vectors' / path) == digest == report['fixture']['files'][path], 'vectors differ')
        for path, digest in report['source_sha256'].items():
            prefix = 'third-party/e203_hbirdv2/vsim/install/rtl/'
            actual = root / 'third-party/e203_hbirdv2/rtl/e203' / path[len(prefix):] if path.startswith(prefix) else root / path
            require(sha(actual) == digest, 'measured source differs: ' + path)
        require(sha(root / 'tools/scripts/e203_soc.py') == report['runner_sha256'] and
                sha(root / 'tools/scripts/xu_firmware_contract.py') == report['contract_sha256'], 'runner/contract changed')
        for path, digest in report['firmware_sha256'].items():
            require(sha(root / 'tests/e203/firmware' / path) == digest, 'firmware source changed')
        runs.append(report)
    common = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256', 'versions', 'tools',
              'vectors', 'fixture', 'firmware_sha256', 'firmware_opt', 'firmware_experiment']
    for key in common:
        require(all(run[key] == runs[0][key] for run in runs[1:]), 'common identity differs: ' + key)
    require(len({run['simulator_sha256'] for run in runs[:3]}) == 1, 'same physical64 binary differs')
    require(len({runs[0]['simulator_sha256'], runs[3]['simulator_sha256'], runs[4]['simulator_sha256']}) == 3, 'physical variants share binary')
    require(runs[1]['layers'] == runs[3]['layers'] and runs[2]['layers'] == runs[4]['layers'], 'compatibility PERF differs')
    direct = []
    for kind, lanes, groups, launches, accepted in [('wide64', 64, 8, 15, 11031), ('compat32', 32, 16, 27, 11131), ('compat8', 8, 64, 99, 11731)]:
        text = (raw / 'direct-02' / kind / 'simulation.log').read_text().split('\n', 1)[1]
        pattern = r'XU_PE64_WRAPPER_PASS mode_lanes=' + str(lanes) + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)'
        matches = re.findall(pattern, text)
        require(len(matches) == 1, 'direct completion missing: ' + kind)
        observed = list(map(int, matches[0]))
        require(observed[1] > 0 and [observed[0]] + observed[2:] == [groups, launches, launches, accepted, accepted], 'direct counts differ: ' + kind)
        require(re.findall(r'XU_PE64_DIRECT_ACTIVITY physical_pes=64 mac_beats=(\d+) lane_macs=(\d+)', text) == [(str(launches * 64), str(49664 + 128 * lanes))], 'direct physical work differs')
        require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text), 'direct failure')
        direct.append(dict(mode=kind, lanes=lanes, counts=observed))
    legacy = json.loads((raw / 'pe64-legacy5-01/result.json').read_text())
    require(legacy['status'] == 'PASS' and legacy['main_commit'] == MAIN and legacy['e203_commit'] == CHILD and
            legacy['accel_variant'] == 'pe64' and legacy['tests'] == ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x'], 'actual legacy5 incomplete')
    for name in legacy['tests']:
        text = (raw / 'pe64-legacy5-01' / (name + '.log')).read_text()
        require('TEST_PASS' in text and 'XU_ACCEL_PE64=1' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', text), 'legacy physical64 execution differs: ' + name)
    for name, digest in legacy['log_sha256'].items():
        require(sha(raw / 'pe64-legacy5-01' / name) == digest, 'legacy log changed')
    require(re.search(r'Ran 67 tests in [^\n]+\n\nOK\s*$', (raw / 'host-02.log').read_text()), 'host67 incomplete')
    require(re.search(r'Ran 68 tests in [^\n]+\n\nOK\s*$', (raw / 'host-03.log').read_text()), 'final host68 incomplete')
    require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$', (raw / 'numeric.log').read_text()), 'numeric42 incomplete')
    require('All tests passed.' in (raw / 'chisel/test.log').read_text(), 'Chisel test incomplete')
    require(re.search(r'Ran 1 test in [^\n]+\n\nOK\s*$', (raw / 'boundary-01.log').read_text()), 'boundary standalone test incomplete')
    boundary = (raw / 'boundary-01/boundary/simulation.log').read_text().split('\n', 1)[1]
    require(re.findall(r'XU_PE64_BOUNDARY_PASS mode=(\d) unknown_reads=14 mode_error=1 pop_retired=1', boundary) == ['0', '1', '2'] and
            boundary.count('XU_PE64_BOUNDARIES_PASS modes=3') == 1, 'boundary actual coverage incomplete')
    for name, record in json.loads((raw / 'boundary-source.json').read_text()).items():
        require((root / name).stat().st_size == record['bytes'] and sha(root / name) == record['sha256'], 'boundary source changed')
    cycles = {name: run['layers'][0]['cycles'] for (name, _, _), run in zip(CASES, runs)}
    return dict(status='LOCAL_SCREEN_PASS_NOT_QUALIFIED', main_commit=MAIN, e203_commit=CHILD,
                scope='Local GCC14.2/Verilator5.032, real layer00 only, historical development clocks and no formal clear/request window',
                frozen_files=checked, raw_payloads=len(manifest), host_tests=68, previous_host_tests=67, additional_boundary_tests=1,
                boundary_modes=3, boundary_unknown_reads=42, boundary_mode_errors=3,
                numeric_tests=42, chisel_tests=1, legacy_cases=5,
                cycles=cycles, enabled_lane_macs_per_task=1622016, same_physical64_binary=runs[0]['simulator_sha256'],
                common_identity=common, direct=direct,
                wide64_reduction_vs_same64_schedule32_percent=100 * (runs[1]['layers'][0]['cycles'] - runs[0]['layers'][0]['cycles']) / runs[1]['layers'][0]['cycles'],
                wide64_reduction_vs_same64_schedule8_percent=100 * (runs[2]['layers'][0]['cycles'] - runs[0]['layers'][0]['cycles']) / runs[2]['layers'][0]['cycles'],
                rows=[dict(case=name, variant=run['accel_variant'], schedule=run['firmware_schedule'], layers=run['layers'],
                           pe_activity=run['pe_activity'], autogroup_activity=run['autogroup_activity']) for (name, _, _), run in zip(CASES, runs)],
                retained=False, not_run=['server VCS full12', 'mapped equivalence', 'complete150MHz STA', 'same-library area', 'fullSoC task energy'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.raw.resolve())
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'cycles', 'raw_payloads', 'frozen_files')}, indent=2))
