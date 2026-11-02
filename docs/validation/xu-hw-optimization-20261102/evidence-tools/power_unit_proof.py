#!/usr/bin/env python3
"""Extract only unit declarations from the installed command reference."""
from pathlib import Path
import hashlib,json,os,re,subprocess
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';O=B/'power-unit-proof-01';O.mkdir(exist_ok=False)
(O/'probe.tcl').write_text('man report_power > installed-report-power-reference.txt\nprintvar *power*unit*\nputs "XU_UNIT_PROBE_COMPLETE"\nexit 0\n')
lc='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env=dict(os.environ,SYNOPSYS_LC_ROOT=lc);env['PATH']=lc+'/bin:'+env['PATH']
with (O/'pt.log').open('x') as f:r=subprocess.run(['pt_shell','-f','probe.tcl'],cwd=str(O),env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
raw=(O/'installed-report-power-reference.txt').read_bytes();lines=raw.decode(errors='replace').splitlines();found=[]
for i,line in enumerate(lines):
 if re.search(r'\bwatts?\b|\bunits?\b',line,re.I):found.append(dict(line=i+1,context='\n'.join(lines[max(0,i-1):i+2])))
j=dict(schema='xu-installed-power-unit-reference-v1',returncode=r.returncode,reference_path=str(O/'installed-report-power-reference.txt'),reference_sha256=hashlib.sha256(raw).hexdigest(),unit_excerpts=found,probe_sha256=hashlib.sha256((O/'probe.tcl').read_bytes()).hexdigest(),log_sha256=hashlib.sha256((O/'pt.log').read_bytes()).hexdigest(),log=(O/'pt.log').read_text(errors='replace'))
(O/'unit-reference.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n');print(json.dumps(j,sort_keys=True))
