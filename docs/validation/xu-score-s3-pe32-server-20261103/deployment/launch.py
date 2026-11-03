#!/usr/bin/env python3
"""xu: frozen single-W32 VCS development acceptance and physical-variant controls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
IDENTITY = json.loads((HERE / 'source-identity.json').read_text())
MAIN, CHILD, BRANCH = [IDENTITY[k] for k in ('main_commit', 'e203_commit', 'branch')]
SCHEDULE = 'bias-hw-pe32-autogroup-window'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
parser.add_argument('--cross-prefix', default='/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')
parser.add_argument('--previous-source', type=Path, default=Path.home() / 'Desktop/xu-score-optimization-20261102/ChipContest-s2c-02')
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
if sys.version_info < (3, 6): parser.error('Python3.6 or newer required')
source, out = args.source.resolve(), args.out.resolve()


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value: raise ValueError(message)


def run(argv, cwd, logfile, timeout=10800):
    with logfile.open('w') as stream:
        stream.write(json.dumps(dict(argv=[str(x) for x in argv], cwd=str(cwd))) + '\n'); stream.flush()
        result = subprocess.run([str(x) for x in argv], cwd=str(cwd), env=dict(os.environ, PWD=str(cwd)),
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    require(result.returncode == 0, 'exit ' + str(result.returncode) + ': ' + str(logfile))
    return logfile.read_text(errors='replace').split('\n', 1)[1]


def git(argv, cwd):
    return subprocess.check_output(['git'] + argv, cwd=str(cwd), universal_newlines=True).strip()


def save():
    state['updated_utc'] = datetime.now(timezone.utc).isoformat()
    (out / 'state.json').write_text(json.dumps(state, indent=2) + '\n')


out.mkdir(parents=True, exist_ok=False)
state = dict(status='STARTED', main_commit=MAIN, e203_commit=CHILD, source=str(source), steps=[], direct_vcs={},
             scope='VCS development acceptance and physical-variant controls; no S0/area/power/retention claim')
try:
    files = json.loads((HERE / 'package-files.json').read_text())
    for name, record in files.items():
        require((HERE / name).stat().st_size == record['bytes'] and sha(HERE / name) == record['sha256'],
                'package file identity differs: ' + name)
    require(not source.exists(), 'source directory must be new')
    previous = args.previous_source.resolve()
    require(previous.is_dir(), 'incremental prerequisite checkout missing')
    run(['git', 'clone', '--no-hardlinks', previous, source], HERE, out / 'main-clone.log', 300)
    run(['git', 'fetch', HERE / 'xu-pe32-main.bundle', BRANCH], source, out / 'main-fetch.log', 300)
    run(['git', 'checkout', '--detach', MAIN], source, out / 'main-checkout.log', 120)
    child = source / 'third-party/e203_hbirdv2'; child.rmdir()
    run(['git', 'clone', '--no-hardlinks', previous / 'third-party/e203_hbirdv2', child], source, out / 'child-clone.log', 300)
    run(['git', 'fetch', HERE / 'xu-pe32-child.bundle', BRANCH], child, out / 'child-fetch.log', 300)
    run(['git', 'checkout', '--detach', CHILD], child, out / 'child-checkout.log', 120)
    require(git(['rev-parse', 'HEAD'], source) == MAIN and git(['rev-parse', 'HEAD'], child) == CHILD, 'commit identity differs')
    require(git(['ls-tree', 'HEAD', 'third-party/e203_hbirdv2'], source).split()[2] == CHILD, 'gitlink differs')
    frozen = json.loads((HERE / 'source-files.json').read_text())

    def verify_sources():
        for name, digest in frozen.items(): require(sha(source / name) == digest, 'source identity differs: ' + name)
        require(not git(['status', '--porcelain'], source) and not git(['status', '--porcelain'], child), 'dirty source checkout')

    verify_sources()
    state.update(status='PREPARED', verified_source_paths=len(frozen)); save()
    if args.prepare_only:
        print('PREPARED ' + str(source), flush=True); sys.exit(0)
    tools = ['git', 'make', 'vcs', 'gcc', 'g++', args.cross_prefix + 'gcc', args.cross_prefix + 'objcopy', args.cross_prefix + 'objdump']
    state['tools'] = {name: shutil.which(name) for name in tools}
    require(all(state['tools'].values()), 'required tool missing')
    gcc = run([args.cross_prefix + 'gcc', '--version'], source, out / 'sifive-version.log', 60)
    require(gcc.splitlines()[0] == 'riscv64-unknown-elf-gcc (SiFive GCC-Metal 10.2.0-2020.12.8) 10.2.0', 'wrong SiFive GCC')
    require('Q-2020.03' in run(['vcs', '-ID'], source, out / 'vcs-version.log', 60), 'wrong VCS version')
    sys.path.insert(0, str(source / 'tools/scripts'))
    import e203_soc as soc
    import server_accept as accept

    # Both directed tests explicitly select actual VCS and the new wrapper itself.
    direct = out / 'direct-pe32-vcs'
    state.update(status='RUNNING', stage='direct-pe32-vcs'); save()
    command = ['env', 'XU_PE32_WRAPPER_SIM=vcs', 'XU_PE32_WRAPPER_LOG_DIR=' + str(direct),
               sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/e203', '-p', 'test_pe32_wrapper.py', '-v']
    run(command, source, out / 'direct-pe32-vcs.log', 1500)
    for kind, prefix, expected in [('wide', 'XU_PE32_WRAPPER_PASS', [16, 27, 27, 11124, 11124]),
                                   ('compat', 'XU_PE32_COMPAT_WRAPPER_PASS', [64, 99, 99, 11737, 11737])]:
        text = (direct / kind / 'simulation.log').read_text().split('\n', 1)[1]
        matches = re.findall(prefix + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)', text)
        require(len(matches) == 1, 'direct completion missing/duplicate: ' + kind)
        values = list(map(int, matches[0]))
        require(values[1] > 0 and [values[0]] + values[2:] == expected, 'direct work/retirement differs: ' + kind)
        require('"vcs"' in (direct / kind / 'compile.log').read_text().split('\n', 1)[0], 'direct backend differs')
        require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text), 'direct failure marker')
        state['direct_vcs'][kind] = dict(status='PASS', backend='vcs', counts=values,
            logs={p.name:sha(p) for p in (direct / kind).glob('*.log')})
    save()

    def checked_result(directory, schedule, tasks, variant):
        report = json.loads((directory / 'result.json').read_text())
        text = (directory / 'simulation.log').read_text().split('\n', 1)[1]
        layers = soc.check_log(text, tasks)
        for layer, performance in zip(layers, soc.check_performance(text, layers, schedule, variant)):
            layer['performance'] = performance
        require(report['status'] == 'PASS' and report['tasks'] == tasks and report['layers'] == layers and
                report['main_commit'] == MAIN and report['e203_commit'] == CHILD and
                report['accel_variant'] == variant and report['firmware_schedule'] == schedule and
                report['simulator'] == 'vcs', 'run identity or complete counters differ')
        require(report['firmware_opt'] == '-O2' and report['firmware_experiment'] == 'both-unroll-no-masks', 'firmware flags differ')
        require(report.get('pe_activity') == soc.check_pe_activity(text, layers, schedule, variant), 'physical MAC activity differs')
        require(report.get('autogroup_activity') == soc.check_autogroup_activity(text, layers, schedule), 'row/FIFO/POP activity differs')
        for name, digest in report['source_sha256'].items():
            prefix = 'third-party/e203_hbirdv2/vsim/install/rtl/'
            path = child / 'rtl/e203' / name[len(prefix):] if name.startswith(prefix) else source / name
            require(sha(path) == digest, 'measured source differs: ' + name)
        require(sha(source / 'tools/scripts/e203_soc.py') == report['runner_sha256'] and
                sha(source / 'tools/scripts/xu_firmware_contract.py') == report['contract_sha256'], 'runner/contract differs')
        for name, digest in report['firmware_sha256'].items(): require(sha(source / 'tests/e203/firmware' / name) == digest, 'firmware source differs')
        for name, digest in report['log_sha256'].items(): require(sha(directory / name) == digest, 'measured log differs: ' + name)
        require(sha(directory / 'accel_soc') == report['firmware_elf_sha256'] and sha(directory / 'accel_soc.verilog') == report['firmware_image_sha256'], 'ELF/image differs')
        return report

    acceptance = out / 'acceptance'; acceptance.mkdir()
    steps = accept.acceptance_steps(acceptance, args.cross_prefix, 'vcs', False, False, SCHEDULE, '-O2', 'both-unroll-no-masks', 'pe32')
    require(len(steps) == 8 and 'XU_WRAPPER_SIM=vcs' in steps[0][1] and 'XU_PE32_WRAPPER_SIM=vcs' in steps[0][1], 'mandatory host VCS selections missing')
    for name, command, timeout in steps:
        record = dict(name=name, argv=command, status='RUNNING'); state['steps'].append(record)
        state['stage'] = name; save(); print('Starting ' + name, flush=True)
        text = run(command, source, acceptance / (name + '.log'), timeout)
        if name == 'host':
            match = re.search(r'Ran (\d+) tests in [^\n]+\n\nOK(?: \(skipped=(\d+)\))?\s*$', text)
            require(match and int(match.group(1)) == 62, 'host62 completion missing')
            record.update(tests=62, skipped=int(match.group(2) or 0), required_actual_vcs=['cached-wrapper', 'pe32-wide', 'pe32-compat'],
                          optional_icarus_helpers='packed/stream/autogroup may skip when Icarus unavailable; their new-wrapper paths covered by mandatory wide/compat VCS')
        if name == 'numeric': require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$', text), 'numeric42 completion missing')
        if name in ('vectors', 'doctor', 'baseline'):
            report = json.loads((acceptance / name / 'result.json').read_text())
            require(report['status'] == 'PASS' and report['main_commit'] == MAIN and report['accel_variant'] == 'pe32' and report['firmware_schedule'] == SCHEDULE, 'preflight/baseline identity differs')
            if name != 'vectors': require(report['e203_commit'] == CHILD, 'preflight child differs')
            if name == 'vectors': require(report['outputs'] == 304128 and len(report['layers']) == 12, 'vector12 incomplete')
            if name == 'baseline': require(report['tests'] == ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'], 'legacy5 incomplete')
        if name in ('synthetic1', 'synthetic2', 'real12'):
            report = checked_result(acceptance / name, SCHEDULE, {'synthetic1':1,'synthetic2':2,'real12':12}[name], 'pe32')
            record['total_cycles'] = sum(layer['cycles'] for layer in report['layers'])
        record['status'] = 'PASS'; save()

    controls = {}
    for variant in ('pe32', 'pe8'):
        name = variant + '-autogroup-control-real12'; directory = acceptance / name
        command = [sys.executable, source / 'tools/scripts/e203_soc.py', '--mode','real','--tasks','12','--sim','vcs',
                   '--cross-prefix',args.cross_prefix,'--out',directory,'--accel-variant',variant,
                   '--firmware-schedule','bias-hw-autogroup-window','--firmware-opt=-O2','--firmware-experiment','both-unroll-no-masks']
        record = dict(name=name, argv=[str(x) for x in command], status='RUNNING'); state['steps'].append(record)
        state['stage'] = name; save(); print('Starting ' + name, flush=True)
        run(command, source, acceptance / (name + '.log'))
        controls[variant] = checked_result(directory, 'bias-hw-autogroup-window', 12, variant)
        record.update(status='PASS', total_cycles=sum(layer['cycles'] for layer in controls[variant]['layers'])); save()
    wide = checked_result(acceptance / 'real12', SCHEDULE, 12, 'pe32')
    common = ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture','firmware_sha256','firmware_opt','firmware_experiment']
    for key in common:
        require(wide[key] == controls['pe32'][key] == controls['pe8'][key], 'three-way common identity differs: ' + key)
    require(wide['simulator_sha256'] == controls['pe32']['simulator_sha256'], '32PE controls must use identical simulator binary')
    require(wide['simulator_sha256'] != controls['pe8']['simulator_sha256'], '8PE control must use distinct physical architecture binary')
    rows = [dict(layer=w['layer'], pe32_wide_cycles=w['cycles'], pe32_auto_cycles=a['cycles'], pe8_auto_cycles=b['cycles'])
            for w, a, b in zip(wide['layers'], controls['pe32']['layers'], controls['pe8']['layers'])]
    totals = {key:sum(row[key] for row in rows) for key in ('pe32_wide_cycles','pe32_auto_cycles','pe8_auto_cycles')}
    comparison = dict(status='PASS', scope=state['scope'], identities_identical=common, rows=rows, totals=totals,
                      same_pe32_simulator_sha256=wide['simulator_sha256'], pe8_simulator_sha256=controls['pe8']['simulator_sha256'],
                      wide_reduction_vs_pe32_auto_percent=100.0*(totals['pe32_auto_cycles']-totals['pe32_wide_cycles'])/totals['pe32_auto_cycles'],
                      result_sha256={name:sha(acceptance / name / 'result.json') for name in ['real12','pe32-autogroup-control-real12','pe8-autogroup-control-real12']})
    (out / 'full12-comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    verify_sources()
    state.update(status='VCS_ACCEPTED_NOT_RETAINED', acceptance_status='PASS',
                 not_run=['candidate formal-clear/request activity','mapped consistency','complete150MHz STA','same-library area','fullSoC energy','retention'])
    (acceptance / 'acceptance.json').write_text(json.dumps(state,indent=2)+'\n')
except Exception as error:
    if state['steps'] and state['steps'][-1]['status'] == 'RUNNING': state['steps'][-1]['status'] = 'FAIL'
    state.update(status='FAIL', error=str(error)); save()
    (out / 'failure.json').write_text(json.dumps(state,indent=2)+'\n')
    print('FAIL ' + str(error),flush=True); sys.exit(1)
save(); print('S3_PE32_DONE VCS_ACCEPTED_NOT_RETAINED ' + str(out),flush=True)
