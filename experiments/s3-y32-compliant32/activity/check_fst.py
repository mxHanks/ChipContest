#!/usr/bin/env python3
"""Verify native FST range, every macro pin and initial values, separately from power.

Build the native helper from installed Verilator sources (example):
 gcc -O2 -DFST_CONFIG_INCLUDE='"fst_config.h"' -I/usr/share/verilator/include/gtkwave -c /usr/share/verilator/include/gtkwave/fstapi.c -o fstapi.o
 gcc -O2 -I/usr/share/verilator/include/gtkwave -c /usr/share/verilator/include/gtkwave/fastlz.c -o fastlz.o
 gcc -O2 -I/usr/share/verilator/include/gtkwave -c /usr/share/verilator/include/gtkwave/lz4.c -o lz4.o
 g++ -O2 -std=c++17 -I/usr/share/verilator/include/gtkwave fst_inventory.cpp fstapi.o fastlz.o lz4.o -lz -o fst_inventory
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def verify(rows, window, actual_macros):
    metadata = [item for item in rows if item['type'] == 'metadata']
    complete = [item for item in rows if item['type'] == 'complete']
    if len(metadata) != 1 or len(complete) != 1:
        raise ValueError('missing/duplicate native metadata or completion')
    metadata = metadata[0]
    if (metadata['timescale'] != -15 or metadata['timezero'] != 0 or
            metadata['first'] != window['trace_first_fs'] or metadata['last'] != window['trace_last_fs'] or
            metadata['last'] - metadata['first'] != window['duration_fs']):
        raise ValueError('native FST range/precision differs from counted full task')
    scopes = [item['path'] for item in rows if item['type'] == 'scope']
    signals = [item for item in rows if item['type'] == 'signal']
    if len(scopes) != metadata['scopes'] or len(signals) != metadata['variables'] or len(set(scopes)) != len(scopes):
        raise ValueError('incomplete/duplicate native hierarchy')
    base = 'TOP.tb_sysbus32_soc'
    core = base + '.dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_perips.u_xu_matrix_dma.u_core'
    expected = {}
    for array in range(2):
        for row in range(8):
            expected[f'{core}.xs_{array}_{row}.memory.mem_ext.macro'] = 'X'
    for bank in range(8):
        for half in range(2):
            expected[f'{core}.weights.banks_{bank}.sram{half}.mem_ext.macro'] = 'W'
    expected[core + '.bias.memory.mem_ext.macro'] = 'bias'
    for bank in range(128):
        for lane in range(2):
            expected[f'{base}.endpoint.storage.macro_storage.depth_bank[{bank}].width_lane[{lane}].macro'] = 'shared'
    macro_widths = dict(CLK=1, CEN=1, GWEN=1, WEN=16, A=10, D=16, Q=16, EMA=3, EMAW=2, RET1N=1)
    cpu_base = base + '.dut.u_e203_subsys_top.u_e203_subsys_main.u_e203_cpu_top.u_e203_srams'
    cpu = {
        cpu_base + '.u_e203_dtcm_ram.u_e203_dtcm_gnrl_ram.u_sirv_sim_ram': dict(clk=1, cs=1, we=1, wem=4, addr=14, din=32, dout=32),
        cpu_base + '.u_e203_itcm_ram.u_e203_itcm_gnrl_ram.u_sirv_sim_ram': dict(clk=1, cs=1, we=1, wem=8, addr=13, din=64, dout=64),
    }
    if actual_macros == 353:
        for ram, banks, lanes in [('itcm', 8, 4), ('dtcm', 16, 2)]:
            prefix = cpu_base + f'.u_e203_{ram}_ram.u_e203_{ram}_gnrl_ram.u_sirv_sim_ram'
            for bank in range(banks):
                for lane in range(lanes):
                    expected[prefix + f'.macro_storage.depth_bank[{bank}].width_lane[{lane}].macro'] = ram
    elif actual_macros != 289:
        raise ValueError('unsupported actual macro count')
    if set(path for path in scopes if path.endswith('.macro')) != set(expected):
        raise ValueError('actual macro hierarchy differs from all expected instances')
    if set(path for path in scopes if path.endswith('.u_sirv_sim_ram')) != set(cpu):
        raise ValueError('CPU behavioral RAM inventory differs')
    initial_rows = [item for item in rows if item['type'] == 'initial']
    initial = {item['handle']: item for item in initial_rows}
    if len(initial) != len(initial_rows):
        raise ValueError('duplicate initial handle values')
    by_scope = {}
    for signal in signals:
        name = signal['name'].split(' ', 1)[0]
        if signal['scope'] in expected and name in macro_widths or signal['scope'] in cpu and name in cpu[signal['scope']]:
            if name in by_scope.setdefault(signal['scope'], {}):
                raise ValueError('duplicate required pin declaration')
            by_scope[signal['scope']][name] = signal
    wanted = set()
    inventory = {}
    for path, widths in {**{path: macro_widths for path in expected}, **cpu}.items():
        pins = by_scope.get(path, {})
        if set(pins) != set(widths):
            raise ValueError('missing required pins: ' + path)
        inventory[path] = {}
        for name, width in widths.items():
            signal = pins[name]
            value = initial.get(signal['handle'])
            if (signal['width'] != width or value is None or value['time'] != metadata['first'] or
                    len(value['value']) != width or any(ch not in '01xzXZ' for ch in value['value'])):
                raise ValueError('invalid/missing declared pin initial value: ' + path + '.' + name)
            wanted.add(signal['handle'])
            inventory[path][name] = dict(width=width, handle=signal['handle'], initial=value['value'])
    if wanted != set(initial) or complete[0]['initial_handles'] != len(wanted) or complete[0]['required_unique_handles'] != len(wanted):
        raise ValueError('required/native initial handle inventories differ')
    groups = ('X', 'W', 'bias', 'shared', 'itcm', 'dtcm') if actual_macros == 353 else ('X', 'W', 'bias', 'shared')
    counts = {name: list(expected.values()).count(name) for name in groups}
    return dict(metadata=metadata, macro_groups=counts, actual_macros=actual_macros, required_macro_ports=actual_macros*10,
                cpu_logical_models=2, required_cpu_logical_ports=14, required_unique_handles=len(wanted),
                inventory=inventory, cpu_physical_macro_ports=('ACTUAL_GENERIC_MODEL_PORTS_CAPTURED' if actual_macros == 353 else 'NOT_CAPTURED_NOT_INFERRED'),
                qualification='NOT_POWER_READY_REQUIRES_FINAL_NETLIST_MAPPING_AND_CPU_MACRO_ACTIVITY')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--native-reader', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.run = args.run.resolve()
    args.out = args.out.resolve()
    args.native_reader = args.native_reader.resolve()
    if args.out.exists():
        parser.error('evidence output must be new')
    args.out.mkdir(parents=True)
    result = dict(schema='compliant32-native-fst-port-audit-v1', status='RUNNING',
                  created_at=datetime.now(timezone.utc).isoformat(), run=str(args.run),
                  run_result_sha256=sha(args.run / 'result.json'), native_reader_sha256=sha(args.native_reader),
                  checker_sha256=sha(Path(__file__)), layers=[])
    try:
        run = json.loads((args.run / 'result.json').read_text())
        if run.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY':
            raise ValueError('functional activity run is not PASS')
        windows = [json.loads(line) for line in (args.run / 'activity/windows.jsonl').read_text().splitlines()]
        if windows != run['windows'] or len(windows) != len(run['functional']['layers']):
            raise ValueError('window/run manifest drift')
        for window in windows:
            filename = f"activity/layer_{window['layer']:02d}.fst"
            path = args.run / filename
            expected_file = run['activity_files'][filename]
            before = sha(path)
            if before != expected_file['sha256'] or path.stat().st_size != expected_file['bytes']:
                raise ValueError('FST bytes drift')
            raw = args.out / f"layer_{window['layer']:02d}-native.jsonl"
            with raw.open('w') as stream:
                subprocess.run([str(args.native_reader), str(path)], stdout=stream, check=True, timeout=300)
            audited = verify([json.loads(line) for line in raw.read_text().splitlines()], window, run['macro_scope']['actual_ramsp_instances'])
            if sha(path) != before:
                raise ValueError('FST bytes drift during audit')
            inventory = args.out / f"layer_{window['layer']:02d}-ports.json"
            write(inventory, audited.pop('inventory'))
            result['layers'].append(dict(layer=window['layer'], fst_sha256=before, fst_bytes=path.stat().st_size,
                native_inventory_sha256=sha(raw), port_values_sha256=sha(inventory), **audited))
        result['status'] = f"PASS_NATIVE_RANGE_ALL_{run['macro_scope']['actual_ramsp_instances']}_MACRO_PORTS_INITIALIZED_NOT_POWER_READY"
    except Exception as error:
        result.update(status='FAIL', error=str(error))
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        write(args.out / 'result.json', result)
    print(json.dumps(dict(status=result['status'], tasks=len(result['layers']), actual_macros_per_task=run['macro_scope']['actual_ramsp_instances'])))


if __name__ == '__main__':
    main()
