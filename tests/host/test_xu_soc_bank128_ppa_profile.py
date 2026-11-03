"""Compact32 W geometry/refusal checks. Dummy DBs are never physical evidence."""
import ast
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import test_xu_soc_ppa_profiles as fixtures

PPA, IMPL, ROOT = fixtures.PPA, fixtures.IMPL, fixtures.ROOT
PARENT = 'e19304cb3f1f45ad2b691a9e316702ff2aeea9d1'


class XuBank128PpaProfileTest(unittest.TestCase):
    def fixture(self, directory):
        helper = fixtures.XuPpaProfileConfigurationTest()
        inv, impl = helper.fixture(directory, 's3-pe32')
        bank = PPA.template(inv, 's3-pe32-bank128')
        inv.update(main_commit=PPA.BANK128_MAIN_COMMIT,source_profile='s3-pe32-bank128',
                   accelerator_configuration=dict(PPA.BANK128_CONFIGURATION))
        for key in ['source_profile','accel_variant','accelerator_configuration','defines','memory_groups','retained_instances']:
            impl[key] = bank[key]
        impl['replacements'][PPA.BANK128_MEMORY] = helper.identity(ROOT/'tools/ppa/xu_weight128_sram_adapter.sv')
        path = directory/'w128.db';path.write_text('HOST RAM128 LIBRARY FIXTURE ONLY')
        impl['libraries'].append(dict(helper.identity(path),role='weight_sram128'))
        impl['source_freeze'].update(main_commit=inv['main_commit'],memory_groups_sha256=PPA.digest(impl['memory_groups']),
            libraries_sha256=PPA.digest(impl['libraries']),defines_sha256=PPA.digest(impl['defines']),
            accelerator_configuration_sha256=PPA.digest(impl['accelerator_configuration']))
        self.resign(directory, impl)
        return inv,impl

    def resign(self, directory, impl):
        path = directory/'proof.json';path.write_text(json.dumps(PPA.mapping_review_template(impl)))
        impl['mapping_proof'] = dict(path=str(path),sha256=PPA.sha(path))

    def test_mixed448_macros_zero_padding_single_rw_one_cycle(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            inv,impl = self.fixture(Path(temporary))
            _,_,gaps = PPA.checked_implementation(impl,inv,allow_unqualified=True)
            self.assertEqual([group['count'] for group in impl['memory_groups']],[32,32,256,128])
            self.assertEqual([group['macro_ref'] for group in impl['memory_groups']],['RAMSP1024X16']*3+['RAMSP128X16'])
            self.assertEqual(sum(group['count'] for group in impl['memory_groups']),448)
            self.assertEqual((impl['memory_groups'][-1]['logical_bits'],impl['memory_groups'][-1]['physical_bits'],impl['memory_groups'][-1]['padding_bits']),(262144,262144,0))
            self.assertEqual((impl['memory_groups'][-1]['read_latency_cycles'],impl['memory_groups'][-1]['single_rw']),(1,True))
            self.assertEqual(impl['defines'],['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_ACCEL_PE32=1','XU_ACCEL_PE32_BANK128=1'])
            targets,links = PPA.library_paths(impl)
            self.assertEqual((len(targets),len(links)),(1,3))
            self.assertNotIn(impl['libraries'][-1]['path'],targets)
            self.assertIn('mapped-equivalence:NOT_RUN',gaps)
            with self.assertRaisesRegex(ValueError,'allow-unqualified'):
                PPA.checked_implementation(impl,inv)

    def test_resigned_geometries_defines_libraries_adapter_and_main_mutations_fail(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            directory = Path(temporary);inv,impl = self.fixture(directory)
            changes = [lambda value:value['defines'].pop(), lambda value:value['defines'].append('XU_ACCEL_PE64=1'),
                lambda value:value['defines'].__setitem__(3,'XU_ACCEL_PE32_BANK128=0'),
                lambda value:value.update(accel_variant='pe32'),
                lambda value:value['accelerator_configuration'].update(weight_depth_slices=2),
                lambda value:value['accelerator_configuration'].update(read_latency_cycles=2),
                lambda value:value['accelerator_configuration'].update(single_rw=False),
                lambda value:value['memory_groups'][-1].update(count=32),
                lambda value:value['memory_groups'][-1].update(macro_ref='RAMSP1024X16'),
                lambda value:value['memory_groups'][-1].update(padding_bits=262144),
                lambda value:value['memory_groups'][-1].update(instance_pattern='*'),
                lambda value:value['memory_groups'][-1].update(read_latency_cycles=2),
                lambda value:value['retained_instances'][0].update(reference_pattern='xu_pe32_icb_slave*'),
                lambda value:value['replacements'].pop(PPA.BANK128_MEMORY),
                lambda value:value['libraries'].pop(),
                lambda value:value['libraries'][-1].update(role='sram'),
                lambda value:value['libraries'][-1].update(role='bias_sram')]
            for index,change in enumerate(changes):
                with self.subTest(index=index):
                    bad = copy.deepcopy(impl);change(bad)
                    bad['source_freeze'].update(memory_groups_sha256=PPA.digest(bad['memory_groups']),
                        libraries_sha256=PPA.digest(bad['libraries']),defines_sha256=PPA.digest(bad['defines']),
                        accelerator_configuration_sha256=PPA.digest(bad['accelerator_configuration']))
                    self.resign(directory,bad)
                    with self.assertRaises(ValueError): PPA.checked_implementation(bad,inv,allow_unqualified=True)
            bad_inv = dict(inv,main_commit='UNAPPROVED')
            bad = copy.deepcopy(impl);bad['source_freeze']['main_commit']='UNAPPROVED'
            with self.assertRaisesRegex(ValueError,'exact approved candidate main commit'):
                PPA.checked_implementation(bad,bad_inv,allow_unqualified=True)
            bad = copy.deepcopy(impl)
            bad['replacements'][PPA.BANK128_MEMORY] = dict(bad['replacements'][PPA.RTL+'/perips/mem_1024x16.sv'])
            with self.assertRaisesRegex(ValueError,'exact approved single-RW'):
                PPA.checked_implementation(bad,inv,allow_unqualified=True)

    def test_each_existing_template_mapping_and_macro_tcl_stays_byte_identical(self):
        old_text = subprocess.check_output(['git','show',PARENT+':tools/scripts/xu_soc_ppa.py'],cwd=ROOT,universal_newlines=True)
        old = types.ModuleType('xu_parent_ppa');old.__file__ = str(ROOT/'tools/scripts/xu_soc_ppa.py')
        exec(compile(old_text,old.__file__,'exec'),old.__dict__)
        inv = dict(platform_source_manifest_sha256='HOST SAME INPUT')
        for profile in old.SOURCE_PROFILES:
            with self.subTest(profile=profile):
                left,right = old.template(inv,profile),PPA.template(inv,profile)
                self.assertEqual(left,right)
                self.assertEqual(old.memory_checks(left),PPA.memory_checks(right))
                self.assertEqual(old.mapping_identity(left),PPA.mapping_identity(right))
        before = {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(old_text).body if isinstance(node,ast.FunctionDef)}
        after = {node.name:ast.dump(node,include_attributes=False) for node in ast.parse((ROOT/'tools/scripts/xu_soc_ppa.py').read_text()).body if isinstance(node,ast.FunctionDef)}
        for name in ['prepare','memory_checks','clock_contract_checks','guarded_tcl']:
            self.assertEqual(before[name],after[name],name)

    def test_128_library_is_required_only_for_opted_in_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);standard=directory/'standard.db';sram=directory/'sram.db';small=directory/'small.db'
            for path in [standard,sram,small]:path.write_text('HOST DB ONLY')
            args=(ROOT,directory/'out',standard,PPA.sha(standard),sram,PPA.sha(sram))
            for kwargs in [{},{'weight_sram128_db':small}]:
                with self.subTest(kwargs=kwargs),self.assertRaisesRegex(ValueError,'requires --weight-sram128-db'):
                    IMPL.generate(*args,profile='s3-pe32-bank128',**kwargs)
            with self.assertRaisesRegex(ValueError,'only for bank128 profile'):
                IMPL.generate(*args,weight_sram128_db=small,weight_sram128_sha=PPA.sha(small))
            self.assertFalse((directory/'out').exists())

    def test_legacy_vcd_energy_cannot_reuse_another_geometry(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            (directory/'prepared.json').write_text(json.dumps(dict(implementation=dict(source_profile='s3-pe32-bank128'))))
            with self.assertRaisesRegex(ValueError,'candidate-specific clear/request-window'):
                PPA.activity_power(directory,{}, {})
