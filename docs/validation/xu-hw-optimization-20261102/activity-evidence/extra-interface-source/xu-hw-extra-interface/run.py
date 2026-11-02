#!/usr/bin/env python3
"""Run the extra xu ICB contract observations against frozen generated RTL."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--sim', choices=['iverilog', 'vcs'], required=True)
    parser.add_argument('--out', required=True, help='new output directory')
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    repo = Path(args.repo).resolve()
    output = Path(args.out).resolve()
    manifest = json.loads((bundle/'manifest.json').read_text())
    testbench = bundle/'tb_xu_cached_wrapper_extra.sv'
    if sha256(testbench) != manifest['supplement_tb_sha256']:
        raise ValueError('supplemental testbench hash differs from manifest')
    inputs = [str(testbench)]
    for source in manifest['rtl_sources']:
        path = repo/source['path']
        if sha256(path) != source['sha256']:
            raise ValueError('RTL source hash mismatch: ' + source['path'])
        inputs.append(str(path))
    output.mkdir(parents=True, exist_ok=False)
    binary = output/('wrapper.vvp' if args.sim == 'iverilog' else 'simv')
    if args.sim == 'iverilog':
        compile_command = ['iverilog', '-g2012', '-s', manifest['top'],
                           '-o', str(binary), *inputs]
        simulation_command = ['vvp', str(binary)]
    else:
        compile_command = ['vcs', '-full64', '-sverilog', '-timescale=1ns/10ps',
                           '-top', manifest['top'], '+define+DISABLE_SV_ASSERTION=1',
                           '-Mdir='+str(output/'csrc'), '-o', str(binary), *inputs]
        simulation_command = [str(binary)]
    start = time.monotonic()
    metadata = dict(simulator=args.sim, compile_command=compile_command,
                    simulation_command=simulation_command, cwd=str(output),
                    base_tb_sha256=manifest['base_tb_sha256'],
                    supplement_tb_sha256=manifest['supplement_tb_sha256'],
                    status='RUNNING')
    (output/'commands.json').write_text(json.dumps(metadata, indent=2)+'\n')
    built = subprocess.run(compile_command, cwd=str(output),
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           universal_newlines=True, timeout=180)
    (output/'compile.log').write_text(built.stdout)
    metadata['compile_returncode'] = built.returncode
    metadata['compile_log_sha256'] = sha256(output/'compile.log')
    result = None
    if built.returncode == 0:
        result = subprocess.run(simulation_command, cwd=str(output),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=60)
        (output/'simulation.log').write_text(result.stdout)
        metadata['simulation_returncode'] = result.returncode
        metadata['simulation_log_sha256'] = sha256(output/'simulation.log')
    expected = ['XU_EXTRA_RO_WINDOW_PASS words=16 writes_ignored=16',
                'XU_EXTRA_BUSY_CACHE_CTRL_ADDR_PASS ctrl=1 addr=173 numeric_check=excluded',
                'XU_EXTRA_INTERFACE_PASS']
    passed = (result is not None and result.returncode == 0 and
              all(marker in result.stdout for marker in expected) and
              not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', result.stdout, re.IGNORECASE))
    metadata['status'] = 'PASS' if passed else 'FAIL'
    metadata['elapsed_seconds'] = time.monotonic()-start
    (output/'commands.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print('status=' + metadata['status'])
    print('commands=' + str(output/'commands.json'))
    if result is not None:
        print(result.stdout)
    elif built.returncode:
        print(built.stdout)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
