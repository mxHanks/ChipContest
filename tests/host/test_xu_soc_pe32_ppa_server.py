"""Host-only refusal checks; no synthetic record is an EDA/acceptance result."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('xu_pe32_server',ROOT/'tools/ppa/xu_pe32_ppa_server.py')
SERVER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(SERVER)


class XuPe32PpaLaunchRefusalTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.source=self.root/'source';self.source.mkdir()
        self.acceptance=self.root/'acceptance';self.acceptance.mkdir()
        names=['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12',
               'pe32-autogroup-control-real12','pe8-autogroup-control-real12']
        self.state=dict(status='VCS_ACCEPTED_NOT_RETAINED',main_commit=SERVER.MAIN,e203_commit=SERVER.CHILD,
            steps=[dict(name=n,status='PASS') for n in names],
            direct_vcs={kind:dict(status='PASS',backend='vcs') for kind in ['wide','compat']})
        def fixture_git(path,*args):
            if args==('rev-parse','HEAD'):
                return SERVER.MAIN if path==self.source else SERVER.CHILD
            return ''
        self.patch=mock.patch.object(SERVER,'git',side_effect=fixture_git);self.patch.start();self.addCleanup(self.patch.stop)

    def save(self):
        (self.acceptance/'state.json').write_text(json.dumps(self.state))

    def test_running_acceptance_cannot_launch_eda_or_create_output(self):
        self.state['status']='RUNNING';self.save();out=self.root/'new-ppa'
        argv=['xu_pe32_ppa_server.py','--source',str(self.source),'--acceptance',str(self.acceptance),'--out',str(out)]
        with mock.patch('sys.argv',argv),mock.patch.object(SERVER.subprocess,'Popen') as start:
            with self.assertRaisesRegex(ValueError,'complete actual32PE VCS acceptance'):
                SERVER.main()
        start.assert_not_called();self.assertFalse(out.exists())

    def test_missing_default8_control_is_not_a_three_way_acceptance(self):
        self.state['steps'].pop();self.save()
        with self.assertRaisesRegex(ValueError,'two controls required'):
            SERVER.checked_acceptance(self.source,self.acceptance)

    def test_icarus_direct_cannot_substitute_for_required_vcs(self):
        self.state['direct_vcs']['wide']['backend']='iverilog';self.save()
        with self.assertRaisesRegex(ValueError,'mandatory new-wrapper direct VCS'):
            SERVER.checked_acceptance(self.source,self.acceptance)

    def test_wrong_source_commit_cannot_use_an_old_acceptance(self):
        self.save()
        with mock.patch.object(SERVER,'git',return_value='WRONG_COMMIT'):
            with self.assertRaisesRegex(ValueError,'source commit differs'):
                SERVER.checked_acceptance(self.source,self.acceptance)

    def test_foreground_never_overwrites_an_existing_campaign(self):
        out=self.root/'existing';out.mkdir();sentinel=out/'old-result.json';sentinel.write_text('preserve raw bytes\n')
        with mock.patch('sys.argv',['xu_pe32_ppa_server.py','--foreground','--out',str(out)]):
            with self.assertRaisesRegex(ValueError,'output is not fresh'):
                SERVER.main()
        self.assertEqual(sentinel.read_text(),'preserve raw bytes\n');self.assertFalse((out/'state.json').exists())


if __name__=='__main__':unittest.main()
