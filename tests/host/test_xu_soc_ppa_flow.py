"""Fail-closed PPA preparation/execution guards; no simulator or EDA results mocked as qualified."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_soc_ppa', ROOT/'tools/scripts/xu_soc_ppa.py')
PPA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PPA)


class XuSocPpaFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = PPA.inventory(ROOT)

    def identity(self, path):
        return dict(path=str(path.resolve()), sha256=PPA.sha(path))

    def fixture(self, directory):
        impl=PPA.template(self.inventory)
        impl['replacements']={
            PPA.RTL+'/general/sirv_sim_ram.v':self.identity(ROOT/'tools/ppa/xu_sirv_sram_adapter.sv'),
            PPA.RTL+'/perips/mem_1024x16.sv':self.identity(ROOT/'tools/ppa/xu_weight_sram_adapter.sv')}
        impl['added_sources']=[self.identity(ROOT/'tools/ppa'/name) for name in ['xu_soc_ppa_top.sv','xu_shared_icb_sram.sv']]
        impl['libraries']=[]
        for role in ['standard_cell','sram']:
            path=directory/(role+'.db')
            path.write_text('HOST FIXTURE ONLY: '+role)
            impl['libraries'].append(dict(self.identity(path),role=role))
        impl['constraints']=self.identity(ROOT/'tools/ppa/xu_full_soc.sdc')
        review=dict(status='REVIEWED',constraints_sha256=impl['constraints']['sha256'])
        for name in ['primary_clocks','generated_clock_policy','reset_exceptions','clock_domain_crossings','untested_check_policy']:
            review[name]='HOST FIXTURE ONLY: report review still required'
        path=directory/'clock-review.json';path.write_text(json.dumps(review))
        impl['clock_review']=self.identity(path)
        proof=PPA.mapping_review_template(impl)
        path=directory/'mapping-proof.json';path.write_text(json.dumps(proof))
        impl['mapping_proof']=self.identity(path)
        return impl,proof

    def power_fixture(self, directory):
        impl,_=self.fixture(directory)
        out=directory/'prepared'
        prepared=PPA.prepare(ROOT,out,impl,allow_unqualified=True)
        (out/'mapped.v').write_text('HOST NETLIST FIXTURE ONLY')
        (out/'mapped.sdc').write_text('HOST MAPPED SDC FIXTURE ONLY')
        execution=dict(status='EXECUTED_NOT_QUALIFIED',netlist_sha256=PPA.sha(out/'mapped.v'),
                       sdc_sha256=PPA.sha(out/'mapped.sdc'),analysis_sdc_sha256=PPA.sha(out/'constraints.sdc'))
        (out/'execution.json').write_text(json.dumps(execution))
        layers=[dict(layer=i,cycles=i+2,firmware_cycles=i+10) for i in range(12)]
        log=directory/'simulation.log'
        log.write_text(''.join('TASK_PASS layer={layer} outputs=25344 writes=50688 cycles={cycles} firmware_cycles={firmware_cycles}\n'.format(**x) for x in layers)+
                       'SOC_PASS tasks=12 outputs=304128 writes=608256\n')
        result=dict(status='PASS',tasks=12,outputs=304128,write_words=608256,layers=layers,
                    log_sha256={'simulation.log':PPA.sha(log)})
        resultpath=directory/'result.json';resultpath.write_text(json.dumps(result))
        vcd=directory/'activity.vcd';vcd.write_text('HOST VCD FIXTURE ONLY')
        windows=[[i*1000+10,i*1000+10+(x['cycles']-1)*20/3] for i,x in enumerate(layers)]
        record=dict(vcd=self.identity(vcd),result=self.identity(resultpath),simulation_log=self.identity(log),
                    mapping_sha256=PPA.digest(dict(replacements=impl['replacements'],added_sources=impl['added_sources'])),
                    source_manifest_sha256=prepared['input_manifest_sha256'],netlist_sha256=execution['netlist_sha256'],
                    sdc_sha256=execution['sdc_sha256'],analysis_sdc_sha256=execution['analysis_sdc_sha256'],
                    windows_ns=windows,clock_period_ns=20/3,
                    scope='full-digital-soc-including-all-srams',strip_path='tb/dut',
                    scope_paths={x:'tb/dut/'+x for x in ['cpu','accelerator','interconnect','shared','itcm','dtcm']})
        return out,record,windows

    def test_unreviewed_template_cannot_be_used_as_qualified_proof(self):
        with tempfile.TemporaryDirectory() as temporary:
            impl,proof=self.fixture(Path(temporary))
            self.assertEqual(proof['status'],'UNREVIEWED')
            self.assertTrue(all(x['status']=='NOT_RUN' and x['log'] is None for x in proof['checks'].values()))
            with self.assertRaisesRegex(ValueError,'allow-unqualified'):
                PPA.checked_implementation(impl,self.inventory)
            _,_,gaps=PPA.checked_implementation(impl,self.inventory,allow_unqualified=True)
            self.assertIn('mapping:sram_pvt_timing_eligibility:NOT_RUN',gaps)
            self.assertIn('mapped-equivalence:NOT_RUN',gaps)
            changed=copy.deepcopy(impl)
            changed['added_sources'][0]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'SHA256'):
                PPA.checked_implementation(changed,self.inventory,allow_unqualified=True)

    def test_library_roles_geometry_and_retained_topology_are_mandatory(self):
        with tempfile.TemporaryDirectory() as temporary:
            impl,_=self.fixture(Path(temporary))
            for label,mutate in [
                ('role',lambda x:x['libraries'][0].pop('role')),
                ('count',lambda x:x['memory_groups'][0].update(count=1)),
                ('hierarchy',lambda x:x['retained_instances'][0].update(pattern='*')),
            ]:
                changed=copy.deepcopy(impl);mutate(changed)
                with self.subTest(label=label),self.assertRaises(ValueError):
                    PPA.checked_implementation(changed,self.inventory,allow_unqualified=True)

    def test_prepared_scripts_preserve_scope_and_separate_sram_from_target_library(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            impl,_=self.fixture(directory)
            out=directory/'prepared'
            result=PPA.prepare(ROOT,out,impl,allow_unqualified=True)
            self.assertEqual(result['status'],'PREPARED_NOT_QUALIFIED')
            self.assertTrue(result['qualification_gaps'])
            script=(out/'synth.tcl').read_text()
            target=next(line for line in script.splitlines() if line.startswith('set_app_var target_library'))
            self.assertIn('standard_cell.db',target)
            self.assertNotIn('/sram.db',target)
            self.assertIn('/sram.db',next(line for line in script.splitlines() if line.startswith('set_app_var link_library')))
            self.assertIn('compile_ultra -no_autoungroup',script)
            self.assertIn('set_fix_hold [all_clocks]',script)
            self.assertIn('total must be exactly 336',script)
            self.assertIn('full_name =~ u_shared/storage/* && ref_name == RAMSP1024X16',script)
            self.assertIn('XU_FATAL:',script)
            self.assertIn('clock-review.tcl',result['generated_sha256'])
            pt=(out/'sta.tcl').read_text()
            self.assertIn('source constraints.sdc\n',pt)
            self.assertNotIn('read_sdc mapped.sdc',pt)
            self.assertIn('set_propagated_clock [all_clocks]',pt)
            self.assertIn('report_analysis_coverage -status_details untested',pt)
            self.assertIn('foreach xu_type {max min}',pt)
            self.assertNotIn('slack_lesser_than',pt)

    def test_zero_exit_without_marker_and_indented_errors_are_rejected(self):
        cases=[('print("normal termination")',False),
               ('print("  Error: unresolved reference"); print("XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED")',False),
               ('print("XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED")',True)]
        for code,success in cases:
            with self.subTest(code=code),tempfile.TemporaryDirectory() as temporary:
                command=[sys.executable,'-c',code]
                if success:
                    result=PPA.run_tool(Path(temporary),command,'dc',os.environ.copy())
                    self.assertIn('execution only',result['scope'])
                else:
                    with self.assertRaises(ValueError):
                        PPA.run_tool(Path(temporary),command,'dc',os.environ.copy())

    def test_tcl_guard_stops_before_success_marker_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'guard.tcl'
            path.write_text(PPA.guarded_tcl('error {host injected failure}\n','SHOULD_NOT_APPEAR'))
            result=subprocess.run(['tclsh',str(path)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('XU_FATAL:',result.stdout)
            self.assertNotIn('SHOULD_NOT_APPEAR',result.stdout)

    def test_hold_failures_and_missing_clocks_never_become_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary);(out/'clock-reports').mkdir()
            for name in ['check-timing.rpt','units.rpt','pt-clocks.rpt','analysis-coverage.rpt','setup.rpt','hold.rpt','violations.rpt','clock-reports/clock_endpoints.tsv']:
                (out/name).write_text('HOST REPORT FIXTURE ONLY\n')
            (out/'timing-slack.tsv').write_text('delay_type\tpath_count\tworst_slack\nmax\t1\t0.1\nmin\t1\t-0.02\n')
            (out/'clock-reports/review_status.txt').write_text('NO_CLOCK_ENDPOINTS=2\nREPORT_COMMAND_FAILURES=\n')
            review=PPA.timing_execution_review(out)
            self.assertEqual(review['qualification'],'NOT_QUALIFIED')
            self.assertIn('hold_slack_negative',review['observed_issues'])
            self.assertIn('no_clock_endpoints',review['observed_issues'])
            (out/'hold.rpt').unlink()
            with self.assertRaisesRegex(ValueError,'hold.rpt'):
                PPA.timing_execution_review(out)

    def test_power_runs_twelve_independent_start_end_pairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            out,record,windows=self.power_fixture(Path(temporary))
            self.assertNotEqual(record['sdc_sha256'],record['analysis_sdc_sha256'])
            called=[]
            def fake_tool(directory,command,label,env):
                index=int(label.rsplit('-',1)[1]);called.append(index)
                text=(directory/command[-1]).read_text()
                pairs=re.findall(r'-time \[list ([^\]]+)\]',text)
                self.assertEqual(len(pairs),1)
                self.assertEqual([float(x) for x in pairs[0].split()],windows[index])
                self.assertIn('source constraints.sdc\n',text)
                self.assertNotIn('read_sdc mapped.sdc',text)
                for name in ['switching-before','switching-after','unannotated','power','power-hierarchy','units']:
                    (directory/('task-%02d-%s.rpt'%(index,name))).write_text('HOST REPORT FIXTURE ONLY')
                return dict(scope='HOST EXECUTION FIXTURE ONLY')
            with mock.patch.object(PPA,'run_tool',side_effect=fake_tool):
                receipt=PPA.activity_power(out,record,{})
            self.assertEqual(called,list(range(12)))
            self.assertEqual(receipt['status'],'EXECUTED_NOT_QUALIFIED')
            self.assertEqual(len(receipt['tasks']),12)
            self.assertEqual(receipt['sdc_sha256'],PPA.sha(out/'mapped.sdc'))
            self.assertEqual(receipt['analysis_sdc_sha256'],PPA.sha(out/'constraints.sdc'))
            self.assertNotIn('energy_joules',receipt)

    def test_power_rejects_missing_or_mismatched_analysis_sdc_identity(self):
        for label in ['missing_activity','missing_execution','mapped_as_analysis','execution_mismatch',
                      'actual_file_changed','prepared_mismatch','mapped_file_changed','symlink']:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as temporary:
                out,record,_=self.power_fixture(Path(temporary))
                execution=json.loads((out/'execution.json').read_text())
                if label=='missing_activity':
                    record.pop('analysis_sdc_sha256')
                elif label=='missing_execution':
                    execution.pop('analysis_sdc_sha256')
                elif label=='mapped_as_analysis':
                    record['analysis_sdc_sha256']=record['sdc_sha256']
                elif label=='execution_mismatch':
                    execution['analysis_sdc_sha256']='0'*64
                elif label=='actual_file_changed':
                    (out/'constraints.sdc').write_text('HOST CHANGED ANALYSIS CONSTRAINTS')
                elif label=='prepared_mismatch':
                    (out/'constraints.sdc').write_text('HOST UNPREPARED ANALYSIS CONSTRAINTS')
                    record['analysis_sdc_sha256']=execution['analysis_sdc_sha256']=PPA.sha(out/'constraints.sdc')
                elif label=='mapped_file_changed':
                    (out/'mapped.sdc').write_text('HOST CHANGED MAPPED CONSTRAINTS')
                elif label=='symlink':
                    (out/'constraints.sdc').rename(out/'other.sdc')
                    (out/'constraints.sdc').symlink_to(out/'other.sdc')
                (out/'execution.json').write_text(json.dumps(execution))
                with mock.patch.object(PPA,'run_tool') as run_tool,self.assertRaisesRegex(ValueError,'SDC'):
                    PPA.activity_power(out,record,{})
                run_tool.assert_not_called()
                self.assertFalse((out/'power-run.json').exists())
                self.assertFalse((out/'activity-input.json').exists())

    def test_power_cannot_report_success_if_analysis_sdc_changes_during_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            out,record,_=self.power_fixture(Path(temporary))
            def change_constraints(directory,command,label,env):
                (directory/'constraints.sdc').write_text('HOST CHANGED DURING POWER EXECUTION')
                return dict(scope='HOST EXECUTION FIXTURE ONLY')
            with mock.patch.object(PPA,'run_tool',side_effect=change_constraints) as run_tool,\
                    self.assertRaisesRegex(ValueError,'analysis SDC changed during'):
                PPA.activity_power(out,record,{})
            run_tool.assert_called_once()
            receipt=json.loads((out/'power-run.json').read_text())
            self.assertEqual(receipt['status'],'FAIL')
            self.assertEqual(receipt['tasks'],[])

    def test_run_receipt_separates_mapped_and_analysis_sdc_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            impl,_=self.fixture(directory)
            out=directory/'prepared'
            PPA.prepare(ROOT,out,impl,allow_unqualified=True)
            def fake_tool(directory,command,label,env):
                if label=='dc':
                    (directory/'mapped.v').write_text('HOST NETLIST FIXTURE ONLY')
                    (directory/'mapped.sdc').write_text('HOST MAPPED SDC FIXTURE ONLY')
                return dict(scope='HOST EXECUTION FIXTURE ONLY')
            with mock.patch.object(sys,'argv',['xu_soc_ppa.py','run','--root',str(ROOT),'--out',str(out)]),\
                    mock.patch.object(PPA,'run_tool',side_effect=fake_tool),\
                    mock.patch.object(PPA,'timing_execution_review',return_value=dict(qualification='NOT_QUALIFIED')):
                self.assertEqual(PPA.main(),0)
            execution=json.loads((out/'execution.json').read_text())
            self.assertEqual(execution['status'],'EXECUTED_NOT_QUALIFIED')
            self.assertEqual(execution['sdc_sha256'],PPA.sha(out/'mapped.sdc'))
            self.assertEqual(execution['analysis_sdc_sha256'],PPA.sha(out/'constraints.sdc'))
            self.assertNotEqual(execution['sdc_sha256'],execution['analysis_sdc_sha256'])


if __name__=='__main__':
    unittest.main()
