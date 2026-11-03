#!/usr/bin/env python3
"""xu: frozen single-W64 VCS development acceptance and physical-variant controls."""
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
SCHEDULE = 'bias-hw-pe64-autogroup-window'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
parser.add_argument('--cross-prefix', default='/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')
parser.add_argument('--previous-source', type=Path, default=Path.home() / 'Desktop/xu-score-optimization-20261102/ChipContest-s3-pe32-01')
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
if sys.version_info < (3, 6): parser.error('Python3.6 or newer required')
IDENTITY = json.loads((HERE / 'source-identity.json').read_text())
MAIN, CHILD = [IDENTITY[k] for k in ('main_commit', 'e203_commit')]
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
    run(['git', 'fetch', HERE / 'main.bundle', 'HEAD'], source, out / 'main-fetch.log', 300)
    run(['git', 'checkout', '--detach', MAIN], source, out / 'main-checkout.log', 120)
    child = source / 'third-party/e203_hbirdv2'; child.rmdir()
    run(['git', 'clone', '--no-hardlinks', previous / 'third-party/e203_hbirdv2', child], source, out / 'child-clone.log', 300)
    run(['git', 'fetch', HERE / 'child.bundle', 'HEAD'], child, out / 'child-fetch.log', 300)
    run(['git', 'checkout', '--detach', CHILD], child, out / 'child-checkout.log', 120)
    require(git(['rev-parse', 'HEAD'], source) == MAIN and git(['rev-parse', 'HEAD'], child) == CHILD, 'commit identity differs')
    require(git(['ls-tree', 'HEAD', 'third-party/e203_hbirdv2'], source).split()[2] == CHILD, 'gitlink differs')
    frozen = json.loads((HERE / 'source-files.json').read_text())

    def verify_sources():
        for label, repo, expected in [('main', source, MAIN), ('child', child, CHILD)]:
            require(git(['rev-parse', 'HEAD'], repo) == expected, 'checkout commit differs')
            records = frozen[label]['files']
            current = subprocess.check_output(['git', 'ls-files', '-s', '-z'], cwd=str(repo)).split(b'\0')
            entries = {}
            for entry in current:
                if not entry: continue
                meta, path = entry.split(b'\t', 1)
                mode, oid, stage = meta.decode().split()
                require(stage == '0', 'unmerged source index')
                entries[os.fsdecode(path)] = (mode, oid)
            require(set(entries) == {record['path'] for record in records}, 'tracked path inventory differs')
            for record in records:
                name, mode, oid = record['path'], record['mode'], record['git_oid']
                require(entries[name] == (mode, oid), 'tracked identity differs: ' + name)
                path = repo / name
                if mode == '160000':
                    require(oid == CHILD, 'nested gitlink differs'); continue
                if mode == '120000':
                    require(path.is_symlink(), 'symlink type differs: ' + name)
                    data = os.readlink(str(path)).encode()
                else:
                    require(path.is_file() and not path.is_symlink(), 'file type differs: ' + name)
                    require(bool(path.stat().st_mode & 0o100) == (mode == '100755'), 'file mode differs: ' + name)
                    data = path.read_bytes()
                require(len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'], 'source bytes differ: ' + name)
        require(not git(['status', '--porcelain'], source) and not git(['status', '--porcelain'], child), 'dirty source checkout')

    verify_sources()
    state.update(status='PREPARED', verified_source_paths=sum(len(value['files']) for value in frozen.values())); save()
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

    # All three modes explicitly select actual VCS and the physical64 wrapper.
    direct = out / 'direct-pe64-vcs'
    state.update(status='RUNNING', stage='direct-pe64-vcs'); save()
    command = ['env', 'XU_PE64_WRAPPER_SIM=vcs', 'XU_PE64_WRAPPER_LOG_DIR=' + str(direct),
               sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/e203', '-p', 'test_pe64_wrapper.py', '-v']
    run(command, source, out / 'direct-pe64-vcs.log', 2400)
    for kind, lanes, expected in [('wide64', 64, [8,15,15,11031,11031]),
                                  ('compat32', 32, [16,27,27,11131,11131]),
                                  ('compat8', 8, [64,99,99,11731,11731])]:
        text = (direct / kind / 'simulation.log').read_text().split('\n', 1)[1]
        matches = re.findall('XU_PE64_WRAPPER_PASS mode_lanes=' + str(lanes) + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)', text)
        require(len(matches) == 1, 'direct completion missing/duplicate: ' + kind)
        values = list(map(int, matches[0]))
        require(values[1] > 0 and [values[0]] + values[2:] == expected, 'direct work/retirement differs: ' + kind)
        require('"vcs"' in (direct / kind / 'compile.log').read_text().split('\n', 1)[0], 'direct backend differs')
        launches = expected[1]
        require(re.findall(r'XU_PE64_DIRECT_ACTIVITY physical_pes=64 mac_beats=(\d+) lane_macs=(\d+)', text) == [(str(launches*64), str(49664+128*lanes))], 'direct enabled-lane work differs')
        require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text), 'direct failure marker')
        state['direct_vcs'][kind] = dict(status='PASS', backend='vcs', counts=values,
            logs={p.name:sha(p) for p in (direct / kind).glob('*.log')})
    save()

    state['stage'] = 'direct-pe64-boundary-vcs'; save()
    boundary_command = ['env', 'XU_PE64_WRAPPER_SIM=vcs', 'XU_PE64_WRAPPER_LOG_DIR=' + str(direct),
                        sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/e203', '-p', 'test_pe64_boundaries.py', '-v']
    run(boundary_command, source, out / 'direct-pe64-boundary-vcs.log', 900)
    boundary_text = (direct / 'boundary/simulation.log').read_text().split('\n', 1)[1]
    require(re.findall(r'XU_PE64_BOUNDARY_PASS mode=(\d) unknown_reads=14 mode_error=1 pop_retired=1', boundary_text) == ['0', '1', '2'] and
            boundary_text.count('XU_PE64_BOUNDARIES_PASS modes=3') == 1, 'actual VCS boundary coverage incomplete')
    require('"vcs"' in (direct / 'boundary/compile.log').read_text().split('\n', 1)[0], 'boundary backend differs')
    state['direct_vcs']['boundary'] = dict(status='PASS', backend='vcs', modes=3, unknown_reads=42, mode_errors=3,
                                         logs={p.name:sha(p) for p in (direct / 'boundary').glob('*.log')})
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
    steps = accept.acceptance_steps(acceptance, args.cross_prefix, 'vcs', False, False, SCHEDULE, '-O2', 'both-unroll-no-masks', 'pe64')
    require(len(steps) == 8 and 'XU_WRAPPER_SIM=vcs' in steps[0][1] and 'XU_PE64_WRAPPER_SIM=vcs' in steps[0][1], 'mandatory host VCS selections missing')
    for name, command, timeout in steps:
        record = dict(name=name, argv=command, status='RUNNING'); state['steps'].append(record)
        state['stage'] = name; save(); print('Starting ' + name, flush=True)
        text = run(command, source, acceptance / (name + '.log'), timeout)
        if name == 'host':
            match = re.search(r'Ran (\d+) tests in [^\n]+\n\nOK(?: \(skipped=(\d+)\))?\s*$', text)
            require(match and int(match.group(1)) == 68, 'host68 completion missing')
            record.update(tests=68, skipped=int(match.group(2) or 0), required_actual_vcs=['cached-wrapper', 'pe64-wide64', 'pe64-compat32', 'pe64-compat8', 'pe64-boundaries'],
                          optional_icarus_helpers='packed/stream/autogroup may skip when Icarus unavailable; their physical64 paths covered by mandatory three-mode VCS')
        if name == 'numeric': require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$', text), 'numeric42 completion missing')
        if name in ('vectors', 'doctor', 'baseline'):
            report = json.loads((acceptance / name / 'result.json').read_text())
            require(report['status'] == 'PASS' and report['main_commit'] == MAIN and report['accel_variant'] == 'pe64' and report['firmware_schedule'] == SCHEDULE, 'preflight/baseline identity differs')
            if name != 'vectors': require(report['e203_commit'] == CHILD, 'preflight child differs')
            if name == 'vectors': require(report['outputs'] == 304128 and len(report['layers']) == 12, 'vector12 incomplete')
            if name == 'baseline':
                require(report['tests'] == ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'], 'legacy5 incomplete')
                for test in report['tests']:
                    legacy_text = (acceptance / name / (test + '.log')).read_text()
                    require('TEST_PASS' in legacy_text and 'XU_ACCEL_PE64=1' in legacy_text and
                            not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', legacy_text), 'actual physical64 legacy execution differs: ' + test)
                for logfile, digest in report['log_sha256'].items():
                    require(sha(acceptance / name / logfile) == digest, 'legacy log differs: ' + logfile)
        if name in ('synthetic1', 'synthetic2', 'real12'):
            report = checked_result(acceptance / name, SCHEDULE, {'synthetic1':1,'synthetic2':2,'real12':12}[name], 'pe64')
            record['total_cycles'] = sum(layer['cycles'] for layer in report['layers'])
        record['status'] = 'PASS'; save()

    controls = {}
    control_cases = [('same64-schedule32', 'pe64', 'bias-hw-pe32-autogroup-window'),
                     ('same64-schedule8', 'pe64', 'bias-hw-autogroup-window'),
                     ('physical32-wide32', 'pe32', 'bias-hw-pe32-autogroup-window'),
                     ('physical8-auto8', 'pe8', 'bias-hw-autogroup-window')]
    for label, variant, schedule in control_cases:
        name = label + '-control-real12'; directory = acceptance / name
        command = [sys.executable, source / 'tools/scripts/e203_soc.py', '--mode','real','--tasks','12','--sim','vcs',
                   '--cross-prefix',args.cross_prefix,'--out',directory,'--accel-variant',variant,
                   '--firmware-schedule',schedule,'--firmware-opt=-O2','--firmware-experiment','both-unroll-no-masks']
        record = dict(name=name, argv=[str(x) for x in command], status='RUNNING'); state['steps'].append(record)
        state['stage'] = name; save(); print('Starting ' + name, flush=True)
        run(command, source, acceptance / (name + '.log'))
        controls[label] = checked_result(directory, schedule, 12, variant)
        record.update(status='PASS', total_cycles=sum(layer['cycles'] for layer in controls[label]['layers'])); save()
    wide = checked_result(acceptance / 'real12', SCHEDULE, 12, 'pe64')
    common = ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture','firmware_sha256','firmware_opt','firmware_experiment']
    for key in common:
        require(all(wide[key] == value[key] for value in controls.values()), 'five-way common identity differs: ' + key)
    require(wide['simulator_sha256'] == controls['same64-schedule32']['simulator_sha256'] == controls['same64-schedule8']['simulator_sha256'], 'same physical64 binary differs')
    require(len({wide['simulator_sha256'], controls['physical32-wide32']['simulator_sha256'], controls['physical8-auto8']['simulator_sha256']}) == 3, 'physical variants share binary')
    require(controls['same64-schedule32']['layers'] == controls['physical32-wide32']['layers'], '32schedule compatibility PERF differs')
    require(controls['same64-schedule8']['layers'] == controls['physical8-auto8']['layers'], '8schedule compatibility PERF differs')
    rows = []
    for index, layer in enumerate(wide['layers']):
        row = dict(layer=layer['layer'], pe64_wide_cycles=layer['cycles'])
        for label, value in controls.items(): row[label + '_cycles'] = value['layers'][index]['cycles']
        rows.append(row)
    totals = {key:sum(row[key] for row in rows) for key in rows[0] if key != 'layer'}
    comparison = dict(status='PASS', scope=state['scope'], identities_identical=common, rows=rows, totals=totals,
                      same_pe64_simulator_sha256=wide['simulator_sha256'],
                      physical32_simulator_sha256=controls['physical32-wide32']['simulator_sha256'],
                      physical8_simulator_sha256=controls['physical8-auto8']['simulator_sha256'],
                      wide64_reduction_vs_same64_schedule32_percent=100.0*(totals['same64-schedule32_cycles']-totals['pe64_wide_cycles'])/totals['same64-schedule32_cycles'],
                      wide64_reduction_vs_same64_schedule8_percent=100.0*(totals['same64-schedule8_cycles']-totals['pe64_wide_cycles'])/totals['same64-schedule8_cycles'],
                      result_sha256={name:sha(acceptance / name / 'result.json') for name in ['real12']+[label+'-control-real12' for label,_,_ in control_cases]})
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
save(); print('S3_PE64_DONE VCS_ACCEPTED_NOT_RETAINED ' + str(out),flush=True)
