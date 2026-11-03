#!/usr/bin/env python3
"""Print or execute the eight retrieved candidate commands in a frozen checkout."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate', choices=['h2', 'sram'], required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--cross-prefix', help='default: the original server SiFive GCC 10.2 prefix')
parser.add_argument('--run', action='store_true', help='execute; without this flag only print commands')
args = parser.parse_args()
directory = HERE / 'raw/server-export' / ('s1-' + args.candidate + '-accept-01')
state = json.loads((directory / 'state.json').read_text())
source, out = args.source.resolve(), args.out.resolve()


def commit(path):
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], universal_newlines=True).strip()


if commit(source) != state['candidate']['main'] or commit(source / 'third-party/e203_hbirdv2') != state['candidate']['child']:
    parser.error('source main/E203 commits differ from the measured candidate')
old_output = next(s['command'][s['command'].index('--out') + 1] for s in state['steps'] if '--out' in s['command'])
old_output = str(Path(old_output).parent)
old_prefix = next(s['command'][s['command'].index('--cross-prefix') + 1] for s in state['steps'] if '--cross-prefix' in s['command'])
steps = []
for step in state['steps']:
    command = [arg.replace(state['source'], str(source)).replace(old_output, str(out))
               .replace(old_prefix, args.cross_prefix or old_prefix) for arg in step['command']]
    command = [sys.executable if arg == '/bin/python3' else arg for arg in command]
    steps.append(dict(name=step['name'], command=command, timeout=step['timeout']))
    print(' '.join(shlex.quote(arg) for arg in command))
if not args.run:
    sys.exit(0)
out.mkdir(parents=True, exist_ok=False)
result = dict(status='RUNNING', scope='replay of development acceptance commands; no S0/PPA/retention claim', steps=[])
for step in steps:
    record = dict(step, status='RUNNING')
    result['steps'].append(record)
    try:
        with (out / (step['name'] + '.log')).open('w') as log:
            log.write(json.dumps(step['command']) + '\n')
            log.flush()
            process = subprocess.run(step['command'], cwd=str(source), stdout=log, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, timeout=step['timeout'])
        if process.returncode:
            raise RuntimeError('command exit ' + str(process.returncode))
        record['status'] = 'PASS'
    except Exception as error:
        record.update(status='FAIL', error=str(error))
        result['status'] = 'FAIL'
        break
else:
    result['status'] = 'PASS'
(out / 'acceptance.json').write_text(json.dumps(result, indent=2) + '\n')
sys.exit(0 if result['status'] == 'PASS' else 1)
