#!/usr/bin/env python3
"""xu one short VCS run; preserve every returned string byte as hex."""
import argparse,hashlib,json,os,re,shlex,shutil,subprocess,time
from pathlib import Path

def identity(path):
    p=Path(path).resolve();b=p.read_bytes()
    return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--vcs',default='vcs');p.add_argument('--cc',default='gcc');p.add_argument('--include',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[3];c=Path(__file__).with_suffix('.c');tb=root/'tests/ppa/tb_xu_joint_string_probe.sv'
    vcs=Path(shutil.which(a.vcs) or a.vcs).resolve();cc=Path(shutil.which(a.cc) or a.cc).resolve();inc=a.include.resolve()
    a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=False)
    frozen={str(p.resolve()):identity(p) for p in (c,tb,Path(__file__),vcs,cc,inc/'vpi_user.h')}
    state=dict(schema='xu-vpi-string-argument-probe-v1',status='RUNNING_NOT_ACTIVITY_OR_ENERGY',steps=[],started_epoch=time.time())
    def save(): (a.out/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
    def recheck():
        if any(identity(p)!=record for p,record in frozen.items()):raise ValueError('frozen input changed')
    def run(cmd,name):
        recheck()
        with (a.out/name).open('xb') as f:r=subprocess.run(cmd,cwd=str(a.out),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        state['steps'].append(dict(command=cmd,returncode=r.returncode,log=identity(a.out/name)));save();recheck()
        if r.returncode:raise ValueError('command failed '+name)
    save()
    try:
        run([str(vcs),'-ID'],'vcs-version.log');run([str(cc),'--version'],'cc-version.log')
        dep=a.out/'dependencies.d';lib=a.out/'probe.so'
        run([str(cc),'-std=c99','-fPIC','-shared','-Wall','-Wextra','-Wshadow','-Wstrict-prototypes','-Werror','-O2','-isystem',str(inc),'-MD','-MF',str(dep),str(c),'-o',str(lib)],'c-build.log')
        for x in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):frozen[str(Path(x).resolve())]=identity(x)
        frozen[str(lib)]=identity(lib);frozen[str(dep)]=identity(dep)
        state['input_identities_before']=list(frozen.values());save()
        run([str(vcs),'-full64','-sverilog','-timescale=1ns/1fs','-debug_access+all','-load',str(lib)+':xu_joint_string_probe_register','-top','tb_xu_joint_string_probe','-o',str(a.out/'probe'),str(tb)],'vcs-build.log')
        frozen[str(a.out/'probe')]=identity(a.out/'probe')
        run([str(a.out/'probe')],'simulation.log')
        log=(a.out/'simulation.log').read_text(encoding='ascii')
        if re.search(r'^XU_STRING_PROBE_REJECT(?: |$)',log,re.M) or len(re.findall(r'^XU_STRING_PROBE_DONE calls=18$',log,re.M))!=1:raise ValueError('missing/failed diagnostic completion')
        rows=[]
        expected={10:('task-joint','source_request cycle=1403985 addr=a0000000 read=1 valid=1 accept=1'),11:('task-joint','source_request cycle=1403985 addr=a0000000 read=1 valid=1 accept=1'),12:('task-joint','literal-source-identity'),20:('','final_y_retire cycle=2394641 request_cycle=2394640 addr=a00517fc response_valid=1 response_ready=1 writes=50688'),21:('','final_y_retire cycle=2394641 request_cycle=2394640 addr=a00517fc response_valid=1 response_ready=1 writes=50688'),22:('','literal-final-identity')}
        for mode,case,n,first,m,second in re.findall(r'^XU_STRING_PROBE mode=(\d+) id=(\d+) first_bytes=(\d+) first_hex=([0-9a-f]*) second_bytes=(\d+) second_hex=([0-9a-f]*)$',log,re.M):
            mode,case,n,m=map(int,(mode,case,n,m));b,d=bytes.fromhex(first),bytes.fromhex(second)
            if len(b)!=n or len(d)!=m:raise ValueError('hex length differs')
            rows.append(dict(mode=mode,case=case,first_hex=first,second_hex=second,exact_match=(b,d)==tuple(x.encode('ascii') for x in expected[case])))
        if len(rows)!=18 or len({(r['mode'],r['case']) for r in rows})!=18:raise ValueError('diagnostic case coverage differs')
        state.update(status='EXECUTED_STRING_BYTES_REVIEWED_NOT_ACTIVITY_OR_ENERGY',results=rows,input_identities_after=list(frozen.values()),passed_cases=sum(r['exact_match'] for r in rows),limitations=['Argument retrieval only; no full SoC, memory model, callback or power qualification.','Mismatched bytes are retained as hex. A passing standalone micro case does not repair historical capture identities.'])
    except Exception as e:state.update(status='FAIL',error=str(e));raise
    finally:state['finished_epoch']=time.time();save()
    print(json.dumps(dict(status=state['status'],passed_cases=state['passed_cases'],out=str(a.out)),sort_keys=True))

if __name__=='__main__':main()
