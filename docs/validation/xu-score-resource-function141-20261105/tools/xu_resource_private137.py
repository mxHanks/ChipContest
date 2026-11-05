from pathlib import Path
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
O = B / 'resource-private-readonly-20261105-137'
assert not O.exists()
O.mkdir()
state = dict(started_epoch=time.time(), qualification='NOT_QUALIFIED')
state['meminfo_kib'] = {k:int(v.split()[0]) for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines()) if v.strip().endswith('kB')}
state['loadavg'] = Path('/proc/loadavg').read_text().strip()
state['cpus'] = os.cpu_count()
state['disk'] = []
for p in [B, Path('/tmp'), Path('/storage1/admin_public_dir/SRAM_Lib_2025')]:
    s = os.statvfs(str(p))
    state['disk'].append(dict(path=str(p), available_bytes=s.f_bavail*s.f_frsize, free_bytes=s.f_bfree*s.f_frsize, total_bytes=s.f_blocks*s.f_frsize, available_inodes=s.f_favail))
state['jobs'] = []
for p in Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try:
        if p.stat().st_uid != os.getuid(): continue
        raw = (p/'cmdline').read_bytes().decode(errors='replace').replace('\0',' ')
        if not any(s in raw for s in ['pt_shell','dc_shell','fm_shell','simv','xu_s2e','xu_mapped']): continue
        if int(p.name) == os.getpid(): continue
        status = dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
        state['jobs'].append(dict(pid=int(p.name), command=raw, status={k:status[k].strip() for k in ['Name','State','VmRSS','VmPeak','Threads'] if k in status}))
    except (OSError, ValueError): pass
print('XU137_RESOURCES', json.dumps({k:state[k] for k in ['cpus','loadavg','disk']}, sort_keys=True), flush=True)
print('XU137_MEMORY', json.dumps({k:state['meminfo_kib'][k] for k in ['MemTotal','MemAvailable','SwapTotal','SwapFree']}, sort_keys=True), flush=True)
print('XU137_JOBS', json.dumps(state['jobs'], sort_keys=True), flush=True)
candidates = [shutil.which('lmutil')]
for pat in ['/eda/synopsys/*/*/bin/lmutil','/eda/synopsys/*/*/linux64/bin/lmutil','/eda/synopsys/*/*/linux64/syn/bin/lmutil']:
    candidates += sorted(glob.glob(pat))
lm = next((p for p in candidates if p and Path(p).is_file() and os.access(p,os.X_OK)), None)
state['license'] = dict(tool=lm, status='UNVERIFIED_NO_LMUTIL', features=[])
if lm:
    with (O/'license-native.log').open('xb') as f:
        try:
            r = subprocess.run([lm,'lmstat','-a'], stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, timeout=45)
            state['license'].update(returncode=r.returncode,status='NATIVE_QUERY_REVIEW_PENDING')
        except subprocess.TimeoutExpired:
            state['license']['status']='NATIVE_QUERY_TIMEOUT_UNKNOWN'
    raw=(O/'license-native.log').read_bytes()
    state['license']['log']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    text=raw.decode(errors='replace')
    state['license']['features']=[dict(feature=m[0],issued=int(m[1]),in_use=int(m[2])) for m in re.findall(r'Users of ([^:]+):\s*\(Total of (\d+) licenses? issued;\s*Total of (\d+) licenses? in use\)',text)]
    if not state['license']['features']:state['license']['tail']=text[-2000:]
print('XU137_LICENSE', json.dumps(state['license'], sort_keys=True), flush=True)
out=B/'private-target133-static-new'
log=B/'private-target133-static-new.stdout.log'
rc=B/'private-target133-static-new.returncode'
assert not out.exists() and not log.exists() and not rc.exists()
command=[sys.executable,str(Path.home()/'Desktop/xu-mapped-private133/extract_private133.py'),'--mapped',str(B/'s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v'),'--out',str(out)]
with log.open('xb') as f:
    result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT)
rc.write_text(str(result.returncode)+'\n')
state['private133']=dict(command=command,returncode=result.returncode,output=str(out),log_bytes=log.stat().st_size,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
print('XU137_PRIVATE133', json.dumps(state['private133'],sort_keys=True),flush=True)
print(log.read_text(errors='replace')[-3000:],flush=True)
state['finished_epoch']=time.time()
(O/'state.json').write_text(json.dumps(state,sort_keys=True,indent=2)+'\n')
print('XU137_READONLY_DONE_NOT_QUALIFIED',flush=True)
