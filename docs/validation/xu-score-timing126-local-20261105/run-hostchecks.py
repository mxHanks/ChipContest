#!/usr/bin/env python3
"""Reproduce original13 local mechanism checks using committed fixtures only."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True, help='new, nonexistent output directory')
    args = parser.parse_args()
    evidence = load('xu126_local_evidence', HERE / 'check-evidence.py')
    evidence.verify()
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    root = out / 'fixture-root'
    actual = root / 'build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116'
    actual.mkdir(parents=True)
    for name, raw in evidence.parent_fixtures().items():
        (actual / name).write_bytes(raw)
    old = root / 'build/xu-score-resume-20261103/next-results-export-82/pmu-reset-condition-20261104-80'
    old.mkdir(parents=True)
    for path in sorted((HERE / 'fixtures/attributes80').glob('*.txt')):
        shutil.copyfile(path, old / path.name)
    original = load('xu126_original_hostchecks', HERE / 'tools/check_local126.py')
    # The frozen checker imports its unchanged sibling worker. Only its local
    # input-root and command-line output path are rebound; no EDA is executed.
    original.ROOT = root
    sys.argv = [str(HERE / 'tools/check_local126.py'), '--out', str(out / 'checks')]
    original.main()
    result = (out / 'checks/results.json').read_bytes()
    evidence.need(result == (HERE / 'hostcheck03-results.json').read_bytes(),
                  'reproduced13 checks differ from exact original03 results')
    print(json.dumps({'status': 'REPRODUCED_EXACT13_ORIGINAL126_HOSTCHECKS_NOT_SERVER_EXECUTION',
                      'qualification': 'NOT_QUALIFIED', 'results_sha256': evidence.ident(result)['sha256']},
                     sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
