#!/usr/bin/env python3
"""Derive a separate 21-macro row-wide candidate, retaining scalar DMA retirement."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(t,a,b,n=1):
    if t.count(a)!=n:raise ValueError('wide derivation seam differs: '+a)
    return t.replace(a,b)
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('storage_prepare',HERE/'prepare_candidate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    manifest=m.prepare(a.out);out=a.out.resolve();core=out/'rtl/LinearTileDmaCore.sv';t=core.read_text()
    t=replace(t,'// Three real single-port macros hold two packets of 64 signed41 results.',
      '// Twenty-one real single-port macros hold two packets of eight328bit rows.')
    # Only the selected branch has these exact declarations/assignments.
    t=replace(t,'wire [2:0] storeRow=storeIndex[5:3],storeColumn=storeIndex[2:0];',
      'wire [2:0] storeRow=storeIndex[2:0],storeColumn=3\'d0;')
    lanes=','.join(f'macQ[storeRow][{c}][40:0]' for c in reversed(range(8)))
    t=replace(t,'wire enqueue=storeWrite&&({1\'b0,storeRow}+1\'b1==validRows)&&storeColumn==7;',
      'wire enqueue=storeWrite&&({1\'b0,storeRow}+1\'b1==validRows);')
    t=replace(t,"{3'b0,tail,storeIndex}:{3'b0,head,outRow,outColumn};", "{6'b0,tail,storeRow}:{6'b0,head,outRow};")
    t=replace(t,"wire [47:0] resultD=clearing?48'd0:{7'b0,storeValue};", "wire [335:0] resultD=clearing?336'd0:{8'b0,"+lanes+'};')
    t=replace(t,'wire [15:0] resultQ[0:2];','wire [15:0] resultQ[0:20];')
    slices=','.join('resultQ['+str(s)+']' for s in reversed(range(21)))
    t=replace(t,'wire [40:0] resultRaw={resultQ[2][8:0],resultQ[1],resultQ[0]};',
      'wire [335:0] resultRowQ={'+slices+'};\n wire [40:0] resultRaw=resultRowQ[41*outColumn+:41];')
    t=replace(t,'for(s=0;s<3;s=s+1)begin: resultSlices','for(s=0;s<21;s=s+1)begin: resultSlices')
    t=replace(t,'         readHeld<=0;\n         if(outColumn==7)begin',
      '         if(outColumn==7)readHeld<=0;\n         if(outColumn==7)begin')
    t=replace(t,'if(storeWrite)assert(macQ[storeRow][storeColumn]=={{7{storeValue[40]}},storeValue})\n     else $fatal(1,"raw MAC result exceeds signed41");',
      'if(storeWrite)for(integer lane=0;lane<8;lane=lane+1)\n     assert(macQ[storeRow][lane]=={{7{macQ[storeRow][lane][40]}},macQ[storeRow][lane][40:0]})\n       else $fatal(1,"raw MAC result exceeds signed41");')
    core.write_text(t)
    dma=out/'rtl/xu_matrix_dma_sysbus32.sv';dt=dma.read_text()
    dt=replace(dt,"+(core_clear_result?32'd3:0);", "+(core_clear_result?32'd21:0);")
    dma.write_text(dt)
    manifest['schema']='compliant32_storage_macro_wide_v1'
    manifest['storage'].update(result_macros=21,internal_macros=54,full_soc_macros=374,result_physical_bits=344064)
    manifest['clear'].update(result_writes=21504,total16bit_writes=55040,mmio_W_X_result_writes=54272)
    manifest['result_contract']='21 macros hold328 rawbits perrow+8zero; ACC row commits in1cycle,8rows/packet; macroQ held at same row through8scalar Y response retirements. No row register snapshot. Only column7 retirement advances row/read pipeline.'
    manifest['origins'][str(Path(__file__).relative_to(m.ROOT))]=sha(Path(__file__))
    manifest['files']={p.name:sha(p) for p in sorted((out/'rtl').glob('*.sv'))}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status=manifest['status'],out=str(out),result_macros=21)))
if __name__=='__main__':main()
