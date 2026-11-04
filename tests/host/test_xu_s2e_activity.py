"""S2e formal activity guards and actual RTL screening, never server activity/power evidence."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/ppa'))
import xu_s2e_activity_context as context
import xu_s2e_task_activity as collector
import xu_s2e_sram_activity_alias as aliases
import xu_s2e_activity_server as server
SOURCE=Path(os.environ['XU_S2E_SOURCE_ROOT']).resolve() if os.environ.get('XU_S2E_SOURCE_ROOT') else None
EVIDENCE=Path(os.environ['XU_S2E_ACTIVITY_TEST_EVIDENCE']) if os.environ.get('XU_S2E_ACTIVITY_TEST_EVIDENCE') else None
spec=importlib.util.spec_from_file_location('xu_old_activity_test_primitives',ROOT/'tests/host/test_xu_candidate_task_activity.py')
primitives=importlib.util.module_from_spec(spec);spec.loader.exec_module(primitives)
# Private helper module only: the original producer modules remain untouched.
primitives.context=context;primitives.collector=collector;primitives.aliases=aliases;primitives.EVIDENCE=EVIDENCE

def save(name,text):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True,exist_ok=True);(EVIDENCE/name).write_text(text)

def run(argv,cwd,name,timeout=300):
    result=subprocess.run(argv,cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          universal_newlines=True,timeout=timeout)
    save(name,json.dumps(list(map(str,argv)))+'\n'+result.stdout)
    return result

def declarations(ctx):
    window=collector.common_collector().CLEAR_WINDOW_DECLARATIONS.replace('      if (xu_payload_phase) xu_observe_upload();\n','')
    window=ctx.base.once(window,'      // Once per post-reset edge,','      xu_observe_candidate();\n      // Once per post-reset edge,')
    return (ROOT/'tools/ppa/xu_s2e_activity_observer.svh').read_text()+collector.clear_observer(ctx)+window


class XuS2eSyntaxAndPolicyTests(unittest.TestCase):
    def test_receipt_equality_does_not_replace_actual_native_file_rehash(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-native-freeze-') as temporary:
            root=Path(temporary);path=root/'own.svf';path.write_bytes(b'local host fixture, not EDA evidence\n')
            record=dict(path=str(path),bytes=path.stat().st_size,sha256=context.sha(path))
            self.assertEqual(context.checked_frozen_records({str(path):record},'host fixture'),[context.identity(path)])
            for changed in [dict(record,bytes=record['bytes']+1),dict(record,sha256='0'*64),
                            {key:value for key,value in record.items() if key!='bytes'}]:
                with self.assertRaises(ValueError):context.checked_frozen_records({str(path):changed},'host fixture')
            with self.assertRaisesRegex(ValueError,'key/path differs'):
                context.checked_frozen_records({str(root/'wrong'):record},'host fixture')
            path.write_bytes(b'changed native input with identical receipt dictionaries\n')
            with self.assertRaisesRegex(ValueError,'actual bytes/hash differ'):
                context.checked_frozen_records({str(path):record},'host fixture')
            link=root/'link.svf';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'non-symlink'):
                context.checked_record(dict(path=str(link),bytes=path.stat().st_size,sha256=context.sha(path)),'host fixture')

    def test_python36_and_common_tools_remain_frozen(self):
        for name in ['xu_s2e_activity_context.py','xu_s2e_task_activity.py','xu_s2e_sram_activity_alias.py','xu_s2e_activity_server.py']:
            ast.parse((ROOT/'tools/ppa'/name).read_text(),feature_version=(3,6))
        for name,digest in context.FROZEN_TOOLS.items():self.assertEqual(context.sha(ROOT/name),digest,name)
        self.assertEqual(context.MAIN_COMMIT,'5bf123bfead8f2a37f97f3234d4e40ce8201aae9')
        self.assertEqual(context.PROFILE,'s2e-paired-hi')

    def test_missing_or_prepared_task00_is_not_permission_for_full12(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-task00-refusal-') as temporary:
            root=Path(temporary)
            with self.assertRaises(FileNotFoundError):server.checked_task00(root,None,None)
            (root/'result.json').write_text(json.dumps(dict(status='PARTIAL_PREPARED_NOT_SIMULATED',requested_task_ids=[0],tasks=[{}])))
            with self.assertRaisesRegex(ValueError,'actual completed isolated S2e task00'):
                server.checked_task00(root,None,None)

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'Icarus required')
    def test_absolute_lf_phase_preserved(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-lf-') as temporary:
            root=Path(temporary);source=root/'lf.sv';binary=root/'lf.vvp'
            source.write_text('`timescale 1ns/1fs\nmodule lf; reg lfclk=0;\n'+collector.nominal_lf_clock()+
                '\ninitial begin #152587891; if(xu_lf_static_checks!=10000) $fatal(1,"LF count"); '+
                '$display("XU_S2E_LF_PHASE_PASS edges=10000 max_phase_error_fs=1"); $finish; end endmodule\n')
            built=run(['iverilog','-g2012','-s','lf','-o',str(binary),str(source)],root,'lf-build.log')
            self.assertEqual(built.returncode,0,built.stdout)
            actual=run(['vvp',str(binary)],root,'lf-simulation.log')
            self.assertEqual(actual.returncode,0,actual.stdout)
            self.assertIn('edges=10000 max_phase_error_fs=1',actual.stdout)


@unittest.skipUnless(SOURCE,'explicit frozen XU_S2E_SOURCE_ROOT required')
class XuS2eActualSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ctx=context.Context(SOURCE)

    def test_real_context_full_tb_and_future_mapping_refusal(self):
        self.ctx.recheck()
        text=collector.generate_tb(self.ctx)
        for marker in ['task observe_result_reads;','xu_result_words!==16\'hffff','xu_result_response_pending',
                       'xu_clear_w_commits!=16384','xu_clear_x_commits!=64','xu_clear_bias_commits!=256',
                       'xu_result_legacy_reads!=25344','xu_result_packed_reads!=12672',
                       'hf_nominal_period_ns=6.666666666666667 precision_fs=1',
                       'xu_lf_target_ns=xu_lf_half_index*15258.7890625;',
                       '$toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut")',
                       'actual_commits=1 fifo_reset_empty=1',"`ACCEL.cmd_addr[11:0]!=12'h0e0"]:
            self.assertIn(marker,text)
        save('generated-s2e-full-tb.sv',text)
        with tempfile.TemporaryDirectory(prefix='xu-s2e-mapped-refusal-') as temporary:
            root=Path(temporary)
            for state in [dict(status='RUNNING_NOT_QUALIFIED'),dict(status='EXECUTED_NOT_QUALIFIED',source_before=dict(name='s2c-autogroup'))]:
                (root/'state.json').write_text(json.dumps(state))
                with self.assertRaises(ValueError):context.checked_mapped_context(SOURCE,root)

    def test_all_336_times_67_aliases_preserve_unknowns_and_reject_tamper(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-alias-') as temporary:
            root=Path(temporary);mapping=aliases.generate(SOURCE,root/'aliases')
            path=root/'aliases/xu_s2e_sram_activity_alias.mapping.json'
            _,pairs=aliases.validate_mapping(path)
            self.assertEqual((mapping['macro_count'],mapping['alias_bit_count'],len(pairs)),(336,22512,22512))
            raw=root/'raw.saif';primitives.raw_saif(raw,pairs)
            original=raw.read_bytes();receipt=aliases.normalize(raw,path,root/'normalized.saif')
            self.assertEqual(raw.read_bytes(),original)
            self.assertEqual(receipt['alias_unknown_bit_ticks'],22512*5)
            missing=root/'missing.saif';primitives.raw_saif(missing,pairs,missing=next(iter(pairs)))
            with self.assertRaises(ValueError):aliases.normalize(missing,path,root/'bad-normalized.saif')
            self.assertFalse((root/'bad-normalized.saif').exists())
            forged=copy.deepcopy(mapping);forged['profile']='s2c-autogroup'
            fp=root/'forged.json';fp.write_text(json.dumps(forged))
            with self.assertRaisesRegex(ValueError,'profile differs'):aliases.validate_mapping(fp)
            save('alias-normalization-receipt.json',json.dumps(receipt,indent=2)+'\n')

    @unittest.skipUnless(shutil.which('riscv64-unknown-elf-gcc'),'actual RISC-V compiler required')
    def test_actual_paired_hi_firmware_with_unchanged_clear_wrapper_builds(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-firmware-') as temporary:
            root=Path(temporary)
            _,record=collector.compile_firmware(self.ctx,root,'riscv64-unknown-elf-')
            self.assertEqual(record['configuration'],self.ctx.configuration)
            self.assertIn('-DXU_HARDWARE_PAIRED_HI=1',record['command'])
            self.assertIn('-DXU_HARDWARE_AUTO_GROUP=1',record['command'])
            self.assertGreater(record['memory']['itcm_remaining_bytes'],0)
            for name in ['firmware-build.json','firmware-build.log','firmware-sections.log','firmware.dump','xu_s2e_clear_main.c']:
                save('actual-local-'+name,(root/name).read_text())

    @unittest.skipUnless(shutil.which('iverilog'),'Icarus required')
    def test_full336_macro_and_all22512_direct_pin_paths_elaborate(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-full-elab-') as temporary:
            root=Path(temporary)
            # Deliberately geometry only: this is path elaboration, never vendor
            # behavior, VCS toggle collection, timing, or energy evidence.
            model=root/'open-geometry-only.v'
            model.write_text('module RAMSP1024X16(output reg [15:0] Q,input CLK,CEN,GWEN,RET1N, '+
                'input [15:0] WEN,D,input [9:0] A,input [2:0] EMA,input [1:0] EMAW); '+
                'reg [63:0] mem [0:255]; endmodule\n')
            mapping=aliases.generate(SOURCE,root/'aliases',placement='include')
            text=collector.generate_tb(self.ctx);point=text.rindex('endmodule')
            tb=root/'full.sv';tb.write_text(text[:point]+Path(mapping['observer_source']['path']).read_text()+text[point:])
            excluded={self.ctx.base.RTL/'general/sirv_sim_ram.v',self.ctx.base.RTL/'perips/mem_1024x16.sv'}
            sources=sorted(p for p in self.ctx.base.RTL.rglob('*') if p.suffix in ('.v','.sv') and p not in excluded)
            sources += [ROOT/'tools/ppa'/name for name in ['xu_sirv_sram_adapter.sv','xu_weight_sram_adapter.sv','xu_shared_icb_sram.sv','xu_soc_ppa_top.sv']]
            sources += [model,tb]
            filelist=root/'rtl.f';filelist.write_text('\n'.join(map(str,sources))+'\n')
            command=['iverilog','-g2012','-s','tb_xu_soc_ppa','-DDISABLE_SV_ASSERTION=1','-DARM_UD_MODEL','-DXU_TASK_ACTIVITY_HOST_CHECK']
            command += ['-I'+str(self.ctx.base.RTL/name) for name in ['core','perips','perips/apb_i2c']]
            command += ['-o',str(root/'soc.vvp'),'-f',str(filelist)]
            actual=run(command,root,'full336-macro22512-path-elaboration.log')
            self.assertEqual(actual.returncode,0,actual.stdout)
            save('full336-elaboration-sources.json',json.dumps(dict(status='ELABORATED_NOT_SIMULATED_OPEN_GEOMETRY_ONLY',
                macro_count=336,pin_bits=22512,sources=[context.identity(p) for p in sources]),indent=2)+'\n')

    def test_hidden_tracked_main_and_child_source_changes_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-hidden-source-') as temporary:
            root=Path(temporary);clone=root/'source'
            self.assertEqual(run(['git','clone','--shared','--no-checkout',str(SOURCE),str(clone)],root,'hidden-clone.log').returncode,0)
            self.assertEqual(run(['git','checkout','--detach',context.MAIN_COMMIT],clone,'hidden-checkout.log').returncode,0)
            child=clone/'third-party/e203_hbirdv2'
            self.assertEqual(run(['git','clone','--shared',str(SOURCE/'third-party/e203_hbirdv2'),str(child)],clone,'hidden-child-clone.log').returncode,0)
            self.assertEqual(run(['git','checkout','--detach','a0767db69628ef30e53de2d1e93dd0360c0ccf76'],child,'hidden-child-checkout.log').returncode,0)
            context.source_identity(clone)
            for repo,name in [(clone,'tests/e203/tb_accel_soc.sv'),(child,'rtl/e203/perips/accel_icb_slave.v')]:
                path=repo/name;original=path.read_bytes()
                self.assertEqual(run(['git','update-index','--assume-unchanged',name],repo,'hidden-flag-'+path.name+'.log').returncode,0)
                path.write_bytes(original+b'\n// deliberately hidden host source mutation\n')
                with self.assertRaisesRegex(ValueError,'bytes differ'):context.source_identity(clone)
                path.write_bytes(original)
                self.assertEqual(run(['git','update-index','--no-assume-unchanged',name],repo,'hidden-unflag-'+path.name+'.log').returncode,0)
                context.source_identity(clone)

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'actual Icarus required')
    def test_real_wrapper_all99_rows_and_destructive_faults(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-actual-observer-') as temporary:
            root=Path(temporary);source=root/'probe.sv'
            source.write_text((ROOT/'tests/ppa/tb_xu_s2e_task_observer.sv').read_text().replace('@DECLARATIONS@',declarations(self.ctx)))
            primitives.golden_file(root/'golden.hex');binary=root/'probe.vvp';perips=self.ctx.base.RTL/'perips'
            command=['iverilog','-g2012','-DXU_TASK_ACTIVITY_HOST_CHECK','-s','tb_xu_s2e_task_observer','-o',str(binary),str(source)]+[str(perips/n) for n in primitives.PERIPS_SOURCES]
            built=run(command,root,'observer-build.log')
            self.assertEqual(built.returncode,0,built.stdout)
            cases=[(0,None),(1,'candidate setup/data write before first source request'),
                   (2,'fixture-mismatched actual W commit'),(3,'nonzero actual X clear commit'),
                   (4,'first source request changed before acceptance'),(5,'first source request changed before acceptance'),
                   (6,'POP before all owned words read'),(7,'unexpected pretask MMIO read'),
                   (8,'W cursor setup'),(9,'result response absent/changed before retirement'),
                   (10,'incomplete/duplicate/incorrect owned FIFO result')]
            for mode,expected in cases:
                actual=run(['vvp',str(binary),'+MODE='+str(mode),'+GOLDEN='+str(root/'golden.hex')],root,'observer-mode-%d.log'%mode)
                if expected is None:
                    self.assertEqual(actual.returncode,0,actual.stdout)
                    self.assertIn('XU_S2E_OBSERVER_RTL_PASS',actual.stdout)
                    self.assertIn('actual_result_reads=38016 paired_hi=12672',actual.stdout)
                else:
                    self.assertNotEqual(actual.returncode,0,actual.stdout);self.assertIn(expected,actual.stdout)
            save('generated-actual-observer-probe.sv',source.read_text())

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'actual Icarus required')
    def test_actual_platform_reset_chain_observation_is_preserved(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2e-reset-') as temporary:
            root=Path(temporary);source=root/'reset.sv';binary=root/'reset.vvp'
            source.write_text((ROOT/'tests/ppa/tb_xu_s2c_reset_guard.sv').read_text().replace('@DECLARATIONS@',declarations(self.ctx)))
            perips=self.ctx.base.RTL/'perips';reset=['sirv_ResetCatchAndSync_2.v','sirv_AsyncResetRegVec_129.v','sirv_AsyncResetReg.v']
            command=['iverilog','-g2012','-DXU_TASK_ACTIVITY_HOST_CHECK','-s','tb_xu_s2c_reset_guard','-o',str(binary),str(source)]+[str(perips/n) for n in primitives.PERIPS_SOURCES+reset]
            built=run(command,root,'reset-build.log');self.assertEqual(built.returncode,0,built.stdout)
            for mode,expected in [(0,None),(1,'request before actual reset ready'),(2,'request before actual reset ready'),
                                  (3,'no actual accelerator clock sampled asserted reset'),(4,'reset reasserted'),
                                  (5,'reset.*unknown'),(6,'FIFO logical ownership was not reset'),
                                  (7,'unknown commit/FIFO ownership state'),(8,'unknown commit/FIFO ownership state')]:
                actual=run(['vvp',str(binary),'+MODE='+str(mode)],root,'reset-mode-%d.log'%mode)
                if expected is None:
                    self.assertEqual(actual.returncode,0,actual.stdout)
                    self.assertIn('XU_RESET_GUARD_PASS actual_20stage_chain=1',actual.stdout)
                else:self.assertNotEqual(actual.returncode,0,actual.stdout);self.assertRegex(actual.stdout,expected)


if __name__=='__main__':unittest.main()
