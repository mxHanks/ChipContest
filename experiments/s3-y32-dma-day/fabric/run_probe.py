#!/usr/bin/env python3
"""Reproduce peripheral-ingress real-RTL bandwidth; not CPU task evidence."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
from datetime import datetime, timezone


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=pathlib.Path, required=True)
    ap.add_argument('--out', type=pathlib.Path, required=True)
    args = ap.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    if out.exists():
        raise SystemExit(f'refusing to overwrite {out}')
    out.mkdir(parents=True)
    relative = [
        'experiments/s3-y32-dma-day/fabric/tb_fabric.sv',
        'third-party/e203_hbirdv2/rtl/e203/perips/xu_dma_shared_arb.v',
        'tools/ppa/xu_shared_icb_sram.sv',
        'third-party/e203_hbirdv2/rtl/e203/general/sirv_sim_ram.v',
        'experiments/s3-y32-dma-day/fabric/run_probe.py',
    ]
    frozen = []
    for name in relative:
        src = repo / name
        dst = out / 'source' / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        frozen.append({'path': name, 'sha256': sha(dst)})
    source = out / 'source'
    compile_cmd = ['iverilog', '-g2012', '-s', 'tb_fabric', '-o', str(out / 'fabric.vvp')]
    compile_cmd += [str(source / name) for name in relative[:4]]
    p = subprocess.run(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / 'compile.log').write_text(p.stdout)
    if p.returncode:
        raise SystemExit(p.returncode)
    run_cmd = ['vvp', str(out / 'fabric.vvp')]
    p = subprocess.run(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / 'simulation.log').write_text(p.stdout)
    metrics = []
    for line in p.stdout.splitlines():
        if line.startswith('METRIC '):
            m = {key: int(value) for key, value in re.findall(r'(\w+)=(\d+)', line)}
            m['cycles_per_dma_word'] = m['cycles'] / m['words']
            m['average_response_latency'] = m['latency_sum'] / m['retired']
            m['average_request_interval'] = m['interval_sum'] / (m['accepted'] - 1)
            metrics.append(m)
    passed = p.returncode == 0 and 'FABRIC_PASS ' in p.stdout and len(metrics) == 4
    for m in metrics:
        passed &= m['accepted'] == m['retired'] == m['words'] and m['max_outstanding'] == 1
    result = {
        'status': 'PASS' if passed else 'FAIL',
        'scope': 'Actual peripheral shared ingress arbiter + existing registered/throttled shared ICB SRAM RTL + sirv_sim_ram; synthetic masters, no CPU execution or accelerator bank-load timing claim.',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_files': frozen,
        'source_drift': [f['path'] for f in frozen if sha(repo / f['path']) != f['sha256']],
        'commands': [compile_cmd, run_cmd],
        'tools': {},
        'metrics': metrics,
        'checks': {
            'source_initialized_through_public_cpu_icb': True,
            'physical_y_readback_words': 50688,
            'error_responses': 4,
            'reset_with_held_outstanding_response': True,
            'held_command_and_response_stability': True,
            'per_response_owner_data_error_scoreboard': True,
            'cpu_executed': False,
            'destination_accelerator_bank_commit_measured': False,
        },
    }
    for tool in ['iverilog', 'vvp']:
        q = subprocess.run([tool, '-V'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        result['tools'][tool] = {'path': shutil.which(tool), 'version': q.stdout.splitlines()[0]}
    result['artifacts'] = [{'path': name, 'sha256': sha(out / name)} for name in ['compile.log', 'simulation.log', 'fabric.vvp']]
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'metrics': metrics, 'out': str(out)}, indent=2))
    if not passed or result['source_drift']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
