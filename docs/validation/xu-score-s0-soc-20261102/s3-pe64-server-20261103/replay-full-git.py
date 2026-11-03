#!/usr/bin/env python3
"""xu: independently replay every deployed path against pinned immutable Git objects."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

H = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xu_prepare_pe64_evidence', H / 'prepare-evidence.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def validate(manifest, records, payload, commit, child):
    prepare.need(manifest['commit'] == commit, 'commit differs')
    listed = manifest['files']
    prepare.need(len(listed) == len({x['path'] for x in listed}) == len(records), 'tracked path set/count differs')
    prepare.need({x['path'] for x in listed} == set(records), 'tracked path set/count differs')
    for record in listed:
        name = record['path']
        actual = records[name]
        prepare.need(record['mode'] == actual['mode'] and record['git_oid'] == actual['oid'], 'mode/OID differs')
        if actual['kind'] == 'commit':
            prepare.need(name == prepare.SUB and actual['oid'] == child and record['mode'] == '160000', 'gitlink differs')
        else:
            b = payload[name]
            prepare.need(len(b) == record['bytes'] and hashlib.sha256(b).hexdigest() == record['sha256'], 'immutable source bytes differ')


def audit(candidate):
    frozen = json.loads((H / 'deployment/source-files.json').read_text())
    rejections = []
    counts = {}
    for label, repo, commit in [('main', candidate, prepare.MAIN), ('child', candidate / prepare.SUB, prepare.CHILD)]:
        records = prepare.tree(repo, commit)
        payload = prepare.blobs(repo, records)
        validate(frozen[label], records, payload, commit, prepare.CHILD)
        counts[label] = dict(entries=len(records), blobs=len(payload), gitlinks=sum(x['kind'] == 'commit' for x in records.values()))
        for field, replacement in [('bytes', -1), ('sha256', '0' * 64), ('mode', '100600'), ('git_oid', '0' * 40)]:
            bad = copy.deepcopy(frozen[label])
            record = next(r for r in bad['files'] if r['mode'] != '160000')
            record[field] = replacement
            try:
                validate(bad, records, payload, commit, prepare.CHILD)
            except ValueError:
                rejections.append(label + '/' + field)
            else:
                raise AssertionError('bad Git freeze accepted')
        bad = copy.deepcopy(frozen[label])
        bad['files'][-1] = bad['files'][0]
        try:
            validate(bad, records, payload, commit, prepare.CHILD)
        except ValueError:
            rejections.append(label + '/duplicate_path')
        else:
            raise AssertionError('duplicate Git path accepted')
    return dict(status='PASS', main_commit=prepare.MAIN, e203_commit=prepare.CHILD,
                source_manifest_sha256=prepare.sha((H / 'deployment/source-files.json').read_bytes()),
                counts=counts, rejected_corruptions=rejections,
                scope='Local immutable Git blobs, modes and gitlink replay; server filesystem stability is the frozen launcher receipt assertion.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, default=prepare.REPO)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate), indent=2, sort_keys=True))
