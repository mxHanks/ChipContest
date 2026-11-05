#!/usr/bin/env python3
"""Same-PID frozen190 launcher: only own unique output root appears in /proc."""
import argparse
from pathlib import Path
import runpy
import sys
import power190 as api


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--command', required=True, choices=['preflight190', 'full12_190'])
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    api.runtime()
    row = api.read(api.HERE / ('command-' + args.command + '.json'))
    api.need(row['schema'] == 'xu-common190-command-v1' and row['qualification'] == 'NOT_QUALIFIED' and
             row['out'] == str(args.out.absolute()), 'frozen190 output differs')
    entry = api.HERE / 'power190.py'
    api.need(api.sha(entry) == row['entry_sha256'], 'frozen190 entry changed')
    argv = row['argv']
    api.need(argv[:2] == [str(entry), 'campaign'] and argv.count('--out') == 1 and
             argv[argv.index('--out') + 1] == str(args.out.absolute()), 'frozen190 argv differs')
    sys.argv = argv
    runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    main()
