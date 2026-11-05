#!/usr/bin/env python3
"""Rebuild a local fixture tree and run original132 red/green checks unchanged."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    e = load('xu132_local_evidence', HERE / 'check-evidence.py'); e.verify()
    sibling122 = HERE.parent / 'xu-score-timing116-terminal122-20261105/xu-server-terminal-20261105-122.tar.xz'
    raw122 = sibling122.read_bytes()
    e.need(e.ident(raw122) == {'bytes':1283388, 'sha256':'654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50'},
           'sibling original122 differs')
    original122 = e.members(raw122)
    sibling126 = HERE.parent / 'xu-score-timing126-local-20261105'
    e126 = load('xu126_local_evidence', sibling126 / 'check-evidence.py'); e126.verify()
    out = args.out.resolve(); out.mkdir(exist_ok=False); root = out / 'fixture-root'
    actual = root / 'build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116'
    actual.mkdir(parents=True)
    expected = {'state.json':'7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f',
                'mapped.v':'16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292',
                'sta.tcl':'7f344a3c017b6de915b522aef798be5fcae06119592391008f16e75841b2aed3',
                'analysis-coverage.rpt':'76a893dc3ac511f29c5f85fafc8119e8d925a8a1f2e20a0096fdf293c7a722ee'}
    for name, digest in expected.items():
        data = original122['full-soc-timing-combined-20261105-116/' + name]
        e.need(e.ident(data)['sha256'] == digest, 'actual116 host fixture differs: ' + name)
        (actual / name).write_bytes(data)
    failed = root / 'build/xu-score-resume-20261103/coverage131'
    for name, data in e.actual131().items():
        target = failed / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    old = root / 'build/xu-score-resume-20261103/next-results-export-82/pmu-reset-condition-20261104-80'
    old.mkdir(parents=True)
    for name, data in e126.attribute_fixtures().items(): (old / name).write_bytes(data)
    oldworker = root / 'build/xu-timing-coverage126/xu_timing_coverage126.py'
    oldworker.parent.mkdir(parents=True); shutil.copyfile(sibling126 / 'tools/xu_timing_coverage126.py', oldworker)
    tools = root / 'build/xu-timing-coverage132'; tools.mkdir()
    for path in (HERE / 'tools').glob('*.py'): shutil.copyfile(path, tools / path.name)
    command = [sys.executable, str(tools / 'check_regression132.py'), '--out', str(out / 'checks')]
    p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out / 'hostchecks.stdout').write_bytes(p.stdout); (out / 'hostchecks.stderr').write_bytes(p.stderr)
    e.need(p.returncode == 0, 'original132 regression failed: ' + p.stderr.decode(errors='replace'))
    saved = json.loads((HERE / 'original-delivery/local-check-final/regression-results.json').read_text())
    actual_result = json.loads((out / 'checks/results.json').read_text())
    e.need(actual_result['checks'] == saved['checks'] and actual_result['worker_sha256'] == e.WORKER_SHA and
           actual_result['qualification'] == 'NOT_QUALIFIED', 'reproduced132 checks differ')
    e.need((out / 'checks/base-local13/results.json').read_bytes() ==
           (HERE / 'original-delivery/local-check-final/mechanism13-results.json').read_bytes(),
           'exact13 mechanism result differs')
    print(json.dumps({'status':'REPRODUCED_ORIGINAL132_13_MECHANISM_AND10_REGRESSION_CHECKS',
                      'qualification':'NOT_QUALIFIED', 'returncode':0,
                      'mechanism13_exact_original_bytes':True,
                      'native132_execution':False}, sort_keys=True, indent=2))


if __name__ == '__main__': main()
