#!/usr/bin/env python3
"""Real generated RTL module screen; no synthesis and no CPU cycle estimate."""
import argparse, hashlib, json, pathlib, subprocess, time
from generate_observer import generate

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path,required=True)
    p.add_argument('--vectors',type=pathlib.Path,required=True)
    p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
    here=pathlib.Path(__file__).resolve().parent;repo=a.repo.resolve();vectors=a.vectors.resolve()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    generated=repo/'generated/LinearRowPairPrototype';rtl=sorted(generated.glob('*.sv'))
    assert len(rtl)==11,rtl
    observer=here/'rowpair_physical_observer.sv';generate(observer)
    command=['verilator','--cc','--exe','--build','-j','2','--assert','-Wno-fatal',
             '--top-module','LinearRowPairPrototype','--Mdir',str(out/'obj'),
             '-CFLAGS','-std=c++17',*[str(x) for x in rtl],str(observer),str(here/'rowpair_driver.cpp')]
    sources=rtl+sorted((repo/'src/main/scala').rglob('*.scala'))+[
                 here/'rowpair_driver.cpp',observer,here/'generate_observer.py',pathlib.Path(__file__).resolve()]
    inputs=[vectors/x for x in ('x.mem','w.mem','bias.mem','y.mem','y32.mem')]
    source_hashes={str(x):digest(x) for x in sources};input_hashes={str(x):digest(x) for x in inputs}
    records=[]
    def run(cmd,name):
        begin=time.monotonic();r=subprocess.run(cmd,cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/(name+'.log')).write_text(r.stdout);records.append(dict(name=name,command=cmd,
            cwd=str(repo),returncode=r.returncode,elapsed_seconds=time.monotonic()-begin))
        if r.returncode:raise RuntimeError(name+' failed; see log')
    run(command,'compile')
    for stall in (0,31,60,80,255):
        for rows in (1,2):
            name=f'rows{rows}-stall{stall}'
            run([str(out/'obj/VLinearRowPairPrototype'),str(vectors),str(rows),str(stall),str(out/(name+'.json'))],name)
    drift=[str(x) for x in sources+inputs if digest(x)!=(source_hashes|input_hashes)[str(x)]]
    assert not drift,drift
    receipt=dict(schema='rowpair_module_campaign_v1',sources=source_hashes,
                 inputs=input_hashes,commands=records,source_drift=drift,
                 scope='Real generated Chisel RTL with Verilator --assert. C++ sink and RNE. No CPU, synthesis, PPA or SoC timing claims.')
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('ROWPAIR_CAMPAIGN_PASS cases=10 outputs_per_case=25344')
if __name__=='__main__':main()
