from pathlib import Path
import hashlib
import io
import json
import os
import tarfile
import time

B=Path.home()/'Desktop/xu-score-optimization-20261102'
O=B/'xu-server-queue-control-power-20261105-149.tar.xz'
assert not O.exists()
data={};observations=[]
def add(p,name):
    assert p.is_file() and not p.is_symlink() and p.stat().st_size < 16000000,name
    assert name not in data
    data[name]=p.read_bytes()
for prefix in ['eight-candidate-freeze-queue-20261105-138','eight-candidate-freeze-launch-20261105-148','unified-experiment-control-20261105-150','license-native-readonly-20261105-143','license-users-readonly-20261105-144']:
    root=B/prefix
    if not root.is_dir():continue
    for directory,dirs,files in os.walk(str(root),followlinks=False):
        dirs[:]=[n for n in dirs if n not in ['__pycache__','.git','private-manuals']]
        for n in sorted(files):
            p=Path(directory)/n
            if p.suffix in ['.json','.log','.jsonl','.md'] or n in ['list-licenses.txt','license-users.txt']:
                add(p,str(p.relative_to(B)))
root=B/'s2e-full-soc-power12-20261105-130'
for n in ['execution.json','preparation-state.json']:
    add(root/n,str((root/n).relative_to(B)))
v=json.loads((root/'execution.json').read_text());pid=v.get('pid');proc=Path('/proc')/str(pid)
observations.append(dict(name=root.name,pid=pid,alive_now=proc.exists(),epoch=time.time(),status=v.get('status'),current_task_id=v.get('current_task_id'),taskset_complete=v.get('taskset_complete'),command=(proc/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ') if proc.exists() else ''))
for task in sorted(root.glob('task_*')):
    for n in ['power.rpt','pt.log','units.rpt','tool-version.rpt']:
        p=task/n
        if p.is_file():add(p,str(p.relative_to(B)))
for prefix in ['s2e-own-timing-repair-20261105-134','s2e-own-timing-repair-launch-20261105-134','full-soc-rdc-next-20261105-142','full-soc-rdc-next-launch-20261105-142']:
    root=B/prefix
    for n in ['state.json','driver.log']:
        p=root/n
        if p.is_file():add(p,str(p.relative_to(B)))
control=B/'unified-experiment-control-20261105-150/controller-launch.json'
if control.exists():
    v=json.loads(control.read_text());pid=v.get('pid');p=Path('/proc')/str(pid)
    observations.append(dict(name='control150',epoch=time.time(),pid=pid,alive_now=p.exists(),command=(p/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ') if p.exists() else ''))
data['live149-observation.json']=(json.dumps(dict(epoch=time.time(),observations=observations,scope='Live bodies are snapshots; terminal receipts and actual original logs require independent review'),sort_keys=True,indent=2)+'\n').encode()
manifest=[dict(path=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(data.items())]
with tarfile.open(str(O),'x:xz') as t:
    for n,raw in sorted(data.items()):
        info=tarfile.TarInfo(n);info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
print('XU149_READY',O.stat().st_size,hashlib.sha256(O.read_bytes()).hexdigest(),len(manifest),sum(r['bytes'] for r in manifest),flush=True)
