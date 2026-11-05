#!/usr/bin/env python3
"""Actual199 acceptance and structurally resealed evidence tampering checks."""
import copy
import json
from pathlib import Path
import tarfile
import unittest

import audit204 as a

WORKSPACE = Path(__file__).resolve().parents[2]
ARCHIVE = WORKSPACE/'docs/validation/xu-score-followup199-20261105/followup199.tar.xz'


class ActualEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        a.frozen171.inspect(ARCHIVE, a.SHA199)
        with tarfile.open(str(ARCHIVE), 'r:xz') as t:
            cls.original = {m.name: t.extractfile(m).read() for m in t}
        cls.runtime, cls.manifest = a.read_runtime(WORKSPACE/'build/xu-two-candidate-control198/runtime198.tar.gz')

    def setUp(self):
        self.payload = copy.deepcopy(self.original)

    def alter(self, name, update):
        value = a.load(self.payload[name])
        update(value)
        raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        old_size = len(self.payload[name])
        self.assertLessEqual(len(raw), old_size)
        self.payload[name] = raw + b' '*(old_size-len(raw))

    def reseal(self):
        def update(snapshot):
            for r in snapshot['captures']:
                raw = self.payload[r['archive_path']]
                r['observed_bytes_sha256'] = a.identity(raw)['sha256']
        self.alter('snapshot171.json', update)
        manifest = a.load(self.payload['manifest.json'])
        manifest['files'] = [a.record(raw, name) for name, raw in sorted(self.payload.items()) if name != 'manifest.json']
        self.payload['manifest.json'] = (json.dumps(manifest, sort_keys=True, indent=2)+'\n').encode()

    def reject(self, pattern):
        self.reseal()
        with self.assertRaisesRegex(ValueError, pattern):
            a.audit(self.payload, self.runtime, self.manifest, WORKSPACE)

    def test_actual_199(self):
        result = a.audit(self.payload, self.runtime, self.manifest, WORKSPACE)
        self.assertEqual(result['registration_frozen_input_records_unchanged'], 48)
        self.assertEqual(len(result['current_runtime_sources']), 24)

    def test_signal_is_not_registration_only(self):
        self.alter('two-candidate-followup-registration-20261105-198.json', lambda v: v.update(workers_signalled=1))
        self.reject('signalled/restarted')

    def test_after_mutation(self):
        self.alter('two-candidate-followup-registration-20261105-198.json', lambda v: v['frozen_after'][0].update(sha256='0'*64))
        self.reject('48 server frozen-input')

    def test_ancestor_hash_not_body_proof(self):
        self.alter('two-candidate-followup-registration-20261105-198.json', lambda v: v['scope163'].update(sha256='0'*64))
        self.reject('ancestor receipt')

    def test_installer_native_launch_forbidden(self):
        self.alter('followup198-install.json', lambda v: v.update(new_native_runs=1))
        self.reject('runtime installer receipt')

    def test_installed_manifest_mismatch(self):
        self.alter('followup198-install.json', lambda v: v['manifest']['files'][0].update(sha256='0'*64))
        self.reject('installed runtime manifest')

    def test_controller_pid_reuse(self):
        self.alter('snapshot171.json', lambda v: v['live_process_observations'][0]['actual'].update(start_ticks=118631999))
        self.reject('same live process')

    def test_zombie_is_not_live(self):
        self.alter('snapshot171.json', lambda v: v['live_process_observations'][0]['actual'].update(process_state='Z'))
        self.reject('same live process')

    def test_waiting_not_completed(self):
        self.alter(a.Q+'/state.json', lambda v: v['jobs']['s2c_common_full12_190'].update(status='SUCCESS'))
        self.reject('historical queued/waiting')

    def test_snapshot_is_not_terminal_freeze(self):
        self.alter('snapshot171.json', lambda v: v.update(all_copies_are_observations_not_terminal_freezes=False))
        self.reject('live snapshot semantics')

    def test_raw_source_change_caught(self):
        self.payload['desktop/xu-two-candidate-control198/register198.py'] += b'#x'
        with self.assertRaisesRegex(ValueError, 'extracted payload differs'):
            a.audit(self.payload, self.runtime, self.manifest, WORKSPACE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
