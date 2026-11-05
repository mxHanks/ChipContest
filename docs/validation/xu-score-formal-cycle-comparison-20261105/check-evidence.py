#!/usr/bin/env python3
"""Compare actual S2c23 and S2e120 task windows; no EDA or energy qualification."""
import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parent
PHASES = ('w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other')
FIELDS = ['layer', 's2c_elapsed_cycles', 's2e_elapsed_cycles', 'saved_cycles',
          's2c_duration_fs', 's2e_duration_fs', 's2c_log_sha256', 's2e_log_sha256']
FIELDS += [label + '_' + phase for phase in PHASES for label in ('s2c', 's2e', 'saved')]


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def only_line(text, prefix):
    rows = [line for line in text.splitlines() if line.startswith(prefix + ' ')]
    need(len(rows) == 1, 'missing/duplicate native line: ' + prefix)
    return dict(re.findall(r'([a-z_]+)=(\d+)', rows[0]))


def read_sources():
    index = json.loads((ROOT / 'payload-manifest.json').read_text())
    raw = (ROOT / 'payload.tar.xz').read_bytes()
    need(len(raw) == index['bytes'] and digest(raw) == index['sha256'], 'payload differs')
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        entries = archive.getmembers()
        need(all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in entries), 'unsafe member')
        expected = {r['path']: r for r in index['members']}
        need(len(entries) == len(expected) == 53 and {m.name for m in entries} == set(expected), 'member set differs')
        data = {m.name: archive.extractfile(m).read() for m in entries}
    for name, content in data.items():
        row = expected[name]
        need(len(content) == row['bytes'] and digest(content) == row['sha256'], 'original member differs: ' + name)
    sources = json.loads(data['source-receipts.json'])
    results = {}
    for label, receipt in sources.items():
        prefix = receipt['activity_prefix']
        original = {r['path']: r for r in json.loads(data[label + '/source-manifest.json'])}
        for name, content in data.items():
            if name.startswith(label + '/' + prefix + '/'):
                row = original[name[len(label) + 1:]]
                need(digest(content) == row['sha256'] and len(content) == row['bytes'], 'upstream member identity differs')
        result = json.loads(data[label + '/' + prefix + '/result.json'])
        need(result['status'] == 'COLLECTED_12_TASKS_REVIEW_PENDING' and result['taskset_complete'] is True and
             result['requested_task_ids'] == list(range(12)) and [t['task_id'] for t in result['tasks']] == list(range(12)), 'incomplete taskset')
        need(digest(json.dumps(result['configuration'], sort_keys=True, separators=(',', ':')).encode()) == result['configuration_sha256'], 'configuration hash differs')
        results[label] = result
    a, b = results['s2c'], results['s2e']
    need(a['original_task_vectors'] == b['original_task_vectors'], 'original twelve fixed tensor identities differ')
    for key in ('nominal_hz', 'lf_hz', 'precision_fs', 'numeric_format', 'activity_scope', 'monitoring_policy', 'simulator_defines'):
        need(a['configuration'][key] == b['configuration'][key], 'comparison setting differs: ' + key)
    need(a['configuration']['constraints']['sha256'] == b['configuration']['constraints']['sha256'] ==
         '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98', 'constraint bytes identity differs')
    need(a['configuration']['nominal_hz'] == 150000000 and a['configuration']['lf_hz'] == 32768 and
         a['configuration']['precision_fs'] == 1 and a['configuration']['numeric_format'] == 'signed16/40/48', 'formal format/clock differs')
    need(a['configuration']['netlist']['sha256'] == '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892' and
         b['configuration']['netlist']['sha256'] == '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0', 'candidate identities differ')
    return data, sources, results


def compare():
    data, sources, results = read_sources()
    rows = []
    for task_id in range(12):
        row = dict(layer=task_id)
        fixtures = []
        for label, result in results.items():
            task = result['tasks'][task_id]
            prefix = label + '/' + sources[label]['activity_prefix'] + '/task_%02d/' % task_id
            log = data[prefix + 'simulation.log']
            need(digest(log) == task['boundary_log']['sha256'], 'task log identity differs')
            text = log.decode()
            need(text.splitlines().count('SOC_PASS tasks=1 outputs=25344 writes=50688') == 1 and
                 not re.search(r'^(?:Fatal:|Error:|FATAL:|SOC_FAIL)', text, re.M), 'native task failure')
            manifest_raw = data[prefix + 'vectors/input-manifest.json']
            need(digest(manifest_raw) == task['input_manifest']['sha256'], 'fixture receipt identity differs')
            fixture = json.loads(manifest_raw)
            need(fixture['global_task_id'] == task_id and fixture['original_layer'] == 'layer_%02d' % task_id and fixture['simulator_layer'] == 'layer_00', 'task materialization differs')
            tensors = {f['tensor']: f['original']['sha256'] for f in fixture['files']}
            need(all(f['original']['sha256'] == f['materialized']['sha256'] for f in fixture['files']) and len(tensors) == 4, 'fixture content identities differ')
            need({k + '.mem': v for k, v in tensors.items()} == result['original_task_vectors'][task_id]['sha256'], 'original layer tensor identities differ')
            fixtures.append(tensors)
            window = task['activity_window']
            marker = only_line(text, 'XU_TASK_WINDOW')
            need(int(marker['formal_elapsed_cycles']) == window['formal_elapsed_cycles'] ==
                 window['end']['cycle'] - window['begin']['cycle'] and
                 window['duration_ticks'] == window['end']['tick'] - window['begin']['tick'], 'actual timing boundary differs')
            clear = only_line(text, 'XU_TASK_CLEAR_OBSERVED')
            need(clear['writes'] == '33697' and clear['w'] == '16384' and clear['x'] == '64' and clear['bias'] == '256' and
                 window['pretask_clear']['accepted_writes'] == 33697 and window['pretask_clear']['verification_at_first_source_request'] is True,
                 'actual pretask clear differs')
            performance = only_line(text, 'PERF_TASK')
            for phase in PHASES:
                value = int(performance[phase])
                need(value == task['layer']['performance'][phase], 'native phase counter differs')
                row[label + '_' + phase] = value
            need(sum(row[label + '_' + phase] for phase in PHASES) == window['formal_inclusive_cycles'] == window['formal_elapsed_cycles'] + 1, 'phase accounting differs')
            row[label + '_elapsed_cycles'] = window['formal_elapsed_cycles']
            row[label + '_duration_fs'] = window['duration_ticks']
            row[label + '_log_sha256'] = digest(log)
        need(fixtures[0] == fixtures[1], 'paired task fixture identities differ')
        row['saved_cycles'] = row['s2c_elapsed_cycles'] - row['s2e_elapsed_cycles']
        for phase in PHASES:
            row['saved_' + phase] = row['s2c_' + phase] - row['s2e_' + phase]
        need(sum(row['saved_' + phase] for phase in PHASES) == row['saved_cycles'], 'saved cycle partition differs')
        rows.append(row)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    summary = dict(qualification='NOT_QUALIFIED', task_count=12,
        source_configurations={k: v['configuration_sha256'] for k, v in results.items()},
        total_elapsed_cycles={k: sum(r[k + '_elapsed_cycles'] for r in rows) for k in results},
        total_duration_fs={k: sum(r[k + '_duration_fs'] for r in rows) for k in results},
        total_saved_cycles=sum(r['saved_cycles'] for r in rows),
        saved_phase_cycles={p: sum(r['saved_' + p] for r in rows) for p in PHASES},
        limitations=['Same original tensor identities, clock/format/clear/window policy; distinct candidate RTL/firmware/netlists.',
                     'Original vector bodies and SAIF bodies are not in this comparison subset; identities are receipt evidence.',
                     'Phase counters are inclusive diagnostics; candidate deltas partition the elapsed-cycle delta exactly.',
                     'Throughput is observed RTL task-window arithmetic, not completed150MHz or energy qualification.',
                     'No same-new-RTL old-firmware formal150 control was run; development control is archived separately.'])
    totals = summary['total_elapsed_cycles']
    summary['cycle_reduction_percent'] = str(Decimal(totals['s2c'] - totals['s2e']) / Decimal(totals['s2c']) * 100)
    summary['observed_tasks_per_second'] = {k: str(Decimal(12) / (Decimal(v) * Decimal('1e-15'))) for k, v in summary['total_duration_fs'].items()}
    summary['throughput_increase_percent'] = str((Decimal(summary['total_duration_fs']['s2c']) / Decimal(summary['total_duration_fs']['s2e']) - 1) * 100)
    return stream.getvalue(), json.dumps(summary, sort_keys=True, indent=2) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    csv_text, summary_text = compare()
    for name, text in [('per-layer.csv', csv_text), ('comparison.json', summary_text)]:
        path = ROOT / name
        if args.write:
            need(not path.exists(), 'refusing to overwrite derived result')
            path.write_text(text)
        else:
            need(path.read_text() == text, 'derived comparison differs: ' + name)
    print('PASS: actual twelve paired logs, original tensor identities, clear/window policy, phase accounting and derived comparison; NOT_QUALIFIED')


if __name__ == '__main__':
    main()
