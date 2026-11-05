#!/usr/bin/env python3
"""Actual131 parser regression and exact126 symptom replays; never native EDA."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ACTUAL = ROOT / 'build/xu-score-resume-20261103/coverage131/full-soc-coverage-rdc-20261105-126'
PARENT = ROOT / 'build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116'


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); out = args.out.resolve(); out.mkdir(exist_ok=False)
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('xu132_regression_worker', HERE / 'xu_timing_coverage132.py')
    w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
    result = []
    def check(name, run):
        run(); result.append({'name': name, 'status': 'PASS'})
    def rejects(run):
        try: run()
        except (ValueError, KeyError): return
        raise AssertionError('mutant incorrectly accepted')
    def replay(worker, folder, rc, passed):
        run = subprocess.run([sys.executable, str(HERE/'reproduce126.py'), '--worker', str(worker), '--out', str(out/folder)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert run.returncode == rc, run.stderr
        data = json.loads((out/folder/'results.json').read_text()); assert data['pass'] is passed
        return data
    check('actual126_original_callsite_replay_catches_both_native_symptoms', lambda: replay(ROOT/'build/xu-timing-coverage126/xu_timing_coverage126.py', 'red-original126', 1, False))
    check('same_callsite132_resolves_both_native_symptoms', lambda: replay(HERE/'xu_timing_coverage132.py', 'green132', 0, True))
    scratch = out/'ACTUAL131_MACRO_PERIOD_WITH_ARTIFICIAL_RESET_TABLES'; scratch.mkdir()
    # The13-mechanism suite contains deliberately artificial reset/display
    # tables. Reuse them only for the independent macro/period parser seam.
    local = out/'base-local13'
    p = subprocess.run([sys.executable, str(HERE/'check_local132.py'), '--out', str(local)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, p.stderr
    for path in (local/'ARTIFICIAL_TABLES_NOT_NATIVE').iterdir():
        if path.is_file(): shutil.copyfile(path, scratch/path.name)
    for name in ['macro-mode-pins.tsv', 'macro-clock-arcs.tsv', 'period-all-status.rpt']:
        shutil.copyfile(ACTUAL/name, scratch/name)
    (scratch/'report-display-policy.tsv').write_text('field\tvalue\noriginal\tfalse\nrestored\tfalse\n')
    raw = (PARENT/'analysis-coverage.rpt').read_text()
    def analyse(): return w.analyse(scratch, raw)
    def actual_period():
        analysis = analyse(); active = analysis['active_period_review']
        assert active['status'] == 'ACTIVE_MODE_MET_DETAILS_PRESENT'
        assert active['native_detail_counts'] == {'met':416, 'untested':10416, 'violated':0}
        assert len(active['macros']) == 336 and all(row['exact_per_clock_details'] for row in active['macros'])
        assert sorted(row['active_met_details'] for row in active['macros']) == [1]*256 + [2]*80
        assert analysis['qualification'] == 'NOT_QUALIFIED'
    check('actual131_native_modes_and416_numeric_met_details_per_clock', actual_period)
    period = (scratch/'period-all-status.rpt').read_text()
    def mutate_period(old, new):
        assert old in period
        (scratch/'period-all-status.rpt').write_text(period.replace(old,new,1))
        try: rejects(analyse)
        finally: (scratch/'period-all-status.rpt').write_text(period)
    check('reject_numeric_slack_missing', lambda: mutate_period('4.03  -', 'UNKNOWN  -'))
    check('reject_native_summary_mismatch', lambda: mutate_period('10832       416', '10832       417'))
    check('reject_zero_rounded_slack_as_unproven', lambda: mutate_period('4.03  -', '0.00  -'))
    check('reject_negative_numeric_slack_against_zero_violations', lambda: mutate_period('4.03  -', '-4.03  -'))
    check('reject_overflow_nonfinite_numeric_slack', lambda: mutate_period('4.03  -', '1e999  -'))
    modes = (scratch/'macro-mode-pins.tsv').read_text()
    def clock_mutant():
        # Replace one real macro's two-clock annotation, without changing any
        # native period row. The native per-clock inventory must remain bound.
        old='xu_hfextclk xu_plldiv_envelope'; assert old in modes
        (scratch/'macro-mode-pins.tsv').write_text(modes.replace(old,'xu_hfextclk',1))
        try:
            assert analyse()['active_period_review']['status']=='NOT_PROVEN'
        finally: (scratch/'macro-mode-pins.tsv').write_text(modes)
    check('mismatched_native_clk_collection_not_promoted', clock_mutant)
    # Exact native literal netless count explains the2017 SEL-005 callsites;
    # this is evidence about pin collections, not a physical timing result.
    def native_failure_binding():
        s=json.loads((ACTUAL/'state.json').read_text())
        assert w.sha(ACTUAL/'state.json')==w.FAILED126_SHA
        modes=list(csv.DictReader((ACTUAL/'macro-mode-pins.tsv').open(),delimiter='\t'))
        assert sum(not row['nets'] for row in modes)==2016
        assert s['runs'][1]['errors'].count('Error: Nothing matched for -of_objects collection (SEL-005)')==2017
        assert s['runs'][1]['errors'][-1]=='XU_FATAL: exact pin identity missing: '+w.SINKS[1][0]+'/Q'
    check('actual131_failed_terminal_and2017_netless_callsite_count', native_failure_binding)
    payload={'status':'LOCAL132_REGRESSION_CHECKS_PASS_NOT_NATIVE_EXECUTION','qualification':'NOT_QUALIFIED',
             'worker_sha256':w.sha(HERE/'xu_timing_coverage132.py'),'checks':result,
             'local13_results':w.ident(local/'results.json'),
             'actual131_input_hashes':{name:w.ident(ACTUAL/name) for name in ('state.json','macro-mode-pins.tsv','period-all-status.rpt','installed-options.json')},
             'limits':'actual131 macro/period evidence only; reset tables explicitly artificial; no native132 execution or reset qualification'}
    (out/'results.json').write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n')
    print(json.dumps(payload,sort_keys=True,indent=2))


if __name__=='__main__': main()
