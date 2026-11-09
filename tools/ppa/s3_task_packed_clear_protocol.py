#!/usr/bin/env python3
"""Generate an optional public PACK32 physical clearing candidate, TASKS=1.

The frozen main and existing payload observers are not edited. This helper is
not a qualification result; see s3_task_clear_protocol.md for integration.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re


_LEGACY_PATH = Path(__file__).with_name('xu_task_clear_protocol.py')
_SPEC = importlib.util.spec_from_file_location('_s3_legacy_clear', _LEGACY_PATH)
_LEGACY = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LEGACY)
sha = _LEGACY.sha

CLEAR_COUNTS = {
    'sram': dict(w=16384, x=64, legacy_bias=8, bias_clear_commands=1,
                 bias_clear_words=768, bias_staging_bits=640,
                 accepted_writes=8252, accepted_reads=8, accepted_commands=8260, cache_disable_writes=1,
                 initial_abi_reads=6, completion_proof_reads=2, w_packed_commands=8192,
                 x_packed_commands=32, w_cursor_writes=1, x_cursor_writes=1),
    'registers': dict(w=16384, x=64, legacy_bias=8, bias_entries=256,
                     bias_clear_commands=0, accepted_writes=9019, accepted_reads=8, accepted_commands=9027,
                     cache_disable_writes=1, initial_abi_reads=6,
                     completion_proof_reads=2, w_packed_commands=8192, x_packed_commands=32,
                     w_cursor_writes=1, x_cursor_writes=1),
}


def firmware_wrapper(main, expected_sha256):
    # Reuse the original helper's strict hash/path validation, without changing
    # its historical recipe or treating it as S3 qualification evidence.
    _LEGACY.firmware_wrapper(main, expected_sha256)
    main = Path(main).resolve()
    return r'''/* S3 public PACK32 separate clear candidate; frozen main SHA256: @MAIN_SHA@ */
#define main s3_frozen_task_main
#include "@MAIN_PATH@"
#undef main

/* No task X/W/bias source is read. Every store uses public 32-bit MMIO. */
static int s3_clear_task_data_and_parameters(void) {
    volatile uint32_t *const reg = (volatile uint32_t *)0x10042000u;
    volatile uint32_t *const host = (volatile uint32_t *)0xa007f000u;
    /* The host descriptor is control, not task input. Reject continuous runs. */
    if (host[0] != 1u) return -1;
    if (reg[0x000 / 4] != 0xacce2030u ||
        reg[0x050 / 4] != 0x58550003u || reg[0x00c / 4] != 0u) return -2;
    const uint32_t bias_capability = reg[0x0ec / 4];
    if (bias_capability != 0u && bias_capability != 0x42530001u) return -3;
    if (reg[0x070 / 4] != 0x58530003u ||
        reg[0x074 / 4] != 0x58500003u) return -4;
    reg[0x040 / 4] = 0u;
    reg[0x054 / 4] = 0u;
    for (unsigned pair = 0; pair < 8192; ++pair)
        reg[0x05c / 4] = 0u;
    if (bias_capability == 0x42530001u) {
        /* ICB completion is withheld until all 768 physical writes finish. */
        reg[0x0e8 / 4] = 1u;
    } else {
        for (unsigned column = 0; column < 256; ++column) {
            reg[0x044 / 4] = column;
            reg[0x048 / 4] = 0u;
            reg[0x04c / 4] = 0u;
        }
    }
    for (unsigned lane = 0; lane < 8; ++lane) {
        reg[0x028 / 4] = lane;
        reg[0x02c / 4] = 0u;
        reg[0x030 / 4] = 0u;
    }
    reg[0x060 / 4] = 0u;
    for (unsigned pair = 0; pair < 32; ++pair)
        reg[0x068 / 4] = 0u;
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    /* Explicit completion proof separates clear from frozen-main ABI reads. */
    if (reg[0x06c / 4] != 0u) return -5;
    if (reg[0x00c / 4] != 0u) return -6;
    return 0;
}

int main(void) {
    if (s3_clear_task_data_and_parameters()) return 17;
    return s3_frozen_task_main();
}
'''.replace('@MAIN_SHA@', expected_sha256).replace('@MAIN_PATH@', str(main))


def observer_declarations(accel='`ACCEL', use_bias_sram=True):
    """Passive declarations; call once/edge before original payload observers.

    first_source_request is VALID/address/read, NOT valid && ready. nice_idle
    must observe the real NICE owner, command, response and completion paths.
    The caller separately enforces fresh reset and TASKS=1, and retains all
    original payload checks. This observer drives no DUT input or memory.
    """
    if not re.fullmatch(r'(?:`?[A-Za-z_][A-Za-z0-9_$]*)(?:\.[A-Za-z_][A-Za-z0-9_$]*)*', accel):
        raise ValueError('invalid observed accelerator hierarchy')
    physical = physical_observer_declarations(accel, use_bias_sram)
    return r'''
  // Public PACK32 passive physical-clear proof. No force, DUT assignment, or task-data preloading.
  integer s3_clear_ticks=0, s3_clear_first=-1, s3_clear_last_response=-1;
  integer s3_clear_writes=0, s3_clear_commands=0, s3_clear_responses=0;
  integer s3_clear_w_count=0, s3_clear_x_count=0, s3_clear_legacy_count=0;
  integer s3_clear_bias_count=0, s3_clear_disable_count=0, s3_clear_reads=0;
  integer s3_clear_w_addr_count=0, s3_clear_x_addr_count=0;
  integer s3_clear_legacy_addr_count=0, s3_clear_bias_addr_count=0;
  integer s3_clear_sram_commands=0, s3_clear_sram_done=0, s3_clear_sram_start=-1;
  integer s3_clear_proof_reads=0, s3_preflight_commands=0, s3_preflight_responses=0;
  integer s3_clear_w_packs=0, s3_clear_x_packs=0, s3_clear_stream_proofs=0;
  reg s3_clear_stream_verified=0;
@PHYSICAL_DECLARATIONS@
  reg [16383:0] s3_clear_w_seen=0;
  reg [63:0] s3_clear_x_seen=0;
  reg [7:0] s3_clear_bank_seen=0;
  reg [4:0] s3_clear_bias_seen [0:255];
  reg [4:0] s3_clear_legacy_seen [0:7];
  reg [5:0] s3_clear_read_seen=0;
  reg s3_clear_complete=0, s3_clear_pending=0, s3_clear_pending_read=0;
  reg [11:0] s3_clear_response_address=0;
  reg s3_clear_cap_seen=0, s3_clear_is_sram=0;
  reg s3_clear_verified=0, s3_clear_pending_proof=0, s3_clear_pending_preflight=0;
  reg s3_clear_held_response=0, s3_clear_held_error=0;
  reg [31:0] s3_clear_held_data=0;
  integer s3_clear_init;
  initial begin
    for (s3_clear_init=0;s3_clear_init<256;s3_clear_init=s3_clear_init+1)
      s3_clear_bias_seen[s3_clear_init]=0;
    for (s3_clear_init=0;s3_clear_init<8;s3_clear_init=s3_clear_init+1)
      s3_clear_legacy_seen[s3_clear_init]=0;
  end

  task s3_require_clear_coverage;
    integer expected_writes;
    begin
      expected_writes=s3_clear_is_sram ? 8252 : 9019;
      if (!s3_clear_cap_seen || s3_clear_read_seen!==6'h3f ||
          s3_clear_writes!=expected_writes || s3_clear_disable_count!=1 ||
          s3_clear_w_count!=16384 || s3_clear_x_count!=64 || s3_clear_legacy_count!=8 ||
          s3_clear_bank_seen!==8'hff || s3_clear_w_addr_count!=1 ||
          s3_clear_x_addr_count!=1 || s3_clear_w_packs!=8192 || s3_clear_x_packs!=32 || s3_clear_legacy_addr_count!=8 ||
          (s3_clear_is_sram && (s3_clear_sram_commands!=1 ||
            s3_clear_sram_done!=1 || s3_clear_bias_count!=0 || s3_clear_bias_addr_count!=0)) ||
          (!s3_clear_is_sram && (s3_clear_bias_count!=256 ||
            s3_clear_bias_addr_count!=256 || s3_clear_sram_commands!=0 || s3_clear_sram_done!=0)))
        $fatal(1,"S3_CLEAR_REJECT incomplete clear before first source request");
      s3_require_physical_clear_coverage();
    end
  endtask

  task s3_observe_task_clear;
    input first_source_request;
    input nice_idle;
    output payload_phase;
    integer a, read_index;
    reg [4:0] old_mask, new_mask;
    begin
      s3_clear_ticks=s3_clear_ticks+1;
      if (!s3_clear_complete) begin
        if (first_source_request!==1'b0 && first_source_request!==1'b1)
          $fatal(1,"S3_CLEAR_REJECT unknown source-request predicate");
        if (nice_idle!==1'b1)
          $fatal(1,"S3_CLEAR_REJECT NICE not idle before task request");
        if (@ACCEL@.cache_enable!==1'b0 || @ACCEL@.busy!==1'b0 ||
            @ACCEL@.core_start!==1'b0 || @ACCEL@.row_count!==0)
          $fatal(1,"S3_CLEAR_REJECT non-idle/enabled clear phase");

        // Check BEFORE consuming anything on this edge. A simultaneous pending
        // write or response is not proof of clear before the first request.
        if (first_source_request) begin
          if (s3_clear_pending || s3_clear_commands!=s3_clear_responses ||
              s3_preflight_commands!=s3_preflight_responses ||
              @ACCEL@.rsp_valid!==1'b0 || @ACCEL@.cmd_valid!==1'b0 ||
              @ACCEL@.cache_pending!==1'b0 || @ACCEL@.stream_pending!==1'b0 ||
              @ACCEL@.cache_idle!==1'b1 || @ACCEL@.w_load_wen!==1'b0 ||
              @ACCEL@.x_load_wen!==1'b0 ||
              @ACCEL@.u_linear_compute_core.io_wLoadWen!==1'b0 ||
              @ACCEL@.u_linear_compute_core.io_xLoadWen!==1'b0)
            $fatal(1,"S3_CLEAR_REJECT undrained clear before first source request");
          s3_require_clear_coverage();
          if (!s3_clear_verified || s3_clear_proof_reads!=1 || s3_clear_reads!=8 ||
              s3_clear_stream_proofs!=1 || !s3_clear_stream_verified)
            $fatal(1,"S3_CLEAR_REJECT missing clear completion proof before first source request");
          s3_clear_complete=1;
          $display("S3_TASK_CLEAR_OBSERVED mode_sram=%0d writes=%0d reads=%0d w=16384 x=64 legacy_bias=8 bias_entries=%0d physical_w=%0d physical_x=%0d physical_bias=%0d w_packs=%0d x_packs=%0d sram_clear_commands=%0d sram_done=%0d commands=%0d responses=%0d clear_cycles=%0d response_end_cycle=%0d gap_to_source_request=%0d preflight_commands=%0d preflight_responses=%0d nice_idle=1 fifo_payload_physical_zero=UNPROVEN policy=REVIEW_PENDING clear_transport=public-pack32",
            s3_clear_is_sram,s3_clear_writes,s3_clear_reads,s3_clear_bias_count,
            s3_physical_w_count,s3_clear_x_count,s3_physical_bias_count,
            s3_clear_w_packs,s3_clear_x_packs,s3_clear_sram_commands,s3_clear_sram_done,s3_clear_commands,s3_clear_responses,
            s3_clear_last_response-s3_clear_first+1,s3_clear_last_response,
            s3_clear_ticks-s3_clear_last_response,s3_preflight_commands,s3_preflight_responses);
        end else begin
          s3_observe_physical_clear();
          if (@ACCEL@.cmd_valid && s3_clear_first<0) s3_clear_first=s3_clear_ticks;
          if (s3_clear_held_response && (@ACCEL@.rsp_valid!==1'b1 ||
              @ACCEL@.rsp_err!==s3_clear_held_error || @ACCEL@.rsp_rdata!==s3_clear_held_data))
            $fatal(1,"S3_CLEAR_REJECT unstable held MMIO response");
          s3_clear_held_response=@ACCEL@.rsp_valid && !@ACCEL@.rsp_ready;
          s3_clear_held_error=@ACCEL@.rsp_err;
          s3_clear_held_data=@ACCEL@.rsp_rdata;

          if (@ACCEL@.cache_clear_done) begin
            if (!s3_clear_is_sram || s3_clear_sram_commands!=1 || s3_clear_sram_done ||
                s3_clear_ticks-s3_clear_sram_start<768 || s3_physical_bias_count!=768)
              $fatal(1,"S3_CLEAR_REJECT invalid or premature physical bias clear done");
            s3_clear_sram_done=s3_clear_sram_done+1;
          end
          // Retire old response before accepting a replacement command.
          if (@ACCEL@.rsp_valid && @ACCEL@.rsp_ready) begin
            if (!s3_clear_pending || @ACCEL@.rsp_err!==1'b0)
              $fatal(1,"S3_CLEAR_REJECT orphan/error clear response");
            if (!s3_clear_pending_read && s3_clear_response_address==12'h05c &&
                (s3_clear_w_count!=2*s3_clear_w_packs ||
                 s3_physical_w_count!=s3_clear_w_count || @ACCEL@.stream_pending!==1'b0 ||
                 @ACCEL@.u_linear_compute_core.io_wLoadWen!==1'b0))
              $fatal(1,"S3_CLEAR_REJECT W packed response preceded both physical writes");
            if (!s3_clear_pending_read && s3_clear_response_address==12'h068 &&
                (s3_clear_x_count!=2*s3_clear_x_packs || @ACCEL@.stream_pending!==1'b0 ||
                 @ACCEL@.u_linear_compute_core.io_xLoadWen!==1'b0))
              $fatal(1,"S3_CLEAR_REJECT X packed response preceded both physical writes");
            if (s3_clear_pending_preflight) begin
              if (!s3_clear_pending_read || (^@ACCEL@.rsp_rdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT unknown/non-read ABI preflight response");
              s3_preflight_responses=s3_preflight_responses+1;
            end else if (s3_clear_pending_read) begin
              case (s3_clear_response_address)
                12'h000: if (@ACCEL@.rsp_rdata!==32'hacce2030)
                  $fatal(1,"S3_CLEAR_REJECT bad ID response");
                12'h050: if (@ACCEL@.rsp_rdata!==32'h58550003)
                  $fatal(1,"S3_CLEAR_REJECT bad legacy capability response");
                12'h00c: begin
                  if (@ACCEL@.rsp_rdata!==0)
                    $fatal(1,"S3_CLEAR_REJECT non-fresh status response");
                  if (s3_clear_pending_proof) begin
                    s3_clear_verified=1; s3_clear_proof_reads=s3_clear_proof_reads+1;
                  end
                end
                12'h070: if (@ACCEL@.rsp_rdata!==32'h58530003)
                  $fatal(1,"S3_CLEAR_REJECT bad stream capability response");
                12'h074: if (@ACCEL@.rsp_rdata!==32'h58500003)
                  $fatal(1,"S3_CLEAR_REJECT bad packed capability response");
                12'h06c: begin
                  if (@ACCEL@.rsp_rdata!==0)
                    $fatal(1,"S3_CLEAR_REJECT nonzero stream completion status");
                  s3_clear_stream_verified=1;
                end
                12'h0ec: begin
                  if (@ACCEL@.rsp_rdata!==0 && @ACCEL@.rsp_rdata!==32'h42530001)
                    $fatal(1,"S3_CLEAR_REJECT unsupported bias capability response");
                  s3_clear_cap_seen=1;
                  s3_clear_is_sram=@ACCEL@.rsp_rdata===32'h42530001;
                end
                default: $fatal(1,"S3_CLEAR_REJECT untracked clear read response");
              endcase
            end else if (s3_clear_response_address==12'h0e8 && s3_clear_sram_done!=1)
              $fatal(1,"S3_CLEAR_REJECT bias response without physical clear done");
            s3_clear_pending=0;
            if (!s3_clear_pending_preflight) begin
              s3_clear_responses=s3_clear_responses+1;
              s3_clear_last_response=s3_clear_ticks;
            end
          end
          if (@ACCEL@.cmd_valid && @ACCEL@.cmd_ready) begin
            if (s3_clear_pending) $fatal(1,"S3_CLEAR_REJECT multiple clear commands in flight");
            s3_clear_pending=1; s3_clear_pending_read=@ACCEL@.cmd_read;
            s3_clear_response_address=@ACCEL@.cmd_addr[11:0];
            s3_clear_pending_proof=0; s3_clear_pending_preflight=s3_clear_verified;
            if (s3_clear_verified) begin
              if (!@ACCEL@.cmd_read)
                $fatal(1,"S3_CLEAR_REJECT parameter write before first source request");
              case (@ACCEL@.cmd_addr[11:0])
                12'h000,12'h00c,12'h050,12'h070,12'h074,12'h078,12'h0e0,12'h0e4: begin end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected ABI preflight read");
              endcase
              s3_preflight_commands=s3_preflight_commands+1;
            end else if (@ACCEL@.cmd_read) begin
              s3_clear_commands=s3_clear_commands+1;
              case (@ACCEL@.cmd_addr[11:0])
                12'h000: read_index=0;
                12'h050: read_index=1;
                12'h00c: read_index=2;
                12'h0ec: read_index=3;
                12'h070: read_index=4;
                12'h074: read_index=5;
                12'h06c: begin
                  if (s3_clear_reads!=6 || s3_clear_stream_proofs!=0)
                    $fatal(1,"S3_CLEAR_REJECT invalid stream completion proof order");
                  s3_require_clear_coverage();
                  if (@ACCEL@.stream_pending!==1'b0 || @ACCEL@.cache_pending!==1'b0 ||
                      @ACCEL@.u_linear_compute_core.io_wLoadWen!==1'b0 ||
                      @ACCEL@.u_linear_compute_core.io_xLoadWen!==1'b0)
                    $fatal(1,"S3_CLEAR_REJECT undrained clear before stream proof");
                  s3_clear_stream_proofs=s3_clear_stream_proofs+1;
                  read_index=6;
                end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO read");
              endcase
              if (read_index==6) begin end
              else if (s3_clear_read_seen[read_index]) begin
                if (read_index!=2 || s3_clear_reads!=7 || !s3_clear_stream_verified)
                  $fatal(1,"S3_CLEAR_REJECT repeated ABI read");
                s3_require_clear_coverage();
                if (@ACCEL@.cache_pending!==1'b0 || @ACCEL@.stream_pending!==1'b0 ||
                    @ACCEL@.cache_idle!==1'b1 || @ACCEL@.w_load_wen!==1'b0 ||
                    @ACCEL@.x_load_wen!==1'b0 ||
                    @ACCEL@.u_linear_compute_core.io_wLoadWen!==1'b0 ||
                    @ACCEL@.u_linear_compute_core.io_xLoadWen!==1'b0)
                  $fatal(1,"S3_CLEAR_REJECT undrained clear before completion proof");
                s3_clear_pending_proof=1;
              end else s3_clear_read_seen[read_index]=1;
              s3_clear_reads=s3_clear_reads+1;
            end else begin
              s3_clear_commands=s3_clear_commands+1;
              if (!s3_clear_cap_seen || s3_clear_read_seen!==6'h3f ||
                  @ACCEL@.cmd_wmask!==4'hf || (^@ACCEL@.cmd_wdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT missing ABI or incomplete/unknown clear word");
              s3_clear_writes=s3_clear_writes+1;
              case (@ACCEL@.cmd_addr[11:0])
                12'h040: begin
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_disable_count!=0)
                    $fatal(1,"S3_CLEAR_REJECT cache disable");
                  s3_clear_disable_count=s3_clear_disable_count+1;
                end
                12'h054: begin
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_w_addr_count!=0 || s3_clear_w_packs!=0)
                    $fatal(1,"S3_CLEAR_REJECT W cursor initialization");
                  s3_clear_w_addr_count=s3_clear_w_addr_count+1;
                end
                12'h060: begin
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_x_addr_count!=0 || s3_clear_x_packs!=0)
                    $fatal(1,"S3_CLEAR_REJECT X cursor initialization");
                  s3_clear_x_addr_count=s3_clear_x_addr_count+1;
                end
                12'h05c: begin
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_w_addr_count!=1 ||
                      @ACCEL@.w_cursor!==2*s3_clear_w_packs || s3_clear_w_packs>=8192)
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate W packed command");
                  s3_clear_w_packs=s3_clear_w_packs+1;
                end
                12'h068: begin
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_x_addr_count!=1 ||
                      @ACCEL@.x_cursor!==2*s3_clear_x_packs || s3_clear_x_packs>=32)
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate X packed command");
                  s3_clear_x_packs=s3_clear_x_packs+1;
                end
                12'h028: begin
                  if (@ACCEL@.cmd_wdata>7) $fatal(1,"S3_CLEAR_REJECT legacy bias address");
                  s3_clear_legacy_addr_count=s3_clear_legacy_addr_count+1;
                end
                12'h044: begin
                  if (s3_clear_is_sram || @ACCEL@.cmd_wdata>255)
                    $fatal(1,"S3_CLEAR_REJECT register bias address");
                  s3_clear_bias_addr_count=s3_clear_bias_addr_count+1;
                end
                12'h0e8: begin
                  if (!s3_clear_is_sram || @ACCEL@.cmd_wdata!==1 || s3_clear_sram_commands)
                    $fatal(1,"S3_CLEAR_REJECT SRAM bias clear command");
                  s3_clear_sram_commands=1; s3_clear_sram_start=s3_clear_ticks;
                end
                12'h048,12'h04c,12'h02c,12'h030: begin
                  if (@ACCEL@.cmd_wdata!==0) $fatal(1,"S3_CLEAR_REJECT nonzero bias clear");
                  if (@ACCEL@.cmd_addr[11:0]==12'h048 || @ACCEL@.cmd_addr[11:0]==12'h04c) begin
                    if (s3_clear_is_sram || (^@ACCEL@.cache_addr_reg)===1'bx)
                      $fatal(1,"S3_CLEAR_REJECT invalid register bias clear");
                    a=@ACCEL@.cache_addr_reg; old_mask=s3_clear_bias_seen[a];
                  end else begin
                    if ((^@ACCEL@.bias_index_reg)===1'bx)
                      $fatal(1,"S3_CLEAR_REJECT unknown legacy bias destination");
                    a=@ACCEL@.bias_index_reg; old_mask=s3_clear_legacy_seen[a];
                  end
                  if (@ACCEL@.cmd_addr[11:0]==12'h048 || @ACCEL@.cmd_addr[11:0]==12'h02c) begin
                    if (old_mask[3:0]!=0) $fatal(1,"S3_CLEAR_REJECT duplicate bias low clear");
                    new_mask=old_mask|5'b01111;
                  end else begin
                    if (old_mask[4]) $fatal(1,"S3_CLEAR_REJECT duplicate bias high clear");
                    new_mask=old_mask|5'b10000;
                  end
                  if (@ACCEL@.cmd_addr[11:0]==12'h048 || @ACCEL@.cmd_addr[11:0]==12'h04c) begin
                    s3_clear_bias_seen[a]=new_mask;
                    if (new_mask==5'b11111) s3_clear_bias_count=s3_clear_bias_count+1;
                  end else begin
                    s3_clear_legacy_seen[a]=new_mask;
                    if (new_mask==5'b11111) s3_clear_legacy_count=s3_clear_legacy_count+1;
                  end
                end
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO write");
              endcase
            end
          end
        end
      end
      payload_phase=s3_clear_complete;
    end
  endtask
'''.replace('@PHYSICAL_DECLARATIONS@', physical).replace('@ACCEL@', accel)


def physical_observer_declarations(accel, use_bias_sram):
    """Observe actual sampled core and macro write pins; never drive the DUT."""
    chunks = [r'''
  reg [16383:0] s3_physical_w_seen=0;
  reg [767:0] s3_physical_bias_seen=0;
  integer s3_physical_w_count=0, s3_physical_bias_count=0;
  task s3_check_physical_w;
    input integer bank, half;
    input [9:0] address;
    input [15:0] data;
    integer flat;
    begin
      if ((^{address,data})===1'bx || data!==0)
        $fatal(1,"S3_CLEAR_REJECT nonzero/unknown physical W write");
      flat=bank*2048+half*1024+address;
      if (s3_physical_w_seen[flat])
        $fatal(1,"S3_CLEAR_REJECT duplicate physical W write");
      if (@ACCEL@.u_linear_compute_core.io_wLoadWen!==1'b1 ||
          @ACCEL@.u_linear_compute_core.io_wLoadBank!==bank ||
          @ACCEL@.u_linear_compute_core.io_wLoadAddr!==half*1024+address ||
          @ACCEL@.u_linear_compute_core.io_wLoadData!==data)
        $fatal(1,"S3_CLEAR_REJECT physical W/core mismatch");
      s3_physical_w_seen[flat]=1;
      s3_physical_w_count=s3_physical_w_count+1;
    end
  endtask

  task s3_observe_physical_clear;
    integer p, row, column, bank, address, macros_this_edge;
    begin
      macros_this_edge=0;
      if ((^{@ACCEL@.u_linear_compute_core.io_wLoadWen,
             @ACCEL@.u_linear_compute_core.io_xLoadWen})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown actual core strobe");
      if (@ACCEL@.u_linear_compute_core.core.weightBanks.io_ren!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT compute memory read during clear");
      if (@ACCEL@.u_linear_compute_core.io_wLoadWen) begin
        if (!s3_clear_pending || s3_clear_pending_read ||
            s3_clear_response_address!=12'h05c || s3_clear_w_count>=16384 ||
            s3_clear_w_count>=2*s3_clear_w_packs)
          $fatal(1,"S3_CLEAR_REJECT unexpected actual W write");
        p=s3_clear_w_count; row=p/256; column=p%256;
        bank=column%8; address=(column/8)*64+row;
        if (@ACCEL@.u_linear_compute_core.io_wLoadBank!==bank ||
            @ACCEL@.u_linear_compute_core.io_wLoadAddr!==address ||
            @ACCEL@.u_linear_compute_core.io_wLoadData!==0 ||
            s3_clear_w_seen[bank*2048+address])
          $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate/misordered actual W write");
        s3_clear_w_seen[bank*2048+address]=1;
        s3_clear_bank_seen[bank]=1;
        s3_clear_w_count=s3_clear_w_count+1;
      end
      if (@ACCEL@.u_linear_compute_core.io_xLoadWen) begin
        address=@ACCEL@.u_linear_compute_core.io_xLoadAddr;
        if (!s3_clear_pending || s3_clear_pending_read ||
            s3_clear_response_address!=12'h068 || s3_clear_x_count>=64 ||
            s3_clear_x_count>=2*s3_clear_x_packs ||
            address!=s3_clear_x_count || s3_clear_x_seen[address] ||
            @ACCEL@.u_linear_compute_core.io_xLoadData!==0)
          $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate/misordered actual X write");
        s3_clear_x_seen[address]=1;
        s3_clear_x_count=s3_clear_x_count+1;
      end
      if (@ACCEL@.u_linear_compute_core.core.xBuffer.io_wen !==
          @ACCEL@.u_linear_compute_core.io_xLoadWen ||
          (@ACCEL@.u_linear_compute_core.core.xBuffer.io_wen &&
           (@ACCEL@.u_linear_compute_core.core.xBuffer.io_waddr !==
            @ACCEL@.u_linear_compute_core.io_xLoadAddr ||
            @ACCEL@.u_linear_compute_core.core.xBuffer.io_wdata!==0)))
        $fatal(1,"S3_CLEAR_REJECT physical X/core mismatch");
''']
    for bank in range(8):
        for half in range(2):
            pin = f'@ACCEL@.u_linear_compute_core.core.weightBanks.banks_{bank}.sram{half}.mem_ext'
            chunks.append(f'''
      if ((^{{{pin}.RW0_en,{pin}.RW0_wmode}})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical W control");
      if ({pin}.RW0_en && {pin}.RW0_wmode) begin
        s3_check_physical_w({bank},{half},{pin}.RW0_addr,{pin}.RW0_wdata);
        macros_this_edge=macros_this_edge+1;
      end
''')
    chunks.append(r'''
      if (macros_this_edge != (@ACCEL@.u_linear_compute_core.io_wLoadWen ? 1 : 0))
        $fatal(1,"S3_CLEAR_REJECT physical W strobe cardinality");
''')
    if use_bias_sram:
        pin = '@ACCEL@.u_linear_compute_core.biasCache.memory.mem_ext'
        chunks.append(f'''
      if ((^{{{pin}.RW0_en,{pin}.RW0_wmode}})===1'bx)
        $fatal(1,"S3_CLEAR_REJECT unknown physical bias control");
      if ({pin}.RW0_en) begin
        address={pin}.RW0_addr;
        if ({pin}.RW0_wmode!==1'b1 || {pin}.RW0_wdata!==0 ||
            s3_clear_sram_commands!=1 || s3_clear_sram_done!=0 ||
            address>=768 || address!=s3_physical_bias_count || s3_physical_bias_seen[address])
          $fatal(1,"S3_CLEAR_REJECT invalid physical bias clear write");
        s3_physical_bias_seen[address]=1;
        s3_physical_bias_count=s3_physical_bias_count+1;
      end
''')
    chunks.append(r'''
    end
  endtask

  task s3_require_physical_clear_coverage;
    integer a;
    begin
      s3_require_physical_clear_idle();
      if (s3_physical_w_count!=16384 || s3_physical_w_seen!=={16384{1'b1}} ||
          s3_clear_w_seen!=={16384{1'b1}} || s3_clear_x_seen!=={64{1'b1}} ||
          @ACCEL@.w_cursor!==16384 || @ACCEL@.x_cursor!==64)
        $fatal(1,"S3_CLEAR_REJECT incomplete physical W/X coverage");
''')
    for bank in range(8):
        for half in range(2):
            chunks.append(f'''
      for (a=0;a<1024;a=a+1)
        if (@ACCEL@.u_linear_compute_core.core.weightBanks.banks_{bank}.sram{half}.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical W poststate bank={bank} half={half}");
''')
    for address in range(64):
        chunks.append(f'''
      if (@ACCEL@.u_linear_compute_core.core.xBuffer.data_{address}!==16'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X poststate address={address}");
''')
    for lane in range(8):
        chunks.append(f'''
      if (@ACCEL@.bias_regs[{lane}]!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical legacy bias poststate lane={lane}");
''')
    if use_bias_sram:
        chunks.append(r'''
      if (!s3_clear_is_sram || s3_physical_bias_count!=768 ||
          s3_physical_bias_seen!=={768{1'b1}} ||
          @ACCEL@.u_linear_compute_core.biasCache.slotValid_0!==1'b0 ||
          @ACCEL@.u_linear_compute_core.biasCache.slotValid_1!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT incomplete physical bias coverage");
      for (a=0;a<768;a=a+1)
        if (@ACCEL@.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'b0)
          $fatal(1,"S3_CLEAR_REJECT physical bias poststate");
''')
        for slot in range(2):
            for lane in range(8):
                chunks.append(f'''
      if (@ACCEL@.u_linear_compute_core.biasCache.slotData_{slot}_{lane}!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias staging poststate slot={slot} lane={lane}");
''')
    else:
        chunks.append('''
      if (s3_clear_is_sram || s3_physical_bias_count!=0)
        $fatal(1,"S3_CLEAR_REJECT register bias mode mismatch");
''')
        for bank in range(8):
            for group in range(32):
                chunks.append(f'''
      if (@ACCEL@.u_linear_compute_core.biasCache.banks_{bank}_{group}!==40'b0)
        $fatal(1,"S3_CLEAR_REJECT physical register bias poststate");
''')
    chunks.append('''
    end
  endtask
  task s3_require_physical_clear_idle;
    begin
      if (@ACCEL@.u_linear_compute_core.core.xBuffer.io_wen!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical X write still active at proof");
''')
    for bank in range(8):
        for half in range(2):
            pin = f'@ACCEL@.u_linear_compute_core.core.weightBanks.banks_{bank}.sram{half}.mem_ext'
            chunks.append(f'''
      if ({pin}.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical W port still active at proof");
''')
    if use_bias_sram:
        chunks.append('''
      if (@ACCEL@.u_linear_compute_core.biasCache.memory.mem_ext.RW0_en!==1'b0)
        $fatal(1,"S3_CLEAR_REJECT physical bias port still active at proof");
''')
    chunks.append('''
    end
  endtask
''')
    return ''.join(chunks).replace('@ACCEL@', accel)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, required=True)
    parser.add_argument('--main-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--accel-hierarchy', default='`ACCEL')
    args = parser.parse_args(argv)
    wrapper = firmware_wrapper(args.main, args.main_sha256)
    observer = observer_declarations(args.accel_hierarchy)
    args.out.mkdir(parents=True, exist_ok=False)
    paths = [args.out/'s3_clear_main.c', args.out/'s3_clear_observer.svh']
    paths[0].write_text(wrapper)
    paths[1].write_text(observer)
    report = dict(schema='s3-task-packed-clear-protocol-v1', status='GENERATED_NOT_FULL_SOC_SIMULATED',
                  cache_policy_review_status='REVIEW_PENDING',
                  frozen_main=dict(path=str(args.main.resolve()), sha256=args.main_sha256),
                  helper=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  reused_validation=dict(path=str(_LEGACY_PATH.resolve()), sha256=sha(_LEGACY_PATH)),
                  outputs=[dict(path=str(p.resolve()), sha256=sha(p)) for p in paths],
                  clear_counts=CLEAR_COUNTS, tasks=1, reset='fresh process before every task',
                  baseline_modified=False, payload_observers='retain unchanged; gate invocation only',
                  measurement_start='first task source request including all pre-accept wait',
                  clearing_activity='retain separate cycles and full-SoC activity',
                  limitations=['No full-SoC, vendor-model, PPA or official policy PASS',
                               'FIFO payload physical zero remains UNPROVEN; metadata invalid only',
                               'NICE snapshot zero relies on fresh reset; observe actual idle before payload',
                               'All RTL, header, firmware and tool inputs still need campaign-level SHA binding'])
    (args.out/'clear-recipe.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print('GENERATED_NOT_FULL_SOC_SIMULATED: '+str(args.out/'clear-recipe.json'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
