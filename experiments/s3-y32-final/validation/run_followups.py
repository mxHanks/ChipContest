#!/usr/bin/env python3
"""Run serial production-GPIO full12 and endpoint wait tests after task0 PASS.

Reuses the exact proven simulator, source, firmware and tensor identities. The
single simulator process leaves the other local CPU available for activity work.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base, out = args.base.resolve(), args.out.resolve()
    if out.exists():
        parser.error('followup output must be new')
    parent = json.loads((base / 'result.json').read_text())
    if (parent.get('status') != 'PASS' or parent.get('outputs') != 25344 or
            parent.get('schema') != 's3-final-production-gpio-cpu-v1'):
        raise ValueError('completed production GPIO task0 PASS required')
    runner = HERE / 'run_cpu.py'
    out.mkdir(parents=True)
    receipt = dict(schema='s3-final-production-gpio-followups-v1', status='RUNNING',
        started_at=now(), base=str(base), base_result_sha256=digest(base / 'result.json'),
        runner_sha256=digest(runner), commands={}, results={}, active_case=None,
        policy='Serial exact-binary simulations; one local CPU; no EDA or changes to production RTL',
        scope='Generic macro CPU functional/cycle evidence; no achieved STA frequency, area, power or formal contest qualification')

    def save():
        target = out / 'receipt.json'
        temporary = target.with_suffix('.new')
        temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        temporary.replace(target)

    cases = [('full12', 12, 0, 0), ('dma-first-wait31', 1, 31, 0), ('load-first-wait31', 1, 0, 31)]
    for name, tasks, dma_wait, load_wait in cases:
        receipt['commands'][name] = [sys.executable, '-u', '-B', str(runner),
            '--out', str(out / name), '--vectors', str(args.vectors.resolve()),
            '--replay-from', str(base), '--tasks', str(tasks), '--rows', '8', '--jobs', '1',
            '--warmup', '--first-source-stall', str(dma_wait), '--first-load-stall', str(load_wait)]
    save()
    try:
        for name, tasks, dma_wait, load_wait in cases:
            receipt['active_case'] = name
            with (out / (name + '.driver.log')).open('w') as stream:
                child = subprocess.Popen(receipt['commands'][name], cwd=ROOT,
                    stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                receipt['active_runner_pid'] = child.pid
                save()
                # The runner owns its bounded simulator timeout and cleanup.
                # The supervisor must not expire first and orphan that process.
                code = child.wait()
            result = json.loads((out / name / 'result.json').read_text())
            receipt['results'][name] = dict(returncode=code, status=result.get('status'),
                outputs=result.get('outputs'), total_cycles=result.get('total_cycles'),
                gpio_input_to_y_cycles=result.get('gpio_input_to_y_cycles'),
                result_sha256=digest(out / name / 'result.json'))
            save()
            print(name, json.dumps(receipt['results'][name]), flush=True)
            if code or result.get('status') != 'PASS':
                raise ValueError('production GPIO followup failed: ' + name)
        baseline = parent['layers'][0]
        receipt['differential'] = {}
        for name in ['dma-first-wait31', 'load-first-wait31']:
            row = json.loads((out / name / 'result.json').read_text())['layers'][0]
            receipt['differential'][name] = dict(total_cycles_delta=row['total'] - baseline['total'],
                gpio_input_to_y_cycles_delta=row['load_to_y'] - baseline['load_to_y'],
                loading_cycles_delta=row['loading'] - baseline['loading'],
                dma_payload_cycles_delta=row['dma_payload'] - baseline['dma_payload'],
                requested_endpoint_wait=31,
                note='Exact endpoint offer/accept wait and unchanged full timing boundaries are checked per run; CPU polling phase may change the overall delta.')
        receipt.update(status='PASS', active_case=None, active_runner_pid=None)
        return 0
    except Exception as error:
        receipt.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        return 1
    finally:
        receipt['finished_at'] = now()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
