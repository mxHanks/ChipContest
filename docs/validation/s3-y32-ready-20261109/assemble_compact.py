#!/usr/bin/env python3
"""Collect small READY evidence byte copies; no simulation or original mutations.

Default preparation skips the active full12 campaign and portable sealing files.
Run --final only after their owners declare the full campaign and seal complete.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'build/ready-20261109'
TEXT_SUFFIXES = {'.log', '.json', '.md', '.py', '.patch', '.diff', '.txt', '.sha256'}
SUCCESS = 'DEVELOPMENT_PASS_POLICY_PENDING'
REQUIRED_SUMMARIES = ('baseline.json', 'baseline-verification.json',
    'selected-baseline-sources.json', 'ready_compare.py', 'test_ready_compare.py',
    'ready-task0-comparison-v2.json', 'ready-task0-sourcepairs.json',
    'comparator-negative-checks-v2.json', 'integrated-sourcecheck-final.json')
FINAL_SUMMARIES = ('ready-full12-comparison.json', 'ready-full12-sourcepairs.json')
REQUIRED_PORTABLE = ('assembly.json', 'archive.sha256', 'archive-verification.json',
    'final-seal-receipt.json', 'verify_evidence.py', 'revalidate_comparisons.py',
    'root-independent-receipt.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', action='store_true',
                        help='owners confirmed full12 and portable evidence are complete')
    args = parser.parse_args()
    origins, pending, inventory = {}, [], []

    def add(src, rel):
        if not src.is_file() or src.is_symlink():
            raise ValueError('not a regular original: ' + str(src))
        before = src.stat()
        identity = sha(src)
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        after = src.stat()
        if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                or sha(dst) != identity):
            dst.unlink()
            raise ValueError('original changed during collection: ' + str(src))
        origins[str(rel)] = dict(original_path=str(src.resolve()),
                                sha256=identity, bytes=before.st_size)

    def tree(src, rel):
        if not src.is_dir():
            pending.append(str(src))
            return
        for path in sorted(src.rglob('*')):
            if ('__pycache__' in path.parts or path.is_symlink() or
                    not path.is_file() or path.suffix not in TEXT_SUFFIXES):
                continue
            # Explicitly exclude source snapshots, even if a later helper creates
            # one inside a proof folder. Tools and recorded patches are allowed.
            if any(part in {'source', 'vectors', 'verilator-obj', 'prototype-repo'}
                   for part in path.relative_to(src).parts):
                continue
            add(path, rel / path.relative_to(src))

    # Only collector-owned output subtrees are replaced, preventing stale copies.
    for name in ('campaigns', 'summaries', 'proofs', 'portable-package'):
        path = OUT / name
        if path.exists():
            shutil.rmtree(path)
    cases = [('baseline-selected-full12', ROOT / 'build/postflow-20261108/selected-full12'),
             ('ready-task0-failed-before-fence', BASE / 'ready-task0'),
             ('ready-fenced-task0', BASE / 'ready-fenced-task0'),
             ('ready-full12', BASE / 'ready-full12')]
    for label, src in cases:
        result = src / 'result.json'
        if label == 'ready-full12' and not args.final:
            pending.append(str(result) + ' (owner completion not yet confirmed)')
            continue
        if not result.is_file():
            pending.append(str(result))
            continue
        run = json.loads(result.read_text())
        status = run.get('status')
        if status in (None, 'RUNNING'):
            pending.append(str(result) + ' (not final)')
            continue
        inventory.append(dict(label=label, original_path=str(src.resolve()),
            status=status, classification='DEVELOPMENT_SUCCESS' if status == SUCCESS else 'FAILED_OR_DIAGNOSTIC',
            layers=len(run.get('task_results', [])), cycles=run.get('cycles'),
            outputs=run.get('outputs'), source_drift=run.get('source_drift'),
            scope='Saved status retained exactly; development success is not qualification.'))
        rel = Path('campaigns') / label
        for name in ('plan.json', 'result.json', 'clear-recipe.json', 's3_clear_main.c'):
            path = src / name
            if path.is_file():
                add(path, rel / name)
            else:
                pending.append(str(path))
        for path in sorted(src.glob('task-*/simulation.log')):
            add(path, rel / path.relative_to(src))

    # Root-level tools, pinned source pairs, comparisons, diagnostics and console
    # receipts. The active full12 console/output is never copied in preparation.
    for path in sorted(BASE.iterdir()):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if not args.final and 'full12' in path.name:
            continue
        add(path, Path('summaries') / path.name)
    for name in REQUIRED_SUMMARIES + (FINAL_SUMMARIES if args.final else ()):
        if not (BASE / name).is_file():
            pending.append(str(BASE / name))
    tree(BASE / 'checks', Path('proofs/checks'))
    tree(BASE / 'rtl-checks', Path('proofs/rtl-checks'))
    if args.final:
        # Never traverse portable staging/extracted trees; the compact copy
        # keeps only seal tools, top-level receipts and explicit diagnostics.
        for path in sorted((BASE / 'handoff').iterdir()):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                add(path, Path('portable-package') / path.name)
        diagnostics = BASE / 'handoff/packaging-diagnostics'
        if diagnostics.is_dir():
            tree(diagnostics, Path('portable-package/packaging-diagnostics'))
        for name in REQUIRED_PORTABLE:
            if not (BASE / 'handoff' / name).is_file():
                pending.append(str(BASE / 'handoff' / name))
    else:
        pending.append(str(BASE / 'handoff') + ' (portable seal and root verification not confirmed)')

    failures = []
    needles = ('FATAL:', 'FAILED (', 'FAIL:', 'Traceback (most recent call last):',
               '%Error:', 'TIMEOUT', 'S3_CLEAR_CAMPAIGN_FAIL')
    for rel in sorted(origins):
        path = OUT / rel
        if path.suffix == '.log' and any(s in path.read_text(errors='replace') for s in needles):
            failures.append(dict(path=rel, classification='NOT_PASS_OR_INJECTED_DIAGNOSTIC',
                note='Original bytes retained. Read original context; failures are never counted as successful measurements.'))
    dump(OUT / 'campaign-inventory.json', inventory)
    dump(OUT / 'failure-log-index.json', failures)
    dump(OUT / 'provenance.json', dict(files=origins, pending_originals=pending,
        policy='Original byte copies; no ELF, native binary, vectors, RTL/source snapshots or intermediate objects.'))
    manifest = {str(path.relative_to(OUT)): sha(path) for path in sorted(OUT.rglob('*'))
                if path.is_file() and path.name not in ('sha256.json', 'collection-summary.json')}
    dump(OUT / 'sha256.json', manifest)
    summary = dict(status='PENDING_FINAL_EVIDENCE' if pending else 'COMPACT_EVIDENCE_COLLECTED',
        phase='final' if args.final else 'preparation', files=len(manifest)+2,
        bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),
        campaigns=len(inventory), copied_originals=len(origins), diagnostic_logs=len(failures),
        pending_originals=pending,
        portable_archive=str(BASE / 'handoff/s3-y32-ready-evidence.tar.gz'))
    dump(OUT / 'collection-summary.json', summary)
    for _ in range(3):
        actual = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
        if actual == summary['bytes']:
            break
        summary['bytes'] = actual
        dump(OUT / 'collection-summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
