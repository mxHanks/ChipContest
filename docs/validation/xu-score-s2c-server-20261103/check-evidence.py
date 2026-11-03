#!/usr/bin/env python3
"""Independently recheck immutable S2c server payload and frozen measured sources."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import tempfile
import types

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'tests/e203/vectors/kwt-silence-v1.tar.gz').is_file())
MAIN = 'd276b55ffecbe8d620f9a361bf5d0859299ba7b5'
CHILD = '49a9436e01ea8ceeead94242e4a99c16e31a0865'
AUTO = 'bias-hw-autogroup-window'
PACKED = 'bias-hw-pack32-window'
STEPS = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2',
         'real12', 'packed-control-real12']
LEGACY = ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x']


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def read(path):
    return json.loads(path.read_text())


def output(path):
    return path.read_text().split('\n', 1)[1]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, help='write derived verification JSON; raw files are read-only')
parser.add_argument('--csv', type=Path, help='write derived per-layer cycles and all work counters')
args = parser.parse_args()
original, selected = [read(HERE / name) for name in
                      ['original-export-manifest.json', 'selected-manifest.json']]
require(len(original) == len({row['path'] for row in original}) == 239, 'original manifest is not unique')
require(len(selected) == len({row['path'] for row in selected}) == 123, 'selected payload is not unique')
for row in selected:
    path = PurePosixPath(row['path'])
    require(not path.is_absolute() and '..' not in path.parts and
            [r for r in original if r['path'] == row['path']] == [row], 'selected manifest differs')
    actual = HERE / 'raw' / row['path']
    require(actual.stat().st_size == row['bytes'] and sha(actual) == row['sha256'],
            'original raw bytes differ: ' + row['path'])
require({p.relative_to(HERE / 'raw').as_posix() for p in (HERE / 'raw').rglob('*') if p.is_file()} ==
        {row['path'] for row in selected}, 'extra or missing raw file')

audit = read(HERE / 'git-source-audit.json')
require(audit['main_commit'] == MAIN and audit['e203_commit'] == CHILD, 'frozen commit differs')
with tarfile.open(HERE / 'frozen-git-sources.tar.xz', 'r:xz') as archive:
    members = archive.getmembers()
    require(len(members) == len({m.name for m in members}) and all(m.isfile() and
            not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts
            for m in members), 'unsafe/duplicate source archive member')
    snapshot = {m.name: archive.extractfile(m).read() for m in members}
require({p: digest(b) for p, b in snapshot.items()} == audit['source_sha256'], 'frozen source digest differs')

# Import the measured source bytes, not today's root implementation or another candidate.
contract = types.ModuleType('xu_firmware_contract')
exec(compile(snapshot['tools/scripts/xu_firmware_contract.py'], '<frozen-contract>', 'exec'), contract.__dict__)
sys.modules['xu_firmware_contract'] = contract
soc = types.ModuleType('xu_frozen_s2c_soc')
soc.__file__ = str(ROOT / 'tools/scripts/e203_soc.py')
exec(compile(snapshot['tools/scripts/e203_soc.py'], '<frozen-runner>', 'exec'), soc.__dict__)
fixture_path = ROOT / 'tests/e203/vectors/kwt-silence-v1.json'
require(fixture_path.read_bytes() == snapshot['tests/e203/vectors/kwt-silence-v1.json'], 'fixture manifest changed')
fixture = read(fixture_path)
require(sha(ROOT / 'tests/e203/vectors/kwt-silence-v1.tar.gz') == fixture['archive_sha256'], 'fixture archive changed')
with tempfile.TemporaryDirectory(prefix='xu-s2c-evidence-vectors-') as temporary:
    directory = Path(temporary)
    soc.load_fixture(directory, 12)
    vectors = soc.check_vectors(directory, 12)

raw = HERE / 'raw/s2c-accept-02'
state, acceptance = read(raw / 'state.json'), read(raw / 'acceptance/acceptance.json')
deploy = read(HERE / 'raw/s2c-deploy-20261103-02/state.json')
require(deploy['status'] == 'EXECUTED_REVIEW_PENDING' and deploy['returncode'] == 0, 'outer execution failed')
require(state['status'] == 'VCS_ACCEPTED_NOT_RETAINED' and state['acceptance_status'] == 'PASS' and
        state['main_commit'] == MAIN and state['e203_commit'] == CHILD and state['verified_source_paths'] == 2384,
        'final candidate state differs')
require(acceptance['status'] == 'PASS' and acceptance['steps'] == state['steps'] and
        [s['name'] for s in state['steps']] == STEPS and all(s['status'] == 'PASS' for s in state['steps']),
        'nine mandatory steps incomplete')
require(acceptance['firmware_configuration'] == contract.configuration(AUTO, '-O2', 'both-unroll-no-masks') and
        acceptance['direct_vcs'] == state['direct_vcs'] and acceptance['not_run'] == state['not_run'],
        'acceptance receipt differs')
for name in ['launch.py', 'README.md', 'source-files.json']:
    require(digest(snapshot['deployment/' + name]) == state['package_sha256'][name], 'deployment input differs')
require(len(json.loads(snapshot['deployment/source-files.json'])) == 2384, 'deployment source manifest incomplete')
for step in state['steps']:
    command = step['command']
    if step['name'] not in ['host', 'numeric']:
        schedule = PACKED if step['name'] == 'packed-control-real12' else AUTO
        require(command[command.index('--sim') + 1] == 'vcs' and
                command[command.index('--firmware-schedule') + 1] == schedule and
                '--firmware-opt=-O2' in command and
                command[command.index('--firmware-experiment') + 1] == 'both-unroll-no-masks',
                'actual command backend/configuration differs')
    require((raw / 'acceptance' / (step['name'] + '.log')).is_file(), 'missing step driver log')
host, numeric = output(raw / 'acceptance/host.log'), output(raw / 'acceptance/numeric.log')
require(re.search(r'Ran 57 tests in [^\n]+\n\nOK \(skipped=3\)\s*$', host) and
        state['steps'][0]['tests'] == 57 and state['steps'][0]['skipped'] == 3, 'host count/skips differ')
require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$', numeric), 'numeric42 completion missing')
require(state['steps'][0]['command'][:2] == ['env', 'XU_WRAPPER_SIM=vcs'], 'cached wrapper backend differs')
cached = output(raw / 'acceptance/host-wrapper-vcs/simulation.log')
require(len(re.findall(r'^XU_CACHED_WRAPPER_PASS accepted=4909 retired=4909$', cached, re.M)) == 1 and
        'Compiler version Q-2020.03-SP2-6_Full64' in cached and not re.search(r'FATAL|TEST_FAIL', cached),
        'actual cached VCS trace differs')

directs = {}
for kind in ['autogroup', 'packed', 'stream']:
    record = state['direct_vcs'][kind]
    directory = raw / ('direct-' + kind + '-vcs')
    require(record['status'] == 'PASS' and record['backend'] == 'vcs', 'direct VCS missing')
    for name, expected in record['log_sha256'].items():
        require(sha(directory / name) == expected, 'direct actual log digest differs')
    require(all(digest(snapshot[p]) == expected for p, expected in record['source_sha256'].items()),
            'direct measured source differs')
    compile_log, text = output(directory / 'compile.log'), output(directory / 'simulation.log')
    require('Compiler version Q-2020.03-SP2-6_Full64' in text and
            not re.search(r'Error-\[|^Error:|\b[1-9][0-9]* errors?\b', compile_log, re.M) and
            not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text, re.I), 'direct compile/simulation failed')
    if kind == 'autogroup':
        pattern = (r'^XU_AUTOGROUP_WRAPPER_PASS rows=(\d+) groups=(\d+) lanes=(\d+) overlap=(\d+) '
                   r'launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)$')
        expected = [2, 64, 512, 958, 99, 99, 11719, 11719]
    else:
        pattern = (r'^XU_' + kind.upper() + r'_WRAPPER_PASS accepted=(\d+) retired=(\d+) '
                   r'writes=(\d+) W=(\d+) X=(\d+) starts=(\d+)$')
        expected = [9653, 9653, 16457, 16390, 67, 33] if kind == 'packed' else [17828, 17828, 16454, 16387, 67, 33]
    found = re.findall(pattern, text, re.M)
    require(len(found) == 1 and list(map(int, found[0])) == expected == record['counts'], 'direct work differs')
    directs[kind] = dict(status='VERIFIED_ACTUAL_VCS_LOGS', counts=expected,
                        binary_identity='recorded SHA only; binary not retrieved')

initial = read(HERE / 'raw/s2c-accept-01/state.json')
failure = output(HERE / 'raw/s2c-accept-01/direct-autogroup-vcs/compile.log')
require(initial['status'] == 'FAIL' and initial['main_commit'] == '0d1f6e9f1b0b6efb2207f99fcef78597855eb5c0' and
        initial['e203_commit'] == 'dd149bb34aa1c3feca066ffbf9bdd3311f4b954c' and
        initial['stage'] == 'direct-autogroup-vcs' and initial['steps'] == [] and
        'command exit 255' in initial['error'] and len(re.findall(r'Error-\[IND\]', failure)) == 5 and
        re.search(r'^5 errors$', failure, re.M), 'initial real compile failure differs')
old, new = snapshot['initial-failed/accel_icb_slave.v'], snapshot['third-party/e203_hbirdv2/rtl/e203/perips/accel_icb_slave.v']
pattern = rb'    wire row_start_accept = cmd_valid && cmd_ready && !cmd_read &&\n(?:.*\n){3}'
before, after = re.search(pattern, old), re.search(pattern, new)
require(before and after and before.group() == after.group() and
        old.replace(before.group(), b'') == new.replace(after.group() + b'\n', b''),
        'declaration repair changed logic or unrelated bytes')

negatives = []


def reject_bad_log(name, log, tasks, schedule):
    try:
        checked = soc.check_log(log, tasks)
        soc.check_performance(log, checked, schedule)
    except ValueError:
        negatives.append(name)
    else:
        raise ValueError('accepted corrupt actual log: ' + name)


def check_run(name, schedule, tasks):
    directory = raw / 'acceptance' / name
    result = read(directory / 'result.json')
    require(result['status'] == 'PASS' and result['tasks'] == tasks and result['simulator'] == 'vcs' and
            result['main_commit'] == MAIN and result['e203_commit'] == CHILD, 'run identity/status differs')
    require(contract.configuration_from_result(result) == contract.configuration(schedule, '-O2', 'both-unroll-no-masks'),
            'run/build configuration differs')
    require(len(result['source_sha256']) == 152 and all(digest(snapshot[p]) == expected
            for p, expected in result['source_sha256'].items()), '152 measured sources differ')
    require(digest(snapshot['tools/scripts/e203_soc.py']) == result['runner_sha256'] and
            digest(snapshot['tools/scripts/xu_firmware_contract.py']) == result['contract_sha256'], 'checker identity differs')
    build = read(directory / 'firmware-build.json')
    require(build == result['firmware_build'] and result['firmware_sha256'] == build['source_sha256'] and
            all(digest(snapshot['tests/e203/firmware/' + p]) == value for p, value in result['firmware_sha256'].items()) and
            result['firmware_elf_sha256'] == build['elf_sha256'] and
            result['firmware_image_sha256'] == build['image_sha256'], 'firmware metadata disagrees')
    require(json.loads((directory / 'firmware-build.log').read_text().splitlines()[0]) == build['command'] and
            all(define in build['command'] for define in contract.compiler_defines(build['configuration'])),
            'actual compile invocation/configuration differs')
    for filename, expected in result['log_sha256'].items():
        require(sha(directory / filename) == expected, 'actual run log missing/changed: ' + name + '/' + filename)
    require(any(v[0] == 'riscv64-unknown-elf-gcc (SiFive GCC-Metal 10.2.0-2020.12.8) 10.2.0'
                for v in result['versions'].values()) and
            'Compiler version = VCS Q-2020.03-SP2-6_Full64' in result['versions']['vcs'], 'server toolchain differs')
    text = output(directory / 'simulation.log')
    layers = soc.check_log(text, tasks)
    counters = soc.check_performance(text, layers, schedule)
    for layer, counter in zip(layers, counters):
        layer['performance'] = counter
        require(counter['busy'] == 215424, '8PE fixed busy latency differs')
    require(layers == result['layers'] and result['outputs'] == tasks * 25344 and
            result['write_words'] == tasks * 50688, 'actual output/performance differs')
    if schedule == AUTO:
        require(soc.check_autogroup_activity(text, layers, schedule) == result['autogroup_activity'], 'FIFO activity differs')
    if name in ['real12', 'packed-control-real12']:
        require(result['fixture'] == fixture and result['vectors'] == fixture['files'], '48 fixed tensor identities differ')
    else:
        with tempfile.TemporaryDirectory(prefix='xu-s2c-synthetic-') as temporary:
            directory = Path(temporary)
            soc.synthetic(directory, tasks)
            require({str(p.relative_to(directory)):sha(p) for p in directory.rglob('*.mem')} == result['vectors'],
                    'synthetic vector generator identity differs')
    for prefix in ['TASK_PASS', 'PERF_TASK', 'SOC_PASS'] + (['AUTO_TASK'] if schedule == AUTO else []):
        line = next(s for s in text.splitlines() if s.startswith(prefix + ' '))
        reject_bad_log(name + '/missing_' + prefix, text.replace(line + '\n', '', 1), tasks, schedule)
        reject_bad_log(name + '/duplicate_' + prefix, text + line + '\n', tasks, schedule)
    for field in ['mmio_writes', 'shared_reads', 'shared_writes', 'mac_fire', 'starts', 'dones']:
        value = counters[0][field]
        reject_bad_log(name + '/wrong_' + field, text.replace(field + '=' + str(value), field + '=' + str(value - 1), 1), tasks, schedule)
    if schedule == AUTO:
        reject_bad_log(name + '/wrong_POP', text.replace('pops_retired=3168', 'pops_retired=3167', 1), tasks, schedule)
        reject_bad_log(name + '/zero_overlap', re.sub(r'compute_writeback_overlap=\d+', 'compute_writeback_overlap=0', text, count=1), tasks, schedule)
    reject_bad_log(name + '/FATAL', text + '\nFATAL: injected negative\n', tasks, schedule)
    return result


runs = {name:check_run(name, schedule, tasks) for name, schedule, tasks in
        [('synthetic1', AUTO, 1), ('synthetic2', AUTO, 2), ('real12', AUTO, 12), ('packed-control-real12', PACKED, 12)]}
for name in ['vectors', 'doctor', 'baseline']:
    directory = raw / 'acceptance' / name
    result = read(directory / 'result.json')
    require(result['status'] == 'PASS' and result['main_commit'] == MAIN and result['firmware_schedule'] == AUTO,
            'preflight/baseline incomplete')
    if name != 'vectors':
        require(result['e203_commit'] == CHILD, 'preflight/baseline child differs')
    for filename, expected in result['log_sha256'].items():
        require(sha(directory / filename) == expected, 'preflight/baseline actual log differs')
    if name == 'vectors':
        require(result['outputs'] == 304128 and result['layers'] == vectors and result['fixture'] == fixture,
                'independent full12 fixed arithmetic differs')
    if name == 'doctor':
        require(read(directory / 'firmware-build.json') == result['firmware_build'], 'doctor build metadata differs')
    if name == 'baseline':
        require(result['tests'] == LEGACY and len(result['source_sha256']) == 151 and
                all(digest(snapshot[p]) == value for p, value in result['source_sha256'].items()), 'legacy source/program set differs')
        for case in LEGACY:
            text = output(directory / (case + '.log'))
            require('TEST_PASS' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', text), 'legacy program failed')

auto, packed = runs['real12'], runs['packed-control-real12']
same = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256',
        'versions', 'tools', 'vectors', 'fixture', 'firmware_sha256', 'simulator_sha256', 'firmware_opt', 'firmware_experiment']
require(all(auto[field] == packed[field] for field in same), 'same-RTL full12 common identity differs')
comparison = read(raw / 'full12-comparison.json')
rows = [dict(layer=a['layer'], packed_cycles=p['cycles'], autogroup_cycles=a['cycles'],
             autogroup_minus_packed=a['cycles'] - p['cycles']) for a, p in zip(auto['layers'], packed['layers'])]
totals = dict(autogroup=sum(x['cycles'] for x in auto['layers']), packed=sum(x['cycles'] for x in packed['layers']))
require(totals == dict(autogroup=11842200, packed=14532449) and comparison['status'] == 'PASS' and
        comparison['rows'] == rows and comparison['identities_identical'] == same and
        comparison['autogroup_total_cycles'] == totals['autogroup'] and comparison['packed_total_cycles'] == totals['packed'] and
        comparison['autogroup_minus_packed'] == totals['autogroup'] - totals['packed'] and
        comparison['autogroup_cycle_reduction_percent'] == 100.0 * (totals['packed'] - totals['autogroup']) / totals['packed'] and
        comparison['auto_result_sha256'] == sha(raw / 'acceptance/real12/result.json') and
        comparison['packed_result_sha256'] == sha(raw / 'acceptance/packed-control-real12/result.json'), 'derived full12 comparison differs')
report = dict(status='VERIFIED_VCS_DEVELOPMENT_RESULTS_WITH_BINARY_RETRIEVAL_GAPS', main_commit=MAIN, e203_commit=CHILD,
              selected_unique_payloads=123, source_paths_verified=152, full_deployment_manifest_paths=2384,
              actual_server_steps=STEPS, host_tests=57, host_skips=3, numeric_tests=42, direct_vcs=directs,
              independently_recomputed_fixed_outputs=304128, total_cycles=totals, per_layer=rows,
              reduction_cycles=totals['packed']-totals['autogroup'],
              reduction_percent=comparison['autogroup_cycle_reduction_percent'], same_identity_fields=same,
              autogroup_activity=auto['autogroup_activity'], rejected_corruptions=negatives,
              initial_failed_main=initial['main_commit'], initial_failed_child=initial['e203_commit'],
              limitations=['actual server ELF/loadable images/simulator binaries/vectors not retrieved; SHA identities are recorded, not rehashed binaries',
                           'all declared run logs retrieved and rehashed; shared original fixture independently recomputed',
                           '4ns development TB and preloaded shared memory; candidate formal clear/request-window,150MHz mapped equivalence/STA and full-SoC energy still required',
                           'official600 accuracy and scoring/retention not established'])
report['layer_counters'] = dict(autogroup=auto['layers'], packed=packed['layers'])
report['aggregate_counters'] = {
    mode: {field: sum(layer['performance'][field] for layer in run['layers'])
           for field in run['layers'][0]['performance']}
    for mode, run in [('autogroup', auto), ('packed', packed)]}
report['source_changes'] = {
    'production_chisel': ['src/main/scala/GenerateRTL.scala',
                          'src/main/scala/linear/LinearAutoGroupCore.scala'],
    'test_chisel': ['src/test/scala/linear/LinearAutoGroupCoreTest.scala'],
    'initial_vcs_repair': 'identical row_start_accept initializer moved below its five input declarations; no logic/Chisel change'}
report['full12_result_sha256'] = {
    'autogroup': sha(raw / 'acceptance/real12/result.json'),
    'packed': sha(raw / 'acceptance/packed-control-real12/result.json')}
if args.out:
    args.out.write_text(json.dumps(report, indent=2) + '\n')
if args.csv:
    fields = ['cycles', 'firmware_cycles'] + list(auto['layers'][0]['performance'])
    flat = []
    for a, p, activity in zip(auto['layers'], packed['layers'], auto['autogroup_activity']):
        row = dict(layer=a['layer'], autogroup_minus_packed=a['cycles'] - p['cycles'])
        for mode, layer in [('packed', p), ('autogroup', a)]:
            row.update({mode + '_' + field: layer.get(field, layer['performance'].get(field))
                        for field in fields})
        row.update({'autogroup_' + key: value for key, value in activity.items() if key != 'layer'})
        flat.append(row)
    with args.csv.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
print('PASS: 123 unique raw payloads; 152 frozen measured sources; direct3 + steps9; 304128 fixed outputs; '
      + str(len(negatives)) + ' rejected corruptions; auto11842200/packed14532449; retrieval/qualification gaps retained')
