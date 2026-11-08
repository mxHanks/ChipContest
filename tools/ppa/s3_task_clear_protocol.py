#!/usr/bin/env python3
"""Generate an isolated, fresh-reset TASKS=1 S3 clearing candidate.

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
                 accepted_writes=32930, cache_disable_writes=1,
                 initial_abi_reads=4, completion_proof_reads=1),
    'registers': dict(w=16384, x=64, legacy_bias=8, bias_entries=256,
                     bias_clear_commands=0, accepted_writes=33697,
                     cache_disable_writes=1, initial_abi_reads=4,
                     completion_proof_reads=1),
}


def firmware_wrapper(main, expected_sha256):
    # Reuse the original helper's strict hash/path validation, without changing
    # its historical recipe or treating it as S3 qualification evidence.
    _LEGACY.firmware_wrapper(main, expected_sha256)
    main = Path(main).resolve()
    return r'''/* S3 separate clear candidate; frozen main SHA256: @MAIN_SHA@ */
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
    reg[0x040 / 4] = 0u;
    for (unsigned bank = 0; bank < 8; ++bank) {
        reg[0x01c / 4] = bank;
        for (unsigned address = 0; address < 2048; ++address) {
            reg[0x020 / 4] = address;
            reg[0x024 / 4] = 0u;
        }
    }
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
    for (unsigned address = 0; address < 64; ++address) {
        reg[0x014 / 4] = address;
        reg[0x018 / 4] = 0u;
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    /* Explicit completion proof separates clear from frozen-main ABI reads. */
    if (reg[0x00c / 4] != 0u) return -4;
    return 0;
}

int main(void) {
    if (s3_clear_task_data_and_parameters()) return 17;
    return s3_frozen_task_main();
}
'''.replace('@MAIN_SHA@', expected_sha256).replace('@MAIN_PATH@', str(main))


def observer_declarations(accel='`ACCEL'):
    """Passive declarations; call once/edge before original payload observers.

    first_source_request is VALID/address/read, NOT valid && ready. nice_idle
    must observe the real NICE owner, command, response and completion paths.
    The caller separately enforces fresh reset and TASKS=1, and retains all
    original payload checks. This observer drives no DUT input or memory.
    """
    if not re.fullmatch(r'(?:`?[A-Za-z_][A-Za-z0-9_$]*)(?:\.[A-Za-z_][A-Za-z0-9_$]*)*', accel):
        raise ValueError('invalid observed accelerator hierarchy')
    return r'''
  // S3 passive clear proof. No force, DUT assignment, or task-data preloading.
  integer s3_clear_ticks=0, s3_clear_first=-1, s3_clear_last_response=-1;
  integer s3_clear_writes=0, s3_clear_commands=0, s3_clear_responses=0;
  integer s3_clear_w_count=0, s3_clear_x_count=0, s3_clear_legacy_count=0;
  integer s3_clear_bias_count=0, s3_clear_disable_count=0, s3_clear_reads=0;
  integer s3_clear_w_addr_count=0, s3_clear_x_addr_count=0;
  integer s3_clear_legacy_addr_count=0, s3_clear_bias_addr_count=0;
  integer s3_clear_sram_commands=0, s3_clear_sram_done=0, s3_clear_sram_start=-1;
  integer s3_clear_proof_reads=0, s3_preflight_commands=0, s3_preflight_responses=0;
  reg [16383:0] s3_clear_w_seen=0;
  reg [63:0] s3_clear_x_seen=0;
  reg [7:0] s3_clear_bank_seen=0;
  reg [4:0] s3_clear_bias_seen [0:255];
  reg [4:0] s3_clear_legacy_seen [0:7];
  reg [3:0] s3_clear_read_seen=0;
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
      expected_writes=s3_clear_is_sram ? 32930 : 33697;
      if (!s3_clear_cap_seen || s3_clear_read_seen!==4'hf ||
          s3_clear_writes!=expected_writes || s3_clear_disable_count!=1 ||
          s3_clear_w_count!=16384 || s3_clear_x_count!=64 || s3_clear_legacy_count!=8 ||
          s3_clear_bank_seen!==8'hff || s3_clear_w_addr_count!=16384 ||
          s3_clear_x_addr_count!=64 || s3_clear_legacy_addr_count!=8 ||
          (s3_clear_is_sram && (s3_clear_sram_commands!=1 ||
            s3_clear_sram_done!=1 || s3_clear_bias_count!=0 || s3_clear_bias_addr_count!=0)) ||
          (!s3_clear_is_sram && (s3_clear_bias_count!=256 ||
            s3_clear_bias_addr_count!=256 || s3_clear_sram_commands!=0 || s3_clear_sram_done!=0)))
        $fatal(1,"S3_CLEAR_REJECT incomplete clear before first source request");
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
              @ACCEL@.x_load_wen!==1'b0)
            $fatal(1,"S3_CLEAR_REJECT undrained clear before first source request");
          s3_require_clear_coverage();
          if (!s3_clear_verified || s3_clear_proof_reads!=1 || s3_clear_reads!=5)
            $fatal(1,"S3_CLEAR_REJECT missing clear completion proof before first source request");
          s3_clear_complete=1;
          $display("S3_TASK_CLEAR_OBSERVED mode_sram=%0d writes=%0d w=16384 x=64 legacy_bias=8 bias_entries=%0d sram_clear_commands=%0d sram_done=%0d commands=%0d responses=%0d clear_cycles=%0d response_end_cycle=%0d gap_to_source_request=%0d preflight_commands=%0d preflight_responses=%0d nice_idle=1 fifo_payload_physical_zero=UNPROVEN policy=REVIEW_PENDING",
            s3_clear_is_sram,s3_clear_writes,s3_clear_bias_count,
            s3_clear_sram_commands,s3_clear_sram_done,s3_clear_commands,s3_clear_responses,
            s3_clear_last_response-s3_clear_first+1,s3_clear_last_response,
            s3_clear_ticks-s3_clear_last_response,s3_preflight_commands,s3_preflight_responses);
        end else begin
          if (@ACCEL@.cmd_valid && s3_clear_first<0) s3_clear_first=s3_clear_ticks;
          if (s3_clear_held_response && (@ACCEL@.rsp_valid!==1'b1 ||
              @ACCEL@.rsp_err!==s3_clear_held_error || @ACCEL@.rsp_rdata!==s3_clear_held_data))
            $fatal(1,"S3_CLEAR_REJECT unstable held MMIO response");
          s3_clear_held_response=@ACCEL@.rsp_valid && !@ACCEL@.rsp_ready;
          s3_clear_held_error=@ACCEL@.rsp_err;
          s3_clear_held_data=@ACCEL@.rsp_rdata;

          if (@ACCEL@.cache_clear_done) begin
            if (!s3_clear_is_sram || s3_clear_sram_commands!=1 || s3_clear_sram_done ||
                s3_clear_ticks-s3_clear_sram_start<768)
              $fatal(1,"S3_CLEAR_REJECT invalid or premature physical bias clear done");
            s3_clear_sram_done=s3_clear_sram_done+1;
          end
          // Retire old response before accepting a replacement command.
          if (@ACCEL@.rsp_valid && @ACCEL@.rsp_ready) begin
            if (!s3_clear_pending || @ACCEL@.rsp_err!==1'b0)
              $fatal(1,"S3_CLEAR_REJECT orphan/error clear response");
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
                default: $fatal(1,"S3_CLEAR_REJECT unexpected pretask MMIO read");
              endcase
              if (s3_clear_read_seen[read_index]) begin
                if (read_index!=2 || s3_clear_reads!=4)
                  $fatal(1,"S3_CLEAR_REJECT repeated ABI read");
                s3_require_clear_coverage();
                if (@ACCEL@.cache_pending!==1'b0 || @ACCEL@.stream_pending!==1'b0 ||
                    @ACCEL@.cache_idle!==1'b1 || @ACCEL@.w_load_wen!==1'b0 ||
                    @ACCEL@.x_load_wen!==1'b0)
                  $fatal(1,"S3_CLEAR_REJECT undrained clear before completion proof");
                s3_clear_pending_proof=1;
              end else s3_clear_read_seen[read_index]=1;
              s3_clear_reads=s3_clear_reads+1;
            end else begin
              s3_clear_commands=s3_clear_commands+1;
              if (!s3_clear_cap_seen || s3_clear_read_seen!==4'hf ||
                  @ACCEL@.cmd_wmask!==4'hf || (^@ACCEL@.cmd_wdata)===1'bx)
                $fatal(1,"S3_CLEAR_REJECT missing ABI or incomplete/unknown clear word");
              s3_clear_writes=s3_clear_writes+1;
              case (@ACCEL@.cmd_addr[11:0])
                12'h040: begin
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_disable_count!=0)
                    $fatal(1,"S3_CLEAR_REJECT cache disable");
                  s3_clear_disable_count=s3_clear_disable_count+1;
                end
                12'h01c: begin
                  if (@ACCEL@.cmd_wdata>7 || s3_clear_bank_seen[@ACCEL@.cmd_wdata[2:0]])
                    $fatal(1,"S3_CLEAR_REJECT W bank selection");
                  s3_clear_bank_seen[@ACCEL@.cmd_wdata[2:0]]=1;
                end
                12'h020: begin
                  if (@ACCEL@.cmd_wdata>2047) $fatal(1,"S3_CLEAR_REJECT W address");
                  s3_clear_w_addr_count=s3_clear_w_addr_count+1;
                end
                12'h014: begin
                  if (@ACCEL@.cmd_wdata>63) $fatal(1,"S3_CLEAR_REJECT X address");
                  s3_clear_x_addr_count=s3_clear_x_addr_count+1;
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
                12'h024: begin
                  if ((^{@ACCEL@.w_bank_reg,@ACCEL@.w_addr_reg})===1'bx)
                    $fatal(1,"S3_CLEAR_REJECT unknown W destination");
                  a=@ACCEL@.w_bank_reg*2048+@ACCEL@.w_addr_reg;
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_w_seen[a])
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate W clear");
                  s3_clear_w_seen[a]=1; s3_clear_w_count=s3_clear_w_count+1;
                end
                12'h018: begin
                  if ((^@ACCEL@.x_addr_reg)===1'bx) $fatal(1,"S3_CLEAR_REJECT unknown X destination");
                  a=@ACCEL@.x_addr_reg;
                  if (@ACCEL@.cmd_wdata!==0 || s3_clear_x_seen[a])
                    $fatal(1,"S3_CLEAR_REJECT nonzero/duplicate X clear");
                  s3_clear_x_seen[a]=1; s3_clear_x_count=s3_clear_x_count+1;
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
'''.replace('@ACCEL@', accel)


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
    report = dict(schema='s3-task-clear-protocol-v1', status='GENERATED_NOT_FULL_SOC_SIMULATED',
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
