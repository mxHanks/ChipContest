from pathlib import Path
import os,json,hashlib,tarfile,zipfile,traceback
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'standard-cell-model-inventory-20261104-84';O.mkdir(exist_ok=False)
roots=[Path('/storage1/admin_public_dir'),Path.home()/'Desktop/xu-work/xu-libs/xu-ss-extract/S40'];rows=[];archives=[];visited=0
state=dict(status='RUNNING_READ_ONLY',scope='All .v/.sv/.v.gz names without SCC/std filename filter; private models are not exported')
def save(): (O/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
save()
try:
 for root in roots:
  for directory,dirs,files in os.walk(str(root),followlinks=False):
   visited+=1
   if len(Path(directory).relative_to(root).parts)>=9:dirs[:]=[]
   for name in sorted(files):
    p=Path(directory)/name
    if p.is_symlink()or not p.is_file():continue
    if name.lower().endswith(('.v','.v.gz','.sv')):
     if len(rows)>=3000:raise ValueError('Model limit: inventory incomplete')
     if p.stat().st_size>80000000:rows.append(dict(path=str(p),bytes=p.stat().st_size,status='TOO_LARGE_UNHASHED'));continue
     h=hashlib.sha256()
     with p.open('rb')as f:
      for d in iter(lambda:f.read(1024*1024),b''):h.update(d)
     rows.append(dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest()))
    if 'SMIC40_2025' in str(p)and name.lower().endswith(('.zip','.tar','.tar.gz','.tgz')):
     entry=dict(path=str(p),bytes=p.stat().st_size);names=[]
     try:
      if name.lower().endswith('.zip'):
       with zipfile.ZipFile(str(p))as t:names=[m for m in t.namelist()if m.lower().endswith(('.v','.sv','.v.gz'))]
      else:
       with tarfile.open(str(p),'r|*')as t:
        for m in t:
         if m.isfile()and m.name.lower().endswith(('.v','.sv','.v.gz')):names.append(m.name)
      entry.update(verilog_entries=names)
     except Exception as e:entry['read_error']=type(e).__name__+': '+str(e)
     archives.append(entry)
 state.update(status='READ_ONLY_INVENTORY_NOT_SIMULATION',models=rows,archives=archives,visited_directories=visited,roots=[str(x)for x in roots])
except BaseException as e:state.update(status='FAIL_INVENTORY',error=type(e).__name__+': '+str(e),models=rows,archives=archives,visited_directories=visited)
save();print('MODEL84',state['status'],'models',len(rows),'archives',len(archives),flush=True)
