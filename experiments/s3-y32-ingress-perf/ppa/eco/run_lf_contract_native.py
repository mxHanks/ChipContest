#!/usr/bin/env python3
"""Run same-map original/revised LF contracts in native PT; never infer closure."""
from pathlib import Path
import argparse, hashlib, json, os, re, signal, subprocess, time

MAP_SHA = 'd83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1'
SDC_SHA = 'c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c'
LIB_SHAS = ['f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
            'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(p, digest):
    assert Path(p).is_file() and sha(p) == digest, 'Input SHA mismatch: ' + str(p)
    return dict(path=str(p), bytes=Path(p).stat().st_size, sha256=digest)
def tcl(p):
    s=str(p)
    assert not any(c in s for c in '{}\\\n\r'), 'Unsafe Tcl path'
    return '{'+s+'}'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--mapped',type=Path,required=True)
    p.add_argument('--overlay',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); package=Path(__file__).resolve().parent
    chain=json.loads((a.baseline/'toolchain.json').read_text())
    assert [x['role'] for x in chain['libraries']] == ['standard_cell','sram']
    assert [x['sha256'] for x in chain['libraries']] == LIB_SHAS
    bindings=[verify(a.mapped,MAP_SHA),verify(a.baseline/'source/contracts/reference-full-soc.sdc',SDC_SHA)]
    bindings.append(verify(a.baseline/'source/ppa/hierarchy_contract.tcl', '8465d9b61c98fd44a8d72161ac1f9918235b1b5a5703d3be4c04860981923544'))
    for f in (package/'common.tcl',package/'pt_lf_contract.tcl',a.overlay):
        bindings.append(verify(f,sha(f)))
    for x in chain['libraries']: bindings.append(verify(x['path'],x['sha256']))
    tool=chain['pt'];verify(tool['path'],tool['sha256'])
    lc=chain['library_compiler'];verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'])
    jobs=[]
    for q in Path('/proc').iterdir():
        if not q.name.isdigit():continue
        try:
            if q.stat().st_uid==os.getuid() and (q/'comm').read_text().strip() in {'pt_shell','dc_shell','fm_shell','vcs','simv'}:jobs.append(q.name)
        except OSError:pass
    assert not jobs,'Another native job is running'
    allowed=sorted(os.sched_getaffinity(0));assert len(allowed)>=10
    os.sched_setaffinity(0,allowed[:8])
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    config='\n'.join([
        'set ::eco_baseline '+tcl(a.baseline),
        'set ::eco_mapped '+tcl(a.mapped),
        'set ::lf_contract_overlay '+tcl(a.overlay),
        'set ::eco_link_libraries [list * '+' '.join(tcl(x['path']) for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256']) for x in chain['libraries'])+']',
        'set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256']) for x in bindings)+']'])+'\n'
    (a.out/'config.tcl').write_text(config)
    env=os.environ.copy();env.update(SYNOPSYS_LC_ROOT=lc['root'],XU_ECO_PACKAGE=str(package),XU_ECO_CONFIG=str(a.out/'config.tcl'))
    r=dict(schema='lf-input-contract-native-v1',status='RUNNING',started_epoch=time.time(),
           command=[tool['path'],'-f',str(package/'pt_lf_contract.tcl')],tool=tool,
           libraries=chain['libraries'],inputs=bindings,config_sha256=sha(a.out/'config.tcl'),
           affinity=allowed[:8],max_cores=8,netlist_modified=False,constraint_revision='team-lf-input-v1')
    def save():(a.out/'execution.json').write_text(json.dumps(r,indent=2)+'\n')
    save()
    with (a.out/'native.log').open('w') as log:
        proc=subprocess.Popen(r['command'],cwd=a.out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        r['pid']=proc.pid;save()
        try:rc=proc.wait(timeout=900)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM);rc=proc.wait(timeout=20);r['timed_out']=True
    for item in bindings:verify(item['path'],item['sha256'])
    r['native_tool_errors']=re.findall(r'^(?:Error:|Fatal:).*$',(a.out/'native.log').read_text(errors='replace'),re.M)
    complete=rc==0 and not r['native_tool_errors'] and (a.out/'LF_CONTRACT_COLLECTION_COMPLETE.txt').is_file()
    r.update(returncode=rc,status='COLLECTED_REQUIRES_REVIEW' if complete else 'FAILED',finished_epoch=time.time())
    r['outputs']={q.name:dict(bytes=q.stat().st_size,sha256=sha(q)) for q in sorted(a.out.iterdir()) if q.is_file() and q.name!='execution.json'}
    save();print(json.dumps(dict(status=r['status'],returncode=rc,errors=r['native_tool_errors'])),flush=True)
    return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())
