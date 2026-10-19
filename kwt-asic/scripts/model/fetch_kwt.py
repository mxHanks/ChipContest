#!/usr/bin/env python3
"""Fetch an explicitly pinned subset of the official KWT tree; verify Git blob IDs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path, PurePosixPath
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
COMMIT = '237e4097afd4f6851e0b82f0a8d65c2dfe8eae30'
BASE = 'https://raw.githubusercontent.com/ARM-software/keyword-transformer/' + COMMIT + '/'
DEST = ROOT / 'vendor/kwt1-237e4097'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'kwt-migration-reproducible-fetch'})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def selected(path):
    return (path in {'LICENSE.txt', 'README.md', 'requirements.txt', 'eval.sh'}
            or path.startswith('kws_streaming/') and path.endswith('.py')
            or path in {'models_data_v2_12_labels/kwt1/' + name for name in [
                'best_weights.data-00000-of-00001', 'best_weights.index', 'flags.json',
                'flags.txt', 'labels.txt', 'model_summary.txt', 'checkpoint']})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch', action='store_true', help='Permit network to fetch missing pinned files.')
    p.add_argument('--output', type=Path, default=ROOT/'docs/runs/kwt-vendor-manifest.json')
    args = p.parse_args()
    tree_path = ROOT/'data/downloads/keyword-transformer/tree.json'
    if not tree_path.exists():
        saved = ROOT/'docs/runs/kwt-vendor-manifest.json'
        if saved.is_file() and not args.fetch:
            result = json.loads(saved.read_text())
            if result.get('commit') != COMMIT or not result.get('files'):
                raise ValueError('invalid offline source manifest')
            for item in result['files']:
                path = (ROOT/item['path']).resolve()
                if not path.is_relative_to(DEST.resolve()):
                    raise ValueError('offline manifest outside vendor subtree')
                blob = path.read_bytes()
                blob_id = hashlib.sha1(b'blob ' + str(len(blob)).encode() + b'\0' + blob).hexdigest()
                if (hashlib.sha256(blob).hexdigest() != item['sha256'] or
                        blob_id != item['git_blob_sha1'] or len(blob) != item['bytes']):
                    raise ValueError('offline source changed: ' + item['path'])
            print(json.dumps({'status':'PASS','scope':'offline pinned vendor bytes','files':len(result['files'])}))
            return
        if not args.fetch:
            p.error('missing tree inventory; use --fetch')
        tree_path.parent.mkdir(parents=True, exist_ok=True)
        tree_path.write_bytes(fetch('https://api.github.com/repos/ARM-software/keyword-transformer/git/trees/' + COMMIT + '?recursive=1'))
    tree = json.loads(tree_path.read_text())
    if tree.get('truncated') or tree.get('sha') != COMMIT:
        raise ValueError('unexpected or truncated fixed-commit tree')
    items = [item for item in tree['tree'] if item['type'] == 'blob' and selected(item['path'])]
    if not items:
        raise ValueError('empty source set')

    def download(item):
        rel = PurePosixPath(item['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('unsafe source path')
        target = DEST.joinpath(*rel.parts)
        if target.exists():
            blob = target.read_bytes()
        else:
            if not args.fetch:
                raise FileNotFoundError(target)
            blob = fetch(BASE + item['path'])
        git_sha = hashlib.sha1(b'blob ' + str(len(blob)).encode() + b'\0' + blob).hexdigest()
        if git_sha != item['sha'] or len(blob) != item['size']:
            raise ValueError('upstream blob integrity failed: ' + item['path'])
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + '.download')
            tmp.write_bytes(blob)
            tmp.replace(target)
        return {'path': str(target.relative_to(ROOT)), 'url': BASE + item['path'],
                'git_blob_sha1': git_sha, 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob)}

    with ThreadPoolExecutor(max_workers=4) as executor:
        files = list(executor.map(download, items))
    result = {'status': 'PASS', 'commit': COMMIT, 'scope': 'official pinned source and best checkpoint byte integrity only',
              'tensor_shape_validation': 'NOT_RUN', 'source_files': len(files),
              'total_bytes': sum(item['bytes'] for item in files), 'files': files}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'files'}))


if __name__ == '__main__':
    main()
