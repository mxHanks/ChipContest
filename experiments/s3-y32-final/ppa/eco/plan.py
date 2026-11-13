#!/usr/bin/env python3
"""Catalog THIS final374 native coverage and freeze explicit diagnostic targets.

No library/tool access, no assumed old pin names, no automatic CDC/reset edits.
Targets are current native violated SRAM-D/gate-enable endpoints only. A native
topology diagnosis and one-buffer probe remain mandatory before delay edits.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

PROFILE = 'sysbus32-dma4-storage-sram-374-final'
CHECKS = {'setup', 'hold', 'recovery', 'removal', 'min_period', 'min_pulse_width',
          'clock_gating_setup', 'clock_gating_hold', 'out_setup', 'out_hold'}
FAMILIES = {'weights_D', 'bias_D', 'x_D', 'result_D', 'gating_enable'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def family(kind, pin):
    if kind == 'hold' and re.search(r'/D\[\d+\]$', pin):
        for part, label in [('weights/', 'weights_D'), ('biasMemory/', 'bias_D'),
                            ('xSets', 'x_D'), ('resultSlices', 'result_D')]:
            if '/u_core/' + part in pin:
                return label
    if kind == 'clock_gating_hold':
        return 'gating_enable'
    if kind == 'removal':
        return 'reset_removal_REQUIRES_CONTRACT'
    if kind == 'out_setup':
        return 'clock_or_output_setup_REQUIRES_TOPOLOGY'
    return 'other_' + kind + '_REQUIRES_CONTRACT'


def catalog(text):
    pat = r'^\s*(\w+|All Checks)\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s*$'
    rows = {name: dict(zip(['total', 'met', 'violated', 'untested'], map(int, values)))
            for name, *values in re.findall(pat, text, re.M)}
    need(set(rows) == CHECKS | {'All Checks'}, 'complete native coverage summary required')
    for name, row in rows.items():
        need(row['total'] == row['met'] + row['violated'] + row['untested'], 'coverage reconciliation: ' + name)
    for key in ['total', 'met', 'violated', 'untested']:
        need(sum(rows[kind][key] for kind in CHECKS) == rows['All Checks'][key],
             'coverage All Checks reconciliation: ' + key)
    checks = []
    # This is the actual production top's native coverage block layout. A new
    # layout or newly violated check kind must reconcile or stop, never vanish.
    for match in re.finditer(r'(?m)^(u_\S+|io_\S+)\n((?:[ \t].*\n|\n)+)', text):
        block = match[0]
        slack = re.search(r'(-[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s+-\s*$', block)
        if not slack:
            continue
        kind = re.search(r'\b(' + '|'.join(sorted(CHECKS, key=len, reverse=True)) + r')\b', block)
        need(kind, 'unclassified violated native coverage block')
        pin = match[1]
        checks.append(dict(pin=pin, kind=kind[1], family=family(kind[1], pin),
            slack_printed_ns=slack[1], coverage_line=text.count('\n', 0, match.start()) + 1,
            native_block_sha256=hashlib.sha256(block.encode()).hexdigest(), native_block=block))
    count = Counter(row['kind'] for row in checks)
    need(all(count.get(k, 0) == rows[k]['violated'] for k in CHECKS),
         'native violated block catalogue does not reconcile with complete coverage: ' + repr(count))
    need(len(checks) == rows['All Checks']['violated'], 'all violated checks must be catalogued')
    return rows, checks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True, help='THIS complete final374 native candidate')
    p.add_argument('--families', default=','.join(sorted(FAMILIES)), help='comma-separated subset of characterized hold-edit families')
    p.add_argument('--clock-root', action='append', default=[], help='exact driver output pin selected from THIS native map/path; read-only topology diagnosis only')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base = a.baseline.resolve()
    m = json.loads((base / 'manifest.json').read_text())
    dc = json.loads((base / 'execution.json').read_text())
    pt = json.loads((base / 'pt/execution.json').read_text())
    need(m['hardware_profile'] == PROFILE and m['expected_geometry']['total_macros'] == 374 and
         m['expected_internal_macros'] == 54 and m['production_test_loader'] is False,
         'only exact final374 production map allowed')
    need(dc['status'] == 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' and
         pt['status'] == 'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED' and
         dc['returncode'] == pt['returncode'] == 0 and dc['source_drift'] == pt['source_drift'] == [] and
         dc['native_tool_errors'] == pt['native_tool_errors'] == [] and
         pt['source_dc']['execution_sha256'] == sha(base / 'execution.json'), 'native DC/PT chain incomplete')
    for name in ['reports/coverage.rpt', 'reports/all_violators.rpt']:
        need(sha(base / 'pt' / name) == pt['outputs'][name]['sha256'], 'native report SHA drift: ' + name)
    need(sha(base / 'mapped.v') == dc['outputs']['mapped.v']['sha256'], 'native mapped.v SHA drift')
    selected = set(a.families.split(',')) if a.families else set()
    need(selected <= FAMILIES, 'unknown or CDC/reset/clock edit family requested')
    rows, checks = catalog((base / 'pt/reports/coverage.rpt').read_text())
    targets = {}
    for row in checks:
        if row['family'] in selected:
            prior = targets.get(row['pin'])
            need(prior is None or prior['kind'] == row['kind'], 'same pin has incompatible check kinds')
            targets[row['pin']] = {k: row[k] for k in ['pin', 'kind', 'family']}
    need(targets or a.clock_root, 'no selected current native target or read-only clock root')
    for pin in a.clock_root:
        need('/' in pin and not any(c in pin for c in '{}\\\r\n\t '), 'unsafe exact clock root')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    catalogue = dict(schema='final374-complete-native-coverage-catalog-v1', status='CATALOGUED_NOT_FIXED',
        coverage=rows, counts=dict(Counter(row['kind'] for row in checks)),
        families=dict(Counter(row['family'] for row in checks)), checks=checks)
    (out / 'catalog.json').write_text(json.dumps(catalogue, indent=2, sort_keys=True) + '\n')
    plan = dict(schema='final374-explicit-native-target-plan-v1', hardware_profile=PROFILE,
        baseline_execution_sha256=sha(base / 'execution.json'), baseline_mapped_sha256=sha(base / 'mapped.v'),
        baseline_pt_execution_sha256=sha(base / 'pt/execution.json'),
        coverage_sha256=sha(base / 'pt/reports/coverage.rpt'), all_violators_sha256=sha(base / 'pt/reports/all_violators.rpt'),
        catalogue_sha256=sha(out / 'catalog.json'), selected_families=sorted(selected),
        targets=[targets[name] for name in sorted(targets)],
        read_only_clock_roots=sorted(set(a.clock_root)),
        excluded_checks=[row for row in checks if row['family'] not in selected],
        qualification='Explicit current-map candidates only; native topology diagnosis/probe and contracts still required')
    (out / 'targets.json').write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status='CURRENT_NATIVE_TARGETS_SEALED_NO_EDA', targets=len(targets),
        clock_roots=len(a.clock_root), plan_sha256=sha(out / 'targets.json'), counts=catalogue['counts']), sort_keys=True))


if __name__ == '__main__':
    main()
