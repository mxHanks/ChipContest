#!/usr/bin/env python3
"""Fresh PT replay of receipt-bound exported LF SDC; collect bounded paths."""
from pathlib import Path
import argparse, hashlib, json, os, re, signal, subprocess, time


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--script',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();prev=a.previous.resolve();script=a.script.resolve()
    r=json.loads((prev/'run/execution.json').read_text())
    assert r['status']=='COLLECTED_REQUIRES_REVIEW' and r['returncode']==0 and not r['native_tool_errors']
    for n,item in r['outputs'].items():
        q=prev/'run'/n;assert q.stat().st_size==item['bytes'] and sha(q)==item['sha256'], 'Prior output drift'
    for item in r['inputs']:
        q=Path(item['path']);assert q.stat().st_size==item['bytes'] and sha(q)==item['sha256'], 'Prior input drift'
    tool=r['tool'];assert sha(Path(tool['path']))==tool['sha256']
    base=Path('/tmp/codex-ingress1064-n3-20261113-r2/candidate')
    chain=json.loads((base/'toolchain.json').read_text());lc=chain['library_compiler']
    assert sha(Path(lc['root'])/'bin/lc_shell')==lc['launcher_sha256']
    for q in Path('/proc').iterdir():
        if not q.name.isdigit():continue
        try:
            if q.stat().st_uid==os.getuid():assert (q/'comm').read_text().strip() not in {'pt_shell','dc_shell','fm_shell','vcs','simv'},'Other native job running'
        except OSError:pass
    allowed=sorted(os.sched_getaffinity(0));assert len(allowed)>=10;os.sched_setaffinity(0,allowed[:8])
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    sdc=prev/'run/revised-export.sdc'
    config=(prev/'run/config.tcl').read_text()+'set ::lf_contract_exported {'+str(sdc)+'}\nset ::lf_contract_exported_sha {'+sha(sdc)+'}\n'
    (a.out/'config.tcl').write_text(config)
    env=os.environ.copy();env.update(SYNOPSYS_LC_ROOT=lc['root'],XU_ECO_PACKAGE=str(prev/'src'),XU_ECO_CONFIG=str(a.out/'config.tcl'))
    rec=dict(schema='lf-input-contract-export-replay-v1',status='RUNNING',started_epoch=time.time(),
             prior_execution_sha256=sha(prev/'run/execution.json'),script_sha256=sha(script),driver_sha256=sha(Path(__file__)),
             exported_sdc_sha256=sha(sdc),tool=tool,libraries=r['libraries'],affinity=allowed[:8],max_cores=8,
             config_sha256=sha(a.out/'config.tcl'),command=[tool['path'],'-f',str(script)])
    def save():(a.out/'execution.json').write_text(json.dumps(rec,indent=2)+'\n')
    save()
    with (a.out/'native.log').open('w') as log:
        proc=subprocess.Popen(rec['command'],cwd=a.out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:rc=proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM);rc=proc.wait(timeout=20);rec['timed_out']=True
    rec['native_tool_errors']=re.findall(r'^(?:Error:|Fatal:).*$',(a.out/'native.log').read_text(errors='replace'),re.M)
    complete=rc==0 and not rec['native_tool_errors'] and (a.out/'LF_CONTRACT_EXPORT_COLLECTION_COMPLETE.txt').is_file()
    rec.update(returncode=rc,status='COLLECTED_REQUIRES_REVIEW' if complete else 'FAILED',finished_epoch=time.time())
    rec['outputs']={q.name:dict(bytes=q.stat().st_size,sha256=sha(q))for q in sorted(a.out.iterdir())if q.is_file()and q.name!='execution.json'}
    save();print(json.dumps(dict(status=rec['status'],returncode=rc,errors=rec['native_tool_errors'])),flush=True)
    return 0 if complete else 1
if __name__=='__main__':raise SystemExit(main())
