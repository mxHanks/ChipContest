from pathlib import Path
import hashlib,json,subprocess
root=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest')
b=root/'build/pe16-20261108'; repo=b/'pe16-repo'; out=b/'wrapper-smoke'
out.mkdir(exist_ok=False)
rtl=repo/'third-party/e203_hbirdv2/rtl/e203'
source=(repo/'tests/e203/tb_xu_direct_wrapper.sv').read_text()
assert source.count('next_group=next_group+1;')==1
source=source.replace('next_group=next_group+1;','next_group=next_group+2;')
# Pair producer waits for two free slots; use the same generous bounded budget
# as firmware instead of the old eight-PE fixture's deliberately tiny budget.
# Preserve the original direct poll_limit=2: each instruction starts only after wait_valid.
source=source.replace('if(polls>40)', 'if(polls>64)')
# Count the actual pair launches/completions of the completed real row.
source=source.replace('    if(snapshots!=32 || direct_pops!=32', '    if(starts!=16 || dones!=16) $fatal(1,"PE16 physical pair count wrong");\n    if(snapshots!=32 || direct_pops!=32')
(out/'tb.sv').write_text(source)
files=[out/'tb.sv',rtl/'subsys/xu_nice_drain8.v',*sorted((rtl/'perips').glob('*.sv')),rtl/'perips/accel_icb_slave.v']
cmd=['iverilog','-g2012','-I'+str(rtl/'core'),'-s','tb_xu_direct_wrapper','-o',str(out/'wrapper.vvp'),*[str(p) for p in files]]
steps=[]
for name,argv in [('compile',cmd),('numeric',['vvp',str(out/'wrapper.vvp')])]+[(f'reset-{n}',['vvp',str(out/'wrapper.vvp'),f'+RESET_PHASE={n}']) for n in (1,2,3)]:
 with (out/(name+'.log')).open('w') as log:
  result=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,timeout=90)
 steps.append(dict(name=name,command=argv,native_exit=result.returncode))
 (out/'result.json').write_text(json.dumps({'steps':steps},indent=2)+'\n')
 if result.returncode: raise SystemExit(result.returncode)
print('WRAPPER_SMOKE_PASS',flush=True)
