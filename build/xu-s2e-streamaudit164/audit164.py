#!/usr/bin/env python3
"""Read-only independent streaming audit of the frozen own130 twelve-layer run."""
import argparse
import os
from pathlib import Path
import sys
import traceback

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common164 import BAD, canonical, check, identity, need, read, utc, write
import primary164
import replay164
import saif164

SUCCESS = 'STREAM_AUDITED_24_ORIGINAL_REPORTS_NOT_QUALIFIED'
FAILURE = 'FAIL_DIAGNOSTIC_NOT_QUALIFIED'
LIMITS = [
    'All states are NOT_QUALIFIED. Complete native byte/statistic replay does not qualify full-SoC energy or a contest score.',
    'Native x_probability=0 is only an engine getter value and never proves a physically known SRAM Q.',
    'Before/after means before/after EXPLICIT update_power; report_attribute getters may trigger lazy propagation or averaged-power calculations.',
    'Source membership is an exact saved native driver-pin-column match only. An absent load/input match is not proof of no file annotation.',
    'Measured TX/TZ/TB and all other SAIF statistics are retained. No physical state, unknown-to-known conversion or energy correction is inferred.',
    'No EDA process is launched. STA/RDC, mapped private function, numerical contest eligibility and SRAM when/internal_power mode qualification remain separate.',
]


def own_bundle():
    manifest = read(HERE/'manifest164.json')
    need(manifest['schema'] == 'xu-s2e-streamaudit164-bundle-v1' and manifest['qualification'] == 'NOT_QUALIFIED', '164 bundle schema differs')
    runtime = manifest['runtime_files']; records = {r['path']: r for r in manifest['files']}
    need(set(runtime) == {'audit164.py', 'common164.py', 'primary164.py', 'replay164.py', 'saif164.py', 'receipts164.json'}, 'exact frozen164 runtime set required')
    result = []
    for name in runtime:
        need(name in records and '/' not in name, '164 runtime manifest member differs')
        row = identity(HERE/name)
        need(row['sha256'] == records[name]['sha256'] and row['bytes'] == records[name]['bytes'], '164 runtime bytes changed: '+name)
        result.append(row)
    return result+[identity(HERE/'manifest164.json')]


def frozen_receipts(campaign):
    expected = read(HERE/'receipts164.json')
    execution_record = check(campaign/'execution.json', expected['execution'])
    prepared_record = check(campaign/'prepared.json', expected['prepared'])
    execution, prepared = read(campaign/'execution.json'), read(campaign/'prepared.json')
    need(execution['schema'] == 'xu-s2e-full-soc-power130-execution-v1' and
         execution['status'] == 'EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and execution['qualification'] == 'NOT_QUALIFIED' and
         execution['taskset_complete'] is True and execution['requested_task_ids'] == list(range(12)) and
         [t['task_id'] for t in execution['tasks']] == list(range(12)), 'exact complete own130 execution required')
    need(prepared['schema'] == 'xu-s2e-full-soc-power130-prepared-v1' and prepared['status'] == 'PREPARED_REVIEW_PENDING' and
         prepared['qualification'] == 'NOT_QUALIFIED' and prepared['taskset_complete'] is True and
         prepared['requested_task_ids'] == list(range(12)) and [t['task_id'] for t in prepared['tasks']] == list(range(12)), 'exact complete own130 prepared required')
    need(execution['prepared'] == execution['prepared_after'] == prepared_record and
         execution['input_sha256_before'] == execution['input_sha256_after'] == prepared['input_sha256'] and
         len(prepared['input_sha256']) == expected['frozen_input_count'], 'own130 exact preparation/before-after input identity differs')
    for task, done in zip(prepared['tasks'], execution['tasks']):
        need(task['directory'] == 'task_%02d' % task['task_id'] and done['status'] == 'EXECUTED_DIAGNOSTIC_REVIEW_PENDING' and
             done['execution']['returncode'] == 0 and task['activity_window']['duration_ticks'] == expected['duration_ticks'] and
             str(task['activity_window']['timescale_seconds']) == '1e-15' and task['activity_window']['formal_elapsed_cycles'] == expected['formal_elapsed_cycles_per_task'] and
             task['measured_summary'] == done['diagnostic']['measured_input_unknown_summary'], 'own130 task/window/native binding differs')
        need(task['saif'] == execution['artifacts'][task['directory']+'/task-mapped.saif'] and
             task['measured_sram_pin_states'] == execution['artifacts'][task['directory']+'/measured-sram-pins.json'], 'own130 mapped/measured artifact identity differs')
    return execution, prepared, dict(execution=execution_record, prepared=prepared_record)


def verify_frozen_inputs(records):
    for path, digest in sorted(records.items()):
        need(identity(path)['sha256'] == digest, 'original130 frozen input changed: '+path)
    return dict(count=len(records), canonical_sha256=canonical(records), all_original_paths_rehashed=True)


def original_log(done, task):
    path = done['execution']['log']['path']; before = check(path, done['execution']['log'])
    count, version = 0, False
    with Path(path).open() as stream:
        for line in stream:
            need(not BAD.search(line), 'original130 PT log contains native error')
            count += line.rstrip('\r\n') == task['completion_marker']
            version = version or 'Version T-2022.03-SP5-1' in line
    need(count == 1 and version, 'original130 unique completion marker/PT version differs')
    need(check(path, done['execution']['log']) == before, 'original130 PT log changed')
    return before


def run(campaign, out):
    need(not Path(out).is_symlink(), 'output symlink is forbidden')
    campaign, out = Path(campaign).resolve(), Path(out).resolve()
    need(not out.exists() and not out.is_symlink() and campaign not in out.parents and out not in campaign.parents and out != campaign,
         'fresh output outside immutable campaign required')
    out.mkdir(parents=True)
    state = dict(schema='xu-s2e-streamaudit164-state-v1', status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        pid=os.getpid(), started_utc=utc(), campaign=str(campaign), tasks=[], limitations=LIMITS)
    write(out/'state.json', state)
    try:
        producers = own_bundle(); state['producers'] = producers
        execution, prepared, receipts = frozen_receipts(campaign)
        state['input_receipts'] = receipts
        state['original_frozen_inputs_before'] = verify_frozen_inputs(prepared['input_sha256'])
        inventory_record = check(prepared['mapped_sram_inventory']['path'], prepared['mapped_sram_inventory'])
        inventory = read(inventory_record['path'])
        need(inventory['netlist'] == prepared['netlist'], 'own130 native inventory netlist differs')
        watched = {inventory_record['path']: inventory_record}
        duration = read(HERE/'receipts164.json')['duration_ticks']
        for task, done in zip(prepared['tasks'], execution['tasks']):
            number, name = task['task_id'], task['directory']; target = out/name; target.mkdir()
            state.update(current_task_id=number, checkpoint_utc=utc()); write(out/'state.json', state)
            result = dict(task_id=number, status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                pt_log=original_log(done, task), activity_window=task['activity_window'], phases=[])
            local_records = {}
            for key in ('mapped_macro_bridge', 'measured_sram_pin_states', 'canonical_saif', 'saif'):
                record = task[key]; local_records[record['path']] = check(record['path'], record)
            bridge = read(task['mapped_macro_bridge']['path'])
            need(bridge == task['mapped_macro_bridge_receipt'] and bridge['input_saif'] == task['canonical_saif'] and
                 bridge['output_saif'] == task['saif'] and bridge['inventory'] == prepared['mapped_sram_inventory'], 'own130 exact original bridge receipt differs')
            mapping = bridge['mapping']; local_records[mapping['path']] = check(mapping['path'], mapping)
            measured, result['measured_body_audit'] = saif164.audit(task, task['measured_sram_pin_states']['path'], mapping['path'], inventory_record['path'], duration)
            previous_primary, previous_replay = None, None
            for phase in ('before', 'after'):
                state.update(current_phase=phase, checkpoint_utc=utc()); write(out/'state.json', state)
                metadata, memberships = {}, {}
                for source in ('file', 'default', 'propagated', 'no_switching_activity'):
                    report_name = 'source-%s-%s.rpt' % (source, phase)
                    record = done['reports'][report_name]
                    need(record == execution['artifacts'][name+'/'+report_name] and Path(record['path']) == campaign/name/report_name, 'own130 source report path/receipt differs')
                    metadata[source], memberships[source] = primary164.source_membership(record['path'], record, measured, source)
                report_name = 'sram-pins-'+phase+'.rpt'; record = done['reports'][report_name]
                need(record == execution['artifacts'][name+'/'+report_name] and Path(record['path']) == campaign/name/report_name, 'own130 native pin report path/receipt differs')
                compact = target/('native-'+phase+'.jsonl.xz')
                first, previous_primary = primary164.extract(record['path'], record, measured, phase, compact, memberships, previous_primary)
                second, previous_replay = replay164.replay(record['path'], record, compact, first['compact'], measured, phase, first, target, memberships, previous_replay)
                result['phases'].append(dict(phase=phase, primary=first, independent_raw_replay=second, source_reports=metadata))
                write(target/'summary.json', result)
                print('XU164_REPLAYED task=%02d phase=%s pins=%d bytes=%d NOT_QUALIFIED' %
                    (number, phase, second['pin_count'], second['complete_original_bytes_replayed']), flush=True)
            for path, before in local_records.items(): need(check(path, before) == before, 'original per-layer evidence changed after replay')
            need(previous_primary == previous_replay, 'independent before/after signatures differ')
            result.update(status='AUDITED_TWO_ORIGINAL_REPORTS_NOT_QUALIFIED', originals_before=local_records,
                          originals_after=dict(local_records), measured_summary=task['measured_summary'])
            write(target/'summary.json', result)
            state['tasks'].append(result); write(out/'state.json', state)
        need(len(state['tasks']) == 12 and all(len(task['phases']) == 2 for task in state['tasks']), 'all24 actual raw native reports required')
        state['original_frozen_inputs_after'] = verify_frozen_inputs(prepared['input_sha256'])
        need(state['original_frozen_inputs_before'] == state['original_frozen_inputs_after'], 'complete original130 input set changed')
        for path, before in watched.items(): need(check(path, before) == before, 'original global evidence changed')
        _, _, after = frozen_receipts(campaign); need(after == receipts and own_bundle() == producers, 'original164/130 receipts or tools changed')
        state.update(status=SUCCESS, original_reports_streamed=24, native_pin_blocks=12*2*22512,
            task_count=12, input_receipts_after=after, total_formal_elapsed_cycles=sum(t['activity_window']['formal_elapsed_cycles'] for t in state['tasks']))
        state.pop('current_task_id', None); state.pop('current_phase', None)
    except BaseException as error:
        state.update(status=FAILURE, error=type(error).__name__+': '+str(error))
        with (out/'failure.txt').open('x') as stream: traceback.print_exc(file=stream)
        raise
    finally:
        state['finished_or_checkpoint_utc'] = utc(); write(out/'state.json', state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); state = run(args.campaign, args.out)
    print(state['status']+' '+str(args.out), flush=True)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('FAIL164: '+type(error).__name__+': '+str(error), file=sys.stderr); sys.exit(1)
