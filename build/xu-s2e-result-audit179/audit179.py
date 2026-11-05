#!/usr/bin/env python3
"""Independent, local-only review of actual166 in a returned171 snapshot.

No EDA, network, DUT writes, runtime imports, or eligibility promotion.
Large pin originals are compared only through bounded server hash snapshots.
"""
import argparse
import csv
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import traceback

import safe171

HERE = Path(__file__).resolve().parent
REFSHA = 'c6fa79d87965da951d403697fb30730272339208f8d303ad706c40bca5cdab36'
NET = '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794'
OLDNET = '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
STATE155 = '3474d4aaf4801ead290534a25fefcb6cab8d4613ff2191edef71900f7fec6952'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
PRODUCER166 = '745d196537f95ee9822e9e8de41871749f449fa02cc296dc9371b641be8a9a2e'
FROZEN130 = '95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46'
CHAIN = ['1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9',
         '1c47a3c93d0730408d8a7fc30483e1508e349ead3cb1e71dedfa3a78067ce7ee',
         '2060819a8ec232a2554c1d18206531c6ca3646379b22f225d0ff725be2bfa92e']
TASK0 = 'EXECUTED_TASK0_DIAGNOSTIC_NOT_QUALIFIED'
FULL12 = 'EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'
ROOT0 = 's2e-final155-power-preflight-20261105-166'
ROOT12 = 's2e-final155-power12-20261105-166'
PT = 'T-2022.03-SP5-1'
STRIP = 'tb_xu_soc_ppa/dut'
BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)
ACCEL = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'
WIDTHS = {'CLK': 1, 'CEN': 1, 'WEN': 16, 'A': 10, 'D': 16,
          'EMA': 3, 'EMAW': 2, 'GWEN': 1, 'RET1N': 1, 'Q': 16}
PIN_NAMES = {k if w == 1 else '%s[%d]' % (k, bit) for k, w in WIDTHS.items() for bit in range(w)}
LIMITATIONS = [
    'NOT_QUALIFIED: no contest score or qualified energy is asserted.',
    'Returned copied bytes are locally hashed; remote frozen-input before/after are recorded server receipts, not local rehashes of absent RTL/libraries/SAIF/netlist/SVF.',
    'Huge pin reports are absent locally. Only stable bounded server SHA snapshots are matched to execution receipts; this is not local20GB pin-report replay.',
    'Any other native report above the exporter copy limit is also hash-only: its body/error lines are not locally rescanned; exact omitted names and counts are reported per layer.',
    '336/22512 native inventory is locally reconstructed. Source-to-target SAIF preservation is receipt continuity to frozen130, not a new local SAIF parse.',
    'Measured unknown Q and TX/TZ/TB remain; native x_probability=0 does not establish physical known Q.',
    'SRAM conditional/internal power modes, repair-logic inferred activity, gate-level functionality and full150MHz timing coverage remain unqualified.',
    '155 area is paired only with166 energy measured on155. Historical130 energy retains its original89 map and area.',
    'New155 uses frozen forwarded-clock scope; historical S2c/130 used propagated clocks. Cross-method energy differences are not controlled architectural gains.',
]
CLOCK_CHECKS = '''foreach xu_pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {
  set xu_clock [get_clocks -quiet [lindex $xu_pair 0]]
  if {[sizeof_collection $xu_clock] != 1} {error "missing primary clock $xu_pair"}
  if {abs([get_attribute $xu_clock period]-[lindex $xu_pair 1]) > 0.000001} {error "wrong clock period $xu_pair"}
}
if {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] != 1} {error {default conservative divider clock is missing}}
'''


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    return safe171.unique_json(Path(path).read_bytes())


def sha(path):
    return safe171.sha_file(path)


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def identity(path):
    p = Path(path)
    need(p.is_file() and not p.is_symlink(), 'regular file required: ' + str(p))
    return dict(bytes=p.stat().st_size, sha256=sha(p))


def same_identity(a, b):
    return all(a.get(k) == b.get(k) for k in ['bytes', 'sha256'])


def expected_reports():
    names = ['read-saif.rpt', 'inconsistent.rpt', 'tool-version.rpt', 'units.rpt', 'clocks.rpt',
             'check-timing.rpt', 'power.rpt', 'power-hierarchy.rpt', 'sram-power.rpt', 'sram-library.rpt',
             'sram-pins-before.rpt', 'sram-pins-after.rpt']
    for phase in ['before', 'after']:
        names += ['switching-%s.rpt' % phase, 'coverage-%s.rpt' % phase, 'unannotated-%s.rpt' % phase]
        names += ['source-%s-%s.rpt' % (source, phase) for source in ['file', 'default', 'propagated', 'no_switching_activity']]
    return names + ['update-power.rpt']


def reference_data():
    need(sha(HERE / 'references179.json') == REFSHA, '179 frozen reference index changed')
    index = load(HERE / 'references179.json')
    need(index['schema'] == 'xu-result179-reference-manifest-v1', 'reference schema')
    for row in index['files']:
        safe171.safe_name(row['path'])
        need(same_identity(identity(HERE / row['path']), row), 'frozen reference differs: ' + row['path'])
    root = HERE / 'references'
    # All165 inputs are rehashed independently, rather than trusting165 summary.
    source = load(root / '165-source-manifest.json')
    need(len(source) == 12 and len({r['path'] for r in source}) == 12, '165 input inventory')
    for row in source:
        p = Path(row['path'])
        need(p.parts[0] == 'inputs' and len(p.parts) == 2, '165 unsafe input')
        need(same_identity(identity(root / '165-inputs' / p.name), row), '165 input hash')
    state = load(root / '155-state.json')
    need(sha(root / '155-state.json') == STATE155 and state['formal_passing'] == 42338 and
         state['frozen_before'] == state['frozen_after'] and len(state['frozen_before']) == 204 and
         state['frozen_input_errors'] == [] and state['resume155_adopted_originals_rechecked'] is True,
         'actual155 frozen recorded terminal')
    need([r['sha256'] for r in state['svf_chain']] == CHAIN, 'ordered three SVF155')
    native_fm((root / '155-final-fm.log').read_text())
    for name, original in [('fm.log', state['runs'][-1]['log']),
                           ('verify.tcl', state['runs'][-1]['script'])]:
        need(same_identity(identity(root / ('155-final-' + name)), original), '155 native reference identity ' + name)
    for name in ['area.rpt', 'sta.tcl']:
        matches = [r for p, r in state['reports'].items() if p.endswith('/' + name)]
        if not matches:
            matches = [r for r in state.get('generated', {}).values() if isinstance(r, dict) and r.get('path', '').endswith('/' + name)]
        if name == 'sta.tcl':
            matches = [r['script'] for r in state['runs'] if r['tool'] == 'pt' and Path(r['directory']).name == 'final']
        need(len(matches) == 1 and same_identity(identity(root / ('155-final-' + name)), matches[0]), '155 ' + name + ' identity')
    area_text = (root / '155-final-area.rpt').read_text()
    need(re.findall(r'^' + re.escape(ACCEL) + r'\n\s+([0-9.]+)\s', area_text, re.M) == ['300309.6339'], '155 accelerator area')
    need(re.findall(r'^Total cell area:\s*([0-9.]+)\s*$', area_text, re.M) == ['3373696.204286'], '155 SoC area')
    oldprep = load(root / '165-inputs/s2e130-prepared.json')
    oldexecution = load(root / '165-inputs/s2e130-execution.json')
    need(oldprep['netlist']['sha256'] == OLDNET and oldexecution['input_sha256_before'] ==
         oldexecution['input_sha256_after'] == oldprep['input_sha256'], 'historical130 recorded input guard')
    with (root / '165-per-layer.csv').open() as f:
        comparison_rows = list(csv.DictReader(f))
    need(len(comparison_rows) == 12, '165 layer rows')
    cc = ec = 0
    ce = ee = D(0)
    for i, row in enumerate(comparison_rows):
        need(int(row['layer']) == i and int(row['s2c_elapsed_cycles']) == 990656 and
             int(row['s2e_elapsed_cycles']) == 868343, '165 layer cycles')
        cc += int(row['s2c_elapsed_cycles']); ec += int(row['s2e_elapsed_cycles'])
        ce += D(row['s2c_diagnostic_energy_j']); ee += D(row['s2e_diagnostic_energy_j'])
        need(D(row['s2c_diagnostic_energy_j']) == D(row['s2c_reported_power_w']) * D(row['s2c_duration_fs']) * D('1e-15') and
             D(row['s2e_diagnostic_energy_j']) == D(row['s2e_reported_power_w']) * D(row['s2e_duration_fs']) * D('1e-15'), '165 independent energy')
    historic = load(root / '165-comparison.json')['original_map_comparison']
    need(cc == 11887872 and ec == 10420116 and ce == D(historic['s2c']['diagnostic_energy12_j']) and
         ee == D(historic['s2e']['diagnostic_energy12_j']), '165 historical aggregate')
    return dict(state=state, oldprep=oldprep, oldexecution=oldexecution, historic=historic, rows=comparison_rows,
                reference_index=identity(HERE / 'references179.json'))


def native_fm(text):
    need('Version R-2020.09-SP5' in text and
         text.splitlines().count('XU_S2E_TIMING134_FORMALITY_PASS') == 1 and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)\s*$', text, re.M) == ['Verification SUCCEEDED'] and
         re.findall(r'^\s*(\d+) Passing compare points\s*$', text, re.M) == ['42338'], '155 full native FM')
    need(not any(BAD.search(line) for line in text.splitlines()) and not
         re.search(r'^\s*(?:[1-9][0-9]* (?:Failing|Aborted|Unverified) compare points|XU_S2E_TIMING134_FORMALITY_FAIL)\s*$', text, re.M), '155 native FM failure')
    need(re.findall(r'^Passing \(equivalent\)\s+([0-9 \t]+)$', text, re.M) == ['17136     0     0     0   144 25019    39 42338'] or
         [list(map(int, s.split())) for s in re.findall(r'^Passing \(equivalent\)\s+([0-9 \t]+)$', text, re.M)] == [[17136, 0, 0, 0, 144, 25019, 39, 42338]], '155 native FM full scope')


class Evidence:
    def __init__(self, root, archive, expected_sha=None):
        self.root = Path(root).absolute()
        self.report, self.declared = safe171.inspect(archive, expected_sha)
        need(self.root.is_dir() and not self.root.is_symlink(), 'regular evidence root required')
        actual = set()
        for p in self.root.rglob('*'):
            need(not p.is_symlink(), 'evidence symlink rejected')
            if p.is_file(): actual.add(str(p.relative_to(self.root)))
        need(actual == set(self.declared) | {'manifest.json', 'checked171.json'} or
             actual == set(self.declared) | {'manifest.json'}, 'evidence extraction file inventory differs')
        for name, row in self.declared.items():
            need(same_identity(identity(self.root / name), row), 'extracted payload bytes differ: ' + name)
        manifest = load(self.root / 'manifest.json')
        need({r['path']: r for r in manifest['files']} == self.declared, 'extracted manifest differs')
        with tarfile.open(str(archive), 'r:xz') as stream:
            need(stream.extractfile('manifest.json').read() == (self.root / 'manifest.json').read_bytes(),
                 'extracted manifest bytes differ from original archive')
        self.snapshot = load(self.root / 'snapshot171.json')
        need(self.snapshot['schema'] == 'xu-two-candidate-snapshot171-v1' and
             self.snapshot['qualification'] == 'NOT_QUALIFIED', 'snapshot171 provenance')
        self.copies = {}
        self.omitted = {}
        for rows, dest in [(self.snapshot['captures'], self.copies), (self.snapshot['omitted_originals'], self.omitted)]:
            for row in rows:
                name = row['archive_path']
                need(name not in dest and name not in (self.omitted if dest is self.copies else self.copies), 'duplicate source snapshot')
                dest[name] = row
                if dest is self.copies:
                    need(name in self.declared and same_identity(self.declared[name],
                         dict(bytes=row['bytes_observed'], sha256=row['observed_bytes_sha256'])), 'copy/source snapshot SHA differs')

    def path(self, name):
        safe171.safe_name(name)
        return self.root / name

    def json(self, name):
        return load(self.path(name))

    def has(self, name):
        return name in self.declared

    def check(self, name, receipt=None, omitted=False):
        table = self.omitted if omitted else self.copies
        need(name in table, 'source snapshot absent: ' + name)
        row = table[name]
        need(row['metadata_unchanged_during_read'] is True and row['fd_before'] == row['fd_after'] == row['path_after'] and
             row['bytes_observed'] == row['fd_before']['bytes'], 'unstable bounded source snapshot: ' + name)
        if receipt is not None:
            need(receipt['path'] == row['source_path'] and same_identity(receipt,
                 dict(bytes=row['bytes_observed'], sha256=row['observed_bytes_sha256'])), 'source/receipt identity differs: ' + name)
        if omitted:
            expected = 'PIN_ORIGINAL_NEVER_PACKAGED' if omitted == 'pin' or omitted is True else 'ABOVE_SMALL_FILE_LIMIT'
            need(row['omission_reason'] == expected and name not in self.declared, 'omitted report policy differs')
        return row


def check_native(evidence, name, execution, marker):
    evidence.check(name, execution['log'])
    text = evidence.path(name).read_text(errors='strict')
    need(execution['returncode'] == 0 and text.splitlines().count(marker) == 1 and
         'Version ' + PT in text and not any(BAD.search(line) for line in text.splitlines()), 'native marker/version/returncode/error: ' + name)
    first = json.loads(text.splitlines()[0])
    need(first['command'] == execution['command'] and first['cwd'] == execution['cwd'] and
         first['started_utc'] == execution['started_utc'], 'native execution/header provenance')


def target_check(prepared, refs):
    target, old, s = prepared['target_mapped_context'], refs['oldprep'], refs['state']
    need(target['schema'] == 'xu-s2e-final155-target166-v1' and target['qualification'] == 'NOT_QUALIFIED' and
         target['state']['sha256'] == STATE155 and target['netlist']['sha256'] == NET and target['netlist']['bytes'] == 14152273,
         'same own155 state and target identity')
    need(prepared['netlist'] == target['netlist'] and prepared['analysis_sdc'] == target['constraints'] and
         target['constraints']['sha256'] == SDC and prepared['clock_scope'] == target['clock_scope'] and
         target['clock_scope']['sha256'] == SCOPE, 'same155 SDC/clock scope')
    need(prepared['capture_mapped_context'] == target['capture_mapped_context'] == s['own89_context'] == old['mapped_context'] and
         prepared['capture_mapped_context']['netlist']['sha256'] == OLDNET, 'capture120/own89 retained separately')
    need(prepared['activity'] == old['activity'] and prepared['source_context'] == s['source'] == old['source_context'] and
         prepared['original_capture_configuration_sha256'] == old['original_capture_configuration_sha256'] and
         prepared['original_capture_tool_context'] == old['original_capture_tool_context'], 'same original capture configuration/source')
    need(prepared['producer']['sha256'] == PRODUCER166 and prepared['frozen130']['sha256'] == FROZEN130,
         'frozen166 and130 producer identity')
    need(target['svf_chain'] == s['svf_chain'] and [r['sha256'] for r in target['svf_chain']] == CHAIN and
         target['native_formality'] == dict(passing=42338, black_box_pins=17136, ports=144, dff=25019, latches=39,
            unread_dff=511, unmatched_reference_dff=17, failing=0, qualification='NOT_QUALIFIED'), 'same155 ordered3SVF/native full42338 FM')
    for key, local in [('area_report', '155-final-area.rpt'), ('fm_log', '155-final-fm.log'), ('fm_script', '155-final-verify.tcl')]:
        need(same_identity(target[key], identity(HERE / 'references' / local)), 'actual155 original ' + key)
    need(target['area']['accelerator_mm2'] == '0.3003096339' and target['area']['full_soc_mm2'] == '3.373696204286' and
         target['area']['accelerator_limit_mm2'] == '2.25' and target['area']['below_area_limit'] is True and
         target['area']['qualification'] == 'NOT_QUALIFIED', 'same155 area')
    need(prepared['strip_path'] == STRIP and prepared['implementation_controls'] == old['implementation_controls'] and
         prepared['mapping'] == old['tasks'][0]['mapped_macro_bridge_receipt']['mapping'], 'same libraries/mapping/strip scope')
    contract = target['analysis_clock_contract']
    need(contract.startswith('set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\n') and
         'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n' in contract and target['constraints']['path'] in contract and
         target['clock_scope']['path'] in contract, 'explicit clock contract')
    return target


def inventory_check(ev, folder, prepared):
    prefix = folder + '/inventory/'
    ev.check(prefix + 'inventory.json', prepared['mapped_sram_inventory'])
    inv = ev.json(prefix + 'inventory.json'); prov = inv['provenance']
    need(inv['schema'] == 'xu-mapped-sram-pin-inventory-v1' and inv['status'] == 'EXPORTED_REVIEW_PENDING' and
         inv['macro_count'] == 336 and inv['pin_bit_count'] == 22512 and inv['netlist'] == prepared['netlist'] and
         inv['constraints'] == prepared['analysis_sdc'] and
         [{k: r[k] for k in ['path', 'sha256']} for r in inv['libraries']] ==
         [{k: r[k] for k in ['path', 'sha256']} for r in prepared['implementation_controls']['libraries']], 'inventory own155 scope/counts')
    check_native(ev, prefix + 'pt.log', prov['execution'], prov['marker'])
    for name, key in [('macro-pins.tsv', 'raw_tsv'), ('export.tcl', 'script'), ('version.rpt', 'tool_version')]:
        ev.check(prefix + name, prov[key])
    need(prov['input_sha256_before'] == prov['input_sha256_after'], 'inventory recorded source guard')
    need(prov['tool'] == prepared['pt'] and
         all(prepared['input_sha256'].get(p) == h for p, h in prov['input_sha256_before'].items()),
         'inventory same native tool and prepared input identities')
    need(PT in ev.path(prefix + 'version.rpt').read_text(), 'inventory native version')
    script_check(ev.path(prefix + 'export.tcl').read_text(), prepared, None)
    lines = ev.path(prefix + 'macro-pins.tsv').read_text().splitlines()
    need(lines[0] == 'kind\tcell\tref_or_pin\tlibcell_or_direction', 'inventory raw header')
    macros = {}; seen = set(); allpins = set()
    for line in lines[1:]:
        row = line.split('\t')
        need(len(row) == 4 and tuple(row) not in seen, 'raw inventory row duplicate/shape')
        seen.add(tuple(row)); kind, cell, value, extra = row
        if kind == 'MACRO':
            need(cell not in macros and value == 'RAMSP1024X16' and extra == 'RAMSP1024X16_ss_0p99v_0p99v_125c/RAMSP1024X16', 'macro reference/library')
            macros[cell] = dict(instance=cell, ref_name=value, lib_cell=extra, pins=[])
        else:
            need(kind == 'PIN' and cell in macros and value.startswith(cell + '/'), 'raw pin parent')
            name = value[len(cell) + 1:]
            need(name in PIN_NAMES and value not in allpins and extra == ('out' if name.startswith('Q[') else 'in'), 'raw pin geometry/direction/uniqueness')
            allpins.add(value); macros[cell]['pins'].append(dict(name=name, full_name=value, direction=extra))
    need(len(macros) == 336 and len(allpins) == 22512 and all({p['name'] for p in row['pins']} == PIN_NAMES for row in macros.values()), 'all336/22512 exact inventory')
    need(inv['macros'] == [macros[n] for n in sorted(macros)], 'native raw TSV and JSON disagree')
    return inv, sorted(macros)


def script_check(text, prepared, task):
    target = prepared['target_mapped_context']
    contract = target['analysis_clock_contract'].replace('set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n',
        CLOCK_CHECKS + 'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n')
    need(text.count(contract) == 1 and 'set_propagated_clock [all_clocks]' not in text and
         prepared['netlist']['path'] in text and 'link_design' in text, 'same155 Tcl net/SDC/scope and no propagated override')
    if task is not None:
        need(task['completion_marker'] in text and task['saif']['path'] in text and '-strip_path ' in text and STRIP in text and
             'set_app_var power_analysis_mode averaged' in text, 'task Tcl activity/design method')


def power_values(text):
    need(re.findall(r'^Design\s*:\s*(\S+)\s*$', text, re.M) == ['xu_soc_ppa_top'], 'fullSoC power report design')
    for unit in ['Dynamic', 'Leakage']:
        need(re.findall(r'^\s*' + unit + r' Power Units\s*=\s*(\S+)\s+(\S+)\s*$', text, re.M) == [('1', 'W')], 'explicit native watts')
    result = {}
    for key, label in [('switching', 'Net Switching Power'), ('internal', 'Cell Internal Power'), ('leakage', 'Cell Leakage Power'), ('total', 'Total Power')]:
        hits = re.findall(r'^\s*' + label + r'\s*=\s*([0-9.eE+-]+)\s+\(', text, re.M)
        need(len(hits) == 1, 'one native power value: ' + key)
        value = D(hits[0]); need(value.is_finite() and value >= 0, 'finite nonnegative power')
        result[key + '_power_w'] = str(value)
    return result


def check_task(ev, folder, prepared, task, native, macros, refs):
    i = task['task_id']; prefix = folder + '/task_%02d/' % i
    old = refs['oldprep']['tasks'][i]
    need(task['directory'] == 'task_%02d' % i and task['macro_names'] == macros == old['macro_names'], 'task macro bijection/name set')
    need(task['activity_window'] == old['activity_window'] and task['activity_window']['formal_elapsed_cycles'] == 868343 and
         task['activity_window']['duration_ticks'] == 5788953333333, 'exact measured task window/cycle count')
    need(task['canonical_saif'] == old['canonical_saif'] and task['measured_summary'] == old['measured_summary'], 'same original120 SAIF and measured unknown summary')
    ev.check(prefix + 'power.tcl', task['script']); script_check(ev.path(prefix + 'power.tcl').read_text(), prepared, task)
    ev.check(prefix + 'task-mapped-receipt.json', task['mapped_macro_bridge'])
    bridge = ev.json(prefix + 'task-mapped-receipt.json')
    need(bridge == task['mapped_macro_bridge_receipt'] and bridge['inventory'] == prepared['mapped_sram_inventory'] and
         bridge['input_saif'] == task['canonical_saif'] and bridge['output_saif'] == task['saif'] and
         bridge['macro_count'] == 336 and bridge['mapped_pin_bit_count'] == 22512 and bridge['strip_path'] == STRIP,
         'own155 recorded SAIF bridge bijection')
    for key in ['mapping', 'macro_bijection_sha256', 'per_bit_comparison_sha256', 'measured_unknown_bit_ticks', 'duration_ticks', 'timescale_seconds',
                'source_records_removed', 'relocated_pin_bits_added_as_port', 'unchanged_pin_bits_verified', 'native_mapped_pin_bits_verified_reused']:
        need(bridge[key] == old['mapped_macro_bridge_receipt'][key], 'original130 recorded mapping/statistic continuity: ' + key)
    need(task['expected_reports'] == expected_reports() and set(native['reports']) == set(expected_reports()), 'exact native report set')
    need(native['task_id'] == i and native['status'] == 'EXECUTED_DIAGNOSTIC_NOT_QUALIFIED' and
         native['frozen_inputs_sha256'] == canonical(prepared['input_sha256']), 'executed task frozen context receipt')
    check_native(ev, prefix + 'pt.log', native['execution'], task['completion_marker'])
    need(native['execution']['command'] == [prepared['pt']['path'], '-f', 'power.tcl'] and
         native['execution']['cwd'] == str(Path(task['script']['path']).parent), 'actual native tool/cwd')
    hash_only = []
    for name, receipt in native['reports'].items():
        omit = 'pin' if name.startswith('sram-pins-') else 'large' if prefix + name in ev.omitted else False
        ev.check(prefix + name, receipt, omit)
        if omit:
            hash_only.append(name)
        else:
            text = ev.path(prefix + name).read_text(errors='strict')
            need(not any(BAD.search(line) for line in text.splitlines()), 'native report error: ' + name)
            need(name == 'inconsistent.rpt' or receipt['bytes'] > 0, 'native report empty: ' + name)
    need(PT in ev.path(prefix + 'tool-version.rpt').read_text(), 'native version report')
    sramnames = re.findall(r'^XU_SRAM_POWER_CELL name=(.+) ref=(\S+)$', ev.path(prefix + 'sram-power.rpt').read_text(), re.M)
    need(len(sramnames) == 336 and sorted(n for n, ref in sramnames) == macros and all(ref == 'RAMSP1024X16' for n, ref in sramnames), 'all336 native macro power reports')
    power = power_values(ev.path(prefix + 'power.rpt').read_text())
    duration = D(task['activity_window']['duration_ticks']) * D('1e-15'); energy = D(power['total_power_w']) * duration
    diag = native['diagnostic']
    need(diag['qualification'] == 'NOT_QUALIFIED' and diag['report'] == native['reports']['power.rpt'] and
         diag['power_components'] == power and D(diag['duration_seconds']) == duration and D(diag['diagnostic_energy_j']) == energy and
         diag['measured_input_unknown_summary'] == task['measured_summary'], 'independent fullSoC P*duration energy')
    summary = task['measured_summary']
    need(summary['pin_count'] == 22512 and summary['q_pin_count'] == 5376 and summary['q_tx_positive'] == 5280 and
         summary['q_tx_full_window'] == 4256, 'unknown Q still measured; no eligibility upgrade')
    return dict(layer=i, elapsed_cycles=868343, duration_fs=5788953333333, reported_total_power_w=power['total_power_w'],
                diagnostic_energy_j=str(energy), accelerator_area_mm2='0.3003096339', mapped_sha256=NET,
                unknown_q_bits=summary['q_tx_positive'], all_window_unknown_q_bits=summary['q_tx_full_window'],
                native_log_sha256=native['execution']['log']['sha256'], power_report_sha256=native['reports']['power.rpt']['sha256'],
                pin_before_server_bounded_sha256=native['reports']['sram-pins-before.rpt']['sha256'],
                pin_after_server_bounded_sha256=native['reports']['sram-pins-after.rpt']['sha256'],
                locally_rescanned_report_body_count=len(native['reports']) - len(hash_only),
                server_bounded_hash_only_report_count=len(hash_only), server_bounded_hash_only_report_names=';'.join(sorted(hash_only)),
                qualification='NOT_QUALIFIED')


def campaign(ev, folder, ids, refs, preflight=None):
    wanted = TASK0 if ids == [0] else FULL12
    base = dict(output=folder, qualification='NOT_QUALIFIED', requested_task_ids=ids, complete=False, layers=[])
    required = [folder + '/' + n for n in ['result.json', 'prepared.json', 'execution.json', 'summary.json']]
    missing = [n for n in required if not ev.has(n)]
    if missing:
        result = ev.json(folder + '/result.json') if ev.has(folder + '/result.json') else {}
        need(result.get('status') != wanted, 'terminal successful result but required files missing')
        base.update(status='OBSERVED_INCOMPLETE_NOT_QUALIFIED', source_status=result.get('status'), missing=missing,
                    source_error=result.get('error'))
        return base
    prepared, execution, result, summary = [ev.json(folder + '/' + n) for n in ['prepared.json', 'execution.json', 'result.json', 'summary.json']]
    if result.get('status') != wanted or execution.get('status') != wanted or summary.get('status') != wanted:
        base.update(status='OBSERVED_NON_SUCCESS_NOT_QUALIFIED', source_status=result.get('status'), source_error=result.get('error'))
        return base
    for name in required: ev.check(name)
    need(prepared['schema'] == 'xu-s2e-final-power166-prepared-v1' and prepared['requested_task_ids'] == ids and
         [t['task_id'] for t in prepared['tasks']] == ids and execution['requested_task_ids'] == ids and
         [t['task_id'] for t in execution['tasks']] == ids and summary['requested_task_ids'] == ids, 'strict task0/full12 ID scope')
    need(all(v['qualification'] == 'NOT_QUALIFIED' for v in [prepared, execution, result, summary]), 'all outputs retain qualification')
    need(summary['taskset_complete'] is (len(ids) == 12) and execution['taskset_complete'] is (len(ids) == 12) and
         prepared['taskset_complete'] is (len(ids) == 12) and summary['task_count'] == len(ids) and
         prepared['source_capture_complete12'] is True, 'task0 distinct from full12')
    need(execution['input_sha256_before'] == execution['input_sha256_after'] == prepared['input_sha256'] and
         result['input_sha256_before'] == result['input_sha256_after'] == prepared['input_sha256'], 'recorded server before/after freeze guard')
    for key, name in [('prepared', 'prepared.json'), ('summary', 'summary.json')]:
        ev.check(folder + '/' + name, execution[key])
    ev.check(folder + '/summary.json', result['summary'])
    need(summary['tasks'] == execution['tasks'], 'summary/execution task set')
    target = target_check(prepared, refs)
    need(execution['target_context'] == target and summary['target_netlist'] == target['netlist'] and summary['area'] == target['area'] and
         summary['capture_configuration_sha256'] == prepared['original_capture_configuration_sha256'], 'summary/execution same155 target')
    inv, macros = inventory_check(ev, folder, prepared)
    layers = [check_task(ev, folder, prepared, t, n, macros, refs) for t, n in zip(prepared['tasks'], execution['tasks'])]
    total = sum(D(row['diagnostic_energy_j']) for row in layers)
    need(D(summary['sum_diagnostic_energy_j']) == total and summary['total_elapsed_cycles'] == 868343 * len(ids) and
         D(summary['arithmetic_mean_reported_power_w']) == sum(D(r['reported_total_power_w']) for r in layers) / D(len(ids)), 'independent summary aggregates')
    if len(ids) == 1:
        need(prepared['preflight'] is None, 'preflight must be task0 only with no prior preflight')
    else:
        need(preflight is not None and preflight['complete'], 'full12 requires independently audited successful preflight')
        pf = prepared['preflight']
        need(pf['status'] == TASK0 and pf['qualification'] == 'NOT_QUALIFIED' and Path(pf['root']).name == ROOT0, 'full12 preflight success receipt')
        old = ev.json(ROOT0 + '/prepared.json')
        need(prepared['capture_mapped_context'] == old['capture_mapped_context'] and
             prepared['target_mapped_context'] == old['target_mapped_context'] and
             prepared['original_capture_configuration_sha256'] == old['original_capture_configuration_sha256'], 'full12/task0 same capture and target')
        for key in ['prepared', 'execution', 'summary', 'result']: ev.check(ROOT0 + '/' + key + '.json', pf[key])
    base.update(status='AUDITED_NATIVE_TASK0_NOT_QUALIFIED' if len(ids) == 1 else 'AUDITED_NATIVE_FULL12_NOT_QUALIFIED',
                source_status=wanted, complete=True, layers=layers, total_elapsed_cycles=868343 * len(ids),
                sum_diagnostic_energy_j=str(total), recorded_input_sha_count=len(prepared['input_sha256']),
                recorded_input_guard='SERVER_BEFORE_AFTER_RECEIPTS_EQUAL_NOT_LOCAL_EXTERNAL_REHASH',
                inventory=dict(macro_count=336, pin_bit_count=22512, inventory_sha256=prepared['mapped_sram_inventory']['sha256']),
                target_mapped_sha256=NET, capture_original89_sha256=OLDNET, accelerator_area_mm2='0.3003096339')
    return base


def audit(ev, refs):
    zero = campaign(ev, ROOT0, [0], refs)
    full = campaign(ev, ROOT12, list(range(12)), refs, zero)
    comparison = dict(original_map_comparison=refs['historic'], same155_final=dict(mapped_sha256=NET,
        accelerator_area_mm2='0.3003096339', area_limit_mm2='2.25', within_area_limit=True,
        diagnostic_energy12_j=full.get('sum_diagnostic_energy_j') if full['complete'] else None,
        elapsed_cycles12=10420116 if full['complete'] else None),
        analysis_method_mismatch=True, controlled_comparison_status='CONTROLLED_COMPARISON_PENDING',
        new155_clock_method='ORIGINAL_SDC_PLUS_FROZEN_FORWARDED_CLOCK_SCOPE_NO_ALL_CLOCK_PROPAGATION',
        historical_s2c_and130_clock_method='ORIGINAL_SDC_PLUS_ALL_CLOCK_PROPAGATION',
        diagnostic_energy_reduction_vs_s2c_percent=None,
        reason='Own155 native diagnostics are measured, but the changed clock analysis method prevents a controlled energy comparison to historical S2c/130.')
    paired = []
    if full['complete']:
        for old, new in zip(refs['rows'], full['layers']):
            paired.append(dict(layer=new['layer'], s2c_cycles=old['s2c_elapsed_cycles'], s2e_cycles=new['elapsed_cycles'],
                s2c_original_map_sha256=refs['historic']['s2c']['mapped_sha256'], s2e_final155_map_sha256=NET,
                s2c_original_accelerator_area_mm2=refs['historic']['s2c']['accelerator_area_mm2'], s2e_final155_accelerator_area_mm2='0.3003096339',
                s2c_original_diagnostic_energy_j=old['s2c_diagnostic_energy_j'], s2e_final155_diagnostic_energy_j=new['diagnostic_energy_j'],
                s2e_final155_power_report_sha256=new['power_report_sha256'],
                controlled_comparison_status='CONTROLLED_COMPARISON_PENDING_CLOCK_METHOD_MISMATCH', qualification='NOT_QUALIFIED'))
    return dict(schema='xu-s2e166-independent-audit179-v1', qualification='NOT_QUALIFIED',
        status='AUDITED_FULL12_DIAGNOSTIC_NOT_QUALIFIED' if full['complete'] else 'AUDITED_TASK0_FULL12_INCOMPLETE_NOT_QUALIFIED' if zero['complete'] else 'INCOMPLETE_EVIDENCE_NOT_QUALIFIED',
        archive_check=ev.report, reference_index=refs['reference_index'],
        producer=identity(Path(__file__).resolve()), frozen_safe171=identity(HERE / 'safe171.py'),
        task0=zero, full12=full, comparison=comparison,
        paired_layers=paired, limitations=LIMITATIONS)


def write_outputs(out, result):
    (out / 'audit179.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    for filename, rows in [('task0.csv', result.get('task0', {}).get('layers', [])),
                           ('full12.csv', result.get('full12', {}).get('layers', [])),
                           ('comparison.csv', result.get('paired_layers', []))]:
        if rows:
            with (out / filename).open('x', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence-root', type=Path, required=True); p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--sha256'); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); out = a.out.absolute()
    need(not out.exists() and not out.is_symlink(), 'fresh output directory required; failed evidence is retained')
    out.mkdir(parents=True)
    try:
        refs = reference_data(); ev = Evidence(a.evidence_root, a.archive, a.sha256)
        result = audit(ev, refs); write_outputs(out, result)
        print(json.dumps(dict(status=result['status'], output=str(out), task0=result['task0']['source_status'],
                             full12=result['full12']['source_status'], qualification='NOT_QUALIFIED'), sort_keys=True))
    except BaseException as error:
        failure = dict(schema='xu-s2e166-independent-audit179-v1', status='FAILED_AUDIT_RETAINED_NOT_QUALIFIED',
                       qualification='NOT_QUALIFIED', error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc(), limitations=LIMITATIONS)
        (out / 'audit179.json').write_text(json.dumps(failure, sort_keys=True, indent=2) + '\n')
        raise


if __name__ == '__main__':
    main()
