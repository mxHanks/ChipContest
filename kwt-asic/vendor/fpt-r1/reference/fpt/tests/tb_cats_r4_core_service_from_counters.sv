`timescale 1ns/1ps
module tb_cats_r4_core_service_from_counters;
    logic clk=0, rst_n=0, capture=0;
    always #5 clk=~clk;
    logic [3:0][63:0] job_count='0, context_words='0;
    logic [3:0][15:0] core_epoch='0;
    logic registered_mode=0;
    logic [3:0] qk_valid=0, qk_ready=0, pv_valid=0, pv_ready=0;
    wire [3:0] qk_fire=qk_valid & qk_ready, pv_fire=pv_valid & pv_ready;
    logic [3:0][63:0] registered_jobs='0, registered_words='0;
    wire [3:0][63:0] dut_jobs=registered_mode ? registered_jobs : job_count;
    wire [3:0][63:0] dut_words=registered_mode ? registered_words : context_words;
    wire [63:0] elapsed_cycles;
    wire [15:0] epoch;
    wire running, finished, fault, overflow, valid;
    integer tick=0, start_tick, scenarios=0;
    integer first_job_tick=-1, last_word_tick=-1;
    logic captured_valid;
    logic [63:0] captured_cycles;
    logic [15:0] captured_epoch;
    always @(posedge clk) begin
        tick=tick+1;
        if(registered_mode) begin
            if(first_job_tick<0 && (|qk_fire)) first_job_tick=tick;
            if(|pv_fire) last_word_tick=tick;
        end
        if (capture) begin
            captured_valid <= valid;
            captured_cycles <= elapsed_cycles;
            captured_epoch <= epoch;
        end
    end
    // Producer counter-register doubles match the actual QK/PV accepted-event
    // updates. The independent span oracle uses handshake edges before these
    // NBA updates, not the observer's counters or row-completion conditions.
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            registered_jobs <= '0;
            registered_words <= '0;
        end else if(registered_mode) begin
            for(integer c=0;c<4;c=c+1) begin
                if(qk_fire[c]) registered_jobs[c] <= registered_jobs[c]+1;
                if(pv_fire[c]) registered_words[c] <= registered_words[c]+32;
            end
        end
    end
    cats_r4_core_service_from_counters #(.ROWS_PER_CLUSTER(2)) dut(
        .clk,.rst_n,.capture,.job_count(dut_jobs),.context_words(dut_words),.core_epoch,
        .elapsed_cycles,.epoch,.running,.finished,.fault,.overflow,.valid);

    task automatic start(input logic [3:0] mask, input logic [15:0] e,
                         input integer increment);
        @(negedge clk);
        for(integer c=0;c<4;c=c+1) begin
            core_epoch[c]=e;
            if(mask[c]) job_count[c]=job_count[c]+increment;
        end
        @(posedge clk);#1;
    endtask
    task automatic words(input logic [3:0] mask);
        @(negedge clk);
        for(integer c=0;c<4;c=c+1)
            if(mask[c]) context_words[c]=context_words[c]+32;
        @(posedge clk);#1;
    endtask
    task automatic idle_step;
        @(negedge clk);@(posedge clk);#1;
    endtask
    task automatic producer_step(input logic [3:0] jv, jr, pv, pr);
        @(negedge clk);qk_valid=jv;qk_ready=jr;pv_valid=pv;pv_ready=pr;
        @(posedge clk);#1;
    endtask
    task automatic take_snapshot;
        @(negedge clk);capture=1;
        @(posedge clk);#1;
        if (valid || finished || running || fault || overflow || elapsed_cycles!=0)
            $fatal(1,"counter adapter capture did not re-arm");
        @(negedge clk);capture=0;
    endtask
    task automatic full_words;
        for(integer transfer=1;transfer<=8;transfer=transfer+1) begin
            words(4'b1111);
            if(transfer<8 && valid)
                $fatal(1,"completed before eight fresh transfers per cluster");
        end
        if(!valid || !finished || running || fault || overflow ||
           elapsed_cycles!=tick-start_tick)
            $fatal(1,"counter adapter independent span mismatch");
    endtask
    initial begin
        #2;rst_n=1;#1;rst_n=0;#1;rst_n=1;
        if($test$plusargs("registered_producers_only")) begin
            registered_mode=1;
            for(integer c=0;c<4;c=c+1) core_epoch[c]=16'd300;
            producer_step(4'b0001,4'b1111,0,0);
            if(running || valid) $fatal(1,"counter observation started without its register delay");
            producer_step(0,0,0,0);
            if(!running || epoch!=300 || fault)
                $fatal(1,"registered QK event not observed one edge later");
            producer_step(4'b1110,4'b1111,0,0);
            for(integer transfer=1;transfer<=8;transfer=transfer+1) begin
                producer_step(0,0,4'b1111,0);
                if(valid) $fatal(1,"backpressured PV output counted as completion");
                producer_step(0,0,4'b1111,4'b1111);
                if(valid) $fatal(1,"registered final PV count observed without its delay");
            end
            producer_step(0,0,0,0);
            if(!valid || running || fault || overflow ||
               elapsed_cycles!=last_word_tick-first_job_tick)
                $fatal(1,"registered counter delay changed handshake span");
            take_snapshot();
            if(!captured_valid || captured_epoch!=300 ||
               captured_cycles!=last_word_tick-first_job_tick)
                $fatal(1,"registered span capture lost completed metric");
            $display("PASS CORE_SERVICE_REGISTERED_PRODUCERS delayed_edges=1 source_span=%0d captured=%0d",
                     last_word_tick-first_job_tick,captured_cycles);
            $finish;
        end

        // An aborted transaction leaves 32/64/96/160 lifetime words. Each next
        // transaction still needs eight NEW transfers per child, not abs%128.
        start(4'b1111,16'd100,1);
        for(integer chunk=0;chunk<5;chunk=chunk+1) begin
            case(chunk)
                0: words(4'b1111);
                1: words(4'b1110);
                2: words(4'b1100);
                default: words(4'b1000);
            endcase
        end
        if(valid || finished || fault || context_words[0]!=32 ||
           context_words[1]!=64 || context_words[2]!=96 || context_words[3]!=160)
            $fatal(1,"partial counter residue setup mismatch");
        take_snapshot();
        if(captured_valid) $fatal(1,"partial transaction snapshot claimed valid");
        start(4'b1111,16'd101,1);start_tick=tick;
        full_words();
        if(elapsed_cycles!=8) $fatal(1,"fresh transfer span is not eight edges");
        repeat(2) idle_step();
        if(!valid || elapsed_cycles!=8) $fatal(1,"completed counter metric changed");
        take_snapshot();
        if(!captured_valid || captured_cycles!=8 || captured_epoch!=101)
            $fatal(1,"counter metric pre-rearm capture mismatch");
        scenarios=scenarios+1;

        start(4'b1111,16'd102,1);words(4'b1111);
        @(negedge clk);context_words[0]=0;
        @(posedge clk);#1;
        if(!fault || valid) $fatal(1,"active counter decrease accepted");
        take_snapshot();scenarios=scenarios+1;

        start(4'b1111,16'd103,1);
        @(negedge clk);core_epoch[1]=16'd203;context_words[1]=context_words[1]+32;
        @(posedge clk);#1;
        if(!fault || valid) $fatal(1,"sub-row wrong epoch accepted");
        take_snapshot();scenarios=scenarios+1;

        start(4'b0001,16'd104,2);
        if(!fault || valid) $fatal(1,"multi-job counter jump accepted");
        take_snapshot();scenarios=scenarios+1;

        start(4'b1111,16'd105,1);start_tick=tick;full_words();
        words(4'b0001);
        if(!fault || valid || !finished)
            $fatal(1,"extra sub-row words after finish accepted");
        take_snapshot();scenarios=scenarios+1;

        start(4'b0001,16'd106,1);words(4'b0010);
        if(!fault || valid) $fatal(1,"words from child without QK start accepted");
        take_snapshot();scenarios=scenarios+1;

        @(negedge clk);job_count='0;context_words='0;
        @(posedge clk);#1;
        if(fault || valid) $fatal(1,"idle producer clear rejected");
        start(4'b0001,16'd107,1);start_tick=tick;
        repeat(2) idle_step();
        start(4'b1110,16'd107,1);full_words();
        if(elapsed_cycles!=11) $fatal(1,"late child start restarted elapsed span");
        take_snapshot();scenarios=scenarios+1;

        start(4'b1111,16'd108,1);words(4'b0011);
        #2;rst_n=0;job_count='0;context_words='0;core_epoch='0;#1;
        if(valid || finished || running || fault || elapsed_cycles!=0)
            $fatal(1,"counter adapter async reset failed");
        rst_n=1;
        start(4'b1111,16'd109,1);start_tick=tick;full_words();
        take_snapshot();scenarios=scenarios+1;

        start(4'b1111,16'd110,1);
        @(negedge clk);context_words[0]=context_words[0]+64;
        @(posedge clk);#1;
        if(!fault || valid) $fatal(1,"impossible double PV transfer accepted");
        take_snapshot();scenarios=scenarios+1;

        $display("PASS CORE_SERVICE_COUNTER_ADAPTER scenarios=%0d clusters=4 rows_per_cluster=2",scenarios);
        $finish;
    end
    initial begin #20000;$fatal(1,"timeout");end
endmodule
