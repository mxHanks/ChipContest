`timescale 1ns/1ps
module tb_kwt_shared512_checked;
    reg clk=0,rst_n=0,cmd_valid=0,cmd_read=0,rsp_ready=0;
    reg [31:0] cmd_addr=0,cmd_wdata=0;
    reg [3:0] cmd_wmask=0;
    wire cmd_ready,rsp_valid,rsp_err;
    wire [31:0] rsp_rdata;
    integer checks=0;
    always #5 clk=~clk;
    kwt_shared512_checked_model dut (.*);
    task automatic transaction(input bit read_op,input [31:0] address,input [31:0] data,
                               input [3:0] mask,input bit expected_error,input [31:0] expected);
        integer wait_cycles;
        reg [31:0] held;
        reg held_err;
        @(negedge clk); cmd_valid=1;cmd_read=read_op;cmd_addr=address;cmd_wdata=data;cmd_wmask=mask;
        wait_cycles=0;
        while(!cmd_ready && wait_cycles<30) begin @(negedge clk);wait_cycles=wait_cycles+1;end
        if(!cmd_ready) $fatal(1,"SHARED command timeout");
        @(posedge clk); #1;
        @(negedge clk);cmd_valid=0;
        wait_cycles=0;
        while(!rsp_valid && wait_cycles<30) begin @(negedge clk);wait_cycles=wait_cycles+1;end
        if(!rsp_valid || rsp_err !== expected_error) $fatal(1,"SHARED response error address=%h",address);
        if(read_op && !expected_error && rsp_rdata !== expected) $fatal(1,"SHARED read mismatch address=%h expected=%h actual=%h",address,expected,rsp_rdata);
        held=rsp_rdata;held_err=rsp_err;
        repeat(3) begin
            @(posedge clk); #1;
            if(rsp_valid!==1 || rsp_rdata!==held || rsp_err!==held_err || cmd_ready!==0)
                $fatal(1,"SHARED response not stable under backpressure");
        end
        @(negedge clk);rsp_ready=1;
        @(negedge clk);rsp_ready=0;
        checks=checks+1;
    endtask
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        transaction(0,32'ha0000000,32'h12345678,4'hf,0,0);
        transaction(1,32'ha0000000,0,0,0,32'h12345678); // read mask ignored
        transaction(0,32'ha0000000,32'hcafebabe,4'h3,0,0);
        transaction(1,32'ha0000000,0,4'hf,0,32'h1234babe);
        transaction(0,32'ha0000000,32'habcd0000,4'hc,0,0);
        transaction(1,32'ha0000000,0,4'hf,0,32'habcdbabe);
        transaction(0,32'ha007fffc,32'h87654321,4'hf,0,0);
        transaction(1,32'ha007fffc,0,4'hf,0,32'h87654321);
        // Regression for the original false-success halfword request.
        transaction(0,32'ha0000002,32'hffffffff,4'h3,1,0);
        transaction(1,32'ha0000002,0,4'h3,1,0);
        transaction(0,32'ha0000001,32'hffffffff,4'h1,1,0);
        transaction(0,32'ha0000000,32'hffffffff,4'h5,1,0);
        transaction(1,32'ha0080000,0,4'hf,1,0);
        transaction(1,32'ha0000000,0,4'hf,0,32'habcdbabe);
        @(negedge clk);rst_n=0;
        @(negedge clk);rst_n=1;
        transaction(1,32'ha007fffc,0,4'hf,0,32'h87654321);
        $display("PASS KWT_SHARED512_CHECKED checks=%0d",checks);
        $finish;
    end
endmodule
