#!/usr/bin/env python3
"""Independently check paired wrapper PPA report bytes and numerical comparisons.

No EDA tool or execution helper is imported. Library units and physical coverage
are deliberately left as reported; this does not establish physical signoff.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def number(pattern, text):
    found = re.findall(pattern, text, re.M)
    require(len(found) == 1, 'ambiguous/missing report metric: ' + pattern)
    return float(found[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paired', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    raw = args.paired.read_bytes()
    report = json.loads(raw.decode())
    checked, cases = [], {}
    for label in ['baseline', 'candidate']:
        case = report['cases'][label]
        entries = dict(case['reports'], **{'area.rpt': case['area_report']})
        for name, item in entries.items():
            data = item['text'].encode('utf-8')
            require(digest(data) == item['sha256'], label + '/' + name + ': exported text differs from original bytes')
            checked.append(dict(case=label, name=name, bytes=len(data), sha256=item['sha256']))
        area = case['area_report']['text']
        total = number(r'^Total cell area:\s+(\S+)', area)
        macros = number(r'^Macro/Black Box area:\s+(\S+)', area)
        count = number(r'^Number of macros/black boxes:\s+(\S+)', area)
        require(total == case['total_cell_area'] and macros == case['macro_area'] and count == case['macro_count'] == 16,
                label + ': area/macro metadata differs from original report')
        require(abs((total - macros) - case['stdcell_area']) < 1e-8, 'standard-cell subtraction differs')
        require('No wire load specified' in area and 'Total area:                 undefined' in area,
                'wire-load/total-area limitation is missing')
        setup_values = re.findall(r'^\s*slack \(MET\)\s+(\S+)', case['reports']['setup-exact.rpt']['text'], re.M)
        hold_values = re.findall(r'^\s*slack \(VIOLATED\)\s+(\S+)', case['reports']['hold-exact.rpt']['text'], re.M)
        require(setup_values and hold_values, 'timing report has no explicit slack values')
        setup, hold = min(map(float, setup_values)), min(map(float, hold_values))
        require(abs(setup - case['setup_slack_ns']) < 5.1e-7 and abs(hold - case['hold_slack_ns']) < 5.1e-7,
                label + ': exact timing attribute differs from high-precision report')
        require(setup > 0 and hold < 0, 'reported pre-layout timing classification differs')
        cases[label] = dict(total_cell_area_library_units=total, macro_area_library_units=macros,
                            standard_cell_area_library_units=total - macros, macro_count=int(count),
                            setup_slack_ns=case['setup_slack_ns'], hold_slack_ns=case['hold_slack_ns'],
                            netlist_sha256=case['netlist_sha256'], sdc_sha256=case['sdc_sha256'],
                            timing_coverage_report_sha256=case['reports']['analysis-coverage.rpt']['sha256'])
    before, after = report['cases']['baseline'], report['cases']['candidate']
    require(before['constraints_sha256'] == after['constraints_sha256'], 'input constraints differ')
    require(before['manifest']['libraries'] == after['manifest']['libraries'], 'library identities/PVT differ')
    for name, value in before['manifest']['source_sha256'].items():
        if name != 'accel_icb_slave.v':
            require(after['manifest']['source_sha256'][name] == value, 'original core/SRAM adapter differs: ' + name)
    require(set(after['manifest']['source_sha256']) - set(before['manifest']['source_sha256']) ==
            {'BiasBankCache.sv', 'LinearCachedCore.sv'}, 'unexpected added PPA source')
    b, a = cases['baseline'], cases['candidate']
    comparison = dict(cell_area_delta_library_units=a['total_cell_area_library_units'] - b['total_cell_area_library_units'],
                      cell_area_ratio=a['total_cell_area_library_units'] / b['total_cell_area_library_units'],
                      standard_cell_area_ratio=a['standard_cell_area_library_units'] / b['standard_cell_area_library_units'],
                      setup_slack_delta_ns=a['setup_slack_ns'] - b['setup_slack_ns'],
                      hold_slack_delta_ns=a['hold_slack_ns'] - b['hold_slack_ns'])
    require(abs(comparison['cell_area_ratio'] - report['comparison']['cell_area_ratio']) < 1e-12,
            'source area comparison differs from independent arithmetic')
    result = dict(status='PASS', scope='original report-byte integrity and paired numerical/source/constraint audit; no EDA rerun or physical signoff',
                  source_summary_sha256=digest(raw), cases=cases, comparison=comparison,
                  checked_reports=checked, constraints_sha256=before['constraints_sha256'],
                  library_identity=before['manifest']['libraries'], limitations=report['limitations'],
                  coverage='See original analysis-coverage reports; untested paths and hold violations are retained, not waived by this audit.')
    with args.out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('PASS: paired report bytes, libraries, original core, constraints and area/STA arithmetic')


if __name__ == '__main__':
    main()
