// Read-only physical pins/register observer. No force/deposit/array writes.
module TilePhysicalObserver(
 input clock,reset,clearFire,clearDone,start,done,abort,warmup,
 input strictDirty,ownersIdle,snapshotZero,
 input [3:0] validRows,
 input [16:0] macroEn,macroWrite,
 input [169:0] macroAddr,input [271:0] macroData,
 input [15:0] xEn,xPacked,input [95:0] xAddr,
 input [255:0] xData,xDataHi,
 input allDatapathZero,allDatapathNonzero
);
 reg observing=0;
 integer clears=0,wCount=0,bCount=0,xCount=0,physicalCycles=0;
 integer rowWeightReads=0,rowBiasReads=0,rowRows=0;
 integer nonzeroW=0,nonzeroB=0,nonzeroX=0;
 reg [1023:0] seenW[0:15],dirtyW[0:15];
 reg [767:0] seenB=0,dirtyB=0;
 reg [63:0] seenX[0:15],dirtyX[0:15];
 integer i,j,address;
 initial begin
   for(integer n=0;n<16;n++)begin
     seenW[n]=0;dirtyW[n]=0;seenX[n]=0;dirtyX[n]=0;
   end
 end
 always @(posedge clock)begin
   if(reset)begin
     observing=0;clears=0;seenB=0;dirtyB=0;
     rowWeightReads=0;rowBiasReads=0;
     for(i=0;i<16;i++)begin seenW[i]=0;dirtyW[i]=0;seenX[i]=0;dirtyX[i]=0;end
   end else begin
     if(abort)observing=0;
     if(start)begin rowWeightReads=0;rowBiasReads=0;rowRows=validRows;end
     for(i=0;i<17;i++)if(macroEn[i]&&!macroWrite[i])begin
       if(observing)$fatal(1,"physical SRAM read during exclusive clear");
       if(i<16)rowWeightReads=rowWeightReads+1;else rowBiasReads=rowBiasReads+1;
     end
     if(done)begin
       if(rowWeightReads!=16384||rowBiasReads!=768)
         $fatal(1,"tile actual macro reads W=%0d B=%0d",rowWeightReads,rowBiasReads);
       $display("D4K_TILE_MACRO_READ_PASS rows=%0d W=16384 BIAS=768",rowRows);
     end
     if(clearFire)begin
       if(observing||!ownersIdle)$fatal(1,"clear overlaps live owner");
       nonzeroW=0;nonzeroB=0;nonzeroX=0;
       for(i=0;i<16;i++)begin
         for(j=0;j<1024;j++)nonzeroW=nonzeroW+dirtyW[i][j];
         for(j=0;j<64;j++)nonzeroX=nonzeroX+dirtyX[i][j];
       end
       for(j=0;j<768;j++)nonzeroB=nonzeroB+dirtyB[j];
       if(clears>0)begin
         if(nonzeroW==0||nonzeroB==0||nonzeroX==0)
           $fatal(1,"clear lacks prior publicly produced dirty W/BIAS/X");
         if(strictDirty)begin
           for(i=0;i<16;i++)if(!(&dirtyW[i])||!(&dirtyX[i]))$fatal(1,"all-address dirty prestate missing");
           if(!(&dirtyB)||!allDatapathNonzero)$fatal(1,"register/bias dirty prestate missing");
         end
       end
       $display("D4K_PHYSICAL_CLEAR_BEGIN call=%0d warmup=%0d nonzero_W=%0d nonzero_BIAS=%0d nonzero_X=%0d observed_last_public_writes=1",clears+1,warmup,nonzeroW,nonzeroB,nonzeroX);
       observing=1;wCount=0;bCount=0;xCount=0;physicalCycles=0;seenB=0;
       for(i=0;i<16;i++)begin seenW[i]=0;seenX[i]=0;end
     end
     if(observing)physicalCycles=physicalCycles+1;
     for(i=0;i<17;i++)if(macroEn[i]&&macroWrite[i])begin
       address=macroAddr[i*10+:10];
       if(i<16)dirtyW[i][address]=(macroData[i*16+:16]!==16'b0);
       else begin
         if(address>=768)$fatal(1,"bias write outside physical aperture");
         dirtyB[address]=(macroData[i*16+:16]!==16'b0);
       end
       if(observing)begin
         if(macroData[i*16+:16]!==16'b0)$fatal(1,"nonzero physical SRAM clear write");
         if(i<16)begin
           if(seenW[i][address])$fatal(1,"duplicate physical W clear address");
           seenW[i][address]=1;wCount=wCount+1;
         end else begin
           if(seenB[address])$fatal(1,"duplicate physical bias clear address");
           seenB[address]=1;bCount=bCount+1;
         end
       end
     end
     for(i=0;i<16;i++)if(xEn[i])begin
       address=xAddr[i*6+:6];
       dirtyX[i][address]=(xData[i*16+:16]!==16'b0);
       if(xPacked[i])begin
         if(address[0]||address>=63)$fatal(1,"invalid packed physical X write");
         dirtyX[i][address+1]=(xDataHi[i*16+:16]!==16'b0);
       end
       if(observing)begin
         if(xPacked[i]||xData[i*16+:16]!==16'b0||seenX[i][address])
           $fatal(1,"bad/duplicate physical X clear write");
         seenX[i][address]=1;xCount=xCount+1;
       end
     end
     if(clearDone)begin
       if(!observing||wCount!=16384||bCount!=768||xCount!=1024)
         $fatal(1,"incomplete physical clear W=%0d B=%0d X=%0d",wCount,bCount,xCount);
       for(i=0;i<16;i++)if(!(&seenW[i])||!(&seenX[i]))$fatal(1,"physical address coverage hole");
       if(!(&seenB)||!allDatapathZero||!snapshotZero||!ownersIdle)
         $fatal(1,"physical clear payload or owner not zero");
       clears=clears+1;observing=0;
       $display("D4K_PHYSICAL_CLEAR_PASS call=%0d warmup=%0d W=16384 BIAS=768 X=1024 total16bit_writes=18176 physical_cycles=%0d X_REGS=1024 ACC=64 ENGINE_RESULT=64 FIFO=128 BIAS_CACHE=16 DMA_SNAPSHOT=1 all_addresses=1 all_payload_zero=1",clears,warmup,physicalCycles);
     end
   end
 end
endmodule
