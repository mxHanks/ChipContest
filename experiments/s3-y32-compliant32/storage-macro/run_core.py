#!/usr/bin/env python3
"""Reuse existing raw48/endpoint/abort/dirty-clear module campaign with scalar POP."""
import argparse,hashlib,json,shutil,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(t,a,b):
    if t.count(a)!=1:raise ValueError('test seam differs: '+a)
    return t.replace(a,b)
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--tasks',type=int,default=1);p.add_argument('--jobs',type=int,choices=[1,2],default=1)
    p.add_argument('--smoke-only',action='store_true');a=p.parse_args();assert 1<=a.tasks<=12
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=out/'source';src.mkdir()
    manifest=json.loads((a.candidate.resolve()/'manifest.json').read_text());macro_count=manifest['storage']['internal_macros']
    for f in (a.candidate.resolve()/'rtl').glob('*.sv'):shutil.copy2(f,src/f.name)
    original=HERE.parent/'x-macro/tile_macro_driver.cpp';t=original.read_text()
    t=replace(t,'      unsigned group=d.io_outGroup,sel=d.io_outRow;\n      require(group==bundles/rows && sel==bundles%rows,"bundle order/group/tail mask");',
      '      unsigned group=d.io_outGroup,sel=d.io_outRow,lane=d.io_outColumn;\n      require(group==bundles/(rows*8) && sel==(bundles/8)%rows && lane==bundles%8,"scalar order/group/tail mask");')
    t=replace(t,'d.io_outRow==sel&&output()==held,','d.io_outRow==sel&&d.io_outColumn==lane&&output()==held,')
    t=replace(t,'      for(int lane=0;lane<8;lane++) {','      {')
    t=t.replace('held[lane]','held[0]')
    t=replace(t,'require(bundles==32*(unsigned)rows,"row bundle count");','require(bundles==256*(unsigned)rows,"scalar result count");')
    t=replace(t,'if(phase==2){d.io_outPop=1;tick();d.io_outPop=0;require(d.io_outRow==1,"reset second row bundle phase");}',
      'if(phase==2){for(unsigned q=0;q<8;q++){while(!d.io_outValid)tick();d.io_outPop=1;tick();d.io_outPop=0;}require(d.io_outRow==1&&d.io_outColumn==0,"reset second row scalar phase");}')
    t=replace(t,'    require(c.xclear-xc==16384,"all1024 physical addresses in16 X macros cleared");',
      '    require(c.xclear-xc==16384,"all1024 physical addresses in16 X macros cleared");')
    cpp=src/'storage_core_driver.cpp';cpp.write_text(t)
    (src/'source-driver-origin.json').write_text(json.dumps(dict(path=str(original),sha256=sha(original)),indent=2)+'\n')
    rtl=sorted(src.glob('*.sv'));vectors=a.vectors.resolve();ids={str(f):sha(f) for f in src.iterdir() if f.is_file()}
    for layer in range(a.tasks):
      for name in ['x.mem','w.mem','bias.mem','y.mem','y32.mem']:
        f=vectors/f'layer_{layer:02d}'/name;ids[str(f)]=sha(f)
    rec=dict(schema='storage_macro_raw_core_v1',status='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),inputs=ids,commands=[],cases=[])
    def save():(out/'receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
    def run(cmd,name):
      save();start=time.monotonic()
      with (out/(name+'.log')).open('w') as log:
        done=subprocess.run([str(x) for x in cmd],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
      rec['commands'].append(dict(name=name,command=[str(x) for x in cmd],returncode=done.returncode,seconds=time.monotonic()-start));save()
      if done.returncode:raise RuntimeError(name+' failed; preserved log')
    try:
      run(['verilator','--cc','--exe','--build','--assert','-Wno-fatal','-j',a.jobs,
        '-DXU_MATRIX_DMA_SYSBUS32','-DXU_MATRIX_X_SRAM','-DXU_MATRIX_STORAGE_SRAM',
        '--top-module','LinearTileDmaCore','--Mdir',out/'obj','-CFLAGS','-std=c++17',*rtl,cpp],'compile')
      exe=out/'obj/VLinearTileDmaCore';rec['simulator_sha256']=sha(exe)
      for layer in range(a.tasks):
        for rows,stall in ([(8,0)] if a.smoke_only else [(8,0),(8,31),(8,255),(1,0),(3,0)]):
          name=f'layer{layer:02d}-rows{rows}-stall{stall}';run([exe,vectors/f'layer_{layer:02d}',rows,stall,out/(name+'.json')],name)
          r=json.loads((out/(name+'.json')).read_text())
          if r['outputs_exact_raw48']!=25344 or r['outputs_exact_cpp_rne_y32']!=25344:raise ValueError('incomplete raw/RNE output')
          if (out/(name+'.log')).read_text().count('S3_GENERIC_NON_PPA_MACRO_INSTANCE ')!=macro_count:raise ValueError('macro count mismatch')
          rec['cases'].append(dict(name=name,result=r))
      if any(sha(Path(s))!=h for s,h in ids.items()):raise ValueError('source/vector drift')
      rec['status']='PASS';print('STORAGE_MACRO_RAW_CORE_PASS cases='+str(len(rec['cases'])))
    except Exception as e:rec.update(status='FAIL',error=str(e));raise
    finally:
      rec['finished_at']=datetime.now(timezone.utc).isoformat();rec['outputs']={f.name:dict(sha256=sha(f),bytes=f.stat().st_size) for f in out.iterdir() if f.is_file() and f.name!='receipt.json'};save()
if __name__=='__main__':main()
