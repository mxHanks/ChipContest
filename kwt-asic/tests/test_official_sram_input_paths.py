"""Path errors must produce an audit failure, not abandon the run record."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('official_path_subject',ROOT/'scripts/verify/official_sram_inputs.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class MalformedTechnologyPath(unittest.TestCase):
    def check_rejected(self,name):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            data=json.loads((ROOT/'configs/official-sram-package.json').read_text())
            data['functional_sources']=[{'path':name,'sha256':'0'*64}]
            manifest=root/'package.json';manifest.write_text(json.dumps(data))
            result=M.inspect_package(root,manifest)
            self.assertEqual(result['status'],'FAIL')
            self.assertEqual(result['stages']['simulation']['status'],'FAIL')
            self.assertEqual(result['official_validation'],'NOT_RUN')
            self.assertEqual(result['official_ppa'],'BLOCKED')

    def test_embedded_nul_is_reported_as_failure(self):
        self.check_rejected('bad\x00model.v')

    def test_filesystem_name_too_long_is_reported_as_failure(self):
        self.check_rejected('x'*300+'.v')
