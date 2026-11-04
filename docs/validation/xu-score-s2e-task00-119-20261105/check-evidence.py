#!/usr/bin/env python3
"""Recheck returned S2e task00 bytes and measured alias bijection; no energy claim."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
PRE = 's2e-formal-activity-task00-20261104-104/'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def canonical(obj):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode())


def unpack(archive, manifest):
    expected = {row['path']: row for row in manifest}
    data, internal = {}, None
    with tarfile.open(archive, 'r|xz') as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in data and member.size < 64000000, 'unsafe/duplicate member')
            body = stream.extractfile(member).read()
            if member.name == 'manifest.json':
                need(internal is None, 'duplicate internal manifest')
                internal = json.loads(body)
                continue
            need(dict(path=member.name, bytes=len(body), sha256=sha(body)) == expected.get(member.name),
                 'raw source member differs: ' + member.name)
            data[member.name] = body
    need(internal == manifest and set(data) == set(expected), 'missing/unaccounted raw member')
    return data


def verify(extract=None):
    meta = json.loads((ROOT / 'selection.json').read_text())
    archive = ROOT / 'payload.tar.xz'
    need(archive.stat().st_size == 731452 and sha(archive.read_bytes()) ==
         'fd084168155c5f4bc7ce43a87958e34e61eab73ad1b9c8001b482fb477ee8d2d', 'derived archive differs')
    manifest = json.loads((ROOT / 'payload-manifest.json').read_text())
    need(len(manifest) == 19 and sum(row['bytes'] for row in manifest) == 40514461 and
         all(row['path'].startswith(PRE) for row in manifest), 'task00 subtree dimensions differ')
    data = unpack(archive, manifest)
    source = ROOT / meta['source_archive']['path']
    need(source.stat().st_size == 872692 and sha(source.read_bytes()) ==
         'ec9657776616f72bc98bb7c876acf71a77bdc9614ab31b9581f4c780c3acb934', 'original119 source archive differs')
    source_manifest = json.loads((ROOT / 'source119-manifest.json').read_text())
    need([row for row in source_manifest if row['path'].startswith(PRE)] == manifest,
         'selected manifest is not the complete119 task00 subtree')
    original = unpack(source, source_manifest)
    need(all(original[name] == body for name, body in data.items()), 'derived archive changed original119 bytes')
    tools = json.loads((ROOT / 'tools-manifest.json').read_text())
    for row in tools:
        body = (ROOT / row['path']).read_bytes()
        need(len(body) == row['bytes'] and sha(body) == row['sha256'], 'archived tool differs')

    def obj(name):
        return json.loads(data[PRE + name])

    result, task = obj('result.json'), obj('task_00/result.json')
    norm = obj('task_00/task-normalization.json')
    config = result['configuration']
    need(result['status'] == 'PARTIAL_COLLECTED_REVIEW_PENDING' and result['taskset_complete'] is False and
         result['requested_task_ids'] == [0] and result['tasks'] == [task] and
         task['status'] == 'COLLECTED_REVIEW_PENDING', 'task00 must remain partial/review pending')
    need(canonical(config) == result['configuration_sha256'] == task['configuration_sha256'] ==
         '0e839b465577bf313345ddba8f02d4f860c5fa3a02f4f753e6acd327ef2df029', 'actual configuration digest differs')
    need(config['nominal_hz'] == 150000000 and config['lf_hz'] == 32768 and config['precision_fs'] == 1 and
         result['source_context']['main_commit'] == '5bf123bfead8f2a37f97f3234d4e40ce8201aae9' and
         result['source_context']['source_profile']['e203_commit'] == 'a0767db69628ef30e53de2d1e93dd0360c0ccf76',
         'frozen nominal source/clock profile differs')
    mapped = config['mapped_context']
    need(mapped['netlist']['sha256'] == '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0' and
         mapped['formality_audit']['status'] == 'AUDITED_ORIGINAL_FULL_SOC_FORMALITY_PASS_NOT_QUALIFIED' and
         mapped['formality_audit']['receipt']['sha256'] == '79c011fc965b620cd39954405ade0b9759e4a409a90b33ad6c683eea3f18594f' and
         mapped['native_formality']['passing'] == 42338, 'own mapped/native109 proof binding differs')
    with tarfile.open(ROOT.parent / 'xu-score-server-progress114-20261105/payload.tar.xz', 'r:xz') as stream:
        proofbody = stream.extractfile('s2e-own-formality-audit-20261104-109/state.json').read()
    need(sha(proofbody) == mapped['formality_audit']['receipt']['sha256'] and
         json.loads(proofbody)['context']['native'] == mapped['native_formality'], 'returned109 proof body differs')
    for item in config['producer_sources']:
        name = Path(item['path']).name
        need(sha((ROOT / 'tools/ppa' / name).read_bytes()) == item['sha256'], 'actual producer source differs')
    w = task['activity_window']
    need(w['begin'] == dict(cycle=1403992, tick=9359950000000) and
         w['end']['cycle'] == 2272335 and w['end']['tick'] == 15148903333333 and
         w['duration_ticks'] == w['end']['tick'] - w['begin']['tick'] == 5788953333333 and
         w['formal_elapsed_cycles'] == w['end']['cycle'] - w['begin']['cycle'] == 868343 and
         w['formal_inclusive_cycles'] == w['formal_elapsed_cycles'] + 1 == 868344 and
         w['first_source_accept'] == w['begin'] and w['initial_source_wait_cycles'] == 0,
         'request-to-retire elapsed/inclusive boundary differs')
    clear = w['pretask_clear']
    need(clear['accepted_writes'] == 33697 and clear['actual_internal_zero_commits_observed'] == dict(w=16384, x=64, bias=256) and
         clear['last_write']['cycle'] < w['begin']['cycle'] and clear['last_write_to_source_request_cycles'] == 98 and
         clear['original_task_destination_setup_writes_before_source'] == 0 and
         clear['fifo_logical_ownership_reset_and_empty_observed'] and clear['verification_at_first_source_request'],
         'clear/reset/fresh ownership evidence differs')
    log = data[PRE + 'task_00/simulation.log'].decode()
    need(sha(log.encode()) == task['boundary_log']['sha256'] and
         log.splitlines().count('SOC_PASS tasks=1 outputs=25344 writes=50688') == 1 and
         not re.search(r'^(?:Fatal:|Error:|XU_\S*REJECT)', log, re.M), 'actual task00 native log failed/differs')
    expected = [
        'XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 actual_commits=1 fifo_reset_empty=1',
        'XU_SOURCE_REQUEST task=0 cycle=1403992 tick=9359950000000',
        'XU_ACTIVITY_END task=0 tick=15148903333333',
        'XU_CANDIDATE_UPLOAD_PASS task=0 w_commits=16384 bias=256 x_commits=6336 rows=99 starts=3168 dones=3168 pops_retired=3168 w_pack32=8192 x_pack32=3168 fifo_empty=1 checked_data=1',
        'XU_S2E_RESULT_READS_PASS task=0 legacy_words=25344 packed_words=12672 logical_words=50688 actual_reads=38016',
        'TASK_PASS layer=0 outputs=25344 writes=50688 cycles=868344 firmware_cycles=868419',
        'XU_LF_CLOCK_STATIC_PASS nominal_hz=32768 checked_edges=992 max_phase_error_fs=1']
    need(all(log.splitlines().count(line) == 1 for line in expected), 'actual counts/clock marker differs')
    need(task['autogroup']['rows'] == 99 and task['autogroup']['pops_retired'] == 3168 and
         task['layer']['result_activity'] == dict(layer=0, legacy_words=25344, packed_words=12672, logical_words=50688),
         'returned task counters differ')
    rawbody, normalized = data[PRE + 'task_00/task.saif'], data[PRE + 'task_00/task-normalized.saif']
    need(len(rawbody) == 25568880 and sha(rawbody) == task['raw_saif']['sha256'] ==
         '5390a5698d41d4734ae218e93c410076e0dd55f9c2e68dfc5cee764e2f7969c7' and
         len(normalized) == 12854048 and sha(normalized) == task['saif']['sha256'] ==
         '7d91fc3e15f3abe42c6f3e7572e46f41ad34f3afb6cd4db91be41827f32294d2' and norm == task['normalization'],
         'raw/normalized original SAIF bytes differ')
    mapping = obj('simulator/sram-pin-alias/xu_s2e_sram_activity_alias.mapping.json')
    need(mapping['macro_count'] == 336 and mapping['alias_bit_count'] == 22512 and
         sha(data[PRE + 'simulator/sram-pin-alias/xu_s2e_sram_activity_alias.mapping.json']) == norm['mapping']['sha256'] and
         sha(data[PRE + 'simulator/sram-pin-alias/xu_s2e_sram_activity_alias.sv']) == norm['observer_source']['sha256'],
         'actual observer/mapping identities differ')
    # Stateless original SAIF reader only. Do not bypass or claim replay of the
    # server source guard, which requires the original absolute source checkout.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('xu_task00_saved_saif_reader', ROOT / 'tools/scripts/xu_soc_activity.py')
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    with tempfile.TemporaryDirectory(prefix='xu-task00-original-') as temp:
        rawpath, normpath = Path(temp) / 'raw.saif', Path(temp) / 'normalized.saif'
        rawpath.write_bytes(rawbody)
        normpath.write_bytes(normalized)
        raw = reader.read_saif(rawpath)
        transformed = reader.read_saif(normpath)
    original_signals = {(s['kind'], s['path']): s for s in raw['signals']}
    target_signals = {(s['kind'], s['path']): s for s in transformed['signals']}
    observer = mapping['observer_scope'].replace('.', '/') + '/'
    widths = dict(CLK=1, CEN=1, WEN=16, A=10, D=16, EMA=3, EMAW=2, GWEN=1, RET1N=1, Q=16)
    pairs, names, comparisons, unknown = {}, [], [], 0
    for index, macro in enumerate(mapping['macros']):
        target_prefix = macro['instance'].replace('.', '/') + '/'
        for pin, width in widths.items():
            for bit in range(width):
                suffix = pin if width == 1 else pin + '[%d]' % bit
                alias = observer + 'macro_%04d/' % index + suffix
                encoded = observer + 'macro_%04d.' % index + suffix
                target = target_prefix + suffix
                source_signal = original_signals[('NET', encoded)]
                dest_signal = target_signals[('PORT', target)]
                stats = {key: value for key, value in source_signal.items() if key not in ['kind', 'path']}
                need(stats == {key: value for key, value in dest_signal.items() if key not in ['kind', 'path']},
                     'measured alias and normalized pin statistics differ')
                pairs[alias] = target
                names.append([alias, encoded])
                comparisons.append([alias, target, stats])
                unknown += sum(stats.get(key, 0) for key in ['TX', 'TZ', 'TB'])
    preserved = {key: signal for key, signal in original_signals.items() if not signal['path'].startswith(observer)}
    need(len(pairs) == len(set(pairs.values())) == 22512 and len(preserved) == 114927 and
         all(target_signals.get(key) == value for key, value in preserved.items()) and
         set(target_signals) == set(preserved) | {('PORT', name) for name in pairs.values()} and
         len(target_signals) == 137439, 'full measured bijection or nonalias preservation differs')
    need(canonical(sorted(names)) == norm['alias_name_comparison_sha256'] and
         canonical(sorted(comparisons)) == norm['per_bit_comparison_sha256'] and
         unknown == norm['alias_unknown_bit_ticks'] == 26076600970238528 and
         raw['duration_ticks'] == transformed['duration_ticks'] == w['duration_ticks'] and
         raw['timescale_seconds'] == transformed['timescale_seconds'] == '1E-15',
         'all-bit measured comparison digest/dwell/timebase differs')
    if extract:
        extract.mkdir(exist_ok=False)
        for name, body in data.items():
            target = extract / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    return dict(status='PASS', qualification='REVIEW_PENDING_NOT_ENERGY_OR_TIMING_QUALIFIED', tasks=1,
                formal_elapsed_cycles=868343, inclusive_cycles=868344, duration_fs=5788953333333,
                measured_macro_pin_bits_compared=22512, nonalias_signals_preserved=114927,
                normalized_signals=137439, raw_and_normalized_original_bytes_verified=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.extract), sort_keys=True, indent=2))
