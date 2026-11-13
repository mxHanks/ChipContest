#!/usr/bin/env python3
"""Replay a native-direction-proven dead-cone plan on an explicit completed seed.

Only DC apply and fresh PT reload are supported. The plan is proven against the
original map, while the actual loaded seed has its own apply/reload SHA chain.
Every planned output is rechecked natively before its deletion wave; buffers
already added by earlier repairs are retained. This runner has no transport.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True

SCHEMA = 'ingress1064-n3-dead-cone-stage-v1'
MAPPED_SHA = '882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'
SEED_SCHEMAS = {'ingress1064-n3-bounded-eco-stage-v1', 'ingress1064-n3-clock-eco-stage-v1',
                'ingress1064-n3-electrical-eco-stage-v1'}


def require(value, message):
    if not value: raise ValueError(message)


def tcl(value):
    value = str(value)
    require(not any(c in value for c in '{}\\\r\n'), 'unsafe Tcl literal')
    return '{' + value + '}'


def verify_plan(plan):
    require(plan.get('schema') == 'ingress1064-original-map-native-dead-cone-whitelist-v1' and
            plan.get('original_mapped_sha256') == MAPPED_SHA and plan.get('preserved_macro_count') == 353,
            'not the exact original1064 native dead-cone whitelist')
    names, flattened = set(), set()
    for wave in plan['waves']:
        require(wave, 'empty deletion wave')
        for row in wave:
            require(set(row) == {'native_instance', 'flattened_instance', 'reference', 'is_sequential'},
                    'invalid exact deletion row')
            name, flat, ref = row['native_instance'], row['flattened_instance'], row['reference']
            require(name not in names and flat not in flattened and '/' in name and
                    not any(c in name + ref for c in '{}\\\r\n\t '), 'unsafe/duplicate exact dead leaf')
            require(not ref.startswith('RAMSP') and type(row['is_sequential']) is bool,
                    'RAMSP or uncharacterized sequential classification in deletion plan')
            names.add(name); flattened.add(flat)
    require(len(names) == plan['removed_leaf_count'] == 1796 and
            sum(row['is_sequential'] for wave in plan['waves'] for row in wave) == 36,
            'only the exact independently proved1796-leaf/36-dead-state whitelist is permitted')
    return plan


def emit(plan):
    verify_plan(plan)
    lines = [
        '# Original-map proof; runtime target is explicitly receipted repaired seed DDC.',
        'current_instance',
        'eco_sha $::xu_dead_original_map {' + MAPPED_SHA + '}',
        'eco_capture api-all-connected-man.rpt {man all_connected}',
        'set xu_dead_manual [open [file join $::eco_out api-all-connected-man.rpt] r]',
        'set xu_dead_manual_text [read $xu_dead_manual]; close $xu_dead_manual',
        'eco_require [expr {[string first {-leaf} $xu_dead_manual_text] >= 0}] {native all_connected manual does not document -leaf; no deletion attempted}',
        'set xu_dead_macro_count [sizeof_collection [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]]',
        'eco_require [expr {$xu_dead_macro_count == 353}] {seed SRAM count differs}',
        'set xu_dead_ledger [eco_open dead-output-visibility.tsv]',
        'puts $xu_dead_ledger "wave\tinstance\toutput_pin\tconnected_output_pins\tleaf_input_count\ttop_port_count"',
        'set xu_dead_deletions [eco_open deleted-leaves.tsv]',
        'puts $xu_dead_deletions "wave\tinstance\treference\tis_sequential"',
        'set xu_dead_removed 0',
    ]
    for index, wave in enumerate(plan['waves']):
        lines.append('set xu_dead_wave [list ' + ' '.join(tcl(x['native_instance']) for x in wave) + ']')
        for row in wave:
            name, ref = tcl(row['native_instance']), tcl(row['reference'])
            lines += [
                'set xu_dead_cell [get_cells -quiet ' + name + ']',
                'eco_require [expr {[sizeof_collection $xu_dead_cell] == 1 && [get_object_name $xu_dead_cell] eq ' + name + '}] {dead leaf missing/ambiguous in repaired seed}',
                'eco_require [expr {![get_attribute $xu_dead_cell is_hierarchical] && [get_attribute $xu_dead_cell ref_name] eq ' + ref + '}] {dead-leaf reference/hierarchy changed in seed}',
            ]
        lines += [
            '# Verify complete wave before applying its first deletion.',
            'foreach xu_dead_name $xu_dead_wave {',
            '  set xu_dead_cell [get_cells $xu_dead_name]',
            '  set xu_dead_out_count 0',
            '  foreach_in_collection xu_dead_pin [get_pins -of_objects $xu_dead_cell] {',
            '    if {[get_attribute $xu_dead_pin direction] ne {out}} {continue}',
            '    incr xu_dead_out_count',
            '    set xu_dead_connected_outputs 0',
            '    foreach_in_collection xu_dead_connected [all_connected -leaf $xu_dead_pin] {',
            '      set xu_dead_class [get_attribute $xu_dead_connected object_class]',
            '      eco_require [expr {$xu_dead_class ne {port}}] {planned dead output connects to top port; abort seed pruning}',
            '      eco_require [expr {$xu_dead_class eq {pin}}] {unexpected native all_connected object class}',
            '      eco_require [expr {[get_attribute $xu_dead_connected direction] eq {out}}] {planned dead output still drives leaf input/inout in repaired seed}',
            '      incr xu_dead_connected_outputs',
            '    }',
            '    puts $xu_dead_ledger "' + str(index) + '\t$xu_dead_name\t[get_object_name $xu_dead_pin]\t$xu_dead_connected_outputs\t0\t0"',
            '  }',
            '  eco_require [expr {$xu_dead_out_count > 0}] {leaf lacks characterized connected outputs}',
            '}',
            'flush $xu_dead_ledger',
        ]
        for row in wave:
            lines += [
                'remove_cell [get_cells ' + tcl(row['native_instance']) + ']',
                'incr xu_dead_removed',
                'puts $xu_dead_deletions [join [list ' + str(index) + ' ' + tcl(row['native_instance']) + ' ' +
                tcl(row['reference']) + ' ' + tcl(str(row['is_sequential']).lower()) + '] "\\t"]',
            ]
        lines += ['flush $xu_dead_deletions', 'puts "DEAD_CONE_WAVE_COMPLETE ' + str(index) + ' removed=$xu_dead_removed"']
    lines += [
        'close $xu_dead_ledger; close $xu_dead_deletions',
        'eco_require [expr {$xu_dead_removed == 1796}] {dead-cone removed count differs}',
        'eco_require [expr {[sizeof_collection [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}]] == 353}] {SRAM deletion forbidden}',
        '# Only added identity buffers may become newly dead after their sole dead-state CK load disappears.',
        'eco_require [expr {$::xu_dead_cleanup_new_buffers in {0 1}}] {invalid explicit buffer cleanup mode}',
        'set xu_dead_cleanup [eco_open removed-added-buffers.tsv]',
        'puts $xu_dead_cleanup "round\\tinstance\\treference"',
        'if {$::xu_dead_cleanup_new_buffers} {',
        '  set xu_dead_lib [get_lib_cells -quiet */BUFV2_12TR40]',
        '  eco_require [expr {[sizeof_collection $xu_dead_lib] == 1 && ![get_attribute $xu_dead_lib is_sequential]}] {cleanup buffer native library identity missing}',
        '  set xu_dead_ip [get_lib_pins -of_objects $xu_dead_lib -filter {direction == in}]',
        '  set xu_dead_op [get_lib_pins -of_objects $xu_dead_lib -filter {direction == out}]',
        '  eco_require [expr {[sizeof_collection $xu_dead_ip] == 1 && [sizeof_collection $xu_dead_op] == 1 && [file tail [get_object_name $xu_dead_ip]] eq {I} && [file tail [get_object_name $xu_dead_op]] eq {Z}}] {cleanup cell not exact unary I/Z}',
        '  eco_require [expr {[string map [list {(} {} {)} {} { } {} {"} {}] [get_attribute $xu_dead_op function]] eq {I}}] {cleanup buffer function not native-proven identity}',
        '  set xu_dead_cleanup_count 0',
        '  for {set xu_dead_round 0} {$xu_dead_round <= 2048} {incr xu_dead_round} {',
        '    set xu_dead_ready {}',
        '    foreach_in_collection xu_dead_buffer [get_cells -hierarchical -filter {ref_name == BUFV2_12TR40 && is_hierarchical == false}] {',
        '      set xu_dead_name [get_object_name $xu_dead_buffer]',
        '      if {![string match */XU_ECO_* $xu_dead_name]} {continue}',
        '      set xu_dead_visible 0',
        '      foreach_in_collection xu_dead_connection [all_connected -leaf [get_pins ${xu_dead_name}/Z]] {',
        '        set xu_dead_class [get_attribute $xu_dead_connection object_class]',
        '        if {$xu_dead_class eq {port} || ($xu_dead_class eq {pin} && [get_attribute $xu_dead_connection direction] ne {out})} {set xu_dead_visible 1}',
        '        eco_require [expr {$xu_dead_class in {port pin}}] {unknown cleanup connectivity object}',
        '      }',
        '      if {!$xu_dead_visible} {lappend xu_dead_ready $xu_dead_name}',
        '    }',
        '    if {[llength $xu_dead_ready] == 0} {break}',
        '    foreach xu_dead_name $xu_dead_ready {',
        '      incr xu_dead_cleanup_count',
        '      eco_require [expr {$xu_dead_cleanup_count <= 2048}] {new-buffer cleanup bound exceeded}',
        '      remove_cell [get_cells $xu_dead_name]',
        '      puts $xu_dead_cleanup "$xu_dead_round\\t$xu_dead_name\\tBUFV2_12TR40"',
        '    }',
        '  }',
        '}',
        'close $xu_dead_cleanup',
        'puts {PROVEN_DEAD_CONE_PRUNING_COMPLETE_NOT_STA_OR_RTL_FORMAL_SIGNOFF}',
    ]
    return ('\n'.join(lines) + '\n').encode()


def clean(root, schemas, stage, base_hash):
    r = json.loads((root / 'execution.json').read_text())
    require(r.get('schema') in schemas and r.get('stage') == stage and
            r.get('status') == 'NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and
            r.get('returncode') == 0 and r.get('completion_marker') is True and
            r.get('tool_timed_out') is False and
            r.get('source_drift') == [] and r.get('native_tool_errors') == [] and r.get('missing_outputs') == [] and
            r.get('baseline_execution_sha256') == base_hash, 'seed/prior native receipt is incomplete or from another original baseline')
    return r


def seed_inputs(apply, reload, base_hash, chain):
    ap = clean(apply, SEED_SCHEMAS, 'apply', base_hash)
    rp = clean(reload, SEED_SCHEMAS, 'reload', base_hash)
    require(ap['schema'] == rp['schema'] and ap['package_sha256'] == rp['package_sha256'] and
            rp.get('prior_execution_sha256') == sha(apply / 'execution.json') and
            ap.get('libraries') == rp.get('libraries') == chain['libraries'], 'seed apply/freshreload lineage or library mismatch')
    for field in ['target_plan_sha256', 'clock_plan_sha256', 'electrical_plan_sha256']:
        require(ap.get(field) == rp.get(field), 'seed plan mismatch: ' + field)
    inputs = bind_outputs(ap, apply, ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'eco.svf', 'original-clock-association.tsv'])
    inputs += bind_outputs(rp, reload, ['persisted-coverage.rpt', 'persisted-all_violators.rpt', 'original-clock-association.tsv'])
    svf_names = sorted(name for name in ap['outputs'] if name.endswith('.svf'))
    require('eco.svf' in svf_names, 'seed own SVF missing')
    inputs += bind_outputs(ap, apply, svf_names)
    inputs += [verify(p / 'execution.json', sha(p / 'execution.json')) for p in [apply, reload]]
    identity = dict(schema=ap['schema'], apply_dir=str(apply), reload_dir=str(reload),
                    apply_execution_sha256=sha(apply / 'execution.json'), reload_execution_sha256=sha(reload / 'execution.json'),
                    mapped_sha256=sha(apply / 'mapped.v'), ddc_sha256=sha(apply / 'mapped.ddc'), svf_sha256=sha(apply / 'eco.svf'),
                    retained_seed_svfs=[dict(source_name=name, retained_name='seed-svf/' + name,
                                             sha256=ap['outputs'][name]['sha256']) for name in svf_names],
                    ancestor_seed_identity=ap.get('seed_identity'))
    return inputs, identity


def wait(command, cwd, env, timeout, record, receipt):
    timed_out = False
    with (cwd / 'native.log').open('x') as log:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record['pid'] = proc.pid; dump(receipt, record)
        try: code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True; os.killpg(proc.pid, signal.SIGTERM)
            try: code = proc.wait(timeout=10)
            except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL); code = proc.wait()
    return code, timed_out


def main():
    # Imports requiring sealed development_controls/profiles are deferred so
    # prepare_prune can verify/emit plan bytes directly from the source tree.
    global baseline, bind_outputs, dump, heavy_jobs, sha, verify, TOP, PROFILE
    from run_stage import baseline, bind_outputs, dump, heavy_jobs, sha, verify, TOP, PROFILE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['apply', 'reload'], required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--baseline-pt-dir', type=Path, required=True)
    p.add_argument('--seed-apply', type=Path, required=True)
    p.add_argument('--seed-reload', type=Path, required=True)
    p.add_argument('--prior', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--run', action='store_true')
    p.add_argument('--cleanup-new-dead-buffers', action='store_true',
                   help='Also prune only newly added native-identity XU_ECO_* BUFV2 leaves with no leaf-input/top load')
    p.add_argument('--timeout-seconds', type=int, default=1800)
    p.add_argument('--allow-coordinated-busy-jobs', action='store_true')
    p.add_argument('--coordination-note')
    a = p.parse_args()
    require(0 < a.timeout_seconds <= 3600, 'bounded prune timeout exceeded')
    package = Path(__file__).resolve().parent; seal = package / 'package-files.json'
    entries = json.loads(seal.read_text()); inputs = []
    for name, digest in entries.items():
        q = Path(name); require(not q.is_absolute() and '..' not in q.parts, 'unsafe sealed path')
        inputs.append(verify(package / q, digest))
    require({'run_prune_stage.py', 'pt_prune_reload.tcl', 'prune-plan.json.gz', 'dead_cones.py'} <= set(entries), 'prune tools/plan not sealed')
    plan = verify_plan(json.loads(gzip.decompress((package / 'prune-plan.json.gz').read_bytes())))
    plan_hash = sha(package / 'prune-plan.json.gz'); payload = emit(plan)
    require(plan.get('generated_tcl_sha256') == hashlib.sha256(payload).hexdigest(), 'deterministic prune Tcl differs from sealed plan')
    base, ptroot = a.baseline.resolve(), a.baseline_pt_dir.resolve()
    more, base_receipt, chain = baseline(base, ptroot); inputs += more
    require(sha(base / 'mapped.v') == MAPPED_SHA, 'prune original provenance differs')
    base_hash = sha(base / 'execution.json')
    seed_apply, seed_reload = a.seed_apply.resolve(), a.seed_reload.resolve()
    more, seed = seed_inputs(seed_apply, seed_reload, base_hash, chain); inputs += more
    if a.stage == 'reload':
        require(a.prior is not None, 'fresh prune reload requires explicit prune DC apply receipt')
        prior_root = a.prior.resolve(); prior = clean(prior_root, {SCHEMA}, 'apply', base_hash)
        require(prior.get('package_sha256') == sha(seal) and prior.get('prune_plan_sha256') == plan_hash and prior.get('seed_identity') == seed,
                'prune fresh reload differs from explicit plan/package/seed')
        require(prior.get('cleanup_new_dead_buffers') == a.cleanup_new_dead_buffers,
                'fresh prune reload must retain the explicit apply cleanup mode')
        inputs += bind_outputs(prior, prior_root, ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'eco.svf', 'original-clock-association.tsv', 'deleted-leaves.tsv', 'dead-output-visibility.tsv', 'removed-added-buffers.tsv'])
        inputs.append(verify(prior_root / 'execution.json', sha(prior_root / 'execution.json')))
    else:
        require(a.prior is None, 'first prune apply loads the explicit completed seed only')
        prior_root = None
    record = dict(schema=SCHEMA, stage=a.stage, status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED', mode='prune',
        package_sha256=sha(seal), prune_plan_sha256=plan_hash, baseline_execution_sha256=base_hash,
        baseline_mapped_sha256=MAPPED_SHA, baseline_pt_execution_sha256=sha(ptroot / 'execution.json'), seed_identity=seed,
        prior_execution_sha256=sha(prior_root / 'execution.json') if prior_root else None,
        source_ddc_sha256=seed['ddc_sha256'], original_plan_provenance='ORIGINAL_MAP_PROOF_WITH_NATIVE_RUNTIME_SEED_VISIBILITY_RECHECK',
        cleanup_new_dead_buffers=a.cleanup_new_dead_buffers,
        max_deleted_leaves=1796, dead_sequential_leaves=36, preserved_SRAM_macros=353,
        top=TOP, hardware_profile=PROFILE, max_cores=8, user_authorized_cap=8, run_requested=a.run,
        qualification='NOT_QUALIFIED', timing_verdict='NOT_TIMING_CLOSURE')
    if not a.run:
        print(json.dumps(record, sort_keys=True)); return 0
    jobs = heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:
        require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip()) >= 16, 'explicit coordinated busy-job note required')
    allowed = sorted(os.sched_getaffinity(0)); require(len(allowed) >= 10, 'cap8 reserves at least2 allowed CPUs')
    os.sched_setaffinity(0, allowed[:8]); record.update(linux_affinity=allowed[:8], online_cpus=os.cpu_count(), observed_jobs=jobs, coordination_note=a.coordination_note)
    role = 'dc' if a.stage == 'apply' else 'pt'; tool = verify(chain[role]['path'], chain[role]['sha256'], external=True)
    libraries = [verify(x['path'], x['sha256'], external=True) for x in chain['libraries']]
    out = a.out.resolve(); out.mkdir(mode=0o700, parents=True, exist_ok=False)
    changes = out / 'delete-dead-cones.tcl'
    if a.stage == 'apply':
        changes.write_bytes(payload); inputs.append(verify(changes, plan['generated_tcl_sha256']))
    source_mapped = seed_apply / 'mapped.v' if a.stage == 'apply' else prior_root / 'mapped.v'
    config = ['set ::eco_baseline ' + tcl(base), 'set ::eco_ddc ' + tcl(seed_apply / 'mapped.ddc'),
        'set ::eco_mapped ' + tcl(source_mapped), 'set ::eco_mode {prune}',
        'set ::xu_dead_original_map ' + tcl(base / 'mapped.v'),
        'set ::xu_dead_cleanup_new_buffers ' + str(int(a.cleanup_new_dead_buffers)),
        'set ::eco_buffer_reference {BUFV2_12TR40}', 'set ::eco_max_buffers 2048', 'set ::eco_max_per_pin 8',
        'set ::eco_max_paths_per_query 8192', 'set ::eco_max_added_area 10000.0',
        'set ::eco_hold_margin 0.03', 'set ::eco_setup_margin 0.03', 'set ::eco_selected_targets {}', 'set ::eco_read_only_clock_roots {}',
        'set ::eco_link_libraries [list * ' + ' '.join(tcl(x['path']) for x in chain['libraries']) + ']',
        'set ::eco_library_bindings [list ' + ' '.join(tcl(x['path']) + ' ' + tcl(x['sha256']) for x in chain['libraries']) + ']',
        'set ::eco_bindings [list ' + ' '.join(tcl(x['path']) + ' ' + tcl(x['sha256']) for x in inputs) + ']']
    if a.stage == 'apply':
        shutil.copyfile(seed_reload / 'original-clock-association.tsv', out / 'original-clock-association.tsv')
        for item in seed['retained_seed_svfs']:
            destination = out / item['retained_name']; destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(seed_apply / item['source_name'], destination)
        config += ['set ::eco_changes ' + tcl(changes), 'set ::eco_changes_sha ' + tcl(sha(changes))]
    else:
        config += ['set ::eco_reference_clocks ' + tcl(prior_root / 'original-clock-association.tsv'),
                   'set ::eco_prune_deleted ' + tcl(prior_root / 'deleted-leaves.tsv'),
                   'set ::eco_prune_deleted_sha ' + tcl(sha(prior_root / 'deleted-leaves.tsv'))]
    configuration = out / 'config.tcl'; configuration.write_text('\n'.join(config) + '\n')
    env = os.environ.copy(); env.update(XU_ECO_PACKAGE=str(package), XU_ECO_CONFIG=str(configuration), XU_ECO_HOST_TOOL=role)
    if role == 'pt':
        lc = chain['library_compiler']; verify(Path(lc['root']) / 'bin/lc_shell', lc['launcher_sha256'], external=True); env['SYNOPSYS_LC_ROOT'] = lc['root']
        # Existing eco_native_proof requires the separately native-DC-proven
        # identity function; this proof bundle was sealed by prepare_prune.
        function = package / 'native-proof' / 'dc-library-proof.tsv'
        configuration.write_text(configuration.read_text() + 'set ::eco_dc_function_file ' + tcl(function) + '\nset ::eco_dc_function_sha ' + tcl(sha(function)) + '\n')
    command = [tool['path'], '-f', str(package / ('dc_apply.tcl' if role == 'dc' else 'pt_prune_reload.tcl'))]
    record.update(status='RUNNING', tool=tool, libraries=chain['libraries'], inputs=inputs, command=command,
                  config_sha256=sha(configuration), started_epoch=time.time(), timeout_seconds=a.timeout_seconds)
    receipt = out / 'execution.json'; code, timeout = wait(command, out, env, a.timeout_seconds, record, receipt)
    drift = [x['path'] for x in inputs + libraries + [tool] if not Path(x['path']).is_file() or sha(x['path']) != x['sha256']]
    if sha(configuration) != record['config_sha256']: drift.append(str(configuration))
    errors = re.findall(r'^(?:Error:|Fatal:).*$', (out / 'native.log').read_text(errors='replace'), re.M)
    outputs = {q.relative_to(out).as_posix(): dict(sha256=sha(q), bytes=q.stat().st_size) for q in sorted(out.rglob('*')) if q.is_file() and q.name != 'execution.json'}
    if role == 'dc':
        required = ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'eco.svf', 'area-upper-bound.tsv', 'leaf-inventory.tsv',
                    'original-clock-association.tsv', 'deleted-leaves.tsv', 'dead-output-visibility.tsv', 'removed-added-buffers.tsv', 'api-all-connected-man.rpt']
        required += [item['retained_name'] for item in seed['retained_seed_svfs']]
        marker = 'DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'
    else:
        required = ['persisted-coverage.rpt', 'persisted-all_violators.rpt', 'persisted-setup.rpt', 'persisted-hold.rpt',
                    'persisted-recovery.rpt', 'persisted-removal.rpt', 'persisted-gating_hold.rpt', 'persisted-min_pulse_width.rpt',
                    'retained-clock-association.tsv', 'removed-clock-association.tsv', 'original-clock-association.tsv',
                    'buffer-functions.tsv', 'leaf-pin-directions.tsv', 'reference-metadata.tsv']
        marker = 'PRUNE_RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'
    required += ['required-reports.list', 'host-options.rpt']
    if (out / 'required-reports.list').is_file(): required += (out / 'required-reports.list').read_text().splitlines()
    missing = [x for x in required if x not in outputs or (outputs[x]['bytes'] == 0 and x != 'required-reports.list')]
    complete = (out / marker).is_file(); ok = code == 0 and complete and not timeout and not drift and not errors and not missing
    record.update(status='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' if ok else 'NATIVE_STAGE_FAILED', returncode=code,
                  tool_timed_out=timeout, finished_epoch=time.time(), completion_marker=complete, source_drift=drift,
                  native_tool_errors=errors, missing_outputs=missing, outputs=outputs)
    dump(receipt, record)
    if ok and role == 'pt':
        dump(out / 'function-proof.json', dict(schema='xu-native-buffer-function-proof-v1', native_execution=dict(path='execution.json', sha256=sha(receipt)),
            report=dict(path='buffer-functions.tsv', sha256=sha(out / 'buffer-functions.tsv')),
            direction_report=dict(path='leaf-pin-directions.tsv', sha256=sha(out / 'leaf-pin-directions.tsv')),
            reference_metadata=dict(path='reference-metadata.tsv', sha256=sha(out / 'reference-metadata.tsv'))))
    print(json.dumps({k: record[k] for k in ['stage', 'status', 'returncode', 'source_drift', 'native_tool_errors', 'missing_outputs']}, sort_keys=True))
    return 0 if ok else 1


if __name__ == '__main__':
    try: sys.exit(main())
    except (OSError, ValueError, KeyError) as error: print('FAIL: ' + str(error), file=sys.stderr); sys.exit(1)
