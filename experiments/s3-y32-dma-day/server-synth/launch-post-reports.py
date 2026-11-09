#!/usr/bin/env python3
import hashlib,json,os,subprocess,time
from pathlib import Path
home=Path.home();desktop=home/'Desktop';root=desktop/'xu-dma-synth-20261109-r3/candidate';out=desktop/'xu-dma-synth-20261109-r3-post'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((root/'execution.json').read_text())['status']=='SYNTHESIS_COMPLETE_NOT_QUALIFIED'
seal=json.loads((desktop/'xu-dma-synth-20261109-r3-return/final-files.json').read_text())
assert sha(root/'mapped.ddc')==seal['files']['mapped.ddc']['sha256']
names=set(subprocess.check_output(['ps','-u',str(os.getuid()),'-o','comm='],universal_newlines=True).split())
assert not names.intersection({'common_shell_ex','dc_shell','dc_shell-xg-t','pt_shell','fm_shell'}),'EDA slot busy'
original=json.loads((root/'execution.json').read_text())
for lib in original['libraries']:assert sha(Path(lib['path']))==lib['sha256'],'library drift'
assert not out.exists();out.mkdir(mode=0o700)
src=desktop/'codex-dma-synth-post-clock-reports.tcl';(out/'post.tcl').write_bytes(src.read_bytes())
tool='/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell'
record=dict(schema='xu-dma-read-mapped-report-recovery-v1',mode='NO_COMPILE_READ_DDC_REPORTS_ONLY',started_epoch=time.time(),mapped_ddc_sha256=sha(root/'mapped.ddc'),script_sha256=sha(out/'post.tcl'),command=[tool,'-f','post.tcl'],status='RUNNING',libraries=original['libraries'],tool_sha256=sha(Path(tool)))
(out/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
with (out/'post.log').open('w') as log:
 p=subprocess.Popen(record['command'],cwd=out,stdout=log,stderr=subprocess.STDOUT);record['pid']=p.pid
 (out/'execution.json').write_text(json.dumps(record,indent=2)+'\n');code=p.wait()
record.update(returncode=code,finished_epoch=time.time(),completion_marker=(out/'REPORT_RECOVERY_COMPLETE_NOT_QUALIFIED.txt').exists());record['status']='REPORTS_RECOVERED_NOT_QUALIFIED' if code==0 and record['completion_marker'] else 'FAILED'
record['outputs']={f.name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f in out.iterdir() if f.is_file() and f.name!='execution.json'}
(out/'execution.json').write_text(json.dumps(record,indent=2)+'\n');print(record['status'])
