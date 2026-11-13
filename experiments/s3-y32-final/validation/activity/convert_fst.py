#!/usr/bin/env python3
"""Build/probe the native FST -> SAIF exporter and audit one sealed GPIO task.

This writes digital activity only. It does not run EDA or establish mapped
coverage, SRAM power characterization, achieved timing or contest eligibility.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

from activity_profile import validate as validate_profile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE_ROOT = 'TOP.tb_sysbus32_soc'
TARGET_ROOT = 'xu_soc_sysbus32_ppa_top'
PIN_WIDTHS = dict(CLK=1, CEN=1, GWEN=1, WEN=16, A=10, D=16, Q=16, EMA=3, EMAW=2, RET1N=1)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def load_activity():
    path = ROOT / 'tools/scripts/xu_soc_activity.py'
    spec = importlib.util.spec_from_file_location('existing_saif_parser', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result, path


def execute(command, out, name, timeout=300):
    log = out / (name + '.log')
    with log.open('w') as stream:
        stream.write(json.dumps(dict(command=[str(x) for x in command])) + '\n')
        stream.flush()
        code = subprocess.run([str(x) for x in command], stdin=subprocess.DEVNULL,
                              stdout=stream, stderr=subprocess.STDOUT, timeout=timeout).returncode
    return code, log.read_text().split('\n', 1)[1]


def build(args, out):
    include = Path('/usr/share/verilator/include/gtkwave')
    records = {}
    for source in ('fstapi.c', 'fastlz.c', 'lz4.c'):
        command = ['gcc', '-O2', '-DFST_CONFIG_INCLUDE="fst_config.h"', '-I' + str(include),
                   '-c', str(include / source), '-o', str(out / (source + '.o'))]
        code, _ = execute(command, out, source + '-compile')
        if code:
            raise RuntimeError('native library compile failed: ' + source)
        records[str(include / source)] = sha(include / source)
    binary = out / 'fst_to_saif'
    command = ['g++', '-O2', '-std=c++17', '-I' + str(include), str(HERE / 'fst_to_saif.cpp'),
               *[str(out / (name + '.o')) for name in ('fstapi.c', 'fastlz.c', 'lz4.c')],
               '-lz', '-o', str(binary)]
    code, _ = execute(command, out, 'exporter-compile')
    if code:
        raise RuntimeError('native exporter compile failed')
    return dict(status='BUILT_NOT_PROBED', binary=str(binary), binary_sha256=sha(binary),
                native_sources=records, source_sha256=sha(HERE / 'fst_to_saif.cpp'),
                native_header_sha256=sha(include / 'fstapi.h'))


def probe(args, out):
    parser, parser_path = load_activity()
    source = out / 'probe.vcd'
    source.write_text('''$timescale 1fs $end
$scope module TOP $end
$scope module tb_sysbus32_soc $end
$var wire 1 ! discarded_tb_alias $end
$var wire 1 ^ discarded_tb_only $end
$scope module dut $end
$var wire 1 ! clk $end
$var wire 1 ! alias_clk $end
$var wire 1 " q $end
$var wire 2 # vec [1:0] $end
$var wire 1 $ stable $end
$scope module macro $end
$var wire 1 ! CLK $end
$var wire 2 # D [1:0] $end
$var integer 32 & model_internal $end
$upscope $end
$upscope $end
$scope module endpoint $end
$var wire 1 ! clk $end
$var wire 2 # alias_vec [1:0] $end
$upscope $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
x"
b10 #
1$
0^
b0 &
$end
#10
1!
1"
1^
#20
0!
0"
b01 #
#30
1!
z"
#40
0!
x"
b10 #
#50
1!
1"
#60
0!
0"
b11 #
''')
    executable = Path(shutil.which('vcd2fst'))
    code, _ = execute([executable, str(source), str(out / 'probe.fst')], out, 'vcd2fst')
    if code:
        raise RuntimeError('native vcd2fst probe failed')
    code, text = execute([args.native_exporter, out / 'probe.fst', out / 'probe.saif', out / 'probe-ports.jsonl'], out, 'native-export')
    if code:
        raise RuntimeError('native exporter probe failed')
    summary = json.loads(text)
    data = parser.read_saif(out / 'probe.saif')
    actual = {row['path']: tuple(row.get(k, 0) for k in ('T0', 'T1', 'TX', 'TZ', 'TC')) for row in data['signals']}
    prefix = TARGET_ROOT + '/'
    clock = (30, 30, 0, 0, 5)
    bit1, bit0 = (20, 40, 0, 0, 2), (40, 20, 0, 0, 2)
    expected = {
        prefix + 'u_soc/clk': clock, prefix + 'u_soc/alias_clk': clock,
        prefix + 'u_soc/q': (10, 20, 20, 10, 1), prefix + 'u_soc/stable': (0, 60, 0, 0, 0),
        prefix + 'u_soc/vec[1]': bit1, prefix + 'u_soc/vec[0]': bit0,
        prefix + 'u_soc/macro/CLK': clock,
        prefix + 'u_soc/macro/D[1]': bit1, prefix + 'u_soc/macro/D[0]': bit0,
        prefix + 'u_shared/clk': clock,
        prefix + 'u_shared/alias_vec[1]': bit1, prefix + 'u_shared/alias_vec[0]': bit0,
    }
    if actual != expected or data['duration_ticks'] != 60 or data['timescale_seconds'] != '1E-15':
        raise ValueError('independently specified dwell/alias/XZ/scope/boundary probe failed')
    wrong = out / 'wrong-unit.vcd'
    wrong.write_text(source.read_text().replace('1fs', '1ps', 1))
    code, _ = execute([executable, wrong, out / 'wrong-unit.fst'], out, 'wrong-unit-vcd2fst')
    if code:
        raise RuntimeError('wrong-unit fixture creation failed')
    code, wrong_message = execute([args.native_exporter, out / 'wrong-unit.fst', out / 'wrong-unit.saif', out / 'wrong-unit-ports.jsonl'], out, 'wrong-unit-export')
    if code == 0 or '1fs/timezero0' not in wrong_message:
        raise ValueError('exporter did not reject incorrect waveform units')
    return dict(status='PASS_NATIVE_FST_SAIF_DIGITAL_PROBE_NOT_POWER_READY',
                expected_stats={k: list(v) for k, v in expected.items()}, summary=summary,
                source_sha256=sha(source), fst_sha256=sha(out / 'probe.fst'), saif_sha256=sha(out / 'probe.saif'),
                native_exporter_sha256=sha(args.native_exporter), vcd2fst_sha256=sha(executable),
                independent_parser_sha256=sha(parser_path), wrong_units_rejected=True,
                transition_policy='Known 0-to-1 and 1-to-0 transitions after initial frame, before final timestamp only. X/Z dwell retained; unknown transitions do not increment TC.')


def convert(args, out):
    probe = json.loads(args.probe_result.read_text())
    if (probe.get('status') != 'PASS_NATIVE_FST_SAIF_DIGITAL_PROBE_NOT_POWER_READY' or
            probe.get('native_exporter_sha256') != sha(args.native_exporter)):
        raise ValueError('native exporter is not bound to a completed semantic probe')
    run = json.loads((args.run / 'result.json').read_text())
    audit = json.loads((args.audit / 'result.json').read_text())
    actual = run.get('macro_scope', {}).get('actual_ramsp_instances')
    if run.get('activity_profile'):
        if not args.profile or sha(args.profile) != run['activity_profile']['sha256']:
            raise ValueError('same explicit source-reviewed activity profile is required')
        validate_profile(json.loads(args.profile.read_text()), run)
        if (audit.get('schema') != 'compliant32-profiled-native-fst-port-audit-v1' or
                audit.get('profile_sha256') != run['activity_profile']['sha256'] or
                audit.get('actual_macro_count') != actual):
            raise ValueError('native audit is not bound to the same explicit macro profile')
    elif actual != 353 or args.profile:
        raise ValueError('nonlegacy macro layout requires exact profile and native inventory')
    if (run.get('status') != 'PASS_RTL_ACTIVITY_WINDOW_NOT_POWER_READY' or
            'XU_SYSBUS_TEST_LOADER' in run.get('definitions', [])):
        raise ValueError('only exact-profile production N2 completed GPIO activity is accepted')
    if (audit.get('status') != f'PASS_NATIVE_RANGE_ALL_{actual}_MACRO_PORTS_INITIALIZED_NOT_POWER_READY' or
            audit.get('run_result_sha256') != sha(args.run / 'result.json')):
        raise ValueError('missing same-run native complete-profile port/time audit')
    window = next(row for row in run['windows'] if row['layer'] == args.layer)
    fst = args.run / f'activity/layer_{args.layer:02d}.fst'
    expected = run['activity_files'][str(fst.relative_to(args.run))]
    if sha(fst) != expected['sha256'] or fst.stat().st_size != expected['bytes']:
        raise ValueError('sealed waveform bytes differ')
    result_file = out / 'activity.saif'
    code, text = execute([args.native_exporter, fst, result_file, out / 'macro-ports.jsonl'], out, 'native-export', 3600)
    if code:
        raise RuntimeError('native FST export failed')
    summary = json.loads(text)
    if (summary['first_fs'] != window['trace_first_fs'] or summary['last_fs'] != window['trace_last_fs'] or
            summary['duration_fs'] != window['duration_fs'] or summary['macro_port_declarations'] != actual * 10):
        raise ValueError('native export time/full-profile port count differs')
    ports = [json.loads(line) for line in (out / 'macro-ports.jsonl').read_text().splitlines()]
    inventory = json.loads((args.audit / f'layer_{args.layer:02d}-ports.json').read_text())
    expected_ports = {}
    for source, pins in inventory.items():
        if source.endswith('.macro'):
            for pin, entry in pins.items():
                expected_ports[source + '.' + pin] = entry
    actual_ports = {row['source']: row for row in ports}
    if len(actual_ports) != len(ports) or set(actual_ports) != set(expected_ports):
        raise ValueError('native export macro pin identity differs from independent inventory')
    for source, port in actual_ports.items():
        initial = expected_ports[source]
        if (port['handle'] != initial['handle'] or port['width'] != initial['width'] or
                port['width'] != PIN_WIDTHS[port['pin']] or len(port['stats']) != port['width']):
            raise ValueError('exported pin width/handle differs: ' + source)
        for stats in port['stats']:
            if len(stats) != 5 or min(stats) < 0 or sum(stats[:4]) != window['duration_fs']:
                raise ValueError('exported pin state statistics do not cover entire task')
        expected_target = source.rsplit('.', 1)[0]
        if expected_target.startswith(SOURCE_ROOT + '.dut.'):
            expected_target = TARGET_ROOT + '/u_soc/' + expected_target[len(SOURCE_ROOT + '.dut.'):].replace('.', '/')
        elif expected_target.startswith(SOURCE_ROOT + '.endpoint.'):
            expected_target = TARGET_ROOT + '/u_shared/' + expected_target[len(SOURCE_ROOT + '.endpoint.'):].replace('.', '/')
        else:
            raise ValueError('macro outside the two physical SoC subtrees')
        if port['target_scope'] != expected_target:
            raise ValueError('unexpected macro hierarchy mapping')
    parser, parser_path = load_activity()
    saif = parser.read_saif(result_file)
    if (saif['duration_ticks'] != window['duration_fs'] or saif['timescale_seconds'] != '1E-15' or
            len(saif['signals']) != summary['digital_bits']):
        raise ValueError('independent SAIF readback duration/unit/bit inventory differs')
    by_path = {row['path']: row for row in saif['signals']}
    if any(not (path.startswith(TARGET_ROOT + '/u_soc/') or path.startswith(TARGET_ROOT + '/u_shared/')) for path in by_path):
        raise ValueError('SAIF contains a nonphysical TB/helper root')
    for port in ports:
        for bit, stats in enumerate(port['stats']):
            name = port['pin'] if port['width'] == 1 else port['pin'] + '[' + str(port['width'] - 1 - bit) + ']'
            entry = by_path.get(port['target_scope'] + '/' + name)
            if entry is None or tuple(entry.get(key, 0) for key in ('T0', 'T1', 'TX', 'TZ', 'TC')) != tuple(stats):
                raise ValueError('independent SAIF readback macro-bit statistics differ')
    if sha(fst) != expected['sha256']:
        raise ValueError('waveform changed during export')
    return dict(status=f'PASS_STRUCTURAL_FST_TO_SAIF_ALL{actual}_MACRO_PINS_NOT_POWER_READY', layer=args.layer,
                summary=summary, source_fst=dict(path=str(fst), **expected),
                run_result_sha256=sha(args.run / 'result.json'), native_audit_sha256=sha(args.audit / 'result.json'),
                native_exporter_sha256=sha(args.native_exporter),
                semantic_probe_sha256=sha(args.probe_result), independent_saif_parser_sha256=sha(parser_path),
                independent_saif_readback=dict(digital_bits=len(by_path), macro_port_bits_checked=actual * 67,
                                              duration_fs=saif['duration_ticks']),
                saif=dict(path=str(result_file), sha256=sha(result_file), bytes=result_file.stat().st_size),
                macro_ports=dict(path=str(out / 'macro-ports.jsonl'), sha256=sha(out / 'macro-ports.jsonl'),
                                 macros=actual, declarations=actual * 10, bits=actual * 67),
                mapping=[dict(source=SOURCE_ROOT + '.dut', target=TARGET_ROOT + '/u_soc'),
                         dict(source=SOURCE_ROOT + '.endpoint', target=TARGET_ROOT + '/u_shared')],
                exclusions='TB/helper/reference scopes and generic SRAM model internal variables; all actual macro interface pins retained',
                transition_policy='Known 0-to-1 and 1-to-0 transitions after initial frame, before final timestamp only; TX/TZ retained',
                limitations=['RTL scope transformation only; mapped generate-instance name correspondence still needs actual mapped inventory.',
                             'Unknown dwell is not coerced to zero. SAIF does not retain pin-to-pin temporal correlations.',
                             'No EDA, annotation coverage, SRAM power model or power result is established.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'probe', 'convert'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-exporter', type=Path)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--probe-result', type=Path)
    parser.add_argument('--profile', type=Path, help='Same bound explicit profile for a nonlegacy macro layout')
    parser.add_argument('--layer', type=int, default=0, choices=range(12))
    args = parser.parse_args()
    args.out = args.out.resolve()
    for name in ('native_exporter', 'run', 'audit', 'probe_result', 'profile'):
        if getattr(args, name):
            setattr(args, name, getattr(args, name).resolve())
    if args.command != 'build' and not args.native_exporter:
        parser.error('--native-exporter is required')
    if args.command == 'convert' and not (args.run and args.audit and args.probe_result):
        parser.error('--run, --audit and --probe-result are required')
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(schema='compliant32-native-fst-saif-v1', status='RUNNING',
                  started_at=datetime.now(timezone.utc).isoformat(), runner_sha256=sha(Path(__file__)))
    try:
        result.update(dict(build=build, probe=probe, convert=convert)[args.command](args, args.out))
    except Exception as error:
        result.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        write(args.out / 'result.json', result)
    print(json.dumps(dict(status=result['status'], result=str(args.out / 'result.json'))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
