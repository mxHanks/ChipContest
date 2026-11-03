from pathlib import Path
import json,hashlib,tarfile,io
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'xu-clear-proof-export-20261103-03.tar.xz';assert not O.exists();files={}
patterns=['task-activity-clear-alias-20261103-01/state.json','task-activity-clear-alias-20261103-01/*.log','task-activity-clear-alias-20261103-01/task00/result.json','task-activity-clear-alias-20261103-01/task00/firmware/*.json','task-activity-clear-alias-20261103-01/task00/task_00/*.json','task-activity-clear-alias-20261103-01/task00/task_00/*.log','task-activity-clear-alias-20261103-01/task00/task_00/vectors/input-manifest.json','task-activity-clear-alias-20261103-01/task00/simulator/sram-pin-alias/*','saif-bind-hand-review-20261103*/result.json','saif-bind-port-review-05/result.json','saif-bind-probe-04/*']
for pattern in patterns:
 for p in B.glob(pattern):
  if p.is_file()and p.stat().st_size<5000000 and p.suffix in ['.json','.log','.sv','.vcd','.saif']:files[str(p.relative_to(B))]=p
m=[dict(path=n,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())for n,p in sorted(files.items())]
with tarfile.open(str(O),'x:xz')as t:
 for n,p in sorted(files.items()):t.add(str(p),arcname=n,recursive=False)
 raw=(json.dumps(m,indent=2,sort_keys=True)+'\n').encode();info=tarfile.TarInfo('manifest.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
print('CLEAR_EXPORT_READY',len(m),O.stat().st_size,hashlib.sha256(O.read_bytes()).hexdigest())
