`timescale 1ns/1ps
module tb_acc41;
reg clock=0,reset=0,io_init=0,io_enable=0;
reg signed [15:0] io_x=0,io_w=0;
reg signed [39:0] io_bias=0;
wire signed [47:0] result48,result41,result40;
MacPE48 full(.clock(clock),.reset(reset),.io_init(io_init),.io_enable(io_enable),.io_x(io_x),.io_w(io_w),.io_bias(io_bias),.io_result(result48));
MacPE41 narrow(.clock(clock),.reset(reset),.io_init(io_init),.io_enable(io_enable),.io_x(io_x),.io_w(io_w),.io_bias(io_bias),.io_result(result41));
MacPE40 too_small(.clock(clock),.reset(reset),.io_init(io_init),.io_enable(io_enable),.io_x(io_x),.io_w(io_w),.io_bias(io_bias),.io_result(result40));
longint signed expected=0;
integer checks=0,stalls=0,resets=0,inits=0,counterexamples=0,tiepos=0,tieneg=0;
integer prefixes[0:64];
reg [31:0] rng=32'h51a041ed;
integer mode,k,c;
longint signed xv,wv,bv;
function automatic [31:0] next_rng(input [31:0] value);
reg [31:0] a;
begin a=value^(value<<13); a=a^(a>>17); next_rng=a^(a<<5); end
endfunction
function automatic signed [31:0] actual_rne(input signed [47:0] value);
reg signed [47:0] floor_value;
begin
 floor_value=value>>>9;
 actual_rne=floor_value[31:0]+((value[8:0]>9'd256)||((value[8:0]==9'd256)&&floor_value[0]));
end
endfunction
function automatic signed [63:0] oracle_rne(input signed [63:0] value);
reg signed [63:0] magnitude,quotient,remainder;
begin
 magnitude=value<0 ? -value:value; quotient=magnitude/512; remainder=magnitude%512;
 if(remainder>256 || (remainder==256 && quotient%2==1)) quotient=quotient+1;
 oracle_rne=value<0 ? -quotient:quotient;
end
endfunction
task automatic edge_check(input bit rv,iv,ev,input longint signed x,w,b,input bit bounded41);
reg signed [39:0] wrapped40;
longint signed product;
begin
 reset=rv;io_init=iv;io_enable=ev;io_x=x;io_w=w;io_bias=b;
 if(rv) begin expected=0;resets=resets+1;end
 else if(iv) begin expected=b;inits=inits+1;end
 else if(ev) begin product=x*w;expected=expected+product;end
 else stalls=stalls+1;
 #5;clock=1;#1;
 if(result48!==expected[47:0]) $fatal(1,"48 prefix mismatch expected=%0d got=%0d",expected,result48);
 if(bounded41 && result41!==expected[47:0]) $fatal(1,"41 prefix mismatch expected=%0d got=%0d",expected,result41);
 wrapped40=expected[39:0];
 if(result40!=={{8{wrapped40[39]}},wrapped40}) $fatal(1,"40 modular mismatch");
 if(bounded41 && actual_rne(result41)!==oracle_rne(expected)) $fatal(1,"RNE mismatch expected=%0d",expected);
 if(result40!==result48) counterexamples=counterexamples+1;
 if(expected%512==256) tiepos=tiepos+1;
 if(expected%512==-256) tieneg=tieneg+1;
 checks=checks+1;
 #4;clock=0;
end
endtask
initial begin
 for(k=0;k<=64;k=k+1) prefixes[k]=0;
 edge_check(1,1,1,32767,32767,549755813887,1);
 // Every prefix 0..64 for both bias extremes and all four product corners,
 // mixed extrema, sign-changing cancellation, deterministic arbitrary values,
 // positive and negative nearest-even ties. Disabled edges preserve state.
 for(c=0;c<36;c=c+1) begin
  mode=c%9;
  case(c/9)
   0:bv=-549755813888;
   1:bv=549755813887;
   2:bv=(c%2 ? 768:256);
   default:bv=(c%2 ? -768:-256);
  endcase
  edge_check(0,1,1,-32768,-32768,bv,1); prefixes[0]=prefixes[0]+1;
  for(k=0;k<64;k=k+1) begin
   case(mode)
    0:begin xv=-32768;wv=-32768;end
    1:begin xv=-32768;wv=32767;end
    2:begin xv=32767;wv=-32768;end
    3:begin xv=32767;wv=32767;end
    4:begin xv=-32768;wv=k%2 ? -32768:32767;end
    5:begin xv=k%2 ? -32768:32767;wv=k%3 ? 32767:-32768;end
    6:begin rng=next_rng(rng);xv=$signed(rng[15:0]);rng=next_rng(rng);wv=$signed(rng[15:0]);end
    7:begin xv=0;wv=-32768;end
    default:begin xv=1;wv=k%2 ? -1:1;end
   endcase
   if(k%7==0) edge_check(0,0,0,-32768,32767,-549755813888,1);
   edge_check(0,0,1,xv,wv,0,1); prefixes[k+1]=prefixes[k+1]+1;
  end
  edge_check(0,0,0,32767,32767,549755813887,1);
 end
 // Concrete signed40 failure after ONE legal MAC.
 edge_check(0,1,0,0,0,549755813887,1);
 edge_check(0,0,1,1,1,0,1);
 if(result40!==-48'sd549755813888 || result41!==48'sd549755813888) $fatal(1,"40-bit counterexample missing");
 // Reset in mid accumulation and init while enable=1 override old state.
 edge_check(1,0,1,-32768,-32768,0,1);
 edge_check(0,1,1,32767,32767,-768,1);
 edge_check(0,0,1,1,0,0,1);
 edge_check(1,1,0,0,0,549755813887,1);
 // Default generic MacPE remains usable beyond the 64-product specialization.
 edge_check(0,1,0,0,0,549755813887,1);
 for(k=0;k<600;k=k+1) edge_check(0,0,1,-32768,-32768,0,k<64);
 edge_check(1,0,0,0,0,0,1);
 for(k=0;k<=64;k=k+1) if(prefixes[k]!=36) $fatal(1,"missing prefix %0d",k);
 if(counterexamples==0 || tiepos==0 || tieneg==0 || stalls==0 || inits==0 || resets==0) $fatal(1,"missing coverage");
 $display("ACC41_PREFIX_PASS checks=%0d scenarios=36 prefixes=65 signed40_mismatches=%0d stalls=%0d resets=%0d init_priority=%0d positive_ties=%0d negative_ties=%0d generic48_products=600",checks,counterexamples,stalls,resets,inits,tiepos,tieneg);
 $finish;
end
endmodule
