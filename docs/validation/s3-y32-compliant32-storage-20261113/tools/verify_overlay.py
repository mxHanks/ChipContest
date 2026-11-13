#!/usr/bin/env python3
"""Check selected payload removal and exact preprocessed fallback identities."""
import argparse,hashlib,itertools,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE=ROOT/'build/compliant32-20261113/x-macro/candidate-r2/rtl'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pp(p,flags):
    out=subprocess.check_output(['verilator','-E','-P',*['-D'+x for x in flags],str(p)],text=True)
    out=re.sub(r'/\*.*?\*/|//[^\n]*','',out,flags=re.S)
    return re.findall(r'\S+',out)
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    candidate=a.candidate.resolve();m=json.loads((candidate/'manifest.json').read_text());rtl=candidate/'rtl'
    if any(sha(rtl/name)!=h for name,h in m['files'].items()):raise ValueError('candidate file drift')
    names=['XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM','XU_MATRIX_STORAGE_SRAM'];cases=[]
    for bits in itertools.product([False,True],repeat=3):
      flags=[x for x,b in zip(names,bits) if b]
      if all(bits):continue
      for name,old in [('LinearTileDmaCore.sv',BASE/'LinearTileDmaCore.sv'),('xu_matrix_dma_sysbus32.sv',ROOT/'third-party/e203_hbirdv2/rtl/e203/perips/xu_matrix_dma_sysbus32.sv')]:
        same=pp(rtl/name,flags)==pp(old,flags)
        if not same:raise ValueError('fallback token drift: '+str(flags)+' '+name)
      cases.append(dict(defines=flags,core_and_dma_tokens_equal=True))
    selected={name:' '.join(pp(rtl/name,names)) for name in ['LinearTileDmaCore.sv','xu_matrix_dma_sysbus32.sv']}
    for name,text in selected.items():
      for bad in ['resultReg_','results_0_','results_1_','slotData_','y_payload']:
        if bad in text:raise ValueError('selected reusable/register result payload retained: '+bad)
    orig=(BASE/'LinearTileDmaCore.sv').read_text();new=(rtl/'LinearTileDmaCore.sv').read_text()
    def pe(t):
      start=t.index('module MacPE_Acc41(');return t[start:t.index('endmodule',start)+len('endmodule')]
    if pe(orig)!=pe(new):raise ValueError('original arithmetic byte identity differs')
    res=dict(status='PASS',scope='Structural/fallback evidence, no functional/PPA claim',fallback_cases=cases,
      selected_arithmetic_module_byte_identical=True,selected_payload_caches_removed=True,
      candidate_manifest_sha256=sha(candidate/'manifest.json'),inputs={str(rtl/n):sha(rtl/n) for n in m['files']})
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(res,indent=2)+'\n');print('STORAGE_MACRO_OVERLAY_PASS fallbacks=7')
if __name__=='__main__':main()
