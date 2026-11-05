import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


class AcceptanceTests(unittest.TestCase):
    def test_failed_child_is_recorded_and_stops_following_steps(self):
        source=Path(__file__).resolve().parents[2]/'tools/scripts/server_accept.py'
        self.assertTrue(source.is_file(), 'server acceptance entry point is missing')
        sys.path.insert(0,str(source.parent))
        spec=importlib.util.spec_from_file_location('server_accept',source)
        accept=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(accept)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            marker=out/'should-not-exist'
            steps=[('first',[sys.executable,'-c','print("ok")'],10),
                   ('broken',[sys.executable,'-c','raise SystemExit(4)'],10),
                   ('never',[sys.executable,'-c',f'open({str(marker)!r},"w").close()'],10)]
            result=accept.execute_steps(steps,out)
            self.assertEqual(result['status'],'FAIL')
            self.assertEqual(result['failed_step'],'broken')
            self.assertFalse(marker.exists())
            self.assertEqual(json.loads((out/'acceptance.json').read_text())['status'],'FAIL')
            self.assertEqual([s['status'] for s in result['steps']],['PASS','FAIL'])
            with self.assertRaises(ValueError):
                accept.execute_steps([],out)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(accept.execute_steps(steps[:1],Path(tmp))['status'],'PASS')


if __name__ == '__main__':
    unittest.main()
