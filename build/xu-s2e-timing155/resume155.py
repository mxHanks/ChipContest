#!/usr/bin/env python3
"""Fresh own-S2e155 repair, adopting only the five completed native134 phases.

The original failed134 remains immutable. Its CSV reader limit is enlarged;
all selection rules, SDC, mapped ancestry, repair limits and FM remain frozen.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
OLD_STATE_SHA = '1ce842c387872e473352bc84cef7eac11680dad5dfd32b794b2236a69251b435'
OLD_WORKER_SHA = 'dcf5341fb9c09cb7db545fb2a208a1c204e2a14309c4741a4c5cd63c0f8364ef'
RESET_SHA = '8e50f0559a0f443cc4359b28cf55d7e0e54e6778ca8490bce4aac91b157ac33c'
OLD_NAME = 's2e-own-timing-repair-20261105-134'
NEW_NAME = 's2e-own-timing-repair-20261105-155'
PHASES = [('original-inventory', 'dc'), ('original-inventory', 'pt'), ('hold-gating', 'dc'),
          ('posthold-inventory', 'dc'), ('posthold-inventory', 'pt')]


def need(ok, text):
    if not ok:
        raise ValueError(text)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def load_original():
    need(sha(HERE/'xu_s2e_timing134.py') == OLD_WORKER_SHA and sha(HERE/'reset134.tcl') == RESET_SHA,
         'frozen134 implementation or reset method changed')
    spec = importlib.util.spec_from_file_location('xu_original134_for155', str(HERE/'xu_s2e_timing134.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def check_record(api, row):
    need(api.ident(row['path']) == row, 'original134 artifact changed: ' + row['path'])


class Adoption:
    def __init__(self, api, old, new):
        self.api, self.old, self.new = api, Path(old), Path(new)
        path = self.old/'state.json'
        need(sha(path) == OLD_STATE_SHA, 'exact failed134 terminal state required')
        self.state = api.read(path)
        state = self.state
        need(state['status'] == 'FAILED_NOT_QUALIFIED' and state['error'] == 'Error: field larger than field limit (131072)',
             'only the recorded CSV-limit failure is resumable as fresh155')
        need(state['frozen_before'] == state['frozen_after'] and state['frozen_input_errors'] == [], '134 input freeze failed')
        need([(Path(r['directory']).name, r['tool']) for r in state['runs']] == PHASES, 'five exact original phases required')
        self.records = {str(path): api.ident(path)}
        def watch(row):
            check_record(api, row)
            self.records[row['path']] = row
        for rows in [state['frozen_before'], state['hold_outputs'], state['generated']]:
            for row in rows.values():
                watch(row)
        for value in state['diagnostics'].values():
            watch(value['mapped'])
            for row in value['reports'].values():
                watch(row)
        for run in state['runs']:
            need(run['returncode'] == 0 and run['marker_count'] == 1 and run['errors'] == [], 'native134 phase failed')
            watch(run['log']); watch(run['script'])
        self.done, self.copied = [], set()
        self.actual_native = api.native

    def recheck(self):
        for row in self.records.values():
            check_record(self.api, row)

    def native(self, directory, state, kind, script, marker, env):
        directory = Path(directory)
        phase = (directory.name, kind)
        if phase not in PHASES:
            need(self.done == PHASES, 'all five adopted phases must precede new native work')
            return self.actual_native(directory, state, kind, script, marker, env)
        need(len(self.done) < len(PHASES) and PHASES[len(self.done)] == phase, 'adoption order differs')
        run = self.state['runs'][len(self.done)]
        old_dir = self.old/directory.name
        expected = Path(run['script']['path']).read_bytes().replace(str(self.old).encode(), str(self.new).encode())
        need((directory/script).read_bytes() == expected, 'fresh script differs beyond output-directory relocation')
        # Every copied output must already have a complete terminal134 receipt.
        if directory.name not in self.copied:
            for record_path in sorted(self.records):
                path = Path(record_path)
                if path.parent != old_dir or path.suffix not in ('.rpt', '.tsv', '.log', '.v', '.svf'):
                    continue
                need(not path.is_symlink(), 'symlink original output: ' + str(path))
                dest = directory/path.name
                need(not dest.exists(), 'adopted destination exists')
                shutil.copyfile(str(path), str(dest))
                need(sha(dest) == self.records[str(path)]['sha256'], 'copied native output differs')
            self.copied.add(directory.name)
        self.done.append(phase)
        adopted = dict(run, directory=str(directory), log=self.api.ident(directory/(kind+'.log')),
                       script=self.api.ident(directory/script), execution_provenance='ADOPTED_ORIGINAL134_NATIVE_PHASE_NOT_RERUN',
                       original_native_run=run)
        state['runs'].append(adopted)
        state.update(phase='ADOPTED134_' + directory.name + '_' + kind,
                     resume155=dict(original_terminal=self.api.ident(self.old/'state.json'),
                                    adopted_phases=[list(p) for p in self.done], csv_field_limit=64*1024*1024,
                                    new_native_required=['final DC', 'same-final-map PT', 'full own FM']))
        self.api.dump(self.new/'state.json', state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    api = load_original()
    old = api.BASE/OLD_NAME
    new = (args.out or api.BASE/NEW_NAME).resolve()
    need(new == api.BASE/NEW_NAME and not new.exists(), 'fresh original-host155 output required')
    frozen = {name: sha(HERE/name) for name in ['resume155.py', 'xu_s2e_timing134.py', 'reset134.tcl']}
    adoption = Adoption(api, old, new)
    api.OUT = NEW_NAME
    api.native = adoption.native
    # This affects parsing only; it neither truncates fields nor relaxes TSV checks.
    csv.field_size_limit(64*1024*1024)
    sys.argv = [str(HERE/'xu_s2e_timing134.py'), '--out', str(new)]
    try:
        api.main()
    finally:
        if (new/'state.json').exists():
            state = api.read(new/'state.json')
            try:
                adoption.recheck()
                need(all(sha(HERE/name) == digest for name, digest in frozen.items()), '155 adapter bytes changed')
                state['resume155_adapter_frozen'] = frozen
                state['resume155_adopted_originals_rechecked'] = True
                state['resume155_finished_epoch'] = time.time()
            except BaseException as exc:
                state.update(status='FAILED_NOT_QUALIFIED', resume155_integrity_error=str(exc))
                raise
            finally:
                api.dump(new/'state.json', state)


if __name__ == '__main__':
    main()
