"""S3 clear generation and real-wrapper probes; no full-SoC/PPA PASS.

Run native tests on the isolated Linux server. The register fallback requires
S3_REGISTER_BIAS_RTL_DIR to name the explicitly generated register-bias core.
No test substitutes a mocked DUT or writes its internal memories.
"""
import importlib.util
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    's3_task_clear_protocol', ROOT/'tools/ppa/s3_task_clear_protocol.py')
clear = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clear)


@contextmanager
def native_artifact_dir(label):
    """Keep source, binaries and raw logs when the isolated campaign asks."""
    root = os.environ.get('S3_CLEAR_TEST_ARTIFACT_DIR')
    if root:
        path = Path(root)/label
        path.mkdir(parents=True, exist_ok=False)
        yield path
    else:
        with tempfile.TemporaryDirectory(prefix='s3-clear-'+label+'-') as temporary:
            yield Path(temporary)


def probe(use_sram=True):
    """Public MMIO writes; hierarchy is observation only, never a DUT driver."""
    checks = []
    for bank in range(8):
        for half in range(2):
            checks.append('''    for (a=0;a<1024;a=a+1)
      if (dut.u_linear_compute_core.core.weightBanks.banks_%d.sram%d.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical W not zero bank=%d half=%d address=%%0d",a);'''
                          % (bank, half, bank, half))
    for address in range(64):
        checks.append('''    if (dut.u_linear_compute_core.core.xBuffer.data_%d!==16'b0)
      $fatal(1,"physical X not zero address=%d");''' % (address, address))
    if use_sram:
        checks.append('''    for (a=0;a<768;a=a+1)
      if (dut.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'b0)
        $fatal(1,"physical bias SRAM not zero address=%0d",a);''')
        for slot in range(2):
            for lane in range(8):
                checks.append('''    if (dut.u_linear_compute_core.biasCache.slotData_%d_%d!==40'b0)
      $fatal(1,"physical bias staging not zero slot=%d lane=%d");'''
                              % (slot, lane, slot, lane))
    else:
        for bank in range(8):
            for group in range(32):
                checks.append('''    if (dut.u_linear_compute_core.biasCache.banks_%d_%d!==40'b0)
      $fatal(1,"physical register bias not zero bank=%d group=%d");'''
                              % (bank, group, bank, group))
    return r'''
`timescale 1ns/1ps
module tb_s3_task_clear_protocol;
  reg clk=0, rst_n=0, cmd_valid=0, cmd_read=0, rsp_ready=0;
  always #5 clk=~clk;
  reg [31:0] cmd_addr=0, cmd_wdata=0;
  reg [3:0] cmd_wmask=0;
  wire cmd_ready, rsp_valid, rsp_err;
  wire [31:0] rsp_rdata;
  accel_icb_slave dut(.*);
  reg first_source_request=0, payload_phase=0, nice_idle=1;
  integer bank, a, lane, mode=0, accepted=0, retired=0;
  reg [31:0] response;
@OBSERVER@
  always @(posedge clk) if (rst_n) begin
    s3_observe_task_clear(first_source_request,nice_idle,payload_phase);
    if (cmd_valid && cmd_ready) accepted=accepted+1;
    if (rsp_valid && rsp_ready) retired=retired+1;
  end

  task automatic transfer(input bit reading,input [11:0] offset,
                          input [31:0] data,input [3:0] mask,
                          output [31:0] word);
    integer elapsed;
    reg [31:0] held;
    begin
      @(negedge clk);
      cmd_valid=1; cmd_read=reading; cmd_addr={20'h10042,offset};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      elapsed=0;
      @(posedge clk);
      while (cmd_ready!==1'b1) begin
        elapsed=elapsed+1;
        if (elapsed>2048) $fatal(1,"probe command deadline offset=%h",offset);
        @(posedge clk);
      end
      #1;
      @(negedge clk); cmd_valid=0;
      // An early request is deliberately rejected before SRAM clear completes.
      if (mode==8 && offset==12'h0e8) first_source_request=1;
      elapsed=0;
      while (rsp_valid!==1'b1) begin
        @(posedge clk); #1; elapsed=elapsed+1;
        if (elapsed>2048) $fatal(1,"probe response deadline offset=%h",offset);
      end
      if (rsp_err!==1'b0) $fatal(1,"probe unexpected MMIO error offset=%h",offset);
      held=rsp_rdata;
      repeat (2) begin
        @(posedge clk); #1;
        if (rsp_valid!==1'b1 || rsp_err!==1'b0 || rsp_rdata!==held)
          $fatal(1,"probe unstable held response offset=%h",offset);
      end
      word=held;
      @(negedge clk); rsp_ready=1;
      @(posedge clk); #1;
      @(negedge clk); rsp_ready=0;
    end
  endtask
  task automatic put(input [11:0] offset,input [31:0] data,input [3:0] mask);
    reg [31:0] ignored;
    begin transfer(0,offset,data,mask,ignored); end
  endtask
  task automatic get(input [11:0] offset,input [31:0] expected_word);
    reg [31:0] actual;
    begin
      transfer(1,offset,0,0,actual);
      if (actual!==expected_word)
        $fatal(1,"probe ABI mismatch offset=%h got=%h expected=%h",offset,actual,expected_word);
    end
  endtask
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    repeat (4) @(negedge clk);
    rst_n=1;
    @(negedge clk);
    if (mode==7) begin
      first_source_request=1;
      @(posedge clk); #1;
      $fatal(1,"missing-clear negative unexpectedly accepted");
    end
    get('h000,32'hacce2030);
    get('h050,32'h58550003);
    get('h00c,0);
    get('h0ec,@BIAS_CAPABILITY@);
    put('h040,0,15);
    for (bank=0;bank<8;bank=bank+1) begin
      put('h01c,bank,15);
      for (a=0;a<2048;a=a+1) begin
        put('h020,a,15);
        if (!(mode==1 && bank==7 && a==2047))
          put('h024,(mode==4 && bank==0 && a==0)?1:0,15);
      end
    end
@BIAS_CLEAR@
    for (lane=0;lane<8;lane=lane+1) begin
      put('h028,lane,15); put('h02c,0,15);
      put('h030,0,(mode==3 && lane==0)?0:15);
    end
    for (a=0;a<64;a=a+1) begin
      put('h014,a,15);
      if (mode==5 && a==63) begin
        // Source is requested while the final physical X strobe/response lives.
        @(negedge clk);
        cmd_valid=1; cmd_read=0; cmd_addr=32'h10042018;
        cmd_wdata=0; cmd_wmask=15; rsp_ready=1;
        @(posedge clk); #1;
        @(negedge clk); cmd_valid=0; first_source_request=1;
        @(posedge clk); #1;
        $fatal(1,"undrained negative unexpectedly accepted");
      end else put('h018,0,15);
    end
    if (mode==9) put('h018,0,15);
    // The real frozen main performs ABI reads before its first W source load.
    // A separate final STATUS proof ends clear, without treating these original
    // reads as another clear recipe or permitting an uncounted parameter write.
    if (mode!=10) get('h00c,0);
    if (mode==11) put('h014,0,15);
    if (mode==12) get('h048,0);
    if (mode!=10) begin
      get('h000,32'hacce2030); get('h00c,0); get('h050,32'h58550003);
      get('h078,32'h58410001); get('h070,32'h58530003); get('h074,32'h58500003);
    end
    @(negedge clk);
    if (mode==6) nice_idle=0;
    first_source_request=1;
    @(posedge clk); #1;
    if (!payload_phase || !s3_clear_complete)
      $fatal(1,"payload observer not enabled at first source request");
    @(negedge clk); first_source_request=0;
@PHYSICAL_CHECKS@
    for (lane=0;lane<8;lane=lane+1)
      if (dut.bias_regs[lane]!==40'b0) $fatal(1,"physical legacy bias not zero");
    if (accepted!=retired || accepted!=s3_clear_commands+s3_preflight_commands ||
        retired!=s3_clear_responses+s3_preflight_responses)
      $fatal(1,"probe command/response conservation");
    $display("S3_CLEAR_MMIO_PROBE_PASS mode_sram=@MODE_SRAM@ writes=%0d checked_w=16384 checked_x=64 checked_bias=256 checked_legacy=8 clear_cycles=%0d fifo_payload_physical_zero=UNPROVEN policy=REVIEW_PENDING",
      s3_clear_writes,s3_clear_last_response-s3_clear_first+1);
    $finish;
  end
  initial begin #30000000; $fatal(1,"probe watchdog"); end
endmodule
'''.replace('@OBSERVER@', clear.observer_declarations('dut')).replace(
        '@PHYSICAL_CHECKS@', '\n'.join(checks)).replace(
        '@BIAS_CAPABILITY@', "32'h42530001" if use_sram else "32'b0").replace(
        '@MODE_SRAM@', '1' if use_sram else '0').replace(
        '@BIAS_CLEAR@', '''    if (mode!=2) put('h0e8,1,15);''' if use_sram else '''
    for (a=0;a<256;a=a+1) begin
      put('h044,a,15); put('h048,0,15);
      if (!(mode==2 && a==255)) put('h04c,0,15);
    end''')


class S3TaskClearGenerationTests(unittest.TestCase):
    def test_generation_rejects_drift_and_binds_all_outputs(self):
        main = ROOT/'tests/e203/firmware/main.c'
        with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
            clear.firmware_wrapper(main, '0'*64)
        with tempfile.TemporaryDirectory(prefix='s3-clear-generation-') as temporary:
            out = Path(temporary)/'recipe'
            self.assertEqual(clear.main(['--main', str(main), '--main-sha256', clear.sha(main),
                                         '--out', str(out)]), 0)
            record = json.loads((out/'clear-recipe.json').read_text())
            self.assertEqual(record['status'], 'GENERATED_NOT_FULL_SOC_SIMULATED')
            self.assertEqual(record['cache_policy_review_status'], 'REVIEW_PENDING')
            for item in record['outputs']:
                self.assertEqual(clear.sha(item['path']), item['sha256'])
            self.assertEqual(record['frozen_main']['sha256'], clear.sha(main))
            self.assertFalse(record['baseline_modified'])
            self.assertEqual(record['tasks'], 1)
            with self.assertRaises(FileExistsError):
                clear.main(['--main', str(main), '--main-sha256', clear.sha(main), '--out', str(out)])

    def test_observer_rejects_invalid_hierarchy(self):
        for name in ['dut;force x=1', 'dut[0]', 'dut\n.foo', 'dut/foo']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                clear.observer_declarations(name)


class S3TaskClearNativeTests(unittest.TestCase):
    def test_frozen_wrapper_riscv_compile(self):
        prefix = os.environ.get('S3_RISCV_PREFIX',
            '/opt/eda/xilinx/2025.2/Vitis/gnu/riscv/lin/bin/riscv64-unknown-elf-')
        compiler = shutil.which(prefix+'gcc')
        self.assertIsNotNone(compiler, 'Run native clear tests on Linux with S3_RISCV_PREFIX')
        main = ROOT/'tests/e203/firmware/main.c'
        with native_artifact_dir('firmware') as temporary:
            source = temporary/'s3_clear_main.c'
            source.write_text(clear.firmware_wrapper(main, clear.sha(main)))
            result = subprocess.run([compiler, '-march=rv32imac_zicsr2p0_zifencei2p0',
                '-mabi=ilp32', '-O2', '-ffreestanding', '-fno-builtin', '-Wall', '-Wextra',
                '-Werror', '-c', str(source), '-o', str(temporary/'clear.o')],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
            (temporary/'compile.log').write_text(result.stdout+result.stderr)
            (temporary/'compile-result.json').write_text(json.dumps(
                dict(argv=result.args, native_exit=result.returncode), indent=2)+'\n')
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def _actual_wrapper(self, use_sram, cases):
        self.assertIsNotNone(shutil.which('iverilog'), 'Icarus is required; run on own Linux')
        self.assertIsNotNone(shutil.which('vvp'), 'vvp is required; run on own Linux')
        perips = ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'
        variant = None
        if not use_sram:
            self.assertIn('S3_REGISTER_BIAS_RTL_DIR', os.environ,
                          'Set generated register-bias RTL directory explicitly; do not skip fallback')
            variant = Path(os.environ['S3_REGISTER_BIAS_RTL_DIR'])
            self.assertTrue((variant/'LinearAutoGroupCore.sv').is_file())
        names = ['accel_icb_slave.v', 'LinearAutoGroupCore.sv', 'BiasSramPrefetch.sv',
                 'BiasBankCache.sv', 'LinearComputeCore.sv', 'DotProductEngine.sv',
                 'MacController.sv', 'MacPEArray.sv', 'MacPE.sv', 'XRowBuffer.sv',
                 'WeightBankArray.sv', 'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv']
        sources = [variant/name if variant and (variant/name).is_file() else perips/name for name in names]
        with native_artifact_dir('sram' if use_sram else 'registers') as temporary:
            source, binary = temporary/'tb.sv', temporary/'clear.vvp'
            source.write_text(probe(use_sram))
            built = subprocess.run(['iverilog', '-g2012', '-s', 'tb_s3_task_clear_protocol',
                '-o', str(binary), str(source), *[str(p) for p in sources]],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=90)
            (temporary/'compile.log').write_text(built.stdout+built.stderr)
            (temporary/'compile-result.json').write_text(json.dumps(
                dict(argv=built.args, native_exit=built.returncode), indent=2)+'\n')
            self.assertEqual(built.returncode, 0, built.stdout+built.stderr)
            for mode, rejected in cases:
                with self.subTest(sram=use_sram, mode=mode):
                    result = subprocess.run(['vvp', str(binary), '+MODE='+str(mode)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=180)
                    log = result.stdout+result.stderr
                    (temporary/('mode-%02d.log' % mode)).write_text(log)
                    (temporary/('mode-%02d-result.json' % mode)).write_text(json.dumps(
                        dict(argv=result.args, native_exit=result.returncode, expected_rejection=rejected),
                        indent=2)+'\n')
                    print(log, flush=True)
                    if rejected is None:
                        self.assertEqual(result.returncode, 0, log)
                        self.assertIn('S3_CLEAR_MMIO_PROBE_PASS', log)
                        self.assertIn('S3_TASK_CLEAR_OBSERVED mode_sram='+str(int(use_sram)), log)
                        self.assertIn('fifo_payload_physical_zero=UNPROVEN', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('S3_CLEAR_REJECT '+rejected, log)
                        self.assertNotIn('S3_CLEAR_MMIO_PROBE_PASS', log)

    def test_actual_sram_wrapper_and_rejection_paths(self):
        self._actual_wrapper(True, [
            (0, None), (1, 'incomplete clear before first source request'),
            (2, 'incomplete clear before first source request'),
            (3, 'missing ABI or incomplete/unknown clear word'),
            (4, 'nonzero/duplicate W clear'),
            (5, 'undrained clear before first source request'),
            (6, 'NICE not idle before task request'),
            (7, 'incomplete clear before first source request'),
            (8, 'undrained clear before first source request'),
            (9, 'nonzero/duplicate X clear'),
            (10, 'missing clear completion proof before first source request'),
            (11, 'parameter write before first source request'),
            (12, 'unexpected ABI preflight read')])

    def test_actual_register_wrapper_fallback(self):
        self._actual_wrapper(False, [
            (0, None), (2, 'incomplete clear before first source request')])


if __name__ == '__main__':
    unittest.main()
