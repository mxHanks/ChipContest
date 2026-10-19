#!/usr/bin/env python3
"""Durable local task state, source manifests, checkpoints and portable releases."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'harness/tasks.json'
STATUSES = {'TODO', 'IN_PROGRESS', 'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'}
TOP_FILES = {'AGENTS.md', 'README.md', 'PROGRESS.md', 'DECISION.md', 'Makefile', '.gitignore',
             'FPT_KWT1_UNDERGRAD_REUSE_20261014_r1.zip', '赛题要求.pdf', 'data/README.md',
             'reports/PPA_PRELIMINARY.md', 'tech/official_sram/README.md'}
TREES = ('configs', 'docs', 'env', 'harness', 'model', 'src', 'sim', 'soc',
         'constraints', 'scripts', 'tests', 'vendor')
EXCLUDED = {'__pycache__', '.git', '.venv', '.tools', 'platform', 'lib', 'private'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sources():
    files = [ROOT / p for p in sorted(TOP_FILES) if (ROOT / p).is_file()]
    for tree in TREES:
        for p in sorted((ROOT / tree).rglob('*')):
            rel = p.relative_to(ROOT)
            if p.is_file() and not p.is_symlink() and not any(x in EXCLUDED for x in rel.parts):
                if p.suffix not in {'.pyc', '.vcd', '.fst', '.saif'}:
                    files.append(p)
    return sorted(set(files))


def manifest():
    return {str(p.relative_to(ROOT)): {'sha256': digest(p), 'bytes': p.stat().st_size}
            for p in sources()}


def read_state():
    return json.loads(STATE.read_text())


def validate():
    state = read_state()
    tasks = state['tasks']
    ids = [t['id'] for t in tasks]
    errors = []
    if len(set(ids)) != len(ids):
        errors.append('duplicate task ids')
    indexed = {t['id']: t for t in tasks}
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            errors.append('dependency cycle at ' + task_id)
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        task = indexed[task_id]
        if task['status'] not in STATUSES:
            errors.append('invalid status: ' + task_id)
        for dep in task.get('depends_on', []):
            if dep not in indexed:
                errors.append('unknown dependency: ' + dep)
            else:
                visit(dep)
                if task['status'] == 'PASS' and indexed[dep]['status'] != 'PASS':
                    errors.append('PASS with incomplete prerequisite: ' + task_id)
        if task['status'] == 'PASS' and not task.get('evidence'):
            errors.append('PASS without evidence: ' + task_id)
        for ev in task.get('evidence', []):
            p = (ROOT / ev['path']).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file():
                errors.append('missing/outside evidence: ' + ev['path'])
            elif ev.get('sha256') != digest(p):
                errors.append('changed evidence: ' + ev['path'])
        if task['status'] == 'PASS' and not task.get('source_bindings'):
            errors.append('PASS without source bindings: ' + task_id)
        for binding in task.get('source_bindings', []):
            p = (ROOT / binding['path']).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file():
                errors.append('missing/outside bound source: ' + binding['path'])
            elif binding.get('sha256') != digest(p):
                errors.append('source changed since evidence; rerun task ' + task_id + ': ' + binding['path'])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in ids:
        visit(task_id)
    print(json.dumps({'status': 'FAIL' if errors else 'PASS', 'errors': errors,
                      'tasks': len(tasks), 'scope': 'task graph and evidence integrity; not design acceptance'},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 0


def resume():
    state = read_state()
    print((ROOT / 'PROGRESS.md').read_text())
    indexed = {t['id']: t for t in state['tasks']}
    print('\nReady tasks (requirements satisfied):')
    for task in state['tasks']:
        if task['status'] in {'TODO', 'IN_PROGRESS', 'FAIL'} and all(
                indexed[d]['status'] == 'PASS' for d in task.get('depends_on', [])):
            print(f"{task['id']}: {task['title']}\n  {task['next_action']}")
    print('\nBlocked tasks:')
    for task in state['tasks']:
        if task['status'] == 'BLOCKED':
            print(f"{task['id']}: {task.get('blocker', 'see task details')}")
    return validate()


def archive(label, package=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', label):
        raise ValueError('label must be a short filename-safe identifier')
    if validate():
        return 1
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:6]
    out = ROOT / 'artifacts' / ('releases' if package else 'checkpoints') / (stamp + '-' + label)
    out.mkdir(parents=True, exist_ok=False)
    entries = manifest()
    (out / 'manifest.json').write_text(json.dumps({
        'schema': 'kwt-source-snapshot-v1', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'label': label, 'files': entries, 'excluded': 'tools, venv, credentials, datasets, platform/libraries and raw runs',
    }, ensure_ascii=False, indent=2) + '\n')
    # With no usable root Git repository, hashes alone cannot restore edits.
    # Store the actual whitelisted source bytes; official technology payloads
    # remain excluded unless explicitly added through a reviewed source policy.
    for name, expected in entries.items():
        p = out / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, p)
        if digest(p) != expected['sha256']:
            raise ValueError('source changed while creating snapshot: '+name)
    if package:
        package_path = out / (label + '.tar.gz')
        with tarfile.open(package_path, 'w:gz') as archive_file:
            for name in entries:
                archive_file.add(out / name, arcname=label + '/' + name, recursive=False)
            archive_file.add(out / 'manifest.json', arcname=label + '/RELEASE_MANIFEST.json')
        # Validate archive bytes against the manifest, not merely that the file exists.
        with tarfile.open(package_path, 'r:gz') as archive_file:
            for name, record in entries.items():
                blob = archive_file.extractfile(label + '/' + name).read()
                if hashlib.sha256(blob).hexdigest() != record['sha256']:
                    raise ValueError('archive mismatch: ' + name)
        (out / 'SHA256SUMS').write_text(digest(package_path) + '  ' + package_path.name + '\n')
    print(json.dumps({'status': 'PASS', 'output': str(out), 'source_files': len(entries),
                      'source_bytes': sum(v['bytes'] for v in entries.values())}, ensure_ascii=False))
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('resume')
    sub.add_parser('validate')
    for command in ['checkpoint', 'package']:
        cmd = sub.add_parser(command)
        cmd.add_argument('--label', required=True)
    args = p.parse_args()
    if args.command == 'resume':
        return resume()
    if args.command == 'validate':
        return validate()
    return archive(args.label, package=args.command == 'package')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, KeyError, OSError, TypeError) as error:
        print('HARNESS FAIL: ' + str(error), file=sys.stderr)
        sys.exit(1)
