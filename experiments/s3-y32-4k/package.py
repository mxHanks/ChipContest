#!/usr/bin/env python3
"""Seal a completed CPU experiment for read-only verification or explicit replay."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[2]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
REPLAY=r'''#!/usr/bin/env python3
import argparse,datetime,hashlib,importlib.util,json,pathlib,subprocess,sys
sys.dont_write_bytecode=True
root=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser(description='Default: verify sealed files; --run explicitly starts local simulation')
p.add_argument('--run',action='store_true');p.add_argument('--rebuild',action='store_true');p.add_argument('--out',type=pathlib.Path)
p.add_argument('--deadline',default='2026-11-10T23:59:00+08:00',help='A later deadline needs renewed user authorization')
a=p.parse_args()
if a.rebuild and not a.run:p.error('--rebuild requires --run')
manifest=json.loads((root/'SHA256.json').read_text())
for path,digest in manifest.items():
    item=root/path
    if not item.is_file() or hashlib.sha256(item.read_bytes()).hexdigest()!=digest:raise SystemExit('File identity mismatch: '+path)
print('SEALED_FILES_PASS',len(manifest),flush=True)
if not a.run:raise SystemExit(0)
if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(a.deadline).astimezone(datetime.timezone.utc):p.error('Experiment deadline reached; verify-only remains available')
if a.out is None:p.error('--run requires a new --out directory')
out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
record=json.loads((root/'cpu/result.json').read_text());args=record['arguments'];binary=root/'cpu/simulator/dma_day_soc'
if a.rebuild:
    source=root/'cpu/source';rtl=source/'rtl'
    filelist=out/'rtl.f';filelist.write_text(''.join(str(x)+'\n' for x in sorted(rtl.rglob('*')) if x.suffix in ('.v','.sv'))+str(source/'tests/tb_dma64_soc.sv')+'\n')
    command=['verilator','--binary','--timing','--assert','-CFLAGS','-std=gnu++20','-Wno-fatal','-j','2','--top-module','tb_dma64_soc','-Mdir',str(out/'obj'),'-o','dma_day_soc','-DDISABLE_SV_ASSERTION=1','-DXU_MATRIX_DMA','-DXU_MATRIX_DMA64','-DD4K_THROTTLE='+str(args['throttle']),*['-I'+str(x) for x in (rtl/'core',rtl/'perips',rtl/'perips/apb_i2c',source/'tests')],'-f',str(filelist)]
    (out/'build-command.json').write_text(json.dumps(command,indent=2)+'\n')
    with (out/'build.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    binary=out/'obj/dma_day_soc'
if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(a.deadline).astimezone(datetime.timezone.utc):p.error('Experiment deadline reached before simulation')
command=[str(binary),'+TESTCASE='+str(root/'cpu/firmware/dma_day_soc'),'+VECTORS='+str(root/'cpu/vectors'),'+TASKS='+str(args['tasks']),'+ROWS='+str(args['rows']),'+WARMUP='+str(int(args['warmup'])),'+MAX_CYCLES='+str(args['max_cycles']),'+FIRST_SOURCE_STALL='+str(args['first_source_stall'])]
(out/'command.json').write_text(json.dumps(command,indent=2)+'\n')
with (out/'simulation.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
checker=root/'cpu/source/check_results.py';spec=importlib.util.spec_from_file_location('sealed_checker',checker);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
result=module.check_log((out/'simulation.log').read_text(),args['tasks'],args['rows'],args['warmup'])
(out/'verified-result.json').write_text(json.dumps(result,indent=2)+'\n')
print('REAL_CPU_REPLAY_PASS',result['outputs'],result['principal_cycles'],flush=True)
'''

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run=a.candidate.resolve();out=a.out.resolve()
 r=json.loads((run/'result.json').read_text())
 if r.get('status')!='PASS' or r.get('arguments',{}).get('tasks')!=12 or not r.get('full12_target_met') or any(x['principal']>37500 for x in r['layers']):raise ValueError('Complete CPU12 PASS and all cycle gates required')
 actual={x.relative_to(run/'source').as_posix():sha(x) for x in (run/'source').rglob('*') if x.is_file()}
 if actual!=r['source_sha256']:raise ValueError('source identity drift')
 if sha(run/'firmware/dma_day_soc')!=r['firmware']['elf_sha256'] or sha(run/'firmware/dma_day_soc.verilog')!=r['firmware']['image_sha256'] or sha(run/'simulator/dma_day_soc')!=r['simulator_sha256']:raise ValueError('Executable drift')
 for layer in r['vectors']:
  for name,digest in layer['sha256'].items():
   if sha(run/'vectors'/f"layer_{layer['layer']:02d}"/name)!=digest:raise ValueError('vector drift')
 out.mkdir(parents=True,exist_ok=False);cpu=out/'cpu';cpu.mkdir()
 for name in ('source','firmware','vectors'):shutil.copytree(run/name,cpu/name)
 (cpu/'simulator').mkdir();shutil.copy2(run/'simulator/dma_day_soc',cpu/'simulator/dma_day_soc')
 for path in run.iterdir():
  if path.is_file() and path.suffix in ('.json','.log'):shutil.copy2(path,cpu/path.name)
 shutil.copytree(ROOT/'experiments/s3-y32-4k',out/'experiment',ignore=shutil.ignore_patterns('__pycache__','.scala-build','.bsp'))
 docs=out/'docs';docs.mkdir()
 for name in ('s3-y32-4k-goal.md','s3-y32-4k-plan.md','s3-y32-4k-handoff.md','s3-y32-4k-results.md'):
  path=ROOT/'docs'/name
  if path.exists():shutil.copy2(path,docs/name)
 evidence=out/'evidence';evidence.mkdir();base=ROOT/'build/parallel4k-20261110'
 for name in ('goal-baseline.json','goal-execution.json','task0-bottleneck-r1.json','dma64-lint-failure-disposition.json','dma64-error-code-r2-amendment.json','cpu-core-pins-r1.json','cpu-replay-guard-amendment-r1.json','delivery-rebuild-proof-r1.json','completion-audit-r1.json','completion-audit-r2.json'):
  path=base/name
  if path.exists():shutil.copy2(path,evidence/name)
 for name in ('core-screen-r1','core-matrix-r1','fabric-r1','fabric-r2','dma-screen-r1','dma-screen-r2','dma-reset-recovery-r3','fallback-preprocess-r1','independent-audit-r1'):
  directory=base/name
  if not directory.exists():continue
  target=evidence/name;target.mkdir()
  for path in directory.rglob('*'):
   if path.is_file() and path.suffix in ('.log','.json','.md') and not any(x in ('obj','source','simulator') for x in path.relative_to(directory).parts):
    dst=target/path.relative_to(directory);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dst)
 for pattern in ('dma64-lint-r*.log','core-generation-*.log'):
  for path in base.glob(pattern):shutil.copy2(path,evidence/path.name)
 for directory in ('storage-inventory-r1','delivery-rebuild-r1'):
  source=base/directory
  if source.exists():
   target=evidence/directory;target.mkdir()
   for path in source.iterdir():
    if path.is_file() and path.suffix in ('.json','.log','.md'):shutil.copy2(path,target/path.name)
 server=ROOT/'build/server-4k-synth-20261110/final-r3'
 if server.exists():
  target=out/'prepared-synthesis';target.mkdir()
  for name in ('candidate.tar.gz','candidate.receipt.json','candidate.review.json'):
   path=server/name
   if path.is_file():shutil.copy2(path,target/name)
 for path in base.glob('cpu-*-selection-audit.json'):shutil.copy2(path,evidence/path.name)
 for repo,base_commit,name in [(ROOT/'third-party/e203_hbirdv2','45e61b6101ad6f0aaa7583098294ffb1550f1f2d','hardware.patch'),(ROOT,'655713b304597ca5b2810a0940ac3f1850072d63','parent.patch')]:
  (out/name).write_bytes(subprocess.check_output(['git','diff','--binary',base_commit,'HEAD'],cwd=repo))
 (out/'REPLAY.py').write_text(REPLAY);(out/'REPLAY.py').chmod(0o755)
 (out/'README.md').write_text('This is local functional/cycle evidence, not achieved150MHz, area or official qualification.\nRun python3 REPLAY.py to verify identities without simulation.\nExplicit --run --out NEW_DIR replays the exact sealed simulator; --rebuild also recompiles frozen RTL.\nLater experiments require renewed deadline authorization. Do not mistake fixture transfer time for payload.\n')
 manifest={x.relative_to(out).as_posix():sha(x) for x in sorted(out.rglob('*')) if x.is_file()};(out/'SHA256.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 archive=out.with_suffix('.tar.gz')
 if archive.exists():raise FileExistsError(archive)
 with tarfile.open(archive,'w:gz') as tar:tar.add(out,arcname=out.name)
 print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),sealed_files=len(manifest)),indent=2))
if __name__=='__main__':main()
