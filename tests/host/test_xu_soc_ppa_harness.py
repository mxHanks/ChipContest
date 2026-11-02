"""Guard the independent top/TB seam without touching the frozen platform."""
import importlib.util
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_soc_ppa_verify', ROOT / 'tools/ppa/xu_soc_ppa_verify.py')
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class XuSocPpaHarnessTest(unittest.TestCase):
    def test_all_real_pad_ports_preserved_and_forwarded(self):
        source = (ROOT / 'third-party/e203_hbirdv2/rtl/e203/soc/e203_soc_top.v').read_text()
        original = source.split('module e203_soc_top', 1)[1].split(');', 1)[0]
        top = (ROOT / 'tools/ppa/xu_soc_ppa_top.sv').read_text()
        header = top.split('module xu_soc_ppa_top', 1)[1].split(');', 1)[0]
        pattern = r'\b(input|output)\s*(\[[^\]]+\])?\s*(\w+)\s*[,\n]'
        expected = [p for p in re.findall(pattern, original+'\n') if not p[2].startswith('ext_sysmem_')]
        self.assertEqual(len(expected), 37)
        self.assertEqual(re.findall(pattern, header+'\n'), expected)
        for _, _, name in expected:
            self.assertRegex(top, r'\.'+name+r'\('+name+r'\)')
        self.assertIn('.clk(hfextclk), .rst_n(io_pads_aon_erst_n_i_ival)', top)
        self.assertIn('e203_soc_top #(.EXTERNAL_SYSMEM(1)) u_soc', top)

    def test_original_scoreboard_and_performance_boundaries_preserved(self):
        original = VERIFY.TB.read_text()
        generated = VERIFY.generate_tb(True)
        for task in ['observe_performance', 'report_performance', 'reset_performance']:
            def extract(text):
                return text.split('  task '+task+';', 1)[1].split('  endtask', 1)[0]
            expected = extract(original)
            if task == 'observe_performance':
                expected = expected.replace('$dumpvars(0,`ACCEL);', '$dumpvars(0,dut);')
            self.assertEqual(extract(generated), expected)
        begin = '      if (rsp_valid && rsp_ready && final_write_pending) begin'
        end = '      if (`EXU.u_e203_exu_commit.alu_cmt_i_valid'
        original_score = original.split(begin, 1)[1].split(end, 1)[0]
        generated_score = generated.split(begin, 1)[1].split(end, 1)[0]
        # The only behavioral removals are the old endpoint's response drivers.
        original_score = original_score.replace(
            '      // Response retirement is independent of accepting the next command.\n'
            '      if (rsp_valid && rsp_ready) rsp_valid <= 0;\n', '')
        original_score = original_score.replace('        rsp_valid <= cmd_valid;\n', '')
        original_score = original_score.replace('            rsp_rdata <= ram[word_index];\n', '')
        generated_score = generated_score.replace(
            '      if (rsp_valid && rsp_err) $fatal(1,"shared endpoint error");\n'
            '      if (cmd_ready !== ((!rsp_valid || rsp_ready) && (cycles % 7 != 0)))\n'
            '        $fatal(1,"shared endpoint backpressure phase differs cycle=%0d",cycles);\n', '')
        self.assertEqual(generated_score, original_score)
        for anchor in ['always #2 clk = ~clk;', 'always #33 lfclk = ~lfclk;', '#(120-$realtime) rst_n=1;']:
            self.assertIn(anchor, generated)
        self.assertNotRegex(generated, r'\brsp_(?:valid|rdata)\s*<=')

    def test_only_itcm_and_shared_backdoor_preloaded(self):
        macro = VERIFY.generate_tb(True)
        # 8 banks * 4 lanes + 128 banks * 2 lanes. DTCM and weights use CPU traffic.
        self.assertEqual(macro.count('.macro.mem[row]='), 288)
        self.assertIn('xu_pack_vendor_row[4*b +: 4]={a3[b],a2[b],a1[b],a0[b]};', macro)
        self.assertIn('dut.u_shared.storage.macro_storage.depth_bank[127].width_lane[1].macro.mem[row]', macro)
        self.assertNotIn('`ITCM.mem_r', macro)
        self.assertNotIn('force ', macro.replace('// Non-synthesizable preload: no force, no changes to live bus timing.', ''))
        self.assertIn('`ITCM.mem_r[row]=xu_program_words[row];', VERIFY.generate_tb(False))

    def test_tb_drift_is_rejected(self):
        with self.assertRaises(ValueError):
            VERIFY.once('different frozen TB', 'expected original anchor', 'replacement')

    def test_nominal_clocks_reset_and_public_boundaries(self):
        for reference in [False, True]:
            generated = VERIFY.generate_tb(False, 'nominal150', reference=reference)
            self.assertIn('`timescale 1ns/1fs', generated)
            self.assertIn('xu_target_ns=xu_half_index*(10.0/3.0);', generated)
            self.assertIn('#(xu_target_ns-$realtime);', generated)
            self.assertIn('always #15258.7890625 lfclk = ~lfclk;', generated)
            self.assertIn('#(200-$realtime);', generated)
            self.assertIn('if (xu_reset_edges!=30)', generated)
            self.assertNotIn('always #2 clk = ~clk;', generated)
            scope = 'dut.' + ('' if reference else 'u_soc.')
            self.assertIn('`define XU_HCLK '+scope+'u_e203_subsys_top.', generated)
            for marker in ['PPA_WINDOW_BEGIN', 'PPA_WINDOW_END', 'XU_ACTIVITY_BEGIN',
                           'XU_ACTIVITY_END', 'XU_CACHE_RELOAD', 'XU_CLOCK_STATIC_PASS']:
                self.assertEqual(generated.count('"'+marker), 1)
        generated = VERIFY.generate_tb(True, 'nominal150')
        self.assertLess(generated.index('      xu_preload_shared();'),
                        generated.index('      $display("XU_CACHE_RELOAD'))

    def test_nominal_window_validates_inclusive_cycles_and_elapsed_time(self):
        layers = [dict(layer=0, cycles=4)]
        log = ('PPA_WINDOW_BEGIN layer=0 cycle=3 time_ns=3.333333 tick_fs=3333333\n'
               'PPA_WINDOW_END layer=0 cycle=6 time_ns=23.333333 tick_fs=23333333\n'
               'XU_CLOCK_STATIC_PASS checked_hf_edges=10\n')
        windows = VERIFY.check_windows(log, layers)
        self.assertEqual(windows[0]['duration_ticks'], 20000000)
        for invalid in [log.replace('cycle=6', 'cycle=7'),
                        log.replace('tick_fs=23333333', 'tick_fs=23333335'),
                        log.replace('checked_hf_edges=10', 'checked_hf_edges=3'),
                        log+log.splitlines()[0]+'\n']:
            with self.assertRaises(ValueError):
                VERIFY.check_windows(invalid, layers)

    def test_external_tools_have_closed_stdin(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with mock.patch.object(VERIFY.soc.subprocess, 'run') as run:
                run.return_value.returncode = 0
                VERIFY.soc.run(['simulator'], path, path/'run.log')
            self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
