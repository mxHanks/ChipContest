"""Inert temporary records and mocked prerequisites; never run HDL or tools."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/'scripts/verify/sram_adapter_system_evidence.py'


class SRAMAdapterSystemEvidenceTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('adapter_system_evidence_test_subject', MODULE)
        self.subject = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.subject)
        self.temp = tempfile.TemporaryDirectory(prefix='kwt-system-evidence-format-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root/'report';self.out.mkdir()
        patcher = patch.object(self.subject, 'ROOT', self.root);patcher.start();self.addCleanup(patcher.stop)
        self.E = self.subject.E
        self.adapter = self.file('logical.sv')
        self.manifest = self.root/'unused-manifest.json'
        self.plan = {'status':'FILES_VERIFIED','sources':[self.adapter],'dependencies':[self.E.record(self.adapter)],
                     'scope':'development_logical_adapter_only','development':True,'intake':None,'manifest':None}
        prerequisite_path = self.file('primitive.json')
        self.prerequisite = {'report':self.E.record(prerequisite_path),'dependencies':[self.E.record(prerequisite_path)],
                             'scope':'development_logical_adapter_only','source_id':'1'*64,
                             'positive_cases':8,'expected_rejections':15,'native_commands':33}
        mock = patch.object(self.subject.PLAN,'verify_primitive_report',return_value=self.prerequisite)
        self.primitive_mock = mock.start();self.addCleanup(mock.stop)
        self.tools = [self.file('.tools/bin/'+n) for n in ('verilator','iverilog','vvp')]
        mock = patch.object(self.subject.SYS,'tool_inputs',return_value=self.tools);mock.start();self.addCleanup(mock.stop)
        self.runtime = self.file('vectors/inert.mem')
        def runtime_reader(report,out):
            values=[self.subject._record(r) for r in report['runtime_inputs']]
            self.subject.require(values == [self.E.record(self.runtime)],'runtime input coverage differs')
            return values
        mock = patch.object(self.subject,'_runtime_records',side_effect=runtime_reader);mock.start();self.addCleanup(mock.stop)
        self.commands=[];self.cases=[];self.binaries=[]
        self.report_path=self.build_report()

    def file(self,name,text='INERT TEST FILE; NO MODEL OR EXECUTION CLAIM\n'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);return path

    def command(self,name,argv,cwd,text='',timeout=120):
        log=self.out/(name+'.log');log.write_text(text)
        state={'schema':'kwt-sram-command-v1','status':'EXITED','exit_code':0,'timed_out':False,'interrupted':False,
               'argv':list(map(str,argv)),'cwd':str(cwd),'timeout_seconds':timeout,'log':self.E.record(log)}
        path=self.out/(name+'.command.json');self.E.write_json(path,state)
        item={**state,'native_state':self.E.record(path)};self.commands.append(item);return item

    def core_text(self,tasks,verilator):
        engine=self.subject.ENGINE;expected=engine.expected_metrics({'engine':'rowpair','lanes':8,'pipe_mul':1,'result_buffers':2})
        cycles=expected['core_cycles_without_stalls']+1;window=22976+cycles
        lines=[]
        for task in range(tasks):
            row={'task':task,'outputs':25344,'core_cycles':cycles,'load_words':22976,'load_cycles':22976,
                 'output_stalls':1,**{k:expected[k] for k in ('x_reads','w_reads','b_reads')},'window_cycles':window,
                 'result_reads':25344,'result_writes':25344,'overlap_cycles':1,'buffer_wait_cycles':1}
            lines.append('PASS ROWPAIR_BENCH_TASK '+' '.join(f'{key}={row[key]}' for key in engine.TASK_KEYS))
        lines.append(f'PASS ROWPAIR_BENCH_SUITE tasks={tasks} outputs={tasks*25344} resets=3 illegal=3 input_bubbles=1 stalls={tasks} stable={tasks} busy_load_rejections=1 full_window_cycles={tasks*window}')
        tb=self.root/'sim/tb_rowpair_sram.sv'
        lines.append(f'- {tb}:1: Verilog $finish' if verilator else f'{tb}:1: $finish called at 100 (1ps)')
        return '\n'.join(lines)+'\n'

    def build_report(self):
        s=self.subject;producers=s._producer_paths()
        # Only the three ROOT-derived producer paths are absent from the source
        # package in this isolated root. Real imported helpers stay read-only.
        for path in producers:
            if path.is_relative_to(self.root):self.file(str(path.relative_to(self.root)))
        base=[self.file(p) for p in ('src/rtl/memory/kwt_sram_1rw.sv','src/rtl/memory/kwt_sram_bank.sv','src/rtl/kwt_linear_engine_rowpair_sram.sv')]
        core_tb=self.file('sim/tb_rowpair_sram.sv')
        icb=[self.file(p) for p in ('soc/kwt_icb_slave_sram.sv','sim/tb_kwt_icb_slave_sram.sv','sim/tb_kwt_icb_backend3_checked.sv')]
        model=self.file('model/fixed16_acc48.py');export=self.file('sim/vectors/kwt-silence-v1/manifest.json')
        initial=self.E.source_identity(producers,s.CONFIG,self.out/'runner_identity.json')
        plan_paths=list(dict.fromkeys([*producers,self.adapter]))
        self.E.source_identity(plan_paths,s.CONFIG,self.out/'plan_identity.json')
        inputs=list(dict.fromkeys([*producers,self.adapter,*base,core_tb,*icb,*self.tools,model,export,Path(self.prerequisite['report']['path'])]))
        identity=self.E.source_identity(inputs,s.CONFIG,self.out/'source_identity.json')
        for name,option in (('verilator','--version'),('iverilog','-V'),('vvp','-V')):
            self.command(name+'-version',[self.root/'.tools/bin'/name,option],self.out,timeout=20)
        sources=[*base,self.adapter]
        for index,(label,tasks) in enumerate((('real12',12),('signed41-range',2),('icb',None))):
            work=self.out/('core-real' if index==0 else 'core-range' if index==1 else 'icb');work.mkdir()
            binary=work/('obj/simulation' if index==0 else 'simulation.vvp');binary.parent.mkdir(exist_ok=True);binary.write_text('INERT BINARY\n')
            self.binaries.append(self.E.record(binary))
            if index==0:
                build=[self.tools[0],'--binary','--timing','--assert','-Wno-fatal','--top-module','tb_rowpair_sram','--Mdir',work/'obj','-o','simulation','-j','2','--threads','1','-GRESULT_BUFFERS=2','-GPIPE_MUL=1','-GSRAM_BACKEND=3',*sources,core_tb]
            else:
                top='tb_rowpair_sram' if index==1 else 'tb_kwt_icb_backend3_checked'
                params=[f'-P{top}.{k}={v}' for k,v in (('RESULT_BUFFERS',2),('PIPE_MUL',1),('SRAM_BACKEND',3))] if index==1 else []
                build=[self.tools[1],'-g2012','-s',top,'-o',binary,*params,*sources,*([core_tb] if index==1 else icb)]
            self.command(label+'-build',build,work,timeout=180)
            run=[binary] if index==0 else [self.tools[2],binary]
            if tasks:
                run += [f'+VECTORS={work/"vectors"}',f'+TASKS={tasks}','+SEED=20261015','+RANDOM_STALLS=1']
                text=self.core_text(tasks,index==0)
            else:
                text=('ICB_ADAPTER_PASS transactions=193938 hold_checks=86 actual_core_outputs=25348 complete_tasks=1 aborted_tasks=1\n'
                      f'{icb[1]}:1: $finish called at 100 (1ps)\n'
                      'PASS ICB_BACKEND3_MONITOR accepted_outputs=25348 response_holds=86 accepted_commands=193939 accepted_responses=193938 reset_discarded_responses=1\n')
            command=self.command(label+'-run',run,work,text)
            if tasks:
                config={'engine':'rowpair','lanes':8,'tasks':tasks,'pipe_mul':1,'result_buffers':2,'stalls':'random'}
                coverage=s.SYS.accept_core(command,text,config)
                case={'name':label,'status':'PASS','semantics':'two-state' if index==0 else 'four-state','coverage':coverage,'command':command}
            else:case={'name':'icb-four-state','status':'PASS','coverage':s.SYS.accept_icb(command,text),'command':command}
            self.cases.append(case)
        report={'schema':'kwt-sram-adapter-system-v1','status':'PASS','configuration':s.CONFIG,'scope':'development logical adapter',
                'official_validation':'NOT_RUN','official_ppa':'BLOCKED','cpu_soc':'NOT_RUN','supplied_model_functional':'NOT_RUN',
                'synthesis':'NOT_RUN','timing':'NOT_RUN','area':'NOT_RUN','power':'NOT_RUN',
                'started_utc':'2026-10-18T00:00:00+00:00','finished_utc':'2026-10-18T00:01:00+00:00',
                'primitive_prerequisite':self.prerequisite,'plan':{k:v for k,v in self.plan.items() if k!='sources'},
                'selected_sources':[str(self.adapter)],'identity':identity,'commands':self.commands,'cases':self.cases,
                'binaries':self.binaries,'runtime_inputs':[self.E.record(self.runtime)]}
        path=self.out/'result.json';self.E.write_json(path,report);return path

    def verify(self):
        return self.subject.verify_system_report(self.report_path,self.plan,self.manifest,development=True)

    def change(self,mutate):
        report=json.loads(self.report_path.read_text());mutate(report);self.E.write_json(self.report_path,report)

    def test_complete_format_uses_real_core_and_icb_parsers(self):
        result=self.verify()
        self.assertEqual(result['native_commands'],9)
        self.assertEqual([c['name'] for c in result['verified_cases']],['real12','signed41-range','icb-four-state'])
        self.assertEqual([c['coverage']['suite']['outputs'] for c in result['verified_cases'][:2]],[304128,50688])
        self.assertIn(MODULE.resolve(),{Path(r['path']) for r in result['dependencies']})
        self.primitive_mock.assert_called_once_with(self.prerequisite['report']['path'],self.plan,self.manifest,development=True)

    def test_primitive_failure_is_not_bypassed(self):
        self.primitive_mock.side_effect=ValueError('bad primitive evidence')
        with self.assertRaisesRegex(ValueError,'bad primitive'):self.verify()

    def test_missing_stage_or_wrong_configuration_is_rejected(self):
        original=self.report_path.read_text()
        for modify in (lambda r:r['cases'].pop(),lambda r:r['configuration'].update(suite='core'),
                       lambda r:r.update(scope='supplied-model functional core/ICB only'),lambda r:r.update(cpu_soc='PASS')):
            self.report_path.write_text(original);self.change(modify)
            with self.assertRaises(ValueError):self.verify()

    def test_selected_source_or_prerequisite_substitution_is_rejected(self):
        original=self.report_path.read_text()
        for modify in (lambda r:r.update(selected_sources=[]),lambda r:r['primitive_prerequisite'].update(source_id='0'*64),
                       lambda r:r['plan'].update(development=False)):
            self.report_path.write_text(original);self.change(modify)
            with self.assertRaises(ValueError):self.verify()

    def test_noncanonical_or_incomplete_source_identity_is_rejected(self):
        self.change(lambda r:r['identity'].update(source_id='0'*64))
        with self.assertRaisesRegex(ValueError,'canonical'):self.verify()

    def test_runtime_and_binary_bytes_are_rechecked(self):
        self.runtime.write_text('changed runtime bytes\n')
        with self.assertRaisesRegex(ValueError,'identity differs'):self.verify()

    def test_binary_record_hash_is_not_trusted(self):
        self.change(lambda r:r['binaries'][0].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'identity differs'):self.verify()

    def test_native_state_and_compile_backend_cannot_be_substituted(self):
        self.change(lambda r:r['commands'][3]['argv'].__setitem__(17,'-GSRAM_BACKEND=0'))
        with self.assertRaises(ValueError):self.verify()

    def test_native_log_and_saved_coverage_are_rechecked(self):
        self.change(lambda r:r['cases'][2]['coverage'].update(accepted_core_outputs=1))
        with self.assertRaisesRegex(ValueError,'saved coverage'):self.verify()

    def test_no_runtime_vector_or_project_relative_alias_is_accepted(self):
        self.change(lambda r:r.update(runtime_inputs=[]))
        with self.assertRaisesRegex(ValueError,'runtime input coverage'):self.verify()
        item=self.E.record(self.runtime)
        item['project_relative_path']='wrong.mem'
        with self.assertRaisesRegex(ValueError,'project-relative'):self.subject._record(item)


if __name__ == '__main__':unittest.main()
