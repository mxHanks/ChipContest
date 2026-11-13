#!/usr/bin/env python3
"""Seal exact original-map dead-cone proof and deterministic guarded DC edits."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import check_buffer_equivalence as eq
import dead_cones
from prepare import FILES
from run_prune_stage import emit, verify_plan, MAPPED_SHA


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--dead-plan-dir', type=Path, required=True)
    p.add_argument('--native-proof', type=Path, required=True)
    p.add_argument('--native-inventory', type=Path, required=True)
    a = p.parse_args()
    source = Path(__file__).resolve().parent; plans = a.dead_plan_dir.resolve()
    result_path = plans / 'result.json'; result = json.loads(result_path.read_text())
    eq.require(result.get('status') == 'DEAD_CONE_PLAN_SEALED_NOT_EXECUTED' and
               result.get('original', {}).get('sha256') == MAPPED_SHA and result.get('protect_sequential') is False and
               result.get('removed_leaf_count') == 1796, 'WRONG_ORIGINAL_DEAD_PLAN', str(plans))
    flat_path = plans / 'original' / 'flattened.json'
    eq.require(eq.sha(flat_path) == result['original_flatten']['flattened_json_sha256'], 'FLATTENED_ORIGINAL_PLAN_DRIFT', str(flat_path))
    original = json.loads(flat_path.read_text())['modules']['xu_soc_sysbus32_ppa_top']
    functions, directions, proof_identity = eq.load_native_functions(a.native_proof)
    metadata, meta_identity = dead_cones.load_metadata(a.native_proof)
    eq.require(proof_identity == result['native_function_and_direction_proof'] and
               meta_identity['sha256'] == result['native_reference_metadata']['sha256'],
               'PLAN_NATIVE_PROOF_IDENTITY_CHANGED', str(a.native_proof))
    info = dead_cones.topology(original, directions, metadata, allow_state=True, expected_macros=353)
    eq.require(info['waves'] == result['waves'], 'DEAD_PLAN_RECOMPUTATION_DIFFERS', str(plans))
    inventory = list(csv.DictReader(a.native_inventory.read_text().splitlines(), delimiter='\t'))
    constants = [x for x in inventory if x['classification'] == 'native_constant']
    eq.require(all(x['reference'] in {'**logic_0**', '**logic_1**'} for x in constants),
               'UNRECOGNIZED_NATIVE_CONSTANT', constants[:2])
    leaves = [x for x in inventory if x['classification'] != 'native_constant']
    native = {x['instance']: x['reference'] for x in leaves}
    eq.require(len(native) == len(leaves) == len(original['cells']), 'NATIVE_INVENTORY_LEAF_COUNT', [len(native), len(original['cells'])])
    all_names = {}
    for flat, cell in original['cells'].items():
        name = dead_cones.native_instance(flat, cell)
        eq.require(not name.rsplit('/', 1)[-1].startswith('XU_ECO_'),
                   'ORIGINAL_LEAF_USES_RESERVED_ECO_PREFIX', name)
        eq.require(name not in all_names and native.get(name) == cell['type'], 'HDLNAME_NATIVE_INVENTORY_MISMATCH', [flat, name, cell['type']])
        all_names[name] = flat
    plan = dict(schema='ingress1064-original-map-native-dead-cone-whitelist-v1', original_mapped_sha256=MAPPED_SHA,
                original_proof_result_sha256=eq.sha(result_path), original_flattened_sha256=eq.sha(flat_path),
                native_proof=proof_identity, native_reference_metadata=meta_identity,
                native_inventory_sha256=eq.sha(a.native_inventory), preserved_macro_count=353,
                removed_leaf_count=len(info['removed']), waves=[])
    for wave in info['waves']:
        plan['waves'].append([dict(native_instance=dead_cones.native_instance(n, original['cells'][n]),
                                  flattened_instance=n, reference=original['cells'][n]['type'],
                                  is_sequential=metadata[original['cells'][n]['type']]['is_sequential']) for n in wave])
    verify_plan(plan); payload = emit(plan)
    plan['generated_tcl_sha256'] = hashlib.sha256(payload).hexdigest()
    origins = {name: source / name for name in FILES}
    for name in ['run_prune_stage.py', 'prepare_prune.py', 'pt_prune_reload.tcl', 'dead_cones.py']:
        origins[name] = source / name
    origins['development_controls.py'] = source.parent / 'run_once.py'
    origins['profiles.py'] = source.parent / 'profiles.py'
    for name, path in origins.items():
        text = path.read_text()
        if name.endswith('.py'): compile(text, name, 'exec')
        if name.endswith('.tcl'):
            checked = subprocess.run(['tclsh'], input='set f [open {' + str(path) + '} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n', text=True, capture_output=True)
            eq.require(checked.returncode == 0, 'TCL_INCOMPLETE', name)
    checked = subprocess.run(['tclsh'], input='set s {' + payload.decode() + '}\nif {![info complete $s]} {exit 2}\n', text=True, capture_output=True)
    eq.require(checked.returncode == 0, 'DETERMINISTIC_TCL_INCOMPLETE', checked.stderr)
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, path in origins.items(): shutil.copyfile(path, a.out / name)
    proof = json.loads(a.native_proof.read_text()); proof_out = a.out / 'native-proof'; proof_out.mkdir()
    needed = {a.native_proof.resolve()}
    for field in ['native_execution', 'report', 'direction_report', 'reference_metadata']:
        needed.add(dead_cones.pinned_path(a.native_proof, proof[field]))
    for path in needed: shutil.copyfile(path, proof_out / path.name)
    # Preserve the native-proven table byte for byte. Only independent local
    # parsers may normalize formatting; the native Tcl consumer sees raw bytes.
    shutil.copyfile(dead_cones.pinned_path(a.native_proof, proof['report']),
                    proof_out / 'dc-library-proof.tsv')
    (a.out / 'prune-plan.json.gz').write_bytes(gzip.compress((json.dumps(plan, sort_keys=True, indent=2) + '\n').encode(), mtime=0))
    manifest = {q.relative_to(a.out).as_posix(): hashlib.sha256(q.read_bytes()).hexdigest()
                for q in sorted(a.out.rglob('*')) if q.is_file()}
    (a.out / 'package-files.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status='SEALED_ORIGINAL_DEAD_CONES_FOR_NATIVE_SEED_RECHECK_NOT_EXECUTED',
                         files=len(manifest), dead_leaves=1796, dead_state_leaves=36,
                         package_sha256=hashlib.sha256((a.out / 'package-files.json').read_bytes()).hexdigest(),
                         out=str(a.out)), sort_keys=True))


if __name__ == '__main__': main()
