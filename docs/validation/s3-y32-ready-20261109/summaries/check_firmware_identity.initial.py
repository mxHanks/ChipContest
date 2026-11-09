#!/usr/bin/env python3
"""Recompile frozen 0x23 firmware and prove optional ready disabled load identity."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'postflow-20261108/selected-full12'
REPO=ROOT/'prototype-repo'
OUT=ROOT/'checks/firmware-identity';OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=json.loads((BASE/'result.json').read_text()); cmd=next(x['command'] for x in r['steps'] if x['name']=='firmware-build')
records=[]
for variant in ['frozen','default-off','explicit-off']:
 argv=list(cmd); elf=OUT/variant;argv[-1]=str(elf)
 if variant!='frozen':
  argv[argv.index(str(BASE/'source/tests/e203/firmware/accel.c'))]=str(REPO/'tests/e203/firmware/accel.c')
 if variant=='explicit-off':argv.insert(4,'-DXU_NICE_READY=0')
 commands=[argv,['/usr/bin/riscv64-unknown-elf-objcopy','-O','binary',str(elf),str(elf)+'.bin'],
           ['/usr/bin/riscv64-unknown-elf-objcopy','-O','verilog',str(elf),str(elf)+'.verilog']]
 for n,command in enumerate(commands):
  p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,cwd=OUT)
  (OUT/(variant+'-'+str(n)+'.log')).write_text(json.dumps(command)+'\n'+p.stdout)
  if p.returncode:raise RuntimeError(variant+': '+p.stdout)
 records.append(dict(variant=variant,commands=commands,elf_sha256=sha(elf),load_binary_sha256=sha(str(elf)+'.bin'),image_sha256=sha(str(elf)+'.verilog')))
assert len({x['load_binary_sha256'] for x in records})==1
assert len({x['image_sha256'] for x in records})==1
assert sha(BASE/'accel_soc')==records[0]['elf_sha256']
negative=[]
for flags in [[],['-DXU_NICE_DRAINN=1','-DXU_NICE_DIRECT=1'],['-DXU_NICE_DRAIN8=1','-DXU_NICE_DIRECT=1']]:
 command=['/usr/bin/riscv64-unknown-elf-gcc','-march=rv32imac_zicsr2p0_zifencei2p0','-mabi=ilp32','-fsyntax-only','-DXU_NICE_READY=1',*flags,str(REPO/'tests/e203/firmware/accel.c')]
 p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 (OUT/('negative-'+str(len(negative))+'.log')).write_text(json.dumps(command)+'\n'+p.stdout)
 assert p.returncode and 'NICE ready requires direct NICE drainN transport' in p.stdout
 negative.append(dict(command=command,native_exit=p.returncode,diagnostic='NICE ready requires direct NICE drainN transport'))
(OUT/'result.json').write_text(json.dumps(dict(status='PASS',variants=records,macro_dependency_rejections=negative,baseline_elf_sha256=sha(BASE/'accel_soc'),baseline_accel_sha256=sha(BASE/'source/tests/e203/firmware/accel.c'),candidate_accel_sha256=sha(REPO/'tests/e203/firmware/accel.c')),indent=2)+'\n')
print('PASS: identical frozen/default-off/explicit-off load binary + image; 3 invalid dependency builds rejected')
