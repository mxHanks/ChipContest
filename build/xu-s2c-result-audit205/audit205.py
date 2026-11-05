#!/usr/bin/env python3
"""Independent local review of actual common-method S2c190. No runtime imports/EDA."""
import argparse
import csv
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import re
import tarfile
import traceback

import safe171

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REMOTE = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
RUNTIME = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-s2c-common-power198/'
REFSHA = 'c4e6b3ab5cc76a87eb056c1038a4ae11f0bfbbd66a180197b69291a6fa75f1ec'
NET = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
FMSTATE = 'dadd3bb693a3ae17bf92682d9586fa1ba07e6ead468465e07b67fa91eabea5dd'
PRODUCER = '941d99e641ceee571a57b7f6076094197de7253fdcc0bc3692398a543c50ad13'
PT = 'T-2022.03-SP5-1'
ROOT0 = 's2c-common-scope-preflight-20261105-190'
ROOT12 = 's2c-common-scope-power12-20261105-190'
TASK0 = 'EXECUTED_TASK0_COMMON190_DIAGNOSTIC_NOT_QUALIFIED'
FULL12 = 'EXECUTED_12_COMMON190_DIAGNOSTIC_NOT_QUALIFIED'
STRIP = 'tb_xu_soc_ppa/dut'
ACCEL = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'
BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)
WIDTHS = dict(CLK=1, CEN=1, WEN=16, A=10, D=16, EMA=3, EMAW=2, GWEN=1, RET1N=1, Q=16)
PINS = {k if width == 1 else '%s[%d]' % (k, bit) for k, width in WIDTHS.items() for bit in range(width)}
LIMITS = [
 'NOT_QUALIFIED: diagnostic measured task energy only; no contest score or full qualification.',
 'Returned bodies are locally hashed/rescanned; absent large reports have only stable bounded server hashes, not local pin-body replay.',
 'External RTL/netlist/SVF/library/SAIF hashes are server before/after receipts; absent external contents are not locally rehashed.',
 'Original57 twelve measured bit-statistic bodies and native macro inventories are locally checked; mapped SAIF bodies are absent, so SAIF continuity is exact recorded SHA continuity, not local SAIF parsing.',
 'Unknown Q/TX/TZ/TB are retained; x_probability=0 does not establish physical known Q or complete SRAM conditional/internal power.',
 'Same166 SDC/forwarded-clock method does not establish actual clock-tree power, full150MHz closure or gate-level functionality.',
 'Original167 mapped VCS fatal remains unresolved; no force, timing suppression, new initialization, RTL or testbench edits.',
 'CPU pretask clear lies outside measured task windows; clear-phase energy is not included.',
]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    return safe171.unique_json(Path(path).read_bytes())


def sha(path):
    return safe171.sha_file(path)


def ident(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'regular non-symlink file required: ' + str(p))
    return dict(bytes=p.stat().st_size, sha256=sha(p))


def same(a, b):
    return all(a.get(k) == b.get(k) for k in ['bytes', 'sha256'])


def canonical(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def raw_inventory(text):
    lines = text.splitlines()
    need(lines[0] == 'kind\tcell\tref_or_pin\tlibcell_or_direction', 'raw inventory header')
    macros = {}; allpins = set()
    for line in lines[1:]:
        fields = line.split('\t'); need(len(fields) == 4, 'inventory row shape')
        kind, cell, value, extra = fields
        if kind == 'MACRO':
            need(cell not in macros and value == 'RAMSP1024X16' and extra ==
                 'RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16', 'unique macro/library')
            macros[cell] = dict(instance=cell, ref_name=value, lib_cell=extra, pins=[])
        else:
            need(kind == 'PIN' and cell in macros and value.startswith(cell + '/'), 'exact pin owner')
            name = value[len(cell) + 1:]
            need(name in PINS and value not in allpins and extra == ('out' if name.startswith('Q[') else 'in'),
                 'exact pin geometry/direction/uniqueness')
            allpins.add(value); macros[cell]['pins'].append(dict(name=name, full_name=value, direction=extra))
    need(len(macros) == 336 and len(allpins) == 22512 and all({p['name'] for p in m['pins']} == PINS for m in macros.values()),
         'complete native336/22512 inventory')
    return [macros[k] for k in sorted(macros)]


def clock_section(text):
    return text[text.index('set XU_CLOCK_MODE envelope\n'):text.index('# Exact post-elaboration macro groups;')]


def normal_clock(text):
    return re.sub(r'(?m)^source \{[^\n]+/constraints\.sdc\}$', 'source {SAME404c7d_SDC}', clock_section(text))


def reference_data():
    need(sha(HERE / 'references205.json') == REFSHA, '205 reference index differs')
    index = load(HERE / 'references205.json')
    files = {}; manifests = {}
    for row in index['files']:
        name = safe171.safe_name(row['path']); p = REPO / name
        need(name not in files and same(ident(p), row), 'preserved reference bytes differ: ' + name)
        files[name] = p
        if p.name == 'manifest.json':
            content = load(p); entries = content['files'] if isinstance(content, dict) else content
            manifests[p.parent] = {r['path']: r for r in entries}
    for name, p in files.items():
        matches = [(base, rows) for base, rows in manifests.items() if base in p.parents]
        if matches and p.name != 'manifest.json':
            base, rows = max(matches, key=lambda row: len(str(row[0])))
            rel = str(p.relative_to(base)); need(rel in rows and same(ident(p), rows[rel]), 'original payload manifest differs')
    oldroot = REPO / 'build/xu-score-resume-20261103/next-results-export-69/s2c-full-soc-power12-20261104-57'
    old = load(oldroot / 'prepared.json'); execution = load(oldroot / 'execution.json')
    need(old['schema'] == 'xu-s2c-full-soc-power-prepared-v1' and old['qualification'] == 'NOT_QUALIFIED' and
         old['taskset_complete'] is True and old['requested_task_ids'] == list(range(12)) and
         [t['task_id'] for t in old['tasks']] == list(range(12)), 'original57 full12 preparation')
    need(execution['status'] == 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and execution['taskset_complete'] is True and
         execution['requested_task_ids'] == list(range(12)) and len(execution['tasks']) == 12 and
         old['input_sha256'] == execution['input_sha256_before'] == execution['input_sha256_after'] and len(old['input_sha256']) == 367,
         'original57 recorded freeze/taskset')
    need(same(execution['prepared'], ident(oldroot / 'prepared.json')) and
         execution['prepared_sha256_after'] == sha(oldroot / 'prepared.json'), 'original57 prepared receipt continuity')
    need(old['netlist']['sha256'] == NET and old['analysis_sdc']['sha256'] == SDC and old['strip_path'] == STRIP and
         old['source_context']['main_commit'] == 'd276b55ffecbe8d620f9a361bf5d0859299ba7b5', 'own S2c source/map/SDC')
    refdir = REPO / 'build/xu-s2c-common-power190'; refs = load(refdir / 'references190.json')
    need(refs['fm_state']['sha256'] == refs['fm_state_original']['sha256'] == sha(refdir / 'frozen-fm190.json') == FMSTATE and
         refs['fm_state']['bytes'] == refs['fm_state_original']['bytes'] == 349702 and
         refs['fm_state']['path'] == RUNTIME + 'frozen-fm190.json', 'immutable whole original FM snapshot')
    need(refs['prepared57']['sha256'] == sha(oldroot / 'prepared.json') and refs['execution57']['sha256'] == sha(oldroot / 'execution.json'), 'own57 reference identities')
    fmroot = REPO / 'build/xu-score-resume-20261103/current-evidence-export-09'
    need(sha(fmroot / 'candidate-formality-campaign-20261103-01/state.json') == FMSTATE, 'whole FM original09 equals immutable snapshot')
    fmstate = load(refdir / 'frozen-fm190.json'); own = [r for r in fmstate['runs'] if r['candidate'] == 's2c']
    need(len(own) == 1, 'unique own FM'); fm = own[0]
    need(fm['status'] == 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' and fm['returncode'] == 0 and fm['frozen_before'] == fm['frozen_after'], 'own FM freeze/rc')
    text = (fmroot / fm['log']['path'].split(REMOTE)[1]).read_text()
    need('Version R-2020.09-SP5' in text and text.splitlines().count('XU_FULL_SOC_FORMALITY_PASS') == 1 and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)$', text, re.M) == ['Verification SUCCEEDED'] and
         re.findall(r'^\s*(\d+) Passing compare points\s*$', text, re.M) == ['42338'] and
         not any(BAD.search(line) for line in text.splitlines()), 'native own42338 FM body')
    need(any(row['sha256'] == NET for row in fm['frozen_before'].values()), 'own FM targets9c16')
    ppa = load(fmroot / fm['ppa_execution']['path'].split(REMOTE)[1])
    area = (fmroot / refs['area']['path'].split(REMOTE)[1]).read_text()
    need(ppa['netlist_sha256'] == NET and ppa['analysis_sdc_sha256'] == SDC and ppa['dc']['returncode'] == ppa['pt']['returncode'] == 0 and
         ppa['reports']['area.rpt']['sha256'] == refs['area']['sha256'], 'own area/PPA pairing')
    need(re.findall(r'^' + re.escape(ACCEL) + r'\n\s*([0-9.]+)[^\n]*accel_icb_slave\s*$', area, re.M) == ['294801.8380'] and
         re.findall(r'^Total cell area:\s*([0-9.]+)\s*$', area, re.M) == ['3365797.600429'], 'own original accelerator/SoC area')
    invroot = REPO / 'build/xu-score-resume-20261103/terminal-results-export-22'
    inventory = load(invroot / old['mapped_sram_inventory']['path'].split(REMOTE)[1])
    macros = raw_inventory((invroot / inventory['provenance']['raw_tsv']['path'].split(REMOTE)[1]).read_text())
    need(inventory['macros'] == macros and inventory['netlist'] == old['netlist'], 'original native raw/JSON inventory/map')
    allpins = {p['full_name'] for m in macros for p in m['pins']}; measured = []
    clock166 = REPO / 'build/xu-score-resume-20261103/preflight178/s2e-final155-power-preflight-20261105-166/task_00/power.tcl'
    for i, task in enumerate(old['tasks']):
        need(task['task_id'] == execution['tasks'][i]['task_id'] == i and execution['tasks'][i]['status'] == 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING', 'original57 executed task IDs')
        w = task['activity_window']; need(w['duration_ticks'] == 6604373333334 and w['formal_elapsed_cycles'] == 990656 and w['timescale_seconds'] == 1e-15, 'exact original measured window')
        source = load(oldroot / ('task_%02d/measured-sram-pins.json' % i)); pins = source['pins']
        need(len(pins) == len({p['mapped_path'] for p in pins}) == 22512 and {p['mapped_path'] for p in pins} == allpins and
             all(sum(p.get(k, 0) for k in ['T0', 'T1', 'TX', 'TZ', 'TB']) == w['duration_ticks'] for p in pins), 'measured bit-time conservation and exact22512 bijection')
        q = [p for p in pins if re.search(r'/Q\[\d+\]$', p['mapped_path'])]; need(len(q) == 5376, 'all measured Q bits')
        unknown = sum(p.get(k, 0) for p in pins for k in ['TX', 'TZ', 'TB'])
        need(unknown == source['alias_unknown_bit_ticks'] == task['mapped_macro_bridge_receipt']['measured_unknown_bit_ticks'], 'measured unknown tick continuity')
        measured.append(dict(pin_count=22512, q_pin_count=5376, measured_unknown_bit_ticks=unknown,
             q_tx_positive=sum(p.get('TX', 0) > 0 for p in q), q_tx_full_window=sum(p.get('TX', 0) == w['duration_ticks'] for p in q),
             duration_ticks=w['duration_ticks'], timescale_seconds='1E-15'))
        bridge = load(oldroot / ('task_%02d/task-mapped-receipt.json' % i))
        need(bridge == task['mapped_macro_bridge_receipt'] and bridge['macro_count'] == 336 and bridge['mapped_pin_bit_count'] == 22512 and
             bridge['inventory'] == old['mapped_sram_inventory'] and bridge['output_saif'] == task['saif'], 'original own mapped SAIF receipt')
        text = (oldroot / ('task_%02d/power.tcl' % i)).read_text()
        forward = text.replace('set_propagated_clock [all_clocks]\nupdate_timing\n',
             'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource {' + refs['scope']['path'] + '}\nupdate_timing\n')
        need(forward != text and normal_clock(forward) == normal_clock(clock166.read_text()), 'actual166/common190 clock method exact identity')
    return dict(old=old, oldexec=execution, refs=refs, oldroot=oldroot, macros=macros, measured=measured,
         fm=fm, area=refs['area'], reference_index=ident(HERE / 'references205.json'), reference_files=len(files))


class Evidence:
    def __init__(self, root, archive, expected_sha):
        self.root = Path(root).absolute(); self.report, self.declared = safe171.inspect(archive, expected_sha)
        need(self.root.is_dir() and not self.root.is_symlink(), 'regular extracted root')
        actual = set()
        for p in self.root.rglob('*'):
            need(not p.is_symlink(), 'extracted symlink rejected')
            if p.is_file(): actual.add(str(p.relative_to(self.root)))
        need(actual in [set(self.declared) | {'manifest.json'}, set(self.declared) | {'manifest.json', 'checked171.json'}], 'exact extracted inventory')
        for name, row in self.declared.items(): need(same(ident(self.root / name), row), 'extracted byte hash differs: ' + name)
        with tarfile.open(str(archive), 'r:xz') as tar:
            need(tar.extractfile('manifest.json').read() == (self.root / 'manifest.json').read_bytes(), 'original archive manifest bytes')
        snapshot = self.json('snapshot171.json'); need(snapshot['schema'] == 'xu-two-candidate-snapshot171-v1' and snapshot['qualification'] == 'NOT_QUALIFIED', 'snapshot identity')
        self.copies = {}; self.omitted = {}
        for rows, table in [(snapshot['captures'], self.copies), (snapshot['omitted_originals'], self.omitted)]:
            for row in rows:
                n = safe171.safe_name(row['archive_path']); need(n not in self.copies and n not in self.omitted, 'duplicate snapshot member')
                table[n] = row
                if table is self.copies:
                    need(n in self.declared and same(self.declared[n], dict(bytes=row['bytes_observed'], sha256=row['observed_bytes_sha256'])), 'copied snapshot hash differs')

    def path(self, name):
        return self.root / safe171.safe_name(name)

    def json(self, name):
        return load(self.path(name))

    def check(self, name, receipt=None):
        omitted = name in self.omitted; table = self.omitted if omitted else self.copies
        need(name in table, 'snapshot source absent: ' + name); row = table[name]
        need(row['metadata_unchanged_during_read'] is True and row['fd_before'] == row['fd_after'] == row['path_after'] and
             row['bytes_observed'] == row['fd_before']['bytes'], 'unstable bounded snapshot: ' + name)
        if receipt is not None:
            need(receipt['path'] == row['source_path'] and same(receipt, dict(bytes=row['bytes_observed'], sha256=row['observed_bytes_sha256'])), 'receipt/source byte identity: ' + name)
        if omitted:
            reason = 'PIN_ORIGINAL_NEVER_PACKAGED' if Path(name).name in ['sram-pins-before.rpt', 'sram-pins-after.rpt'] else 'ABOVE_SMALL_FILE_LIMIT'
            need(row['omission_reason'] == reason and name not in self.declared, 'exact omission policy')
        return omitted


def native(ev, name, receipt, marker):
    need(not ev.check(name, receipt['log']), 'native log body must be returned')
    text = ev.path(name).read_text()
    need(receipt['returncode'] == 0 and not receipt.get('timed_out', False) and text.splitlines().count(marker) == 1 and
         'Version ' + PT in text and not any(BAD.search(x) for x in text.splitlines()), 'native rc/version/marker/errors: ' + name)


def power_values(text):
    need(re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'native fullSoC design')
    for unit in ['Dynamic', 'Leakage']:
        need(re.findall(r'^\s*' + unit + r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')], 'native explicit watts')
    output = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'), ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*' + label + r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        need(len(hits) == 1, 'one native power component: ' + key); value = D(hits[0])
        need(value.is_finite() and value >= 0, 'finite nonnegative native power'); output[key + '_power_w'] = str(value)
    return output


def context_check(context, refs):
    r = refs['refs']; old = refs['old']
    need(context['netlist'] == old['netlist'] and context['netlist']['sha256'] == NET and
         context['analysis_sdc'] == old['analysis_sdc'] and context['analysis_sdc']['sha256'] == SDC and
         context['clock_scope'] == r['scope'] and context['clock_scope']['sha256'] == SCOPE and
         context['source_context'] == old['source_context'] and context['original_configuration_sha256'] == old['original_capture_configuration_sha256'], 'same own source/map/method/capture')
    need(context['original_prepared'] == r['prepared57'] and context['original_execution'] == r['execution57'] and
         context['native_fm_state'] == r['fm_state'] and context['archived_original_fm_state'] == r['fm_state_original'] and
         context['native_fm_log'] == refs['fm']['log'] and context['passing_compare_points'] == 42338 and context['area_report'] == r['area'], 'original FM/area source receipt continuity')
    need(context['area'] == dict(accelerator_mm2='0.2948018380', full_soc_mm2='3.365797600429', accelerator_limit_mm2='2.25',
         below_area_limit=True, qualification='NOT_QUALIFIED'), 'same own9c16 area')


def campaign(ev, folder, ids, refs, preflight=None):
    status = TASK0 if ids == [0] else FULL12
    result = ev.json(folder + '/result.json')
    need(result['status'] == status and result['qualification'] == 'NOT_QUALIFIED', 'actual successful terminal required: ' + folder)
    names = ['prepared.json', 'execution.json', 'summary.json', 'result.json', 'output-manifest190.json']
    for name in names: need(not ev.check(folder + '/' + name), 'required campaign body omitted')
    m, e, s = [ev.json(folder + '/' + name) for name in names[:3]]
    need(m['schema'] == 'xu-common190-prepared-v1' and e['schema'] == 'xu-common190-execution-v1' and
         all(x['qualification'] == 'NOT_QUALIFIED' for x in [m, e, s]) and e['status'] == s['status'] == status,
         'terminal/schema/qualification')
    need(m['requested_task_ids'] == e['requested_task_ids'] == result['requested_task_ids'] == ids and
         [t['task_id'] for t in m['tasks']] == [t['task_id'] for t in e['tasks']] == ids and s['task_count'] == len(ids) and
         s['taskset_complete'] is (len(ids) == 12) and e['taskset_complete'] is (len(ids) == 12), 'exact task0/full12 identities')
    need(m['input_sha256'] == e['input_sha256_before'] == e['input_sha256_after'] == result['input_sha256_before'] == result['input_sha256_after'], 'recorded external frozen-input before/after')
    need(m['producer']['sha256'] == PRODUCER and m['producer']['path'] == RUNTIME + 'power190.py' and
         all(m['input_sha256'].get(p) == h for p, h in refs['old']['input_sha256'].items()), 'own frozen source inputs/producer')
    need(m['input_sha256'].get(RUNTIME + 'frozen-fm190.json') == FMSTATE and
         REMOTE + 'candidate-formality-campaign-20261103-01/state.json' not in m['input_sha256'], 'immutable snapshot; mutable live FM excluded')
    for row in load(REPO / 'build/xu-s2c-common-power190/manifest190.json')['runtime']:
        need(m['input_sha256'].get(RUNTIME + row['name']) == row['sha256'], 'complete runtime frozen-input receipt')
    for key in ['original_prepared', 'original_execution', 'native_fm_state', 'native_fm_log', 'area_report', 'clock_scope', 'netlist', 'analysis_sdc']:
        row = m['context'][key]
        need(m['input_sha256'].get(row['path']) == row['sha256'], 'context input freeze inclusion: ' + key)
    context_check(m['context'], refs); need(e['context'] == s['context'] == m['context'], 'same context across outputs')
    need(e['tasks'] == s['tasks'], 'same summary tasks')
    if 'tool' in e: need(e['tool'] == m['tool'], 'same execution tool')
    need(m['tool'] == refs['oldexec']['tool'], 'same native PT executable')
    ev.check(folder + '/prepared.json', e['prepared']); ev.check(folder + '/summary.json', e['summary']); ev.check(folder + '/summary.json', result['summary'])
    # Native raw336/22512 inventory, not a hand-authored count.
    inv = ev.json(folder + '/inventory/state.json'); ev.check(folder + '/inventory/state.json')
    need(inv['status'] == 'EXPORTED_COMMON190_NOT_QUALIFIED' and inv['qualification'] == 'NOT_QUALIFIED' and
         inv['context'] == m['context'] and inv['input_sha256_before'] == inv['input_sha256_after'] and
         all(m['input_sha256'].get(p) == h for p, h in inv['input_sha256_before'].items()), 'native inventory recorded context/freeze')
    native(ev, folder + '/inventory/pt.log', inv['execution'], inv['marker'])
    for name in ['export.tcl', 'macro-pins.tsv']: ev.check(folder + '/inventory/' + name)
    macros = raw_inventory(ev.path(folder + '/inventory/macro-pins.tsv').read_text()); need(macros == refs['macros'], 'new native inventory equals own original inventory')
    inventory_tcl = ev.path(folder + '/inventory/export.tcl').read_text()
    need('set_propagated_clock [all_clocks]' not in inventory_tcl and
         '{' + m['context']['clock_scope']['path'] + '}' in inventory_tcl and refs['old']['netlist']['path'] in inventory_tcl and inv['marker'] in inventory_tcl,
         'native inventory own map/scope/marker')
    macro_names = sorted(row['instance'] for row in macros); layers = []
    for task, run in zip(m['tasks'], e['tasks']):
        i = task['task_id']; old = refs['old']['tasks'][i]; prefix = folder + '/task_%02d/' % i
        need(task['directory'] == old['directory'] == 'task_%02d' % i and task['macro_names'] == old['macro_names'] == macro_names and
             task['activity_window'] == old['activity_window'] and task['measured_summary'] == refs['measured'][i], 'original12 windows/cycles/macros/unknown unchanged')
        need(task['original_task_saif'] == old['saif'] and same(task['saif'], old['saif']) and
             task['canonical_saif'] == old['canonical_saif'] and task['mapped_macro_bridge'] == old['mapped_macro_bridge'] and
             task['mapped_macro_bridge_receipt'] == old['mapped_macro_bridge_receipt'] and task['measured_sram_pin_states'] == old['measured_sram_pin_states'], 'exact original activity SHA/bridge/unknown continuity')
        need(all(m['input_sha256'].get(task[key]['path']) == task[key]['sha256'] for key in ['script', 'saif']), 'per-task script/SAIF frozen inclusion')
        ev.check(prefix + 'power.tcl', task['script'])
        original = (refs['oldroot'] / ('task_%02d/power.tcl' % i)).read_text()
        clock_old = 'set_propagated_clock [all_clocks]\nupdate_timing\n'
        clock_new = 'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource {' + m['context']['clock_scope']['path'] + '}\nupdate_timing\n'
        need(original.count(clock_old) == 1 and original.count('{' + old['saif']['path'] + '}') == 1 and original.count(old['completion_marker']) == 1, 'unique permitted original substitutions')
        expected = original.replace(clock_old, clock_new).replace('{' + old['saif']['path'] + '}', '{' + task['saif']['path'] + '}').replace(old['completion_marker'], task['completion_marker'])
        need(ev.path(prefix + 'power.tcl').read_text() == expected and 'set_propagated_clock [all_clocks]' not in expected, 'only clock scope/SAIF path/marker changed')
        need(run['task_id'] == i and run['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' and
             run['frozen_inputs_sha256'] == canonical(m['input_sha256']), 'native task frozen identity')
        native(ev, prefix + 'pt.log', run['execution'], task['completion_marker'])
        need(run['execution']['command'] == [m['tool']['path'], '-f', 'power.tcl'] and
             run['execution']['cwd'] == str(Path(task['script']['path']).parent), 'native exact tool/cwd')
        need(task['expected_reports'] == old['expected_reports'] and set(run['reports']) == set(task['expected_reports']) and len(run['reports']) == 27, 'all27 original reports retained')
        omitted = []
        for name, receipt in run['reports'].items():
            if ev.check(prefix + name, receipt): omitted.append(name)
            else:
                text = ev.path(prefix + name).read_text()
                need((name == 'inconsistent.rpt' or receipt['bytes'] > 0) and not any(BAD.search(line) for line in text.splitlines()), 'native report body/errors: ' + name)
        need(all(name in omitted for name in ['sram-pins-before.rpt', 'sram-pins-after.rpt']), 'large original pin bodies explicitly hash-only')
        need(PT in ev.path(prefix + 'tool-version.rpt').read_text(), 'native report tool version')
        pairs = re.findall(r'^XU_SRAM_POWER_CELL name=(.+) ref=(\S+)$', ev.path(prefix + 'sram-power.rpt').read_text(), re.M)
        need(len(pairs) == 336 and sorted(n for n, ref in pairs) == macro_names and all(ref == 'RAMSP1024X16' for n, ref in pairs), 'all336 native macro power identities')
        values = power_values(ev.path(prefix + 'power.rpt').read_text()); duration = D(6604373333334) * D('1e-15'); energy = D(values['total_power_w']) * duration
        diag = run['diagnostic']
        need(diag['qualification'] == 'NOT_QUALIFIED' and diag['report'] == run['reports']['power.rpt'] and diag['power_components'] == values and
             D(diag['duration_seconds']) == duration and D(diag['diagnostic_energy_j']) == energy and diag['measured_input_unknown_summary'] == refs['measured'][i], 'independent Decimal P*6604373333334fs energy')
        u = refs['measured'][i]
        layers.append(dict(layer=i, elapsed_cycles=990656, duration_fs=6604373333334, reported_total_power_w=values['total_power_w'], diagnostic_energy_j=str(energy),
             accelerator_area_mm2='0.2948018380', mapped_sha256=NET, unknown_q_bits=u['q_tx_positive'], all_window_unknown_q_bits=u['q_tx_full_window'],
             native_log_sha256=run['execution']['log']['sha256'], power_report_sha256=run['reports']['power.rpt']['sha256'],
             pin_before_server_bounded_sha256=run['reports']['sram-pins-before.rpt']['sha256'], pin_after_server_bounded_sha256=run['reports']['sram-pins-after.rpt']['sha256'],
             locally_rescanned_report_body_count=27 - len(omitted), server_bounded_hash_only_report_count=len(omitted), server_bounded_hash_only_report_names=';'.join(sorted(omitted)), qualification='NOT_QUALIFIED'))
    total = sum(D(r['diagnostic_energy_j']) for r in layers)
    need(D(s['sum_diagnostic_energy_j']) == total and s['total_elapsed_cycles'] == 990656 * len(ids), 'independent energy/cycle aggregates')
    if ids == [0]: need(m['preflight'] is None, 'task0 has no preflight')
    else:
        need(preflight is not None and preflight['complete'], 'full12 independent successful task0 required'); pf = m['preflight']
        need(pf['status'] == TASK0 and pf['root'] == REMOTE + ROOT0 and ev.json(ROOT0 + '/prepared.json')['context'] == m['context'], 'same-map/method successful task0 guard')
        for name in ['prepared', 'execution', 'summary', 'result']: ev.check(ROOT0 + '/' + name + '.json', pf[name])
    manifest = ev.json(folder + '/output-manifest190.json'); seen = set(); bodies = hashed = absent = 0
    need(manifest['schema'] == 'xu-common190-output-manifest-v1' and manifest['qualification'] == 'NOT_QUALIFIED', 'native output manifest schema')
    for row in manifest['files']:
        name = safe171.safe_name(row['relative']); need(name not in seen, 'unique native output manifest'); seen.add(name)
        qualified = folder + '/' + name
        if qualified in ev.copies or qualified in ev.omitted:
            is_hash = ev.check(qualified, dict(path=REMOTE + qualified, **{k: row[k] for k in ['bytes', 'sha256']}))
            if is_hash: hashed += 1
            else: bodies += 1
        else:
            need(Path(name).suffix == '.saif', 'unexpected absent output-manifest body: ' + name); absent += 1
            need(any(t['saif']['path'] == REMOTE + qualified and same(t['saif'], row) for t in m['tasks']), 'absent SAIF exact frozen identity')
    need(absent == len(ids) and all(n in seen for n in ['prepared.json', 'execution.json', 'summary.json', 'result.json', 'inventory/state.json', 'inventory/macro-pins.tsv', 'inventory/pt.log', 'inventory/export.tcl']), 'native output manifest required membership')
    return dict(status='AUDITED_NATIVE_TASK0_NOT_QUALIFIED' if ids == [0] else 'AUDITED_NATIVE_FULL12_NOT_QUALIFIED', complete=True, qualification='NOT_QUALIFIED',
         output=folder, source_status=status, layers=layers, total_elapsed_cycles=990656 * len(ids), sum_diagnostic_energy_j=str(total),
         recorded_input_sha_count=len(m['input_sha256']), recorded_input_guard='SERVER_BEFORE_AFTER_EQUAL_NOT_LOCAL_EXTERNAL_REHASH',
         native_inventory=dict(macro_count=336, pin_bit_count=22512), output_manifest=dict(local_body_count=bodies, server_bounded_hash_only_count=hashed, absent_saif_count=absent),
         target_mapped_sha256=NET, accelerator_area_mm2='0.2948018380')


def audit(ev, refs):
    zero = campaign(ev, ROOT0, [0], refs); full = campaign(ev, ROOT12, list(range(12)), refs, zero)
    return dict(schema='xu-s2c190-independent-audit205-v1', status='AUDITED_FULL12_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
         producer=ident(Path(__file__).resolve()), frozen_safe171=ident(HERE / 'safe171.py'), archive_check=ev.report,
         references=refs['reference_index'], locally_rehashed_reference_files=refs['reference_files'], task0=zero, full12=full,
         controlled_method=dict(sdc_sha256=SDC, scope_sha256=SCOPE, same166_forwarded_clock_method=True, all_clock_propagation_override=False,
             joint_comparison_status='READY_FOR_SEPARATE_INDEPENDENT_S2E166_JOIN_NOT_QUALIFIED'), limitations=LIMITS)


def joint_compare(result, c_ev, e_ev, e_audit_path):
    """Join actual166 through native171 bodies, preserving the old179 historical warning."""
    e_audit = load(e_audit_path); full = e_audit['full12']
    need(e_audit['schema'] == 'xu-s2e166-independent-audit179-v1' and e_audit['qualification'] == 'NOT_QUALIFIED' and
         e_audit['status'] == 'AUDITED_FULL12_DIAGNOSTIC_NOT_QUALIFIED' and full['complete'] is True and len(full['layers']) == 12 and
         e_audit['archive_check']['archive']['sha256'] == e_ev.report['archive']['sha256'], 'actual successful179 bound to actual171')
    folder = 's2e-final155-power12-20261105-166'; m = e_ev.json(folder + '/prepared.json'); x = e_ev.json(folder + '/execution.json')
    c_m = c_ev.json(ROOT12 + '/prepared.json')
    need(m['analysis_sdc']['sha256'] == SDC and m['clock_scope']['sha256'] == SCOPE and
         m['target_mapped_context']['area']['accelerator_mm2'] == '0.3003096339' and
         m['netlist']['sha256'] == full['target_mapped_sha256'] == '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794' and
         m['input_sha256'] == x['input_sha256_before'] == x['input_sha256_after'] and
         m['requested_task_ids'] == x['requested_task_ids'] == list(range(12)), 'actual same155 target/area/frozen12')
    rows = []; ce = ee = D(0); cc = ec = 0
    for c, e, task, run, ctask in zip(result['full12']['layers'], full['layers'], m['tasks'], x['tasks'], c_m['tasks']):
        i = c['layer']; prefix = folder + '/task_%02d/' % i
        need(e['layer'] == task['task_id'] == run['task_id'] == ctask['task_id'] == i and
             task['activity_window']['formal_elapsed_cycles'] == e['elapsed_cycles'] == 868343 and
             task['activity_window']['duration_ticks'] == e['duration_fs'] == 5788953333333, 'paired true task windows')
        native(e_ev, prefix + 'pt.log', run['execution'], task['completion_marker'])
        e_ev.check(prefix + 'power.rpt', run['reports']['power.rpt']); e_ev.check(prefix + 'power.tcl', task['script'])
        need(normal_clock(e_ev.path(prefix + 'power.tcl').read_text()) == normal_clock(c_ev.path(ROOT12 + '/task_%02d/power.tcl' % i).read_text()), 'actual twelve-pair clock contract')
        p = power_values(e_ev.path(prefix + 'power.rpt').read_text())['total_power_w']; energy = D(p) * D(5788953333333) * D('1e-15')
        need(D(e['reported_total_power_w']) == D(p) and D(e['diagnostic_energy_j']) == energy and
             e['power_report_sha256'] == run['reports']['power.rpt']['sha256'] and
             e['native_log_sha256'] == run['execution']['log']['sha256'] and e['mapped_sha256'] == m['netlist']['sha256'], '179 derivative/native171 crosscheck')
        cenergy = D(c['diagnostic_energy_j']); ce += cenergy; ee += energy; cc += c['elapsed_cycles']; ec += e['elapsed_cycles']
        rows.append(dict(layer=i, s2c_cycles=c['elapsed_cycles'], s2e_cycles=e['elapsed_cycles'], s2c_power_w=c['reported_total_power_w'], s2e_power_w=p,
             s2c_duration_fs=c['duration_fs'], s2e_duration_fs=e['duration_fs'], s2c_diagnostic_energy_j=str(cenergy), s2e_diagnostic_energy_j=str(energy),
             diagnostic_energy_reduction_percent=str((D(1) - energy / cenergy) * 100), s2c_area_mm2='0.2948018380', s2e_area_mm2='0.3003096339',
             s2c_mapped_sha256=NET, s2e_mapped_sha256=m['netlist']['sha256'], s2c_power_report_sha256=c['power_report_sha256'], s2e_power_report_sha256=e['power_report_sha256'],
             same_clock_method=True, qualification='NOT_QUALIFIED'))
    need(ce == D(result['full12']['sum_diagnostic_energy_j']) and ee == D(full['sum_diagnostic_energy_j']) and cc == 11887872 and ec == 10420116, 'independent paired totals')
    return dict(schema='xu-common-method-two-candidate-comparison205-v1', status='CONTROLLED_CLOCK_METHOD_DIAGNOSTIC_COMPARISON_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
         original179_audit=ident(e_audit_path), s2e_archive=e_ev.report['archive'], s2c_archive=c_ev.report['archive'], layers=rows,
         total=dict(s2c_elapsed_cycles=cc, s2e_elapsed_cycles=ec, cycle_reduction_percent=str((D(1) - D(ec) / D(cc)) * 100),
             throughput_increase_percent=str((D(cc) / D(ec) - D(1)) * 100), s2c_diagnostic_energy_j=str(ce), s2e_diagnostic_energy_j=str(ee),
             diagnostic_energy_reduction_percent=str((D(1) - ee / ce) * 100), s2c_accelerator_area_mm2='0.2948018380', s2e_accelerator_area_mm2='0.3003096339',
             accelerator_area_increase_percent=str((D('0.3003096339') / D('0.2948018380') - 1) * 100), accelerator_area_limit_mm2='2.25', both_below_area_limit=True),
         clock_method=dict(sdc_sha256=SDC, scope_sha256=SCOPE, all_clock_propagation_override=False, all_twelve_actual_tcl_contracts_match=True),
         historical179_unchanged=True, note='179 historical comparison to old57 retains its method-mismatch warning. This separate join uses new190 common scope and rechecks actual171 native power bodies; unknown/qualification gaps persist.', limitations=LIMITS)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--evidence-root', type=Path, required=True)
    p.add_argument('--archive', type=Path, required=True); p.add_argument('--sha256', required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--s2e-audit', type=Path); p.add_argument('--s2e-evidence-root', type=Path); p.add_argument('--s2e-archive', type=Path); p.add_argument('--s2e-sha256')
    a = p.parse_args(); out = a.out.absolute(); need(not out.exists() and not out.is_symlink(), 'fresh audit output required'); out.mkdir(parents=True)
    try:
        refs = reference_data(); ev = Evidence(a.evidence_root, a.archive, a.sha256); result = audit(ev, refs)
        extra = [a.s2e_audit, a.s2e_evidence_root, a.s2e_archive, a.s2e_sha256]
        need(not any(extra) or all(extra), 'all four S2e join arguments required together')
        if all(extra): result['joint_comparison'] = joint_compare(result, ev, Evidence(a.s2e_evidence_root, a.s2e_archive, a.s2e_sha256), a.s2e_audit)
        (out / 'audit205.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
        for name, rows in [('task0.csv', result['task0']['layers']), ('full12.csv', result['full12']['layers'])]:
            with (out / name).open('x', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        if 'joint_comparison' in result:
            rows = result['joint_comparison']['layers']
            with (out / 'comparison.csv').open('x', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        print(json.dumps(dict(status=result['status'], output=str(out), full12_energy_j=result['full12']['sum_diagnostic_energy_j'], qualification='NOT_QUALIFIED'), sort_keys=True))
    except BaseException as error:
        failure = dict(schema='xu-s2c190-independent-audit205-v1', status='FAILED_AUDIT_RETAINED_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
             error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc(), limitations=LIMITS)
        (out / 'audit205.json').write_text(json.dumps(failure, sort_keys=True, indent=2) + '\n'); raise


if __name__ == '__main__': main()
