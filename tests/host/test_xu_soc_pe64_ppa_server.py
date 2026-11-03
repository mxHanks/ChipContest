"""Fail before any process/output on incomplete or non-VCS synthetic state headers."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_pe64_server', ROOT/'tools/ppa/xu_pe64_ppa_server.py')
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


class XuPe64PpaLaunchRefusalTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root/'source'; self.source.mkdir()
        self.acceptance = self.root/'acceptance'; self.acceptance.mkdir()
        names = ['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12',
                 'same64-schedule32-control-real12','same64-schedule8-control-real12',
                 'physical32-wide32-control-real12','physical8-auto8-control-real12']
        self.state = dict(status='VCS_ACCEPTED_NOT_RETAINED', main_commit=SERVER.MAIN,e203_commit=SERVER.CHILD,
                          source=str(self.source), steps=[dict(name=name,status='PASS') for name in names],
                          direct_vcs={kind:dict(status='PASS',backend='vcs') for kind in ['wide64','compat32','compat8','boundary']})

        def fixture_git(path,*args):
            if args == ('rev-parse','HEAD'):
                return SERVER.MAIN if path == self.source else SERVER.CHILD
            return ''
        patch = mock.patch.object(SERVER,'git',side_effect=fixture_git)
        patch.start(); self.addCleanup(patch.stop)

    def save(self):
        (self.acceptance/'state.json').write_text(json.dumps(self.state))

    def arguments(self, foreground=False):
        return ['xu_pe64_ppa_server.py','--source',str(self.source),'--acceptance',str(self.acceptance),
                '--out',str(self.root/'new-ppa')] + (['--foreground'] if foreground else [])

    def test_running_state_refuses_foreground_and_detached_launch_before_output(self):
        self.state['status'] = 'RUNNING'; self.save()
        for foreground in [False,True]:
            with self.subTest(foreground=foreground), mock.patch('sys.argv',self.arguments(foreground)), \
                    mock.patch.object(SERVER.subprocess,'Popen') as spawn, mock.patch.object(SERVER.subprocess,'run') as execute:
                with self.assertRaisesRegex(ValueError,'complete actual64PE VCS acceptance'):
                    SERVER.main()
                spawn.assert_not_called(); execute.assert_not_called()
                self.assertFalse((self.root/'new-ppa').exists())

    def test_each_required_full12_control_must_be_terminal_pass(self):
        for index in range(8,12):
            original = self.state['steps'][index]['status']
            self.state['steps'][index]['status'] = 'RUNNING'; self.save()
            with self.subTest(index=index), self.assertRaisesRegex(ValueError,'four full12 controls required'):
                SERVER.checked_acceptance(self.source,self.acceptance)
            self.state['steps'][index]['status'] = original
        self.state['steps'].pop(); self.save()
        with self.assertRaisesRegex(ValueError,'four full12 controls required'):
            SERVER.checked_acceptance(self.source,self.acceptance)

    def test_every_direct_mode_and_boundary_requires_actual_vcs(self):
        for kind in list(self.state['direct_vcs']):
            self.state['direct_vcs'][kind]['backend'] = 'iverilog'; self.save()
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError,'three mandatory physical64 direct VCS'):
                SERVER.checked_acceptance(self.source,self.acceptance)
            self.state['direct_vcs'][kind]['backend'] = 'vcs'
        self.state['direct_vcs'].pop('boundary'); self.save()
        with self.assertRaisesRegex(ValueError,'three mandatory physical64 direct VCS'):
            SERVER.checked_acceptance(self.source,self.acceptance)

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
        producer.source_profile_identity.assert_called_once_with(self.source,'s3-pe64')

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
