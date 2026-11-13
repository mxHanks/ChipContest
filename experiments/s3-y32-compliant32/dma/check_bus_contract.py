#!/usr/bin/env python3
"""Require the actual DMA source memory ports and advertised capability be32-bit."""
import argparse,hashlib,json,pathlib,re
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('source',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args();raw=a.source.read_bytes();s=raw.decode();header=s.split(');',1)[0]
observed={}
for name in ['mem_cmd_wdata','mem_rsp_rdata','mem_cmd_wmask']:
 m=re.search(r'\[(\d+):0\]\s+'+name+r'\b',header)
 observed[name]=int(m[1])+1 if m else None
m=re.search(r"7'h4c:cfg_rsp_rdata<=32'h([0-9a-fA-F]+)",s);observed['capability']=int(m[1],16)if m else None
expected=dict(mem_cmd_wdata=32,mem_rsp_rdata=32,mem_cmd_wmask=4,capability=0x00082001)
wrong={k:dict(required=v,observed=observed[k])for k,v in expected.items()if observed[k]!=v}
r=dict(schema='compliant32-memory-width-source-contract-v1',source=str(a.source.resolve()),source_sha256=hashlib.sha256(raw).hexdigest(),observed=observed,expected=expected,violations=wrong,status='FAIL'if wrong else'PASS',scope='Actual source port/capability contract; no dynamic numeric or SystemBus path proof')
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n');print(r['status'],json.dumps(wrong));raise SystemExit(bool(wrong))
