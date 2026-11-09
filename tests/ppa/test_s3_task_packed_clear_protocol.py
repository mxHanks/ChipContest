"""Optional public PACK32 clearing probes; real wrapper, no full-SoC/PPA PASS.

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
    's3_task_packed_clear_protocol', ROOT/'tools/ppa/s3_task_packed_clear_protocol.py')
clear = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clear)


@contextmanager
def native_artifact_dir(label):
    """Keep source, binaries and raw logs when the isolated campaign asks."""
    root = os.environ.get('S3_PACKED_CLEAR_TEST_ARTIFACT_DIR')
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
  wire xu_direct_capable, xu_direct_valid, xu_direct_commit_ready, xu_direct_commit_err;
  wire [255:0] xu_direct_payload;
  wire [31:0] xu_direct_status;
  wire xu_direct_claim=0, xu_direct_ready=0, xu_direct_commit=0;
  accel_icb_slave dut(.*);
  reg first_source_request=0, payload_phase=0, nice_idle=1;
  integer bank, a, lane, mode=0, accepted=0, retired=0;
  reg armed=0, expected_error=0;
  integer low_commits=0, high_commits=0;
  reg [31:0] dummy;
  reg [31:0] response;
@OBSERVER@
  always @(posedge clk) if (rst_n) begin
    if (armed) s3_observe_task_clear(first_source_request,nice_idle,payload_phase);
    if (armed && cmd_valid && cmd_ready) accepted=accepted+1;
    if (armed && rsp_valid && rsp_ready) retired=retired+1;
  end

  task automatic transfer(input bit reading,input [11:0] offset,
                          input [31:0] data,input [3:0] mask,
                          output [31:0] word);
    integer elapsed, before_physical;
    reg [31:0] held;
    begin
      @(negedge clk);
      cmd_valid=1; cmd_read=reading; cmd_addr={20'h10042,offset};
      cmd_wdata=data; cmd_wmask=mask; rsp_ready=0;
      elapsed=0; before_physical=s3_clear_w_count+s3_clear_x_count;
      @(posedge clk);
      while (cmd_ready!==1'b1) begin
        elapsed=elapsed+1;
        if (elapsed>2048) $fatal(1,"probe command deadline offset=%h",offset);
        @(posedge clk);
      end
      #1;
      if (armed && !reading && (offset==12'h05c || offset==12'h068) && mask==15 && data==0) begin
        if (rsp_valid || cmd_ready || s3_clear_w_count+s3_clear_x_count!=before_physical)
          $fatal(1,"packed clear replied/wrote before the first physical edge");
      end
      @(negedge clk); cmd_valid=0;
      if (armed && !reading && (offset==12'h05c || offset==12'h068) && mask==15 && data==0) begin
        @(posedge clk); #1;
        if (rsp_valid || cmd_ready || s3_clear_w_count+s3_clear_x_count!=before_physical+1)
          $fatal(1,"packed clear low physical beat did not precede response");
        @(posedge clk); #1;
        if (!rsp_valid || rsp_err || s3_clear_w_count+s3_clear_x_count!=before_physical+2)
          $fatal(1,"packed clear high physical beat did not precede response");
      end
      // An early request is deliberately rejected before SRAM clear completes.
      if (armed && mode==8 && offset==12'h0e8) first_source_request=1;
      elapsed=0;
      while (rsp_valid!==1'b1) begin
        @(posedge clk); #1; elapsed=elapsed+1;
        if (elapsed>2048) $fatal(1,"probe response deadline offset=%h",offset);
      end
      if (rsp_err!==expected_error) $fatal(1,"probe unexpected MMIO error offset=%h got=%b expected=%b",offset,rsp_err,expected_error);
      held=rsp_rdata;
      repeat (2) begin
        @(posedge clk); #1;
        if (rsp_valid!==1'b1 || rsp_err!==expected_error || rsp_rdata!==held)
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
@PREFILL_TASKS@
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    repeat (4) @(negedge clk);
    rst_n=1;
    @(negedge clk);
    prefill_nonzero();
    if (mode>=20 && mode<=22) reset_packed_boundary(mode-20);
    if (mode==23) exercise_errors();
    check_nonzero_prestate();
    armed=1;
    if (mode==7) begin
      first_source_request=1;
      @(posedge clk); #1;
      $fatal(1,"missing-clear negative unexpectedly accepted");
    end
    get('h000,32'hacce2030);
    get('h050,32'h58550003);
    get('h00c,0);
    get('h0ec,@BIAS_CAPABILITY@);
    get('h070,32'h58530003); get('h074,32'h58500003);
    put('h040,0,15);
    put('h054,0,15);
    for (a=0;a<8192;a=a+1) begin
      if (mode==17 && a==8191) begin
        // Completion proof before the last pair is forbidden even though the
        // omitted physical words were already nonzero before observer arming.
        get('h06c,0);
      end
      if (!(mode==1 && a==8191)) begin
        if (mode==14 && a==8191) begin
          @(negedge clk); cmd_valid=1; cmd_read=0;
          cmd_addr=32'h1004205c; cmd_wdata=0; cmd_wmask=15; rsp_ready=0;
          @(posedge clk); #1;
          @(negedge clk); cmd_valid=0;
          @(posedge clk); #1; // Low physical beat has committed; high is pending.
          @(negedge clk); first_source_request=1;
          @(posedge clk); #1;
          $fatal(1,"early packed source negative unexpectedly accepted");
        end
        if (mode==16 && a==1) put('h054,0,15);
        put('h05c,(mode==4 && a==0)?1:((mode==15 && a==0)?32'h00010000:0),
            (mode==3 && a==0)?0:15);
      end
    end
@BIAS_CLEAR@
    for (lane=0;lane<8;lane=lane+1) begin
      put('h028,lane,15); put('h02c,0,15);
      put('h030,0,(mode==3 && lane==0)?0:15);
    end
    put('h060,0,15);
    for (a=0;a<32;a=a+1) begin
      if (mode==5 && a==31) begin
        @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h10042068;
        cmd_wdata=0; cmd_wmask=15; rsp_ready=0;
        @(posedge clk); #1;
        @(negedge clk); cmd_valid=0;
        @(posedge clk); #1;
        @(posedge clk); #1; // Physical writes finished, response remains blocked.
        @(negedge clk); first_source_request=1;
        @(posedge clk); #1;
        $fatal(1,"undrained negative unexpectedly accepted");
      end else put('h068,0,15);
    end
    if (mode==9) put('h068,0,15);
    // The real frozen main performs ABI reads before its first W source load.
    // A separate final STATUS proof ends clear, without treating these original
    // reads as another clear recipe or permitting an uncounted parameter write.
    if (mode!=10) begin
      if (mode!=18) get('h06c,0);
      get('h00c,0);
    end
    if (mode==11) put('h060,0,15);
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
    $display("S3_PACKED_CLEAR_MMIO_PROBE_PASS mode_sram=@MODE_SRAM@ writes=%0d checked_w=16384 checked_x=64 checked_bias=256 checked_legacy=8 clear_cycles=%0d fifo_payload_physical_zero=UNPROVEN policy=REVIEW_PENDING",
      s3_clear_writes,s3_clear_last_response-s3_clear_first+1);
    $finish;
  end
  initial begin #30000000; $fatal(1,"probe watchdog"); end
endmodule
'''.replace('@OBSERVER@', clear.observer_declarations('dut', use_bias_sram=use_sram)).replace(
        '@PHYSICAL_CHECKS@', '\n'.join(checks)).replace(
        '@PREFILL_TASKS@', prefill_tasks(use_sram)).replace(
        '@BIAS_CAPABILITY@', "32'h42530001" if use_sram else "32'b0").replace(
        '@MODE_SRAM@', '1' if use_sram else '0').replace(
        '@BIAS_CLEAR@', '''    if (mode!=2) put('h0e8,1,15);''' if use_sram else '''
    for (a=0;a<256;a=a+1) begin
      put('h044,a,15); put('h048,0,15);
      if (!(mode==2 && a==255)) put('h04c,0,15);
    end''')


def prefill_tasks(use_sram):
    """Only public MMIO drives the DUT. Deep hierarchy is exclusively read-only."""
    checks = []
    for bank in range(8):
        for half in range(2):
            checks.append(f'''
      for (a=0;a<1024;a=a+1)
        if (dut.u_linear_compute_core.core.weightBanks.banks_{bank}.sram{half}.mem_ext.Memory[a]!==16'h1357)
          $fatal(1,"nonzero prestate W not independently covered bank={bank} half={half} addr=%0d",a);
''')
    for address in range(64):
        checks.append(f'''
      if (dut.u_linear_compute_core.core.xBuffer.data_{address}!==16'h2468)
        $fatal(1,"nonzero prestate X missing addr={address}");
''')
    for lane in range(8):
        checks.append(f'''
      if (dut.bias_regs[{lane}]!==40'h3c44556677)
        $fatal(1,"nonzero prestate legacy bias missing lane={lane}");
''')
    if use_sram:
        checks.append('''
      for (a=0;a<768;a=a+1) begin
        case (a%3)
          0: if (dut.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'h4938)
               $fatal(1,"nonzero prestate bias word0 missing addr=%0d",a);
          1: if (dut.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'h6b5a)
               $fatal(1,"nonzero prestate bias word1 missing addr=%0d",a);
          2: if (dut.u_linear_compute_core.biasCache.memory.mem_ext.Memory[a]!==16'h0027)
               $fatal(1,"nonzero prestate bias word2 missing addr=%0d",a);
        endcase
      end
''')
        for slot in range(2):
            for lane in range(8):
                checks.append(f'''
      if (dut.u_linear_compute_core.biasCache.slotData_{slot}_{lane}!==40'h276b5a4938)
        $fatal(1,"nonzero prestate staging missing slot={slot} lane={lane}");
''')
    else:
        for bank in range(8):
            for group in range(32):
                checks.append(f'''
      if (dut.u_linear_compute_core.biasCache.banks_{bank}_{group}!==40'h276b5a4938)
        $fatal(1,"nonzero prestate register bias missing");
''')
    bias_init = "    put('h0e8,1,15);" if use_sram else ''
    return r'''
  task automatic wait_compute;
    integer polls;
    reg [31:0] status;
    begin
      status=0; polls=0;
      while (!status[1]) begin
        transfer(1,'h00c,0,0,status); polls=polls+1;
        if (polls>128) $fatal(1,"nonzero prefill compute timed out");
      end
      if (status[0]) $fatal(1,"nonzero prefill compute still busy");
      put('h00c,2,15);
    end
  endtask

  task automatic prefill_nonzero;
    integer b, a, l;
    begin
      put('h040,0,15);
      // Independent scalar mapping, not the packed cursor map under test.
      for (b=0;b<8;b=b+1) begin
        put('h01c,b,15);
        for (a=0;a<2048;a=a+1) begin
          put('h020,a,15); put('h024,32'h1357,15);
        end
      end
      for (a=0;a<64;a=a+1) begin
        put('h014,a,15); put('h018,32'h2468,15);
      end
@BIAS_INIT@
      for (a=0;a<256;a=a+1) begin
        put('h044,a,15); put('h048,32'h6b5a4938,15); put('h04c,32'h27,15);
      end
      for (l=0;l<8;l=l+1) begin
        put('h028,l,15); put('h02c,32'h44556677,15); put('h030,32'h3c,15);
      end
      // Public manual group requests fill both staging slots with nonzero data.
      put('h040,1,15);
      put('h010,0,15); put('h008,1,15); wait_compute();
      put('h010,1,15); put('h008,1,15); wait_compute();
      put('h040,0,15);
      // The initial clear ABI requires fresh control state, independent of data.
      put('h010,0,15);
      get('h00c,0); get('h06c,0);
    end
  endtask

  task automatic check_nonzero_prestate;
    integer a;
    begin
@NONZERO_CHECKS@
      $display("S3_PACKED_CLEAR_NONZERO_PRESTATE_PASS W=16384 X=64 bias_words=@BIAS_WORDS@ legacy_bits=320 staging_bits=@STAGING_BITS@ public_mmio_only=1");
    end
  endtask

  task automatic reset_packed_boundary(input integer boundary);
    begin
      put('h054,0,15);
      @(negedge clk); cmd_valid=1; cmd_read=0; cmd_addr=32'h1004205c;
      cmd_wdata=32'hbbbbaaaa; cmd_wmask=15; rsp_ready=0;
      @(posedge clk); #1; // Accepted, no physical write yet.
      @(negedge clk); cmd_valid=0;
      if (boundary>=1) begin @(posedge clk); #1; @(negedge clk); end
      if (boundary>=2) begin @(posedge clk); #1; @(negedge clk); end
      rst_n=0;
      repeat(2) @(negedge clk);
      rst_n=1;
      @(negedge clk);
      if (rsp_valid!==0 || dut.stream_pending!==0 || dut.w_cursor!==0)
        $fatal(1,"reset did not abort outstanding packed transaction");
      if (dut.u_linear_compute_core.core.weightBanks.banks_0.sram0.mem_ext.Memory[0] !==
          (boundary>=1 ? 16'haaaa : 16'h1357))
        $fatal(1,"reset boundary low beat physical work differs");
      if (dut.u_linear_compute_core.core.weightBanks.banks_1.sram0.mem_ext.Memory[0] !==
          (boundary>=2 ? 16'hbbbb : 16'h1357))
        $fatal(1,"reset boundary high beat physical work differs");
      $display("S3_PACKED_RESET_BOUNDARY_PASS boundary=%0d",boundary);
      // Reset does not erase operand memories. Refill every location publicly
      // before arming a fresh, complete clear proof after the abort.
      prefill_nonzero();
    end
  endtask

  task automatic exercise_errors;
    begin
      expected_error=1;
      put('h054,0,0);
      expected_error=0; put('h054,1,15);
      expected_error=1; put('h05c,32'hdeadbeef,15);
      expected_error=0; put('h054,16384,15);
      expected_error=1; put('h05c,32'hdeadbeef,15);
      expected_error=0; put('h054,0,15);
      expected_error=1; put('h05c,32'hdeadbeef,7);
      expected_error=0; put('h060,63,15);
      expected_error=1; put('h068,32'hdeadbeef,15);
      expected_error=0; put('h060,64,15);
      expected_error=1; put('h068,32'hdeadbeef,15);
      expected_error=0; put('h060,0,15);
      expected_error=1; put('h068,32'hdeadbeef,3);
      expected_error=0;
      get('h06c,2); put('h06c,2,1); get('h06c,0);
      // Busy rejection on the real compute engine, before observer arming.
      put('h040,0,15); put('h010,0,15); put('h008,1,15);
      expected_error=1;
      put('h05c,32'hdeadbeef,15); put('h068,32'hdeadbeef,15);
      expected_error=0; wait_compute();
      get('h06c,2); put('h06c,2,1); get('h06c,0);
      $display("S3_PACKED_ERROR_ATOMICITY_PASS masks_odd_bounds_busy=1");
    end
  endtask
'''.replace('@BIAS_INIT@', bias_init).replace('@NONZERO_CHECKS@', ''.join(checks)).replace(
        '@BIAS_WORDS@', '768' if use_sram else '0').replace(
        '@STAGING_BITS@', '640' if use_sram else '0')


class S3TaskPackedClearGenerationTests(unittest.TestCase):
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


class S3TaskPackedClearNativeTests(unittest.TestCase):
    def test_packed_frozen_wrapper_riscv_compile(self):
        prefix = os.environ.get('S3_RISCV_PREFIX',
            '/usr/bin/riscv64-unknown-elf-')
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

    def _actual_wrapper(self, use_sram, cases, mutation=None):
        self.assertIsNotNone(shutil.which('iverilog'), 'Icarus is required; run on own Linux')
        self.assertIsNotNone(shutil.which('vvp'), 'vvp is required; run on own Linux')
        perips = ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'
        variant = None
        if not use_sram:
            self.assertTrue('S3_REGISTER_BIAS_RTL_DIR' in os.environ,
                          'Set generated register-bias RTL directory explicitly; do not skip fallback')
            variant = Path(os.environ['S3_REGISTER_BIAS_RTL_DIR'])
            self.assertTrue((variant/'LinearAutoGroupCore.sv').is_file())
        names = ['accel_icb_slave.v', 'LinearAutoGroupCore.sv', 'BiasSramPrefetch.sv',
                 'BiasBankCache.sv', 'LinearComputeCore.sv', 'DotProductEngine.sv',
                 'MacController.sv', 'MacPEArray.sv', 'MacPE.sv', 'XRowBuffer.sv',
                 'WeightBankArray.sv', 'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv']
        sources = [variant/name if variant and (variant/name).is_file() else perips/name for name in names]
        with native_artifact_dir(mutation[0] if mutation else ('sram' if use_sram else 'registers')) as temporary:
            source, binary = temporary/'tb.sv', temporary/'clear.vvp'
            if mutation:
                label, name, before, after = mutation
                original = next(p for p in sources if p.name == name)
                content = original.read_text()
                self.assertEqual(content.count(before), 1)
                changed = temporary/name
                changed.write_text(content.replace(before, after))
                sources = [changed if p == original else p for p in sources]
                (temporary/'mutation.json').write_text(json.dumps(dict(
                    purpose='Negative fault injection into an isolated real RTL copy; not a production or full-SoC result',
                    original=str(original), original_sha256=clear.sha(original),
                    mutant_sha256=clear.sha(changed), before=before, after=after), indent=2)+'\n')
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
                        self.assertIn('S3_PACKED_CLEAR_MMIO_PROBE_PASS', log)
                        self.assertIn('S3_TASK_CLEAR_OBSERVED mode_sram='+str(int(use_sram)), log)
                        self.assertIn('fifo_payload_physical_zero=UNPROVEN', log)
                    else:
                        self.assertNotEqual(result.returncode, 0, log)
                        self.assertIn('S3_CLEAR_REJECT '+rejected, log)
                        self.assertNotIn('S3_PACKED_CLEAR_MMIO_PROBE_PASS', log)

    def test_actual_sram_wrapper_and_rejection_paths(self):
        self._actual_wrapper(True, [
            (0, None),
            (1, 'incomplete clear before first source request'),
            (2, 'incomplete clear before first source request'),
            (3, 'missing ABI or incomplete/unknown clear word'),
            (4, 'nonzero/duplicate W packed command'),
            (5, 'undrained clear before first source request'),
            (6, 'NICE not idle before task request'),
            (7, 'incomplete clear before first source request'),
            (8, 'undrained clear before first source request'),
            (9, 'nonzero/duplicate X packed command'),
            (10, 'missing clear completion proof before first source request'),
            (11, 'parameter write before first source request'),
            (12, 'unexpected ABI preflight read'),
            (14, 'undrained clear before first source request'),
            (15, 'nonzero/duplicate W packed command'),
            (16, 'W cursor initialization'),
            (17, 'incomplete clear before first source request'),
            (18, 'repeated ABI read'),
            (20, None), (21, None), (22, None), (23, None)])

    def test_actual_physical_write_faults_rejected_after_nonzero_prefill(self):
        mutations = [
            ('missing-bank7-zero-write', 'WeightBankArray.sv',
             ".io_wen   (io_loadWen & (&io_loadBank))",
             ".io_wen   (io_loadWen & (&io_loadBank) & (|io_loadData))",
             'physical W strobe cardinality'),
            ('missing-x0-zero-write', 'XRowBuffer.sv',
             "if (io_wen & io_waddr == 6'h0)",
             "if (io_wen & io_waddr == 6'h0 & (|io_wdata))",
             'physical X poststate address=0'),
            ('missing-legacy-high-zero-write', 'accel_icb_slave.v',
             'if (cmd_wmask[0])\n                                    bias_regs[bias_index_reg][39:32]',
             'if (cmd_wmask[0] && (|cmd_wdata[7:0]))\n                                    bias_regs[bias_index_reg][39:32]',
             'physical legacy bias poststate lane=0')]
        for label, name, before, after, rejection in mutations:
            with self.subTest(mutation=label):
                self._actual_wrapper(True, [(0, rejection)], (label, name, before, after))

    @unittest.skipUnless(os.environ.get('S3_REGISTER_BIAS_RTL_DIR'),
                         'Optional register-bias generated variant not supplied; SRAM is the selected candidate')
    def test_actual_register_wrapper_fallback(self):
        self._actual_wrapper(False, [
            (0, None), (2, 'incomplete clear before first source request')])


if __name__ == '__main__':
    unittest.main()
