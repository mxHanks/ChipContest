"""xu VCS platform adapter contracts; no licensed simulator is invoked here."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/scripts'))
import e203_soc as soc
import server_accept as accept


class VcsPlatformTests(unittest.TestCase):
    def test_vcs_and_doctor_do_not_require_other_simulators(self):
        for mode in ['baseline','synthetic','real','vectors']:
            required=soc.required_tools(mode,'vcs','rv-')
            self.assertIn('vcs',required)
            self.assertIn('rv-gcc',required)
            self.assertTrue(set(required).isdisjoint({'verilator','iverilog','vvp','g++','scala-cli'}))
        self.assertEqual(soc.required_tools('doctor','vcs','rv-'),
                         ['git','rv-gcc','rv-objcopy','rv-objdump'])
        self.assertEqual(soc.required_tools('check-vectors','vcs','rv-'),['git'])

    def test_matrix_filelist_excludes_legacy_testbench(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed=Path(tmp)/'install'
            rtl=installed/'rtl/core/core.v'
            old_tb=installed/'tb/tb_top.v'
            rtl.parent.mkdir(parents=True)
            old_tb.parent.mkdir(parents=True)
            rtl.write_text('module core; endmodule\n')
            old_tb.write_text('module tb_top; endmodule\n')
            sources=soc.matrix_sources(installed/'rtl')
            self.assertIn(rtl,sources)
            self.assertNotIn(old_tb,sources)
            self.assertEqual([p.name for p in sources if p.name.startswith('tb_')],['tb_accel_soc.sv'])

    def test_vcs_build_is_isolated_and_failed_build_cannot_enter_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            cache=out/'cache'
            cache.mkdir()
            filelist=cache/'rtl.f'
            filelist.write_text('core.v\ntb_accel_soc.sv\n')
            binary=cache/'accel_soc'
            binary.write_bytes(b'incomplete executable')
            includes=[out/'rtl/core']
            with patch.object(soc,'run',side_effect=RuntimeError('VCS link failed')):
                with self.assertRaises(RuntimeError):
                    soc.build_simulator('vcs',cache,filelist,includes,False,out)
            self.assertFalse((cache/'vcs-build.json').exists())

            def compile_vcs(command,cwd,log):
                self.assertEqual(cwd,cache)
                self.assertEqual(command[0],'vcs')
                self.assertIn('-sverilog',command)
                self.assertIn('-full64',command)
                self.assertEqual(command[command.index('-top')+1],'tb_accel_soc')
                self.assertIn('+define+DISABLE_SV_ASSERTION=1',command)
                self.assertIn('+incdir+'+str(includes[0]),command)
                self.assertIn('-Mdir='+str(cache/'csrc'),command)
                self.assertEqual(command[command.index('-f')+1],str(filelist))
                binary.write_bytes(b'linked executable')

            with patch.object(soc,'run',side_effect=compile_vcs) as run:
                built,command=soc.build_simulator('vcs',cache,filelist,includes,False,out)
                self.assertEqual((built,command),(binary,[str(binary)]))
                soc.build_simulator('vcs',cache,filelist,includes,False,out)
                self.assertEqual(run.call_count,1)
                binary.write_bytes(b'damaged executable')
                soc.build_simulator('vcs',cache,filelist,includes,False,out)
                self.assertEqual(run.call_count,2)

    def test_baseline_selects_vcs_without_matrix_testbench(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            e203=root/'e203'
            image=e203/'riscv-tools/riscv-tests/isa/generated/rv32ui-p-add.verilog'
            image.parent.mkdir(parents=True)
            image.write_text('@00000000\n00\n')
            out=root/'out'
            out.mkdir()
            calls=[]

            def execute(command,cwd,log):
                calls.append(command)
                if command[0]=='rv-gcc': Path(command[-1]).write_bytes(b'ELF')
                elif command[0]=='rv-objcopy': Path(command[-1]).write_text('@80000000\n00\n')
                return 'TEST_PASS\n'

            with patch.object(soc,'E203',e203),patch.object(soc,'run',side_effect=execute):
                result=soc.baseline(out,'rv-','vcs')
            simulation_calls=[c for c in calls if c[0]=='make']
            self.assertEqual(len(result['tests']),5)
            self.assertEqual(len(simulation_calls),5)
            self.assertTrue(all('SIM=vcs' in c for c in simulation_calls))
            self.assertFalse(any('tb_accel_soc' in str(c) for c in calls))

    def test_acceptance_separates_vcs_from_original_full(self):
        out=Path('/unused-xu-output')
        vcs=accept.acceptance_steps(out,'rv-','vcs')
        self.assertEqual([s[0] for s in vcs],['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12'])
        self.assertIn('tests/numeric',vcs[1][1])
        for _,command,_ in vcs[2:]:
            self.assertEqual(command[command.index('--sim')+1],'vcs')
        full=accept.acceptance_steps(out,'rv-',full=True,offline=True)
        self.assertEqual([s[0] for s in full][-2:],['icarus1','chisel'])
        self.assertIn('iverilog',full[-2][1])
        self.assertEqual(full[-1][1][0],'scala-cli')
        self.assertIn('--offline',full[-1][1])
        with self.assertRaises(ValueError):
            accept.acceptance_steps(out,'rv-','vcs',full=True)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(accept.soc,'run'):
                result=accept.execute_steps(vcs,Path(tmp),accept.VCS_SCOPE,'vcs-platform',['icarus1','chisel'])
            saved=json.loads((Path(tmp)/'acceptance.json').read_text())
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(saved['profile'],'vcs-platform')
            self.assertEqual(saved['not_run'],['icarus1','chisel'])
            self.assertIn('Icarus and Chisel not run',saved['scope'])

    def test_cache_identity_tracks_backend_version_and_binary_recipe(self):
        report={'source_sha256':{'core.sv':'rtl'},'versions':{'vcs':['2020.03']},
                'runner_sha256':'recipe','tools':{'vcs':'/opt/vcs/bin/vcs'}}
        key=soc.build_key(report,'vcs',False)
        self.assertNotEqual(key,soc.build_key(report,'iverilog',False))
        self.assertNotEqual(key,soc.build_key(report,'vcs',True))
        report['versions']['vcs']=['2021.09']
        self.assertNotEqual(key,soc.build_key(report,'vcs',False))


if __name__=='__main__':
    unittest.main()
