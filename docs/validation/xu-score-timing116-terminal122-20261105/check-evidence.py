#!/usr/bin/env python3
"""Verify actual116 terminal original bytes. No EDA, remote access, or waiver."""
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
PREFIX = 'full-soc-timing-combined-20261105-116/'
ARCHIVE = 'xu-server-terminal-20261105-122.tar.xz'
ARCHIVE_SHA = '654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50'
STATE_SHA = '7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f'
MAPPED_SHA = '16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292'
SVF_SHA = '2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def ident(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def rows(data):
    return list(csv.DictReader(io.StringIO(data.decode('utf-8')), delimiter='\t'))


def main():
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    for name, record in manifest['files'].items():
        need(ident((HERE / name).read_bytes()) == record, 'local delivery differs: ' + name)
    archive = (HERE / ARCHIVE).read_bytes()
    need(ident(archive) == dict(bytes=1283388, sha256=ARCHIVE_SHA), 'original122 archive differs')
    payload = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:xz') as source:
        for member in source:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in payload, 'unsafe/duplicate archive member')
            payload[member.name] = source.extractfile(member).read()
    original = json.loads(payload.pop('manifest.json').decode('utf-8'))
    need(original == manifest['archive_original_manifest'], 'original manifest differs')
    need(len(original) == len(payload) == 121 and sum(map(len, payload.values())) == 37978683,
         'original payload count/bytes differ')
    for record in original:
        need(ident(payload[record['path']]) == {key: record[key] for key in ('bytes', 'sha256')},
             'original payload differs: ' + record['path'])
    get = lambda name: payload[PREFIX + name]
    text = lambda name: get(name).decode('utf-8')
    need(ident(get('state.json'))['sha256'] == STATE_SHA, 'actual116 final state differs')
    state = json.loads(text('state.json'))
    need(state['status'] == 'EXECUTED_SAME_MAPPED_DC_PT_AND_FULL_FM_NOT_QUALIFIED' and
         state['qualification'] == 'NOT_QUALIFIED', 'wrong actual116 terminal status')
    need(state['frozen_inputs_unchanged'] is True and not state['frozen_after_observation_errors'] and
         state['frozen_before'] == state['frozen_after'] and len(state['frozen_before']) == 274,
         'server original input freeze differs')
    available = 0
    for path, record in state['frozen_before'].items():
        need(record['path'] == path and record['bytes'] >= 0 and len(record['sha256']) == 64,
             'invalid original input receipt')
        suffix = path.split('/xu-score-optimization-20261102/', 1)[-1]
        if suffix in payload:
            need(ident(payload[suffix]) == {key: record[key] for key in ('bytes', 'sha256')},
                 'available original input differs: ' + suffix)
            available += 1
    need(ident(get('mapped.v')) == {key: state['final_mapped'][key] for key in ('bytes', 'sha256')} and
         state['final_mapped']['sha256'] == MAPPED_SHA, 'same final mapped differs')
    need(ident(get('repair.svf')) == {key: state['final_svf'][key] for key in ('bytes', 'sha256')} and
         state['final_svf']['sha256'] == SVF_SHA, 'same final SVF differs')
    run_checks = []
    markers = [('dc', 'repair.tcl', 'XU_COMBINED116_DC_DONE_NOT_QUALIFIED'),
               ('pt', 'sta.tcl', 'XU_COMBINED116_PT_DIAGNOSTIC_DONE_NOT_QUALIFIED'),
               ('fm', 'verify.tcl', 'XU_FULL_SOC_FORMALITY_PASS')]
    need([r['label'] for r in state['runs']] == ['dc', 'pt', 'fm'], 'native run ordering differs')
    for run, (label, script, marker) in zip(state['runs'], markers):
        need(run['returncode'] == 0 and not run['errors'] and run['marker_count'] == 1,
             'native receipt failed: ' + label)
        need(ident(get(label + '.log')) == {key: run['log'][key] for key in ('bytes', 'sha256')} and
             ident(get(script)) == {key: run['script'][key] for key in ('bytes', 'sha256')},
             'native actual script/log differs: ' + label)
        log = text(label + '.log')
        need(sum(line.strip() == marker for line in log.splitlines()) == 1 and
             not re.search(r'^\s*(?:Error:|Error-|XU_FATAL:|XU_FULL_SOC_FORMALITY_FAIL|XU_FULL_SOC_FORMALITY_SCRIPT_ERROR)', log, re.M),
             'native original log failed: ' + label)
        run_checks.append(dict(label=label, returncode=0, marker_count=1,
                               log_sha256=run['log']['sha256'], script_sha256=run['script']['sha256']))
    fm = text('fm.log')
    need(sum(line.strip() == 'Verification SUCCEEDED' for line in fm.splitlines()) == 1 and
         re.findall(r'^\s*(\d+) Passing compare points\s*$', fm, re.M) == ['41462'],
         'native full FM success/result differs')
    verify = text('verify.tcl')
    chain = re.findall(r'\{([^{}]+\.svf)\}', verify.split('read_db ', 1)[0])
    need(chain == state['svf_chain'] and len(chain) == 10 and
         'read_verilog -i {' + state['final_mapped']['path'] + '}' in verify,
         'own final implementation/SVF chain differs')
    need('set hdlin_unresolved_modules black_box' in verify and 'set synopsys_auto_setup true' in verify,
         'original FM interpretation scope differs')
    for group in ('reports', 'audits'):
        for name, record in state[group].items():
            need(ident(get(name)) == {key: record[key] for key in ('bytes', 'sha256')},
                 'terminal report/audit differs: ' + name)
    rounds = rows(get('cleanup-rounds.tsv'))
    need([[int(r[k]) for k in ('round', 'frontier', 'removed', 'upstream')] for r in rounds] ==
         [[0,17,17,36],[1,36,17,33],[2,33,7,15],[3,15,4,10],[4,10,2,5],[5,5,0,0]],
         'bounded cleanup rounds differ')
    removed, preflight = rows(get('removed-cells.tsv')), rows(get('cleanup-preflight.tsv'))
    need(len(removed) == 47 and len({r['cell'] for r in removed}) == 47 and
         {r['cell'] for r in preflight} == {r['cell'] for r in removed} and
         all(r['is_sequential'] == 'false' and r['owner_instance_count'] == '1' and
             r['output'] == r['leaf_connections'] for r in preflight), 'native cleanup proof differs')
    inserted = rows(get('inserted-reset-cells.tsv'))
    need(len(inserted) == 40 and len({r['cell'] for r in inserted}) == 40,
         'native reset insertion count differs')
    reset_pins = {r['endpoint'] for r in inserted}
    need(len(reset_pins) == 5 and all(sum(r['endpoint'] == p for r in inserted) == 8 for p in reset_pins),
         'five exact reset chains differ')
    slacks = {}
    for name in ('setup', 'hold'):
        values = re.findall(r'^\s*slack \((\w+)\)\s+([-+\d.]+)', text(name + '.rpt'), re.M)
        need(len(values) == 50 and all(status == 'MET' for status, _ in values), 'reported slack differs')
        slacks[name] = min(float(value) for _, value in values)
    need(slacks == dict(setup=0.0, hold=0.00601495), 'actual minimum slack differs')
    need(not re.search(r'\b(?:max_capacitance|min_capacitance)\b', text('constraints.rpt')),
         'actual electrical violator sections appeared')
    coverage = {}
    for name, total, met, violated, untested in re.findall(
            r'^(setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold)\s+'
            r'(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)', text('analysis-coverage.rpt'), re.M):
        coverage[name] = dict(zip(('total', 'met', 'violated', 'untested'), map(int, (total, met, violated, untested))))
    need(len(coverage) == 10 and sum(r['total'] for r in coverage.values()) == 294473 and
         sum(r['met'] for r in coverage.values()) == 267349 and
         sum(r['violated'] for r in coverage.values()) == 0 and
         sum(r['untested'] for r in coverage.values()) == 27124,
         'coverage total differs')
    reset = rows(get('reset-paths.tsv'))
    need(len(reset) == 16 and sum(r['check'] == 'recovery' and r['source_kind'] == 'HF_RESET' and
         r['count'] == '0' and r['worst_slack'] == 'UNKNOWN' and r['status'] == 'NO_PATH_UNKNOWN' for r in reset) == 5,
         'HF missing recovery diagnostics differ')
    need(state['reset_paths'] == text('reset-paths.tsv') and state['timing'] == text('timing-slack.tsv'),
         'actual terminal TSV receipts differ')
    observation = json.loads(payload['live122-observation.json'].decode('utf-8'))
    own = [r for r in observation['observed'] if r['prefix'] == PREFIX.rstrip('/')]
    need(len(own) == 1 and own[0]['pid_alive_now'] is False and own[0]['status'] == state['status'],
         'terminal PID observation differs')
    result = dict(status='ACTUAL116_TERMINAL_BYTES_SAME_MAPPED_DC_PT_FM_VERIFIED', qualification='NOT_QUALIFIED',
        archive_files=121, archive_payload_bytes=37978683, frozen_input_receipts=274,
        frozen_input_bodies_present_in_this_archive=available,
        native_runs=run_checks, passing_compare_points=41462, mapped_sha256=MAPPED_SHA, svf_sha256=SVF_SHA,
        cleanup_removed_cells=47, cleanup_rounds=rounds, inserted_reset_cells=40,
        global_reported_slacks_ns=slacks, coverage=coverage, hf_recovery_missing_paths=5,
        outstanding='27124 untested; reset/RDC/conditional pulses/UART; baseline116 is not S2e or power qualification',
        companion120_scope='Original bytes verified only; S2e120 semantic review belongs to its separate archive')
    expected = json.loads((HERE / 'analysis116.json').read_text())
    need(expected == result, 'saved independent116 analysis differs')
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
