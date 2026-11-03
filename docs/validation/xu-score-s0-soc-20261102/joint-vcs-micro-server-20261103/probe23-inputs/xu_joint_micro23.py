"""xu new VCS/native-SAIF/owner-port variant; never edits micro19 evidence."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
OUT=Path.home()/'Desktop/xu-score-optimization-20261102/vcs-joint-micro-saif-20261103-23'
C=HERE/'xu_sram_joint_vpi23.c'
P=HERE/'xu_joint_probe23.c'
T=HERE/'tb_xu_sram_joint_micro23.sv'
INCLUDE=Path('/eda/synopsys/vcs/vcs_2020.03-SP2-6/include')
EXPECTED_C='cbeadf216665fc0b212ab3e239f299f4c83a64f59df561d8715414e854ed8cb1'


def identity(path):
    p=Path(path).resolve()
    if not p.is_file():raise ValueError('missing input '+str(p))
    return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def save(state):
    (OUT/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')


if len(sys.argv)==1:
    OUT.mkdir(exist_ok=False)
    with (OUT/'driver.log').open('x') as stream:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,
            stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    print('JOINT_SAIF_VCS_MICRO_STARTED pid=%d out=%s'%(process.pid,OUT))
    sys.exit(0)

state=dict(status='RUNNING_NOT_QUALIFIED',started_epoch=time.time(),steps=[],limitations=[
    'Open micro module, not vendor cell or actual whole-SoC task.',
    'Observed callback order and SV always-event order do not establish assignment or delta semantics.',
    'Native SAIF/raw joint and owner/port callbacks must be compared before any event-equivalence claim.',
    'No timing, power, energy or contest qualification.'])
save(state)
frozen={}


def freeze(path):
    record=identity(path);frozen[record['path']]=record


def recheck():
    if any(identity(path)!=record for path,record in frozen.items()):raise ValueError('frozen micro input changed')


def run(command,cwd,name):
    recheck()
    log=OUT/name
    with log.open('x') as stream:
        result=subprocess.run(command,cwd=str(cwd),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=600)
    state['steps'].append(dict(command=command,cwd=str(cwd),returncode=result.returncode,log=identity(log)))
    save(state);recheck()
    if result.returncode:raise ValueError('command failed: '+name)


try:
    for path in (C,P,T,Path(__file__),INCLUDE/'vpi_user.h',shutil.which('gcc'),shutil.which('vcs')):freeze(path)
    if identity(C)['sha256']!=EXPECTED_C:raise ValueError('must compile exact b2 cached C bytes')
    state['initial_input_identities']=list(frozen.values());save(state)
    run(['vcs','-ID'],OUT,'vcs-version.log');run(['gcc','--version'],OUT,'gcc-version.log')
    base=['gcc','-std=c99','-D_POSIX_C_SOURCE=200809L','-fPIC','-Wall','-Wextra','-Wshadow',
        '-Wstrict-prototypes','-Werror','-O2','-I'+str(INCLUDE)]
    for label,source in [('joint',C),('probe',P)]:
        dep=OUT/(label+'-dependencies.d')
        run(base+['-M','-MF',str(dep),str(source)],OUT,label+'-dependencies.log')
        data=dep.read_text().replace('\\\n',' ')
        for name in shlex.split(data.split(':',1)[1]):freeze(name)
        freeze(dep)
    state['input_identities_before_compile']=list(frozen.values());save(state)
    for label,source in [('joint',C),('probe',P)]:
        run(base+['-shared',str(source),'-o',str(OUT/(label+'.so'))],OUT,label+'-build.log')
    run(['vcs','-full64','-sverilog','-timescale=1ns/1fs','-debug_access+all','-debug_region+cell',
        '-load',str(OUT/'joint.so')+':xu_sram_joint_register_tasks',
        '-load',str(OUT/'probe.so')+':xu_sram_probe_register_tasks','-top','tb_xu_sram_joint_micro',
        '-o',str(OUT/'micro'),str(T)],OUT,'vcs-build.log')
    for path in (OUT/'micro',OUT/'joint.so',OUT/'probe.so'):freeze(path)
    state['input_identities_before_simulation']=list(frozen.values());save(state)
    for mode in range(4):
        destination=OUT/('mode-%d'%mode);destination.mkdir(exist_ok=False)
        run([str(OUT/'micro'),'+MODE='+str(mode),'+OUT='+str(destination/'joint')],
            destination,'mode-%d.log'%mode)
        text=(OUT/('mode-%d.log'%mode)).read_text()
        if 'XU_JOINT_REJECT' in text or 'XU_PROBE_REJECT' in text:raise ValueError('actual probe rejection mode '+str(mode))
        if mode<3:
            if 'XU_JOINT_COMPLETE' not in text or not (destination/'native.saif').is_file():raise ValueError('missing complete/native SAIF')
        elif 'XU_JOINT_INCOMPLETE' not in text or 'XU_PROBE_INCOMPLETE' not in text:raise ValueError('unfinished case not retained')
    recheck();state['input_identities_after']=list(frozen.values())
    state['outputs']=[identity(path) for path in sorted(OUT.rglob('*')) if path.is_file() and
        (path.suffix in ('.saif','.jsonl','.log','.d'))]
    state['status']='MICRO_SAIF_EXECUTED_REVIEW_PENDING_NOT_QUALIFIED'
except Exception as error:
    state.update(status='FAIL',error=str(error))
    raise
finally:
    state['finished_epoch']=time.time();save(state)
