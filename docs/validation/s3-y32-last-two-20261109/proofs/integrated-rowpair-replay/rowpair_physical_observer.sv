// Test-only read-only observation of actual physical memory pins and registers.
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
bind LinearRowPairPrototype RowPairPhysicalObserver physical_observer (
  .clock(clock),
  .reset(reset),
  .clearFire(clearFire),
  .clearDone(io_clearDone),
  .start(io_start),
  .done(io_done),
  .second(io_secondRow),
  .macroEn({bias.memory.mem_ext.RW0_en, weights.banks_7.sram1.mem_ext.RW0_en, weights.banks_7.sram0.mem_ext.RW0_en, weights.banks_6.sram1.mem_ext.RW0_en, weights.banks_6.sram0.mem_ext.RW0_en, weights.banks_5.sram1.mem_ext.RW0_en, weights.banks_5.sram0.mem_ext.RW0_en, weights.banks_4.sram1.mem_ext.RW0_en, weights.banks_4.sram0.mem_ext.RW0_en, weights.banks_3.sram1.mem_ext.RW0_en, weights.banks_3.sram0.mem_ext.RW0_en, weights.banks_2.sram1.mem_ext.RW0_en, weights.banks_2.sram0.mem_ext.RW0_en, weights.banks_1.sram1.mem_ext.RW0_en, weights.banks_1.sram0.mem_ext.RW0_en, weights.banks_0.sram1.mem_ext.RW0_en, weights.banks_0.sram0.mem_ext.RW0_en}),
  .macroWrite({bias.memory.mem_ext.RW0_wmode, weights.banks_7.sram1.mem_ext.RW0_wmode, weights.banks_7.sram0.mem_ext.RW0_wmode, weights.banks_6.sram1.mem_ext.RW0_wmode, weights.banks_6.sram0.mem_ext.RW0_wmode, weights.banks_5.sram1.mem_ext.RW0_wmode, weights.banks_5.sram0.mem_ext.RW0_wmode, weights.banks_4.sram1.mem_ext.RW0_wmode, weights.banks_4.sram0.mem_ext.RW0_wmode, weights.banks_3.sram1.mem_ext.RW0_wmode, weights.banks_3.sram0.mem_ext.RW0_wmode, weights.banks_2.sram1.mem_ext.RW0_wmode, weights.banks_2.sram0.mem_ext.RW0_wmode, weights.banks_1.sram1.mem_ext.RW0_wmode, weights.banks_1.sram0.mem_ext.RW0_wmode, weights.banks_0.sram1.mem_ext.RW0_wmode, weights.banks_0.sram0.mem_ext.RW0_wmode}),
  .macroAddr({bias.memory.mem_ext.RW0_addr, weights.banks_7.sram1.mem_ext.RW0_addr, weights.banks_7.sram0.mem_ext.RW0_addr, weights.banks_6.sram1.mem_ext.RW0_addr, weights.banks_6.sram0.mem_ext.RW0_addr, weights.banks_5.sram1.mem_ext.RW0_addr, weights.banks_5.sram0.mem_ext.RW0_addr, weights.banks_4.sram1.mem_ext.RW0_addr, weights.banks_4.sram0.mem_ext.RW0_addr, weights.banks_3.sram1.mem_ext.RW0_addr, weights.banks_3.sram0.mem_ext.RW0_addr, weights.banks_2.sram1.mem_ext.RW0_addr, weights.banks_2.sram0.mem_ext.RW0_addr, weights.banks_1.sram1.mem_ext.RW0_addr, weights.banks_1.sram0.mem_ext.RW0_addr, weights.banks_0.sram1.mem_ext.RW0_addr, weights.banks_0.sram0.mem_ext.RW0_addr}),
  .macroData({bias.memory.mem_ext.RW0_wdata, weights.banks_7.sram1.mem_ext.RW0_wdata, weights.banks_7.sram0.mem_ext.RW0_wdata, weights.banks_6.sram1.mem_ext.RW0_wdata, weights.banks_6.sram0.mem_ext.RW0_wdata, weights.banks_5.sram1.mem_ext.RW0_wdata, weights.banks_5.sram0.mem_ext.RW0_wdata, weights.banks_4.sram1.mem_ext.RW0_wdata, weights.banks_4.sram0.mem_ext.RW0_wdata, weights.banks_3.sram1.mem_ext.RW0_wdata, weights.banks_3.sram0.mem_ext.RW0_wdata, weights.banks_2.sram1.mem_ext.RW0_wdata, weights.banks_2.sram0.mem_ext.RW0_wdata, weights.banks_1.sram1.mem_ext.RW0_wdata, weights.banks_1.sram0.mem_ext.RW0_wdata, weights.banks_0.sram1.mem_ext.RW0_wdata, weights.banks_0.sram0.mem_ext.RW0_wdata}),
  .xEn({xs_1.io_wen, xs_0.io_wen}),
  .xAddr({xs_1.io_waddr, xs_0.io_waddr}),
  .xData({xs_1.io_wdata, xs_0.io_wdata}),
  .allDatapathZero((xs_0.data_0 == 0) && (xs_0.data_1 == 0) && (xs_0.data_2 == 0) && (xs_0.data_3 == 0) && (xs_0.data_4 == 0) && (xs_0.data_5 == 0) && (xs_0.data_6 == 0) && (xs_0.data_7 == 0) && (xs_0.data_8 == 0) && (xs_0.data_9 == 0) && (xs_0.data_10 == 0) && (xs_0.data_11 == 0) && (xs_0.data_12 == 0) && (xs_0.data_13 == 0) && (xs_0.data_14 == 0) && (xs_0.data_15 == 0) && (xs_0.data_16 == 0) && (xs_0.data_17 == 0) && (xs_0.data_18 == 0) && (xs_0.data_19 == 0) && (xs_0.data_20 == 0) && (xs_0.data_21 == 0) && (xs_0.data_22 == 0) && (xs_0.data_23 == 0) && (xs_0.data_24 == 0) && (xs_0.data_25 == 0) && (xs_0.data_26 == 0) && (xs_0.data_27 == 0) && (xs_0.data_28 == 0) && (xs_0.data_29 == 0) && (xs_0.data_30 == 0) && (xs_0.data_31 == 0) && (xs_0.data_32 == 0) && (xs_0.data_33 == 0) && (xs_0.data_34 == 0) && (xs_0.data_35 == 0) && (xs_0.data_36 == 0) && (xs_0.data_37 == 0) && (xs_0.data_38 == 0) && (xs_0.data_39 == 0) && (xs_0.data_40 == 0) && (xs_0.data_41 == 0) && (xs_0.data_42 == 0) && (xs_0.data_43 == 0) && (xs_0.data_44 == 0) && (xs_0.data_45 == 0) && (xs_0.data_46 == 0) && (xs_0.data_47 == 0) && (xs_0.data_48 == 0) && (xs_0.data_49 == 0) && (xs_0.data_50 == 0) && (xs_0.data_51 == 0) && (xs_0.data_52 == 0) && (xs_0.data_53 == 0) && (xs_0.data_54 == 0) && (xs_0.data_55 == 0) && (xs_0.data_56 == 0) && (xs_0.data_57 == 0) && (xs_0.data_58 == 0) && (xs_0.data_59 == 0) && (xs_0.data_60 == 0) && (xs_0.data_61 == 0) && (xs_0.data_62 == 0) && (xs_0.data_63 == 0) && (xs_1.data_0 == 0) && (xs_1.data_1 == 0) && (xs_1.data_2 == 0) && (xs_1.data_3 == 0) && (xs_1.data_4 == 0) && (xs_1.data_5 == 0) && (xs_1.data_6 == 0) && (xs_1.data_7 == 0) && (xs_1.data_8 == 0) && (xs_1.data_9 == 0) && (xs_1.data_10 == 0) && (xs_1.data_11 == 0) && (xs_1.data_12 == 0) && (xs_1.data_13 == 0) && (xs_1.data_14 == 0) && (xs_1.data_15 == 0) && (xs_1.data_16 == 0) && (xs_1.data_17 == 0) && (xs_1.data_18 == 0) && (xs_1.data_19 == 0) && (xs_1.data_20 == 0) && (xs_1.data_21 == 0) && (xs_1.data_22 == 0) && (xs_1.data_23 == 0) && (xs_1.data_24 == 0) && (xs_1.data_25 == 0) && (xs_1.data_26 == 0) && (xs_1.data_27 == 0) && (xs_1.data_28 == 0) && (xs_1.data_29 == 0) && (xs_1.data_30 == 0) && (xs_1.data_31 == 0) && (xs_1.data_32 == 0) && (xs_1.data_33 == 0) && (xs_1.data_34 == 0) && (xs_1.data_35 == 0) && (xs_1.data_36 == 0) && (xs_1.data_37 == 0) && (xs_1.data_38 == 0) && (xs_1.data_39 == 0) && (xs_1.data_40 == 0) && (xs_1.data_41 == 0) && (xs_1.data_42 == 0) && (xs_1.data_43 == 0) && (xs_1.data_44 == 0) && (xs_1.data_45 == 0) && (xs_1.data_46 == 0) && (xs_1.data_47 == 0) && (xs_1.data_48 == 0) && (xs_1.data_49 == 0) && (xs_1.data_50 == 0) && (xs_1.data_51 == 0) && (xs_1.data_52 == 0) && (xs_1.data_53 == 0) && (xs_1.data_54 == 0) && (xs_1.data_55 == 0) && (xs_1.data_56 == 0) && (xs_1.data_57 == 0) && (xs_1.data_58 == 0) && (xs_1.data_59 == 0) && (xs_1.data_60 == 0) && (xs_1.data_61 == 0) && (xs_1.data_62 == 0) && (xs_1.data_63 == 0) && (engines_0.peArray.pes_0.ACC == 0) && (engines_0.peArray.pes_1.ACC == 0) && (engines_0.peArray.pes_2.ACC == 0) && (engines_0.peArray.pes_3.ACC == 0) && (engines_0.peArray.pes_4.ACC == 0) && (engines_0.peArray.pes_5.ACC == 0) && (engines_0.peArray.pes_6.ACC == 0) && (engines_0.peArray.pes_7.ACC == 0) && (engines_1.peArray.pes_0.ACC == 0) && (engines_1.peArray.pes_1.ACC == 0) && (engines_1.peArray.pes_2.ACC == 0) && (engines_1.peArray.pes_3.ACC == 0) && (engines_1.peArray.pes_4.ACC == 0) && (engines_1.peArray.pes_5.ACC == 0) && (engines_1.peArray.pes_6.ACC == 0) && (engines_1.peArray.pes_7.ACC == 0) && (engines_0.resultReg_0 == 0) && (engines_0.resultReg_1 == 0) && (engines_0.resultReg_2 == 0) && (engines_0.resultReg_3 == 0) && (engines_0.resultReg_4 == 0) && (engines_0.resultReg_5 == 0) && (engines_0.resultReg_6 == 0) && (engines_0.resultReg_7 == 0) && (engines_1.resultReg_0 == 0) && (engines_1.resultReg_1 == 0) && (engines_1.resultReg_2 == 0) && (engines_1.resultReg_3 == 0) && (engines_1.resultReg_4 == 0) && (engines_1.resultReg_5 == 0) && (engines_1.resultReg_6 == 0) && (engines_1.resultReg_7 == 0) && (results_0_0_0 == 0) && (results_0_0_1 == 0) && (results_0_0_2 == 0) && (results_0_0_3 == 0) && (results_0_0_4 == 0) && (results_0_0_5 == 0) && (results_0_0_6 == 0) && (results_0_0_7 == 0) && (results_0_1_0 == 0) && (results_0_1_1 == 0) && (results_0_1_2 == 0) && (results_0_1_3 == 0) && (results_0_1_4 == 0) && (results_0_1_5 == 0) && (results_0_1_6 == 0) && (results_0_1_7 == 0) && (results_1_0_0 == 0) && (results_1_0_1 == 0) && (results_1_0_2 == 0) && (results_1_0_3 == 0) && (results_1_0_4 == 0) && (results_1_0_5 == 0) && (results_1_0_6 == 0) && (results_1_0_7 == 0) && (results_1_1_0 == 0) && (results_1_1_1 == 0) && (results_1_1_2 == 0) && (results_1_1_3 == 0) && (results_1_1_4 == 0) && (results_1_1_5 == 0) && (results_1_1_6 == 0) && (results_1_1_7 == 0)),
  .allDatapathNonzero((xs_0.data_0 != 0) && (xs_0.data_1 != 0) && (xs_0.data_2 != 0) && (xs_0.data_3 != 0) && (xs_0.data_4 != 0) && (xs_0.data_5 != 0) && (xs_0.data_6 != 0) && (xs_0.data_7 != 0) && (xs_0.data_8 != 0) && (xs_0.data_9 != 0) && (xs_0.data_10 != 0) && (xs_0.data_11 != 0) && (xs_0.data_12 != 0) && (xs_0.data_13 != 0) && (xs_0.data_14 != 0) && (xs_0.data_15 != 0) && (xs_0.data_16 != 0) && (xs_0.data_17 != 0) && (xs_0.data_18 != 0) && (xs_0.data_19 != 0) && (xs_0.data_20 != 0) && (xs_0.data_21 != 0) && (xs_0.data_22 != 0) && (xs_0.data_23 != 0) && (xs_0.data_24 != 0) && (xs_0.data_25 != 0) && (xs_0.data_26 != 0) && (xs_0.data_27 != 0) && (xs_0.data_28 != 0) && (xs_0.data_29 != 0) && (xs_0.data_30 != 0) && (xs_0.data_31 != 0) && (xs_0.data_32 != 0) && (xs_0.data_33 != 0) && (xs_0.data_34 != 0) && (xs_0.data_35 != 0) && (xs_0.data_36 != 0) && (xs_0.data_37 != 0) && (xs_0.data_38 != 0) && (xs_0.data_39 != 0) && (xs_0.data_40 != 0) && (xs_0.data_41 != 0) && (xs_0.data_42 != 0) && (xs_0.data_43 != 0) && (xs_0.data_44 != 0) && (xs_0.data_45 != 0) && (xs_0.data_46 != 0) && (xs_0.data_47 != 0) && (xs_0.data_48 != 0) && (xs_0.data_49 != 0) && (xs_0.data_50 != 0) && (xs_0.data_51 != 0) && (xs_0.data_52 != 0) && (xs_0.data_53 != 0) && (xs_0.data_54 != 0) && (xs_0.data_55 != 0) && (xs_0.data_56 != 0) && (xs_0.data_57 != 0) && (xs_0.data_58 != 0) && (xs_0.data_59 != 0) && (xs_0.data_60 != 0) && (xs_0.data_61 != 0) && (xs_0.data_62 != 0) && (xs_0.data_63 != 0) && (xs_1.data_0 != 0) && (xs_1.data_1 != 0) && (xs_1.data_2 != 0) && (xs_1.data_3 != 0) && (xs_1.data_4 != 0) && (xs_1.data_5 != 0) && (xs_1.data_6 != 0) && (xs_1.data_7 != 0) && (xs_1.data_8 != 0) && (xs_1.data_9 != 0) && (xs_1.data_10 != 0) && (xs_1.data_11 != 0) && (xs_1.data_12 != 0) && (xs_1.data_13 != 0) && (xs_1.data_14 != 0) && (xs_1.data_15 != 0) && (xs_1.data_16 != 0) && (xs_1.data_17 != 0) && (xs_1.data_18 != 0) && (xs_1.data_19 != 0) && (xs_1.data_20 != 0) && (xs_1.data_21 != 0) && (xs_1.data_22 != 0) && (xs_1.data_23 != 0) && (xs_1.data_24 != 0) && (xs_1.data_25 != 0) && (xs_1.data_26 != 0) && (xs_1.data_27 != 0) && (xs_1.data_28 != 0) && (xs_1.data_29 != 0) && (xs_1.data_30 != 0) && (xs_1.data_31 != 0) && (xs_1.data_32 != 0) && (xs_1.data_33 != 0) && (xs_1.data_34 != 0) && (xs_1.data_35 != 0) && (xs_1.data_36 != 0) && (xs_1.data_37 != 0) && (xs_1.data_38 != 0) && (xs_1.data_39 != 0) && (xs_1.data_40 != 0) && (xs_1.data_41 != 0) && (xs_1.data_42 != 0) && (xs_1.data_43 != 0) && (xs_1.data_44 != 0) && (xs_1.data_45 != 0) && (xs_1.data_46 != 0) && (xs_1.data_47 != 0) && (xs_1.data_48 != 0) && (xs_1.data_49 != 0) && (xs_1.data_50 != 0) && (xs_1.data_51 != 0) && (xs_1.data_52 != 0) && (xs_1.data_53 != 0) && (xs_1.data_54 != 0) && (xs_1.data_55 != 0) && (xs_1.data_56 != 0) && (xs_1.data_57 != 0) && (xs_1.data_58 != 0) && (xs_1.data_59 != 0) && (xs_1.data_60 != 0) && (xs_1.data_61 != 0) && (xs_1.data_62 != 0) && (xs_1.data_63 != 0) && (engines_0.peArray.pes_0.ACC != 0) && (engines_0.peArray.pes_1.ACC != 0) && (engines_0.peArray.pes_2.ACC != 0) && (engines_0.peArray.pes_3.ACC != 0) && (engines_0.peArray.pes_4.ACC != 0) && (engines_0.peArray.pes_5.ACC != 0) && (engines_0.peArray.pes_6.ACC != 0) && (engines_0.peArray.pes_7.ACC != 0) && (engines_1.peArray.pes_0.ACC != 0) && (engines_1.peArray.pes_1.ACC != 0) && (engines_1.peArray.pes_2.ACC != 0) && (engines_1.peArray.pes_3.ACC != 0) && (engines_1.peArray.pes_4.ACC != 0) && (engines_1.peArray.pes_5.ACC != 0) && (engines_1.peArray.pes_6.ACC != 0) && (engines_1.peArray.pes_7.ACC != 0) && (engines_0.resultReg_0 != 0) && (engines_0.resultReg_1 != 0) && (engines_0.resultReg_2 != 0) && (engines_0.resultReg_3 != 0) && (engines_0.resultReg_4 != 0) && (engines_0.resultReg_5 != 0) && (engines_0.resultReg_6 != 0) && (engines_0.resultReg_7 != 0) && (engines_1.resultReg_0 != 0) && (engines_1.resultReg_1 != 0) && (engines_1.resultReg_2 != 0) && (engines_1.resultReg_3 != 0) && (engines_1.resultReg_4 != 0) && (engines_1.resultReg_5 != 0) && (engines_1.resultReg_6 != 0) && (engines_1.resultReg_7 != 0) && (results_0_0_0 != 0) && (results_0_0_1 != 0) && (results_0_0_2 != 0) && (results_0_0_3 != 0) && (results_0_0_4 != 0) && (results_0_0_5 != 0) && (results_0_0_6 != 0) && (results_0_0_7 != 0) && (results_0_1_0 != 0) && (results_0_1_1 != 0) && (results_0_1_2 != 0) && (results_0_1_3 != 0) && (results_0_1_4 != 0) && (results_0_1_5 != 0) && (results_0_1_6 != 0) && (results_0_1_7 != 0) && (results_1_0_0 != 0) && (results_1_0_1 != 0) && (results_1_0_2 != 0) && (results_1_0_3 != 0) && (results_1_0_4 != 0) && (results_1_0_5 != 0) && (results_1_0_6 != 0) && (results_1_0_7 != 0) && (results_1_1_0 != 0) && (results_1_1_1 != 0) && (results_1_1_2 != 0) && (results_1_1_3 != 0) && (results_1_1_4 != 0) && (results_1_1_5 != 0) && (results_1_1_6 != 0) && (results_1_1_7 != 0))
);
