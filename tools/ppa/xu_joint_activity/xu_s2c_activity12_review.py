#!/usr/bin/env python3
"""xu offline consistency review of the actual 12-task S2c export53 evidence.

This checks the exported logs and receipts, not the unexported SAIF contents.
No simulator, PT runner, source evidence, or historical result is modified.
"""

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


CAMPAIGN = 's2c-formal-activity12-20261103-23'
EXPORT_MANIFEST_SHA = 'dd5f1135a7a593e0027f991bea82ddfbfabfc4e557c0b732543755fa1258c20f'
GROUPS = {'accelerator_weights': 16, 'dtcm': 32, 'itcm': 32, 'shared': 256}
PIN_WIDTHS = dict(A=10, CEN=1, CLK=1, D=16, EMA=3, EMAW=2, GWEN=1, Q=16, RET1N=1, WEN=16)
CLEAR_LINE = ('XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 '
              'drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 '
              'actual_commits=1 fifo_reset_empty=1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse(data):
    return json.loads(data, object_pairs_hook=unique_json)


def event(log, name):
    rows = [line for line in log.splitlines() if line.startswith(name + ' ')]
    require(len(rows) == 1, name + ' absent/duplicated')
    pairs = re.findall(r'([A-Za-z0-9_]+)=([^ ]+)', rows[0][len(name) + 1:])
    require(len(pairs) == len({key for key, _ in pairs}), name + ' duplicate field')
    return {key: int(value) if re.fullmatch(r'\d+', value) else value for key, value in pairs}


class Inputs:
    def __init__(self, root, manifest):
        self.root = root.resolve()
        self.manifest = manifest.resolve()
        blob = self.manifest.read_bytes()
        require(digest(blob) == EXPORT_MANIFEST_SHA, 'actual export53 manifest identity differs')
        self.records = {}
        all_names = set()
        for record in parse(blob):
            name = record['path']
            require(name not in all_names and not Path(name).is_absolute() and '..' not in Path(name).parts,
                    'unsafe/duplicate export path')
            all_names.add(name)
            if name.startswith(CAMPAIGN + '/'):
                self.records[name[len(CAMPAIGN) + 1:]] = record
        require(len(self.records) == 63, 'expected exactly 63 exported campaign files')
        actual = {str(p.relative_to(self.root)) for p in self.root.rglob('*') if p.is_file()}
        require(actual == set(self.records), 'local campaign file membership differs from export')
        self.payload = {}
        self.verify()

    def verify(self):
        for name, record in self.records.items():
            path = self.root / name
            require(path.is_file() and not path.is_symlink(), 'regular original file required: ' + name)
            data = path.read_bytes()
            require(len(data) == record['bytes'] and digest(data) == record['sha256'],
                    'export bytes/SHA mismatch: ' + name)
            if self.payload:
                require(name not in self.payload or self.payload[name] == data, 'input changed during review')
            self.payload[name] = data

    def json(self, name):
        return parse(self.payload[name])

    def identity(self, record):
        prefix = '/' + CAMPAIGN + '/'
        require(prefix in record['path'], 'identity is outside campaign: ' + record['path'])
        name = record['path'].split(prefix, 1)[1]
        require(name in self.payload, 'identity has no exported original: ' + name)
        data = self.payload[name]
        require(digest(data) == record['sha256'], 'declared identity differs: ' + name)
        if 'bytes' in record:
            require(len(data) == record['bytes'], 'declared byte count differs: ' + name)


def check_task(source, top, task_id, mapping):
    prefix = f'task_{task_id:02d}/'
    task = source.json(prefix + 'result.json')
    norm = source.json(prefix + 'task-normalization.json')
    inputs = source.json(prefix + 'vectors/input-manifest.json')
    log = source.payload[prefix + 'simulation.log'].decode('ascii')
    require(task == top['tasks'][task_id], prefix + 'top/per-task result differs')
    require(task['task_id'] == task_id and task['status'] == 'COLLECTED_REVIEW_PENDING', 'task identity/status')
    require(task['configuration_sha256'] == top['configuration_sha256'], 'per-task config SHA')
    require(task['normalization'] == norm, 'normalization result/receipt differs')
    source.identity(task['boundary_log'])
    source.identity(task['input_manifest'])
    command = task['run_command']
    require(parse(log.splitlines()[0]) == command, 'run command differs from simulation log')
    require(command == [top['binary']['path'], '+TESTCASE=' + top['firmware_build']['elf']['path'],
                        '+VECTORS=' + task['input_manifest']['path'].rsplit('/', 1)[0], '+TASKS=1',
                        '+XU_GLOBAL_TASK=' + str(task_id), '+MAX_CYCLES=4000000', '+DUMPWAVE=0'],
            'isolated fresh-process command differs')
    require(not re.search(r'\b(?:FATAL|TEST_FAIL|SOC_FAIL|TASK_FAIL|XU_CANDIDATE_REJECT|'
                          r'XU_CANDIDATE_RESET_REJECT)\b|Error-\[', log), 'simulation rejection/failure')
    require(log.count(CLEAR_LINE) == 1, 'actual clear observation differs')

    w = task['activity_window']
    require(w['global_task_id'] == task_id and w['layer'] == 0, 'global/local layer mapping differs')
    reset = event(log, 'XU_CANDIDATE_RESET_READY')
    ready = w['accelerator_reset_readiness']
    require(reset == dict(task=task_id, actual_rst_n=1, checked_empty_fifo=1,
                         **{key: ready[key] for key in ('actual_reset_clock_edges', 'startup_observer_edges',
                           'first_reset_tick', 'last_reset_tick', 'first_ready_cycle', 'first_ready_tick')}),
            'actual reset readiness/log differs')
    require(ready['actual_reset_clock_edges'] > 0 and ready['checked_empty_fifo'] is True,
            'actual reset/FIFO readiness missing')
    clear = w['pretask_clear']
    for name, field in [('XU_TASK_CLEAR_BEGIN', 'begin'), ('XU_TASK_CLEAR_LAST_WRITE', 'last_write')]:
        expected = dict(task=task_id, **clear[field])
        if field == 'last_write':
            expected['writes'] = 33697
        require(event(log, name) == expected, 'clear boundary differs')
    require(clear['accepted_writes'] == 33697 and clear['actual_internal_zero_commits_observed'] ==
            dict(w=16384, bias=256, x=64), 'clear internal zero commit counts differ')
    require(clear['verification_at_first_source_request'] is True and
            clear['fifo_logical_ownership_reset_and_empty_observed'] is True and
            clear['original_task_destination_setup_writes_before_source'] == 0, 'clear qualification differs')
    require(clear['activity_status'] == 'outside task SAIF; no clear-phase SAIF measured', 'clear energy scope differs')
    require(clear['last_write']['cycle'] - clear['begin']['cycle'] == clear['accepted_write_span_cycles'] and
            clear['last_write']['tick'] - clear['begin']['tick'] == clear['accepted_write_span_ticks'] and
            w['begin']['cycle'] - clear['last_write']['cycle'] == clear['last_write_to_source_request_cycles'],
            'clear span arithmetic differs')
    require(ready['first_reset_tick'] <= ready['last_reset_tick'] < ready['first_ready_tick'] <
            clear['begin']['tick'] < clear['last_write']['tick'] < w['begin']['tick'] < w['end']['tick'],
            'reset/clear/source/final-retire ordering differs')
    for name, field in [('XU_SOURCE_REQUEST', 'begin'), ('XU_SOURCE_ACCEPT', 'first_source_accept')]:
        require(event(log, name) == dict(task=task_id, **w[field]), 'source boundary differs')
    for name, field in [('XU_ACTIVITY_BEGIN', 'begin'), ('XU_ACTIVITY_END', 'end')]:
        require(event(log, name) == dict(task=task_id, tick=w[field]['tick']), 'activity boundary differs')
    require(event(log, 'XU_TASK_WINDOW') == dict(task=task_id, request_cycle=w['begin']['cycle'],
            accept_cycle=w['first_source_accept']['cycle'], end_cycle=w['end']['cycle'],
            initial_wait_cycles=w['initial_source_wait_cycles'], legacy_inclusive_cycles=w['legacy_task_pass_inclusive_cycles'],
            formal_inclusive_cycles=w['formal_inclusive_cycles'], formal_elapsed_cycles=w['formal_elapsed_cycles']),
            'formal window log/result differs')
    require(w['end']['tick'] - w['begin']['tick'] == w['duration_ticks'] == 6604373333334 and
            w['end']['cycle'] - w['begin']['cycle'] == w['formal_elapsed_cycles'] == 990656 and
            w['formal_inclusive_cycles'] == w['formal_elapsed_cycles'] + 1 == 990657 and
            w['initial_source_wait_cycles'] == 0, 'formal window arithmetic differs')
    legacy = w['legacy_accept_window']
    for name, field in [('PPA_WINDOW_BEGIN', 'begin'), ('PPA_WINDOW_END', 'end')]:
        expected = dict(layer=0, cycle=legacy[field]['cycle'], time_ns=legacy[field]['time_ns'], tick_fs=legacy[field]['tick'])
        require(event(log, name) == expected, 'legacy boundary log/result differs')
    require(legacy['begin']['tick'] == w['first_source_accept']['tick'] and
            legacy['end'] == w['end'] and legacy['duration_ticks'] == w['duration_ticks'], 'legacy/formal span differs')
    require(w['timescale_seconds'] == 1e-15 and w['nominal_hf_period_seconds'] == 1 / 150000000,
            'window timebase differs')
    require(event(log, 'XU_CACHE_INITIAL') == dict(task=task_id, fresh_process=1, cache_enable=0,
            busy=0, prior_uploads=0, prior_starts=0), 'initial cache state differs')
    require(task['cache_policy'] == dict(fresh_process=True, physical_zero_clear_observed=True,
            all_fixture_commits_inside_window=True, fifo_ownership_reset_and_fresh_production_observed=True,
            cross_task_reuse=False), 'cache policy differs')
    upload = event(log, 'XU_CANDIDATE_UPLOAD_PASS')
    require(upload == dict(task=task_id, w_commits=16384, bias=256, x_commits=6336, rows=99,
            starts=3168, dones=3168, pops_retired=3168, w_pack32=8192, x_pack32=3168,
            fifo_empty=1, checked_data=1), 'fresh operand/FIFO result counts differ')
    layer = task['layer']
    require(event(log, 'TASK_PASS') == dict(layer=0, outputs=25344, writes=50688,
            cycles=layer['cycles'], firmware_cycles=layer['firmware_cycles']), 'task pass/result differs')
    require(layer['cycles'] == w['legacy_task_pass_inclusive_cycles'] == w['formal_inclusive_cycles'] and
            layer['firmware_cycles'] == 990728, 'task timing differs')
    require(event(log, 'AUTO_TASK') == task['autogroup'] and task['autogroup']['rows'] == 99 and
            task['autogroup']['pops_retired'] == 3168, 'autogroup counts differ')
    perf = layer['performance']
    require(event(log, 'PERF_TASK') == dict(layer=0, cycles=layer['cycles'], **perf), 'performance log/result differs')
    require(sum(perf[k] for k in ('w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other')) ==
            layer['cycles'] and perf['starts'] == perf['dones'] == 3168 and perf['mac_fire'] == 202752,
            'performance partition/counters differ')
    require(event(log, 'SOC_PASS') == dict(tasks=1, outputs=25344, writes=50688), 'SoC pass missing')
    hf, lf = event(log, 'XU_CLOCK_STATIC_PASS'), event(log, 'XU_LF_CLOCK_STATIC_PASS')
    require(hf['checked_hf_edges'] > w['end']['cycle'] and lf['nominal_hz'] == 32768 and
            lf['checked_edges'] > 0 and lf['max_phase_error_fs'] <= 1, 'static clock checks differ')

    require(inputs['schema'] == 'xu-soc-single-task-input-v1' and inputs['global_task_id'] == task_id and
            inputs['original_layer'] == f'layer_{task_id:02d}' and inputs['simulator_layer'] == 'layer_00', 'tensor task mapping')
    require(len(inputs['files']) == 4 and {r['tensor'] for r in inputs['files']} == {'x', 'w', 'bias', 'y'}, 'four tensor identities required')
    vectors = top['original_task_vectors'][task_id]
    require(vectors['layer'] == task_id and vectors['outputs'] == 25344, 'original task vector metadata differs')
    for record in inputs['files']:
        tensor = record['tensor'] + '.mem'
        original, materialized = record['original'], record['materialized']
        require(original['sha256'] == materialized['sha256'] == vectors['sha256'][tensor] ==
                top['fixture']['files'][f'layer_{task_id:02d}/' + tensor], 'tensor declared SHA differs')
        require(original['path'].endswith(f'/original-vectors/layer_{task_id:02d}/' + tensor) and
                materialized['path'].endswith(f'/task_{task_id:02d}/vectors/layer_00/' + tensor), 'tensor path mapping differs')

    require(norm['schema'] == 'xu-s2c-sram-activity-normalization-v1' and
            norm['status'] == 'NORMALIZED_NOT_ANNOTATION_OR_POWER_QUALIFIED', 'normalization status differs')
    require(norm['macro_count'] == 336 and norm['alias_bit_count'] == norm['mapped_pin_bits_added_as_port'] == 22512 and
            norm['native_pin_bits_verified_reused'] == norm['preexisting_native_net_and_port_bits_preserved'] == 0 and
            norm['nonalias_raw_signal_count_preserved'] == 114927 and
            norm['alias_name_encoding_counts'] == dict(hierarchical=0, vcs_generate_net_atom=22512), 'alias geometry differs')
    for key in ('mapping', 'observer_source'):
        source.identity(norm[key])
    require(norm['generator'] == mapping['generator'] and norm['mapping']['sha256'] ==
            top['configuration']['sram_alias_mapping']['sha256'], 'normalization source identities differ')
    for key in ('per_bit_comparison_sha256', 'alias_name_comparison_sha256'):
        require(re.fullmatch('[a-f0-9]{64}', norm[key]), 'normalization comparison SHA invalid')
    saif = task['saif']
    require(norm['raw_saif']['path'] == task['raw_saif']['path'] and norm['raw_saif']['sha256'] == task['raw_saif']['sha256'] and
            norm['normalized_saif']['path'] == saif['path'] and norm['normalized_saif']['sha256'] == saif['sha256'],
            'SAIF identity/result/receipt differs')
    require(norm['duration_ticks'] == saif['duration_ticks'] == w['duration_ticks'] and
            norm['timescale_seconds'] == saif['timescale_seconds'] == '1E-15' and
            Decimal(saif['duration_seconds']) == Decimal(w['duration_ticks']) * Decimal('1E-15'), 'SAIF declared timebase differs')
    require(saif['signal_count'] == 114927 + 22512 == 137439 and saif['mapped_coverage_status'] == 'REVIEW_PENDING',
            'SAIF signal count or pending annotation status differs')
    inventory = saif['macro_inventory']
    require(set(inventory) == set(GROUPS), 'macro group membership differs')
    all_instances = []
    for group, count in GROUPS.items():
        inv = inventory[group]
        require(inv['expected_count'] == inv['observed_count'] == len(inv['instances']) == count and
                inv['pin_coverage_and_internal_power_status'] == 'REVIEW_PENDING', 'declared macro coverage differs')
        all_instances.extend(inv['instances'])
    require(len(set(all_instances)) == 336 and set(all_instances) ==
            {r['instance'].replace('.', '/') for r in mapping['macros']}, 'alias/inventory macro identities differ')
    clock = saif['source_clock']
    require(len(clock) == 1 and clock[0] == dict(IG=0, T0=3302186666667, T1=3302186666667,
            TC=1981311, TX=0, kind='NET', path='tb_xu_soc_ppa/dut/hfextclk'), 'declared source clock statistics differ')
    scopes = saif['scope_presence']
    require(set(scopes) == {'accelerator', 'cpu', 'dtcm', 'interconnect', 'itcm', 'shared'}, 'scope membership differs')
    for name, scope in scopes.items():
        require(all(type(scope[k]) is int and scope[k] >= 0 for k in ('signal_count', 'total_toggles', 'unknown_bit_ticks')),
                'invalid scope statistics')
        if name != 'dtcm':
            require(scope['state'] == 'OBSERVED_ACTIVITY' and scope['total_toggles'] > 0, 'active scope declaration differs')
    dtcm = scopes['dtcm']
    require(dtcm['state'] == 'OBSERVED_KNOWN_STATIC_DISABLED' and dtcm['macro_count'] == 32 and dtcm['total_toggles'] == 0 and
            dtcm['unknown_bit_ticks'] > 0, 'DTCM unknown/static declaration differs')
    controls = dtcm['idle_control_evidence']
    require(len(controls) == 96 and len({r['path'] for r in controls}) == 96, 'DTCM static control membership differs')
    expected_controls = {instance + '/' + pin for instance in inventory['dtcm']['instances'] for pin in ('CEN', 'CLK', 'RET1N')}
    require({r['path'] for r in controls} == expected_controls, 'DTCM exact control set differs')
    for row in controls:
        high = row['path'].endswith(('/CEN', '/RET1N'))
        require(row == dict(path=row['path'], kind='PORT', IG=0, T0=0 if high else w['duration_ticks'],
                           T1=w['duration_ticks'] if high else 0, TC=0, TX=0), 'DTCM declared static control dwell differs')
    missing_saif = []
    for kind in ('raw_saif', 'normalized_saif'):
        record = norm[kind]
        require(not (source.root / prefix / Path(record['path']).name).exists(), 'review requires original SAIF-absent export scope')
        require(record['bytes'] > 0 and re.fullmatch('[a-f0-9]{64}', record['sha256']), 'server SAIF identity invalid')
        missing_saif.append(dict(kind=kind, **record))
    return dict(task_id=task_id, global_layer=task_id, simulator_layer=0,
                activity_window=w, layer=layer, autogroup=task['autogroup'],
                declared_scope_statistics={k: {f: v[f] for f in ('state', 'signal_count', 'total_toggles', 'unknown_bit_ticks')}
                                           for k, v in scopes.items()},
                declared_alias_unknown_bit_ticks=norm['alias_unknown_bit_ticks'],
                server_only_saif_identities=missing_saif), inputs


def review(source):
    top = source.json('result.json')
    require(top['schema'] == 'xu-s2c-isolated-task-activity-v1' and
            top['status'] == 'COLLECTED_12_TASKS_REVIEW_PENDING' and top['taskset_complete'] is True and
            top['requested_task_ids'] == list(range(12)) and len(top['tasks']) == 12, 'complete12 final status differs')
    config = top['configuration']
    require(canonical(config) == top['configuration_sha256'], 'canonical configuration SHA differs')
    require(config['source_context'] == top['source_context'] and config['tool_context'] == top['tool_context'], 'source/tool context differs')
    require(config['source_context']['source_profile']['name'] == 's2c-autogroup' and
            config['nominal_hz'] == 150000000 and config['lf_hz'] == 32768 and config['precision_fs'] == 1 and
            config['numeric_format'] == 'signed16/40/48' and config['activity_scope'] == 'tb_xu_soc_ppa.dut' and
            config['monitoring_policy'] == 'rtl_on', 'S2c numeric/clock/monitor configuration differs')
    defines = ['+define+DISABLE_SV_ASSERTION=1', '+define+ARM_UD_MODEL']
    require(config['simulator_defines'] == ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION=1'] and
            all(x in top['build_command'] for x in defines) and
            not any('INITIALIZE_MEMORY' in x or 'POWER_PINS' in x for x in top['build_command']), 'vendor model variant differs')
    build_log = source.payload['simulator/build.log'].decode('utf-8')
    require(not re.search(r'Error-\[|undefined system task|unknown system task', build_log, re.I), 'build diagnostic failure')
    firmware = source.json('firmware/firmware-build.json')
    require(firmware == top['firmware_build'] == config['firmware'], 'firmware receipt differs')
    source.identity(config['firmware_build'])
    for key in ('wrapper', 'compiler_version'):
        source.identity(firmware[key])
    require(firmware['recipe'] == 's2c-cpu-legacy-33697-zero-clear-before-source-request-v1' and
            firmware['configuration'] == dict(experiment='both-unroll-no-masks', optimization='-O2',
            schedule='bias-hw-autogroup-window'), 'firmware clear/schedule configuration differs')
    mapping = source.json('simulator/sram-pin-alias/xu_candidate_sram_activity_alias.mapping.json')
    require(mapping == config['sram_alias'] and mapping['macro_count'] == 336 and mapping['alias_bit_count'] == 22512 and
            mapping['pin_widths'] == PIN_WIDTHS and len(mapping['macros']) == 336 and sum(PIN_WIDTHS.values()) == 67,
            'mapping/config SRAM geometry differs')
    source.identity(config['sram_alias_mapping'])
    source.identity(mapping['observer_source'])
    require(Counter(r['group'] for r in mapping['macros']) == Counter(GROUPS), 'mapping macro groups differ')
    require(len({r['instance'] for r in mapping['macros']}) == 336, 'mapping duplicate macro')
    for record in config['rtl_sources']:
        if '/' + CAMPAIGN + '/' in record['path']:
            source.identity(record)
    filelist = source.payload['simulator/rtl.f'].decode('ascii').splitlines()
    require(filelist == [r['path'] for r in config['rtl_sources']], 'compiled RTL file list differs')
    tasks, manifests = [], {}
    for task_id in range(12):
        task, inputs = check_task(source, top, task_id, mapping)
        tasks.append(task)
        manifests[str(task_id)] = inputs
    require(canonical(manifests) == top['taskset_inputs_sha256'], 'canonical full12 input manifests SHA differs')
    require(len(top['original_task_vectors']) == 12 and len(top['fixture']['files']) == 48, 'fixture membership differs')
    source.verify()
    return dict(schema='xu-s2c-actual-activity12-offline-review-v1',
                status='EXPORTED_12_TASK_LOG_RECEIPT_CONSISTENCY_PASS_SAIF_CONTENTS_NOT_REPLAYED',
                campaign=CAMPAIGN, owner='xu',
                original_directory=str(source.root), original_export_manifest=str(source.manifest),
                original_export_manifest_sha256=EXPORT_MANIFEST_SHA,
                configuration_sha256=top['configuration_sha256'], source_context=top['source_context'],
                tool_context=top['tool_context'], netlist_declared_identity=config['netlist'],
                constraints_declared_identity=config['constraints'], fixture=top['fixture'],
                exported_file_count=len(source.records), task_count=12,
                aggregate=dict(formal_elapsed_cycles=sum(t['activity_window']['formal_elapsed_cycles'] for t in tasks),
                               formal_inclusive_cycles=sum(t['activity_window']['formal_inclusive_cycles'] for t in tasks),
                               duration_ticks=sum(t['activity_window']['duration_ticks'] for t in tasks),
                               accepted_pretask_clear_writes=12 * 33697, task_outputs=12 * 25344),
                checks=['Original63 file membership, bytes and SHA256 against fixed export53 manifest, before/after review.',
                        'Top/per-task results; canonical configuration and all12 input-manifest hashes; firmware/mapping/RTL identities.',
                        'Exactly one required boundary/pass event per log; isolated TASKS=1 commands; actual reset, clear, FIFO, uploads.',
                        'Formal source-request/final-Y-retire span, legacy diagnostics, clear separation, clock checks and per-layer counters.',
                        'All48 tensor declared identities agree; all12 normalization receipts and24 SAIF declared identities agree.',
                        'Declared336 macro membership,22512 alias bits,137439 signals, source clock and96 DTCM control dwell records.'],
                tasks=tasks,
                limitations=['24 raw/normalized SAIF files are not exported locally. Their server path/bytes/SHA are identities only; no SAIF parsing, per-bit dwell/TC comparison, normalization replay, or independent activity recomputation is claimed.',
                             'The48 original/materialized tensor bodies, executable, firmware ELF/image, mapped netlist and SDC are absent from this63-file export; their identities are checked between receipts, not recomputed from absent files.',
                             'DTCM static known controls and zero declared toggles coexist with retained internal unknown dwell; this gives no zero-power inference.',
                             'Pretask33697-write clear lies outside each task SAIF; no clear-phase SAIF or energy was measured.',
                             'One real checkpoint silence sample across12 independent FFN1 layers; no official accuracy, STA, equivalence, mapped PT annotation, Liberty power, energy or contest qualification is established.'],
                verified_original_files=[dict(path=name, bytes=source.records[name]['bytes'], sha256=source.records[name]['sha256'])
                                         for name in sorted(source.records)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-dir', type=Path, required=True)
    parser.add_argument('--export-manifest', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'new output path required; historical evidence is immutable')
    source = Inputs(args.original_dir, args.export_manifest or args.original_dir.parent / 'manifest.json')
    result = review(source)
    result['checker'] = dict(path=str(Path(__file__).resolve()), sha256=digest(Path(__file__).read_bytes()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status=result['status'], tasks=result['task_count'], files=result['exported_file_count'],
                          server_only_saif_count=sum(len(t['server_only_saif_identities']) for t in result['tasks'])), sort_keys=True))


if __name__ == '__main__':
    main()
