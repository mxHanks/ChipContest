"""Host geometry/refusal contracts; dummy libraries never claim physical results."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import test_xu_soc_ppa_profiles as fixtures

PPA = fixtures.PPA
ROOT = fixtures.ROOT


class XuPe64PpaProfileTest(unittest.TestCase):
    def fixture(self, directory, profile='s3-pe64'):
        return fixtures.XuPpaProfileConfigurationTest().fixture(directory, profile)

    def test_exact_single64_bank_geometry_and_missing_qualification_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA, 'source_profile_identity', return_value={}):
            inv, impl = self.fixture(Path(temporary))
            _, _, gaps = PPA.checked_implementation(impl, inv, allow_unqualified=True)
            self.assertIn('mapped-equivalence:NOT_RUN', gaps)
            self.assertEqual([group['count'] for group in impl['memory_groups']], [32,32,256,64])
            self.assertEqual(sum(group['count'] for group in impl['memory_groups']), 384)
            self.assertEqual(impl['defines'], ['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_ACCEL_PE64=1'])
            self.assertEqual((impl['memory_groups'][-1]['logical_bits'], impl['memory_groups'][-1]['physical_bits'],
                              impl['memory_groups'][-1]['padding_bits']), (262144,1048576,786432))
            with self.assertRaisesRegex(ValueError, 'allow-unqualified'):
                PPA.checked_implementation(impl, inv)

    def test_resigned_geometry_defines_and_retained_reference_mutations_fail(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA, 'source_profile_identity', return_value={}):
            directory = Path(temporary)
            inv, impl = self.fixture(directory)
            mutations = [lambda value:value['defines'].pop(),
                         lambda value:value['defines'].append('XU_ACCEL_PE32=1'),
                         lambda value:value['defines'].__setitem__(2,'XU_ACCEL_PE64=0'),
                         lambda value:value.update(accel_variant='pe32'),
                         lambda value:value['accelerator_configuration'].update(weight_padding_bytes=0),
                         lambda value:value['accelerator_configuration'].update(full_soc_macros=352),
                         lambda value:value['memory_groups'][-1].update(count=32),
                         lambda value:value['memory_groups'][-1].update(logical_depth=512),
                         lambda value:value['memory_groups'][-1].update(physical_bits=262144,padding_bits=0),
                         lambda value:value['memory_groups'][-1].update(instance_pattern='*'),
                         lambda value:value['retained_instances'][0].update(reference_pattern='xu_pe32_icb_slave*')]
            for index, mutate in enumerate(mutations):
                with self.subTest(index=index):
                    bad = copy.deepcopy(impl)
                    mutate(bad)
                    bad['source_freeze'].update(memory_groups_sha256=PPA.digest(bad['memory_groups']),
                        defines_sha256=PPA.digest(bad['defines']),
                        accelerator_configuration_sha256=PPA.digest(bad['accelerator_configuration']))
                    proof = directory/('resigned-proof-%d.json'%index)
                    proof.write_text(json.dumps(PPA.mapping_review_template(bad)))
                    bad['mapping_proof'] = dict(path=str(proof),sha256=PPA.sha(proof))
                    with self.assertRaises(ValueError):
                        PPA.checked_implementation(bad, inv, allow_unqualified=True)

    def test_other_profiles_cannot_select_the_new_physical_variant(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA, 'source_profile_identity', return_value={}):
            directory = Path(temporary)
            for profile in ['baseline','s3-pe32']:
                inv, impl = self.fixture(directory, profile)
                impl['defines'].append('XU_ACCEL_PE64=1')
                with self.subTest(profile=profile), self.assertRaises(ValueError):
                    PPA.checked_implementation(impl, inv, allow_unqualified=True)

    def test_every_old_template_and_macro_tcl_is_byte_identical_to_parent(self):
        old_text = subprocess.check_output(['git','show','d933d62211c30b35b094ece5e6638d8e8c63af85:tools/scripts/xu_soc_ppa.py'],cwd=ROOT,universal_newlines=True)
        old = types.ModuleType('xu_parent_ppa')
        old.__file__ = str(ROOT/'tools/scripts/xu_soc_ppa.py')
        exec(compile(old_text, old.__file__, 'exec'), old.__dict__)
        inv = dict(platform_source_manifest_sha256='HOST IDENTICAL INPUT')
        for profile in old.SOURCE_PROFILES:
            with self.subTest(profile=profile):
                self.assertEqual(old.template(inv,profile),PPA.template(inv,profile))
                self.assertEqual(old.memory_checks(old.template(inv,profile)),PPA.memory_checks(PPA.template(inv,profile)))
                self.assertEqual(old.mapping_identity(old.template(inv,profile)),PPA.mapping_identity(PPA.template(inv,profile)))
        before = {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(old_text).body if isinstance(node,ast.FunctionDef)}
        after = {node.name:ast.dump(node,include_attributes=False) for node in ast.parse((ROOT/'tools/scripts/xu_soc_ppa.py').read_text()).body if isinstance(node,ast.FunctionDef)}
        for name in ['prepare','memory_checks','clock_contract_checks','guarded_tcl']:
            self.assertEqual(before[name],after[name],name+' Tcl generation implementation changed')

    def test_legacy_vcd_power_refuses_unbound_baseline_activity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory/'prepared.json').write_text(json.dumps(dict(implementation=dict(source_profile='s3-pe64'))))
            with self.assertRaisesRegex(ValueError,'candidate-specific clear/request-window'):
                PPA.activity_power(directory,{}, {})
