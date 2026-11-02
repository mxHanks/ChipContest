#!/usr/bin/env python3
"""Prepare fresh-output replays of the recorded xu wrapper runs; never run EDA."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parent
SERVER = '/storage2/2026contest/server4/s4_23usr/Desktop/'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check(path, expected):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'missing or symlink input: '+str(path))
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'input SHA256 mismatch: '+str(path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new directory; must not exist')
    args = parser.parse_args()
    out = args.out.resolve()
    require(not out.exists(), 'output exists: '+str(out))
    require(not any(c in str(out) for c in '{}[]$;\\\n\r'), 'unsupported Tcl output path')
    identities = json.loads((ROOT/'source-identities.json').read_text())
    inputs = identities['qualification_inputs']
    old = SERVER+'xu-hw-optimization-20261102/ppa/candidate-ss-02/'
    check(old+'mapped.ddc', inputs['ddc_sha256'])
    check(old+'mapped.v', inputs['netlist_sha256'])
    for path, item in inputs['libraries'].items():
        check(path, item['sha256'])
    frozen = SERVER+'xu-hw-optimization-20261102/ppa/frozen-hw-rtl-02/'
    for name, value in inputs['rtl'].items():
        check(frozen+name, value)
    gate_state = json.loads((ROOT/'raw/server-qualification-01/gate-dc-01/state.json').read_text())
    gate = json.loads((ROOT/'raw/server-qualification-01/gate-dc-01/replay/result.json').read_text())
    for path, item in gate['inputs'].items():
        check(path, item['sha256'])
    for item in gate['tool_identities'].values():
        check(item['path'], item['sha256'])
    out.mkdir()
    fixed = out/'hold-fixed02'
    fm = out/'fm-original02'
    fixed.mkdir()
    fm.mkdir()
    original = ROOT/'raw/server-qualification-01/wrapper-qualification-02'
    (fixed/'repair.tcl').write_bytes((original/'hold-fixed/repair.tcl').read_bytes())
    audit = (original/'hold-fixed/audit.tcl').read_text()
    audit = audit.replace(SERVER+'xu-score-optimization-20261102/wrapper-qualification-02/hold-fixed', str(fixed))
    (fixed/'audit.tcl').write_text(audit)
    (fm/'verify.tcl').write_bytes((original/'fm-original/verify.tcl').read_bytes())
    gate_command = gate_state['command'][:]
    gate_command[gate_command.index('--out')+1] = str(out/'gate01')
    dc = 'dc_shell'
    pt = 'pt_shell'
    fm_shell = 'fm_shell'
    clean_commands = []
    for name in ['fm-original', 'fm-hold-fixed']:
        directory = out/(name+'03')
        directory.mkdir()
        text = (ROOT/'raw/server-qualification-03'/name/'verify.tcl').read_text()
        text = text.replace(SERVER+'xu-score-optimization-20261102/wrapper-qualification-02/hold-fixed', str(fixed))
        (directory/'verify.tcl').write_text(text)
        clean_commands.append({'name': name+'03', 'cwd': str(directory),
                               'command': [fm_shell, '-f', 'verify.tcl'], 'expected_returncode': 0})
    fixed_gate = gate_command[:]
    fixed_gate[fixed_gate.index('--out')+1] = str(out/'gate-fixed03')
    fixed_gate[fixed_gate.index('--netlist')+1] = str(fixed/'mapped.v')
    fixed_gate[fixed_gate.index('--netlist-sha256')+1] = '__XU_FIXED_SHA__'
    commands = [
        {'name': 'gate01', 'cwd': str(out), 'command': gate_command, 'expected_returncode': 0},
        {'name': 'hold-dc02', 'cwd': str(fixed), 'command': [dc, '-64bit', '-f', 'repair.tcl'], 'expected_returncode': 0},
        {'name': 'hold-pt02', 'cwd': str(fixed), 'command': [pt, '-f', 'audit.tcl'], 'expected_returncode': 0},
        {'name': 'fm-original02', 'cwd': str(fm), 'command': [fm_shell, '-f', 'verify.tcl'], 'expected_returncode': 1},
    ]
    commands += clean_commands
    commands.append({'name': 'gate-fixed03', 'cwd': str(out),
                     'command': fixed_gate, 'expected_returncode': 0,
                     'runtime_substitution': '__XU_FIXED_SHA__ becomes SHA256 of freshly repaired mapped.v'})
    (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n')
    lines = ['#!/bin/bash', 'set -euo pipefail',
             'export SYNOPSYS_LC_ROOT=/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5',
             'export PATH="$SYNOPSYS_LC_ROOT/bin:$PATH"']
    for entry in commands:
        if entry['name'] == 'gate-fixed03':
            lines += ['xu_fixed_sha=$(sha256sum -- '+shlex.quote(str(fixed/'mapped.v'))+')',
                      'xu_fixed_sha=${xu_fixed_sha%% *}']
        rendered = shlex.join(entry['command']).replace('__XU_FIXED_SHA__', '"$xu_fixed_sha"')
        lines += ['cd '+shlex.quote(entry['cwd']), 'set +e',
                  rendered+' > '+shlex.quote(entry['name']+'.log')+' 2>&1',
                  'xu_rc=$?', 'set -e',
                  'printf "%s\\n" "$xu_rc" > '+shlex.quote(entry['name']+'.returncode'),
                  'test "$xu_rc" -eq '+str(entry['expected_returncode'])]
    (out/'run.sh').write_text('\n'.join(lines)+'\n')
    (out/'input-identities.json').write_text(json.dumps(identities, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'status': 'PREPARED_ONLY_NO_EDA_RUN', 'out': str(out),
                      'run_script': str(out/'run.sh'), 'fm02_expected_returncode': 1}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        print('XU_REPLAY_PREPARE_FAIL: '+str(error), file=sys.stderr)
        raise SystemExit(1)
