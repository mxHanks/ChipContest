#!/usr/bin/env python3
"""Local-only independent tests of register198 with the real frozen153 API."""
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import tarfile
from pathlib import Path
import subprocess
import tempfile
import runpy
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE = REPO / 'build/xu-two-candidate-control198'
CORE = REPO / 'build/xu-campaign-batch154/control153/xu_experiments.py'
LEGACY = REPO / 'build/xu-s2c-readonly177-control182/s2c_readonly177.json'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name) / 'Desktop'; self.d.mkdir()
        self.b = self.d / 'xu-score-optimization-20261102'; self.b.mkdir()
        self.c = self.b / 'unified-experiment-control-20261105-150'; self.c.mkdir()
        (self.c / 'registrations').mkdir()
        self.h = self.d / 'xu-two-candidate-control198'; self.h.mkdir()
        (self.h / 'register198.py').write_bytes((SOURCE / 'register198.py').read_bytes())
        self.m = load(self.h / 'register198.py', 'xu196_wrapper')
        self.m.D = self.d; self.m.B = self.b; self.m.C = self.c; self.m.HERE = self.h
        self.m.WORKER = self.d / 'xu-campaign-batch154/control153/xu_experiments.py'
        self.m.WORKER.parent.mkdir(parents=True); self.m.WORKER.write_bytes(CORE.read_bytes())
        self.core = load(self.m.WORKER, 'xu196_frozen153')
        assert hashlib.sha256(CORE.read_bytes()).hexdigest() == self.m.WORKER_SHA
        legacy = self.c / 'registrations/s2c_readonly177.json'; legacy.write_bytes(LEGACY.read_bytes())
        assert hashlib.sha256(legacy.read_bytes()).hexdigest() == 'a86e46ab86453c48e8dbf57df4ef40c3401e824448c4bb8ec0510457869bba8d'
        # The current test process is an identity stand-in. This exercises
        # PID/uid/start_ticks/argv comparisons; no controller is started.
        self.state = dict(worker=self.core.identity(self.m.WORKER), controller_pid=os.getpid(),
                          controller_identity=self.core.process_identity(os.getpid()))
        write(self.c / 'state.json', self.state)
        scope = self.b / 'unified-experiment-control-20261105-150.scope-two163-fixture'; scope.mkdir()
        write(scope / 'receipt.json', dict(status='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED',
            preserved_profiles=['s2e', 's2c'], workers_signalled=0, workers_restarted=0))
        write(self.b / 's2c-readonly177-registration-20261105-182.json', dict(
            status='REGISTERED_OWN_S2C_READONLY177_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
            workers_signalled=0, workers_restarted=0, experiments_directly_launched=0,
            registration=self.core.identity(legacy)))
        common = self.d / 'shared-runtime.txt'; common.write_text('FROZEN_ONLY_NOT_EXECUTABLE\n')
        record = self.core.identity(common)
        self.jobs = []
        for ident, deps in zip(self.m.IDS, self.m.DEPS):
            out = self.b / (ident + '-fixture')
            self.jobs.append(dict(schema='xu-experiment-control150-job-v1', qualification='NOT_QUALIFIED',
                id=ident, kind='launch', launch_mode='direct', native=True,
                argv=['/bin/python3', '-B', '-u', '/not/executed.py', '--out', str(out)],
                output_root=str(out), process_contains=str(out), result_state=str(out / 'state.json'),
                dependencies=[dict(id=i, policy=p) for i, p in deps], frozen_inputs=[copy.deepcopy(record)],
                success_statuses=['DONE_NOT_QUALIFIED'], failure_statuses=['FAIL_NOT_QUALIFIED']))
        self.freeze()

    def freeze(self):
        rows = []
        for job in self.jobs:
            p = self.h / (job['id'] + '.json'); write(p, job)
            identity = self.core.identity(p)
            rows.append(dict(name=p.name, bytes=identity['bytes'], sha256=identity['sha256']))
        self.guard = dict(schema='xu-two-candidate-control198-v1', qualification='NOT_QUALIFIED', jobs=rows)
        write(self.h / 'frozen-jobs198.json', self.guard)

    def run_main(self):
        # Both would be a severe regression for a registration-only wrapper.
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no child launch')), \
             mock.patch('os.kill', side_effect=AssertionError('no process signal')), \
             mock.patch('sys.stdout', new=io.StringIO()):
            self.m.main()

    def test_register_only_and_idempotent_original_bytes(self):
        self.run_main()
        receipt = self.b / 'two-candidate-followup-registration-20261105-198.json'
        original = receipt.read_bytes(); value = json.loads(original)
        self.assertEqual(value['workers_signalled'], 0)
        self.assertEqual(value['workers_restarted'], 0)
        self.assertEqual(value['experiments_directly_launched'], 0)
        before = value['frozen_before']; self.assertEqual(before, value['frozen_after'])
        self.assertEqual(len(before), len({r['path'] for r in before}))
        for job in self.jobs:
            self.assertEqual((self.c / 'registrations' / (job['id'] + '.json')).read_bytes(),
                             (self.h / (job['id'] + '.json')).read_bytes())
            self.assertFalse(Path(job['output_root']).exists())
        self.run_main(); self.assertEqual(receipt.read_bytes(), original)

    def test_changed_guard_job_bytes_rejected(self):
        p = self.h / (self.jobs[0]['id'] + '.json'); p.write_text(p.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'frozen198 job bytes'):
            self.run_main()
        self.assertFalse((self.c / 'registrations' / p.name).exists())

    def test_duplicate_output_root_rejected(self):
        for k in ['output_root', 'process_contains', 'result_state']:
            self.jobs[1][k] = self.jobs[0][k]
        self.jobs[1]['argv'][-1] = self.jobs[0]['output_root']
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'four unique output'):
            self.run_main()

    def test_dependency_or_native_policy_change_rejected(self):
        for key, value, regex in [('dependencies', [], 'dependency chain'), ('native', False, 'native jobs')]:
            with self.subTest(key=key):
                old = copy.deepcopy(self.jobs[0][key]); self.jobs[0][key] = value; self.freeze()
                with self.assertRaisesRegex(ValueError, regex): self.run_main()
                self.jobs[0][key] = old; self.freeze()

    def test_unregistered_existing_output_and_broken_symlink_rejected(self):
        out = Path(self.jobs[0]['output_root']); out.mkdir()
        with self.assertRaisesRegex(ValueError, 'unadopted existing output'): self.run_main()
        out.rmdir(); out.symlink_to(self.b / 'absent-target')
        with self.assertRaisesRegex(ValueError, 'unadopted existing output'): self.run_main()

    def test_conflicting_runtime_identities_rejected(self):
        self.jobs[1]['frozen_inputs'][0]['sha256'] = '0' * 64; self.freeze()
        with self.assertRaisesRegex(ValueError, 'conflicting frozen guard/runtime identity'): self.run_main()

    def test_reused_pid_identity_and_modified_controller_rejected(self):
        self.state['controller_identity']['start_ticks'] += 1; write(self.c / 'state.json', self.state)
        with self.assertRaisesRegex(ValueError, 'original153 must be alive'): self.run_main()
        self.m.WORKER.write_text(self.m.WORKER.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'controller runtime identity'): self.run_main()

    def test_job_change_after_validate_cannot_rebind_guard_identity(self):
        original = self.m.validate_jobs
        def changed(module, guard):
            result = original(module, guard)
            p = self.h / (self.jobs[0]['id'] + '.json')
            p.write_text(p.read_text() + ' ')
            return result
        with mock.patch.object(self.m, 'validate_jobs', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'job changed after guard validation'):
                self.run_main()
        self.assertFalse((self.c / 'registrations' / (self.jobs[0]['id'] + '.json')).exists())

    def test_actual_four_job_guard_and_runtime_tar(self):
        api = load(SOURCE / 'register198.py', 'xu196_actual')
        api.B = Path('/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102')
        api.C = self.c
        guard = json.loads((SOURCE / 'frozen-jobs198.json').read_text())
        jobs, records = api.validate_jobs(self.core, guard)
        self.assertEqual([j['id'] for _, j in jobs], api.IDS)
        self.assertEqual(len({j['output_root'] for _, j in jobs}), 4)
        self.assertEqual(len(records), len({r['path'] for r in records}))
        transport = json.loads((SOURCE / 'transport198.json').read_text())
        for name, spec in [('runtime198.tar.gz', transport['archive']), ('install198.py', transport['installer'])]:
            raw = (SOURCE / name).read_bytes()
            self.assertEqual(len(raw), spec['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), spec['sha256'])
        with tarfile.open(str(SOURCE / 'runtime198.tar.gz'), 'r:gz') as archive:
            members = archive.getmembers()
            self.assertTrue(all(x.isfile() and not x.issym() and not x.islnk() for x in members))
            payload = {m.name: archive.extractfile(m).read() for m in members}
            self.assertEqual(len(payload), len(members))
        manifest = json.loads(payload.pop('manifest198.json'))
        self.assertEqual(manifest, json.loads((SOURCE / 'manifest198.json').read_text()))
        self.assertEqual(set(payload), {r['name'] for r in manifest['files']})
        for row in manifest['files']:
            raw = payload[row['name']]
            self.assertEqual(len(raw), row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
            self.assertEqual(raw, (REPO / 'build' / row['name'].replace('xu-s2c-common-power198/', 'xu-s2c-common-power190/', 1)).read_bytes())
        self.assertFalse(any(n.endswith(('.lib', '.db', '.v', '.sv')) for n in payload))

    def test_builder_reproduces_archive_and_installer_byte_for_byte(self):
        build = Path(self.tmp.name) / 'rebuild'
        for name in ['xu-two-candidate-control198', 'xu-s2e-coverage186', 'xu-s2c-common-power190', 'xu-two-candidate-finalpack191']:
            shutil.copytree(REPO / 'build' / name, build / name)
        maker = load(build / 'xu-two-candidate-control198/build198.py', 'xu196_builder')
        with mock.patch('sys.stdout', new=io.StringIO()): maker.main()
        for name in ['runtime198.tar.gz', 'install198.py', 'transport198.json', 'manifest198.json', 'frozen-jobs198.json']:
            self.assertEqual((build / 'xu-two-candidate-control198' / name).read_bytes(), (SOURCE / name).read_bytes())

    def test_register_is_exact_namespace_clone_of_reviewed192(self):
        old = (REPO / 'build/xu-two-candidate-control192/register192.py').read_text()
        self.assertEqual((SOURCE / 'register198.py').read_text(), old.replace('192', '198'))

    def test_frozen_fm_is_original09_and_runtime_isolated(self):
        root = REPO / 'build/xu-s2c-common-power190'
        original = REPO / 'build/xu-score-resume-20261103/current-evidence-export-09/candidate-formality-campaign-20261103-01/state.json'
        raw = (root / 'frozen-fm190.json').read_bytes()
        self.assertEqual(raw, original.read_bytes())
        self.assertEqual(len(raw), 349702)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'dadd3bb693a3ae17bf92682d9586fa1ba07e6ead468465e07b67fa91eabea5dd')
        origin_manifest = json.loads((original.parents[1] / 'manifest.json').read_text())
        rows = origin_manifest['files'] if isinstance(origin_manifest, dict) else origin_manifest
        receipts = [r for r in rows if r['path'] == 'candidate-formality-campaign-20261103-01/state.json']
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(receipts[0]['bytes'], len(raw))
        ref = json.loads((root / 'references190.json').read_text())
        self.assertEqual(ref['fm_state']['sha256'], ref['fm_state_original']['sha256'])
        self.assertEqual(Path(ref['fm_state']['path']).parent.name, 'xu-s2c-common-power198')
        manifest = json.loads((root / 'manifest190.json').read_text())
        self.assertEqual(len(manifest['runtime']), 8)
        for filename in ['s2c_common_preflight190.json', 's2c_common_full12_190.json']:
            job = json.loads((SOURCE / filename).read_text())
            self.assertEqual(Path(job['argv'][3]).parent.name, 'xu-s2c-common-power198')
            self.assertFalse(any(r['path'] == ref['fm_state_original']['path'] for r in job['frozen_inputs']))
            names = {r['path'] for r in job['frozen_inputs']}
            prefix = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-s2c-common-power198/'
            self.assertTrue({prefix + r['name'] for r in manifest['runtime']} <= names)
            self.assertIn(prefix + 'manifest190.json', names)
        for name in ['s2e_coverage186.json', 'two_candidate_finalpack191.json']:
            self.assertEqual((SOURCE / name).read_bytes(), (REPO / 'build/xu-two-candidate-control192' / name).read_bytes())

    def test_install198_preserves_every_existing192_runtime_byte(self):
        isolated_home = Path(self.tmp.name) / 'install-isolated'
        desktop = isolated_home / 'Desktop'; desktop.mkdir(parents=True)
        campaign = desktop / 'xu-score-optimization-20261102'; campaign.mkdir()
        old_tar = REPO / 'build/xu-two-candidate-control192/runtime192.tar.gz'
        old = {}
        with tarfile.open(str(old_tar), 'r:gz') as archive:
            for member in archive:
                if member.name == 'manifest192.json': continue
                self.assertTrue(member.isfile())
                raw = archive.extractfile(member).read()
                destination = desktop / member.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw); old[member.name] = raw
        prior_receipt = campaign / 'followup192-install.json'
        prior_receipt.write_text('PRESERVE_OLD_192_FAILURE_RECEIPT')
        transport = json.loads((SOURCE / 'transport198.json').read_text())
        shutil.copyfile(SOURCE / 'runtime198.tar.gz', desktop / transport['archive']['name'])
        with mock.patch.object(Path, 'home', return_value=isolated_home), mock.patch('sys.stdout', new=io.StringIO()):
            runpy.run_path(str(SOURCE / 'install198.py'))
        for name, raw in old.items(): self.assertEqual((desktop / name).read_bytes(), raw)
        self.assertEqual(prior_receipt.read_text(), 'PRESERVE_OLD_192_FAILURE_RECEIPT')
        self.assertEqual((desktop / 'xu-s2c-common-power198/frozen-fm190.json').read_bytes(),
                         (REPO / 'build/xu-s2c-common-power190/frozen-fm190.json').read_bytes())
        self.assertTrue((campaign / 'followup198-install.json').is_file())

    def test_scope_expansion_rejected(self):
        path = next(self.b.glob('*.scope-two163-*/receipt.json')); value = json.loads(path.read_text())
        value['preserved_profiles'].append('pe64'); write(path, value)
        with self.assertRaisesRegex(ValueError, 'scope163 differs'): self.run_main()

    def test_existing_changed_registration_preserved(self):
        p = self.c / 'registrations' / (self.jobs[0]['id'] + '.json'); p.write_text('ORIGINAL_UNTOUCHED')
        with self.assertRaisesRegex(ValueError, 'changed registration'): self.run_main()
        self.assertEqual(p.read_text(), 'ORIGINAL_UNTOUCHED')


if __name__ == '__main__': unittest.main(verbosity=2)
