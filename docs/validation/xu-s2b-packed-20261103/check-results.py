#!/usr/bin/env python3
"""Recheck actual local old ABI/scalar/packed results and reject corrupt records."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / 'tools/scripts/xu_firmware_contract.py').is_file())
sys.path.insert(0, str(ROOT / 'tools/scripts'))
import e203_soc as soc
import xu_perf_report as perf

parser = argparse.ArgumentParser(description=__doc__)
HERE = Path(__file__).resolve().parent
for name, suffix in [('oldabi', 'oldabi'), ('scalar', 'scalar'), ('packed', 'packed')]:
    parser.add_argument('--' + name, type=Path, default=HERE / ('raw/' + suffix + '-real1'))
parser.add_argument('--simulator-archive', type=Path, default=HERE / 'raw/simulator.tar.xz')
parser.add_argument('--out', type=Path, help='optional derived report; default is a read-only check')
args = parser.parse_args()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


with tarfile.open(args.simulator_archive, 'r:xz') as archive:
    require(archive.getnames() == ['accel_soc'], 'unexpected simulator archive members')
    simulator_sha256 = hashlib.sha256(archive.extractfile('accel_soc').read()).hexdigest()

fixture = json.loads((ROOT / 'tests/e203/vectors/kwt-silence-v1.json').read_text())
require(sha(ROOT / 'tests/e203/vectors/kwt-silence-v1.tar.gz') == fixture['archive_sha256'],
        'fixture archive hash differs')


variants = {}
for name, schedule in [('oldabi', 'bias-hw-window'), ('scalar', 'bias-hw-stream16-window'),
                       ('packed', 'bias-hw-pack32-window')]:
    directory = getattr(args, name).resolve()
    source = json.loads((directory / 'result.json').read_text())
    require(source['status'] == 'PASS' and source['mode'] == 'real' and source['tasks'] == 1,
            'not a passing single real layer')
    require(source['firmware_schedule'] == schedule, 'wrong firmware schedule')
    log = (directory / 'simulation.log').read_text().split('\n', 1)[1]
    layers = soc.check_log(log, 1)
    counters = soc.check_performance(log, layers, schedule)
    require(counters == [source['layers'][0]['performance']], 'log/result counters differ')
    require(layers == [{k: v for k, v in source['layers'][0].items() if k != 'performance'}],
            'log/result task records differ')
    summary = perf.summarize(source, 150)
    with tempfile.TemporaryDirectory(prefix='xu-s2b-evidence-vectors-') as temporary:
        vector_directory = Path(temporary)
        with tarfile.open(directory / 'vectors.tar.xz', 'r:xz') as archive:
            expected = {'layer_00/' + name + '.mem' for name in ['x', 'w', 'bias', 'y']}
            require({member.name for member in archive.getmembers() if member.isfile()} == expected,
                    'unexpected vector archive members')
            for vector_name in expected:
                path = vector_directory / vector_name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(vector_name).read())
        vectors = soc.check_vectors(vector_directory, 1)
    require(vectors[0]['outputs'] == 25344, 'wrong vector output count')
    vector_hashes = {'layer_00/' + name: digest for name, digest in vectors[0]['sha256'].items()}
    require(vector_hashes == source['vectors'], 'actual/recorded vector hashes differ')
    require(source['fixture'] == fixture, 'fixture manifest differs')
    require(all(fixture['files'][name] == digest for name, digest in vector_hashes.items()),
            'vector hashes differ from fixture')
    for path, digest in source['source_sha256'].items():
        require(sha(ROOT / path) == digest, 'source hash differs: ' + path)
    require(sha(ROOT / 'tools/scripts/e203_soc.py') == source['runner_sha256'], 'runner hash differs')
    require(sha(ROOT / 'tools/scripts/xu_firmware_contract.py') == source['contract_sha256'],
            'contract hash differs')
    require(json.loads((directory / 'firmware-build.json').read_text()) == source['firmware_build'],
            'firmware build metadata differs')
    require(source['firmware_build']['source_sha256'] == source['firmware_sha256'],
            'firmware source metadata differs')
    for filename, digest in source['firmware_sha256'].items():
        require(sha(ROOT / 'tests/e203/firmware' / filename) == digest,
                'firmware source hash differs: ' + filename)
    for filename, digest in source['log_sha256'].items():
        require(sha(directory / filename) == digest, 'log hash differs: ' + filename)
    require(sha(directory / 'accel_soc') == source['firmware_elf_sha256'] == source['firmware_build']['elf_sha256'],
            'firmware ELF hash differs')
    require(sha(directory / 'accel_soc.verilog') == source['firmware_image_sha256'] == source['firmware_build']['image_sha256'],
            'firmware image hash differs')
    require(simulator_sha256 == source['simulator_sha256'], 'simulator binary hash differs')
    variants[name] = dict(source=source, summary=summary, directory=str(directory),
                          result_sha256=sha(directory / 'result.json'),
                          simulation_log_sha256=sha(directory / 'simulation.log'), vectors=vectors)

same = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256',
        'versions', 'tools', 'vectors', 'fixture', 'firmware_sha256', 'simulator_sha256',
        'firmware_opt', 'firmware_experiment']
for field in same:
    require(variants['oldabi']['source'][field] == variants['scalar']['source'][field] == variants['packed']['source'][field],
            'common identity differs: ' + field)

source = variants['packed']['source']
directory = Path(variants['packed']['directory'])
log = (directory / 'simulation.log').read_text().split('\n', 1)[1]
negative = []
for name, mutate in [
    ('one_missing_mmio_write', lambda d: d['layers'][0]['performance'].__setitem__('mmio_writes',21733)),
    ('one_extra_mmio_write', lambda d: d['layers'][0]['performance'].__setitem__('mmio_writes',21735)),
    ('phase_gap', lambda d: d['layers'][0]['performance'].__setitem__('other',d['layers'][0]['performance']['other']-1)),
    ('phase_overlap', lambda d: d['layers'][0]['performance'].__setitem__('other',d['layers'][0]['performance']['other']+1)),
    ('one_missing_mac_fire', lambda d: d['layers'][0]['performance'].__setitem__('mac_fire',202751)),
    ('one_extra_mac_fire', lambda d: d['layers'][0]['performance'].__setitem__('mac_fire',202753)),
    ('wrong_schedule', lambda d: d.__setitem__('firmware_schedule','bias-hw-stream16-window')),
    ('one_missing_output', lambda d: d.__setitem__('outputs',25343)),
    ('one_missing_y_word', lambda d: d.__setitem__('write_words',50687))]:
    bad = copy.deepcopy(source)
    mutate(bad)
    try:
        perf.summarize(bad, 150)
    except ValueError:
        negative.append(dict(case=name, rejected=True))
    else:
        raise AssertionError('accepted corrupt actual result: ' + name)
for field in ['shared_reads', 'shared_writes', 'starts', 'dones']:
    for delta in [-1, 1]:
        bad = copy.deepcopy(source)
        bad['layers'][0]['performance'][field] += delta
        try:
            perf.summarize(bad, 150)
        except ValueError:
            negative.append(dict(case=field + ('_missing_one' if delta == -1 else '_extra_one'), rejected=True))
        else:
            raise AssertionError('accepted corrupt actual counter: ' + field)
lines = log.splitlines()
for prefix, check in [('PERF_TASK', lambda x: soc.check_performance(x, soc.check_log(log,1), 'bias-hw-pack32-window')),
                      ('TASK_PASS', lambda x: soc.check_log(x,1))]:
    row = next(x for x in lines if x.startswith(prefix + ' '))
    for kind, bad in [('missing', '\n'.join(x for x in lines if x != row) + '\n'),
                      ('duplicate', log + row + '\n')]:
        try:
            check(bad)
        except ValueError:
            negative.append(dict(case=kind + '_' + prefix, rejected=True))
        else:
            raise AssertionError('accepted corrupt actual log: ' + kind + '_' + prefix)
perf_row = next(x for x in lines if x.startswith('PERF_TASK '))
soc_row = next(x for x in lines if x.startswith('SOC_PASS '))
for name, bad in [
    ('PERF_wrong_layer', log.replace(perf_row, perf_row.replace('layer=0', 'layer=1'))),
    ('PERF_wrong_cycles', log.replace(perf_row, perf_row.replace('cycles=1250899', 'cycles=1250900'))),
    ('PERF_missing_field', log.replace(perf_row, perf_row.replace(' mmio_stall=0', ''))),
    ('PERF_extra_field', log.replace(perf_row, perf_row + ' unexpected=0')),
    ('missing_SOC_PASS', log.replace(soc_row + '\n', '')),
    ('duplicate_SOC_PASS', log + soc_row + '\n'),
    ('SOC_wrong_totals', log.replace(soc_row, soc_row.replace('outputs=25344', 'outputs=25343'))),
    ('appended_FATAL', log + 'FATAL: injected negative\n')]:
    try:
        checked_layers = soc.check_log(bad, 1)
        soc.check_performance(bad, checked_layers, 'bias-hw-pack32-window')
    except ValueError:
        negative.append(dict(case=name, rejected=True))
    else:
        raise AssertionError('accepted corrupt actual log: ' + name)
rows = {name: dict(cycles=v['source']['layers'][0]['cycles'],
                   firmware_cycles=v['source']['layers'][0]['firmware_cycles'],
                   **v['source']['layers'][0]['performance']) for name, v in variants.items()}
comparisons = {}
for base in ['oldabi', 'scalar']:
    comparisons['packed_minus_' + base] = {k: rows['packed'][k] - rows[base][k] for k in rows[base]}
    comparisons['packed_cycle_reduction_percent_vs_' + base] = 100 * (rows[base]['cycles'] - rows['packed']['cycles']) / rows[base]['cycles']

baseline_directory = HERE / 'raw/legacy-baseline'
baseline = json.loads((baseline_directory / 'result.json').read_text())
legacy_tests = ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x']
require(baseline['status'] == 'PASS' and baseline['tests'] == legacy_tests, 'legacy baseline incomplete')
require(baseline['main_commit'] == source['main_commit'] and baseline['e203_commit'] == source['e203_commit'],
        'legacy baseline source identity differs')
for path, digest in baseline['source_sha256'].items():
    require(sha(ROOT / path) == digest, 'baseline source hash differs: ' + path)
for filename, digest in baseline['log_sha256'].items():
    require(sha(baseline_directory / filename) == digest, 'baseline log hash differs: ' + filename)
for name in legacy_tests:
    text = (baseline_directory / (name + '.log')).read_text()
    require('TEST_PASS' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', text),
            'legacy baseline failed: ' + name)

legacy_directory = HERE / 'raw/original-local'
legacy = json.loads((legacy_directory / 'legacy-firmware-load-image-equality.json').read_text())
require(legacy['status'] == 'PASS' and legacy['comparison_count'] == 12
        and len(legacy['comparisons']) == 12, 'legacy image comparison incomplete')
require(legacy['current_commit'] == source['main_commit'], 'legacy firmware measured source differs')
with tarfile.open(legacy_directory / 'legacy-firmware-load-image-equality.tar.xz', 'r:xz') as archive:
    for variant, dirname in [('HEAD', 'sources-head'), ('current', 'sources-current')]:
        for filename, digest in legacy['source_snapshots'][variant].items():
            member = 'legacy-firmware-load-image-equality/' + dirname + '/' + filename
            require(hashlib.sha256(archive.extractfile(member).read()).hexdigest() == digest,
                    'legacy source snapshot hash differs: ' + member)
    require(legacy['source_snapshots']['current'] == source['firmware_sha256'],
            'legacy comparison current firmware differs')
    for row in legacy['comparisons']:
        binaries = []
        defines = []
        for variant in ['HEAD', 'current']:
            record = row['images'][variant]
            member = 'legacy-firmware-load-image-equality/' + record['binary_path'].split('/legacy-firmware-load-image-equality/', 1)[1]
            binary = archive.extractfile(member).read()
            binaries.append(binary)
            defines.append([arg for arg in record['compiler_command'] if arg.startswith('-D')])
            require(hashlib.sha256(binary).hexdigest() == record['binary_sha256']
                    and len(binary) == record['binary_bytes'], 'legacy loadable image hash differs')
            require(hashlib.sha256(archive.extractfile(member[:-4] + '.elf').read()).hexdigest()
                    == record['elf_sha256'], 'legacy ELF hash differs')
        require(binaries[0] == binaries[1] and defines[0] == defines[1],
                'legacy loadable bytes or compiler defines differ')

result = dict(status='PASS', scope='same-toolchain local fixed layer_00 only; no qualification, PPA or retention claim',
              identities_identical=same, variants={n: {k: v for k,v in x.items() if k not in ['source','summary']}
                                                  for n,x in variants.items()},
              measured_source=dict(main_commit=source['main_commit'],e203_commit=source['e203_commit']),
              firmware_elf_sha256={n:x['source']['firmware_elf_sha256'] for n,x in variants.items()},
              firmware_image_sha256={n:x['source']['firmware_image_sha256'] for n,x in variants.items()},
              simulator_sha256=simulator_sha256, simulator_binary_rehashed=True,
              fixture_and_actual_vector_hashes_checked=True,
              firmware_source_build_elf_image_hashes_checked=True, rows=rows, comparisons=comparisons,
              legacy_baseline_tests=legacy_tests, legacy_loadable_image_comparisons=12,
              legacy_archived_source_elf_image_bytes_rehashed=True,
              negative_actual_record_checks=negative)
if args.out is not None:
    args.out.write_text(json.dumps(result, indent=2) + '\n')
print('PASS: 3 actual results, exact vectors/hashes, ' + str(len(negative)) + ' rejected corruptions'
      + ('; ' + str(args.out) if args.out is not None else '; read-only check'))
