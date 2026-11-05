#!/usr/bin/env python3
"""Read-only, standard-library verification of the portable S2e/S2c handoff.

Python 3.6+. No EDA, network, extracted build tree, or producer-code imports.
The result is always NOT_QUALIFIED: packaged bytes and diagnostic arithmetic
are checked; absent server inputs, SAIF and huge reports are receipt evidence.
"""
import argparse
import codecs
import csv
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
PT = 'T-2022.03-SP5-1'
CAPTURE_E = '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
ACCEL = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'
BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)
SHA = re.compile(r'[0-9a-f]{64}\Z')
CHUNK = 1024 * 1024
PACKETS = {
    'original171.tar.xz': (12919652, '2f46075e337a21608faf8dc4f4308e90a31c610e6dd5d1dec4a4fb7bb17ae515'),
    'original191.tar.xz': (13216384, '44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3'),
}
CONFIG = {
    's2e': dict(packet='original171.tar.xz', zero='s2e-final155-power-preflight-20261105-166',
                full='s2e-final155-power12-20261105-166', cycles=868343, fs=5788953333333,
                net='3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794',
                area='0.3003096339', total='3.373696204286',
                status0='EXECUTED_TASK0_DIAGNOSTIC_NOT_QUALIFIED', status12='EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'),
    's2c': dict(packet='original191.tar.xz', zero='s2c-common-scope-preflight-20261105-190',
                full='s2c-common-scope-power12-20261105-190', cycles=990656, fs=6604373333334,
                net='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892',
                area='0.2948018380', total='3.365797600429',
                status0='EXECUTED_TASK0_COMMON190_DIAGNOSTIC_NOT_QUALIFIED', status12='EXECUTED_12_COMMON190_DIAGNOSTIC_NOT_QUALIFIED'),
}
LIMITATIONS = [
    'NOT_QUALIFIED: diagnostic task energy; no final contest energy or score.',
    'Copied report bodies are locally hashed and scanned; omitted huge reports have bounded server hashes only.',
    'Absent RTL, netlists, libraries, SVF and SAIF have server before/after or bridge receipts, not local body rehashes.',
    '5280 Q bits have unknown time; 4256 remain unknown throughout each window. x_probability=0 does not prove physically known Q.',
    'Gate functionality, full 150MHz coverage, SRAM conditional/internal power and physical clock power remain unqualified.',
    'CPU pretask clear is outside the measured task windows; its energy is excluded.',
]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def safe_name(name):
    need(isinstance(name, str) and name and '\0' not in name and '\\' not in name, 'invalid member name')
    p = PurePosixPath(name)
    need(not p.is_absolute() and str(p) == name and not {'.', '..', '.git', '__pycache__', 'private-manuals', 'private-docs'} & set(p.parts), 'unsafe member: ' + name)
    return name


def unique_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, 'duplicate JSON key: ' + key)
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: need(False, 'nonfinite JSON: ' + value))


def identity(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'regular non-symlink file required: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            h.update(block)
    return dict(bytes=path.stat().st_size, sha256=h.hexdigest())


def same(a, b):
    return all(a.get(key) == b.get(key) for key in ['bytes', 'sha256'])


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


class Packet:
    """Validate every archive byte; retain only small bodies needed for review."""
    def __init__(self, path, expected=None):
        self.path = Path(path)
        self.identity = identity(path)
        if expected is not None:
            need(same(self.identity, expected), 'archive SHA/length differs: ' + str(path))
        self.files = {}; self.bodies = {}; self.report_errors = set(); total = 0
        with tarfile.open(str(path), 'r:xz') as archive:
            for member in archive:
                name = safe_name(member.name)
                need(member.isfile() and not member.issym() and not member.islnk() and not member.sparse,
                     'only regular nonsparse archive files allowed')
                need(name not in self.files and 0 <= member.size <= 512 * CHUNK, 'duplicate/oversized archive member')
                need(len(self.files) < 5000 and total + member.size <= 2 * 1024 * CHUNK, 'archive resource limit')
                keep = name.endswith(('.json', '.tcl', '.tsv', '/pt.log', '/power.rpt', '/sram-power.rpt', '/tool-version.rpt', '/version.rpt'))
                chunks = []; h = hashlib.sha256(); size = 0; pending = ''
                decoder = codecs.getincrementaldecoder('utf-8')('strict') if name.endswith('.rpt') else None
                stream = archive.extractfile(member)
                need(stream is not None, 'missing archive body')
                for block in iter(lambda: stream.read(CHUNK), b''):
                    size += len(block); h.update(block)
                    if keep:
                        chunks.append(block)
                    if decoder:
                        lines = (pending + decoder.decode(block)).split('\n'); pending = lines.pop()
                        if any(BAD.search(line) for line in lines):
                            self.report_errors.add(name)
                if decoder and BAD.search(pending + decoder.decode(b'', final=True)):
                    self.report_errors.add(name)
                need(size == member.size, 'truncated member')
                self.files[name] = dict(path=name, bytes=size, sha256=h.hexdigest()); total += size
                if keep:
                    self.bodies[name] = b''.join(chunks)
                    if name.endswith('.json'):
                        unique_json(self.bodies[name])
        need('manifest.json' in self.files, 'manifest missing')
        manifest = self.json('manifest.json')
        need(manifest.get('schema') == 'xu-two-candidate-export171-v1' and manifest.get('qualification') == 'NOT_QUALIFIED', 'archive manifest schema/qualification')
        declared = {}
        for row in manifest['files']:
            need(isinstance(row, dict) and set(row) == {'path', 'bytes', 'sha256'}, 'manifest identity shape')
            name = safe_name(row['path'])
            need(name != 'manifest.json' and name not in declared and type(row['bytes']) is int and row['bytes'] >= 0 and
                 isinstance(row['sha256'], str) and SHA.fullmatch(row['sha256']), 'invalid/duplicate manifest entry')
            declared[name] = row
        actual = dict(self.files); actual.pop('manifest.json')
        need(actual == declared, 'manifest member set/length/SHA differs')
        need(manifest['payload_files'] == len(actual) and manifest['payload_bytes'] == total - self.files['manifest.json']['bytes'], 'manifest totals differ')
        for name in actual:
            need(not any(str(parent) in self.files for parent in PurePosixPath(name).parents), 'file/directory prefix collision')
        need(identity(path) == self.identity, 'archive changed during verification')
        snapshot = self.json('snapshot171.json')
        need(snapshot['schema'] == 'xu-two-candidate-snapshot171-v1' and snapshot['qualification'] == 'NOT_QUALIFIED', 'snapshot schema/qualification')
        self.copies = {}; self.omitted = {}
        for rows, table in [(snapshot['captures'], self.copies), (snapshot['omitted_originals'], self.omitted)]:
            for row in rows:
                name = safe_name(row['archive_path'])
                need(name not in self.copies and name not in self.omitted, 'duplicate snapshot member')
                table[name] = row
                if table is self.copies:
                    need(name in self.files and same(self.files[name], dict(bytes=row['bytes_observed'], sha256=row['observed_bytes_sha256'])), 'snapshot copied hash differs')
        self.payload_files = len(actual); self.payload_bytes = manifest['payload_bytes']

    def json(self, name):
        need(name in self.bodies, 'required JSON body absent: ' + name)
        return unique_json(self.bodies[name])

    def text(self, name):
        need(name in self.bodies, 'required text body absent: ' + name)
        return self.bodies[name].decode('utf-8')

    def check(self, name, receipt=None):
        omitted = name in self.omitted
        table = self.omitted if omitted else self.copies
        need(name in table, 'source snapshot absent: ' + name)
        row = table[name]
        need(row['metadata_unchanged_during_read'] is True and row['fd_before'] == row['fd_after'] == row['path_after'] and
             row['bytes_observed'] == row['fd_before']['bytes'], 'unstable server bounded snapshot: ' + name)
        if receipt is not None:
            need(receipt['path'] == row['source_path'] and same(receipt, dict(bytes=row['bytes_observed'], sha256=row['observed_bytes_sha256'])), 'source receipt identity differs: ' + name)
        if omitted:
            reason = 'PIN_ORIGINAL_NEVER_PACKAGED' if PurePosixPath(name).name in ['sram-pins-before.rpt', 'sram-pins-after.rpt'] else 'ABOVE_SMALL_FILE_LIMIT'
            need(name not in self.files and row['omission_reason'] == reason, 'omission policy differs')
        return omitted


def native(packet, name, execution, marker):
    need(not packet.check(name, execution['log']), 'native log must have local body')
    text = packet.text(name)
    need(execution['returncode'] == 0 and not execution.get('timed_out', False) and
         text.splitlines().count(marker) == 1 and 'Version ' + PT in text and
         not any(BAD.search(line) for line in text.splitlines()), 'native rc/version/unique marker/errors: ' + name)
    # S2e's runner prefixes JSON; original common190 logs begin with native PT.
    if name.startswith('s2e-'):
        first = unique_json(text.splitlines()[0].encode('utf-8'))
        need(all(first[k] == execution[k] for k in ['command', 'cwd', 'started_utc']), 'native log execution header')


def power_values(text):
    need(re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'native fullSoC power design')
    for unit in ['Dynamic', 'Leakage']:
        need(re.findall(r'^\s*' + unit + r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')], 'explicit native watts required')
    values = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'), ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*' + label + r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        need(len(hits) == 1, 'unique native power component: ' + key)
        value = D(hits[0]); need(value.is_finite() and value >= 0, 'finite nonnegative native power')
        values[key + '_power_w'] = str(value)
    return values


def clock_contract(text):
    need('set_propagated_clock [all_clocks]' not in text, 'all-clock propagation override prohibited')
    begin = 'set XU_CLOCK_MODE envelope\n'; end = '# Exact post-elaboration macro groups;'
    need(text.count(begin) == 1 and text.count(end) == 1, 'unique actual Tcl clock contract')
    section = text[text.index(begin):text.index(end)]
    need('set XU_PLL_DIV 0\n' in section and 'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n' in section and
         all(token in section for token in ['xu_hfextclk 6.666666667', 'xu_lfextclk 30517.578125', 'xu_jtag_tck 100.0', 'xu_plldiv_envelope']), 'actual Tcl primary/forward clock guards')
    return re.sub(r'(?m)^source \{[^\n]+/constraints\.sdc\}$', 'source {SAME404c7d_SDC}', section)


def context(prepared, candidate):
    c = CONFIG[candidate]
    target = prepared['target_mapped_context'] if candidate == 's2e' else prepared['context']
    net = prepared['netlist'] if candidate == 's2e' else target['netlist']
    sdc = prepared['analysis_sdc'] if candidate == 's2e' else target['analysis_sdc']
    scope = prepared['clock_scope'] if candidate == 's2e' else target['clock_scope']
    need(net['sha256'] == c['net'] and target['netlist'] == net and sdc['sha256'] == SDC and scope['sha256'] == SCOPE,
         candidate + ' own mapped target/SDC/scope differs')
    need(target['area']['accelerator_mm2'] == c['area'] and target['area']['full_soc_mm2'] == c['total'] and
         target['area']['accelerator_limit_mm2'] == '2.25' and target['area']['below_area_limit'] is True and
         target['area']['qualification'] == 'NOT_QUALIFIED', candidate + ' own target/area binding differs')
    if candidate == 's2e':
        need(prepared['capture_mapped_context']['netlist']['sha256'] == CAPTURE_E and
             target['capture_mapped_context'] == prepared['capture_mapped_context'] and net['sha256'] != CAPTURE_E,
             'S2e capture and measurement targets must remain separate')
        need(target['constraints'] == sdc and target['clock_scope'] == scope and target['qualification'] == 'NOT_QUALIFIED', 'S2e target method')
    for receipt in [net, sdc, scope]:
        need(prepared['input_sha256'].get(receipt['path']) == receipt['sha256'], 'target/method frozen input inclusion')
    return target, net, sdc, scope


def inventory(packet, folder, prepared, candidate):
    base = folder + '/inventory/'
    if candidate == 's2e':
        inv = packet.json(base + 'inventory.json'); provenance = inv['provenance']
        packet.check(base + 'inventory.json', prepared['mapped_sram_inventory'])
        native(packet, base + 'pt.log', provenance['execution'], provenance['marker'])
        before, after = provenance['input_sha256_before'], provenance['input_sha256_after']
        need(inv['netlist'] == prepared['netlist'] and inv['constraints'] == prepared['analysis_sdc'], 'inventory target/method')
    else:
        inv = packet.json(base + 'state.json'); packet.check(base + 'state.json')
        native(packet, base + 'pt.log', inv['execution'], inv['marker'])
        before, after = inv['input_sha256_before'], inv['input_sha256_after']
        need(inv['context'] == prepared['context'], 'inventory target context')
    need(before == after and all(prepared['input_sha256'].get(p) == h for p, h in before.items()), 'inventory before/after frozen receipts')
    for name in ['macro-pins.tsv', 'export.tcl']:
        packet.check(base + name)
    text = packet.text(base + 'export.tcl'); target, net, sdc, scope = context(prepared, candidate)
    need(net['path'] in text and scope['path'] in text and 'set_propagated_clock [all_clocks]' not in text, 'inventory Tcl target/method')
    lines = packet.text(base + 'macro-pins.tsv').splitlines()
    need(lines[0] == 'kind\tcell\tref_or_pin\tlibcell_or_direction', 'native raw inventory header')
    widths = dict(CLK=1, CEN=1, WEN=16, A=10, D=16, EMA=3, EMAW=2, GWEN=1, RET1N=1, Q=16)
    pins = {k if w == 1 else '%s[%d]' % (k, bit) for k, w in widths.items() for bit in range(w)}
    macros = {}; allpins = set()
    for line in lines[1:]:
        fields = line.split('\t'); need(len(fields) == 4, 'native inventory row shape')
        kind, cell, value, extra = fields
        if kind == 'MACRO':
            need(cell not in macros and value == 'RAMSP1024X16' and extra == 'RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16', 'native unique macro/library')
            macros[cell] = set()
        else:
            need(kind == 'PIN' and cell in macros and value.startswith(cell + '/'), 'native pin owner')
            pin = value[len(cell) + 1:]
            need(pin in pins and value not in allpins and extra == ('out' if pin.startswith('Q[') else 'in'), 'native unique pin geometry/direction')
            macros[cell].add(pin); allpins.add(value)
    need(len(macros) == 336 and len(allpins) == 22512 and all(ps == pins for ps in macros.values()), 'complete native336/22512 inventory')
    return sorted(macros)


def campaign(packet, candidate, ids, preflight=None):
    c = CONFIG[candidate]; folder = c['zero'] if ids == [0] else c['full']; status = c['status0'] if ids == [0] else c['status12']
    m, e, s, r = [packet.json(folder + '/' + n + '.json') for n in ['prepared', 'execution', 'summary', 'result']]
    for name in ['prepared', 'execution', 'summary', 'result']:
        need(not packet.check(folder + '/' + name + '.json'), 'campaign body required')
    need(all(x['qualification'] == 'NOT_QUALIFIED' for x in [m, e, s, r]) and all(x['status'] == status for x in [e, s, r]), 'successful diagnostic terminal required')
    need(m['requested_task_ids'] == e['requested_task_ids'] == r['requested_task_ids'] == ids and
         [t['task_id'] for t in m['tasks']] == [t['task_id'] for t in e['tasks']] == ids and
         s['task_count'] == len(ids) and e['taskset_complete'] is (len(ids) == 12) and s['taskset_complete'] is (len(ids) == 12), 'exact task0/full12 layer IDs')
    frozen = m['input_sha256']
    need(frozen == e['input_sha256_before'] == e['input_sha256_after'] == r['input_sha256_before'] == r['input_sha256_after'], 'recorded input before/after differs')
    need(all(isinstance(p, str) and isinstance(h, str) and SHA.fullmatch(h) for p, h in frozen.items()), 'invalid input SHA receipt')
    need(e['tasks'] == s['tasks'], 'summary native task continuity')
    target, net, sdc, scope = context(m, candidate)
    if candidate == 's2e':
        need(e['target_context'] == target and s['target_netlist'] == net and s['area'] == target['area'], 'same measurement target')
    else:
        need(e['context'] == s['context'] == target, 'same measurement target')
    for key, file in [('prepared', 'prepared.json'), ('summary', 'summary.json')]:
        packet.check(folder + '/' + file, e[key])
    packet.check(folder + '/summary.json', r['summary'])
    macros = inventory(packet, folder, m, candidate); rows = []; contracts = []
    tool = m['pt'] if candidate == 's2e' else m['tool']
    for task, run in zip(m['tasks'], e['tasks']):
        i = task['task_id']; prefix = folder + '/task_%02d/' % i; w = task['activity_window']
        need(task['directory'] == 'task_%02d' % i and task['macro_names'] == macros, 'native task macro inventory')
        need(w['formal_elapsed_cycles'] == c['cycles'] and w['duration_ticks'] == c['fs'] and w['timescale_seconds'] == 1e-15 and
             w['end']['tick'] - w['begin']['tick'] == c['fs'] and w['end']['cycle'] - w['begin']['cycle'] == c['cycles'], 'actual fs window/cycles')
        packet.check(prefix + 'power.tcl', task['script']); text = packet.text(prefix + 'power.tcl')
        need(net['path'] in text and sdc['path'] in text and scope['path'] in text and
             task['completion_marker'] in text and task['saif']['path'] in text and
             'set_app_var power_analysis_mode averaged' in text and 'tb_xu_soc_ppa/dut' in text, 'actual Tcl target/activity/method')
        contracts.append(clock_contract(text))
        need(all(frozen.get(task[key]['path']) == task[key]['sha256'] for key in ['script', 'saif']), 'task frozen script/SAIF receipt')
        need(prefix + 'task-mapped.saif' not in packet.files, 'SAIF absence accounting differs')
        bridge = task['mapped_macro_bridge_receipt']
        need(same(bridge['output_saif'], task['saif']) and bridge['input_saif'] == task['canonical_saif'] and
             bridge['macro_count'] == 336 and bridge['mapped_pin_bit_count'] == 22512, 'SAIF bridge receipt continuity')
        if candidate == 's2e':
            packet.check(prefix + 'task-mapped-receipt.json', task['mapped_macro_bridge'])
            need(packet.json(prefix + 'task-mapped-receipt.json') == bridge, 'local SAIF bridge receipt body')
        else:
            need(same(task['original_task_saif'], task['saif']), 'S2c original SAIF receipt continuity')
        need(run['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' and run['frozen_inputs_sha256'] == canonical(frozen), 'native task input identity')
        native(packet, prefix + 'pt.log', run['execution'], task['completion_marker'])
        need(run['execution']['command'] == [tool['path'], '-f', 'power.tcl'] and
             run['execution']['cwd'] == str(PurePosixPath(task['script']['path']).parent), 'native command/cwd')
        need(len(task['expected_reports']) == 27 and len(set(task['expected_reports'])) == 27 and set(run['reports']) == set(task['expected_reports']), 'complete27 native reports')
        omitted = []
        for name, receipt in run['reports'].items():
            if packet.check(prefix + name, receipt):
                omitted.append(name)
            else:
                need(prefix + name not in packet.report_errors and (name == 'inconsistent.rpt' or receipt['bytes'] > 0), 'native report body error/empty: ' + name)
        need(len(omitted) == 6 and all(n in omitted for n in ['sram-pins-before.rpt', 'sram-pins-after.rpt']), 'explicit six hash-only reports')
        need(PT in packet.text(prefix + 'tool-version.rpt'), 'native report version')
        pairs = re.findall(r'^XU_SRAM_POWER_CELL name=(.+) ref=(\S+)$', packet.text(prefix + 'sram-power.rpt'), re.M)
        need(len(pairs) == 336 and sorted(n for n, ref in pairs) == macros and all(ref == 'RAMSP1024X16' for n, ref in pairs), 'native336 macro power identities')
        values = power_values(packet.text(prefix + 'power.rpt')); duration = D(c['fs']) * D('1e-15'); energy = D(values['total_power_w']) * duration
        diag = run['diagnostic']; u = task['measured_summary']
        need(u['pin_count'] == 22512 and u['q_pin_count'] == 5376 and u['q_tx_positive'] == 5280 and u['q_tx_full_window'] == 4256, 'unknown Q evidence retained')
        need(diag['qualification'] == 'NOT_QUALIFIED' and diag['report'] == run['reports']['power.rpt'] and diag['power_components'] == values and
             D(diag['duration_seconds']) == duration and D(diag['diagnostic_energy_j']) == energy and diag['measured_input_unknown_summary'] == u, 'independent native W times actual fs energy')
        rows.append(dict(layer=i, elapsed_cycles=c['cycles'], duration_fs=c['fs'], reported_total_power_w=values['total_power_w'],
                         diagnostic_energy_j=str(energy), accelerator_area_mm2=c['area'], mapped_sha256=c['net'],
                         unknown_q_bits=5280, all_window_unknown_q_bits=4256, native_log_sha256=run['execution']['log']['sha256'],
                         power_report_sha256=run['reports']['power.rpt']['sha256'],
                         pin_before_server_bounded_sha256=run['reports']['sram-pins-before.rpt']['sha256'],
                         pin_after_server_bounded_sha256=run['reports']['sram-pins-after.rpt']['sha256'],
                         locally_rescanned_report_body_count=27-len(omitted), server_bounded_hash_only_report_count=len(omitted),
                         server_bounded_hash_only_report_names=';'.join(sorted(omitted)), qualification='NOT_QUALIFIED'))
    total = sum(D(row['diagnostic_energy_j']) for row in rows)
    need(D(s['sum_diagnostic_energy_j']) == total and s['total_elapsed_cycles'] == c['cycles'] * len(ids), 'independent cycle/energy totals')
    if ids == [0]:
        need(m['preflight'] is None, 'task0 must be independent preflight')
    else:
        need(preflight is not None and m['preflight']['status'] == c['status0'] and PurePosixPath(m['preflight']['root']).name == c['zero'], 'successful independent task0 guard')
        old = packet.json(c['zero'] + '/prepared.json')
        need(context(old, candidate) == (target, net, sdc, scope), 'task0/full12 same target/method')
        for key in ['prepared', 'execution', 'summary', 'result']:
            packet.check(c['zero'] + '/' + key + '.json', m['preflight'][key])
        need(old['tasks'][0]['activity_window'] == m['tasks'][0]['activity_window'], 'task0/full12 same captured window')
    return dict(layers=rows, cycles=c['cycles'] * len(ids), diagnostic_energy_j=str(total),
                recorded_input_count=len(frozen), report_bodies_rescanned=21*len(ids), server_hash_only_reports=6*len(ids),
                absent_saif_bodies=len(ids)), contracts, m


class References:
    def __init__(self, root):
        root = Path(root)
        need(root.is_dir() and not root.is_symlink(), 'preserved reference directory required')
        self.files = {}
        for path in root.rglob('*'):
            need(not path.is_symlink(), 'reference symlink rejected')
            if path.is_file():
                row = identity(path); self.files.setdefault(row['sha256'], []).append((path, row))

    def body(self, receipt):
        rows = self.files.get(receipt['sha256'], [])
        need(rows and all(same(row, receipt) for path, row in rows), 'preserved native reference SHA/length absent: ' + receipt.get('path', ''))
        raw = rows[0][0].read_bytes()
        need(len(raw) == receipt['bytes'] and hashlib.sha256(raw).hexdigest() == receipt['sha256'], 'native reference changed during read')
        return raw

    def json(self, receipt):
        return unique_json(self.body(receipt))


def native_references(refs, prepared, candidate):
    c = CONFIG[candidate]; target, net, sdc, scope = context(prepared, candidate)
    if candidate == 's2e':
        state = refs.json(target['state']); fm = state['runs'][-1]
        need(state['qualification'] == 'NOT_QUALIFIED' and state['formal_passing'] == 42338 and
             state['frozen_before'] == state['frozen_after'] and state['frozen_input_errors'] == [] and
             state['final_outputs'][net['path']] == net and fm['tool'] == 'fm' and fm['returncode'] == 0 and
             fm['log'] == target['fm_log'] and state['svf_chain'] == target['svf_chain'], 'S2e155 native frozen state/map/FM binding')
        area_receipt = target['area_report']; log_receipt = target['fm_log']; marker = 'XU_S2E_TIMING134_FORMALITY_PASS'
        need(any(same(row, area_receipt) for row in state['reports'].values()), 'S2e155 native area state binding')
    else:
        state = refs.json(target['native_fm_state'])
        need(same(target['native_fm_state'], target['archived_original_fm_state']), 'S2c original frozen FM snapshot identity')
        runs = [r for r in state['runs'] if r['candidate'] == 's2c']; need(len(runs) == 1, 'unique own S2c FM run')
        fm = runs[0]
        need(fm['status'] == 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' and fm['returncode'] == 0 and fm['frozen_before'] == fm['frozen_after'] and
             any(row['sha256'] == c['net'] for row in fm['frozen_before'].values()) and fm['log'] == target['native_fm_log'], 'own S2c FM target/freeze/rc')
        ppa = refs.json(fm['ppa_execution']); area_receipt = target['area_report']; log_receipt = fm['log']; marker = 'XU_FULL_SOC_FORMALITY_PASS'
        need(ppa['netlist_sha256'] == c['net'] and ppa['analysis_sdc_sha256'] == SDC and
             ppa['dc']['returncode'] == ppa['pt']['returncode'] == 0 and same(ppa['reports']['area.rpt'], area_receipt), 'own S2c native PPA area/map binding')
    text = refs.body(log_receipt).decode('utf-8')
    need('Version R-2020.09-SP5' in text and text.splitlines().count(marker) == 1 and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)\s*$', text, re.M) == ['Verification SUCCEEDED'] and
         re.findall(r'^\s*(\d+) Passing compare points\s*$', text, re.M) == ['42338'] and
         not any(BAD.search(line) for line in text.splitlines()), 'native own42338 FM version/unique completion/errors')
    text = refs.body(area_receipt).decode('utf-8')
    need('Version: T-2022.03-SP5-5' in text and re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'native area version/design')
    accel = re.findall(r'^' + re.escape(ACCEL) + r'\n\s*([0-9.]+)[^\n]*accel_icb_slave\s*$', text, re.M)
    total = re.findall(r'^Total cell area:\s*([0-9.]+)\s*$', text, re.M)
    need(len(accel) == len(total) == 1 and D(accel[0]) / D(1000000) == D(c['area']) and
         D(total[0]) / D(1000000) == D(c['total']), 'native own-map accelerator/fullSoC area conversion')
    return dict(mapped_sha256=c['net'], accelerator_mm2=c['area'], full_soc_mm2=c['total'],
                native_formality_passing_compare_points=42338, qualification='NOT_QUALIFIED')


def check_csv(path, expected):
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        need(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), 'duplicate CSV columns')
        rows = list(reader)
    need(len(rows) == len(expected), 'CSV layer count differs: ' + str(path))
    for row, wanted in zip(rows, expected):
        need(row == {k: str(v) for k, v in wanted.items()}, 'CSV/native or audit rows differ: ' + str(path))


def compare_rows(c_rows, e_rows):
    rows = []
    for c, e in zip(c_rows, e_rows):
        ce, ee = D(c['diagnostic_energy_j']), D(e['diagnostic_energy_j'])
        rows.append(dict(layer=c['layer'], s2c_cycles=c['elapsed_cycles'], s2e_cycles=e['elapsed_cycles'],
                         s2c_power_w=c['reported_total_power_w'], s2e_power_w=e['reported_total_power_w'],
                         s2c_duration_fs=c['duration_fs'], s2e_duration_fs=e['duration_fs'],
                         s2c_diagnostic_energy_j=str(ce), s2e_diagnostic_energy_j=str(ee),
                         diagnostic_energy_reduction_percent=str((D(1)-ee/ce)*100),
                         s2c_area_mm2=c['accelerator_area_mm2'], s2e_area_mm2=e['accelerator_area_mm2'],
                         s2c_mapped_sha256=c['mapped_sha256'], s2e_mapped_sha256=e['mapped_sha256'],
                         s2c_power_report_sha256=c['power_report_sha256'], s2e_power_report_sha256=e['power_report_sha256'],
                         same_clock_method=True, qualification='NOT_QUALIFIED'))
    return rows


def verify(evidence_root, references_root):
    root = Path(evidence_root); refs = References(references_root); results = {}; packets = {}; manifests = {}; csv_hashes = {}
    index = unique_json((root / 'original-packets.json').read_bytes())
    need(index['schema'] == 'xu-two-candidate-final-packets-v1' and index['qualification'] == 'NOT_QUALIFIED' and
         set(index['packets']) == set(PACKETS), 'official original packet index')
    for candidate in ['s2e', 's2c']:
        c = CONFIG[candidate]; size, sha = PACKETS[c['packet']]; expected = dict(bytes=size, sha256=sha)
        need(index['packets'][c['packet']] == expected, 'official packet identity differs')
        packet = Packet(root / c['packet'], expected); packets[candidate] = packet
        zero, _, _ = campaign(packet, candidate, [0])
        full, clocks, prepared = campaign(packet, candidate, list(range(12)), zero)
        native = native_references(refs, prepared, candidate)
        results[candidate] = dict(task0=zero, full12=full, native_reference=native)
        manifests[candidate] = clocks
        auditname = 's2e-audit179.json' if candidate == 's2e' else 's2c-audit205.json'
        audit = unique_json((root / auditname).read_bytes())
        need(audit['status'] == 'AUDITED_FULL12_DIAGNOSTIC_NOT_QUALIFIED' and audit['qualification'] == 'NOT_QUALIFIED' and
             same(audit['archive_check']['archive'], packet.identity), 'retained audit packet binding')
        for phase, computed in [('task0', zero), ('full12', full)]:
            recorded = audit[phase]
            need(recorded['complete'] is True and recorded['layers'] == computed['layers'] and
                 recorded['total_elapsed_cycles'] == computed['cycles'] and D(recorded['sum_diagnostic_energy_j']) == D(computed['diagnostic_energy_j']) and
                 recorded['target_mapped_sha256'] == c['net'] and D(recorded['accelerator_area_mm2']) == D(c['area']), 'retained audit/native arithmetic differs')
            filename = candidate + '-' + phase + '.csv'; check_csv(root / filename, computed['layers']); csv_hashes[filename] = identity(root / filename)
        results[candidate]['retained_audit_sha256'] = identity(root / auditname)['sha256']
        if candidate == 's2e':
            need(audit['comparison']['analysis_method_mismatch'] is True and audit['comparison']['diagnostic_energy_reduction_vs_s2c_percent'] is None,
                 'historical179 method warning retained')
            check_csv(root / 's2e-comparison.csv', audit['paired_layers']); csv_hashes['s2e-comparison.csv'] = identity(root / 's2e-comparison.csv')
        else:
            comparison = audit['joint_comparison']
    need(len(manifests['s2e']) == len(manifests['s2c']) == 12 and manifests['s2e'] == manifests['s2c'], 'all12 actual paired Tcl clock methods must match')
    rows = compare_rows(results['s2c']['full12']['layers'], results['s2e']['full12']['layers'])
    need(comparison['layers'] == rows and comparison['qualification'] == 'NOT_QUALIFIED' and
         comparison['clock_method'] == dict(sdc_sha256=SDC, scope_sha256=SCOPE, all_clock_propagation_override=False, all_twelve_actual_tcl_contracts_match=True), 'joint205 actual native join differs')
    check_csv(root / 's2c-comparison.csv', rows); csv_hashes['s2c-comparison.csv'] = identity(root / 's2c-comparison.csv')
    c, e = results['s2c']['full12'], results['s2e']['full12']; ce, ee = D(c['diagnostic_energy_j']), D(e['diagnostic_energy_j'])
    totals = dict(s2c_elapsed_cycles=c['cycles'], s2e_elapsed_cycles=e['cycles'],
                  cycle_reduction_percent=str((D(1)-D(e['cycles'])/D(c['cycles']))*100),
                  throughput_increase_percent=str((D(c['cycles'])/D(e['cycles'])-1)*100),
                  s2c_diagnostic_energy_j=str(ce), s2e_diagnostic_energy_j=str(ee),
                  diagnostic_energy_reduction_percent=str((D(1)-ee/ce)*100),
                  s2c_accelerator_area_mm2=CONFIG['s2c']['area'], s2e_accelerator_area_mm2=CONFIG['s2e']['area'],
                  accelerator_area_increase_percent=str((D(CONFIG['s2e']['area'])/D(CONFIG['s2c']['area'])-1)*100),
                  accelerator_area_limit_mm2='2.25', both_below_area_limit=True)
    need(comparison['total'] == totals and same(comparison['s2e_archive'], packets['s2e'].identity) and
         same(comparison['s2c_archive'], packets['s2c'].identity) and
         same(comparison['original179_audit'], identity(root / 's2e-audit179.json')), 'joint205 totals/archive/original179 binding')
    return dict(schema='xu-portable-handoff-verification-v1', status='VERIFIED_PACKAGED_DIAGNOSTIC_EVIDENCE_NOT_QUALIFIED',
                qualification='NOT_QUALIFIED', candidates=results, comparison=totals,
                archives={k: dict(identity=v.identity, payload_files=v.payload_files, payload_bytes=v.payload_bytes) for k, v in packets.items()},
                csv_identities=csv_hashes, all_twelve_actual_clock_contracts_match=True, limitations=LIMITATIONS)


def main(argv=None):
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, default=repo / 'docs/validation/xu-score-two-candidate-final-20261105')
    parser.add_argument('--references-root', type=Path, default=repo / 'docs/handoff-evidence')
    parser.add_argument('--out', type=Path, help='Optional fresh JSON report file; no writes by default')
    parser.add_argument('--json', action='store_true', help='Print full JSON report instead of compact result')
    args = parser.parse_args(argv)
    try:
        if args.out is not None:
            need(not args.out.exists() and not args.out.is_symlink(), '--out must be a fresh file')
        report = verify(args.evidence_root, args.references_root)
        if args.out is not None:
            with args.out.open('x') as stream:
                stream.write(json.dumps(report, sort_keys=True, indent=2) + '\n')
        output = report if args.json else dict(status=report['status'], qualification='NOT_QUALIFIED',
                                               comparison=report['comparison'], limitations=report['limitations'])
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, tarfile.TarError) as error:
        print(json.dumps(dict(status='FAILED_VERIFICATION_NOT_QUALIFIED', qualification='NOT_QUALIFIED', error=str(error)), sort_keys=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
