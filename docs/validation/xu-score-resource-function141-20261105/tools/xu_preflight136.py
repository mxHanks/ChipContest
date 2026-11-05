from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
O = B / 's2e-preflight-readonly-20261105-136'
T = Path.home() / 'Desktop/xu-s2e-timing134'
assert not O.exists()
O.mkdir()
state = dict(started_epoch=time.time(), qualification='NOT_QUALIFIED', runs=[], observations=[])
for name, expected in json.loads((T / 'bundle-manifest134.json').read_text())['files'].items():
    raw = (T / name).read_bytes()
    assert len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'], name
for label, command in [
    ('readonly', [sys.executable, str(T / 'xu_s2e_timing134_readonly.py')]),
    ('preflight', [sys.executable, str(T / 'xu_s2e_timing134.py'), '--preflight-only']),
]:
    with (O / (label + '.log')).open('xb') as f:
        result = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    raw = (O / (label + '.log')).read_bytes()
    row = dict(label=label, returncode=result.returncode, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    state['runs'].append(row)
    print('XU136_PREFLIGHT', json.dumps(row, sort_keys=True), flush=True)
    if result.returncode:
        print(raw.decode(errors='replace')[-6000:], flush=True)
        break
for name in ['mapped-public-function-20261105-128', 's2e-full-soc-power12-20261105-130']:
    root = B / name
    candidates = [root / n for n in ['execution.json', 'state.json'] if (root / n).is_file()]
    value = json.loads(candidates[0].read_text()) if candidates else {}
    pid = value.get('pid')
    process = Path('/proc/' + str(pid))
    item = dict(name=name, epoch=time.time(), pid=pid, alive_now=process.exists(),
                state={k:value[k] for k in ['status', 'error', 'phase', 'current_task_id', 'native_pid'] if k in value})
    if process.exists():
        item['cmdline'] = (process / 'cmdline').read_bytes().decode(errors='replace').replace('\0', ' ')
        item['proc_status'] = (process / 'status').read_text().splitlines()[:8]
        children = process / 'task' / str(pid) / 'children'
        item['children'] = []
        for child in children.read_text().split() if children.is_file() else []:
            cp = Path('/proc') / child
            if cp.is_dir():
                item['children'].append(dict(pid=int(child), cmdline=(cp / 'cmdline').read_bytes().decode(errors='replace').replace('\0', ' ')))
    if name.startswith('mapped-'):
        p = root / 'functional-simulation.log'
        if p.is_file():
            with p.open('rb') as f:
                f.seek(max(0, p.stat().st_size - 4000))
                item['log_tail'] = f.read().decode(errors='replace').splitlines()[-8:]
    state['observations'].append(item)
    print('XU136_OBSERVE', json.dumps(item, sort_keys=True), flush=True)
state['finished_epoch'] = time.time()
state['status'] = 'READONLY_PREFLIGHT_PASS_NOT_QUALIFIED' if len(state['runs']) == 2 and not any(r['returncode'] for r in state['runs']) else 'PREFLIGHT_REJECTED_NOT_QUALIFIED'
(O / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
print('XU136_DONE', state['status'], flush=True)
