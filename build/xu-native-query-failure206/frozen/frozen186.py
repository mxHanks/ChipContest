#!/usr/bin/env python3
"""Read-only ownS2e155 native coverage diagnosis for original153 single slot.

Python3.6+ standard library only. Foreground, fresh root, no design/SDC/model/TB
writes. This worker does not register or launch anything outside its one PT run.
"""
import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
FROZEN177 = '21cdc13892d0f64476bfe903ad2dcfa87c6ef7b90e5f5bd280167055fd736e54'
NET = '3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
SUCCESS = 'EXECUTED_OWN_S2E_COVERAGE186_NOT_QUALIFIED'
FAILURE = 'FAIL_OWN_S2E_COVERAGE186_NOT_QUALIFIED'
MARKER = 'XU_OWN_S2E_COVERAGE186_COMPLETE_NOT_QUALIFIED'
RUNTIME = {'coverage186.py', 'frozen177.py', 'frozen-own155-sta.tcl', 'query186.tcl.in', 'references186.json', 'targets186.json', 'job186.py'}
LIMITS = [
    'NOT_QUALIFIED: native read-only coverage diagnosis, not full150MHz closure, functional acceptance or contest energy.',
    'Only final own1553440182e netlist, own404c7d SDC and45037c audit-forward scope; no S2c57 all-propagated or baseline116 inheritance.',
    '9219 no_clock checks are min_pulse_width: 8766RDN(low)+429SDN(low)+24UART E(high); not9219 functional CK pins without clocks.',
    'All9219 exact pulse pins get native metadata; deep connectivity/paths are limited to frozen UART/PMU/HF/GPIO/PLIC targets.',
    'Absent or unsupported case/constant attributes are explicit sentinel values; absence never means logical0 or functional disabling.',
    'Static library/SDC relations do not establish UART E runtime inactivity, mapped knownness, conditional-arc sensitization or reset pulse qualification.',
    'No-path timing reports remain unresolved. Five directed HF queries are not identical to five unknown coverage checks.',
    'Native arc identity is owner/index/from/to only. Native timing_arc full_name is never read.',
    'No design, clock, SDC, case, false-path, model or TB changes, force/init, inserted delay, timing-check suppression or model/library body export.',
]


def need(value, message):
    if not value:
        raise ValueError(message)


def utility():
    path = HERE / 'frozen177.py'
    need(path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == FROZEN177,
         'byte-identical177 identity/atomic-write utility required')
    spec = importlib.util.spec_from_file_location('xu_frozen177_for186', str(path))
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


base = utility()
identity, read, write = base.identity, base.read, base.write


def bundle():
    manifest = read(HERE / 'manifest186.json')
    need(manifest['schema'] == 'xu-s2e-coverage186-manifest-v1' and manifest['qualification'] == 'NOT_QUALIFIED', 'wrong runtime manifest')
    need(len(manifest['runtime']) == len(RUNTIME) and {x['name'] for x in manifest['runtime']} == RUNTIME,
         'runtime manifest must cover every exact executable/data member once')
    for row in manifest['runtime']:
        name = row['name']
        need(Path(name).name == name, 'unsafe runtime name')
        p = HERE / name
        need(p.is_file() and not p.is_symlink(), 'missing/symlink runtime: ' + name)
        actual = identity(p)
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'], 'runtime changed: ' + name)
    return manifest


def checked_inputs(ref):
    actuals = []
    for expected in ref['server_inputs']:
        actual = identity(expected['path'])
        need(actual['sha256'] == expected['sha256'] and actual['bytes'] == expected['bytes'],
             'own155 input bytes differ: ' + expected['path'])
        actuals.append(actual)
    need(Path(ref['library_compiler_root']).is_dir(), 'same library compiler installation missing')
    return actuals


def verify_provenance(ref, prepared, execution, result, state155):
    target = ref['target_context']
    need(target['netlist']['sha256'] == NET and target['constraints']['sha256'] == SDC and
         target['clock_scope']['sha256'] == SCOPE and target['state']['sha256'] ==
         '3474d4aaf4801ead290534a25fefcb6cab8d4613ff2191edef71900f7fec6952', 'only actual own155 target permitted')
    need(prepared['schema'] == 'xu-s2e-final-power166-prepared-v1' and prepared['status'] == 'PREPARED166_NOT_QUALIFIED' and
         prepared['target_mapped_context'] == target and prepared['netlist'] == target['netlist'] and
         prepared['analysis_sdc'] == target['constraints'] and prepared['clock_scope'] == target['clock_scope'],
         'original178 task0 prepared target identity differs')
    for data in (execution, result):
        need(data['status'] == 'EXECUTED_TASK0_DIAGNOSTIC_NOT_QUALIFIED' and data['requested_task_ids'] == [0] and
             data['input_sha256_before'] == data['input_sha256_after'] and data['qualification'] == 'NOT_QUALIFIED',
             'original own155 task0 preflight terminal/freeze differs')
    need(execution['target_context'] == target and result['target_mapped_context'] == target,
         'preflight/result own155 context differs')
    need(state155['status'] == 'EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED' and
         state155['formal_passing'] == 42338 and state155['frozen_before'] == state155['frozen_after'] and
         not state155['frozen_input_errors'] and state155['final_outputs'][target['netlist']['path']]['sha256'] == NET,
         'own155 native DC/PT/fullFM provenance differs')


def own_setup(ref, original):
    need(hashlib.sha256(original).hexdigest() == ref['original_sta']['sha256'], 'original own155 STA template changed')
    text = original.decode('ascii')
    start = text.index('set XU_CLOCK_MODE envelope\n')
    end = text.index('# Exact post-elaboration macro groups;')
    method = text[start:end]
    need(method.rstrip() + '\n' == ref['target_context']['analysis_clock_contract'], 'own155 original clock method mismatch')
    need('set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\n' in method and 'set_propagated_clock [all_clocks]' not in method,
         'own155 method may not inherit S2c57 all-propagated clocks')
    libs = [x['path'] for x in ref['libraries']]
    setup = 'set_app_var link_path [list * ' + ' '.join('{' + x + '}' for x in libs) + ']\n'
    setup += 'redirect -file tool-version.rpt {puts $sh_product_version}\n'
    setup += 'read_verilog {' + ref['target_context']['netlist']['path'] + '}\n'
    setup += 'if {![link_design {xu_soc_ppa_top}]} {error {own155186 link failed}}\n'
    return setup + method, method


def literal(value):
    need(isinstance(value, str) and not any(c in value for c in '{}\r\n\t\\'), 'unsafe frozen literal')
    return '{' + value + '}'


def tcl_rows(rows):
    return '[list ' + ' '.join('[list ' + ' '.join(literal(str(x)) for x in row) + ']' for row in rows) + ']'


def render(ref, targets):
    need(targets['schema'] == 'xu-s2e-coverage186-targets-v1' and targets['pulse_counts'] == {'E_high': 24, 'RDN_low': 8766, 'SDN_low': 429},
         'exact own155185 minpulse categories differ')
    rows = targets['objects']
    need(len(rows) == len({x['name'] for x in rows}) and sum('pulse_' in x['role'] for x in rows) == 9219,
         'duplicate/missing exact pulse target names')
    need(len(targets['uart_pairs']) == 24 and len(targets['reset_queries']) == 5 and len(targets['plic_pins']) == 3,
         'critical own155 target counts differ')
    for x in rows:
        literal(x['role']); literal(x['name'])
    setup, method = own_setup(ref, (HERE / 'frozen-own155-sta.tcl').read_bytes())
    replacements = [('@OWN_SETUP@', setup), ('@EXACT_TARGETS@', tcl_rows((x['role'], x['name']) for x in rows)),
                    ('@UART_PAIRS@', tcl_rows((i, x['E'], x['D']) for i, x in enumerate(targets['uart_pairs']))),
                    ('@RESET_QUERIES@', tcl_rows((i, x['source_object'], x['target_pin']) for i, x in enumerate(targets['reset_queries']))),
                    ('@PLIC_PINS@', tcl_rows((i, x) for i, x in enumerate(targets['plic_pins'])))]
    text = (HERE / 'query186.tcl.in').read_text()
    for token, value in replacements:
        need(text.count(token) == 1, 'query placeholder differs: ' + token)
        text = text.replace(token, value)
    need(not re.search(r'@[A-Z_]+@', text), 'unexpanded query placeholder')
    return text, method


def inspect_log(text, code):
    need(code == 0 and len(re.findall(r'^' + MARKER + r'$', text, re.M)) == 1, 'native returncode/unique actual marker differs')
    need('Version T-2022.03-SP5-1' in text and not re.search(r'^XU186_FATAL:', text, re.M), 'same PT version or mandatory native step failed')
    context = None
    errors = []
    for line in text.splitlines():
        if line.startswith('XU186_REPORT_BEGIN '):
            context = line.split(' ', 1)[1]
        elif line.startswith('XU186_REPORT_END '):
            context = None
        elif line.startswith('Error:'):
            errors.append(dict(report=context, line=line))
    return dict(marker_count=1, native_warning_count=len(re.findall(r'^Warning:', text, re.M)), errors=errors)


def required_names():
    names = {'relevant-library.rpt', 'relevant-arcs.rpt', 'check-timing.rpt', 'analysis-coverage.rpt', 'constraints.rpt',
             'clocks.rpt', 'case-analysis.rpt', 'disabled-timing.rpt', 'exceptions.rpt', 'units.rpt'}
    names.update('uart-{}-native.rpt'.format(i) for i in range(24))
    names.update('reset-{}-native.rpt'.format(i) for i in range(5))
    names.update('reset-{}-{}-unfiltered.rpt'.format(i, kind) for i in range(5)
                 for kind in ('HF-recovery', 'HF-removal', 'any-recovery', 'any-removal'))
    names.update('plic-{}-load.rpt'.format(i) for i in range(3))
    return names


def review(out, log):
    lines = (out / 'query-status.tsv').read_text().splitlines()
    need(lines and lines[0] == 'report\tcatch_code\tmessage', 'native report status table absent')
    rows = [line.split('\t', 2) for line in lines[1:]]
    need(all(len(x) == 3 and x[1] in ('0', '1') for x in rows) and len(rows) == len({x[0] for x in rows}), 'native report status malformed/duplicate')
    required = required_names()
    need(required.issubset({x[0] for x in rows if x[1] == '0'}), 'required native query unavailable')
    files = required | {'static-metadata.tsv', 'driver-load.tsv', 'net-startpoints.tsv', 'design-arcs.tsv', 'library-arcs.tsv', 'tool-version.rpt', 'attribute-diagnostics.tsv'}
    for name in files:
        p = out / name
        need(p.is_file() and p.stat().st_size > 0, 'native required report missing/empty: ' + name)
        need(not re.search(r'^Error:', p.read_text(errors='replace'), re.M), 'native required report emitted Error: ' + name)
    need(not any(x['report'] is None or x['report'] in required for x in log['errors']), 'required/unattributed native Error retained')
    return [dict(report=x[0], catch_code=int(x[1]), message=x[2]) for x in rows]



def table(path, required_fields=()):
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        need(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)) and
             set(required_fields).issubset(reader.fieldnames), 'native table header differs: ' + path.name)
        rows = list(reader)
    need(all(None not in x and None not in x.values() for x in rows), 'malformed native table: ' + path.name)
    return rows


def review_metadata(out, targets):
    rows = table(out / 'static-metadata.tsv', ('role', 'object', 'class', 'owner', 'ref', 'lib_pin',
                                           'min_pulse_width_high', 'min_pulse_width_low'))
    expected = {x['name']: x['role'] for x in targets['objects']}
    need(len(rows) == len(expected) and {x['object'] for x in rows} == set(expected),
         'native metadata must contain all9257 unique frozen exact objects')
    counts = Counter()
    width_gaps = Counter()
    refs = Counter()
    for row in rows:
        need(row['role'] == expected[row['object']], 'native metadata frozen role mismatch')
        need(row['class'] in ('pin', 'port'), 'native object class differs')
        if row['class'] == 'pin':
            need(all(row[k] for k in ('owner', 'ref', 'lib_pin')), 'actual owner/ref/library pin mapping absent')
        if 'pulse_' in row['role']:
            role = next(x for x in row['role'].split('|') if x.startswith('pulse_'))
            counts[role[6:]] += 1
            need(row['class'] == 'pin' and row['object'].rsplit('/', 1)[1] == role.split('_')[1],
                 'pulse endpoint native identity differs')
            refs[row['ref']] += 1
            level = 'min_pulse_width_high' if role.endswith('_high') else 'min_pulse_width_low'
            need(row[level] != '', 'native minpulse width missing without explicit sentinel')
            if row[level].startswith(('UNAVAILABLE:', 'ABSENT_OR_EMPTY:')):
                width_gaps[role[6:]] += 1
    need(dict(counts) == targets['pulse_counts'], 'native pulse counts differ from actual185')
    diagnostics = table(out / 'attribute-diagnostics.tsv',
                        ('object_handle', 'context', 'attribute', 'catch_code', 'value', 'raw_diagnostics'))
    return dict(schema='xu-s2e-coverage186-native-metadata-review-v1', exact_object_count=len(rows),
                pulse_counts=dict(counts), pulse_native_ref_counts=dict(refs),
                pulse_width_unavailable_or_empty=dict(width_gaps), optional_attribute_diagnostic_rows=len(diagnostics),
                qualification='NOT_QUALIFIED', pulse_or_recovery_exemptions=0,
                note='Attribute absence and static clock metadata do not establish runtime disabling or150MHz qualification.')


def output_manifest(out, status):
    files = []
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name != 'output-manifest186.json':
            item = identity(p)
            files.append(dict(name=p.name, sha256=item['sha256'], bytes=item['bytes']))
    write(out / 'output-manifest186.json', dict(schema='xu-s2e-coverage186-output-v1', status=status,
          qualification='NOT_QUALIFIED', vendor_bodies_exported=False, files=files))


def run(out, timeout):
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='xu-s2e-coverage186-state-v1', status='PREPARING_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                 limitations=LIMITS, pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(), native_runs=0)
    write(out / 'state.json', state)
    before = None
    try:
        manifest = bundle()
        ref = read(HERE / 'references186.json')
        before = checked_inputs(ref)
        state['inputs_before'] = before
        state['runtime_before'] = [identity(HERE / x['name']) for x in manifest['runtime']] + [identity(HERE / 'manifest186.json')]
        preflight = ref['preflight']
        verify_provenance(ref, read(preflight['prepared']['path']), read(preflight['execution']['path']),
                          read(preflight['result']['path']), read(ref['target_context']['state']['path']))
        targets = read(HERE / 'targets186.json')
        text, method = render(ref, targets)
        (out / 'query.tcl').write_text(text)
        (out / 'own-clock-method.tcl').write_text(method)
        argv = [ref['pt']['path'], '-f', 'query.tcl']
        env = os.environ.copy()
        env['SYNOPSYS_LC_ROOT'] = ref['library_compiler_root']
        env['PATH'] = ref['library_compiler_root'] + '/bin:' + env.get('PATH', '')
        state.update(status='RUNNING_NATIVE_NOT_QUALIFIED', command=argv, native_runs=1,
                     query=identity(out / 'query.tcl'), targets=identity(HERE / 'targets186.json'))
        write(out / 'state.json', state)
        start = time.monotonic()
        with (out / 'pt.log').open('wb') as log:
            proc = subprocess.Popen(argv, cwd=str(out), env=env, stdout=log, stderr=subprocess.STDOUT)
            state['native_pid'] = proc.pid
            write(out / 'state.json', state)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
                raise ValueError('native186 timeout; partial reports retained; never restart this output root')
        state.update(returncode=code, native_elapsed_seconds=time.monotonic() - start)
        state['log_review'] = inspect_log((out / 'pt.log').read_text(errors='replace'), code)
        state['report_status'] = review(out, state['log_review'])
        state['native_metadata_review'] = review_metadata(out, targets)
        state['optional_report_gaps'] = [x['report'] for x in state['report_status'] if x['catch_code']]
        state['status'] = SUCCESS
    except BaseException as exc:
        state.update(status=FAILURE, error=str(exc), traceback=traceback.format_exc())
    finally:
        if before is not None:
            try:
                state['inputs_after'] = checked_inputs(read(HERE / 'references186.json'))
                need(state['inputs_after'] == before, 'own155 inputs changed during native query')
                state['runtime_after'] = [identity(x['path']) for x in state['runtime_before']]
                need(state['runtime_after'] == state['runtime_before'], 'runtime changed during native query')
                state['inputs_equal_before_after'] = True
            except BaseException as exc:
                state.update(status=FAILURE, inputs_equal_before_after=False, identity_error=str(exc))
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        state['artifacts'] = [identity(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'state.json']
        write(out / 'state.json', state)
        output_manifest(out, state['status'])
    print(json.dumps(dict(status=state['status'], out=str(out), qualification='NOT_QUALIFIED')))
    return 0 if state['status'] == SUCCESS else 1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    p.add_argument('--timeout', type=int, default=3600)
    p.add_argument('--describe', action='store_true')
    args = p.parse_args()
    if args.describe:
        bundle()
        print(json.dumps(dict(status='DESCRIBED_NOT_RUN_NOT_QUALIFIED', success=SUCCESS, failure=FAILURE,
                              result_state='state.json', native=True, limitations=LIMITS), indent=2))
        return 0
    need(args.out is not None and args.out.is_absolute(), 'fresh absolute --out required')
    need(1 <= args.timeout <= 7200, 'native timeout must be1..7200 seconds')
    return run(args.out.absolute(), args.timeout)


if __name__ == '__main__':
    sys.exit(main())
