#!/usr/bin/env python3
"""Keep a unique controller process marker while running the unchanged166 CLI in-process."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--command', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    c = json.loads(a.command.read_text())
    assert c['schema'] == 'xu-frozen-inprocess-command170-v1'
    assert c['qualification'] == 'NOT_QUALIFIED' and c['out'] == str(a.out)
    entry = Path(c['entry']['path'])
    assert entry.is_file() and not entry.is_symlink()
    assert entry.stat().st_size == c['entry']['bytes']
    assert hashlib.sha256(entry.read_bytes()).hexdigest() == c['entry']['sha256']
    argv = c['argv']
    assert argv[:2] == [str(entry), 'campaign'] and argv.count('--out') == 1
    assert argv[argv.index('--out') + 1] == str(a.out)
    sys.argv = argv
    runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    main()
