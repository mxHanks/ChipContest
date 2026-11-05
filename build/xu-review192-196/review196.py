#!/usr/bin/env python3
"""Local-only independent tests of register192 with the real frozen153 API."""
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
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = REPO / 'build/xu-two-candidate-control192'
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
        self.h = self.d / 'xu-two-candidate-control192'; self.h.mkdir()
        (self.h / 'register192.py').write_bytes((SOURCE / 'register192.py').read_bytes())
        self.m = load(self.h / 'register192.py', 'xu196_wrapper')
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
        self.guard = dict(schema='xu-two-candidate-control192-v1', qualification='NOT_QUALIFIED', jobs=rows)
        write(self.h / 'frozen-jobs192.json', self.guard)

    def run_main(self):
        # Both would be a severe regression for a registration-only wrapper.
        with mock.patch('subprocess.Popen', side_effect=AssertionError('no child launch')), \
             mock.patch('os.kill', side_effect=AssertionError('no process signal')), \
             mock.patch('sys.stdout', new=io.StringIO()):
            self.m.main()

    def test_register_only_and_idempotent_original_bytes(self):
        self.run_main()
        receipt = self.b / 'two-candidate-followup-registration-20261105-192.json'
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
        with self.assertRaisesRegex(ValueError, 'frozen192 job bytes'):
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
        api = load(SOURCE / 'register192.py', 'xu196_actual')
        api.B = Path('/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102')
        api.C = self.c
        guard = json.loads((SOURCE / 'frozen-jobs192.json').read_text())
        jobs, records = api.validate_jobs(self.core, guard)
        self.assertEqual([j['id'] for _, j in jobs], api.IDS)
        self.assertEqual(len({j['output_root'] for _, j in jobs}), 4)
        self.assertEqual(len(records), len({r['path'] for r in records}))
        transport = json.loads((SOURCE / 'transport192.json').read_text())
        for name, spec in [('runtime192.tar.gz', transport['archive']), ('install192.py', transport['installer'])]:
            raw = (SOURCE / name).read_bytes()
            self.assertEqual(len(raw), spec['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), spec['sha256'])
        with tarfile.open(str(SOURCE / 'runtime192.tar.gz'), 'r:gz') as archive:
            members = archive.getmembers()
            self.assertTrue(all(x.isfile() and not x.issym() and not x.islnk() for x in members))
            payload = {m.name: archive.extractfile(m).read() for m in members}
            self.assertEqual(len(payload), len(members))
        manifest = json.loads(payload.pop('manifest192.json'))
        self.assertEqual(manifest, json.loads((SOURCE / 'manifest192.json').read_text()))
        self.assertEqual(set(payload), {r['name'] for r in manifest['files']})
        for row in manifest['files']:
            raw = payload[row['name']]
            self.assertEqual(len(raw), row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
            self.assertEqual(raw, (REPO / 'build' / row['name']).read_bytes())
        self.assertFalse(any(n.endswith(('.lib', '.db', '.v', '.sv')) for n in payload))

    def test_builder_reproduces_archive_and_installer_byte_for_byte(self):
        build = Path(self.tmp.name) / 'rebuild'
        for name in ['xu-two-candidate-control192', 'xu-s2e-coverage186', 'xu-s2c-common-power190', 'xu-two-candidate-finalpack191']:
            shutil.copytree(REPO / 'build' / name, build / name)
        maker = load(build / 'xu-two-candidate-control192/build192.py', 'xu196_builder')
        with mock.patch('sys.stdout', new=io.StringIO()): maker.main()
        for name in ['runtime192.tar.gz', 'install192.py', 'transport192.json', 'manifest192.json', 'frozen-jobs192.json']:
            self.assertEqual((build / 'xu-two-candidate-control192' / name).read_bytes(), (SOURCE / name).read_bytes())

    def test_scope_expansion_rejected(self):
        path = next(self.b.glob('*.scope-two163-*/receipt.json')); value = json.loads(path.read_text())
        value['preserved_profiles'].append('pe64'); write(path, value)
        with self.assertRaisesRegex(ValueError, 'scope163 differs'): self.run_main()

    def test_existing_changed_registration_preserved(self):
        p = self.c / 'registrations' / (self.jobs[0]['id'] + '.json'); p.write_text('ORIGINAL_UNTOUCHED')
        with self.assertRaisesRegex(ValueError, 'changed registration'): self.run_main()
        self.assertEqual(p.read_text(), 'ORIGINAL_UNTOUCHED')


if __name__ == '__main__': unittest.main(verbosity=2)
