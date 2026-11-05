#!/usr/bin/env python3
"""Replay actual177/186 failure guards against verified191 original bytes only.

Local read-only diagnosis: never invokes native EDA, edits Tcl, or qualifies a
design. Both original workers' guards are frozen byte-for-byte for the replay.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
FROZEN = {
    'frozen177.py': '21cdc13892d0f64476bfe903ad2dcfa87c6ef7b90e5f5bd280167055fd736e54',
    'frozen186.py': 'ea1b78905a095e21be9f235e521aae514f0913f5f6a2180c08465982b31d4997',
    'query177.tcl.in': 'ae96d6cf0259ec97aca8aeef064badbeaf1bc5dc996aaa736f5d75cea710b6da',
    'query186.tcl.in': '33a7a3aea101f11e9848a0fcf2efb25a2be7eedc29fcc19e7bbd62ce44505a2e',
    'check171.py': 'c6c695f87e2ab2d0617ecd5ef0bd66c2162eb4af8c6ac960487e1dafa56d5ce1',
}
ROOTS = {
    '177': 's2c-own9c16-readonly-20261105-177',
    '186': 's2e-own155-coverage-readonly-20261105-186',
}


def need(value, message):
    if not value:
        raise ValueError(message)


def record(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return dict(bytes=path.stat().st_size, sha256=h.hexdigest())


def read(path):
    return json.loads(Path(path).read_text())


def load(name):
    path = HERE / 'frozen' / name
    need(record(path)['sha256'] == FROZEN[name], 'frozen source bytes changed: ' + name)
    spec = importlib.util.spec_from_file_location('xu206_' + name.replace('.', '_'), str(path))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


def status_rows(path):
    if not path.exists():
        return []
    # 186 aborted before close/flush of its first top-level report table. Its
    # actual 0-byte file is a preserved partial result, not a valid empty table.
    if path.stat().st_size == 0:
        return []
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        need(reader.fieldnames == ['report', 'catch_code', 'message'], 'query status header changed')
        rows = list(reader)
    need(all(set(x) == set(reader.fieldnames) and None not in x.values() for x in rows), 'query status malformed')
    need(len(rows) == len({x['report'] for x in rows}), 'duplicate original query report status')
    return rows


def replay(api, code, root, state):
    text = (root / 'pt.log').read_text(errors='replace')
    outcome = dict(stage=None, exception=None, returned=None)
    try:
        outcome['stage'] = 'inspect_log'
        review = api.inspect_log(text, state['returncode'])
        outcome['stage'] = 'review_reports' if code == '177' else 'review'
        statuses = api.review_reports(root, review) if code == '177' else api.review(root, review)
        outcome['returned'] = statuses
    except Exception as error:
        outcome['exception'] = str(error)
        outcome['exception_type'] = type(error).__name__
    return outcome


def inspect_case(root, code, declared):
    api = load('frozen' + code + '.py')
    case = root / ROOTS[code]
    state = read(case / 'state.json')
    need(state['status'] == getattr(api, 'FAILURE') and state['qualification'] == 'NOT_QUALIFIED',
         'expected actual failed diagnostic state: ' + code)
    need(state['native_runs'] == 1, 'expected exactly one original native attempt')
    need('returncode' in state and (case / 'pt.log').is_file(), 'original native result/log missing')
    before, after = state['inputs_before'], state['inputs_after']
    need(before == after and state['inputs_equal_before_after'] is True,
         'original input freeze receipts differ')
    need(state['runtime_before'] == state['runtime_after'], 'original runtime receipts differ')
    for artifact in state['artifacts']:
        name = Path(artifact['path']).name
        relative = ROOTS[code] + '/' + name
        if relative in declared:
            actual = record(case / name)
            need(all(actual[k] == artifact[k] for k in ['bytes', 'sha256']),
                 'original state artifact identity differs: ' + relative)
    output = read(case / ('output-manifest' + code + '.json'))
    need(output['status'] == state['status'] and output['qualification'] == 'NOT_QUALIFIED',
         'native output manifest status differs')
    for row in output['files']:
        relative = ROOTS[code] + '/' + row['name']
        if relative in declared:
            actual = record(case / row['name'])
            need(all(actual[k] == row[k] for k in ['bytes', 'sha256']),
                 'output manifest artifact differs: ' + relative)
    original = (case / 'pt.log').read_text(errors='replace').splitlines()
    signals = []
    context = None
    for number, line in enumerate(original, 1):
        if line.startswith('XU' + code + '_REPORT_BEGIN '):
            context = line.split(' ', 1)[1]
        if (line.startswith(('Error:', 'Warning:', 'XU' + code + '_FATAL:')) or
                re.search(r'\b(?:unknown command|unknown option|not found|No paths\.)', line, re.I)):
            signals.append(dict(line=number, report=context, text=line))
        if line.startswith('XU' + code + '_REPORT_END '):
            context = None
    replayed = replay(api, code, case, state)
    need(replayed['exception'] == state['error'], 'original failure guard replay differs: ' + code)
    return dict(status=state['status'], native_returncode=state['returncode'],
                native_elapsed_seconds=state['native_elapsed_seconds'],
                original_error=state['error'], guard_replay=replayed,
                original_native_signal_lines=signals,
                report_status=status_rows(case / 'query-status.tsv'),
                native_log=record(case / 'pt.log'), state=record(case / 'state.json'),
                server_input_receipts=dict(count=len(before), before_after_equal=True,
                    scope='Recorded original server receipts; server-only bodies are not locally rehashed.'),
                qualification='NOT_QUALIFIED')


def run(evidence, archive, sha256, out):
    evidence, archive, out = [Path(x).absolute() for x in [evidence, archive, out]]
    need(not out.exists(), 'fresh output root required')
    for name in FROZEN:
        need(record(HERE / 'frozen' / name)['sha256'] == FROZEN[name], 'frozen source changed: ' + name)
    checker = load('check171.py')
    checked, declared = checker.inspect(archive, sha256)
    for name, expected in declared.items():
        path = evidence / name
        need(path.is_file() and not path.is_symlink(), 'local verified payload missing or symlink: ' + name)
        actual = record(path)
        need(all(actual[k] == expected[k] for k in ['bytes', 'sha256']), 'local payload bytes differ: ' + name)
    result = dict(schema='xu-native-query-failure206-v1',
        qualification='NOT_QUALIFIED', status='LOCAL_ORIGINAL_FAILURE_GUARDS_REPRODUCED_NOT_QUALIFIED',
        archive=checked['archive'], verified_payload_files=checked['payload_files'],
        verified_payload_bytes=checked['payload_bytes'],
        cases={code: inspect_case(evidence, code, declared) for code in ROOTS},
        limitations=[
            'No native rerun, remote operation, design/model/SDC/clock edit or qualification.',
            'A failed query is not a proof of graph inequivalence, failed timing or waived checks.',
            'Native no-path reports and actual coverage gaps remain separate from query implementation errors.',
            'Original worker failure guards replayed unchanged; any follow-up requires a new namespace and controller job.',
        ])
    out.mkdir(parents=True, exist_ok=False)
    (out / 'analysis206.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print('XU206_ORIGINAL_FAILURE_GUARDS_REPRODUCED_NOT_QUALIFIED cases=177,186')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    run(args.evidence_root, args.archive, args.sha256, args.out)


if __name__ == '__main__':
    main()
