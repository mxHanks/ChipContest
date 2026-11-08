from pathlib import Path
import csv, hashlib, json, shutil
root=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest')
b=root/'build/writeback-v2-20261108'
out=root/'docs/validation/s3-y32-writeback-v2-20261108'
out.mkdir(exist_ok=True,parents=True)
def copy(src,dest):
 if src.is_file():
  dest.parent.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(src,dest)
for label,src in [('baseline-full12',root/'build/writeback-20261108/read-pop-full12'),('direct-full12',b/'direct-full12'),('burst-full12',b/'burst-full12'),('direct-legacy-task0',b/'direct-legacy-task0')]:
 for name in ['result.json','plan.json','clear-recipe.json']:
  copy(src/name,out/label/name)
 for log in src.glob('task-*/simulation.log'):
  copy(log,out/label/log.relative_to(src))
for name in ['direct-comparison.json','direct-comparison.log','direct-source-differences.json','direct-postvalidation-receipt.json','integrated-production-source-check.json','burst-summary.json','burst-review.patch','burst-changed-files.json','burst-summarize.py','cpu-experiments.json','cpu-unroll4-comparison.json','cpu-unroll32-comparison.json']:
 copy(b/name,out/name)
for src in (b/'checks').rglob('*'):
 if src.suffix in ('.log','.json','.py'):
  copy(src,out/'checks'/src.relative_to(b/'checks'))
for src in (b/'direct-proof').rglob('*'):
 if src.suffix in ('.log','.json','.txt') and 'obj' not in src.relative_to(b/'direct-proof').parts:
  copy(src,out/'direct-proof'/src.relative_to(b/'direct-proof'))
for label in ['direct-task0','direct-task0-diagnostic','direct-task0-phase','cpu-baseline-task0','cpu-unroll4-task0','cpu-unroll32-task0']:
 for name in ['result.json','plan.json','clear-recipe.json','simulator-build.log']:
  copy(b/label/name,out/label/name)
 for log in (b/label).glob('task-*/simulation.log'):
  copy(log,out/label/log.relative_to(b/label))
for src in (b/'direct-first-stall7').iterdir():
 copy(src,out/'direct-first-stall7'/src.name)
poll=b/'poll-repo/experiments/poll_backoff'
for name in ['summary.json','report.md','baseline-provenance.json','poll-backoff-rtl-default0.patch','poll-backoff-candidate13.patch','poll-backoff-diagnostics.patch']:
 copy(poll/name,out/'poll'/name)
for label in ['backoff-0','backoff-0-r1','backoff-2','backoff-8','backoff-13']:
 src=poll/label
 for name in ['result.json','plan.json','poll-analysis.json','simulator-build.log']:
  copy(src/name,out/'poll'/label/name)
 for log in src.glob('task-*/simulation.log'):
  copy(log,out/'poll'/label/log.relative_to(src))
for folder,label in [(poll/'unit','poll/unit'),(b/'burst-unit','burst-unit')]:
 for src in folder.iterdir():
  if src.suffix in ('.log','.json'):
   copy(src,out/label/src.name)
# Record the single-variable source change for the reversible CPU candidates.
import subprocess
for factor in [4,32]:
 cmd=['diff','-u','--label','baseline/tests/e203/firmware/accel.c','--label',f'unroll{factor}/tests/e203/firmware/accel.c',str(b/'cpu-repo/tests/e203/firmware/accel.c'),str(b/f'cpu-unroll{factor}-repo/tests/e203/firmware/accel.c')]
 r=subprocess.run(cmd,stdout=subprocess.PIPE,check=False)
 assert r.returncode==1
 (out/f'cpu-unroll{factor}.patch').write_bytes(r.stdout)
base=json.loads((out/'baseline-full12/result.json').read_text())
direct=json.loads((out/'direct-full12/result.json').read_text())
burst=json.loads((out/'burst-full12/result.json').read_text())
with (out/'layers.csv').open('w',newline='') as f:
 w=csv.writer(f)
 w.writerow(['original_layer','baseline_payload','direct_payload','drainn_payload','clear_cycles','baseline_payload_plus_clear','direct_payload_plus_clear','drainn_payload_plus_clear','direct_delta','drainn_delta'])
 for a,c,n in zip(base['task_results'],direct['task_results'],burst['task_results']):
  assert a['original_layer']==c['original_layer']==n['original_layer']
  clear=int(a['clear']['clear_cycles']); assert clear==int(c['clear']['clear_cycles'])==int(n['clear']['clear_cycles'])
  w.writerow([a['original_layer'],a['cycles'],c['cycles'],n['cycles'],clear,a['cycles']+clear,c['cycles']+clear,n['cycles']+clear,c['cycles']-a['cycles'],n['cycles']-a['cycles']])
manifest={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ['sha256.json','README.md']}
(out/'sha256.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print('files',len(manifest),'bytes',sum((out/name).stat().st_size for name in manifest))
