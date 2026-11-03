"""Fail before any process/output on incomplete or non-VCS synthetic state headers."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_bank128_server', ROOT/'tools/ppa/xu_bank128_ppa_server.py')
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class XuBank128PpaLaunchRefusalTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root/'source'; self.source.mkdir()
        self.acceptance = self.root/'acceptance'; self.acceptance.mkdir()
        names = ['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12',
                 'old32-wide-real12','bank128-oldauto-real12']
        self.state = dict(status='VCS_ACCEPTED_NOT_RETAINED', main_commit=SERVER.MAIN,e203_commit=SERVER.CHILD,
                          source=str(self.source), steps=[dict(name=name,status='PASS') for name in names],
                          direct_vcs={kind:{} for kind in ['bank-generated','bank-designated-macro','wide','compat','wide-designated-macro','compat-designated-macro']})

        def fixture_git(path,*args):
            if args == ('rev-parse','HEAD'):
                return SERVER.MAIN if path == self.source else SERVER.CHILD
            return ''
        patch = mock.patch.object(SERVER,'git',side_effect=fixture_git)
        patch.start(); self.addCleanup(patch.stop)

    def save(self):
        (self.acceptance/'state.json').write_text(json.dumps(self.state))

    def arguments(self, foreground=False):
        return ['xu_bank128_ppa_server.py','--source',str(self.source),'--acceptance',str(self.acceptance),
                '--out',str(self.root/'new-ppa')] + (['--foreground'] if foreground else [])

    def test_running_state_refuses_foreground_and_detached_launch_before_output(self):
        self.state['status'] = 'RUNNING'; self.save()
        for foreground in [False,True]:
            with self.subTest(foreground=foreground), mock.patch('sys.argv',self.arguments(foreground)), \
                    mock.patch.object(SERVER.subprocess,'Popen') as spawn, mock.patch.object(SERVER.subprocess,'run') as execute:
                with self.assertRaisesRegex(ValueError,'complete actual compact-W32 VCS acceptance'):
                    SERVER.main()
                spawn.assert_not_called(); execute.assert_not_called()
                self.assertFalse((self.root/'new-ppa').exists())

    def test_each_required_full12_control_must_be_terminal_pass(self):
        for index in range(8,10):
            original = self.state['steps'][index]['status']
            self.state['steps'][index]['status'] = 'RUNNING'; self.save()
            with self.subTest(index=index), self.assertRaisesRegex(ValueError,'two full12 controls required'):
                SERVER.checked_acceptance(self.source,self.acceptance)
            self.state['steps'][index]['status'] = original
        self.state['steps'].pop(); self.save()
        with self.assertRaisesRegex(ValueError,'two full12 controls required'):
            SERVER.checked_acceptance(self.source,self.acceptance)

    def test_every_generated_and_designated_direct_run_is_mandatory(self):
        for kind in list(self.state['direct_vcs']):
            value = self.state['direct_vcs'].pop(kind);self.save()
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'six mandatory actual VCS'):
                SERVER.checked_acceptance(self.source,self.acceptance)
            self.state['direct_vcs'][kind]=value

    def test_wrong_source_pin_and_origin_cannot_use_old_acceptance(self):
        self.save()
        with mock.patch.object(SERVER,'git',return_value='WRONG_COMMIT'), self.assertRaisesRegex(ValueError,'source commit differs'):
            SERVER.checked_acceptance(self.source,self.acceptance)
        self.state['source'] = str(self.root/'another-source'); self.save()
        with self.assertRaisesRegex(ValueError,'source origin differs'):
            SERVER.checked_acceptance(self.source,self.acceptance)

    def test_all_green_headers_still_require_full_original_main_object_guard(self):
        self.save()
        producer = mock.Mock()
        producer.source_profile_identity.side_effect = ValueError('actual hidden main bytes differ')
        with mock.patch.object(SERVER.importlib.util,'module_from_spec',return_value=producer), \
                mock.patch.object(SERVER.importlib.util,'spec_from_file_location') as spec, \
                self.assertRaisesRegex(ValueError,'actual hidden main bytes differ'):
            SERVER.checked_acceptance(self.source,self.acceptance)
        producer.source_profile_identity.assert_called_once_with(self.source,'s3-pe32-bank128')

    def test_terminal_status_without_raw_direct_logs_cannot_launch_eda(self):
        self.save()
        producer = mock.Mock()
        producer.source_profile_identity.return_value = dict(scope='HOST FIXTURE ONLY')
        with mock.patch.object(SERVER.importlib.util,'module_from_spec',return_value=producer), \
                mock.patch.object(SERVER.importlib.util,'spec_from_file_location'), \
                mock.patch.object(SERVER.subprocess,'Popen') as spawn, mock.patch('sys.argv',self.arguments()):
            with self.assertRaises((ValueError,KeyError,FileNotFoundError)):
                SERVER.main()
            spawn.assert_not_called(); self.assertFalse((self.root/'new-ppa').exists())

    def test_foreground_never_overwrites_an_existing_campaign(self):
        out = self.root/'new-ppa'; out.mkdir()
        sentinel = out/'old-result.json'; sentinel.write_text('preserve original evidence\n')
        with mock.patch.object(SERVER,'checked_acceptance',return_value={}), mock.patch('sys.argv',self.arguments(True)):
            with self.assertRaisesRegex(ValueError,'output is not fresh'):
                SERVER.main()
        self.assertEqual(sentinel.read_text(),'preserve original evidence\n')
        self.assertFalse((out/'state.json').exists())


class XuBank128OfficialModelRefusalTest(unittest.TestCase):
    def test_exact_official_pin_is_required_even_if_record_is_self_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary);model=directory/'official.v';model.write_bytes(b'HOST MODEL PIN FIXTURE ONLY\n')
            digest = SERVER.sha(model);size=model.stat().st_size
            record = dict(path=str(model),sha256=digest,bytes=size)
            with mock.patch.object(SERVER,'DESIGNATED_MODEL_PATH',model), \
                    mock.patch.object(SERVER,'DESIGNATED_MODEL_SHA',digest), \
                    mock.patch.object(SERVER,'DESIGNATED_MODEL_BYTES',size):
                self.assertEqual(SERVER.checked_designated_model(record,SERVER.sha),model)
                other=directory/'other.v';other.write_bytes(model.read_bytes())
                for mutation in [dict(record,path=str(other)),dict(record,sha256='0'*64),dict(record,bytes=size+1)]:
                    with self.subTest(record=mutation),self.assertRaisesRegex(ValueError,'official128 model pin differs'):
                        SERVER.checked_designated_model(mutation,SERVER.sha)
                model.write_bytes(b'CHANGED ACTUAL FILE SAME LENGTH'[:size].ljust(size,b' '))
                with self.assertRaisesRegex(ValueError,'actual128 model changed'):
                    SERVER.checked_designated_model(record,SERVER.sha)
                model.unlink();model.symlink_to(other)
                with self.assertRaisesRegex(ValueError,'actual128 model changed'):
                    SERVER.checked_designated_model(record,SERVER.sha)
