from pathlib import Path
import hashlib
import io
import json
import os
import tarfile
import time

B=Path.home()/'Desktop/xu-score-optimization-20261102'
O=B/'xu-server-resource-private-function-20261105-141.tar.xz'
assert not O.exists()
data={}
def add(p,name):
    assert p.is_file() and not p.is_symlink() and p.stat().st_size < 16000000
    assert name not in data
    data[name]=p.read_bytes()
for prefix in ['s2e-preflight-readonly-20261105-136','resource-private-readonly-20261105-137','license-readonly-20261105-140','private-target133-static-new','mapped-public-function-20261105-128','mapped-public-function-launch-20261105-128']:
    root=B/prefix
    assert root.is_dir(),prefix
    for directory,dirs,files in os.walk(str(root),followlinks=False):
        dirs[:]=[n for n in dirs if n not in ['csrc','__pycache__','.git'] and not n.endswith(('.daidir','.vdb'))]
        for n in sorted(files):
            p=Path(directory)/n
            if p.suffix in ['.json','.log','.txt','.py','.tsv','.csv','.tcl','.rpt','.jsonl']:
                add(p,str(p.relative_to(B)))
for n in ['private-target133-static-new.stdout.log','private-target133-static-new.returncode']:
    add(B/n,n)
add(Path.home()/'Desktop/xu-license-discovery139.log','license-discovery139.log')
observations=[]
root=B/'s2e-full-soc-power12-20261105-130'
for n in ['execution.json','preparation-state.json']:
    add(root/n,'s2e-full-soc-power12-20261105-130/'+n)
v=json.loads((root/'execution.json').read_text());pid=v.get('pid');proc=Path('/proc')/str(pid)
observations.append(dict(name=root.name,pid=pid,alive_now=proc.exists(),epoch=time.time(),status=v.get('status'),current_task_id=v.get('current_task_id'),command=(proc/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ') if proc.exists() else ''))
for task in sorted(root.glob('task_*')):
    for n in ['power.rpt','pt.log','units.rpt','tool-version.rpt']:
        p=task/n
        if p.is_file():add(p,str(p.relative_to(B)))
launch=B/'s2e-full-soc-power-launch-20261105-130'
for n in ['state.json','driver.log']:
    p=launch/n
    if p.is_file():add(p,str(p.relative_to(B)))
data['live141-observation.json']=(json.dumps(dict(epoch=time.time(),observations=observations,scope='Read-only snapshots do not prove unfinished campaigns complete'),sort_keys=True,indent=2)+'\n').encode()
manifest=[dict(path=n,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for n,raw in sorted(data.items())]
with tarfile.open(str(O),'x:xz') as t:
    for n,raw in sorted(data.items()):
        info=tarfile.TarInfo(n);info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    info=tarfile.TarInfo('manifest.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
print('XU141_READY',O.stat().st_size,hashlib.sha256(O.read_bytes()).hexdigest(),len(manifest),sum(r['bytes'] for r in manifest),flush=True)
