#!/usr/bin/env python3
"""Bounded, tiny reproduction of the mapped snapshot vector scheduling warning.

This never edits or compiles the accepted full netlist. Both a declaration
metacomment and an external, variable-scoped Verilator configuration are tested.
The latter permits preserving even the simulation-view Verilog byte for byte.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import sram_evidence as E

MARKER = (r'^KWT_MAPPED_ALIAS_PASS checks=48 positive_loads=4 '
          r'negative_loads=3 holds=7 resets=2$')


def warning_count(text, name):
    return len(re.findall(r'^%Warning-' + re.escape(name) + r':', text, re.M))


def accept_lint(text, baseline):
    count = warning_count(text, 'UNOPTFLAT')
    if baseline:
        if count != 1 or not re.search(r'^%Warning-UNOPTFLAT:.*y_snapshot', text, re.M):
            raise ValueError('baseline did not reproduce exactly the snapshot scheduling warning')
    elif count or warning_count(text, 'SPLITVAR'):
        raise ValueError('targeted split left a scheduling or unsupported-split warning')
    return {'unoptflat_warnings': count, 'splitvar_warnings': warning_count(text, 'SPLITVAR')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('timeout must be positive')
    out = ROOT / 'artifacts/runs' / (
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        + '-sram-alias-' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    report = {
        'schema': 'kwt-mapped-alias-diagnostic-v1', 'status': 'RUNNING',
        'scope': 'tiny reference functional fixture only; not full netlist equivalence or timing',
        'full_netlist_compilation': 'NOT_RUN', 'official_ppa': 'BLOCKED',
        'commands': [], 'inputs': [], 'cases': {},
        'configuration': {'jobs': 2, 'threads': 1, 'timeout_seconds': args.timeout},
    }
    E.write_json(out / 'result.json', report)
    try:
        tool = shutil.which('verilator')
        if not tool:
            raise FileNotFoundError('source env/activate.sh; local Verilator required')
        fixture = ROOT / 'sim/fixtures/kwt_mapped_alias.sv'
        docs = ROOT / '.tools/eda/usr/share/doc/verilator/html'
        config = out / 'split_alias.vlt'
        config.write_text('`verilator_config\nsplit_var -module "kwt_mapped_alias" -var "y_snapshot"\n')
        dependencies = [Path(__file__), Path(E.__file__), fixture, Path(tool),
                        ROOT / '.tools/eda/usr/bin/verilator',
                        ROOT / '.tools/eda/usr/bin/verilator_bin',
                        docs / 'extensions.html', docs / 'warnings.html',
                        docs / 'exe_verilator.html', config]
        identity = E.source_identity(dependencies, report['configuration'], out / 'source_identity.json')
        report['inputs'] = identity['inputs']
        report['identity'] = identity

        def execute(argv, name, patterns=()):
            command = E.run_command(argv, ROOT, out / (name + '.log'), args.timeout, 2)
            report['commands'].append(command)
            E.write_json(out / 'result.json', report)
            error = E.completion_error(command, list(patterns))
            if error:
                raise ValueError(name + ' rejected: ' + error)
            return Path(command['log']['path']).read_text()

        version = execute([tool, '--version'], 'version')
        if not re.search(r'^Verilator 5\.020\b', version):
            raise ValueError('this reproduction requires the project Verilator 5.020')
        report['tool_version'] = version.strip()
        common = [tool, '--timing', '--assert', '-Wno-fatal',
                  '--top-module', 'tb_kwt_mapped_alias']
        variants = {
            'baseline': [],
            'metacomment': ['+define+KWT_ALIAS_SPLIT'],
            'configuration': [str(config)],
        }
        for name, extra in variants.items():
            log = execute([*common, '--lint-only', '--Mdir', str(out / ('lint-' + name)),
                           *extra, str(fixture)], 'lint-' + name)
            report['cases'][name] = {'lint': accept_lint(log, name == 'baseline')}
            E.write_json(out / 'result.json', report)
        # Exercise the unannotated circuit too. Its expected warning stays
        # visible; every version must satisfy the same independent scoreboard.
        for name in ('baseline', 'metacomment', 'configuration'):
            obj = out / ('obj-' + name)
            log = execute([*common, '--binary', '--Mdir', str(obj), '-o', 'simulation',
                           '-j', '2', '--threads', '1', *variants[name], str(fixture)],
                          'compile-' + name, [r'^make: Leaving directory '])
            accept_lint(log, name == 'baseline')
            binary = obj / 'simulation'
            if not binary.is_file():
                raise ValueError('compile lacks executable: ' + name)
            report['inputs'].append(E.record(binary))
            log = execute([str(binary)], 'run-' + name, [MARKER])
            if len(re.findall(r'^- .*\$finish$', log, re.M)) != 1:
                raise ValueError('fixture lacks complete simulation termination: ' + name)
            report['cases'][name]['behavior'] = {
                'status': 'PASS', 'checks': 48, 'positive_loads': 4,
                'negative_loads': 3, 'holds': 7, 'asynchronous_resets': 2,
            }
        report['status'] = 'PASS'
    except FileNotFoundError as exc:
        report.update(status='BLOCKED', error=str(exc))
    except Exception as exc:
        report.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
    finally:
        try:
            E.verify_records(report['inputs'])
        except (OSError, ValueError) as exc:
            report.update(status='FAIL', error=str(exc))
        E.write_json(out / 'result.json', report)
    print(json.dumps({'status': report['status'], 'report': str(out / 'result.json'),
                      'error': report.get('error')}))
    return {'PASS': 0, 'FAIL': 1, 'BLOCKED': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
