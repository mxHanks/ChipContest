"""Frozen S2c activity producer development checks; never server qualification.

Set XU_S2C_SOURCE_ROOT to the clean, exact d276b55/49a9436 source checkout.
All generated outputs and deliberately damaged clones stay in temporary dirs.
"""
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ppa'))
import xu_candidate_activity_context as context
import xu_candidate_task_activity as collector
import xu_candidate_sram_activity_alias as aliases

SOURCE = Path(os.environ['XU_S2C_SOURCE_ROOT']).resolve() if os.environ.get('XU_S2C_SOURCE_ROOT') else None
EVIDENCE = Path(os.environ['XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE']) if os.environ.get('XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE') else None
PERIPS_SOURCES = ['BiasBankCache.sv','LinearAutoGroupCore.sv','LinearCachedCore.sv','LinearComputeCore.sv',
    'DotProductEngine.sv','MacController.sv','MacPEArray.sv','MacPE.sv','XRowBuffer.sv','WeightBankArray.sv',
    'WeightBank.sv','Sram1024x16.sv','mem_1024x16.sv','accel_icb_slave.v']


def save(name, value):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE/name).write_text(value)


def run(command, cwd, name, timeout=180):
    result = subprocess.run(command, cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
    save(name, json.dumps(dict(command=command,cwd=str(cwd),returncode=result.returncode))+'\n'+result.stdout)
    return result


def signed(value, bits):
    value &= (1 << bits)-1
    return value-(1 << bits) if value & (1 << (bits-1)) else value


def golden_file(path):
    w = [signed(0x8000 if a%17==0 else (0x7fff if a%19==0 else a*7-1000),16) for a in range(16384)]
    x = [signed(0x8000 if a%13==0 else (0x7fff if a%11==0 else a*3-64),16) for a in range(6336)]
    bias = [signed(0x7fffffffff-c if c%2 else 0x8000000000+c,40) for c in range(256)]
    values = [bias[c]+sum(x[r*64+k]*w[k*256+c] for k in range(64)) for r in range(99) for c in range(256)]
    assert all(-(1<<47) <= v < 1<<47 for v in values)
    path.write_text(''.join('%012x\n' % (v & ((1<<48)-1)) for v in values))


def observer_declarations(ctx):
    window = collector.common_collector().CLEAR_WINDOW_DECLARATIONS.replace('      if (xu_payload_phase) xu_observe_upload();\n','')
    window = ctx.base.once(window,'      // Once per post-reset edge,','      xu_observe_candidate();\n      // Once per post-reset edge,')
    return (ROOT/'tools/ppa/xu_s2c_activity_observer.svh').read_text()+collector.clear_observer(ctx)+window


def rtl_probe(ctx):
    return (ROOT/'tests/ppa/tb_xu_s2c_task_observer.sv').read_text().replace('@DECLARATIONS@',observer_declarations(ctx))


def reset_probe(ctx):
    return (ROOT/'tests/ppa/tb_xu_s2c_reset_guard.sv').read_text().replace('@DECLARATIONS@',observer_declarations(ctx))


def raw_saif(path, pairs, missing=None, extra=None):
    root=['SAIFILE',['SAIFVERSION','"2.0"'],['TIMESCALE','1','ns'],['DURATION','10']]
    instances={}
    all_signals=[(p,'NET',dict(T0=2,T1=3,TX=4,TZ=1,TB=0,TC=i%3)) for i,p in enumerate(sorted(pairs)) if p!=missing]
    all_signals.append(('tb_xu_soc_ppa/dut/literal.dot','NET',dict(T0=1,T1=2,TX=3,TZ=1,TB=3,TC=5,IG=2)))
    if extra: all_signals.append(extra)
    for name,kind,stats in all_signals:
        parts=name.split('/')
        for depth in range(1,len(parts)):
            key='/'.join(parts[:depth])
            if key not in instances:
                node=['INSTANCE',aliases.atom(parts[depth-1])]
                (root if depth==1 else instances['/'.join(parts[:depth-1])]).append(node)
                instances[key]=node
        parent=instances['/'.join(parts[:-1])]
        section=next((n for n in parent[2:] if n[0]==kind),None)
        if section is None: section=[kind];parent.append(section)
        section.append([aliases.atom(parts[-1])]+[[key,str(value)] for key,value in stats.items()])
    with path.open('w') as output: aliases.write_sexpr(output,root)


class CandidateSyntaxTests(unittest.TestCase):
    def test_python36_syntax_and_frozen_common_bytes(self):
        for name in ('xu_candidate_activity_context.py','xu_candidate_task_activity.py','xu_candidate_sram_activity_alias.py'):
            p=ROOT/'tools/ppa'/name
            ast.parse(p.read_text(),filename=str(p),feature_version=(3,6))
        for name,digest in context.FROZEN_TOOLS.items(): self.assertEqual(context.sha(ROOT/name),digest,name)

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'Icarus required')
    def test_actual_lf_absolute_phase_has_no_accumulated_rounding(self):
        with tempfile.TemporaryDirectory(prefix='xu-lf-phase-') as t:
            d=Path(t);source=d/'lf.sv';binary=d/'lf.vvp'
            source.write_text('`timescale 1ns/1fs\nmodule lf; reg lfclk=0;\n'+collector.nominal_lf_clock()+
                '\ninitial begin #152587891; if(xu_lf_static_checks!=10000) $fatal(1,"LF count"); '+
                '$display("XU_LF_PHASE_PASS edges=10000 max_phase_error_fs=1"); $finish; end endmodule\n')
            result=run(['iverilog','-g2012','-s','lf','-o',str(binary),str(source)],d,'lf-phase-build.log')
            self.assertEqual(result.returncode,0,result.stdout)
            result=run(['vvp',str(binary)],d,'lf-phase-simulation.log')
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertIn('XU_LF_PHASE_PASS edges=10000 max_phase_error_fs=1',result.stdout)

    def test_candidate_window_checks_actual_integer_timestamps_without_log_rewrite(self):
        legacy=dict(begin=dict(cycle=13,tick=86666667),end=dict(cycle=100,tick=666666667))
        layer=dict(cycles=88)
        log=('XU_TASK_CLEAR_BEGIN task=7 cycle=1 tick=6666667\n'
             'XU_TASK_CLEAR_LAST_WRITE task=7 cycle=9 tick=60000000 writes=33697\n'
             'XU_SOURCE_REQUEST task=7 cycle=10 tick=66666667\n'
             'XU_SOURCE_ACCEPT task=7 cycle=13 tick=86666667\n'
             'XU_TASK_WINDOW task=7 request_cycle=10 accept_cycle=13 end_cycle=100 initial_wait_cycles=3 '
             'legacy_inclusive_cycles=88 formal_inclusive_cycles=91 formal_elapsed_cycles=90\n')
        window=collector.checked_window(log,7,layer,legacy)
        self.assertEqual(window['initial_source_wait_cycles'],3)
        self.assertEqual(window['duration_ticks'],600000000)
        self.assertEqual(window['pretask_clear']['original_task_destination_setup_writes_before_source'],0)
        for damaged in (log.replace('tick=66666667','tick=66666677'),log.replace('formal_elapsed_cycles=90','formal_elapsed_cycles=89'),
                        log.replace('XU_SOURCE_REQUEST task=7','XU_SOURCE_REQUEST task=8'),log+log):
            with self.assertRaises(ValueError): collector.checked_window(damaged,7,layer,legacy)

    def test_actual_simulation_fatal_is_not_hidden_by_later_missing_lf_marker(self):
        with self.assertRaisesRegex(ValueError,'unknown commit/FIFO ownership state'):
            collector.checked_log(None,'Fatal: XU_CANDIDATE_REJECT unknown commit/FIFO ownership state\n',0)


@unittest.skipUnless(SOURCE,'explicit XU_S2C_SOURCE_ROOT is required')
class CandidateActivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx=context.Context(SOURCE)

    def test_full_context_and_independent_candidate_tb(self):
        self.ctx.recheck()
        text=collector.generate_tb(self.ctx)
        self.assertEqual(text.count('xu_observe_candidate();'),1)
        self.assertIn('$set_gate_level_monitoring("rtl_on")',text)
        self.assertIn('$toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut")',text)
        self.assertIn('hf_nominal_period_ns=6.666666666666667 precision_fs=1',text)
        self.assertIn('xu_lf_target_ns=xu_lf_half_index*15258.7890625;',text)
        self.assertNotIn('xu_observe_upload()',text)
        self.assertIn('task_setup_writes=0 actual_commits=1 fifo_reset_empty=1',text)
        self.assertIn('      xu_observe_candidate_reset_window();',text)
        save('generated-candidate-tb.sv',text)

    @unittest.skipUnless(shutil.which('riscv64-unknown-elf-gcc'),'actual RISC-V toolchain required')
    def test_actual_riscv_firmware_and_partial_prepare(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2c-prepare-') as t:
            d=Path(t)
            model=d/'identity-only-not-simulated.v'
            model.write_text('// Geometry-only identity placeholder; no simulation/power model.\nreg [63:0] mem [0:255];\n')
            netlist=d/'identity-only-netlist.v';netlist.write_text('// identity only, never simulated\n')
            out=d/'prepared'
            command=[sys.executable,str(ROOT/'tools/ppa/xu_candidate_task_activity.py'),
                '--source-root',str(SOURCE),'--tool-root',str(ROOT),'--profile','s2c-autogroup','--out',str(out),
                '--vendor-model',str(model),'--netlist',str(netlist),'--constraints',str(ROOT/'tools/ppa/xu_full_soc.sdc'),
                '--task-ids','7','--prepare-only']
            result=run(command,d,'candidate-prepare.log',300)
            self.assertEqual(result.returncode,0,result.stdout)
            report=json.loads((out/'result.json').read_text())
            self.assertEqual(report['status'],'PARTIAL_PREPARED_NOT_SIMULATED')
            self.assertEqual(report['requested_task_ids'],[7])
            self.assertFalse(report['taskset_complete'])
            self.assertEqual(report['configuration']['source_context'],self.ctx.source)
            self.assertEqual(report['configuration']['sram_alias']['macro_count'],336)
            self.assertEqual(report['configuration']['sram_alias']['alias_bit_count'],22512)
            self.assertEqual(report['configuration']['numeric_format'],'signed16/40/48')
            self.assertIn('-DXU_HARDWARE_AUTO_GROUP=1',report['firmware_build']['command'])
            self.assertIn('-DXU_HARDWARE_PACK32=1',report['firmware_build']['command'])
            self.assertGreater(report['firmware_build']['memory']['itcm_remaining_bytes'],0)
            manifest=json.loads((out/'task_07/vectors/input-manifest.json').read_text())
            self.assertEqual(manifest['global_task_id'],7)
            self.assertEqual(manifest['original_layer'],'layer_07')
            self.assertEqual(manifest['simulator_layer'],'layer_00')
            save('candidate-partial-prepare-result.json',json.dumps(report,indent=2)+'\n')
            for name in ('firmware-build.log','firmware-sections.log','firmware.dump','xu_s2c_clear_main.c'):
                save(name,(out/'firmware'/name).read_text())

    def test_strict_source_blob_guard_rejects_assume_unchanged_edits(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2c-damaged-clone-') as t:
            clone=Path(t)/'source'
            result=run(['git','clone','--shared','--no-checkout',str(SOURCE),str(clone)],Path(t),'clone.log')
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertEqual(run(['git','checkout',context.MAIN_COMMIT],clone,'checkout.log').returncode,0)
            child=clone/'third-party/e203_hbirdv2'
            self.assertEqual(run(['git','clone','--shared',str(SOURCE/'third-party/e203_hbirdv2'),str(child)],clone,'child-clone.log').returncode,0)
            self.assertEqual(run(['git','checkout','49a9436e01ea8ceeead94242e4a99c16e31a0865'],child,'child-checkout.log').returncode,0)
            context.source_identity(clone)
            target='tests/e203/tb_accel_soc.sv'
            self.assertEqual(run(['git','update-index','--assume-unchanged',target],clone,'assume-unchanged.log').returncode,0)
            with (clone/target).open('a') as stream: stream.write('// deliberately hidden tracked source corruption\n')
            with self.assertRaisesRegex(ValueError,'bytes differ'): context.source_identity(clone)

    def test_complete_22512_pin_alias_normalization_preserves_unknowns_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2c-alias-') as t:
            d=Path(t)
            mapping=aliases.generate(SOURCE,d/'aliases')
            mp=d/'aliases/xu_candidate_sram_activity_alias.mapping.json'
            _,pairs=aliases.validate_mapping(mp)
            self.assertEqual((mapping['macro_count'],len(pairs)),(336,22512))
            self.assertEqual({m['group'] for m in mapping['macros']},{'shared','itcm','dtcm','accelerator_weights'})
            self.assertTrue(all('u_linear_compute_core.core.weightBanks' in m['instance'] for m in mapping['macros'] if m['group']=='accelerator_weights'))
            raw=d/'task.saif';raw_saif(raw,pairs)
            before=aliases.identity(raw)
            receipt=aliases.normalize(raw,mp,d/'normalized.saif')
            self.assertEqual(aliases.identity(raw),before)
            self.assertEqual(receipt['alias_bit_count'],22512)
            self.assertEqual(receipt['mapped_pin_bits_added_as_port'],22512)
            self.assertEqual(receipt['alias_unknown_bit_ticks'],22512*5)
            parsed=aliases.activity_module().read_saif(d/'normalized.saif')
            self.assertEqual(len(parsed['signals']),22513)
            self.assertEqual(parsed['duration_ticks'],10)
            self.assertTrue(any(s['path'].endswith('/literal.dot') and s['TB']==3 and s['TX']==3 for s in parsed['signals']))
            save('candidate-alias-normalization.json',json.dumps(receipt,indent=2)+'\n')
            first=sorted(pairs)[0]
            for mode in ('missing','native_mismatch','extra'):
                broken=d/(mode+'.saif')
                raw_saif(broken,pairs,missing=first if mode=='missing' else None,
                    extra=(pairs[first],'PORT',dict(T0=10,T1=0,TX=0,TZ=0,TC=0)) if mode=='native_mismatch' else
                          (first+'/unexpected','NET',dict(T0=10,T1=0,TX=0,TZ=0,TC=0)) if mode=='extra' else None)
                with self.assertRaises(ValueError): aliases.normalize(broken,mp,d/(mode+'-out.saif'))
                self.assertFalse((d/(mode+'-out.saif')).exists())
            forged=copy.deepcopy(mapping);forged['mode']='explicit_probe_only';forged['source_files']=[]
            fp=d/'forged.mapping.json';fp.write_text(json.dumps(forged))
            with self.assertRaisesRegex(ValueError,'forbids unguarded/probe mode'): aliases.validate_mapping(fp)
            observer=Path(mapping['observer_source']['path'])
            with observer.open('a') as stream: stream.write('// source tamper\n')
            with self.assertRaisesRegex(ValueError,'identity changed'): aliases.validate_mapping(mp)


    @unittest.skipUnless(shutil.which('iverilog'),'Icarus required')
    def test_full_candidate_336_macros_and_all_22512_direct_alias_paths_elaborate(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2c-full-elab-') as t:
            d=Path(t)
            # Geometry/ports only, explicitly no vendor/power/timing qualification.
            vendor=d/'open-geometry-only.v'
            vendor.write_text('module RAMSP1024X16(output reg [15:0] Q,input CLK,CEN,GWEN,RET1N, '+
                'input [15:0] WEN,D,input [9:0] A,input [2:0] EMA,input [1:0] EMAW); '+
                'reg [63:0] mem [0:255]; endmodule\n')
            mapping=aliases.generate(SOURCE,d/'aliases',placement='include')
            text=collector.generate_tb(self.ctx)
            point=text.rindex('endmodule')
            text=text[:point]+Path(mapping['observer_source']['path']).read_text()+text[point:]
            tb=d/'full.sv';tb.write_text(text)
            excluded={self.ctx.base.RTL/'general/sirv_sim_ram.v',self.ctx.base.RTL/'perips/mem_1024x16.sv'}
            sources=sorted(p for p in self.ctx.base.RTL.rglob('*') if p.suffix in ('.v','.sv') and p not in excluded)
            sources += [ROOT/'tools/ppa'/n for n in ('xu_sirv_sram_adapter.sv','xu_weight_sram_adapter.sv','xu_shared_icb_sram.sv','xu_soc_ppa_top.sv')]
            sources += [vendor,tb]
            fl=d/'rtl.f';fl.write_text('\n'.join(str(p) for p in sources)+'\n')
            command=['iverilog','-g2012','-s','tb_xu_soc_ppa','-DDISABLE_SV_ASSERTION=1','-DARM_UD_MODEL','-DXU_TASK_ACTIVITY_HOST_CHECK']
            command += ['-I'+str(self.ctx.base.RTL/n) for n in ('core','perips','perips/apb_i2c')]
            command += ['-o',str(d/'soc.vvp'),'-f',str(fl)]
            result=run(command,d,'full-336-macro-22512-path-elaboration.log',300)
            self.assertEqual(result.returncode,0,result.stdout)
            save('full-336-macro-elaboration-source-sha256.json',json.dumps(dict(status='ELABORATED_NOT_SIMULATED_OPEN_GEOMETRY_STANDIN',
                macro_count=336,pin_bit_count=22512,sources=[context.identity(p) for p in sources]),indent=2)+'\n')

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'actual Icarus required')
    def test_actual_wrapper_99_rows_all_groups_and_destructive_faults(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2c-actual-observer-') as t:
            d=Path(t); source=d/'probe.sv';source.write_text(rtl_probe(self.ctx));golden_file(d/'golden.hex')
            binary=d/'probe.vvp';perips=self.ctx.base.RTL/'perips'
            command=['iverilog','-g2012','-DXU_TASK_ACTIVITY_HOST_CHECK','-s','tb_xu_s2c_task_observer','-o',str(binary),str(source)]+[str(perips/n) for n in PERIPS_SOURCES]
            result=run(command,d,'actual-wrapper-build.log')
            self.assertEqual(result.returncode,0,result.stdout)
            cases=[(0,None),(1,'candidate setup/data write before first source request'),
                (2,'fixture-mismatched actual W commit'),(3,'nonzero actual X clear commit'),
                (4,'first source request changed before acceptance'),(5,'first source request changed before acceptance'),
                (6,'POP before all owned words read'),(7,'unexpected pretask MMIO read'),
                (8,'W cursor setup'),(9,'result response absent/changed before retirement')]
            for mode,rejected in cases:
                result=run(['vvp',str(binary),'+MODE='+str(mode),'+GOLDEN='+str(d/'golden.hex')],d,'actual-wrapper-mode-%d.log'%mode,180)
                if rejected is None:
                    self.assertEqual(result.returncode,0,result.stdout)
                    self.assertIn('XU_S2C_OBSERVER_RTL_PASS clear=33697 w_actual=16384 x_actual=6336 bias_actual=256 rows=99 groups=3168 retired_pops=3168 words=50688 wait=4 signed16_40_48=1',result.stdout)
                else:
                    self.assertNotEqual(result.returncode,0,result.stdout)
                    self.assertIn(rejected,result.stdout)
            save('actual-wrapper-generated-probe.sv',source.read_text())
            save('actual-wrapper-golden-sha256.json',json.dumps(context.identity(d/'golden.hex'))+'\n')
            self.ctx.recheck()

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'),'actual Icarus required')
    def test_actual_platform_reset_chain_and_unclocked_fifo_startup(self):
        with tempfile.TemporaryDirectory(prefix='xu-s2c-actual-reset-') as t:
            d=Path(t);source=d/'reset.sv';source.write_text(reset_probe(self.ctx));binary=d/'reset.vvp'
            perips=self.ctx.base.RTL/'perips'
            actual_reset=['sirv_ResetCatchAndSync_2.v','sirv_AsyncResetRegVec_129.v','sirv_AsyncResetReg.v']
            command=['iverilog','-g2012','-DXU_TASK_ACTIVITY_HOST_CHECK','-s','tb_xu_s2c_reset_guard','-o',str(binary),str(source)]
            command += [str(perips/n) for n in PERIPS_SOURCES+actual_reset]
            result=run(command,d,'actual-reset-chain-build.log')
            self.assertEqual(result.returncode,0,result.stdout)
            cases=[(0,None),(1,'request before actual reset ready'),(2,'request before actual reset ready'),
                (3,'no actual accelerator clock sampled asserted reset'),(4,'reset reasserted'),
                (5,'reset.*unknown'),(6,'FIFO logical ownership was not reset'),
                (7,'unknown commit/FIFO ownership state'),(8,'unknown commit/FIFO ownership state')]
            for mode,rejected in cases:
                result=run(['vvp',str(binary),'+MODE='+str(mode)],d,'actual-reset-chain-mode-%d.log'%mode)
                self.assertRegex(result.stdout,'XU_RESET_FIXTURE_UNCLOCKED_FIFO_X actual_rst_n=[0x] sampled_reset_edges=0')
                if rejected is None:
                    self.assertEqual(result.returncode,0,result.stdout)
                    self.assertIn('XU_RESET_GUARD_PASS actual_20stage_chain=1 wrapper_sync_fifo=1 stopped_clock_startup_x=1',result.stdout)
                    self.assertIn('XU_CANDIDATE_RESET_READY task=7',result.stdout)
                else:
                    self.assertNotEqual(result.returncode,0,result.stdout)
                    self.assertRegex(result.stdout,rejected)
            save('actual-reset-chain-generated-probe.sv',source.read_text())
            save('actual-reset-chain-source-sha256.json',json.dumps([context.identity(perips/n) for n in actual_reset],indent=2)+'\n')
            self.ctx.recheck()


if __name__=='__main__': unittest.main()
