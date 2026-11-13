#!/usr/bin/env python3
"""Local full-top32bus XML geometry check only; no synthesis/STA/simulation."""
import argparse,hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=a.root.resolve();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True)
 rtl=root/'third-party/e203_hbirdv2/rtl/e203';old=root/'build/area-opt-20261111/baseline-synth-r5/candidate/rtl.f';names=old.read_text().splitlines();paths=[]
 for n in names:
  if n.startswith('source/rtl/'):
   rel=n.removeprefix('source/rtl/');path={'general/sirv_sim_ram.v':root/'tools/ppa/xu_sirv_sram_adapter.sv','perips/mem_1024x16.sv':root/'tools/ppa/xu_weight_sram_adapter.sv'}.get(rel,rtl/rel);paths.append(path)
  elif n=='source/ppa/xu_soc_dma64_ppa_top.sv':paths.append(root/'experiments/s3-y32-compliant32/structure/xu_soc_sysbus32_ppa_top.sv')
  else:raise ValueError('unreviewed original input path:'+n)
 paths.extend([rtl/'subsys/xu_systembus_ingress32.v',rtl/'perips/xu_matrix_dma_sysbus32.sv',root/'tools/ppa/xu_shared_icb_sram.sv',root/'tools/ppa/generic_ramsp_non_ppa.sv'])
 assert len(paths)==len(set(paths));before={str(p):sha(p) for p in paths};(out/'rtl.f').write_text('\n'.join(map(str,paths))+'\n')
 cmd=['verilator','--xml-only','--timing','-Wno-fatal','--top-module','xu_soc_sysbus32_ppa_top','--Mdir',str(out/'obj'),'--xml-output',str(out/'elaborated.xml'),'-DSYNTHESIS','-DDISABLE_SV_ASSERTION=1','-DXU_MATRIX_DMA','-DXU_MATRIX_DMA_SYSBUS32','-I'+str(rtl/'core'),'-I'+str(rtl/'perips'),'-I'+str(rtl/'perips/apb_i2c'),'-f',str(out/'rtl.f')]
 with (out/'elaboration.log').open('w') as log:r=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 report={'schema':'s3-compliant32-fulltop-elaboration-v1','status':'FAIL','command':cmd,'returncode':r.returncode,'source_before_sha256':before,'source_drift':[n for n,h in before.items() if sha(Path(n))!=h],'simulation_run':False,'synthesis_run':False,'sta_run':False,'scope':'Local fulltop elaboration/geometry only, generic functional macro for original32 endpoint adapter. No performance or official framework qualification.'}
 if r.returncode==0:
  doc=ET.parse(out/'elaborated.xml');cells=doc.findall('./cells//cell');refs={};macros=[]
  for c in cells:
   n=c.get('submodname','');refs[n]=refs.get(n,0)+1
   if n.startswith('RAMSP1024X16'):macros.append(c)
  def count(prefix):return sum(v for k,v in refs.items() if k.startswith(prefix))
  groups={'itcm':0,'dtcm':0,'shared':0,'weights':0,'bias':0};unique=True
  for c in macros:
   h=c.get('hier','');matches=[k for k,pat in {'itcm':'.u_e203_itcm_ram.','dtcm':'.u_e203_dtcm_ram.','shared':'.u_shared.storage.','weights':'.u_core.weights.','bias':'.u_core.bias.memory.'}.items() if pat in h];unique&=len(matches)==1
   for k in matches:groups[k]+=1
  macro_good=len(macros)==337 and groups=={'itcm':32,'dtcm':32,'shared':256,'weights':16,'bias':1} and unique
  pe=sum(v for k,v in refs.items() if k.startswith('MacPE') and not k.startswith('MacPEArray'));engine=count('DotProductEngine');ingress=count('xu_systembus_ingress32');endpoint=count('xu_shared_icb_sram');wide=sum(v for k,v in refs.items() if k.startswith(('xu_dma64_shared_arb','xu_dma_shared_arb','xu_shared_icb_sram64','xu_matrix_dma64')))
  report.update(macros=len(macros),macro_groups=groups,macro_scopes_unique=unique,mac_pe=pe,engines=engine,original_systembus_ingress=ingress,original32_endpoint=endpoint,forbidden_wide_or_downstream_instances=wide,cell_reference_counts=refs,xml_sha256=sha(out/'elaborated.xml'))
  good=macro_good and (pe,engine,ingress,endpoint,wide)==(64,8,1,1,0) and not report['source_drift'];report['status']='PASS_LOCAL32_FULLTOP_GEOMETRY_NOT_SIGNOFF' if good else 'FAIL'
 report['log_sha256']=sha(out/'elaboration.log');(out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(report['status']);return report['status']=='FAIL'
if __name__=='__main__':sys.exit(main())
