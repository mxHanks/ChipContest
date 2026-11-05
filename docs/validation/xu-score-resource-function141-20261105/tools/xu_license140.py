from pathlib import Path
import json
import os
import re
import subprocess
import time

B=Path.home()/'Desktop/xu-score-optimization-20261102'
O=B/'license-readonly-20261105-140'
assert not O.exists()
O.mkdir()
state=dict(started_epoch=time.time(),status='LICENSE_UNKNOWN',qualification='NOT_QUALIFIED')
with (O/'discovery.log').open('xb') as f:
    try:
        r=subprocess.run(['find','/eda','/opt','/usr/local','-maxdepth','10','(','-name','lmutil','-o','-name','lmstat',')'],stdout=f,stderr=subprocess.STDOUT,timeout=45)
        state['discovery_returncode']=r.returncode
    except subprocess.TimeoutExpired:state['discovery_timed_out']=True
lines=(O/'discovery.log').read_text(errors='replace').splitlines()
paths=[p for p in lines if p.startswith('/') and Path(p).is_file() and os.access(p,os.X_OK)]
state['tools']=paths
print('XU140_LICENSE_TOOLS',json.dumps(paths),flush=True)
if paths:
    tool=paths[0]
    command=[tool]+(['lmstat'] if Path(tool).name=='lmutil' else [])+['-a']
    license_location=os.environ.get('SNPSLMD_LICENSE_FILE') or os.environ.get('LM_LICENSE_FILE')
    if license_location:command+=['-c',license_location]
    with (O/'native.log').open('xb') as f:
        try:
            r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=45)
            state['native_returncode']=r.returncode
        except subprocess.TimeoutExpired:state['native_timed_out']=True
    text=(O/'native.log').read_text(errors='replace')
    state['features']=[dict(feature=m[0],issued=int(m[1]),in_use=int(m[2]),available=int(m[1])-int(m[2])) for m in re.findall(r'Users of ([^:]+):\s*\(Total of (\d+) licenses? issued;\s*Total of (\d+) licenses? in use\)',text)]
    if state.get('native_returncode')==0 and state['features']:state['status']='NATIVE_LICENSE_INVENTORY_REVIEW_PENDING'
    print('XU140_LICENSE',state['status'],json.dumps(state.get('features',[]),sort_keys=True),flush=True)
    if not state.get('features'):print(text[-2000:],flush=True)
state['finished_epoch']=time.time()
(O/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
print('XU140_LICENSE_DONE',state['status'],flush=True)
