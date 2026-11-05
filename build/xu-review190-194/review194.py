#!/usr/bin/env python3
"""Independent local review of frozen190 and original57/166 receipts. No EDA/network."""
import argparse
import ast
from collections import Counter
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
B = ROOT / 'build/xu-score-resume-20261103'
REMOTE = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
SCOPE = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-ts16.tcl'
SCOPE_SHA = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
NET = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'


def need(value, text):
    if not value:
        raise ValueError(text)


def read(path):
    return json.loads(path.read_text())


def ident(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


class Originals:
    def __init__(self):
        self.consumed = {}
        self.manifests = {}

    def consume(self, archive, relative, expected=None):
        directory = B / archive
        manifest = directory / 'manifest.json'
        rows = read(manifest)
        if isinstance(rows, dict):
            rows = rows['files']
        need(isinstance(rows, list), 'original manifest list required')
        matches = [x for x in rows if x['path'] == relative]
        need(len(matches) == 1, 'unique original manifest row required: ' + relative)
        path = directory / relative
        need(path.is_file() and not path.is_symlink(), 'actual original body missing: ' + relative)
        actual = ident(path)
        row = matches[0]
        need(actual['bytes'] == row['bytes'] and actual['sha256'] == row['sha256'], 'original manifest bytes differ: ' + relative)
        if expected:
            need(actual['sha256'] == expected['sha256'] and ('bytes' not in expected or actual['bytes'] == expected['bytes']),
                 'original receipt bytes differ: ' + relative)
        self.consumed[str(path)] = actual
        self.manifests[str(manifest)] = ident(manifest)
        return path


def clock_section(text):
    start = text.index('set XU_CLOCK_MODE envelope\n')
    end = text.index('# Exact post-elaboration macro groups;')
    return text[start:end]


def norm_sdc(text):
    return re.sub(r'(?m)^source \{[^\n]+/constraints\.sdc\}$', 'source {SAME404c7d_SDC}', text)


def run():
    source = ROOT / 'build/xu-s2c-common-power190'
    manifest = read(source / 'manifest190.json')
    frozen = []
    need(len(manifest['runtime']) == len({x['name'] for x in manifest['runtime']}), 'duplicate190 runtime')
    for row in manifest['runtime']:
        need(Path(row['name']).name == row['name'], 'unsafe190 runtime name')
        actual = ident(source / row['name'])
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'], '190 runtime changed: ' + row['name'])
        frozen.append(actual)
    frozen.append(ident(source / 'manifest190.json'))
    for path in source.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path), feature_version=(3, 6))
    spec = importlib.util.spec_from_file_location('reviewed190', str(source / 'power190.py'))
    api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
    api.runtime()
    ref = read(source / 'references190.json')
    original = Originals()
    oldrel = 's2c-full-soc-power12-20261104-57/'
    prep_path = original.consume('next-results-export-69', oldrel + 'prepared.json', ref['prepared57'])
    exec_path = original.consume('next-results-export-69', oldrel + 'execution.json', ref['execution57'])
    prep, execution = read(prep_path), read(exec_path)
    need(prep['netlist']['sha256'] == NET and prep['analysis_sdc']['sha256'] == SDC and
         execution['input_sha256_before'] == execution['input_sha256_after'] == prep['input_sha256'] and len(prep['input_sha256']) == 367,
         'actual57 source/map/SDC/input receipt mismatch')
    fm_path = original.consume('current-evidence-export-09', 'candidate-formality-campaign-20261103-01/state.json', ref['fm_state'])
    fm = read(fm_path)
    runfm = [r for r in fm['runs'] if r['candidate'] == 's2c']
    need(len(runfm) == 1, 'own S2c FM unique')
    fm = runfm[0]
    need(fm['frozen_before'] == fm['frozen_after'] and fm['returncode'] == 0, 'own FM native receipts differ')
    log = original.consume('current-evidence-export-09', fm['log']['path'].split(REMOTE)[1], fm['log']).read_text()
    need(log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS') == 1 and
         re.findall(r'^\s*(\d+) Passing compare points\s*$', log, re.M) == ['42338'] and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)$', log, re.M) == ['Verification SUCCEEDED'], 'actual own FM incomplete')
    original.consume('current-evidence-export-09', ref['verify']['path'].split(REMOTE)[1], ref['verify'])
    ppa_run = read(original.consume('current-evidence-export-09', fm['ppa_execution']['path'].split(REMOTE)[1], fm['ppa_execution']))
    need(ppa_run['netlist_sha256'] == NET and ppa_run['analysis_sdc_sha256'] == SDC and
         ppa_run['dc']['returncode'] == ppa_run['pt']['returncode'] == 0, 'same own PPA identity required')
    area = original.consume('current-evidence-export-09', ref['area']['path'].split(REMOTE)[1], ref['area']).read_text()
    need(re.search(r'^Total cell area:\s*3365797\.600429\s*$', area, re.M) and
         re.search(r'^u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave\n\s*294801\.8380[^\n]*accel_icb_slave\s*$', area, re.M), 'same own area required')
    inv_path = original.consume('terminal-results-export-22', prep['mapped_sram_inventory']['path'].split(REMOTE)[1], prep['mapped_sram_inventory'])
    inv = read(inv_path)
    raw = original.consume('terminal-results-export-22', inv['provenance']['raw_tsv']['path'].split(REMOTE)[1], inv['provenance']['raw_tsv'])
    need(api.base.inventory_rows(raw) == inv['macros'] and len(inv['macros']) == 336 and sum(len(m['pins']) for m in inv['macros']) == 22512,
         'actual native inventory/body differs')
    exact_pins = {p['full_name'] for m in inv['macros'] for p in m['pins']}
    pre166 = B / 'preflight178/s2e-final155-power-preflight-20261105-166'
    prepared166 = read(original.consume('preflight178', 's2e-final155-power-preflight-20261105-166/prepared.json'))
    clock166 = clock_section(original.consume('preflight178', 's2e-final155-power-preflight-20261105-166/task_00/power.tcl').read_text())
    need(prepared166['clock_scope']['sha256'] == ref['scope']['sha256'] == SCOPE_SHA and
         prepared166['analysis_sdc']['sha256'] == prep['analysis_sdc']['sha256'] == SDC,
         'actual166 common SDC/scope identity differs')
    packet178 = ROOT / 'docs/validation/xu-score-preflight178-20261105/preflight178.tar.xz'
    need(ident(packet178)['sha256'] == 'da981b5ed9d5c07524ece0b454fa7273f61e222917db9037d4155407e0a7ee1a', 'original178 archived packet SHA differs')
    layers = []
    for index, (task, prior) in enumerate(zip(prep['tasks'], execution['tasks'])):
        need(task['task_id'] == prior['task_id'] == index, 'actual task order differs')
        script_path = original.consume('next-results-export-69', oldrel + 'task_%02d/power.tcl' % index, task['script'])
        bridge = read(original.consume('next-results-export-69', oldrel + 'task_%02d/task-mapped-receipt.json' % index, task['mapped_macro_bridge']))
        need(bridge == task['mapped_macro_bridge_receipt'] and bridge['macro_count'] == 336 and bridge['mapped_pin_bit_count'] == 22512 and
             bridge['inventory'] == prep['mapped_sram_inventory'] and bridge['output_saif'] == task['saif'], 'actual bridge identities differ')
        pins = read(original.consume('next-results-export-69', oldrel + 'task_%02d/measured-sram-pins.json' % index, task['measured_sram_pin_states']))['pins']
        need(len(pins) == len({p['mapped_path'] for p in pins}) == 22512 and {p['mapped_path'] for p in pins} == exact_pins,
             'actual measured pin bit bijection differs')
        window = task['activity_window']
        duration = window['duration_ticks']
        need(duration == 6604373333334 and window['formal_elapsed_cycles'] == 990656 and window['timescale_seconds'] == 1e-15,
             'own57 true measured duration/cycle differs')
        for pin in pins:
            need(sum(pin.get(k, 0) for k in ('T0', 'T1', 'TX', 'TZ', 'TB')) == duration, 'actual bit time conservation differs')
        text = script_path.read_text()
        exact_new = text.replace('set_propagated_clock [all_clocks]\nupdate_timing\n',
                                'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource {' + SCOPE + '}\nupdate_timing\n')
        need(exact_new != text and api.common_clock(text, ref['scope']) == exact_new and
             norm_sdc(clock_section(exact_new)) == norm_sdc(clock166), '190 common clock section differs from actual166')
        testtask = dict(task); testtask['script'] = dict(task['script'], path=str(script_path))
        newsaif = '/NO_NATIVE_REVIEW194/task_%02d/task-mapped.saif' % index
        item = dict(saif=dict(path=newsaif), completion_marker='REVIEW194_NOT_A_NATIVE_RUN')
        rendered = api.power_script(testtask, item, ref['scope'])
        expected = exact_new.replace('{' + task['saif']['path'] + '}', '{' + newsaif + '}').replace(task['completion_marker'], item['completion_marker'])
        need(rendered == expected and 'set_propagated_clock [all_clocks]' not in rendered,
             '190 power rewrite changes more than authorized scope/SAIF path/marker')
        q = [p for p in pins if re.search(r'/Q\[\d+\]$', p['mapped_path'])]
        layers.append(dict(task_id=index, cycles=990656, duration_fs=duration, measured_pin_bits=len(pins),
                           q_positive_tx=sum(p.get('TX', 0) > 0 for p in q), q_full_window_tx=sum(p.get('TX', 0) == duration for p in q),
                           old_saif_sha256=task['saif']['sha256'], clock_method_identical_to_actual166=True))
    need(len(layers) == 12, 'all original layers required')
    return dict(schema='xu-review190-194-v1', status='LOCAL_FROZEN190_REVIEW_PASSED_NATIVE_PENDING_NOT_QUALIFIED',
                qualification='NOT_QUALIFIED', native_runs=0, remote_operations=0,
                original_consumed=list(original.consumed.values()), original_manifests=list(original.manifests.values()),
                frozen190=frozen, original178_packet=ident(packet178), own57_map_sha256=NET, common_sdc_sha256=SDC, common_scope_sha256=SCOPE_SHA,
                native_original_macro_count=336, native_original_pin_count=22512, own_original_fm_points=42338,
                own_area_mm2='0.2948018380', full_soc_area_mm2='3.365797600429', layers=layers,
                limitations=['Local original payload bytes verified; original367server inputs are historical receipts here and must all be rehashed by190 on server.',
                             'Original mapped SAIF bodies and technology library bodies are absent locally; no claim of local SAIF replay or new native qualification.',
                             'Actual166 method compared through returned178 power Tcl and prepared identities; same method does not establish physical clock/activity qualification.',
                             'Unknown Q remains positive in every original layer; no new power result, energy gain or score is asserted.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    data = run()
    with args.out.open('x') as stream:
        json.dump(data, stream, indent=2, sort_keys=True); stream.write('\n')
    print(data['status'])


if __name__ == '__main__':
    main()
