#!/usr/bin/env python3
"""Independent local208 archive/lineage and real153 registration-flow checks. No EDA."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = ROOT / 'build/xu-native-query-control208'
SHA = '19a29eea919fcd64f4f71482cae8a96477f1129676b6b527408f912e4444441f'
CONTROL = ROOT / 'build/xu-campaign-batch154/control153/xu_experiments.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


class Review(unittest.TestCase):
    def test_actual_archive_manifest_runtime_and_job_identities(self):
        raw = (P / 'runtime208.tar.gz').read_bytes()
        self.assertEqual(len(raw), 266728); self.assertEqual(hashlib.sha256(raw).hexdigest(), SHA)
        with tarfile.open(str(P / 'runtime208.tar.gz'), 'r:gz') as tar:
            actual = {}
            for row in tar:
                name = PurePosixPath(row.name)
                self.assertTrue(row.isfile() and not row.issym() and not row.islnk() and not row.sparse)
                self.assertFalse(name.is_absolute() or '..' in name.parts)
                self.assertEqual(str(name), row.name); self.assertNotIn(row.name, actual)
                actual[row.name] = tar.extractfile(row).read()
        manifest = json.loads(actual.pop('manifest208.json'))
        self.assertEqual(len(actual), 29); self.assertEqual(set(actual), {r['name'] for r in manifest['files']})
        for row in manifest['files']:
            body = actual[row['name']]; self.assertEqual(len(body), row['bytes']); self.assertEqual(hashlib.sha256(body).hexdigest(), row['sha256'])
            self.assertEqual(body, (ROOT / 'build' / row['name']).read_bytes())
        self.assertFalse(any(Path(n).suffix in ['.v', '.sv', '.lib', '.db', '.pdf'] for n in actual))
        guard = json.loads(actual['xu-native-query-control208/frozen-jobs208.json'])
        self.assertEqual(guard['schema'], 'xu-two-candidate-control208-v1')
        ancestor = ROOT / 'build/xu-score-resume-20261103/followup199/two-candidate-followup-registration-20261105-198.json'
        self.assertEqual(hashlib.sha256(ancestor.read_bytes()).hexdigest(), guard['ancestry198']['sha256'])
        self.assertEqual(ancestor.stat().st_size, guard['ancestry198']['bytes'])
        for row, expected in zip(guard['jobs'], ['native_query207', 'two_candidate_finalpack209']):
            body = actual['xu-native-query-control208/' + row['name']]
            self.assertEqual(hashlib.sha256(body).hexdigest(), row['sha256'])
            job = json.loads(body); self.assertEqual(job['id'], expected); self.assertIs(job['native'], True)
            self.assertEqual(job['process_contains'], job['output_root']); self.assertEqual(job['argv'][-2:], ['--out', job['output_root']])
            self.assertEqual(job['result_state'], job['output_root'] + '/state.json')
        native = json.loads(actual['xu-native-query-control208/native_query207.json'])
        pack = json.loads(actual['xu-native-query-control208/two_candidate_finalpack209.json'])
        self.assertEqual(native['dependencies'], [dict(id='two_candidate_finalpack191', policy='terminal')])
        self.assertEqual(pack['dependencies'], [dict(id='native_query207', policy='terminal')])
        self.assertNotEqual(native['output_root'], pack['output_root'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name) / 'Desktop'; self.b = self.d / 'xu-score-optimization-20261102'; self.b.mkdir(parents=True)
        self.c = self.b / 'unified-experiment-control-20261105-150'; (self.c / 'registrations').mkdir(parents=True)
        self.h = self.d / 'xu-native-query-control208'; self.h.mkdir()
        self.api = load(P / 'register208.py', 'xu213_register'); self.m = load(CONTROL, 'xu213_actual153')
        self.api.D = self.d; self.api.B = self.b; self.api.C = self.c; self.api.HERE = self.h
        self.worker = self.d / 'worker.py'; self.worker.write_bytes(CONTROL.read_bytes()); self.api.WORKER = self.worker
        self.seed = self.b / 'frozen.txt'; self.seed.write_bytes(b'host registration fixture only; no native launch')
        self.old177 = self.c / 'registrations/s2c_readonly177.json'
        self.old177.write_bytes((ROOT / 'build/xu-score-resume-20261103/final171/unified-experiment-control-20261105-150/registrations/s2c_readonly177.json').read_bytes())
        self.old191 = self.c / 'registrations/two_candidate_finalpack191.json'
        self.old191.write_bytes((ROOT / 'build/xu-score-resume-20261103/followup199/unified-experiment-control-20261105-150/registrations/two_candidate_finalpack191.json').read_bytes())
        write(self.b / 's2c-readonly177-registration-20261105-182.json', dict(status='REGISTERED_OWN_S2C_READONLY177_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
             workers_signalled=0, workers_restarted=0, experiments_directly_launched=0, registration=self.m.identity(self.old177)))
        write(self.b / 'unified-experiment-control-20261105-150.scope-two163-fixture/receipt.json', dict(status='DEFERRED_ORIGINAL_WORKERS_PRESERVED_CONTROLLER_RESUMED_NOT_QUALIFIED',
             preserved_profiles=['s2e', 's2c'], workers_signalled=0, workers_restarted=0))
        self.ancestor = self.b / 'two-candidate-followup-registration-20261105-198.json'
        write(self.ancestor, dict(status='REGISTERED_TWO_CANDIDATE_FOLLOWUP198_NOT_QUALIFIED', registrations=[dict(path='unrelated' + str(i)) for i in range(3)] + [self.m.identity(self.old191)]))
        frozen = []
        for name in ['native_query207', 'two_candidate_finalpack209']:
            job = json.loads((P / (name + '.json')).read_text()); out = self.b / Path(job['output_root']).name
            job.update(output_root=str(out), process_contains=str(out), result_state=str(out / 'state.json'), frozen_inputs=[self.m.identity(self.seed)])
            job['argv'][-1] = str(out); write(self.h / (name + '.json'), job)
            row = self.m.identity(self.h / (name + '.json')); frozen.append(dict(name=name + '.json', bytes=row['bytes'], sha256=row['sha256']))
        self.guard = self.h / 'frozen-jobs208.json'
        write(self.guard, dict(schema='xu-two-candidate-control208-v1', qualification='NOT_QUALIFIED', jobs=frozen, ancestry198=self.m.identity(self.ancestor)))
        write(self.c / 'state.json', dict(controller_pid=os.getpid(), controller_identity=self.m.process_identity(os.getpid()), worker=self.m.identity(self.worker)))
        fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda m: None))
        self.api.importlib = types.SimpleNamespace(util=types.SimpleNamespace(spec_from_file_location=lambda *x: fake_spec, module_from_spec=lambda *x: self.m))

    def runmain(self):
        with mock.patch('sys.stdout', new=io.StringIO()): self.api.main()

    def test_real153_registration_positive_and_idempotent(self):
        self.runmain(); receipt = self.b / 'two-candidate-followup-registration-20261105-208.json'; value = json.loads(receipt.read_text())
        self.assertEqual(value['frozen_before'], value['frozen_after']); self.assertEqual(value['experiments_directly_launched'], 0)
        self.assertTrue(any(r['path'] == str(self.old191) for r in value['frozen_before']))
        self.assertTrue(any(r['path'] == str(self.ancestor) for r in value['frozen_before']))
        original = receipt.read_bytes(); self.runmain(); self.assertEqual(receipt.read_bytes(), original)

    def test_guard_job_race_before_register_rejected(self):
        original = self.api.validate_jobs
        def race(m, guard):
            result = original(m, guard); p = self.h / 'native_query207.json'; p.write_bytes(p.read_bytes() + b' '); return result
        self.api.validate_jobs = race
        with self.assertRaises(ValueError): self.runmain()
        self.assertFalse((self.c / 'registrations/native_query207.json').exists())

    def test_race_inside_register_is_not_rebound_to_new_sha(self):
        original = self.m.register
        def race(out, p):
            p.write_bytes(p.read_bytes() + b' '); original(out, p)
        self.m.register = race
        with self.assertRaises(ValueError): self.runmain()
        self.assertTrue((self.c / 'registrations/native_query207.json').is_file())
        self.assertFalse((self.b / 'two-candidate-followup-registration-20261105-208.json').exists())

    def test_ancestor_changes_during_register_rejected(self):
        original = self.m.register
        def race(out, p):
            original(out, p); self.ancestor.write_bytes(self.ancestor.read_bytes() + b' ')
        self.m.register = race
        with self.assertRaises(ValueError): self.runmain()
        self.assertFalse((self.b / 'two-candidate-followup-registration-20261105-208.json').exists())

    def test_original191_changes_during_register_rejected(self):
        original = self.m.register
        def race(out, p):
            original(out, p); self.old191.write_bytes(self.old191.read_bytes() + b' ')
        self.m.register = race
        with self.assertRaises(ValueError): self.runmain()
        self.assertFalse((self.b / 'two-candidate-followup-registration-20261105-208.json').exists())

    def test_duplicate_or_wrong_original191_ancestry_row_rejected(self):
        value = json.loads(self.ancestor.read_text()); value['registrations'][0] = copy.deepcopy(value['registrations'][-1]); write(self.ancestor, value)
        guard = json.loads(self.guard.read_text()); guard['ancestry198'] = self.m.identity(self.ancestor); write(self.guard, guard)
        with self.assertRaises(ValueError): self.runmain()
        self.assertFalse((self.c / 'registrations/native_query207.json').exists())

    def test_controller_must_be_same_live_process(self):
        self.m.process_identity = lambda pid: None
        with self.assertRaises(ValueError): self.runmain()
        self.assertFalse((self.c / 'registrations/native_query207.json').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
