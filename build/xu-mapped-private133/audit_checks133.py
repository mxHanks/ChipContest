#!/usr/bin/env python3
"""Exercise the received-result auditor on unchanged actual116; no S2c receipt."""
import copy
import json

import audit_actual133 as audit
import extract_private133 as xu

checks = []
record = json.loads((xu.HERE / 'mechanism116-v3/inventory133.json').read_text())


def rejects(name, value, mechanism=True):
    try:
        audit.inspect(value, mechanism)
    except (ValueError, KeyError, TypeError):
        checks.append(name)
    else:
        raise AssertionError(name)


result = audit.inspect(record, mechanism_only=True)
assert result['status'] == 'OTHER_NETLIST116_AUDIT_MECHANISM_ONLY_ALL60_RUNTIME_GATES_PENDING'
assert result['private_gates_discharged'] == 0 and result['original_private_gates_remaining'] == 60
checks.append('actual116 mechanism validates all60 schema with zero target/runtime claims')
rejects('actual116 cannot pass default actual-S2c audit', record, mechanism=False)
for name, mutate in [
    ('changed helper hash rejected', lambda r: r['helper_before']['extract_private133.py'].update(sha256='0' * 64)),
    ('altered mapped input rejected', lambda r: r['mapped_after'].update(bytes=1)),
    ('gate discharge rejected', lambda r: r.update(private_gates_discharged=1)),
    ('target qualification claim rejected', lambda r: r.update(target_mapping_proved=True)),
    ('missing private reference rejected', lambda r: r['references'].pop()),
    ('duplicate private reference rejected', lambda r: r['references'].__setitem__(1, copy.deepcopy(r['references'][0]))),
    ('width mismatch rejected', lambda r: r['references'][0]['endpoint_lookups'][0].update(width=17)),
    ('unrelated named endpoint substitution rejected', lambda r: r['references'][0]['endpoint_lookups'][0].update(path='u_soc.unrelated')),
    ('classification count drift rejected', lambda r: r['classification_counts'].update({xu.CLASS1: 999})),
]:
    altered = copy.deepcopy(record)
    mutate(altered)
    rejects(name, altered)

altered = copy.deepcopy(record)
row = next(r for r in altered['references'] if r['original_path'] == 'row_start_accept')
row['classification'] = xu.CLASS2
rejects('source-only unbound expression cannot pass physical reconstruction audit', altered)

altered = copy.deepcopy(record)
row = next(r for r in altered['references'] if r['original_path'] == 'bias_regs')
row['endpoint_lookups'].pop()
rejects('partial eight-lane bias endpoint set rejected', altered)

print(json.dumps(dict(status='PASS_LOCAL_AUDIT_MECHANISMS_ONLY_NO_ACTUAL_S2C_RESULT',
                      count=len(checks), checks=checks), indent=2))
