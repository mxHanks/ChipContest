"""Exercise actual Git/worktree mutations, independently of Git status/index hints."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('xu_pe32_main_source_guard', ROOT/'tools/scripts/xu_soc_ppa.py')
PPA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PPA)


class XuPe32MainSourceGuardTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)/'source'
        self.root.mkdir()
        self.initialize(self.root)
        self.child = self.root/PPA.SUB
        self.child.mkdir(parents=True)
        self.initialize(self.child)
        fixed = self.child/'rtl/e203/core/fixed.v'
        fixed.parent.mkdir(parents=True)
        fixed.write_text('module fixed; endmodule\n')
        self.git(self.child, 'add', '.')
        self.git(self.child, 'commit', '-qm', 'fixed child fixture')
        self.child_commit = self.git(self.child, 'rev-parse', 'HEAD')
        self.tb = self.root/'tests/e203/tb_accel_soc.sv'
        self.tb.parent.mkdir(parents=True)
        self.tb.write_text('module tb; always #2 clk=~clk; endmodule\n')
        self.runner = self.root/'tools/scripts/runner.py'
        self.runner.parent.mkdir(parents=True)
        self.runner.write_text('print("frozen runner")\n')
        self.runner.chmod(0o755)
        source = self.root/'src/main/scala/core.scala'
        source.parent.mkdir(parents=True)
        source.write_text('object Core\n')
        (source.parent/'link.scala').symlink_to('core.scala')
        (self.root/'project.scala').write_text('// frozen project\n')
        (self.root/'.gitignore').write_text('/build/\n__pycache__/\n/tests/e203/ignored*\n')
        self.git(self.root, 'add', '.')
        self.git(self.root, 'commit', '-qm', 'frozen main fixture')
        self.main_commit = self.git(self.root, 'rev-parse', 'HEAD')
        profiles = {'s3-pe32': dict(commit=self.child_commit, changed_files=[])}
        for patch in [mock.patch.object(PPA, 'FROZEN_E203', self.child_commit),
                      mock.patch.object(PPA, 'PE32_MAIN_COMMIT', self.main_commit),
                      mock.patch.object(PPA, 'SOURCE_PROFILES', profiles)]:
            patch.start()
            self.addCleanup(patch.stop)

    def git(self, path, *args):
        return subprocess.check_output(['git']+list(args), cwd=str(path), stderr=subprocess.STDOUT).decode().strip()

    def initialize(self, path):
        self.git(path, 'init', '-q')
        self.git(path, 'config', 'user.name', 'xu source guard fixture')
        self.git(path, 'config', 'user.email', 'xu-source-guard@example.invalid')
        self.git(path, 'config', 'commit.gpgsign', 'false')

    def check(self):
        return PPA.source_profile_identity(self.root, 's3-pe32')

    def test_clean_complete_main_and_child_trees_have_hash_bound_identities(self):
        identity = self.check()
        self.assertEqual(identity['e203_commit'], self.child_commit)
        freeze = identity['main_source_freeze']
        self.assertEqual(freeze['main_commit'], self.main_commit)
        self.assertEqual(freeze['tracked_main_entries'], 7)
        self.assertEqual(freeze['approved_main_tree'], self.git(self.root, 'rev-parse', 'HEAD^{tree}'))
        self.assertRegex(freeze['actual_main_tree_manifest_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(self.git(self.root, 'status', '--porcelain'), '')

    def test_hidden_main_tb_and_runner_changes_fail_independently_of_index_flags(self):
        for flag, path in [('assume-unchanged', self.tb), ('skip-worktree', self.runner)]:
            with self.subTest(flag=flag):
                relative = path.relative_to(self.root).as_posix()
                original = path.read_bytes()
                self.git(self.root, 'update-index', '--'+flag, relative)
                path.write_bytes(original+b'// hidden mutation\n')
                self.assertEqual(self.git(self.root, 'status', '--porcelain'), '')
                with self.assertRaisesRegex(ValueError, 'main tree worktree bytes differ'):
                    self.check()
                path.write_bytes(original)
                self.git(self.root, 'update-index', '--no-'+flag, relative)
        self.check()

    def test_staged_different_main_bytes_are_not_accepted_by_the_frozen_head(self):
        self.tb.write_text('module replaced; endmodule\n')
        self.git(self.root, 'add', str(self.tb.relative_to(self.root)))
        with self.assertRaisesRegex(ValueError, 'main tree worktree bytes differ'):
            self.check()

    def test_main_mode_and_symlink_representation_are_frozen(self):
        self.runner.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'main tree file mode changed'):
            self.check()
        self.runner.chmod(0o755)
        link = self.root/'src/main/scala/link.scala'
        link.unlink()
        link.write_bytes((link.parent/'core.scala').read_bytes())
        with self.assertRaisesRegex(ValueError, 'main tree symlink changed'):
            self.check()

    def test_symlink_target_and_parent_redirection_are_checked(self):
        link = self.root/'src/main/scala/link.scala'
        link.unlink()
        link.symlink_to('other.scala')
        with self.assertRaisesRegex(ValueError, 'main tree worktree bytes differ'):
            self.check()
        link.unlink()
        link.symlink_to('core.scala')
        original = self.root/'src/main'
        external = self.root.parent/'external-main'
        shutil.move(str(original), str(external))
        original.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'main source parent is a symlink'):
            self.check()

    def test_actual_child_gitlink_and_main_pin_are_checked(self):
        (self.child/'README').write_text('another child commit\n')
        self.git(self.child, 'add', '.')
        self.git(self.child, 'commit', '-qm', 'wrong child fixture')
        with self.assertRaisesRegex(ValueError, 'child commit differs'):
            self.check()
        self.git(self.child, 'checkout', '-q', '--detach', self.child_commit)
        (self.root/'README').write_text('another main commit\n')
        self.git(self.root, 'add', '.')
        self.git(self.root, 'commit', '-qm', 'wrong main fixture')
        with self.assertRaisesRegex(ValueError, 'main commit differs'):
            self.check()

    def test_main_gitlink_object_must_be_exact_approved_child(self):
        # Construct a main commit whose gitlink differs while retaining the
        # original child checkout, then pin this fixture commit as approved.
        wrong_oid = 'f'*40
        self.git(self.root, 'update-index', '--cacheinfo', '160000,'+wrong_oid+','+PPA.SUB)
        self.git(self.root, 'commit', '-qm', 'wrong gitlink object fixture')
        with mock.patch.object(PPA, 'PE32_MAIN_COMMIT', self.git(self.root, 'rev-parse', 'HEAD')):
            with self.assertRaisesRegex(ValueError, 'approved child gitlink differs'):
                self.check()

    def test_replace_object_cannot_substitute_main_bytes_under_the_same_pin(self):
        self.tb.write_text('module substitute; endmodule\n')
        self.git(self.root, 'add', '.')
        self.git(self.root, 'commit', '-qm', 'replacement main fixture')
        replacement = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'replace', self.main_commit, replacement)
        self.git(self.root, 'checkout', '-q', '--detach', self.main_commit)
        self.assertIn('substitute', self.tb.read_text())
        self.assertEqual(self.git(self.root, 'status', '--porcelain'), '')
        with self.assertRaisesRegex(ValueError, 'main tree worktree bytes differ'):
            self.check()

    def test_untracked_and_ignored_active_sources_fail_but_build_output_is_allowed(self):
        for relative in ['tests/e203/injected.sv', 'tests/e203/ignored_probe.py',
                         'tools/runner_extra.py', 'src/hidden.scala', 'model/untracked-vector.txt',
                         'extra.scala', 'tools/__pycache__/hidden.py']:
            with self.subTest(relative=relative):
                path = self.root/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('untracked active source\n')
                with self.assertRaisesRegex(ValueError, 'main untracked active source'):
                    self.check()
                path.unlink()
        output = self.root/'build/generated/output.sv'
        output.parent.mkdir(parents=True)
        output.write_text('build output outside discovered source namespaces\n')
        cache = self.root/'tools/__pycache__/runner.cpython-311.pyc'
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(b'bytecode cache')
        self.check()

    def test_extra_gitlink_is_rejected_even_if_main_commit_is_locally_re_pinned(self):
        self.git(self.root, 'update-index', '--add', '--cacheinfo', '160000,'+self.child_commit+',extra-child')
        self.git(self.root, 'commit', '-qm', 'extra gitlink fixture')
        with mock.patch.object(PPA, 'PE32_MAIN_COMMIT', self.git(self.root, 'rev-parse', 'HEAD')):
            with self.assertRaisesRegex(ValueError, 'main gitlink set differs'):
                self.check()


if __name__ == '__main__':
    unittest.main()
