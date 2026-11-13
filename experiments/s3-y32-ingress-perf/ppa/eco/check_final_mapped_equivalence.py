#!/usr/bin/env python3
"""Independently audit original1064 -> final mapped connectivity with dead pruning.

Original standard cells/SRAM remain opaque. Exactly the native1796 dead-leaf
whitelist may disappear; all353 SRAM survive. Retained original leaf identities,
parameters, ports, bit widths and complete net partitions must match after only
native-proven identity buffers are contracted. Original unobservability is
recomputed from native pin directions, rather than trusting a plan PASS field.

The original flattened JSON may be reused only at its fixed campaign SHA and
with the source/script/log/tool receipt checked. A candidate cache is optional;
otherwise only the candidate is flattened. This does not prove RTL mapping,
cell-delay/clock/reset behavior, four-state bus resolution, or timing closure.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import check_buffer_equivalence as eq
import dead_cones

TOP = 'xu_soc_sysbus32_ppa_top'
ORIGINAL_SHA = '882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'
ORIGINAL_FLAT_SHA = '8c61146778fddbf29c57157da30bd6a35951830034a5081d80fdb7d6188a6a38'


def native_name(flat, cell):
    return dead_cones.native_instance(flat, cell)


def direction(directions, ref, port, bits, index):
    return dead_cones.pin_direction(directions, ref, port, bits, index)


def load_plan(path):
    raw = path.read_bytes()
    obj = json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)
    eq.require(obj.get('schema') == 'ingress1064-original-map-native-dead-cone-whitelist-v1' and
               obj.get('original_mapped_sha256') == ORIGINAL_SHA and
               obj.get('preserved_macro_count') == 353 and obj.get('removed_leaf_count') == 1796,
               'WRONG_FINAL_NATIVE_WHITELIST', str(path))
    return obj


def validate_whitelist(original, plan, directions, metadata, expected_count=1796, expected_state=36):
    cells = original['cells']
    selected, seen_native, waves = {}, set(), []
    for wave in plan['waves']:
        names = []
        for row in wave:
            flat, name, ref = row['flattened_instance'], row['native_instance'], row['reference']
            eq.require(flat in cells and flat not in selected and name not in seen_native,
                       'WHITELIST_MISSING_OR_DUPLICATE_LEAF', [flat, name])
            cell = cells[flat]
            eq.require(native_name(flat, cell) == name and cell['type'] == ref,
                       'WHITELIST_NATIVE_IDENTITY_MISMATCH', [flat, name, ref])
            eq.require(ref in metadata and row['is_sequential'] is metadata[ref]['is_sequential'],
                       'WHITELIST_NATIVE_STATE_CLASSIFICATION_MISMATCH', [name, ref])
            eq.require(not ref.startswith('RAMSP'), 'WHITELIST_SRAM_FORBIDDEN', name)
            selected[flat] = row; seen_native.add(name); names.append(flat)
        eq.require(names, 'EMPTY_WHITELIST_WAVE', len(waves))
        waves.append(names)
    eq.require(len(selected) == expected_count and
               sum(r['is_sequential'] for r in selected.values()) == expected_state,
               'WHITELIST_TOTAL_OR_STATE_COUNT', [len(selected), sum(r['is_sequential'] for r in selected.values())])
    outputs, interested = {}, set()
    for flat in selected:
        cell = cells[flat]; outs = set()
        for port, bits in cell['connections'].items():
            for i, bit in enumerate(bits):
                d = direction(directions, cell['type'], port, bits, i)
                eq.require(d != 'inout', 'WHITELIST_BIDIRECTIONAL_LEAF_FORBIDDEN', flat)
                if d == 'out': outs.add(eq.bit_node(bit))
        eq.require(outs and all(n[0] != 'constant' for n in outs),
                   'WHITELIST_NO_OUTPUT_OR_LITERAL_OUTPUT', flat)
        outputs[flat] = outs; interested.update(outs)
    top = {eq.bit_node(bit) for p in original['ports'].values() for bit in p['bits']}
    consumers = defaultdict(set)
    # Pin directions for every opaque original cell are required. A missing
    # library row cannot silently turn an input into an unobservable output.
    for flat, cell in cells.items():
        for port, bits in cell['connections'].items():
            for i, bit in enumerate(bits):
                d = direction(directions, cell['type'], port, bits, i)
                node = eq.bit_node(bit)
                if node in interested and d in {'in', 'inout'}: consumers[node].add(flat)
    active = set(cells)
    for index, wave in enumerate(waves):
        for flat in wave:
            for node in outputs[flat]:
                eq.require(node not in top and not (consumers[node] & active),
                           'WHITELIST_OUTPUT_NOT_DEAD_AT_DECLARED_WAVE',
                           dict(wave=index, cell=flat, node=list(node), consumers=sorted(consumers[node] & active)))
        active.difference_update(wave)
    return dict(selected=selected, outputs=outputs, consumers=consumers, top=top, waves=waves)


def identify_changes(original, candidate, whitelist, functions, directions, partial=False, expected_macros=353):
    oc, cc = original['cells'], candidate['cells']
    missing = set(oc) - set(cc); added = set(cc) - set(oc)
    eq.require(missing <= set(whitelist['selected']), 'UNAUTHORIZED_ORIGINAL_LEAF_DELETION', sorted(missing - set(whitelist['selected']))[:20])
    if not partial:
        eq.require(missing == set(whitelist['selected']), 'FINAL_EXPECTS_EXACT_COMPLETE_DEAD_WHITELIST',
                   dict(removed=len(missing), expected=len(whitelist['selected']), still_present=sorted(set(whitelist['selected']) - missing)[:20]))
    macros = {n for n, c in oc.items() if c['type'].startswith('RAMSP')}
    eq.require(len(macros) == expected_macros and macros <= set(cc),
               'ORIGINAL_SRAM_MACRO_LOSS_OR_COUNT', [len(macros), sorted(macros - set(cc))[:20]])
    eq.require({n for n, c in cc.items() if c['type'].startswith('RAMSP')} == macros,
               'SRAM_MACRO_ADDED_OR_CHANGED', 'candidate SRAM instance set differs')
    retained = set(oc) - missing
    for flat in missing:
        for node in whitelist['outputs'][flat]:
            eq.require(node not in whitelist['top'] and not (whitelist['consumers'][node] & retained),
                       'REMOVED_OUTPUT_STILL_FEEDS_RETAINED_LOGIC',
                       dict(cell=flat, consumers=sorted(whitelist['consumers'][node] & retained)))
    for name in retained:
        a, b = oc[name], cc[name]
        eq.require(native_name(name, a) == native_name(name, b),
                   'RETAINED_NATIVE_HIERARCHY_IDENTITY_CHANGED', name)
        eq.require(a['type'] == b['type'], 'RETAINED_OPAQUE_REFERENCE_CHANGED', name)
        eq.require(a.get('parameters', {}) == b.get('parameters', {}), 'RETAINED_OPAQUE_PARAMETERS_CHANGED', name)
    for name in added:
        cell = cc[name]
        eq.require(cell['type'] in functions and cell['type'] in eq.ALLOWED,
                   'ADDED_LEAF_NOT_NATIVE_IDENTITY_BUFFER', [name, cell['type']])
        eq.require(native_name(name, cell).rsplit('/', 1)[-1].startswith('XU_ECO_'),
                   'ADDED_BUFFER_OUTSIDE_RESERVED_ECO_NAMES', name)
    return missing, added, retained


def prove(original, candidate, whitelist, functions, directions, partial=False, expected_macros=353):
    missing, added, retained = identify_changes(original, candidate, whitelist, functions, directions, partial, expected_macros)
    # Shallow projection shares immutable cell records and avoids another
    # multi-hundred-MB JSON copy. The contraction checker never mutates them.
    projected = dict(original)
    projected['cells'] = {n: c for n, c in original['cells'].items() if n in retained}
    result = eq.compare(projected, candidate, functions, directions)
    result.update(exact_dead_whitelist_fully_removed=missing == set(whitelist['selected']),
                  removed_original_leaves=sorted(missing), removed_original_leaf_count=len(missing),
                  removed_type_counts=dict(Counter(original['cells'][n]['type'] for n in missing)),
                  deleted_original_state_count=sum(whitelist['selected'][n]['is_sequential'] for n in missing),
                  preserved_original_SRAM_count=expected_macros,
                  all_removed_outputs_unobservable_to_retained_original_logic_and_top=True)
    return result


def load_cache(source, receipt_path, side, top, original=False):
    receipt = json.loads(receipt_path.read_text())
    if 'flatten_runs' in receipt:
        eq.require(receipt.get('status') == 'BUFFER_CONTRACTION_STRUCTURAL_EQUIVALENCE_PASS', 'UNSUCCESSFUL_CACHE_RECEIPT', str(receipt_path))
        run, identity = receipt['flatten_runs'][side], receipt['inputs'][side]
    else:
        eq.require(original and side == 'original' and receipt.get('status') == 'DEAD_CONE_PLAN_SEALED_NOT_EXECUTED',
                   'UNSUPPORTED_CACHE_RECEIPT', str(receipt_path))
        run, identity = receipt['original_flatten'], receipt['original']
    eq.require(run.get('returncode') == 0 and run['source_sha256'] == identity['sha256'] == eq.sha(source),
               'CACHE_SOURCE_HASH_MISMATCH', str(source))
    directory = receipt_path.parent / side
    output, script, log = directory / 'flattened.json', directory / 'flatten.ys', directory / 'yosys.log'
    eq.require(eq.sha(output) == run['flattened_json_sha256'] and eq.sha(script) == run['script_sha256'] and eq.sha(log) == run['log_sha256'],
               'CACHE_ARTIFACT_HASH_MISMATCH', str(directory))
    executable = Path(receipt['yosys']['path'])
    eq.require(eq.sha(executable) == receipt['yosys']['sha256'], 'CACHE_YOSYS_EXECUTABLE_CHANGED', str(executable))
    expected_script = 'read_verilog ' + json.dumps(identity['path']) + '\nhierarchy -top ' + top + '\nflatten -noscopeinfo\nwrite_json ' + json.dumps(str(output.resolve())) + '\n'
    eq.require(script.read_text() == expected_script, 'CACHE_UNEXPECTED_FLATTEN_SCRIPT', str(script))
    if original:
        eq.require(run['source_sha256'] == ORIGINAL_SHA and run['flattened_json_sha256'] == ORIGINAL_FLAT_SHA,
                   'ORIGINAL_CACHE_NOT_FIXED_CAMPAIGN_MAP', str(directory))
    obj = json.loads(output.read_text())
    eq.require(top in obj['modules'], 'CACHE_TOP_ABSENT', top)
    mod = obj['modules'][top]
    for cell in mod.get('cells', {}).values():
        definition = obj['modules'].get(cell['type'])
        eq.require(definition is None or str(definition.get('attributes', {}).get('blackbox', '0')).strip('0') in {'1'},
                   'CACHE_HIERARCHY_NOT_FLATTENED', cell['type'])
    return mod, dict(mode='VERIFIED_EXISTING_FLATTEN_CACHE_NO_YOSYS_RERUN', receipt_path=str(receipt_path.resolve()),
                     receipt_sha256=eq.sha(receipt_path), flattened_path=str(output.resolve()),
                     flattened_sha256=eq.sha(output), native_source_sha256=eq.sha(source))


def merge_directions(first, second):
    merged = dict(first)
    for key, value in second.items():
        eq.require(key not in merged or merged[key] == value, 'NATIVE_DIRECTION_PROOFS_CONFLICT', list(key))
        merged[key] = value
    return merged


def self_test():
    def cell(ref, native, **connections):
        return dict(type=ref, parameters={}, attributes={'hdlname': native},
                    connections={p: [b] for p, b in connections.items()})
    mod = dict(ports={'a': dict(direction='input', bits=[1]), 'b': dict(direction='input', bits=[2]),
                      'y': dict(direction='output', bits=[3]), 'clk': dict(direction='input', bits=[4]),
                      'z': dict(direction='output', bits=[8])},
               cells={'live': cell('OPAQUE', 'live', A=1, O=3),
                      'head': cell('OPAQUE', 'head', A=1, O=5), 'tail': cell('OPAQUE', 'tail', A=5, O=6),
                      'state': cell('STATE', 'state', D=1, CK=4, Q=7),
                      'macro': cell('RAMSP', 'macro', D=1, CLK=4, Q=8)})
    dirs = {(r, p): d for r, rows in {'OPAQUE': {'A': 'in', 'O': 'out'}, 'STATE': {'D': 'in', 'CK': 'in', 'Q': 'out'},
            'RAMSP': {'D': 'in', 'CLK': 'in', 'Q': 'out'}}.items() for p, d in rows.items()}
    meta = {r: {'is_sequential': r in {'STATE', 'RAMSP'}} for r in {'OPAQUE', 'STATE', 'RAMSP'}}
    plan = {'waves': [[dict(native_instance=n, flattened_instance=n, reference=mod['cells'][n]['type'], is_sequential=meta[mod['cells'][n]['type']]['is_sequential'])
                       for n in wave] for wave in [['tail', 'state'], ['head']]]}
    info = validate_whitelist(mod, plan, dirs, meta, expected_count=3, expected_state=1)
    candidate = dict(mod, cells={n: c for n, c in mod['cells'].items() if n not in {'head', 'tail', 'state'}})
    functions = {'BUFV2_12TR40': {'input': 'I', 'output': 'Z'}}
    tests = []
    def check(name, cand, expected, partial=False):
        reason = None
        try: prove(mod, cand, info, functions, dirs, partial=partial, expected_macros=1); actual = True
        except eq.Rejected as e: actual, reason = False, e.code
        eq.require(actual == expected, 'SELF_TEST_EXPECTATION_FAILED', [name, expected, actual, reason])
        tests.append(dict(case=name, result='PASS', rejection=reason))
    check('exact_dead_cone_and_state_deletion', candidate, True)
    buffered = dict(candidate, cells=dict(candidate['cells']))
    buffered['cells']['live'] = dict(buffered['cells']['live'], connections={'A': [9], 'O': [3]})
    buffered['cells']['XU_ECO_test'] = cell('BUFV2_12TR40', 'XU_ECO_test', I=1, Z=9)
    check('deletions_plus_native_identity_buffer', buffered, True)
    check('incomplete_prune_rejected_in_final_mode', mod, False)
    check('intermediate_zero_prune_allowed_explicitly', mod, True, partial=True)
    for name, mutation in [('live_reference_change', lambda c: c['cells'].update(live=dict(c['cells']['live'], type='OTHER'))),
                           ('observable_leaf_deletion', lambda c: c['cells'].pop('live')),
                           ('SRAM_deletion', lambda c: c['cells'].pop('macro')),
                           ('live_data_reconnection', lambda c: c['cells'].update(live=dict(c['cells']['live'], connections={'A': [2], 'O': [3]}))),
                           ('retained_parameter_change', lambda c: c['cells'].update(live=dict(c['cells']['live'], parameters={'P': '1'})))]:
        bad = dict(candidate, cells=dict(candidate['cells'])); mutation(bad); check(name, bad, False)
    head_only = dict(mod, cells={n: c for n, c in mod['cells'].items() if n != 'head'})
    check('removed_head_still_drives_retained_tail', head_only, False, partial=True)
    return dict(status='SELF_TEST_PASS', synthetic_fixture=True, tests=tests,
                limitations=['Synthetic opaque-net fixtures; not a native EDA or actual final-map result'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original', type=Path)
    p.add_argument('--candidate', type=Path)
    p.add_argument('--original-cache-receipt', type=Path)
    p.add_argument('--candidate-cache-receipt', type=Path)
    p.add_argument('--original-function-proof', type=Path)
    p.add_argument('--candidate-function-proof', type=Path)
    p.add_argument('--prune-plan', type=Path)
    p.add_argument('--allow-partial-prune', action='store_true', help='Explicit intermediate audit; default requires all1796 original dead leaves removed')
    p.add_argument('--sanity-negatives', action='store_true', help='Check that deleting an actual retained SRAM or changing its ref is rejected, using the already loaded map')
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--yosys', default='yosys')
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    if not a.self_test and not all([a.original, a.candidate, a.original_cache_receipt, a.original_function_proof, a.candidate_function_proof, a.prune_plan]):
        p.error('original/candidate maps, original cache receipt, both native function proofs, and prune plan required')
    a.out_dir.mkdir(parents=True, exist_ok=False)
    try:
        if a.self_test: result = self_test()
        else:
            eq.require(eq.sha(a.original) == ORIGINAL_SHA, 'ORIGINAL_MAP_CAMPAIGN_SHA', str(a.original))
            original_functions, original_dirs, original_proof = eq.load_native_functions(a.original_function_proof)
            metadata, metadata_proof = dead_cones.load_metadata(a.original_function_proof)
            candidate_functions, candidate_dirs, candidate_proof = eq.load_native_functions(a.candidate_function_proof)
            directions = merge_directions(original_dirs, candidate_dirs)
            original, original_cache = load_cache(a.original, a.original_cache_receipt, 'original', TOP, original=True)
            plan = load_plan(a.prune_plan)
            eq.require(plan['native_proof']['standard_cell_db_sha256'] == original_proof['standard_cell_db_sha256'] and
                       plan['native_proof']['sram_db_sha256'] == original_proof['sram_db_sha256'],
                       'PRUNE_PLAN_LIBRARY_IDENTITY_MISMATCH', str(a.prune_plan))
            whitelist = validate_whitelist(original, plan, original_dirs, metadata)
            if a.candidate_cache_receipt:
                candidate, candidate_cache = load_cache(a.candidate, a.candidate_cache_receipt, 'candidate', TOP)
            else:
                executable = shutil.which(a.yosys); eq.require(executable, 'YOSYS_NOT_FOUND', a.yosys)
                candidate, candidate_cache = eq.flatten(a.candidate, TOP, a.out_dir / 'candidate', executable)
                candidate_cache['mode'] = 'ONLY_CANDIDATE_FLATTENED_ORIGINAL_CACHE_REUSED'
                candidate_cache['yosys'] = dict(path=executable, sha256=eq.sha(Path(executable)),
                                               version=subprocess.check_output([executable, '-V'], text=True).strip())
            result = prove(original, candidate, whitelist, candidate_functions, directions, a.allow_partial_prune)
            if a.sanity_negatives:
                macro = next(n for n, c in original['cells'].items() if c['type'].startswith('RAMSP'))
                tests = []
                for mode in ['delete_retained_SRAM', 'change_retained_SRAM_reference']:
                    bad = dict(candidate, cells=dict(candidate['cells']))
                    if mode == 'delete_retained_SRAM': bad['cells'].pop(macro)
                    else: bad['cells'][macro] = dict(bad['cells'][macro], type='OTHER_REFERENCE')
                    try: identify_changes(original, bad, whitelist, candidate_functions, directions, a.allow_partial_prune)
                    except eq.Rejected as error: tests.append(dict(case=mode, result='PASS', rejected_as=error.code))
                    else: raise eq.Rejected('ACTUAL_MAP_NEGATIVE_GUARD_ACCEPTED', mode)
                result['actual_map_negative_guard_checks'] = tests
            result.update(status='FINAL_MAPPED_DEAD_CONE_AND_BUFFER_EQUIVALENCE_PASS' if not a.allow_partial_prune else 'INTERMEDIATE_MAPPED_DEAD_CONE_AND_BUFFER_EQUIVALENCE_PASS',
                          inputs=dict(original=dict(path=str(a.original.resolve()), sha256=eq.sha(a.original)),
                                      candidate=dict(path=str(a.candidate.resolve()), sha256=eq.sha(a.candidate)),
                                      prune_plan=dict(path=str(a.prune_plan.resolve()), sha256=eq.sha(a.prune_plan))),
                          original_flatten=original_cache, candidate_flatten=candidate_cache,
                          original_native_proof=original_proof, candidate_native_proof=candidate_proof,
                          native_reference_metadata=metadata_proof,
                          independently_rechecked_dead_whitelist_count=1796,
                          independently_rechecked_dead_state_count=36,
                          removed_newly_added_buffers_scope='Any absent seed-added buffer needs no original-leaf deletion exemption; all PRESENT added buffers are native-proven and contracted',
                          limitations=['Mapped structural equivalence only; not RTL-to-mapped formal equivalence',
                              'Opaque original leaf functions, parameters and port identities are preserved; no invented cell/SRAM function',
                              'No timing, reset-release/metastability, clock-glitch, analog or four-state multi-driver signoff',
                              'Original dead-output unobservability is recomputed for the explicit whitelist; full fresh native STA remains required'])
    except (eq.Rejected, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        result = dict(status='FINAL_MAPPED_EQUIVALENCE_FAIL', failure=dict(code=error.code if isinstance(error, eq.Rejected) else type(error).__name__,
                      detail=error.detail if isinstance(error, eq.Rejected) else str(error)))
    result['schema'] = 'ingress1064-final-mapped-dead-cone-buffer-proof-v1'
    result['checker_sha256'] = eq.sha(Path(__file__))
    result['dependency_sha256'] = {n: eq.sha(Path(__file__).parent / n) for n in ['check_buffer_equivalence.py', 'dead_cones.py']}
    (a.out_dir / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(result['status'])
    if 'failure' in result: print(json.dumps(result['failure'], sort_keys=True))
    return int(result['status'] == 'FINAL_MAPPED_EQUIVALENCE_FAIL')


if __name__ == '__main__': sys.exit(main())
