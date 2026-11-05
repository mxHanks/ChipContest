#!/usr/bin/env python3
"""Own S2e89/109 + completed S2e120 twelve-task full-SoC PT diagnostics.

Standalone coordinator; Python 3.6+, standard library. No network, credentials,
source edits, library edits, remapping, SDC edits, or implicit qualification.
The immutable original capture checkout supplies the frozen common routines.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
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

SCHEMA = 'xu-s2e-full-soc-power130-prepared-v1'
EXECUTION = 'xu-s2e-full-soc-power130-execution-v1'
CAPTURE_COMMIT = '2c791bcd46499ca6dee4db26ae46ffc6a9e67c32'
MAIN = '5bf123bfead8f2a37f97f3234d4e40ce8201aae9'
NETLIST = '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
LIBRARIES = {
    'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
    'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f',
}
FROZEN = {
    'tools/scripts/xu_soc_saif_power.py': '31664b12ac657879e932f57a1b6c9092121b5355c9db571a474340ada964c0cc',
    'tools/ppa/xu_saif_mapped_macros.py': '316599b0a5cd30203894eeaefdcbbdaf1ad91a7fb08a8d35bce7278549eb734c',
    'tools/ppa/xu_s2e_activity_context.py': '0eedf615e6f6f196fb328407849e4973dff8e036b5ea583c833df260e58d5682',
    'tools/ppa/xu_s2e_task_activity.py': '23872aa782dfde7ea7806a02f23c275a8a59bebc1d5a0dbe0dec5de5f39d1ad0',
    'tools/ppa/xu_s2e_sram_activity_alias.py': 'cbcf1454f647da5a53cb13d851d9bda551d4476e234e8fb01ace9abfe29fba94',
    'tools/ppa/xu_s2e_formality_audit.py': 'fb468c230b528a364e2f013684e80b0135b7debc75746f90a62057f18aa91bbc',
}
STRIP = 'tb_xu_soc_ppa/dut'
PT_VERSION = 'T-2022.03-SP5-1'
REVIEW = [
    'DIAGNOSTIC_ONLY_NOT_QUALIFIED: full-SoC averaged SAIF power; no contest energy or score.',
    'Own source/DC/SVF/native109 proof does not establish full150MHz closure or numerical contest eligibility.',
    'Measured raw/normalized/mapped SAIF retain every TX/TZ/TB bit tick; unknown Q is not guessed zero power.',
    'Native x_probability=0 is an engine getter value, not proof of physically known Q; SAIF unknown conversion remains unresolved.',
    'Before/after means before/after EXPLICIT update_power; report_attribute getters can trigger lazy propagation/power.',
    'file/default/propagated sources and toggle coverage are distinct; default and inferred activity remain visible.',
    'SRAM conditional edge, when/internal_power and operating modes require an independent model/trajectory review.',
    'PT uses original propagated pre-CTS clocks and envelope divider scenario; setup/hold/electrical/unconstrained gaps remain.',
    '33697 CPU pretask zero writes are outside measured window; this run measures no clear-phase energy.',
    'The common PT routine is frozen and unmodified; only its private inventory/SAIF bridge selects the validated S2e capture.',
]
BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), 'regular non-symlink file required: ' + str(path))
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write(path, data):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')
    os.replace(str(temporary), str(path))


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def remember(records, path, expected=None):
    row = identity(path)
    need(expected is None or row['sha256'] == expected, 'input SHA differs: ' + row['path'])
    need(row['path'] not in records or records[row['path']] == row['sha256'], 'conflicting input identity')
    records[row['path']] = row['sha256']
    return row


def check_record(record, records):
    need(isinstance(record, dict) and isinstance(record.get('path'), str) and Path(record['path']).is_absolute() and
         isinstance(record.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', record['sha256']) is not None,
         'absolute actual file identity required')
    row = remember(records, record['path'], record['sha256'])
    need('bytes' not in record or (type(record['bytes']) is int and row['bytes'] == record['bytes']),
         'declared byte count differs: ' + row['path'])
    return row


def checked_capture_pair(left, right, records):
    """Collector identities may omit bytes; declared sizes still bind actual bytes.

    Compare actual file identities, not differently shaped receipt dictionaries.
    The original path and SHA must agree; no path relocation is accepted here.
    """
    need(left.get('path') == right.get('path') and left.get('sha256') == right.get('sha256'),
         'capture/normalization file path or SHA differs')
    actual_left = check_record(left, records)
    actual_right = check_record(right, records)
    need(actual_left == actual_right, 'capture/normalization actual bytes differ')
    return actual_left


def verify_inputs(records):
    for path, expected in records.items():
        remember({}, path, expected)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Modules:
    """Load original committed producer modules, without editing their guards."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.records = {}
        for relative, expected in sorted(FROZEN.items()):
            remember(self.records, self.root / relative, expected)
        # Source modules use their recorded directory and original import names.
        # Restore import namespace afterwards; private module objects retain the
        # exact original context and no shared module's globals are patched.
        old_path = list(sys.path)
        names = ['xu_s2e_activity_context', 'xu_s2e_sram_activity_alias']
        sentinel = object()
        saved = {name: sys.modules.get(name, sentinel) for name in names}
        try:
            sys.path.insert(0, str(self.root / 'tools/ppa'))
            self.context = load('xu_power130_original_context', self.root / 'tools/ppa/xu_s2e_activity_context.py')
            sys.modules['xu_s2e_activity_context'] = self.context
            self.alias = load('xu_power130_original_alias', self.root / 'tools/ppa/xu_s2e_sram_activity_alias.py')
            sys.modules['xu_s2e_sram_activity_alias'] = self.alias
            self.candidate = load('xu_power130_original_candidate', self.root / 'tools/ppa/xu_s2e_task_activity.py')
            self.common = load('xu_power130_frozen_common', self.root / 'tools/scripts/xu_soc_saif_power.py')
        finally:
            sys.path[:] = old_path
            for name, previous in saved.items():
                if previous is sentinel:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous
        self.ppa = self.common.ppa
        self.tool = self.context.tool_identity()
        need(self.tool['root'] == str(self.root) and self.tool['main_commit'] == CAPTURE_COMMIT,
             'exact clean original activity109 tool checkout required')
        # Freeze all actually loaded baseline/common dependencies as well.
        for module in (self.common, self.ppa, self.common.collector, self.common.collector.activity,
                       self.common.collector.sram_alias, self.common.mapped_macros):
            remember(self.records, module.__file__)

    def ctx(self, root):
        return self.context.Context(Path(root))

    def mapped(self, source, ppa, formality):
        result = self.context.checked_mapped_context(source, ppa, formality)
        need(result['netlist']['sha256'] == NETLIST and result['constraints']['sha256'] == SDC,
             'own actual S2e mapped/analysis SDC bytes required')
        need(result.get('formality_audit') and result['native_formality']['passing'] == 42338,
             'explicit own109 full native proof required')
        return result

    def bridge(self, mapping_path):
        # A new private bridge instance composes the exact S2e mapping API.
        # The frozen file and all baseline module instances remain unchanged.
        bridge = load('xu_power130_private_bridge', self.root / 'tools/ppa/xu_saif_mapped_macros.py')
        bridge.alias = self.alias

        def mapping_macros(path, strip):
            need(Path(path).resolve() == Path(mapping_path).resolve(), 'bridge mapping input differs')
            mapping, pairs = self.alias.validate_mapping(path)
            dut = self.alias.slash(mapping['dut_scope'])
            need(strip == dut == STRIP, 'exact full-DUT strip path required')
            canonical_macros = {}
            for macro in mapping['macros']:
                full = self.alias.slash(macro['instance'])
                need(full.startswith(dut + '/'), 'macro outside DUT')
                relative = full[len(dut) + 1:]
                need(relative not in canonical_macros, 'canonical macro collision')
                canonical_macros[relative] = full
            need(len(canonical_macros) == 336 and len(pairs) == 22512, 'complete mapping geometry required')
            return mapping, canonical_macros

        bridge.mapping_macros = mapping_macros
        return bridge


def complete_taskset(report):
    need(report.get('schema') == 'xu-s2e-isolated-task-activity-v1' and
         report.get('status') == 'COLLECTED_12_TASKS_REVIEW_PENDING' and
         report.get('taskset_complete') is True and report.get('requested_task_ids') == list(range(12)) and
         [row.get('task_id') for row in report.get('tasks', [])] == list(range(12)),
         'actual completed S2e full12 activity is required; running/task00/partial is insufficient')


def checked_runtime_sources(modules, report, ctx, mapping):
    config = report['configuration']
    expected_helpers = {
        'original_tb': ctx.base.TB,
        'candidate_contract': Path(ctx.contract.__file__),
        'candidate_soc_helper': Path(ctx.soc.__file__),
    }
    for key, path in expected_helpers.items():
        need(config[key] == modules.context.identity(path), 'actual frozen runtime helper differs: ' + key)
    expected_producers = [Path(modules.candidate.__file__), Path(modules.context.__file__), Path(modules.alias.__file__),
                          modules.root / 'tools/ppa/xu_s2e_activity_observer.svh']
    need(config['producer_sources'] == [modules.context.identity(p) for p in expected_producers], 'actual S2e producer list differs')
    binary = Path(report['binary']['path'])
    testbench = binary.parent / 'tb_xu_s2e_task_activity.sv'
    need(testbench.read_text() == modules.candidate.generate_tb(ctx), 'actual generated S2e TB differs from frozen producer')
    excluded = {ctx.base.RTL / 'general/sirv_sim_ram.v', ctx.base.RTL / 'perips/mem_1024x16.sv'}
    sources = sorted(p for p in ctx.base.RTL.rglob('*') if p.suffix in ('.v', '.sv') and p not in excluded)
    sources += [modules.root / 'tools/ppa' / name for name in (
        'xu_sirv_sram_adapter.sv', 'xu_weight_sram_adapter.sv', 'xu_shared_icb_sram.sv', 'xu_soc_ppa_top.sv')]
    vendor = [row for row in config['rtl_sources'] if Path(row['path']).name == 'RAMSP1024X16.v']
    need(len(vendor) == 1 and vendor[0]['sha256'] == '81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51',
         'same unmodified SRAM vendor model required')
    sources += [Path(vendor[0]['path']), testbench, Path(mapping['observer_source']['path'])]
    need(config['rtl_sources'] == [modules.context.identity(p) for p in sources], 'actual complete candidate RTL/runtime sources differ')
    filelist = binary.parent / 'rtl.f'
    need(filelist.read_text() == '\n'.join(str(p) for p in sources) + '\n', 'actual runtime RTL file list differs')
    expected_command = ctx.base.build_command('vcs', 'macro', binary.parent, filelist, True, 'nominal150')
    expected_command[0] = report['vcs_executable']['path']
    expected_command.insert(1, '-debug_region+cell')
    need(report['build_command'] == expected_command, 'actual VCS build options differ')
    firmware = config['firmware']
    need(read(config['firmware_build']['path']) == firmware, 'actual firmware-build receipt differs')
    wrapper = Path(firmware['wrapper']['path'])
    main = ctx.soc.TESTS / 'firmware/main.c'
    need(wrapper.read_text() == ctx.clear.firmware_wrapper(main, sha(main)), 'actual CPU clear wrapper differs')
    need(firmware['frozen_main'] == modules.context.identity(main), 'actual frozen firmware main differs')
    need(firmware['recipe'] == 's2e-cpu-legacy-33697-zero-clear-before-source-request-v1', 'actual CPU clear recipe differs')
    command = firmware['command']
    need(command and command[0].endswith('gcc'), 'actual firmware GCC command missing')
    expected_command = [command[0], '-march=rv32imac_zicsr2p0_zifencei2p0', '-mabi=ilp32', '-O2'] + ctx.contract.compiler_defines(ctx.configuration) + [
        '-fstack-usage', '-ffreestanding', '-fno-builtin', '-msmall-data-limit=0', '-nostdlib', '-nostartfiles',
        '-static', '-mcmodel=medany', '-Wl,--no-relax', '-T', str(ctx.soc.TESTS / 'firmware/link.ld'),
        str(ctx.soc.TESTS / 'firmware/start.S'), str(wrapper), str(ctx.soc.TESTS / 'firmware/accel.c'), '-o', firmware['elf']['path']]
    need(command == expected_command, 'actual frozen firmware build arguments differ')
    return [identity(filelist), identity(testbench)]


def check_report(modules, activity, source, ppa_root, formality, records):
    remember(records, activity)
    report = read(activity)
    complete_taskset(report)
    ctx = modules.ctx(source)
    mapped = modules.mapped(ctx.root, ppa_root, formality)
    config = report['configuration']
    need(report['configuration_sha256'] == canonical(config), 'activity configuration hash differs')
    need(report['source_context'] == config['source_context'] == ctx.source and
         report['tool_context'] == config['tool_context'] == modules.tool == ctx.tool and
         config['mapped_context'] == mapped, 'actual source/tool/own89/109 binding differs')
    need(config['nominal_hz'] == 150000000 and config['lf_hz'] == 32768 and config['precision_fs'] == 1 and
         config['numeric_format'] == 'signed16/40/48' and config['activity_scope'] == 'tb_xu_soc_ppa.dut' and
         config['monitoring_policy'] == 'rtl_on' and config['simulator_defines'] == ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION=1'],
         'fixed clock/format/full-scope/no-initialization configuration differs')
    need(config['netlist'] == mapped['netlist'] and config['constraints'] == mapped['constraints'],
         'activity own mapped/context path or bytes differ')
    need(report['firmware_build'] == config['firmware'] and config['firmware']['configuration'] == ctx.configuration,
         'actual candidate firmware contract differs')
    need(report['build_command'][0] == report['vcs_executable']['path'] and
         str(Path(report['binary']['path']).parent / 'soc') == report['binary']['path'],
         'capture executable/build identity missing')
    # Recursively rehash actual nested runtime/tool/proof identities, not just
    # matching two receipt dictionaries. Byte counts are checked separately.
    def collect(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                check_record(value, records)
            for key, item in value.items():
                if isinstance(key, str) and key.startswith('/') and isinstance(item, str) and re.fullmatch('[0-9a-f]{64}', item):
                    remember(records, key, item)
                else:
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(report)
    mapping_path = Path(config['sram_alias_mapping']['path'])
    mapping, pairs = modules.alias.validate_mapping(mapping_path)
    need(mapping == config['sram_alias'] and len(pairs) == 22512, 'source-guarded S2e mapping differs')
    for row in checked_runtime_sources(modules, report, ctx, mapping):
        check_record(row, records)
    manifests = {}
    for task in report['tasks']:
        task_id = task['task_id']
        need(task['status'] == 'COLLECTED_REVIEW_PENDING' and task['configuration_sha256'] == report['configuration_sha256'],
             'task status/configuration differs')
        directory = Path(task['boundary_log']['path']).parent
        task_result = directory / 'result.json'
        remember(records, task_result)
        need(read(task_result) == task, 'actual individual task receipt differs')
        layer, window, auto = modules.candidate.checked_log(ctx, Path(task['boundary_log']['path']).read_text(), task_id)
        need((layer, window, auto) == (task['layer'], task['activity_window'], task['autogroup']),
             'raw numeric/clock/clear/request/retirement log differs: %d' % task_id)
        need(window['formal_elapsed_cycles'] == 868343 and window['duration_ticks'] == 5788953333333,
             'actual S2e formal window differs from frozen task00 configuration')
        cache = task['cache_policy']
        need(all(cache.get(k) is True for k in ('fresh_process', 'physical_zero_clear_observed',
             'all_fixture_commits_inside_window', 'fifo_ownership_reset_and_fresh_production_observed')) and
             cache.get('cross_task_reuse') is False, 'actual clear/upload/cache ownership evidence missing')
        manifest = read(task['input_manifest']['path'])
        manifests[str(task_id)] = manifest
        need(manifest.get('schema') == 'xu-soc-single-task-input-v1' and manifest.get('global_task_id') == task_id and
             manifest.get('original_layer') == 'layer_%02d' % task_id and manifest.get('simulator_layer') == 'layer_00',
             'actual original/materialized global task identity differs')
        collect(manifest)
        validated = report['original_task_vectors'][task_id]
        need(validated['layer'] == task_id and len(manifest['files']) == 4 and
             {r['tensor'] for r in manifest['files']} == set(modules.common.collector.TENSORS), 'exact four fixture tensors required')
        for row in manifest['files']:
            need(row['original']['sha256'] == row['materialized']['sha256'] == validated['sha256'][row['tensor'] + '.mem'],
                 'exact frozen fixture bytes differ')
        normalization = task['normalization']
        normpath = directory / 'task-normalization.json'
        remember(records, normpath)
        need(read(normpath) == normalization and normalization['schema'] == 'xu-s2e-sram-activity-normalization-v1' and
             normalization['status'] == 'NORMALIZED_NOT_ANNOTATION_OR_POWER_QUALIFIED' and
             normalization['macro_count'] == 336 and normalization['alias_bit_count'] == 22512,
             'normalization receipt/schema/geometry differs')
        checked_capture_pair(task['raw_saif'], normalization['raw_saif'], records)
        checked_capture_pair(task['saif'], normalization['normalized_saif'], records)
        with tempfile.TemporaryDirectory(prefix='xu-s2e130-replay-') as temporary:
            fresh = modules.alias.normalize(task['raw_saif']['path'], mapping_path, Path(temporary) / 'normalized.saif')
            need(fresh['normalized_saif']['sha256'] == normalization['normalized_saif']['sha256'],
                 'fresh measured raw-to-normalized SAIF differs')
            for key in ('per_bit_comparison_sha256', 'alias_name_comparison_sha256', 'alias_unknown_bit_ticks',
                        'duration_ticks', 'timescale_seconds', 'macro_count', 'alias_bit_count',
                        'alias_name_encoding_counts', 'nonalias_raw_signal_count_preserved'):
                need(fresh[key] == normalization[key], 'fresh measured normalization differs: ' + key)
        inspected = modules.common.collector.inspect_activity(Path(task['saif']['path']), window,
                    modules.common.collector.STATIC_SCOPE_DECLARATIONS)
        need(inspected == task['saif'], 'actual SAIF complete full-scope/window inspection differs')
        print('REPLAYED_S2E130_ACTIVITY task=%d elapsed=%d unknown_bit_ticks=%d NOT_QUALIFIED' %
              (task_id, window['formal_elapsed_cycles'], normalization['alias_unknown_bit_ticks']), flush=True)
    need(canonical(manifests) == report['taskset_inputs_sha256'], 'complete taskset fixture manifest differs')
    ctx.recheck()
    return report, ctx, mapped, mapping_path


def inventory_tcl(ppa, impl, netlist, constraints, marker):
    _, libraries = ppa.library_paths(impl)
    body = ('redirect -file version.rpt {puts $sh_product_version}\n'
            'set_app_var link_path [list * ' + ' '.join(ppa.tcl(p) for p in libraries) + ']\n'
            'read_verilog ' + ppa.tcl(netlist['path']) + '\n'
            'if {![link_design xu_soc_ppa_top]} {error {inventory link failed}}\n'
            'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + ppa.tcl(constraints['path']) + '\n' +
            ppa.clock_contract_checks() + ppa.memory_checks(impl))
    body += '''set f [open macro-pins.tsv w]
puts $f "kind\tcell\tref_or_pin\tlibcell_or_direction"
set nc 0
set np 0
foreach_in_collection c $xu_all_macros {
  set name [get_object_name $c]
  set lc [get_lib_cells -of_objects $c]
  if {[sizeof_collection $lc] != 1} {error {macro library cell not unique}}
  puts $f "MACRO\t$name\t[get_attribute $c ref_name]\t[get_object_name $lc]"
  incr nc
  set pins [get_pins -quiet -of_objects $c]
  if {[sizeof_collection $pins] != 67} {error {macro 67 pins absent}}
  foreach_in_collection p $pins {
    puts $f "PIN\t$name\t[get_object_name $p]\t[get_attribute $p direction]"
    incr np
  }
}
close $f
if {$nc != 336 || $np != 22512} {error {actual macro/pin count differs}}
'''
    return ppa.guarded_tcl(body, marker)


def inventory_rows(path):
    lines = Path(path).read_text().splitlines()
    need(lines and lines[0] == 'kind\tcell\tref_or_pin\tlibcell_or_direction', 'inventory TSV header differs')
    macros, seen = {}, set()
    for line in lines[1:]:
        parts = line.split('\t')
        need(len(parts) == 4 and tuple(parts) not in seen, 'duplicate/malformed inventory TSV row')
        seen.add(tuple(parts))
        kind, cell, value, extra = parts
        if kind == 'MACRO':
            need(cell not in macros, 'duplicate inventory macro')
            macros[cell] = dict(instance=cell, ref_name=value, lib_cell=extra, pins=[])
        elif kind == 'PIN':
            need(cell in macros and value.startswith(cell + '/'), 'pin has missing/wrong macro parent')
            macros[cell]['pins'].append(dict(name=value[len(cell) + 1:], full_name=value, direction=extra))
        else:
            raise ValueError('unknown inventory TSV row type')
    need(len(macros) == 336 and sum(len(row['pins']) for row in macros.values()) == 22512, 'inventory complete counts differ')
    return [macros[name] for name in sorted(macros)]


def checked_native_log(path, marker, returncode):
    text = Path(path).read_text(errors='replace')
    need(returncode == 0 and text.splitlines().count(marker) == 1 and not any(BAD.search(line) for line in text.splitlines()),
         'native PT returncode/error/unique completion check failed')
    need('Version ' + PT_VERSION in text, 'same server PrimeTime2022.03-SP5-1 required')


def export_inventory(modules, impl, mapped, out, tool, environment, timeout, records):
    out.mkdir()
    marker = 'XU_S2E130_OWN_MAPPED_MACRO_INVENTORY_' + uuid.uuid4().hex
    script = out / 'export.tcl'
    script.write_text(inventory_tcl(modules.ppa, impl, mapped['netlist'], mapped['constraints'], marker))
    before = dict(records)
    before[str(script)] = sha(script)
    before[tool['path']] = tool['sha256']
    verify_inputs(before)
    state = dict(status='RUNNING_NOT_QUALIFIED', pid=os.getpid(), input_sha256_before=before,
                 qualification='NOT_QUALIFIED', limitations=REVIEW, marker=marker)
    write(out / 'state.json', state)
    try:
        state['execution'] = modules.common.execute([tool['path'], '-f', 'export.tcl'], out, out / 'pt.log', timeout, environment)
        write(out / 'state.json', state)
        checked_native_log(out / 'pt.log', marker, state['execution']['returncode'])
        macros = inventory_rows(out / 'macro-pins.tsv')
        result = dict(schema='xu-mapped-sram-pin-inventory-v1', status='EXPORTED_REVIEW_PENDING',
            design='xu_soc_ppa_top', macro_count=336, pin_bit_count=22512, netlist=identity(mapped['netlist']['path']),
            constraints=identity(mapped['constraints']['path']), libraries=[identity(row['path']) for row in impl['libraries']],
            macros=macros, provenance=dict(raw_tsv=identity(out / 'macro-pins.tsv'), pt_log=identity(out / 'pt.log'),
                script=identity(script), tool_version=identity(out / 'version.rpt'), tool=tool,
                input_sha256_before=before, input_sha256_after={p: sha(p) for p in before},
                execution=state['execution'], marker=marker, limitations=REVIEW))
        need(result['provenance']['input_sha256_after'] == before, 'inventory frozen inputs changed')
        write(out / 'inventory.json', result)
        state.update(status='EXPORTED_REVIEW_PENDING', inventory=identity(out / 'inventory.json'))
    except BaseException as error:
        state.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        state['input_sha256_after'] = {p: sha(p) if Path(p).is_file() and not Path(p).is_symlink() else None for p in before}
        if state['input_sha256_after'] != before:
            state.update(status='FAIL', integrity_error='inventory frozen input changed')
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write(out / 'state.json', state)
    need(state['status'] == 'EXPORTED_REVIEW_PENDING', 'inventory failed or changed inputs')
    return result


def measured_pins(modules, saif, actual, unknown_ticks):
    measured = modules.alias.activity_module().read_saif(saif)
    by_path = {}
    for pin in measured['signals']:
        by_path.setdefault(pin['path'], []).append(pin)
    states = []
    for macro in actual.values():
        for pin in macro['pins']:
            found = by_path.get(STRIP + '/' + pin['full_name'], [])
            need(found and all(modules.alias.stats(item) == modules.alias.stats(found[0]) for item in found),
                 'mapped measured SRAM pin missing/conflicting: ' + pin['full_name'])
            states.append(dict(found[0], mapped_path=pin['full_name']))
    need(len(states) == 22512 and len({row['mapped_path'] for row in states}) == 22512, 'all exact 22512 pins required')
    unknown = sum(row.get(k, 0) for row in states for k in ('TX', 'TZ', 'TB'))
    need(unknown == unknown_ticks and measured['timescale_seconds'] == '1E-15', 'mapped unknown dwell/timebase differs')
    q = [row for row in states if row['mapped_path'].rsplit('/', 1)[1].startswith('Q[')]
    summary = dict(pin_count=len(states), q_pin_count=len(q), measured_unknown_bit_ticks=unknown,
        q_tx_positive=sum(row.get('TX', 0) > 0 for row in q),
        q_tx_full_window=sum(row.get('TX', 0) == measured['duration_ticks'] for row in q),
        duration_ticks=measured['duration_ticks'], timescale_seconds=measured['timescale_seconds'])
    need(summary['q_pin_count'] == 5376, 'complete Q inventory required')
    return dict(status='MEASURED_INPUT_ACTIVITY_NOT_NATIVE_PT_OR_POWER_QUALIFIED', pins=states,
                measured_summary=summary, alias_unknown_bit_ticks=unknown, review_pending=REVIEW)


def power_tcl(modules, impl, netlist, constraints, task):
    text = modules.common.generate_tcl(impl, netlist, constraints, task, task['completion_marker'])
    need(text.count('\nupdate_power\n') == 1, 'unique frozen common update_power required')
    text = text.replace('\nupdate_power\n', '\nredirect -file update-power.rpt {update_power}\n')
    needle = '\nputs ' + modules.ppa.tcl(task['completion_marker'])
    need(text.count(needle) == 1, 'unique expected native completion marker required')
    return text.replace(needle, '\nif {![file isfile update-power.rpt]} {error {missing update-power.rpt}}\n' + needle)


def checked_power_tcl(modules, impl, netlist, constraints, task):
    expected = power_tcl(modules, impl, netlist, constraints, task)
    need(Path(task['script']['path']).read_text() == expected,
         'actual power Tcl differs from reconstructed own-context script')
    return sha(task['script']['path'])


def prepare(args):
    out = args.out.resolve()
    need(not out.exists() and not out.is_symlink(), 'fresh independent output required')
    modules = Modules(args.tool_root)
    records = dict(modules.records)
    remember(records, Path(__file__).resolve())
    report, ctx, mapped, mapping_path = check_report(modules, args.activity, args.source_root, args.ppa_root,
                                                    args.formality_root, records)
    ppa_path = args.ppa_root.resolve() / 'ppa/prepared.json'
    original_prepared = read(ppa_path)
    remember(records, ppa_path)
    impl = original_prepared['implementation']
    need(impl['source_profile'] == 's2e-paired-hi' and len(impl['libraries']) == 2 and
         {row['sha256'] for row in impl['libraries']} == LIBRARIES, 'exact own S2e implementation/SS DBs required')
    for row in impl['libraries']:
        check_record(row, records)
    environment = modules.common.execution_environment(args.lc_root)
    executable = shutil.which(str(args.pt), path=environment.get('PATH'))
    need(executable is not None, 'PT executable unavailable')
    tool = remember(records, Path(executable).resolve())
    verify_inputs(records)
    out.mkdir(parents=True)
    state = dict(status='PREPARING_NOT_QUALIFIED', pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
                 qualification='NOT_QUALIFIED', limitations=REVIEW, inputs_before=dict(records))
    write(out / 'preparation-state.json', state)
    try:
        inventory_path = out / 'inventory/inventory.json'
        inventory = export_inventory(modules, impl, mapped, out / 'inventory', tool, environment, args.inventory_timeout, records)
        bridge = modules.bridge(mapping_path)
        inventory, actual, comparison = bridge.inventory_macros(inventory_path)
        need(inventory['macros'] == inventory_rows(out / 'inventory/macro-pins.tsv'), 'actual inventory TSV/JSON differs')
        need(all(row['lib_cell'] == 'RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16' for row in actual.values()),
             'actual SS mapped SRAM cell differs')
        for path in sorted((out / 'inventory').iterdir()):
            if path.is_file():
                remember(records, path)
        manifest = dict(schema=SCHEMA, status='PREPARED_REVIEW_PENDING', qualification='NOT_QUALIFIED', limitations=REVIEW,
            activity=identity(args.activity), source_root=str(ctx.root), source_context=ctx.source,
            original_capture_tool_context=report['tool_context'], tool_root=str(modules.root),
            original_capture_configuration_sha256=report['configuration_sha256'], mapped_context=mapped,
            ppa_root=str(args.ppa_root.resolve()), formality_root=str(args.formality_root.resolve()),
            own_mapping_proof_policy='rehash source/own89 DC+SVF+native109 audit+acceptance; original89 status preserved',
            netlist=identity(mapped['netlist']['path']), analysis_sdc=identity(mapped['constraints']['path']),
            implementation_controls=impl, mapped_sram_inventory=identity(inventory_path), strip_path=STRIP,
            pt=tool, library_compiler_root=environment.get('SYNOPSYS_LC_ROOT'), producer=identity(Path(__file__).resolve()),
            method='twelve fresh independent PT processes; original full SoC mapped netlist and measured SRAM SAIF; diagnostic only',
            requested_task_ids=list(range(12)), taskset_complete=True, tasks=[])
        for task in report['tasks']:
            task_id = task['task_id']
            directory = out / ('task_%02d' % task_id)
            directory.mkdir()
            receipt = bridge.relocate(task['saif']['path'], mapping_path, inventory_path,
                                     directory / 'task-mapped.saif', STRIP, directory / 'task-mapped-receipt.json')
            states = measured_pins(modules, directory / 'task-mapped.saif', actual, task['normalization']['alias_unknown_bit_ticks'])
            need(receipt['measured_unknown_bit_ticks'] == states['alias_unknown_bit_ticks'] and
                 receipt['duration_ticks'] == task['activity_window']['duration_ticks'], 'relocation duration/unknown mismatch')
            write(directory / 'measured-sram-pins.json', states)
            item = dict(task_id=task_id, directory=directory.name, saif=identity(directory / 'task-mapped.saif'),
                canonical_saif=identity(task['saif']['path']), mapped_macro_bridge=identity(directory / 'task-mapped-receipt.json'),
                mapped_macro_bridge_receipt=receipt, measured_sram_pin_states=identity(directory / 'measured-sram-pins.json'),
                measured_summary=states['measured_summary'], activity_window=task['activity_window'],
                macro_names=sorted(actual), completion_marker='XU_S2E130_FULL_SOC_POWER_TASK_%02d_%s' % (task_id, uuid.uuid4().hex),
                expected_reports=modules.common.report_names() + ['update-power.rpt'])
            text = power_tcl(modules, impl, manifest['netlist'], manifest['analysis_sdc'], item)
            (directory / 'power.tcl').write_text(text)
            item['script'] = identity(directory / 'power.tcl')
            manifest['tasks'].append(item)
            state['last_prepared_task'] = task_id
            write(out / 'preparation-state.json', state)
            print('PREPARED_S2E130_FULL_SOC_POWER task=%d pins=22512 unknown_bit_ticks=%d NOT_QUALIFIED' %
                  (task_id, states['alias_unknown_bit_ticks']), flush=True)
        ctx.recheck()
        need(modules.mapped(ctx.root, args.ppa_root, args.formality_root) == mapped, 'own mapped proof changed during preparation')
        verify_inputs(records)
        manifest['input_sha256'] = records
        write(out / 'prepared.json', manifest)
        state.update(status='PREPARED_REVIEW_PENDING', prepared=identity(out / 'prepared.json'))
    except BaseException as error:
        state.update(status='FAIL', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        state['inputs_after'] = {p: sha(p) if Path(p).is_file() and not Path(p).is_symlink() else None for p in state['inputs_before']}
        if state['inputs_after'] != state['inputs_before']:
            state.update(status='FAIL', integrity_error='actual original input changed during preparation')
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write(out / 'preparation-state.json', state)
    need(state['status'] == 'PREPARED_REVIEW_PENDING', 'preparation failed or input changed')
    return manifest


def verify_prepared(out, manifest, modules, full_context=False):
    need(manifest.get('schema') == SCHEMA and manifest.get('qualification') == 'NOT_QUALIFIED' and
         manifest.get('requested_task_ids') == list(range(12)) and manifest.get('taskset_complete') is True and
         [row.get('task_id') for row in manifest.get('tasks', [])] == list(range(12)), 'complete own prepared manifest required')
    need(manifest['producer'] == identity(Path(__file__).resolve()), 'power130 producer changed')
    need(modules.context.tool_identity() == manifest['original_capture_tool_context'], 'original committed capture tools changed')
    need(modules.context.source_identity(manifest['source_root']) == manifest['source_context'], 'actual candidate source changed')
    verify_inputs(manifest['input_sha256'])
    original_impl = read(Path(manifest['ppa_root']) / 'ppa/prepared.json')['implementation']
    need(manifest['implementation_controls'] == original_impl, 'actual original own89 implementation controls differ')
    mapped = manifest['mapped_context']
    need(manifest['netlist'] == identity(mapped['netlist']['path']) and
         manifest['analysis_sdc'] == identity(mapped['constraints']['path']), 'actual own mapped/SDC path or bytes differ')
    inventory, actual, _ = modules.common.mapped_macros.inventory_macros(manifest['mapped_sram_inventory']['path'])
    need(manifest['mapped_sram_inventory'] == identity(manifest['mapped_sram_inventory']['path']) and
         inventory['netlist'] == manifest['netlist'] and inventory['constraints'] == manifest['analysis_sdc'] and
         inventory['macros'] == inventory_rows(inventory['provenance']['raw_tsv']['path']), 'own actual inventory binding differs')
    activity = read(manifest['activity']['path'])
    complete_taskset(activity)
    need(activity['configuration']['mapped_context'] == mapped and
         activity['configuration_sha256'] == manifest['original_capture_configuration_sha256'], 'own actual activity binding differs')
    if full_context:
        need(modules.mapped(manifest['source_root'], manifest['ppa_root'], manifest['formality_root']) == manifest['mapped_context'],
             'actual own89/109 mapped proof changed')
    for task in manifest['tasks']:
        need(task['directory'] == 'task_%02d' % task['task_id'] and task['completion_marker'].startswith('XU_S2E130_FULL_SOC_POWER_TASK_'),
             'prepared task identity differs')
        for key in ('script', 'saif', 'mapped_macro_bridge', 'measured_sram_pin_states'):
            row = task[key]
            need(Path(row['path']).absolute().parent == out / task['directory'], 'prepared task file escapes output')
            need(identity(row['path']) == row, 'prepared task file changed: ' + key)
        need(task['macro_names'] == sorted(actual) and
             task['activity_window'] == activity['tasks'][task['task_id']]['activity_window'] and
             task['canonical_saif'] == identity(activity['tasks'][task['task_id']]['saif']['path']) and
             task['saif']['path'] == str(out / task['directory'] / 'task-mapped.saif') and
             task['script']['path'] == str(out / task['directory'] / 'power.tcl'), 'prepared task/source/actual macro binding differs')
        checked_power_tcl(modules, original_impl, manifest['netlist'], manifest['analysis_sdc'], task)
        need(task['expected_reports'] == modules.common.report_names() + ['update-power.rpt'], 'required native reports differ')
        need(read(task['mapped_macro_bridge']['path']) == task['mapped_macro_bridge_receipt'], 'bridge receipt changed')
    need(manifest['netlist']['sha256'] == NETLIST and manifest['analysis_sdc']['sha256'] == SDC and manifest['strip_path'] == STRIP,
         'own mapped/SDC/full-DUT scope differs')


def diagnostic(directory, task):
    text = (directory / 'power.rpt').read_text()
    need(re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'full-SoC power report design differs')
    for unit in ('Dynamic', 'Leakage'):
        need(re.findall(r'^\s*' + unit + r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')],
             'explicit watt power units required')
    values = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'),
                       ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*' + label + r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        need(len(hits) == 1, 'native power component missing/ambiguous: ' + label)
        value = Decimal(hits[0])
        need(value.is_finite() and value >= 0, 'negative/nonfinite power diagnostic')
        values[key + '_power_w'] = str(value)
    duration = Decimal(task['activity_window']['duration_ticks']) * Decimal('1e-15')
    return dict(status='PARTIAL_MODEL_DIAGNOSTIC_NOT_ENERGY_QUALIFIED', full_soc_design='xu_soc_ppa_top',
        report=identity(directory / 'power.rpt'), reported_power_precision='native rounded report; no extra precision claimed',
        duration_seconds=str(duration), diagnostic_energy_j=str(Decimal(values['total_power_w']) * duration),
        power_components=values, measured_input_unknown_summary=task['measured_summary'],
        native_pin_semantics='full original before/after report_attribute retained, not interpreted as physically known Q',
        qualification='NOT_QUALIFIED', unresolved=REVIEW)


def run(args):
    out = args.out.resolve()
    manifest_path = out / 'prepared.json'
    prepared = identity(manifest_path)
    manifest = read(manifest_path)
    modules = Modules(Path(manifest['tool_root']))
    verify_prepared(out, manifest, modules, True)
    need(not (out / 'execution.json').exists(), 'execution already exists; never restart/overwrite a campaign')
    environment = modules.common.execution_environment(Path(manifest['library_compiler_root']))
    tool = manifest['pt']
    need(identity(tool['path']) == tool, 'frozen PT executable changed')
    for task in manifest['tasks']:
        need(not any((out / task['directory'] / name).exists() for name in task['expected_reports'] + ['pt.log']),
             'actual PT report/log exists; use a fresh campaign')
    receipt = dict(schema=EXECUTION, status='RUNNING_REVIEW_PENDING', qualification='NOT_QUALIFIED', limitations=REVIEW,
        prepared=prepared, pt=tool, pid=os.getpid(), taskset_complete=False, requested_task_ids=list(range(12)),
        input_sha256_before=dict(manifest['input_sha256']), library_compiler_root=manifest['library_compiler_root'],
        started_utc=datetime.now(timezone.utc).isoformat(), tasks=[])
    write(out / 'execution.json', receipt)
    try:
        for task in manifest['tasks']:
            verify_prepared(out, manifest, modules)
            need(identity(manifest_path) == prepared and identity(tool['path']) == tool, 'prepared/PT changed')
            receipt['current_task_id'] = task['task_id']
            write(out / 'execution.json', receipt)
            directory = out / task['directory']
            result = modules.common.execute([tool['path'], '-f', 'power.tcl'], directory, directory / 'pt.log', args.timeout, environment)
            entry = dict(task_id=task['task_id'], execution=result, status='TOOL_EXECUTION_UNREVIEWED')
            receipt['tasks'].append(entry)
            write(out / 'execution.json', receipt)
            verify_prepared(out, manifest, modules)
            need(identity(manifest_path) == prepared and identity(tool['path']) == tool, 'prepared/PT changed during actual task')
            entry['frozen_inputs_before_after_rehashed_sha256'] = canonical(manifest['input_sha256'])
            checked_native_log(directory / 'pt.log', task['completion_marker'], result['returncode'])
            entry['reports'] = modules.common.checked_reports(directory, task)
            need(PT_VERSION in (directory / 'tool-version.rpt').read_text(), 'native PT version report differs')
            entry['diagnostic'] = diagnostic(directory, task)
            entry['status'] = 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING'
            write(out / 'execution.json', receipt)
            print('EXECUTED_S2E130_FULL_SOC_POWER task=%d diagnostic_w=%s diagnostic_j=%s NOT_QUALIFIED' %
                  (task['task_id'], entry['diagnostic']['power_components']['total_power_w'],
                   entry['diagnostic']['diagnostic_energy_j']), flush=True)
        verify_prepared(out, manifest, modules, True)
        need(len(receipt['tasks']) == 12 and all(row['status'] == 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING' for row in receipt['tasks']),
             'all twelve actual native PT tasks required')
        receipt.update(status='EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING', taskset_complete=True)
        durations = [Decimal(row['diagnostic']['duration_seconds']) for row in receipt['tasks']]
        receipt['diagnostic_summary'] = dict(status='PARTIAL_MODEL_DIAGNOSTIC_NOT_ENERGY_QUALIFIED', task_count=12,
            durations_seconds=[str(value) for value in durations],
            total_elapsed_cycles=sum(task['activity_window']['formal_elapsed_cycles'] for task in manifest['tasks']),
            arithmetic_mean_reported_power_w=str(sum(Decimal(row['diagnostic']['power_components']['total_power_w'])
                for row in receipt['tasks']) / Decimal(12)),
            sum_diagnostic_energy_j=str(sum(Decimal(row['diagnostic']['diagnostic_energy_j']) for row in receipt['tasks'])),
            qualification='NOT_QUALIFIED', limitations=REVIEW)
    except BaseException as error:
        receipt.update(status='FAIL', error=type(error).__name__ + ': ' + str(error), taskset_complete=False)
        raise
    finally:
        receipt['input_sha256_after'] = {p: sha(p) if Path(p).is_file() and not Path(p).is_symlink() else None
                                         for p in manifest['input_sha256']}
        receipt['prepared_after'] = identity(manifest_path)
        receipt['pt_after'] = identity(tool['path'])
        try:
            receipt['source_context_after'] = modules.context.source_identity(manifest['source_root'])
            receipt['capture_tool_context_after'] = modules.context.tool_identity()
            need(receipt['source_context_after'] == manifest['source_context'] and
                 receipt['capture_tool_context_after'] == manifest['original_capture_tool_context'], 'actual source/tool context changed')
        except BaseException as error:
            receipt['context_integrity_error'] = type(error).__name__ + ': ' + str(error)
        changed = (receipt['input_sha256_after'] != receipt['input_sha256_before'] or receipt['prepared_after'] != prepared or
                   receipt['pt_after'] != tool or 'context_integrity_error' in receipt)
        if changed:
            receipt.update(status='FAIL', integrity_error='actual input/preparation/PT executable changed', taskset_complete=False)
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        receipt['artifacts'] = {str(path.relative_to(out)): identity(path) for path in sorted(out.rglob('*'))
                                if path.is_file() and not path.is_symlink() and path.name != 'execution.json'}
        write(out / 'execution.json', receipt)
        if changed:
            raise ValueError(receipt['integrity_error'])
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run', 'campaign'])
    parser.add_argument('--activity', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--tool-root', type=Path)
    parser.add_argument('--ppa-root', type=Path)
    parser.add_argument('--formality-root', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--pt', type=Path, default=Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell'))
    parser.add_argument('--lc-root', type=Path, default=Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
    parser.add_argument('--inventory-timeout', type=int, default=900)
    parser.add_argument('--timeout', type=int, default=21600)
    args = parser.parse_args(argv)
    need(args.timeout > 0 and args.inventory_timeout > 0, 'positive real tool execution timeout required')
    if args.action in ('prepare', 'campaign'):
        for name in ('activity', 'source_root', 'tool_root', 'ppa_root', 'formality_root'):
            need(getattr(args, name) is not None, 'explicit --' + name.replace('_', '-') + ' required')
        result = prepare(args)
    if args.action in ('run', 'campaign'):
        result = run(args)
    print(result['status'] + ': ' + str(args.out), flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('FAIL: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
