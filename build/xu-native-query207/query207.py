#!/usr/bin/env python3
"""xu207: three isolated, sequential read-only native PT compatibility queries.

Python3.6+, no network. Original177/186 sources stay byte-identical. Only exact
query API compatibility substitutions and a separately bound common190 clock
case are derived. Failure in one native case does not discard later cases.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
SUCCESS = 'EXECUTED_THREE_CASE_QUERY207_NOT_QUALIFIED'
FAILURE = 'FAIL_QUERY207_NOT_QUALIFIED'
CASES = ['s2c_original177', 's2c_common190', 's2e_final155186']
NET2C = '9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
NET2E = '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
API_SHA = {'177': '21cdc13892d0f64476bfe903ad2dcfa87c6ef7b90e5f5bd280167055fd736e54',
           '186': 'ea1b78905a095e21be9f235e521aae514f0913f5f6a2180c08465982b31d4997'}
LIMITS = [
    'NOT_QUALIFIED: query compatibility replay only; no150MHz, mapped-function or energy acceptance.',
    'Three separate native PT sessions: originalS2c57 clock method, actual190 common scope on sameS2c map, own155 S2e scope.',
    'S2c original/all-propagated and common scope timing results remain distinct; no baseline116 borrowing.',
    'Native clocks are read from one pin/port at a time; absent attributes remain explicit, never logical0 or a waiver.',
    'Native no-path/coverage gaps and real violations remain unresolved evidence regardless of query success.',
    'No source/RTL/model/SDC/clock changes, new case values/exceptions, force/init/delay or timing-check suppression.',
    'No model/library/manual body export; own177 syntactic model relationship metadata stays bounded.',
    'Actual177 model metadata records10ps/1ps and1.0 setuphold/width tokens; this does not establish correspondence to the SS DB or a same-corner SDF simulation.',
    'Fresh output root only, no resume/retry/registration; the original153 controller owns the native slot.',
    'A native timeout stops later207 cases: terminating a PT launcher alone does not prove every native descendant exited.',
]


def need(value, message):
    if not value:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def identity(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), 'regular nonsymlink input required: ' + str(path))
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    after = path.stat()
    key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    need(key(before) == key(after), 'input changed while hashing: ' + str(path))
    return dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())


def write(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    with temp.open('x') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temp), str(path))


def sha_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def bundle():
    manifest = read(HERE / 'manifest207.json')
    need(manifest['schema'] == 'xu-native-query207-manifest-v1' and manifest['qualification'] == 'NOT_QUALIFIED',
         'incorrect207 runtime manifest')
    names = set()
    for row in manifest['runtime']:
        name = row['name']
        p = PurePosixPath(name)
        need(str(p) == name and not p.is_absolute() and not {'.', '..'}.intersection(p.parts) and name not in names,
             'unsafe/duplicate207 runtime name')
        names.add(name)
        actual = identity(HERE / name)
        need(all(actual[k] == row[k] for k in ['sha256', 'bytes']), '207 runtime changed: ' + name)
    need({'query207.py', 'compat207.tcl', 'references207.json', 'job207.py'}.issubset(names), 'missing207 runtime member')
    return manifest


def load_api(code):
    name = 'readonly177.py' if code == '177' else 'coverage186.py'
    path = HERE / ('frozen' + code) / name
    need(identity(path)['sha256'] == API_SHA[code], 'original worker bytes changed')
    spec = importlib.util.spec_from_file_location('xu207_frozen' + code, str(path))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    api.bundle()
    return api


def method_from(text):
    start = text.index('set XU_CLOCK_MODE envelope\n')
    end = text.index('# Exact post-elaboration macro groups;')
    return text[start:end]


def common_context():
    ref = read(HERE / 'references207.json')
    need(ref['case_ids'] == CASES, 'three207 cases changed')
    prepared = read(HERE / 'frozen190/prepared.json')
    result = read(HERE / 'frozen190/result.json')
    inventory = read(HERE / 'frozen190/inventory/state.json')
    need(prepared['status'] == 'PREPARED_COMMON190_NOT_QUALIFIED' and prepared['requested_task_ids'] == [0] and
         result['status'] == 'EXECUTED_TASK0_COMMON190_DIAGNOSTIC_NOT_QUALIFIED' and
         result['input_sha256_before'] == result['input_sha256_after'] and
         inventory['status'] == 'EXPORTED_COMMON190_NOT_QUALIFIED' and
         inventory['input_sha256_before'] == inventory['input_sha256_after'], 'actual190 preflight provenance differs')
    context = prepared['context']
    need(context['netlist']['sha256'] == NET2C and context['analysis_sdc']['sha256'] == SDC and
         context['clock_scope']['sha256'] == SCOPE, 'common190 map/SDC/scope differs')
    need(inventory['context'] == context, 'actual190 inventory/context differs')
    methods = [method_from((HERE / 'frozen190' / x).read_text()) for x in ['inventory/export.tcl', 'task_00/power.tcl']]
    need(methods[0] == methods[1], 'actual190 power and inventory clock contracts differ')
    method = methods[0]
    need('set_propagated_clock [all_clocks]' not in method and
         'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n' in method and
         'source {' + context['clock_scope']['path'] + '}\n' in method and method.endswith('update_timing\n'),
         'actual190 common method changed')
    return ref, context, method


def derive(case_id, api, ref):
    need(case_id in CASES, 'unknown207 case')
    if case_id == 's2e_final155186':
        text, method = api.render(ref, read(api.HERE / 'targets186.json'))
        need(ref['target_context']['netlist']['sha256'] == NET2E, 'own155 map changed')
        replacements = [('$cp', 1), ('$p', 1), ('$xu_E', 1), ('$xu_D', 1)]
        code = '186'
    else:
        text, method = api.render_query(ref)
        need(ref['next_minimal_readonly_query']['target']['sha256'] == NET2C, 'own9c16 map changed')
        replacements = [('$p', 1)]
        code = '177'
    original_method = method
    if case_id == 's2c_common190':
        common_ref, context, method = common_context()
        q = ref['next_minimal_readonly_query']
        need(all(q['target'][k] == context['netlist'][k] for k in ['path', 'bytes', 'sha256']) and
             q['own_s2c_sdc'] == context['analysis_sdc'],
             'common190 must retain exact same2c target/SDC identities')
        need(text.count(original_method) == 1, 'original2c clock method count changed')
        text = text.replace(original_method, method)
    counts = {}
    for variable, expected in replacements:
        old = 'get_clocks -quiet -of_objects ' + variable
        need(text.count(old) == expected, 'exact unsupported clock query count differs: ' + old)
        text = text.replace(old, 'xu207_pin_clocks ' + variable)
        counts[old] = expected
    if code == '186':
        old = 'get_lib_pins -quiet -of_objects $p'
        need(text.count(old) == 1, 'original design-pin lib lookup count differs')
        text = text.replace(old, 'xu207_libpin $p')
        counts[old] = 1
    old = 'xu' + code + '_report annotated-check.rpt {report_annotated_check -list_annotated -list_not_annotated}'
    need(text.count(old) == 1, 'original mutual-exclusive annotated query count differs')
    text = text.replace(old, 'xu' + code + '_report annotated-check-annotated.rpt {report_annotated_check -list_annotated}\n' +
                        'xu' + code + '_report annotated-check-not-annotated.rpt {report_annotated_check -list_not_annotated}')
    counts['split_annotated_check'] = 1
    helper = (HERE / 'compat207.tcl').read_text()
    pivot = 'set xu_status [open query-status.tsv w]\n'
    need(text.count(pivot) == 1, 'original query status pivot differs')
    text = text.replace(pivot, helper + '\n' + pivot)
    close = 'close $xu_status\n'
    need(text.count(close) == 1, 'original status close count differs')
    text = text.replace(close, 'close $xu207_clock_map\nclose $xu207_lib_map\n' + close)
    need('get_clocks -quiet -of_objects' not in text and
         'report_annotated_check -list_annotated -list_not_annotated' not in text, 'unsupported query remains')
    need(text.count(method) == 1, 'derived native clock contract changed')
    return text, dict(case_id=case_id, original_worker_sha256=API_SHA[code],
        original_clock_method_sha256=sha_text(original_method), clock_method_sha256=sha_text(method),
        clock_method=method, compatibility_substitutions=counts, helper_sha256=sha_text(helper),
        original_completion_marker_retained=api.MARKER, qualification='NOT_QUALIFIED')


def common_inputs():
    ref, context, method = common_context()
    rows = []
    for expected in ref['common190']:
        local = identity(HERE / 'frozen190' / expected['name'])
        actual = identity(expected['path'])
        need(all(local[k] == expected[k] == actual[k] for k in ['sha256', 'bytes']), 'actual190 source differs')
        rows.append(actual)
    # clock_scope in original190 context lacks a bytes field; check its exact
    # actual content hash, keeping the independently recorded native path.
    scope = identity(context['clock_scope']['path'])
    need(scope['sha256'] == SCOPE, 'common native scope changed')
    rows.append(scope)
    return rows


def clock_mapping_review(out, expected_objects=None):
    path = out / 'pin-clocks207.tsv'
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        need(reader.fieldnames == ['request', 'pin_handle', 'pin_name', 'pin_class', 'attribute_status',
                                  'raw_attribute', 'clock_handle', 'clock_name', 'clock_class', 'diagnostics'],
             'native clock mapping header changed')
        rows = list(reader)
    need(rows and all(None not in x and None not in x.values() for x in rows), 'native clock mapping missing/malformed')
    need(all(x['pin_class'] in ('pin', 'port') and x['pin_handle'] and x['pin_name'] for x in rows), 'invalid native pin identity')
    need(all(x['attribute_status'] in ('ABSENT_OR_EMPTY', 'NATIVE_CLOCK_COLLECTION') for x in rows), 'native clocks mapping contains unresolved API failure')
    for x in rows:
        if x['attribute_status'] == 'NATIVE_CLOCK_COLLECTION':
            need(x['clock_class'] == 'clock' and x['clock_handle'] and x['clock_name'] and x['raw_attribute'], 'invalid native clock identity')
        else:
            need(not any(x[k] for k in ['clock_handle', 'clock_name', 'clock_class', 'raw_attribute']), 'absent clocks must not invent clock values')
    if expected_objects is not None:
        need(set(expected_objects).issubset({x['pin_name'] for x in rows}), 'not every frozen186 native target has clock metadata')
    return dict(rows=len(rows), unique_pins=len({x['pin_name'] for x in rows}),
                absent_or_empty_rows=sum(x['attribute_status'] == 'ABSENT_OR_EMPTY' for x in rows),
                mapped_clock_names=sorted({x['clock_name'] for x in rows if x['clock_name']}), qualification='NOT_QUALIFIED')


def library_mapping_review(out):
    with (out / 'static-metadata.tsv').open(newline='') as stream:
        metadata = list(csv.DictReader(stream, delimiter='\t'))
    expected = {x['object']: x['lib_pin'] for x in metadata if x['class'] == 'pin'}
    with (out / 'pin-lib207.tsv').open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        need(reader.fieldnames == ['pin_handle', 'pin_name', 'owner_handle', 'owner_name', 'libcell_handle',
                                  'libcell_name', 'libpin_handle', 'libpin_name'], 'native library mapping header changed')
        rows = list(reader)
    need(len(rows) == len(expected) and {x['pin_name'] for x in rows} == set(expected),
         'native library mappings must cover every exact186 design pin once')
    need(all(None not in x and all(x.values()) and x['libpin_name'] == expected[x['pin_name']] for x in rows),
         'native library object identity differs from original186 metadata')
    return dict(exact_design_pin_count=len(rows), actual_libcell_count=len({x['libcell_name'] for x in rows}),
                qualification='NOT_QUALIFIED')


def run_case(case_id, out, timeout):
    code = '186' if case_id == 's2e_final155186' else '177'
    out.mkdir()
    state = dict(schema='xu-native-query207-case-v1', case_id=case_id, status='PREPARING_NOT_QUALIFIED',
                 qualification='NOT_QUALIFIED', pid=os.getpid(), started_utc=now(), native_runs=0)
    write(out / 'state.json', state)
    before = None
    api = None
    try:
        api = load_api(code)
        ref = read(api.HERE / ('references' + code + '.json'))
        before = api.checked_inputs(ref)
        if case_id == 's2c_common190':
            state['common_inputs_before'] = common_inputs()
        if code == '186':
            p = ref['preflight']
            api.verify_provenance(ref, read(p['prepared']['path']), read(p['execution']['path']),
                                  read(p['result']['path']), read(ref['target_context']['state']['path']))
        state['inputs_before'] = before
        query, derived = derive(case_id, api, ref)
        (out / 'query.tcl').write_text(query)
        (out / 'own-clock-method.tcl').write_text(derived['clock_method'])
        write(out / 'derivation207.json', derived)
        if code == '177':
            write(out / 'model-relations.json', api.model_summary(Path(ref['model']['path']).read_bytes()))
        command = [ref['pt']['path'], '-f', 'query.tcl']
        env = os.environ.copy()
        env['SYNOPSYS_LC_ROOT'] = ref['library_compiler_root']
        env['PATH'] = ref['library_compiler_root'] + '/bin:' + env.get('PATH', '')
        state.update(status='RUNNING_NATIVE_NOT_QUALIFIED', native_runs=1, command=command,
                     query=identity(out / 'query.tcl'), clock_method_sha256=derived['clock_method_sha256'])
        write(out / 'state.json', state)
        start = time.monotonic()
        with (out / 'pt.log').open('wb') as log:
            proc = subprocess.Popen(command, cwd=str(out), env=env, stdout=log, stderr=subprocess.STDOUT)
            state['native_pid'] = proc.pid
            write(out / 'state.json', state)
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                state['native_timeout'] = True
                write(out / 'state.json', state)
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait()
                raise ValueError('207 native case timeout; original partial output retained; no retry')
        state.update(returncode=rc, native_elapsed_seconds=time.monotonic() - start)
        log_review = api.inspect_log((out / 'pt.log').read_text(errors='replace'), rc)
        state['log_review'] = log_review
        state['report_status'] = api.review_reports(out, log_review) if code == '177' else api.review(out, log_review)
        state['optional_report_gaps'] = [x for x in state['report_status'] if x['catch_code'] != 0]
        expected = None
        if code == '186':
            targets = read(api.HERE / 'targets186.json')
            state['native_metadata_review'] = api.review_metadata(out, targets)
            expected = [x['name'] for x in targets['objects']]
            state['library_mapping_review'] = library_mapping_review(out)
        else:
            target = ref['next_minimal_readonly_query']['target_pt_cell_candidate']
            expected = [target + '/CK', target + '/RDN']
        state['clock_mapping_review'] = clock_mapping_review(out, expected)
        state['status'] = 'EXECUTED_CASE207_NOT_QUALIFIED'
    except BaseException as exc:
        state.update(status='FAIL_CASE207_NOT_QUALIFIED', error=str(exc), traceback=traceback.format_exc())
    finally:
        if before is not None and api is not None:
            try:
                state['inputs_after'] = api.checked_inputs(ref)
                need(before == state['inputs_after'], 'original native inputs changed during207 case')
                if case_id == 's2c_common190':
                    state['common_inputs_after'] = common_inputs()
                    need(state['common_inputs_before'] == state['common_inputs_after'], 'common190 sources changed during207 case')
                state['inputs_equal_before_after'] = True
            except BaseException as exc:
                state.update(status='FAIL_CASE207_NOT_QUALIFIED', identity_error=str(exc), inputs_equal_before_after=False)
        state['finished_utc'] = now()
        state['artifacts'] = [identity(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'state.json']
        write(out / 'state.json', state)
    return state


def output_manifest(out, status):
    files = []
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name != 'output-manifest207.json':
            row = identity(path)
            files.append(dict(name=str(path.relative_to(out)), bytes=row['bytes'], sha256=row['sha256']))
    write(out / 'output-manifest207.json', dict(schema='xu-native-query207-output-v1', status=status,
        qualification='NOT_QUALIFIED', vendor_bodies_exported=False, files=files,
        file_count=len(files), total_bytes=sum(x['bytes'] for x in files)))


def run(out, timeout):
    out = Path(out).absolute()
    need(not out.exists() and not out.is_symlink(), 'fresh207 output root required; no restart/resume')
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='xu-native-query207-state-v1', status='PREPARING_QUERY207_NOT_QUALIFIED',
                 qualification='NOT_QUALIFIED', pid=os.getpid(), started_utc=now(), cases=[], limitations=LIMITS)
    write(out / 'state.json', state)
    runtime = None
    try:
        manifest = bundle()
        runtime = [identity(HERE / x['name']) for x in manifest['runtime']] + [identity(HERE / 'manifest207.json')]
        state['runtime_before'] = runtime
        state['status'] = 'RUNNING_QUERY207_NOT_QUALIFIED'
        for case_id in CASES:
            state['current_case'] = case_id
            write(out / 'state.json', state)
            # run_case catches its own native/setup failure, allowing the next
            # independent case to run. Runtime integrity remains a root guard.
            item = run_case(case_id, out / case_id, timeout)
            state['cases'].append(dict(case_id=case_id, status=item['status'],
                native_runs=item['native_runs'], result_state=str(out / case_id / 'state.json'),
                error=item.get('error'), returncode=item.get('returncode'),
                native_timeout=item.get('native_timeout', False)))
            write(out / 'state.json', state)
            need([identity(x['path']) for x in runtime] == runtime, '207 runtime changed during native cases')
            if item.get('native_timeout'):
                # pt_shell may be a launcher for native descendants. A timeout
                # cannot release this worker's internal slot merely because
                # that launcher exited; stop, leave original evidence, and let
                # original153's native process scan gate any later job.
                state['stopped_after_native_timeout'] = True
                state['remaining_cases_not_run'] = CASES[len(state['cases']):]
                break
        complete = len(state['cases']) == 3 and not state.get('stopped_after_native_timeout')
        complete = complete and all(x['status'] == 'EXECUTED_CASE207_NOT_QUALIFIED' and
                                    x['native_runs'] == 1 and not x['native_timeout'] for x in state['cases'])
        state['status'] = SUCCESS if complete else FAILURE
    except BaseException as exc:
        state.update(status=FAILURE, error=str(exc), traceback=traceback.format_exc())
    finally:
        if runtime is not None:
            try:
                state['runtime_after'] = [identity(x['path']) for x in runtime]
                need(state['runtime_after'] == runtime, '207 runtime changed before/after')
                state['runtime_equal_before_after'] = True
            except BaseException as exc:
                state.update(status=FAILURE, runtime_equal_before_after=False, identity_error=str(exc))
        state['finished_utc'] = now()
        state['native_runs'] = sum(x['native_runs'] for x in state['cases'])
        write(out / 'state.json', state)
        output_manifest(out, state['status'])
    print('XU207_TERMINAL ' + state['status'], flush=True)
    return 0 if state['status'] == SUCCESS else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--describe', action='store_true')
    args = parser.parse_args()
    if args.describe:
        bundle()
        for code in ['177', '186']:
            load_api(code)
        common_context()
        print(json.dumps(dict(schema='xu-native-query207-description-v1', qualification='NOT_QUALIFIED',
            status='DESCRIBED_NOT_RUN_NOT_QUALIFIED', case_ids=CASES, result_state='state.json',
            success=SUCCESS, failure=FAILURE, native=True, max_native_sessions_concurrent=1,
            fresh_output_required=True, native_sessions_sequential=3, limitations=LIMITS), sort_keys=True, indent=2))
        return 0
    need(args.out is not None and args.out.is_absolute(), 'absolute fresh207 --out required')
    need(1 <= args.timeout <= 7200, 'per-case native timeout must be1..7200 seconds')
    return run(args.out, args.timeout)


if __name__ == '__main__':
    sys.exit(main())
