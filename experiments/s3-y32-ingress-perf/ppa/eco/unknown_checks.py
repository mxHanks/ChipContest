#!/usr/bin/env python3
"""Audit the four native unknown checks without treating missing rows as met.

Report-only by default. Closure additionally needs full native identity details
for both designs, identical other checks/clocks, and receipt-bound candidate
coverage, clock report and tool log. This does not certify CDC/RDC or silicon.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DEFAULT = ROOT / 'docs/validation/s3-y32-ingress-perf-native-20261114/catch3/reload/persisted-coverage.rpt'
FROZEN_COVERAGE_SHA256 = '3975ca9364fdc03dfd22f3d3b8a5f5ecfde10435370f57b3785584dbcb135ad6'
MAPPED_SHA256 = 'd83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1'
ORIGINAL_SDC_SHA256 = 'c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c'
PT_ADD_SHA256 = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
LIBRARIES = {'standard_cell': 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
             'sram': 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}
_AON = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
ORIGINAL_UNKNOWN_IDENTITIES = frozenset(
    [(_AON + name + '/T_8_reg/D', 'CK(rise)', 'xu_lfextclk', 'setup', '-')
     for name in ('dwakeup_deglitch', 'bootrom_deglitch')]
    + [(_AON + 'u_sirv_aon/u_sirv_pmu/' + name + '/SDN(rise)', 'CK(rise)',
        'xu_lfextclk', 'recovery', "sdf_cond(ENABLE_NOT_D===1'b1)")
       for name in ('erst_reset_r_reg', 'erst_reset_r_r_reg')])
SPEC = importlib.util.spec_from_file_location('unknown_native_plan', HERE / 'plan.py')
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


def require(value, message):
    if not value:
        raise ValueError(message)


def file_identity(path):
    path = Path(path)
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def identity(row):
    return tuple(row[k] for k in ('constrained_pin', 'related_pin', 'clock', 'kind', 'condition'))


def parse_coverage(text):
    # Reuse the production summary/violated reconciliation, rather than another
    # approximation of PrimeTime's check totals.
    summary, _ = plan.catalog(text)
    header = re.search(r'(?m)^Pin\s+Pin\s+Clock\s+Type\s+Condition\s+Slack\s+Reason\s*\n-+\s*\n', text)
    require(header, 'Native coverage detail header missing')
    rows = {}
    detail = text[header.end():]
    newlines = [m.start() for m in re.finditer('\n', text)]
    for block in re.finditer(r'(?m)^(\S+)([^\n]*)\n((?:[ \t].*\n|\n)*)', detail):
        if block[0].strip() == '1':  # Native Tcl command return value.
            continue
        tokens = block[0].split()
        positions = [i for i, token in enumerate(tokens) if token in plan.CHECKS]
        require(positions == [3], 'Unparsed/ambiguous native check block: ' + block[1])
        pin, related, clock, kind = tokens[:4]
        tail = ' '.join(tokens[4:])
        untested = re.fullmatch(r'(.+?)\s+untested\s+(\w+)', tail)
        slack = None
        if untested:
            condition, reason = untested.groups()
            status = 'untested'
        else:
            tested = re.fullmatch(r'(.+?)\s+([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+-', tail)
            require(tested, 'Unparsed native status/slack: ' + pin)
            condition, number = tested.groups()
            slack = float(number)
            require(math.isfinite(slack), 'Nonfinite native slack: ' + pin)
            status, reason = ('violated' if number.startswith('-') else 'met'), '-'
        instance, separator, pin_name = pin.rpartition('/')
        row = dict(constrained_pin=pin, instance=instance if separator else None,
                   pin=pin_name if separator else pin, related_pin=related,
                   clock=clock, kind=kind, condition=condition, status=status,
                   reason=reason, slack_printed_ns=slack,
                   coverage_line=bisect_right(newlines, header.end() + block.start()) + 1)
        key = identity(row)
        require(key not in rows, 'Duplicate native check identity: ' + pin)
        rows[key] = row
    counts = Counter((r['kind'], r['status']) for r in rows.values())
    for kind in plan.CHECKS:
        for status in ('untested', 'violated'):
            require(counts[kind, status] == summary[kind][status],
                    'Incomplete native ' + kind + '/' + status + ' identity catalog')
        require(counts[kind, 'met'] in (0, summary[kind]['met']),
                'Partial native met detail catalog: ' + kind)
    design = re.findall(r'(?m)^Design\s*:\s*(\S+)\s*$', text)
    require(len(design) == 1, 'Missing/ambiguous native design')
    return dict(design=design[0], summary=summary, checks=rows,
                complete_identities=len(rows) == summary['All Checks']['total'])


def unknowns(report):
    return {k: r for k, r in report['checks'].items()
            if r['status'] == 'untested' and r['reason'] == 'unknown'}


def states(report, except_keys=()):
    return {k: (r['status'], r['reason']) for k, r in report['checks'].items() if k not in except_keys}


def compare(baseline, candidate, baseline_details=None):
    original = unknowns(baseline)
    require(set(original) == ORIGINAL_UNKNOWN_IDENTITIES,
            'Baseline must retain the exact frozen four unknown identities')
    if baseline_details is not None:
        require(baseline_details['summary'] == baseline['summary']
                and baseline_details['design'] == baseline['design'], 'Baseline detailed summary/design changed')
        require({k: v for k, v in states(baseline_details).items() if v[0] != 'met'}
                == {k: v for k, v in states(baseline).items() if v[0] != 'met'},
                'Baseline detailed untested/violated identities changed')
        baseline = baseline_details
    failures = []
    def check(value, message):
        if not value:
            failures.append(message)
    check(candidate['design'] == baseline['design'], 'design changed')
    check({k: v['total'] for k, v in candidate['summary'].items()}
          == {k: v['total'] for k, v in baseline['summary'].items()}, 'check type/total counts changed')
    candidate_unknown = unknowns(candidate)
    check(not candidate_unknown, 'unknown checks remain: ' + str(len(candidate_unknown)))
    for key, row in original.items():
        found = candidate['checks'].get(key)
        check(found is not None, 'original unknown has no explicit native verdict: ' + row['constrained_pin'])
        if found:
            check(found['status'] == 'met' and found['reason'] == '-',
                  'original unknown is not explicitly met: ' + row['constrained_pin'])
    # A summary-only increase in met cannot establish which native checks ran.
    check(baseline['complete_identities'], 'baseline lacks full native check identities; recollect met details')
    check(candidate['complete_identities'], 'candidate lacks full native check identities')
    if baseline['complete_identities'] and candidate['complete_identities']:
        check(set(baseline['checks']) == set(candidate['checks']), 'native check identity set changed')
        check(states(baseline, original) == states(candidate, original), 'other native check states/reasons changed')
    else:
        # Even partial original coverage supplies every non-met identity.
        before = {k: v for k, v in states(baseline, original).items() if v[0] != 'met'}
        after = {k: v for k, v in states(candidate, original).items() if v[0] != 'met'}
        check(before == after, 'other untested/violated identity/reason set changed')
    return dict(closed=not failures, failures=failures,
                original_unknown_checks=list(original.values()),
                current_unknown_checks=list(candidate_unknown.values()),
                current_summary=candidate['summary'],
                complete_baseline_identities=baseline['complete_identities'],
                complete_candidate_identities=candidate['complete_identities'])


def parse_clocks(text):
    # report_clock wraps long clock names onto their own line.
    pattern = r'(?m)^(\S+)[ \t]*\n?[ \t]+([\d.eE+-]+)[ \t]+\{([^}]+)\}[ \t]+([pGI ]*)\{([^}]+)\}'
    rows = {}
    for name, period, waveform, attributes, source in re.findall(pattern, text):
        require(name not in rows, 'Duplicate clock: ' + name)
        value = float(period)
        require(math.isfinite(value) and value > 0, 'Invalid clock period: ' + name)
        rows[name] = dict(period_printed_ns=period, waveform=' '.join(waveform.split()),
                          attributes=''.join(sorted(attributes.split())), source=' '.join(source.split()))
    require(rows, 'No native clock definitions parsed')
    return rows


def execution_signature(receipt):
    """The clock table is rounded; only the pinned SDC/map/library contract binds it."""
    require(receipt.get('schema') == 'ingress1064-n3-catch-arc-envelope-v1'
            and receipt.get('status') == 'NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE'
            and receipt.get('stage') == 'reload' and receipt.get('completion_marker') is True
            and receipt.get('tool_timed_out') is False,
            'Native execution schema/status/stage/marker/timeout is invalid')
    require(receipt.get('source_mapped_sha256') == MAPPED_SHA256,
            'Native current mapped signature changed')
    inputs = receipt.get('inputs', [])
    for name, expected in [('reference-full-soc.sdc', ORIGINAL_SDC_SHA256),
                           ('constraints-pt-add.sdc', PT_ADD_SHA256)]:
        found = [r for r in inputs if Path(r['path']).name == name]
        require(len(found) == 1 and found[0].get('sha256') == expected,
                'Native SDC input signature changed: ' + name)
    require(any(Path(r['path']).name == 'mapped.v' and r.get('sha256') == MAPPED_SHA256 for r in inputs),
            'Current mapped input bytes are not bound')
    require(receipt.get('outputs', {}).get('original-constraints-pt-add.sdc')
            == dict(bytes=6384, sha256=PT_ADD_SHA256), 'Native PT-add SDC output signature changed')
    libraries = receipt.get('libraries', [])
    require(len(libraries) == 2 and {r['role']: r['sha256'] for r in libraries} == LIBRARIES,
            'Native dual-library signatures changed')
    return dict(mapped_sha256=MAPPED_SHA256, original_sdc_sha256=ORIGINAL_SDC_SHA256,
                pt_add_sha256=PT_ADD_SHA256, libraries=LIBRARIES)


def bind_native(coverage, logs, clocks, execution, require_log=True):
    files = [coverage, *logs, *([clocks] if clocks else [])]
    require(len({Path(p).resolve() for p in files}) == len(files),
            'Coverage, tool logs and clock report must be independent files')
    require(all(Path(p).suffix == '.log' for p in logs), 'Native tool log must be a .log output')
    records = [file_identity(p) for p in files]
    failures, warnings = [], []
    for path in logs:
        lines = Path(path).read_text().splitlines()
        warnings.extend(dict(file=str(path), line=i + 1, text=line.strip(),
                             context=lines[max(0, i-2):i+3])
                        for i, line in enumerate(lines) if re.search(r'\bPTE-052\b', line))
    if require_log and not logs:
        failures.append('independent native tool log missing')
    if not clocks:
        failures.append('native clock report missing')
    signature = None
    if execution:
        receipt = json.loads(Path(execution).read_text())
        require(receipt.get('returncode') == 0 and receipt.get('run_requested') is True
                and all(receipt.get(k) == [] for k in ('source_drift', 'native_tool_errors', 'missing_outputs')),
                'Native execution receipt is not clean/executed')
        signature = execution_signature(receipt)
        outputs = receipt.get('outputs', {})
        for record in records:
            expected = outputs.get(Path(record['path']).name)
            require(expected == {k: record[k] for k in ('bytes', 'sha256')},
                    'Native receipt output binding mismatch: ' + record['path'])
    else:
        failures.append('native execution receipt missing')
    return dict(files=records, execution=file_identity(execution) if execution else None,
                contract_signature=signature,
                pte_052_count=len(warnings), pte_052=warnings, failures=failures)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', nargs='?', choices=['report'], default='report')
    parser.add_argument('--baseline', type=Path, default=DEFAULT)
    parser.add_argument('--coverage', type=Path, default=DEFAULT)
    parser.add_argument('--baseline-details', type=Path, help='Same-baseline native coverage including all met details')
    parser.add_argument('--log', action='append', type=Path, default=[])
    parser.add_argument('--clocks', type=Path)
    parser.add_argument('--baseline-clocks', type=Path)
    parser.add_argument('--baseline-execution', type=Path, help='Clean receipt binding baseline full details and clocks')
    parser.add_argument('--execution', type=Path)
    parser.add_argument('--require-closed', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        require(file_identity(args.baseline)['sha256'] == FROZEN_COVERAGE_SHA256,
                'Original frozen coverage signature changed; baseline details are a separate recollection')
        baseline = parse_coverage(args.baseline.read_text())
        candidate = parse_coverage(args.coverage.read_text())
        details = parse_coverage(args.baseline_details.read_text()) if args.baseline_details else None
        result = compare(baseline, candidate, details)
        native = bind_native(args.coverage, args.log, args.clocks, args.execution)
        result['failures'].extend(native['failures'])
        if args.baseline_details and args.baseline_clocks and args.baseline_execution:
            result['baseline_native'] = bind_native(args.baseline_details, [], args.baseline_clocks,
                                                    args.baseline_execution, require_log=False)
            result['failures'].extend(result['baseline_native']['failures'])
            require(result['baseline_native']['contract_signature'] == native['contract_signature'],
                    'Baseline/candidate native constraint/map/library contracts differ')
        else:
            result['failures'].append('receipt-bound baseline full details/clocks missing')
        if args.clocks:
            result['clocks'] = parse_clocks(args.clocks.read_text())
            required = {r['clock'] for r in baseline['checks'].values() if r['clock'] != '-'}
            require(required <= set(result['clocks']), 'Coverage clocks absent from native clock report')
        if args.baseline_clocks and args.clocks:
            if parse_clocks(args.baseline_clocks.read_text()) != result['clocks']:
                result['failures'].append('native clock definitions changed')
        else:
            result['failures'].append('baseline/candidate native clock comparison missing')
        result.update(schema='ingress1064-native-unknown4-audit-v1', native=native,
                      baseline=file_identity(args.baseline), coverage=file_identity(args.coverage),
                      baseline_details=file_identity(args.baseline_details) if args.baseline_details else None,
                      baseline_clocks=file_identity(args.baseline_clocks) if args.baseline_clocks else None,
                      qualification='NATIVE_COVERAGE_ONLY_NOT_CDC_RDC_OR_PHYSICAL_SIGNOFF')
        result['closed'] = not result['failures']
        result['status'] = 'UNKNOWN4_NATIVE_COVERAGE_CLOSED' if result['closed'] else 'UNKNOWN4_NOT_CLOSED'
    except (ValueError, OSError, KeyError) as error:
        result = dict(status='INVALID_NATIVE_EVIDENCE', closed=False, error=str(error))
    if args.out:
        require(not args.out.exists(), 'Output receipt must be new')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 1 if result['status'] == 'INVALID_NATIVE_EVIDENCE' or (args.require_closed and not result['closed']) else 0


if __name__ == '__main__':
    raise SystemExit(main())
