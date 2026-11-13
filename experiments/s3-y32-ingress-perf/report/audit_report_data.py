#!/usr/bin/env python3
"""Export report data from frozen raw logs; never run synthesis or simulation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
E203 = ROOT / 'third-party/e203_hbirdv2'
EVIDENCE = ROOT / 'docs/validation/s3-y32-ingress-perf-20261113'
OUTPUT = ROOT / 'docs/validation/s3-y32-ingress-perf-report-20261113'
BASE = 'bde23ba9d06c57f6536d9992b3cd3427daccd9f8'
CHILD = '5470c5650f2d11d16e7c52cc96626d21030a3973'
HZ = 150_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def write_csv(path, rows):
    require(bool(rows), f'empty CSV {path}')
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=E203)


def records(text, marker):
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        if line == marker or line.startswith(marker + ' '):
            fields = line[len(marker):].strip().split()
            require(all(re.fullmatch(r'\w+=\d+', field) for field in fields), f'malformed {marker}:{number}')
            values = {key: int(value) for key, value in (field.split('=') for field in fields)}
            require(len(values) == len(fields), f'duplicate field {marker}:{number}')
            result.append((number, values))
    return result


def audit_run(name, tasks):
    log_path = EVIDENCE / f'{name}-simulation.log'
    result_path = EVIDENCE / f'{name}-result.json'
    text, result = log_path.read_text(), load(result_path)
    require(result['status'] == 'PASS', f'{name}: result is not PASS')
    require(not re.search(r'^.*(?:%Error|FATAL|TEST_FAIL|Time Out|timeout)', text, re.M | re.I), f'{name}: failure marker')
    marker_keys = dict(TASK_PASS=None, WINDOW='window', COUNTS='counters', CHANNEL='channel', ENDPOINT='endpoint')
    groups = {key: records(text, 'C32_' + key) for key in marker_keys}
    require(all(len(group) == tasks for group in groups.values()), f'{name}: missing/duplicate layer groups')
    loader = records(text, 'C32_LOADER_PIPELINE')
    require(len(loader) in (0, tasks), f'{name}: partial loader records')
    require(len(result['layers']) == tasks, f'{name}: JSON layer count')
    rows = []
    for layer in range(tasks):
        raw = {key: group[layer][1] for key, group in groups.items()}
        for key, item in raw.items():
            require(item['layer'] == layer, f'{name}: {key} layer order')
            reference = result['layers'][layer] if marker_keys[key] is None else result['layers'][layer][marker_keys[key]]
            require(all(reference.get(k) == v for k, v in item.items()), f'{name}: JSON/raw {key} mismatch')
        item, window, count, channel, endpoint = (raw[key] for key in marker_keys)
        require(item['rows'] == 8 and item['outputs'] == 25344, f'{name}: output/mode scope')
        durations = dict(total=window['last_y_response'] - window['clear_request'] + 1,
                         clear=window['clear_done'] - window['clear_request'] + 1,
                         loading=window['load_finish'] - window['load_begin'] + 1,
                         dma_payload=window['last_y_response'] - window['first_request'] + 1,
                         load_to_y=window['last_y_response'] - window['load_begin'] + 1,
                         start_to_done=window['done'] - window['start'] + 1)
        require(all(item[key] == value for key, value in durations.items()), f'{name}: window duration mismatch')
        require(window['clear_request'] <= window['clear_done'] < window['load_begin'] <= window['load_finish'] <
                window['start'] <= window['first_request'] <= window['first_accept'] <= window['last_y_response'] < window['done'],
                f'{name}: window ordering')
        after_clear = window['load_begin'] - window['clear_done'] - 1
        after_source = window['first_request'] - window['load_finish'] - 1
        gap = item['total'] - item['clear'] - item['loading'] - item['dma_payload']
        require(gap == after_clear + after_source, f'{name}: nonoverlapping phase accounting')
        expected_counts = dict(reads=15040, w_reads=8192, bias_reads=512, x_reads=6336,
                               writes=25344, write_responses=25344, requests=40384, responses=40384,
                               pops=3168, macs=26624, mmio_writes=6)
        require(all(count[key] == value for key, value in expected_counts.items()), f'{name}: DMA counters')
        require(count['mmio_reads'] > 0 and 1 <= channel['max_outstanding'] <= 4, f'{name}: CPU or DMA occupancy')
        require(endpoint['requests'] == endpoint['responses'] and endpoint['outstanding'] == 0 and
                endpoint['source_reads'] == endpoint['source_writes'] == 15040 and
                endpoint['y_writes'] == endpoint['y_write_responses'] == 50688, f'{name}: endpoint conservation')
        pipeline = loader[layer][1] if loader else {}
        if pipeline:
            require(pipeline == result['layers'][layer]['loader_pipeline'], f'{name}: loader raw/JSON mismatch')
            require(pipeline['layer'] == layer and pipeline['requests'] == pipeline['responses'] == 15040 and
                    pipeline['outstanding'] == 0, f'{name}: loader retirement')
        row = dict(run=name, layer=layer, outputs=item['outputs'], total_cycles=item['total'], clear_cycles=item['clear'],
                   source_cycles=item['loading'], dma_cycles=item['dma_payload'], control_gap_cycles=gap,
                   after_clear_gap_cycles=after_clear, after_source_gap_cycles=after_source,
                   tasks_per_second_at_assumed_150mhz=HZ / item['total'],
                   dma_reads=count['reads'], dma_writes=count['writes'], dma_responses=count['responses'],
                   pops=count['pops'], mac_steps=count['macs'], mmio_reads=count['mmio_reads'],
                   dma_peak_outstanding=channel['max_outstanding'], loader_mode=pipeline.get('mode', 'baseline_serial_not_instrumented'),
                   loader_peak_outstanding=pipeline.get('max_outstanding', ''),
                   task_log_line=groups['TASK_PASS'][layer][0], window_log_line=groups['WINDOW'][layer][0],
                   counts_log_line=groups['COUNTS'][layer][0], channel_log_line=groups['CHANNEL'][layer][0],
                   endpoint_log_line=groups['ENDPOINT'][layer][0])
        row.update(window)
        rows.append(row)
    clears = records(text, 'C32_PHYSICAL_CLEAR_PASS')
    begins = records(text, 'C32_PHYSICAL_CLEAR_BEGIN')
    require(len(clears) == len(begins) == tasks + 1, f'{name}: warmup + physical-clear count')
    for call, ((_, begin), (_, clear)) in enumerate(zip(begins, clears), 1):
        require(clear['call'] == begin['call'] == call and clear['warmup'] == begin['warmup'] == int(call == 1), f'{name}: clear identity')
        expected = dict(W=16384, BIAS=768, X=16384, total16bit_writes=33536, physical_cycles=1027,
                        X_REGS=0, X_MACROS=16, X_USED_WORDS=1024, ACC=64, ENGINE_RESULT=64,
                        FIFO=128, BIAS_CACHE=16, DMA_SNAPSHOT=1, all_addresses=1, all_payload_zero=1)
        require(all(clear[key] == value for key, value in expected.items()), f'{name}: physical-clear payload/address count')
        require(begin['observed_last_public_writes'] == 1, f'{name}: clear public prestate')
        if call > 1:
            require(all(begin[key] > 0 for key in ('nonzero_W', 'nonzero_BIAS', 'nonzero_X')), f'{name}: clean prestate')
    require(records(text, 'C32_SOC_PASS') == [(next(i for i, line in enumerate(text.splitlines(), 1) if line.startswith('C32_SOC_PASS ')),
                                            dict(tasks=tasks, rows=8, outputs=tasks*25344, writes=tasks*25344))], f'{name}: SoC completion')
    require(len(records(text, 'C32_WARMUP_TASK_PASS')) == 1 and
            re.findall(r'^C32_WARMUP_DONE.*$', text, re.M) == ['C32_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1'], f'{name}: excluded warmup')
    clocks = records(text, 'C32_CLOCK')
    require(len(clocks) == 1 and clocks[0][1] == result['measured_clock'] and
            clocks[0][1]['measured_hf_period_fs'] == 6666666 and
            clocks[0][1]['measured_lf_period_fs'] == 30517578126, f'{name}: stimulus clock identity')
    aggregate = dict(run=name, tasks=tasks, outputs=sum(row['outputs'] for row in rows))
    for key in ('total_cycles', 'clear_cycles', 'source_cycles', 'dma_cycles', 'control_gap_cycles'):
        aggregate[key] = sum(row[key] for row in rows)
        aggregate['mean_' + key] = aggregate[key] / tasks
    aggregate['tasks_per_second_at_assumed_150mhz'] = HZ * tasks / aggregate['total_cycles']
    for source, dest in [('total_cycles', 'total_cycles'), ('clear_cycles', 'clear_cycles'),
                         ('source_loading_cycles', 'source_cycles'), ('dma_payload_cycles', 'dma_cycles')]:
        require(result[source] == aggregate[dest], f'{name}: total {source} raw/JSON mismatch')
    require(result['outputs'] == aggregate['outputs'], f'{name}: output total raw/JSON mismatch')
    aggregate['physical_clear_writes_16bit_per_task'] = 33536
    aggregate['raw_log'] = str(log_path.relative_to(ROOT))
    aggregate['result_json'] = str(result_path.relative_to(ROOT))
    return rows, aggregate, result


def source_identity():
    require(git('rev-parse', 'HEAD').decode().strip() == CHILD, 'wrong frozen optimized child')
    require(not git('status', '--porcelain').strip(), 'hardware worktree is dirty')
    names = git('ls-tree', '-r', '--name-only', BASE, 'rtl/e203').decode().splitlines()
    actual = {str(path.relative_to(E203)) for path in (E203/'rtl/e203').rglob('*') if path.is_file()}
    require(set(names) == actual, 'production source-set drift')
    changed = [name for name in names if git('show', f'{BASE}:{name}') != (E203/name).read_bytes()]
    require(set(changed) == {'rtl/e203/perips/xu_matrix_dma_sysbus32.sv', 'rtl/e203/subsys/xu_systembus_ingress32.v'}, 'unexpected RTL change')
    manifest = load(EVIDENCE/'cpu-source-manifest.json')
    mismatch, missing, exact = [], [], []
    for relative, expected in manifest['files'].items():
        if not relative.startswith('rtl/'):
            continue
        path = E203/'rtl/e203'/relative[4:]
        (missing if not path.is_file() else exact if sha(path) == expected else mismatch).append(relative)
    require(len(exact) == 167 and mismatch == ['rtl/perips/mem_1024x16.sv'] and set(missing) == {
        'rtl/perips/generic_ramsp_non_ppa.sv', 'rtl/perips/tile_physical_observer.sv',
        'rtl/perips/xu_compliance_shared_sram.sv', 'rtl/perips/xu_shared_icb_sram.sv'}, 'captured CPU source correspondence changed')
    firmware = ROOT/'experiments/s3-y32-ingress-perf/cpu_main.c'
    require(firmware.read_bytes() == (ROOT/'experiments/s3-y32-compliant32/validation/sysbus32_main.c').read_bytes(), 'CPU firmware source drift')
    return dict(schema='s3-ingress-perf-report-source-identity-v1', child_commit=CHILD, frozen_reference_child=BASE,
                production_rtl_files_compared=len(names), production_rtl_changed=changed,
                cpu_captured_rtl_byte_identical_to_child=len(exact), cpu_captured_model_replacement=mismatch,
                cpu_captured_extra_model_and_observer_files=missing,
                model_transform_receipt=manifest['typename_only_shared_macro_transforms'],
                firmware_c_sha256=sha(firmware),
                capture_note='Full12 ran before the two RTL edits were committed; captured per-file hashes bind those exact bytes to child 5470. The recorded bde23ba HEAD plus dirty diff is not an alternate hardware candidate.',
                platform_note='All other production RTL files, including CPU/LSU/BIU and original mem_fab, are byte-identical to the frozen baseline.')


def storage_inventory():
    base = E203/'rtl/e203/perips'
    core = (base/'LinearTileDmaCore.sv').read_text()
    require(core.count('\n`ifdef C32_X_SRAM_SELECTED\nmodule LinearTileDmaCore(') == 1, 'X SRAM branch selector changed')
    selected = core.split('\n`ifdef C32_X_SRAM_SELECTED\nmodule LinearTileDmaCore(', 1)[1].split('\n`else\nmodule LinearTileDmaCore(', 1)[0]
    result_names = re.findall(r'\breg\s+\[40:0\]\s+(results_\d_\d_\d);', selected)
    require(len(set(result_names)) == len(result_names) == 128, 'selected FIFO shape changed')
    engines = re.findall(r'\bDotProductEngine_Acc41_Result41\s+(engines_\d)\s*\(', selected)
    require(len(engines) == len(set(engines)) == 8, 'selected engine count changed')
    result_reg = re.findall(r'\breg\s+\[40:0\]\s+(resultReg_\d);', core.split('`ifdef XU_MATRIX_DMA_SYSBUS32', 1)[0])
    require(len(result_reg) == 8, 'engine result register shape changed')
    bias = (base/'DmaBiasSramPrefetch.sv').read_text()
    bias_slots = re.findall(r'\breg\s+\[39:0\]\s+(slotData_\d_\d);', bias)
    require(len(bias_slots) == len(set(bias_slots)) == 16 and 'DmaBiasSramPrefetch bias (' in selected, 'bias slot shape/binding changed')
    dma = (base/'xu_matrix_dma_sysbus32.sv').read_text()
    require(re.search(r'reg\s+\[255:0\]\s+y_payload;', dma), 'Y snapshot changed')
    rows = [
        dict(component='core result FIFO', instance='u_xu_matrix_dma/u_core/results_{slot}_{row}_{lane}',
             organization='2 slots x 8 rows x 8 lanes x signed41', payload_bits=128*41,
             implementation='RTL registers', source='third-party/e203_hbirdv2/rtl/e203/perips/LinearTileDmaCore.sv', line=768,
             charge_scope='dma/core_fifo_and_control', qualification='result storage SRAM remediation not integrated'),
        dict(component='engine result registers', instance='u_xu_matrix_dma/u_core/engines_{0..7}/resultReg_{0..7}',
             organization='8 engines x 8 lanes x signed41', payload_bits=8*8*41,
             implementation='RTL registers', source='third-party/e203_hbirdv2/rtl/e203/perips/LinearTileDmaCore.sv', line=317,
             charge_scope='dma/engines_64pe', qualification='result storage SRAM remediation not integrated'),
        dict(component='bias prefetch slots', instance='u_xu_matrix_dma/u_core/bias/slotData_{slot}_{lane}',
             organization='2 slots x 8 lanes x signed40', payload_bits=16*40,
             implementation='RTL registers with valid/tag/epoch and hit reuse', source='third-party/e203_hbirdv2/rtl/e203/perips/DmaBiasSramPrefetch.sv', line=115,
             charge_scope='dma/bias', qualification='no-cache bias remediation not integrated'),
        dict(component='DMA Y row snapshot', instance='u_xu_matrix_dma/y_payload', organization='8 Y32 lanes', payload_bits=256,
             implementation='RTL register', source='third-party/e203_hbirdv2/rtl/e203/perips/xu_matrix_dma_sysbus32.sv', line=35,
             charge_scope='dma/dma32_frontend_and_scheduler', qualification='row-payload removal not integrated'),
    ]
    for row in rows:
        row['source_sha256'] = sha(ROOT/row['source'])
    return dict(schema='s3-ingress-perf-report-storage-v1', selected_defines=['XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM'],
                selection_note='Count only the selected X-SRAM LinearTileDmaCore branch. The file also contains an inactive register-X branch; counting both would double FIFO and engine instances.',
                payload_rows=rows, listed_result_and_bias_payload_bits=sum(row['payload_bits'] for row in rows),
                count_note='Logical declared payload capacity only; excludes accumulators, tags, valid bits, metadata, assembly registers and other control. This is neither mapped flop count nor cell area.',
                metadata=dict(dma_request_slots=4, kind_bits_per_slot=3, index_bits_per_slot=14,
                              pending_count_bits=3, read_pointer_bits=2, write_pointer_bits=2,
                              owner_slots=4, production_N2_owner_bits_per_slot=1, development_N3_owner_bits_per_slot=2),
                area_rule='All accelerator result/bias payload registers, DMA metadata/assembly/control registers and upstream ingress logic remain chargeable. Macro count does not include register payload storage.',
                compliance_note='Selection of the 1064 candidate does not establish storage-rule compliance. Result/bias remediation belongs to another unmerged candidate and its proofs cannot qualify these bytes.')


def functional_scope(symbols, output):
    if symbols is None:
        return dict(status='SOURCE_CONFIGURATION_ONLY', functional_macro_models_expected=289,
                    note='Expected shared256 + internal33 from captured adapter/configuration; generated scope file not supplied.')
    lines = symbols.read_text().splitlines()
    scopes = []
    for number, line in enumerate(lines, 1):
        if '.configure(this, name(),' not in line:
            continue
        quoted = re.findall(r'"([^\"]*)"', line)
        if len(quoted) > 1 and quoted[1] == 'macro':
            path = quoted[0]
            category = ('shared' if '.endpoint.storage.' in path else 'weights' if '.weights.' in path else
                        'bias' if '.bias.' in path else 'x' if re.search(r'\.xs_\d_\d\.', path) else 'unknown')
            scopes.append(dict(instance=path, category=category, generated_source_line=number))
    counts = {category: sum(row['category'] == category for row in scopes) for category in ('shared', 'weights', 'bias', 'x', 'unknown')}
    require(counts == dict(shared=256, weights=16, bias=1, x=16, unknown=0), 'functional model scope count changed')
    write_csv(output/'cpu-functional-macro-scopes.csv', scopes)
    return dict(status='LOCAL_GENERATED_MODEL_SCOPE_COUNTED', generated_source=str(symbols), generated_source_sha256=sha(symbols),
                counts=counts, total=289, cpu_ram='existing behavioral ITCM/DTCM models; no 64 CPU macro models in this run',
                evidence_note='Generated Verilator scope inventory corroborates configuration only. No gate-level activity, timing, area, or power is established.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--functional-symbols', type=Path)
    parser.add_argument('--ppa-root', type=Path, help='Optional current N3 sealed preparation; records identity only, never takes PPA results.')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    all_rows, aggregate, results = [], [], {}
    for name, tasks in [('baseline', 12), ('full12', 12), ('serialized-loader', 1), ('dma-first-wait31', 1), ('load-first-wait31', 1)]:
        rows, total, result = audit_run(name, tasks)
        all_rows.extend(rows)
        aggregate.append(total)
        results[name] = result
    baseline, optimized = aggregate[:2]
    require(baseline['total_cycles'] == 3568690 and optimized['total_cycles'] == 1691172, 'frozen full12 cycle totals changed')
    require(all((row['total_cycles'], row['clear_cycles'], row['source_cycles'], row['dma_cycles'], row['control_gap_cycles']) ==
                (140931, 1028, 42114, 97729, 60) for row in all_rows if row['run'] == 'full12'), 'optimized layer phases changed')
    image_hashes = {result['firmware']['image_sha256'] for result in results.values()}
    require(image_hashes == {'7f5e794c54680e0249fdb6780b3f0254139e1633c3acb76cc021db240abb1905'}, 'loaded firmware image mismatch')
    for name in ('dma_day_main.c', 'firmware/start.S', 'firmware/link.ld'):
        require(len({result['firmware']['source_sha256'][name] for result in results.values()}) == 1, f'firmware source {name} differs across runs')
    identity, storage = source_identity(), storage_inventory()
    write_csv(out/'per-layer-cycles.csv', all_rows)
    write_csv(out/'run-aggregate.csv', aggregate)
    plot_rows = []
    for total in aggregate:
        for field, phase in [('clear_cycles', 'physical clear'), ('source_cycles', 'complete source loading'),
                             ('dma_cycles', 'DMA reads/compute/Y-response retirement'), ('control_gap_cycles', 'control gaps')]:
            plot_rows.append(dict(run=total['run'], tasks=total['tasks'], phase=phase,
                                  total_cycles=total[field], mean_cycles_per_task=total[field]/total['tasks']))
    write_csv(out/'phase-plot-data.csv', plot_rows)
    write_json(out/'source-identity.json', identity)
    write_json(out/'storage-inventory.json', storage)
    write_csv(out/'storage-inventory.csv', storage['payload_rows'])
    geometry = [dict(component=name, full_soc_PPA_macros=count, original_CPU_functional_macro_models=functional,
                     note=note) for name, count, functional, note in [
        ('CPU ITCM', 32, 0, 'CPU simulation retains behavioral RAM'),
        ('CPU DTCM', 32, 0, 'CPU simulation retains behavioral RAM'),
        ('shared 512 KiB endpoint', 256, 256, '32-bit endpoint; two 16-bit lanes per bank'),
        ('weights', 16, 16, 'internal physical macro owners'), ('bias', 1, 1, 'bias macro plus register prefetch slots'),
        ('X', 16, 16, 'physical 16-macro double set; 1024 used INT16 words'),
        ('result/Y buffers', 0, 0, 'register FIFO/engine result registers/DMA snapshot, not SRAM macros')]]
    write_csv(out/'macro-geometry.csv', geometry)
    symbols = args.functional_symbols
    if symbols is None:
        default_symbols = ROOT/'build/ingress-perf-20261113/cpu-task0-r2/simulator/Vtb_sysbus32_soc__Syms.cpp'
        symbols = default_symbols if default_symbols.is_file() else None
    cpu_scope = functional_scope(symbols, out)
    write_json(out/'cpu-functional-model-scope.json', cpu_scope)
    saved = load(EVIDENCE/'summary.json')
    used = {f'{name}-{kind}' for name in results for kind in ('result.json', 'simulation.log')}
    used |= {'summary.json', 'cpu-source-manifest.json', 'source-invariants.json', 'firmware-container-diff.txt',
             'checker-negative-cases.json', 'endpoint-throttle-probe.log', 'ingress-regression.log'}
    evidence = []
    for name in sorted(used):
        path = EVIDENCE/name
        expected = saved.get('origins', {}).get(name, {}).get('sha256')
        if expected:
            require(sha(path) == expected, f'evidence hash drift {name}')
        evidence.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path),
                             original_declared_sha256=expected, original_declared_sha256_matches=(sha(path) == expected) if expected else None))
    for name in ['LinearTileDmaCore.sv', 'DmaBiasSramPrefetch.sv', 'xu_matrix_dma_sysbus32.sv']:
        path = E203/'rtl/e203/perips'/name
        evidence.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path),
                             original_declared_sha256=None, original_declared_sha256_matches=None))
    path = E203/'rtl/e203/subsys/xu_systembus_ingress32.v'
    evidence.append(dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path),
                         original_declared_sha256=None, original_declared_sha256_matches=None))
    write_json(out/'evidence-index.json', dict(schema='s3-ingress-perf-report-evidence-index-v1', files=evidence))
    ppa_identity = dict(schema='s3-ingress-perf-report-PPA-input-identity-v1', status='NOT_IMPORTED',
                        note='Await the PPA owner same-N3-source DC/PT receipts. Old353 STA, merged374 PASS and S2 FM are excluded.')
    area = dict(schema='s3-ingress-perf-report-area-accounting-v1', status='EXPECTED_ACCOUNTING_ONLY_NO_NUMERIC_AREA',
                full_soc_macros=353, charged_internal_macros=33, excluded_reused_CPU_shared_macros=320,
                result_macros=0, result_and_bias_register_payload_bits=storage['listed_result_and_bias_payload_bits'],
                charged_scopes=['complete DMA/core including payload registers, assembly and metadata',
                                'complete upstream SystemBus ingress including N3 owner/control logic',
                                'complete NICE interface scope conservatively', 'shared endpoint standard-cell logic'],
                upper_bound='Every full-SoC standard cell plus all33 internal macros; excludes only320 reused CPU/shared macros',
                official_mm2_and_macro_pricing='UNRESOLVED; no contest area PASS follows from raw library area sums',
                note='Declared register payload bits are not cell area; preserve full mapped leaf accounting, not a hand subtraction of result/bias buffers.')
    if args.ppa_root:
        ppa = args.ppa_root.resolve()
        manifest, sources = load(ppa/'manifest.json'), load(ppa/'source-manifest.json')
        require(manifest['hardware_profile'] == sources['hardware_profile'] == 'sysbus32-x-sram-353-dev-n3', 'wrong N3 PPA profile')
        require(manifest['source_manifest_sha256'] == sha(ppa/'source-manifest.json'), 'PPA manifest binding')
        require(len(sources['ordered_compile_sources']) == manifest['source_count'] == 159, 'PPA compile source count')
        catalog = load(ppa/'package-files.json')
        require(len(catalog) == 186, 'PPA input catalog count')
        for relative, expected_hash in catalog.items():
            require(sha(ppa/relative) == expected_hash, f'PPA input catalog drift {relative}')
        for entry in sources['ordered_compile_sources']:
            require(sha(ppa/entry['path']) == entry['sha256'], f'PPA compile input drift {entry["path"]}')
        ppa_identity = dict(schema='s3-ingress-perf-report-PPA-input-identity-v1', status='SEALED_INPUT_IDENTITY_ONLY', root=str(ppa), manifest_sha256=sha(ppa/'manifest.json'),
                            source_manifest_sha256=sha(ppa/'source-manifest.json'), hardware_profile=manifest['hardware_profile'],
                            top=manifest['top'], defines=manifest['defines'], source_count=manifest['source_count'],
                            package_files_catalog_sha256=sha(ppa/'package-files.json'), package_input_hashes_verified=186,
                            expected_geometry=manifest['expected_geometry'], production_test_loader=manifest.get('production_test_loader'),
                            declared_status=manifest['status'], sealed_compile_source_hashes_verified=159,
                            N3_development_loader_extra_top_port_bits=106,
                            no_DC_STA_FM_area_or_power_verdict_imported=True, hardware_sources_verified_against_child={})
        top_path = ppa/'source/ppa/xu_soc_sysbus32_ppa_top.sv'
        top_header = top_path.read_text().split('// This clock should', 1)[0]
        loader_ports = re.findall(r'\b(input|output)\s+(?:\[(\d+):0\]\s+)?(sysbus_load_\w+)', top_header)
        require(len(loader_ports) == 10 and sum(int(width)+1 if width else 1 for _, width, _ in loader_ports) == 106,
                'N3 development top interface changed')
        ppa_identity['development_PPA_top_sha256'] = sha(top_path)
        for basename in ('xu_matrix_dma_sysbus32.sv', 'xu_systembus_ingress32.v', 'LinearTileDmaCore.sv', 'DmaBiasSramPrefetch.sv'):
            matches = [entry for entry in sources['ordered_compile_sources'] if Path(entry['path']).name == basename]
            require(len(matches) == 1, f'PPA input missing {basename}')
            path = ppa/matches[0]['path']
            original = E203/'rtl/e203'/('subsys' if basename == 'xu_systembus_ingress32.v' else 'perips')/basename
            require(sha(path) == matches[0]['sha256'] == sha(original), f'PPA source does not match1064 {basename}')
            ppa_identity['hardware_sources_verified_against_child'][basename] = sha(path)
        synth = ppa/'synth.tcl'
        area.update(sealed_synthesis_source=str(synth), sealed_synthesis_source_sha256=sha(synth),
                    sealed_synthesis_area_guard_lines=[57, 58, 59, 77, 78, 79, 80, 97, 106, 111, 113])
        (out/'ppa-sealed-input-manifest.json').write_bytes((ppa/'manifest.json').read_bytes())
    write_json(out/'ppa-input-identity.json', ppa_identity)
    write_json(out/'area-expected-accounting.json', area)
    transaction_count = 15040 + 15040 + 25344
    ideal_two_cycle_bound = HZ/(transaction_count*2 + 1028)
    model_throttle_bound = HZ/(transaction_count*7/3 + 1028)
    delta = {phase: baseline[phase] - optimized[phase] for phase in ('total_cycles', 'clear_cycles', 'source_cycles', 'dma_cycles', 'control_gap_cycles')}
    require(delta['total_cycles'] == sum(value for key, value in delta.items() if key != 'total_cycles'), 'speedup phase sum')
    summary = dict(schema='s3-ingress-perf-report-data-audit-v1', status='RAW_LOG_AND_SOURCE_AUDIT_PASS_NOT_QUALIFICATION',
                   frequency_assumption_hz=HZ, source_child=CHILD, runs=aggregate,
                   comparison=dict(baseline_tasks_per_second=baseline['tasks_per_second_at_assumed_150mhz'],
                                   optimized_tasks_per_second=optimized['tasks_per_second_at_assumed_150mhz'],
                                   throughput_factor=baseline['total_cycles']/optimized['total_cycles'],
                                   cycles_reduction_percent=100*(1-optimized['total_cycles']/baseline['total_cycles']),
                                   full12_cycle_savings_by_phase=delta),
                   counting_window=dict(begin='accepted accelerator physical clear request', end='last Y32 write response retirement',
                                        inclusive_cycles=True, warmup='one completed layer, excluded from twelve principal layers',
                                        source='all X/W/bias reloaded each task; 15040 real shared-endpoint source writes',
                                        included=['physical clear', 'source writes and responses', 'CPU control and polls in window', 'DMA reads', 'compute', 'Y writes and final response'],
                                        outside=['Y poison setup', 'post-task golden/readback validation']),
                   scope=dict(loading='development third upstream SystemBus test-loader source, maximum4 ordered requests; not GPIO-to-CPU production loading',
                              cpu='real CPU executes unchanged C/start/linker image; CPU RAM stays behavioral in this functional simulation',
                              full_soc_PPA_macro_geometry_expected=353, CPU_functional_macro_models=289,
                              arithmetic='current exact Y32 comparison against fixed-point golden on this twelve-layer exported vector set',
                              public600_NRMSE='NOT_IMPORTED: no current candidate same-operation proof was added by this data audit',
                              achieved_frequency_STA='NOT_ESTABLISHED_BY_SIMULATION', current_PPA='SEPARATE_SAME_SOURCE_RESULTS_REQUIRED',
                              current_FM='NOT_RUN_BY_THIS_AUDIT; no old S2 or merged374 proof imported',
                              storage='original result register FIFO, engine result registers, reusable bias slots and DMA row snapshot remain'),
                   firmware_loaded_image_sha256=next(iter(image_hashes)),
                   bandwidth_estimates=dict(shared_endpoint_payload_transactions_per_task=transaction_count,
                                            ideal_two_cycles_per_transaction_tasks_per_second=ideal_two_cycle_bound,
                                            model_seven_over_three_cycles_per_transaction_tasks_per_second=model_throttle_bound,
                                            measured_fraction_of_model_estimate=optimized['tasks_per_second_at_assumed_150mhz']/model_throttle_bound,
                                            assumptions='optimistic bandwidth arithmetic only, physical clear1028 added; omits CPU polling/control/compute gaps, no physical SRAM timing proof'),
                   attribution='The serialized-loader task0 control isolates a material loader scheduling benefit; the entire2.1102x cannot be assigned to owner-depth alone. Controls are one-task results, not full12 campaigns.',
                   script_sha256=sha(Path(__file__)))
    write_json(out/'audit-summary.json', summary)
    checksums = [f'{sha(path)}  {path.name}' for path in sorted(out.iterdir()) if path.is_file() and path.name != 'SHA256SUMS']
    (out/'SHA256SUMS').write_text('\n'.join(checksums)+'\n')
    print(json.dumps(dict(status=summary['status'], output=str(out), baseline_cycles=baseline['total_cycles'], optimized_cycles=optimized['total_cycles'],
                          optimized_tasks_per_second=optimized['tasks_per_second_at_assumed_150mhz'], listed_register_payload_bits=storage['listed_result_and_bias_payload_bits']), indent=2))


if __name__ == '__main__':
    main()
