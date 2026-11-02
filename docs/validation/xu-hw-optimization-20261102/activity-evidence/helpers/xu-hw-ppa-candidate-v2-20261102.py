#!/usr/bin/env python3
"""Same-library/constraint complete new-wrapper PPA against frozen old-wrapper baseline."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

base=Path.home()/'Desktop/xu-hw-optimization-20261102/ppa'
old=base/'baseline-ss-01'
out=base/'candidate-ss-02'
rtl=base/'frozen-hw-rtl-02'
repo=base.parent/'ChipContest'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(data):(out/'job-state.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


action=sys.argv[1]
if action=='setup':
    main=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(repo)).decode().strip()
    sub=repo/'third-party/e203_hbirdv2'
    child=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(sub)).decode().strip()
    if main!='97b35421dfbbfa8f4d495b6927a7c66610ff8206' or child!='f49a5fc914971426bd4530db39e270a84b41139f':
        raise ValueError('hardware frozen source mismatch')
    if subprocess.check_output(['git','diff','--name-only','HEAD','--','rtl'],cwd=str(sub)).strip():
        raise ValueError('hardware source dirty')
    out.mkdir(exist_ok=False)
    rtl.mkdir(exist_ok=False)
    previous=json.loads((old/'manifest.json').read_text())
    for name in previous['source_sha256']:
        path=(base/'frozen-fw-rtl'/name) if name=='xu-sram-adapter.sv' else sub/'rtl/e203/perips'/name
        shutil.copyfile(str(path),str(rtl/name))
    for name in ['BiasBankCache.sv','LinearCachedCore.sv']:
        shutil.copyfile(str(sub/'rtl/e203/perips'/name),str(rtl/name))
    for name in previous['source_sha256']:
        if name!='accel_icb_slave.v' and sha(rtl/name)!=previous['source_sha256'][name]:
            raise ValueError('original computation core or macro adapter changed: '+name)
    manifest=dict(previous,source_repository=str(repo),source_commit=main,e203_commit=child,
        source_sha256={p.name:sha(p) for p in sorted(rtl.iterdir())},
        comparison='complete new wrapper incl 256x40 Reg bias cache and result window vs complete old wrapper; original nine core SV unchanged')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    shutil.copyfile(str(old/'constraints.sdc'),str(out/'constraints.sdc'))
    text=(old/'synth.tcl').read_text().replace(str(base/'frozen-fw-rtl'),str(rtl))
    marker='if {![analyze -format sverilog {'+str(rtl/'accel_icb_slave.v')+'}]}'
    insertion=''.join('if {![analyze -format sverilog {'+str(rtl/name)+'}]} {error {analysis failed: '+name+'}}\n' for name in ['BiasBankCache.sv','LinearCachedCore.sv'])
    if marker not in text:raise ValueError('baseline analyze marker missing')
    text=text.replace(marker,insertion+marker)
    (out/'synth.tcl').write_text(text)
    shutil.copyfile(str(base/'pt-baseline-fixed-01/pt.tcl'),str(out/'pt.tcl'))
    print('CANDIDATE_PPA_PREPARED '+str(out)+' constraints_sha256='+sha(out/'constraints.sdc'))
elif action=='start':
    if (out/'job-state.json').exists() or (out/'driver.log').exists():raise ValueError('candidate PPA already started')
    with (out/'driver.log').open('x') as stream:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'execute'],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    print('STARTED candidate PPA pid='+str(process.pid),flush=True)
elif action=='execute':
    state=dict(status='RUNNING',stage='dc',started_epoch=time.time())
    save(state)
    try:
        manifest=json.loads((out/'manifest.json').read_text())
        for name,digest in manifest['source_sha256'].items():
            if sha(rtl/name)!=digest:raise ValueError('frozen source changed')
        for name,value in manifest['libraries'].items():
            if sha(Path(name))!=value['sha256']:raise ValueError('PPA library changed')
        for stage,command in [('dc',['dc_shell','-64bit','-f','synth.tcl']),('pt',['pt_shell','-f','pt.tcl'])]:
            state['stage']=stage
            save(state)
            lc='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'
            env=dict(os.environ,SYNOPSYS_LC_ROOT=lc)
            env['PATH']=lc+'/bin:'+env.get('PATH','')
            with (out/(stage+'.log')).open('x') as stream:
                result=subprocess.run(command,cwd=str(out),env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=7200)
            text=(out/(stage+'.log')).read_text(errors='replace')
            errors=re.findall(r'^Error:.*$',text,re.M)
            state[stage+'_returncode']=result.returncode
            state[stage+'_errors']=errors
            if result.returncode or errors:raise RuntimeError(stage+' failed: '+str(errors))
            marker='XU_DC_BASELINE_PASS' if stage=='dc' else 'XU_PT_STA_PASS'
            if marker not in text.splitlines():raise ValueError('missing actual '+stage+' PASS marker')
        state.update(status='PASS',stage='complete')
    except Exception as error:state.update(status='FAIL',error=str(error))
    state['finished_epoch']=time.time()
    state['log_sha256']={p.name:sha(p) for p in sorted(out.glob('*.log'))}
    state['report_sha256']={p.name:sha(p) for p in sorted(out.glob('*.rpt'))}
    save(state)
    print(json.dumps(state,sort_keys=True),flush=True)
elif action=='status':
    if (out/'job-state.json').exists():print((out/'job-state.json').read_text())
    for name in ['dc.log','pt.log']:
        if (out/name).exists():print(name+'\n'+(out/name).read_text(errors='replace')[-1500:])
else:raise ValueError('unknown action')
