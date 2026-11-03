#!/usr/bin/env python3
"""Read-only recheck of actual local baseline/S2b/S2c evidence and negatives."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/scripts'))
import e203_soc as soc
import xu_perf_report as perf


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


manifest = json.loads((HERE / 'sha256.json').read_text())
for filename, digest in manifest.items():
    require(sha(HERE / filename) == digest, 'archived evidence changed: ' + filename)

with tarfile.open(HERE / 'raw/simulator.tar.xz') as archive:
    require(archive.getnames() == ['accel_soc'], 'simulator archive members differ')
    simulator_sha = hashlib.sha256(archive.extractfile('accel_soc').read()).hexdigest()
fixture = json.loads((ROOT / 'tests/e203/vectors/kwt-silence-v1.json').read_text())
require(sha(ROOT / 'tests/e203/vectors/kwt-silence-v1.tar.gz') == fixture['archive_sha256'],
        'original fixture archive changed')
variants = {}
for name, schedule in [('oldabi', 'bias-hw-window'), ('packed', 'bias-hw-pack32-window'),
                       ('autogroup', 'bias-hw-autogroup-window')]:
    directory = HERE / 'raw' / (name + '-real1')
    result = json.loads((directory / 'result.json').read_text())
    require(result['status'] == 'PASS' and result['mode'] == 'real' and result['tasks'] == 1,
            'not actual passing real1: ' + name)
    require(result['firmware_schedule'] == schedule, 'wrong schedule')
    log = (directory / 'simulation.log').read_text().split('\n', 1)[1]
    layers = soc.check_log(log, 1)
    counters = soc.check_performance(log, layers, schedule)
    require(counters == [result['layers'][0]['performance']], 'result/log counters differ')
    require(layers == [{k: v for k, v in result['layers'][0].items() if k != 'performance'}],
            'result/log completion differs')
    if name == 'autogroup':
        require(soc.check_autogroup_activity(log, layers, schedule) == result['autogroup_activity'],
                'result/log autonomous retirements differ')
    perf.summarize(result, 150)
    with tempfile.TemporaryDirectory(prefix='s2c-vector-check-') as temporary:
        dest = Path(temporary)
        with tarfile.open(directory / 'vectors.tar.xz') as archive:
            expected = {'layer_00/' + n + '.mem' for n in ['x', 'w', 'bias', 'y']}
            require({m.name for m in archive.getmembers() if m.isfile()} == expected,
                    'unexpected archived vector members')
            for member in expected:
                path = dest / member
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
        checked = soc.check_vectors(dest, 1)
    hashes = {'layer_00/' + n: h for n, h in checked[0]['sha256'].items()}
    require(hashes == result['vectors'] and result['fixture'] == fixture,
            'actual vectors differ from report')
    require(all(fixture['files'][n] == h for n, h in hashes.items()), 'fixture tensors differ')
    for path, digest in result['source_sha256'].items():
        require(sha(ROOT / path) == digest, 'measured RTL/TB changed: ' + path)
    require(sha(ROOT / 'tools/scripts/e203_soc.py') == result['runner_sha256'], 'runner changed')
    require(sha(ROOT / 'tools/scripts/xu_firmware_contract.py') == result['contract_sha256'],
            'transaction contract changed')
    for n, digest in result['firmware_sha256'].items():
        require(sha(ROOT / 'tests/e203/firmware' / n) == digest, 'firmware source changed')
    require(json.loads((directory / 'firmware-build.json').read_text()) == result['firmware_build'],
            'firmware build metadata differs')
    for filename, digest in result['log_sha256'].items():
        require(sha(directory / filename) == digest, 'measured log changed: ' + filename)
    require(sha(directory / 'accel_soc') == result['firmware_elf_sha256'] ==
            result['firmware_build']['elf_sha256'], 'actual ELF changed')
    require(sha(directory / 'accel_soc.verilog') == result['firmware_image_sha256'] ==
            result['firmware_build']['image_sha256'], 'actual loadable image changed')
    require(simulator_sha == result['simulator_sha256'], 'actual simulator changed')
    variants[name] = result

same = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256',
        'versions', 'tools', 'vectors', 'fixture', 'firmware_sha256', 'simulator_sha256',
        'firmware_opt', 'firmware_experiment']
for field in same:
    require(len({json.dumps(r[field], sort_keys=True) for r in variants.values()}) == 1,
            'common screen identity differs: ' + field)

compat = json.loads((HERE / 'rtl-compatibility.json').read_text())
for name, row in compat['default_files'].items():
    path = ROOT / 'third-party/e203_hbirdv2/rtl/e203/perips' / name
    require(sha(path) == row['sha256'] and row['unchanged'], 'old generated RTL changed')
require(len(compat['default_files']) == 12, 'not all original generated files checked')
require(sha(ROOT / 'third-party/e203_hbirdv2/rtl/e203/perips/LinearAutoGroupCore.sv') ==
        compat['new_top_sha256'], 'generated autonomous top changed')
images = json.loads((HERE / 'firmware-image-compatibility.json').read_text())
require(len(images['comparisons']) == 14, 'legacy image matrix incomplete')
with tarfile.open(HERE / 'legacy-firmware-images.tar.xz') as archive:
    for row in images['comparisons']:
        case = row['schedule'] + row['optimization'] + row['experiment']
        entries = [archive.extractfile('s2c-legacy-image-check/' + v + '-' + case +
                                      '/accel_soc.verilog').read() for v in ['s2b', 's2c']]
        require(entries[0] == entries[1] and hashlib.sha256(entries[1]).hexdigest() ==
                row['image_sha256'] and row['identical'], 'legacy image bytes differ')

baseline = HERE / 'raw/legacy-baseline'
base = json.loads((baseline / 'result.json').read_text())
require(base['status'] == 'PASS' and base['tests'] ==
        ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x'],
        'legacy full-SoC checks incomplete')
for n, digest in base['log_sha256'].items():
    require(sha(baseline / n) == digest, 'legacy log changed')

source = variants['autogroup']
for field in ['mmio_writes', 'shared_reads', 'shared_writes', 'starts', 'dones', 'mac_fire']:
    for delta in [-1, 1]:
        bad = copy.deepcopy(source)
        bad['layers'][0]['performance'][field] += delta
        try:
            perf.summarize(bad, 150)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted corrupt actual counter: ' + field)
log = (HERE / 'raw/autogroup-real1/simulation.log').read_text().split('\n', 1)[1]
for prefix in ['PERF_TASK', 'TASK_PASS', 'AUTO_TASK', 'SOC_PASS']:
    line = next(n for n in log.splitlines() if n.startswith(prefix + ' '))
    for bad in [log.replace(line + '\n', ''), log + line + '\n']:
        try:
            layers = soc.check_log(bad, 1)
            soc.check_performance(bad, layers, 'bias-hw-autogroup-window')
        except ValueError:
            pass
        else:
            raise AssertionError('accepted missing/duplicate actual log record: ' + prefix)
for bad in [log.replace('pops_retired=3168', 'pops_retired=3167'),
            re.sub(r'compute_writeback_overlap=\d+', 'compute_writeback_overlap=0', log),
            log + 'FATAL: injected negative\n']:
    try:
        layers = soc.check_log(bad, 1)
        soc.check_performance(bad, layers, 'bias-hw-autogroup-window')
    except ValueError:
        pass
    else:
        raise AssertionError('accepted corrupt actual autonomous activity')
print('PASS: actual three-way real1 identity, all outputs, retired FIFO, 12 RTL/14 image compatibility, negatives')
