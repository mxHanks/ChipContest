`timescale 1ns/1ps
// Development-only 512 KiB shared SRAM transaction model. Not a macro model,
// not in the accelerator synthesis file list, and never zero-power evidence.
module kwt_shared512_model (
    input logic clk, rst_n,
    input logic cmd_valid, output logic cmd_ready,
    input logic [31:0] cmd_addr, input logic cmd_read,
    input logic [31:0] cmd_wdata, input logic [3:0] cmd_wmask,
    output logic rsp_valid, input logic rsp_ready,
    output logic rsp_err, output logic [31:0] rsp_rdata
);
    logic [31:0] memory [0:131071];
    logic pending;
    logic [2:0] delay_count;
    logic [31:0] pending_data;
    logic pending_err;
    assign cmd_ready = rst_n && !pending && !rsp_valid;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pending<=0; rsp_valid<=0; rsp_err<=0; rsp_rdata<=0; delay_count<=0;
        end else begin
            if (rsp_valid && rsp_ready) rsp_valid<=0;
            if (pending) begin
                if (delay_count==0) begin
                    pending<=0; rsp_valid<=1; rsp_err<=pending_err; rsp_rdata<=pending_data;
                end else delay_count<=delay_count-1'b1;
            end
            if (cmd_valid && cmd_ready) begin
                pending<=1;
                delay_count <= {1'b0,cmd_addr[3:2]};
                pending_err <= cmd_addr[31:19] != 13'h1400 || ((cmd_wmask==4'hf) && cmd_addr[1:0]!=0) || ((cmd_wmask==4'h3) && cmd_addr[0]!=0) || ((cmd_wmask==4'hc) && cmd_addr[0]!=0) || ((cmd_wmask!=4'hf) && (cmd_wmask!=4'h3) && (cmd_wmask!=4'hc) && (cmd_wmask!=4'h1) && (cmd_wmask!=4'h2) && (cmd_wmask!=4'h4) && (cmd_wmask!=4'h8));
                pending_data <= 0;
                if (cmd_addr[31:19]==13'h1400 && cmd_addr[1:0]==0) begin
                    // ICB read data is the complete aligned 32-bit word;
                    // the E203 LSU selects the addressed byte/halfword from
                    // the returned word using its command address.
                    if (cmd_read) pending_data<=memory[cmd_addr[18:2]];
                    else for(integer b=0;b<4;b=b+1)
                        if(cmd_wmask[b]) memory[cmd_addr[18:2]][b*8+:8]<=cmd_wdata[b*8+:8];
                end
            end
        end
    end
endmodule
