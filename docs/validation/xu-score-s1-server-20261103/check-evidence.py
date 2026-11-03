#!/usr/bin/env python3
"""Read-only replay of retrieved S1 evidence; optional derived JSON output."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import types

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'tests/e203/vectors/kwt-silence-v1.tar.gz').is_file())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path)
args = parser.parse_args()


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def read_json(path):
    return json.loads(path.read_text())


raw = HERE / 'raw'
package = raw / 's1-acceptance-evidence-23.tar.xz'
require(package.stat().st_size == 23644 and sha(package) ==
        '96824ca873915a9c1bcb27d407c6dcd1e03d4d3ae6b94f7dbc8ef5a5cd2e3e5f', 'retrieved archive differs')
with tarfile.open(package, 'r:xz') as archive:
    members = archive.getmembers()
    require(all(m.isfile() for m in members), 'export contains non-file member')
    require(len({m.name for m in members}) == len(members) == 55, 'export member count differs')
    manifest = json.loads(archive.extractfile('manifest.json').read())
    require(len(manifest) == len({row['path'] for row in manifest}) == 54, 'manifest count differs')
    require({m.name for m in members} == {'manifest.json'} | {row['path'] for row in manifest},
            'export members differ from manifest')
    for row in manifest:
        data = archive.extractfile(row['path']).read()
        require(len(data) == row['bytes'] and digest(data) == row['sha256'], 'export SHA differs')
        require((raw / 'server-export' / row['path']).read_bytes() == data, 'raw copy differs')
    require((raw / 'server-export/manifest.json').read_bytes() == archive.extractfile('manifest.json').read(),
            'manifest raw copy differs')

source_audit = read_json(HERE / 'git-source-audit.json')
fixture = read_json(ROOT / 'tests/e203/vectors/kwt-silence-v1.json')
require(sha(ROOT / 'tests/e203/vectors/kwt-silence-v1.tar.gz') == fixture['archive_sha256'],
        'fixed fixture archive differs')
variants, checkers, negatives = {}, {}, []
expected_steps = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']

for name, schedule, host_count in [('h2', 'bias-dtcm-window', 49), ('sram', 'bias-hw-window', 50)]:
    directory = raw / 'server-export' / ('s1-' + name + '-accept-01')
    state = read_json(directory / 'state.json')
    acceptance = read_json(directory / 'acceptance/acceptance.json')
    require(state['status'] == 'VCS_ACCEPTED_NOT_RETAINED' and acceptance['status'] == 'PASS',
            'acceptance did not complete')
    require(sha(directory / 'acceptance/acceptance.json') == state['acceptance_sha256'], 'acceptance hash differs')
    require([s['name'] for s in acceptance['steps']] == expected_steps
            and all(s['status'] == 'PASS' for s in acceptance['steps']), 'eight acceptance steps incomplete')
    require([s['command'] for s in state['steps']] == [s['command'] for s in acceptance['steps']],
            'recorded commands differ')
    for step in acceptance['steps'][2:]:
        command = step['command']
        require(command[command.index('--firmware-schedule') + 1] == schedule
                and '--firmware-opt=-O2' in command
                and command[command.index('--firmware-experiment') + 1] == 'both-unroll-no-masks',
                'acceptance firmware configuration differs')
        if name == 'sram':
            require(command[command.index('--bias-storage') + 1] == 'sram', 'SRAM flag missing')
    for log_name, count in [('host', host_count), ('numeric', 42)]:
        log = (directory / 'acceptance' / (log_name + '.log')).read_text()
        require(re.search(r'Ran ' + str(count) + r' tests in [^\n]+\n\nOK\s*$', log),
                'unittest completion differs: ' + log_name)

    with tarfile.open(HERE / 'frozen-git-sources' / (name + '.tar.xz'), 'r:xz') as archive:
        snapshot = {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
    require(set(snapshot) == set(source_audit[name]['members_sha256']), 'frozen source member set differs')
    require(all(digest(data) == source_audit[name]['members_sha256'][path] for path, data in snapshot.items()),
            'frozen Git source SHA differs')
    contract = types.ModuleType('xu_firmware_contract')
    exec(compile(snapshot['tools/scripts/xu_firmware_contract.py'], '<frozen-contract>', 'exec'), contract.__dict__)
    sys.modules['xu_firmware_contract'] = contract
    soc = types.ModuleType('xu_s1_frozen_' + name)
    soc.__file__ = str(ROOT / 'tools/scripts/e203_soc.py')
    exec(compile(snapshot['tools/scripts/e203_soc.py'], '<frozen-' + name + '-runner>', 'exec'), soc.__dict__)
    checkers[name] = soc
    real = None
    declared_missing_logs = {}
    for mode, tasks in [('synthetic1', 1), ('synthetic2', 2), ('real12', 12)]:
        run_dir = directory / 'acceptance' / mode
        run = read_json(run_dir / 'result.json')
        require(run['status'] == 'PASS' and run['tasks'] == tasks and run['simulator'] == 'vcs',
                'run incomplete')
        require(run['main_commit'] == state['candidate']['main'] == source_audit[name]['main_commit']
                and run['e203_commit'] == state['candidate']['child'] == source_audit[name]['e203_commit'],
                'candidate commit identity differs')
        require(run['firmware_schedule'] == schedule and run['firmware_opt'] == '-O2'
                and run['firmware_experiment'] == 'both-unroll-no-masks', 'run firmware configuration differs')
        require(digest(snapshot['tools/scripts/e203_soc.py']) == run['runner_sha256']
                and digest(snapshot['tools/scripts/xu_firmware_contract.py']) == run['contract_sha256'],
                'measured checker source identity differs')
        require(all(digest(snapshot[path]) == value for path, value in run['source_sha256'].items()),
                'measured RTL/TB source identity differs')
        require(run['firmware_sha256'] == run['firmware_build']['source_sha256']
                and all(digest(snapshot['tests/e203/firmware/' + path]) == value
                        for path, value in run['firmware_sha256'].items()), 'firmware source identity differs')
        require(run['firmware_elf_sha256'] == run['firmware_build']['elf_sha256']
                and run['firmware_image_sha256'] == run['firmware_build']['image_sha256'],
                'recorded firmware binary identities differ')
        require(json.loads((run_dir / 'firmware-build.log').read_text().splitlines()[0])
                == run['firmware_build']['command'], 'actual firmware compiler command differs')
        missing = []
        for filename, value in run['log_sha256'].items():
            if (run_dir / filename).is_file():
                require(sha(run_dir / filename) == value, 'retrieved log SHA differs: ' + filename)
            else:
                missing.append(filename)
        declared_missing_logs[mode] = missing
        log = (run_dir / 'simulation.log').read_text().split('\n', 1)[1]
        layers = soc.check_log(log, tasks)
        counters = soc.check_performance(log, layers, schedule)
        for layer, counter in zip(layers, counters):
            layer['performance'] = counter
            if name == 'sram':
                layer['sram_bias_contract'] = soc.check_sram_bias_latency(counter, schedule)
            else:
                require(counter['busy'] == 215424, 'H2 fixed busy latency differs')
        require(layers == run['layers'], 'actual log/result layers differ')
        require(run['outputs'] == tasks * 25344 and run['write_words'] == tasks * 50688, 'run totals differ')
        if mode == 'real12':
            require(run['fixture'] == fixture and run['vectors'] == fixture['files'], 'real fixed vectors differ')
            real = run
        for case, bad in [('missing_TASK', re.sub(r'^TASK_PASS[^\n]*\n', '', log, count=1, flags=re.M)),
                          ('missing_PERF', re.sub(r'^PERF_TASK[^\n]*\n', '', log, count=1, flags=re.M)),
                          ('wrong_MMIO', log.replace('mmio_writes=' + str(counters[0]['mmio_writes']),
                                                     'mmio_writes=' + str(counters[0]['mmio_writes'] - 1), 1)),
                          ('wrong_MAC', log.replace('mac_fire=202752', 'mac_fire=202751', 1)),
                          ('missing_SOC', re.sub(r'^SOC_PASS[^\n]*\n', '', log, flags=re.M)),
                          ('appended_FATAL', log + '\nFATAL: negative\n')]:
            try:
                checked = soc.check_log(bad, tasks)
                soc.check_performance(bad, checked, schedule)
            except ValueError:
                negatives.append(name + '/' + mode + '/' + case)
            else:
                raise ValueError('accepted corrupt actual log: ' + case)
        if name == 'sram':
            corrupt = copy.deepcopy(counters[0]); corrupt['busy'] -= 1
            try:
                soc.check_sram_bias_latency(corrupt, schedule)
            except ValueError:
                negatives.append(name + '/' + mode + '/wrong_SRAM_busy')
            else:
                raise ValueError('accepted corrupt SRAM busy latency')
    baseline = read_json(directory / 'acceptance/baseline/result.json')
    require(baseline['status'] == 'PASS' and baseline['tests'] ==
            ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x'],
            'five baseline tests incomplete')
    variants[name] = dict(result=real, acceptance_steps=expected_steps, host_tests=host_count, numeric_tests=42,
                          missing_declared_logs=declared_missing_logs,
                          independently_rehashed_source_count=source_audit[name]['server_source_paths_verified'])

soc = checkers['h2']
with tempfile.TemporaryDirectory(prefix='xu-s1-fixed-vectors-') as temporary:
    soc.load_fixture(Path(temporary), 12)
    checked_vectors = soc.check_vectors(Path(temporary), 12)
require(sum(v['outputs'] for v in checked_vectors) == 304128, 'independent integer vector check incomplete')

base_dir = raw / 'baseline-reference4ns'
baseline = read_json(base_dir / 'result.json')
require(baseline['status'] == 'PASS' and baseline['clock_mode'] == 'reference4ns'
        and baseline['fixture'] == fixture and baseline['vectors'] == checked_vectors, 'baseline identity differs')
baseline_layers = None
for name in ['reference', 'macro']:
    result = read_json(base_dir / name / 'result.json')
    log = (base_dir / name / 'simulation.log').read_text().split('\n', 1)[1]
    layers = soc.check_log(log, 12)
    counters = soc.check_performance(log, layers, 'bias-hw-window')
    for layer, counter in zip(layers, counters):
        layer['performance'] = counter
    require(result['status'] == 'PASS' and layers == result['layers'], 'baseline actual layers differ')
    for filename, value in result['log_sha256'].items():
        if (base_dir / name / filename).is_file():
            require(sha(base_dir / name / filename) == value, 'baseline log SHA differs')
    require(baseline_layers is None or baseline_layers == layers, 'baseline reference/macro disagree')
    baseline_layers = layers
require(sum(layer['cycles'] for layer in baseline_layers) == 16510344, 'frozen baseline total differs')
for name, data in variants.items():
    run = data['result']
    gcc = next(key for key in run['versions'] if key.endswith('riscv64-unknown-elf-gcc'))
    require(run['versions'][gcc][0] == baseline['tool_versions'][gcc][0], 'GCC toolchain differs')
    require(run['versions']['vcs'][0] == baseline['tool_versions']['vcs'][0], 'VCS version differs')
require(variants['sram']['result']['firmware_sha256'] == baseline['firmware_sha256']
        and variants['sram']['result']['firmware_image_sha256'] == baseline['firmware_image_sha256'],
        'SRAM/baseline firmware image differs')

comparison = []
for index, base in enumerate(baseline_layers):
    row = dict(layer=index, baseline=base)
    for name, data in variants.items():
        candidate = data['result']['layers'][index]
        row[name] = candidate
        row[name + '_minus_baseline'] = dict(cycles=candidate['cycles'] - base['cycles'],
            performance={field: value - base['performance'][field]
                         for field, value in candidate['performance'].items()})
    comparison.append(row)
totals = dict(baseline=16510344, **{name: sum(layer['cycles'] for layer in data['result']['layers'])
                                 for name, data in variants.items()})
report = dict(status='VERIFIED_SERVER_VCS_DEVELOPMENT_ACCEPTANCE_ONLY', archive_sha256=sha(package),
    payload_files_verified=54, variants=variants, baseline_source=dict(main_commit=baseline['main_commit'],
    e203_commit=baseline['e203_commit'], clock_mode=baseline['clock_mode']), total_cycles=totals,
    delta_cycles={name: total - totals['baseline'] for name, total in totals.items() if name != 'baseline'},
    slowdown_percent={name: 100 * (total - totals['baseline']) / totals['baseline']
                      for name, total in totals.items() if name != 'baseline'},
    per_layer=comparison, rejected_corruptions=negatives,
    fixed_fixture_outputs_independently_recomputed=304128,
    limitations=['legacy development window; candidate-specific formal clear window not established',
                 'retrieval omits firmware/simulator binaries and material server vectors; their hashes remain recorded identities',
                 'source snapshots rehashed against original measured RTL/TB and Git commits at collection',
                 'no new simulation, qualified throughput, energy, area, retention or score result'])
if args.out:
    args.out.write_text(json.dumps(report, indent=2) + '\n')
print('PASS: 54 payload hashes; 6 actual candidate runs; 305 source identities; 12-layer baseline; '
      '304128 fixed outputs; ' + str(len(negatives)) + ' rejected corruptions')
