#!/usr/bin/env python3
"""Summarize measured xu development-SoC cycles at a conditional frequency."""
import argparse
import hashlib
import json
import math
from pathlib import Path

PHASES = ['w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other']
MACS_PER_TASK = 99 * 64 * 256
PES = 8


def summarize(result, frequency_mhz):
    if not math.isfinite(frequency_mhz) or frequency_mhz <= 0:
        raise ValueError('frequency must be finite and positive')
    if result.get('status') != 'PASS' or result.get('mode') != 'real':
        raise ValueError('a passing real-task simulation is required')
    layers = result['layers']
    if not layers or [x['layer'] for x in layers] != list(range(result['tasks'])):
        raise ValueError('incomplete or unordered layers')
    if any('performance' in x for x in layers) and not all('performance' in x for x in layers):
        raise ValueError('incomplete performance profiles')
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
                   end_to_end_peak_fraction=MACS_PER_TASK / (cycles * PES))
        perf = layer.get('performance')
        if perf is not None:
            if any(type(v) is not int or v < 0 for v in perf.values()):
                raise ValueError('invalid performance counters')
            if sum(perf[p] for p in PHASES) != cycles:
                raise ValueError('phase cycles do not cover the measured interval')
            if perf['mac_fire'] * PES != MACS_PER_TASK:
                raise ValueError('MAC activity does not match the task work')
            if (not perf['mac_fire'] <= perf['busy'] <= cycles or
                    perf['starts'] != 3168 or perf['dones'] != 3168 or
                    perf['shared_reads'] != 73408 or perf['shared_writes'] != 50688 or
                    any(v > cycles for v in perf.values())):
                raise ValueError('performance work or activity counters are inconsistent')
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
                     end_to_end_peak_fraction=count * MACS_PER_TASK / (total * PES))
    if all('counters' in x for x in rows):
        keys = rows[0]['counters'].keys()
        aggregate['counters'] = {k: sum(x['counters'][k] for x in rows) for k in keys}
        aggregate['phase_fraction'] = {p: aggregate['counters'][p] / total for p in PHASES}
    return dict(schema='xu-development-perf-v1', frequency_mhz=frequency_mhz,
                frequency_status='conditional conversion; physical timing closure not established',
                scope='12 independent FFN1 layers at most; development shared SRAM with modulo-7 backpressure; '
                      'first shared input/parameter read acceptance through final Y write-response retirement; '
                      'TB/ITCM preload and between-task host loading excluded',
                ops_per_mac=2, pes=PES, macs_per_task=MACS_PER_TASK,
                conditional_peak_gmac_per_second=PES * hz / 1e9,
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
