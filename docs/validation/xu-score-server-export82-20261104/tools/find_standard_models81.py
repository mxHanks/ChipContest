from pathlib import Path
import os,json,hashlib
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'standard-cell-model-inventory-20261104-81';O.mkdir(exist_ok=False)
roots=[Path('/storage1/admin_public_dir'),Path.home()/'Desktop/xu-work/xu-libs/xu-ss-extract/S40'];rows=[];visited=0
for root in roots:
 for directory,dirs,files in os.walk(str(root),followlinks=False):
  visited+=1
  if len(Path(directory).relative_to(root).parts)>=9:dirs[:]=[]
  for name in files:
   if not name.lower().endswith(('.v','.v.gz','.sv')):continue
   p=Path(directory)/name
   # SRAM models are separately pinned already; collect standard-cell models.
   if 'scc40'not in str(p).lower()and 'std'not in str(p).lower() and 'standard'not in str(p).lower():continue
   if p.is_symlink()or not p.is_file()or p.stat().st_size>80000000:continue
   h=hashlib.sha256()
   with p.open('rb')as f:
    for d in iter(lambda:f.read(1024*1024),b''):h.update(d)
   rows.append(dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest()))
result=dict(status='READ_ONLY_INVENTORY_NOT_SIMULATION',visited_directories=visited,models=rows,roots=[str(p)for p in roots],public_top_level=sorted(p.name for p in Path('/storage1/admin_public_dir').iterdir()))
(O/'state.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
