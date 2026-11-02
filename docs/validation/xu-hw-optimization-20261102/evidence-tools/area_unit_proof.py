#!/usr/bin/env python3
"""Physical-size proof without exporting vendor library contents."""
from pathlib import Path
import gzip,hashlib,json,re,tarfile,time
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';O=B/'area-units-01'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def lefs(raw,names):
 text=raw.decode('ascii',errors='replace');result=[]
 for name in names:
  match=re.search(r'\bMACRO\s+'+re.escape(name)+r'\b(.*?)\bEND\s+'+re.escape(name)+r'\b',text,re.S)
  if not match:continue
  m=re.search(r'\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;',match.group(1))
  if m:result.append(dict(cell=name,width_microns=float(m[1]),height_microns=float(m[2]),physical_area_um2=float(m[1])*float(m[2]),size_line=m.group(0)))
 unit=re.search(r'DATABASE\s+MICRONS\s+(\d+)\s*;',text)
 return dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),database_microns=int(unit.group(1)) if unit else None,cells=result)
ramlef=Path('/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/lef/RAMSP1024X16.lef')
ramlib=Path('/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/lib/RAMSP1024X16_ss_0p99v_0p99v_125c.lib')
ram=lefs(ramlef.read_bytes(),['RAMSP1024X16']);ram['lef_path']=str(ramlef);ram['lib_path']=str(ramlib);ram['lib_sha256']=sha(ramlib)
t=ramlib.read_text();m=re.search(r'\barea\s*:\s*([\d.eE+-]+)\s*;',t);ram['lib_cell_area']=float(m[1]) if m else None
(O/'ram-physical-proof.json').write_text(json.dumps(ram,sort_keys=True,indent=2)+'\n')
print('SRAM_PROOF',json.dumps(ram,sort_keys=True),flush=True)
archive=Path('/storage1/admin_public_dir/SMIC40_2025/S40.tar.gz');started=time.time();visited=[]
state=dict(status='RUNNING',archive_path=str(archive),archive_bytes=archive.stat().st_size,started_epoch=started,visited=0,last_member=None,selected=[])
def save():(O/'stdcell-archive-progress.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
save()
try:
 with tarfile.open(str(archive),'r|gz') as tar:
  for member in tar:
   state['visited']+=1;state['last_member']=member.name
   if state['visited']<=50:visited.append(dict(name=member.name,bytes=member.size))
   if state['visited']%100==0:save()
   target='RVT' in member.name.upper() and member.name.lower().endswith(('.lef','.lef.gz'))
   if target and member.isfile():
    data=tar.extractfile(member).read()
    if member.name.endswith('.gz'):data=gzip.decompress(data)
    proof=lefs(data,['NAND2CV2_12TR40','INV2_12TR40','DRNQV2_12TR40','BUFV2RD_12TR40'])
    proof['archive_member']=member.name;state['selected'].append(proof);save()
    if len(proof['cells'])>=3:
     state['status']='PASS';break
   if time.time()-started>900:
    state['status']='BOUNDED_STOP';break
  else:state['status']='NOT_FOUND'
except Exception as e:state.update(status='FAIL',error=str(e));raise
finally:
 state['finished_epoch']=time.time();state['first_members']=visited;save()
print('STANDARD_CELL_PROOF',json.dumps(state,sort_keys=True),flush=True)
