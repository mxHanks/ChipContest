#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,sys,time
R=Path(__file__).resolve().parents[2]
O=Path(__file__).resolve().parent
cases=[('wide64-real1-02','real','pe64','bias-hw-pe64-autogroup-window'),
       ('compat32-real1-01','real','pe64','bias-hw-pe32-autogroup-window'),
       ('compat8-real1-01','real','pe64','bias-hw-autogroup-window'),
       ('physical32-real1-01','real','pe32','bias-hw-pe32-autogroup-window'),
       ('physical8-real1-01','real','pe8','bias-hw-autogroup-window'),
       ('pe64-legacy5-01','baseline','pe64','baseline')]
state=dict(status='RUNNING_LOCAL_NOT_QUALIFIED',started=time.time(),cases=[])
def save():(O/'screen-state.json').write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
save()
for name,mode,variant,schedule in cases:
 command=[sys.executable,str(R/'tools/scripts/e203_soc.py'),'--mode',mode,'--tasks','1',
          '--sim','iverilog'if mode=='baseline'else'verilator','--accel-variant',variant,
          '--firmware-schedule',schedule,'--firmware-opt=-O2',
          '--firmware-experiment','both-unroll-no-masks','--out',str(O/name)]
 record=dict(name=name,command=command,started=time.time());state['cases'].append(record);save()
 with(O/(name+'.log')).open('x')as log:
  result=subprocess.run(command,cwd=R,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
 record.update(returncode=result.returncode,finished=time.time());save()
 if result.returncode:state['status']='FAILED_LOCAL_REVIEW_REQUIRED';save();sys.exit(1)
state.update(status='COMPLETED_LOCAL_NOT_QUALIFIED',finished=time.time());save()
