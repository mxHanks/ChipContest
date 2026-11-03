"""Independent joint integration checks; no VCS, foundry or energy claim.

These tests execute actual RISC-V/C builds and the frozen wrapper tests. The
strict real inventory/netlist/library gate is never bypassed for a host positive.
An actual-server prepare is optional and requires all original input files.
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

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/ppa'))
import xu_candidate_joint_context as context
import xu_candidate_joint_task_activity as collector
import xu_candidate_sram_activity_alias as aliases

SOURCE=Path(os.environ['XU_S2C_SOURCE_ROOT']).resolve() if os.environ.get('XU_S2C_SOURCE_ROOT') else None
EVIDENCE=Path(os.environ['XU_JOINT_COLLECTOR_TEST_EVIDENCE']) if os.environ.get('XU_JOINT_COLLECTOR_TEST_EVIDENCE') else None


def save(name,value):
    if EVIDENCE:
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        (EVIDENCE/name).write_text(value)


def run(command,cwd,name,timeout=300):
    result=subprocess.run(command,cwd=str(cwd),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,universal_newlines=True,timeout=timeout)
    save(name,json.dumps(dict(command=command,cwd=str(cwd),returncode=result.returncode))+'\n'+result.stdout)
    return result


def joint_auditor():
    return context.load('xu_test_joint_auditor',collector.JOINT/'xu_sram_joint_audit.py')


class JointGuards(unittest.TestCase):
    def test_python36_syntax_and_old_producer_bytes_remain_frozen(self):
        for name in ('xu_candidate_joint_context.py','xu_candidate_joint_task_activity.py'):
            p=ROOT/'tools/ppa'/name;ast.parse(p.read_text(),filename=str(p),feature_version=(3,6))
        for name,digest in context.FROZEN_DERIVATION.items():self.assertEqual(context.sha(ROOT/name),digest,name)
        self.assertEqual(collector.S2C_MAPPED_SHA,'9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892')

    def test_runtime_file_freeze_rejects_type_mode_and_content_changes(self):
        with tempfile.TemporaryDirectory(prefix='xu-joint-frozen-') as t:
            p=Path(t)/'input';p.write_text('measured input\n');record=context.identity(p)
            collector.check_frozen([record])
            p.chmod(record['mode']^0o100)
            with self.assertRaisesRegex(ValueError,'bytes/type/mode changed'):collector.check_frozen([record])
            p.chmod(record['mode']);p.write_text('modified input\n')
            with self.assertRaisesRegex(ValueError,'bytes/type/mode changed'):collector.check_frozen([record])
            p.unlink();target=Path(t)/'target';target.write_text('measured input\n');p.symlink_to(target)
            with self.assertRaisesRegex(ValueError,'non-symlink'):collector.check_frozen([record])

    def test_host_header_cannot_be_used_for_actual_vcs_run(self):
        with self.assertRaisesRegex(ValueError,'same selected VCS installation'):
            collector.actual_vcs_header_guard(Path('/eda/vcs/bin/vcs'),Path('/usr/include/iverilog'))

    @unittest.skipUnless(shutil.which('cc') and shutil.which('iverilog') and shutil.which('vvp') and
        Path('/usr/include/iverilog/vpi_user.h').is_file(),'actual C/Icarus/VPI header required')
    def test_actual_callback_boundary_and_saif_crosschecks_reject_resigned_changes(self):
        with tempfile.TemporaryDirectory(prefix='xu-joint-boundary-') as t:
            d=Path(t);library=d/'xu_sram_joint_vpi.vpi';binary=d/'micro.vvp';prefix=d/'micro'
            result=run(['cc','-std=c99','-D_POSIX_C_SOURCE=200809L','-fPIC','-shared','-Wall','-Wextra',
                '-Wshadow','-Wstrict-prototypes','-Werror','-O2','-I/usr/include/iverilog',
                str(collector.JOINT/'xu_sram_joint_vpi.c'),'-o',str(library)],d,'boundary-vpi-build.log')
            self.assertEqual(result.returncode,0,result.stdout)
            result=run(['iverilog','-g2012','-s','tb_xu_sram_joint_micro','-o',str(binary),
                str(ROOT/'tests/ppa/tb_xu_sram_joint_micro.sv')],d,'boundary-micro-build.log')
            self.assertEqual(result.returncode,0,result.stdout)
            result=run(['vvp','-M'+str(d),'-mxu_sram_joint_vpi',str(binary),'+MODE=0','+OUT='+str(prefix)],
                d,'boundary-micro-simulation.log')
            self.assertEqual(result.returncode,0,result.stdout)
            side=Path(str(prefix)+'.simultaneous.jsonl');stats=Path(str(prefix)+'.stats.jsonl')
            joint=joint_auditor().audit(stats,side)
            checked=collector.check_boundary_sidecar(joint,side)
            self.assertEqual((checked['checked_macros'],checked['checked_pin_bits']),(1,67))
            save('boundary-actual.stats.jsonl',stats.read_text())
            save('boundary-actual.simultaneous.jsonl',side.read_text())
            original=[json.loads(line) for line in side.read_text().splitlines()]
            cases=[]
            x=copy.deepcopy(original);x[0]['initial_state_lsb_ports']='1'+x[0]['initial_state_lsb_ports'][1:];cases.append(('initial-state',x))
            x=copy.deepcopy(original);next(r for r in x if r.get('tick')==526000000)['boundary']=False;cases.append(('boundary-flag',x))
            x=copy.deepcopy(original);r=next(r for r in x if r.get('tick')==526000000);r['events'][-1]['callback_ordinal']=joint['window']['end_callback_ordinal'];cases.append(('after-end',x))
            for name,rows in cases:
                bad=d/(name+'.jsonl');bad.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                with self.subTest(name=name),self.assertRaises(ValueError):collector.check_boundary_sidecar(joint,bad)
            changed=copy.deepcopy(joint);changed['macros'][0]['pin_transitions']['CLK'][1]-=1
            with self.assertRaisesRegex(ValueError,'disagree with begin/end state'):
                collector.check_boundary_sidecar(changed,side)
            # Independent hand-authored SAIF uses recorded raw dwell only. It
            # deliberately has no TC calibration and is labelled synthetic.
            saif=d/'synthetic-dwell-only.saif';duration=joint['window']['duration_ticks'];macro=joint['macros'][0]
            signals=[]
            for pin,values in macro['pin_dwell'].items():
                signals.append('(%s (T0 %d) (T1 %d) (TX %d) (TZ %d) (TC 0))'%tuple([pin]+values))
            saif.write_text('(SAIFILE (TIMESCALE 1 fs) (DURATION %d) (INSTANCE tb_xu_sram_joint_micro (INSTANCE dut (PORT %s))))\n'%(duration,' '.join(signals)))
            class Reader:activity=context.load('xu_test_joint_saif',ROOT/'tools/scripts/xu_soc_activity.py')
            compared=collector.compare_saif_joint(Reader,saif,joint,dict(pin_bit_count=67))
            self.assertEqual(compared['different_or_tb_pin_bits'],0)
            self.assertIn('NOT_CALIBRATED',compared['status'])
            save('boundary-synthetic-dwell-only.saif',saif.read_text())
            wrong=copy.deepcopy(joint);wrong['window']['duration_ticks']+=1
            with self.assertRaisesRegex(ValueError,'duration or precision differs'):
                collector.compare_saif_joint(Reader,saif,wrong,dict(pin_bit_count=67))
            save('boundary-crosscheck.json',json.dumps(checked,indent=2)+'\n')
            save('boundary-tamper-cases.json',json.dumps([n for n,_ in cases]+['transition-flow','saif-duration'])+'\n')


@unittest.skipUnless(SOURCE,'explicit frozen XU_S2C_SOURCE_ROOT required')
class JointCandidateIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ctx=context.Context(SOURCE)

    def test_exact_tool_context_and_336_readonly_registration(self):
        self.ctx.recheck()
        with tempfile.TemporaryDirectory(prefix='xu-joint-generate-') as t:
            mapping=aliases.generate(SOURCE,Path(t)/'aliases')
            text=collector.generate_tb(self.ctx,mapping)
            self.assertEqual(text.count('$xu_sram_joint_register('),336)
            self.assertEqual(text.count('$xu_sram_joint_begin('),1)
            self.assertEqual(text.count('$xu_sram_joint_end('),1)
            self.assertIn('$toggle_start();\n        $xu_sram_joint_begin(',text)
            self.assertIn('$toggle_stop();\n          $xu_sram_joint_end(',text)
            self.assertIn('xu_joint_final_request_addr=cmd_addr;',text)
            self.assertIn('xu_joint_final_request_addr!==BASE+YOFF+50687*4',text)
            self.assertIn('task_setup_writes=0 actual_commits=1 fifo_reset_empty=1',text)
            self.assertNotIn('vpi_put_value',text)
            for record in mapping['macros']:
                instance=record['instance']
                expected='$xu_sram_joint_register("%s",%s);'%(instance,','.join(instance+'.'+p for p in ('A','CEN','CLK','D','EMA','EMAW','GWEN','Q','RET1N','WEN')))
                self.assertEqual(text.count(expected),1)
            save('generated-joint-candidate-tb.sv',text)
            save('joint-tool-context.json',json.dumps(self.ctx.joint_tool,indent=2)+'\n')

    def test_new_tool_full_blob_guard_rejects_hidden_noncommon_source_change(self):
        with tempfile.TemporaryDirectory(prefix='xu-joint-tool-clone-') as t:
            d=Path(t);clone=d/'tool'
            result=run(['git','clone','--shared','--no-checkout',str(ROOT),str(clone)],d,'joint-tool-clone.log')
            self.assertEqual(result.returncode,0,result.stdout)
            result=run(['git','checkout',context.original.git(ROOT,'rev-parse','HEAD')],clone,'joint-tool-checkout.log')
            self.assertEqual(result.returncode,0,result.stdout)
            command=[sys.executable,'-c','import sys;sys.path.insert(0,"tools/ppa");import xu_candidate_joint_context as c;c.full_tool_identity();print("XU_JOINT_TOOL_ALL_BLOBS_PASS")']
            result=run(command,clone,'joint-tool-clean.log');self.assertEqual(result.returncode,0,result.stdout)
            target='tests/ppa/tb_xu_sram_joint_micro.sv'
            result=run(['git','update-index','--assume-unchanged',target],clone,'joint-tool-hidden-index.log')
            self.assertEqual(result.returncode,0,result.stdout)
            with (clone/target).open('a') as stream:stream.write('// deliberately hidden joint source modification\n')
            result=run(command,clone,'joint-tool-hidden-change.log')
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertIn('tool tracked bytes differ from committed Git',result.stdout)

    @unittest.skipUnless(shutil.which('iverilog'),'actual Icarus required')
    def test_actual_336_port_registration_and_22512_alias_paths_elaborate(self):
        with tempfile.TemporaryDirectory(prefix='xu-joint-elab-') as t:
            d=Path(t);mapping=aliases.generate(SOURCE,d/'aliases',placement='include')
            text=collector.generate_tb(self.ctx,mapping)
            point=text.rindex('endmodule');text=text[:point]+Path(mapping['observer_source']['path']).read_text()+text[point:]
            tb=d/'joint.sv';tb.write_text(text)
            vendor=d/'open-geometry-only.v'
            vendor.write_text('module RAMSP1024X16(output reg [15:0] Q,input CLK,CEN,GWEN,RET1N, '+
                'input [15:0] WEN,D,input [9:0] A,input [2:0] EMA,input [1:0] EMAW); reg [63:0] mem [0:255]; endmodule\n')
            excluded={self.ctx.base.RTL/'general/sirv_sim_ram.v',self.ctx.base.RTL/'perips/mem_1024x16.sv'}
            sources=sorted(p for p in self.ctx.base.RTL.rglob('*') if p.suffix in ('.v','.sv') and p not in excluded)
            sources += [ROOT/'tools/ppa'/n for n in ('xu_sirv_sram_adapter.sv','xu_weight_sram_adapter.sv','xu_shared_icb_sram.sv','xu_soc_ppa_top.sv')]
            sources += [vendor,tb];filelist=d/'rtl.f';filelist.write_text('\n'.join(str(p) for p in sources)+'\n')
            command=['iverilog','-g2012','-s','tb_xu_soc_ppa','-DDISABLE_SV_ASSERTION=1','-DARM_UD_MODEL','-DXU_TASK_ACTIVITY_HOST_CHECK']
            command += ['-I'+str(self.ctx.base.RTL/n) for n in ('core','perips','perips/apb_i2c')]
            result=run(command+['-o',str(d/'joint.vvp'),'-f',str(filelist)],d,'joint-336-paths-elaboration.log')
            self.assertEqual(result.returncode,0,result.stdout)
            save('joint-336-elaboration-summary.json',json.dumps(dict(status='ELABORATED_NOT_SIMULATED_OPEN_GEOMETRY_STANDIN',
                macro_count=336,pin_bit_count=22512,registration_count=336,sources=[context.identity(p) for p in sources]),indent=2)+'\n')

    @unittest.skipUnless(shutil.which('riscv64-unknown-elf-gcc') and shutil.which('cc') and
        Path('/usr/include/iverilog/vpi_user.h').is_file(),'actual RISC-V/C/VPI build tools required')
    def test_actual_components_prepare_and_wrong_netlist_cli_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='xu-joint-components-') as t:
            d=Path(t);firmware=d/'firmware';firmware.mkdir();vpi=d/'vpi';vpi.mkdir()
            _,built=collector.compile_firmware(self.ctx,firmware,'riscv64-unknown-elf-')
            compiled=collector.compile_vpi(self.ctx,vpi,'cc',Path('/usr/include/iverilog'),300)
            self.assertGreater(built['memory']['itcm_remaining_bytes'],0)
            self.assertGreater(compiled['library']['bytes'],0)
            collector.check_frozen(compiled['frozen_files'])
            vectors=d/'original-vectors';self.ctx.soc.load_fixture(vectors,12)
            validated=self.ctx.soc.check_vectors(vectors,12)
            materialized=collector.common_collector().materialize_task(vectors,d/'task_07/vectors',7,validated[7])
            self.assertEqual(materialized['global_task_id'],7)
            save('joint-host-components-result.json',json.dumps(dict(status='ACTUAL_HOST_COMPONENTS_PREPARED_NOT_COLLECTOR_ACCEPTED_OR_VCS_SIMULATED',
                firmware=built,vpi=compiled,task=materialized),indent=2)+'\n')
            for name in ('firmware-build.log','firmware-sections.log','firmware.dump'):
                save('joint-'+name,(firmware/name).read_text())
            save('joint-vpi-build.log',(vpi/'joint-vpi-build.log').read_text())
            # Exercise the real CLI, source guard and GCC before the mandatory
            # netlist/inventory guard. Placeholder files can never yield a
            # PARTIAL_PREPARED positive or be presented as a foundry result.
            netlist=d/'wrong-netlist.v';netlist.write_text('// HOST INVALID IDENTITY, never accepted\n')
            model=d/'geometry-only.v';model.write_text('reg [63:0] mem [0:255];\n')
            inventory=d/'invalid-inventory.json';inventory.write_text('{}\n')
            out=d/'rejected-prepare'
            command=[sys.executable,str(ROOT/'tools/ppa/xu_candidate_joint_task_activity.py'),
                '--source-root',str(SOURCE),'--tool-root',str(ROOT),'--out',str(out),
                '--vendor-model',str(model),'--netlist',str(netlist),'--mapped-inventory',str(inventory),
                '--constraints',str(ROOT/'tools/ppa/xu_full_soc.sdc'),'--vpi-include','/usr/include/iverilog',
                '--vectors',str(vectors),'--task-ids','7','--prepare-only']
            result=run(command,d,'joint-invalid-actual-prepare.log')
            self.assertNotEqual(result.returncode,0,result.stdout)
            report=json.loads((out/'result.json').read_text())
            self.assertEqual(report['status'],'FAIL')
            self.assertIn('unsupported mapped SRAM inventory schema',report['error'])
            self.assertTrue((out/'firmware/accel_soc').is_file())
            save('joint-invalid-prepare-result.json',json.dumps(report,indent=2)+'\n')
            self.ctx.recheck()


if __name__=='__main__':unittest.main()
