#!/usr/bin/env python3
"""Prepare/run local independent averaged PrimeTime SAIF power probes.

Tool execution is evidence only. No annotation, SRAM power, energy or contest
qualification is inferred from a successful shell exit. Python standard library.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ppa'))
import xu_soc_task_activity as collector

_spec = importlib.util.spec_from_file_location('xu_saif_power_ppa', ROOT / 'tools/scripts/xu_soc_ppa.py')
ppa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ppa)
require, sha, digest, write, tcl = ppa.require, ppa.sha, ppa.digest, ppa.write, ppa.tcl
SCHEMA = 'xu-soc-saif-power-prepared-v1'
STRIP = 'tb_xu_soc_ppa/dut'
REVIEW = 'Annotation file/default/propagated coverage, every SRAM pin including unknown dwell, and SRAM Liberty when/internal_power operating modes require review; no energy or score claim'
DIAGNOSTIC = re.compile(r'^\s*(?:Error:|Error-|Fatal:|XU_FATAL:)|^\s*.*\b[1-9][0-9]* errors?\b', re.I)


def identity(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'required absolute regular non-symlink file missing: ' + str(path))
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def read_json(path):
    return json.loads(Path(path).read_text())


def remember(records, path, expected=None):
    record = identity(path)
    require(expected is None or record['sha256'] == expected, 'input SHA256 differs: ' + str(path))
    require(record['path'] not in records or records[record['path']] == record['sha256'], 'conflicting input identity: ' + str(path))
    records[record['path']] = record['sha256']
    return record


def collect_identities(value, records):
    """Freeze nested collector identities and absolute path->SHA256 source maps."""
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            ppa.absolute_file(value, 'activity/implementation identity')
            remember(records, value['path'], value['sha256'])
        for key, item in value.items():
            if isinstance(key, str) and key.startswith('/') and isinstance(item, str) and re.fullmatch('[0-9a-f]{64}', item):
                remember(records, key, item)
            else:
                collect_identities(item, records)
    elif isinstance(value, list):
        for item in value:
            collect_identities(item, records)


def verify_inputs(records):
    for path, expected in records.items():
        remember({}, path, expected)


def checked_sources(report, impl, inventory):
    captured = report['configuration']['rtl_sources_sha256']
    # Compare original RTL excluding the exact implementation replacements.
    # Vendor simulation model, generated testbench and bound observer are also
    # hash-bound, but are deliberately absent from synthesis inputs.
    for relative, record in inventory['platform_source'].items():
        if relative in impl['replacements']:
            continue
        path = str(Path(inventory['root']) / relative)
        require(captured.get(path) == record['sha256'], 'activity/implementation source differs: ' + relative)
    for record in list(impl['replacements'].values()) + impl['added_sources']:
        require(captured.get(record['path']) == record['sha256'], 'activity implementation adapter/top source differs: ' + record['path'])


def checked_task(task, report, records):
    task_id = task['task_id']
    require(task.get('status') == 'COLLECTED_REVIEW_PENDING' and task.get('local_scoreboard_layer') == 0,
            'task is not an actually collected isolated simulation')
    require(task.get('configuration_sha256') == report['configuration_sha256'], 'task configuration identity differs')
    cache = task.get('cache_policy', {})
    require(all(cache.get(key) is True for key in ('fresh_process', 'reset_cache_enable_zero_observed',
                'complete_fixture_matched_uploads_inside_window_observed', 'no_prior_task_in_process',
                'physical_initial_clearing_proven')), 'fresh-process clear/upload evidence missing')
    config = report['configuration']
    log = Path(task['boundary_log']['path']).read_text()
    schedule = config['firmware_configuration']['schedule']
    layer, window = collector.checked_log(log, task_id, schedule, True)
    require(task.get('layer') == layer and task.get('activity_window') == window, 'task boundary/window differs from raw simulation log')
    manifest = read_json(task['input_manifest']['path'])
    require(manifest.get('schema') == 'xu-soc-single-task-input-v1' and manifest.get('global_task_id') == task_id and
            manifest.get('original_layer') == 'layer_%02d' % task_id and manifest.get('simulator_layer') == 'layer_00',
            'task input global/local identity differs')
    files = manifest.get('files', [])
    require(len(files) == 4 and {x['tensor'] for x in files} == set(collector.TENSORS), 'four exact task tensors required')
    validated = report['original_task_vectors'][task_id]
    require(validated['layer'] == task_id, 'original task vector identity differs')
    for item in files:
        expected = validated['sha256'][item['tensor'] + '.mem']
        require(item['original']['sha256'] == item['materialized']['sha256'] == expected, 'original/materialized task tensor differs')
    collect_identities(manifest, records)
    alias_config = config['sram_pin_alias']
    collector.check_sram_pin_alias(alias_config)
    capture = task.get('sram_pin_alias_capture', {})
    require(capture.get('status') == 'NORMALIZED_REVIEW_PENDING', 'normalized SRAM pin capture required')
    for key, source in (('mapping_file', 'mapping_file'), ('observer_source', 'observer_source'), ('normalizer', 'helper')):
        require(capture.get(key) == alias_config[source], 'task SRAM observer/normalizer identity differs')
    receipt = read_json(capture['normalization_receipt']['path'])
    require(capture.get('normalization') == receipt and receipt.get('schema') == 'xu-sram-activity-normalization-v1' and
            receipt.get('status') == 'NORMALIZED_NOT_ANNOTATION_OR_POWER_QUALIFIED' and
            receipt.get('macro_count') == 336 and receipt.get('alias_bit_count') == 22512,
            'normalized SRAM receipt/count differs')
    require(capture['raw_saif'] == receipt['raw_saif'] and capture['normalized_saif'] == receipt['normalized_saif'], 'raw/normalized SAIF identity differs')
    require(receipt['normalized_saif']['sha256'] == task['saif']['sha256'] and
            receipt['normalized_saif']['path'] == task['saif']['path'], 'task must use its normalized SAIF')
    # Re-run the bijection against immutable measured raw activity. A forged
    # normalization receipt cannot turn guessed zero activity into pin evidence.
    with tempfile.TemporaryDirectory(prefix='xu-saif-power-check-') as directory:
        check = collector.sram_alias.normalize(receipt['raw_saif']['path'], alias_config['mapping_file']['path'], Path(directory) / 'normalized.saif')
        require(check['normalized_saif']['sha256'] == receipt['normalized_saif']['sha256'], 'normalized SAIF differs from measured raw aliases')
        for key in ('per_bit_comparison_sha256', 'alias_unknown_bit_ticks', 'duration_ticks', 'timescale_seconds'):
            require(check[key] == receipt[key], 'normalization evidence differs: ' + key)
    inspected = collector.inspect_activity(Path(task['saif']['path']), window, config['declared_static_scopes'])
    require(inspected == task['saif'], 'SAIF/window/scope inventory differs from collector record')
    measured = collector.activity.read_saif(task['saif']['path'])
    prefix = STRIP + '/'
    mapping = alias_config['mapping']
    pin_paths = {collector.sram_alias.slash(m['instance']) + '/' + pin + ('[%d]' % bit if width > 1 else '')
                 for m in mapping['macros'] for pin, width in mapping['pin_widths'].items() for bit in range(width)}
    pins = [signal for signal in measured['signals'] if signal['path'] in pin_paths]
    by_path = {}
    for signal in pins:
        path = signal['path']
        if path in by_path:
            require(collector.sram_alias.equivalent(signal, by_path[path]), 'duplicate native SRAM pin statistics differ')
        by_path[path] = signal
    require(set(by_path) == pin_paths, 'missing measured SRAM pin state')
    return dict(task_id=task_id, saif=identity(task['saif']['path']), activity_window=window,
                input_manifest=identity(task['input_manifest']['path']), boundary_log=identity(task['boundary_log']['path']),
                macro_names=sorted(collector.sram_alias.slash(m['instance'])[len(prefix):] for m in mapping['macros']),
                measured_sram_pin_states=[dict(by_path[path], mapped_path=path[len(prefix):]) for path in sorted(by_path)],
                unknown_state_policy='TX/TZ/TB retained, including disabled DTCM; unknown state does not mean zero power')


def checked_activity(report, impl, inventory, netlist, constraints, task_ids, records):
    require(report.get('schema') == 'xu-soc-isolated-task-activity-v1', 'activity collector schema differs')
    ids = report.get('requested_task_ids')
    require(isinstance(ids, list) and ids and ids == sorted(set(ids)) and all(type(x) is int and 0 <= x < 12 for x in ids), 'collector task IDs invalid')
    complete = ids == list(range(12))
    require(report.get('taskset_complete') is complete and report.get('status') ==
            ('COLLECTED_12_TASKS_REVIEW_PENDING' if complete else 'PARTIAL_COLLECTED_REVIEW_PENDING'), 'collector is incomplete, failed, or not simulated')
    require([x.get('task_id') for x in report.get('tasks', [])] == ids, 'collector task list differs')
    require(set(task_ids) <= set(ids), 'requested tasks absent from completed collector')
    require(report.get('clear_task_before_window') is True and report.get('sram_pin_alias') is True, 'request-window clearing and normalized SRAM pin observer required')
    require(report.get('nominal_hz') == 150000000 and report.get('clock_mode') == 'nominal150', 'nominal150 activity required')
    config = report['configuration']
    for key in ('binary', 'vendor_model', 'firmware_build', 'firmware_input_sources_sha256', 'helpers', 'runner', 'build_command'):
        require(report.get(key), 'collector input/tool evidence missing: ' + key)
    for key in ('firmware_image', 'firmware_elf', 'original_tb', 'testbench', 'vendor_model', 'rtl_sources_sha256'):
        require(config.get(key), 'collector configuration identity missing: ' + key)
    require(report.get('configuration_sha256') == collector.activity.canonical_hash(config), 'activity configuration hash differs')
    require(config.get('activity_scope') == collector.SCOPE and config.get('monitoring_policy') == 'rtl_on', 'full DUT RTL activity scope differs')
    require(config.get('task_clear_recipe', {}).get('name') == 'cpu-mmio-clear-before-source-request-v1', 'source-request clear recipe required')
    require(config['netlist']['sha256'] == netlist['sha256'], 'activity netlist identity differs')
    require(config['constraints']['sha256'] == config.get('analysis_sdc_sha256') == constraints['sha256'] == impl['constraints']['sha256'], 'activity/implementation analysis SDC identity differs')
    require(report['runner']['sha256'] == sha(collector.__file__), 'collector producer changed')
    collect_identities(report, records)
    checked_sources(report, impl, inventory)
    manifests = {str(task['task_id']): read_json(task['input_manifest']['path']) for task in report['tasks']}
    require(report.get('taskset_inputs_sha256') == collector.activity.canonical_hash(manifests), 'collector task input set differs')
    return [checked_task(task, report, records) for task in report['tasks'] if task['task_id'] in task_ids]


def report_names():
    names = ['read-saif.rpt', 'inconsistent.rpt', 'tool-version.rpt', 'units.rpt', 'clocks.rpt',
             'check-timing.rpt', 'power.rpt', 'power-hierarchy.rpt', 'sram-power.rpt',
             'sram-library.rpt', 'sram-pins-before.rpt', 'sram-pins-after.rpt']
    for phase in ('before', 'after'):
        names += ['switching-%s.rpt' % phase, 'coverage-%s.rpt' % phase, 'unannotated-%s.rpt' % phase]
        names += ['source-%s-%s.rpt' % (source, phase) for source in ('file', 'default', 'propagated', 'no_switching_activity')]
    return names


def generate_tcl(impl, netlist, constraints, task, marker):
    _, libraries = ppa.library_paths(impl)
    body = ('set_app_var power_enable_analysis true\nset_app_var power_analysis_mode averaged\n'
            'set_app_var link_path [list * ' + ' '.join(tcl(path) for path in libraries) + ']\n'
            'redirect -file tool-version.rpt {puts $sh_product_version}\nread_verilog ' + tcl(netlist['path']) + '\n'
            'if {![link_design ' + tcl(impl['top']) + ']} {error {PT power link failed}}\n'
            'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + tcl(constraints['path']) + '\n' +
            ppa.clock_contract_checks() + 'set_propagated_clock [all_clocks]\nupdate_timing\n' + ppa.memory_checks(impl))
    body += 'set xu_expected_macros [list ' + ' '.join(tcl(name) for name in task['macro_names']) + ']\n'
    body += '''foreach_in_collection xu_c $xu_all_macros {
  if {[lsearch -exact $xu_expected_macros [string map {. /} [get_object_name $xu_c]]] < 0} {error {mapped SRAM name differs from normalized activity}}
  if {[sizeof_collection [get_lib_cells -of_objects $xu_c]] != 1} {error {SRAM is unresolved or has no unique actual library cell}}
}
redirect -file units.rpt {report_units}
redirect -file clocks.rpt {report_clock}
redirect -file check-timing.rpt {check_timing -verbose}
'''
    body += 'redirect -file read-saif.rpt {\n  if {![read_saif ' + tcl(task['saif']['path']) + ' -strip_path ' + tcl(STRIP) + ' -report_inconsistent_annotation inconsistent.rpt]} {error {SAIF annotation command failed}}\n}\n'
    for phase in ('before', 'after'):
        if phase == 'after':
            body += 'update_power\n'
        for name, command in [('switching', 'report_switching_activity -hierarchy'),
                              ('coverage', 'report_switching_activity -coverage -hierarchy'),
                              ('unannotated', 'report_switching_activity -list_not_annotated -show_pin')]:
            body += 'redirect -file %s-%s.rpt {%s}\n' % (name, phase, command)
        for source in ('file', 'default', 'propagated', 'no_switching_activity'):
            body += 'redirect -file source-%s-%s.rpt {report_switching_activity -list_by_source %s -show_pin}\n' % (source, phase, source)
        body += 'redirect -file sram-pins-%s.rpt {\n' % phase
        body += '''  foreach_in_collection xu_c $xu_all_macros {
    set xu_pins [get_pins -quiet -of_objects $xu_c]
    if {[sizeof_collection $xu_pins] != 67} {error {SRAM signal pin count differs; review library interface}}
    foreach_in_collection xu_p $xu_pins {
      puts "XU_SRAM_PIN name=[string map {. /} [get_object_name $xu_p]]"
      report_attribute -application $xu_p
    }
  }
}
'''
    body += '''redirect -file power.rpt {report_power -verbose}
redirect -file power-hierarchy.rpt {report_power -hierarchy -verbose}
redirect -file sram-power.rpt {
  foreach_in_collection xu_c $xu_all_macros {
    puts "XU_SRAM_POWER_CELL name=[string map {. /} [get_object_name $xu_c]] ref=[get_attribute $xu_c ref_name]"
    report_power -cell_power -nosplit -include_lib_cells $xu_c
  }
}
redirect -file sram-library.rpt {
  puts "XU_SRAM_LIBERTY_WHEN_INTERNAL_POWER_MODE_REVIEW_PENDING"
  set xu_libcells [get_lib_cells -of_objects $xu_all_macros]
  if {[sizeof_collection $xu_libcells] < 1} {error {SRAM link has no actual library cells}}
  foreach_in_collection xu_lc $xu_libcells {
    puts "XU_SRAM_LIBRARY_CELL [get_object_name $xu_lc]"
    report_attribute -application $xu_lc
    set xu_libname [lindex [split [get_object_name $xu_lc] /] 0]
    report_lib -power_arcs [get_libs $xu_libname] $xu_lc
  }
  foreach_in_collection xu_lib [get_libs *] {report_lib [get_object_name $xu_lib]}
}
'''
    # Explicit report existence checks also run inside PT before its unique marker.
    for name in report_names():
        body += 'if {![file isfile ' + tcl(name) + ']} {error ' + tcl('missing report: ' + name) + '}\n'
        if name != 'inconsistent.rpt':
            body += 'if {[file size ' + tcl(name) + '] == 0} {error ' + tcl('empty report: ' + name) + '}\n'
    return ppa.guarded_tcl(body, marker)


def prepare(activity, implementation, prepared_path, netlist, constraints, out, task_ids=(0,), root=ROOT):
    out = Path(out).absolute()
    require(not out.exists() and not out.is_symlink(), 'output directory must be new; reuse is forbidden')
    require((implementation is None) != (prepared_path is None), 'choose exactly one implementation or PPA prepared manifest')
    records = {}
    activity_record = remember(records, activity)
    report = read_json(activity)
    netlist_record, constraints_record = remember(records, netlist), remember(records, constraints)
    prepared_record = None
    if prepared_path is not None:
        prepared_record = remember(records, prepared_path)
        prepared = read_json(prepared_path)
        require(prepared.get('schema') == 'xu-full-soc-ppa-prepared-v1', 'PPA prepared schema differs')
        root = Path(prepared['inventory']['root'])
        ppa.verify_prepared(root, Path(prepared_path).parent, prepared)
        require(prepared['generated_sha256']['constraints.sdc'] == constraints_record['sha256'], 'PPA prepared analysis SDC differs')
        impl = prepared['implementation']
        collect_identities(prepared, records)
        for relative, record in prepared['source_files'].items():
            remember(records, Path(prepared_path).parent / relative, record['sha256'])
        for name, value in prepared['generated_sha256'].items():
            remember(records, Path(prepared_path).parent / name, value)
    else:
        remember(records, implementation)
        impl = read_json(implementation)
    inventory = ppa.inventory(root)
    _, _, gaps = ppa.checked_implementation(impl, inventory, allow_unqualified=True)
    require(sum(group['count'] for group in impl['memory_groups']) == 336 and
            {group['macro_ref'] for group in impl['memory_groups']} == {'RAMSP1024X16'},
            'normalized 336-macro collector does not cover this implementation profile')
    collect_identities(impl, records)
    task_ids = list(task_ids)
    require(task_ids and task_ids == sorted(set(task_ids)) and all(type(x) is int and 0 <= x < 12 for x in task_ids), 'task IDs must be unique increasing values in 0..11')
    tasks = checked_activity(report, impl, inventory, netlist_record, constraints_record, task_ids, records)
    for path in (Path(__file__), Path(ppa.__file__), Path(collector.__file__), Path(collector.activity.__file__), Path(collector.sram_alias.__file__)):
        remember(records, path)
    verify_inputs(records)
    full = task_ids == list(range(12)) and report['taskset_complete']
    out.mkdir(parents=True)
    manifest = dict(schema=SCHEMA, status=('PREPARED_REVIEW_PENDING' if full else 'PARTIAL_PREPARED_REVIEW_PENDING'),
                    qualification='NOT_QUALIFIED', review_pending=REVIEW, method='one independent averaged PT process per task; read_saif normalized measured activity',
                    activity=activity_record, ppa_prepared=prepared_record, implementation=impl, root=str(Path(root).resolve()),
                    netlist=netlist_record, analysis_sdc=constraints_record, strip_path=STRIP,
                    requested_task_ids=task_ids, taskset_complete=full, collector_taskset_complete=report['taskset_complete'],
                    qualification_gaps=gaps, input_sha256=records, producer_sha256=sha(__file__), tasks=[])
    for task in tasks:
        directory = out / ('task_%02d' % task['task_id'])
        directory.mkdir()
        marker = 'XU_SOC_SAIF_POWER_TASK_%02d_COMPLETE_REVIEW_PENDING_%s' % (task['task_id'], uuid.uuid4().hex)
        states = directory / 'measured-sram-pins.json'
        write(states, dict(status='MEASURED_ACTIVITY_NOT_POWER_QUALIFIED', pins=task.pop('measured_sram_pin_states'),
                           unknown_state_policy=task['unknown_state_policy'], review_pending=REVIEW))
        script = directory / 'power.tcl'
        script.write_text(generate_tcl(impl, netlist_record, constraints_record, task, marker))
        task.update(directory=directory.name, script=identity(script), measured_sram_pin_states=identity(states),
                    completion_marker=marker, expected_reports=report_names())
        manifest['tasks'].append(task)
    verify_inputs(records)
    write(out / 'prepared.json', manifest)
    return manifest


def verify_prepared(out, manifest):
    require(manifest.get('schema') == SCHEMA and manifest.get('producer_sha256') == sha(__file__), 'power preparation producer/schema changed')
    verify_inputs(manifest['input_sha256'])
    ids = manifest.get('requested_task_ids')
    require(ids and ids == sorted(set(ids)) and all(type(x) is int and 0 <= x < 12 for x in ids), 'prepared task IDs invalid')
    require([task.get('task_id') for task in manifest['tasks']] == ids and
            manifest.get('taskset_complete') is (ids == list(range(12)) and manifest.get('collector_taskset_complete') is True),
            'prepared taskset/completion identity differs')
    for task in manifest['tasks']:
        require(Path(task['directory']).name == task['directory'], 'invalid task output directory')
        for key in ('script', 'measured_sram_pin_states'):
            record = task[key]
            require(Path(record['path']).absolute().parent == out / task['directory'], 'prepared task path escapes output')
            remember({}, record['path'], record['sha256'])
    ppa.checked_implementation(manifest['implementation'], ppa.inventory(manifest['root']), allow_unqualified=True)


def execute(command, directory, log_path, timeout, environment=None):
    started = datetime.now(timezone.utc).isoformat()
    with log_path.open('x') as log:
        log.write(json.dumps(dict(command=command, cwd=str(directory), started_utc=started, timeout_seconds=timeout)) + '\n')
        log.flush()
        process = subprocess.Popen(command, cwd=str(directory), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                   env=os.environ.copy() if environment is None else environment, start_new_session=True)
        try:
            rc = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(process.pid, signal.SIGKILL)
            rc = process.wait()
            log.write('\nXU_FATAL: PT timeout; process group killed\n')
    return dict(command=command, cwd=str(directory), returncode=rc, started_utc=started,
                finished_utc=datetime.now(timezone.utc).isoformat(), log=identity(log_path))


def checked_reports(directory, task):
    reports = {}
    for name in task['expected_reports']:
        record = identity(directory / name)
        require(name == 'inconsistent.rpt' or record['bytes'] > 0, 'missing/empty report: ' + name)
        with (directory / name).open(errors='replace') as report:
            require(not any(DIAGNOSTIC.search(line) for line in report), 'PT diagnostic failure in report: ' + name)
        reports[name] = record
    power = (directory / 'sram-power.rpt').read_text(errors='replace')
    names = re.findall(r'^XU_SRAM_POWER_CELL name=(.+) ref=(\S+)$', power, re.M)
    require(len(names) == len(task['macro_names']) and sorted(name for name, ref in names) == task['macro_names'] and
            all(ref == 'RAMSP1024X16' for name, ref in names), 'missing/duplicate/unexpected SRAM power cell report')
    expected_pins = sorted(pin['mapped_path'] for pin in read_json(task['measured_sram_pin_states']['path'])['pins'])
    for phase in ('before', 'after'):
        names = re.findall(r'^XU_SRAM_PIN name=(.+)$', (directory / ('sram-pins-%s.rpt' % phase)).read_text(), re.M)
        require(sorted(names) == expected_pins, 'missing/duplicate/unexpected SRAM pin report: ' + phase)
    return reports


def execution_environment(lc_root=None):
    environment = os.environ.copy()
    if lc_root is not None:
        lc_root = Path(lc_root).resolve()
        require(lc_root.is_dir() and (lc_root / 'bin').is_dir(), 'Library Compiler root/bin directory missing')
        environment['SYNOPSYS_LC_ROOT'] = str(lc_root)
        environment['PATH'] = str(lc_root / 'bin') + os.pathsep + environment.get('PATH', '')
    return environment


def run(out, pt='pt_shell', timeout=21600, lc_root=None):
    out = Path(out).absolute()
    require(type(timeout) is int and timeout > 0, 'positive timeout required')
    environment = execution_environment(lc_root)
    manifest_path = out / 'prepared.json'
    manifest_record = identity(manifest_path)
    manifest = read_json(manifest_path)
    require(not (out / 'execution.json').exists(), 'execution output exists; prepare a new output directory')
    verify_prepared(out, manifest)
    for task in manifest['tasks']:
        directory = out / task['directory']
        require(not any((directory / name).exists() for name in task['expected_reports'] + ['pt.log']), 'task reports/log already exist; reuse forbidden')
    executable = shutil.which(pt, path=environment.get('PATH'))
    require(executable is not None, 'PT executable not found: ' + pt)
    executable = str(Path(executable).resolve())
    tool = identity(executable)
    receipt = dict(schema='xu-soc-saif-power-execution-v1', status='RUNNING_REVIEW_PENDING', qualification='NOT_QUALIFIED',
                   prepared=manifest_record, tool=tool, input_sha256_before=dict(manifest['input_sha256']),
                   requested_task_ids=manifest['requested_task_ids'], taskset_complete=manifest['taskset_complete'],
                   library_compiler_root=environment.get('SYNOPSYS_LC_ROOT'),
                   review_pending=REVIEW, tasks=[], started_utc=datetime.now(timezone.utc).isoformat())
    write(out / 'execution.json', receipt)
    try:
        for task in manifest['tasks']:
            verify_prepared(out, manifest)
            remember({}, manifest_path, manifest_record['sha256'])
            remember({}, tool['path'], tool['sha256'])
            directory = out / task['directory']
            execution = execute([str(executable), '-f', 'power.tcl'], directory, directory / 'pt.log', timeout, environment)
            entry = dict(task_id=task['task_id'], execution=execution, status='TOOL_EXECUTION_UNREVIEWED')
            receipt['tasks'].append(entry)
            verify_prepared(out, manifest)
            remember({}, manifest_path, manifest_record['sha256'])
            remember({}, tool['path'], tool['sha256'])
            log = (directory / 'pt.log').read_text(errors='replace')
            require(execution['returncode'] == 0, 'PT nonzero return code: ' + str(execution['returncode']))
            require(log.splitlines().count(task['completion_marker']) == 1, 'missing or duplicate unique PT completion marker')
            require(not any(DIAGNOSTIC.search(line) for line in log.splitlines()), 'PT diagnostic failure; inspect ' + str(directory / 'pt.log'))
            entry['reports'] = checked_reports(directory, task)
            write(out / 'execution.json', receipt)
        receipt['status'] = ('EXECUTED_REVIEW_PENDING' if manifest['taskset_complete'] else 'PARTIAL_EXECUTED_REVIEW_PENDING')
    except Exception as error:
        receipt.update(status='FAIL', error=str(error))
        raise
    finally:
        receipt['input_sha256_after'] = {path: (sha(path) if Path(path).is_file() and not Path(path).is_symlink() else None) for path in manifest['input_sha256']}
        changed = receipt['input_sha256_after'] != receipt['input_sha256_before']
        receipt['prepared_sha256_after'] = sha(manifest_path) if manifest_path.is_file() and not manifest_path.is_symlink() else None
        receipt['tool_sha256_after'] = sha(tool['path']) if Path(tool['path']).is_file() and not Path(tool['path']).is_symlink() else None
        changed = changed or receipt['prepared_sha256_after'] != manifest_record['sha256'] or receipt['tool_sha256_after'] != tool['sha256']
        if changed:
            receipt.update(status='FAIL', integrity_error='input/preparation/tool identity changed during execution')
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        receipt['artifacts'] = {str(path.relative_to(out)): identity(path) for path in sorted(out.rglob('*')) if path.is_file() and not path.is_symlink() and path.name != 'execution.json'}
        write(out / 'execution.json', receipt)
        if changed:
            raise ValueError(receipt['integrity_error'])
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action')
    pre = sub.add_parser('prepare')
    pre.add_argument('--activity', type=Path, required=True)
    group = pre.add_mutually_exclusive_group(required=True)
    group.add_argument('--implementation', type=Path)
    group.add_argument('--ppa-prepared', type=Path)
    pre.add_argument('--netlist', type=Path, required=True)
    pre.add_argument('--constraints', type=Path, required=True)
    pre.add_argument('--root', type=Path, default=ROOT)
    pre.add_argument('--task-ids', type=collector.parse_task_ids, default=[0])
    pre.add_argument('--out', type=Path, required=True)
    exe = sub.add_parser('run')
    exe.add_argument('--out', type=Path, required=True)
    exe.add_argument('--pt', default='pt_shell')
    exe.add_argument('--timeout', type=int, default=21600)
    exe.add_argument('--lc-root', type=Path, help='actual Library Compiler root; prepend its bin and set SYNOPSYS_LC_ROOT for PT')
    args = parser.parse_args(argv)
    require(args.action is not None, 'choose prepare or run')
    if args.action == 'prepare':
        result = prepare(args.activity, args.implementation, args.ppa_prepared, args.netlist, args.constraints, args.out, args.task_ids, args.root)
    else:
        result = run(args.out, args.pt, args.timeout, args.lc_root)
    print(result['status'] + ': ' + str(args.out))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
