#!/usr/bin/env python3
"""S2c own9c16 power with the exact166 forward-scope clock method. Python3.6+.

Only old57 SAIF and own S2c mapped design are used. No design/SDC/activity edits,
no automatic retry, and no energy/timing/function qualification.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback
import uuid

HERE = Path(__file__).resolve().parent
FROZEN130 = '95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46'
NET = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
TASK0 = 'EXECUTED_TASK0_COMMON190_DIAGNOSTIC_NOT_QUALIFIED'
FULL12 = 'EXECUTED_12_COMMON190_DIAGNOSTIC_NOT_QUALIFIED'
FAIL = 'FAIL_COMMON190_NOT_QUALIFIED'
LIMITS = [
 'NOT_QUALIFIED: averaged full-SoC SAIF diagnostic, not contest energy or score.',
 'Same ownS2c9c16 mapping, source, original57 twelve capture windows and measured SAIF bytes; own42338-point FM is conditional original proof.',
 'Analysis uses the same404c7d SDC, primary-clock contract and45037c forward scope as166, without all-clock propagation override.',
 'Common clock method alone does not establish complete150MHz closure or equivalence of real clock activity.',
 'All TX/TZ/TB and unknown Q remain unchanged; native x_probability=0 is not physically known Q.',
 'Mapped/default/propagated activity, SRAM conditional edge/internal-power modes and pre-CTS clock power remain review pending.',
 '33697 CPU pretask clear writes lie outside the measured task window; no clear-phase energy is measured.',
 'Original167 mapped VCS fatal remains unresolved. No timing suppression, force, new initialization or testbench change.',
]

def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_base():
    p = HERE / 'frozen130.py'
    need(hashlib.sha256(p.read_bytes()).hexdigest() == FROZEN130 and not p.is_symlink(), 'byte-identical frozen130 required')
    spec = importlib.util.spec_from_file_location('xu_frozen130_for190', str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


base = load_base()
read, write, identity, sha, canonical = base.read, base.write, base.identity, base.sha, base.canonical


def now():
    return datetime.now(timezone.utc).isoformat()


def selected_ids(value):
    need(value in ['0', 'all'], 'only task0 or all twelve tasks supported')
    return [0] if value == '0' else list(range(12))


def runtime():
    m = read(HERE / 'manifest190.json')
    need(m['schema'] == 'xu-common190-manifest-v1', 'runtime manifest schema differs')
    records = {}
    required = ['power190.py', 'frozen130.py', 'references190.json', 'run190.py', 'jobs190.py', 'command-preflight190.json', 'command-full12_190.json']
    need(sorted(row['name'] for row in m['runtime']) == sorted(required), 'complete unique runtime member set required')
    for row in m['runtime']:
        need(Path(row['name']).name == row['name'], 'unsafe runtime filename')
        actual = base.remember(records, HERE / row['name'], row['sha256'])
        need(actual['bytes'] == row['bytes'], 'runtime size differs')
    base.remember(records, HERE / 'manifest190.json')
    return records


def checked(row, records):
    return base.check_record(row, records)


def rehash(records):
    result = {}
    for p in records:
        try:
            result[p] = identity(p)['sha256']
        except (OSError, ValueError) as error:
            result[p] = 'UNAVAILABLE:' + type(error).__name__
    return result


def collect(value, records):
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            checked(value, records)
        for item in value.values():
            collect(item, records)
    elif isinstance(value, list):
        for item in value:
            collect(item, records)


def tcl(path):
    text = str(path)
    need(not any(x in text for x in ['{', '}', '\n', '\r']), 'unsafe Tcl literal path')
    return '{' + text + '}'


def source_context(records):
    ref = read(HERE / 'references190.json')
    need(ref['schema'] == 'xu-s2c-common190-references-v1', 'wrong190 references')
    for key in ['prepared57', 'execution57', 'fm_state', 'ppa_prepared', 'area', 'verify', 'scope']:
        checked(ref[key], records)
    prepared, execution = read(ref['prepared57']['path']), read(ref['execution57']['path'])
    need(prepared['schema'] == 'xu-s2c-full-soc-power-prepared-v1' and prepared['qualification'] == 'NOT_QUALIFIED' and
         prepared['requested_task_ids'] == list(range(12)) and prepared['taskset_complete'] is True and
         [x['task_id'] for x in prepared['tasks']] == list(range(12)), 'original57 complete preparation differs')
    need(execution['status'] == 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and execution['taskset_complete'] is True and
         execution['requested_task_ids'] == list(range(12)) and len(execution['tasks']) == 12 and
         execution['input_sha256_before'] == execution['input_sha256_after'] == prepared['input_sha256'] and
         len(prepared['input_sha256']) == 367 and execution['prepared'] == ref['prepared57'] and
         execution['prepared_sha256_after'] == ref['prepared57']['sha256'], 'original57 terminal/input receipts differ')
    for path, expected in prepared['input_sha256'].items():
        base.remember(records, path, expected)
    need(prepared['netlist']['sha256'] == NET and prepared['analysis_sdc']['sha256'] == SDC and
         prepared['implementation_controls']['source_profile'] == 's2c-autogroup' and
         prepared['source_context']['main_commit'] == 'd276b55ffecbe8d620f9a361bf5d0859299ba7b5' and
         prepared['strip_path'] == base.STRIP and ref['scope']['sha256'] == SCOPE,
         'own S2c source/map/SDC/scope differs')
    collect([prepared['netlist'], prepared['analysis_sdc'], prepared['implementation_controls']['libraries'],
             prepared['activity'], prepared['mapped_sram_inventory'], execution['tool']], records)
    need({x['sha256'] for x in prepared['implementation_controls']['libraries']} == base.LIBRARIES,
         'same two SS libraries required')
    fm = read(ref['fm_state']['path'])
    runs = [r for r in fm['runs'] if r['candidate'] == 's2c']
    need(len(runs) == 1, 'unique own S2c FM receipt required')
    native = runs[0]
    need(native['status'] == 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' and native['returncode'] == 0 and
         native['frozen_before'] == native['frozen_after'], 'own S2c original FM receipt differs')
    collect(native, records)
    text = Path(native['log']['path']).read_text(errors='replace')
    need(text.splitlines().count('XU_FULL_SOC_FORMALITY_PASS') == 1 and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)$', text, re.M) == ['Verification SUCCEEDED'] and
         re.findall(r'^\s*(\d+) Passing compare points\s*$', text, re.M) == ['42338'] and
         'Version R-2020.09-SP5' in text and not any(base.BAD.search(x) for x in text.splitlines()),
         'native own S2c complete FM log differs')
    need(any(r['sha256'] == NET for r in native['frozen_before'].values()), 'FM target must be own9c16')
    ppa = read(ref['ppa_prepared']['path'])
    collect(ppa['source_files'], records)
    need(all(ppa['implementation'].get(k) == v for k, v in prepared['implementation_controls'].items() if k != 'libraries') and
         [{k: r[k] for k in ['path', 'role', 'sha256']} for r in ppa['implementation']['libraries']] ==
         [{k: r[k] for k in ['path', 'role', 'sha256']} for r in prepared['implementation_controls']['libraries']],
         'own PPA implementation differs (library bytes separately rehashed)')
    ppa_run = read(native['ppa_execution']['path'])
    need(ppa_run['netlist_sha256'] == NET and ppa_run['analysis_sdc_sha256'] == SDC and
         ppa_run['dc']['returncode'] == 0 and ppa_run['pt']['returncode'] == 0 and
         ppa_run['reports']['area.rpt']['sha256'] == ref['area']['sha256'], 'own PPA area/map receipt differs')
    area_text = Path(ref['area']['path']).read_text()
    accel = re.findall(r'^u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave\n\s*([0-9.]+)[^\n]*accel_icb_slave\s*$', area_text, re.M)
    total = re.findall(r'^Total cell area:\s*([0-9.]+)\s*$', area_text, re.M)
    need(accel == ['294801.8380'] and total == ['3365797.600429'], 'own9c16 original area differs')
    original_inventory = read(prepared['mapped_sram_inventory']['path'])
    checked(original_inventory['provenance']['raw_tsv'], records)
    original_macros = base.inventory_rows(original_inventory['provenance']['raw_tsv']['path'])
    need(original_macros == original_inventory['macros'] and original_inventory['netlist'] == prepared['netlist'],
         'original native inventory TSV/map differs')
    for task, old in zip(prepared['tasks'], execution['tasks']):
        need(task['task_id'] == old['task_id'] and old['status'] == 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING' and
             task['activity_window']['duration_ticks'] == 6604373333334 and
             task['activity_window']['formal_elapsed_cycles'] == 990656 and
             task['activity_window']['timescale_seconds'] == 1e-15 and len(task['macro_names']) == 336,
             'original own57 task identity/window differs')
        collect([task['script'], task['saif'], task['canonical_saif'], task['mapped_macro_bridge'],
                 task['measured_sram_pin_states'], old['execution']['log'], old['diagnostic']['report']], records)
        base.checked_native_log(old['execution']['log']['path'], task['completion_marker'], old['execution']['returncode'])
        need(read(task['mapped_macro_bridge']['path']) == task['mapped_macro_bridge_receipt'], 'original bridge receipt changed')
        b = task['mapped_macro_bridge_receipt']
        need(b['macro_count'] == 336 and b['mapped_pin_bit_count'] == 22512 and
             b['output_saif'] == task['saif'] and b['duration_ticks'] == 6604373333334 and
             b['inventory'] == prepared['mapped_sram_inventory'], 'original mapped SAIF bijection differs')
    return dict(original_prepared=ref['prepared57'], original_execution=ref['execution57'],
                netlist=prepared['netlist'], analysis_sdc=prepared['analysis_sdc'], clock_scope=ref['scope'],
                source_context=prepared['source_context'], native_fm_log=native['log'],
                native_fm_state=ref['fm_state'], passing_compare_points=42338, area_report=ref['area'],
                area=dict(accelerator_mm2='0.2948018380', full_soc_mm2='3.365797600429',
                          accelerator_limit_mm2='2.25', below_area_limit=True, qualification='NOT_QUALIFIED'),
                original_configuration_sha256=prepared['original_capture_configuration_sha256']), prepared, execution, original_macros


def common_clock(original, scope):
    old = 'set_propagated_clock [all_clocks]\nupdate_timing\n'
    need(original.count(old) == 1 and scope['sha256'] == SCOPE, 'unique original allprop clock block required')
    new = 'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' + tcl(scope['path']) + '\nupdate_timing\n'
    result = original.replace(old, new)
    need('set_propagated_clock [all_clocks]' not in result and result.count('source ' + tcl(scope['path'])) == 1,
         'forwarded common clock scope differs')
    return result


def power_script(task, item, scope):
    text = Path(task['script']['path']).read_text()
    need(sha(task['script']['path']) == task['script']['sha256'], 'original power Tcl changed')
    text = common_clock(text, scope)
    need(text.count(tcl(task['saif']['path'])) == 1 and text.count(task['completion_marker']) == 1,
         'unique original SAIF/marker replacements required')
    return text.replace(tcl(task['saif']['path']), tcl(item['saif']['path'])).replace(task['completion_marker'], item['completion_marker'])


def inventory_script(task, scope, marker):
    text = common_clock(Path(task['script']['path']).read_text(), scope)
    stop = 'set xu_expected_macros [list '
    need(text.count(stop) == 1 and text.startswith('if {[catch {\n'), 'original57 macro prelude differs')
    prefix = text[:text.index(stop)]
    body = '''set f [open macro-pins.tsv w]
puts $f "kind\\tcell\\tref_or_pin\\tlibcell_or_direction"
set nc 0
set np 0
foreach_in_collection c $xu_all_macros {
 set name [get_object_name $c]
 set lc [get_lib_cells -of_objects $c]
 if {[sizeof_collection $lc] != 1} {error {macro library cell not unique}}
 puts $f "MACRO\\t$name\\t[get_attribute $c ref_name]\\t[get_object_name $lc]"
 incr nc
 foreach_in_collection p [get_pins -quiet -of_objects $c] {
  puts $f "PIN\\t$name\\t[get_object_name $p]\\t[get_attribute $p direction]"
  incr np
 }
}
close $f
if {$nc != 336 || $np != 22512} {error {native inventory counts differ}}
'''
    return prefix + body + 'puts ' + tcl(marker) + '\n} err]} {puts stderr "XU_FATAL: $err"; exit 1}\nexit 0\n'


def environment(lc_root):
    need(Path(lc_root).is_dir() and (Path(lc_root) / 'bin').is_dir(), 'library compiler root/bin unavailable')
    env = dict(os.environ)
    env['SYNOPSYS_LC_ROOT'] = str(lc_root)
    env['PATH'] = str(Path(lc_root) / 'bin') + os.pathsep + env.get('PATH', '')
    return env


def native(script, directory, tool, env, timeout):
    command = [tool['path'], '-f', script.name]
    result = dict(command=command, cwd=str(directory), started_utc=now())
    with (directory / 'pt.log').open('wb') as log:
        process = subprocess.Popen(command, cwd=str(directory), env=env, stdout=log, stderr=subprocess.STDOUT)
        result['pid'] = process.pid
        try:
            result['returncode'] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            result['timed_out'] = True
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            result['returncode'] = process.returncode
    result.update(finished_utc=now(), log=identity(directory / 'pt.log'))
    return result


def checked_reports(directory, task):
    reports = {}
    expected_pins = sorted(p['mapped_path'] for p in read(task['measured_sram_pin_states']['path'])['pins'])
    for name in task['expected_reports']:
        p = directory / name
        row = identity(p)
        need(row['bytes'] > 0 or name == 'inconsistent.rpt', 'empty mandatory native report: ' + name)
        pin_names, power_names = [], []
        # Streaming error/name scan avoids loading ~0.8GB pin reports into memory.
        with p.open(errors='replace') as stream:
            for line in stream:
                need(base.BAD.search(line) is None, 'native report error: ' + name)
                if name in ['sram-pins-before.rpt', 'sram-pins-after.rpt']:
                    match = re.fullmatch(r'XU_SRAM_PIN name=(.+)', line.rstrip('\n'))
                    if match:
                        pin_names.append(match.group(1))
                elif name == 'sram-power.rpt':
                    match = re.fullmatch(r'XU_SRAM_POWER_CELL name=(.+) ref=(\S+)', line.rstrip('\n'))
                    if match:
                        need(match.group(2) == 'RAMSP1024X16', 'native power SRAM reference differs')
                        power_names.append(match.group(1))
        if name in ['sram-pins-before.rpt', 'sram-pins-after.rpt']:
            need(sorted(pin_names) == expected_pins, 'native pin report must cover exactly every22512 pin: ' + name)
        if name == 'sram-power.rpt':
            need(sorted(power_names) == task['macro_names'], 'native power report must cover exactly336 macros')
        reports[name] = row
    return reports


def prepared_verify(out, m):
    need(m['schema'] == 'xu-common190-prepared-v1' and m['qualification'] == 'NOT_QUALIFIED' and
         m['requested_task_ids'] in [[0], list(range(12))] and
         [t['task_id'] for t in m['tasks']] == m['requested_task_ids'], '190 prepared taskset/schema differs')
    base.verify_inputs(m['input_sha256'])
    need(m['producer'] == identity(HERE / 'power190.py'), '190 producer differs')
    original = read(m['context']['original_prepared']['path'])
    macros = base.inventory_rows(out / 'inventory/macro-pins.tsv')
    need(macros == read(original['mapped_sram_inventory']['path'])['macros'] and
         len(macros) == 336 and sum(len(x['pins']) for x in macros) == 22512, '190 native inventory changed')
    inv = read(out / 'inventory/state.json')
    need(inv['status'] == 'EXPORTED_COMMON190_NOT_QUALIFIED' and
         inv['input_sha256_before'] == inv['input_sha256_after'] and
         inv['context'] == m['context'], '190 native inventory receipt differs')
    base.checked_native_log(out / 'inventory/pt.log', inv['marker'], inv['execution']['returncode'])
    need((out / 'inventory/export.tcl').read_text() == inventory_script(original['tasks'][0], m['context']['clock_scope'], inv['marker']),
         '190 inventory Tcl reconstruction differs')
    need(m['context']['netlist'] == original['netlist'] and m['context']['netlist']['sha256'] == NET and
         m['context']['analysis_sdc'] == original['analysis_sdc'] and m['context']['analysis_sdc']['sha256'] == SDC and
         m['context']['clock_scope'] == read(HERE / 'references190.json')['scope'] and
         m['context']['source_context'] == original['source_context'], '190 own context/clock method differs')
    for task in m['tasks']:
        need(task['expected_reports'] == original['tasks'][task['task_id']]['expected_reports'] and
             task['macro_names'] == sorted(x['instance'] for x in macros) and
             task['measured_summary'] == measured_summary(original['tasks'][task['task_id']], macros), '190 full report/macro/unknown summary differs')
        need(task['directory'] == 'task_%02d' % task['task_id'] and len(task['macro_names']) == 336 and
             task['saif'] == identity(task['saif']['path']) and
             task['saif']['sha256'] == original['tasks'][task['task_id']]['saif']['sha256'] and
             task['activity_window'] == original['tasks'][task['task_id']]['activity_window'] and
             task['script'] == identity(out / task['directory'] / 'power.tcl'), '190 own57 SAIF/window/script differs')
        need((out / task['directory'] / 'power.tcl').read_text() == power_script(original['tasks'][task['task_id']], task, m['context']['clock_scope']),
             '190 power Tcl reconstruction differs')
    return original


def checked_preflight(root, context, records):
    root = Path(root).absolute()
    for name in ['prepared.json', 'execution.json', 'summary.json', 'result.json']:
        base.remember(records, root / name)
    m = read(root / 'prepared.json')
    prepared_verify(root, m)
    e, s, r = [read(root / n) for n in ['execution.json', 'summary.json', 'result.json']]
    need(m['requested_task_ids'] == [0] and m['preflight'] is None and m['context'] == context and
         all(x['status'] == TASK0 and x['qualification'] == 'NOT_QUALIFIED' for x in [e, s, r]) and
         e['input_sha256_before'] == e['input_sha256_after'] == m['input_sha256'] and
         e['prepared'] == identity(root / 'prepared.json') and e['summary'] == r['summary'] == identity(root / 'summary.json') and
         len(e['tasks']) == s['task_count'] == 1 and e['tasks'] == s['tasks'] and s['context'] == context and
         s['sum_diagnostic_energy_j'] == e['tasks'][0]['diagnostic']['diagnostic_energy_j'], 'successful real same-map/method task0 required')
    entry, task = e['tasks'][0], m['tasks'][0]
    base.checked_native_log(root / 'task_00/pt.log', task['completion_marker'], entry['execution']['returncode'])
    need(entry['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' and
         entry['execution']['log'] == identity(root / 'task_00/pt.log') and
         entry['frozen_inputs_sha256'] == canonical(m['input_sha256']) and
         entry['reports'] == checked_reports(root / 'task_00', task) and
         entry['diagnostic'] == diagnostic(root / 'task_00', task), 'preflight native reports/diagnostic differ')
    collect(entry, records)
    return dict(status=TASK0, root=str(root), prepared=identity(root / 'prepared.json'),
                execution=identity(root / 'execution.json'), summary=identity(root / 'summary.json'), result=identity(root / 'result.json'))


def measured_summary(task, macros):
    source = read(task['measured_sram_pin_states']['path'])
    pins = source['pins']
    expected = {p['full_name'] for macro in macros for p in macro['pins']}
    need(len(pins) == len(expected) == 22512 and {p['mapped_path'] for p in pins} == expected,
         'original measured22512 pin inventory must be exact')
    duration = task['activity_window']['duration_ticks']
    need(all(sum(p.get(k, 0) for k in ['T0', 'T1', 'TX', 'TZ', 'TB']) == duration for p in pins),
         'original measured per-bit dwell differs')
    unknown = sum(p.get(k, 0) for p in pins for k in ['TX', 'TZ', 'TB'])
    need(unknown == source['alias_unknown_bit_ticks'] == task['mapped_macro_bridge_receipt']['measured_unknown_bit_ticks'],
         'original measured unknown bit ticks differ')
    q = [p for p in pins if p['mapped_path'].rsplit('/', 1)[-1].startswith('Q[')]
    need(len(q) == 5376, 'original measured Q inventory differs')
    return dict(pin_count=22512, q_pin_count=5376, measured_unknown_bit_ticks=unknown,
                q_tx_positive=sum(p.get('TX', 0) > 0 for p in q),
                q_tx_full_window=sum(p.get('TX', 0) == duration for p in q),
                duration_ticks=duration, timescale_seconds='1E-15')


def diagnostic(directory, task):
    result = base.diagnostic(directory, task)
    result['unresolved'] = LIMITS
    return result


def prepare(args, state):
    out = args.out.absolute()
    records = runtime()
    state['input_sha256_before'] = dict(records)
    write(out / 'result.json', state)
    try:
        context, old, oldexec, macros = source_context(records)
    finally:
        state.update(input_sha256_before=dict(records), phase='source-context-checked-or-failed')
        write(out / 'result.json', state)
    preflight = checked_preflight(args.preflight_root, context, records) if args.task_ids != [0] else None
    env = environment(args.lc_root)
    tool = checked(oldexec['tool'], records)
    need(Path(args.pt).absolute() == Path(tool['path']), 'same original native PT executable required')
    state.update(phase='native-inventory', input_sha256_before=dict(records))
    write(out / 'result.json', state)
    invdir = out / 'inventory'
    invdir.mkdir()
    marker = 'XU_COMMON190_INVENTORY_' + uuid.uuid4().hex
    script = invdir / 'export.tcl'
    script.write_text(inventory_script(old['tasks'][0], context['clock_scope'], marker))
    base.remember(records, script)
    before = dict(records)
    inv = dict(status='RUNNING_COMMON190_NOT_QUALIFIED', qualification='NOT_QUALIFIED', context=context,
               marker=marker, input_sha256_before=before)
    write(invdir / 'state.json', inv)
    try:
        inv['execution'] = native(script, invdir, tool, env, args.inventory_timeout)
        write(invdir / 'state.json', inv)
        need(not inv['execution'].get('timed_out', False), '190 inventory native timeout')
        base.checked_native_log(invdir / 'pt.log', marker, inv['execution']['returncode'])
        need(base.inventory_rows(invdir / 'macro-pins.tsv') == macros, 'new native336/22512 inventory differs from original SAIF mapping')
        inv['status'] = 'EXPORTED_COMMON190_NOT_QUALIFIED'
    except BaseException as error:
        inv.update(status=FAIL, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
        raise
    finally:
        inv['input_sha256_after'] = rehash(before)
        if inv['input_sha256_after'] != before:
            inv.update(status=FAIL, error='inventory input changed')
        write(invdir / 'state.json', inv)
    need(inv['status'] == 'EXPORTED_COMMON190_NOT_QUALIFIED', '190 inventory failed')
    for p in invdir.iterdir():
        if p.is_file():
            base.remember(records, p)
    m = dict(schema='xu-common190-prepared-v1', status='PREPARED_COMMON190_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
             context=context, producer=identity(HERE / 'power190.py'), requested_task_ids=args.task_ids, preflight=preflight,
             tool=tool, library_compiler_root=str(args.lc_root), tasks=[], limitations=LIMITS)
    for taskid in args.task_ids:
        original = old['tasks'][taskid]
        directory = out / ('task_%02d' % taskid)
        directory.mkdir()
        shutil.copyfile(original['saif']['path'], str(directory / 'task-mapped.saif'))
        item = dict(original)
        item.update(saif=identity(directory / 'task-mapped.saif'), measured_summary=measured_summary(original, macros),
                    original_task_saif=original['saif'], completion_marker='XU_COMMON190_TASK_%02d_%s' % (taskid, uuid.uuid4().hex))
        need(item['saif']['sha256'] == original['saif']['sha256'], 'original measured SAIF bytes must remain exact')
        (directory / 'power.tcl').write_text(power_script(original, item, context['clock_scope']))
        item['script'] = identity(directory / 'power.tcl')
        checked(item['saif'], records)
        checked(item['script'], records)
        m['tasks'].append(item)
    base.verify_inputs(records)
    m['input_sha256'] = records
    write(out / 'prepared.json', m)
    state.update(status=m['status'], phase='prepared', prepared=identity(out / 'prepared.json'),
                 input_sha256_before=dict(records), input_sha256_after=rehash(records))
    write(out / 'result.json', state)
    return m


def run(args, state):
    out = args.out.absolute()
    m = read(out / 'prepared.json')
    prepared_verify(out, m)
    need(m['requested_task_ids'] == args.task_ids and not (out / 'execution.json').exists(), '190 execution exists or requested taskset changed')
    if args.task_ids != [0]:
        need(checked_preflight(m['preflight']['root'], m['context'], {}) == m['preflight'], '190 preflight changed')
    for t in m['tasks']:
        need(not any((out / t['directory'] / n).exists() for n in t['expected_reports'] + ['pt.log']), 'native output exists; never restart')
    e = dict(schema='xu-common190-execution-v1', status='RUNNING_COMMON190_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
             pid=os.getpid(), requested_task_ids=args.task_ids, prepared=identity(out / 'prepared.json'), tasks=[],
             input_sha256_before=m['input_sha256'], taskset_complete=False, context=m['context'], started_utc=now())
    state.update(status=e['status'], phase='power')
    write(out / 'execution.json', e)
    write(out / 'result.json', state)
    try:
        env = environment(m['library_compiler_root'])
        for task in m['tasks']:
            prepared_verify(out, m)
            need(identity(out / 'prepared.json') == e['prepared'], '190 prepared changed')
            e['current_task_id'] = state['current_task_id'] = task['task_id']
            write(out / 'execution.json', e)
            write(out / 'result.json', state)
            directory = out / task['directory']
            entry = dict(task_id=task['task_id'], status='NATIVE_UNREVIEWED_NOT_QUALIFIED')
            e['tasks'].append(entry)
            entry['execution'] = native(directory / 'power.tcl', directory, m['tool'], env, args.timeout)
            write(out / 'execution.json', e)
            need(not entry['execution'].get('timed_out', False), '190 native power timeout')
            base.checked_native_log(directory / 'pt.log', task['completion_marker'], entry['execution']['returncode'])
            entry['reports'] = checked_reports(directory, task)
            need(base.PT_VERSION in (directory / 'tool-version.rpt').read_text(), 'native PT version differs')
            entry.update(diagnostic=diagnostic(directory, task), status='EXECUTED_DIAGNOSTIC_NOT_QUALIFIED',
                         frozen_inputs_sha256=canonical(m['input_sha256']))
            prepared_verify(out, m)
            write(out / 'execution.json', e)
            print('XU190_EXECUTED_TASK id=%d NOT_QUALIFIED' % task['task_id'], flush=True)
        status = TASK0 if args.task_ids == [0] else FULL12
        summary = dict(status=status, qualification='NOT_QUALIFIED', task_count=len(args.task_ids),
                       taskset_complete=args.task_ids == list(range(12)), tasks=e['tasks'], context=m['context'],
                       total_elapsed_cycles=sum(t['activity_window']['formal_elapsed_cycles'] for t in m['tasks']),
                       sum_diagnostic_energy_j=str(sum(Decimal(t['diagnostic']['diagnostic_energy_j']) for t in e['tasks'])),
                       limitations=LIMITS)
        write(out / 'summary.json', summary)
        e.update(status=status, taskset_complete=summary['taskset_complete'], summary=identity(out / 'summary.json'))
        state.update(status=status, phase='complete', summary=identity(out / 'summary.json'))
    except BaseException as error:
        e.update(status=FAIL, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
        raise
    finally:
        e.update(finished_utc=now(), input_sha256_after=rehash(m['input_sha256']))
        if e['input_sha256_after'] != e['input_sha256_before']:
            e.update(status=FAIL, taskset_complete=False, integrity_error='190 input changed')
        write(out / 'execution.json', e)
    need(e['status'] in [TASK0, FULL12], '190 native execution/input failure')


def output_manifest(out):
    files = []
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name not in ['output-manifest190.json', 'controller-worker.lock'] and '.tmp' not in p.name:
            files.append(dict(relative=str(p.relative_to(out)), **identity(p)))
    write(out / 'output-manifest190.json', dict(schema='xu-common190-output-manifest-v1', qualification='NOT_QUALIFIED', files=files))


@contextmanager
def exclusive(out):
    with (out / 'controller-worker.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'verify', 'run', 'campaign'])
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--task-ids', type=selected_ids, default=[0])
    p.add_argument('--preflight-root', type=Path)
    p.add_argument('--pt', type=Path, default=Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell'))
    p.add_argument('--lc-root', type=Path, default=Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
    p.add_argument('--timeout', type=int, default=21600)
    p.add_argument('--inventory-timeout', type=int, default=900)
    args = p.parse_args(argv)
    need(args.timeout > 0 and args.inventory_timeout > 0, 'positive native timeout required')
    out = args.out.absolute()
    if args.action in ['prepare', 'campaign']:
        need((args.task_ids == [0]) == (args.preflight_root is None), 'full12 requires successful preflight; task0 cannot supply one')
        need(not out.exists() and not out.is_symlink(), 'fresh190 output required; no restart/overwrite')
        out.mkdir(parents=True)
        state = dict(schema='xu-common190-result-v1', status='PREPARING_COMMON190_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                     pid=os.getpid(), started_utc=now(), requested_task_ids=args.task_ids, limitations=LIMITS)
        write(out / 'result.json', state)
    else:
        state = read(out / 'result.json')
        need(state['status'] == 'PREPARED_COMMON190_NOT_QUALIFIED', 'only immutable prepared190 may run/verify')
    with exclusive(out):
        try:
            runtime()
            if args.action in ['prepare', 'campaign']:
                prepare(args, state)
            if args.action == 'verify':
                m = read(out / 'prepared.json')
                need(m['requested_task_ids'] == args.task_ids, 'verify requested taskset differs')
                prepared_verify(out, m)
            if args.action in ['run', 'campaign']:
                run(args, state)
        except BaseException as error:
            state.update(status=FAIL, error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
            raise
        finally:
            state.update(finished_utc=now(), input_sha256_after=rehash(state.get('input_sha256_before', {})))
            if state['input_sha256_after'] != state.get('input_sha256_before', {}):
                state.update(status=FAIL, integrity_error='190 final input changed')
            write(out / 'result.json', state)
            output_manifest(out)
    print(state['status'] + ': ' + str(out), flush=True)
    return 0 if state['status'] != FAIL else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('FAIL190: ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        sys.exit(1)
