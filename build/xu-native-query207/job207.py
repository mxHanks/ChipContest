#!/usr/bin/env python3
"""Build one207 original153 job; no registration, EDA invocation or network."""
import argparse
import json
from pathlib import Path
import query207 as api

D = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B = D / 'xu-score-optimization-20261102'
OUT = B / 'native-query-replay-20261105-207'


def job():
    manifest = api.bundle()
    root = D / 'xu-native-query207'
    rows = [dict(path=str(root / r['name']), bytes=r['bytes'], sha256=r['sha256']) for r in manifest['runtime']]
    item = api.identity(api.HERE / 'manifest207.json')
    rows.append(dict(path=str(root / 'manifest207.json'), bytes=item['bytes'], sha256=item['sha256']))
    ref177 = api.read(api.HERE / 'frozen177/references177.json')
    q = ref177['next_minimal_readonly_query']
    rows += [q['target'], q['own_s2c_sdc']] + q['own_s2c_libraries']
    rows += [ref177['pt'], ref177['model'], ref177['own_clock_method_source']]
    rows += api.read(api.HERE / 'frozen186/references186.json')['server_inputs']
    rows += api.read(api.HERE / 'references207.json')['common190']
    unique = {}
    for row in rows:
        item = {k: row[k] for k in ['path', 'bytes', 'sha256']}
        api.need(item['path'] not in unique or unique[item['path']] == item,
                 'inconsistent frozen input identities')
        unique[item['path']] = item
    return dict(schema='xu-experiment-control150-job-v1', id='native_query207',
        kind='launch', launch_mode='direct', native=True,
        argv=['/bin/python3', '-B', '-u', str(root / 'query207.py'), '--out', str(OUT)],
        dependencies=[dict(id='two_candidate_finalpack191', policy='terminal')],
        output_root=str(OUT), process_contains=str(OUT), result_state=str(OUT / 'state.json'),
        success_statuses=[api.SUCCESS], failure_statuses=[api.FAILURE],
        frozen_inputs=[unique[k] for k in sorted(unique)], qualification='NOT_QUALIFIED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    text = json.dumps(job(), sort_keys=True, indent=2) + '\n'
    if args.out:
        with args.out.open('x') as stream:
            stream.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
