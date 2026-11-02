#!/usr/bin/env python3
"""Read-only xu server inventory; writes only a new independent output directory."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

desktop = Path.home() / 'Desktop'
out = desktop / 'xu-hw-inventory-20261102-01'
out.mkdir(exist_ok=False)
campaign = desktop / 'xu-fw-optimization-20261102/xu-vcs-campaign-01'
repo = campaign.parent / 'ChipContest'
report = dict(schema='xu-hardware-readonly-inventory-v1', started_epoch=time.time(),
    output=str(out), host=socket.gethostname(), cwd=os.getcwd(),
    scope='read-only environment/tool/version/library/script inventory; no candidate build or simulation',
    commands=[], tools={}, baseline={}, files=[], scan_roots=[], errors=[])


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save():
    (out / 'inventory.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


def run(name, command, timeout=25, cwd=out):
    record = dict(name=name, command=command, cwd=str(cwd), log=name + '.log')
    report['commands'].append(record)
    try:
        result = subprocess.run(command, cwd=str(cwd), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        raw = result.stdout
        record.update(returncode=result.returncode, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    except subprocess.TimeoutExpired as error:
        raw = error.stdout or b''
        record.update(timeout=True, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    except Exception as error:
        raw = str(error).encode()
        record.update(error=str(error))
    (out / record['log']).write_bytes(raw)
    save()
    return raw.decode('utf-8', errors='replace')


run('system', ['uname', '-a'])
run('identity', ['id'])
run('disk', ['df', '-h', str(desktop)])
processes = run('processes', ['ps', '-u', str(os.getuid()), '-o', 'pid,comm,etime,args'])
eda_names = ['vcs', 'accel_soc', 'simv', 'dc_shell', 'pt_shell', 'icc2', 'genus', 'innovus',
             'yosys', 'openroad', 'xu_fw_experiments', 'server_accept.py', 'server_job.py']
report['eda_processes'] = [line for line in processes.splitlines()
                           if any(name in line for name in eda_names) and 'hw_inventory' not in line]
for name in ['dc_shell', 'dcnxt_shell', 'dc_shell-xg-t', 'pt_shell', 'icc2_shell', 'icc_shell',
             'genus', 'innovus', 'voltus', 'joules', 'yosys', 'sta', 'openroad', 'vcs', 'verilator',
             'lmutil', 'python3', 'java', 'scala-cli', 'firtool']:
    found = shutil.which(name)
    report['tools'][name] = dict(path=found)
    if found:
        path = Path(found)
        report['tools'][name].update(realpath=str(path.resolve()), bytes=path.stat().st_size)
        if path.stat().st_size <= 20 * 1024 * 1024:
            report['tools'][name]['sha256'] = sha(path)
        arguments = {'dc_shell':['-version'], 'dcnxt_shell':['-version'], 'dc_shell-xg-t':['-version'],
                     'pt_shell':['-version'], 'icc2_shell':['-version'], 'icc_shell':['-version'],
                     'yosys':['-V'], 'vcs':['-ID'], 'verilator':['--version'], 'java':['-version'],
                     'python3':['--version'], 'firtool':['--version']}.get(name)
        if arguments:
            run('version-' + name, [found] + arguments, timeout=30)
for name, expected in [('experiments.json', 'fc87e5d0b5bcd29118e96942b45769b0f45df15a924feb49e59d2398a4bbfe22'),
                       ('acceptance/acceptance.json', 'ea458063dbe1c47e91a9732e7d43cd658fe3e1c833c9c2e989758c686d4866f3'),
                       ('acceptance/real12/result.json', 'fa1422c9ae2eb1cf4ed0d2d3434afe008fb2256849617eee0914c3ebedced611'),
                       ('acceptance/xu-performance.json', '191923e446b333bebd9bc5a9d75bdf122165718da8f024e0107f959901404078')]:
    path = campaign / name
    if path.is_file():
        actual = sha(path)
        data = json.loads(path.read_text())
        report['baseline'][name] = dict(sha256=actual, expected=expected, matches=actual == expected,
            status=data.get('status'), bytes=path.stat().st_size)
        if name == 'experiments.json':
            report['baseline'][name].update(selection=data.get('selected'), retention_status=data.get('retention_status'))
    else:
        report['errors'].append('missing prior baseline ' + str(path))
if repo.is_dir():
    run('repository-head', ['git', 'log', '-1', '--format=%H%n%P'], cwd=repo)
    run('repository-tracked-diff', ['git', 'diff', '--name-only', 'HEAD', '--'], cwd=repo)
    run('submodule-head', ['git', 'rev-parse', 'HEAD'], cwd=repo / 'third-party/e203_hbirdv2')
    run('submodule-tracked-diff', ['git', 'diff', '--name-only', 'HEAD', '--'], cwd=repo / 'third-party/e203_hbirdv2')

extensions = {'.lib', '.db', '.lef', '.tcl', '.sdc', '.ddc', '.spef', '.saif', '.vcd', '.sdf'}
pruned = {'.git', '.cache', 'node_modules', 'riscv-tools', 'riscv-tests', 'scala', 'usr', 'csrc', 'simv.daidir'}
roots = [desktop]
for candidate in ['/opt', '/tools', '/eda', '/EDA', '/PDK', '/pdk', '/storage2/2026contest/lib',
                  '/storage2/2026contest/libs', '/storage2/2026contest/pdk', '/storage2/2026contest/PDK']:
    if Path(candidate).is_dir():
        roots.append(Path(candidate))
for root in roots:
    report['scan_roots'].append(str(root))
    limit = 7 if root == desktop else 4
    for current, directories, names in os.walk(str(root), followlinks=False):
        path = Path(current)
        depth = len(path.relative_to(root).parts)
        directories[:] = [name for name in directories if name not in pruned and
                          not name.startswith(('sifive-', 'xpack-', 'sim-')) and depth < limit]
        if len(report['files']) >= 1500:
            report['errors'].append('file inventory capped at 1500 entries')
            break
        for name in names:
            file = path / name
            if file.suffix.lower() in extensions or name in ['.synopsys_dc.setup', '.synopsys_pt.setup']:
                try:
                    stat = file.stat()
                    entry = dict(path=str(file), bytes=stat.st_size, symlink=file.is_symlink())
                    if stat.st_size <= 1024 * 1024 and file.suffix.lower() in ['.sdc','.tcl']:
                        entry['sha256'] = sha(file)
                        entry['text_head'] = file.read_text(errors='replace')[:16000]
                    report['files'].append(entry)
                except OSError as error:
                    report['errors'].append(str(error))
    save()
report['finished_epoch'] = time.time()
save()
print('INVENTORY_DONE {} sha256={} files={}'.format(out, sha(out / 'inventory.json'), len(report['files'])), flush=True)
print('TOOLS ' + ' '.join(name + '=' + str(value.get('path')) for name, value in report['tools'].items()), flush=True)
print('BASELINE ' + ' '.join(name + '=' + str(value.get('matches')) for name,value in report['baseline'].items()), flush=True)
print('EDA_PROCESSES ' + json.dumps(report['eda_processes']), flush=True)
