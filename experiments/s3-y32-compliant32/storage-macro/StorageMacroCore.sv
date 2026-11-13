// Opt-in storage repair. Arithmetic is the byte-identical MacPE_Acc41 below.
// Three real single-port macros hold two packets of 64 signed41 results.
module LinearTileDmaCore(
 input clock,reset,io_start,input [3:0] io_validRows,input io_abort,
 output io_active,output reg io_done,
 input io_xLoadWen,input [2:0] io_xLoadRow,input io_xLoadSet,io_xRunSet,
 input [5:0] io_xLoadAddr,input [15:0] io_xLoadData,input io_xLoadPacked,
 input [15:0] io_xLoadDataHi,input io_wLoadWen,input [2:0] io_wLoadBank,
 input [10:0] io_wLoadAddr,input [15:0] io_wLoadData_0,io_wLoadData_1,io_wLoadData_2,io_wLoadData_3,
 input io_biasHostValid,output io_biasHostReady,input [7:0] io_biasHostAddr,
 input [39:0] io_biasHostData,output reg io_biasRspValid,output io_biasRspError,
 input io_clearValid,output io_clearReady,output reg io_clearDone,output io_clearing,
 output io_outValid,input io_outPop,output [4:0] io_outGroup,output [2:0] io_outRow,
 output [2:0] io_outColumn,
 output [47:0] io_outResult_0,io_outResult_1,io_outResult_2,io_outResult_3,
 output [47:0] io_outResult_4,io_outResult_5,io_outResult_6,io_outResult_7,
 output io_computeStart,io_weightRead,io_macStep,io_fifoFullWait,
 output io_clearWeightWrite,io_clearXWrite,io_clearResultWrite
);
 localparam WAIT=0, B0=1,B1=2,B2=3,BI=4,PRE=5,RUN=6,STORE=7;
 reg [3:0] state,validRows;
 reg active,runSet,clearing;
 reg [9:0] clearIndex;
 reg [5:0] produced,k,storeIndex;
 reg [2:0] biasLane,outRow,outColumn;
 reg [31:0] biasLow;
 reg head,tail,readHeld;
 reg [1:0] count;
 reg [4:0] tag0,tag1;
 reg [1:0] hostState;
 reg [7:0] hostAddr;
 reg [39:0] hostData;
 wire clearFire=io_clearValid&&io_clearReady;
 wire abortOrReset=reset||io_abort||clearFire;
 wire good=!reset&&!io_abort;
 wire [15:0] weightsQ[0:7],xQ[0:1][0:7];
 wire [47:0] macQ[0:7][0:7];
 wire biasRead=good&&active&&(state==B0||state==B1||state==B2);
 wire [9:0] biasLogical={2'b0,produced[4:0],biasLane};
 wire [9:0] biasReadAddr=(biasLogical<<1)+biasLogical+
   (state==B1?10'd1:state==B2?10'd2:10'd0);
 wire [15:0] biasQ;
 wire [9:0] biasHostBase=({2'b0,hostAddr}<<1)+{2'b0,hostAddr};
 wire biasHostWrite=good&&hostState!=0;
 wire [1:0] hostWord=hostState-1'b1;
 wire [15:0] biasHostWord=hostState==1?hostData[15:0]:
   hostState==2?hostData[31:16]:{8'b0,hostData[39:32]};
 wire [39:0] initBias={biasQ[7:0],biasLow};
 wire weightRen=good&&active&&(state==PRE||(state==RUN&&k!=63));
 wire [5:0] readK=state==PRE?6'd0:k+1'b1;
 wire [2:0] storeRow=storeIndex[5:3],storeColumn=storeIndex[2:0];
 wire [40:0] storeValue=macQ[storeRow][storeColumn][40:0];
 wire storeWrite=good&&active&&state==STORE&&!readHeld&&!clearing;
 wire enqueue=storeWrite&&({1'b0,storeRow}+1'b1==validRows)&&storeColumn==7;
 wire pop=io_outValid&&io_outPop;
 wire retire=pop&&outColumn==7&&({1'b0,outRow}+1'b1==validRows);
 wire resultRead=good&&!clearing&&count!=0&&!storeWrite;
 wire [9:0] resultAddress=clearing?clearIndex:storeWrite?
   {3'b0,tail,storeIndex}:{3'b0,head,outRow,outColumn};
 wire [47:0] resultD=clearing?48'd0:{7'b0,storeValue};
 wire [15:0] resultQ[0:2];
 wire [40:0] resultRaw={resultQ[2][8:0],resultQ[1],resultQ[0]};
 wire resultWrite=good&&(clearing||storeWrite);
 assign io_clearReady=good&&!active&&!clearing&&count==0&&hostState==0;
 assign io_biasHostReady=good&&!active&&!clearing&&!io_clearValid&&hostState==0;
 assign io_biasRspError=1'b0;
 assign io_active=active&&!io_abort;
 assign io_clearing=clearing&&!io_abort;
 assign io_outValid=good&&active&&count!=0&&readHeld;
 assign io_outGroup=head?tag1:tag0;
 assign io_outRow=outRow;
 assign io_outColumn=outColumn;
 assign io_outResult_0={{7{resultRaw[40]}},resultRaw};
 assign io_outResult_1=0; assign io_outResult_2=0; assign io_outResult_3=0;
 assign io_outResult_4=0; assign io_outResult_5=0; assign io_outResult_6=0; assign io_outResult_7=0;
 assign io_computeStart=good&&active&&state==PRE;
 assign io_weightRead=weightRen;
 assign io_macStep=good&&active&&state==RUN;
 assign io_fifoFullWait=good&&active&&state==WAIT&&produced<32&&count==2;
 assign io_clearWeightWrite=good&&clearing;
 assign io_clearXWrite=good&&clearing;
 assign io_clearResultWrite=good&&clearing;
 Sram1024x16 biasMemory(.clock(clock),.reset(reset),
   .io_en(good&&((clearing&&clearIndex<768)||biasHostWrite||biasRead)),
   .io_isWrite(clearing||biasHostWrite),
   .io_addr(clearing?clearIndex:biasHostWrite?biasHostBase+{8'b0,hostWord}:biasReadAddr),
   .io_wdata(clearing?16'b0:biasHostWord),.io_rdata(biasQ),.io_rvalid());
 TileWeightBankArray weights(.clock(clock),.reset(reset),
   .io_loadWen(io_wLoadWen&&!active&&!clearing&&!clearFire&&good),
   .io_loadBank(io_wLoadBank),.io_loadAddr(io_wLoadAddr),
   .io_loadData_0(io_wLoadData_0),.io_loadData_1(io_wLoadData_1),
   .io_loadData_2(io_wLoadData_2),.io_loadData_3(io_wLoadData_3),
   .io_clearWen(io_clearWeightWrite),.io_clearAddr(clearIndex),
   .io_ren(weightRen),.io_raddr({produced[4:0],readK}),
   .io_rdata_0(weightsQ[0]),.io_rdata_1(weightsQ[1]),.io_rdata_2(weightsQ[2]),
   .io_rdata_3(weightsQ[3]),.io_rdata_4(weightsQ[4]),.io_rdata_5(weightsQ[5]),
   .io_rdata_6(weightsQ[6]),.io_rdata_7(weightsQ[7]));
 genvar s,r,c;
 generate for(s=0;s<2;s=s+1)begin: xSets
   for(r=0;r<8;r=r+1)begin: rows
     TileXMacroRowBuffer memory(.clock(clock),.reset(reset),
       .io_wen(good&&(clearing||(io_xLoadWen&&io_xLoadSet==s&&io_xLoadRow==r&&(!active||io_xLoadSet!=runSet)))),
       .io_waddr(clearing?clearIndex:{4'b0,io_xLoadAddr}),
       .io_wdata(clearing?16'b0:io_xLoadData),.io_packed(io_xLoadPacked),.io_wdataHi(io_xLoadDataHi),
       .io_ren(weightRen&&runSet==s&&r<validRows),.io_raddr(readK),.io_rdata(xQ[s][r]),.io_rvalid());
   end
 end
 for(r=0;r<8;r=r+1)begin: rows
   for(c=0;c<8;c=c+1)begin: lanes
     MacPE_Acc41 pe(.clock(clock),.reset(abortOrReset),
       .io_init(good&&active&&state==BI&&biasLane==c&&r<validRows),
       .io_enable(io_macStep&&r<validRows),.io_x(xQ[runSet][r]),.io_w(weightsQ[c]),
       .io_bias(initBias),.io_result(macQ[r][c]));
   end
 end
 for(s=0;s<3;s=s+1)begin: resultSlices
   Sram1024x16 memory(.clock(clock),.reset(reset),
     .io_en(resultWrite||resultRead),.io_isWrite(resultWrite),.io_addr(resultAddress),
     .io_wdata(resultD[16*s+:16]),.io_rdata(resultQ[s]),.io_rvalid());
 end endgenerate
 always @(posedge clock)begin
   if(abortOrReset)begin
     state<=WAIT;active<=0;runSet<=0;validRows<=0;produced<=0;k<=0;storeIndex<=0;
     biasLane<=0;biasLow<=0;head<=0;tail<=0;count<=0;tag0<=0;tag1<=0;
     outRow<=0;outColumn<=0;readHeld<=0;hostState<=0;hostAddr<=0;hostData<=0;
     io_done<=0;io_clearDone<=0;io_biasRspValid<=0;clearing<=clearFire;clearIndex<=0;
   end else begin
     io_done<=0;io_clearDone<=0;io_biasRspValid<=0;
     if(clearing)begin
       if(clearIndex==1023)begin clearing<=0;io_clearDone<=1;end
       else clearIndex<=clearIndex+1'b1;
     end
     if(io_biasHostValid&&io_biasHostReady)begin
       hostState<=1;hostAddr<=io_biasHostAddr;hostData<=io_biasHostData;
     end else if(hostState!=0)begin
       if(hostState==3)begin hostState<=0;hostData<=0;hostAddr<=0;io_biasRspValid<=1;end
       else hostState<=hostState+1'b1;
     end
     if(io_start)begin
       active<=1;validRows<=io_validRows;runSet<=io_xRunSet;produced<=0;
       state<=WAIT;head<=0;tail<=0;count<=0;outRow<=0;outColumn<=0;readHeld<=0;
     end else begin
       case({enqueue,retire})
         2'b10:count<=count+1'b1;
         2'b01:count<=count-1'b1;
         default:;
       endcase
       if(resultRead)readHeld<=1;
       if(pop)begin
         readHeld<=0;
         if(outColumn==7)begin
           outColumn<=0;
           if(retire)begin outRow<=0;head<=!head;
             if(io_outGroup==31)begin active<=0;io_done<=1;end
           end else outRow<=outRow+1'b1;
         end else outColumn<=outColumn+1'b1;
       end
       if(active)case(state)
         WAIT:if(produced<32&&count<2)begin biasLane<=0;biasLow<=0;state<=B0;end
         B0:state<=B1;
         B1:begin biasLow[15:0]<=biasQ;state<=B2;end
         B2:begin biasLow[31:16]<=biasQ;state<=BI;end
         BI:if(biasLane==7)begin biasLow<=0;state<=PRE;end
            else begin biasLane<=biasLane+1'b1;state<=B0;end
         PRE:begin k<=0;state<=RUN;end
         RUN:if(k==63)begin storeIndex<=0;state<=STORE;end else k<=k+1'b1;
         STORE:if(storeWrite)begin
           if(enqueue)begin
             if(tail)tag1<=produced[4:0];else tag0<=produced[4:0];
             tail<=!tail;produced<=produced+1'b1;state<=WAIT;
           end else storeIndex<=storeIndex+1'b1;
         end
         default:state<=WAIT;
       endcase
     end
   end
 end
`ifndef SYNTHESIS
 always @(posedge clock)if(good)begin
   assert(count<=2)else $fatal(1,"result macro queue overflow");
   assert(!(resultWrite&&resultRead))else $fatal(1,"result macro port collision");
   if(io_start)begin
     assert(!active&&!clearing&&count==0&&hostState==0)else $fatal(1,"illegal START");
     assert(io_validRows>=1&&io_validRows<=8)else $fatal(1,"invalid tail rows");
   end
   if(io_outPop)assert(io_outValid)else $fatal(1,"POP before synchronous result read");
   if(storeWrite)assert(macQ[storeRow][storeColumn]=={{7{storeValue[40]}},storeValue})
     else $fatal(1,"raw MAC result exceeds signed41");
 end
`endif
endmodule
