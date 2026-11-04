`timescale 1ns/1fs
module tb_xu_soc_ppa;
 node0 dut();
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

module node4;
 accel u_accel_icb_slave();
endmodule
module node10;
 ff wrong_target();
endmodule
module node9;
 node10 vec_31_dfflr();
endmodule
module node8;
 node9 dp_gt0();
reg[1:0]vec_r=1;reg i_vld=0,i_rdy=1,o_vld=0,o_rdy=1;initial #9359390.05 vec_r=2'bxx;
endmodule
module node7;
 node8 u_sirv_gnrl_rsp_fifo();
endmodule
module node6;
 node7 u_sirv_gnrl_icb_buffer();
endmodule
module node5;
 node6 u_sirv_mem_fab();
endmodule
module node3;
 node4 u_e203_subsys_perips();
 node5 u_e203_subsys_mems();
endmodule
module node2;
 node3 u_e203_subsys_main();
endmodule
module node1;
 node2 u_e203_subsys_top();
endmodule
module node0;
 shared u_shared();
 node1 u_soc();
endmodule