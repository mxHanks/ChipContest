#!/usr/bin/env python3
"""Read-only bundle integrity and declared source-set checks. No HDL compiler."""
import ast
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def member(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('unsafe member: ' + name)
    result = ROOT.joinpath(*p.parts)
    if not result.is_relative_to(ROOT):
        raise ValueError('member outside root')
    return result


def verify():
    expected = {}
    for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', digest) or name in expected:
            raise ValueError('invalid/duplicate checksum: ' + name)
        expected[name] = digest
        path = member(name)
        if path.is_symlink() or not path.is_file() or sha(path) != digest:
            raise ValueError('missing/changed member: ' + name)
    all_members = list(ROOT.rglob('*'))
    if any(p.is_symlink() for p in all_members):
        raise ValueError('symlink in bundle')
    actual = {p.relative_to(ROOT).as_posix() for p in all_members if p.is_file()}
    if actual != set(expected) | {'SHA256SUMS'}:
        raise ValueError('unlisted files: ' + repr(sorted(actual - set(expected) - {'SHA256SUMS'})))
    origins = json.loads((ROOT / 'metadata/source_manifest.json').read_text())
    seen = set()
    for entry in origins['files']:
        name = entry['package_path']
        if name in seen or expected.get(name) != entry['sha256']:
            raise ValueError('invalid origin record: ' + name)
        if member(name).stat().st_size != entry['size']:
            raise ValueError('source size mismatch: ' + name)
        seen.add(name)
    dependencies = json.loads((ROOT / 'metadata/dependencies.json').read_text())
    total_modules = 0
    for group in dependencies['groups']:
        lines = member(group['filelist']).read_text().splitlines()
        if lines != group['sources']:
            raise ValueError('filelist mismatch: ' + group['name'])
        modules = {}
        packages = set()
        if len(set(lines)) != len(lines):
            raise ValueError('duplicate source path')
        for source in lines:
            if source not in expected:
                raise ValueError('untracked dependency: ' + source)
            text = member(source).read_text()
            text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
            for module in re.findall(r'\bmodule\s+(\w+)', text):
                if module in modules:
                    raise ValueError('duplicate module: ' + module)
                modules[module] = source
            packages.update(re.findall(r'\bpackage\s+(\w+)\s*;', text))
            if re.search(r'`include\s+"', text):
                raise ValueError('unreviewed include: ' + source)
        needed = set(group['required_modules']) | {group['top']}
        if not needed.issubset(modules):
            raise ValueError('missing declared modules: ' + repr(sorted(needed - set(modules))))
        if not set(group.get('required_packages', [])).issubset(packages):
            raise ValueError('missing declared package: ' + group['name'])
        total_modules += len(modules)
    python_files = list(ROOT.rglob('*.py'))
    for path in python_files:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    return {'status': 'PASS', 'scope': 'byte integrity, declared dependencies and Python syntax only',
            'files_checked': len(expected), 'source_files': len(seen),
            'file_sets': len(dependencies['groups']), 'module_definitions_across_sets': total_modules,
            'python_syntax_files': len(python_files), 'hdl_elaboration': 'NOT_RUN',
            'kwt_acceptance': 'NOT_RUN'}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
