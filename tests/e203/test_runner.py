import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('e203_soc', ROOT / 'tools/scripts/e203_soc.py')
soc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soc)


class RunnerTests(unittest.TestCase):
    def test_submodule_must_have_own_repository_and_match_gitlink(self):
        import subprocess
        verify=getattr(soc,'verify_submodule',None)
        self.assertIsNotNone(verify, 'submodule preflight is missing')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            sub=root/'third-party/e203_hbirdv2'
            sub.mkdir(parents=True)
            def git(cwd,*args):
                return subprocess.check_output(['git','-c','user.name=Test',
                    '-c','user.email=test@example.invalid',*args],cwd=cwd,text=True,stderr=subprocess.DEVNULL).strip()
            git(root,'init')
            git(root,'commit','--allow-empty','-m','root')
            with self.assertRaisesRegex(ValueError,'not initialized'):
                verify(root,sub)
            git(sub,'init')
            git(sub,'commit','--allow-empty','-m','submodule')
            first=git(sub,'rev-parse','HEAD')
            git(root,'update-index','--add','--cacheinfo',f'160000,{first},third-party/e203_hbirdv2')
            git(root,'commit','-m','pin')
            self.assertEqual(verify(root,sub), first)
            git(sub,'commit','--allow-empty','-m','unpinned')
            with self.assertRaisesRegex(ValueError,'gitlink'):
                verify(root,sub)

    def test_signed_mem_and_exact_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.mem'
            path.write_text('8000\n7fff\nffff\n')
            self.assertEqual(soc.read_mem(path, 16, 3), [-32768, 32767, -1])
            with self.assertRaises(ValueError):
                soc.read_mem(path, 16, 4)
            path.write_text('10000\n')
            with self.assertRaises(ValueError):
                soc.read_mem(path, 16, 1)

    def test_pass_requires_all_layers_and_counts(self):
        good = ('TASK_PASS layer=0 outputs=25344 writes=50688 cycles=99 firmware_cycles=100\n'
                'SOC_PASS tasks=1 outputs=25344 writes=50688\n')
        self.assertEqual(soc.check_log(good, 1)[0]['cycles'], 99)
        for bad in [good.replace('25344', '1'), good.replace('TASK_PASS', 'SKIPPED'),
                    good.replace('layer=0', 'layer=1'), good + 'FATAL: mismatch\n', '',
                    good.replace('SOC_PASS', 'NO_COMPLETION'),
                    good.replace('SOC_PASS tasks=1 outputs=25344 writes=50688',
                                 'SOC_PASS tasks=1 outputs=25344 writes=506880'),
                    good+'SOC_PASS tasks=2 outputs=50688 writes=101376\n']:
            with self.assertRaises(ValueError):
                soc.check_log(bad, 1)

    def test_command_failure_is_not_pass(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                soc.run([sys.executable, '-c', 'raise SystemExit(3)'], ROOT, Path(tmp)/'fail.log')

    def test_command_pwd_matches_working_directory(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            soc.run([sys.executable, '-c',
                     'import os; assert os.path.samefile(os.getcwd(), os.environ["PWD"])'],
                    Path(tmp), Path(tmp)/'pwd.log')

    def test_command_metadata_cannot_be_mistaken_for_simulator_failure(self):
        import sys
        good=('TASK_PASS layer=0 outputs=25344 writes=50688 cycles=99 firmware_cycles=100\n'
              'SOC_PASS tasks=1 outputs=25344 writes=50688\n')
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'run.log'
            output=soc.run([sys.executable,'-c',f'print({good!r})','/tmp/timeout/FATAL'],ROOT,log)
            self.assertEqual(soc.check_log(output,1)[0]['cycles'],99)
            self.assertIn('/tmp/timeout/FATAL',log.read_text())

    def test_synthetic_distinguishes_layers_and_signs(self):
        with tempfile.TemporaryDirectory() as tmp:
            soc.synthetic(Path(tmp), 2)
            a = Path(tmp)/'layer_00'
            b = Path(tmp)/'layer_01'
            x = soc.read_mem(a/'x.mem', 16, 6336)
            w = soc.read_mem(a/'w.mem', 16, 16384)
            bias = soc.read_mem(a/'bias.mem', 40, 256)
            y = soc.read_mem(a/'y.mem', 48, 25344)
            self.assertEqual(y[0], bias[0]+sum(x[k]*w[k*256] for k in range(64)))
            self.assertLess(y[0], -(1 << 32))
            self.assertGreater(y[-1], 1 << 32)
            self.assertNotEqual((a/'y.mem').read_bytes(), (b/'y.mem').read_bytes())

    def test_doctor_requires_the_selected_simulator(self):
        from unittest.mock import patch
        def which(name):
            return None if name in ('verilator', 'g++') else '/bin/tool'
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'doctor'
            with patch('sys.argv',['e203_soc.py','--mode','doctor','--out',str(out)]), \
                 patch.object(soc.shutil,'which',side_effect=which):
                self.assertEqual(soc.main(),1)
            import json
            result=json.loads((out/'result.json').read_text())
            self.assertEqual(result['error'],'missing tools: verilator, g++')

    def test_cache_changes_with_build_recipe_or_compiler(self):
        report={'source_sha256':{'core.sv':'source'},
                'versions':{'g++':['version1']},'runner_sha256':'recipe1'}
        original=soc.build_key(report,'verilator',False)
        report['runner_sha256']='recipe2'
        self.assertNotEqual(original,soc.build_key(report,'verilator',False))
        report['runner_sha256']='recipe1'
        report['versions']['g++']=['version2']
        self.assertNotEqual(original,soc.build_key(report,'verilator',False))


if __name__ == '__main__':
    unittest.main()
