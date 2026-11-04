#!/usr/bin/env python3
"""xu frozen S2c mapped elaboration metadata probe, never activity qualification."""
import argparse, hashlib, json, re, subprocess, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TB_SHA='d39016ea50fafe7df8c97dd209702fbc3c4e7eb0e2bb8fded570e427fde6d850'
NET_SHA='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
INV_SHA='721ce0773570c54a8757a32165a47f399cd5c1ee9e3a57eab612dbeeeea15d8d'
VENDOR_SHA='81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51'
CONFIG='5b5cf619e8b0e5c2fc050abe8b589d5f7544a98eed174f4fc979bffe60fa6018'
def need(ok,msg):
 if not ok: raise ValueError(msg)
def identity(path):
 p=Path(path).resolve();need(p.is_file(),'missing source: '+str(p));b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def dump(path,x):path.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tb',required=True,type=Path);p.add_argument('--activity',required=True,type=Path);p.add_argument('--inventory',required=True,type=Path);p.add_argument('--mapped',type=Path);p.add_argument('--vendor',type=Path);p.add_argument('--standard-model',action='append',type=Path,default=[]);p.add_argument('--out',required=True,type=Path);p.add_argument('--run-vcs',type=Path);p.add_argument('--vpi-include',type=Path);p.add_argument('--cc',default='gcc');a=p.parse_args()
 tbidentity=identity(a.tb);need(tbidentity['sha256']==TB_SHA,'original generated TB differs');text=a.tb.read_text();activity=json.loads(a.activity.read_text());need(activity['configuration_sha256']==CONFIG,'original capture config differs');need(hashlib.sha256(json.dumps(activity['configuration'],sort_keys=True,separators=(',',':')).encode()).hexdigest()==CONFIG,'capture config body differs');inventory=identity(a.inventory);need(inventory['sha256']==INV_SHA,'actual inventory differs');inv=json.loads(a.inventory.read_text());need(inv['netlist']['sha256']==NET_SHA and inv['macro_count']==336 and inv['pin_bit_count']==22512,'actual inventory netlist/count differs')
 a.out.mkdir(parents=True,exist_ok=False)
 refs={key:sorted(set(re.findall('`'+key+r'\.([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)',text)))for key in ['ACCEL','EXU','ITCM','XU_HCLK']}
 memrefs=re.findall(r'(?m)^\s*(`ITCM\.[^\s=]+|dut\.u_shared\.[^\s=]+)\.mem\[row\]=',text)
 dut=re.findall(r'  xu_soc_ppa_top dut \(.*?\n  \);',text,re.S);need(len(dut)==1,'original pad instance missing/ambiguous')
 fixture='`timescale 1ns/1fs\nmodule tb_xu_soc_ppa;\n  reg clk=0,lfclk=0,rst_n=0;\n'+dut[0]+'\n  initial begin\n    #0.000001;\n    $xu_mapped_inventory74();\n    $finish;\n  end\nendmodule\n'
 (a.out/'tb_xu_mapped_inventory74.sv').write_text(fixture)
 names=['tb_xu_soc_ppa.dut.'+r['instance'].replace('/','.') for r in inv['macros']];need(len(set(names))==336,'canonical macro ambiguity');header='#define XU_EXPECTED_MACROS 336\nstatic const char *xu_expected_macros[336]={\n'+',\n'.join(json.dumps(n)for n in names)+'\n};\n';(a.out/'xu_expected_macros74.h').write_text(header);(a.out/'xu_mapped_inventory74.c').write_bytes((ROOT/'xu_mapped_inventory74.c').read_bytes())
 review={'status':'PREPARED_STRUCTURE_PROBE_NOT_SIMULATED','qualification':'NOT_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_PROOF','original_tb':tbidentity,'activity':identity(a.activity),'inventory':inventory,'same_original_configuration_sha256':CONFIG,'required_mapped_sha256':NET_SHA,'rtl_internal_dependencies':refs,'rtl_preload_macro_references':len(memrefs),'required_vpi_preload_shapes':{'itcm':32,'shared':256,'no_other_preload':True,'mem_words':256,'word_bits':64},'original_task00_window':activity['tasks'][0]['activity_window'],'inputs':[]}
 need(len(memrefs)==288,'original physical preload count differs')
 if a.mapped:
  need(a.vendor and a.standard_model,'vendor and actual standard-cell Verilog model(s) required');net=identity(a.mapped);vendor=identity(a.vendor);need(net['sha256']==NET_SHA and vendor['sha256']==VENDOR_SHA,'actual mapped/vendor bytes differ');models=[identity(x)for x in a.standard_model];review['inputs']=[net,vendor]+models
  files=[str(a.mapped.resolve()),str(a.vendor.resolve())]+[str(x.resolve())for x in a.standard_model]+[str((a.out/'tb_xu_mapped_inventory74.sv').resolve())];(a.out/'mapped-probe.f').write_text('\n'.join(files)+'\n')
  include=a.vpi_include.resolve()if a.vpi_include else(a.run_vcs.resolve().parent.parent/'include'if a.run_vcs else Path('/ACTUAL_VCS_ROOT/include'))
  library=(a.out/'xu_mapped_inventory74.so').resolve();compiler=shutil.which(a.cc)
  cc_command=[compiler or a.cc,'-std=gnu99','-fPIC','-shared','-Wall','-Wextra','-Werror','-isystem',str(include),'-I'+str(a.out.resolve()),str((a.out/'xu_mapped_inventory74.c').resolve()),'-o',str(library)]
  review['vpi_compile_command']=cc_command
  command=[str(a.run_vcs)if a.run_vcs else 'vcs','-load',str(library)+':xu_mapped_probe_register','-full64','-sverilog','-timescale=1ns/1fs','-top','tb_xu_soc_ppa','-debug_access+all','-debug_region+cell','+vpi','+define+ARM_UD_MODEL','+define+DISABLE_SV_ASSERTION=1','-f',str((a.out/'mapped-probe.f').resolve()),'-Mdir='+str((a.out/'csrc').resolve()),'-o',str((a.out/'probe').resolve())];review['build_command']=command
  if a.run_vcs:
   need(compiler and(include/'vpi_user.h').is_file(),'matching VCS SDK header/compiler absent; pass --vpi-include')
   review['vpi_header']=identity(include/'vpi_user.h');review['cc']=identity(compiler);review['vcs']=identity(a.run_vcs)
   with(a.out/'vpi-build.log').open('wb')as output:r=subprocess.run(cc_command,cwd=str(a.out.resolve()),stdout=output,stderr=subprocess.STDOUT)
   need(r.returncode==0,'native VCS SDK probe compilation failed; raw vpi-build.log retained')
   review['vpi_compile_returncode']=r.returncode;review['vpi_library']=identity(library)
   with (a.out/'build.log').open('wb')as output:r=subprocess.run(command,cwd=str(a.out.resolve()),stdout=output,stderr=subprocess.STDOUT)
   need(r.returncode==0,'mapped structure VCS build failed; original build.log retained');review['build_returncode']=r.returncode
   with (a.out/'simulation.log').open('wb')as output:r=subprocess.run([str((a.out/'probe').resolve())],cwd=str(a.out.resolve()),stdout=output,stderr=subprocess.STDOUT)
   log=(a.out/'simulation.log').read_text();need(r.returncode==0 and log.count('status=PASS NOT_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_PROOF')==1 and 'XU_MAPPED_PROBE_ERROR'not in log,'actual mapped structure probe failed; raw log retained');review['simulation_returncode']=r.returncode;review['status']='EXECUTED_STRUCTURE_PROBE_ONLY'
  review['input_sha256_after']={v['path']:identity(v['path'])['sha256']for v in review['inputs']};need(all(review['input_sha256_after'][v['path']]==v['sha256']for v in review['inputs']),'mapped compile source changed')
 dump(a.out/'review.json',review);print(review['status'])
if __name__=='__main__':main()
