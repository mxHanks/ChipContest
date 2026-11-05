#!/usr/bin/env python3
"""Read-only four-state SRAM marginal classification for original S2e120/130.

No external tools, network, new activity or unknown-value substitutions.
Constant-state implications and overlap bounds are distinct from joint traces.
"""
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import traceback

from saif188 import selected_signals, need

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE_SHA = '6b71fa38d36905c10a8c40aec2e5379f145f3d34d0fbde137fdcaefe5211d3a7'
DURATION = 5788953333333
STRIP = 'tb_xu_soc_ppa/dut'
PREFIX = 's2e-full-soc-power12-20261105-130'
ACTIVITY = 's2e-formal-activity12-20261105-120'
AUDIT = 's2e-native-pin-streamaudit-20261105-164'
WIDTHS = dict(CLK=1, CEN=1, GWEN=1, RET1N=1, WEN=16, A=10, D=16, EMA=3, EMAW=2, Q=16)
PINS = {k if w == 1 else '%s[%d]' % (k, b) for k, w in WIDTHS.items() for b in range(w)}
CONTROLS = ['CLK', 'CEN', 'GWEN', 'RET1N'] + ['WEN[%d]' % b for b in range(16)] + ['EMA[%d]' % b for b in range(3)] + ['EMAW[%d]' % b for b in range(2)]
STATS = ['T0', 'T1', 'TX', 'TZ', 'TB', 'TC', 'IG']
LIMITATIONS = [
    'NOT_QUALIFIED. Original120 RTL marginals/130 mapped names are classified; old89 connectivity is not new155 connectivity proof.',
    'No timestamped joint full-task control trajectory or conditional per-edge evidence is present in these SAIF files. Aggregate TC is not edge-time correlation.',
    'Whole-window known constants imply that control state coexists with every measured Q-unknown interval, but do not establish per-edge internal-power conditions, event ordering or DUT read validity.',
    'Overlap ranges are exact marginal bounds, not reconstructed joint waveforms or probabilities. No independence assumption is used.',
    'CEN=1 is not zero power: the archived library arc ledger includes CLK internal_power under RET1N & CEN. The ledger itself remains NOT_QUALIFIED.',
    'Unknown Q, constant Q, zero output toggle count and native getter x_probability=0 must not be replaced with 0, 0.5, or proof of physically known storage.',
    'Every unknown macro output can affect downstream standard cells/muxes unless same155 connectivity and simultaneous masking/ownership are demonstrated. No downstream cone is waived.',
    'NCS/WEB/NAP/CE names are not captured pins in this67-pin macro contract; no unproved alias or nap-mode inference is introduced.',
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def load(path):
    def unique(items):
        out = {}
        for k, v in items:
            need(k not in out, 'duplicate JSON key'); out[k] = v
        return out
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def ident(path):
    p = Path(path); need(p.is_file() and not p.is_symlink(), 'regular file required: ' + str(p))
    return dict(bytes=p.stat().st_size, sha256=sha(p))


def same(a, b): return all(a.get(k) == b.get(k) for k in ['bytes', 'sha256'])


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def source_check(roots):
    need(sha(HERE / 'sources188.json') == SOURCE_SHA, 'frozen188 source index changed')
    index = load(HERE / 'sources188.json'); records = []
    need(index['schema'] == 'xu-unknown188-frozen-sources-v1', '188 source schema')
    manifests = {}
    for tag, spec in index['roots'].items():
        root = roots[tag]
        need(same(ident(root / 'manifest.json'), spec['manifest']), 'source manifest SHA/bytes changed: ' + tag)
        archive = REPO / spec['archive']['path']
        need(same(ident(archive), spec['archive']), 'source original archive SHA/bytes changed: ' + tag)
        with tarfile.open(str(archive), 'r:xz') as stream:
            need(stream.extractfile('manifest.json').read() == (root / 'manifest.json').read_bytes(), 'source extracted manifest/archive mismatch')
        manifest = load(root / 'manifest.json')
        rows = manifest['files'] if isinstance(manifest, dict) else manifest
        need(len({r['path'] for r in rows}) == len(rows), 'source manifest duplicate path')
        manifests[tag] = {r['path']: r for r in rows}
    for row in index['files']:
        rel = PurePosixPath(row['path']); need(not rel.is_absolute() and '..' not in rel.parts, 'unsafe source name')
        root = roots[row['root']]; p = root / row['path']
        need(same(row, manifests[row['root']][row['path']]) and same(ident(p), row), 'source actual/manifest/index mismatch: ' + row['path'])
        records.append(dict(root=row['root'], path=row['path'], **ident(p)))
    for row in index['local_references']:
        need(same(ident(HERE / row['path']), row), 'local188 reference changed')
    return index, records


def overlap(unknown_ticks, control_ticks, duration=DURATION):
    need(0 <= unknown_ticks <= duration and 0 <= control_ticks <= duration, 'invalid marginal interval')
    return max(0, unknown_ticks + control_ticks - duration), min(unknown_ticks, control_ticks)


def stat(row): return {k: row[k] for k in row if k not in ['path', 'mapped_path', 'kind']}


def binding(mapping, inventory):
    need(mapping['pin_widths'] == WIDTHS and mapping['macro_count'] == inventory['macro_count'] == 336 and
         mapping['alias_bit_count'] == inventory['pin_bit_count'] == 22512, 'complete336/22512 binding')
    canonical_macros = {}
    for row in mapping['macros']:
        path = row['instance'].replace('.', '/')
        need(path.startswith(STRIP + '/') and path not in canonical_macros, 'canonical macro identity collision')
        canonical_macros[path] = row['group']
    actual = {}; comparison = {}
    for row in inventory['macros']:
        path = row['instance']; key = STRIP + '/' + path.replace('.', '/')
        need(path not in actual and key not in comparison and row['ref_name'] == 'RAMSP1024X16' and
             len(row['pins']) == 67 and {p['name'] for p in row['pins']} == PINS, 'native exact geometry/identity')
        actual[path] = row; comparison[key] = path
    need(set(canonical_macros) == set(comparison), 'canonical-to-native explicit macro bijection')
    # Dots are compared only inside this enumerated336 macro mapping. Actual
    # destination pin paths always retain their literal mapped names.
    return {path: dict(canonical=key, group=canonical_macros[key]) for key, path in comparison.items()}


def streams(out):
    result = {}
    fields = {
        'q-bits': ['layer', 'group', 'instance', 'bit', 'class'] + STATS + ['CEN1_unknown_overlap_lower_fs', 'CEN1_unknown_overlap_upper_fs', 'joint_evidence'],
        'controls': ['layer', 'group', 'instance', 'pin'] + STATS + ['whole_window_known_constant'],
        'macros': ['layer', 'group', 'instance', 'q_tx_positive_bits', 'q_tx_full_bits', 'q_tx_zero_bits', 'CEN_constant', 'CLK_TC', 'GWEN_constant', 'RET1N_constant', 'unknown_Q_and_CEN1_exact_constant_overlap_bits', 'joint_trace_available', 'downstream_masking_proven'],
    }
    for name, names in fields.items():
        raw = (out / (name + '.csv.gz')).open('xb')
        gz = gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0)
        text = io.TextIOWrapper(gz, newline=''); writer = csv.DictWriter(text, fieldnames=names); writer.writeheader()
        result[name] = (writer, text, raw)
    return result


def constant(row):
    return '0' if row['T0'] == DURATION else '1' if row['T1'] == DURATION else 'NOT_WHOLE_WINDOW_KNOWN_CONSTANT'


def analyze(roots, out):
    index, inputs = source_check(roots)
    prepared = load(roots['progress135'] / PREFIX / 'prepared.json')
    inventory = load(roots['progress135'] / PREFIX / 'inventory/inventory.json')
    mapping = load(roots['activity125'] / ACTIVITY / 'simulator/sram-pin-alias/xu_s2e_sram_activity_alias.mapping.json')
    state = load(roots['audit174'] / AUDIT / 'state.json')
    need(state['status'] == 'STREAM_AUDITED_24_ORIGINAL_REPORTS_NOT_QUALIFIED' and state['task_count'] == 12 and
         state['qualification'] == 'NOT_QUALIFIED' and state['input_receipts'] == state['input_receipts_after'] and
         state['original_frozen_inputs_before'] == state['original_frozen_inputs_after'], 'actual164 original guard/terminal')
    need(same(state['input_receipts']['prepared'], ident(roots['progress135'] / PREFIX / 'prepared.json')) and
         prepared['netlist']['sha256'] == '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0', 'old130 input identity')
    macro_binding = binding(mapping, inventory)
    ledger = load(HERE / 'arc-ledger.json')
    need(ledger['qualification'] == 'NOT_QUALIFIED' and any(r['kind'] == 'internal' and r['toggling_pin'] == 'CLK' and
         r['when'] == 'RET1N & CEN' for r in ledger['arcs']), 'frozen disabled-clock internal-power counterexample')
    rows = []; native = []; representative = {}; all_streams = streams(out)
    try:
        for layer in range(12):
            measured_path = roots['progress135'] / PREFIX / ('task_%02d' % layer) / 'measured-sram-pins.json'
            source_path = roots['activity125'] / ACTIVITY / ('task_%02d' % layer) / 'task-normalized.saif'
            summary = load(roots['audit174'] / AUDIT / ('task_%02d' % layer) / 'summary.json')
            task = prepared['tasks'][layer]; measured = load(measured_path)
            need(summary['originals_before'] == summary['originals_after'] and summary['task_id'] == layer and
                 summary['qualification'] == 'NOT_QUALIFIED', 'same164 per-layer original before/after')
            for path in [measured_path, source_path, roots['activity125'] / ACTIVITY / 'simulator/sram-pin-alias/xu_s2e_sram_activity_alias.mapping.json']:
                matches = [r for remote, r in summary['originals_before'].items() if remote.endswith('/' + str(path.relative_to(roots['progress135'] if path.is_relative_to(roots['progress135']) else roots['activity125'])))]
                need(len(matches) == 1 and same(matches[0], ident(path)), '164 per-layer original source SHA differs: ' + str(path))
            pins = {p['mapped_path']: p for p in measured['pins']}
            need(len(pins) == 22512 and measured['measured_summary'] == task['measured_summary'] == summary['measured_summary'], '22512 measured records and summaries')
            wanted = {row['canonical'] + '/' + pin for row in macro_binding.values() for pin in PINS}
            canonical_pins, parse_receipt = selected_signals(source_path, wanted, DURATION)
            need(parse_receipt['signal_records'] == summary['measured_body_audit']['canonical_signal_records'], 'complete canonical SAIF record count')
            per_group = defaultdict(Counter); comparisons = []
            for instance, bound in sorted(macro_binding.items()):
                group = bound['group']; group_counts = per_group[group]; group_counts['macros'] += 1
                macro = {}
                for pin in sorted(PINS):
                    actual = pins[instance + '/' + pin]; path = bound['canonical'] + '/' + pin
                    candidates = [canonical_pins[(kind, path)] for kind in ['NET', 'PORT'] if (kind, path) in canonical_pins]
                    need(candidates and all(r == stat(actual) == candidates[0] for r in candidates), 'every measured/canonical pin statistic must match')
                    macro[pin] = actual; comparisons.append([path, STRIP + '/' + instance + '/' + pin, stat(actual)])
                c = Counter()
                for bit in range(16):
                    q = macro['Q[%d]' % bit]
                    # These original Q marginals have no Z or TB dwell. This is
                    # measured four-state output classification, not a claim
                    # about the physical contents of the memory array.
                    need(q.get('TZ', 0) == 0 and q.get('TB', 0) == 0, 'Q Z/TB dwell needs a separate classification')
                    label = 'FULL_WINDOW_TX' if q['TX'] == DURATION else 'PARTIAL_WINDOW_TX' if q['TX'] else 'TX_ZERO'
                    c[label] += 1; group_counts[label] += 1
                    low, high = overlap(q['TX'], macro['CEN']['T1'])
                    group_counts['Q_TX_and_CEN1_overlap_lower_bit_fs'] += low
                    group_counts['Q_TX_and_CEN1_overlap_upper_bit_fs'] += high
                    if q['TX'] and macro['CEN']['T1'] == DURATION:
                        c['UNKNOWN_AND_CEN1_CONSTANT'] += 1; group_counts['UNKNOWN_AND_CEN1_CONSTANT'] += 1
                    all_streams['q-bits'][0].writerow(dict(layer=layer, group=group, instance=instance, bit=bit, **{'class': label},
                        **{k: q.get(k, 0) for k in STATS}, CEN1_unknown_overlap_lower_fs=low, CEN1_unknown_overlap_upper_fs=high,
                        joint_evidence='CONSTANT_CONTROL_IMPLICATION_ONLY' if q['TX'] and macro['CEN']['T1'] == DURATION else 'MARGINAL_BOUNDS_NO_JOINT_TRACE'))
                for pin in CONTROLS:
                    control = macro[pin]
                    all_streams['controls'][0].writerow(dict(layer=layer, group=group, instance=instance, pin=pin,
                        **{k: control.get(k, 0) for k in STATS}, whole_window_known_constant=constant(control)))
                group_counts['CEN_whole_window_1_macros'] += int(macro['CEN']['T1'] == DURATION)
                group_counts['CLK_no_toggle_macros'] += int(macro['CLK']['TC'] == 0)
                group_counts['input_unknown_bit_fs'] += sum(macro[p].get(k, 0) for p in PINS if not p.startswith('Q[') for k in ['TX', 'TZ', 'TB'])
                all_streams['macros'][0].writerow(dict(layer=layer, group=group, instance=instance,
                    q_tx_positive_bits=c['FULL_WINDOW_TX'] + c['PARTIAL_WINDOW_TX'], q_tx_full_bits=c['FULL_WINDOW_TX'],
                    q_tx_zero_bits=c['TX_ZERO'], CEN_constant=constant(macro['CEN']), CLK_TC=macro['CLK']['TC'], GWEN_constant=constant(macro['GWEN']),
                    RET1N_constant=constant(macro['RET1N']), unknown_Q_and_CEN1_exact_constant_overlap_bits=c['UNKNOWN_AND_CEN1_CONSTANT'],
                    joint_trace_available=False, downstream_masking_proven=False))
                bucket = (group, 'full' if c['FULL_WINDOW_TX'] == 16 else 'partial' if c['PARTIAL_WINDOW_TX'] else 'tx_zero',
                          'CEN1' if macro['CEN']['T1'] == DURATION else 'CENvar', 'CLKstatic' if macro['CLK']['TC'] == 0 else 'CLKtoggles')
                representative.setdefault('|'.join(bucket), dict(group=group, instance=instance, Q_class=bucket[1],
                    CEN_class=bucket[2], CLK_class=bucket[3], selection='FIRST_SORTED_INSTANCE_REPRESENTATIVE_NOT_FULL_COVERAGE'))
            need(canonical(sorted(comparisons)) == task['mapped_macro_bridge_receipt']['per_bit_comparison_sha256'], 'entire22512 canonical/mapped bit comparison digest')
            need(sum(c['FULL_WINDOW_TX'] for c in per_group.values()) == 4256 and
                 sum(c['PARTIAL_WINDOW_TX'] for c in per_group.values()) == 1024 and sum(c['TX_ZERO'] for c in per_group.values()) == 96,
                 '5280/4256 Q classification invariants')
            for group, counts in sorted(per_group.items()): rows.append(dict(layer=layer, group=group, **dict(counts), qualification='NOT_QUALIFIED'))
            for phase in summary['phases']:
                for key, value in phase['independent_raw_replay']['measured_native_cross_counts'].items():
                    if key.startswith('SRAM_OUTPUT_Q|'):
                        native.append(dict(layer=layer, phase=phase.get('phase', phase.get('name')), measured_native_class=key,
                                           pin_count=value, evidence='RETURNED164_SERVER_REPLAY_RECEIPT_NOT_LOCAL_BIG_REPORT_READ', qualification='NOT_QUALIFIED'))
            print('XU188_CLASSIFIED_LAYER %d pins=22512 Q_TXpositive=5280 Q_TXfull=4256 NOT_QUALIFIED' % layer, flush=True)
    finally:
        for writer, text, raw in all_streams.values(): text.close(); raw.close()
    group_fields = ['layer', 'group', 'macros', 'FULL_WINDOW_TX', 'PARTIAL_WINDOW_TX', 'TX_ZERO',
        'Q_TX_and_CEN1_overlap_lower_bit_fs', 'Q_TX_and_CEN1_overlap_upper_bit_fs', 'UNKNOWN_AND_CEN1_CONSTANT',
        'CEN_whole_window_1_macros', 'CLK_no_toggle_macros', 'input_unknown_bit_fs', 'qualification']
    for name, data, fields in [('groups.csv', rows, group_fields), ('native-getter-difference.csv', native, list(native[0]))]:
        with (out / name).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, restval=0); writer.writeheader(); writer.writerows(data)
    totals = defaultdict(Counter)
    for row in rows:
        for k, v in row.items():
            if isinstance(v, int) and k != 'layer': totals[row['group']][k] += v
    _, inputs_after = source_check(roots)
    need(inputs_after == inputs, '188 local selected source inputs changed during classification')
    output = dict(schema='xu-s2e-sram-unknown188-v1', status='CLASSIFIED_ORIGINAL12_MARGINALS_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        producer=ident(Path(__file__).resolve()), sources_index=ident(HERE / 'sources188.json'), inputs_rehashed=inputs,
        inputs_rehashed_after=inputs_after,
        layer_count=12, Q_bits_per_layer=5376, unknown_Q_bits_per_layer=5280, all_window_unknown_Q_bits_per_layer=4256,
        partially_unknown_Q_bits_per_layer=1024, TX_zero_Q_bits_per_layer=96, exact_joint_event_traces_available=0,
        missing_named_controls=['NCS', 'WEB', 'NAP', 'CE'], captured_control_pins=CONTROLS,
        groups_all12={g: dict(c) for g, c in totals.items()}, representatives=list(representative.values()),
        unchanged_capture_relevance_to155='Same120 capture/336x67 activity statistics support missing-evidence diagnosis; no89-to155 connectivity or gate-level proof is inferred.',
        next_probe=dict(mode='PROPOSED_ONLY_NO_REMOTE_ACTION', first_stage='Passive original120 joint four-state controls/A/D/16Q at every transition and both clock edges, including pre/post/simultaneous-change provenance; use listed representative classes first, then full336 for coverage.',
            required_missing_evidence=['conditional dwell and per-edge arc truth/unknown counts', 'original full-task SAIF marginal reconciliation',
                'same155 static fanout and mux/select/ownership predicates', 'same155 four-state downstream observations during Q-unknown intervals'],
            scope='No force, Q writes, new initialization/reset, timing-check suppression or unknown replacement.'),
        limitations=LIMITATIONS)
    (out / 'analysis188.json').write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--progress135', type=Path, default=REPO / 'build/xu-score-resume-20261103/progress135')
    parser.add_argument('--activity125', type=Path, default=REPO / 'build/xu-score-resume-20261103/activity125')
    parser.add_argument('--audit174', type=Path, default=REPO / 'build/xu-score-resume-20261103/progress174')
    parser.add_argument('--out', type=Path, required=True); args = parser.parse_args(); out = args.out.absolute()
    need(not out.exists() and not out.is_symlink(), 'fresh output directory required; failures are retained')
    out.mkdir(parents=True)
    try:
        result = analyze({k: getattr(args, k).absolute() for k in ['progress135', 'activity125', 'audit174']}, out)
        manifest = dict(schema='xu-unknown188-output-manifest-v1', qualification='NOT_QUALIFIED',
            status=result['status'], files=[dict(path=p.name, **ident(p)) for p in sorted(out.iterdir())])
        (out / 'output-manifest188.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        print(result['status'], flush=True)
    except BaseException as error:
        (out / 'FAILED188.json').write_text(json.dumps(dict(status='FAILED_CLASSIFICATION_RETAINED_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
            error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc()), indent=2, sort_keys=True) + '\n')
        raise


if __name__ == '__main__': main()
