"""Immutable original evidence utilities; Python 3.6 standard library only."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)


def need(ok, text):
    if not ok: raise ValueError(text)


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key: '+str(key)); result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write(path, value):
    path = Path(path); temporary = path.with_name(path.name+'.tmp.%d' % os.getpid())
    with temporary.open('w') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2)+'\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def stat_key(path):
    value = Path(path).stat()
    return value.st_size, value.st_mtime_ns, value.st_ino


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): value.update(block)
    return value.hexdigest()


def identity(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), 'regular non-symlink evidence required: '+str(path))
    before = stat_key(path); value = digest(path)
    need(stat_key(path) == before, 'original changed during SHA: '+str(path))
    return dict(path=str(path), bytes=before[0], sha256=value)


def check(path, expected):
    actual = identity(path)
    need(actual['path'] == expected['path'] and actual['sha256'] == expected['sha256'] and
         ('bytes' not in expected or actual['bytes'] == expected['bytes']), 'original identity differs: '+str(path))
    return actual


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
