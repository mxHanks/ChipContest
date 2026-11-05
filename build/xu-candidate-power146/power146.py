#!/usr/bin/env python3
"""Eight frozen inventory137 candidates: independent twelve-layer PT diagnostics.

Python 3.6+, standard library, no network. Original RTL, DB, SDC, source guards
and historical receipts remain immutable. Successful execution never qualifies
unknown Q, timing, SRAM power modeling, contest energy, or a score.
"""
import argparse
from decimal import Decimal
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common146 import BAD, canonical, checked_log, collect, environment, execute, identity, load, need, now, read, record, sha, tcl, verify, write
from bridge146 import PIN_WIDTHS, STRIP, bijection, inventory_rows, pin_names, relocate
from native146 import LIMITS, audit

SCHEMA = 'xu-candidate-power146-prepared-v1'
STATUS = 'EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'
PT = '/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell'
LC = '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'
ACCEL = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'


def producers():
    return [identity(p) for p in sorted(HERE.rglob('*')) if p.is_file() and
            p.suffix in ('.py', '.json') and '__pycache__' not in p.parts and not p.name.startswith('test_')]


def candidate(profile):
    inventory = read(HERE/'inventory137.snapshot.json')
    rows = [c for c in inventory['candidates'] if c['id'] == profile]
    need(len(rows) == 1, 'one of eight exact inventory137 candidate IDs required')
    return rows[0]


def activity_modules(root):
    root = Path(root).resolve()
    need((root/'context145.py').is_file() and (root/'macro145.py').is_file(), 'activity145 runtime missing')
    context = load('xu_power146_context145', root/'context145.py')
    macro = load('xu_power146_macro145', root/'macro145.py')
    return context, macro


def checked_activity(args, ctx, macro, adopted, records):
    root = args.activity_root.resolve()
    path = root/'result.json'
    report = read(path); record(identity(path), records)
    runtime = load('xu_power146_activity145', args.activity_tools/'activity145.py')
    verified = runtime.verify_result(root, expected_profile=args.profile, replay_normalization=False)
    need(verified['status'] == 'VERIFIED_12_REVIEW_PENDING_NOT_QUALIFIED' and
         verified['activity_result'] == identity(path), 'actual145 raw log/physical clear/numeric/clock verification failed')
    need(report.get('schema') == 'xu-profile-activity145-v1' and
         report.get('status') == 'COLLECTED_12_REVIEW_PENDING_NOT_QUALIFIED' and report.get('profile') == args.profile and
         report.get('taskset_complete') is True and report.get('requested_task_ids') == list(range(12)) and
         [t.get('task_id') for t in report.get('tasks', [])] == list(range(12)), 'actual complete own activity145 twelve tasks required')
    config = report['configuration']
    need(report['configuration_sha256'] == canonical(config), 'activity145 actual configuration hash differs')
    need(config['adoption'] == adopted, 'activity145 selected ownFM mapped/SDC/freeze binding differs')
    need(config['memory_groups'] == ctx.candidate['ppa']['memory_groups'], 'activity145 frozen complete memory groups differ')
    need(config.get('nominal_hz') == 150000000 and config.get('lf_hz') == 32768 and
         config.get('activity_scope') == 'tb_xu_soc_ppa.dut', 'activity145 fixed150MHz/LF/full-DUT scope differs')
    collect(report, records)
    inventories = []
    for task in report['tasks']:
        number = task['task_id']; directory = root/('task_%02d' % number)
        need(task.get('schema') == 'xu-profile-task-activity145-v1' and
             task.get('status') == 'COLLECTED_REVIEW_PENDING_NOT_QUALIFIED' and task['profile'] == args.profile and
             task['configuration_sha256'] == report['configuration_sha256'] and read(directory/'result.json') == task,
             'actual activity145 individual task receipt differs')
        record(identity(directory/'result.json'), records)
        window = task['activity_window']
        need(type(window['duration_ticks']) is int and window['duration_ticks'] > 0 and
             type(window['formal_elapsed_cycles']) is int and window['formal_elapsed_cycles'] > 0 and
             Decimal(window['timescale_seconds']) == Decimal('1e-15') and
             task['saif']['duration_ticks'] == window['duration_ticks'] and
             Decimal(task['saif']['timescale_seconds']) == Decimal('1e-15') and
             Path(task['saif']['path']).resolve() == directory/'task-normalized.saif', 'actual per-layer measured window differs')
        need(task['normalization']['schema'] == 'xu-profile-macro-normalization145-v1' and
             task['normalization']['status'] == 'NORMALIZED_REVIEW_PENDING_NOT_QUALIFIED', 'actual145 normalization missing')
        inventory = read(task['actual_macro_inventory']['path'])
        need(inventory['memory_groups'] == config['memory_groups'] and
             inventory['macro_count'] == sum(g['count'] for g in config['memory_groups']), 'actual145 complete inventory differs')
        # Re-derive elaborated inventory from the immutable original simulation
        # log, rather than trusting a self-declared list or probe-only mapping.
        fresh_inventory = macro.parse_inventory(Path(task['boundary_log']['path']), config['memory_groups'],
                    expected_count=inventory['macro_count'], expected_x_count=len(inventory['x_buffers']))
        need(fresh_inventory == inventory, 'fresh actual elaboration inventory differs from original log')
        with tempfile.TemporaryDirectory(prefix='xu-power146-normalize-') as temporary:
            replay = macro.normalize(task['raw_saif']['path'], Path(temporary)/'normalized.saif', inventory,
                                     ctx.reader, ctx.alias_helpers)
            need(replay['normalized_saif']['sha256'] == task['saif']['sha256'], 'replayed measured raw-to-normalized SAIF differs')
            for key in ('inventory_sha256', 'alias_name_sha256', 'macro_count', 'pin_bit_count', 'alias_unknown_bit_ticks',
                        'duration_ticks', 'timescale_seconds', 'nonalias_signal_count_preserved'):
                need(replay[key] == task['normalization'][key], 'normalization replay differs: '+key)
        manifest = read(task['input_manifest']['path'])
        need(manifest['schema'] == 'xu-soc-single-task-input-v1' and manifest['global_task_id'] == number and
             manifest['original_layer'] == 'layer_%02d' % number and manifest['simulator_layer'] == 'layer_00',
             'frozen numerical vector global/local task binding differs')
        files = manifest['files']
        need(len(files) == 4 and {f['tensor'] for f in files} == {'w', 'x', 'bias', 'y'}, 'exact four original tensors required')
        for item in files:
            need(item['original']['sha256'] == item['materialized']['sha256'], 'materialized numerical input differs')
        collect(manifest, records)
        inventories.append(inventory)
        print('XU146_REPLAY_ACTIVITY profile=%s task=%02d cycles=%d duration_fs=%d NOT_QUALIFIED' %
              (args.profile, number, window['formal_elapsed_cycles'], window['duration_ticks']), flush=True)
    # Whole-SoC macros must be independently enumerated in every fresh process.
    shape = lambda value: {k: value[k] for k in ('schema', 'dut_scope', 'macro_count', 'pin_bit_count', 'macros', 'group_counts', 'memory_groups', 'x_buffers')}
    need(all(shape(v) == shape(inventories[0]) for v in inventories), 'actual RTL full-macro inventory changes across tasks')
    ctx.recheck()
    return report, inventories


def clock_checks():
    return '''foreach xu_pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {
  set xu_clock [get_clocks -quiet [lindex $xu_pair 0]]
  if {[sizeof_collection $xu_clock] != 1} {error "missing primary clock $xu_pair"}
  if {abs([get_attribute $xu_clock period]-[lindex $xu_pair 1]) > 0.000001} {error "wrong clock period $xu_pair"}
}
if {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] != 1} {error {conservative divider clock missing}}
'''


def memory_checks(groups):
    lines = ['set xu_seen [dict create]']
    for group in groups:
        filt = 'full_name =~ '+group['instance_pattern']+' && ref_name == '+group['macro_ref']+' && is_hierarchical == false'
        lines += ['set xu_cells [get_cells -quiet -hierarchical -filter '+tcl(filt)+']',
                  'if {[sizeof_collection $xu_cells] != %d} {error %s}' % (group['count'], tcl('wrong SRAM group: '+group['name'])),
                  'foreach_in_collection xu_c $xu_cells {', '  set xu_n [get_object_name $xu_c]',
                  '  if {[dict exists $xu_seen $xu_n]} {error {overlapping native SRAM group}}',
                  '  dict set xu_seen $xu_n 1', '}']
    lines += ['set xu_all_macros [get_cells -quiet -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}]',
              'if {[sizeof_collection $xu_all_macros] != %d || [dict size $xu_seen] != %d} {error {complete SRAM native count differs}}' %
              (sum(g['count'] for g in groups), sum(g['count'] for g in groups)),
              'foreach_in_collection xu_c $xu_all_macros {if {![dict exists $xu_seen [get_object_name $xu_c]]} {error {unexpected native SRAM}}}',
              'proc xu_pin_count {c} {', '  set ref [get_attribute $c ref_name]',
              '  if {$ref eq "RAMSP1024X16"} {return 67}', '  if {$ref eq "RAMSP128X16"} {return 64}',
              '  error "unsupported actual SRAM $ref"', '}']
    return '\n'.join(lines)+'\n'


def guarded(body, marker):
    return 'if {[catch {\n'+body+'\nputs '+tcl(marker)+'\n} xu_error]} {\n  puts stderr "XU_FATAL: $xu_error"\n  exit 1\n}\nexit 0\n'


def prefix(manifest):
    return ('set_app_var link_path [list * '+' '.join(tcl(r['path']) for r in manifest['libraries'])+']\n'
            'redirect -file tool-version.rpt {puts $sh_product_version}\nread_verilog '+tcl(manifest['netlist']['path'])+'\n'
            'if {![link_design xu_soc_ppa_top]} {error {PT full-SoC link failed}}\n'
            'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource '+tcl(manifest['analysis_sdc']['path'])+'\n'+
            clock_checks()+memory_checks(manifest['memory_groups']))


def inventory_tcl(manifest, marker):
    need(manifest['accelerator_hierarchy'] == ACCEL, 'exact selected accelerator hierarchy required')
    body = prefix(manifest)+'''set f [open macro-pins.tsv w]
puts $f "kind\tcell\tref_or_pin\tlibcell_or_direction"
foreach_in_collection c $xu_all_macros {
  set name [get_object_name $c]
  set lc [get_lib_cells -of_objects $c]
  if {[sizeof_collection $lc] != 1} {error {macro library cell not unique}}
  puts $f "MACRO\t$name\t[get_attribute $c ref_name]\t[get_object_name $lc]"
  set pins [get_pins -quiet -of_objects $c]
  if {[sizeof_collection $pins] != [xu_pin_count $c]} {error {macro pin count differs}}
  foreach_in_collection p $pins {puts $f "PIN\t$name\t[get_object_name $p]\t[get_attribute $p direction]"}
}
close $f
# Area comes from the same selected mapped leaves and actual linked DBs. No
# original-map DC area is attached to repaired S2d/PE32 selected maps.
set f [open mapped-leaf-area.tsv w]
puts $f "cell\tlibcell\tarea_native_library_units"
set xu_area_cache [dict create]
foreach_in_collection c [get_cells -quiet -hierarchical -filter {is_hierarchical == false}] {
  set lc [get_lib_cells -of_objects $c]
  if {[sizeof_collection $lc] != 1} {error {mapped area leaf library cell not unique}}
  set key [get_object_name $lc]
  if {![dict exists $xu_area_cache $key]} {dict set xu_area_cache $key [get_attribute $lc area]}
  set area [dict get $xu_area_cache $key]
  if {![string is double -strict $area] || $area < 0} {error {invalid actual linked library area}}
  puts $f "[get_object_name $c]\t$key\t$area"
}
close $f
'''
    return guarded(body, marker)


def report_names():
    names = ['read-saif.rpt', 'inconsistent.rpt', 'tool-version.rpt', 'units.rpt', 'clocks.rpt',
             'check-timing.rpt', 'power.rpt', 'power-hierarchy.rpt', 'sram-power.rpt', 'sram-library.rpt',
             'sram-pins-before.rpt', 'sram-pins-after.rpt', 'update-power.rpt']
    for phase in ('before', 'after'):
        names += ['%s-%s.rpt' % (kind, phase) for kind in ('switching', 'coverage', 'unannotated')]
        names += ['source-%s-%s.rpt' % (source, phase) for source in ('file', 'default', 'propagated', 'no_switching_activity')]
    return names


def power_tcl(manifest, task):
    body = ('set_app_var power_enable_analysis true\nset_app_var power_analysis_mode averaged\n'+prefix(manifest)+
            'set_propagated_clock [all_clocks]\nupdate_timing\n')
    body += 'set xu_expected_macros [list '+' '.join(tcl(n) for n in task['macro_names'])+']\n'
    body += '''foreach_in_collection c $xu_all_macros {
  if {[lsearch -exact $xu_expected_macros [get_object_name $c]] < 0} {error {actual native macro differs}}
  if {[sizeof_collection [get_lib_cells -of_objects $c]] != 1} {error {SRAM linked library not unique}}
}
redirect -file units.rpt {report_units}
redirect -file clocks.rpt {report_clock}
redirect -file check-timing.rpt {check_timing -verbose}
'''
    body += 'redirect -file read-saif.rpt {\n  if {![read_saif '+tcl(task['saif']['path'])+' -strip_path '+tcl(STRIP)+' -report_inconsistent_annotation inconsistent.rpt]} {error {SAIF annotation failed}}\n}\n'
    for phase in ('before', 'after'):
        if phase == 'after': body += 'redirect -file update-power.rpt {update_power}\n'
        for kind, command in [('switching', 'report_switching_activity -hierarchy'),
                              ('coverage', 'report_switching_activity -coverage -hierarchy'),
                              ('unannotated', 'report_switching_activity -list_not_annotated -show_pin')]:
            body += 'redirect -file %s-%s.rpt {%s}\n' % (kind, phase, command)
        for source in ('file', 'default', 'propagated', 'no_switching_activity'):
            body += 'redirect -file source-%s-%s.rpt {report_switching_activity -list_by_source %s -show_pin}\n' % (source, phase, source)
        body += 'redirect -file sram-pins-%s.rpt {\n' % phase
        body += '''  foreach_in_collection c $xu_all_macros {
    set pins [get_pins -quiet -of_objects $c]
    if {[sizeof_collection $pins] != [xu_pin_count $c]} {error {native mixed SRAM pin count differs}}
    foreach_in_collection p $pins {
      puts "XU_SRAM_PIN name=[get_object_name $p]"
      report_attribute -application $p
    }
  }
}
'''
    body += '''redirect -file power.rpt {report_power -verbose}
redirect -file power-hierarchy.rpt {report_power -hierarchy -verbose}
redirect -file sram-power.rpt {
  foreach_in_collection c $xu_all_macros {
    puts "XU_SRAM_POWER_CELL name=[get_object_name $c] ref=[get_attribute $c ref_name]"
    report_power -cell_power -nosplit -include_lib_cells $c
  }
}
redirect -file sram-library.rpt {
  puts "XU_SRAM_LIBERTY_WHEN_INTERNAL_POWER_MODE_REVIEW_PENDING"
  foreach_in_collection lc [get_lib_cells -of_objects $xu_all_macros] {
    puts "XU_SRAM_LIBRARY_CELL [get_object_name $lc]"
    report_attribute -application $lc
    set libname [lindex [split [get_object_name $lc] /] 0]
    report_lib -power_arcs [get_libs $libname] $lc
  }
  foreach_in_collection lib [get_libs *] {report_lib [get_object_name $lib]}
}
'''
    for name in report_names():
        body += 'if {![file isfile '+tcl(name)+']} {error '+tcl('missing native report: '+name)+'}\n'
        if name != 'inconsistent.rpt': body += 'if {[file size '+tcl(name)+'] == 0} {error '+tcl('empty native report: '+name)+'}\n'
    return guarded(body, task['completion_marker'])


def measured_area(path, accelerator_hierarchy=ACCEL):
    need(accelerator_hierarchy == ACCEL, 'exact accelerator area boundary required')
    total, count, seen = Decimal(0), 0, set()
    accel_total, accel_count, accel_macros = Decimal(0), 0, 0
    with Path(path).open() as source:
        need(source.readline().rstrip('\n') == 'cell\tlibcell\tarea_native_library_units', 'native selected-map area header differs')
        for line in source:
            cell, libcell, value = line.rstrip('\n').split('\t')
            area = Decimal(value)
            need(cell not in seen and libcell.count('/') == 1 and area.is_finite() and area >= 0, 'native leaf area invalid/duplicate')
            seen.add(cell); count += 1; total += area
            if cell.startswith(accelerator_hierarchy+'/'):
                accel_total += area; accel_count += 1
                accel_macros += libcell.split('/')[1] in PIN_WIDTHS
    need(count > 0 and total > 0 and accel_count > 0 and accel_total > 0 and accel_macros > 0,
         'native selected-map full-SoC/accelerator area empty')
    return dict(status='SAME_SELECTED_MAP_LIBRARY_AREA_DIAGNOSTIC_NOT_QUALIFIED', report=identity(path),
                full_soc=dict(leaf_count=count, area_native_library_units=str(total), area_mm2_diagnostic=str(total/Decimal(1000000))),
                accelerator=dict(hierarchy=accelerator_hierarchy, leaf_count=accel_count, sram_leaf_count=accel_macros,
                    area_native_library_units=str(accel_total), area_mm2_diagnostic=str(accel_total/Decimal(1000000)),
                    contest_area_limit_mm2='2.25', diagnostic_within_limit=accel_total <= Decimal(2250000)),
                conversion='native library area convention um^2 / 1e6; no placed/filler/routing area inferred')


def prepare(args):
    out = args.out.resolve()
    need(not out.exists() and not out.is_symlink(), 'fresh146 output required; existing work uses resume')
    selected = candidate(args.profile)
    context, macro = activity_modules(args.activity_tools)
    ctx = context.Context(args.profile, args.source_root)
    need(str(ctx.root) == selected['source']['server_root'] and ctx.candidate == selected,
         'exact frozen server source root and inventory137 profile required')
    frozen, adopted_receipt = read(args.freeze_receipt), read(args.adoption_receipt)
    need(adopted_receipt['selected_mapped']['path'] == selected['formal']['mapped']['path'] == frozen['selected_mapped']['path'],
         'exact selected mapped path differs; original/repaired maps cannot mix')
    adopted = ctx.adoption(args.freeze_receipt, args.adoption_receipt,
                           selected['formal']['mapped']['path'], selected['ppa']['analysis_sdc']['path'])
    records = {}
    for row in producers(): record(row, records)
    for path in sorted(args.activity_tools.resolve().rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.json', '.sv', '.svh') and '__pycache__' not in path.parts and not path.name.startswith('test_'):
            record(identity(path), records)
    collect(adopted, records)
    for row in frozen['after']: record(row, records)
    for row in selected['ppa']['libraries']: record(row, records)
    queued = next(c for c in read(HERE/'queue138.snapshot.json')['candidates'] if c['id'] == args.profile)
    record(queued['formal_log'], records)
    report, inventories = checked_activity(args, ctx, macro, adopted, records)
    tool = record(identity(Path(args.pt).resolve()), records)
    expected_tool = [r for r in queued['freeze_inputs'] if r['path'] == PT]
    need(len(expected_tool) == 1 and tool['sha256'] == expected_tool[0]['sha256'], 'original frozen PT executable differs')
    env = environment(args.lc_root)
    verify(records)
    out.mkdir(parents=True)
    state = dict(status='PREPARING_DIAGNOSTIC_NOT_QUALIFIED', started_utc=now(), pid=os.getpid(), qualification='NOT_QUALIFIED')
    write(out/'preparation-state.json', state)
    try:
        manifest = dict(schema=SCHEMA, status='PREPARED_12_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
            profile=args.profile, source_root=str(ctx.root), source_context=ctx.source, activity_tools=str(args.activity_tools.resolve()),
            accelerator_hierarchy=ACCEL,
            activity=identity(args.activity_root/'result.json'), activity_configuration_sha256=report['configuration_sha256'],
            adoption=adopted, memory_groups=selected['ppa']['memory_groups'], libraries=[identity(r['path']) for r in selected['ppa']['libraries']],
            netlist=identity(selected['formal']['mapped']['path']), analysis_sdc=identity(selected['ppa']['analysis_sdc']['path']),
            original_mapped=selected['ppa']['original_mapped'], original_area_mm2_reference=selected['ppa'].get('original_area_mm2'),
            original_area_policy='reference only; never used for selected repaired mapping measurements',
            strip_path=STRIP, pt=tool, library_compiler_root=str(Path(args.lc_root).resolve()),
            producer=identity(__file__), producers=producers(), limitations=LIMITS,
            reproduction=dict(campaign=[sys.executable, '-B', str(HERE/'power146.py'), 'campaign', '--profile', args.profile,
                '--freeze-receipt', str(args.freeze_receipt.resolve()), '--adoption-receipt', str(args.adoption_receipt.resolve()),
                '--source-root', str(ctx.root), '--activity-root', str(args.activity_root.resolve()),
                '--activity-tools', str(args.activity_tools.resolve()), '--out', str(out), '--pt', tool['path'],
                '--lc-root', str(Path(args.lc_root).resolve()), '--timeout', str(args.timeout),
                '--inventory-timeout', str(args.inventory_timeout)],
                resume=[sys.executable, '-B', str(HERE/'power146.py'), 'resume', '--out', str(out)],
                verify=[sys.executable, '-B', str(HERE/'power146.py'), 'verify', '--out', str(out)]),
            requested_task_ids=list(range(12)), taskset_complete=True, tasks=[])
        native_dir = out/'inventory'; native_dir.mkdir()
        marker = 'XU146_NATIVE_FULL_MACRO_INVENTORY_'+uuid.uuid4().hex
        (native_dir/'inventory.tcl').write_text(inventory_tcl(manifest, marker))
        native_run = execute([tool['path'], '-f', 'inventory.tcl'], native_dir, marker, args.inventory_timeout, env)
        native = inventory_rows(native_dir/'macro-pins.tsv', manifest['memory_groups'])
        _, bindings = bijection(inventories[0], native)
        manifest['area'] = measured_area(native_dir/'mapped-leaf-area.tsv', manifest['accelerator_hierarchy'])
        need(manifest['area']['accelerator']['sram_leaf_count'] == sum(g['count'] for g in manifest['memory_groups'] if g['name'].startswith('accelerator_')),
             'same selected-map accelerator area macro coverage differs')
        inventory = dict(schema='xu-profile-native-macro-inventory146-v1', status='EXPORTED_DIAGNOSTIC_NOT_QUALIFIED',
            profile=args.profile, macros=native, macro_count=len(native), pin_bit_count=sum(len(r['pins']) for r in native),
            memory_groups=manifest['memory_groups'], netlist=manifest['netlist'], constraints=manifest['analysis_sdc'],
            libraries=manifest['libraries'], macro_bindings=bindings, macro_bindings_sha256=canonical(bindings),
            provenance=dict(execution=native_run, script=identity(native_dir/'inventory.tcl'), tsv=identity(native_dir/'macro-pins.tsv'),
                            tool_version=identity(native_dir/'tool-version.rpt')))
        write(native_dir/'inventory.json', inventory)
        manifest['mapped_sram_inventory'] = identity(native_dir/'inventory.json')
        for path in sorted(native_dir.iterdir()):
            if path.is_file(): record(identity(path), records)
        for source, rtl in zip(report['tasks'], inventories):
            number = source['task_id']; directory = out/('task_%02d' % number); directory.mkdir()
            receipt, measured = relocate(source['saif']['path'], directory/'task-mapped.saif', rtl, native, ctx.reader, ctx.alias_helpers)
            need(receipt['measured_summary']['measured_unknown_bit_ticks'] == source['normalization']['alias_unknown_bit_ticks'] and
                 receipt['measured_summary']['duration_ticks'] == source['activity_window']['duration_ticks'], 'mapped measured unknown/duration differs')
            write(directory/'mapped-bridge.json', receipt)
            write(directory/'measured-sram-pins.json', measured)
            task = dict(task_id=number, directory=directory.name, activity_task=identity(args.activity_root/('task_%02d' % number)/'result.json'),
                activity_window=source['activity_window'], layer=source['layer'], canonical_saif=identity(source['saif']['path']),
                actual_macro_inventory=source['actual_macro_inventory'], saif=identity(directory/'task-mapped.saif'),
                mapped_macro_bridge=identity(directory/'mapped-bridge.json'), measured_sram_pin_states=identity(directory/'measured-sram-pins.json'),
                measured_summary=measured['measured_summary'], macro_names=sorted(m['instance'] for m in native),
                completion_marker='XU146_FULL_SOC_POWER_TASK_%02d_%s' % (number, uuid.uuid4().hex), expected_reports=report_names())
            (directory/'power.tcl').write_text(power_tcl(manifest, task))
            task['script'] = identity(directory/'power.tcl'); manifest['tasks'].append(task)
            state['last_prepared_task'] = number; write(out/'preparation-state.json', state)
        ctx.recheck(); verify(records)
        manifest['input_sha256'] = records
        write(out/'prepared.json', manifest)
        state.update(status=manifest['status'], prepared=identity(out/'prepared.json'))
    except BaseException as error:
        state.update(status='FAIL_DIAGNOSTIC_NOT_QUALIFIED', error=type(error).__name__+': '+str(error))
        raise
    finally:
        state['finished_utc'] = now(); write(out/'preparation-state.json', state)
    return manifest


def verify_prepared(out, full=True):
    out = Path(out).resolve(); manifest = read(out/'prepared.json')
    need(manifest['schema'] == SCHEMA and manifest['producer'] == identity(__file__) and manifest['producers'] == producers(),
         'actual146 producer/prepared schema changed')
    need(manifest['qualification'] == 'NOT_QUALIFIED' and manifest['requested_task_ids'] == list(range(12)) and
         manifest['taskset_complete'] is True and [t['task_id'] for t in manifest['tasks']] == list(range(12)), 'complete146 prepared taskset required')
    selected = candidate(manifest['profile'])
    need(manifest['netlist']['path'] == selected['formal']['mapped']['path'] and
         manifest['netlist']['sha256'] == selected['formal']['mapped']['sha256'] and
         manifest['analysis_sdc']['sha256'] == selected['ppa']['analysis_sdc']['sha256'], 'selected-map/SDC frozen binding differs')
    if full: verify(manifest['input_sha256'])
    else:
        # Recheck immutable native design/DB/SDC/tools and the current layer's
        # captured/derived artifacts. Other layers are verified at entry/exit.
        verify({p: v for p, v in manifest['input_sha256'].items() if '/task_' not in p})
    context, _ = activity_modules(manifest['activity_tools'])
    ctx = context.Context(manifest['profile'], manifest['source_root'])
    need(ctx.source == manifest['source_context'], 'exact original candidate source context changed')
    adopted = manifest['adoption']
    need(ctx.adoption(adopted['freeze']['path'], adopted['own_fm']['path'], manifest['netlist']['path'],
                      manifest['analysis_sdc']['path']) == adopted, 'actual selected ownFM freeze/adoption changed')
    inventory = read(manifest['mapped_sram_inventory']['path'])
    need(identity(manifest['mapped_sram_inventory']['path']) == manifest['mapped_sram_inventory'] and
         inventory['macros'] == inventory_rows(inventory['provenance']['tsv']['path'], manifest['memory_groups']) and
         inventory['netlist'] == manifest['netlist'] and inventory['libraries'] == manifest['libraries'], 'native inventory changed')
    need(manifest['area'] == measured_area(out/'inventory/mapped-leaf-area.tsv', manifest['accelerator_hierarchy']),
         'same selected-map full-SoC/accelerator area changed')
    for task in manifest['tasks']:
        directory = out/task['directory']
        need(task['directory'] == 'task_%02d' % task['task_id'], 'prepared task directory identity differs')
        for key in ('script', 'saif', 'mapped_macro_bridge', 'measured_sram_pin_states'):
            row = task[key]
            need(Path(row['path']).parent == directory and identity(row['path']) == row, 'prepared current artifact changed: '+key)
        need((directory/'power.tcl').read_text() == power_tcl(manifest, task), 'prepared Tcl differs from exact reconstruction')
        actual_task = read(task['activity_task']['path'])
        need(identity(task['activity_task']['path']) == task['activity_task'] and
             task['activity_window'] == actual_task['activity_window'] and task['layer'] == actual_task['layer'] and
             task['canonical_saif'] == identity(actual_task['saif']['path']), 'prepared per-layer original duration/SAIF changed')
    return manifest


def checked_reports(directory, task, native):
    records = {}
    for name in task['expected_reports']:
        path = directory/name
        actual = identity(path)
        need(name == 'inconsistent.rpt' or actual['bytes'] > 0, 'native report empty: '+name)
        # Attribute reports are streamed with offsets, SHA and errors in audit.
        if not name.startswith('sram-pins-'):
            with path.open(errors='replace') as stream:
                need(not any(BAD.search(line) for line in stream), 'native error in report: '+name)
        records[name] = actual
    need('T-2022.03-SP5-1' in (directory/'tool-version.rpt').read_text(), 'native PT version differs')
    found = []
    with (directory/'sram-power.rpt').open() as source:
        for line in source:
            match = re.fullmatch(r'XU_SRAM_POWER_CELL name=(.+) ref=(\S+)\n?', line)
            if match: found.append(match.groups())
    need(sorted(found) == sorted((m['instance'], m['ref_name']) for m in native), 'complete mixed SRAM power-cell inventory differs')
    return records


def diagnostic(directory, task, area):
    text = (directory/'power.rpt').read_text()
    need(re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'full-SoC power design differs')
    for unit in ('Dynamic', 'Leakage'):
        need(re.findall(r'^\s*'+unit+r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')], 'explicit power watts required')
    values = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'), ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*'+label+r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        need(len(hits) == 1, 'native power component ambiguous/missing: '+label)
        value = Decimal(hits[0]); need(value.is_finite() and value >= 0, 'negative/nonfinite native power')
        values[key+'_power_w'] = str(value)
    duration = Decimal(task['activity_window']['duration_ticks'])*Decimal(task['activity_window']['timescale_seconds'])
    return dict(status='DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED', formal_elapsed_cycles=task['activity_window']['formal_elapsed_cycles'],
                original_layer_cycles=task['layer']['cycles'], duration_seconds=str(duration), power_components=values,
                diagnostic_energy_j=str(duration*Decimal(values['total_power_w'])), same_selected_map_area=area,
                measured_input_unknown_summary=task['measured_summary'], limitations=LIMITS)


def run(args, resume=False):
    out = args.out.resolve(); manifest = verify_prepared(out)
    prepared = identity(out/'prepared.json'); execution_path = out/'execution.json'
    env = environment(manifest['library_compiler_root'])
    if execution_path.exists():
        need(resume, 'existing execution must use resume; never restart completed native tasks')
        receipt = read(execution_path)
        need(receipt['prepared'] == prepared, 'resume actual preparation identity changed')
        if receipt['status'] == STATUS:
            for entry in receipt['tasks']:
                for row in entry['reports'].values(): need(identity(row['path']) == row, 'completed native report changed')
            return receipt
    else:
        receipt = dict(schema='xu-candidate-power146-execution-v1', profile=manifest['profile'],
            status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED', prepared=prepared, started_utc=now(),
            input_sha256_before=manifest['input_sha256'], requested_task_ids=list(range(12)), taskset_complete=False,
            tasks=[], limitations=LIMITS)
    native = read(manifest['mapped_sram_inventory']['path'])['macros']
    try:
        for task in manifest['tasks']:
            number = task['task_id']; directory = out/task['directory']; task_result = directory/'result.json'
            if task_result.exists():
                entry = read(task_result)
                need(entry['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' and entry['task_id'] == number and
                     entry['prepared'] == prepared, 'completed layer recovery binding differs')
                for row in entry['reports'].values(): need(identity(row['path']) == row, 'completed layer report changed')
                for key in ('native_audit',): need(identity(entry[key]['path']) == entry[key], 'completed audit changed')
            else:
                verify_prepared(out, full=False)
                need(identity(out/'prepared.json') == prepared, 'prepared changed during execution')
                receipt.update(status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED', current_task_id=number, pid=os.getpid())
                write(execution_path, receipt)
                native_run = execute([manifest['pt']['path'], '-f', 'power.tcl'], directory, task['completion_marker'], args.timeout, env, resume)
                # Discard only unfinished derived audits on explicit resume;
                # original native reports and measured activity are immutable.
                if resume:
                    for name in ('native-before.jsonl', 'native-after.jsonl', 'native-audit.json'):
                        path = directory/name
                        if path.exists(): path.rename(directory/(name+'.interrupted-'+uuid.uuid4().hex))
                audit_result = audit(directory, task['measured_sram_pin_states']['path'])
                reports = checked_reports(directory, task, native)
                for phase in audit_result['phases']:
                    need(phase['original'] == reports['sram-pins-'+phase['phase']+'.rpt'], 'streamed original native report SHA differs')
                entry = dict(task_id=number, status='EXECUTED_DIAGNOSTIC_NOT_QUALIFIED', prepared=prepared,
                    execution=native_run, reports=reports, native_audit=identity(directory/'native-audit.json'),
                    diagnostic=diagnostic(directory, task, manifest['area']), log_sha256=native_run['log']['sha256'])
                verify_prepared(out, full=False)
                write(task_result, entry)
            receipt['tasks'] = [e for e in receipt['tasks'] if e['task_id'] != number]+[entry]
            receipt['tasks'].sort(key=lambda e: e['task_id']); write(execution_path, receipt)
            print('XU146_EXECUTED profile=%s task=%02d cycles=%d W=%s J=%s DIAGNOSTIC_NOT_QUALIFIED' %
                  (manifest['profile'], number, entry['diagnostic']['formal_elapsed_cycles'],
                   entry['diagnostic']['power_components']['total_power_w'], entry['diagnostic']['diagnostic_energy_j']), flush=True)
        verify_prepared(out)
        need([t['task_id'] for t in receipt['tasks']] == list(range(12)), 'all twelve actual PT tasks required')
        energies = [Decimal(t['diagnostic']['diagnostic_energy_j']) for t in receipt['tasks']]
        durations = [Decimal(t['diagnostic']['duration_seconds']) for t in receipt['tasks']]
        cycles12 = sum(t['diagnostic']['formal_elapsed_cycles'] for t in receipt['tasks'])
        summary = dict(schema='xu-candidate-power146-summary-v1', profile=manifest['profile'], status=STATUS, qualification='NOT_QUALIFIED',
            selected_mapped=manifest['netlist'], analysis_sdc=manifest['analysis_sdc'], area=manifest['area'], task_count=12,
            elapsed_cycles12=cycles12, nominal_hz=150000000,
            nominal_12layer_latency_seconds_diagnostic=str(Decimal(cycles12)/Decimal(150000000)),
            nominal_12layer_throughput_per_second_diagnostic=str(Decimal(150000000)/Decimal(cycles12)),
            total_duration_seconds=str(sum(durations)), sum_diagnostic_energy_j=str(sum(energies)),
            time_weighted_mean_reported_power_w=str(sum(energies)/sum(durations)),
            layers=[dict(task_id=e['task_id'], **e['diagnostic'], log_sha256=e['log_sha256'], native_audit=e['native_audit']) for e in receipt['tasks']],
            limitations=LIMITS)
        write(out/'summary.json', summary)
        receipt.update(status=STATUS, taskset_complete=True, summary=identity(out/'summary.json'),
                       input_sha256_after={p: sha(p) for p in sorted(manifest['input_sha256'])})
        need(receipt['input_sha256_after'] == receipt['input_sha256_before'], 'execution before/after input identities differ')
    except BaseException as error:
        receipt.update(status='FAIL_DIAGNOSTIC_NOT_QUALIFIED', error=type(error).__name__+': '+str(error), taskset_complete=False)
        raise
    finally:
        receipt['finished_or_checkpoint_utc'] = now(); write(execution_path, receipt)
    return receipt


def audit_campaign(args):
    out = args.out.resolve(); manifest = verify_prepared(out)
    need(args.audit_out is not None, 'audit requires fresh --audit-out directory')
    destination = args.audit_out.resolve()
    need(not destination.exists() and not destination.is_symlink(), 'fresh independent audit output required')
    receipt = read(out/'execution.json')
    need(receipt['status'] == STATUS and receipt['taskset_complete'] is True and
         receipt['prepared'] == identity(out/'prepared.json') and
         [e['task_id'] for e in receipt['tasks']] == list(range(12)), 'complete own146 execution required for audit')
    destination.mkdir(parents=True)
    result = dict(schema='xu-candidate-power146-independent-audit-v1', status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED',
        qualification='NOT_QUALIFIED', profile=manifest['profile'], execution=identity(out/'execution.json'),
        prepared=identity(out/'prepared.json'), tasks=[], limitations=LIMITS)
    native = read(manifest['mapped_sram_inventory']['path'])['macros']
    try:
        for task, original in zip(manifest['tasks'], receipt['tasks']):
            number = task['task_id']; directory = out/task['directory']; target = destination/task['directory']; target.mkdir()
            need(read(directory/'result.json') == original and original['prepared'] == receipt['prepared'], 'original per-layer result differs')
            native_state = read(directory/'native-state.json')
            checked_log(directory/'pt.log', task['completion_marker'], native_state['returncode'])
            need(identity(directory/'pt.log') == original['execution']['log'], 'original PT execution log changed')
            reports = checked_reports(directory, task, native)
            need(reports == original['reports'], 'original native reports changed')
            audit_result = audit(directory, task['measured_sram_pin_states']['path'], output_directory=target)
            old = read(original['native_audit']['path'])
            for replay, previous in zip(audit_result['phases'], old['phases']):
                need(replay['original'] == previous['original'] and replay['compact']['sha256'] == previous['compact']['sha256'] and
                     all(replay[k] == previous[k] for k in ('pin_count', 'selected_attribute_counts', 'measured_native_cross_counts',
                         'before_after_counts', 'native_diagnostic_counts', 'source_membership_counts')), 'independent native streaming audit differs')
            current = diagnostic(directory, task, manifest['area'])
            need(current == original['diagnostic'], 'native power/duration/area recomputation differs')
            result['tasks'].append(dict(task_id=number, status='AUDITED_DIAGNOSTIC_NOT_QUALIFIED', native_audit=identity(target/'native-audit.json'), diagnostic=current))
            write(destination/'audit.json', result)
        verify_prepared(out)
        result.update(status='AUDITED_12_DIAGNOSTIC_NOT_QUALIFIED', task_count=12)
    except BaseException as error:
        result.update(status='FAIL_DIAGNOSTIC_NOT_QUALIFIED', error=type(error).__name__+': '+str(error))
        raise
    finally:
        result['finished_utc'] = now(); write(destination/'audit.json', result)
    return result


def plan(args):
    base = args.server_base.resolve(); rows = []
    for selected in read(HERE/'inventory137.snapshot.json')['candidates']:
        profile = selected['id']; receipts = base/'eight-candidate-freeze-queue-20261105-138'/profile
        output = base/args.campaign_name/profile
        argv = [args.python, str(HERE/'power146.py'), 'campaign', '--profile', profile,
                '--freeze-receipt', str(receipts/'freeze.json'), '--adoption-receipt', str(receipts/'adopt-own-fm.json'),
                '--source-root', selected['source']['server_root'], '--activity-root', str(base/args.activity_campaign/profile),
                '--activity-tools', str(args.activity_tools.resolve()), '--out', str(output)]
        rows.append(dict(id=profile, argv=argv, resume_argv=[args.python, str(HERE/'power146.py'), 'resume', '--out', str(output)],
                         expected_status=STATUS, expected_result=str(output/'execution.json'), expected_summary=str(output/'summary.json'),
                         selected_mapped=selected['formal']['mapped'], analysis_sdc=selected['ppa']['analysis_sdc'],
                         depends_on='activity145:'+profile, qualification='NOT_QUALIFIED'))
    result = dict(schema='xu-candidate-power146-job-plan-v1', status='PLANNED_NOT_EXECUTED_NOT_QUALIFIED', jobs=rows,
                  qualification='NOT_QUALIFIED', limitations=LIMITS)
    if args.plan_output: write(args.plan_output, result)
    else: print(__import__('json').dumps(result, indent=2, sort_keys=True))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify', 'run', 'resume', 'campaign', 'audit', 'plan'])
    parser.add_argument('--profile')
    parser.add_argument('--freeze-receipt', type=Path)
    parser.add_argument('--adoption-receipt', type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--activity-root', type=Path)
    parser.add_argument('--activity-tools', type=Path, default=HERE.parent/'xu-profile-activity145')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--audit-out', type=Path)
    parser.add_argument('--pt', default=PT)
    parser.add_argument('--lc-root', default=LC)
    parser.add_argument('--inventory-timeout', type=int, default=900)
    parser.add_argument('--timeout', type=int, default=21600)
    parser.add_argument('--server-base', type=Path, default=Path.home()/'Desktop/xu-score-optimization-20261102')
    parser.add_argument('--activity-campaign', default='eight-candidate-activity-20261105-145')
    parser.add_argument('--campaign-name', default='eight-candidate-power-20261105-146')
    parser.add_argument('--python', default='python3')
    parser.add_argument('--plan-output', type=Path)
    args = parser.parse_args(argv)
    need(args.timeout > 0 and args.inventory_timeout > 0, 'positive native timeouts required')
    if args.action == 'plan': plan(args); return 0
    need(args.out is not None, 'explicit --out required')
    new_intent = args.action in ('prepare', 'campaign') and not args.out.exists() and not args.out.is_symlink()
    try:
        if args.action in ('prepare', 'campaign'):
            for key in ('profile', 'freeze_receipt', 'adoption_receipt', 'source_root', 'activity_root'):
                need(getattr(args, key) is not None, 'explicit --'+key.replace('_', '-')+' required')
            result = prepare(args)
        if args.action == 'verify': result = verify_prepared(args.out)
        if args.action == 'audit': result = audit_campaign(args)
        if args.action in ('run', 'resume', 'campaign'): result = run(args, args.action == 'resume')
    except BaseException as error:
        # Preflight failures are terminal evidence too. Only an output that was
        # absent at entry may receive a new failure receipt; prior attempts and
        # a mistakenly repeated campaign are never edited by this handler.
        if new_intent and not args.out.is_symlink():
            args.out.mkdir(parents=True, exist_ok=True)
            target = args.out/('execution.json' if args.action == 'campaign' else 'preparation-state.json')
            if not target.exists():
                write(target, dict(schema='xu-candidate-power146-preflight-failure-v1',
                    status='FAIL_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED', profile=args.profile,
                    error=type(error).__name__+': '+str(error), taskset_complete=False, finished_utc=now()))
        raise
    print(result['status']+': '+str(args.out), flush=True)
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('FAIL146: '+type(error).__name__+': '+str(error), file=sys.stderr); sys.exit(1)
