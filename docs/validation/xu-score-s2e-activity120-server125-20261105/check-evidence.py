#!/usr/bin/env python3
"""Verify all original125 bytes and 12 independent raw-to-normalized SAIF bijections.

PASS concerns this returned RTL activity archive only: never timing, mapped
annotation, internal-power coverage, single-task energy or contest qualification.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent
PREFIX = 's2e-formal-activity12-20261105-120/'
CONFIG_SHA = '53e44a6600d99ae3e527a96317dd8bb13c427d4b4e6eea8705aa757ed30fd7fe'
PROOF_SHA = '79c011fc965b620cd39954405ade0b9759e4a409a90b33ad6c683eea3f18594f'
WIDTHS = dict(CLK=1, CEN=1, WEN=16, A=10, D=16, EMA=3, EMAW=2, GWEN=1, RET1N=1, Q=16)
CSV_FIELDS = ['layer', 'formal_elapsed_cycles', 'formal_inclusive_cycles', 'firmware_cycles',
              'begin_tick_fs', 'end_tick_fs', 'duration_fs', 'clear_writes_before_window',
              'outputs', 'shared_y_writes', 'result_physical_reads', 'alias_pin_bits_compared',
              'nonalias_signals_preserved', 'alias_unknown_bit_ticks', 'simulation_log_sha256',
              'raw_saif_sha256', 'normalized_saif_sha256', 'per_bit_comparison_sha256']


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical(obj):
    return sha(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode())


def checked_extract(destination):
    """Manually copy validated regular members; never use extractall or symlinks."""
    archive = ROOT / 'payload.tar.xz'
    need(archive.stat().st_size == 8171768 and sha_file(archive) ==
         'ebfba2f46193dca30362ccce4fbbe602be238abd21a316240da0da2f828fbf10', 'original125 archive bytes differ')
    manifest = json.loads((ROOT / 'payload-manifest.json').read_text())
    need(len(manifest) == 88 and sum(row['bytes'] for row in manifest) == 465539700, 'original125 member dimensions differ')
    expected = {row['path']: row for row in manifest}
    need(len(expected) == 88, 'duplicate manifest names')
    seen, internal = set(), None
    with tarfile.open(archive, 'r|xz') as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in seen and 0 <= member.size < 64000000, 'unsafe or duplicate original125 member')
            seen.add(member.name)
            if member.name == 'manifest.json':
                internal = json.loads(stream.extractfile(member).read())
                continue
            row = expected.get(member.name)
            need(row is not None and row['bytes'] == member.size, 'unaccounted/size-mismatched member: ' + member.name)
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            digest, size = hashlib.sha256(), 0
            with target.open('xb') as out:
                source = stream.extractfile(member)
                for block in iter(lambda: source.read(1048576), b''):
                    size += len(block); digest.update(block); out.write(block)
            need(size == row['bytes'] and digest.hexdigest() == row['sha256'], 'original member SHA differs: ' + member.name)
    need(internal == manifest and seen == set(expected) | {'manifest.json'}, 'missing or unaccounted125 body')
    return manifest


def compare_saif(rawpath, normalizedpath, mapping, norm, window, reader):
    """Build all 22,512 mappings independently; compare every retained statistic."""
    raw, normalized = reader.read_saif(rawpath), reader.read_saif(normalizedpath)
    source = {(s['kind'], s['path']): s for s in raw['signals']}
    target = {(s['kind'], s['path']): s for s in normalized['signals']}
    need(len(source) == len(raw['signals']) and len(target) == len(normalized['signals']), 'duplicate SAIF signals')
    observer = mapping['observer_scope'].replace('.', '/') + '/'
    pairs, names, comparisons, unknown = {}, [], [], 0
    for index, macro in enumerate(mapping['macros']):
        prefix = macro['instance'].replace('.', '/') + '/'
        for pin, width in WIDTHS.items():
            for bit in range(width):
                suffix = pin if width == 1 else pin + '[%d]' % bit
                alias = observer + 'macro_%04d/' % index + suffix
                encoded = observer + 'macro_%04d.' % index + suffix
                destination = prefix + suffix
                original = source[('NET', encoded)]
                measured = target[('PORT', destination)]
                stats = {k: v for k, v in original.items() if k not in ('kind', 'path')}
                need(stats == {k: v for k, v in measured.items() if k not in ('kind', 'path')},
                     'alias and normalized pin statistics differ: ' + destination)
                pairs[alias] = destination; names.append([alias, encoded]); comparisons.append([alias, destination, stats])
                unknown += sum(stats.get(key, 0) for key in ('TX', 'TZ', 'TB'))
    preserved = {key: signal for key, signal in source.items() if not signal['path'].startswith(observer)}
    need(len(pairs) == len(set(pairs.values())) == 22512 and len(preserved) == 114927 and
         all(target.get(key) == value for key, value in preserved.items()) and
         set(target) == set(preserved) | {('PORT', value) for value in pairs.values()} and len(target) == 137439,
         'full measured bijection or nonalias preservation differs')
    need(canonical(sorted(names)) == norm['alias_name_comparison_sha256'] and
         canonical(sorted(comparisons)) == norm['per_bit_comparison_sha256'] and
         unknown == norm['alias_unknown_bit_ticks'] == 26076600970238528 and
         raw['duration_ticks'] == normalized['duration_ticks'] == window['duration_ticks'] and
         raw['timescale_seconds'] == normalized['timescale_seconds'] == '1E-15',
         'all-bit comparison digest, unknown dwell, duration, or timebase differs')
    return dict(alias_pin_bits_compared=22512, nonalias_signals_preserved=114927,
                normalized_signals=137439, alias_unknown_bit_ticks=unknown,
                per_bit_comparison_sha256=canonical(sorted(comparisons)))


def csv_body(rows):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader(); writer.writerows({key: row[key] for key in CSV_FIELDS} for row in rows)
    return out.getvalue()


def validate_artifact_manifest():
    rows = json.loads((ROOT / 'manifest.json').read_text())
    expected = {row['path'] for row in rows}
    actual = {str(path.relative_to(ROOT)) for path in ROOT.rglob('*')
              if path.is_file() and '__pycache__' not in path.parts and path != ROOT / 'manifest.json'}
    need(len(expected) == len(rows) and actual == expected, 'archive support-file manifest membership differs')
    for row in rows:
        path = PurePosixPath(row['path'])
        need(not path.is_absolute() and '..' not in path.parts, 'unsafe support-file manifest path')
        item = ROOT / row['path']
        need(item.stat().st_size == row['bytes'] and sha_file(item) == row['sha256'], 'archive support-file SHA differs: ' + row['path'])


def replay(directory):
    def obj(relative):
        return json.loads((directory / PREFIX / relative).read_text())
    result = obj('result.json')
    config = result['configuration']
    need(result['status'] == 'COLLECTED_12_TASKS_REVIEW_PENDING' and result['taskset_complete'] is True and
         result['requested_task_ids'] == list(range(12)) and len(result['tasks']) == 12, 'full12 completion dimensions differ')
    need(canonical(config) == result['configuration_sha256'] == CONFIG_SHA, 'actual120 configuration digest differs')
    need(config['nominal_hz'] == 150000000 and config['lf_hz'] == 32768 and config['precision_fs'] == 1 and
         result['source_context']['main_commit'] == '5bf123bfead8f2a37f97f3234d4e40ce8201aae9' and
         result['source_context']['source_profile']['e203_commit'] == 'a0767db69628ef30e53de2d1e93dd0360c0ccf76',
         'frozen source or nominal clock profile differs')
    mapped = config['mapped_context']
    proofbody = (ROOT / 'proof109-state.json').read_bytes()
    proof = json.loads(proofbody)
    need(sha(proofbody) == mapped['formality_audit']['receipt']['sha256'] == PROOF_SHA and
         mapped['netlist']['sha256'] == '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0' and
         mapped['formality_audit']['status'] == proof['status'] == 'AUDITED_ORIGINAL_FULL_SOC_FORMALITY_PASS_NOT_QUALIFIED' and
         mapped['native_formality'] == proof['context']['native'] and mapped['native_formality']['passing'] == 42338,
         'own mapped and original109 proof binding differs')
    for row in json.loads((ROOT / 'tools-manifest.json').read_text()):
        path = ROOT / row['path']
        need(path.stat().st_size == row['bytes'] and sha_file(path) == row['sha256'], 'archived public tool differs')
    for item in config['producer_sources']:
        need(sha_file(ROOT / 'tools/ppa' / Path(item['path']).name) == item['sha256'], 'actual120 producer source differs')
    mappingpath = directory / PREFIX / 'simulator/sram-pin-alias/xu_s2e_sram_activity_alias.mapping.json'
    observerpath = directory / PREFIX / 'simulator/sram-pin-alias/xu_s2e_sram_activity_alias.sv'
    mapping = json.loads(mappingpath.read_text())
    need(mapping['macro_count'] == len(mapping['macros']) == 336 and mapping['alias_bit_count'] == 22512,
         'actual observer macro/pin dimensions differ')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('xu_original125_saif_reader', ROOT / 'tools/scripts/xu_soc_activity.py')
    reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
    rows, input_sets = [], {}
    for index in range(12):
        prefix = 'task_%02d/' % index
        task, norm = obj(prefix + 'result.json'), obj(prefix + 'task-normalization.json')
        need(task == result['tasks'][index] and task['task_id'] == index and task['status'] == 'COLLECTED_REVIEW_PENDING' and
             task['configuration_sha256'] == CONFIG_SHA and norm == task['normalization'], 'actual120 task record differs')
        w = task['activity_window']
        need(w['global_task_id'] == index and w['layer'] == 0 and task['layer']['layer'] == 0 and
             w['begin'] == dict(cycle=1403992, tick=9359950000000) and
             w['end']['cycle'] == 2272335 and w['end']['tick'] == 15148903333333 and
             w['duration_ticks'] == w['end']['tick'] - w['begin']['tick'] == 5788953333333 and
             w['formal_elapsed_cycles'] == w['end']['cycle'] - w['begin']['cycle'] == 868343 and
             w['formal_inclusive_cycles'] == w['formal_elapsed_cycles'] + 1 == task['layer']['cycles'] == 868344 and
             w['first_source_accept'] == w['begin'] and w['initial_source_wait_cycles'] == 0,
             'actual request-to-retire elapsed/inclusive boundary differs')
        clear = w['pretask_clear']
        need(clear['accepted_writes'] == 33697 and clear['actual_internal_zero_commits_observed'] == dict(w=16384, x=64, bias=256) and
             clear['last_write']['cycle'] < w['begin']['cycle'] and clear['last_write_to_source_request_cycles'] == 98 and
             clear['original_task_destination_setup_writes_before_source'] == 0 and
             clear['fifo_logical_ownership_reset_and_empty_observed'] and clear['verification_at_first_source_request'] and
             all(task['cache_policy'][key] for key in ('all_fixture_commits_inside_window', 'fifo_ownership_reset_and_fresh_production_observed', 'fresh_process', 'physical_zero_clear_observed')) and
             task['cache_policy']['cross_task_reuse'] is False, 'clear/reset/fresh process evidence differs')
        logpath = directory / PREFIX / prefix / 'simulation.log'
        log = logpath.read_text(); lines = log.splitlines()
        need(sha_file(logpath) == task['boundary_log']['sha256'] and lines.count('SOC_PASS tasks=1 outputs=25344 writes=50688') == 1 and
             not re.search(r'^(?:Fatal:|Error:|XU_\S*REJECT)', log, re.M), 'actual120 native log failed or differs')
        expected = [
            'XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 actual_commits=1 fifo_reset_empty=1',
            'XU_SOURCE_REQUEST task=%d cycle=1403992 tick=9359950000000' % index,
            'XU_ACTIVITY_BEGIN task=%d tick=9359950000000' % index,
            'XU_ACTIVITY_END task=%d tick=15148903333333' % index,
            'XU_TASK_WINDOW task=%d request_cycle=1403992 accept_cycle=1403992 end_cycle=2272335 initial_wait_cycles=0 legacy_inclusive_cycles=868344 formal_inclusive_cycles=868344 formal_elapsed_cycles=868343' % index,
            'XU_CANDIDATE_UPLOAD_PASS task=%d w_commits=16384 bias=256 x_commits=6336 rows=99 starts=3168 dones=3168 pops_retired=3168 w_pack32=8192 x_pack32=3168 fifo_empty=1 checked_data=1' % index,
            'XU_S2E_RESULT_READS_PASS task=%d legacy_words=25344 packed_words=12672 logical_words=50688 actual_reads=38016' % index,
            'TASK_PASS layer=0 outputs=25344 writes=50688 cycles=868344 firmware_cycles=868419',
            'XU_LF_CLOCK_STATIC_PASS nominal_hz=32768 checked_edges=992 max_phase_error_fs=1',
            'XU_CLOCK_STATIC_PASS checked_hf_edges=2272347']
        need(all(lines.count(line) == 1 for line in expected), 'task boundary, count, result, or clock marker differs')
        need(task['autogroup']['rows'] == 99 and task['autogroup']['pops_retired'] == 3168 and
             task['layer']['result_activity'] == dict(layer=0, legacy_words=25344, packed_words=12672, logical_words=50688),
             'actual120 task counters differ')
        inputs = obj(prefix + 'vectors/input-manifest.json'); input_sets[str(index)] = inputs
        need(inputs['global_task_id'] == index and inputs['original_layer'] == 'layer_%02d' % index and
             inputs['simulator_layer'] == 'layer_00' and len(inputs['files']) == 4 and
             sha_file(directory / PREFIX / prefix / 'vectors/input-manifest.json') == task['input_manifest']['sha256'], 'global/original/simulator layer mapping differs')
        need({row['tensor'] for row in inputs['files']} == {'x', 'w', 'bias', 'y'}, 'task tensor identity set differs')
        for item in inputs['files']:
            need(item['original']['sha256'] == item['materialized']['sha256'] ==
                 result['original_task_vectors'][index]['sha256'][item['tensor'] + '.mem'], 'frozen original tensor receipt differs')
        rawpath, normalizedpath = directory / PREFIX / prefix / 'task.saif', directory / PREFIX / prefix / 'task-normalized.saif'
        need(sha_file(rawpath) == task['raw_saif']['sha256'] == norm['raw_saif']['sha256'] and
             sha_file(normalizedpath) == task['saif']['sha256'] == norm['normalized_saif']['sha256'] and
             sha_file(mappingpath) == norm['mapping']['sha256'] and sha_file(observerpath) == norm['observer_source']['sha256'],
             'raw/normalized SAIF or mapping/observer original bytes differ')
        stats = compare_saif(rawpath, normalizedpath, mapping, norm, w, reader)
        row = dict(layer=index, formal_elapsed_cycles=868343, formal_inclusive_cycles=868344, firmware_cycles=868419,
                   begin_tick_fs=w['begin']['tick'], end_tick_fs=w['end']['tick'], duration_fs=w['duration_ticks'],
                   clear_writes_before_window=33697, outputs=25344, shared_y_writes=50688, result_physical_reads=38016,
                   simulation_log_sha256=sha_file(logpath), raw_saif_sha256=sha_file(rawpath),
                   normalized_saif_sha256=sha_file(normalizedpath), **stats)
        rows.append(row)
        print('REPLAYED_ACTUAL120 task=%d measured_bits=22512 nonalias_preserved=114927 NOT_ENERGY_OR_TIMING_QUALIFIED' % index, file=sys.stderr, flush=True)
    need(canonical(input_sets) == result['taskset_inputs_sha256'] == '6ba79d709925d22258d0624a53198e2f7d5926d8bdbe82699def9f9728459dca',
         'all12 original tensor receipt digest differs')
    driver = (directory / 's2e-formal-activity12-20261105-120-driver.log').read_text().splitlines()
    need(all(driver.count('COLLECTED_CANDIDATE task=%d duration_fs=5788953333333' % i) == 1 for i in range(12)) and
         len([line for line in driver if line.startswith('COLLECTED_12_TASKS_REVIEW_PENDING:')]) == 1 and
         json.loads((directory / 'omitted125-bodies.json').read_text()) == [], 'full12 original driver or export completeness differs')
    return dict(status='PASS', qualification='RTL_ACTIVITY_REVIEW_PENDING_NOT_MAPPED_OR_ENERGY_OR_TIMING_QUALIFIED',
                original125_payload_files=88, original125_payload_bytes=465539700, tasks=12,
                total_formal_elapsed_cycles=sum(row['formal_elapsed_cycles'] for row in rows),
                total_inclusive_diagnostic_cycles=sum(row['formal_inclusive_cycles'] for row in rows),
                total_duration_fs=sum(row['duration_fs'] for row in rows),
                measured_macro_pin_bits_compared=sum(row['alias_pin_bits_compared'] for row in rows),
                nonalias_signals_preserved_across_tasks=sum(row['nonalias_signals_preserved'] for row in rows),
                own109_proof_receipt_sha256=PROOF_SHA, configuration_sha256=CONFIG_SHA, per_layer=rows)


def verify(extract=None, compare_derived=True):
    if compare_derived:
        validate_artifact_manifest()
    if extract is None:
        with tempfile.TemporaryDirectory(prefix='xu-original125-') as temporary:
            directory = Path(temporary)
            checked_extract(directory)
            summary = replay(directory)
    else:
        extract.mkdir(parents=True, exist_ok=False)
        checked_extract(extract)
        summary = replay(extract)
    if compare_derived:
        need(summary == json.loads((ROOT / 'verification.json').read_text()), 'saved independent replay differs')
        need(csv_body(summary['per_layer']) == (ROOT / 'per-layer.csv').read_text(), 'saved per-layer CSV differs')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path, help='retain the complete88 original payload files in a new directory')
    args = parser.parse_args()
    summary = verify(args.extract)
    print(json.dumps({key: value for key, value in summary.items() if key != 'per_layer'}, sort_keys=True, indent=2))
