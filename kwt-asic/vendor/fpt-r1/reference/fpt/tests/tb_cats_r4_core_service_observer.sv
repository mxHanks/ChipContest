`timescale 1ns/1ps
module tb_cats_r4_core_service_observer;
    logic clk=0, rst_n=0, capture=0;
    always #5 clk=~clk;
    logic [3:0] job_start=0, row_release=0;
    logic [3:0][15:0] job_epoch='0, row_epoch='0;
    wire [63:0] cycles64, cycles4;
    wire [15:0] epoch64, epoch4;
    wire run64, done64, fault64, overflow64, valid64;
    wire run4, done4, fault4, overflow4, valid4;
    integer tick=0, scenarios=0, start_tick;
    logic [63:0] captured_cycles;
    logic [15:0] captured_epoch;
    logic captured_valid;
    always @(posedge clk) begin
        tick=tick+1;
        if (capture) begin
            captured_cycles <= cycles64;
            captured_epoch <= epoch64;
            captured_valid <= valid64;
        end
    end
    cats_r4_core_service_observer #(.ROWS_PER_CLUSTER(2)) dut64(
        .clk,.rst_n,.capture,.job_start,.row_release,.job_epoch,.row_epoch,
        .elapsed_cycles(cycles64),.epoch(epoch64),.running(run64),.finished(done64),
        .fault(fault64),.overflow(overflow64),.valid(valid64));
    cats_r4_core_service_observer #(.ROWS_PER_CLUSTER(2),.COUNTER_BITS(4)) dut4(
        .clk,.rst_n,.capture,.job_start,.row_release,.job_epoch,.row_epoch,
        .elapsed_cycles(cycles4),.epoch(epoch4),.running(run4),.finished(done4),
        .fault(fault4),.overflow(overflow4),.valid(valid4));

    task automatic step(input logic [3:0] starts, releases, input logic [15:0] e);
        @(negedge clk);
        job_start=starts; row_release=releases; capture=0;
        for (integer c=0;c<4;c=c+1) begin job_epoch[c]=e;row_epoch[c]=e;end
        @(posedge clk); #1;
    endtask
    task automatic take_snapshot;
        @(negedge clk);job_start=0;row_release=0;capture=1;
        @(posedge clk);#1;
        if (run64 || done64 || valid64 || fault64 || overflow64 || cycles64!=0)
            $fatal(1,"capture did not re-arm observer");
        @(negedge clk);capture=0;
    endtask
    task automatic normal(input logic [15:0] e);
        step(4'b0001,0,e);start_tick=tick;
        step(4'b1110,0,e);
        for (integer row=0;row<2;row=row+1)
            for (integer c=0;c<4;c=c+1) begin
                step(0,4'b0001<<c,e);
                if (!(row==1 && c==3) && valid64)
                    $fatal(1,"completed before every cluster released all rows");
            end
        if (!valid64 || run64 || !done64 || fault64 || overflow64 ||
            epoch64!=e || cycles64!=tick-start_tick)
            $fatal(1,"independent edge-span oracle mismatch");
    endtask
    initial begin
        #2;rst_n=1; #1;rst_n=0; #1;rst_n=1;
        if ($test$plusargs("completed_overflow_only")) begin
            step(4'b1111,0,16'd100);start_tick=tick;
            repeat(20) step(0,0,16'd100);
            for (integer row=0;row<2;row=row+1)
                for (integer c=0;c<4;c=c+1) step(0,4'b0001<<c,16'd100);
            if (!done64 || !valid64 || cycles64!=tick-start_tick ||
                !done4 || !overflow4 || valid4 || cycles4!=15)
                $fatal(1,"completed overflow qualification missing");
            $display("PASS CORE_SERVICE_COMPLETED_OVERFLOW cycles64=%0d",cycles64);
            $finish;
        end
        normal(16'd7);
        repeat(3) step(0,0,16'd7);
        if (!valid64 || cycles64!=9) $fatal(1,"completed metric not held");
        take_snapshot();
        if (!captured_valid || captured_epoch!=7 || captured_cycles!=9)
            $fatal(1,"snapshot did not sample pre-rearm payload");
        scenarios=scenarios+1;

        step(4'b1111,0,16'd8);
        step(0,4'b0001,16'd8);
        repeat(20) step(0,0,16'd8);
        if (!run64 || valid64 || !overflow4 || valid4 || cycles4!=15)
            $fatal(1,"partial completion/overflow invalidity missing");
        take_snapshot();
        if (captured_valid) $fatal(1,"aborted partial span claimed valid");
        scenarios=scenarios+1;

        step(4'b1111,0,16'd9);
        step(0,4'b0001,16'd10);
        if (!fault64 || valid64) $fatal(1,"wrong epoch accepted");
        take_snapshot();scenarios=scenarios+1;

        step(0,4'b0001,16'd10);
        if (!fault64 || valid64 || run64) $fatal(1,"orphan release accepted");
        take_snapshot();scenarios=scenarios+1;

        normal(16'd11);
        step(0,4'b0001,16'd11);
        if (!fault64 || valid64) $fatal(1,"extra release after finish accepted");
        take_snapshot();scenarios=scenarios+1;

        step(4'b1111,0,16'd12);
        step(0,4'b0011,16'd12);
        #2;rst_n=0;#1;
        if (run64 || done64 || valid64 || cycles64!=0) $fatal(1,"async reset failed");
        rst_n=1;scenarios=scenarios+1;

        normal(16'd13);take_snapshot();
        if (!captured_valid || captured_epoch!=13 || captured_cycles!=9)
            $fatal(1,"reset/retry retained prior transaction rows");
        scenarios=scenarios+1;
        $display("PASS CORE_SERVICE_OBSERVER scenarios=%0d clusters=4 rows_per_cluster=2",scenarios);
        $finish;
    end
    initial begin #10000;$fatal(1,"timeout");end
endmodule
