#!/usr/bin/env python3
"""xu compact-W32: frozen VCS development acceptance, designated macro checks and full12 controls."""
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
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
parser.add_argument('--previous-source', required=True, type=Path)
parser.add_argument('--ramsp128-model', required=True, type=Path)
parser.add_argument('--cross-prefix', required=True)
parser.add_argument('--prepare-only', action='store_true')
args = parser.parse_args()
source, out = args.source.resolve(), args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
state = dict(status='STARTED', steps=[], source=str(source),
             scope='VCS development full12 with generated memories; actual designated128 single-bank/wide/compat directed tests; no mapped/STA/area/fullSoC-energy claim')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save():
    state['updated_utc'] = datetime.now(timezone.utc).isoformat()
    (out / 'state.json').write_text(json.dumps(state, indent=2) + '\n')


def run(argv, cwd, logfile, timeout=10800):
    argv = [str(value) for value in argv]
    with logfile.open('w') as stream:
        stream.write(json.dumps(dict(argv=argv, cwd=str(cwd))) + '\n')
        stream.flush()
        result = subprocess.run(argv, cwd=str(cwd), env=dict(os.environ, PWD=str(cwd)),
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    require(result.returncode == 0, 'exit ' + str(result.returncode) + ': ' + str(logfile))
    return logfile.read_text(errors='replace').split('\n', 1)[1]


def git(argv, cwd):
    return subprocess.check_output(['git'] + argv, cwd=str(cwd), universal_newlines=True).strip()


try:
    for name, record in json.loads((HERE / 'package-files.json').read_text()).items():
        require((HERE / name).stat().st_size == record['bytes'] and sha(HERE / name) == record['sha256'],
                'package identity differs: ' + name)
    identity = json.loads((HERE / 'source-identity.json').read_text())
    main, child_commit, branch = [identity[key] for key in ('main_commit', 'e203_commit', 'branch')]
    require(not source.exists(), 'source must be a new directory')
    previous = args.previous_source.resolve()
    require(previous.is_dir(), 'incremental prerequisite source missing')
    run(['git', 'clone', '--no-hardlinks', previous, source], HERE, out / 'main-clone.log', 300)
    run(['git', 'fetch', HERE / 'xu-bank128-main.bundle', branch], source, out / 'main-fetch.log', 300)
    run(['git', 'checkout', '--detach', main], source, out / 'main-checkout.log', 120)
    child = source / 'third-party/e203_hbirdv2'
    child.rmdir()
    run(['git', 'clone', '--no-hardlinks', previous / 'third-party/e203_hbirdv2', child], source, out / 'child-clone.log', 300)
    run(['git', 'fetch', HERE / 'xu-bank128-child.bundle', branch], child, out / 'child-fetch.log', 300)
    run(['git', 'checkout', '--detach', child_commit], child, out / 'child-checkout.log', 120)
    frozen = json.loads((HERE / 'source-files.json').read_text())

    def verify_sources():
        require(git(['rev-parse', 'HEAD'], source) == main and git(['rev-parse', 'HEAD'], child) == child_commit,
                'commit identity differs')
        require(git(['ls-tree', 'HEAD', 'third-party/e203_hbirdv2'], source).split()[2] == child_commit,
                'gitlink differs')
        require(not git(['status', '--porcelain'], source) and not git(['status', '--porcelain'], child),
                'dirty source checkout')
        current = set()
        for directory, prefix in [(source, ''), (child, 'third-party/e203_hbirdv2/')]:
            for line in git(['ls-files', '-s'], directory).splitlines():
                metadata, name = line.split('\t')
                if metadata.split()[0] != '160000':
                    current.add(prefix + name)
        require(current == set(frozen), 'tracked source path set differs')
        for name, record in frozen.items():
            path = source / name
            if record['git_mode'] == '120000':
                require(path.is_symlink() and os.readlink(path) == record['link_target'], 'source link differs: ' + name)
                data = os.readlink(path).encode()
            else:
                require(path.is_file() and not path.is_symlink(), 'source is not regular: ' + name)
                require(bool(path.stat().st_mode & 0o111) == (record['git_mode'] == '100755'), 'source mode differs: ' + name)
                data = path.read_bytes()
            require(len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'],
                    'source bytes differ: ' + name)

    verify_sources()
    state.update(status='PREPARED', main_commit=main, e203_commit=child_commit, verified_source_paths=len(frozen))
    save()
    if args.prepare_only:
        print('PREPARED ' + str(source), flush=True)
        sys.exit(0)

    model = args.ramsp128_model
    require(model.is_file() and not model.is_symlink(), 'regular actual RAMSP128X16 model required')
    model = model.resolve()
    model_record = dict(path=str(model), bytes=model.stat().st_size, sha256=sha(model))
    state['designated_ramsp128_model'] = model_record
    tools = ['git', 'make', 'vcs', 'gcc', 'g++', args.cross_prefix+'gcc', args.cross_prefix+'objcopy', args.cross_prefix+'objdump']
    state['tools'] = {name: shutil.which(name) for name in tools}
    require(all(state['tools'].values()), 'required tool missing')
    require(run([args.cross_prefix+'gcc', '--version'], source, out/'gcc-version.log', 60).splitlines()[0] ==
            'riscv64-unknown-elf-gcc (SiFive GCC-Metal 10.2.0-2020.12.8) 10.2.0', 'wrong GCC toolchain')
    require('Q-2020.03' in run(['vcs', '-ID'], source, out/'vcs-version.log', 60), 'wrong VCS version')
    os.environ['XU_PE32_BANK128_MACRO_MODEL'] = str(model)
    os.environ['XU_PE32_BANK128_WRAPPER_SIM'] = 'vcs'
    os.environ['XU_PE32_BANK128_WRAPPER_LOG_DIR'] = str(out/'direct-bank128-vcs')
    sys.path.insert(0, str(source/'tools/scripts'))
    import e203_soc as soc
    import server_accept as accept
    schedule = 'bias-hw-pe32-autogroup-window'
    variant = 'pe32-bank128'

    state.update(status='RUNNING', stage='direct-bank128-vcs')
    save()
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/e203', '-p', 'test_pe32_bank128*.py', '-v'],
        source, out/'direct-bank128-vcs.log', 3000)
    require(re.search(r'Ran 7 tests in [^\n]+\n\nOK\s*$', (out/'direct-bank128-vcs.log').read_text()),
            'mandatory direct tests incomplete or skipped')
    direct_records = {}
    for kind, marker in [('bank-generated', 'XU_PE32_BANK128_PASS'),
                         ('bank-designated-macro', 'XU_PE32_BANK128_PASS'),
                         ('wide', 'XU_PE32_WRAPPER_PASS'), ('compat', 'XU_PE32_COMPAT_WRAPPER_PASS'),
                         ('wide-designated-macro', 'XU_PE32_WRAPPER_PASS'),
                         ('compat-designated-macro', 'XU_PE32_COMPAT_WRAPPER_PASS')]:
        directory = out/'direct-bank128-vcs'/kind
        metadata = json.loads((directory/'compile.log').read_text().split('\n', 1)[0])
        text = (directory/'simulation.log').read_text().split('\n', 1)[1]
        require(metadata['argv'][0] == 'vcs' and text.count(marker) == 1 and
                not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text), 'direct actual VCS completion differs: '+kind)
        if 'designated-macro' in kind:
            require(metadata['designated_model']['sha256'] == model_record['sha256'] and
                    metadata['designated_model']['path'] == str(model), 'actual SRAM model identity differs')
            require('+define+ARM_UD_MODEL' in metadata['argv'] and
                    str(model) in metadata['argv'] and not any(value.endswith('/mem_128x16.sv') for value in metadata['argv']),
                    'designated path used behavioral shadow memory')
        direct_records[kind] = {path.name:sha(path) for path in directory.glob('*.log')}
    state['direct_vcs'] = direct_records
    save()

    def checked_result(directory, config, tasks, physical):
        report = json.loads((directory/'result.json').read_text())
        text = (directory/'simulation.log').read_text().split('\n', 1)[1]
        layers = soc.check_log(text, tasks)
        for layer, performance in zip(layers, soc.check_performance(text, layers, config, physical)):
            layer['performance'] = performance
        require(report['status'] == 'PASS' and report['tasks'] == tasks and report['layers'] == layers and
                report['main_commit'] == main and report['e203_commit'] == child_commit and
                report['accel_variant'] == physical and report['firmware_schedule'] == config and
                report['simulator'] == 'vcs' and report['firmware_opt'] == '-O2' and
                report['firmware_experiment'] == 'both-unroll-no-masks', 'run identity or complete counters differ')
        require(report['pe_activity'] == soc.check_pe_activity(text, layers, config, physical) and
                report['autogroup_activity'] == soc.check_autogroup_activity(text, layers, config), 'PE/FIFO work differs')
        for name, digest in report['source_sha256'].items():
            prefix = 'third-party/e203_hbirdv2/vsim/install/rtl/'
            path = child/'rtl/e203'/name[len(prefix):] if name.startswith(prefix) else source/name
            require(sha(path) == digest, 'measured source differs: '+name)
        require(sha(source/'tools/scripts/e203_soc.py') == report['runner_sha256'] and
                sha(source/'tools/scripts/xu_firmware_contract.py') == report['contract_sha256'], 'runner/contract differs')
        for name, digest in report['firmware_sha256'].items():
            require(sha(source/'tests/e203/firmware'/name) == digest, 'firmware source differs')
        for name, digest in report['log_sha256'].items():
            require(sha(directory/name) == digest, 'measured log differs: '+name)
        require(sha(directory/'accel_soc') == report['firmware_elf_sha256'] and
                sha(directory/'accel_soc.verilog') == report['firmware_image_sha256'], 'ELF/image differs')
        return report

    acceptance = out/'acceptance'
    acceptance.mkdir()
    steps = accept.acceptance_steps(acceptance, args.cross_prefix, 'vcs', False, False,
                                   schedule, '-O2', 'both-unroll-no-masks', variant)
    require(len(steps) == 8 and 'XU_PE32_BANK128_WRAPPER_SIM=vcs' in steps[0][1] and
            'XU_PE32_WRAPPER_SIM=vcs' in steps[0][1] and 'XU_WRAPPER_SIM=vcs' in steps[0][1], 'mandatory host paths missing')
    for name, command, timeout in steps:
        record = dict(name=name, argv=[str(value) for value in command], status='RUNNING')
        state['steps'].append(record)
        state['stage'] = name
        save()
        print('Starting '+name, flush=True)
        text = run(command, source, acceptance/(name+'.log'), timeout)
        if name == 'host':
            match = re.search(r'Ran 69 tests in [^\n]+\n\nOK(?: \(skipped=(\d+)\))?\s*$', text)
            require(match, 'host69 completion missing')
            record.update(tests=69, skipped=int(match.group(1) or 0),
                          required_actual_vcs=['cached-wrapper', 'pe32-wide', 'pe32-compat',
                              'bank128-generated-single-bank', 'bank128-designated-single-bank',
                              'bank128-generated-wide', 'bank128-generated-compat',
                              'bank128-designated-wide', 'bank128-designated-compat'])
        if name == 'numeric':
            require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$', text), 'numeric42 incomplete')
        if name in ('vectors', 'doctor', 'baseline'):
            report = json.loads((acceptance/name/'result.json').read_text())
            require(report['status'] == 'PASS' and report['main_commit'] == main and
                    report['accel_variant'] == variant and report['firmware_schedule'] == schedule, 'preflight identity differs')
            if name != 'vectors':
                require(report['e203_commit'] == child_commit, 'preflight child differs')
            if name == 'vectors':
                require(report['outputs'] == 304128 and len(report['layers']) == 12, 'vector12 incomplete')
            if name == 'baseline':
                require(report['tests'] == ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'], 'actual legacy5 incomplete')
        if name in ('synthetic1', 'synthetic2', 'real12'):
            report = checked_result(acceptance/name, schedule, {'synthetic1':1,'synthetic2':2,'real12':12}[name], variant)
            record['total_cycles'] = sum(layer['cycles'] for layer in report['layers'])
        record['status'] = 'PASS'
        save()

    controls = {}
    for name, physical, config in [('old32-wide-real12', 'pe32', schedule),
                                    ('bank128-oldauto-real12', variant, 'bias-hw-autogroup-window')]:
        directory = acceptance/name
        command = [sys.executable, source/'tools/scripts/e203_soc.py', '--mode', 'real', '--tasks', '12', '--sim', 'vcs',
                   '--cross-prefix', args.cross_prefix, '--out', directory, '--accel-variant', physical,
                   '--firmware-schedule', config, '--firmware-opt=-O2', '--firmware-experiment', 'both-unroll-no-masks']
        record = dict(name=name, argv=[str(value) for value in command], status='RUNNING')
        state['steps'].append(record)
        state['stage'] = name
        save()
        run(command, source, acceptance/(name+'.log'))
        controls[name] = checked_result(directory, config, 12, physical)
        record.update(status='PASS', total_cycles=sum(layer['cycles'] for layer in controls[name]['layers']))
        save()
    wide = checked_result(acceptance/'real12', schedule, 12, variant)
    common = ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools',
              'vectors','fixture','firmware_sha256','firmware_opt','firmware_experiment']
    for key in common:
        require(wide[key] == controls['old32-wide-real12'][key] == controls['bank128-oldauto-real12'][key],
                'full12 common identity differs: '+key)
    require(wide['simulator_sha256'] == controls['bank128-oldauto-real12']['simulator_sha256'] and
            wide['simulator_sha256'] != controls['old32-wide-real12']['simulator_sha256'], 'physical simulator identity differs')
    require(wide['firmware_image_sha256'] == controls['old32-wide-real12']['firmware_image_sha256'], 'same-wide firmware image differs')
    rows = [dict(layer=compact['layer'], bank128_wide_cycles=compact['cycles'], old32_wide_cycles=original['cycles'],
                 bank128_oldauto_cycles=legacy['cycles'])
            for compact, original, legacy in zip(wide['layers'], controls['old32-wide-real12']['layers'], controls['bank128-oldauto-real12']['layers'])]
    totals = {key:sum(row[key] for row in rows) for key in ('bank128_wide_cycles','old32_wide_cycles','bank128_oldauto_cycles')}
    comparison = dict(status='VCS_ACCEPTED_NOT_RETAINED', scope=state['scope'], rows=rows, totals=totals,
                      common_identity=common, designated_model=model_record,
                      result_sha256={name:sha(acceptance/name/'result.json') for name in ('real12','old32-wide-real12','bank128-oldauto-real12')})
    (out/'full12-comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
    verify_sources()
    require(model.stat().st_size == model_record['bytes'] and sha(model) == model_record['sha256'], 'designated model changed during campaign')
    state.update(status='VCS_ACCEPTED_NOT_RETAINED', acceptance_status='PASS',
                 not_run=['candidate formal-clear/request activity','mapped consistency','complete150MHz STA',
                          'same-library area','fullSoC task energy','retention'])
    (acceptance/'acceptance.json').write_text(json.dumps(state, indent=2)+'\n')
except Exception as error:
    if state['steps'] and state['steps'][-1]['status'] == 'RUNNING':
        state['steps'][-1]['status'] = 'FAIL'
    state.update(status='FAIL', error=str(error))
    save()
    (out/'failure.json').write_text(json.dumps(state, indent=2)+'\n')
    print('FAIL '+str(error), flush=True)
    sys.exit(1)
save()
print('XU_BANK128_DONE VCS_ACCEPTED_NOT_RETAINED '+str(out), flush=True)
