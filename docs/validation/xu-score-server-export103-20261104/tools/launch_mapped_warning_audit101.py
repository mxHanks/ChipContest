#!/usr/bin/env python3
"""xu detach read-only original mapped UDP/port-warning audit101."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
SHA='301da3ccffd62d037509a6ab61ff0ad9ec364120618c95d18fc6c4eda17711e5'
def need(ok,msg):
    if not ok:raise ValueError(msg)
def identity(path):
    p=Path(path).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tool',type=Path,default=Path.home()/'Desktop/xu_mapped_warning_audit101.py');p.add_argument('--base',type=Path,default=Path.home()/'Desktop/xu-score-optimization-20261102');a=p.parse_args();tool=identity(a.tool);need(tool['sha256']==SHA,'exact audit101 helper differs');base=a.base.resolve();out=base/'mapped-warning-audit-20261104-101';deploy=base/'mapped-warning-deploy-20261104-101';need(not out.exists()and not deploy.exists(),'new101 directories required; do not overwrite previous experiments');deploy.mkdir();command=[sys.executable,'-u',tool['path'],'--base',str(base),'--out',str(out)];state=dict(status='PREPARED_NOT_LAUNCHED',tool=tool,launcher=identity(__file__),qualification='NOT_QUALIFIED',command=command,started_epoch=time.time());(deploy/'state.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
    with(deploy/'driver.log').open('xb')as output:child=subprocess.Popen(command,cwd=str(deploy),stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    state.update(status='LAUNCHED_NOT_REVIEWED',pid=child.pid,launcher_pid=os.getpid());(deploy/'state.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n');print('XU_MAPPED_WARNING101_LAUNCHED pid=%d out=%s NOT_QUALIFIED'%(child.pid,out),flush=True)
if __name__=='__main__':main()
