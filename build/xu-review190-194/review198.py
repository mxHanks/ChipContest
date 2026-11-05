#!/usr/bin/env python3
"""Review immutable198 deployment correction against frozen190/actual09. No remote/EDA."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'build/xu-s2c-common-power190'
PREFIX = 'build/xu-s2c-common-power190/'
D = '/storage2/2026contest/server4/s4_23usr/Desktop/'
B = D + 'xu-score-optimization-20261102/'
FM = 'dadd3bb693a3ae17bf92682d9586fa1ba07e6ead468465e07b67fa91eabea5dd'


def need(value, message):
    if not value: raise ValueError(message)


def old(name):
    return subprocess.check_output(['git', 'show', '2d61547:' + PREFIX + name], cwd=str(ROOT))


def read(path):
    return json.loads(path.read_text())


def identity(path):
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def collect(value, paths):
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value: paths.add(value['path'])
        for item in value.values(): collect(item, paths)
    elif isinstance(value, list):
        for item in value: collect(item, paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    snapshot = SOURCE / 'frozen-fm190.json'
    original = ROOT / 'build/xu-score-resume-20261103/current-evidence-export-09/candidate-formality-campaign-20261103-01/state.json'
    need(snapshot.read_bytes() == original.read_bytes() and identity(snapshot)['sha256'] == FM and snapshot.stat().st_size == 349702,
         'original09 whole snapshot must be byte-identical, never regenerated or summarized')
    oldref = json.loads(old('references190.json'))
    ref = read(SOURCE / 'references190.json')
    need(ref['fm_state_original'] == oldref['fm_state'] and ref['fm_state'] == dict(oldref['fm_state'], path=D + 'xu-s2c-common-power198/frozen-fm190.json'),
         'immutable snapshot provenance/path differs')
    need({k: ref[k] for k in oldref if k != 'fm_state'} == {k: oldref[k] for k in oldref if k != 'fm_state'},
         'unrelated map/PPA/SAIF/tool references must not change')
    before = old('power190.py').decode()
    after = (SOURCE / 'power190.py').read_text()
    oldtree = ast.parse(before); newtree = ast.parse(after)
    olddefs = {n.name: ast.dump(n) for n in oldtree.body if isinstance(n, ast.FunctionDef)}
    newdefs = {n.name: ast.dump(n) for n in newtree.body if isinstance(n, ast.FunctionDef)}
    need(set(olddefs) == set(newdefs), 'runner function set changed')
    changes = sorted(n for n in olddefs if olddefs[n] != newdefs[n])
    need(changes == ['runtime', 'source_context'], 'analysis/native/preflight/failure functions must remain exact original190')
    # All source-context guards and original read/collect operations remain;
    # add only immutable-copy identity and historical provenance in return.
    newguard = ("    need(ref['fm_state']['sha256'] == ref['fm_state_original']['sha256'] == sha(HERE / 'frozen-fm190.json') and\n"
                "         ref['fm_state']['bytes'] == ref['fm_state_original']['bytes'] == 349702 and\n"
                "         ref['fm_state']['path'] == '/storage2/2026contest/server4/s4_23usr/Desktop/xu-s2c-common-power198/frozen-fm190.json',\n"
                "         'byte-identical original09 FM state must use isolated immutable198 runtime copy')\n")
    expected = before.replace("'command-full12_190.json']\n    need(sorted", "'command-full12_190.json', 'frozen-fm190.json']\n    need(sorted")
    location = '        checked(ref[key], records)\n'
    need(expected.count(location) == 1, 'unique reference guard location required')
    expected = expected.replace(location, location + newguard)
    expected = expected.replace("native_fm_state=ref['fm_state'], passing_compare_points=42338", "native_fm_state=ref['fm_state'], archived_original_fm_state=ref['fm_state_original'], passing_compare_points=42338")
    need(after == expected, '198 runner may only add exact immutable snapshot binding/provenance')
    need((SOURCE / 'jobs190.py').read_text() == old('jobs190.py').decode().replace("ROOT = D / 'xu-s2c-common-power190'", "ROOT = D / 'xu-s2c-common-power198'"),
         'job generator may only change isolated deployment root')
    manifest = read(SOURCE / 'manifest190.json')
    need(len(manifest['runtime']) == 8 and len({x['name'] for x in manifest['runtime']}) == 8, 'eight unique runtime members required')
    frozen = []
    for row in manifest['runtime']:
        actual = identity(SOURCE / row['name'])
        need(all(actual[k] == row[k] for k in ('bytes', 'sha256')), 'new runtime identity differs')
        frozen.append(actual)
    frozen.append(identity(SOURCE / 'manifest190.json'))
    for name in ['power190.py', 'run190.py', 'jobs190.py']:
        ast.parse((SOURCE / name).read_text(), filename=name, feature_version=(3,6))
    entry_sha = identity(SOURCE / 'power190.py')['sha256']
    jobs = []
    for name in ['preflight190', 'full12_190']:
        command = read(SOURCE / ('command-' + name + '.json'))
        originalcommand = json.loads(old('command-' + name + '.json'))
        expectedcommand = dict(originalcommand, entry_sha256=entry_sha,
                               argv=[x.replace(D + 'xu-s2c-common-power190/', D + 'xu-s2c-common-power198/') for x in originalcommand['argv']])
        need(command == expectedcommand, 'command semantics/output/taskset changed')
        filename = 's2c_common_' + name + '.json'
        job = read(SOURCE / filename); oldjob = json.loads(old(filename))
        ignore = {'argv', 'frozen_inputs'}
        need({k:v for k,v in job.items() if k not in ignore} == {k:v for k,v in oldjob.items() if k not in ignore},
             'job ID/out/dependency/result/qualification changed')
        need(job['argv'] == [x.replace(D + 'xu-s2c-common-power190/', D + 'xu-s2c-common-power198/') for x in oldjob['argv']],
             'same-PID job argv changed beyond isolated runtime root')
        need(oldref['fm_state']['path'] not in {x['path'] for x in job['frozen_inputs']}, 'mutable live state remains in actual frozen inputs')
        records = {}
        for row in job['frozen_inputs']:
            need(row['path'] not in records or records[row['path']] == row, 'duplicate input identity conflicts')
            records[row['path']] = row
        need(records[ref['fm_state']['path']] == ref['fm_state'], 'snapshot not actually frozen by job')
        runtime_paths = {D+'xu-s2c-common-power198/'+row['name'] for row in manifest['runtime']} | {D+'xu-s2c-common-power198/manifest190.json'}
        need(runtime_paths.issubset(records), 'complete isolated runtime not frozen')
        for key in ['prepared57','execution57','ppa_prepared','area','verify','scope']:
            need(records[ref[key]['path']] == ref[key], 'strict original nonmutable reference omitted')
        jobs.append(dict(identity=identity(SOURCE / filename), id=job['id'], output_root=job['output_root'],
                         frozen_input_rows=len(job['frozen_inputs']), frozen_unique_input_paths=len(records),
                         repeated_identical_snapshot_rows=len(job['frozen_inputs'])-len(records)))
    r = ROOT / 'build/xu-score-resume-20261103'
    p = read(r / 'next-results-export-69/s2c-full-soc-power12-20261104-57/prepared.json')
    e = read(r / 'next-results-export-69/s2c-full-soc-power12-20261104-57/execution.json')
    f = read(original); n = next(x for x in f['runs'] if x['candidate']=='s2c')
    ppa = read(r / 'current-evidence-export-09/s2c-ppa-campaign-20261103-01/s2c/ppa/prepared.json')
    inventory = read(r / 'terminal-results-export-22/s2c-pt-macro-pin-inventory-20261103-20/inventory.json')
    groups = {k:set() for k in ['original57_inputs','prepared_contexts','own_native_records','ppa_sources','inventory_tsv','task_records']}
    groups['original57_inputs'].update(p['input_sha256'])
    collect([p['netlist'],p['analysis_sdc'],p['implementation_controls']['libraries'],p['activity'],p['mapped_sram_inventory'],e['tool']],groups['prepared_contexts'])
    collect(n,groups['own_native_records']); collect(ppa['source_files'],groups['ppa_sources']); collect(inventory['provenance']['raw_tsv'],groups['inventory_tsv'])
    for task,native in zip(p['tasks'],e['tasks']):
        collect([task['script'],task['saif'],task['canonical_saif'],task['mapped_macro_bridge'],task['measured_sram_pin_states'],native['execution']['log'],native['diagnostic']['report']],groups['task_records'])
    allpaths = set().union(*groups.values())
    need(len(allpaths)==601 and not [x for x in allpaths if Path(x).name=='state.json'] and oldref['fm_state']['path'] not in allpaths,
         'another mutable aggregate state appears in recursively consumed original inputs')
    result = dict(schema='xu-review198-snapshot-correction-v1', status='LOCAL_REVIEW_PASSED_SERVER_REGISTRATION_PENDING_NOT_QUALIFIED',
                  qualification='NOT_QUALIFIED', native_runs=0, remote_operations=0, previous_review_commit='471e798',
                  original190_commit='2d61547', snapshot=identity(snapshot), original09=identity(original),
                  changed_runner_functions=changes, unchanged_runner_functions=sorted(set(olddefs)-set(changes)),
                  frozen_runtime=frozen, jobs=jobs, original_recursive_unique_paths=601,
                  original_recursive_state_json_count=0, groups={k:sorted(v) for k,v in groups.items()},
                  limits=['Historical mutable live FM aggregate is provenance only; its SHA is never relaxed or replaced by a newer map/result.',
                          'Original601 file contents are still strictly checked on server; local enumeration is not their full byte replay.',
                          'Two identical frozen snapshot rows in each job are non-conflicting; original153 and registration wrapper accept identical records.',
                          'No new native result or qualification is claimed; failed192 deployment/guard evidence remains separate and unchanged.'])
    with args.out.open('x') as stream:
        json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(result['status'])


if __name__=='__main__':main()
