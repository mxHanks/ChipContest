// Isolated P3 prototype. Instantiates the repository's REAL Sram1024x16 wrapper.
// No second storage model, behavioral shadow RAM, or combinational-Q assumption.
module bias_sram_prefetch (
  input wire clock, reset,
  input wire compute_active,
  input wire invalidate,
  input wire clear_valid,
  output wire clear_ready,
  output reg clear_done,
  input wire cmd_valid,
  output wire cmd_ready,
  input wire cmd_read,
  input wire [7:0] cmd_addr,
  input wire [39:0] cmd_wdata,
  input wire [4:0] cmd_wmask,
  output reg rsp_valid,
  input wire rsp_ready,
  output reg rsp_err,
  output reg [39:0] rsp_rdata,
  input wire group_req_valid,
  output wire group_req_ready,
  input wire [4:0] group_req_tag,
  output wire group_valid,
  output wire [4:0] group_tag,
  output wire [31:0] group_epoch,
  output wire [319:0] group_data,
  input wire group_take,
  output reg [31:0] epoch
);
  localparam IDLE=0, SELECT_WORD=1, READ_ISSUE=2, READ_CAPTURE=3,
             WRITE_COMMIT=4, CLEAR_WORD=5;
  localparam HOST_READ=0, HOST_WRITE=1, GROUP_FILL=2;
  reg [2:0] state;
  reg [1:0] owner;
  reg [7:0] host_addr;
  reg [39:0] host_data, host_read_data;
  reg [4:0] host_mask;
  reg [1:0] host_word;
  reg [15:0] write_word;
  reg [9:0] clear_addr;
  reg wanted_pending;
  reg [4:0] wanted_tag;
  reg [1:0] slot_valid;
  reg [4:0] slot_tag [0:1];
  reg [31:0] slot_epoch [0:1];
  reg [319:0] slot_data [0:1];
  reg fill_slot;
  reg [4:0] fill_tag, fill_word;
  reg [31:0] fill_epoch;
  reg last_grant_host;

  wire slot0_hit=slot_valid[0] && slot_tag[0]==wanted_tag && slot_epoch[0]==epoch;
  wire slot1_hit=slot_valid[1] && slot_tag[1]==wanted_tag && slot_epoch[1]==epoch;
  wire current_hit=slot0_hit || slot1_hit;
  wire next_hit=(slot_valid[0] && slot_tag[0]==wanted_tag+5'd1 && slot_epoch[0]==epoch) ||
                (slot_valid[1] && slot_tag[1]==wanted_tag+5'd1 && slot_epoch[1]==epoch);
  wire demand_missing=wanted_pending && !current_hit;
  wire prefetch_missing=wanted_pending && current_hit && wanted_tag!=31 && !next_hit;
  wire fill_needed=demand_missing || prefetch_missing;
  wire next_fill_slot=demand_missing ? (slot_valid[0] && !slot_valid[1]) : slot0_hit;
  wire [4:0] next_fill_tag=demand_missing ? wanted_tag : wanted_tag+5'd1;
  wire clear_fire=clear_valid && clear_ready;
  wire host_fire=cmd_valid && cmd_ready;
  wire group_fire=group_req_valid && group_req_ready;
  assign clear_ready=!reset && state==IDLE && !compute_active && !wanted_pending && !invalidate;
  assign cmd_ready=!reset && state==IDLE && (!rsp_valid || rsp_ready) && !clear_fire && !invalidate &&
                   (!fill_needed || !last_grant_host);
  assign group_req_ready=!reset && !wanted_pending && !clear_fire && !invalidate;
  assign group_valid=!reset && wanted_pending && current_hit && !invalidate && !clear_fire;
  assign group_tag=wanted_tag;
  assign group_epoch=epoch;
  assign group_data=slot0_hit ? slot_data[0] : slot_data[1];

  wire [1:0] word_mask=host_word==0 ? host_mask[1:0] :
                            host_word==1 ? host_mask[3:2] : {1'b0,host_mask[4]};
  wire [15:0] word_data=host_word==0 ? host_data[15:0] :
                              host_word==1 ? host_data[31:16] : {8'b0,host_data[39:32]};
  wire [15:0] byte_mask={{8{word_mask[1]}},{8{word_mask[0]}}};
  reg mem_en, mem_write;
  reg [9:0] mem_addr;
  reg [15:0] mem_wdata;
  wire [15:0] mem_rdata;
  // Existing generated wrapper: synchronous Q, no exposed rvalid. READ_CAPTURE
  // is the first edge after READ_ISSUE and the only place allowed to sample Q.
  Sram1024x16 storage (
    .clock(clock), .io_en(mem_en), .io_isWrite(mem_write),
    .io_addr(mem_addr), .io_wdata(mem_wdata), .io_rdata(mem_rdata)
  );
  always @* begin
    mem_en=0; mem_write=0; mem_addr=0; mem_wdata=0;
    if (!reset && state==READ_ISSUE) begin
      mem_en=1;
      mem_addr=owner==GROUP_FILL ? ({5'b0,fill_tag}*24+fill_word) :
                                  ({2'b0,host_addr}*3+host_word);
    end else if (!reset && state==WRITE_COMMIT) begin
      mem_en=1; mem_write=1;
      mem_addr={2'b0,host_addr}*3+host_word; mem_wdata=write_word;
    end else if (!reset && state==CLEAR_WORD) begin
      mem_en=1; mem_write=1; mem_addr=clear_addr; mem_wdata=0;
    end
  end

  integer lane;
  always @(posedge clock) begin
    if (reset) begin
      state<=IDLE; owner<=HOST_READ;
      rsp_valid<=0; rsp_err<=0; rsp_rdata<=0;
      clear_done<=0; clear_addr<=0;
      epoch<=0; slot_valid<=0; wanted_pending<=0; wanted_tag<=0;
      fill_slot<=0; fill_tag<=0; fill_word<=0; fill_epoch<=0;
      host_addr<=0; host_data<=0; host_mask<=0; host_word<=0;
      host_read_data<=0; write_word<=0; last_grant_host<=0;
      for (lane=0; lane<2; lane=lane+1) begin
        slot_tag[lane]<=0; slot_epoch[lane]<=0;
      end
      // SRAM and staging payloads deliberately have no reset muxes.
    end else begin
      clear_done<=0;
      if (rsp_valid && rsp_ready) rsp_valid<=0;
      if (group_fire) begin
        wanted_pending<=1; wanted_tag<=group_req_tag;
      end
      if (group_valid && group_take) begin
        wanted_pending<=0;
        if (slot0_hit) slot_valid[0]<=0;
        if (slot1_hit) slot_valid[1]<=0;
      end
      if (invalidate) begin
        epoch<=epoch+1; slot_valid<=0;
        // Keep an accepted demand alive; an old in-flight fill cannot publish
        // because its captured epoch no longer matches. Demand then retries.
      end
      case (state)
        IDLE: begin
          if (clear_fire) begin
            epoch<=epoch+1; slot_valid<=0; clear_addr<=0; state<=CLEAR_WORD;
          end else if (host_fire) begin
            last_grant_host<=1;
            if (!cmd_read && (compute_active || (group_valid && group_take))) begin
              rsp_valid<=1; rsp_err<=1; rsp_rdata<=0;
            end else begin
              owner<=cmd_read ? HOST_READ : HOST_WRITE;
              host_addr<=cmd_addr; host_data<=cmd_wdata; host_mask<=cmd_wmask;
              host_word<=0; host_read_data<=0; state<=SELECT_WORD;
              if (!cmd_read) begin epoch<=epoch+1; slot_valid<=0; end
            end
          end else if (fill_needed && !invalidate) begin
            last_grant_host<=0; owner<=GROUP_FILL;
            fill_slot<=next_fill_slot; fill_tag<=next_fill_tag;
            fill_word<=0; fill_epoch<=epoch;
            slot_valid[next_fill_slot]<=0; state<=READ_ISSUE;
          end
        end
        SELECT_WORD: begin
          if (owner==HOST_READ) state<=READ_ISSUE;
          else if (word_mask==0) begin
            if (host_word==2) begin
              rsp_valid<=1; rsp_err<=0; rsp_rdata<=0; state<=IDLE;
            end else host_word<=host_word+1;
          end else if (word_mask==3 || host_word==2) begin
            write_word<=word_data; state<=WRITE_COMMIT;
          end else state<=READ_ISSUE;
        end
        READ_ISSUE: state<=READ_CAPTURE;
        READ_CAPTURE: begin
          if (owner==GROUP_FILL) begin
            if (fill_epoch!=epoch || invalidate) state<=IDLE;
            else begin
              case (fill_word%3)
                0: slot_data[fill_slot][40*(fill_word/3)+:16]<=mem_rdata;
                1: slot_data[fill_slot][40*(fill_word/3)+16+:16]<=mem_rdata;
                2: slot_data[fill_slot][40*(fill_word/3)+32+:8]<=mem_rdata[7:0];
              endcase
              if (fill_word==23) begin
                slot_valid[fill_slot]<=1; slot_tag[fill_slot]<=fill_tag;
                slot_epoch[fill_slot]<=fill_epoch; state<=IDLE;
              end else begin fill_word<=fill_word+1; state<=READ_ISSUE; end
            end
          end else if (owner==HOST_READ) begin
            case (host_word)
              0: host_read_data[15:0]<=mem_rdata;
              1: host_read_data[31:16]<=mem_rdata;
              2: host_read_data[39:32]<=mem_rdata[7:0];
            endcase
            if (host_word==2) begin
              rsp_valid<=1; rsp_err<=0;
              rsp_rdata<={mem_rdata[7:0],host_read_data[31:0]}; state<=IDLE;
            end else begin host_word<=host_word+1; state<=SELECT_WORD; end
          end else begin
            write_word<=(mem_rdata & ~byte_mask) | (word_data & byte_mask);
            state<=WRITE_COMMIT;
          end
        end
        WRITE_COMMIT: begin
          if (host_word==2) begin
            rsp_valid<=1; rsp_err<=0; rsp_rdata<=0; state<=IDLE;
          end else begin host_word<=host_word+1; state<=SELECT_WORD; end
        end
        CLEAR_WORD: begin
          if (clear_addr==767) begin clear_done<=1; state<=IDLE; end
          else clear_addr<=clear_addr+1;
        end
        default: state<=IDLE;
      endcase
    end
  end
endmodule
