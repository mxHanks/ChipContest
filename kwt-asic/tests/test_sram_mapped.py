"""A mapped simulation must use explicit functional cells/macros and exact input."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'scripts/verify/run_sram_mapped.py'


class SRAMMappedInputs(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(),'mapped comparison entry is not implemented')
        spec=importlib.util.spec_from_file_location('sram_mapped',MODULE)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_renames_only_verified_top_without_rewriting_logic(self):
        text='module kwt_icb_slave_sram(input clk); wire keep_net; endmodule\n'
        changed=self.m.rename_mapped_top(text)
        self.assertEqual(changed,text.replace('module kwt_icb_slave_sram(','module kwt_icb_slave_sram_mapped('))
        with self.assertRaises(ValueError):self.m.rename_mapped_top('module wrong; endmodule')
        with self.assertRaises(ValueError):self.m.rename_mapped_top(text+text)

    def test_opaque_cells_get_real_behavior_not_empty_simulation(self):
        text=self.m.logical_macro_models({'known_128':(16,128),'known_1024':(16,1024)})
        self.assertIn('module \\known_128 ',text)
        self.assertIn('module \\known_1024 ',text)
        self.assertEqual(text.count('kwt_sram_1rw #'),2)
        self.assertIn('.BACKEND(0)',text)
        self.assertIn('.CHECKS(1)',text)
        self.assertNotIn('blackbox',text)
        with self.assertRaises(ValueError):self.m.logical_macro_models({'wrong':(32,128)})

    def test_complete_task_and_suite_markers_required(self):
        good=('MAPPED_RECOVERY_PASS soft_aborts=1 pending_resets=1\n'
              'MAPPED_TASK_PASS task=0 outputs=25344\n'
              'MAPPED_PROTOCOL_PASS errors=12 holds=835 final_hi=1 ack=1 requests=300001 responses=300000\n'
              'MAPPED_PAIR_PASS tasks=1 outputs=25344 transactions=300000 trace_checks=900000\n')
        self.assertEqual(self.m.validate_mapped_log(good,1)['outputs'],25344)
        for bad in (good.replace('outputs=25344','outputs=25343',1),good+good,good.splitlines()[1],
                    '\n'.join(good.splitlines()[1:]),
                    good.replace('pending_resets=1','pending_resets=0'),
                    good.replace('final_hi=1','final_hi=0'),good.replace('ack=1','ack=0'),
                    good.replace('errors=12','errors=0'),good.replace('requests=300001','requests=300000'),
                    good.replace('responses=300000','responses=299999')):
            with self.assertRaises(ValueError):self.m.validate_mapped_log(bad,1)

    def test_alias_configuration_changes_scheduling_only_one_net(self):
        text=self.m.mapped_alias_configuration()
        self.assertEqual(text,'`verilator_config\nsplit_var -module "kwt_icb_slave_sram_mapped" -var "y_snapshot"\n')
        self.assertNotIn('lint_off',text)

    def test_compile_rejects_any_remaining_loop_or_failed_split(self):
        self.m.accept_mapped_compile('normal compile\n')
        for warning in ['UNOPTFLAT','SPLITVAR','UNSUPPORTED','PINMISSING']:
            with self.assertRaises(ValueError):self.m.accept_mapped_compile('%Warning-'+warning+': bad\n')

    def test_alias_report_rejects_repeated_version_instead_of_variant_runs(self):
        value={'schema':'kwt-mapped-alias-diagnostic-v1','status':'PASS','inputs':[],
               'commands':[{'log':{'path':'version.log'}}]*10,
               'cases':dict.fromkeys(('baseline','metacomment','configuration'),{})}
        with patch.object(Path,'read_text',return_value=json.dumps(value)), \
             patch.object(self.m.E,'verify_records'),patch.object(self.m.E,'completion_error',return_value=None):
            with self.assertRaises(ValueError):self.m.accepted_alias_report('in-memory-report.json')

    def test_checker_report_requires_source_identity_even_when_all_logs_pass(self):
        names=['version','compile']+[x[0] for x in self.m.CHECKER.POSITIVES.values()]+[x[0] for x in self.m.CHECKER.NEGATIVES.values()]
        value={'schema':'kwt-mapped-checker-tests-v1','status':'PASS','inputs':[],
               'commands':[{'log':{'path':name+'.log'}} for name in names],
               'cases':[{'case':i} for i in [*self.m.CHECKER.POSITIVES,*self.m.CHECKER.NEGATIVES]]}
        with patch.object(Path,'read_text',return_value=json.dumps(value)), \
             patch.object(self.m.E,'verify_records'),patch.object(self.m.E,'completion_error',return_value=None), \
             patch.object(self.m.CHECKER,'accept_rejection'):
            with self.assertRaises(ValueError):self.m.accepted_checker_report('in-memory-report.json')

    def test_identity_cannot_omit_required_sources_or_corrupt_source_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'checker.sv';source.write_text('module checker; endmodule\n')
            identity=self.m.E.source_identity([source],{'tasks':1},root/'identity.json')
            report={'identity':identity,'configuration':{'tasks':1},'inputs':identity['inputs'].copy()}
            self.m.require_input_identity(report,[source])
            report['inputs']=[]
            with self.assertRaises(ValueError):self.m.require_input_identity(report,[source])

    def test_canonical_probe_manifest_binds_sources_before_binary_append(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'checker.sv';source.write_text('fixed checker\n')
            binary=root/'simulation';binary.write_text('fixed binary\n');manifest=root/'source_identity.json'
            identity=self.m.E.source_identity([source],{'jobs':1},manifest)
            identity['inputs'].append(self.m.E.record(binary)) # Historical producer shared this list.
            value={'identity':identity,'configuration':{'jobs':1},'inputs':identity['inputs'].copy()}
            self.m.require_input_identity(value,[source],manifest)
            identity['source_id']='f'*64
            with self.assertRaises(ValueError):self.m.require_input_identity(value,[source],manifest)

    def test_native_coverage_and_variant_arguments_are_exact(self):
        with self.assertRaises(ValueError):
            self.m._native_by_name({'commands':[{'log':{'path':'version.log'}}]*10},['version'])
        with self.assertRaises(ValueError):
            self.m._expect_argv({'argv':['verilator','--lint-only'],'cwd':str(ROOT)},
                                ['verilator','--lint-only','+define+KWT_ALIAS_SPLIT'],ROOT)
            report['inputs']=identity['inputs'].copy();identity['source_id']='0'*64
            with self.assertRaises(ValueError):self.m.require_input_identity(report,[source])

    def test_required_observables_have_drivers_but_unused_alias_need_not(self):
        names=('output_count','engine_busy','core_done_sticky','software_done','window_active','y_snapshot_last','rsp_pop_y')
        top={'netnames':{name:{'bits':[i]} for i,name in enumerate(names,100)},
             'cells':{name:{'type':'DFFR_X1','port_directions':{'Q':'output'},'connections':{'Q':[i]}}
                      for i,name in enumerate(names,100)}}
        top['netnames']['engine_y_ready']={'bits':[999]}
        accepted=self.m.mapped_observable_report(top)
        self.assertEqual(accepted['status'],'PASS')
        self.assertEqual(accepted['unused_aliases']['engine_y_ready']['undriven_bits'],[999])
        top['cells'].pop('rsp_pop_y')
        with self.assertRaises(ValueError):self.m.mapped_observable_report(top)

    def make_reused_fixture(self,root):
        old=root/'accepted';old.mkdir();new=root/'new';new.mkdir()
        source=root/'source.sv';source.write_text('module source; endmodule\n')
        mapping=root/'mapping.json';mapping.write_text('{}\n')
        tools={name:root/name for name in ('yosys','verilator')}
        for path in tools.values():path.write_text('fixed tool identity\n')
        generated={}
        for name in ('mapped_top.v','logical_macros.sv','mapped_alias.vlt','cells.ys'):
            (old/name).write_text('fixed '+name+'\n');(new/name).write_text('fixed '+name+'\n')
            generated[name]=self.m.E.record(new/name)
        (old/'standard_cells.v').write_text('fixed functional cells\n')
        (old/'obj').mkdir();binary=old/'obj/simulation';binary.write_text('fixed simulation binary\n')
        config={'tasks':1,'top':'tb_kwt_icb_mapped_pair','jobs':2,'memory_model':'validated logical 1RW behavior'}
        required=[source,mapping,*tools.values()]
        identity=self.m.E.source_identity(required,config,old/'source_identity.json')
        probes={}
        for name in ('alias','checker'):
            path=root/(name+'.json');path.write_text('{}\n');probes[name+'_probe']=self.m.E.record(path)
        compile_argv=[tools['verilator'],'--binary','--timing','--assert','-Wno-fatal',
            '--top-module','tb_kwt_icb_mapped_pair','--Mdir',old/'obj','-o','simulation','-j','2','--threads','1',
            source,*[old/name for name in ('mapped_top.v','logical_macros.sv','standard_cells.v','mapped_alias.vlt')]]
        run_text=('MAPPED_RECOVERY_PASS soft_aborts=1 pending_resets=1\n'
            'MAPPED_TASK_PASS task=0 outputs=25344\n'
            'MAPPED_PROTOCOL_PASS errors=12 holds=835 final_hi=1 ack=1 requests=300001 responses=300000\n'
            'MAPPED_PAIR_PASS tasks=1 outputs=25344 transactions=300000 trace_checks=900000\n')
        commands=[]
        for name,argv,text in (
            ('cells',[tools['yosys'],'-Q','-s','cells.ys'],'KWT_SRAM_FUNCTIONAL_CELLS_COMPLETE\n'),
            ('compile',compile_argv,'compile complete\n'),
            ('run',[binary,f'+VECTORS={old/"vectors"}','+TASKS=1'],run_text)):
            log=old/(name+'.log');log.write_text(text)
            commands.append({'argv':list(map(str,argv)),'cwd':str(old),'log':self.m.E.record(log)})
        value={'schema':'kwt-sram-mapped-functional-v1','status':'PASS','phase':'complete',
            'configuration':config,'identity':identity,'inputs':identity['inputs']+[
                *[self.m.E.record(old/name) for name in (*generated,'standard_cells.v')],self.m.E.record(binary),*probes.values()],
            'commands':commands,'mapping_report':self.m.E.record(mapping),'binary':self.m.E.record(binary),**probes}
        path=old/'result.json';path.write_text(json.dumps(value))
        return path,mapping,required,[source],tools,generated,value

    def test_reuse_allows_runtime_task_change_with_complete_same_build(self):
        with tempfile.TemporaryDirectory() as directory:
            path,mapping,required,sources,tools,generated,value=self.make_reused_fixture(Path(directory))
            # These are current compile dependencies for a future 12-task run;
            # the accepted build ran one task, a runtime-only choice.
            with patch.object(self.m.E,'completion_error',return_value=None), \
                 patch.object(self.m,'accepted_alias_report'),patch.object(self.m,'accepted_checker_report'):
                accepted=self.m.accepted_reused_build(path,mapping,required,sources,tools,generated)
            self.assertEqual(accepted['configuration']['tasks'],1)

    def test_reuse_rejects_stale_source_model_mapping_binary_or_compile_inputs(self):
        for changed in ('source','model','mapping','binary','compile'):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as directory:
                path,mapping,required,sources,tools,generated,value=self.make_reused_fixture(Path(directory))
                if changed=='source':sources[0].write_text('different source\n')
                elif changed=='model':(path.parent/'standard_cells.v').write_text('different model\n')
                elif changed=='mapping':value['mapping_report']['sha256']='0'*64
                elif changed=='binary':Path(value['binary']['path']).write_text('different binary\n')
                else:value['commands'][1]['argv'].remove(str(sources[0]))
                path.write_text(json.dumps(value))
                with patch.object(self.m.E,'completion_error',return_value=None), \
                     patch.object(self.m,'accepted_alias_report'),patch.object(self.m,'accepted_checker_report'):
                    with self.assertRaises(ValueError):self.m.accepted_reused_build(path,mapping,required,sources,tools,generated)


if __name__=='__main__':unittest.main()
