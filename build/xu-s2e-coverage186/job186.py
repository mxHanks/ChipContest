#!/usr/bin/env python3
"""Generate one186 job for original153; never registers or launches a job."""
import argparse
import json
from pathlib import Path
import coverage186 as api

D = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B = D / 'xu-score-optimization-20261102'


def job():
    manifest = api.bundle()
    ref = api.read(api.HERE / 'references186.json')
    root = D / 'xu-s2e-coverage186'
    out = B / 's2e-own155-coverage-readonly-20261105-186'
    frozen = [dict(path=str(root / x['name']), bytes=x['bytes'], sha256=x['sha256']) for x in manifest['runtime']]
    item = api.identity(api.HERE / 'manifest186.json')
    frozen.append(dict(path=str(root / 'manifest186.json'), bytes=item['bytes'], sha256=item['sha256']))
    frozen.extend({k: x[k] for k in ('path', 'bytes', 'sha256')} for x in ref['server_inputs'])
    return dict(schema='xu-experiment-control150-job-v1', id='s2e_coverage186', kind='launch', launch_mode='direct',
                native=True, argv=['/bin/python3', '-B', '-u', str(root / 'coverage186.py'), '--out', str(out)],
                dependencies=[dict(id='s2c_readonly177', policy='terminal'), dict(id='s2e_final155_preflight166', policy='success')],
                output_root=str(out), process_contains=str(out), result_state=str(out / 'state.json'),
                success_statuses=[api.SUCCESS], failure_statuses=[api.FAILURE], frozen_inputs=frozen, qualification='NOT_QUALIFIED')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    text = json.dumps(job(), indent=2, sort_keys=True) + '\n'
    if args.out:
        with args.out.open('x') as stream:
            stream.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
