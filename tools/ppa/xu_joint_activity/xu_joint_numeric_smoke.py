#!/usr/bin/env python3
"""xu fresh short actual VCS collector run; no full SoC or energy qualification."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time


def identity(path):
    path=Path(path).resolve();data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def check_positive(directory):
    stats=directory/'task-joint.stats.jsonl';sidecar=directory/'task-joint.simultaneous.jsonl'
    rows=[json.loads(s) for s in stats.read_text(encoding='ascii').splitlines()]
    header=rows[0]
    expected=dict(task_id=0,transaction_argument_encoding='known-uint32-v1',
        begin_transaction='source_request cycle=1403985 addr=a0000000 read=1 valid=1 accept=1',
        end_transaction='final_y_retire cycle=2394641 request_cycle=2394640 addr=a00517fc response_valid=1 response_ready=1 writes=50688',
        start_tick=1000000,end_tick=4000000,duration_ticks=3000000,macro_count=1)
    if any(header.get(k)!=v for k,v in expected.items()):raise ValueError('numeric identity/window differs')
    spec=importlib.util.spec_from_file_location('xu_numeric_smoke_audit',Path(__file__).with_name('xu_sram_joint_audit.py'))
    auditor=importlib.util.module_from_spec(spec);spec.loader.exec_module(auditor)
    observed=auditor.audit(stats,sidecar)
    if observed['macro_count']!=1 or len(observed['macros'][0]['arcs'])!=121:raise ValueError('collector counters incomplete')
    return dict(exact_header_fields=expected,integer_audit_status=observed['status'],
        stats=identity(stats),sidecar=identity(sidecar),arc_count=121)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--vcs',default='vcs');parser.add_argument('--cc',default='gcc')
    parser.add_argument('--include',type=Path,required=True);args=parser.parse_args()
    here=Path(__file__).resolve().parent;root=here.parents[2]
    source=here/'xu_sram_joint_vpi.c';micro=root/'tests/ppa/tb_xu_sram_joint_micro.sv'
    tb=root/'tests/ppa/tb_xu_joint_numeric_smoke.sv'
    vcs=Path(shutil.which(args.vcs) or args.vcs).resolve()
    cc=Path(shutil.which(args.cc) or args.cc).resolve();include=args.include.resolve()
    if vcs.parent.parent not in (include/'vpi_user.h').resolve().parents:raise ValueError('VPI header must belong to selected VCS installation')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    frozen={str(p.resolve()):identity(p) for p in (source,micro,tb,Path(__file__),here/'xu_sram_joint_audit.py',here/'xu_sram1024x16_arc_ledger.json',vcs,cc,include/'vpi_user.h')}
    state=dict(schema='xu-joint-numeric-vcs-smoke-v1',status='RUNNING_NOT_FULL_SOC_OR_ENERGY',
        steps=[],started_epoch=time.time(),limitations=[
            'Synthetic one-macro pin fixture; numerical transaction values test transport, not elapsed CPU cycles.',
            'No vendor SRAM model, full SoC, SAIF/PT conditional semantics or energy qualification.',
            'This run cannot repair historical capture 36 or change existing twelve-task SAIF windows.'])
    def save():(out/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
    def recheck():
        if any(identity(p)!=record for p,record in frozen.items()):raise ValueError('frozen input changed')
    def run(command,name,cwd=None,negative=False):
        recheck();log=out/name
        with log.open('xb') as stream:
            result=subprocess.run(command,cwd=str(cwd or out),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
        state['steps'].append(dict(command=command,cwd=str(cwd or out),returncode=result.returncode,log=identity(log)));save();recheck()
        if result.returncode and not negative:raise ValueError('command failed '+name)
        return log.read_text(encoding='ascii')
    save()
    try:
        run([str(vcs),'-ID'],'vcs-version.log');run([str(cc),'--version'],'cc-version.log')
        library=out/'xu_sram_joint_vpi.so';deps=out/'dependencies.d'
        run([str(cc),'-std=c99','-D_POSIX_C_SOURCE=200809L','-fPIC','-shared','-Wall','-Wextra','-Wshadow','-Wstrict-prototypes','-Werror','-O2','-isystem',str(include),'-MD','-MF',str(deps),str(source),'-o',str(library)],'c-build.log')
        for p in shlex.split(deps.read_text().replace('\\\n',' ').split(':',1)[1]):frozen[str(Path(p).resolve())]=identity(p)
        frozen[str(library)]=identity(library);frozen[str(deps)]=identity(deps)
        binary=out/'smoke'
        run([str(vcs),'-full64','-sverilog','-timescale=1ns/1fs','-debug_access+all','-load',str(library)+':xu_sram_joint_register_tasks','-top','tb_xu_joint_numeric_smoke','-o',str(binary),str(micro),str(tb)],'vcs-build.log')
        frozen[str(binary)]=identity(binary);state['input_identities_before']=list(frozen.values());save()
        results=[]
        for mode in range(5):
            directory=out/('mode-%d'%mode);directory.mkdir()
            log=run([str(binary),'+MODE='+str(mode)],'mode-%d-simulation.log'%mode,directory,negative=mode>0)
            reject=re.findall(r'^XU_JOINT_REJECT (.+)$',log,re.M)
            complete=re.findall(r'^XU_JOINT_COMPLETE .+$',log,re.M)
            if mode==0:
                if reject or len(complete)!=1 or len(re.findall(r'^XU_JOINT_NUMERIC_SMOKE_DONE mode=0$',log,re.M))!=1:raise ValueError('positive completion missing')
                results.append(dict(mode=mode,positive=check_positive(directory)))
            else:
                expected={1:'numeric transaction argument contains X/Z',2:'end task/arguments differ',3:'final RETIRE numeric identity differs',4:'final RETIRE numeric identity differs'}[mode]
                if reject!=[expected] or complete:raise ValueError('negative rejection differs for mode '+str(mode))
                stats=directory/'task-joint.stats.jsonl'
                if stats.exists() and '"complete":true' in stats.read_text():raise ValueError('rejected capture has completion footer')
                results.append(dict(mode=mode,rejected=expected))
        recheck();state.update(status='EXECUTED_NUMERIC_IDENTITIES_AND_REJECTIONS_REVIEWED_NOT_FULL_SOC_OR_ENERGY',results=results,input_identities_after=list(frozen.values()))
    except Exception as error:state.update(status='FAIL',error=str(error));raise
    finally:state['finished_epoch']=time.time();save()
    print(json.dumps(dict(status=state['status'],out=str(out),cases=len(results)),sort_keys=True))


if __name__=='__main__':main()
