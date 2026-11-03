import json,subprocess,time
from pathlib import Path
root=Path('/home/mxhanks/Projects/ChipContest-xu-pe32-bank128')
out=Path('/home/mxhanks/Projects/ChipContest-xu-pe32-bank128/build/xu-pe32-bank128-20261103')
steps=[('real1-old32', ['/usr/bin/python3', 'tools/scripts/e203_soc.py', '--mode', 'real', '--tasks', '1', '--sim', 'verilator', '--accel-variant', 'pe32', '--firmware-schedule', 'bias-hw-pe32-autogroup-window', '--firmware-opt=-O2', '--firmware-experiment', 'both-unroll-no-masks', '--out', '/home/mxhanks/Projects/ChipContest-xu-pe32-bank128/build/xu-pe32-bank128-20261103/real1-old32']), ('legacy5-bank128', ['/usr/bin/python3', 'tools/scripts/e203_soc.py', '--mode', 'baseline', '--sim', 'iverilog', '--accel-variant', 'pe32-bank128', '--firmware-schedule', 'bias-hw-pe32-autogroup-window', '--firmware-opt=-O2', '--firmware-experiment', 'both-unroll-no-masks', '--out', '/home/mxhanks/Projects/ChipContest-xu-pe32-bank128/build/xu-pe32-bank128-20261103/legacy5-bank128'])]
records=[]
for name,argv in steps:
 with (out/(name+"-driver.log")).open("wb") as f:
  records.append(dict(name=name,argv=argv,state="RUNNING"))
  (out/"control-driver.json").write_text(json.dumps(records,indent=2)+"\n")
  r=subprocess.run(argv,cwd=root,stdout=f,stderr=subprocess.STDOUT)
 records[-1].update(state="PASS" if r.returncode==0 else "FAIL",exit_code=r.returncode)
 (out/"control-driver.json").write_text(json.dumps(records,indent=2)+"\n")
 if r.returncode:break
