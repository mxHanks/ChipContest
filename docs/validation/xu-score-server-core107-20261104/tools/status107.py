from pathlib import Path
import json,hashlib,tarfile,io,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'xu-core-results-20261104-107.tar.xz';assert not O.exists();data={};obs={}
for n in [295091,156772,144236]:
 p=Path('/proc/'+str(n));obs[str(n)]=dict(alive=p.exists(),command=(p/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ')if p.exists()else'')
for rel in ['s2e-ppa-campaign-20261104-89/state.json','s2e-ppa-campaign-20261104-89/formality/state.json','s2e-ppa-campaign-20261104-89/formality/fm.log','s2e-ppa-campaign-20261104-89/formality/verify.tcl','s2e-ppa-campaign-20261104-89/formality/failing.rpt','s2e-ppa-campaign-20261104-89/formality/unmatched.rpt','s2e-ppa-campaign-20261104-89/ppa/area.rpt','s2e-ppa-campaign-20261104-89/ppa/units.rpt','s2e-ppa-campaign-20261104-89/ppa/execution.json','s2e-ppa-campaign-20261104-89/ppa/prepared.json','xu-export106-state.json','xu-export106-driver.log']:
 p=B/rel
 if p.is_file()and p.stat().st_size<12000000:data[rel]=p.read_bytes()
for pre in ['vpi-vendor-preload-primitive-20261104-105','s2c-native-pin-stream-20261104-93']:
 p=B/pre/'state.json'
 if p.exists():data[pre+'/state.json']=p.read_bytes()
 for label in ['diagnostic_only','reference']:
  p=B/pre/label/'sim.log'
  if p.exists():data[str(p.relative_to(B))]=p.read_bytes()
q=B/'xu-next-results-export-20261104-106.tar.xz';obs['export106_out']=dict(exists=q.exists(),bytes=q.stat().st_size if q.exists()else 0);obs['epoch']=time.time();data['status107-observation.json']=(json.dumps(obs,sort_keys=True,indent=2)+'\n').encode()
m=[dict(path=n,bytes=len(d),sha256=hashlib.sha256(d).hexdigest())for n,d in sorted(data.items())]
with tarfile.open(str(O),'x:xz')as t:
 for n,d in sorted(data.items()):
  x=tarfile.TarInfo(n);x.size=len(d);t.addfile(x,io.BytesIO(d))
 d=(json.dumps(m,sort_keys=True,indent=2)+'\n').encode();x=tarfile.TarInfo('manifest.json');x.size=len(d);t.addfile(x,io.BytesIO(d))
print('CORE107_READY',O.stat().st_size,hashlib.sha256(O.read_bytes()).hexdigest(),len(m),sum(x['bytes']for x in m),flush=True)
