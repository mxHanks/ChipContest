#!/usr/bin/env python3
"""Derive S3 transport files from frozen legacy vectors without inference.

CLI: export the pinned 12-task archive (or its extracted old vectors) to a new
output directory. The reusable helper also accepts validated synthetic vectors.
Legacy x/w/bias/y bytes are never rewritten; y32 and packed W are separate files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from model import fixed16_acc48 as legacy
from model import s3_y32 as s3

FIXTURE = ROOT / 'tests/e203/vectors/kwt-silence-v1.json'
ARCHIVE = FIXTURE.with_suffix('.tar.gz')
LEGACY_FILES = {'x.mem': (16, 6336), 'w.mem': (16, 16384),
                'bias.mem': (40, 256), 'y.mem': (48, 25344)}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _tasks(tasks):
    if type(tasks) is not int or not 1 <= tasks <= 12:
        raise ValueError('tasks must be an integer in 1..12')


def _hex_bytes(values, bits):
    # pack_weight_source returns unsigned bus words; their signed interpretation
    # is irrelevant to this serialization. Y32 values are checked by the model.
    mask = (1 << bits) - 1
    return ''.join('%0*x\n' % ((bits + 3)//4, v & mask) for v in values).encode('ascii')


def add_s3_files(directory, tasks, shared_w_packed=False, output_y32=True):
    """Add or verify S3 files in a legacy vector directory and return its profile.

    Every old tensor is shape/encoding checked. Existing generated files must be
    byte-identical, including profile metadata; conflicting files are rejected
    before any writes. MAC outputs come from y.mem, never a new inference run.
    """
    _tasks(tasks)
    profile = s3.profile(shared_w_packed, output_y32)
    directory = Path(directory)
    inputs, generated, records = {}, {}, []
    for layer in range(tasks):
        prefix = 'layer_%02d' % layer
        values, files = {}, {}
        for name, (bits, count) in LEGACY_FILES.items():
            path = directory / prefix / name
            if path.is_symlink():
                raise ValueError('vector files must not be symlinks: ' + str(path))
            raw = path.read_bytes()
            values[name] = legacy.read_hex_mem(path, bits, count)
            inputs[path] = raw
            files[name] = dict(bits=bits, words=count, bytes=len(raw), sha256=sha256(raw))
        y32 = [s3.quantize_result(v) for v in values['y.mem']]
        flat_w = values['w.mem']
        packed = s3.pack_weight_source([flat_w[k*256:(k+1)*256] for k in range(64)])
        for name, words in [('y32.mem', y32), ('w_packed16.mem', packed)]:
            payload = _hex_bytes(words, 32)
            path = directory / prefix / name
            generated[path] = payload
            files[name] = dict(bits=32, words=len(words), bytes=len(payload), sha256=sha256(payload))
        records.append(dict(layer=layer, files=files))
    profile.update(schema='s3_vector_profile_v1', tasks=tasks,
                   scope='integer transport conversion only; no inference or accuracy claim',
                   legacy_format=legacy.FORMAT_ID,
                   legacy_y=dict(bits=48, scale_exponent=-27, file='y.mem',
                                 layout='row_major_signed48'),
                   y32_file='y32.mem', packed_w_file='w_packed16.mem',
                   models={name: sha256((ROOT/'model'/name).read_bytes())
                           for name in ['fixed16_acc48.py', 's3_y32.py']},
                   exporter_sha256=sha256(Path(__file__).read_bytes()), layers=records)
    if not output_y32:
        profile['y_file'] = 'y.mem'
        profile['auxiliary_y32_file'] = profile.pop('y32_file')
    generated[directory/'profile.json'] = _json_bytes(profile)
    # Validate all destinations first, so a stale file cannot leave a partial
    # update. Repeated calls verify artifacts rather than silently replacing them.
    for path, payload in generated.items():
        if path.is_symlink() or (path.exists() and path.read_bytes() != payload):
            raise ValueError('existing S3 artifact differs: ' + str(path))
    for path, payload in inputs.items():
        if path.read_bytes() != payload:
            raise ValueError('legacy input changed during conversion: ' + str(path))
    for path, payload in generated.items():
        if not path.exists():
            path.write_bytes(payload)
    return profile


def _frozen_source(source):
    """Read exactly the pinned old 12-task input set, verifying all 48 hashes."""
    fixture = json.loads(FIXTURE.read_text())
    expected = fixture['files']
    source = Path(source)
    if source.is_dir():
        data = {}
        for name in expected:
            path = source / name
            if path.is_symlink():
                raise ValueError('frozen source must not contain symlinks')
            data[name] = path.read_bytes()
        origin = dict(kind='extracted_frozen_vectors', path=str(source.resolve()))
    else:
        archive = source.read_bytes()
        if sha256(archive) != fixture['archive_sha256']:
            raise ValueError('archive differs from frozen 12-task archive')
        data = {}
        with tarfile.open(source, 'r:*') as tar:
            members = tar.getmembers()
            if len(members) != len(expected) or {m.name for m in members} != set(expected):
                raise ValueError('unexpected or duplicate frozen archive members')
            for member in members:
                if not member.isfile():
                    raise ValueError('frozen archive contains a nonregular file')
                data[member.name] = tar.extractfile(member).read()
        origin = dict(kind='frozen_archive', path=str(source.resolve()), sha256=sha256(archive))
    for name, digest in expected.items():
        if sha256(data[name]) != digest:
            raise ValueError('frozen source hash mismatch: ' + name)
    origin.update(verified_tasks=12, verified_files=len(expected),
                  fixture_manifest_sha256=sha256(FIXTURE.read_bytes()),
                  source_commit=fixture['source_commit'], kwt_commit=fixture['kwt_commit'])
    return data, origin


def export_vectors(source, out, tasks=12, shared_w_packed=False):
    """Export selected tasks only after checking the complete frozen source."""
    _tasks(tasks)
    data, origin = _frozen_source(source)
    out = Path(out)
    if out.exists():
        raise ValueError('output directory already exists: ' + str(out))
    out.mkdir(parents=True)
    try:
        for layer in range(tasks):
            prefix = 'layer_%02d' % layer
            (out/prefix).mkdir()
            for name in LEGACY_FILES:
                (out/prefix/name).write_bytes(data[prefix+'/'+name])
        profile = add_s3_files(out, tasks, shared_w_packed)
        receipt = dict(schema='s3_vector_export_v1', source=origin, tasks=tasks,
                       profile_sha256=sha256((out/'profile.json').read_bytes()),
                       format=profile['format'])
        (out/'export-manifest.json').write_bytes(_json_bytes(receipt))
    except Exception:
        shutil.rmtree(out)
        raise
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ARCHIVE,
                        help='frozen archive or extracted old 12-task vectors')
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    parser.add_argument('--tasks', type=int, default=12, help='first N tasks, 1..12')
    parser.add_argument('--shared-w-packed16', action='store_true',
                        help='select packed16 shared W in profile (both images are always emitted)')
    args = parser.parse_args(argv)
    try:
        profile = export_vectors(args.source, args.out, args.tasks, args.shared_w_packed16)
    except (OSError, ValueError, TypeError, tarfile.TarError) as exc:
        parser.exit(1, 'S3_VECTOR_EXPORT_FAILED: %s\n' % exc)
    print('S3_VECTOR_EXPORT_PASS tasks=%d format=%s profile=%s' %
          (args.tasks, profile['format'], args.out/'profile.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
