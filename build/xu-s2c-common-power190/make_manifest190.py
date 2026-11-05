#!/usr/bin/env python3
"""Rebuild local190 commands/manifest after an intentional code review change."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B = D / 'xu-score-optimization-20261102'
ROOT = D / 'xu-s2c-common-power198'

def main():
    entry = ROOT / 'power190.py'
    digest = hashlib.sha256((HERE / 'power190.py').read_bytes()).hexdigest()
    preflight = B / 's2c-common-scope-preflight-20261105-190'
    for name, out, ids in [('preflight190', preflight, '0'), ('full12_190', B / 's2c-common-scope-power12-20261105-190', 'all')]:
        argv = [str(entry), 'campaign', '--task-ids', ids, '--out', str(out)]
        if ids == 'all':
            argv += ['--preflight-root', str(preflight)]
        (HERE / ('command-' + name + '.json')).write_text(json.dumps(dict(schema='xu-common190-command-v1', qualification='NOT_QUALIFIED',
                 out=str(out), entry_sha256=digest, argv=argv), indent=2, sort_keys=True) + '\n')
    names = ['power190.py', 'frozen130.py', 'references190.json', 'run190.py', 'jobs190.py', 'command-preflight190.json', 'command-full12_190.json', 'frozen-fm190.json']
    rows = [dict(name=n, bytes=(HERE / n).stat().st_size, sha256=hashlib.sha256((HERE / n).read_bytes()).hexdigest()) for n in names]
    (HERE / 'manifest190.json').write_text(json.dumps(dict(schema='xu-common190-manifest-v1', runtime=rows, qualification='NOT_QUALIFIED'), indent=2, sort_keys=True) + '\n')

if __name__ == '__main__':
    main()
