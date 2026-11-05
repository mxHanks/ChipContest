#!/usr/bin/env python3
"""Read-only structural inventory of all original111 private observations.

This does not alter the DUT, generate a passing adapter, run a simulator, or
discharge any original fatal/check. No vendor library/model body is read.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import mapped_parser123 as parser

HERE = Path(__file__).resolve().parent
TARGET_SHA = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
TARGET_BYTES = 14199670
MECHANISM_SHA = '16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292'
PARSER_SHA = '688aa9aa49b85c08d493e9cf50b150376f311acfa07bfa0245d80c14c100b4e9'
CANDIDATES_SHA = '156d575b34f5060cbeee2371217874f0549ff7e9529aaa99ca030f5932c9cca9'
PLAN_SHA = '6f3f337ddbd93cb103182d82ca4b821d9c99cdf3f7b594da1195c4ff98ccb486'
BASE = 'u_soc.u_e203_subsys_top.u_e203_subsys_main.'
SCOPES = {
    'ACCEL': BASE + 'u_e203_subsys_perips.u_accel_icb_slave',
    'EXU': BASE + 'u_e203_cpu_top.u_e203_cpu.u_e203_core.u_e203_exu',
    'XU_HCLK': BASE + 'u_e203_subsys_hclkgen',
}
CLASS1 = '1_RETAINED_NAMED_ENDPOINT'
CLASS2 = '2_PHYSICAL_RECONSTRUCTION_CANDIDATE'
CLASS3 = '3_NOT_LOCATED_OR_FORMAL_CORRESPONDENCE_NEEDED'
SOURCE1 = {'existing_core_port_alias', 'existing_nested_module_port',
           'existing_commit_input_port', 'existing_hclkgen_input_port'}
EXPRESSION_OPERANDS = {
    'busy': {'manual_busy': 1, 'row_active': 1, 'row_start': 1},
    'row_start_accept': {'cmd_valid': 1, 'cmd_ready': 1, 'cmd_read': 1,
                         'cmd_addr': 32, 'cmd_wmask': 4, 'cmd_wdata': 32,
                         'cache_enable': 1, 'busy': 1, 'row_start': 1,
                         'core_start': 1, 'x_load_wen': 1, 'w_load_wen': 1,
                         'row_count': 2},
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_references():
    need(digest(HERE / 'original111-private-plan.json') == PLAN_SHA, 'original111 plan differs')
    need(digest(HERE / 'reference-candidates115.json') == CANDIDATES_SHA, 'source115 candidates differ')
    plan = json.loads((HERE / 'original111-private-plan.json').read_text())
    candidates = json.loads((HERE / 'reference-candidates115.json').read_text())
    pending = {(r['original_macro'], r['original_path']) for r in plan['original_references']
               if 'pending' in r['handling']}
    rows = [dict(r) for r in candidates['references']
            if (r['original_macro'], r['original_path']) in pending]
    need(len(plan['original_references']) == 72 and len(pending) == 60 and len(rows) == 60,
         'original72/private60 inventory changed')
    need({(r['original_macro'], r['original_path']) for r in rows} == pending,
         'private reference identity differs')
    return rows


def elaborate(designs, top):
    scopes = {}

    def walk(module, parts, ancestors):
        need(module not in ancestors, 'recursive design hierarchy')
        scope = '.'.join(parts)
        need(scope not in scopes, 'ambiguous textual hierarchical name: ' + scope)
        scopes[scope] = designs[module]
        for r in designs[module]['records']:
            if r['kind'] == 'instance' and r['type'] in designs:
                # Escaped instance identifiers are atomic. Never split at '.'
                # inside names such as regfile[3].rfno0.rf_dffl.
                walk(r['type'], parts + (r['name'],), ancestors + (module,))
    need(top in designs, 'missing exact top module')
    walk(top, (), ())
    return scopes


def width(bounds):
    return abs(bounds[0] - bounds[1]) + 1 if bounds is not None else 1


def locate(scopes, full, expected):
    # Longest complete scope match also handles escaped instance identifiers.
    for scope in sorted(scopes, key=len, reverse=True):
        prefix = scope + '.' if scope else ''
        if not full.startswith(prefix):
            continue
        net = full[len(prefix):]
        module = scopes[scope]
        if net in module['widths']:
            actual = width(module['widths'][net])
            return dict(path=full, scope=scope, module=module['name'], net=net,
                        kind='port' if net in module['ports'] else 'named_net',
                        direction=module['ports'].get(net), width=actual,
                        expected_width=expected, exact_width=actual == expected)
        # Synthesis may flatten an unpacked RTL array to escaped scalar nets.
        bits = [net + '[' + str(i) + ']' for i in range(expected - 1, -1, -1)]
        if expected > 1 and all(b in module['widths'] and width(module['widths'][b]) == 1 for b in bits):
            return dict(path=full, scope=scope, module=module['name'], net=net,
                        kind='escaped_scalar_bundle', width=expected,
                        expected_width=expected, exact_width=True,
                        bit_order='MSB_FIRST', bits=[prefix + b for b in bits])
    return None


def expanded_candidates(row):
    candidate = row['candidate']
    if '{0..7}' in candidate:
        return [candidate.replace('{0..7}', str(i)) for i in range(8)]
    return [candidate]


def bound_endpoints(scopes, row):
    macro_scope = SCOPES[row['original_macro']]
    endpoints = [locate(scopes, macro_scope + '.' + p, row['width_each'])
                 for p in expanded_candidates(row)]
    if not all(p and p['exact_width'] for p in endpoints):
        original_paths = ([row['original_path'] + '[' + str(i) + ']' for i in range(8)]
                          if row['lanes'] == 8 else [row['original_path']])
        originals = [locate(scopes, macro_scope + '.' + p, row['width_each']) for p in original_paths]
        if all(p and p['exact_width'] for p in originals):
            return originals
    return endpoints


def ff_candidates(scopes, macro_scope, original, expected):
    # Candidate identity by retained instance name only; polarity semantics,
    # runtime value, and formal source correspondence remain to be proved.
    if '.' in original:
        parent, _, signal = original.rpartition('.')
        scope = macro_scope + '.' + parent
    else:
        scope, signal = macro_scope, original
    module = scopes.get(scope)
    if module is None:
        return []
    desired = [signal + '_reg'] if expected == 1 else [signal + '_reg[' + str(i) + ']'
                                                       for i in range(expected - 1, -1, -1)]
    instances = {r['name']: r for r in module['records'] if r['kind'] == 'instance'}
    if not all(n in instances for n in desired):
        return []
    result = []
    for n in desired:
        record = instances[n]
        outputs = {p: expr for p, expr in record['pins'].items() if p in ('Q', 'QN')}
        if not outputs:
            return []
        result.append(dict(instance=scope + '.' + n, cell=record['type'],
                           candidate_output_pins=outputs,
                           semantics='PIN_NAME_CANDIDATE_NOT_LIBRARY_OR_FORMAL_PROOF'))
    return result


def source_strategy(row):
    cat = row['category']
    if cat in SOURCE1:
        return '1_EXISTING_RTL_PORT_OR_ALIAS_LOOKUP_FIRST'
    if cat == 'literal_wrapper_combinational_expression':
        return '2_RECONSTRUCT_FROM_SAME_NETLIST_PHYSICAL_OPERANDS'
    return '1_RETAINED_NAME_THEN_2_PHYSICAL_FF_OR_3_FORMAL'


def inspect(text, references, top='xu_soc_ppa_top'):
    designs = parser.modules(text)
    scopes = elaborate(designs, top)
    reference_index = {(r['original_macro'], r['original_path']): r for r in references}
    result = []
    for row in references:
        item = dict(row)
        item['source_strategy'] = source_strategy(row)
        macro_scope = SCOPES[row['original_macro']]
        endpoints = bound_endpoints(scopes, row)
        item['endpoint_lookups'] = endpoints
        item['qualification'] = 'NOT_QUALIFIED_RUNTIME_FOUR_STATE_AND_CORRESPONDENCE_PENDING'
        if all(p and p['exact_width'] for p in endpoints):
            item['classification'] = CLASS1
        else:
            ffs = ff_candidates(scopes, macro_scope, row['original_path'], row['width_each'])
            item['physical_ff_candidates'] = ffs
            if ffs:
                item['classification'] = CLASS2
            elif row['category'] == 'literal_wrapper_combinational_expression':
                operands = {}
                for signal, bits in EXPRESSION_OPERANDS[row['original_path']].items():
                    operand = reference_index.get(('ACCEL', signal),
                        dict(original_macro='ACCEL', original_path=signal, candidate=signal,
                             width_each=bits, lanes=1))
                    operands[signal] = bound_endpoints(scopes, operand)
                item['physical_expression_operand_lookups'] = operands
                complete = all(all(p and p['exact_width'] for p in ps) for ps in operands.values())
                item['classification'] = CLASS2 if complete else CLASS3
                item['reconstruction_status'] = ('ALL_PHYSICAL_OPERAND_NAMES_BOUND_EXPRESSION_NOT_EXECUTED'
                                                 if complete else 'SOURCE_EXPRESSION_KNOWN_PHYSICAL_OPERANDS_MISSING')
            else:
                item['classification'] = CLASS3
                item['missing_meaning'] = 'ABSENCE_FROM_NAME_LOOKUP_IS_NOT_PROOF_OF_SYNTHESIS_REMOVAL'
        result.append(item)
    return dict(design_modules=len(designs), elaborated_scopes=len(scopes),
                classification_counts=dict(Counter(r['classification'] for r in result)),
                references=result)


def run(mapped, out, mechanism_only=False):
    need(digest(HERE / 'mapped_parser123.py') == PARSER_SHA, 'frozen123 parser differs')
    helper_before = {p: parser.identity(HERE / p) for p in
                     ['mapped_parser123.py', 'reference-candidates115.json',
                      'original111-private-plan.json', 'extract_private133.py']}
    mapped = Path(mapped).resolve(strict=True)
    out = Path(out).absolute()
    need(not out.exists(), 'output must be new; do not overwrite historical evidence')
    need(mapped not in out.parents and out != mapped.parent,
         'output must be distinct from immutable input directory')
    before = parser.identity(mapped)
    expected = MECHANISM_SHA if mechanism_only else TARGET_SHA
    need(before['sha256'] == expected, 'wrong mapped hash; target mapping not established')
    if not mechanism_only:
        need(before['bytes'] == TARGET_BYTES, 'wrong target mapped length')
    refs = load_references()
    result = inspect(mapped.read_text(), refs)
    after = parser.identity(mapped)
    need(before == after, 'mapped source mutated during inventory')
    helper_after = {p: parser.identity(HERE / p) for p in helper_before}
    need(helper_before == helper_after, 'helper source mutated during inventory')
    result.update(status='OTHER_NETLIST116_PARSER_MECHANISM_ONLY' if mechanism_only
                  else 'S2C_PRIVATE_TARGET_STATIC_INVENTORY_NOT_QUALIFIED',
                  target_mapping_proved=False, runtime_adapters_implemented=0,
                  private_gates_discharged=0, original_private_gates_remaining=60,
                  original_reference_count=72, original_preload_statements=288,
                  mapped_before=before, mapped_after=after,
                  helper_before=helper_before, helper_after=helper_after)
    out.mkdir(parents=True)
    (out / 'inventory133.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'design_modules', 'elaborated_scopes',
                                           'classification_counts', 'original_private_gates_remaining']}))
    return result


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--mapped', type=Path, required=True)
    arg.add_argument('--out', type=Path, required=True)
    arg.add_argument('--mechanism-only', action='store_true',
                     help='Allow exact actual116 hash, never target S2c mapping proof')
    args = arg.parse_args()
    run(args.mapped, args.out, args.mechanism_only)


if __name__ == '__main__':
    main()
