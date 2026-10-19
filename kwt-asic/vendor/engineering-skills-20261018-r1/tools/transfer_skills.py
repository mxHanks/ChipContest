#!/usr/bin/env python3
"""Verify a portable skill kit and preview/copy selected project skills without overwrite."""
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('Unsafe relative path: ' + name)
    return p


def verify():
    expected = {}
    for line in (ROOT / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        value, name = line.split('  ', 1)
        safe_relative(name)
        if name in expected or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Invalid checksum entry: ' + name)
        p = ROOT / name
        if not p.is_file() or p.is_symlink() or digest(p) != value:
            raise ValueError('Missing/changed file: ' + name)
        expected[name] = value
    members = list(ROOT.rglob('*'))
    if any(p.is_symlink() for p in members):
        raise ValueError('Symlinks are not part of this kit')
    actual = {p.relative_to(ROOT).as_posix() for p in members if p.is_file()}
    if actual != set(expected) | {'SHA256SUMS'}:
        raise ValueError('Unlisted or missing kit members')
    profile_data = json.loads((ROOT / 'metadata/profiles.json').read_text())
    for names in profile_data.values():
        for name in names:
            if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', name):
                raise ValueError('Invalid skill name')
            if 'skills/' + name + '/SKILL.md' not in expected:
                raise ValueError('Profile references a missing skill')
    return {'status': 'PASS', 'files_checked': len(expected), 'profiles': profile_data}


def no_symlink_path(path):
    for item in [path, *path.parents]:
        if item.is_symlink():
            raise ValueError('Refusing symlink destination component: ' + str(item))


def tree_map(root):
    items = list(root.rglob('*'))
    if any(p.is_symlink() for p in items):
        raise ValueError('Symlink in existing skill: ' + str(root))
    return {p.relative_to(root).as_posix(): digest(p) for p in items if p.is_file()}


def install(project, profile, apply):
    raw_project = project.expanduser().absolute()
    no_symlink_path(raw_project)
    project = raw_project.resolve()
    if not project.is_dir():
        raise ValueError('Target project must already be a directory')
    if project == ROOT or ROOT.is_relative_to(project) or project.is_relative_to(ROOT):
        raise ValueError('Choose a project outside the immutable kit directory tree')
    destination = project / '.agents/skills'
    no_symlink_path(destination)
    for directory in [project / '.agents', destination]:
        if directory.exists() and not directory.is_dir():
            raise ValueError('Destination is not a directory: ' + str(directory))
    profiles = json.loads((ROOT / 'metadata/profiles.json').read_text())
    plan = []
    for name in profiles[profile]:
        source = ROOT / 'skills' / name
        target = destination / name
        no_symlink_path(target)
        state = 'COPY'
        if target.exists():
            if not target.is_dir() or tree_map(target) != tree_map(source):
                raise ValueError('Conflict; no skills installed: ' + str(target))
            state = 'UNCHANGED'
        plan.append({'name': name, 'source': str(source), 'target': str(target), 'action': state})
    # All conflicts are checked before any destination mutation.
    if apply:
        destination.mkdir(parents=True, exist_ok=True)
        for item in plan:
            if item['action'] == 'COPY':
                target = Path(item['target'])
                target.mkdir(exist_ok=False)
                for path in sorted(Path(item['source']).rglob('*')):
                    relative = path.relative_to(item['source'])
                    if path.is_dir():
                        (target / relative).mkdir(exist_ok=False)
                    else:
                        with path.open('rb') as source, (target / relative).open('xb') as out:
                            shutil.copyfileobj(source, out)
                if tree_map(target) != tree_map(Path(item['source'])):
                    raise ValueError('Copy verification failed; inspect preserved target: ' + str(target))
    return {'status': 'PASS', 'mode': 'APPLY' if apply else 'DRY_RUN',
            'project': str(project), 'profile': profile, 'plan': plan}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('verify')
    parser = sub.add_parser('install')
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--profile', choices=['general', 'fpga'], default='general')
    parser.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    try:
        result = verify()
        if args.command == 'install':
            result = install(args.project, args.profile, args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
