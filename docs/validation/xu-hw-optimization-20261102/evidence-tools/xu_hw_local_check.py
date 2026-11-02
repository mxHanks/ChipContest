#!/usr/bin/env python3
"""Reproduce local serial checks using the frozen runtime file hashes, not HEAD."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from xu_verify_local_evidence import validate_run, verify_runtime_sources


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, help='repository checkout with initialized E203 submodule')
    parser.add_argument('--out', required=True, help='new output directory')
    parser.add_argument('--check-sources-only', action='store_true')
    args = parser.parse_args()
    repo, out = Path(args.repo).resolve(), Path(args.out).resolve()
    snapshot = json.loads(Path(__file__).with_name('runtime-source-97b3542.json').read_text())

    def check_sources():
        verified = verify_runtime_sources(repo, snapshot)
        return verified['current_main_commit']

    actual_commit = check_sources()
    if args.check_sources_only:
        print('PASS frozen runtime hashes; current report/HEAD commit=' + actual_commit)
        return 0
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='RUNNING', scope='local GCC14/Verilator screening; no server performance claim',
                  frozen_runtime_source=snapshot, actual_main_commit=actual_commit, runs=[])

    def save():
        (out/'local-check.json').write_text(json.dumps(report, indent=2)+'\n')

    cases = [('B0', 'bias-dtcm', 'real', 1),
             ('H1', 'bias-hw', 'synthetic', 2), ('H1', 'bias-hw', 'real', 1),
             ('H2', 'bias-dtcm-window', 'synthetic', 2), ('H2', 'bias-dtcm-window', 'real', 1),
             ('H1H2', 'bias-hw-window', 'synthetic', 2), ('H1H2', 'bias-hw-window', 'real', 1)]
    save()
    try:
        for name, schedule, mode, tasks in cases:
            check_sources()
            label = '{}-{}{}'.format(name, mode, tasks)
            target = out/label
            command = [sys.executable, str(repo/'tools/scripts/e203_soc.py'),
                       '--mode', mode, '--tasks', str(tasks), '--sim', 'verilator',
                       '--firmware-schedule', schedule, '--firmware-opt=-O2',
                       '--firmware-experiment', 'both-unroll-no-masks', '--out', str(target)]
            record = dict(name=label, command=command, status='RUNNING')
            report['runs'].append(record)
            save()
            print('START ' + label, flush=True)
            with (out/(label+'.log')).open('w') as log:
                completed = subprocess.run(command, cwd=str(repo), stdout=log,
                                           stderr=subprocess.STDOUT, timeout=7200)
            result = json.loads((target/'result.json').read_text())
            if completed.returncode:
                raise ValueError('run failed: ' + label)
            validation = validate_run(result, (target/'simulation.log').read_text(),
                                      schedule, mode, tasks, source_commit=actual_commit)
            if name == 'B0' and result['firmware_image_sha256'] != \
                    '1e038157321ac5891329762064d7da77125fbf0134dfe29600e94105b5acefd8':
                raise ValueError('B0 image differs from the frozen GCC14 software baseline')
            record.update(status='PASS', cycles=[row['cycles'] for row in validation['layers']],
                          result_sha256=sha256(target/'result.json'),
                          log_sha256=result['log_sha256'],
                          firmware_image_sha256=result['firmware_image_sha256'])
            check_sources()
            save()
            print('PASS {} {}'.format(label, record['cycles']), flush=True)
        report['status'] = 'PASS'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        raise
    finally:
        save()
    return 0


if __name__ == '__main__':
    sys.exit(main())
