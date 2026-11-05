#!/usr/bin/env python3
"""Build one frozen job for existing153; does not register or run it."""
import argparse
import json
from pathlib import Path
import readonly177 as api

D = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B = D / 'xu-score-optimization-20261102'


def job(dependency='two_candidate_autopack173'):
    api.bundle()
    root = D / 'xu-s2c-readonly177'
    out = B / 's2c-own9c16-readonly-20261105-177'
    manifest = api.read(api.HERE / 'manifest177.json')
    frozen = []
    for row in manifest['runtime']:
        frozen.append(dict(path=str(root / row['name']), sha256=row['sha256'], bytes=row['bytes']))
    actual = api.identity(api.HERE / 'manifest177.json')
    frozen.append(dict(path=str(root / 'manifest177.json'), sha256=actual['sha256'], bytes=actual['bytes']))
    ref = api.read(api.HERE / 'references177.json')
    q = ref['next_minimal_readonly_query']
    for row in [q['target'], q['own_s2c_sdc']] + q['own_s2c_libraries'] + [ref['pt'], ref['model'], ref['own_clock_method_source']]:
        frozen.append({k: row[k] for k in ('path', 'sha256', 'bytes')})
    return dict(schema='xu-experiment-control150-job-v1', id='s2c_readonly177', kind='launch', launch_mode='direct',
                native=True, argv=['/bin/python3', '-B', '-u', str(root / 'readonly177.py'), '--out', str(out)],
                dependencies=[dict(id=dependency, policy='terminal'), dict(id='s2c_unknown167', policy='success')], frozen_inputs=frozen,
                output_root=str(out), process_contains=str(out), result_state=str(out / 'state.json'),
                success_statuses=[api.SUCCESS], failure_statuses=[api.FAILURE], qualification='NOT_QUALIFIED')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--after', default='two_candidate_autopack173')
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    data = json.dumps(job(args.after), indent=2, sort_keys=True) + '\n'
    if args.out:
        with args.out.open('x') as out:
            out.write(data)
    else:
        print(data, end='')


if __name__ == '__main__':
    main()
