#!/usr/bin/env python3
"""Read-only 36 macro-pin clear proof and scalar transaction lifetime checks."""
from pathlib import Path

def generate(path,core='dma.u_core',clock='clk',result_macros=3,dma='dma',reset='!rst_n'):
    if result_macros not in (3,21):raise ValueError('known result macro organization required')
    total_macros=33+result_macros
    macros=[]
    for bank in range(8):
        for half in range(2):macros.append(f'{core}.weights.banks_{bank}.sram{half}.mem_ext.macro')
    macros.append(f'{core}.biasMemory.mem_ext.macro')
    for s in range(2):
        for row in range(8):macros.append(f'{core}.xSets[{s}].rows[{row}].memory.memory.mem_ext.macro')
    for s in range(result_macros):macros.append(f'{core}.resultSlices[{s}].memory.mem_ext.macro')
    lines=[f'wire [{total_macros-1}:0] sm_en,sm_wr,sm_ret;',f'wire [{total_macros*10-1}:0] sm_addr;',f'wire [{total_macros*16-1}:0] sm_data,sm_wen;']
    for i,m in enumerate(macros):
        lines.extend([f'assign sm_en[{i}]=!{m}.CEN;',f'assign sm_wr[{i}]=!{m}.GWEN;',
          f'assign sm_ret[{i}]={m}.RET1N;',f'assign sm_addr[{i*10}+:10]={m}.A;',
          f'assign sm_data[{i*16}+:16]={m}.D;',f'assign sm_wen[{i*16}+:16]={m}.WEN;'])
    zeros=[f'({core}.rows[{r}].lanes[{c}].pe.ACC===0)' for r in range(8) for c in range(8)]
    zeros.extend([f'({core}.biasLow===0)',f'({core}.hostData===0)', f'({dma}.w_low===0)', f'({dma}.bias_low===0)', f'({dma}.bias_data===0)', f'({dma}.lock_data===0)'])
    lines.extend(['StorageMacroObserver storage_observer(',
      f'.clock({clock}),.reset({reset}),.abort({dma}.aborting),.clearFire({core}.clearFire),',
      f'.clearDone({core}.io_clearDone),.dirtyRequired({dma}.done),.en(sm_en),.wr(sm_wr),.ret(sm_ret),',
      '.address(sm_addr),.data(sm_data),.wen(sm_wen),',
      '.datapathZero('+ '&&'.join(zeros)+'),',
      f'.held({core}.readHeld),.pop({core}.pop),.raw({core}.resultRaw),',
      f'.storeBlocked({core}.active&&{core}.state==7&&{core}.readHeld),.storeWrite({core}.storeWrite),',
      f'.resultRead({core}.resultRead),.taskDone({dma}.done),',
      f'.ownersIdle(!{dma}.pending&&!{dma}.locked&&!{dma}.core_active&&!{dma}.core_out_valid));'])
    Path(path).write_text('\n'.join(lines)+'\n')
    body=r'''module StorageMacroObserver(
 input clock,reset,abort,clearFire,clearDone,dirtyRequired,
 input [35:0] en,wr,ret,input [359:0] address,input [575:0] data,wen,
 input datapathZero,held,pop,input [40:0] raw,input ownersIdle,
 input storeBlocked,storeWrite,resultRead,taskDone
);
 reg [1023:0] seen[0:35],dirty[0:35];
 reg observing=0,previousHeld=0,previousPop=0;
 reg [40:0] previousRaw=0;
 integer clears=0,writes=0,i,j,a;
 integer nw,nb,nx,nr;
 integer blockedEdges=0,heldEdges=0,storeEdges=0,readEdges=0,pops=0;
 reg previousDone=0;
 initial for(integer n=0;n<36;n++)begin seen[n]=0;dirty[n]=0;end
 always @(posedge clock)begin
   if(reset)begin
     observing=0;clears=0;previousHeld=0;previousPop=0;previousDone=0;
     for(i=0;i<36;i++)begin seen[i]=0;dirty[i]=0;end
   end else begin
     if(abort)begin observing=0;previousHeld=0;end
     if(previousHeld&&!previousPop&&!abort&&!clearFire&&held&&raw!==previousRaw)
       $fatal(1,"Result macro Q changed before scalar write response retirement");
     previousHeld=held;previousPop=pop;previousRaw=raw;
     if(clearFire)begin
       if(!ownersIdle||observing)$fatal(1,"clear before owners drained");
       nw=0;nb=0;nx=0;nr=0;
       for(i=0;i<36;i++)for(j=0;j<1024;j++)begin
         if(dirty[i][j])begin
           if(i<16)nw=nw+1;else if(i==16)nb=nb+1;else if(i<33)nx=nx+1;else nr=nr+1;
         end
       end
       if(clears>0&&dirtyRequired&&(nw==0||nb==0||nx==0||nr==0))
         $fatal(1,"clear lacks publicly produced nonzero W/bias/X/result prestate");
       $display("SM_CLEAR_BEGIN W_dirty=%0d B_dirty=%0d X_dirty=%0d R_dirty=%0d",nw,nb,nx,nr);
       observing=1;writes=0;
       blockedEdges=0;heldEdges=0;storeEdges=0;readEdges=0;pops=0;
       for(i=0;i<36;i++)seen[i]=0;
     end
     if(storeBlocked)blockedEdges=blockedEdges+1;
     if(held)heldEdges=heldEdges+1;
     if(storeWrite)storeEdges=storeEdges+1;
     if(resultRead)readEdges=readEdges+1;
     if(pop)pops=pops+1;
     if(storeWrite&&resultRead)$fatal(1,"physical result read/store conflict");
     if(taskDone&&!previousDone)
       $display("SM_RESULT_PORT_MEASURE store_edges=%0d read_edges=%0d hold_edges=%0d producer_blocked_by_read=%0d scalar_rsp_retired_pops=%0d",storeEdges,readEdges,heldEdges,blockedEdges,pops);
     previousDone=taskDone;
     for(i=0;i<36;i++)if(en[i])begin
       if(ret[i]!==1'b1)$fatal(1,"macro retention not active");
       if(wr[i])begin
         a=address[10*i+:10];
         if(wen[16*i+:16]!==16'b0)$fatal(1,"physical write mask not whole16bit");
         if(i==16&&a>=768)$fatal(1,"bias write outside logical aperture");
         dirty[i][a]=(data[16*i+:16]!==16'b0);
         if(observing)begin
           if(data[16*i+:16]!==16'b0||seen[i][a])$fatal(1,"nonzero/duplicate physical clear write");
           seen[i][a]=1;writes=writes+1;
         end
       end else if(observing)$fatal(1,"macro read during exclusive clear");
     end
     if(clearDone)begin
       if(!observing||writes!=36608||!datapathZero||!ownersIdle)$fatal(1,"incomplete physical clear/state zero proof writes=%0d",writes);
       for(i=0;i<36;i++)begin
         if(i==16)begin if(!(&seen[i][767:0]))$fatal(1,"bias clear address hole");end
         else if(!(&seen[i]))$fatal(1,"physical macro clear address hole macro=%0d",i);
       end
       observing=0;clears=clears+1;
       $display("SM_PHYSICAL_CLEAR_PASS W=16384 BIAS=768 X=16384 RESULT=3072 total16bit_writes=36608 all_addresses=1 ACC64_zero=1");
     end
   end
 end
endmodule
'''
    if result_macros!=3:
        body=(body.replace('[35:0]',f'[{total_macros-1}:0]').replace('[359:0]',f'[{total_macros*10-1}:0]')
          .replace('[575:0]',f'[{total_macros*16-1}:0]').replace('[0:35]',f'[0:{total_macros-1}]')
          .replace('n<36',f'n<{total_macros}').replace('i<36',f'i<{total_macros}')
          .replace('writes!=36608',f'writes!={33536+1024*result_macros}')
          .replace('RESULT=3072 total16bit_writes=36608',f'RESULT={1024*result_macros} total16bit_writes={33536+1024*result_macros}'))
    Path(path).with_name('StorageMacroObserver.sv').write_text(body)
