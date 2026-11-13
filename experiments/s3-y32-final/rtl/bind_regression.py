#!/usr/bin/env python3
"""Bind a sealed DMA regression to the final selected preprocessing projection."""
import argparse,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('freeze',HERE/'freeze.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 run=a.run.resolve();rec=json.loads((run/'receipt.json').read_text());assert rec['status']=='PASS','not a successful sealed regression'
 bindings=[]
 for name in f.FILES:
  actual=f.PERIPS/name;snapshot=run/'source'/name
  tokens_actual=f.tokens(actual,f.DEFINES);tokens_run=f.tokens(snapshot,f.DEFINES)
  assert tokens_actual==tokens_run,('selected functional source differs',name)
  bindings.append(dict(file=name,final_bytes_sha256=f.sha(actual.read_bytes()),run_bytes_sha256=f.sha(snapshot.read_bytes()),byte_identical=actual.read_bytes()==snapshot.read_bytes(),selected_tokens_identical=True,selected_token_sha256=f.sha(json.dumps(tokens_actual).encode())))
 # Source stimulus, generic model and fabric were all sealed by the run receipt.
 for name in ['xu_systembus_ingress32.v','sirv_icb1to8_bus.v','sirv_gnrl_icbs.v','sirv_gnrl_bufs.v','sirv_gnrl_dffs.v']:
  choices=list((f.CHILD/'rtl/e203').rglob(name));assert len(choices)==1,name
  assert choices[0].read_bytes()==(run/'source'/name).read_bytes(),('platform source changed',name)
 result=dict(schema='s3_y32_final_regression_projection_binding_v1',status='PASS',receipt_sha256=f.sha((run/'receipt.json').read_bytes()),run=str(run),required_defines=f.DEFINES,bindings=bindings,platform_bytes_identical=True,
  note='Final DMA adds the conjunction guard and byte-identical5470 fallback after the unit snapshot. Selected production preprocessing tokens are exactly identical. Final GPIO CPU regression independently uses the final wrapper source bytes.')
 a.out.write_text(json.dumps(result,indent=2)+'\n');print('FINAL_DMA_SELECTED_PROJECTION_BIND_PASS')
if __name__=='__main__':main()
