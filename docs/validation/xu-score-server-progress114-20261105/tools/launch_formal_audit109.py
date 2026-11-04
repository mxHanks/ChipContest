from pathlib import Path
import hashlib,subprocess,sys,json,time
b=Path.home()/'Desktop/xu-score-optimization-20261102';s=Path.home()/'Desktop/xu_s2e_formality_audit109.py';o=b/'s2e-own-formality-audit-20261104-109';l=b/'s2e-own-formality-audit-launch-20261104-109'
assert not o.exists()and not l.exists()
assert hashlib.sha256(s.read_bytes()).hexdigest()=='fb468c230b528a364e2f013684e80b0135b7debc75746f90a62057f18aa91bbc'
l.mkdir()
with(l/'driver.log').open('xb')as f:p=subprocess.Popen([sys.executable,str(s)],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
(l/'state.json').write_text(json.dumps(dict(status='LAUNCHED_NOT_QUALIFIED',pid=p.pid,epoch=time.time(),script_sha256=hashlib.sha256(s.read_bytes()).hexdigest()),sort_keys=True,indent=2)+'\n')
print('AUDIT109_STARTED',p.pid,flush=True)
