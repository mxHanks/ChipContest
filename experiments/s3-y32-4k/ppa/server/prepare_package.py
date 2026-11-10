#!/usr/bin/env python3
"""Make a reviewable server package; never launches or connects to EDA/server."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    source = a.prepared.resolve()
    out = a.out.resolve()
    if out.exists():
        raise ValueError('refuse overwrite: ' + str(out))
    m = json.loads((source / 'manifest.json').read_text())
    if not m.get('preparation_complete') or m.get('preflight_status') != 'PASS' or m.get('partial'):
        raise ValueError('candidate preparation is incomplete')
    for f in m['provenance']:
        if sha(source / f['path']) != f['sha256']:
            raise ValueError('prepared source drift: ' + f['path'])
    if sha(source / 'rtl.f') != m['rtl_f_sha256']:
        raise ValueError('RTL file-list drift')
    cpu = Path(m['candidate'])
    result = json.loads((cpu / 'result.json').read_text())
    if sha(cpu / 'result.json') != m['candidate_result_sha256'] or result['status'] != 'PASS':
        raise ValueError('CPU result identity/status mismatch')
    if m.get('candidate_tasks') != 12 or m.get('candidate_outputs') != 304128:
        raise ValueError('not a full12 source')
    out.mkdir(parents=True)
    shutil.copytree(source / 'source', out / 'source')
    for name in ['rtl.f', 'defines.json', 'manifest.json']:
        shutil.copy2(source / name, out / name)
    evidence = out / 'evidence'
    evidence.mkdir()
    for name in ['result.json', 'source-manifest.json', 'simulation.log']:
        shutil.copy2(cpu / name, evidence / ('cpu-full12-' + name))
    shutil.copy2(source / 'preflight/result.json', evidence / 'ppa-preflight-result.json')
    here = Path(__file__).resolve().parent
    for name in ['run_once.py', 'synth.tcl', 'README.md']:
        shutil.copy2(here / name, out / name)
    binding = {
        'schema': 's3-parallel4k-server-final-binding-v1',
        'status': 'PREPARED_NOT_EXECUTED', 'top': m['top'],
        'cpu_full12_result_sha256': m['candidate_result_sha256'],
        'cpu_source_manifest_sha256': sha(cpu / 'source-manifest.json'),
        'prepared_manifest_sha256': sha(source / 'manifest.json'),
        'dma_sha256': m['required_dma_sha256'], 'defines': m['defines'],
        'geometry': m['expected_geometry'], 'qualification': 'NOT_QUALIFIED',
        'principal_cycles': result['principal_cycles'],
        'unresolved': m['unresolved'], 'charged_area_scopes': m['charged_area_scopes'],
    }
    (out / 'final-binding.json').write_text(json.dumps(binding, indent=2, sort_keys=True) + '\n')
    files = {str(f.relative_to(out)): sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
    (out / 'package-files.json').write_text(json.dumps(files, indent=2, sort_keys=True) + '\n')
    review = subprocess.run(['python3', str(out / 'run_once.py')], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    # Keep review outside the pinned execution directory.
    out.with_suffix('.review.json').write_text(review.stdout)
    archive = out.with_suffix('.tar.gz')
    if archive.exists():
        raise ValueError('refuse archive overwrite')
    with tarfile.open(archive, 'w:gz') as tf:
        tf.add(out, arcname='candidate', recursive=True)
    receipt = dict(binding, package=str(out), archive=str(archive), archive_sha256=sha(archive),
                   archive_bytes=archive.stat().st_size, package_file_count=len(files))
    out.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': receipt['status'], 'archive': str(archive),
                      'sha256': receipt['archive_sha256'], 'files': len(files)}, sort_keys=True))


if __name__ == '__main__':
    main()
