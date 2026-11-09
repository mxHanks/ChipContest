// Experimental bridge for LinearRowPairPrototype. This has no MMIO interface,
// capability register, CPU route or software lifecycle: fixture use only.
// Eight signed48 results convert through one RNE path in eight cycles. Snapshot
// metadata includes row identity; POP occurs only on the later commit handshake.
module rowpair_direct_bridge(
  input clk,input rst_n,input active,input head_valid,input [4:0] head_group,
  input head_second,input [383:0] head_result,output head_pop,
  input claim,output valid,input ready,output [255:0] payload,output [31:0] status,
  input commit,output commit_ready,output commit_err);
  localparam IDLE=0,CAPTURE=1,VALID=2,OWNED=3,DONE=4;
  reg [2:0] state,lane;reg [255:0] captured;reg [31:0] metadata;
  wire [31:0] live=32'hc0000000|({31'b0,head_second}<<11)|({27'b0,head_group}<<6)|
                   ({31'b0,head_valid}<<1)|{31'b0,active};
  function automatic [31:0] rne(input signed [47:0] value);
    reg signed [47:0] floor_value;reg [8:0] fraction;
    begin floor_value=value>>>9;fraction=value[8:0];
      rne=floor_value+((fraction>256)||((fraction==256)&&floor_value[0]));end
  endfunction
  assign valid=state==VALID;assign payload=captured;
  assign status=claim?metadata:live;assign commit_ready=state==OWNED;
  assign commit_err=!active||!head_valid||head_group!=metadata[10:6]||head_second!=metadata[11];
  assign head_pop=commit&&commit_ready&&!commit_err;
  always @(posedge clk or negedge rst_n)begin
    if(!rst_n)begin state<=IDLE;lane<=0;captured<=0;metadata<=0;end
    else if(!claim)state<=IDLE;
    else case(state)
      IDLE:begin metadata<=live&32'h7fffffff;lane<=0;state<=active&&head_valid?CAPTURE:VALID;end
      CAPTURE:begin
        if((^head_result[48*lane+:48])===1'bx||$signed(head_result[48*lane+:48]) < -48'sd618473193472||
           $signed(head_result[48*lane+:48])>48'sd618475290623)$fatal(1,"pair bridge unknown/range");
        captured[32*lane+:32]<=rne(head_result[48*lane+:48]);
        if(lane==7)state<=VALID;else lane<=lane+1'b1;
      end
      VALID:if(valid&&ready)state<=OWNED;
      OWNED:if(commit&&commit_ready)state<=DONE;
      DONE:begin end
      default:state<=IDLE;
    endcase
  end
endmodule
