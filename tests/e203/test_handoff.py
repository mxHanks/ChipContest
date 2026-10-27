from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform.startswith('linux'), 'handoff recipes target Linux bash')
class HandoffTests(unittest.TestCase):
    def test_recovery_stops_on_checksum_failure_before_clone(self):
        root=Path(__file__).resolve().parents[2]
        doc=(root/'docs/server-handoff.md').read_text(encoding='utf-8')
        recipe=next(block.split('```',1)[0] for block in doc.split('```bash\n')[1:]
                    if 'bundle=/交接包的绝对路径' in block.split('```',1)[0])
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            bundle=work/'bundle'
            bundle.mkdir()
            (bundle/'ChipContest.bundle').write_text('damaged archive')
            (bundle/'SHA256SUMS').write_text('0'*64+'  ChipContest.bundle\n')
            recipe=recipe.replace('bundle=/交接包的绝对路径','bundle='+shlex.quote(str(bundle)))
            result=subprocess.run(['bash','-c',recipe],cwd=work,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('FAILED',result.stdout+result.stderr)
            self.assertNotIn('Cloning',result.stderr)
            self.assertNotIn('python3',result.stderr)


if __name__=='__main__':
    unittest.main()
