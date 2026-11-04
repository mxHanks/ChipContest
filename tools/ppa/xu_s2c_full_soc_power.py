#!/usr/bin/env python3
"""Run twelve independent full-SoC PT averaged-power diagnostics for actual S2c.

The original producer, raw SAIF, normalization and mapped inventory are inputs,
not a new simulation. Baseline entry points and their identity guards are intact.
Successful execution never qualifies conditional SRAM semantics or task energy.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import xu_candidate_joint_context as context
import xu_candidate_task_activity as candidate
import xu_candidate_joint_task_activity as joint

ROOT = HERE.parents[1]
common = context.load('xu_s2c_private_power_core', ROOT / 'tools/scripts/xu_soc_saif_power.py')
ppa = common.ppa
require, sha, write, identity = common.require, common.sha, common.write, common.identity
SCHEMA = 'xu-s2c-full-soc-power-prepared-v1'
EXECUTION = 'xu-s2c-full-soc-power-execution-v1'
CAPTURE_COMMIT = '5e75581319f926642ee7dc214ad825f3564a8e39'
CONFIG_SHA = '5b5cf619e8b0e5c2fc050abe8b589d5f7544a98eed174f4fc979bffe60fa6018'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
INVENTORY_SHA = '721ce0773570c54a8757a32165a47f399cd5c1ee9e3a57eab612dbeeeea15d8d'
REVIEW = ('DIAGNOSTIC_ONLY_NOT_QUALIFIED: full SoC averaged SAIF power; mapped annotation file/default/propagated '
          'coverage, unknown dwell and conditional SRAM internal_power/when semantics remain review pending. '
          'P times measured duration is diagnostic energy, not contest energy or a score.')


def check_identity(record, records):
    current = common.remember(records, record['path'], record['sha256'])
    require('bytes' not in record or record['bytes'] == current['bytes'], 'declared input size differs: ' + record['path'])
    return current


def capture_alias(report, records):
    """Load the actual old normalizer with its own original import context.

    No old/new module global is patched. Temporary import names are restored;
    this private normalizer retains the original clean producer root identity.
    """
    old_root = Path(report['tool_context']['root'])
    require(report['tool_context']['main_commit'] == CAPTURE_COMMIT, 'actual capture producer commit differs')
    require(context.original.git(old_root, 'rev-parse', 'HEAD') == CAPTURE_COMMIT, 'original capture checkout HEAD changed')
    old_context_path = old_root / 'tools/ppa/xu_candidate_activity_context.py'
    old_alias_path = old_root / 'tools/ppa/xu_candidate_sram_activity_alias.py'
    common.remember(records, old_context_path, context.FROZEN_DERIVATION['tools/ppa/xu_candidate_activity_context.py'])
    common.remember(records, old_alias_path, context.FROZEN_DERIVATION['tools/ppa/xu_candidate_sram_activity_alias.py'])
    old_context = context.load('xu_s2c_power_original_capture_context', old_context_path)
    require(old_context.tool_identity() == report['tool_context'], 'actual capture checkout context differs from original report')
    sentinel = object()
    saved = sys.modules.get('xu_candidate_activity_context', sentinel)
    try:
        sys.modules['xu_candidate_activity_context'] = old_context
        aliases = context.load('xu_s2c_power_original_capture_alias', old_alias_path)
    finally:
        if saved is sentinel:
            sys.modules.pop('xu_candidate_activity_context', None)
        else:
            sys.modules['xu_candidate_activity_context'] = saved
    return aliases


def mapped_bridge(aliases, mapping_path):
    """Compose a private unchanged bridge with the validated S2c mapping API."""
    bridge = context.load('xu_s2c_power_private_mapped_bridge', HERE / 'xu_saif_mapped_macros.py')
    bridge.alias = aliases

    def mapping_macros(path, strip_path):
        require(Path(path).resolve() == Path(mapping_path).resolve(), 'bridge mapping input differs')
        mapping, _ = aliases.validate_mapping(path)
        dut = aliases.slash(mapping['dut_scope'])
        require(strip_path == dut == common.STRIP, 'exact S2c DUT strip path differs')
        canonical = {}
        for row in mapping['macros']:
            full = aliases.slash(row['instance'])
            require(full.startswith(dut + '/'), 'S2c macro outside DUT')
            relative = full[len(dut) + 1:]
            require(relative not in canonical, 'S2c canonical macro collision')
            canonical[relative] = full
        require(len(canonical) == 336 and mapping['alias_bit_count'] == 22512, 'S2c macro/pin counts differ')
        return mapping, canonical

    bridge.mapping_macros = mapping_macros
    return bridge


def implementation(inventory):
    # Only the Tcl geometry/hierarchy controls are reused. This is not a filled
    # or qualified baseline implementation manifest and bypasses no old guard.
    return dict(top='xu_soc_ppa_top', source_profile='s2c-autogroup',
        libraries=[dict(row, role='standard_cell' if row['sha256'] == joint.STD_DB_SHA else 'sram')
                   for row in inventory['libraries']],
        memory_groups=[dict(name=name, logical_bits=bits, instance_pattern=ppa.MEMORY_SCOPES[name],
                            macro_ref='RAMSP1024X16', depth=1024, width=16, count=bits // 16384)
                       for name, bits in ppa.REQUIRED_BITS.items()],
        retained_instances=[dict(name=name, pattern=row[0], reference_pattern=row[1])
                            for name, row in sorted(ppa.RETAINED.items())])


def check_report(report, ctx, records, aliases):
    require(report.get('schema') == 'xu-s2c-isolated-task-activity-v1' and
            report.get('status') == 'COLLECTED_12_TASKS_REVIEW_PENDING' and
            report.get('taskset_complete') is True and report.get('requested_task_ids') == list(range(12)),
            'actual complete S2c 12-task capture required')
    config = report['configuration']
    require(report['configuration_sha256'] == CONFIG_SHA == context.canonical(config), 'actual S2c configuration hash differs')
    require(report['source_context'] == config['source_context'] == ctx.source, 'frozen actual S2c source context differs')
    require(report['tool_context'] == config['tool_context'], 'capture tool contexts disagree')
    require(config['nominal_hz'] == 150000000 and config['lf_hz'] == 32768 and config['precision_fs'] == 1 and
            config['activity_scope'] == candidate.SCOPE and config['monitoring_policy'] == 'rtl_on' and
            config['simulator_defines'] == ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION=1'],
            'actual clock/scope/precision/no-initialization contract differs')
    common.collect_identities(report, records)
    mapping_path = config['sram_alias_mapping']['path']
    mapping, pairs = aliases.validate_mapping(mapping_path)
    require(mapping == config['sram_alias'] and len(pairs) == 22512, 'actual source-guarded S2c observer mapping differs')
    require([task['task_id'] for task in report['tasks']] == list(range(12)), 'all task IDs 0..11 required')
    manifests = {}
    for task in report['tasks']:
        i = task['task_id']
        require(task['status'] == 'COLLECTED_REVIEW_PENDING' and task['configuration_sha256'] == CONFIG_SHA,
                'actual task collection/configuration differs')
        log = Path(task['boundary_log']['path']).read_text()
        layer, window, auto = candidate.checked_log(ctx, log, i)
        require((layer, window, auto) == (task['layer'], task['activity_window'], task['autogroup']),
                'actual task raw-log reconstruction differs: %d' % i)
        require(window['duration_ticks'] == 6604373333334 and window['formal_elapsed_cycles'] == 990656,
                'actual same-candidate window differs')
        cache = task['cache_policy']
        require(all(cache.get(k) is True for k in ('fresh_process', 'physical_zero_clear_observed',
                'all_fixture_commits_inside_window', 'fifo_ownership_reset_and_fresh_production_observed')) and
                cache.get('cross_task_reuse') is False, 'actual task clear/cache policy differs')
        manifest = common.read_json(task['input_manifest']['path'])
        manifests[str(i)] = manifest
        require(manifest.get('schema') == 'xu-soc-single-task-input-v1' and manifest.get('global_task_id') == i and
                manifest.get('original_layer') == 'layer_%02d' % i and manifest.get('simulator_layer') == 'layer_00',
                'actual input global/local task identity differs')
        common.collect_identities(manifest, records)
        files = manifest['files']
        validated = report['original_task_vectors'][i]
        require(validated['layer'] == i and len(files) == 4 and {r['tensor'] for r in files} == set(common.collector.TENSORS),
                'actual fixture tensors differ')
        for row in files:
            require(row['original']['sha256'] == row['materialized']['sha256'] == validated['sha256'][row['tensor'] + '.mem'],
                    'actual task original/materialized vector differs')
        norm = task['normalization']
        require(norm == common.read_json(Path(task['boundary_log']['path']).parent / 'task-normalization.json') and
                norm['schema'] == 'xu-s2c-sram-activity-normalization-v1' and
                norm['status'] == 'NORMALIZED_NOT_ANNOTATION_OR_POWER_QUALIFIED' and
                norm['macro_count'] == 336 and norm['alias_bit_count'] == 22512,
                'actual normalization receipt differs')
        require(norm['raw_saif']['path'] == task['raw_saif']['path'] and norm['raw_saif']['sha256'] == task['raw_saif']['sha256'] and
                norm['normalized_saif']['path'] == task['saif']['path'] and norm['normalized_saif']['sha256'] == task['saif']['sha256'],
                'task raw/normalized identities differ')
        common.remember(records, Path(task['boundary_log']['path']).parent / 'task-normalization.json')
        # Recompute every bit from the immutable raw native SAIF on the server.
        with tempfile.TemporaryDirectory(prefix='xu-s2c-full-power-normalize-') as tmp:
            fresh = aliases.normalize(norm['raw_saif']['path'], mapping_path, Path(tmp) / 'normalized.saif')
            require(fresh['normalized_saif']['sha256'] == norm['normalized_saif']['sha256'], 'recomputed normalized SAIF differs')
            for key in ('per_bit_comparison_sha256', 'alias_name_comparison_sha256', 'alias_unknown_bit_ticks',
                        'duration_ticks', 'timescale_seconds', 'macro_count', 'alias_bit_count'):
                require(fresh[key] == norm[key], 'recomputed normalization differs: ' + key)
        inspected = common.collector.inspect_activity(Path(task['saif']['path']), window,
                                                       common.collector.STATIC_SCOPE_DECLARATIONS)
        require(inspected == task['saif'], 'actual complete SAIF scope/time/macro inventory differs')
    require(context.canonical(manifests) == report['taskset_inputs_sha256'], 'actual task input set hash differs')
    return mapping_path


def prepare(activity, source_root, inventory_path, out):
    out = Path(out).absolute()
    require(not out.exists() and not out.is_symlink(), 'new output directory required')
    records = {}
    activity_id = common.remember(records, activity)
    report = common.read_json(activity)
    ctx = context.Context(source_root)
    aliases = capture_alias(report, records)
    mapping_path = check_report(report, ctx, records, aliases)
    inventory_id = common.remember(records, inventory_path)
    # Pinning the complete export prevents equal counts from accepting another design.
    require(inventory_id['sha256'] == INVENTORY_SHA, 'actual S2c inventory file SHA differs')
    bridge = mapped_bridge(aliases, mapping_path)
    inventory, actual, comparison = bridge.inventory_macros(inventory_path)
    require(inventory['design'] == 'xu_soc_ppa_top' and inventory['macro_count'] == 336 and inventory['pin_bit_count'] == 22512,
            'actual S2c mapped inventory dimensions/design differ')
    common.collect_identities(inventory, records)
    require(inventory['netlist']['sha256'] == report['configuration']['netlist']['sha256'] == joint.S2C_MAPPED_SHA and
            Path(inventory['netlist']['path']).resolve() == Path(report['configuration']['netlist']['path']).resolve(),
            'original actual S2c mapped netlist differs')
    require(inventory['constraints']['sha256'] == report['configuration']['constraints']['sha256'] == SDC_SHA and
            Path(inventory['constraints']['path']).resolve() == Path(report['configuration']['constraints']['path']).resolve(),
            'original actual analysis SDC differs')
    require(len(inventory['libraries']) == 2 and {r['sha256'] for r in inventory['libraries']} == {joint.STD_DB_SHA, joint.SRAM_DB_SHA},
            'exact actual SS standard-cell and SRAM DBs required')
    require(all(r['lib_cell'] == 'RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16' for r in actual.values()),
            'actual SS SRAM library cell differs')
    before = inventory['provenance']['input_sha256_before']
    require(before == inventory['provenance']['input_sha256_after'] and
            all(before.get(r['path']) == r['sha256'] for r in [inventory['netlist'], inventory['constraints']] + inventory['libraries']),
            'actual inventory original input identities differ')
    joint.check_raw_inventory_table(inventory['provenance']['raw_tsv']['path'], actual)
    impl = implementation(inventory)
    for path in (Path(__file__), Path(common.__file__), Path(ppa.__file__), Path(context.__file__), Path(candidate.__file__),
                 Path(joint.__file__), Path(context.original.__file__), HERE / 'xu_saif_mapped_macros.py',
                 Path(common.collector.__file__), Path(common.collector.activity.__file__), Path(common.collector.sram_alias.__file__)):
        common.remember(records, path)
    ctx.recheck()
    common.verify_inputs(records)
    out.mkdir(parents=True)
    manifest = dict(schema=SCHEMA, status='PREPARED_REVIEW_PENDING', qualification='NOT_QUALIFIED', review_pending=REVIEW,
        activity=activity_id, source_context=ctx.source, power_tool_context=ctx.joint_tool,
        original_capture_tool_context=report['tool_context'], original_capture_configuration_sha256=CONFIG_SHA,
        netlist=identity(inventory['netlist']['path']), analysis_sdc=identity(inventory['constraints']['path']),
        implementation_controls=impl, mapped_sram_inventory=inventory_id, strip_path=common.STRIP,
        method='twelve fresh independent PT processes; exact original complete SoC mapped netlist and recomputed native SRAM alias SAIF',
        requested_task_ids=list(range(12)), taskset_complete=True, input_sha256=records, producer_sha256=sha(__file__), tasks=[])
    for task in report['tasks']:
        i = task['task_id']
        directory = out / ('task_%02d' % i)
        directory.mkdir()
        receipt = bridge.relocate(task['saif']['path'], mapping_path, inventory_path,
                                  directory / 'task-mapped.saif', common.STRIP, directory / 'task-mapped-receipt.json')
        measured = aliases.activity_module().read_saif(directory / 'task-mapped.saif')
        by_path = {}
        for pin in measured['signals']:
            by_path.setdefault(pin['path'], []).append(pin)
        states = []
        for macro in actual.values():
            for pin in macro['pins']:
                found = by_path.get(common.STRIP + '/' + pin['full_name'], [])
                require(found and all(aliases.stats(x) == aliases.stats(found[0]) for x in found),
                        'mapped measured SRAM pin missing/conflicting: ' + pin['full_name'])
                states.append(dict(found[0], mapped_path=pin['full_name']))
        require(len(states) == 22512, 'all mapped pin states required')
        state_file = directory / 'measured-sram-pins.json'
        write(state_file, dict(status='MEASURED_ACTIVITY_NOT_POWER_QUALIFIED', pins=states,
                              alias_unknown_bit_ticks=task['normalization']['alias_unknown_bit_ticks'], review_pending=REVIEW))
        item = dict(task_id=i, directory=directory.name, saif=identity(directory / 'task-mapped.saif'),
                    canonical_saif=identity(task['saif']['path']), mapped_macro_bridge=identity(directory / 'task-mapped-receipt.json'),
                    mapped_macro_bridge_receipt=receipt, measured_sram_pin_states=identity(state_file),
                    activity_window=task['activity_window'], macro_names=sorted(actual),
                    completion_marker='XU_S2C_FULL_SOC_POWER_TASK_%02d_DIAGNOSTIC_COMPLETE_%s' % (i, uuid.uuid4().hex),
                    expected_reports=common.report_names() + ['update-power.rpt'])
        text = common.generate_tcl(impl, manifest['netlist'], manifest['analysis_sdc'], item, item['completion_marker'])
        text = text.replace('\nupdate_power\n', '\nredirect -file update-power.rpt {update_power}\n')
        require(text.count('redirect -file update-power.rpt {update_power}') == 1, 'full SoC update_power capture missing')
        text = text.replace('\nputs ' + ppa.tcl(item['completion_marker']),
                            '\nif {![file isfile update-power.rpt]} {error {missing update-power.rpt}}\nputs ' + ppa.tcl(item['completion_marker']))
        script = directory / 'power.tcl'
        script.write_text(text)
        item['script'] = identity(script)
        manifest['tasks'].append(item)
        print('PREPARED_S2C_FULL_SOC_POWER task=%d pins=22512 unknown_bit_ticks=%d' %
              (i, task['normalization']['alias_unknown_bit_ticks']), flush=True)
    ctx.recheck()
    common.verify_inputs(records)
    write(out / 'prepared.json', manifest)
    return manifest


def verify_prepared(out, manifest):
    require(manifest['schema'] == SCHEMA and manifest['producer_sha256'] == sha(__file__), 'new S2c power producer/schema differs')
    require(manifest['requested_task_ids'] == list(range(12)) and manifest['taskset_complete'] is True and
            [t['task_id'] for t in manifest['tasks']] == list(range(12)), 'complete prepared 12-task set required')
    common.verify_inputs(manifest['input_sha256'])
    require(context.full_tool_identity() == manifest['power_tool_context'], 'power tool checkout changed')
    require(context.original.source_identity(manifest['source_context']['root']) == manifest['source_context'], 'S2c source checkout changed')
    for task in manifest['tasks']:
        require(task['directory'] == 'task_%02d' % task['task_id'], 'prepared task directory differs')
        for key in ('script', 'saif', 'mapped_macro_bridge', 'measured_sram_pin_states'):
            row = task[key]
            require(Path(row['path']).absolute().parent == out / task['directory'], 'prepared task escapes output')
            check_identity(row, {})
        require(common.read_json(task['mapped_macro_bridge']['path']) == task['mapped_macro_bridge_receipt'], 'mapped bridge receipt changed')


def diagnostic(directory, task):
    text = (directory / 'power.rpt').read_text()
    require(re.search(r'^Design\s*:\s*xu_soc_ppa_top\s*$', text, re.M), 'full SoC power report design differs')
    for unit in ('Dynamic', 'Leakage'):
        require(re.findall(r'^\s*' + unit + r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')],
                'explicit watt power units required')
    values = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'),
                       ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*' + label + r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        require(len(hits) == 1, 'power diagnostic value missing/ambiguous: ' + label)
        value = Decimal(hits[0])
        require(value.is_finite() and value >= 0, 'power diagnostic nonfinite/negative')
        values[key + '_power_w'] = str(value)
    duration = Decimal(task['activity_window']['duration_ticks']) * Decimal('1e-15')
    return dict(status='PARTIAL_MODEL_DIAGNOSTIC_NOT_ENERGY_QUALIFIED', full_soc_design='xu_soc_ppa_top',
                report=identity(directory / 'power.rpt'), reported_power_precision='native report_power rounded text; no extra precision claimed',
                duration_seconds=str(duration), diagnostic_energy_j=str(Decimal(values['total_power_w']) * duration),
                power_components=values, unresolved=['mapped annotation coverage and defaults', 'SAIF time-unit/engine conversion review',
                'SRAM conditional edge/internal_power semantics and unknown Q absolute states',
                'same original mapped netlist timing/electrical/qualification gaps'], qualification='NOT_QUALIFIED')


def run(out, pt='pt_shell', timeout=21600, lc_root=None):
    out = Path(out).absolute()
    require(timeout > 0, 'positive per-task timeout required')
    manifest_path = out / 'prepared.json'
    prepared = identity(manifest_path)
    manifest = common.read_json(manifest_path)
    verify_prepared(out, manifest)
    require(not (out / 'execution.json').exists(), 'new prepared output required; execution exists')
    environment = common.execution_environment(lc_root)
    executable = shutil.which(pt, path=environment.get('PATH'))
    require(executable is not None, 'PrimeTime executable unavailable')
    tool = identity(Path(executable).resolve())
    for task in manifest['tasks']:
        require(not any((out / task['directory'] / n).exists() for n in task['expected_reports'] + ['pt.log']), 'existing PT report/log')
    receipt = dict(schema=EXECUTION, status='RUNNING_REVIEW_PENDING', qualification='NOT_QUALIFIED', review_pending=REVIEW,
        prepared=prepared, tool=tool, requested_task_ids=list(range(12)), taskset_complete=True,
        library_compiler_root=environment.get('SYNOPSYS_LC_ROOT'), input_sha256_before=dict(manifest['input_sha256']),
        started_utc=datetime.now(timezone.utc).isoformat(), tasks=[])
    write(out / 'execution.json', receipt)
    try:
        for task in manifest['tasks']:
            verify_prepared(out, manifest)
            check_identity(prepared, {})
            check_identity(tool, {})
            directory = out / task['directory']
            result = common.execute([tool['path'], '-f', 'power.tcl'], directory, directory / 'pt.log', timeout, environment)
            entry = dict(task_id=task['task_id'], execution=result, status='TOOL_EXECUTION_UNREVIEWED')
            receipt['tasks'].append(entry)
            write(out / 'execution.json', receipt)
            require(result['returncode'] == 0, 'PT nonzero return code on task %d' % task['task_id'])
            lines = (directory / 'pt.log').read_text(errors='replace').splitlines()
            require(lines.count(task['completion_marker']) == 1 and not any(common.DIAGNOSTIC.search(x) for x in lines),
                    'PT error or completion marker differs; inspect original log')
            entry['reports'] = common.checked_reports(directory, task)
            entry['diagnostic'] = diagnostic(directory, task)
            entry['status'] = 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING'
            write(out / 'execution.json', receipt)
            print('EXECUTED_S2C_FULL_SOC_POWER task=%d diagnostic_w=%s diagnostic_j=%s NOT_QUALIFIED' %
                  (task['task_id'], entry['diagnostic']['power_components']['total_power_w'], entry['diagnostic']['diagnostic_energy_j']), flush=True)
        receipt['status'] = 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING'
        durations = {entry['diagnostic']['duration_seconds'] for entry in receipt['tasks']}
        require(len(durations) == 1, 'actual twelve diagnostic durations differ')
        receipt['diagnostic_summary'] = dict(status='PARTIAL_MODEL_DIAGNOSTIC_NOT_ENERGY_QUALIFIED',
            task_count=12, same_duration_seconds=next(iter(durations)),
            arithmetic_mean_reported_power_w=str(sum(Decimal(e['diagnostic']['power_components']['total_power_w'])
                for e in receipt['tasks']) / Decimal(12)),
            sum_diagnostic_energy_j=str(sum(Decimal(e['diagnostic']['diagnostic_energy_j']) for e in receipt['tasks'])),
            qualification='NOT_QUALIFIED', review_pending=REVIEW)
    except Exception as error:
        receipt.update(status='FAIL', error=str(error))
        raise
    finally:
        receipt['input_sha256_after'] = {path: sha(path) if Path(path).is_file() and not Path(path).is_symlink() else None
                                         for path in manifest['input_sha256']}
        receipt['prepared_sha256_after'] = sha(manifest_path)
        receipt['tool_sha256_after'] = sha(tool['path'])
        changed = (receipt['input_sha256_after'] != receipt['input_sha256_before'] or
                   receipt['prepared_sha256_after'] != prepared['sha256'] or receipt['tool_sha256_after'] != tool['sha256'])
        if changed:
            receipt.update(status='FAIL', integrity_error='actual input/preparation/PT executable changed')
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        receipt['artifacts'] = {str(p.relative_to(out)): identity(p) for p in sorted(out.rglob('*'))
                                 if p.is_file() and not p.is_symlink() and p.name != 'execution.json'}
        write(out / 'execution.json', receipt)
        if changed:
            raise ValueError(receipt['integrity_error'])
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action')
    pre = sub.add_parser('prepare')
    pre.add_argument('--activity', required=True, type=Path)
    pre.add_argument('--source-root', required=True, type=Path)
    pre.add_argument('--mapped-sram-inventory', required=True, type=Path)
    pre.add_argument('--out', required=True, type=Path)
    exe = sub.add_parser('run')
    exe.add_argument('--out', required=True, type=Path)
    exe.add_argument('--pt', default='pt_shell')
    exe.add_argument('--timeout', default=21600, type=int)
    exe.add_argument('--lc-root', type=Path)
    args = parser.parse_args(argv)
    require(args.action in ('prepare', 'run'), 'choose prepare or run')
    result = (prepare(args.activity, args.source_root, args.mapped_sram_inventory, args.out) if args.action == 'prepare'
              else run(args.out, args.pt, args.timeout, args.lc_root))
    print(result['status'] + ': ' + str(args.out), flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
