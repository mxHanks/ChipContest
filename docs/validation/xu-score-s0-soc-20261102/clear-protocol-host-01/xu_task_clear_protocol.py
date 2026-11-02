#!/usr/bin/env python3
"""Generate an explicit pre-task CPU-MMIO clearing candidate, never a baseline.

This helper changes no existing source. See xu_task_clear_protocol.md for the
separate firmware recipe, passive observer integration and evidence limits.
Python 3.6+ and the standard library are sufficient.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


CLEAR_COUNTS = dict(w=16384, bias=256, legacy_bias=8, x=64,
                    accepted_writes=33697, cache_disable_writes=1)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def firmware_wrapper(main, expected_sha256):
    """Include the exact caller-pinned main, adding no task-source reads."""
    main = Path(main).resolve()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('main SHA256 must be an explicit lowercase SHA256')
    if sha(main) != expected_sha256:
        raise ValueError('frozen main SHA256 differs')
    if any(c in str(main) for c in ('"', '\\', '\n', '\r')):
        raise ValueError('main path cannot be represented by a literal C include')
    return '''/* xu explicit clear candidate; original main SHA256: MAIN_SHA */
#define main xu_frozen_task_main
#include "MAIN_PATH"
#undef main

/* Fresh-process TASKS=1 only. No task X/W/bias pointer is accessed here. */
static int xu_clear_task_data_and_parameters(void) {
    volatile uint32_t *const reg = (volatile uint32_t *)0x10042000u;
    if (reg[0x000 / 4] != 0xacce2030u ||
        reg[0x050 / 4] != 0x58550003u || (reg[0x00c / 4] & 1u)) return -1;
    reg[0x040 / 4] = 0; /* cache disabled throughout clearing */
    for (unsigned bank = 0; bank < 8; ++bank) {
        reg[0x01c / 4] = bank;
        for (unsigned address = 0; address < 2048; ++address) {
            reg[0x020 / 4] = address;
            reg[0x024 / 4] = 0;
        }
    }
    for (unsigned column = 0; column < 256; ++column) {
        reg[0x044 / 4] = column;
        reg[0x048 / 4] = 0;
        reg[0x04c / 4] = 0;
    }
    for (unsigned lane = 0; lane < 8; ++lane) {
        reg[0x028 / 4] = lane;
        reg[0x02c / 4] = 0;
        reg[0x030 / 4] = 0;
    }
    for (unsigned address = 0; address < 64; ++address) {
        reg[0x014 / 4] = address;
        reg[0x018 / 4] = 0;
    }
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
    return 0;
}

int main(void) {
    if (xu_clear_task_data_and_parameters()) return 17;
    return xu_frozen_task_main();
}
'''.replace('MAIN_SHA', expected_sha256).replace('MAIN_PATH', str(main))


def observer_declarations(accel='`ACCEL'):
    """Return passive TB declarations; caller invokes the task after reset.

    source_accept is the first accepted task X/W/bias source read, using the
    same range predicate as the timing observer. payload_phase gates only the
    existing payload observer's invocation, never its assertions or DUT inputs.
    """
    if not re.fullmatch(r'(?:`?[A-Za-z_][A-Za-z0-9_$]*)(?:\.[A-Za-z_][A-Za-z0-9_$]*)*', accel):
        raise ValueError('invalid observed accelerator hierarchy')
    return r'''
  // xu passive clear observer: no force, no DUT assignment, no task payload.
  integer xu_clear_writes=0, xu_clear_w_count=0, xu_clear_bias_count=0;
  integer xu_clear_legacy_count=0, xu_clear_x_count=0, xu_clear_disable_count=0;
  reg [16383:0] xu_clear_w_seen=0;
  reg [63:0] xu_clear_x_seen=0;
  reg [4:0] xu_clear_bias_seen [0:255];
  reg [4:0] xu_clear_legacy_seen [0:7];
  reg xu_clear_complete=0;
  integer xu_clear_init;
  initial begin
    for (xu_clear_init=0;xu_clear_init<256;xu_clear_init=xu_clear_init+1)
      xu_clear_bias_seen[xu_clear_init]=0;
    for (xu_clear_init=0;xu_clear_init<8;xu_clear_init=xu_clear_init+1)
      xu_clear_legacy_seen[xu_clear_init]=0;
  end

  task xu_observe_task_clear;
    input source_accept;
    output payload_phase;
    integer a;
    reg [4:0] old_mask, new_mask;
    begin
      if (!xu_clear_complete) begin
        if (@ACCEL@.cache_enable!==1'b0 || @ACCEL@.busy!==1'b0 ||
            @ACCEL@.core_start!==1'b0)
          $fatal(1,"XU_CLEAR_REJECT non-idle/enabled clear phase");
        if (source_accept) begin
          if (xu_clear_writes!=33697 || xu_clear_disable_count!=1 ||
              xu_clear_w_count!=16384 || xu_clear_bias_count!=256 ||
              xu_clear_legacy_count!=8 || xu_clear_x_count!=64)
            $fatal(1,"XU_CLEAR_REJECT incomplete clear before first source accept");
          // W/X stores are committed one clock after MMIO acceptance.
          if (@ACCEL@.w_load_wen!==1'b0 || @ACCEL@.x_load_wen!==1'b0)
            $fatal(1,"XU_CLEAR_REJECT undrained W/X clear strobe");
          xu_clear_complete=1;
          $display("XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1");
        end else if (@ACCEL@.cmd_valid && @ACCEL@.cmd_ready) begin
          if (@ACCEL@.cmd_read) begin
            if (@ACCEL@.cmd_addr[11:0]!=12'h000 &&
                @ACCEL@.cmd_addr[11:0]!=12'h00c &&
                @ACCEL@.cmd_addr[11:0]!=12'h050)
              $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO read");
          end else begin
            if (@ACCEL@.cmd_wmask!==4'hf ||
                (^@ACCEL@.cmd_wdata)===1'bx)
              $fatal(1,"XU_CLEAR_REJECT incomplete/unknown clear word");
            xu_clear_writes=xu_clear_writes+1;
            case (@ACCEL@.cmd_addr[11:0])
              12'h040: begin
                if (@ACCEL@.cmd_wdata!==32'b0 || xu_clear_disable_count!=0)
                  $fatal(1,"XU_CLEAR_REJECT cache disable");
                xu_clear_disable_count=xu_clear_disable_count+1;
              end
              12'h01c: if (@ACCEL@.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT W bank");
              12'h020: if (@ACCEL@.cmd_wdata>2047)
                $fatal(1,"XU_CLEAR_REJECT W address");
              12'h044: if (@ACCEL@.cmd_wdata>255)
                $fatal(1,"XU_CLEAR_REJECT bias address");
              12'h028: if (@ACCEL@.cmd_wdata>7)
                $fatal(1,"XU_CLEAR_REJECT legacy bias address");
              12'h014: if (@ACCEL@.cmd_wdata>63)
                $fatal(1,"XU_CLEAR_REJECT X address");
              12'h024: begin
                if ((^{@ACCEL@.w_bank_reg,@ACCEL@.w_addr_reg})===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown W destination");
                a=@ACCEL@.w_bank_reg*2048+@ACCEL@.w_addr_reg;
                if (@ACCEL@.cmd_wdata!==32'b0 || xu_clear_w_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate W clear");
                xu_clear_w_seen[a]=1;
                xu_clear_w_count=xu_clear_w_count+1;
              end
              12'h018: begin
                if ((^@ACCEL@.x_addr_reg)===1'bx)
                  $fatal(1,"XU_CLEAR_REJECT unknown X destination");
                a=@ACCEL@.x_addr_reg;
                if (@ACCEL@.cmd_wdata!==32'b0 || xu_clear_x_seen[a])
                  $fatal(1,"XU_CLEAR_REJECT nonzero/duplicate X clear");
                xu_clear_x_seen[a]=1;
                xu_clear_x_count=xu_clear_x_count+1;
              end
              12'h048,12'h04c,12'h02c,12'h030: begin
                if (@ACCEL@.cmd_wdata!==32'b0)
                  $fatal(1,"XU_CLEAR_REJECT nonzero bias clear");
                if (@ACCEL@.cmd_addr[11:0]==12'h048 ||
                    @ACCEL@.cmd_addr[11:0]==12'h04c) begin
                  if ((^@ACCEL@.cache_addr_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown bias destination");
                  a=@ACCEL@.cache_addr_reg;
                  old_mask=xu_clear_bias_seen[a];
                end else begin
                  if ((^@ACCEL@.bias_index_reg)===1'bx)
                    $fatal(1,"XU_CLEAR_REJECT unknown legacy bias destination");
                  a=@ACCEL@.bias_index_reg;
                  old_mask=xu_clear_legacy_seen[a];
                end
                if (@ACCEL@.cmd_addr[11:0]==12'h048 ||
                    @ACCEL@.cmd_addr[11:0]==12'h02c) begin
                  if (old_mask[3:0]!=0)
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias low clear");
                  new_mask=old_mask|5'b01111;
                end else begin
                  if (old_mask[4])
                    $fatal(1,"XU_CLEAR_REJECT duplicate bias high clear");
                  new_mask=old_mask|5'b10000;
                end
                if (@ACCEL@.cmd_addr[11:0]==12'h048 ||
                    @ACCEL@.cmd_addr[11:0]==12'h04c) begin
                  xu_clear_bias_seen[a]=new_mask;
                  if (new_mask==5'b11111) xu_clear_bias_count=xu_clear_bias_count+1;
                end else begin
                  xu_clear_legacy_seen[a]=new_mask;
                  if (new_mask==5'b11111) xu_clear_legacy_count=xu_clear_legacy_count+1;
                end
              end
              default: $fatal(1,"XU_CLEAR_REJECT unexpected pretask MMIO write");
            endcase
          end
        end
      end
      payload_phase=xu_clear_complete;
    end
  endtask
'''.replace('@ACCEL@', accel)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', type=Path, required=True, help='exact frozen firmware/main.c')
    parser.add_argument('--main-sha256', required=True, help='explicit expected SHA256 of main.c')
    parser.add_argument('--out', type=Path, required=True, help='new candidate directory')
    parser.add_argument('--accel-hierarchy', default='`ACCEL')
    args = parser.parse_args(argv)
    wrapper = firmware_wrapper(args.main, args.main_sha256)
    observer = observer_declarations(args.accel_hierarchy)
    args.out.mkdir(parents=True, exist_ok=False)
    wrapper_path, observer_path = [args.out / name for name in
                                   ('xu_clear_main.c', 'xu_clear_observer.svh')]
    wrapper_path.write_text(wrapper)
    observer_path.write_text(observer)
    report = dict(schema='xu-task-clear-protocol-v1', status='GENERATED_NOT_FULL_SOC_SIMULATED',
                  cache_policy_review_status='REVIEW_PENDING',
                  frozen_main=dict(path=str(args.main.resolve()), sha256=args.main_sha256),
                  helper=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
                  outputs=[dict(path=str(p.resolve()), sha256=sha(p))
                           for p in (wrapper_path, observer_path)], clear_counts=CLEAR_COUNTS,
                  requires='one fresh reset process; TASKS=1; original payload observer retained',
                  baseline_modified=False,
                  limitations=['No full-SoC execution, official cache-policy acceptance or PPA PASS',
                               'No vendor initialization or model modification',
                               'Clearing activity and elapsed cycles require separate reporting'])
    (args.out / 'clear-recipe.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print('GENERATED_NOT_FULL_SOC_SIMULATED: ' + str(args.out / 'clear-recipe.json'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
