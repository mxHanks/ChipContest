#!/usr/bin/env python3
"""Host checks: actual155 parser/template evidence, negative guards, worker lifecycle.

No EDA run is made. Synthetic execution tests cover orchestration only; they do
not stand in for actual155 inventory, SRAM mapping, power, or qualification.
"""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sp = importlib.util.spec_from_file_location('xu_test166_runtime', str(HERE / 'power166.py'))
a = importlib.util.module_from_spec(sp)
sp.loader.exec_module(a)
EVIDENCE = ROOT / 'build/xu-score-resume-20261103/serverfailed159/s2e-own-timing-repair-20261105-155'
ORIGINAL = ROOT / 'build/xu-score-resume-20261103/core-results-107/s2e-ppa-campaign-20261104-89/formality/verify.tcl'
TOOLS = ROOT / 'build/xu-s2e-power124/frozen-tools109'
P130 = ROOT / 'build/xu-score-resume-20261103/terminal151/s2e-full-soc-power12-20261105-130/prepared.json'


class Test166(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = a.read(EVIDENCE / 'state.json')
        cls.remote_root = Path(cls.state['_state_path']).parent
        cls.native_log = (EVIDENCE / 'final/fm.log').read_text()
        cls.modules = a.base.Modules(TOOLS)
        cls.old = a.read(P130)
        # Template generation insists its library files exist. These tiny
        # placeholders exercise strings only; never link or execute them.
        temp = tempfile.TemporaryDirectory(prefix='xu166-template-only-')
        cls.addClassCleanup(temp.cleanup)
        cls.template_impl = copy.deepcopy(cls.old['implementation_controls'])
        cls.template_impl['libraries'] = []
        for i in range(2):
            file = Path(temp.name)/('host-template-only-%d.db' % i)
            file.write_text('HOST TEMPLATE PLACEHOLDER; NEVER EDA\n')
            row = dict(cls.old['implementation_controls']['libraries'][i])
            row.update(a.identity(file))
            cls.template_impl['libraries'].append(row)
        cls.target = dict(netlist=cls.state['final_outputs'][str(cls.remote_root / 'final/mapped.v')],
            constraints=cls.state['own89_context']['constraints'],
            clock_scope=next(r for r in cls.state['frozen_before'].values() if r['sha256'] == a.SCOPE155))

    def meta(self, state):
        a.metadata155(state, self.remote_root, self.state['own89_context'], self.state['source'], self.state['tools'])

    def test_python36(self):
        for name in ['power166.py', 'frozen130.py']:
            ast.parse((HERE / name).read_text(), feature_version=(3, 6))

    def test_original130_exact_sha(self):
        self.assertEqual(a.sha(HERE / 'frozen130.py'), a.FROZEN130)

    def test_actual155_state_sha(self):
        self.assertEqual(a.sha(EVIDENCE / 'state.json'), a.STATE155)
        self.meta(self.state)

    def test_state_reject_wrong_capture(self):
        s = copy.deepcopy(self.state); s['own89_context']['netlist']['sha256'] = a.NET155
        with self.assertRaises(ValueError): self.meta(s)

    def test_state_reject_baseline_source(self):
        s = copy.deepcopy(self.state); s['source']['main_commit'] = 'd276b55f'
        with self.assertRaises(ValueError): self.meta(s)

    def test_state_reject_running(self):
        s = copy.deepcopy(self.state); s['status'] = 'RUNNING'
        with self.assertRaises(ValueError): self.meta(s)

    def test_state_reject_svf_reorder(self):
        s = copy.deepcopy(self.state); s['svf_chain'].reverse()
        with self.assertRaises(ValueError): self.meta(s)

    def test_state_reject_missing_native(self):
        s = copy.deepcopy(self.state); s['runs'].pop()
        with self.assertRaises(ValueError): self.meta(s)

    def test_state_reject_hash_changed(self):
        s = copy.deepcopy(self.state); k = next(iter(s['frozen_after'])); s['frozen_after'][k]['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.meta(s)

    def test_state_reject_failed_native(self):
        s = copy.deepcopy(self.state); s['runs'][-1]['returncode'] = 1
        with self.assertRaises(ValueError): self.meta(s)

    def test_actual155_fm_echo_not_a_failure(self):
        self.assertIn('FORMALITY_FAIL', self.native_log)
        self.assertEqual(a.native_fm(self.native_log, 0)['passing'], 42338)

    def test_native_fm_reject_rc(self):
        with self.assertRaises(ValueError): a.native_fm(self.native_log, 1)

    def test_native_fm_reject_echo_only_marker(self):
        text = self.native_log.replace('\n' + a.MARKER_FM + '\n', '\n')
        with self.assertRaises(ValueError): a.native_fm(text, 0)

    def test_native_fm_reject_duplicate_marker(self):
        with self.assertRaises(ValueError): a.native_fm(self.native_log+'\n'+a.MARKER_FM+'\n',0)

    def test_native_fm_reject_native_fail_line(self):
        for line in ['XU_S2E_TIMING134_FORMALITY_FAIL', 'XU_S2E_TIMING134_FORMALITY_SCRIPT_ERROR injected',
                     'Error: injected', '1 Failing compare points', '1 Unverified compare points']:
            with self.subTest(line=line), self.assertRaises(ValueError): a.native_fm(self.native_log+'\n'+line+'\n',0)

    def test_native_fm_reject_scope_shrink(self):
        with self.assertRaises(ValueError): a.native_fm(self.native_log.replace('42338 Passing compare points','42337 Passing compare points'),0)

    def test_actual_original89_to155_full_template(self):
        original_root = Path(self.state['own89_context']['netlist']['path']).parent.parent
        self.assertEqual(a.fm_script(ORIGINAL.read_text(), original_root, self.remote_root, self.modules.ppa.tcl),
                         (EVIDENCE / 'final/verify.tcl').read_text())

    def test_fm_template_reject_duplicate_original_svf(self):
        original_root = Path(self.state['own89_context']['netlist']['path']).parent.parent
        text = ORIGINAL.read_text()+'\nset_svf '+self.modules.ppa.tcl(original_root/'ppa/default.svf')
        with self.assertRaises(ValueError): a.fm_script(text,original_root,self.remote_root,self.modules.ppa.tcl)

    def test_actual155_area(self):
        d = a.area((EVIDENCE/'final/area.rpt').read_text())
        self.assertEqual(d['accelerator_mm2'], '0.3003096339')
        self.assertEqual(d['qualification'], 'NOT_QUALIFIED')

    def test_area_reject_duplicate_or_changed(self):
        text=(EVIDENCE/'final/area.rpt').read_text()
        for changed in [text+text,text.replace('300309.6339','295000.3804')]:
            with self.assertRaises(ValueError): a.area(changed)

    def test_inventory_rebuilds155_clock_method(self):
        text=a.inventory_tcl(self.modules,self.template_impl,self.target,'INVENTORY_TEST166')
        self.assertNotIn('set_propagated_clock [all_clocks]',text)
        self.assertEqual(text.count('source '+self.modules.ppa.tcl(self.target['clock_scope']['path'])),1)
        self.assertIn('read_verilog '+self.modules.ppa.tcl(self.target['netlist']['path']),text)
        self.assertIn('if {$nc != 336 || $np != 22512}',text)

    def test_power_rebuilds155_clock_and_full_dut_saif(self):
        task=copy.deepcopy(self.old['tasks'][0]); task['completion_marker']='POWER_TEST166'
        text=a.power_tcl(self.modules,self.template_impl,self.target,task)
        self.assertNotIn('set_propagated_clock [all_clocks]',text)
        self.assertEqual(text.count('source '+self.modules.ppa.tcl(self.target['clock_scope']['path'])),1)
        self.assertIn('-strip_path {tb_xu_soc_ppa/dut}',text)
        self.assertIn('redirect -file update-power.rpt {update_power}',text)
        self.assertIn('sram-pins-before.rpt',text); self.assertIn('sram-pins-after.rpt',text)
        self.assertNotIn(a.base.NETLIST,text)

    def test_clock_reject_unknown_scope_or_prelude(self):
        scope=dict(self.target['clock_scope'],sha256='0'*64)
        for text,s in [('not a prelude',self.target['clock_scope']),('not a prelude',scope)]:
            with self.assertRaises(ValueError): a.replace_clock(self.modules,text,self.target['constraints'],s,True)

    def test_complete_capture12_required(self):
        report=a.read(ROOT/'build/xu-score-resume-20261103/activity125/s2e-formal-activity12-20261105-120/result.json')
        a.base.complete_taskset(report)
        report['tasks'].pop()
        with self.assertRaises(ValueError):a.base.complete_taskset(report)

    def test_task_selector(self):
        self.assertEqual(a.selected_ids('0'),[0]);self.assertEqual(a.selected_ids('all'),list(range(12)))
        for text in ['1','0,1','0,0','11','']:
            with self.assertRaises(ValueError):a.selected_ids(text)

    def test_missing_full12_preflight_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'new'
            argv=['campaign','--out',str(out)]
            for name in ['activity','source-root','tool-root','ppa-root','formality-root','target-root']:
                argv+=['--'+name,td]
            with self.assertRaisesRegex(ValueError,'preflight-root'):a.main(argv)
            self.assertFalse(out.exists())

    def test_preflight_reject_full12_disguised_as_task0(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name in ['execution.json','summary.json','result.json']:a.write(root/name,{})
            a.write(root/'prepared.json',{'requested_task_ids':list(range(12)),'preflight':None})
            with self.assertRaisesRegex(ValueError,'task0-only'):a.checked_preflight(root,None,{}, {}, {})

    def test_current_hash_records_deletion(self):
        with tempfile.TemporaryDirectory() as td:
            file=Path(td)/'f';file.write_text('frozen');records={str(file):a.sha(file)}
            self.assertEqual(a.current_hashes(records),records);file.unlink()
            self.assertNotEqual(a.current_hashes(records),records)

    def test_nonblocking_exclusive_lock(self):
        with tempfile.TemporaryDirectory() as td:
            with a.exclusive(Path(td)):
                with self.assertRaises(BlockingIOError):
                    with a.exclusive(Path(td)):pass

    def lifecycle(self, ids, fail_task=None, mutate=False):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);frozen=root/'frozen';frozen.write_text('before')
            target=dict(self.target,area={'accelerator_mm2':'0.3003096339','qualification':'NOT_QUALIFIED'},area_report={})
            tasks=[]
            for task_id in ids:
                directory=root/('task_%02d'%task_id);directory.mkdir()
                pins=directory/'measured-sram-pins.json';a.write(pins,{'pins':[]})
                tasks.append(dict(task_id=task_id,directory=directory.name,completion_marker='TASK_%d_DONE'%task_id,
                    expected_reports=self.modules.common.report_names()+['update-power.rpt'],macro_names=[],
                    measured_sram_pin_states=a.identity(pins),measured_summary={'q_tx_positive':5280},
                    activity_window={'duration_ticks':5788953333333,'formal_elapsed_cycles':868343}))
            manifest=dict(requested_task_ids=ids,tool_root='synthetic',library_compiler_root='synthetic',
                pt=a.identity(Path(sys.executable).resolve()),tasks=tasks,input_sha256={str(frozen):a.sha(frozen)},
                target_mapped_context=target,netlist=target['netlist'],original_capture_configuration_sha256='c'*64)
            a.write(root/'prepared.json',manifest)
            calls=[]
            def execute(argv,directory,log,timeout,environment):
                task=tasks[len(calls)];calls.append(task['task_id'])
                for name in task['expected_reports']:(directory/name).write_text('synthetic lifecycle report\n')
                (directory/'sram-power.rpt').write_text('synthetic lifecycle\n')
                for phase in ['before','after']:(directory/('sram-pins-%s.rpt'%phase)).write_text('synthetic lifecycle\n')
                (directory/'power.rpt').write_text('Design : xu_soc_ppa_top\nDynamic Power Units = 1 W\nLeakage Power Units = 1 W\n'+
                    ''.join(label+' = 0.01 ( synthetic )\n' for label in ['Net Switching Power','Cell Internal Power','Cell Leakage Power','Total Power']))
                (directory/'tool-version.rpt').write_text(a.base.PT_VERSION+'\n')
                log.write_text('Version '+a.base.PT_VERSION+'\n'+task['completion_marker']+'\n')
                if mutate:frozen.write_text('changed')
                return {'returncode':1 if fail_task==task['task_id'] else 0}
            common=SimpleNamespace(execution_environment=lambda p:{},execute=execute,checked_reports=self.modules.common.checked_reports)
            modules=SimpleNamespace(common=common)
            args=SimpleNamespace(out=root,task_ids=ids,timeout=1)
            state={'status':'PREPARED166_NOT_QUALIFIED','qualification':'NOT_QUALIFIED'}
            with patch.object(a.base,'Modules',return_value=modules),patch.object(a,'verify_prepared',return_value=target):
                if fail_task is not None or mutate:
                    with self.assertRaises(ValueError):a.run(args,state)
                    self.assertEqual(a.read(root/'execution.json')['status'],a.FAIL)
                    if fail_task is not None:self.assertEqual(calls,list(range(fail_task+1)))
                else:
                    a.run(args,state)
                    self.assertEqual(calls,ids)
                    execution=a.read(root/'execution.json');summary=a.read(root/'summary.json')
                    self.assertEqual(execution['status'],a.TASK0 if ids==[0] else a.FULL12)
                    self.assertEqual(summary['qualification'],'NOT_QUALIFIED')
                    self.assertEqual(summary['taskset_complete'],ids==list(range(12)))
                    self.assertEqual(summary['total_elapsed_cycles'],len(ids)*868343)
                    with self.assertRaisesRegex(ValueError,'execution exists'):a.run(args,state)

    def test_synthetic_task0_worker_lifecycle_no_qualification(self):self.lifecycle([0])
    def test_synthetic_full12_worker_lifecycle_no_qualification(self):self.lifecycle(list(range(12)))
    def test_synthetic_native_failure_stops_next_layer(self):self.lifecycle(list(range(12)),fail_task=2)
    def test_synthetic_input_change_cannot_succeed(self):self.lifecycle([0],mutate=True)


if __name__=='__main__':
    unittest.main(verbosity=2)
