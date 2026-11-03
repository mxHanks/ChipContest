#!/usr/bin/env python3
"""Summarize measured xu development-SoC cycles at a conditional frequency."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xu_firmware_contract as contract

PHASES = contract.PHASES
MACS_PER_TASK = contract.MACS_PER_TASK
PES = contract.PES


def summarize(result, frequency_mhz):
    if not math.isfinite(frequency_mhz) or frequency_mhz <= 0:
        raise ValueError('frequency must be finite and positive')
    if result.get('status') != 'PASS' or result.get('mode') != 'real':
        raise ValueError('a passing real-task simulation is required')
    config = contract.configuration_from_result(result)
    variant = result.get('accel_variant', 'pe8')
    if variant not in ('pe8', 'pe32', 'pe32-bank128') or (config['schedule'] == 'bias-hw-pe32-autogroup-window' and variant == 'pe8'):
        raise ValueError('invalid physical accelerator variant')
    pes = 32 if variant in ('pe32', 'pe32-bank128') else PES
    explicit = 'firmware_schedule' in result
    layers = result['layers']
    if (type(result['tasks']) is not int or not 1 <= result['tasks'] <= 12 or
            not layers or [x['layer'] for x in layers] != list(range(result['tasks']))):
        raise ValueError('incomplete or unordered layers')
    for field, expected in [('outputs', result['tasks'] * contract.OUTPUTS_PER_TASK),
                            ('write_words', result['tasks'] * contract.task_contract(config['schedule'])['shared_writes'])]:
        if (explicit or field in result) and result.get(field) != expected:
            raise ValueError('incomplete result ' + field)
    if any('performance' in x for x in layers) and not all('performance' in x for x in layers):
        raise ValueError('incomplete performance profiles')
    if (explicit or config['schedule'] != 'baseline') and not all('performance' in x for x in layers):
        raise ValueError('explicit firmware schedule requires complete performance profiles')
    if pes == 32:
        expected_activity = [dict(layer=layer['layer'], physical_pes=32,
            mac_beats=contract.task_contract(config['schedule'])['mac_fire'],
            lane_macs=MACS_PER_TASK, useful_macs=MACS_PER_TASK) for layer in layers]
        if result.get('pe_activity') != expected_activity:
            raise ValueError('missing or inconsistent actual enabled-lane activity')
    elif result.get('pe_activity', []) != []:
        raise ValueError('unexpected physical PE activity')
    hz = frequency_mhz * 1e6
    rows = []
    for layer in layers:
        cycles = layer['cycles']
        if type(cycles) is not int or cycles <= 0:
            raise ValueError('invalid cycle count')
        row = dict(layer=layer['layer'], cycles=cycles,
                   firmware_cycles=layer['firmware_cycles'],
                   conditional_latency_ms=cycles / hz * 1000,
                   conditional_tasks_per_second=hz / cycles,
                   conditional_gmac_per_second=MACS_PER_TASK / cycles * hz / 1e9,
                   end_to_end_peak_fraction=MACS_PER_TASK / (cycles * pes))
        perf = layer.get('performance')
        if perf is not None:
            contract.validate_performance(perf, cycles, config['schedule'])
            row['counters'] = perf
            row['phase_fraction'] = {p: perf[p] / cycles for p in PHASES}
            row['mac_active_fraction'] = perf['mac_fire'] / cycles
            row['busy_fraction'] = perf['busy'] / cycles
        rows.append(row)
    total = sum(x['cycles'] for x in rows)
    count = len(rows)
    aggregate = dict(tasks=count, cycles=total, macs=count * MACS_PER_TASK,
                     conditional_total_latency_ms=total / hz * 1000,
                     conditional_mean_latency_ms=total / count / hz * 1000,
                     conditional_tasks_per_second=count * hz / total,
                     conditional_gmac_per_second=count * MACS_PER_TASK / total * hz / 1e9,
                     conditional_gops=count * MACS_PER_TASK * 2 / total * hz / 1e9,
                     end_to_end_peak_fraction=count * MACS_PER_TASK / (total * pes))
    if all('counters' in x for x in rows):
        keys = rows[0]['counters'].keys()
        aggregate['counters'] = {k: sum(x['counters'][k] for x in rows) for k in keys}
        aggregate['phase_fraction'] = {p: aggregate['counters'][p] / total for p in PHASES}
    return dict(schema='xu-development-perf-v1', frequency_mhz=frequency_mhz,
                firmware_schedule=config['schedule'], firmware_opt=config['optimization'],
                firmware_experiment=config['experiment'],
                firmware_build=result.get('firmware_build'),
                transaction_contract=contract.task_contract(config['schedule']),
                source_identity={key:result[key] for key in [
                    'main_commit','e203_commit','runner_sha256','contract_sha256',
                    'firmware_sha256','firmware_elf_sha256','firmware_image_sha256',
                    'source_sha256','vectors','accel_variant','pe_activity','tools','versions','simulator_sha256','log_sha256']
                    if key in result},
                frequency_status='conditional conversion; physical timing closure not established',
                scope='12 independent FFN1 layers at most; development shared SRAM with modulo-7 backpressure; '
                      'first shared input/parameter read acceptance through final Y write-response retirement; '
                      'TB/ITCM preload and between-task host loading excluded',
                ops_per_mac=2, accel_variant=variant, pes=pes, macs_per_task=MACS_PER_TASK,
                conditional_peak_gmac_per_second=pes * hz / 1e9,
                layers=rows, aggregate=aggregate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--frequency-mhz', type=float, default=150.0)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    data = args.result.read_bytes()
    report = summarize(json.loads(data.decode()), args.frequency_mhz)
    report['source_result_sha256'] = hashlib.sha256(data).hexdigest()
    report['source_result'] = str(args.result.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('PASS: ' + str(args.out))


if __name__ == '__main__':
    main()
