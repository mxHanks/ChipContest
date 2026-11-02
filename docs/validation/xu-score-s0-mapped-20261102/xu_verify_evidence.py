#!/usr/bin/env python3
"""Verify xu S0 mapped-wrapper package bytes and the claims supported by them."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads((ROOT/path).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_manifest(prefix):
    manifest = read_json(prefix/'manifest.json')
    expected = {'manifest.json'}
    for item in manifest['files']:
        relative = Path(item['path'])
        require(not relative.is_absolute() and '..' not in relative.parts,
                'unsafe original manifest path')
        path = ROOT/prefix/relative
        if item['included']:
            expected.add(item['path'])
            require(path.is_file() and not path.is_symlink(), 'missing original: '+str(path))
            require(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'],
                    'original bytes differ: '+str(path))
        else:
            require(not path.exists(), 'excluded payload present: '+str(path))
    actual = {str(p.relative_to(ROOT/prefix)) for p in (ROOT/prefix).rglob('*') if p.is_file()}
    require(actual == expected, 'original file set differs: '+str(prefix))
    return len(expected)-1


def main():
    manifest = read_json(Path('evidence-sha256.json'))
    require(manifest['schema'] == 'xu-s0-mapped-evidence-sha256-v1', 'manifest schema')
    expected = set(manifest['files']) | {'evidence-sha256.json'}
    actual = set()
    for path in ROOT.rglob('*'):
        require(not path.is_symlink(), 'symlink in package: '+str(path))
        if path.is_file():
            actual.add(str(path.relative_to(ROOT)))
    require(actual == expected, 'package file set differs; missing='+str(sorted(expected-actual))+
            '; extra='+str(sorted(actual-expected)))
    for name, entry in manifest['files'].items():
        path = ROOT/name
        require(path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'],
                'package bytes differ: '+name)
    raw = Path('raw/server-qualification-01')
    count = original_manifest(raw)
    gate = read_json(raw/'gate-dc-01/replay/result.json')
    gate_state = read_json(raw/'gate-dc-01/state.json')
    require(gate['status'] == gate_state['status'] == 'PASS', 'gate process status')
    require(gate['netlist']['sha256'] == '6f90b1ce3ea180eeb59c2438ddad74aea7ac0d87690608814b2fba7384dd5971',
            'original gate netlist identity')
    require(gate_state['replay_result_sha256'] == digest(ROOT/raw/'gate-dc-01/replay/result.json'),
            'gate result state binding')
    for side in ['rtl', 'gate']:
        sim = gate['simulations'][side]
        require(sim['status'] == 'PASS' and sim['accepted'] == sim['retired'] == 17151,
                'gate accepted/retired counts')
        require(sim['traced_transfers'] == 17149, 'gate trace count')
        trace = ROOT/raw/'gate-dc-01/replay'/side/'transactions.trace'
        require(digest(trace) == sim['transaction_trace_sha256'], 'gate trace identity')
    require((ROOT/raw/'gate-dc-01/replay/rtl/transactions.trace').read_bytes() ==
            (ROOT/raw/'gate-dc-01/replay/gate/transactions.trace').read_bytes(), 'gate traces differ')
    require(all(x['returncode'] == 0 for x in gate['steps']), 'gate command failure')
    for name, value in gate['log_sha256'].items():
        require(digest(ROOT/raw/'gate-dc-01/replay'/name) == value, 'gate log binding')
    qual = read_json(raw/'wrapper-qualification-02/state.json')
    fixed = ROOT/raw/'wrapper-qualification-02/hold-fixed'
    require(qual['hold_dc']['returncode'] == qual['hold_pt']['returncode'] == 0, 'DC/PT process failure')
    require(qual['formality']['returncode'] == 1 and qual['formality']['pass_marker'], 'FM02 status changed')
    fm = (ROOT/raw/'wrapper-qualification-02/fm-original/fm.log').read_text()
    require('Verification SUCCEEDED' in fm and '13362 Passing compare points' in fm, 'FM02 proof marker')
    require("Error: unknown command 'report_verification' (CMD-005)" in fm and
            'XU_FORMALITY_SCRIPT_ERROR' in fm, 'FM02 script failure missing')
    require(re.search(r'slack \(MET\)\s+0\.00292103', (fixed/'setup-exact.rpt').read_text()), 'setup report value')
    require(re.search(r'slack \(MET\)\s+0\.06229059', (fixed/'hold-exact.rpt').read_text()), 'hold report value')
    area = (fixed/'area.rpt').read_text()
    require(re.search(r'Total cell area:\s+294418\.797328', area), 'area report value')
    require(re.search(r'Number of macros/black boxes:\s+16', area), 'macro count')
    require('No wire load specified' in area, 'area interconnect limitation')
    coverage = (fixed/'analysis-coverage.rpt').read_text()
    require(re.search(r'All Checks\s+53772\s+51056 \(\s*95%\)\s+0 \(\s*0%\)\s+2716', coverage),
            'coverage total')
    identities = read_json(Path('source-identities.json'))
    require(identities['gate_execution_main_commit'] == gate_state['main_commit'], 'execution source identity')
    require(identities['qualification_inputs'] == qual['inputs'], 'qualification input identities')
    require(identities['raw_import']['included_manifest_entries_verified'] == count, 'import file count')
    summary = read_json(Path('result.json'))
    require(summary['status'] == 'WRAPPER_EVIDENCE_ONLY_NOT_CONTEST_QUALIFIED', 'summary qualification')
    require(summary['gate01']['netlist_sha256'] == gate['netlist']['sha256'] and
            summary['gate01']['accepted_each'] == summary['gate01']['retired_each'] == 17151 and
            summary['gate01']['trace_sha256'] == gate['simulations']['gate']['transaction_trace_sha256'],
            'summary gate01 binding')
    fixed_identity = next(x for x in read_json(raw/'manifest.json')['files']
                          if x['path'] == 'wrapper-qualification-02/hold-fixed/mapped.v')
    require(summary['hold_fixed02']['netlist_sha256'] == fixed_identity['sha256'] and
            summary['hold_fixed02']['setup_slack_report_ns'] == 0.00292103 and
            summary['hold_fixed02']['hold_slack_report_ns'] == 0.06229059 and
            summary['hold_fixed02']['total_cell_area_um2'] == 294418.797328 and
            summary['hold_fixed02']['untested_checks'] == 2716,
            'summary fixed02 binding')
    require(summary['formality02']['returncode'] == 1 and
            summary['formality02']['status'] == 'PROOF_SUCCEEDED_SCRIPT_FAILED', 'summary FM02 binding')
    proof = read_json(Path('raw/prior-area-unit-proof/area-compliance.json'))
    proof_check = read_json(Path('raw/prior-area-unit-proof/area-limit-verification.json'))
    require(proof_check['area_proof_sha256'] == digest(ROOT/'raw/prior-area-unit-proof/area-compliance.json'),
            'area proof identity')
    require(proof_check['current_requirement_sha256'] == digest(ROOT/'raw/prior-area-unit-proof/area-requirement.json'),
            'area requirement identity')
    require(proof['paired_summary']['sha256'] == digest(ROOT/'raw/prior-candidate-ss-02/paired-exact-summary.json'),
            'area paired source identity')
    prior_manifest = read_json(Path('raw/prior-candidate-ss-02/manifest.json'))
    require(prior_manifest['libraries'] == qual['inputs']['libraries'], 'same-library area unit basis')
    require(proof['physical_sram']['lib_sha256'] ==
            qual['inputs']['libraries'][proof['physical_sram']['lib_path']]['sha256'], 'SRAM area unit basis')
    for cell in proof['physical_standard_cells']['checks']:
        require(abs(cell['width_microns']*cell['height_microns']-cell['library_report_cell_area']) < 1e-8,
                'standard-cell LEF area product')
    require(summary['hold_fixed02']['total_cell_area_mm2'] == summary['hold_fixed02']['total_cell_area_um2']/1e6,
            'summary area conversion')
    raw03 = Path('raw/server-qualification-03')
    import03 = identities['raw_import03']
    actual03 = {str(p.relative_to(ROOT/raw03)) for p in (ROOT/raw03).rglob('*') if p.is_file()}
    require(actual03 == {x['path'] for x in import03['member_files']}, '03 imported file set')
    for item in import03['member_files']:
        path = ROOT/raw03/item['path']
        require(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'], '03 imported bytes')
    state03 = read_json(raw03/'state.json')
    fixed03 = read_json(raw03/'gate-fixed/result.json')
    require(state03['results']['gate_fixed']['returncode'] == 0 and
            state03['results']['gate_fixed']['result_sha256'] == digest(ROOT/raw03/'gate-fixed/result.json'),
            'fixed gate03 process binding')
    require(fixed03['status'] == 'PASS' and fixed03['netlist']['sha256'] == fixed_identity['sha256'] and
            fixed03['transaction_trace_byte_identical'], 'fixed gate03 result')
    require(all(x['returncode'] == 0 for x in fixed03['steps']), 'fixed gate03 command failure')
    for name, value in fixed03['log_sha256'].items():
        require(digest(ROOT/raw03/'gate-fixed'/name) == value, 'fixed gate03 log binding')
    for side in ['rtl', 'gate']:
        sim = fixed03['simulations'][side]
        require(sim['accepted'] == sim['retired'] == 17151 and sim['traced_transfers'] == 17149 and
                sim['transaction_trace_sha256'] == gate['simulations'][side]['transaction_trace_sha256'],
                'fixed gate03 count/reported trace binding')
    for name in ['fm-original', 'fm-hold-fixed']:
        item = state03['results'][name]
        require(item['returncode'] == 0 and not item['errors'] and item['pass_marker'], 'FM03 process failed')
        log = ROOT/raw03/name/'fm.log'
        require(digest(log) == item['log_sha256'], 'FM03 log identity')
        text = log.read_text()
        require('Verification SUCCEEDED' in text and '13362 Passing compare points' in text and
                not re.search(r'^Error:', text, re.M), 'FM03 proof failed')
    require(summary['formality03']['status'] == 'PASS' and
            summary['formality03']['original_returncode'] == summary['formality03']['hold_fixed_returncode'] == 0,
            'summary FM03 binding')
    require(summary['gate_fixed03']['result_sha256'] == state03['results']['gate_fixed']['result_sha256'] and
            summary['gate_fixed03']['netlist_sha256'] == fixed03['netlist']['sha256'], 'summary gate03 binding')
    if '--git' in sys.argv:
        repo = ROOT.parents[2]
        for item in identities['gate_source_files']:
            if item['repository_relative_path'].startswith('third-party/e203_hbirdv2/'):
                git_root = repo/'third-party/e203_hbirdv2'
            else:
                git_root = repo
            data = subprocess.check_output(['git', '-C', str(git_root), 'show',
                                            item['git_commit']+':'+item['git_tree_path']])
            require(len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'],
                    'Git object differs: '+item['repository_relative_path'])
    print(json.dumps({'schema': 'xu-s0-mapped-evidence-check-v1', 'status': 'PASS',
                      'strict_package_files': len(actual), 'original_server01_files': count,
                      'gate01': 'PASS: 17151 accepted/retired each; byte-identical traces',
                      'formality02': 'PROOF_SUCCEEDED_SCRIPT_FAILED_RC1',
                      'hold_fixed02': 'DC/PT rc0; positive reported setup/hold; 2716 untested',
                      'formality03': 'PASS: original and hold-fixed, each rc0 / 13362 passing points',
                      'gate_fixed03': 'PASS: rc0; 17151 accepted/retired each; identical trace SHA reported',
                      'contest_qualified': False, 'git_objects_verified': '--git' in sys.argv}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print('XU_EVIDENCE_FAIL: '+str(error), file=sys.stderr)
        raise SystemExit(1)
