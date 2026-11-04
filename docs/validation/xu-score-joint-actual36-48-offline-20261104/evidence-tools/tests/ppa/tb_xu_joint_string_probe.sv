// xu dynamic-expression, materialized-variable and literal argument diagnostic.
`timescale 1ns/1fs
module tb_xu_joint_string_probe;
integer cycles=1403985,request_cycle=2394640;
reg [31:0] addr=32'ha00517fc;
string source_identity,final_identity;
initial begin
  source_identity=$sformatf("source_request cycle=%0d addr=%08h read=1 valid=1 accept=%b",cycles,32'ha0000000,1'b1);
  final_identity=$sformatf("final_y_retire cycle=%0d request_cycle=%0d addr=%08h response_valid=1 response_ready=1 writes=50688",2394641,request_cycle,addr);
`define XU_STRING_CASES(B,E) \
    B(10,"task-joint",$sformatf("source_request cycle=%0d addr=%08h read=1 valid=1 accept=%b",cycles,32'ha0000000,1'b1)); \
    B(11,"task-joint",source_identity); \
    B(12,"task-joint","literal-source-identity"); \
    E(20,$sformatf("final_y_retire cycle=%0d request_cycle=%0d addr=%08h response_valid=1 response_ready=1 writes=50688",2394641,request_cycle,addr)); \
    E(21,final_identity); \
    E(22,"literal-final-identity"); \
    #1;
  `XU_STRING_CASES($xu_joint_string_seq,$xu_joint_end_seq)
  `XU_STRING_CASES($xu_joint_string_handles,$xu_joint_end_handles)
  `XU_STRING_CASES($xu_joint_string_reverse,$xu_joint_end_reverse)
`undef XU_STRING_CASES
  $xu_joint_string_done();$finish;
end
endmodule
