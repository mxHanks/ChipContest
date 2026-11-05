#!/usr/bin/env python3
"""Necessary adversarial checks against actual returned191, without modifying originals."""
import argparse
import copy
import json
from pathlib import Path
import audit205 as a


class Changed:
    def __init__(self, original, filename, mutation):
        self.original = original; self.filename = filename; self.mutation = mutation

    def __getattr__(self, name):
        return getattr(self.original, name)

    def json(self, filename):
        data = self.original.json(filename)
        if filename == self.filename:
            data = copy.deepcopy(data); self.mutation(data)
        return data


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--evidence-root', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True); p.add_argument('--sha256', required=True); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); a.need(not args.out.exists(), 'fresh negative-result file required')
    refs = a.reference_data(); ev = a.Evidence(args.evidence_root, args.archive, args.sha256)
    zero = a.campaign(ev, a.ROOT0, [0], refs)
    full = a.campaign(ev, a.ROOT12, list(range(12)), refs, zero)
    results = []; folder = a.ROOT12
    cases = [
        ('borrow_other_mapping', 'prepared.json', lambda x: x['context']['netlist'].update(sha256='0' * 64)),
        ('mutable_live_fm_state', 'prepared.json', lambda x: x['context']['native_fm_state'].update(path=a.REMOTE + 'candidate-formality-campaign-20261103-01/state.json')),
        ('drop_final_layer', 'execution.json', lambda x: x['tasks'].pop()),
        ('inclusive_cycle_substitution', 'prepared.json', lambda x: x['tasks'][0]['activity_window'].update(formal_elapsed_cycles=990657)),
        ('erase_unknown_q', 'prepared.json', lambda x: x['tasks'][0]['measured_summary'].update(q_tx_positive=0)),
        ('missing_frozen_runtime', 'prepared.json', lambda x: x['input_sha256'].pop(a.RUNTIME + 'power190.py')),
        ('changed_external_after_hash', 'execution.json', lambda x: x['input_sha256_after'].update({'UNDECLARED_EXTERNAL': '0' * 64})),
        ('wrong_preflight_status', 'prepared.json', lambda x: x['preflight'].update(status='FAILED_NOT_QUALIFIED')),
        ('wrong_own_area', 'prepared.json', lambda x: x['context']['area'].update(accelerator_mm2='0.01')),
        ('omitted_pin_receipt_mismatch', 'execution.json', lambda x: x['tasks'][0]['reports']['sram-pins-before.rpt'].update(sha256='0' * 64)),
        ('pretend_qualified', 'summary.json', lambda x: x.update(qualification='QUALIFIED')),
    ]
    for name, filename, mutation in cases:
        try:
            a.campaign(Changed(ev, folder + '/' + filename, mutation), folder, list(range(12)), refs, zero)
        except (ValueError, KeyError) as error:
            results.append(dict(case=name, rejected=True, error=str(error)))
        else:
            raise AssertionError('unsafe actual-packet mutation accepted: ' + name)
    try:
        a.safe171.inspect(args.archive, '0' * 64)
    except ValueError as error:
        results.append(dict(case='wrong_original_archive_hash', rejected=True, error=str(error)))
    else: raise AssertionError('wrong packet hash accepted')
    power = ev.path(folder + '/task_00/power.rpt').read_text().replace('1 W', '1 mW')
    try:
        a.power_values(power)
    except ValueError as error:
        results.append(dict(case='native_milliwatt_unit_substitution', rejected=True, error=str(error)))
    else: raise AssertionError('wrong unit accepted')
    result = dict(schema='xu-audit205-actual-packet-adversarial-v1', status='ALL_ACTUAL_PACKET_COUNTEREXAMPLES_REJECTED_NOT_QUALIFIED',
        qualification='NOT_QUALIFIED', archive=ev.report['archive'], positive_full12=full['complete'],
        checks=results, count=len(results), originals_modified=False, native_runs=0, remote_operations=0)
    with args.out.open('x') as stream: json.dump(result, stream, sort_keys=True, indent=2); stream.write('\n')
    print(result['status'] + ' count=' + str(len(results)))


if __name__ == '__main__': main()
