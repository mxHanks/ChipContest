#!/usr/bin/env python3
"""Rebuild current default RTL against the frozen real-CPU baseline contract."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(argv, cwd, log):
    argv = list(map(str, argv))
    with log.open('w') as f:
        f.write(json.dumps({'command': argv, 'cwd': str(cwd)})+'\n')
        f.flush()
        result = subprocess.run(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=f, stderr=subprocess.STDOUT, timeout=1200)
    if result.returncode:
        raise RuntimeError(f'exit {result.returncode}: {log}')
    return log.read_text()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, default=ROOT/'build/bias-demand-20261109/full12')
    args = parser.parse_args()
    if datetime.now(timezone.utc) >= datetime.fromisoformat('2026-11-09T23:59:00+08:00'):
        parser.error('deadline reached')
    out = args.out.resolve()
    if out.exists():
        parser.error('new evidence directory required')
    out.mkdir(parents=True)
    report = {'status': 'RUNNING', 'scope': 'current default fallback real-CPU task0; no DMA define'}
    try:
        old = args.baseline.resolve()
        rtl = out/'source/rtl'
        shutil.copytree(old/'source/rtl', rtl)
        current = ROOT/'third-party/e203_hbirdv2/rtl/e203'
        # Freeze all current source files, so unchanged CPU files are also bound.
        for p in current.rglob('*'):
            if p.suffix in ('.v', '.sv', '.vh'):
                q = rtl/p.relative_to(current)
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, q)
        shutil.copy2(old/'tb.sv', out/'source/tb.sv')
        shutil.copy2(old/'accel_soc', out/'firmware.elf')
        shutil.copy2(old/'accel_soc.verilog', out/'firmware.verilog')
        shutil.copytree(old/'task-00/vectors', out/'vectors')
        pins = {str(p.relative_to(out)): sha(p) for p in sorted((out/'source').rglob('*')) if p.is_file()}
        report['source_sha256'] = pins
        report['firmware_elf_sha256'] = sha(out/'firmware.elf')
        report['firmware_image_sha256'] = sha(out/'firmware.verilog')
        report['baseline_result_sha256'] = sha(old/'result.json')
        files = sorted(p for p in rtl.rglob('*') if p.suffix in ('.v', '.sv'))+[out/'source/tb.sv']
        filelist = out/'rtl.f'
        filelist.write_text(''.join(str(p)+'\n' for p in files))
        includes = [rtl/'core', rtl/'perips', rtl/'perips/apb_i2c']
        binary = out/'obj/soc_sim'
        run(['verilator', '--binary', '--timing', '--assert', '-CFLAGS', '-std=gnu++20',
             '-j', '2', '-Wno-fatal', '--top-module', 'tb_accel_soc',
             '-Mdir', out/'obj', '-o', 'soc_sim', '-DDISABLE_SV_ASSERTION=1',
             *['-I'+str(p) for p in includes], '-f', filelist], out, out/'build.log')
        log = run([binary, f'+TESTCASE={out}/firmware', f'+VECTORS={out}/vectors',
                   '+TASKS=1', '+DUMPWAVE=0', '+MAX_CYCLES=3000000', '+FIRST_SOURCE_STALL=0',
                   '+OUTPUT_Y32=1', '+SHARED_W_PACKED16=1', '+NICE_DRAIN8=1',
                   '+NICE_DIRECT=1', '+NICE_STREAM=1', '+NICE_READY=1'], out, out/'simulation.log')
        if re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout', log, re.I):
            raise ValueError('fallback reported failure')
        if not re.search(r'^TASK_PASS layer=0 outputs=25344 writes=25344 cycles=422768 ', log, re.M):
            raise ValueError('fallback payload or output contract changed')
        clear = re.search(r'^S3_TASK_CLEAR_OBSERVED .*clear_cycles=(\d+) .*gap_to_source_request=(\d+)', log, re.M)
        if not clear or tuple(map(int, clear.groups())) != (66802, 102):
            raise ValueError('fallback clear or gap changed')
        if not re.search(r'^SOC_PASS tasks=1 outputs=25344 writes=25344$', log, re.M):
            raise ValueError('fallback whole task completion missing')
        after = {str(p.relative_to(out)): sha(p) for p in sorted((out/'source').rglob('*')) if p.is_file()}
        if after != pins:
            raise ValueError('source drift')
        report.update(status='PASS', outputs=25344, payload=422768, clear=66802,
                      principal=489570, gap=102, source_drift=[], binary_sha256=sha(binary))
        print('FALLBACK_PASS outputs=25344 payload=422768 clear=66802 gap=102')
        return 0
    except Exception as exc:
        report.update(status='FAIL', error=str(exc))
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    sys.exit(main())
