#!/usr/bin/env python3
"""Frozen 64 PE candidate synthesis. Review-only unless --run is explicit."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

DEADLINE = datetime.datetime(2026, 11, 10, 15, 59, tzinfo=datetime.timezone.utc).timestamp()
DC = '/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell'
DC_SHA = '23a4101c711fdb4747a57e6f9524d4989eb76a2b3120f0fa9766f4b25ae8e6d2'
STDD = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db'
SRAMD = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db'
LIBS = [('standard_cell', STDD, 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'),
        ('sram', SRAMD, 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f')]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def tcl(value):
    if any(c in str(value) for c in '{}\\\r\n'):
        raise ValueError('unsafe Tcl literal')
    return '{' + str(value) + '}'


def heavy_jobs():
    """Same-account native executables only; no broad process termination."""
    heavy = {'simv', 'vcs', 'vcs1', 'dc_shell', 'snps_shell', 'common_shell_ex',
             'pt_shell', 'icc2_shell', 'fm_shell', 'lc_shell'}
    jobs = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            if p.stat().st_uid != os.getuid():
                continue
            comm = (p / 'comm').read_text().strip()
            exe = Path(os.readlink(str(p / 'exe'))).name
            if comm in heavy or exe in heavy:
                jobs.append({'pid': int(p.name), 'comm': comm, 'exe': exe,
                             'cwd_basename': Path(os.readlink(str(p / 'cwd'))).name,
                             'starttime': (p / 'stat').read_text().rsplit(')', 1)[1].split()[19]})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return sorted(jobs, key=lambda v: v['pid'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', action='store_true')
    p.add_argument('--coordinated-simv-pid', type=int, choices=[90373],
                   help='Use only after explicit user resource coordination; cannot allow EDA jobs.')
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'package-files.json').read_text())
    for name, digest in manifest.items():
        if not (root / name).is_file() or sha(root / name) != digest:
            raise ValueError('frozen package drift: ' + name)
    review = {'status': 'INPUT_REVIEW_PASS_NOT_EXECUTED', 'inputs': len(manifest),
              'manifest_sha256': sha(root / 'package-files.json'), 'max_cores': 2,
              'deadline_utc': '2026-11-10T15:59:00Z', 'qualification': 'NOT_QUALIFIED',
              'run_requested': a.run}
    if not a.run:
        print(json.dumps(review, sort_keys=True))
        return 0
    if time.time() >= DEADLINE:
        raise ValueError('experiment deadline reached; refuse a new run')
    os.chdir(str(root))
    for name in ['execution.json', 'WORK', 'dc.log', 'libraries.tcl',
                 'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt', 'SYNTHESIS_FAILED.txt']:
        if (root / name).exists():
            raise ValueError('refuse restart/overwrite: ' + name)
    busy = heavy_jobs()
    denied = [j for j in busy if not (a.coordinated_simv_pid == j['pid'] and j['comm'] == 'simv'
              and j['exe'] == 'simv' and j['cwd_basename'] == 'xu-gls-cen-local-strict')]
    if denied:
        raise ValueError('uncoordinated same-account heavy jobs: ' + json.dumps(denied))
    if not Path(DC).is_file() or sha(DC) != DC_SHA:
        raise ValueError('DC identity mismatch')
    libraries = []
    for role, path, digest in LIBS:
        if not Path(path).is_file() or sha(path) != digest:
            raise ValueError('library identity mismatch: ' + role)
        libraries.append(dict(role=role, path=path, sha256=digest))
    (root / 'libraries.tcl').write_text('set_app_var target_library [list ' + tcl(STDD) + ']\n' +
        'set_app_var link_library [list * ' + tcl(STDD) + ' ' + tcl(SRAMD) + ']\n')
    cmd = [DC, '-f', 'synth.tcl']
    receipt = dict(review, status='RUNNING', command=cmd, started_epoch=time.time(),
                   libraries=libraries, tool={'path': DC, 'sha256': DC_SHA},
                   observed_jobs=busy, coordinated_simv_pid=a.coordinated_simv_pid)
    rp = root / 'execution.json'
    rp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    timeout = False
    with (root / 'dc.log').open('w') as log:
        process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        receipt['pid'] = process.pid
        rp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        try:
            code = process.wait(timeout=max(1, DEADLINE - time.time()))
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    drift = [n for n, h in manifest.items() if not (root / n).is_file() or sha(root / n) != h]
    marker = (root / 'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt').is_file()
    errors = re.findall(r'^(?:Error:|Fatal:).*$', (root / 'dc.log').read_text(errors='replace'), re.MULTILINE)
    receipt.update(returncode=code, finished_epoch=time.time(), deadline_terminated=timeout,
                   source_drift=drift, completion_marker=marker, native_tool_errors=errors)
    receipt['status'] = 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' if code == 0 and marker and not drift and not timeout and not errors else 'FAILED'
    receipt['outputs'] = {str(f.relative_to(root)): {'bytes': f.stat().st_size, 'sha256': sha(f)}
                          for f in root.rglob('*') if f.is_file() and str(f.relative_to(root)) not in manifest
                          and str(f.relative_to(root)) != 'execution.json'}
    rp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(receipt['status'])
    return 0 if receipt['status'] == 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print('FAIL: ' + str(e), file=sys.stderr)
        sys.exit(1)
