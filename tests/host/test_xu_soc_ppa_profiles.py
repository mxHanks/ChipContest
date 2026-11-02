"""Approved S1 source/geometry guards; all library/collection fixtures are host only."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
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
    def identity(self, path):
        return dict(path=str(path.resolve()),sha256=PPA.sha(path))

    def fixture(self, directory, profile='sram-bias'):
        inv=dict(root=str(ROOT),main_commit='HOST',e203_commit='HOST',platform_source_manifest_sha256='HOST')
        impl=PPA.template(inv,profile)
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
        for profile in ['baseline','h2-only','sram-bias']:
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


if __name__=='__main__':
    unittest.main()
