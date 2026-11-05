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
import types

import e203_soc as soc
import server_accept as accept

E203_COMMIT = 'a0767db69628ef30e53de2d1e93dd0360c0ccf76'
BASE_MAIN = 'd276b55ffecbe8d620f9a361bf5d0859299ba7b5'
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


def identity(path, allowed_root=None):
    path = Path(path).absolute()
    if path.is_symlink():
        # Upstream env/pm/link.ld is a committed symlink. Freeze both its
        # literal link and resolved body; never replace it or silently skip it.
        link = os.readlink(str(path))
        target = path.resolve(strict=True)
        need(allowed_root is not None, 'runtime symlink requires a controlled root: ' + str(path))
        allowed_root = Path(allowed_root).resolve(strict=True)
        need(target == allowed_root or allowed_root in target.parents,
             'runtime symlink escapes controlled root: ' + str(path))
        need(target.is_file(), 'runtime symlink target is not a file: ' + str(path))
        return dict(path=str(path), kind='symlink', git_mode='120000', link_text=link,
                    filesystem_mode=oct(path.lstat().st_mode & 0o7777),
                    allowed_root=str(allowed_root),
                    link_sha256=hashlib.sha256(link.encode('utf-8')).hexdigest(),
                    target=identity(target))
    need(path.is_file(), 'regular runtime input missing: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest(),
                filesystem_mode=oct(path.stat().st_mode & 0o7777))


def freeze_runtime():
    records = {}
    # make install copies these directories without consulting .gitignore.
    # An ignored or newly added HDL/header could otherwise enter the wildcard
    # simulator file list while remaining outside the tracked-file freeze.
    unexpected = command(['git','ls-files','--others','-z','--','rtl/','tb/'], soc.E203)
    need(not unexpected, 'untracked E203 runtime input: ' + unexpected.replace('\0', ', '))
    for repo, prefixes in [(soc.ROOT, ('src/', 'tests/e203/', 'tests/numeric/', 'tools/scripts/',
                                     'tools/model/', 'model/', 'docs/server-handoff.md',
                                     'docs/validation/xu-performance-20261102/observed-receipt.json')),
                            (soc.E203, ('rtl/', 'vsim/', 'tb/', 'riscv-tools/riscv-tests/env/',
                                        'riscv-tools/riscv-tests/isa/generated/rv32ui-p-add'))]:
        paths = command(['git','ls-files','-z'], repo).split('\0')
        for relative in paths:
            if relative and relative.startswith(prefixes):
                path = repo / relative
                records[str(path)] = identity(path, repo)
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


def verify_legacy_images(out, prefix):
    """Build every old schedule/profile using its original and current sources."""
    out.mkdir(parents=True, exist_ok=False)
    oldtests = out/'frozen-tests'
    (oldtests/'firmware').mkdir(parents=True)
    for name in ['accel.c','accel.h','start.S','main.c','link.ld']:
        data = subprocess.check_output(['git','show',BASE_MAIN+':tests/e203/firmware/'+name],
                                       cwd=str(soc.ROOT))
        (oldtests/'firmware'/name).write_bytes(data)
    oldcode = subprocess.check_output(['git','show',BASE_MAIN+':tools/scripts/xu_firmware_contract.py'],
                                      cwd=str(soc.ROOT))
    (out/'frozen-contract.py').write_bytes(oldcode)
    oldcontract = types.ModuleType('xu_s2e_frozen_contract')
    exec(compile(oldcode, str(out/'frozen-contract.py'), 'exec'), oldcontract.__dict__)
    need(len(oldcontract.SCHEDULES)==8 and len(oldcontract.OPTIMIZATIONS)==3 and
         len(oldcontract.EXPERIMENTS)==8, 'unexpected original firmware configuration domain')
    newtests, newcontract = soc.TESTS, soc.contract
    records = []
    try:
        for schedule in oldcontract.SCHEDULES:
            for optimization in oldcontract.OPTIMIZATIONS:
                for experiment in oldcontract.EXPERIMENTS:
                    config = dict(schedule=schedule, optimization=optimization, experiment=experiment)
                    need(oldcontract.compiler_defines(config)==newcontract.compiler_defines(config),
                         'legacy compiler definitions changed: '+str(config))
                    pair = []
                    name = schedule+'-'+optimization[1:]+'-'+experiment
                    for kind, tests, contract in [('frozen',oldtests,oldcontract),
                                                   ('new',newtests,newcontract)]:
                        destination = out/name/kind
                        destination.mkdir(parents=True)
                        soc.TESTS, soc.contract = tests, contract
                        soc.compile_firmware(destination,prefix,schedule,optimization,experiment)
                        pair.append(dict(kind=kind, image=identity(destination/'accel_soc.verilog')))
                    need(pair[0]['image']['sha256']==pair[1]['image']['sha256'],
                         'legacy firmware load image changed: '+str(config))
                    records.append(dict(configuration=config, images=pair, equal=True))
    finally:
        soc.TESTS, soc.contract = newtests, newcontract
    result = dict(status='PASS', original_main=BASE_MAIN, configurations=len(records),
                  cross_prefix=prefix, scope='Exact RV32 load-image equality, all 8 old schedules x 3 optimizations x 8 experiments; not execution of every legacy configuration',
                  records=records)
    write_json(out/'image-equality.json', result)
    return result


def finalize(out, state, frozen):
    """Persist a terminal failure even if individual evidence files are unreadable."""
    if frozen is not None:
        if 'source_input_paths' in state:
            try:
                current = freeze_runtime()
                need(sorted(current) == state['source_input_paths'], 'runtime source inventory changed')
            except BaseException as error:
                state.update(status='FAIL', runtime_inventory_error=type(error).__name__ + ': ' + str(error))
        after = {}
        for p, before in frozen.items():
            try:
                after[p] = identity(p, before.get('allowed_root'))
            except BaseException as error:
                after[p] = dict(identity_error=type(error).__name__ + ': ' + str(error))
        state['frozen_after'] = after
        if after != frozen:
            state.update(status='FAIL', integrity_error='frozen runtime inputs changed or unreadable')
    raw, errors = {}, []
    try:
        paths = sorted(out.rglob('*'))
    except BaseException as error:
        paths = []
        errors.append(dict(path=str(out), error=type(error).__name__ + ': ' + str(error)))
    for p in paths:
        try:
            if p.is_file() and not p.is_symlink() and p.name != 'state.json':
                raw[str(p.relative_to(out))] = identity(p)
        except BaseException as error:
            errors.append(dict(path=str(p), error=type(error).__name__ + ': ' + str(error)))
    state['raw_files'] = raw
    if errors:
        state.update(status='FAIL', raw_identity_errors=errors)
    # No interrupted or incomplete campaign may retain its initial RUNNING state.
    if state['status'] == 'RUNNING_NOT_QUALIFIED':
        state.update(status='FAIL', error='campaign ended without an acceptance result')
    state['finished_epoch'] = time.time()
    write_json(out/'state.json', state)


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
        state['source_input_paths'] = sorted(frozen)
        for row in tool_records:
            frozen[row['path']] = row
        state.update(frozen_before=frozen, tools=tool_records,
                     cross_prefix=args.cross_prefix, vcs=args.vcs)
        save()
        state['legacy_images'] = verify_legacy_images(out/'legacy-images',args.cross_prefix)
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
    except BaseException as error:
        state.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
    finally:
        finalize(out, state, frozen)
    print('XU_S2E_VCS_DONE ' + state['status'],flush=True)
    return 0 if state['status']=='EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED' else 1


if __name__ == '__main__':
    sys.exit(main())
