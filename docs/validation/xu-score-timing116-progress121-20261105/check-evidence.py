#!/usr/bin/env python3
"""Verify immutable progress121 bytes; never infer FM completion from this snapshot."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent


def ident(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    assert manifest['scope'] == 'READ_ONLY_NONATOMIC_PROGRESS121_SNAPSHOT'
    assert manifest['qualification'] == 'NOT_QUALIFIED'
    for name, record in manifest['files'].items():
        assert ident((HERE / name).read_bytes()) == record, name
    archive = HERE / 'xu-server-progress-20261105-121.tar.xz'
    assert ident(archive.read_bytes()) == dict(bytes=542668, sha256=
        '07be4ca0267cdcbbec4263215c04e2dc5fdc8c6c5c544337d9d5da39898dbf14')
    payload = {}
    with tarfile.open(str(archive), 'r:xz') as source:
        for member in source:
            path = PurePosixPath(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert member.name not in payload
            payload[member.name] = source.extractfile(member).read()
    original = json.loads(payload.pop('manifest.json').decode('utf-8'))
    assert original == manifest['archive_original_manifest']
    assert len(original) == len(payload) == 88
    assert sum(len(data) for data in payload.values()) == 24741085
    for record in original:
        assert ident(payload[record['path']]) == {key: record[key] for key in ('bytes', 'sha256')}
    base = 'full-soc-timing-combined-20261105-116/'
    state = json.loads(payload[base + 'state.json'].decode('utf-8'))
    assert state['status'] == 'RUNNING_NOT_QUALIFIED' and state['phase'] == 'fm'
    assert state['pid'] == 25920 and 'frozen_after' not in state and len(state['runs']) == 2
    for label, marker in [('dc', 'XU_COMBINED116_DC_DONE_NOT_QUALIFIED'),
                          ('pt', 'XU_COMBINED116_PT_DIAGNOSTIC_DONE_NOT_QUALIFIED')]:
        run = next(row for row in state['runs'] if row['label'] == label)
        assert run['returncode'] == 0 and not run['errors'] and run['marker_count'] == 1
        data = payload[base + label + '.log']
        assert ident(data) == {key: run['log'][key] for key in ('bytes', 'sha256')}
        assert sum(line.strip() == marker for line in data.decode('utf-8').splitlines()) == 1
    analysis = json.loads((HERE / 'analysis116.json').read_text())
    for label in ('setup', 'hold'):
        rows = re.findall(r'^\s*slack \((\w+)\)\s+([-+\d.]+)',
                          payload[base + label + '.rpt'].decode('utf-8'), re.M)
        assert len(rows) == 50 and all(status == 'MET' for status, _ in rows)
        assert min(float(slack) for _, slack in rows) == analysis['global_slacks_ns'][label]['worst']
    for name, record in analysis['reset_paths'].items():
        text = payload[base + name].decode('utf-8')
        rows = re.findall(r'^\s*slack \((\w+)\)\s+([-+\d.]+)', text, re.M)
        assert [float(value) for _, value in rows] == record['slacks_ns']
        if not rows:
            assert 'No constrained paths.' in text and record['status'] == 'NO_CONSTRAINED_PATH_UNKNOWN'
    assert not re.search(r'\b(?:max_capacitance|min_capacitance)\b',
                         payload[base + 'constraints.rpt'].decode('utf-8'))
    print(json.dumps(dict(status='PROGRESS121_ORIGINAL_BYTES_AND_DC_PT_REPORTS_PASS',
                          qualification='NOT_QUALIFIED', files=88, bytes=24741085,
                          fm='RUNNING_AT_SNAPSHOT_NOT_FINAL',
                          execution_scripts_and_tsv_bodies='NOT_EXPORTED'), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
