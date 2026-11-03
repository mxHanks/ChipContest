#!/usr/bin/env python3
"""Recheck actual local old ABI/scalar/packed results and reject corrupt records."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / 'tools/scripts/xu_firmware_contract.py').is_file())
sys.path.insert(0, str(ROOT / 'tools/scripts'))
import e203_soc as soc
import xu_perf_report as perf

parser = argparse.ArgumentParser(description=__doc__)
for name, suffix in [('oldabi', 'oldabi'), ('scalar', 'scalar'), ('packed', 'packed')]:
    parser.add_argument('--' + name, type=Path, default=ROOT / ('build/xu-s2b-' + suffix + '-real1'))
parser.add_argument('--out', type=Path, default=Path(__file__).with_name('comparison.json'))
args = parser.parse_args()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


variants = {}
for name, schedule in [('oldabi', 'bias-hw-window'), ('scalar', 'bias-hw-stream16-window'),
                       ('packed', 'bias-hw-pack32-window')]:
    directory = getattr(args, name).resolve()
    source = json.loads((directory / 'result.json').read_text())
    assert source['status'] == 'PASS' and source['mode'] == 'real' and source['tasks'] == 1
    assert source['firmware_schedule'] == schedule
    log = (directory / 'simulation.log').read_text().split('\n', 1)[1]
    layers = soc.check_log(log, 1)
    counters = soc.check_performance(log, layers, schedule)
    assert counters == [source['layers'][0]['performance']]
    assert layers == [{k: v for k, v in source['layers'][0].items() if k != 'performance'}]
    summary = perf.summarize(source, 150)
    vectors = soc.check_vectors(directory / 'vectors', 1)
    assert vectors[0]['outputs'] == 25344
    for path, digest in source['source_sha256'].items():
        assert sha(ROOT / path) == digest, path
    assert sha(ROOT / 'tools/scripts/e203_soc.py') == source['runner_sha256']
    assert sha(ROOT / 'tools/scripts/xu_firmware_contract.py') == source['contract_sha256']
    for filename, digest in source['log_sha256'].items():
        assert sha(directory / filename) == digest, filename
    assert sha(directory / 'accel_soc') == source['firmware_elf_sha256']
    assert sha(directory / 'accel_soc.verilog') == source['firmware_image_sha256']
    variants[name] = dict(source=source, summary=summary, directory=str(directory),
                          result_sha256=sha(directory / 'result.json'),
                          simulation_log_sha256=sha(directory / 'simulation.log'), vectors=vectors)

same = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256',
        'versions', 'tools', 'vectors', 'simulator_sha256', 'firmware_opt', 'firmware_experiment']
for field in same:
    assert variants['oldabi']['source'][field] == variants['scalar']['source'][field] == variants['packed']['source'][field], field

source = variants['packed']['source']
directory = Path(variants['packed']['directory'])
log = (directory / 'simulation.log').read_text().split('\n', 1)[1]
negative = []
for name, mutate in [
    ('one_missing_mmio_write', lambda d: d['layers'][0]['performance'].__setitem__('mmio_writes',21733)),
    ('phase_gap', lambda d: d['layers'][0]['performance'].__setitem__('other',d['layers'][0]['performance']['other']-1)),
    ('one_missing_mac_fire', lambda d: d['layers'][0]['performance'].__setitem__('mac_fire',202751)),
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
rows = {name: dict(cycles=v['source']['layers'][0]['cycles'],
                   firmware_cycles=v['source']['layers'][0]['firmware_cycles'],
                   **v['source']['layers'][0]['performance']) for name, v in variants.items()}
comparisons = {}
for base in ['oldabi', 'scalar']:
    comparisons['packed_minus_' + base] = {k: rows['packed'][k] - rows[base][k] for k in rows[base]}
    comparisons['packed_cycle_reduction_percent_vs_' + base] = 100 * (rows[base]['cycles'] - rows['packed']['cycles']) / rows[base]['cycles']
result = dict(status='PASS', scope='same-toolchain local fixed layer_00 only; no qualification, PPA or retention claim',
              identities_identical=same, variants={n: {k: v for k,v in x.items() if k not in ['source','summary']}
                                                  for n,x in variants.items()},
              measured_source=dict(main_commit=source['main_commit'],e203_commit=source['e203_commit']),
              firmware_elf_sha256={n:x['source']['firmware_elf_sha256'] for n,x in variants.items()},
              firmware_image_sha256={n:x['source']['firmware_image_sha256'] for n,x in variants.items()},
              simulator_sha256=source['simulator_sha256'], rows=rows, comparisons=comparisons,
              negative_actual_record_checks=negative)
args.out.write_text(json.dumps(result, indent=2) + '\n')
print('PASS: 3 actual results, exact vectors/hashes, 10 rejected corruptions; ' + str(args.out))
