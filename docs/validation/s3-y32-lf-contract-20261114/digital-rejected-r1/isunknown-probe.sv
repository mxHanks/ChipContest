`timescale 1ns/1fs
module t;
reg a=0,b=1,c=0;
initial begin #0.000001;$display("%b %b %b unknownconcat=%b scalar=%b",a,b,c,$isunknown({a,b,c}),$isunknown(a));$finish;end
endmodule
