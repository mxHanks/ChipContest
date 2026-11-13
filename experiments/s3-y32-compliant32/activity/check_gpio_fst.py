#!/usr/bin/env python3
"""Audit exact source-reviewed GPIO activity profile against native FST.

Unlike a numeric-count switch, the profile binds all macro instance paths,
group counts, pin widths, production RTL and preprocessing configuration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from activity_profile import validate as validate_profile


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def verify(rows, window, profile):
    metadata = [row for row in rows if row['type'] == 'metadata']
    complete = [row for row in rows if row['type'] == 'complete']
    if len(metadata) != 1 or len(complete) != 1:
        raise ValueError('native FST metadata/completion missing or duplicated')
    metadata = metadata[0]
    if (metadata['timescale'] != -15 or metadata['timezero'] != 0 or
            metadata['first'] != window['trace_first_fs'] or metadata['last'] != window['trace_last_fs'] or
            metadata['last'] - metadata['first'] != window['duration_fs']):
        raise ValueError('native full-task FST time range/precision differs')
    scopes = [row['path'] for row in rows if row['type'] == 'scope']
    signals = [row for row in rows if row['type'] == 'signal']
    if len(scopes) != metadata['scopes'] or len(signals) != metadata['variables'] or len(set(scopes)) != len(scopes):
        raise ValueError('native hierarchy is incomplete or duplicated')
    macros = profile['macros']
    cpu = profile['cpu_interfaces']
    if set(path for path in scopes if path.endswith('.macro')) != set(macros):
        raise ValueError('native macro instance SET differs from complete source-reviewed profile')
    if set(path for path in scopes if path.endswith('.u_sirv_sim_ram')) != set(cpu):
        raise ValueError('CPU logical memory instance set differs')
    initial_rows = [row for row in rows if row['type'] == 'initial']
    initial = {row['handle']: row for row in initial_rows}
    if len(initial) != len(initial_rows):
        raise ValueError('duplicate native initial handle values')
    widths = {**{path: profile['macro_pin_widths'] for path in macros}, **cpu}
    by_scope = {}
    for signal in signals:
        name = signal['name'].split(' ', 1)[0]
        scope = signal['scope']
        if scope in widths and name in widths[scope]:
            if name in by_scope.setdefault(scope, {}):
                raise ValueError('duplicate required pin declaration')
            by_scope[scope][name] = signal
    wanted = set()
    inventory = {}
    for path, pins in widths.items():
        actual = by_scope.get(path, {})
        if set(actual) != set(pins):
            raise ValueError('missing required pin declaration: ' + path)
        inventory[path] = {}
        for name, width in pins.items():
            signal = actual[name]
            value = initial.get(signal['handle'])
            if (signal['width'] != width or value is None or value['time'] != metadata['first'] or
                    len(value['value']) != width or any(ch not in '01xzXZ' for ch in value['value'])):
                raise ValueError('required pin initialization/width differs: ' + path + '.' + name)
            wanted.add(signal['handle'])
            inventory[path][name] = dict(width=width, handle=signal['handle'], initial=value['value'])
    if (wanted != set(initial) or complete[0]['initial_handles'] != len(wanted) or
            complete[0]['required_unique_handles'] != len(wanted)):
        raise ValueError('native initial values differ from required unique alias-handle set')
    return dict(metadata=metadata, macro_groups=profile['group_counts'], actual_macros=len(macros),
        required_macro_ports=len(macros) * len(profile['macro_pin_widths']),
        required_macro_port_bits=len(macros) * sum(profile['macro_pin_widths'].values()),
        cpu_logical_models=2, required_cpu_logical_ports=14, required_unique_handles=len(wanted),
        inventory=inventory, qualification='Generic RTL activity only; mapped annotation and characterized power unproven')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--native-reader', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for name in ('run', 'profile', 'native_reader', 'out'):
        setattr(args, name, getattr(args, name).resolve())
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(schema='compliant32-profiled-native-fst-port-audit-v1', status='RUNNING',
        created_at=datetime.now(timezone.utc).isoformat(), run=str(args.run),
        run_result_sha256=sha(args.run / 'result.json'), native_reader_sha256=sha(args.native_reader),
        checker_sha256=sha(Path(__file__)), profile_sha256=sha(args.profile), layers=[])
    try:
        run = json.loads((args.run / 'result.json').read_text())
        if run.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY':
            raise ValueError('functional production GPIO activity has not passed')
        profile = validate_profile(json.loads(args.profile.read_text()), run)
        if run.get('activity_profile', {}).get('sha256') != sha(args.profile):
            raise ValueError('captured run is not bound to this exact explicit profile')
        windows = [json.loads(line) for line in (args.run / 'activity/windows.jsonl').read_text().splitlines()]
        if windows != run['windows'] or len(windows) != len(run['functional']['layers']):
            raise ValueError('per-task window manifest differs')
        for window in windows:
            filename = f"activity/layer_{window['layer']:02d}.fst"
            path = args.run / filename
            expected = run['activity_files'][filename]
            before = sha(path)
            if before != expected['sha256'] or path.stat().st_size != expected['bytes']:
                raise ValueError('FST bytes differ from sealed functional result')
            raw = args.out / f"layer_{window['layer']:02d}-native.jsonl"
            with raw.open('w') as stream:
                subprocess.run([str(args.native_reader), str(path)], stdout=stream, check=True, timeout=600)
            checked = verify([json.loads(line) for line in raw.read_text().splitlines()], window, profile)
            if sha(path) != before:
                raise ValueError('FST drifted during native audit')
            inventory = args.out / f"layer_{window['layer']:02d}-ports.json"
            write(inventory, checked.pop('inventory'))
            result['layers'].append(dict(layer=window['layer'], fst_sha256=before, fst_bytes=path.stat().st_size,
                native_inventory_sha256=sha(raw), port_values_sha256=sha(inventory), **checked))
        result.update(status=f"PASS_NATIVE_RANGE_ALL_{len(profile['macros'])}_MACRO_PORTS_INITIALIZED_NOT_POWER_READY",
                      macro_groups=profile['group_counts'], actual_macro_count=len(profile['macros']))
    except Exception as error:
        result.update(status='FAIL', error=str(error))
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        write(args.out / 'result.json', result)
    print(json.dumps(dict(status=result['status'], tasks=len(result['layers']))))


if __name__ == '__main__':
    main()
