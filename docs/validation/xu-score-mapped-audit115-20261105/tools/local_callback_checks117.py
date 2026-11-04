from pathlib import Path
import hashlib,json,subprocess,re
B=Path(__file__).resolve().parent;O=B/'local-callback117-v1';O.mkdir(exist_ok=False)
def run(name,args):
 log=O/(name+'.log')
 with log.open('xb')as f:p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=60)
 if p.returncode:raise ValueError(name+' failed '+log.read_text())
 return dict(name=name,command=args,returncode=p.returncode,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
rows=[run('cc',['cc','-std=gnu99','-Wall','-Wextra','-Werror','-fPIC','-shared','-isystem','/usr/include/iverilog',str(B/'xu_mapped_causal117.c'),'-o',str(O/'causal117.vpi')])]
main={};root={'u_shared':'shared'};d=root
for part in ['u_soc','u_e203_subsys_top','u_e203_subsys_main']:d[part]={};d=d[part]
d['u_e203_subsys_perips']={'u_accel_icb_slave':'accel'}
a=d
for part in ['u_e203_subsys_mems','u_sirv_mem_fab','u_sirv_gnrl_icb_buffer','u_sirv_gnrl_rsp_fifo']:
 a[part]={};a=a[part]
a['dp_gt0']={'vec_31_dfflr':{'qout_r_reg[0]':'ff'}}
bodies=[];number=[0]
def emit(tree):
 name='node%d'%number[0];number[0]+=1;items=[]
 for instance,value in tree.items():
  module=value if isinstance(value,str)else emit(value)
  token=instance if re.fullmatch(r'\w+',instance)else'\\'+instance+' '
  items.append(' %s %s();'%(module,token))
 # All parent FIFO native nodes are named as local regs in this mechanism-only fixture.
 if 'dp_gt0'in tree:items.append('reg[1:0]vec_r=1;reg i_vld=0,i_rdy=1,o_vld=0,o_rdy=1;initial #9359390.05 vec_r=2\'bxx;')
 bodies.append('module '+name+';\n'+'\n'.join(items)+'\nendmodule');return name
base=emit(root)
body='''`timescale 1ns/1fs
module tb_xu_soc_ppa;
 %s dut();
 initial begin #9359424;$display("HOST117_MECHANISM_DONE NO_DUT_OR_TIMING_PROOF");$finish;end
endmodule
module shared;
 reg clk=0,rst_n=1,cmd_valid=0,cmd_ready=1,cmd_read=1,rsp_valid=0,rsp_ready=1,rsp_err=0;
 reg[31:0]cmd_addr=0,cmd_wdata=0,rsp_rdata=0;reg[3:0]cmd_wmask=15;
 initial begin #9359390.05;cmd_valid=1;#10;cmd_ready=1'bx;end
endmodule
module accel;reg clk=0,rst_n=1;initial #9359390.05 clk=1;endmodule
module ff;reg D=0,CK=0,RDN=1,notifier=0,Q=0;
 always@(notifier)if($time>0)Q=1'bx;
 initial begin #9359390.05;D=1;CK=1;notifier=1;end
endmodule
'''%base+'\n'+'\n'.join(bodies)
for label,source in [('reference',body),('missing-target',body.replace('\\qout_r_reg[0] ','wrong_target'))]:
 p=O/(label+'.sv');p.write_text(source)
 rows.append(run(label+'-compile',['iverilog','-g2012','-s','tb_xu_soc_ppa','-o',str(O/(label+'.vvp')),str(p)]))
 rows.append(run(label+'-run',['vvp','-M'+str(O),'-mcausal117',str(O/(label+'.vvp'))]))
 text=(O/(label+'-run.log')).read_text()
 if label=='reference':
  assert re.search(r'XU_CAUSAL117_READY target_cells=1 fifo_modules=1 shared_modules=1 accel_modules=1 observed_nodes=\d+ failed=0 ',text)
  assert re.search(r'XU_CAUSAL117_EVENT .*bval=0000000000000001 name=.*\.Q$',text,re.M)
  assert re.search(r'XU_CAUSAL117_EVENT .*aval=0000000000000001 bval=0000000000000000 name=.*\.notifier$',text,re.M)
  assert re.search(r'XU_CAUSAL117_EVENT .*bval=0000000000000001 name=.*\.cmd_ready$',text,re.M)
  assert 'events_in_slice=0'not in text
 else:assert re.search(r'XU_CAUSAL117_READY target_cells=0 fifo_modules=1 shared_modules=1 accel_modules=1 observed_nodes=\d+ failed=1 ',text)
(O/'results.json').write_text(json.dumps(dict(scope='ICARUS_PASSIVE_CALLBACK_MECHANISM_ONLY_NOT_VENDOR_OR_MAPPED_VCS',source_sha256=hashlib.sha256((B/'xu_mapped_causal117.c').read_bytes()).hexdigest(),commands=rows,positive='actual callback serial/tick/four-state notifier/Q/shared handshake in synthetic hierarchy',negative='missing target yields failed=1, no fake binding success'),sort_keys=True,indent=2)+'\n')
print('LOCAL117_CALLBACK: native Icarus callback positive + missing-target rejection; no vendor or mapped qualification')
