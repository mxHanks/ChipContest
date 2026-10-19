"""Backend selection must reject incompatible or ambiguous source sets."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'scripts/verify/sram_sources.py'


class SRAMSourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(),'central SRAM source selector is missing')
        spec=importlib.util.spec_from_file_location('sram_sources',MODULE)
        self.source=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.source)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=json.loads((ROOT/'configs/sram-backends.json').read_text())
        self.path=self.root/'backends.json'
        for name in self.config['common_sources']+self.config['backends']['BLACKBOX']['extra_sources']:
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('// fixture\n')
        self.save()

    def save(self):self.path.write_text(json.dumps(self.config))

    def select(self, mode, purpose='simulation', **kwargs):
        return self.source.select_backend(mode,purpose,root=self.root,config_path=self.path,**kwargs)

    def test_simulation_modes_share_contract_without_blackbox(self):
        behavioral=self.select('behavioral');ff=self.select('ff')
        self.assertEqual((behavioral['value'],ff['value']),(0,2))
        self.assertEqual(behavioral['sources'],ff['sources'])
        self.assertEqual(len(behavioral['sources']),3)

    def test_blackbox_requires_synthesis_and_has_exactly_one_stub(self):
        with self.assertRaises(ValueError):self.select('blackbox')
        choice=self.select('blackbox','synthesis')
        self.assertEqual(choice['value'],1)
        self.assertEqual(len(choice['sources']),4)
        self.assertEqual(sum('blackbox' in p.name for p in choice['sources']),1)

    def test_behavioral_synthesis_and_accidental_ff_expansion_rejected(self):
        with self.assertRaises(ValueError):self.select('behavioral','synthesis')
        with self.assertRaises(ValueError):self.select('ff','synthesis')
        self.assertEqual(self.select('ff','synthesis',allow_full_ff=True)['value'],2)

    def test_missing_official_files_never_fall_back(self):
        with self.assertRaises(FileNotFoundError):self.select('official')

    def test_duplicate_missing_and_escaped_sources_rejected(self):
        original=self.config['common_sources'][:]
        for names in (original+[original[0]],original+['missing.sv'],original+['../outside.sv']):
            self.config['common_sources']=names;self.save()
            with self.assertRaises((ValueError,FileNotFoundError)):self.select('behavioral')

    def test_numeric_geometry_and_interface_contract_cannot_drift_silently(self):
        for field,value in [('numeric_contract','wrong'),('logical_bank_count',19),('configured_bits',0),
                            ('interface',{'ports':'2RW','read_latency_cycles':0})]:
            before=self.config[field];self.config[field]=value;self.save()
            with self.assertRaises(ValueError):self.select('behavioral')
            self.config[field]=before

    def test_backend_value_and_schema_are_checked(self):
        self.config['backends']['BEHAVIORAL']['SRAM_BACKEND']=2;self.save()
        with self.assertRaises(ValueError):self.select('behavioral')
        self.config['schema']='unknown';self.save()
        with self.assertRaises(ValueError):self.select('ff')


if __name__=='__main__':unittest.main()
