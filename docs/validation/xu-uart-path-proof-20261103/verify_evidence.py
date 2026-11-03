#!/usr/bin/env python3
"""xu: validate byte-exact UART proof archives without rewriting their contents."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def unique(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError('duplicate JSON key: ' + k)
        out[k] = v
    return out


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(str(message))


def main():
    here = Path(__file__).resolve().parent
    counts = []
    for name in ['run09-manifest.json', 'run08-manifest.json', 'prototype-manifest.json']:
        manifest = json.loads((here / 'raw' / name).read_text(), object_pairs_hook=unique)
        arc = manifest['archive']
        require(PurePosixPath(arc['name']).name == arc['name'], 'invalid archive name')
        path = here / 'raw' / arc['name']
        require(path.is_file() and not path.is_symlink(), path)
        data = path.read_bytes()
        require(len(data) == arc['bytes'] and digest(data) == arc['sha256'], path)
        seen = set()
        with tarfile.open(path, 'r:xz') as tar:
            for member in tar:
                rel = PurePosixPath(member.name)
                require(not rel.is_absolute() and '..' not in rel.parts and member.isfile(), member.name)
                require(member.name not in seen and member.name in manifest['files'], member.name)
                seen.add(member.name)
                content = tar.extractfile(member).read()
                entry = manifest['files'][member.name]
                require(len(content) == member.size == entry['bytes'] and digest(content) == entry['sha256'], member.name)
        require(seen == set(manifest['files']), path)
        counts.append(len(seen))
    print(json.dumps(dict(status='ARCHIVE_BYTES_VERIFIED', final_files=counts[0], previous_files=counts[1], prototype_files=counts[2])))


if __name__ == '__main__':
    main()
