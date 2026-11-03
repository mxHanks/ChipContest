#!/usr/bin/env python3
"""xu: require actual frozen32PE full12 VCS acceptance, then run fresh same-library DC/PT.

This launcher does not contact a server or read credentials. Run it on the EDA
server after deploying the frozen candidate and this producer/tool commit.
All outputs remain NOT_QUALIFIED; energy and retention are separate work.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[2]
BASE = Path.home()/'Desktop/xu-score-optimization-20261102'
MAIN = '94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114'
CHILD = 'fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5'
STANDARD_SHA = 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
SRAM_SHA = 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def git(path,*args):
    return subprocess.check_output(['git','--no-replace-objects']+list(args),cwd=str(path),universal_newlines=True).strip()


def checked_acceptance(source,acceptance):
    state=json.loads((acceptance/'state.json').read_text())
    require(state['status']=='VCS_ACCEPTED_NOT_RETAINED' and state['main_commit']==MAIN and state['e203_commit']==CHILD,
            'frozen complete actual32PE VCS acceptance required before PPA')
    require(git(source,'rev-parse','HEAD')==MAIN and git(source/'third-party/e203_hbirdv2','rev-parse','HEAD')==CHILD,
            'source commit differs from accepted candidate')
    require(not git(source,'status','--porcelain') and not git(source/'third-party/e203_hbirdv2','status','--porcelain'),
            'accepted source is dirty')
    expected_steps=['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12',
                    'pe32-autogroup-control-real12','pe8-autogroup-control-real12']
    require([s['name'] for s in state['steps']]==expected_steps and all(s['status']=='PASS' for s in state['steps']),
            'eight acceptance steps plus two controls required')
    require(set(state['direct_vcs'])=={'wide','compat'} and all(d['status']=='PASS' and d['backend']=='vcs' for d in state['direct_vcs'].values()),
            'both mandatory new-wrapper direct VCS tests required')
    for kind in ['wide','compat']:
        directory=acceptance/'direct-pe32-vcs'/kind
        for filename,digest in state['direct_vcs'][kind]['logs'].items():
            require(sha(directory/filename)==digest,'direct VCS log changed: '+kind+'/'+filename)
        text=(directory/'simulation.log').read_text().split('\n',1)[1]
        prefix='XU_PE32'+('_COMPAT' if kind=='compat' else '')+'_WRAPPER_PASS'
        found=re.findall(prefix+r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)',text)
        require(len(found)==1,'direct VCS completion missing/duplicate: '+kind)
        values=list(map(int,found[0]));expected=[16,27,27,11124,11124] if kind=='wide' else [64,99,99,11737,11737]
        require(values[1]>0 and [values[0]]+values[2:]==expected and values==state['direct_vcs'][kind]['counts'],
                'direct VCS work/retirement counts differ: '+kind)
        require('"vcs"' in (directory/'compile.log').read_text().split('\n',1)[0], 'direct compiler is not VCS')
    sys.path.insert(0,str(source/'tools/scripts'))
    import e203_soc as soc
    results={}
    for name,variant,schedule in [('real12','pe32','bias-hw-pe32-autogroup-window'),
            ('pe32-autogroup-control-real12','pe32','bias-hw-autogroup-window'),
            ('pe8-autogroup-control-real12','pe8','bias-hw-autogroup-window')]:
        directory=acceptance/'acceptance'/name
        result=json.loads((directory/'result.json').read_text())
        text=(directory/'simulation.log').read_text().split('\n',1)[1]
        layers=soc.check_log(text,12)
        for layer,performance in zip(layers,soc.check_performance(text,layers,schedule,variant)):layer['performance']=performance
        require(result['status']=='PASS' and result['tasks']==12 and result['layers']==layers and result['main_commit']==MAIN and
                result['e203_commit']==CHILD and result['simulator']=='vcs' and result['accel_variant']==variant and
                result['firmware_schedule']==schedule and result['firmware_opt']=='-O2' and
                result['firmware_experiment']=='both-unroll-no-masks', 'actual full12 identity/counters differ: '+name)
        require(result['pe_activity']==soc.check_pe_activity(text,layers,schedule,variant) and
                result['autogroup_activity']==soc.check_autogroup_activity(text,layers,schedule), 'PE/FIFO/row work differs: '+name)
        for relative,digest in result['source_sha256'].items():
            prefix='third-party/e203_hbirdv2/vsim/install/rtl/'
            path=source/'third-party/e203_hbirdv2/rtl/e203'/relative[len(prefix):] if relative.startswith(prefix) else source/relative
            require(sha(path)==digest,'measured source changed: '+relative)
        require(sha(source/'tools/scripts/e203_soc.py')==result['runner_sha256'] and
                sha(source/'tools/scripts/xu_firmware_contract.py')==result['contract_sha256'], 'runner/contract changed')
        for filename,digest in result['firmware_sha256'].items():require(sha(source/'tests/e203/firmware'/filename)==digest,'firmware source changed')
        for filename,digest in result['log_sha256'].items():require(sha(directory/filename)==digest,'measured log changed: '+filename)
        require(sha(directory/'accel_soc')==result['firmware_elf_sha256'] and sha(directory/'accel_soc.verilog')==result['firmware_image_sha256'], 'ELF/image changed')
        results[name]=result
    wide=results['real12'];same=results['pe32-autogroup-control-real12'];old=results['pe8-autogroup-control-real12']
    for key in ['source_sha256','versions','tools','fixture','vectors','firmware_sha256','runner_sha256','contract_sha256']:
        require(wide[key]==same[key]==old[key], 'three-way identity mismatch: '+key)
    require(wide['simulator_sha256']==same['simulator_sha256']!=old['simulator_sha256'], 'same32/distinct8 executable required')
    return dict(state_sha256=sha(acceptance/'state.json'),
                result_sha256={name:sha(acceptance/'acceptance'/name/'result.json') for name in results},
                measured_total_cycles={name:sum(x['cycles'] for x in result['layers']) for name,result in results.items()})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=BASE/'ChipContest-s3-pe32-01')
    p.add_argument('--acceptance',type=Path,default=BASE/'s3-pe32-accept-01')
    p.add_argument('--producer-root',type=Path,default=TOOLS)
    p.add_argument('--out',type=Path,default=BASE/'s3-pe32-ppa-campaign-20261103-01')
    p.add_argument('--standard-cell-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db')
    p.add_argument('--sram-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db')
    p.add_argument('--foreground',action='store_true',help='run directly; otherwise detach with durable PID/log')
    a=p.parse_args();out=a.out.resolve();producer=a.producer_root.resolve();source=a.source.resolve()
    if not a.foreground:
        require(not out.exists(),'fresh output directory required')
        # Verify acceptance before creating any output or detached process.
        checked_acceptance(source,a.acceptance.resolve())
        out.mkdir(parents=True)
        command=[sys.executable,str(Path(__file__).resolve())]+sys.argv[1:]+['--foreground']
        with (out/'driver.log').open('xb') as stream:
            process=subprocess.Popen(command,cwd=str(producer),env=dict(os.environ,PWD=str(producer)),stdin=subprocess.DEVNULL,
                stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        boot=dict(status='LAUNCHED_NOT_QUALIFIED',pid=process.pid,argv=command,launcher_sha256=sha(Path(__file__)))
        (out/'boot.json').write_text(json.dumps(boot,indent=2)+'\n');print(json.dumps(boot),flush=True);return
    if out.exists():
        require({path.name for path in out.iterdir()} <= {'driver.log','boot.json'}, 'foreground output is not fresh')
    else:
        out.mkdir(parents=True)
    require(not (out/'state.json').exists(),'fresh foreground campaign required')
    state=dict(status='RUNNING_NOT_QUALIFIED',source=str(source),producer_root=str(producer),profile='s3-pe32',steps=[])
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat()
        (out/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    try:
        state['acceptance']=checked_acceptance(source,a.acceptance.resolve());save()
        require(sha(a.standard_cell_db)==STANDARD_SHA and sha(a.sram_db)==SRAM_SHA,'same-server frozen library SHA differs')
        spec=importlib.util.spec_from_file_location('xu_pe32_implementation',producer/'tools/ppa/xu_soc_implementation.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);ppa=module.ppa_module()
        require(ppa.SOURCE_PROFILES['s3-pe32']['commit']==CHILD and ppa.PE32_CONFIGURATION['full_soc_macros']==352,
                'producer lacks approved complete PE32 geometry profile')
        commands=[
            [sys.executable,producer/'tools/ppa/xu_soc_implementation.py','--root',source,'--profile','s3-pe32','--out',out/'implementation',
             '--standard-cell-db',a.standard_cell_db,'--standard-cell-sha256',STANDARD_SHA,'--sram-db',a.sram_db,'--sram-sha256',SRAM_SHA],
            [sys.executable,producer/'tools/scripts/xu_soc_ppa.py','prepare','--root',source,'--implementation',out/'implementation/implementation.json',
             '--out',out/'ppa','--allow-unqualified-mapping'],
            [sys.executable,producer/'tools/scripts/xu_soc_ppa.py','run','--root',source,'--out',out/'ppa']]
        state['tool_sha256']={name:sha(producer/name) for name in ['tools/ppa/xu_soc_implementation.py','tools/scripts/xu_soc_ppa.py']}
        for index,command in enumerate(commands):
            record=dict(index=index,argv=[str(x) for x in command],status='RUNNING');state['steps'].append(record);save()
            with (out/('step-%d.log'%index)).open('x') as stream:
                stream.write(json.dumps(dict(argv=record['argv'],cwd=str(producer)))+'\n');stream.flush()
                result=subprocess.run(record['argv'],cwd=str(producer),env=dict(os.environ,PWD=str(producer)),stdin=subprocess.DEVNULL,
                    stdout=stream,stderr=subprocess.STDOUT,timeout=21600)
            record.update(returncode=result.returncode,status='PASS' if result.returncode==0 else 'FAIL');save()
            require(result.returncode==0,'PPA step%d failed; preserve actual raw DC/PT reports'%index)
        execution=json.loads((out/'ppa/execution.json').read_text());require(execution['status']=='EXECUTED_NOT_QUALIFIED','PPA execution incomplete')
        for name,digest in state['tool_sha256'].items():require(sha(producer/name)==digest,'producer changed during execution')
        checked_acceptance(source,a.acceptance.resolve())
        state.update(status='EXECUTED_NOT_QUALIFIED',execution_sha256=sha(out/'ppa/execution.json'),
            not_run=['candidate-specific formal clear/request activity','mapped consistency','fullSoC task energy','retention'])
    except Exception as error:
        state.update(status='FAIL',error=str(error));save();raise
    save();print('XU_PE32_PPA_DONE '+state['status'],flush=True)


if __name__=='__main__':
    main()
