#!/usr/bin/env python3
"""Preprocess and check the original32 SystemBus path. Never runs simulation/EDA."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
PIN='ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,m,failures):
 if not v:failures.append(m)
def compact(s):return re.sub(r'\s+','',s)
def instance(s,name):
 m=re.search(r'\b'+re.escape(name)+r'\s*\(',s)
 if not m:return ''
 i=m.end();depth=1
 while i<len(s) and depth:
  depth+=(s[i]=='(')-(s[i]==')');i+=1
 return s[m.end():i-1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--config',choices=['sysbus32','old64'],default='sysbus32');p.add_argument('--out',type=Path,required=True);a=p.parse_args();root=a.root.resolve();child=root/'third-party/e203_hbirdv2';rtl=child/'rtl/e203';out=a.out
 if out.exists():raise ValueError('refuse gate output overwrite')
 out.mkdir(parents=True);flags=['XU_MATRIX_DMA','XU_MATRIX_DMA_SYSBUS32'] if a.config=='sysbus32' else ['XU_MATRIX_DMA','XU_MATRIX_DMA64'];failures=[];texts={};commands=[]
 for n in ['subsys/e203_subsys_main.v','subsys/e203_subsys_perips.v','subsys/e203_subsys_top.v','soc/e203_soc_top.v']:
  cmd=['verilator','-E','-P','-I'+str(rtl/'core'),'-I'+str(rtl/'perips')]+['-D'+f for f in flags]+[str(rtl/n)];r=subprocess.run(cmd,capture_output=True,text=True);commands.append({'argv':cmd,'returncode':r.returncode});(out/(Path(n).stem+'.pp.v')).write_text(r.stdout);(out/(Path(n).stem+'.stderr')).write_text(r.stderr);require(r.returncode==0,'PREPROCESS_FAILED:'+n,failures);texts[Path(n).stem]=r.stdout
 maintext=texts['e203_subsys_main'];perips=texts['e203_subsys_perips'];top=texts['e203_subsys_top'];soc=texts['e203_soc_top']
 for label,text,prefix in [('main',maintext,'sysmem'),('top',top,'sysmem'),('soc',soc,'ext_sysmem')]:
  for suffix,w in [('cmd_wdata',32),('cmd_wmask',4),('rsp_rdata',32)]:
   port=prefix+'_icb_'+suffix if prefix=='sysmem' else prefix+'_'+suffix
   matches=re.findall(r'\b(?:input|output)\s+(?:wire\s+)?\[([^]]+)\]\s*'+port+r'\b',text);ok=len(matches)==1 and compact(matches[0]) in ({'31:0','32-1:0'} if w==32 else {'3:0','32/8-1:0'})
   require(ok,'PLATFORM_PORT_NOT_'+str(w)+':'+label+':'+port,failures)
  require(not re.search(r'\b'+prefix+(r'_icb' if prefix=='sysmem' else '')+r'_cmd_is32\b',text),'WIDE_MODE_SIDECHANNEL:'+label,failures)
 require('xu_matrix_dma_sysbus32 u_xu_matrix_dma' in compact(perips).replace('xu_matrix_dma_sysbus32u_xu_matrix_dma','xu_matrix_dma_sysbus32 u_xu_matrix_dma'),'WRONG_DMA_MODULE',failures)
 require(not re.search(r'\b(?:xu_dma64_shared_arb|xu_dma_shared_arb)\s+u_xu_dma_shared_arb\b',maintext),'OLD_DOWNSTREAM_SYSMEM_ARBITER_ACTIVE',failures)
 ingress=compact(instance(maintext,'u_xu_systembus_ingress'));mem=compact(instance(maintext,'u_e203_subsys_mems'));cpu=compact(instance(maintext,'u_e203_cpu_top'))
 require(bool(ingress),'MISSING_SYSTEMBUS_INGRESS',failures)
 for suffix in ['cmd_valid','cmd_ready','cmd_addr','cmd_read','cmd_wdata','cmd_wmask','rsp_valid','rsp_ready','rsp_err','rsp_rdata']:
  require('.cpu_'+suffix+'(mem_icb_'+suffix+')' in ingress,'CPU_NOT_AT_UPSTREAM_INGRESS:'+suffix,failures)
  require('.dma_'+suffix+'(dma_'+suffix+')' in ingress,'DMA_NOT_AT_UPSTREAM_INGRESS:'+suffix,failures)
  require('.bus_'+suffix+'(bus_mem_icb_'+suffix+')' in ingress,'INGRESS_NOT_TO_ORIGINAL_BUS:'+suffix,failures)
  require('.mem_icb_'+suffix+'(bus_mem_icb_'+suffix+')' in mem,'MEM_FAB_INPUT_BYPASS:'+suffix,failures)
  require('.sysmem_icb_'+suffix+'(sysmem_icb_'+suffix+')' in mem,'SYSMEM_NOT_ORIGINAL_OUTPUT:'+suffix,failures)
  require('.mem_icb_'+suffix+'(mem_icb_'+suffix+')' in cpu,'CPU_ORIGINAL_PORT_CHANGED:'+suffix,failures)
 # These immutable platform components are reused, not widened/retimed.
 pinned={}
 for n in ['rtl/e203/subsys/e203_subsys_mems.v']+subprocess.check_output(['git','-C',str(child),'ls-tree','-r','--name-only',PIN,'rtl/e203/core'],text=True).splitlines():
  raw=subprocess.check_output(['git','-C',str(child),'show',PIN+':'+n]);require((child/n).read_bytes()==raw,'ORIGINAL_PLATFORM_FILE_CHANGED:'+n,failures);pinned[n]=hashlib.sha256(raw).hexdigest()
 wrapper=root/'experiments/s3-y32-compliant32/structure/xu_soc_sysbus32_ppa_top.sv'
 require(wrapper.is_file(),'MISSING_PRODUCTION32_WRAPPER',failures)
 if wrapper.is_file():
  s=wrapper.read_text();require('xu_shared_icb_sram u_shared' in s,'WRONG_SHARED_ENDPOINT',failures);require('sram64' not in s and 'public_ingress' not in s and 'host_' not in s,'WRAPPER_HAS_WIDE_OR_SIDE_INGRESS',failures)
 adapter=root/'tools/ppa/xu_sirv_sram_adapter.sv';endpoint=root/'tools/ppa/xu_shared_icb_sram.sv';require(endpoint.is_file() and 'DP(131072),.DW(32),.MW(4),.AW(17)' in compact(endpoint.read_text()),'NOT_ORIGINAL32_SHARED_GEOMETRY',failures)
 report={'schema':'s3-compliant32-preprocessed-systembus-structure-v1','status':'STRUCTURE_PASS_NOT_FUNCTIONAL_OR_OFFICIAL_SIGNOFF' if not failures else 'STRUCTURE_RED','configuration':a.config,'defines':flags,'failures':failures,'commands':commands,'source_sha256':{str(rtl/n):sha(rtl/n) for n in ['subsys/e203_subsys_main.v','subsys/e203_subsys_perips.v','subsys/e203_subsys_top.v','soc/e203_soc_top.v']},'pinned_cpu_and_original_mems_sha256':pinned,'endpoint_sha256':sha(endpoint),'adapter_sha256':sha(adapter),'scope':'Active preprocessed32bit ports and exact named nets from CPU/DMA upstream ingress through unchanged original mem_fab/sysmem. Historical fallback source may remain inactive. No simulation, mapped equivalence, STA or official qualification.'};(out/'result.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(report['status'],len(failures),'failures');return bool(failures)
if __name__=='__main__':sys.exit(main())
