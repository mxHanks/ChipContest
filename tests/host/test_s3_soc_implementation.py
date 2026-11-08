"""S3 preparation guards and actual Tcl control replay; no EDA/qualification result."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S3 = load('s3_soc_implementation', ROOT/'tools/ppa/s3_soc_implementation.py')
PPA = S3.ppa_module(ROOT)


class S3SocImplementationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='s3-ppa-control-')
        cls.directory = Path(cls.temporary.name)
        cls.roots = {}
        registers = Path(os.environ.get('S3_REGISTER_GENERATED_RTL_DIR',
                         str(ROOT.parent/'reports/s3-y32-development/generated-capability-r1/LinearAutoGroupCoreRegisters')))
        if not (registers/'LinearAutoGroupCore.sv').is_file():
            raise ValueError('Set S3_REGISTER_GENERATED_RTL_DIR to the real generated register-cache ablation')
        for profile in PPA.S3_PROFILES:
            root = cls.directory/profile
            for relative in PPA.S3_SOURCE_ROOTS:
                source, destination = ROOT/relative, root/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(str(source), str(destination),
                                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.scala-build', '.bsp'))
                else:
                    shutil.copyfile(str(source), str(destination))
            if profile == 's3-y32-bias-registers':
                for source in registers.glob('*.sv'):
                    shutil.copyfile(str(source), str(root/PPA.RTL/'perips'/source.name))
            cls.roots[profile] = root
        cls.standard = cls.directory/'standard.db'
        cls.sram = cls.directory/'sram.db'
        cls.standard.write_text('HOST CONTROL TEST FIXTURE ONLY: not a usable cell library\n')
        cls.sram.write_text('HOST CONTROL TEST FIXTURE ONLY: not a usable SRAM library\n')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        original_git = PPA.git

        def fixture_git(root, *arguments):
            # Exported test trees lack .git; only revision lookup is substituted.
            # All runtime files, profile identity, source hashes and Tcl are real.
            root = Path(root).resolve()
            if root in self.roots.values():
                self.assertEqual(arguments, ('rev-parse', 'HEAD'))
                return S3.BASELINE_MAIN
            if any(root == candidate/PPA.SUB for candidate in self.roots.values()):
                self.assertEqual(arguments, ('rev-parse', 'HEAD'))
                return S3.BASELINE_E203
            return original_git(root, *arguments)

        patch = mock.patch.object(PPA, 'git', side_effect=fixture_git)
        patch.start(); self.addCleanup(patch.stop)
        patch = mock.patch.object(S3, 'ppa_module', return_value=PPA)
        patch.start(); self.addCleanup(patch.stop)
        self.case = Path(tempfile.mkdtemp(dir=str(self.directory)))

    def identity(self, path):
        return dict(path=str(path.resolve()), sha256=PPA.sha(path))

    def generated(self, profile='s3-y32-bias-sram', schedule='bias-hw-autogroup-y32-packed16-nice-window'):
        root = self.roots[profile]
        receipt = S3.freeze(root, self.case/'freeze', profile)
        source = receipt['worktree_freeze']
        clock = dict(schema='xu-full-soc-clock-review-v1', status='REVIEWED',
                     constraints_sha256=PPA.sha(root/'tools/ppa/xu_full_soc.sdc'),
                     source_files={name:self.identity(root/name) for name in [
                         'tools/ppa/xu_soc_ppa_top.sv', 'tools/ppa/xu_shared_icb_sram.sv',
                         'tools/ppa/xu_full_soc.sdc', 'tools/ppa/xu_review_full_soc_clocks.py']})
        for name in ['primary_clocks', 'generated_clock_policy', 'reset_exceptions',
                     'clock_domain_crossings', 'untested_check_policy']:
            clock[name] = 'HOST CONTROL FIXTURE ONLY; no timing result'
        review = self.case/'clock-review.json'; review.write_text(json.dumps(clock))
        generation = S3.generate(root, self.case/'implementation', Path(source['path']), source['sha256'],
                                 self.standard, PPA.sha(self.standard), self.sram, PPA.sha(self.sram), review, schedule)
        impl = json.loads((self.case/'implementation/implementation.json').read_text())
        return root, generation, impl

    def test_explicit_profiles_have_exact_nonoverlapping_macro_and_area_scope(self):
        for profile, total in [('s3-y32-bias-sram', 337), ('s3-y32-bias-registers', 336)]:
            with self.subTest(profile=profile):
                inv = PPA.inventory(self.roots[profile], profile)
                impl = PPA.template(inv)
                counts = {g['name']:g['count'] for g in impl['memory_groups']}
                self.assertEqual(sum(counts.values()), total)
                self.assertEqual(counts['accelerator_weights'], 16)
                self.assertEqual(counts.get('accelerator_bias', 0), total-336)
                self.assertEqual([counts[name] for name in ['itcm','dtcm','shared']], [32,32,256])
                self.assertIn('/core/weightBanks/*', next(g['instance_pattern'] for g in impl['memory_groups'] if g['name']=='accelerator_weights'))
                scopes = impl['accelerator_area_scopes']
                self.assertEqual([x['name'] for x in scopes], ['peripheral', 'nice_extension'])
                self.assertIn('/u_e203_cpu/u_e203_nice_core', scopes[1]['pattern'])
                self.assertFalse(any(a['pattern'].startswith(b['pattern']+'/') for a in scopes for b in scopes if a is not b))
                self.assertIn('total must be exactly '+str(total), PPA.memory_checks(impl))
                with self.assertRaisesRegex(ValueError, 'capability'):
                    PPA.inventory(self.roots[profile], 's3-y32-bias-registers' if total==337 else 's3-y32-bias-sram')
        legacy = PPA.template(PPA.inventory(self.roots['s3-y32-bias-sram']))
        self.assertNotIn('hardware_profile', legacy)
        self.assertNotIn('accelerator_area_scopes', legacy)
        self.assertEqual(sum(g['count'] for g in legacy['memory_groups']),336)

    def test_real_source_snapshot_prepares_but_never_prefills_qualification(self):
        root, generation, impl = self.generated()
        self.assertEqual(generation['status'], 'GENERATED_NOT_QUALIFIED')
        self.assertEqual(generation['macro_total'],337)
        proof = json.loads((self.case/'implementation/mapping-proof.json').read_text())
        self.assertEqual(proof['status'],'UNREVIEWED')
        self.assertTrue(all(x['status']=='NOT_RUN' and x['log'] is None for x in proof['checks'].values()))
        for name in ['nice_oitf_completion_and_errors', 's3_task_clear_protocol', 'bias_prefetch_epoch_and_clear']:
            self.assertIn('mapping:'+name+':NOT_RUN',generation['qualification_gaps'])
        with self.assertRaisesRegex(ValueError,'allow-unqualified'):
            PPA.checked_implementation(impl,PPA.inventory(root,impl['hardware_profile']))
        prepared = PPA.prepare(root,self.case/'prepared',impl,allow_unqualified=True)
        self.assertEqual(prepared['status'],'PREPARED_NOT_QUALIFIED')
        files = (self.case/'prepared/rtl.f').read_text()
        self.assertIn('xu_nice_drain8.v',files)
        self.assertIn('BiasSramPrefetch.sv',files)
        script = (self.case/'prepared/synth.tcl').read_text()
        self.assertIn('accelerator-area.tsv',script)
        self.assertIn('entire_nice',script)
        self.assertIn('total must be exactly 337',script)
        PPA.verify_prepared(root,self.case/'prepared',prepared)

    def test_register_ablation_prepares_with_no_fictitious_bias_macro(self):
        root, generation, impl = self.generated('s3-y32-bias-registers')
        self.assertEqual(generation['macro_total'],336)
        self.assertNotIn('accelerator_bias',{g['name'] for g in impl['memory_groups']})
        prepared = PPA.prepare(root,self.case/'prepared',impl,allow_unqualified=True)
        self.assertEqual(prepared['status'],'PREPARED_NOT_QUALIFIED')
        self.assertIn('total must be exactly 336',(self.case/'prepared/synth.tcl').read_text())

    def test_added_untracked_or_modified_source_invalidates_frozen_implementation(self):
        root, _, impl = self.generated()
        new = root/'model/s3_untracked_probe.py'
        try:
            new.write_text('# Added after freeze: must not be omitted\n')
            with self.assertRaisesRegex(ValueError,'full worktree source freeze differs'):
                PPA.checked_implementation(impl,PPA.inventory(root,impl['hardware_profile']),allow_unqualified=True)
        finally:
            new.unlink()
        source = root/'tests/e203/firmware/accel.c'
        original = source.read_bytes()
        try:
            source.write_bytes(original+b'\n/* source drift */\n')
            with self.assertRaisesRegex(ValueError,'full worktree source freeze differs'):
                PPA.prepare(root,self.case/'must-not-prepare',impl,allow_unqualified=True)
            self.assertFalse((self.case/'must-not-prepare').exists())
        finally:
            source.write_bytes(original)

    def test_wrong_freeze_revision_or_library_sha_cannot_generate(self):
        root, _, impl = self.generated()
        source = impl['worktree_freeze']
        freeze = json.loads(Path(source['path']).read_text())
        freeze['e203_commit'] = 'f49a5fc914971426bd4530db39e270a84b41139f'
        changed = self.case/'wrong-freeze.json'; changed.write_text(json.dumps(freeze))
        args = [root,self.case/'wrong-output',changed,PPA.sha(changed),
                self.standard,PPA.sha(self.standard),self.sram,PPA.sha(self.sram),self.case/'clock-review.json']
        with self.assertRaisesRegex(ValueError,'S3 baseline revision differs'):
            S3.generate(*args)
        self.assertFalse((self.case/'wrong-output').exists())
        args[2:4] = [Path(source['path']),source['sha256']]
        args[5] = '0'*64
        with self.assertRaisesRegex(ValueError,'supplied SHA256 differs'):
            S3.generate(*args)
        args[4] = self.case/'missing.db'
        with self.assertRaisesRegex(ValueError,'regular non-symlink'):
            S3.generate(*args)

    def test_excluding_nice_or_broadening_weight_scope_is_rejected(self):
        root, _, impl = self.generated()
        for name, mutate in [
            ('nice-area', lambda x:x['accelerator_area_scopes'].pop()),
            ('nice-retained', lambda x:x.update(retained_instances=[r for r in x['retained_instances'] if r['name']!='nice'])),
            ('overlapping-memory', lambda x:next(g for g in x['memory_groups'] if g['name']=='accelerator_weights').update(instance_pattern=PPA.RETAINED['accelerator'][0]+'/*')),
        ]:
            changed = copy.deepcopy(impl); mutate(changed)
            with self.subTest(name=name), self.assertRaises(ValueError):
                PPA.checked_implementation(changed,PPA.inventory(root,impl['hardware_profile']),allow_unqualified=True)

    def test_s3_power_input_requires_full_soc_nice_and_bias_then_stays_unqualified(self):
        parent = self.case
        for profile in PPA.S3_PROFILES:
            self.case = parent/profile
            self.case.mkdir()
            schedule=('bias-hw-autogroup-paired-hi-window' if profile=='s3-y32-bias-registers'
                      else 'bias-hw-autogroup-y32-packed16-nice-window')
            root, _, impl = self.generated(profile,schedule)
            out = self.case/'prepared'
            prepared = PPA.prepare(root,out,impl,allow_unqualified=True)
            (out/'mapped.v').write_text('HOST NETLIST FIXTURE ONLY; not a mapped implementation\n')
            (out/'mapped.sdc').write_text('HOST SDC FIXTURE ONLY\n')
            (out/'execution.json').write_text(json.dumps(dict(status='EXECUTED_NOT_QUALIFIED',
                netlist_sha256=PPA.sha(out/'mapped.v'),sdc_sha256=PPA.sha(out/'mapped.sdc'))))
            layers = [dict(layer=index,cycles=index+2,firmware_cycles=index+10) for index in range(12)]
            log = self.case/'simulation.log'
            words=impl['transaction_contract']['shared_writes']
            log.write_text(''.join(('TASK_PASS layer={layer} outputs=25344 writes='+str(words)+' cycles={cycles} firmware_cycles={firmware_cycles}\n').format(**row) for row in layers)+
                           'SOC_PASS tasks=12 outputs=304128 writes='+str(words*12)+'\n')
            result = self.case/'result.json'
            result.write_text(json.dumps(dict(status='PASS',tasks=12,outputs=304128,write_words=12*words,
                                             firmware_schedule=schedule,transaction_contract=impl['transaction_contract'],
                                             firmware_build=dict(configuration=dict(schedule=schedule)),
                                             layers=layers,log_sha256={'simulation.log':PPA.sha(log)})))
            vcd = self.case/'activity.vcd'; vcd.write_text('HOST VCD FIXTURE ONLY\n')
            strip = 'tb/dut'
            scopes = dict(cpu=strip+'/'+PPA.RETAINED['cpu'][0],accelerator=strip+'/'+PPA.RETAINED['accelerator'][0],
                          interconnect=strip+'/'+PPA.RETAINED['interconnect'][0],shared=strip+'/u_shared',
                          itcm=strip+'/'+PPA.MEMORY_SCOPES['itcm'][:-2],dtcm=strip+'/'+PPA.MEMORY_SCOPES['dtcm'][:-2])
            config = PPA.hardware_profile(profile)
            scopes['nice_extension'] = strip+'/'+config['retained']['nice'][0]
            for name in ['accelerator_weights', 'accelerator_bias']:
                if name in config['scopes']:
                    scopes[name] = strip+'/'+config['scopes'][name][:-2]
            ticks=[[i*1000000000000+1000000,i*1000000000000+1000000+((row['cycles']-1)*20000000)//3] for i,row in enumerate(layers)]
            record = dict(hardware_profile=profile,vcd=self.identity(vcd),result=self.identity(result),simulation_log=self.identity(log),
                          mapping_sha256=PPA.digest(dict(replacements=impl['replacements'],added_sources=impl['added_sources'])),
                          source_manifest_sha256=prepared['input_manifest_sha256'],netlist_sha256=PPA.sha(out/'mapped.v'),
                          sdc_sha256=PPA.sha(out/'mapped.sdc'),windows_ns=[[a/1000000,b/1000000] for a,b in ticks],
                          windows_fs=ticks,clock_profile=PPA.S3_CLOCK_PROFILES['nominal150-balanced-v1'],
                          clock_period_ns=20/3,scope='full-digital-soc-including-all-srams',
                          strip_path=strip,scope_paths=scopes)
            for missing in ['nice_extension']+(['accelerator_bias'] if profile=='s3-y32-bias-sram' else []):
                bad = copy.deepcopy(record); bad['scope_paths'].pop(missing)
                with self.subTest(profile=profile,missing=missing), self.assertRaisesRegex(ValueError,'full-power activity scopes'):
                    PPA.activity_power(out,bad,{})
            bad = copy.deepcopy(record); bad['scope_paths']['nice_extension'] = strip+'/hidden_elsewhere'
            with self.assertRaisesRegex(ValueError,'S3 NICE/W/bias activity scope differs'):
                PPA.activity_power(out,bad,{})
            called=[]

            def fixture_tool(directory,command,label,environment):
                index=int(label.rsplit('-',1)[1]); called.append(index)
                script=(directory/command[-1]).read_text()
                self.assertIn('read_vcd -rtl -strip_path {tb/dut}',script)
                self.assertIn('missing/wrong nice',script)
                self.assertIn('total must be exactly '+str(337 if profile=='s3-y32-bias-sram' else 336),script)
                for name in ['switching-before','switching-after','unannotated','power','power-hierarchy','units']:
                    (directory/('task-%02d-%s.rpt'%(index,name))).write_text('HOST CONTROL REPORT FIXTURE ONLY\n')
                return dict(scope='HOST EXECUTION FIXTURE ONLY; no PT run')

            with mock.patch.object(PPA,'run_tool',side_effect=fixture_tool):
                receipt=PPA.activity_power(out,record,{})
            self.assertEqual(called,list(range(12)))
            self.assertEqual(receipt['status'],'EXECUTED_NOT_QUALIFIED')
            self.assertNotIn('energy_joules',receipt)
        self.case = parent

    def run_tcl(self, impl, mutation=None, area=True):
        cells = {}
        for group in impl['memory_groups']:
            prefix = group['instance_pattern'][:-1]
            for index in range(group['count']):
                cells[prefix+'memory_%03d/macro'%index] = ('RAMSP1024X16', '1.0', 0)
        for scope in impl['retained_instances']:
            cells[scope['pattern']] = (scope['reference_pattern'].rstrip('*'), '0', 1)
        scopes = impl['accelerator_area_scopes']
        cells[scopes[0]['pattern']+'/logic'] = ('STD', '7.0', 0)
        cells[scopes[1]['pattern']+'/router'] = ('STD', '3.0', 0)
        cells[scopes[1]['pattern']+'/u_drain8/payload'] = ('STD', '5.0', 0)
        cells[scopes[1]['pattern']+'/u_demo/legacy'] = ('STD', '2.0', 0)
        if mutation:
            mutation(cells)
        script = 'set cells [dict create]\n'
        for name, (ref, size, hierarchy) in cells.items():
            script += 'dict set cells '+PPA.tcl(name)+' [dict create ref_name '+PPA.tcl(ref)+' area '+size+' is_hierarchical '+('true' if hierarchy else 'false')+']\n'
        script += r'''
proc get_cells {args} {
  set filter [lindex $args end]
  set result {}
  dict for {name attrs} $::cells {
    if {[regexp {full_name (==|=~) (\S+)} $filter unused operation pattern]} {
      if {$operation eq "==" && $name ne $pattern} {continue}
      if {$operation eq "=~" && ![string match $pattern $name]} {continue}
    }
    if {[regexp {ref_name (==|=~) (\S+)} $filter unused operation pattern]} {
      set ref [dict get $attrs ref_name]
      if {$operation eq "==" && $ref ne $pattern} {continue}
      if {$operation eq "=~" && ![string match $pattern $ref]} {continue}
    }
    if {[string first {is_hierarchical == false} $filter]>=0 && [dict get $attrs is_hierarchical]} {continue}
    lappend result $name
  }
  return $result
}
proc sizeof_collection {collection} {return [llength $collection]}
proc get_object_name {object} {return $object}
proc get_attribute {object name} {return [dict get $::cells $object $name]}
proc foreach_in_collection {variable collection body} {
  foreach object $collection {
    uplevel 1 [list set $variable $object]
    uplevel 1 $body
  }
}
'''
        script += PPA.guarded_tcl(PPA.memory_checks(impl)+(PPA.accelerator_area_tcl(impl) if area else ''),'HOST_TCL_CONTROL_PASS')
        file = self.case/'control.tcl'; file.write_text(script)
        return subprocess.run(['tclsh',str(file)],cwd=str(self.case),stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,universal_newlines=True)

    def test_actual_tcl_guards_count_all_macros_and_disjoint_nice_area(self):
        for profile in PPA.S3_PROFILES:
            impl = PPA.template(PPA.inventory(self.roots[profile],profile))
            with self.subTest(profile=profile):
                run = self.run_tcl(impl)
                self.assertEqual(run.returncode,0,run.stdout)
                rows = (self.case/'accelerator-area.tsv').read_text().splitlines()
                self.assertEqual(rows[2].split('\t')[0],'nice_extension')
                self.assertEqual(float(rows[2].split('\t')[-1]),10.0)
                total = sum(g['count'] for g in impl['memory_groups'] if g['name'].startswith('accelerator'))+17
                self.assertEqual(float(rows[3].split('\t')[-1]),total)

    def test_actual_tcl_rejects_missing_unaccounted_or_overlapping_macros(self):
        impl = PPA.template(PPA.inventory(self.roots['s3-y32-bias-sram'],'s3-y32-bias-sram'))
        bias = next(g for g in impl['memory_groups'] if g['name']=='accelerator_bias')
        for label, mutation in [
            ('missing',lambda cells:cells.pop(bias['instance_pattern'][:-1]+'memory_000/macro')),
            ('unaccounted',lambda cells:cells.update({'outside/unaccounted_macro':('RAMSP1024X16','1.0',0)})),
        ]:
            with self.subTest(label=label):
                run = self.run_tcl(impl,mutation,area=False)
                self.assertNotEqual(run.returncode,0,run.stdout)
                self.assertIn('XU_FATAL:',run.stdout)
                self.assertNotIn('HOST_TCL_CONTROL_PASS',run.stdout)
        changed = copy.deepcopy(impl)
        weight = next(g for g in changed['memory_groups'] if g['name']=='accelerator_weights')
        first_weight = weight['instance_pattern'][:-1]+'memory_000/macro'
        # Keep the independent physical macro fixture, then point bias at one W
        # leaf to prove the generated Tcl rejects overlap even with count=1.
        next(g for g in changed['memory_groups'] if g['name']=='accelerator_bias')['instance_pattern'] = first_weight
        original = PPA.memory_checks
        with mock.patch.object(PPA,'memory_checks',side_effect=lambda ignored:original(changed)):
            run = self.run_tcl(impl,area=False)
        self.assertNotEqual(run.returncode,0,run.stdout)
        self.assertIn('overlapping SRAM group',run.stdout)


if __name__ == '__main__':
    unittest.main()
