"""Host/Icarus checks for the isolated full-SoC activity producer.

These are not VCS, full-SoC execution, PT or power qualification evidence.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_soc_task_activity', ROOT / 'tools/ppa/xu_soc_task_activity.py')
collector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class TaskMappingTests(unittest.TestCase):
    def test_development_task_ids_preserve_real_ids_and_reject_ambiguous_sets(self):
        self.assertEqual(collector.parse_task_ids('0,7,11'), [0, 7, 11])
        for value in ('', '12', '-1', '7,0', '0,0', '0 1'):
            with self.subTest(value=value), self.assertRaises(Exception):
                collector.parse_task_ids(value)

    def test_all_twelve_real_fixtures_map_to_local_zero_with_original_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / 'original'
            manifest = collector.soc.load_fixture(source, 12)
            original_w = []
            for task_id in range(12):
                hashes = {name + '.mem': manifest['files']['layer_%02d/%s.mem' % (task_id, name)]
                          for name in collector.TENSORS}
                original_w.append(hashes['w.mem'])
                result = collector.materialize_task(source, directory / ('task_%02d' % task_id),
                                                     task_id, dict(layer=task_id, sha256=hashes))
                self.assertEqual(result['global_task_id'], task_id)
                self.assertEqual(result['original_layer'], 'layer_%02d' % task_id)
                self.assertEqual(result['simulator_layer'], 'layer_00')
                for record in result['files']:
                    self.assertEqual(record['materialized']['sha256'], record['original']['sha256'])
                    self.assertIn('/layer_%02d/' % task_id, record['original']['path'])
                    self.assertIn('/layer_00/', record['materialized']['path'])
            self.assertGreater(len(set(original_w)), 1, 'test must expose silently repeated layer0')
            hashes['x.mem'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'changed after integer validation'):
                collector.materialize_task(source, directory / 'changed', 11, dict(layer=11, sha256=hashes))

    def test_generation_retains_original_scope_and_exact_boundary_hooks(self):
        before = collector.base.sha(collector.base.TB)
        text = collector.generate_tb()
        self.assertEqual(collector.base.sha(collector.base.TB), before)
        for call in ('$toggle_start();', '$toggle_stop();', '$toggle_report(',
                     '$set_toggle_region(tb_xu_soc_ppa.dut);', '$set_gate_level_monitoring("rtl_on");'):
            self.assertEqual(text.count(call), 1)
        begin = text.index('if (!perf_active) begin', text.index('task observe_performance'))
        self.assertLess(begin, text.index('$toggle_start();'))
        self.assertLess(text.index('$toggle_start();'), text.index('perf_active=1;', begin))
        end = text.index('if (shared_retire && final_write_pending) begin')
        self.assertLess(end, text.index('$toggle_stop();'))
        self.assertLess(text.index('$toggle_stop();'), text.index('perf_active=0;', end))
        self.assertIn('xu_pack_vendor_row', text)
        self.assertIn('xu_preload_itcm();', text)
        self.assertIn('xu_preload_shared();', text)
        self.assertNotIn('"rtl_on", "sv"', text)
        self.assertNotIn('force ', text)

    def test_opt_in_keeps_legacy_window_and_starts_formal_saif_at_request(self):
        text = collector.generate_tb(True)
        self.assertEqual(text.count('xu_observe_clear_window();'), 1)
        self.assertEqual(text.count('if (xu_payload_phase) xu_observe_upload();'), 1)
        self.assertNotIn('if (!in_window) xu_observe_upload();', text)
        for call in ('$toggle_start();', '$toggle_stop();', '$toggle_report('):
            self.assertEqual(text.count(call), 1)
        self.assertIn('source_request=cmd_valid && cmd_read', text)
        self.assertIn('xu_observe_task_clear(source_request,xu_payload_phase);', text)
        self.assertIn('`ACCEL.rsp_valid!==1\'b0', text)
        self.assertIn('in_window=perf_active || (first_cycle<0 && shared_accept', text)
        self.assertIn('layer,last_cycle-first_cycle+1,firmware_cycles', text)
        self.assertIn('xu_formal_cycles!=perf_cycles+xu_initial_wait', text)
        self.assertNotIn('force ', text)

    def test_global_task_log_boundary_does_not_accept_local_zero(self):
        cycles = 2000000
        perf = dict((key, 0) for key in collector.contract.PERFORMANCE_FIELDS)
        perf.update(collector.contract.task_contract('bias-hw-window'))
        perf.update(layer=0, cycles=cycles, w_load=cycles, busy=perf['mac_fire'])
        perf_line = 'PERF_TASK ' + ' '.join('%s=%d' % (key, perf[key])
                                             for key in collector.contract.PERFORMANCE_FIELDS)
        begin = 1000000
        end = begin + round((cycles - 1) * 20000000 / 3)
        log = '\n'.join([
            'TASK_PASS layer=0 outputs=25344 writes=50688 cycles=%d firmware_cycles=10' % cycles,
            perf_line, 'SOC_PASS tasks=1 outputs=25344 writes=50688',
            'PPA_WINDOW_BEGIN layer=0 cycle=100 time_ns=1.0 tick_fs=%d' % begin,
            'PPA_WINDOW_END layer=0 cycle=%d time_ns=2.0 tick_fs=%d' % (99 + cycles, end),
            'XU_CLOCK_STATIC_PASS checked_hf_edges=%d' % (cycles + 100),
            'XU_ACTIVITY_BEGIN task=7 tick=%d' % begin,
            'XU_ACTIVITY_END task=7 tick=%d' % end,
            'XU_CACHE_INITIAL task=7 fresh_process=1 cache_enable=0 busy=0 prior_uploads=0 prior_starts=0',
            'XU_CACHE_UPLOAD_PASS task=7 w=16384 bias=256 x=6336 rows=99 starts=3168 window=inside checked_data=1'])
        layer, window = collector.checked_log(log, 7, 'bias-hw-window')
        self.assertEqual(layer['layer'], 0)
        self.assertEqual(window['begin']['tick'], begin)
        with self.assertRaisesRegex(ValueError, 'global task boundary identity'):
            collector.checked_log(log.replace('task=7', 'task=0'), 7, 'bias-hw-window')

        # A real blocked request must extend formal SAIF, retaining raw legacy logs.
        request = begin - 20000000
        formal = log.replace('XU_ACTIVITY_BEGIN task=7 tick=%d' % begin,
                             'XU_ACTIVITY_BEGIN task=7 tick=%d' % request)
        formal += '\n' + '\n'.join([
            'XU_TASK_CLEAR_BEGIN task=7 cycle=50 tick=1',
            'XU_TASK_CLEAR_LAST_WRITE task=7 cycle=90 tick=2 writes=33697',
            'XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=2',
            'XU_SOURCE_REQUEST task=7 cycle=97 tick=%d' % request,
            'XU_SOURCE_ACCEPT task=7 cycle=100 tick=%d' % begin,
            ('XU_TASK_WINDOW task=7 request_cycle=97 accept_cycle=100 end_cycle=%d '
             'initial_wait_cycles=3 legacy_inclusive_cycles=%d formal_inclusive_cycles=%d formal_elapsed_cycles=%d')
            % (99 + cycles, cycles, cycles+3, cycles+2)])
        # Shift this synthetic clock origin forward so all physical ticks are positive.
        formal = formal.replace('tick=%d' % request, 'tick=%d' % (request + 30000000))
        formal = formal.replace('tick=%d' % begin, 'tick=%d' % (begin + 30000000))
        formal = formal.replace('tick_fs=%d' % begin, 'tick_fs=%d' % (begin + 30000000))
        formal = formal.replace('tick=%d' % end, 'tick=%d' % (end + 30000000))
        formal = formal.replace('tick_fs=%d' % end, 'tick_fs=%d' % (end + 30000000))
        layer, window = collector.checked_log(formal, 7, 'bias-hw-window', True)
        self.assertEqual(layer['cycles'], cycles)
        self.assertEqual(window['formal_inclusive_cycles'], cycles+3)
        self.assertEqual(window['initial_source_wait_cycles'], 3)
        self.assertEqual(window['legacy_accept_window']['begin']['cycle'], 100)
        with self.assertRaisesRegex(ValueError, 'cycle accounting differs'):
            collector.checked_log(formal.replace('initial_wait_cycles=3', 'initial_wait_cycles=2'),
                                  7, 'bias-hw-window', True)

    def test_scope_inventory_requires_all_336_macro_instances_and_exact_duration(self):
        # Synthetic digital SAIF, expressly not a measured SoC fixture.
        paths = {'hfextclk': 12, 'u_soc/u_e203_cpu_top/q': 1,
                 'u_soc/u_e203_cpu_top/u_e203_biu/cmd': 1,
                 'u_soc/u_e203_cpu_top/u_e203_biu/rsp': 1,
                 'u_soc/u_accel_icb_slave/busy': 1}
        for group, count in [('u_shared', 256), ('u_soc/u_e203_itcm_ram', 32),
                             ('u_soc/u_e203_dtcm_ram', 32),
                             ('u_soc/u_accel_icb_slave/u_linear_compute_core/core', 16)]:
            for index in range(count):
                for pin in (['CLK', 'CEN', 'RET1N'] if 'dtcm' in group else ['CLK', 'CEN']):
                    paths['%s/bank_%d/macro/%s' % (group, index, pin)] = 1

        def saif(records, static_dtcm=False, unknown_cen=False):
            tree = {}
            for path, toggles in records.items():
                node = tree
                parts = path.split('/')
                for name in parts[:-1]:
                    node = node.setdefault(name, {})
                node[parts[-1]] = toggles

            def render(name, node, parent=''):
                current = parent+'/'+name
                nets = []
                for key, value in node.items():
                    if not isinstance(value, int):
                        continue
                    if static_dtcm and '/u_e203_dtcm_ram/' in current:
                        high = key != 'CLK'
                        tx = 1 if unknown_cen and key == 'CEN' else 0
                        t0, t1 = (0, 40000000-tx) if high else (40000000-tx, 0)
                        nets.append('(%s (T0 %d) (T1 %d) (TX %d) (TC 0))' % (key, t0, t1, tx))
                    else:
                        nets.append('(%s (T0 20000000) (T1 20000000) (TX 0) (TC %d))' % (key, value))
                nets = ' '.join(nets)
                children = ' '.join(render(key, value, current) for key, value in node.items() if isinstance(value, dict))
                return '(INSTANCE %s (NET %s) %s)' % (name, nets, children)
            return '(SAIFILE (TIMESCALE 1 fs) (DURATION 40000000) (INSTANCE tb_xu_soc_ppa %s))' % render('dut', tree)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'synthetic.saif'
            path.write_text(saif(paths))
            result = collector.inspect_activity(path, dict(duration_ticks=40000000))
            self.assertEqual(sum(g['observed_count'] for g in result['macro_inventory'].values()), 336)
            with self.assertRaisesRegex(ValueError, 'DURATION differs'):
                collector.inspect_activity(path, dict(duration_ticks=40000001))
            path.write_text(saif(paths, static_dtcm=True))
            with self.assertRaisesRegex(ValueError, 'no static declaration: dtcm'):
                collector.inspect_activity(path, dict(duration_ticks=40000000))
            result = collector.inspect_activity(path, dict(duration_ticks=40000000), ('dtcm',))
            self.assertEqual(result['scope_presence']['dtcm']['state'], 'OBSERVED_KNOWN_STATIC_DISABLED')
            self.assertEqual(result['scope_presence']['dtcm']['macro_count'], 32)
            path.write_text(saif(paths, static_dtcm=True, unknown_cen=True))
            with self.assertRaisesRegex(ValueError, 'control missing/unknown/not held idle'):
                collector.inspect_activity(path, dict(duration_ticks=40000000), ('dtcm',))
            del paths['u_soc/u_e203_dtcm_ram/bank_31/macro/RET1N']
            path.write_text(saif(paths, static_dtcm=True))
            with self.assertRaisesRegex(ValueError, 'control missing/unknown/not held idle'):
                collector.inspect_activity(path, dict(duration_ticks=40000000), ('dtcm',))
            del paths['u_soc/u_e203_dtcm_ram/bank_31/macro/CLK']
            del paths['u_soc/u_e203_dtcm_ram/bank_31/macro/CEN']
            path.write_text(saif(paths, static_dtcm=True))
            with self.assertRaisesRegex(ValueError, 'SRAM macro count differs: dtcm'):
                collector.inspect_activity(path, dict(duration_ticks=40000000), ('dtcm',))
            del paths['u_shared/bank_255/macro/CLK']
            del paths['u_shared/bank_255/macro/CEN']
            path.write_text(saif(paths))
            with self.assertRaisesRegex(ValueError, 'SRAM macro count differs: shared'):
                collector.inspect_activity(path, dict(duration_ticks=40000000))


@unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus required')
class PassiveUploadIcarusTests(unittest.TestCase):
    def test_actual_sv_monitor_accepts_complete_upload_and_rejects_missing_corrupt_outside(self):
        mock = r'''
`timescale 1ns/1fs
module xu_mock_accel;
  reg cmd_valid=1,cmd_ready=1,cmd_read=0,busy=0,cache_enable=0;
  reg [31:0] cmd_addr=0,cmd_wdata=0;
  reg [3:0] cmd_wmask=15;
  reg [2:0] w_bank_reg=0;
  reg [10:0] w_addr_reg=0;
  reg [7:0] cache_addr_reg=0;
  reg [5:0] x_addr_reg=0;
  reg [4:0] group_reg=0;
endmodule
module xu_monitor_test;
  xu_mock_accel accel();
  `define ACCEL accel
  reg [15:0] w[0:16383],x[0:6335];
  reg [39:0] bias[0:255];
MONITOR
  integer i,b,a,r,g,index,mode;
  initial begin
    if (!$value$plusargs("MODE=%d",mode)) mode=0;
    for(i=0;i<16384;i=i+1) begin w[i]=i*7;xu_w_seen[i]=0;end
    for(i=0;i<6336;i=i+1) x[i]=i*3;
    for(i=0;i<256;i=i+1) begin bias[i]=40'h1230000000+i;xu_bias_seen[i]=0;end
    xu_saif_started=(mode!=5);
    for(b=0;b<8;b=b+1) for(a=0;a<2048;a=a+1) begin
      accel.w_bank_reg=b;accel.w_addr_reg=a;accel.cmd_addr='h024;
      index=(a%64)*256+(a/64)*8+b;
      accel.cmd_wdata=w[index];
      if(mode==4 && b==7 && a==2047) accel.cmd_wdata=accel.cmd_wdata^1;
      #1;if(!(mode==1 && b==7 && a==2047)) xu_observe_upload();
    end
    for(i=0;i<256;i=i+1) begin
      accel.cache_addr_reg=i;
      accel.cmd_addr='h048;accel.cmd_wdata=bias[i][31:0];#1;xu_observe_upload();
      accel.cmd_addr='h04c;accel.cmd_wdata=bias[i][39:32];#1;
      if(!(mode==2 && i==255)) xu_observe_upload();
    end
    accel.cache_enable=1;
    for(r=0;r<99;r=r+1) begin
      for(a=0;a<64;a=a+1) begin
        accel.x_addr_reg=a;accel.cmd_addr='h018;accel.cmd_wdata=x[r*64+a];#1;
        if(!(mode==3 && r==0 && a==63)) xu_observe_upload();
      end
      for(g=0;g<32;g=g+1) begin
        accel.group_reg=g;accel.cmd_addr='h008;accel.cmd_wdata=1;#1;xu_observe_upload();
      end
    end
    if(xu_w_count!=16384 || xu_bias_count!=256 || xu_x_count!=6336 ||
       xu_rows!=99 || xu_starts!=3168) $fatal(1,"bad completion");
    $display("XU_PASSIVE_UPLOAD_PROBE_PASS");$finish;
  end
endmodule
'''.replace('MONITOR', collector.UPLOAD_DECLARATIONS)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / 'probe.sv'
            source.write_text(mock)
            evidence = Path(os.environ['XU_TASK_ACTIVITY_TEST_EVIDENCE']) if os.environ.get('XU_TASK_ACTIVITY_TEST_EVIDENCE') else None
            if evidence:
                evidence.mkdir(parents=True, exist_ok=True)
                (evidence / 'passive-probe.sv').write_text(mock)
            command = ['iverilog', '-g2012', '-s', 'xu_monitor_test', '-o', str(directory / 'probe.vvp'), str(source)]
            build = subprocess.run(command,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   universal_newlines=True, timeout=60)
            if evidence:
                (evidence / 'passive-probe-build.log').write_text(json.dumps(command) + '\n' + build.stdout)
            self.assertEqual(build.returncode, 0, build.stdout)
            for mode in range(6):
                command = ['vvp', str(directory / 'probe.vvp'), '+MODE=%d' % mode]
                result = subprocess.run(command,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, universal_newlines=True, timeout=60)
                if evidence:
                    (evidence / ('passive-probe-mode-%d.log' % mode)).write_text(
                        json.dumps(dict(command=command, returncode=result.returncode)) + '\n' + result.stdout)
                if mode == 0:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn('XU_PASSIVE_UPLOAD_PROBE_PASS', result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0, 'destructive probe mode=%d accepted' % mode)
                    self.assertIn('FATAL', result.stdout)


if __name__ == '__main__':
    unittest.main()
