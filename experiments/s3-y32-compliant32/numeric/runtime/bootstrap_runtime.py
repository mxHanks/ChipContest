#!/usr/bin/env python3
"""Restore the pinned legacy inference runtime without changing system Python.

Run with the host Python (3.12+). All writes and installed packages stay under
build/compliant32-20261113/numeric/runtime. No model, dataset or EDA execution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import urllib.request


ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / 'build/compliant32-20261113/numeric/runtime'
PYTHON_URL = ('https://github.com/astral-sh/python-build-standalone/releases/download/'
              '20241002/cpython-3.8.20%2B20241002-x86_64-unknown-linux-gnu-install_only.tar.gz')
PYTHON_SHA256 = '285e141c36f88b2e9357654c5f77d1f8fb29cc25132698fe35bb30d787f38e87'
REQUIREMENTS = Path(__file__).with_name('requirements.txt')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def run(command, runtime, env, log_name):
    with (runtime / log_name).open('w') as log:
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('command failed; see ' + str(runtime / log_name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    runtime = RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    downloads = runtime / 'downloads'
    downloads.mkdir(exist_ok=True)
    temporary = runtime / 'tmp'
    temporary.mkdir(exist_ok=True)
    # An affinity limit also constrains compiler subprocesses and library pools.
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    env = os.environ.copy()
    env.update({key: '1' for key in ('TF_NUM_INTRAOP_THREADS', 'TF_NUM_INTEROP_THREADS',
                'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MAX_JOBS')})
    env.update(CUDA_VISIBLE_DEVICES='-1', PYTHONNOUSERSITE='1',
               PYTHONDONTWRITEBYTECODE='1', PIP_CONFIG_FILE='/dev/null',
               PIP_CACHE_DIR=str(runtime / 'pip-cache'), PIP_DISABLE_PIP_VERSION_CHECK='1',
               PIP_NO_INPUT='1', TMPDIR=str(temporary))
    archive = downloads / 'cpython-3.8.20+20241002-x86_64-unknown-linux-gnu-install_only.tar.gz'
    if not archive.exists() or sha256(archive) != PYTHON_SHA256:
        partial = archive.with_suffix('.partial')
        with urllib.request.urlopen(PYTHON_URL, timeout=60) as response, partial.open('wb') as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if sha256(partial) != PYTHON_SHA256:
            raise ValueError('standalone CPython SHA256 does not match publisher checksum')
        partial.replace(archive)
    save(runtime / 'python-download.json', dict(
        schema='s3-compliant32-runtime-download-v1', created_utc=datetime.now(timezone.utc).isoformat(),
        publisher='astral-sh/python-build-standalone', python_version='3.8.20',
        release='20241002', url=PYTHON_URL, sha256=sha256(archive), bytes=archive.stat().st_size,
        checksum_url=PYTHON_URL + '.sha256',
        release_metadata_url='https://api.github.com/repos/astral-sh/python-build-standalone/releases/tags/20241002',
        python_release_url='https://www.python.org/downloads/release/python-3820/'))
    print('verified CPython archive:', archive, flush=True)
    if args.download_only:
        return
    python = runtime / 'python/bin/python3.8'
    if not python.exists():
        with tarfile.open(archive, 'r:gz') as contents:
            contents.extractall(runtime, filter='data')
    if subprocess.check_output([str(python), '-c', 'import platform; print(platform.python_version())'],
                               env=env, text=True).strip() != '3.8.20':
        raise ValueError('restored interpreter is not Python 3.8.20')
    venv = runtime / 'venv'
    if not (venv / 'bin/python').exists():
        run([str(python), '-m', 'venv', str(venv)], runtime, env, 'venv-create.log')
    executable = venv / 'bin/python'
    print('installing exact inference requirements into:', venv, flush=True)
    report = runtime / ('pip-install-report-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.json')
    log_name = report.stem + '.log'
    locked = REQUIREMENTS.with_name('requirements-lock.txt')
    requirements = ['--require-hashes', '-r', str(locked)] if locked.is_file() else ['-r', str(REQUIREMENTS)]
    run([str(executable), '-m', 'pip', 'install', '--index-url', 'https://pypi.org/simple',
         '--report', str(report)] + requirements,
        runtime, env, log_name)
    if json.loads(report.read_text())['install']:
        save(runtime / 'pip-install-report.json', json.loads(report.read_text()))
        (runtime / 'pip-install.log').write_text((runtime / log_name).read_text())
    run([str(executable), '-m', 'pip', 'check'], runtime, env, 'pip-check.log')
    freeze = subprocess.check_output([str(executable), '-m', 'pip', 'freeze', '--all'], env=env, text=True)
    (runtime / 'installed-freeze.txt').write_text(freeze)
    save(runtime / 'bootstrap-status.json', dict(
        schema='s3-compliant32-runtime-bootstrap-v1', status='PASS_RUNTIME_INSTALLED',
        created_utc=datetime.now(timezone.utc).isoformat(), executable=str(executable),
        python_version='3.8.20', python_archive_sha256=PYTHON_SHA256,
        requirements_sha256=sha256(locked if locked.is_file() else REQUIREMENTS),
        cpu_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        training_executed=False, audio_inference_executed=False,
        package_provenance='pip-install-report.json', package_freeze='installed-freeze.txt'))
    print('runtime ready; no model inference or training was run:', executable, flush=True)


if __name__ == '__main__':
    main()
