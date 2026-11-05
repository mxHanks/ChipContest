#!/usr/bin/env python3
"""Local-only reproducible186 reference/target derivation from verified185/178/159."""
import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
D = '/storage2/2026contest/server4/s4_23usr/Desktop/'
B = D + 'xu-score-optimization-20261102/'


def load(path):
    return json.loads(path.read_text())


def identity(path, remote=None):
    data = path.read_bytes()
    return dict(path=remote or str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    old = ROOT / 'build/xu-s2e-coverage185'
    targets_path = old / 'targets185.json'
    csv_path = old / 'untested185.csv'
    assert identity(targets_path)['sha256'] == 'ae861ecb084f82d5f3e69803800cbe1c7f553c0a79dc6158a5add82b653aa047'
    assert identity(csv_path)['sha256'] == '5de35f54b92b6e746b63a06161ea937fa826b33fe2a37af75f095e97ca3e14c3'
    source = load(targets_path)
    assert source['schema'] == 'xu-s2e185-exact-targets-v1'
    with csv_path.open(newline='') as stream:
        checks = list(csv.DictReader(stream))
    pulse = [x for x in checks if x['reason'] == 'no_clock']
    assert len(checks) == 27217 and len(pulse) == len({x['pin'] for x in pulse}) == 9219
    counts = Counter(x['pin_leaf'] + '_' + x['transition_or_level'] for x in pulse)
    assert counts == {'RDN_low': 8766, 'SDN_low': 429, 'E_high': 24}
    roles = defaultdict(set)
    for row in pulse:
        roles[row['pin']].add('pulse_' + row['pin_leaf'] + '_' + row['transition_or_level'])
    uart = []
    for row in sorted(source['uart_missing_clock'], key=lambda x: x['pin']):
        e = row['pin']; assert e.endswith('/E')
        d = e[:-1] + 'D'
        uart.append(dict(E=e, D=d))
        roles[e].add('deep_uart_E'); roles[d].add('deep_uart_D')
    assert len(uart) == 24
    for row in source['unconstrained']:
        roles[row['pin']].add('deep_unconstrained')
    for row in source['hf_recovery_queries']:
        roles[row['source_object']].add('deep_HF_source')
        roles[row['target_pin']].add('deep_HF_target')
        cell = row['target_pin'].rsplit('/', 1)[0]
        roles[cell + '/CK'].add('deep_reset_CK')
    for row in source['pmu_unknown_recovery']:
        roles[row['pin']].add('deep_PMU_unknown_recovery')
    plic = sorted(source['plic_min_capacitance'])
    for pin in plic:
        roles[pin].add('deep_PLIC_min_cap')
    target_data = dict(schema='xu-s2e-coverage186-targets-v1', qualification='NOT_QUALIFIED',
                       source_targets185=identity(targets_path), source_checks185=identity(csv_path),
                       pulse_counts=dict(counts), objects=[dict(name=n, role='|'.join(sorted(v))) for n, v in sorted(roles.items())],
                       uart_pairs=uart, reset_queries=source['hf_recovery_queries'], plic_pins=plic,
                       original_no_endpoint_clock_checks=48, original_unconstrained_endpoints=31,
                       pmu_original_unknown=source['pmu_unknown_recovery'], limits=source['limits'])
    write('targets186.json', target_data)
    pre = ROOT / 'build/xu-score-resume-20261103/preflight178/s2e-final155-power-preflight-20261105-166'
    orig = ROOT / 'build/xu-score-resume-20261103/serverfailed159/s2e-own-timing-repair-20261105-155'
    prepared = load(pre / 'prepared.json')
    state155 = load(orig / 'state.json')
    target = prepared['target_mapped_context']
    libraries = []
    for row in prepared['implementation_controls']['libraries']:
        found = [x for x in source['own_libraries'] if x['path'] == row['path'] and x['sha256'] == row['sha256']]
        assert len(found) == 1
        libraries.append(found[0])
    preflight = {n: identity(pre / (n + '.json'), B + 's2e-final155-power-preflight-20261105-166/' + n + '.json')
                 for n in ('prepared', 'execution', 'result')}
    original_sta = state155['generated'][B + 's2e-own-timing-repair-20261105-155/final/sta.tcl']
    assert identity(HERE / 'frozen-own155-sta.tcl')['sha256'] == original_sta['sha256']
    sources = [target['netlist'], target['constraints'], target['clock_scope'], target['state'],
               prepared['pt'], original_sta] + libraries + list(preflight.values())
    # Freeze the original check/coverage data that185 classified, without exporting a library/model body.
    for name in ('check-timing.rpt', 'analysis-coverage.rpt', 'constraints.rpt'):
        sources.append(state155['reports'][B + 's2e-own-timing-repair-20261105-155/final/' + name])
    assert len(sources) == len({x['path'] for x in sources})
    write('references186.json', dict(schema='xu-s2e-coverage186-references-v1', qualification='NOT_QUALIFIED',
          target_context=target, original_sta=original_sta, pt=prepared['pt'], libraries=libraries,
          preflight=preflight, library_compiler_root=prepared['library_compiler_root'], server_inputs=sources,
          local_source185=identity(targets_path), local_checks185=identity(csv_path)))


if __name__ == '__main__':
    main()
