#!/usr/bin/env python3
"""Explicit source/tool contexts for the frozen S2c activity candidate.

No baseline source/guard is changed. Private module instances compose the
frozen generator with the separately hash-checked candidate TB and contracts.
Python 3.6+, standard library only.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

TOOL_ROOT = Path(__file__).resolve().parents[2]
PROFILE = 's2c-autogroup'
MAIN_COMMIT = 'd276b55ffecbe8d620f9a361bf5d0859299ba7b5'
SCHEDULE = 'bias-hw-autogroup-window'
FROZEN_TOOLS = {
    'tools/ppa/xu_soc_task_activity.py': '84bd2ac43621fcee46b3e8c336d0ccb0142ec0d1180fc7926ee2af5cef676511',
    'tools/ppa/xu_soc_ppa_verify.py': 'feeb24d171bc251e7020b77ed1b29d6e2a30da4d9037269f4e7c06b150252967',
    'tools/ppa/xu_task_clear_protocol.py': '467e51abbaefa1ef40e3c2d5cfbc18376be351886b212f7667f0a44934488ee8',
    'tools/ppa/xu_sram_activity_alias.py': '5e36356860aae2e6c1993a9dafbce884534c657eec7b1bb0be1b7420a0153c7c',
    'tools/scripts/e203_soc.py': '573d0d1830069cf99ea73bcf2553b175bc77f6f5ecbe7595036453a193970e2b',
    'tools/scripts/xu_firmware_contract.py': 'a0602663237aec93e52f1ea38ff7982ceb21f603f334899cbc48fd6a51c30b96',
    'tools/scripts/xu_soc_activity.py': '8a10bde83fb1a622b01f6b9a014e9b65b286f1f76a3a214c62f6c6d6a784c942',
    'tools/scripts/xu_soc_ppa.py': 'bc4070bdbd7ac6ae48f7ead1599a3a1a143b9872a7c4a9ef76aad3b677b25040',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(path):
    path = Path(path).absolute()
    require(path.is_file() and not path.is_symlink(), 'regular non-symlink file required: ' + str(path))
    return dict(path=str(path), sha256=sha(path))


def git(root, *arguments):
    return subprocess.check_output(['git', '--no-replace-objects'] + list(arguments),
                                   cwd=str(root), stdin=subprocess.DEVNULL).decode().strip()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def source_identity(root):
    """Verify every tracked main blob, gitlink, mode and complete child tree.

    Independent blob hashing also rejects assume-unchanged/skip-worktree edits.
    Nonignored untracked files in the source root are rejected. The approved
    child profile separately rejects ignored/untracked live RTL sources.
    """
    root = Path(root).resolve()
    require(Path(git(root, 'rev-parse', '--show-toplevel')).resolve() == root,
            'candidate source must be its own repository root')
    require(git(root, 'rev-parse', 'HEAD') == MAIN_COMMIT, 'candidate main commit differs from frozen S2c')
    require(not git(root, 'status', '--porcelain', '--untracked-files=all'), 'candidate main/child is dirty or untracked')
    raw = subprocess.check_output(['git', '--no-replace-objects', 'ls-tree', '-rz', 'HEAD'], cwd=str(root))
    records = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        meta, raw_name = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode('ascii').split()
        name = os.fsdecode(raw_name)
        path = root / name
        if mode == '160000':
            require(name == 'third-party/e203_hbirdv2' and git(path, 'rev-parse', 'HEAD') == oid,
                    'unexpected/uninitialized/mismatched candidate gitlink: ' + name)
            records[name] = dict(mode=mode, commit=oid)
            continue
        require(kind == 'blob', 'unsupported main tree entry: ' + name)
        if mode == '120000':
            require(path.is_symlink(), 'main tree symlink differs: ' + name)
            content = os.fsencode(os.readlink(str(path)))
        else:
            require(mode in ('100644', '100755') and path.is_file() and not path.is_symlink(),
                    'main tree file missing/type differs: ' + name)
            require(bool(path.stat().st_mode & 0o111) == (mode == '100755'), 'main file mode differs: ' + name)
            content = path.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content).hexdigest()
        require(actual == oid, 'main worktree bytes differ from frozen S2c: ' + name)
        records[name] = dict(mode=mode, sha256=hashlib.sha256(content).hexdigest())
    # This independent approved-profile guard checks child commit, full fixed
    # platform delta, every tracked byte/mode and untracked/ignored live RTL.
    ppa = load('xu_candidate_profile_guard', TOOL_ROOT / 'tools/scripts/xu_soc_ppa.py')
    child = ppa.source_profile_identity(root, PROFILE)
    return dict(root=str(root), main_commit=MAIN_COMMIT, main_tree=git(root, 'rev-parse', 'HEAD^{tree}'),
                main_worktree_manifest_sha256=canonical(records), main_tracked_entries=len(records),
                source_profile=child)


def tool_identity():
    records = []
    for name, expected in sorted(FROZEN_TOOLS.items()):
        record = identity(TOOL_ROOT / name)
        require(record['sha256'] == expected, 'frozen baseline/common tool bytes differ: ' + name)
        records.append(record)
    require(Path(git(TOOL_ROOT, 'rev-parse', '--show-toplevel')).resolve() == TOOL_ROOT, 'tool root is not repository root')
    require(not git(TOOL_ROOT, 'status', '--porcelain', '--untracked-files=all'), 'tool checkout must be clean and committed')
    return dict(root=str(TOOL_ROOT), main_commit=git(TOOL_ROOT, 'rev-parse', 'HEAD'),
                main_tree=git(TOOL_ROOT, 'rev-parse', 'HEAD^{tree}'), frozen_common_tools=records,
                baseline_tools_policy='unchanged byte-for-byte; baseline guards remain strict')


class Context:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.tool = tool_identity()
        self.source = source_identity(self.root)
        # Explicitly select the frozen candidate contracts. Temporary import
        # bindings are restored; shared baseline module objects are never edited.
        self.contract = load('xu_s2c_frozen_contract', self.root / 'tools/scripts/xu_firmware_contract.py')
        missing = object()
        saved = {name: sys.modules.get(name, missing) for name in ('xu_firmware_contract', 'e203_soc')}
        try:
            sys.modules['xu_firmware_contract'] = self.contract
            self.soc = load('xu_s2c_frozen_soc', self.root / 'tools/scripts/e203_soc.py')
            sys.modules['e203_soc'] = self.soc
            self.base = load('xu_candidate_private_generator', TOOL_ROOT / 'tools/ppa/xu_soc_ppa_verify.py')
        finally:
            for name, value in saved.items():
                if value is missing:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.base.TB = self.root / 'tests/e203/tb_accel_soc.sv'
        self.base.RTL = self.root / 'third-party/e203_hbirdv2/rtl/e203'
        self.base.ROOT = self.root
        self.clear = load('xu_candidate_frozen_clear', TOOL_ROOT / 'tools/ppa/xu_task_clear_protocol.py')
        self.activity = load('xu_candidate_frozen_saif', TOOL_ROOT / 'tools/scripts/xu_soc_activity.py')
        self.configuration = self.contract.configuration(SCHEDULE, '-O2', 'both-unroll-no-masks')

    def recheck(self):
        require(self.tool == tool_identity(), 'tool identity changed during collection')
        require(self.source == source_identity(self.root), 'candidate identity changed during collection')
