#!/usr/bin/env python3
import argparse,hashlib,json,subprocess
from pathlib import Path
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=Path.cwd();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
rtl=root/'third-party/e203_hbirdv2/rtl/e203';files=[root/'experiments/s3-y32-compliant32/structure/tb_ingress32.sv',rtl/'subsys/xu_systembus_ingress32.v',rtl/'general/sirv_gnrl_icbs.v',rtl/'general/sirv_gnrl_bufs.v',rtl/'general/sirv_gnrl_dffs.v'];before={str(p):sha(p) for p in files};runs=[]
for loader in [0,1]:
 binary=out/f'loader{loader}.vvp';cmd=['iverilog','-g2012','-DDISABLE_SV_ASSERTION','-s','tb_ingress32','-Ptb_ingress32.HAS_LOAD='+str(loader),'-o',str(binary),*map(str,files)]
 with (out/f'compile-loader{loader}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=60)
 assert r.returncode==0,'compile failure'
 run=['vvp',str(binary)];r=subprocess.run(run,capture_output=True,text=True,timeout=60);(out/f'loader{loader}.log').write_text(r.stdout+r.stderr);runs.append({'loader':loader,'compile_command':cmd,'run_command':run,'returncode':r.returncode,'pass_marker':'INGRESS32_PASS' in r.stdout});assert r.returncode==0 and runs[-1]['pass_marker'],'ingress behavior failure'
assert before=={str(p):sha(p) for p in files},'source drift'
receipt={'status':'PASS_DIRECTED_UPSTREAM_ICB_ARBITRATION','source_sha256':before,'runs':runs,'scope':'Actual existing platform sirv_gnrl_icb_arbt with new32bit upstream grant wrapper: stalled command stability, CPU/DMA/test-source owner routes, response/error backpressure, oneoutstanding and joint reset recovery. No fullCPU/task/officialSDK/EDA claim.'};(out/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(receipt['status'])
