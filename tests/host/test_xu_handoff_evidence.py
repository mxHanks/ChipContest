"""Portable handoff: real archived positive and focused corruption checks."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_verify_handoff', str(REPO / 'tools/scripts/xu_verify_handoff.py'))
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)
EVIDENCE = REPO / 'docs/validation/xu-score-two-candidate-final-20261105'


class HandoffEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Read actual immutable task records, rather than fabricating the campaign.
        cls.records = {}
        folder = v.CONFIG['s2e']['full']
        with tarfile.open(str(EVIDENCE / 'original171.tar.xz'), 'r:xz') as archive:
            for name in ['prepared', 'execution', 'summary', 'result']:
                cls.records[folder + '/' + name + '.json'] = json.loads(archive.extractfile(folder + '/' + name + '.json').read().decode('utf-8'))
            cls.power = archive.extractfile(folder + '/task_00/power.rpt').read().decode('utf-8')

    def test_actual_portable_packet_and_native_join(self):
        result = v.verify(EVIDENCE, REPO / 'docs/handoff-evidence')
        self.assertEqual(result['qualification'], 'NOT_QUALIFIED')
        self.assertEqual(result['comparison']['s2e_elapsed_cycles'], 10420116)
        self.assertEqual(result['comparison']['s2c_elapsed_cycles'], 11887872)
        self.assertEqual(result['comparison']['s2e_diagnostic_energy_j'], '0.0023659452273331971')
        self.assertEqual(result['comparison']['s2c_diagnostic_energy_j'], '0.0026384471466669330')
        self.assertTrue(result['all_twelve_actual_clock_contracts_match'])
        self.assertEqual(result['candidates']['s2e']['full12']['server_hash_only_reports'], 72)

    def test_missing_layer_cannot_be_complete(self):
        records = copy.deepcopy(self.records)
        records[v.CONFIG['s2e']['full'] + '/execution.json']['tasks'].pop()
        class Records:
            def json(self, name):
                return records[name]
            def check(self, name, receipt=None):
                return False
        with self.assertRaisesRegex(ValueError, 'layer IDs'):
            v.campaign(Records(), 's2e', list(range(12)))

    def test_native_power_unit_cannot_be_relabelled(self):
        self.assertEqual(v.power_values(self.power)['total_power_w'], '0.0341')
        wrong = self.power.replace('Power Units = 1 W', 'Power Units = 1 mW')
        self.assertNotEqual(wrong, self.power)
        with self.assertRaisesRegex(ValueError, 'watts'):
            v.power_values(wrong)

    def test_capture_map_cannot_be_used_as_measurement_target(self):
        prepared = copy.deepcopy(self.records[v.CONFIG['s2e']['full'] + '/prepared.json'])
        prepared['netlist']['sha256'] = v.CAPTURE_E
        with self.assertRaisesRegex(ValueError, 'mapped target'):
            v.context(prepared, 's2e')

    def test_wrong_own_map_area_pair_fails(self):
        prepared = copy.deepcopy(self.records[v.CONFIG['s2e']['full'] + '/prepared.json'])
        prepared['target_mapped_context']['area']['accelerator_mm2'] = v.CONFIG['s2c']['area']
        with self.assertRaisesRegex(ValueError, 'area binding'):
            v.context(prepared, 's2e')

    def test_archive_member_hash_and_unsafe_types(self):
        snapshot = json.dumps(dict(schema='xu-two-candidate-snapshot171-v1', qualification='NOT_QUALIFIED', captures=[], omitted_originals=[])).encode('utf-8')
        row = dict(path='snapshot171.json', bytes=len(snapshot), sha256=hashlib.sha256(snapshot).hexdigest())
        manifest = json.dumps(dict(schema='xu-two-candidate-export171-v1', qualification='NOT_QUALIFIED',
                                   files=[row], payload_files=1, payload_bytes=len(snapshot))).encode('utf-8')
        def write_packet(path, body, link=False):
            with tarfile.open(str(path), 'w:xz') as archive:
                for name, value in [('manifest.json', manifest), ('snapshot171.json', body)]:
                    info = tarfile.TarInfo(name); info.size = len(value)
                    if link and name == 'snapshot171.json':
                        info.type = tarfile.SYMTYPE; info.linkname = '/etc/passwd'; info.size = 0
                        archive.addfile(info)
                    else:
                        archive.addfile(info, io.BytesIO(value))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'packet.tar.xz'
            write_packet(path, snapshot)
            self.assertEqual(v.Packet(path).payload_files, 1)
            write_packet(path, snapshot.replace(b'NOT_QUALIFIED', b'YES_QUALIFIED'))
            with self.assertRaisesRegex(ValueError, 'length/SHA'):
                v.Packet(path)
            write_packet(path, snapshot, link=True)
            with self.assertRaisesRegex(ValueError, 'regular nonsparse'):
                v.Packet(path)

    def test_duplicate_json_keys_and_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
            v.unique_json(b'{"qualification":"NOT_QUALIFIED","qualification":"QUALIFIED"}')
        for name in ['../outside', '/absolute', 'a/../outside', 'a//b', 'a\\b']:
            with self.assertRaises(ValueError):
                v.safe_name(name)


if __name__ == '__main__':
    unittest.main()
