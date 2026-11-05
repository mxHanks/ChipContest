#!/usr/bin/env python3
"""Produce two frozen jobs for existing153; no registration, network or EDA."""
import argparse
import json
from pathlib import Path
import power190 as api

D = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B = D / 'xu-score-optimization-20261102'
ROOT = D / 'xu-s2c-common-power198'
OUTS = {'preflight190': B / 's2c-common-scope-preflight-20261105-190',
        'full12_190': B / 's2c-common-scope-power12-20261105-190'}


def job(which, after='s2e_coverage186'):
    api.need(which in OUTS, 'unknown190 job')
    api.runtime()
    m = api.read(api.HERE / 'manifest190.json')
    frozen = [dict(path=str(ROOT / r['name']), bytes=r['bytes'], sha256=r['sha256']) for r in m['runtime']]
    rec = api.identity(api.HERE / 'manifest190.json')
    frozen.append(dict(path=str(ROOT / 'manifest190.json'), bytes=rec['bytes'], sha256=rec['sha256']))
    ref = api.read(api.HERE / 'references190.json')
    frozen += [ref[k] for k in ['prepared57', 'execution57', 'fm_state', 'ppa_prepared', 'area', 'verify', 'scope']]
    out = OUTS[which]
    dependencies = ([dict(id=after, policy='terminal')] if which == 'preflight190' else
                    [dict(id='s2c_common_preflight190', policy='success')])
    return dict(schema='xu-experiment-control150-job-v1', id='s2c_common_' + which, kind='launch', launch_mode='direct',
                native=True, argv=['/bin/python3', '-B', '-u', str(ROOT / 'run190.py'), '--command', which, '--out', str(out)],
                dependencies=dependencies, frozen_inputs=frozen, output_root=str(out), process_contains=str(out),
                result_state=str(out / 'result.json'), success_statuses=[api.TASK0 if which == 'preflight190' else api.FULL12],
                failure_statuses=[api.FAIL], qualification='NOT_QUALIFIED')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--which', choices=list(OUTS), required=True)
    p.add_argument('--after', default='s2e_coverage186')
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    text = json.dumps(job(args.which, args.after), indent=2, sort_keys=True) + '\n'
    if args.out:
        with args.out.open('x') as output:
            output.write(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
