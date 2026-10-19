`timescale 1ns/1ps
module tb_cats_r4_b3_fp32_reference;
    logic clk=0, rst_n=0;
    always #5 clk=~clk;
    logic a_valid=0,b_valid=0,result_ready=0;
    logic mul_a_ready,mul_b_ready,add_a_ready,add_b_ready,mul_valid,add_valid;
    logic [31:0] a_data,b_data,mul_data,add_data,want_mul,want_add;
    fp32_mul_ip m(.clk,.rst_n,.a_valid,.a_ready(mul_a_ready),.a_data,
        .b_valid,.b_ready(mul_b_ready),.b_data,.result_valid(mul_valid),
        .result_ready,.result_data(mul_data));
    fp32_add_ip a(.clk,.rst_n,.a_valid,.a_ready(add_a_ready),.a_data,
        .b_valid,.b_ready(add_b_ready),.b_data,.result_valid(add_valid),
        .result_ready,.result_data(add_data));
    integer fd,rc,count=0;
    string vector_path;
    task check_result;
        begin
            if (!mul_valid || !add_valid || mul_data !== want_mul || add_data !== want_add)
                $fatal(1,"FP32 vector=%0d a=%h b=%h mul=%h/%h add=%h/%h",
                    count,a_data,b_data,mul_data,want_mul,add_data,want_add);
        end
    endtask
    initial begin
        if (!$value$plusargs("VECTORS=%s",vector_path)) $fatal(1,"missing vectors");
        fd=$fopen(vector_path,"r");
        if (!fd) $fatal(1,"cannot read vectors");
        repeat(3) @(negedge clk);
        rst_n=1;
        while (!$feof(fd)) begin
            rc=$fscanf(fd,"%h %h %h %h\n",a_data,b_data,want_mul,want_add);
            if (rc != 4) $fatal(1,"malformed vector");
            if (!(mul_a_ready && mul_b_ready && add_a_ready && add_b_ready))
                $fatal(1,"model did not rearm");
            a_valid=1; b_valid=1; result_ready=0;
            @(negedge clk);
            a_valid=0; b_valid=0;
            check_result();
            repeat(2) begin
                @(negedge clk);
                check_result();
                if (mul_a_ready || add_a_ready) $fatal(1,"backpressure lost");
            end
            result_ready=1;
            @(negedge clk);
            result_ready=0;
            count=count+1;
        end
        $fclose(fd);
        $display("PASS FP32 reference vectors=%0d operations=%0d with stalled outputs",count,2*count);
        $finish;
    end
endmodule
