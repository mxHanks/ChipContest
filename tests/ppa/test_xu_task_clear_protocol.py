"""Public-MMIO clear probes against the actual wrapper, never a SoC/PPA PASS."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'xu_task_clear_protocol', ROOT / 'tools/ppa/xu_task_clear_protocol.py')
clear = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clear)


def probe():
    """All DUT writes below are public MMIO; hierarchy is observed only."""
    checks = []
    for bank in range(8):
        for half in range(2):
            checks.append('''    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_%d.sram%d.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W content not zero bank=%d half=%d address=%%0d",a);'''
                          % (bank, half, bank, half))
    for address in range(64):
        checks.append('''    if (dut.u_linear_compute_core.core.xBuffer.data_%d!==16'b0)
      $fatal(1,"physical X content not zero address=%d");''' % (address, address))
    for bank in range(8):
        for group in range(32):
            checks.append('''    if (dut.u_linear_compute_core.biasCache.banks_%d_%d!==40'b0)
      $fatal(1,"physical bias content not zero bank=%d group=%d");'''
                          % (bank, group, bank, group))
    return r'''
`timescale 1ns/1ps
module tb_xu_task_clear_protocol;
  reg clk=0, rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  always #5 clk=~clk;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  reg source_accept=0, payload_phase=0;
  integer bank, a, lane, polls, mode=0, accepted=0, retired=0;
  reg [31:0] response;
  reg [39:0] bias_value;
  reg [47:0] expected;
@OBSERVER@
  always @(posedge clk) if (rst_n) begin
    xu_observe_task_clear(source_accept,payload_phase);
    if (cmd_valid && cmd_ready) accepted=accepted+1;
    if (rsp_valid && rsp_ready) retired=retired+1;
  end

  // The target stalls each response for one cycle; the driver checks stability.
  task automatic transfer(input bit read_access, input [11:0] address,
                          input [31:0] data, input [3:0] mask,
                          output [31:0] word);
    reg [31:0] held;
    begin
      @(negedge clk);
      cmd_valid=1; cmd_read=read_access; cmd_addr={20'h10042,address};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      @(posedge clk);
      if (!cmd_ready) $fatal(1,"probe driver unexpected blocked command");
      #1;
      if (!rsp_valid || rsp_err) $fatal(1,"probe driver missing/error response");
      held=rsp_rdata;
      @(negedge clk); cmd_valid=0;
      @(posedge clk); #1;
      if (!rsp_valid || cmd_ready || rsp_rdata!==held)
        $fatal(1,"probe stalled response changed");
      word=held;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask
  task automatic put(input [11:0] address,input [31:0] data,input [3:0] mask);
    reg [31:0] ignored;
    begin transfer(0,address,data,mask,ignored); end
  endtask
  task automatic expect_read(input [11:0] address,input [31:0] expected_word);
    reg [31:0] word;
    begin
      transfer(1,address,0,0,word);
      if (word!==expected_word)
        $fatal(1,"probe read mismatch address=%h actual=%h expected=%h",address,word,expected_word);
    end
  endtask
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    repeat (4) @(negedge clk);
    rst_n=1;
    @(negedge clk);
    // No reset/default-zero assumption: these actual storage elements are X.
    if ((^dut.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.Memory[0])!==1'bx ||
        (^dut.u_linear_compute_core.core.xBuffer.data_0)!==1'bx ||
        (^dut.u_linear_compute_core.biasCache.banks_0_0)!==1'bx)
      $fatal(1,"probe requires uninitialized task memories");
    $display("XU_CLEAR_PROBE_TRACE initial_sampled_w_x_bias=unknown reset_cache_enable=%0d",dut.cache_enable);
    expect_read('h000,32'hacce2030);
    expect_read('h050,32'h58550003);
    expect_read('h00c,0);
    put('h040,0,15);
    for (bank=0;bank<8;bank=bank+1) begin
      put('h01c,bank,15);
      for (a=0;a<2048;a=a+1) begin
        put('h020,a,15);
        if (!(mode==1 && bank==7 && a==2047))
          put('h024,(mode==3 && bank==0 && a==0)?1:0,15);
      end
    end
    for (a=0;a<256;a=a+1) begin
      put('h044,a,15); put('h048,0,15);
      put('h04c,0,(mode==2 && a==0)?0:15);
    end
    for (lane=0;lane<8;lane=lane+1) begin
      put('h028,lane,15); put('h02c,0,15); put('h030,0,15);
    end
    for (a=0;a<64;a=a+1) begin
      put('h014,a,15);
      if (mode==4 && a==63) begin
        @(negedge clk);
        cmd_valid=1; cmd_read=0; cmd_addr=32'h10042018;
        cmd_wdata=0; cmd_wmask=15; rsp_ready=1;
        @(posedge clk); #1;
        @(negedge clk); cmd_valid=0; source_accept=1;
        @(posedge clk); #1;
        $fatal(1,"undrained negative probe unexpectedly accepted");
      end else put('h018,0,15);
    end
    @(negedge clk); source_accept=1;
    @(posedge clk); #1;
    if (!payload_phase || !xu_clear_complete)
      $fatal(1,"payload observer was not enabled at first source accept");
    @(negedge clk); source_accept=0;
@PHYSICAL_CHECKS@
    for (lane=0;lane<8;lane=lane+1)
      if (dut.bias_regs[lane]!==40'b0) $fatal(1,"legacy bias was not cleared");
    $display("XU_CLEAR_PROBE_TRACE all_w_x_bias_storage_zero=1 accepted_clear_writes=%0d",xu_clear_writes);

    // A small post-clear arithmetic witness uses public MMIO and signed data.
    // Unchanged zero W entries must participate correctly in the dot product.
    for (bank=0;bank<8;bank=bank+1) begin
      put('h01c,bank,15); put('h020,31*64,15); put('h024,bank+1,15);
      bias_value=-5*(bank+1);
      put('h044,248+bank,15); put('h048,bias_value[31:0],15);
      put('h04c,{24'b0,bias_value[39:32]},15);
    end
    for (a=0;a<64;a=a+1) begin
      put('h014,a,15); put('h018,3,15);
    end
    put('h040,1,15); put('h010,31,15); put('h00c,2,15); put('h008,1,15);
    polls=0; response=0;
    while (!response[1]) begin
      transfer(1,'h00c,0,0,response); polls=polls+1;
      if (polls>32) $fatal(1,"probe compute timeout");
    end
    if (response[0]) $fatal(1,"probe completion remains busy");
    for (lane=0;lane<8;lane=lane+1) begin
      expected=-2*(lane+1);
      expect_read('h080+8*lane,expected[31:0]);
      expect_read('h084+8*lane,{16'b0,expected[47:32]});
    end
    if (accepted!=retired) $fatal(1,"probe response retirement mismatch");
    $display("XU_CLEAR_MMIO_PROBE_PASS clear_writes=33697 checked_w_words=16384 checked_bias_entries=256 checked_legacy_bias=8 checked_x_words=64 result_lanes=8 accepted=%0d retired=%0d",accepted,retired);
    $finish;
  end
  initial begin #10000000; $fatal(1,"probe timeout"); end
endmodule
'''.replace('@OBSERVER@', clear.observer_declarations('dut')).replace(
        '@PHYSICAL_CHECKS@', '\n'.join(checks))


class XuTaskClearProtocolTests(unittest.TestCase):
    def test_frozen_main_pin_and_riscv_compilation(self):
        main = ROOT / 'tests/e203/firmware/main.c'
        with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
            clear.firmware_wrapper(main, '0'*64)
        generated = clear.firmware_wrapper(main, clear.sha(main))
        self.assertIn('#include "' + str(main) + '"', generated)
        compiler = shutil.which('riscv64-unknown-elf-gcc')
        if not compiler:
            self.skipTest('RISC-V compiler required for generated wrapper compilation')
        with tempfile.TemporaryDirectory(prefix='xu-clear-c-') as temporary:
            source = Path(temporary) / 'xu_clear_main.c'
            source.write_text(generated)
            result = subprocess.run([compiler, '-march=rv32imac_zicsr2p0_zifencei2p0',
                                     '-mabi=ilp32', '-O2', '-ffreestanding', '-fno-builtin',
                                     '-Wall', '-Wextra', '-Werror', '-c', str(source),
                                     '-o', str(Path(temporary)/'clear.o')],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_actual_wrapper_positive_and_negative_mmio(self):
        if not shutil.which('iverilog') or not shutil.which('vvp'):
            self.skipTest('Icarus required for actual-wrapper MMIO probes')
        perips = ROOT / 'third-party/e203_hbirdv2/rtl/e203/perips'
        names = ['BiasBankCache.sv', 'LinearCachedCore.sv', 'LinearComputeCore.sv',
                 'DotProductEngine.sv', 'MacController.sv', 'MacPEArray.sv',
                 'MacPE.sv', 'XRowBuffer.sv', 'WeightBankArray.sv',
                 'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv', 'accel_icb_slave.v']
        with tempfile.TemporaryDirectory(prefix='xu-clear-mmio-') as temporary:
            source = Path(temporary) / 'tb_clear.sv'
            binary = Path(temporary) / 'clear.vvp'
            source.write_text(probe())
            built = subprocess.run(['iverilog', '-g2012', '-s', 'tb_xu_task_clear_protocol',
                                    '-o', str(binary), str(source),
                                    *[str(perips/name) for name in names]],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   universal_newlines=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout+built.stderr)
            cases = [(0, None), (1, 'incomplete clear before first source accept'),
                     (2, 'incomplete/unknown clear word'), (3, 'nonzero/duplicate W clear'),
                     (4, 'undrained W/X clear strobe')]
            for mode, rejected in cases:
                with self.subTest(mode=mode):
                    result = subprocess.run(['vvp', str(binary), '+MODE='+str(mode)],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            universal_newlines=True, timeout=60)
                    log = result.stdout+result.stderr
                    if rejected is None:
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('XU_CLEAR_MMIO_PROBE_PASS', log)
                        self.assertIn('all_w_x_bias_storage_zero=1', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('XU_CLEAR_REJECT '+rejected, log)
                        self.assertNotIn('XU_CLEAR_MMIO_PROBE_PASS', log)


if __name__ == '__main__':
    unittest.main()
