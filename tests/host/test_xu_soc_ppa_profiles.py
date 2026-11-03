"""Approved S1 source/geometry guards; all library/collection fixtures are host only."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_soc_implementation_profiles', ROOT/'tools/ppa/xu_soc_implementation.py')
IMPL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPL)
PPA = IMPL.ppa_module()


class XuSourceProfileGuardTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.child = self.root/PPA.SUB
        self.child.mkdir(parents=True)
        self.git('init', '-q')
        self.git('config', 'user.name', 'xu host fixture')
        self.git('config', 'user.email', 'xu-host-fixture@example.invalid')
        self.git('config', 'commit.gpgsign', 'false')
        self.fixed = self.child/'rtl/e203/core/fixed.v'
        self.fixed.parent.mkdir(parents=True)
        self.fixed.write_text('module fixed; endmodule\n')
        (self.child/'README').write_text('fixed complete tree fixture\n')
        self.baseline = self.commit('baseline fixture')
        self.changed = self.child/'rtl/e203/perips/accel_icb_slave.v'
        self.changed.parent.mkdir(parents=True)
        self.changed.write_text('module accel; endmodule\n')
        self.candidate = self.commit('candidate fixture')
        self.profiles = {'baseline': dict(commit=self.baseline, changed_files=[]),
                         'h2-only': dict(commit=self.candidate, changed_files=['rtl/e203/perips/accel_icb_slave.v'])}
        self.patches = [mock.patch.object(PPA, 'FROZEN_E203', self.baseline),
                        mock.patch.object(PPA, 'SOURCE_PROFILES', self.profiles)]
        for patch in self.patches:patch.start()
        self.addCleanup(self.temporary.cleanup)
        for patch in self.patches:self.addCleanup(patch.stop)

    def git(self, *args):
        return subprocess.check_output(['git']+list(args),cwd=str(self.child),stderr=subprocess.STDOUT).decode().strip()

    def commit(self, message):
        self.git('add', '.');self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def test_explicit_approved_pin_and_complete_fixed_tree_are_required(self):
        identity = PPA.source_profile_identity(self.root, 'h2-only')
        self.assertEqual(identity['e203_commit'], self.candidate)
        self.assertEqual(identity['fixed_tree_file_count'], 2)
        with self.assertRaisesRegex(ValueError, 'approved baseline pin'):
            PPA.source_profile_identity(self.root)
        with self.assertRaisesRegex(ValueError, 'unknown source profile'):
            PPA.source_profile_identity(self.root, 'arbitrary-child')
        (self.child/'README').write_text('non-RTL platform tree also changed\n')
        bad_commit = self.commit('unapproved fixed file mutation')
        self.profiles['h2-only']['commit'] = bad_commit
        with self.assertRaisesRegex(ValueError, 'exact fixed-platform delta'):
            PPA.source_profile_identity(self.root, 'h2-only')

    def test_dirty_fixed_worktree_is_rejected_even_when_git_index_ignores_it(self):
        self.git('update-index', '--assume-unchanged', 'rtl/e203/core/fixed.v')
        self.fixed.write_text('module altered; endmodule\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        with self.assertRaisesRegex(ValueError, 'worktree bytes differ'):
            PPA.source_profile_identity(self.root, 'h2-only')

    def test_untracked_rtl_cannot_enter_the_source_inventory(self):
        (self.fixed.parent/'injected.sv').write_text('module injected; endmodule\n')
        with self.assertRaisesRegex(ValueError, 'untracked/missing fixed-platform RTL'):
            PPA.source_profile_identity(self.root, 'h2-only')

    def test_git_replace_cannot_substitute_different_bytes_under_an_approved_pin(self):
        self.changed.write_text('module substituted; endmodule\n')
        replacement=self.commit('replacement commit fixture')
        self.git('replace',self.candidate,replacement)
        self.git('checkout','-q','--detach',self.candidate)
        self.assertIn('substituted',self.changed.read_text())
        with self.assertRaisesRegex(ValueError,'worktree bytes differ'):
            PPA.source_profile_identity(self.root,'h2-only')


class XuPpaProfileConfigurationTest(unittest.TestCase):
    def test_registered_profiles_reach_the_command_line_generator(self):
        # The deployed S2d command previously stopped in argparse even though
        # direct generate()/memory-geometry tests passed.
        arguments=['xu_soc_implementation.py','--root','candidate','--out','new-output',
                   '--standard-cell-db','std.db','--standard-cell-sha256','a'*64,
                   '--sram-db','ram.db','--sram-sha256','b'*64]
        for profile in PPA.SOURCE_PROFILES:
            with self.subTest(profile=profile), \
                    mock.patch.object(sys,'argv',arguments+['--profile',profile]), \
                    mock.patch.object(IMPL,'generate',return_value={}) as generate, \
                    mock.patch('builtins.print'):
                IMPL.main()
                self.assertEqual(generate.call_args.args[7],profile)
        with mock.patch.object(sys,'argv',arguments+['--profile','unapproved-child']), \
                mock.patch.object(IMPL,'generate') as generate, \
                mock.patch('sys.stderr'):
            with self.assertRaises(SystemExit) as rejected:
                IMPL.main()
            self.assertEqual(rejected.exception.code,2)
            generate.assert_not_called()

    def test_cli_exposes_every_implemented_profile(self):
        result=subprocess.run(['python3',str(ROOT/'tools/ppa/xu_soc_implementation.py'),'--help'],
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,check=True)
        choices=result.stdout.split('--profile {',1)[1].split('}',1)[0].split(',')
        self.assertEqual(choices,sorted(PPA.SOURCE_PROFILES))

    def identity(self, path):
        return dict(path=str(path.resolve()),sha256=PPA.sha(path))

    def fixture(self, directory, profile='sram-bias'):
        inv=dict(root=str(ROOT),main_commit='HOST',e203_commit='HOST',platform_source_manifest_sha256='HOST')
        impl=PPA.template(inv,profile)
        if profile in ('s3-pe32','s3-pe64'):
            prefix = 'PE32' if profile=='s3-pe32' else 'PE64'
            inv.update(main_commit=getattr(PPA,prefix+'_MAIN_COMMIT'), source_profile=profile,
                       accelerator_configuration=dict(getattr(PPA,prefix+'_CONFIGURATION')))
        impl['replacements']={
            PPA.RTL+'/general/sirv_sim_ram.v':self.identity(ROOT/'tools/ppa/xu_sirv_sram_adapter.sv'),
            PPA.RTL+'/perips/mem_1024x16.sv':self.identity(ROOT/'tools/ppa/xu_weight_sram_adapter.sv')}
        if profile=='sram-bias':
            impl['replacements'][PPA.BIAS_MEMORY]=self.identity(ROOT/'tools/ppa/xu_bias_sram_adapter.sv')
        impl['added_sources']=[self.identity(ROOT/'tools/ppa'/name) for name in ['xu_soc_ppa_top.sv','xu_shared_icb_sram.sv']]
        impl['libraries']=[]
        for role in ['standard_cell','sram']+(['bias_sram'] if profile=='sram-bias' else []):
            path=directory/(role+'.db');path.write_text('HOST LIBRARY FIXTURE ONLY '+role)
            impl['libraries'].append(dict(self.identity(path),role=role))
        impl['constraints']=self.identity(ROOT/'tools/ppa/xu_full_soc.sdc')
        review=dict(status='REVIEWED',constraints_sha256=impl['constraints']['sha256'])
        for name in ['primary_clocks','generated_clock_policy','reset_exceptions','clock_domain_crossings','untested_check_policy']:
            review[name]='HOST FIXTURE ONLY'
        path=directory/'clock-review.json';path.write_text(json.dumps(review));impl['clock_review']=self.identity(path)
        if profile in ('s3-pe32','s3-pe64'):
            impl['source_freeze']=dict(profile={},main_commit=inv['main_commit'],e203_commit='HOST',
                memory_groups_sha256=PPA.digest(impl['memory_groups']),libraries_sha256=PPA.digest(impl['libraries']),
                defines_sha256=PPA.digest(impl['defines']),
                accelerator_configuration_sha256=PPA.digest(impl['accelerator_configuration']))
        path=directory/'proof.json';path.write_text(json.dumps(PPA.mapping_review_template(impl)));impl['mapping_proof']=self.identity(path)
        return inv,impl

    def test_bias_padding_and_library_roles_are_explicit_and_fixed(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            inv,impl=self.fixture(Path(temporary))
            _,_,gaps=PPA.checked_implementation(impl,inv,allow_unqualified=True)
            self.assertIn('mapped-equivalence:NOT_RUN',gaps)
            bias=impl['memory_groups'][-1]
            self.assertEqual((bias['logical_bits'],bias['physical_bits'],bias['padding_bits']),(10240,49152,38912))
            self.assertEqual(sum(g['count'] for g in impl['memory_groups']),360)
            targets,links=PPA.library_paths(impl)
            self.assertEqual(len(targets),1);self.assertEqual(len(links),3)
            self.assertNotIn(impl['libraries'][-1]['path'],targets)
            for change in [lambda x:x['memory_groups'][-1].update(physical_bits=10240),
                           lambda x:x['memory_groups'][-1].update(count=25),
                           lambda x:x['memory_groups'][-1].update(instance_pattern='*'),
                           lambda x:x['replacements'].pop(PPA.BIAS_MEMORY),
                           lambda x:x['libraries'][-1].update(role='sram')]:
                bad=copy.deepcopy(impl);change(bad)
                with self.subTest(change=change),self.assertRaises(ValueError):
                    PPA.checked_implementation(bad,inv,allow_unqualified=True)
            with self.assertRaisesRegex(ValueError,'allow-unqualified'):
                PPA.checked_implementation(impl,inv)

    def test_bias_library_is_opt_in_and_cannot_be_attached_to_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            standard=directory/'std.db';sram=directory/'sram.db';bias=directory/'bias.db'
            for path in [standard,sram,bias]:path.write_text('HOST LIBRARY FIXTURE ONLY')
            args=(ROOT,directory/'out',standard,PPA.sha(standard),sram,PPA.sha(sram))
            with self.assertRaisesRegex(ValueError,'requires --bias-sram-db'):
                IMPL.generate(*args,profile='sram-bias')
            with self.assertRaisesRegex(ValueError,'requires --bias-sram-db'):
                IMPL.generate(*args,profile='sram-bias',bias_sram_db=bias)
            with self.assertRaisesRegex(ValueError,'only for sram-bias'):
                IMPL.generate(*args,bias_sram_db=bias,bias_sram_sha=PPA.sha(bias))
            self.assertFalse((directory/'out').exists())

    def test_candidate_source_root_cannot_select_its_stale_ppa_module_or_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            stale=directory/'candidate/tools/scripts/xu_soc_ppa.py';stale.parent.mkdir(parents=True)
            stale.write_text('raise RuntimeError("STALE CANDIDATE MODULE MUST NOT LOAD")\n')
            inv,fixture=self.fixture(directory,'baseline')
            inv.update(root=str(directory/'candidate'))
            review_path=directory/'clock-review.json'
            review=json.loads(review_path.read_text())
            review.update(schema='xu-full-soc-clock-review-v1',source_files={
                name:self.identity(ROOT/name) for name in ['tools/ppa/xu_soc_ppa_top.sv',
                    'tools/ppa/xu_shared_icb_sram.sv','tools/ppa/xu_full_soc.sdc','tools/ppa/xu_review_full_soc_clocks.py']})
            review_path.write_text(json.dumps(review))
            with mock.patch.object(IMPL,'ppa_module',return_value=PPA) as loader, \
                    mock.patch.object(PPA,'source_profile_identity',return_value={}), \
                    mock.patch.object(PPA,'inventory',return_value=inv), \
                    mock.patch.object(IMPL,'topology_identity',return_value={}):
                receipt=IMPL.generate(directory/'candidate',directory/'generated',
                    directory/'standard_cell.db',PPA.sha(directory/'standard_cell.db'),
                    directory/'sram.db',PPA.sha(directory/'sram.db'),clock_review=review_path)
            loader.assert_called_once_with()
            impl=json.loads((directory/'generated/implementation.json').read_text())
            self.assertEqual(impl['source_freeze']['main_commit'],'HOST')
            self.assertEqual(impl['tool_assets_root'],str(ROOT))
            self.assertEqual(impl['constraints']['path'],str(ROOT/'tools/ppa/xu_full_soc.sdc'))
            self.assertEqual(receipt['tool_producer']['ppa']['sha256'],PPA.sha(PPA.__file__))

    def test_macro_namespace_rejects_extra_unknown_and_unaccounted_leaves(self):
        # Tcl collections exercise accounting logic only, never EDA semantics.
        mock_tcl='''
proc get_cells {args} {
  set filter [lindex $args end]; set result {}
  dict for {name ref} $::refs {
    set keep 1
    foreach field {full_name ref_name} value [list $name $ref] {
      if {[regexp "$field (=~|==) (\\\\S+)" $filter ignored op pattern]} {
        if {$op eq "=~"} {set ok [string match $pattern $value]} else {set ok [expr {$pattern eq $value}]}
        if {!$ok} {set keep 0}
      }
    }
    if {$keep} {lappend result $name}
  }
  return $result
}
proc sizeof_collection {cells} {llength $cells}
proc get_object_name {cell} {return $cell}
proc get_attribute {cell attribute} {dict get $::refs $cell}
proc foreach_in_collection {variable cells body} {uplevel 1 [list foreach $variable $cells $body]}
'''
        for profile in PPA.SOURCE_PROFILES:
            impl=PPA.template(dict(platform_source_manifest_sha256='HOST'),profile)
            refs={}
            for group in impl['memory_groups']:
                for index in range(group['count']):
                    refs[group['instance_pattern'].replace('*','host-bank-%d'%index)]=group['macro_ref']
            for retained in impl['retained_instances']:
                refs[retained['pattern']]=retained['reference_pattern'].rstrip('*')
            for extra in [None,'RAMSP128X16','RAMSP2048X16','RAMSP1024X16']:
                with self.subTest(profile=profile,extra=extra),tempfile.TemporaryDirectory() as temporary:
                    cells=dict(refs)
                    if extra:cells['unaccounted/host_macro']=extra
                    script=Path(temporary)/'check.tcl'
                    script.write_text('set refs [dict create '+' '.join(PPA.tcl(k)+' '+PPA.tcl(v) for k,v in cells.items())+']\n'+
                                      mock_tcl+PPA.guarded_tcl(PPA.memory_checks(impl),'HOST_ACCOUNTING_PASS'))
                    result=subprocess.run(['tclsh',str(script)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                    self.assertEqual(result.returncode==0,extra is None,result.stdout)

    def test_pe32_requires_frozen_physical_variant_and_complete_padding(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            inv,impl=self.fixture(Path(temporary),'s3-pe32')
            PPA.checked_implementation(impl,inv,allow_unqualified=True)
            self.assertEqual([g['count'] for g in impl['memory_groups']],[32,32,256,32])
            self.assertEqual(sum(g['count'] for g in impl['memory_groups']),352)
            weight=impl['memory_groups'][-1]
            self.assertEqual((weight['logical_bits'],weight['physical_bits'],weight['padding_bits']),(262144,524288,262144))
            # Re-hash the changed manifest as an attacker might; fixed geometry
            # and variant guards must still reject a self-consistent mutation.
            mutations=[lambda x:x['defines'].pop(),lambda x:x['defines'].append('XU_ACCEL_PE32=0'),
                lambda x:x.update(accel_variant='pe8'),
                lambda x:x['accelerator_configuration'].update(weight_padding_bytes=0),
                lambda x:x['memory_groups'][-1].update(count=16),
                lambda x:x['memory_groups'][-1].update(physical_bits=262144,padding_bits=0),
                lambda x:x['memory_groups'][-1].update(logical_depth=1024),
                lambda x:x['memory_groups'][-1].update(instance_pattern=PPA.MEMORY_SCOPES['accelerator_weights']),
                lambda x:x['retained_instances'][0].update(reference_pattern='accel_icb_slave*')]
            for mutate in mutations:
                with self.subTest(mutation=mutations.index(mutate)):
                    bad=copy.deepcopy(impl);mutate(bad)
                    bad['source_freeze'].update(memory_groups_sha256=PPA.digest(bad['memory_groups']),
                        defines_sha256=PPA.digest(bad['defines']),
                        accelerator_configuration_sha256=PPA.digest(bad['accelerator_configuration']))
                    with self.assertRaises(ValueError):PPA.checked_implementation(bad,inv,allow_unqualified=True)

    def test_pe32_proof_and_source_freeze_bind_the_compile_branch(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            inv,impl=self.fixture(Path(temporary),'s3-pe32')
            for mutate in [lambda x:x.pop('source_freeze'),
                           lambda x:x['source_freeze'].pop('defines_sha256'),
                           lambda x:x['source_freeze'].pop('accelerator_configuration_sha256')]:
                bad=copy.deepcopy(impl);mutate(bad)
                with self.assertRaisesRegex(ValueError,'source freeze'):
                    PPA.checked_implementation(bad,inv,allow_unqualified=True)
            old_proof=PPA.mapping_review_template(impl)
            old_proof['mapping_sha256']=PPA.digest(dict(replacements=impl['replacements'],added_sources=impl['added_sources']))
            path=Path(temporary)/'old-8pe-proof.json';path.write_text(json.dumps(old_proof))
            impl['mapping_proof']=self.identity(path)
            with self.assertRaisesRegex(ValueError,'mapping proof is not bound'):
                PPA.checked_implementation(impl,inv,allow_unqualified=True)

    def test_inventory_identifies_the_32pe_child_instead_of_reporting_16_weight_macros(self):
        # Source inventory classification only; neither mock commit identity
        # nor file declarations constitute an elaboration or SRAM-model test.
        def fixture_git(root,*args):
            return PPA.SOURCE_PROFILES['s3-pe32']['commit'] if Path(root)==ROOT/PPA.SUB else 'HOST_MAIN'
        with mock.patch.object(PPA,'git',side_effect=fixture_git):
            inv=PPA.inventory(ROOT)
        self.assertEqual(inv['source_profile'],'s3-pe32')
        self.assertEqual(inv['memories']['accelerator_weights']['physical_1024x16_macros'],32)
        self.assertEqual(inv['hypothetical_1024x16_macro_total'],352)
        self.assertEqual(inv['required_compile_defines'],PPA.PE32_DEFINES)
        self.assertEqual(PPA.template(inv,'s3-pe32')['defines'],PPA.PE32_DEFINES)

    def test_pe32_define_cannot_silently_select_a_different_baseline_architecture(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            inv,impl=self.fixture(Path(temporary),'baseline')
            impl['defines'].append('XU_ACCEL_PE32=1')
            with self.assertRaisesRegex(ValueError,'only for s3-pe32'):
                PPA.checked_implementation(impl,inv,allow_unqualified=True)

    def test_pe32_cannot_prepare_a_different_main_with_the_same_child_pin(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(PPA,'source_profile_identity',return_value={}):
            inv,impl=self.fixture(Path(temporary),'s3-pe32')
            inv['main_commit']='UNAPPROVED_MAIN'
            impl['source_freeze']['main_commit']=inv['main_commit']
            with self.assertRaisesRegex(ValueError,'exact approved candidate main commit'):
                PPA.checked_implementation(impl,inv,allow_unqualified=True)

    def test_pe32_legacy_vcd_power_cannot_reuse_unbound_eight_pe_activity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            (directory/'prepared.json').write_text(json.dumps(dict(implementation=dict(source_profile='s3-pe32'))))
            with self.assertRaisesRegex(ValueError,'candidate-specific clear/request-window'):
                PPA.activity_power(directory,{}, {})


if __name__=='__main__':
    unittest.main()
