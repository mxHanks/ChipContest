#!/usr/bin/env python3
"""Freeze207 exact runtime list; run locally before deployment/review."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    paths = [HERE / name for name in ['query207.py', 'compat207.tcl', 'references207.json', 'job207.py']]
    for folder in ['frozen177', 'frozen186', 'frozen190']:
        paths += [p for p in sorted((HERE / folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    rows = [dict(name=str(p.relative_to(HERE)), bytes=p.stat().st_size,
                 sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)]
    (HERE / 'manifest207.json').write_text(json.dumps(dict(schema='xu-native-query207-manifest-v1',
        qualification='NOT_QUALIFIED', runtime=rows), sort_keys=True, indent=2) + '\n')
    print('XU207_RUNTIME_FROZEN files=' + str(len(rows)))


if __name__ == '__main__':
    main()
