#!/usr/bin/env python3
"""Audit received133 static inventory; never discharge runtime acceptance gates."""
import argparse
from collections import Counter
import json
from pathlib import Path

import extract_private133 as xu

EXPECTED_HELPERS = {
    'extract_private133.py': '13806e9309e6de5c40314f294ddf92aecfb7a6f3009cf0733fbcae3e3633577b',
    'mapped_parser123.py': xu.PARSER_SHA,
    'reference-candidates115.json': xu.CANDIDATES_SHA,
    'original111-private-plan.json': xu.PLAN_SHA,
}


def read(path):
    return json.loads(Path(path).read_text())


def complete(endpoints):
    return bool(endpoints) and all(p is not None and p.get('exact_width') is True for p in endpoints)


def check_endpoint(endpoint, width):
    xu.need(endpoint['width'] == width and endpoint['expected_width'] == width and
            endpoint['exact_width'] is True, 'width or exact-width claim differs')
    xu.need(endpoint['kind'] in ('port', 'named_net', 'escaped_scalar_bundle'), 'unknown endpoint kind')
    xu.need(endpoint['module'] and endpoint['path'] == endpoint['scope'] + '.' + endpoint['net'],
            'endpoint scope/net identity differs')
    if endpoint['kind'] == 'port':
        xu.need(endpoint['direction'] in ('input', 'output', 'inout'), 'port direction unknown')
    if endpoint['kind'] == 'escaped_scalar_bundle':
        xu.need(endpoint['bit_order'] == 'MSB_FIRST' and endpoint['bits'] ==
                [endpoint['path'] + '[' + str(i) + ']' for i in range(width - 1, -1, -1)],
                'escaped scalar bit set or order differs')


def check_named_binding(reference, endpoints):
    xu.need(len(endpoints) == reference['lanes'] and complete(endpoints),
            'incomplete named endpoint bit/lane set')
    macro = xu.SCOPES[reference['original_macro']] + '.'
    candidate_paths = [macro + p for p in xu.expanded_candidates(reference)]
    original_paths = ([macro + reference['original_path'] + '[' + str(i) + ']' for i in range(8)]
                      if reference['lanes'] == 8 else [macro + reference['original_path']])
    xu.need([e['path'] for e in endpoints] in [candidate_paths, original_paths],
            'lookup substituted an unrelated named endpoint')
    for endpoint in endpoints:
        check_endpoint(endpoint, reference['width_each'])


def inspect(record, mechanism_only=False):
    expected_status = ('OTHER_NETLIST116_PARSER_MECHANISM_ONLY' if mechanism_only else
                       'S2C_PRIVATE_TARGET_STATIC_INVENTORY_NOT_QUALIFIED')
    xu.need(record['status'] == expected_status,
            'not an actual default-mode S2c133 result')
    xu.need(record['mapped_before'] == record['mapped_after'], 'mapped input not frozen')
    mapped = record['mapped_before']
    xu.need(mapped['sha256'] == (xu.MECHANISM_SHA if mechanism_only else xu.TARGET_SHA) and
            mapped['bytes'] == (13671648 if mechanism_only else xu.TARGET_BYTES),
            'wrong target mapped input')
    xu.need(mechanism_only or mapped['input_path'].endswith('/s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v'),
            'unexpected selected target input path')
    xu.need(record['helper_before'] == record['helper_after'], 'helper input not frozen')
    xu.need(set(record['helper_before']) == set(EXPECTED_HELPERS), 'helper set differs')
    for name, digest in EXPECTED_HELPERS.items():
        xu.need(record['helper_before'][name]['sha256'] == digest and
                xu.digest(xu.HERE / name) == digest, 'actual helper bytes differ: ' + name)
    xu.need(record['original_reference_count'] == 72 and record['original_preload_statements'] == 288 and
            record['original_private_gates_remaining'] == 60 and record['private_gates_discharged'] == 0 and
            record['runtime_adapters_implemented'] == 0 and record['target_mapping_proved'] is False,
            'original gates or qualification boundary differs')
    refs = xu.load_references()
    source_index = {(r['original_macro'], r['original_path']): r for r in refs}
    selected = {(r['original_macro'], r['original_path']): r for r in record['references']}
    xu.need(len(record['references']) == len(selected) == 60 and set(selected) ==
            {(r['original_macro'], r['original_path']) for r in refs}, 'private60 identity set differs')
    counts = Counter()
    by_macro = {macro: Counter() for macro in xu.SCOPES}
    runtime_pending = []
    for reference in refs:
        key = (reference['original_macro'], reference['original_path'])
        row = selected[key]
        xu.need(all(row.get(k) == v for k, v in reference.items()), 'frozen source reference changed: ' + str(key))
        xu.need(row['qualification'] == 'NOT_QUALIFIED_RUNTIME_FOUR_STATE_AND_CORRESPONDENCE_PENDING',
                'runtime qualification boundary differs: ' + str(key))
        classification = row['classification']
        xu.need(classification in (xu.CLASS1, xu.CLASS2, xu.CLASS3), 'unknown classification')
        endpoints = row['endpoint_lookups']
        xu.need(len(endpoints) == reference['lanes'], 'incomplete endpoint lane inventory')
        if classification == xu.CLASS1:
            xu.need(complete(endpoints), 'retained-name claim has unbound/width-mismatched endpoint')
            check_named_binding(reference, endpoints)
        elif classification == xu.CLASS2:
            xu.need(not complete(endpoints), 'reconstruction should not hide a complete named lookup')
            ff = row.get('physical_ff_candidates', [])
            operands = row.get('physical_expression_operand_lookups', {})
            if ff:
                xu.need(reference['lanes'] == 1 and len(ff) == reference['width_each'],
                        'incomplete physical FF bit/lane candidate set')
                original = reference['original_path']
                parent, _, signal = original.rpartition('.') if '.' in original else ('', '', original)
                scope = xu.SCOPES[reference['original_macro']] + ('.' + parent if parent else '')
                expected_instances = ([scope + '.' + signal + '_reg'] if reference['width_each'] == 1 else
                                      [scope + '.' + signal + '_reg[' + str(i) + ']'
                                       for i in range(reference['width_each'] - 1, -1, -1)])
                xu.need([f['instance'] for f in ff] == expected_instances, 'unrelated physical FF candidate')
                xu.need(all(f['candidate_output_pins'] and
                            set(f['candidate_output_pins']) <= {'Q', 'QN'} and
                            f['semantics'] == 'PIN_NAME_CANDIDATE_NOT_LIBRARY_OR_FORMAL_PROOF' for f in ff),
                        'FF candidate overclaims library or polarity proof')
            else:
                expected = xu.EXPRESSION_OPERANDS.get(reference['original_path'])
                xu.need(expected is not None and set(operands) == set(expected) and
                        all(complete(ps) for ps in operands.values()), 'unbound expression called physical reconstruction')
                for name, ps in operands.items():
                    xu.need(len(ps) == 1, 'expression operand is not scalar/vector single endpoint')
                    operand = source_index.get(('ACCEL', name),
                        dict(original_macro='ACCEL', original_path=name, candidate=name,
                             width_each=expected[name], lanes=1))
                    check_named_binding(operand, ps)
        else:
            xu.need(not complete(endpoints), 'complete retained endpoint wrongly marked absent')
        counts[classification] += 1
        by_macro[reference['original_macro']][classification] += 1
        runtime_pending.append(dict(original_macro=key[0], original_path=key[1],
                                    static_classification=classification,
                                    runtime_status='ORIGINAL_GATE_PENDING'))
    xu.need(dict(counts) == record['classification_counts'], 'reported classification count differs')
    return dict(status=('OTHER_NETLIST116_AUDIT_MECHANISM_ONLY_ALL60_RUNTIME_GATES_PENDING' if mechanism_only else
                        'ACTUAL_S2C133_STATIC_INVENTORY_AUDITED_ALL60_RUNTIME_GATES_PENDING'),
                classification_counts=dict(counts), by_macro={k: dict(v) for k, v in by_macro.items()},
                design_modules=record['design_modules'], elaborated_scopes=record['elaborated_scopes'],
                private_gates_discharged=0, original_private_gates_remaining=60,
                target_mapping_proved=False, runtime_pending=runtime_pending,
                limitation='Reports are checked against frozen extractor inputs; native handles, four-state values, sampling/polarity and original assertions still require actual runtime evidence.')


def run(inventory, log, returncode, out, mechanism_only=False):
    out = Path(out)
    xu.need(not out.exists(), 'audit output must be new')
    input_paths = [('inventory', inventory), ('log', log), ('returncode', returncode)]
    before = {k: xu.parser.identity(p) for k, p in input_paths}
    record = read(inventory)
    xu.need(Path(returncode).read_text().strip() == '0', 'native extractor command failed')
    summary = read(log)
    summary_keys = ['status', 'design_modules', 'elaborated_scopes',
                    'classification_counts', 'original_private_gates_remaining']
    xu.need(summary == {k: record[k] for k in summary_keys}, 'native stdout summary differs')
    result = inspect(record, mechanism_only)
    after = {k: xu.parser.identity(p) for k, p in input_paths}
    xu.need(before == after, 'received result changed during audit')
    result['received_inputs_before'] = before
    result['received_inputs_after'] = after
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'classification_counts',
                                           'original_private_gates_remaining']}))


if __name__ == '__main__':
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--inventory', type=Path, required=True)
    arg.add_argument('--log', type=Path, required=True)
    arg.add_argument('--returncode', type=Path, required=True)
    arg.add_argument('--out', type=Path, required=True)
    arg.add_argument('--mechanism-only', action='store_true',
                     help='Local actual116 audit mechanism only; never a S2c target receipt')
    args = arg.parse_args()
    run(args.inventory, args.log, args.returncode, args.out, args.mechanism_only)
