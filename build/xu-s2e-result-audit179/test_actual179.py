#!/usr/bin/env python3
"""Negative audit mutations in memory against an actual returned171 packet.

The original packet/extraction are read-only. These are auditor rejection
checks, not modified native inputs, EDA runs or fabricated successful evidence.
"""
import argparse
import copy
import json
from pathlib import Path
import audit179 as a


class View:
    def __init__(self, base, documents):
        self.base = base
        self.documents = documents
        self.omitted = copy.deepcopy(base.omitted)
    def has(self, name): return self.base.has(name)
    def path(self, name): return self.base.path(name)
    def check(self, name, receipt=None, omitted=False): return self.base.check(name, receipt, omitted)
    def json(self, name): return self.documents.get(name, self.base.json(name))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root', type=Path, required=True); p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--sha256', required=True); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    a.need(not args.out.exists(), 'fresh output file required')
    refs = a.reference_data(); ev = a.Evidence(args.evidence_root, args.archive, args.sha256)
    names = {key: a.ROOT0 + '/' + key + '.json' for key in ['prepared', 'execution', 'summary', 'result']}
    originals = {name: ev.json(name) for name in names.values()}
    completed = a.campaign(ev, a.ROOT0, [0], refs)
    a.need(completed['complete'], 'real task0 positive must audit before negative checks')
    checks = ['REAL_TASK0_AUDITED']

    def reject(label, mutation, ids=None):
        docs = copy.deepcopy(originals)
        mutation({key: docs[name] for key, name in names.items()})
        try:
            result = a.campaign(View(ev, docs), a.ROOT0, [0] if ids is None else ids, refs)
            if not result['complete']:
                checks.append(label)
                return
        except (ValueError, KeyError):
            checks.append(label)
            return
        raise AssertionError('audit accepted poisoned in-memory evidence: ' + label)

    reject('RECORDED_INPUT_AFTER_CHANGED_REJECTED',
           lambda d: d['execution']['input_sha256_after'].update({'poison': '0' * 64}))
    reject('CAPTURE89_TARGET155_CONFLATION_REJECTED',
           lambda d: d['prepared']['target_mapped_context']['netlist'].update(sha256=a.OLDNET))
    reject('BORROWED_AREA_REJECTED',
           lambda d: d['prepared']['target_mapped_context']['area'].update(accelerator_mm2='0.2950003804'))
    reject('REORDERED_SVF_CHAIN_REJECTED',
           lambda d: d['prepared']['target_mapped_context']['svf_chain'].reverse())
    reject('ZERO_UNKNOWN_SUMMARY_REJECTED',
           lambda d: d['prepared']['tasks'][0]['measured_summary'].update(q_tx_positive=0))
    reject('TASK0_CANNOT_IMPERSONATE_FULL12', lambda d: None, list(range(12)))
    reject('PROPAGATED_SCOPE_OVERRIDE_REJECTED',
           lambda d: d['prepared']['target_mapped_context']['clock_scope'].update(sha256='0' * 64))
    reject('FALSE166_PRODUCER_REJECTED',
           lambda d: d['prepared']['producer'].update(sha256='0' * 64))

    def poison_rc(d):
        d['execution']['tasks'][0]['execution']['returncode'] = 1
        d['summary']['tasks'] = copy.deepcopy(d['execution']['tasks'])
    reject('NATIVE_NONZERO_RC_REJECTED', poison_rc)

    def poison_power(d):
        d['execution']['tasks'][0]['diagnostic']['power_components']['total_power_w'] = '0.0001'
        d['summary']['tasks'] = copy.deepcopy(d['execution']['tasks'])
    reject('DIAGNOSTIC_POWER_MISMATCH_REJECTED', poison_power)

    pin_name = a.ROOT0 + '/task_00/sram-pins-before.rpt'
    pin_receipt = originals[names['execution']]['tasks'][0]['reports']['sram-pins-before.rpt']
    for label, key, value in [('SERVER_BOUNDED_SHA_MISMATCH_REJECTED', 'observed_bytes_sha256', '0' * 64),
                              ('CHANGED_SOURCE_METADATA_REJECTED', 'metadata_unchanged_during_read', False)]:
        poisoned = copy.copy(ev)
        poisoned.omitted = copy.deepcopy(ev.omitted)
        poisoned.omitted[pin_name][key] = value
        try:
            poisoned.check(pin_name, pin_receipt, 'pin')
        except ValueError:
            checks.append(label)
        else:
            raise AssertionError('audit accepted bad omitted snapshot: ' + label)

    final = a.audit(ev, refs)
    a.need(final['comparison']['analysis_method_mismatch'] is True and
           final['comparison']['controlled_comparison_status'] == 'CONTROLLED_COMPARISON_PENDING' and
           final['comparison']['diagnostic_energy_reduction_vs_s2c_percent'] is None, 'cross-method percentage suppressed')
    checks.append('CROSS_METHOD_GAIN_SUPPRESSED')
    if not final['full12']['complete']:
        a.need(final['comparison']['same155_final']['diagnostic_energy12_j'] is None, 'partial full12 energy must remain null')
        checks.append('PARTIAL_FULL12_AGGREGATE_NULL')
    output = dict(schema='xu-audit179-actual-negative-check-v1', qualification='NOT_QUALIFIED',
                  semantics='IN_MEMORY_AUDITOR_MUTATIONS_ONLY_NOT_EDA_EXECUTIONS', archive=ev.report['archive'],
                  passed=len(checks), checks=checks)
    args.out.write_text(json.dumps(output, sort_keys=True, indent=2) + '\n')
    print(json.dumps(dict(passed=len(checks), output=str(args.out)), sort_keys=True))


if __name__ == '__main__': main()
