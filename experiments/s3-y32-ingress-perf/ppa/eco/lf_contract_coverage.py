#!/usr/bin/env python3
"""Compare all native check identities for the explicitly new LF input contract.

This verifies coverage transition only; root must independently accept native
receipts, exact input-delay polarity changes, constraints, libraries and paths.
It never reclassifies the frozen original-SDC result as closed.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
AUDITOR = ROOT / 'experiments/s3-y32-ingress-perf/ppa/eco/unknown_checks.py'
spec = importlib.util.spec_from_file_location('lf_contract_unknown_auditor', AUDITOR)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def record(path):
    data = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}


def audit(baseline_full, candidate_full):
    baseline_full, candidate_full = Path(baseline_full), Path(candidate_full)
    try:
        frozen_record = record(checks.DEFAULT)
        checks.require(frozen_record['sha256'] == checks.FROZEN_COVERAGE_SHA256,
                       'Frozen original-SDC report drifted')
        frozen = checks.parse_coverage(checks.DEFAULT.read_text())
        baseline = checks.parse_coverage(baseline_full.read_text())
        candidate = checks.parse_coverage(candidate_full.read_text())
        checks.require(baseline['summary'] == frozen['summary']
                       and baseline['design'] == frozen['design'],
                       'Full baseline does not reproduce frozen original-SDC summary')
        before_nonmet = {key: value for key, value in checks.states(baseline).items()
                         if value[0] != 'met'}
        frozen_nonmet = {key: value for key, value in checks.states(frozen).items()
                         if value[0] != 'met'}
        checks.require(before_nonmet == frozen_nonmet,
                       'Full baseline does not retain every frozen non-met identity/reason')
        result = checks.compare(baseline, candidate)
        result['coverage_transition_pass'] = result.pop('closed')
        # The native coverage clock column is the check/capture clock. The
        # separately approved input *launch* polarity/reference changes belong
        # in input-delay and exact-source path evidence, not a coverage rename.
        result.update(
            schema='ingress1064-lf-contract-full-coverage-difference-v1',
            status=('LF_CONTRACT_COVERAGE_TRANSITION_PASS_REVIEW_NATIVE_RECEIPTS'
                    if result['coverage_transition_pass'] else
                    'LF_CONTRACT_COVERAGE_TRANSITION_FAILED'),
            qualification='NEW_INPUT_CONTRACT_ONLY_NOT_ORIGINAL_SDC_OR_CDC_RDC_SIGNOFF',
            original_sdc_unknown_count=4,
            original_sdc_verdict='UNCHANGED_UNKNOWN4_NOT_CLOSED',
            frozen_original_report=frozen_record,
            baseline_full=record(baseline_full),
            candidate_full=record(candidate_full),
            parser=record(AUDITOR),
            allowed_coverage_identity_changes=[],
            allowed_state_changes='EXACT_FOUR_ORIGINAL_UNKNOWN_IDENTITIES_TO_EXPLICIT_MET_ONLY',
            native_receipt_and_input_delay_diff_review='REQUIRED_SEPARATELY')
    except (ValueError, OSError, KeyError) as error:
        result = dict(status='INVALID_NATIVE_COVERAGE_EVIDENCE',
                      coverage_transition_pass=False, error=str(error))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-full', type=Path, required=True)
    parser.add_argument('--candidate-full', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    result = audit(args.baseline_full, args.candidate_full)
    if args.out:
        checks.require(not args.out.exists(), 'Refuse to overwrite review')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['coverage_transition_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
