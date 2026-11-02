"""Opt-in public-MMIO clearing and request-window evidence, never qualification."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


collector = module('xu_clear_activity_collector', ROOT / 'tools/ppa/xu_soc_task_activity.py')
physical = module('xu_clear_physical_probe', ROOT / 'tests/ppa/test_xu_task_clear_protocol.py')
EVIDENCE = Path(os.environ['XU_TASK_ACTIVITY_TEST_EVIDENCE']) if os.environ.get('XU_TASK_ACTIVITY_TEST_EVIDENCE') else None


def evidence(name, value):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / name).write_text(value)


def run(command, cwd, name, timeout=120):
    result = subprocess.run(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            universal_newlines=True, timeout=timeout)
    evidence(name, json.dumps(dict(command=command, cwd=str(cwd), returncode=result.returncode)) + '\n' + result.stdout)
    return result


def blocked_request_probe():
    return r'''
`timescale 1ns/1fs
module xu_clear_mock_accel;
  reg cmd_valid=0,cmd_ready=1,cmd_read=0,busy=0,cache_enable=0,core_start=0;
  reg w_load_wen=0,x_load_wen=0,rsp_valid=0;
  reg [31:0] cmd_addr=0,cmd_wdata=0;
  reg [3:0] cmd_wmask=15;
  reg [2:0] w_bank_reg=0,bias_index_reg=0;
  reg [10:0] w_addr_reg=0;
  reg [7:0] cache_addr_reg=0;
  reg [5:0] x_addr_reg=0;
  reg [4:0] group_reg=0;
endmodule
module tb_xu_clear_request_probe;
  xu_clear_mock_accel accel();
  `define ACCEL accel
  localparam BASE=32'h90000000;
  reg cmd_valid=0,cmd_read=1,cmd_ready=0;
  reg [31:0] cmd_addr=BASE;
  integer cycles=0;
  reg [15:0] w[0:16383],x[0:6335];
  reg [39:0] bias[0:255];
@DECLARATIONS@
  integer i,b,a,r,g,index,mode;
  task step;
    begin #6.666667; cycles=cycles+1; xu_observe_clear_window(); end
  endtask
  task put(input [11:0] address,input [31:0] data);
    begin accel.cmd_addr=address;accel.cmd_wdata=data;accel.cmd_valid=1;step();end
  endtask
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    xu_global_task=7;
    for(i=0;i<16384;i=i+1) begin w[i]=i*7;xu_w_seen[i]=0;end
    for(i=0;i<6336;i=i+1) x[i]=i*3;
    for(i=0;i<256;i=i+1) begin bias[i]=40'h1230000000+i;xu_bias_seen[i]=0;end
    put('h040,0);
    for(b=0;b<8;b=b+1) begin
      put('h01c,b);accel.w_bank_reg=b;
      for(a=0;a<2048;a=a+1) begin
        put('h020,a);accel.w_addr_reg=a;put('h024,0);
      end
    end
    for(a=0;a<256;a=a+1) begin
      put('h044,a);accel.cache_addr_reg=a;put('h048,0);put('h04c,0);
    end
    for(a=0;a<8;a=a+1) begin
      put('h028,a);accel.bias_index_reg=a;put('h02c,0);put('h030,0);
    end
    for(a=0;a<64;a=a+1) begin
      put('h014,a);accel.x_addr_reg=a;put('h018,0);
    end
    accel.cmd_valid=0;
    if(xu_w_count!=0 || xu_bias_count!=0 || xu_x_count!=0 || xu_saif_started)
      $fatal(1,"clear writes leaked into payload/activity window");
    put('h01c,0);accel.w_bank_reg=0;
    if(mode!=4) begin put('h020,0);accel.w_addr_reg=0;end
    if(mode==3) put('h024,0);
    accel.cmd_valid=0;
    cmd_valid=1;
    step();
    if(!xu_saif_started || !xu_payload_phase || xu_request_cycle!=cycles || xu_accept_cycle!=-1)
      $fatal(1,"blocked first request did not open formal window");
    if(mode==1) cmd_addr=BASE+4;
    if(mode==2) cmd_valid=0;
    step();step();
    cmd_ready=1;step();cmd_valid=0;
    if(xu_initial_wait!=3 || xu_accept_cycle-xu_request_cycle!=3)
      $fatal(1,"initial source waiting was not counted");
    for(b=0;b<8;b=b+1) for(a=0;a<2048;a=a+1) begin
      accel.w_bank_reg=b;accel.w_addr_reg=a;
      index=(a%64)*256+(a/64)*8+b;put('h024,w[index]);
    end
    for(i=0;i<256;i=i+1) begin
      accel.cache_addr_reg=i;put('h048,bias[i][31:0]);put('h04c,bias[i][39:32]);
    end
    accel.cache_enable=1;
    for(r=0;r<99;r=r+1) begin
      for(a=0;a<64;a=a+1) begin
        accel.x_addr_reg=a;put('h018,x[r*64+a]);
      end
      for(g=0;g<32;g=g+1) begin accel.group_reg=g;put('h008,1);end
    end
    if(xu_clear_writes!=33697 || xu_w_count!=16384 || xu_bias_count!=256 ||
       xu_x_count!=6336 || xu_rows!=99 || xu_starts!=3168)
      $fatal(1,"clear/payload coverage changed");
    $display("XU_CLEAR_REQUEST_UPLOAD_PROBE_PASS task=7 clear_writes=33697 initial_wait_cycles=3 w=16384 bias=256 x=6336 rows=99 starts=3168");
    $finish;
  end
endmodule
'''.replace('@DECLARATIONS@', collector.UPLOAD_DECLARATIONS + collector.clear_observer_declarations() + collector.CLEAR_WINDOW_DECLARATIONS)


class ClearActivityTests(unittest.TestCase):
    def test_python36_syntax(self):
        for path in (Path(collector.__file__), Path(collector.clear.__file__)):
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 6))

    @unittest.skipUnless(shutil.which('riscv64-unknown-elf-gcc'), 'RISC-V compiler required')
    def test_actual_riscv_build_records_wrapper_and_exact_frozen_inputs(self):
        with tempfile.TemporaryDirectory(prefix='xu-clear-fw-') as temporary:
            out = Path(temporary)
            report = {}
            main = collector.soc.TESTS / 'firmware/main.c'
            before = collector.base.sha(main)
            target = collector.compile_clear_firmware(out, 'riscv64-unknown-elf-', 'bias-hw-window',
                                                       '-O2', 'both-unroll-no-masks', report, before)
            build = report['firmware_build']
            self.assertEqual(build['frozen_main']['sha256'], before)
            self.assertEqual(collector.base.sha(main), before)
            self.assertEqual(build['elf_sha256'], collector.base.sha(target))
            self.assertEqual([Path(item['path']).name for item in build['compile_sources']],
                             ['start.S', 'xu_clear_main.c', 'accel.c'])
            self.assertIn(str(out / 'xu_clear_main.c'), build['command'])
            self.assertNotIn(str(main), build['command'])
            self.assertIn('#include "' + str(main) + '"', (out / 'xu_clear_main.c').read_text())
            self.assertGreater(build['memory']['itcm_remaining_bytes'], 0)
            evidence('clear-firmware-build.json', json.dumps(build, indent=2)+'\n')
            for name in ('xu_clear_main.c', 'xu_clear_observer.svh', 'firmware-build.log',
                         'firmware-sections.log', 'firmware-symbols.log', 'firmware.dump'):
                evidence(name, (out / name).read_text())

    @unittest.skipUnless(shutil.which('riscv64-unknown-elf-gcc') and os.environ.get('XU_TASK_ACTIVITY_VENDOR_MODEL'),
                         'RISC-V compiler and explicit private vendor-model path required')
    def test_prepare_only_real_global_seven_is_explicitly_partial(self):
        with tempfile.TemporaryDirectory(prefix='xu-clear-prepare-') as temporary:
            out = Path(temporary)
            # Identity-only placeholder: prepare never simulates this netlist or claims PPA.
            netlist = out / 'identity-only-not-simulated.v'
            netlist.write_text('// synthetic host-test netlist identity, never simulated\n')
            destination = out / 'partial'
            command = [sys.executable, str(collector.HERE / 'xu_soc_task_activity.py'),
                       '--out', str(destination), '--vendor-model', os.environ['XU_TASK_ACTIVITY_VENDOR_MODEL'],
                       '--netlist', str(netlist), '--constraints', str(collector.HERE / 'xu_full_soc.sdc'),
                       '--clear-task-before-window', '--task-ids', '7', '--prepare-only']
            result = run(command, out, 'clear-partial-prepare.log', 180)
            self.assertEqual(result.returncode, 0, result.stdout)
            report = json.loads((destination / 'result.json').read_text())
            self.assertEqual(report['status'], 'PARTIAL_PREPARED_NOT_SIMULATED')
            self.assertFalse(report['taskset_complete'])
            self.assertEqual(report['requested_task_ids'], [7])
            self.assertEqual([task['task_id'] for task in report['tasks']], [7])
            manifest = json.loads((destination / 'task_07/vectors/input-manifest.json').read_text())
            self.assertEqual(manifest['global_task_id'], 7)
            self.assertEqual(manifest['original_layer'], 'layer_07')
            self.assertEqual(manifest['simulator_layer'], 'layer_00')
            self.assertEqual(report['configuration']['analysis_sdc_sha256'],
                             collector.base.sha(collector.HERE / 'xu_full_soc.sdc'))
            self.assertEqual(report['configuration']['task_clear_recipe']['clear_counts']['accepted_writes'], 33697)
            self.assertEqual(report['firmware_build']['compile_sources'][1]['path'],
                             str(destination / 'firmware/xu_clear_main.c'))
            self.assertNotIn('PASS', report['status'])
            evidence('clear-partial-prepare-result.json', json.dumps(report, indent=2)+'\n')

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus required')
    def test_actual_public_mmio_clear_positive_and_destructive_cases_use_collector_observer(self):
        perips = ROOT / 'third-party/e203_hbirdv2/rtl/e203/perips'
        names = ['BiasBankCache.sv', 'LinearCachedCore.sv', 'LinearComputeCore.sv',
                 'DotProductEngine.sv', 'MacController.sv', 'MacPEArray.sv',
                 'MacPE.sv', 'XRowBuffer.sv', 'WeightBankArray.sv',
                 'WeightBank.sv', 'Sram1024x16.sv', 'mem_1024x16.sv', 'accel_icb_slave.v']
        # Reuse physical-content/arithmetic probe, swapping only the integrated observer.
        source_text = physical.probe().replace(physical.clear.observer_declarations('dut'),
                                               collector.clear_observer_declarations().replace('`ACCEL', 'dut'))
        source_text = source_text.replace('source_accept', 'source_request').replace('source accept', 'source request')
        source_text = source_text.replace('    @(negedge clk); source_request=1;',
                                          "    put('h01c,0,15); put('h020,0,15);\n    @(negedge clk); source_request=1;")
        evidence('tb_xu_collector_clear_mmio.sv', source_text)
        with tempfile.TemporaryDirectory(prefix='xu-clear-real-mmio-') as temporary:
            out = Path(temporary)
            source, binary = out / 'probe.sv', out / 'probe.vvp'
            source.write_text(source_text)
            built = run(['iverilog', '-g2012', '-s', 'tb_xu_task_clear_protocol', '-o', str(binary),
                         str(source)] + [str(perips/name) for name in names], out, 'clear-mmio-build.log')
            self.assertEqual(built.returncode, 0, built.stdout)
            cases = [(0, None), (1, 'incomplete clear before first source request'),
                     (2, 'incomplete/unknown clear word'), (3, 'nonzero/duplicate W clear'),
                     (4, 'undrained W/X clear strobe')]
            for mode, rejected in cases:
                result = run(['vvp', str(binary), '+MODE='+str(mode)], out, 'clear-mmio-mode-%d.log' % mode)
                if rejected is None:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn('XU_CLEAR_MMIO_PROBE_PASS', result.stdout)
                    self.assertIn('all_w_x_bias_storage_zero=1', result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn('XU_CLEAR_REJECT '+rejected, result.stdout)

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus required')
    def test_blocked_first_request_extends_formal_window_and_keeps_all_payload_checks(self):
        source_text = blocked_request_probe()
        evidence('tb_xu_clear_request_probe.sv', source_text)
        with tempfile.TemporaryDirectory(prefix='xu-clear-request-') as temporary:
            out = Path(temporary)
            source, binary = out / 'probe.sv', out / 'probe.vvp'
            source.write_text(source_text)
            built = run(['iverilog', '-g2012', '-DXU_TASK_ACTIVITY_HOST_CHECK', '-s',
                         'tb_xu_clear_request_probe', '-o', str(binary), str(source)], out, 'clear-request-build.log')
            self.assertEqual(built.returncode, 0, built.stdout)
            for mode in range(5):
                result = run(['vvp', str(binary), '+MODE='+str(mode)], out, 'clear-request-mode-%d.log' % mode)
                if mode == 0:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn('XU_CLEAR_REQUEST_UPLOAD_PROBE_PASS', result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    expected = ('first source request changed before acceptance' if mode in (1, 2) else
                                'unexpected task data/setup before first source request' if mode == 3 else
                                'missing original task destination setup before source request')
                    self.assertIn(expected, result.stdout)

    @unittest.skipUnless(shutil.which('iverilog') and os.environ.get('XU_TASK_ACTIVITY_VENDOR_MODEL'),
                         'Icarus and explicit private vendor-model path required')
    def test_full_generated_336_macro_tb_elaborates_with_original_private_vendor(self):
        vendor = Path(os.environ['XU_TASK_ACTIVITY_VENDOR_MODEL']).resolve()
        before = collector.identity(vendor)
        with tempfile.TemporaryDirectory(prefix='xu-clear-full-soc-') as temporary:
            out = Path(temporary)
            source = out / 'tb_xu_soc_task_clear_activity.sv'
            source.write_text(collector.generate_tb(True))
            sources = collector.collect_sources(source, vendor, collector.HERE / 'xu_weight_sram_adapter.sv')
            filelist = out / 'rtl.f'
            filelist.write_text('\n'.join(str(path) for path in sources)+'\n')
            command = ['iverilog', '-g2012', '-s', 'tb_xu_soc_ppa', '-DDISABLE_SV_ASSERTION=1',
                       '-DARM_UD_MODEL', '-DXU_TASK_ACTIVITY_HOST_CHECK']
            command += ['-I'+str(collector.base.RTL / name) for name in ('core', 'perips', 'perips/apb_i2c')]
            command += ['-o', str(out / 'soc.vvp'), '-f', str(filelist)]
            result = run(command, out, 'clear-full-soc-336-compile.log', 180)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(collector.identity(vendor), before)
            evidence('tb_xu_soc_task_clear_activity.sv', source.read_text())
            evidence('clear-full-soc-source-sha256.json', json.dumps(
                dict(status='ELABORATED_NOT_SIMULATED', vendor=before,
                     source_sha256={str(path): collector.base.sha(path) for path in sources}), indent=2)+'\n')


if __name__ == '__main__':
    unittest.main()
