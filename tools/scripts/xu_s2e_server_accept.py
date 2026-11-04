#!/usr/bin/env python3
"""Frozen S2e full VCS acceptance on the original server GCC10.2/VCS2020.

Python 3.6 / Git 1.8 compatible. No network/credentials/deployment operations.
Development acceptance only: not S0 clear/activity, PPA, energy or retention.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import e203_soc as soc
import server_accept as accept

E203_COMMIT = 'a0767db69628ef30e53de2d1e93dd0360c0ccf76'
VCS = '/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs'
GCC_PREFIX = str(Path.home() / 'Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')
LIMIT = ('Full VCS development acceptance and same-physical-RTL firmware control only. '
         'No complete nominal150MHz/clear/activity/mapped consistency/PPA/whole-SoC energy or contest qualification.')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def command(argv, cwd):
    return subprocess.check_output(argv, cwd=str(cwd), stderr=subprocess.STDOUT,
                                   universal_newlines=True)


def identity(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), 'regular runtime input missing: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def freeze_runtime():
    records = {}
    for repo, prefixes in [(soc.ROOT, ('src/', 'tests/e203/', 'tests/numeric/', 'tools/scripts/')),
                            (soc.E203, ('rtl/', 'vsim/', 'riscv-tools/riscv-tests/env/'))]:
        paths = command(['git','ls-files','-z'], repo).split('\0')
        for relative in paths:
            if relative and relative.startswith(prefixes):
                path = repo / relative
                records[str(path)] = identity(path)
    return records


def compare_real12(paired, control):
    fields = ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256',
              'versions','tools','vectors','fixture','simulator_sha256']
    need(paired['status'] == control['status'] == 'PASS' and
         paired['mode'] == control['mode'] == 'real' and paired['tasks'] == control['tasks'] == 12,
         'both complete real12 VCS runs required')
    need(paired['simulator'] == control['simulator'] == 'vcs', 'both real12 runs must use VCS')
    need(paired['firmware_schedule'] == soc.contract.PAIRED_HI_SCHEDULE and
         control['firmware_schedule'] == 'bias-hw-autogroup-window', 'wrong readback schedules')
    need(paired['firmware_opt'] == control['firmware_opt'] == '-O2' and
         paired['firmware_experiment'] == control['firmware_experiment'] == 'both-unroll-no-masks',
         'same frozen compiler configuration required')
    for key in fields:
        need(key in paired and paired[key] == control.get(key), 'same-physical-control identity differs: ' + key)
    for result in (paired, control):
        soc.contract.configuration_from_result(result)
        need(result['outputs'] == 304128 and result['write_words'] == 608256, 'complete canonical output work required')
        need([r['layer'] for r in result['layers']] == list(range(12)), 'missing or reordered layer')
        soc.contract.validate_result_activity(result['result_activity'], result['layers'], result['firmware_schedule'])
        for row in result['layers']:
            soc.contract.validate_performance(row['performance'], row['cycles'], result['firmware_schedule'])
    rows = [dict(layer=a['layer'], paired_cycles=a['cycles'], control_cycles=b['cycles'],
                 delta_cycles=a['cycles']-b['cycles'],
                 paired_result_reads=pa['legacy_words']+pa['packed_words'],
                 control_result_reads=ca['legacy_words']+ca['packed_words'])
            for a,b,pa,ca in zip(paired['layers'], control['layers'],
                                  paired['result_activity'], control['result_activity'])]
    return rows, fields


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(str(temporary), str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-main', required=True, help='full frozen main commit from deployment receipt')
    parser.add_argument('--expected-e203', required=True, help='full frozen child commit from deployment receipt')
    parser.add_argument('--cross-prefix', default=GCC_PREFIX)
    parser.add_argument('--vcs', default=VCS)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    need(re.fullmatch('[0-9a-f]{40}', args.expected_main) is not None and
         re.fullmatch('[0-9a-f]{40}', args.expected_e203) is not None, 'full Git SHA required')
    need(args.expected_e203 == E203_COMMIT, 'unexpected paired-HI wrapper child')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='xu-s2e-vcs-full-acceptance-v1', status='RUNNING_NOT_QUALIFIED',
                 pid=os.getpid(), started_epoch=time.time(), limitations=LIMIT,
                 expected_main=args.expected_main, expected_e203=args.expected_e203)
    save = lambda: write_json(out/'state.json', state)
    save()
    frozen = None
    try:
        for repo, expected in [(soc.ROOT,args.expected_main),(soc.E203,args.expected_e203)]:
            need(command(['git','rev-parse','HEAD'],repo).strip() == expected, 'frozen Git HEAD differs: ' + str(repo))
            need(not command(['git','status','--porcelain','--untracked-files=no'],repo).strip(),
                 'tracked working tree differs: ' + str(repo))
        need(soc.verify_submodule(soc.ROOT,soc.E203) == args.expected_e203, 'main/child gitlink differs')
        need(Path(args.vcs).is_file() and Path(args.cross_prefix+'gcc').is_file(), 'exact server tool paths missing')
        os.environ['PATH'] = str(Path(args.vcs).parent) + os.pathsep + os.environ.get('PATH','')
        need(Path(shutil.which('vcs')).resolve() == Path(args.vcs).resolve(), 'selected VCS executable differs')
        tool_records = [identity(Path(args.vcs).resolve()), identity(Path(args.cross_prefix+'gcc').resolve())]
        gcc_version = command([args.cross_prefix+'gcc','--version'],soc.ROOT)
        vcs_version = command([args.vcs,'-ID'],soc.ROOT)
        (out/'gcc-version.log').write_text(gcc_version)
        (out/'vcs-version.log').write_text(vcs_version)
        need('10.2.0' in gcc_version.splitlines()[0], 'same server GCC10.2 required')
        need('VCS Q-2020.03-SP2-6_Full64' in vcs_version, 'same VCS2020.03-SP2-6 required')
        frozen = freeze_runtime()
        for row in tool_records:
            frozen[row['path']] = row
        state.update(frozen_before=frozen, tools=tool_records,
                     cross_prefix=args.cross_prefix, vcs=args.vcs)
        save()
        steps = accept.acceptance_steps(out,args.cross_prefix,'vcs',False,False,
                                         soc.contract.PAIRED_HI_SCHEDULE,'-O2','both-unroll-no-masks')
        state['steps'] = [dict(name=n, command=c, timeout_seconds=t) for n,c,t in steps]
        save()
        actual = accept.execute_steps(steps,out,accept.VCS_SCOPE,'xu-s2e-paired-hi-vcs-full',
                                      ['chisel (unchanged source)', 'S0/PPA/energy qualification'],
                                      soc.contract.configuration(soc.contract.PAIRED_HI_SCHEDULE,'-O2','both-unroll-no-masks'))
        need(actual['status'] == 'PASS', 'complete VCS acceptance did not pass')
        baseline = json.loads((out/'baseline/result.json').read_text())
        need(baseline['tests'] == ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],
             'all five legacy VCS SoC tests required')
        direct = (out/'host-paired-hi-vcs/simulation.log').read_text()
        need(len(re.findall(r'^XU_PAIRED_HI_WRAPPER_PASS\b.*$',direct,re.M)) == 1 and
             not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b',direct,re.I), 'mandatory direct VCS result missing')
        paired = json.loads((out/'real12/result.json').read_text())
        control = json.loads((out/'autogroup-control-real12/result.json').read_text())
        rows, identical_fields = compare_real12(paired,control)
        with (out/'per-layer-comparison.csv').open('w',newline='') as stream:
            writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        ptotal, ctotal = sum(r['paired_cycles'] for r in rows), sum(r['control_cycles'] for r in rows)
        state.update(status='EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED',
                     paired_real12_cycles=ptotal, control_real12_cycles=ctotal,
                     delta_cycles=ptotal-ctotal, identical_fields=identical_fields,
                     readback_cycle_winner='paired-hi' if ptotal<ctotal else 'old-autogroup' if ptotal>ctotal else 'equal',
                     retention='PENDING_S0_PPA_ENERGY')
    except Exception as error:
        state.update(status='FAIL',error=str(error))
    finally:
        if frozen is not None:
            after = {p:(identity(p) if Path(p).is_file() and not Path(p).is_symlink() else None) for p in frozen}
            state['frozen_after'] = after
            if after != frozen:
                state.update(status='FAIL', integrity_error='frozen runtime inputs changed')
        state['finished_epoch'] = time.time()
        state['raw_files'] = {str(p.relative_to(out)):identity(p) for p in sorted(out.rglob('*'))
                              if p.is_file() and not p.is_symlink() and p.name!='state.json'}
        save()
    print('XU_S2E_VCS_DONE ' + state['status'],flush=True)
    return 0 if state['status']=='EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED' else 1


if __name__ == '__main__':
    sys.exit(main())
