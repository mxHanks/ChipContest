#!/usr/bin/env python3
"""Own S2e155 target power, with unchanged120/89/109 capture provenance.

Python3.6+, standard library only. Task0 preflight and full12 campaign use the
same code path. All results are diagnostic and NOT_QUALIFIED. Never restarts a
native run or overwrites an existing campaign. No credentials or network.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
import uuid

HERE = Path(__file__).resolve().parent
FROZEN130 = '95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46'
STATE155 = '3474d4aaf4801ead290534a25fefcb6cab8d4613ff2191edef71900f7fec6952'
NET155 = '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794'
CHAIN155 = ['1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9',
            '1c47a3c93d0730408d8a7fc30483e1508e349ead3cb1e71dedfa3a78067ce7ee',
            '2060819a8ec232a2554c1d18206531c6ca3646379b22f225d0ff725be2bfa92e']
SCOPE155 = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
OLD134 = '1ce842c387872e473352bc84cef7eac11680dad5dfd32b794b2236a69251b435'
SCHEMA = 'xu-s2e-final-power166-prepared-v1'
TARGET_SCHEMA = 'xu-s2e-final155-target166-v1'
TASK0 = 'EXECUTED_TASK0_DIAGNOSTIC_NOT_QUALIFIED'
FULL12 = 'EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'
FAIL = 'FAIL166_NOT_QUALIFIED'
MARKER_FM = 'XU_S2E_TIMING134_FORMALITY_PASS'
REVIEW = [
    'NOT_QUALIFIED: RTL120 SAIF mapped to own155 final netlist; no contest energy or score.',
    'Capture120 remains bound to original own89/109. Target155 has separate own three-SVF full-FM provenance.',
    '155 original SDC plus frozen forwarded-clock scope is replayed; pre-CTS method, not complete150MHz closure.',
    'Target155 untested27217, unconstrained31, recovery unknown/no-path and three PLIC min-cap debts remain.',
    'Measured TX/TZ/TB are preserved. Native x_probability=0 does not prove physically known SRAM Q.',
    'SAIF default/propagated activity, new repair-logic activity and SRAM conditional/internal-power modes need review.',
    'Original CPU33697 pretask clear writes are outside the measured first-source-request to final-Y-retirement window.',
    'No Chisel/RTL/ABI/numerical/vector/library/model/SDC changes or DUT initialization are performed.',
]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def runtime():
    import hashlib
    path = HERE / 'frozen130.py'
    need(path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN130,
         'byte-identical frozen130 runtime required')
    spec = importlib.util.spec_from_file_location('xu_frozen130_for166', str(path))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


base = runtime()
read, write, identity, sha, canonical = base.read, base.write, base.identity, base.sha, base.canonical


def now():
    return datetime.now(timezone.utc).isoformat()


def selected_ids(text):
    if text == 'all' or text == ','.join(str(i) for i in range(12)):
        return list(range(12))
    need(text == '0', 'only --task-ids 0 preflight or all full12 is supported')
    return [0]


def metadata155(state, target_root, capture, source, tools):
    """Pure metadata gate; actual-byte checks are mandatory in checked_target."""
    root = Path(target_root).absolute()
    need(root.name == 's2e-own-timing-repair-20261105-155', 'only actual own155 target is supported')
    need(state.get('schema') == 'xu-s2e-own-timing134-v1' and
         state.get('status') == 'EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED' and
         state.get('qualification') == 'NOT_QUALIFIED' and state.get('formal_passing') == 42338 and
         state.get('frozen_before') == state.get('frozen_after') and len(state.get('frozen_before', {})) == 204 and
         state.get('frozen_input_errors') == [] and state.get('resume155_adopted_originals_rechecked') is True,
         'actual155 terminal/source freeze/native full-FM status differs')
    need(state['own89_context'] == capture and state['source'] == source and state['tools'] == tools,
         'target155 must have the exact same own89/109 source/tool ancestry as capture120')
    expected_paths = [capture['netlist']['path'].replace('/mapped.v', '/default.svf'),
                      str(root / 'hold-gating/hold.svf'), str(root / 'final/repair.svf')]
    need([row['path'] for row in state['svf_chain']] == expected_paths and
         [row['sha256'] for row in state['svf_chain']] == CHAIN155,
         'exact ordered own89/155hold/155final SVF chain differs')
    need(set(state['final_outputs']) == {str(root / 'final/mapped.v'), str(root / 'final/repair.svf')} and
         state['final_outputs'][str(root / 'final/mapped.v')]['sha256'] == NET155 and
         state['final_outputs'][str(root / 'final/mapped.v')]['bytes'] == 14152273,
         'actual155 final target output set differs')
    phase_order = [('original-inventory', 'dc'), ('original-inventory', 'pt'), ('hold-gating', 'dc'),
                   ('posthold-inventory', 'dc'), ('posthold-inventory', 'pt'),
                   ('final', 'dc'), ('final', 'pt'), ('final', 'fm')]
    need([(Path(r['directory']).name, r['tool']) for r in state['runs']] == phase_order,
         'all five adopted134 and three native155 phases in exact order required')
    for i, run in enumerate(state['runs']):
        need(Path(run['directory']).parent == root and run['returncode'] == 0 and
             run['marker_count'] == 1 and run['errors'] == [], 'native155 phase scope or status differs')
        need((i < 5) == ('original_native_run' in run), 'adopted/new155 phase classification differs')
        if i < 5:
            need(run.get('execution_provenance') == 'ADOPTED_ORIGINAL134_NATIVE_PHASE_NOT_RERUN',
                 'adopted134 provenance missing')


def native_fm(text, returncode):
    """Same complete scope/statistics as109, with155's actual native marker."""
    need(returncode == 0 and 'Version R-2020.09-SP5' in text, 'same native155 FM version/rc required')
    need(re.findall(r'^' + MARKER_FM + r'[ \t]*$', text, re.M) == [MARKER_FM] and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)[ \t]*$', text, re.M) == ['Verification SUCCEEDED'],
         'unique native155 FM marker/verification required')
    # fm_shell echoes the Tcl if/else with both PASS and FAIL strings. Only
    # native output lines are evidence, never an occurrence inside that echo.
    need(not any(base.BAD.search(line) for line in text.splitlines()) and
         not re.search(r'^[ \t]*(?:Verification FAILED|[1-9][0-9]* (?:Aborted|Failing|Unverified) compare points|'
                       r'XU_S2E_TIMING134_FORMALITY_(?:FAIL|SCRIPT_ERROR)(?:[ \t].*)?)[ \t]*$', text, re.M),
         'native155 full-FM error or incomplete proof')
    need(re.findall(r'^[ \t]*(\d+) Passing compare points[ \t]*$', text, re.M) == ['42338'],
         'native155 compare-point total differs')
    for prefix, expected in [('Passing (equivalent)', [17136, 0, 0, 0, 144, 25019, 39, 42338]),
                             ('Failing (not equivalent)', [0] * 8), ('  Unread', [0, 0, 0, 0, 0, 511, 0, 511])]:
        hits = re.findall(r'^' + re.escape(prefix) + r'[ \t]+([0-9 \t]+)$', text, re.M)
        need(len(hits) == 1 and list(map(int, hits[0].split())) == expected, 'native155 ' + prefix + ' scope differs')
    for prefix in ['Reference design: r:/WORK/xu_soc_ppa_top', 'Implementation design: i:/WORK/xu_soc_ppa_top']:
        need(len(re.findall(r'^[ \t]*' + re.escape(prefix) + r'[ \t]*$', text, re.M)) == 1,
             'native155 must prove the complete same original SoC top')
    unmatched = re.findall(r'^[ \t]*(\d+)\((\d+)\) Unmatched reference\(implementation\) compare points[ \t]*$', text, re.M)
    need(unmatched and set(unmatched) == {('17', '0')}, 'native155 unmatched scope differs')
    return dict(passing=42338, black_box_pins=17136, ports=144, dff=25019, latches=39,
                unread_dff=511, unmatched_reference_dff=17, failing=0, qualification='NOT_QUALIFIED')


def fm_script(original, original_root, target_root, tcl):
    ppa, target = Path(original_root), Path(target_root)
    old_svf = 'set_svf ' + tcl(ppa / 'ppa/default.svf')
    old_net = 'read_verilog -i ' + tcl(ppa / 'ppa/mapped.v')
    need(original.count(old_svf) == original.count(old_net) == 1, 'unique original own89 proof commands required')
    chain = [ppa / 'ppa/default.svf', target / 'hold-gating/hold.svf', target / 'final/repair.svf']
    result = original.replace(old_svf, 'set_svf [list ' + ' '.join(tcl(p) for p in chain) + ']')
    result = result.replace(old_net, 'read_verilog -i ' + tcl(target / 'final/mapped.v'))
    return result.replace('XU_S2E_FULL_SOC_FORMALITY', 'XU_S2E_TIMING134_FORMALITY')


def area(text):
    path = ('u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave')
    hits = re.findall(r'^' + re.escape(path) + r'\n[ \t]*([0-9.]+)\s+[^\n]*\baccel_icb_slave[ \t]*$', text, re.M)
    need(hits == ['300309.6339'], 'unique original155 accelerator hierarchy area differs')
    total = re.findall(r'^Total cell area:[ \t]*([0-9.]+)[ \t]*$', text, re.M)
    need(total == ['3373696.204286'], 'original155 total SoC area differs')
    return dict(accelerator_mm2=str(Decimal(hits[0]) / Decimal(1000000)),
                full_soc_mm2=str(Decimal(total[0]) / Decimal(1000000)), accelerator_limit_mm2='2.25',
                below_area_limit=True, method='original155 DC hierarchy cell area, original report precision',
                qualification='NOT_QUALIFIED')


def collect_records(value, records):
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            base.check_record(value, records)
        for item in value.values():
            collect_records(item, records)
    elif isinstance(value, list):
        for item in value:
            collect_records(item, records)


def checked_target(modules, root, original_root, capture, source, records):
    root, original_root = Path(root).absolute(), Path(original_root).absolute()
    state_path = root / 'state.json'
    state_rec = base.remember(records, state_path, STATE155)
    state = read(state_path)
    metadata155(state, root, capture, source, modules.tool)
    collect_records(state, records)  # Actual bytes, including all204 and complete emitted/native receipts.
    old_rec = state['resume155']['original_terminal']
    need(old_rec['sha256'] == OLD134 and Path(old_rec['path']).parent.name ==
         's2e-own-timing-repair-20261105-134', 'original failed134 terminal identity differs')
    old = read(old_rec['path'])
    need(old['status'] == 'FAILED_NOT_QUALIFIED' and old['error'] == 'Error: field larger than field limit (131072)' and
         old['frozen_before'] == old['frozen_after'] and old['frozen_input_errors'] == [], 'original134 adoption gate differs')
    collect_records(old, records)
    need([r['original_native_run'] for r in state['runs'][:5]] == old['runs'], 'all adopted134 native executions differ')
    for i, run in enumerate(state['runs']):
        text = Path(run['log']['path']).read_text(errors='replace')
        marker = (MARKER_FM if run['tool'] == 'fm' else 'XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED'
                  if run['tool'] == 'pt' else 'XU_S2E_TIMING134_INVENTORY_DONE_NOT_QUALIFIED'
                  if Path(run['script']['path']).name == 'inventory.tcl' else
                  'XU_S2E_TIMING134_HOLD_DONE_NOT_QUALIFIED' if i == 2 else 'XU_S2E_TIMING134_REPAIR_DONE_NOT_QUALIFIED')
        version = {'dc': 'T-2022.03-SP5-5', 'pt': 'T-2022.03-SP5-1', 'fm': 'R-2020.09-SP5'}[run['tool']]
        need(text.splitlines().count(marker) == 1 and 'Version ' + version in text and
             not any(base.BAD.search(line) for line in text.splitlines()), 'original155 native log marker/version/error differs')
    native = native_fm((root / 'final/fm.log').read_text(), state['runs'][-1]['returncode'])
    template = original_root / 'formality/verify.tcl'
    base.remember(records, template)
    need((root / 'final/verify.tcl').read_text() == fm_script(template.read_text(), original_root, root, modules.ppa.tcl),
         'complete actual155 FM script differs from original own89 template and exact ordered three-SVF chain')
    sdc = base.check_record(capture['constraints'], records)
    need(sdc['sha256'] == base.SDC, 'same original analysis SDC required')
    sta = (root / 'final/sta.tcl').read_text()
    scope_rows = [r for r in state['frozen_before'].values() if r['sha256'] == SCOPE155]
    need(len(scope_rows) == 1, 'unique frozen155 clock scope required')
    scope = base.check_record(scope_rows[0], records)
    prefix = 'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + modules.ppa.tcl(sdc['path']) + '\n'
    prefix += 'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' + modules.ppa.tcl(scope['path']) + '\n'
    need(sta.count(prefix) == 1 and 'set_propagated_clock [all_clocks]' not in sta,
         'actual155 SDC/forward-clock scope contract differs')
    net = base.check_record(state['final_outputs'][str(root / 'final/mapped.v')], records)
    area_rec = identity(root / 'final/area.rpt')
    result = dict(schema=TARGET_SCHEMA, qualification='NOT_QUALIFIED', state=state_rec,
        netlist=net, constraints=sdc, clock_scope=scope, analysis_clock_contract=prefix,
        source_context=source, capture_mapped_context=capture,
        svf_chain=[base.check_record(row, records) for row in state['svf_chain']], native_formality=native,
        area=area((root / 'final/area.rpt').read_text()), area_report=area_rec,
        fm_log=identity(root / 'final/fm.log'), fm_script=identity(root / 'final/verify.tcl'),
        original134_state=identity(old_rec['path']), limitations=REVIEW)
    need(sha(state_path) == STATE155, '155 terminal state changed during inspection')
    return result


def replace_clock(modules, text, constraints, scope, propagated):
    old = ('set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + modules.ppa.tcl(constraints['path']) + '\n' +
           modules.ppa.clock_contract_checks())
    if propagated:
        old += 'set_propagated_clock [all_clocks]\nupdate_timing\n'
    new = ('set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + modules.ppa.tcl(constraints['path']) + '\n' +
           modules.ppa.clock_contract_checks() + 'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' +
           modules.ppa.tcl(scope['path']) + '\nupdate_timing\n')
    need(text.count(old) == 1 and scope['sha256'] == SCOPE155, 'unique frozen130 clock prelude and actual155 scope required')
    result = text.replace(old, new)
    need('set_propagated_clock [all_clocks]' not in result and result.count('source ' + modules.ppa.tcl(scope['path'])) == 1,
         'power166 must explicitly retain155 clock method, without later all-clock propagation override')
    return result


def inventory_tcl(modules, impl, target, marker):
    text = base.inventory_tcl(modules.ppa, impl, target['netlist'], target['constraints'], marker)
    return replace_clock(modules, text, target['constraints'], target['clock_scope'], False)


def power_tcl(modules, impl, target, task):
    text = base.power_tcl(modules, impl, target['netlist'], target['constraints'], task)
    return replace_clock(modules, text, target['constraints'], target['clock_scope'], True)


def export_inventory(modules, impl, target, out, tool, environment, timeout, records):
    out.mkdir()
    marker = 'XU_S2E166_FINAL155_INVENTORY_' + uuid.uuid4().hex
    script = out / 'export.tcl'
    script.write_text(inventory_tcl(modules, impl, target, marker))
    before = dict(records)
    base.remember(before, script)
    base.verify_inputs(before)
    state = dict(status='RUNNING_NOT_QUALIFIED', qualification='NOT_QUALIFIED', pid=os.getpid(),
                 input_sha256_before=before, marker=marker, target_context=target, started_utc=now())
    write(out / 'state.json', state)
    try:
        execution = modules.common.execute([tool['path'], '-f', 'export.tcl'], out, out / 'pt.log', timeout, environment)
        state['execution'] = execution
        write(out / 'state.json', state)
        base.checked_native_log(out / 'pt.log', marker, execution['returncode'])
        macros = base.inventory_rows(out / 'macro-pins.tsv')
        result = dict(schema='xu-mapped-sram-pin-inventory-v1', status='EXPORTED_REVIEW_PENDING',
            design='xu_soc_ppa_top', macro_count=336, pin_bit_count=22512,
            netlist=identity(target['netlist']['path']), constraints=identity(target['constraints']['path']),
            libraries=[identity(r['path']) for r in impl['libraries']], macros=macros,
            provenance=dict(raw_tsv=identity(out / 'macro-pins.tsv'), pt_log=identity(out / 'pt.log'),
                script=identity(script), tool_version=identity(out / 'version.rpt'), tool=tool,
                input_sha256_before=before, input_sha256_after={p: sha(p) for p in before}, execution=execution,
                marker=marker, limitations=REVIEW))
        need(result['provenance']['input_sha256_after'] == before, '166 target inventory inputs changed')
        write(out / 'inventory.json', result)
        state.update(status='EXPORTED_REVIEW_PENDING', inventory=identity(out / 'inventory.json'))
    except BaseException as error:
        state.update(status=FAIL, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
        raise
    finally:
        state['input_sha256_after'] = current_hashes(before)
        if state['input_sha256_after'] != before:
            state.update(status=FAIL, integrity_error='166 inventory frozen input changed')
        state['finished_utc'] = now()
        write(out / 'state.json', state)
    need(state['status'] == 'EXPORTED_REVIEW_PENDING', '166 inventory failed or changed input')
    return result


def current_hashes(records):
    result = {}
    for path in records:
        try:
            result[path] = identity(path)['sha256']
        except OSError as error:
            result[path] = 'UNREADABLE:' + type(error).__name__
        except ValueError as error:
            result[path] = 'INVALID:' + type(error).__name__
    return result


def checked_preflight(root, modules, target, capture, records):
    """A real successful same155 task0 precedes full12; it never qualifies Q."""
    root = Path(root).absolute()
    for name in ['prepared.json', 'execution.json', 'summary.json', 'result.json']:
        base.remember(records, root / name)
    manifest = read(root / 'prepared.json')
    need(manifest['requested_task_ids'] == [0] and manifest.get('preflight') is None,
         'full12 requires a separate task0-only preflight, without a preflight chain')
    verify_prepared(root, manifest, modules)
    need(manifest['capture_mapped_context'] == capture and manifest['target_mapped_context'] == target,
         'preflight must use exact same capture120/89/109 and final155 target')
    result, execution, summary = [read(root / n) for n in ['result.json', 'execution.json', 'summary.json']]
    need(all(item['status'] == TASK0 and item['qualification'] == 'NOT_QUALIFIED'
             for item in [result, execution, summary]) and summary['task_count'] == 1 and
         summary['taskset_complete'] is False and execution['taskset_complete'] is False and
         execution['requested_task_ids'] == [0] and len(execution['tasks']) == 1 and
         execution['prepared'] == identity(root / 'prepared.json') and
         execution['summary'] == result['summary'] == identity(root / 'summary.json') and
         execution['input_sha256_before'] == execution['input_sha256_after'] == manifest['input_sha256'],
         'preflight must have complete terminal same-input task0 execution receipts')
    task, native = manifest['tasks'][0], execution['tasks'][0]
    need(native['task_id'] == 0 and native['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' and
         native['frozen_inputs_sha256'] == canonical(manifest['input_sha256']), 'preflight native task receipt differs')
    directory = root / task['directory']
    base.checked_native_log(directory / 'pt.log', task['completion_marker'], native['execution']['returncode'])
    need(native['reports'] == modules.common.checked_reports(directory, task),
         'preflight full native report set or actual bytes differ')
    expected = base.diagnostic(directory, task)
    expected['unresolved'] = REVIEW
    need(native['diagnostic'] == expected and summary['tasks'] == execution['tasks'] and
         summary['area'] == target['area'] and summary['target_netlist'] == target['netlist'],
         'preflight diagnostic/area/target report differs')
    collect_records(native, records)
    base.remember(records, directory / 'pt.log')
    return dict(status=TASK0, qualification='NOT_QUALIFIED', root=str(root),
        prepared=identity(root / 'prepared.json'), execution=identity(root / 'execution.json'),
        summary=identity(root / 'summary.json'), result=identity(root / 'result.json'))


def prepare(args, state):
    out = args.out.absolute()
    modules = base.Modules(args.tool_root)
    records = dict(modules.records)
    for path in [Path(__file__).resolve(), HERE / 'frozen130.py']:
        base.remember(records, path)
    state['input_sha256_before'] = dict(records)
    write(out / 'result.json', state)
    report, ctx, capture, mapping_path = base.check_report(modules, args.activity, args.source_root,
                                                          args.ppa_root, args.formality_root, records)
    target = checked_target(modules, args.target_root, args.ppa_root, capture, ctx.source, records)
    preflight = (checked_preflight(args.preflight_root, modules, target, capture, records)
                 if args.task_ids == list(range(12)) else None)
    ppa_path = args.ppa_root.absolute() / 'ppa/prepared.json'
    original = read(ppa_path)
    base.remember(records, ppa_path)
    impl = original['implementation']
    need(impl['source_profile'] == 's2e-paired-hi' and len(impl['libraries']) == 2 and
         {row['sha256'] for row in impl['libraries']} == base.LIBRARIES, 'same own89 two SS libraries required')
    for row in impl['libraries']:
        base.check_record(row, records)
    environment = modules.common.execution_environment(args.lc_root)
    executable = shutil.which(str(args.pt), path=environment.get('PATH'))
    need(executable is not None, 'server PT executable unavailable')
    tool = base.remember(records, Path(executable).resolve())
    base.verify_inputs(records)
    state.update(phase='native-final155-inventory', input_sha256_before=dict(records), capture=identity(args.activity),
                 capture_mapped_context=capture, target_mapped_context=target)
    write(out / 'result.json', state)
    inventory_path = out / 'inventory/inventory.json'
    inventory = export_inventory(modules, impl, target, out / 'inventory', tool, environment, args.inventory_timeout, records)
    bridge = modules.bridge(mapping_path)
    _, actual, _ = bridge.inventory_macros(inventory_path)
    need(inventory['macros'] == base.inventory_rows(out / 'inventory/macro-pins.tsv') and
         all(r['lib_cell'] == 'RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16' for r in actual.values()),
         'complete native own155 macro TSV/JSON/library binding differs')
    for path in sorted((out / 'inventory').iterdir()):
        if path.is_file():
            base.remember(records, path)
    manifest = dict(schema=SCHEMA, qualification='NOT_QUALIFIED', status='PREPARED166_NOT_QUALIFIED',
        producer=identity(Path(__file__).resolve()), frozen130=identity(HERE / 'frozen130.py'),
        requested_task_ids=args.task_ids, source_capture_complete12=True, taskset_complete=args.task_ids == list(range(12)),
        preflight=preflight,
        activity=identity(args.activity), source_root=str(ctx.root), source_context=ctx.source,
        original_capture_tool_context=report['tool_context'], original_capture_configuration_sha256=report['configuration_sha256'],
        tool_root=str(modules.root), ppa_root=str(args.ppa_root.absolute()), formality_root=str(args.formality_root.absolute()),
        target_root=str(args.target_root.absolute()), capture_mapped_context=capture, target_mapped_context=target,
        netlist=target['netlist'], analysis_sdc=target['constraints'], clock_scope=target['clock_scope'],
        mapped_sram_inventory=identity(inventory_path), implementation_controls=impl, mapping=identity(mapping_path),
        strip_path=base.STRIP, pt=tool, library_compiler_root=environment.get('SYNOPSYS_LC_ROOT'),
        limitations=REVIEW, method='RTL120 activity plus independent own155 final target; averaged full-SoC PT diagnostics', tasks=[])
    for task_id in args.task_ids:
        task = report['tasks'][task_id]
        directory = out / ('task_%02d' % task_id)
        directory.mkdir()
        receipt = bridge.relocate(task['saif']['path'], mapping_path, inventory_path,
                                  directory / 'task-mapped.saif', base.STRIP, directory / 'task-mapped-receipt.json')
        states = base.measured_pins(modules, directory / 'task-mapped.saif', actual, task['normalization']['alias_unknown_bit_ticks'])
        need(receipt['measured_unknown_bit_ticks'] == states['alias_unknown_bit_ticks'] and
             receipt['duration_ticks'] == task['activity_window']['duration_ticks'], '166 unknown dwell/duration changed')
        write(directory / 'measured-sram-pins.json', states)
        item = dict(task_id=task_id, directory=directory.name, saif=identity(directory / 'task-mapped.saif'),
            canonical_saif=identity(task['saif']['path']), mapped_macro_bridge=identity(directory / 'task-mapped-receipt.json'),
            mapped_macro_bridge_receipt=receipt, measured_sram_pin_states=identity(directory / 'measured-sram-pins.json'),
            measured_summary=states['measured_summary'], activity_window=task['activity_window'], macro_names=sorted(actual),
            completion_marker='XU_S2E166_FINAL155_POWER_TASK_%02d_%s' % (task_id, uuid.uuid4().hex),
            expected_reports=modules.common.report_names() + ['update-power.rpt'])
        (directory / 'power.tcl').write_text(power_tcl(modules, impl, target, item))
        item['script'] = identity(directory / 'power.tcl')
        manifest['tasks'].append(item)
        for key in ['saif', 'mapped_macro_bridge', 'measured_sram_pin_states', 'script']:
            base.check_record(item[key], records)
        state.update(phase='prepared-task-%02d' % task_id, input_sha256_before=dict(records))
        write(out / 'result.json', state)
    ctx.recheck()
    need(checked_target(modules, args.target_root, args.ppa_root, capture, ctx.source, records) == target,
         'own155 target changed during preparation')
    base.verify_inputs(records)
    manifest['input_sha256'] = dict(records)
    write(out / 'prepared.json', manifest)
    state.update(status='PREPARED166_NOT_QUALIFIED', phase='prepared', prepared=identity(out / 'prepared.json'),
                 input_sha256_before=dict(records), input_sha256_after=current_hashes(records), finished_utc=now())
    write(out / 'result.json', state)
    return manifest


def verify_prepared(out, manifest, modules, full_context=True):
    out = Path(out).absolute()
    ids = manifest['requested_task_ids']
    need(ids in [[0], list(range(12))] and manifest['schema'] == SCHEMA and manifest['qualification'] == 'NOT_QUALIFIED' and
         manifest['source_capture_complete12'] is True and manifest['taskset_complete'] == (ids == list(range(12))) and
         [t['task_id'] for t in manifest['tasks']] == ids, '166 complete requested taskset differs')
    need(manifest['producer'] == identity(Path(__file__).resolve()) and manifest['frozen130'] == identity(HERE / 'frozen130.py'),
         '166 or frozen130 producer changed')
    base.verify_inputs(manifest['input_sha256'])
    need(modules.context.tool_identity() == manifest['original_capture_tool_context'] and
         modules.context.source_identity(manifest['source_root']) == manifest['source_context'], '166 source/capture tools changed')
    capture = manifest['capture_mapped_context']
    target = manifest['target_mapped_context']
    need((ids == [0]) == (manifest.get('preflight') is None), 'only full12 must have a successful task0 preflight')
    need(manifest['netlist'] == target['netlist'] == identity(target['netlist']['path']) and
         manifest['netlist']['sha256'] == NET155 and manifest['analysis_sdc'] == target['constraints'] and
         manifest['analysis_sdc']['sha256'] == base.SDC and manifest['clock_scope'] == target['clock_scope'] and
         manifest['clock_scope']['sha256'] == SCOPE155 and manifest['strip_path'] == base.STRIP,
         '166 separate own155 target/SDC/clock/full-DUT scope differs')
    activity = read(manifest['activity']['path'])
    base.complete_taskset(activity)
    need(activity['configuration']['mapped_context'] == capture and target['capture_mapped_context'] == capture and
         activity['configuration_sha256'] == manifest['original_capture_configuration_sha256'],
         'original120 capture must retain89/109 identity separately from155 target')
    impl = read(Path(manifest['ppa_root']) / 'ppa/prepared.json')['implementation']
    need(manifest['implementation_controls'] == impl and {r['sha256'] for r in impl['libraries']} == base.LIBRARIES,
         '166 original implementation/two libraries differ')
    if full_context:
        need(modules.mapped(manifest['source_root'], manifest['ppa_root'], manifest['formality_root']) == capture,
             '166 actual capture89/109 proof changed')
        need(checked_target(modules, manifest['target_root'], manifest['ppa_root'], capture,
                            manifest['source_context'], {}) == target, '166 actual final155 own proof changed')
        if ids != [0]:
            need(checked_preflight(manifest['preflight']['root'], modules, target, capture, {}) == manifest['preflight'],
                 '166 task0 preflight changed')
    bridge = modules.bridge(manifest['mapping']['path'])
    inventory, actual, _ = bridge.inventory_macros(manifest['mapped_sram_inventory']['path'])
    need(manifest['mapped_sram_inventory'] == identity(manifest['mapped_sram_inventory']['path']) and
         inventory['netlist'] == target['netlist'] and inventory['constraints'] == target['constraints'] and
         inventory['libraries'] == [identity(row['path']) for row in impl['libraries']] and
         inventory['macros'] == base.inventory_rows(inventory['provenance']['raw_tsv']['path']),
         '166 actual native155 inventory target/libraries/macros differ')
    invscript = Path(inventory['provenance']['script']['path'])
    need(invscript.read_text() == inventory_tcl(modules, impl, target, inventory['provenance']['marker']),
         '166 target inventory Tcl semantics changed')
    base.checked_native_log(inventory['provenance']['pt_log']['path'], inventory['provenance']['marker'],
                            inventory['provenance']['execution']['returncode'])
    for task in manifest['tasks']:
        need(task['directory'] == 'task_%02d' % task['task_id'] and
             task['completion_marker'].startswith('XU_S2E166_FINAL155_POWER_TASK_%02d_' % task['task_id']),
             '166 task identity differs')
        for key in ['script', 'saif', 'mapped_macro_bridge', 'measured_sram_pin_states']:
            need(Path(task[key]['path']).parent == out / task['directory'] and identity(task[key]['path']) == task[key],
                 '166 prepared task path/bytes differ: ' + key)
        source = activity['tasks'][task['task_id']]
        need(task['activity_window'] == source['activity_window'] and task['canonical_saif'] == identity(source['saif']['path']) and
             task['macro_names'] == sorted(actual) and task['expected_reports'] == modules.common.report_names() + ['update-power.rpt'],
             '166 task actual activity/window/native macro/report list differs')
        need(Path(task['script']['path']).read_text() == power_tcl(modules, impl, target, task),
             '166 power Tcl semantic reconstruction differs')
        need(read(task['mapped_macro_bridge']['path']) == task['mapped_macro_bridge_receipt'], '166 mapped bridge receipt changed')
    return target


def run(args, state):
    out = args.out.absolute()
    manifest = read(out / 'prepared.json')
    prepared = identity(out / 'prepared.json')
    need(args.task_ids == manifest['requested_task_ids'], 'requested task IDs differ from immutable prepared166')
    modules = base.Modules(manifest['tool_root'])
    verify_prepared(out, manifest, modules)
    need(not (out / 'execution.json').exists(), '166 execution exists; observe it, never restart or overwrite')
    for task in manifest['tasks']:
        need(not any((out / task['directory'] / n).exists() for n in task['expected_reports'] + ['pt.log']),
             '166 native report/log exists; use a fresh campaign')
    environment = modules.common.execution_environment(Path(manifest['library_compiler_root']))
    tool = manifest['pt']
    need(identity(tool['path']) == tool, 'frozen PT executable changed')
    execution = dict(schema='xu-s2e-final-power166-execution-v1', qualification='NOT_QUALIFIED',
        status='RUNNING166_NOT_QUALIFIED', pid=os.getpid(), prepared=prepared, requested_task_ids=args.task_ids,
        taskset_complete=False, started_utc=now(), tasks=[], limitations=REVIEW,
        input_sha256_before=dict(manifest['input_sha256']), target_context=manifest['target_mapped_context'])
    write(out / 'execution.json', execution)
    state.update(status='RUNNING166_NOT_QUALIFIED', phase='power', input_sha256_before=manifest['input_sha256'],
                 execution=str(out / 'execution.json'))
    write(out / 'result.json', state)
    try:
        for task in manifest['tasks']:
            verify_prepared(out, manifest, modules, False)
            need(identity(out / 'prepared.json') == prepared, '166 preparation changed before native PT')
            execution['current_task_id'] = task['task_id']
            state['current_task_id'] = task['task_id']
            write(out / 'execution.json', execution)
            write(out / 'result.json', state)
            directory = out / task['directory']
            native = modules.common.execute([tool['path'], '-f', 'power.tcl'], directory, directory / 'pt.log', args.timeout, environment)
            entry = dict(task_id=task['task_id'], execution=native, status='NATIVE_UNREVIEWED_NOT_QUALIFIED')
            execution['tasks'].append(entry)
            write(out / 'execution.json', execution)
            verify_prepared(out, manifest, modules, False)
            need(identity(out / 'prepared.json') == prepared, '166 preparation changed during native PT')
            base.checked_native_log(directory / 'pt.log', task['completion_marker'], native['returncode'])
            entry['reports'] = modules.common.checked_reports(directory, task)
            need(base.PT_VERSION in (directory / 'tool-version.rpt').read_text(), 'native PT version report differs')
            entry['diagnostic'] = base.diagnostic(directory, task)
            entry['diagnostic']['unresolved'] = REVIEW
            entry['status'] = 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED'
            entry['frozen_inputs_sha256'] = canonical(manifest['input_sha256'])
            write(out / 'execution.json', execution)
            print('XU166_EXECUTED_TASK id=%d target=%s NOT_QUALIFIED' % (task['task_id'], NET155), flush=True)
        verify_prepared(out, manifest, modules)
        status = TASK0 if args.task_ids == [0] else FULL12
        need([t['task_id'] for t in execution['tasks']] == args.task_ids and
             all(t['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' for t in execution['tasks']),
             'all requested native PT executions required')
        summary = dict(status=status, qualification='NOT_QUALIFIED', requested_task_ids=args.task_ids,
            task_count=len(args.task_ids), taskset_complete=args.task_ids == list(range(12)),
            total_elapsed_cycles=sum(t['activity_window']['formal_elapsed_cycles'] for t in manifest['tasks']),
            sum_diagnostic_energy_j=str(sum(Decimal(t['diagnostic']['diagnostic_energy_j']) for t in execution['tasks'])),
            arithmetic_mean_reported_power_w=str(sum(Decimal(t['diagnostic']['power_components']['total_power_w'])
                for t in execution['tasks']) / Decimal(len(args.task_ids))),
            area=manifest['target_mapped_context']['area'], area_report=manifest['target_mapped_context']['area_report'],
            target_netlist=manifest['netlist'], capture_configuration_sha256=manifest['original_capture_configuration_sha256'],
            tasks=execution['tasks'], limitations=REVIEW)
        write(out / 'summary.json', summary)
        execution.update(status=status, taskset_complete=summary['taskset_complete'], summary=identity(out / 'summary.json'))
        state.update(status=status, phase='complete', summary=identity(out / 'summary.json'))
    except BaseException as error:
        execution.update(status=FAIL, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
        raise
    finally:
        execution.update(finished_utc=now(), input_sha256_after=current_hashes(manifest['input_sha256']))
        if execution['input_sha256_after'] != execution['input_sha256_before']:
            execution.update(status=FAIL, integrity_error='166 actual frozen input changed', taskset_complete=False)
        write(out / 'execution.json', execution)
    need(execution['status'] in [TASK0, FULL12], '166 execution failed or changed input')
    return execution


@contextmanager
def exclusive(out):
    with (out / 'controller-worker.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify', 'run', 'campaign'])
    for name in ['activity', 'source-root', 'tool-root', 'ppa-root', 'formality-root', 'target-root']:
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--preflight-root', type=Path,
                        help='successful same155 task0 output; mandatory before full12 prepare/campaign')
    parser.add_argument('--task-ids', type=selected_ids, default=list(range(12)))
    parser.add_argument('--pt', type=Path, default=Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell'))
    parser.add_argument('--lc-root', type=Path, default=Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
    parser.add_argument('--timeout', type=int, default=21600)
    parser.add_argument('--inventory-timeout', type=int, default=900)
    args = parser.parse_args(argv)
    need(args.timeout > 0 and args.inventory_timeout > 0, 'positive native execution timeout required')
    out = args.out.absolute()
    if args.action in ['prepare', 'campaign']:
        for name in ['activity', 'source_root', 'tool_root', 'ppa_root', 'formality_root', 'target_root']:
            need(getattr(args, name) is not None, 'explicit --' + name.replace('_', '-') + ' required')
        need((args.task_ids == [0]) == (args.preflight_root is None),
             '--preflight-root is required only for full12 and must be omitted for task0')
        need(not out.exists() and not out.is_symlink(), 'fresh166 output required; never overwrite or restart')
        out.mkdir(parents=True)
        state = dict(schema='xu-s2e-final-power166-result-v1', status='PREPARING166_NOT_QUALIFIED',
            qualification='NOT_QUALIFIED', pid=os.getpid(), started_utc=now(), requested_task_ids=args.task_ids,
            command=sys.argv if argv is None else [str(Path(__file__).resolve())] + list(argv), limitations=REVIEW)
        write(out / 'result.json', state)
    else:
        need(out.is_dir() and not out.is_symlink(), 'existing prepared166 output required')
        state = read(out / 'result.json')
        need(state['status'] == 'PREPARED166_NOT_QUALIFIED', 'only immutable prepared166 may run/verify; no automatic retries')
    with exclusive(out):
        try:
            if args.action in ['prepare', 'campaign']:
                prepare(args, state)
            if args.action == 'verify':
                manifest = read(out / 'prepared.json')
                need(args.task_ids == manifest['requested_task_ids'], 'verify task IDs differ')
                verify_prepared(out, manifest, base.Modules(manifest['tool_root']))
                print('VERIFIED_PREPARED166_NOT_QUALIFIED', flush=True)
                return 0
            if args.action in ['run', 'campaign']:
                run(args, state)
            state['finished_utc'] = now()
            state['input_sha256_after'] = current_hashes(state.get('input_sha256_before', {}))
            need(state['input_sha256_after'] == state.get('input_sha256_before', {}), '166 final input identities changed')
            write(out / 'result.json', state)
        except BaseException as error:
            state.update(status=FAIL, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc(),
                         finished_utc=now(), input_sha256_after=current_hashes(state.get('input_sha256_before', {})))
            write(out / 'result.json', state)
            raise
    print(state['status'] + ': ' + str(out), flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('FAIL166: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
