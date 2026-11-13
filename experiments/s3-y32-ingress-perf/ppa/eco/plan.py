#!/usr/bin/env python3
"""Catalog THIS ingress1064-n3 native coverage and freeze explicit diagnostic targets.

No library/tool access, no assumed old pin names, no automatic CDC/reset edits.
Targets are current native violated SRAM-D/register-D/gate-enable endpoints only. A native
topology diagnosis and one-buffer probe remain mandatory before delay edits.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

PROFILE = 'sysbus32-x-sram-353-dev-n3'
CHECKS = {'setup', 'hold', 'recovery', 'removal', 'min_period', 'min_pulse_width',
          'clock_gating_setup', 'clock_gating_hold', 'out_setup', 'out_hold'}
DEFAULT_FAMILIES = {'weights_D', 'bias_D', 'x_D', 'result_D', 'register_data_D', 'gating_enable'}
FAMILIES = DEFAULT_FAMILIES | {'reset_removal'}
PT_COMPAT_SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def safe_relative(name):
    path = Path(name)
    need(name and not path.is_absolute() and '..' not in path.parts,
         'unsafe native output path: ' + repr(name))
    return path


def pt_baseline(base, ptroot):
    """Bind an explicitly chosen successful PT receipt to the exact DC baseline.

    There is no automatic fallback from a failed baseline/pt collection. The
    original failure stays in place when an external report-only recollection
    is selected. Its source DC output identities must still match this map.
    """
    dc = json.loads((base / 'execution.json').read_text())
    pt = json.loads((ptroot / 'execution.json').read_text())
    need(pt.get('schema') in {'sysbus32-same-source-pt-execution-v1',
                              'ingress1064-same-source-pt-recollection-v1'},
         'unsupported native PT receipt schema')
    need(pt.get('status') == 'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED' and
         pt.get('returncode') == 0 and pt.get('source_drift') == [] and
         pt.get('native_tool_errors') == [] and
         pt.get('missing_required_outputs') == [] and
         pt.get('tool_timed_out') is False and pt.get('completion_marker') is True and
         (ptroot / 'SYSBUS32_PT_COLLECTION_COMPLETE_NOT_QUALIFIED.txt').is_file(),
         'same final native PT collection required')
    need(pt.get('source_dc', {}).get('execution_sha256') == sha(base / 'execution.json') and
         pt.get('manifest_sha256') == sha(base / 'package-files.json') and
         pt.get('top') == dc.get('top') and
         pt.get('hardware_profile') == dc.get('hardware_profile') == PROFILE and
         pt.get('defines') == dc.get('defines') and
         pt.get('libraries') == dc.get('libraries'),
         'native PT does not bind this DC/package/profile')
    source_outputs = pt.get('source_dc', {}).get('outputs', {})
    for name in ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'final.svf', 'libraries.tcl']:
        item = dc.get('outputs', {}).get(name)
        need(item and source_outputs.get(name) == item,
             'native PT source DC output identity differs: ' + name)
        path = base / name
        need(path.is_file() and not path.is_symlink() and
             path.stat().st_size == item['bytes'] and sha(path) == item['sha256'],
             'native DC output SHA/size drift: ' + name)
    names = ['required-reports.list', 'constraints-pt-add.sdc', 'reports/coverage.rpt', 'reports/setup.rpt',
             'reports/hold.rpt', 'reports/all_violators.rpt',
             'reports/clock_gating_hold.rpt', 'reports/removal.rpt']
    # Validate the list itself before using its entries as mandatory files.
    item = pt.get('outputs', {}).get('required-reports.list')
    reportlist = ptroot / 'required-reports.list'
    need(item and reportlist.is_file() and not reportlist.is_symlink() and
         reportlist.stat().st_size == item['bytes'] and sha(reportlist) == item['sha256'],
         'native required report list SHA/size drift')
    names += reportlist.read_text().splitlines()
    for name in sorted(set(names)):
        path = ptroot / safe_relative(name)
        item = pt.get('outputs', {}).get(name)
        need(item and path.is_file() and not path.is_symlink() and
             path.stat().st_size == item['bytes'] and sha(path) == item['sha256'],
             'native report SHA/size drift: ' + name)
    need(sha(ptroot / 'constraints-pt-add.sdc') == PT_COMPAT_SDC_SHA,
         'native PT constraints differ from unchanged original SDC plus proven -add compatibility')
    return pt, sorted(set(names))


def family(kind, pin):
    # These two current-map AON inputs have native hold checks but unknown
    # setup coverage. Keep the violations catalogued, outside delay edits until
    # their setup contract is established; a missing max path is not a pass.
    if kind == 'hold' and pin in {
        'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/bootrom_deglitch/T_8_reg/D',
        'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/dwakeup_deglitch/T_8_reg/D',
    }:
        return 'unverified_setup_data_D_REQUIRES_CONTRACT'
    if kind == 'hold' and re.search(r'/D\[\d+\]$', pin):
        for part, label in [('weights/', 'weights_D'), ('bias/memory/', 'bias_D'),
                            ('xSets', 'x_D'), ('resultSlices', 'result_D')]:
            if '/u_core/' + part in pin:
                return label
    if kind == 'hold' and pin.endswith('/D'):
        # A candidate only: native all_registers -data_pins membership and
        # sequential leaf/library identity are checked before any mutation.
        return 'register_data_D'
    if kind == 'clock_gating_hold':
        return 'gating_enable'
    if kind == 'removal':
        return 'reset_removal'
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
    for match in re.finditer(r'(?m)^(\S+)\n((?:[ \t].*\n|\n)+)', text):
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


def target_rows(checks, selected):
    targets = {}
    for row in checks:
        if row['family'] not in selected:
            continue
        pin = row['pin']
        if row['family'] == 'reset_removal':
            need(row['kind'] == 'removal' and re.search(r'/(?:RDN|SDN)\((?:rise|fall)\)$', pin),
                 'unexpected native asynchronous removal endpoint: ' + pin)
            pin = re.sub(r'\((?:rise|fall)\)$', '', pin)
        item = dict(pin=pin, kind=row['kind'], family=row['family'])
        need(pin not in targets or targets[pin] == item,
             'same pin has incompatible check kinds or families')
        targets[pin] = item
    return [targets[name] for name in sorted(targets)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True, help='THIS complete ingress1064-n3 native candidate')
    p.add_argument('--baseline-pt-dir', type=Path, help='explicit successful same-DC PT directory; default BASELINE/pt, no automatic fallback')
    p.add_argument('--families', default=','.join(sorted(DEFAULT_FAMILIES)), help='comma-separated subset of characterized hold-edit families')
    p.add_argument('--clock-root', action='append', default=[], help='exact driver output pin selected from THIS native map/path; read-only topology diagnosis only')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base = a.baseline.resolve()
    m = json.loads((base / 'manifest.json').read_text())
    dc = json.loads((base / 'execution.json').read_text())
    ptroot = a.baseline_pt_dir.resolve() if a.baseline_pt_dir else base / 'pt'
    pt, _ = pt_baseline(base, ptroot)
    need(m['hardware_profile'] == PROFILE and m['expected_geometry']['total_macros'] == 353 and
         m['expected_internal_macros'] == 33 and m['production_test_loader'] is True,
         'only exact original1064 N3 development map allowed')
    need(dc['status'] == 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' and
         pt['status'] == 'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED' and
         dc['returncode'] == pt['returncode'] == 0 and dc['source_drift'] == pt['source_drift'] == [] and
         dc['native_tool_errors'] == pt['native_tool_errors'] == [] and
         pt['source_dc']['execution_sha256'] == sha(base / 'execution.json'), 'native DC/PT chain incomplete')
    for name in ['reports/coverage.rpt', 'reports/all_violators.rpt']:
        need(sha(ptroot / name) == pt['outputs'][name]['sha256'], 'native report SHA drift: ' + name)
    need(sha(base / 'mapped.v') == dc['outputs']['mapped.v']['sha256'], 'native mapped.v SHA drift')
    selected = set(a.families.split(',')) if a.families else set()
    need(selected <= FAMILIES, 'unknown or unsupported clock edit family requested')
    need('reset_removal' not in selected or selected == {'reset_removal'},
         'reset_removal requires a separate explicit plan')
    rows, checks = catalog((ptroot / 'reports/coverage.rpt').read_text())
    targets = target_rows(checks, selected)
    need(targets or a.clock_root, 'no selected current native target or read-only clock root')
    for pin in a.clock_root:
        need('/' in pin and not any(c in pin for c in '{}\\\r\n\t '), 'unsafe exact clock root')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    catalogue = dict(schema='ingress1064-n3-complete-native-coverage-catalog-v1', status='CATALOGUED_NOT_FIXED',
        coverage=rows, counts=dict(Counter(row['kind'] for row in checks)),
        families=dict(Counter(row['family'] for row in checks)), checks=checks)
    (out / 'catalog.json').write_text(json.dumps(catalogue, indent=2, sort_keys=True) + '\n')
    plan = dict(schema='ingress1064-n3-explicit-native-target-plan-v1', hardware_profile=PROFILE,
        baseline_execution_sha256=sha(base / 'execution.json'), baseline_mapped_sha256=sha(base / 'mapped.v'),
        baseline_pt_execution_sha256=sha(ptroot / 'execution.json'),
        coverage_sha256=sha(ptroot / 'reports/coverage.rpt'), all_violators_sha256=sha(ptroot / 'reports/all_violators.rpt'),
        catalogue_sha256=sha(out / 'catalog.json'), selected_families=sorted(selected),
        targets=targets,
        read_only_clock_roots=sorted(set(a.clock_root)),
        excluded_checks=[row for row in checks if row['family'] not in selected],
        qualification='Explicit current-map candidates only; native topology diagnosis/probe and contracts still required')
    (out / 'targets.json').write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status='CURRENT_NATIVE_TARGETS_SEALED_NO_EDA', targets=len(targets),
        clock_roots=len(a.clock_root), plan_sha256=sha(out / 'targets.json'), counts=catalogue['counts']), sort_keys=True))


if __name__ == '__main__':
    main()
