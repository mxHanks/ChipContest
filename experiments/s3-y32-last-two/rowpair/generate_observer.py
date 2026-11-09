"""Build a read-only bind; no force, deposit, hierarchical writes or preload."""
from pathlib import Path

def generate(path):
    macros=[f'weights.banks_{bank}.sram{half}.mem_ext' for bank in range(8) for half in range(2)]
    macros+=['bias.memory.mem_ext']
    regs=[f'xs_{row}.data_{k}' for row in range(2) for k in range(64)]
    regs += [f'engines_{row}.peArray.pes_{lane}.ACC' for row in range(2) for lane in range(8)]
    regs += [f'engines_{row}.resultReg_{lane}' for row in range(2) for lane in range(8)]
    regs += [f'results_{slot}_{row}_{lane}' for slot in range(2) for row in range(2) for lane in range(8)]
    def cat(items): return '{'+', '.join(reversed(items))+'}'
    connections={
        'clock':'clock','reset':'reset','clearFire':'clearFire','clearDone':'io_clearDone',
        'start':'io_start','done':'io_done','second':'io_secondRow',
        'macroEn':cat([p+'.RW0_en' for p in macros]),
        'macroWrite':cat([p+'.RW0_wmode' for p in macros]),
        'macroAddr':cat([p+'.RW0_addr' for p in macros]),
        'macroData':cat([p+'.RW0_wdata' for p in macros]),
        'xEn':cat([f'xs_{r}.io_wen' for r in range(2)]),
        'xAddr':cat([f'xs_{r}.io_waddr' for r in range(2)]),
        'xData':cat([f'xs_{r}.io_wdata' for r in range(2)]),
        'allDatapathZero':' && '.join(f'({p} == 0)' for p in regs),
        'allDatapathNonzero':' && '.join(f'({p} != 0)' for p in regs),
    }
    header='''// Test-only read-only observation of actual physical memory pins and registers.
module RowPairPhysicalObserver(
 input clock, reset, clearFire, clearDone, start, done, second,
 input [16:0] macroEn, macroWrite,
 input [169:0] macroAddr, input [271:0] macroData,
 input [1:0] xEn, input [11:0] xAddr, input [31:0] xData,
 input allDatapathZero, allDatapathNonzero
);
 reg observing=0;
 integer clears=0, wCount=0, bCount=0, xCount=0;
 integer rowWeightReads=0,rowBiasReads=0;
 reg rowSecond=0;
 reg [1023:0] seenW[0:15], dirtyW[0:15];
 reg [767:0] seenBias, dirtyBias;
 reg [63:0] seenX[0:1], dirtyX[0:1];
 integer i, address;
 initial begin
   seenBias=0;dirtyBias=0;
   for(integer j=0;j<16;j++)begin seenW[j]=0;dirtyW[j]=0;end
   for(integer j=0;j<2;j++)begin seenX[j]=0;dirtyX[j]=0;end
 end
 always @(posedge clock) begin
   if (!reset) begin
     if(start)begin rowWeightReads=0;rowBiasReads=0;rowSecond=second;end
     for(i=0;i<17;i++)if(macroEn[i]&&!macroWrite[i])begin
       if(i<16)rowWeightReads=rowWeightReads+1;
       else rowBiasReads=rowBiasReads+1;
     end
     if(done)begin
       assert(rowWeightReads==16384) else $fatal(1,"actual physical W macro read count");
       assert(rowBiasReads==768) else $fatal(1,"actual physical bias macro read count");
       $display("ROWPAIR_ACTUAL_MACRO_READ_PASS second_row=%0d W=16384 BIAS=768",rowSecond);
     end
     if(clearFire)begin
       assert(!observing) else $fatal(1,"clear observer overlap");
       if(clears!=0)begin
         for(i=0;i<16;i++)assert(&dirtyW[i]) else $fatal(1,"W preclear physical nonzero coverage");
         assert(&dirtyBias) else $fatal(1,"bias preclear physical nonzero coverage");
         for(i=0;i<2;i++)assert(&dirtyX[i]) else $fatal(1,"X preclear physical nonzero coverage");
         assert(allDatapathNonzero) else $fatal(1,"ACC/result/FIFO/X nonzero preclear state");
       end
       observing=1;wCount=0;bCount=0;xCount=0;seenBias=0;
       for(i=0;i<16;i++)seenW[i]=0;
       for(i=0;i<2;i++)seenX[i]=0;
     end
     for(i=0;i<17;i++)if(macroEn[i]&&macroWrite[i])begin
       address=macroAddr[i*10+:10];
       if(i<16)dirtyW[i][address]=(macroData[i*16+:16]!=0);
       else if(address<768)dirtyBias[address]=(macroData[i*16+:16]!=0);
       if(observing)begin
         assert(macroData[i*16+:16]==0) else $fatal(1,"nonzero physical clear SRAM write");
         if(i<16)begin
           assert(!seenW[i][address]) else $fatal(1,"duplicate physical W clear address");
           seenW[i][address]=1;wCount=wCount+1;
         end else begin
           assert(address<768&&!seenBias[address]) else $fatal(1,"bad/duplicate bias clear address");
           seenBias[address]=1;bCount=bCount+1;
         end
       end
     end
     for(i=0;i<2;i++)if(xEn[i])begin
       address=xAddr[i*6+:6];dirtyX[i][address]=(xData[i*16+:16]!=0);
       if(observing)begin
         assert(xData[i*16+:16]==0&&!seenX[i][address]) else $fatal(1,"bad/duplicate actual X clear write");
         seenX[i][address]=1;xCount=xCount+1;
       end
     end
     if(clearDone)begin
       assert(observing&&wCount==16384&&bCount==768&&xCount==128) else $fatal(1,"physical clear totals");
       for(i=0;i<16;i++)assert(&seenW[i]) else $fatal(1,"physical W clear coverage");
       assert(&seenBias) else $fatal(1,"physical bias clear coverage");
       for(i=0;i<2;i++)assert(&seenX[i]) else $fatal(1,"physical X clear coverage");
       assert(allDatapathZero) else $fatal(1,"physical X/ACC/result/FIFO registers not zero after clear");
       observing=0;clears=clears+1;
       $display("ROWPAIR_PHYSICAL_CLEAR_PASS call=%0d W=16384 BIAS=768 X=128 ACC=16 ENGINE_RESULT=16 FIFO=32 nonzero_prestate=%0d",clears,clears!=1);
     end
   end
 end
endmodule
'''
    binding='bind LinearRowPairPrototype RowPairPhysicalObserver physical_observer (\n'+',\n'.join(
        f'  .{name}({value})' for name,value in connections.items())+'\n);\n'
    Path(path).write_text(header+binding)

if __name__=='__main__':generate(Path(__file__).with_name('rowpair_physical_observer.sv'))
