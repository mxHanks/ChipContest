#!/usr/bin/env python3
"""Exact full-domain interval proof plus generated-RTL prefix regression."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parent/'acc41-repo'
COMMANDS=[]

def run(command, label, cwd=REPO):
    result=subprocess.run(command,cwd=cwd,text=True,capture_output=True)
    (HERE/(label+'.log')).write_text('$ '+' '.join(map(str,command))+'\n'+result.stdout+result.stderr+'\nexit_code='+str(result.returncode)+'\n')
    COMMANDS.append({'name':label,'argv':list(map(str,command)),'returncode':result.returncode})
    (HERE/'commands.json').write_text(json.dumps(COMMANDS,indent=2)+'\n')
    if result.returncode:
        print(result.stdout+result.stderr)
        raise SystemExit(result.returncode)
    return result.stdout

# A bilinear function over an integer rectangle attains its extrema at its
# corners: fixing either operand makes the product linear in the other.
# Therefore these four corners prove product bounds for ALL signed16 operands.
imin,imax=-(1<<15),(1<<15)-1
bmin,bmax=-(1<<39),(1<<39)-1
corners=[{'x':x,'w':w,'product':x*w} for x in (imin,imax) for w in (imin,imax)]
pmin=min(c['product'] for c in corners)
pmax=max(c['product'] for c in corners)
lo41,hi41=-(1<<40),(1<<40)-1
prefixes=[]
for n in range(65):
    lower,upper=bmin+n*pmin,bmax+n*pmax
    assert lo41<=lower<=upper<=hi41
    prefixes.append({'products':n,'lower':lower,'upper':upper,'fits_signed41':True})
# A legal one-product dot is already a counterexample to signed40.
assert bmax+1 > bmax and bmax+1 <= hi41
proof={'method':'Exact integer interval induction; affine bias + independent product terms; extrema of bilinear product on signed16 rectangle at four corners. Covers all legal input values and every prefix 0..64, including pauses (no state update), init and reset.',
       'product_corners':corners,'product_min':pmin,'product_max':pmax,
       'bias_min':bmin,'bias_max':bmax,'signed41_min':lo41,'signed41_max':hi41,
       'prefixes':prefixes,
       'signed40_counterexample':{'bias':bmax,'x':1,'w':1,'after_products':1,'exact':bmax+1,'signed40_wrap':bmin},
       'induction':'Base n=0: ACC=bias. Step: each enabled update adds a product in [pmin,pmax], so ACC_n in [bmin+n*pmin,bmax+n*pmax]. Every interval fits signed41, so modular RTL addition is exact. Disabled edges preserve ACC; INIT restarts n=0 and has priority; reset restarts at zero. Outputs sign extend to signed48.',
       'storage':'8 internal accumulators only: 384 -> 328 bits, saves 56 register bits. Multiplier remains 16x16; add width changes. No PPA measured.'}
(HERE/'full-domain-proof.json').write_text(json.dumps(proof,indent=2)+'\n')

for name in ('MacPE','MacPE40Counterexample','LinearAutoGroupCore'):
    run(['scala-cli','run','.','--server=false','--jvm','system','-M','GenerateRTL','--',name], 'generate-'+name)
for suffix,source in [('48',REPO/'generated/MacPE/MacPE.sv'),('41',REPO/'generated/LinearAutoGroupCore41/MacPE.sv'),('40',REPO/'generated/MacPE40Counterexample/MacPE.sv')]:
    text=source.read_text()
    assert text.count('module MacPE(')==1
    (HERE/('MacPE'+suffix+'.sv')).write_text(text.replace('module MacPE(','module MacPE'+suffix+'(',1))

# Default elaboration must match the immutable baseline source manifest.
baseline=json.loads((HERE.parent/'baseline-source-freeze.json').read_text())['source_sha256']
assert hashlib.sha256((REPO/'generated/MacPE/MacPE.sv').read_bytes()).hexdigest()==baseline['rtl/perips/MacPE.sv']
for source in (REPO/'generated/LinearAutoGroupCore').glob('*.sv'):
    assert hashlib.sha256(source.read_bytes()).hexdigest()==baseline['rtl/perips/'+source.name],source.name

binary=HERE/'acc41.vvp'
run(['iverilog','-g2012','-s','tb_acc41','-o',str(binary),str(HERE/'tb_acc41.sv'),*[str(HERE/('MacPE'+x+'.sv')) for x in ('48','41','40')]],'rtl-prefix-compile',HERE)
result=run(['vvp',str(binary)],'rtl-prefix-simulation',HERE)
assert 'ACC41_PREFIX_PASS' in result
frozen=json.loads((HERE/'production-source-frozen-v2.json').read_text())
for name,digest in frozen['files'].items():
    assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==digest,name
(HERE/'result.json').write_text(json.dumps({'status':'PASS','proof_prefixes':65,'product_domain':'all signed16 x signed16','bias_domain':'all signed40','rtl_prefix_result':result.strip(),'production_source_drift':[],'note':'Analytic domain proof plus cycle-by-cycle real generated RTL regression, no synthesis or PPA.'},indent=2)+'\n')
print(result.strip())
