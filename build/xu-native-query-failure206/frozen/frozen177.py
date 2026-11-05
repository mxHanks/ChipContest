#!/usr/bin/env python3
"""OwnS2c same9c16 read-only native PT query; Python3.6+, standard library.

Foreground worker for the existing single-slot153 controller. Never edits any
design/model/SDC, never restarts a previous output root, and never qualifies a
functional/timing/energy result. No credentials or network.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
SUCCESS = 'EXECUTED_OWN_S2C_READONLY177_NOT_QUALIFIED'
FAILURE = 'FAIL_OWN_S2C_READONLY177_NOT_QUALIFIED'
MARKER = 'XU_OWN_S2C_READONLY177_COMPLETE_NOT_QUALIFIED'
LIMITS = [
    'NOT_QUALIFIED: read-only native connectivity/minimum-delay diagnosis, not complete150MHz or functional acceptance.',
    'Replays ownS2c57 original envelope/propagated-clock method, unchanged SDC and same9c16 mapping; no baseline116/S2e155 inheritance.',
    'PT graph fanout stops at first state/endpoints; static potential connectivity is not Boolean sensitization or X causality.',
    'Original167 early D/handshake transient X is not attributed to the later notifier by this query.',
    'VCS model hold checks and PT static minimum timing are distinct: no SDF equivalence or causal attribution is implied.',
    'Optional report failures and all native warnings/errors remain in query-status.tsv and pt.log; unavailable reports are not inferred.',
    'Model summary exports hashes, source spans and bounded relation metadata only, never model/UDP bodies.',
    'No force, DUT FF write, initialization, testbench/model/RTL/clock/SDC changes, inserted delays or timing-check suppression.',
]


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    path = Path(path)
    st0 = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    st1 = path.stat()
    need((st0.st_dev, st0.st_ino, st0.st_size, st0.st_mtime_ns, st0.st_ctime_ns) ==
         (st1.st_dev, st1.st_ino, st1.st_size, st1.st_mtime_ns, st1.st_ctime_ns),
         'file changed while hashing: ' + str(path))
    return dict(path=str(path), bytes=st1.st_size, sha256=h.hexdigest(), device=st1.st_dev,
                inode=st1.st_ino, mtime_ns=st1.st_mtime_ns, ctime_ns=st1.st_ctime_ns)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    temp = Path(str(path) + '.tmp-' + str(os.getpid()))
    with temp.open('w') as output:
        json.dump(value, output, sort_keys=True, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(str(temp), str(path))


def bundle():
    manifest = read(HERE / 'manifest177.json')
    need(manifest['schema'] == 'xu-s2c-readonly177-manifest-v1', 'wrong runtime manifest schema')
    for row in manifest['runtime']:
        name = row['name']
        need(Path(name).name == name, 'unsafe bundle filename')
        p = HERE / name
        need(p.is_file() and not p.is_symlink(), 'missing/symlink runtime: ' + name)
        actual = identity(p)
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'],
             'bundle runtime bytes changed: ' + name)
    return manifest


def checked_inputs(ref):
    q = ref['next_minimal_readonly_query']
    expected = [q['target'], q['own_s2c_sdc']] + q['own_s2c_libraries'] + [ref['pt'], ref['model'], ref['own_clock_method_source']]
    frozen = []
    for row in expected:
        actual = identity(row['path'])
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'],
             'frozen ownS2c input differs: ' + row['path'])
        frozen.append(actual)
    need(Path(ref['library_compiler_root']).is_dir(), 'same library compiler installation missing')
    return frozen


def clock_setup(ref, original):
    need(digest(original) == ref['own_clock_method_source']['sha256'], 'own57 clock-source template hash differs')
    text = original.decode('ascii')
    start = text.index('set XU_CLOCK_MODE envelope\n')
    stop = text.index('# Exact post-elaboration macro groups;')
    method = text[start:stop]
    need(method.count('source {') == 1 and method.endswith('update_timing\n'), 'own57 clock method scope differs')
    need('set_propagated_clock [all_clocks]\n' in method and 'set XU_PLL_DIV 0\n' in method,
         'own57 envelope/propagated method differs')
    q = ref['next_minimal_readonly_query']
    paths = [x['path'] for x in q['own_s2c_libraries']]
    setup = 'set_app_var link_path [list * ' + ' '.join('{' + x + '}' for x in paths) + ']\n'
    setup += 'redirect -file tool-version.rpt {puts $sh_product_version}\n'
    setup += 'read_verilog {' + q['target']['path'] + '}\n'
    setup += 'if {![link_design {xu_soc_ppa_top}]} {error {ownS2c177 link failed}}\n'
    return setup + method, method


def render_query(ref):
    text = (HERE / 'query177.tcl.in').read_text()
    setup, method = clock_setup(ref, (HERE / 'frozen-ownS2c-power57.tcl').read_bytes())
    q = ref['next_minimal_readonly_query']
    target = '/'.join(q['target_identifier_components'])
    need(target == q['target_pt_cell_candidate'], 'exact target components/candidate disagree')
    need('dp_gt0.vec_31_dfflr/qout_r_reg[0]' in target, 'escaped instance spelling changed')
    bias = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave/u_linear_compute_core/io_cacheWriteEnable'
    for token, replacement in [('@OWN_SETUP@', setup), ('@TARGET@', target), ('@BIAS@', bias)]:
        need(text.count(token) == 1, 'query placeholder differs: ' + token)
        text = text.replace(token, replacement)
    need(not re.search(r'@[A-Z_]+@', text), 'unexpanded query placeholder')
    return text, method


def model_summary(data):
    """Bounded metadata only; never return any model/module/UDP body text."""
    text = data.decode('latin1')
    modules = list(re.finditer(r'\bmodule\s+DRNQV0_12TR40\b(.*?)\bendmodule\b', text, re.S))
    need(len(modules) == 1, 'unique DRNQV0_12TR40 model not found')
    match = modules[0]
    body = match.group(0)
    clean = re.sub(r'/\*.*?\*/|//[^\n]*', '', body, flags=re.S)
    specify = list(re.finditer(r'\bspecify\b(.*?)\bendspecify\b', body, re.S))
    need(len(specify) == 1, 'unique target specify block missing')
    timing = []
    for item in re.finditer(r'\$(hold|setup|setuphold|recovery|removal|recrem|width|period)\s*\((.*?)\)\s*;', clean, re.S):
        args = [re.sub(r'\s+', ' ', x.strip()) for x in item.group(2).split(',')]
        # Bounded expressions identify the check relationships without body export.
        need(len(args) <= 12 and all(len(x) <= 200 for x in args), 'unexpected model timing-check expression')
        timing.append(dict(kind=item.group(1), arguments=args))
    udp = []
    for primitive in re.finditer(r'\bprimitive\s+(\w+)\s*\((.*?)\)\s*;(.*?)\bendprimitive\b', text, re.S):
        name = primitive.group(1)
        instances = list(re.finditer(r'(?<!\w)' + re.escape(name) + r'\s+(\w+)\s*\((.*?)\)\s*;', clean, re.S))
        for inst in instances:
            ports = [x.strip() for x in primitive.group(2).split(',')]
            conns = [re.sub(r'\s+', ' ', x.strip()) for x in inst.group(2).split(',')]
            need(len(ports) == len(conns) and len(ports) <= 20 and all(len(x) <= 200 for x in conns) and
                 all(re.match(r'^[A-Za-z_][\w$]*$', x) for x in ports),
                 'unexpected primitive relationship')
            udp.append(dict(primitive=name, instance=inst.group(1), port_connections=dict(zip(ports, conns)),
                            source_sha256=digest(primitive.group(0).encode('latin1')),
                            source_line=text[:primitive.start()].count('\n') + 1,
                            table_exported=False))
    assigns = []
    for item in re.finditer(r'\bassign\s+(\w+)\s*=\s*([^;]+);', clean):
        rhs = item.group(2).strip()
        if item.group(1) in ('Q', 'n0', 'ENABLE_D', 'ENABLE_RDN'):
            need(len(rhs) <= 200, 'unexpected model assign')
            assigns.append(dict(destination=item.group(1), expression=rhs))
    return dict(schema='xu-s2c177-model-relations-v1', qualification='NOT_QUALIFIED',
                model_sha256=digest(data), module='DRNQV0_12TR40',
                source_timescale_tokens=sorted(set(re.findall(r'^\s*`timescale\s+([^\r\n]+)', text, re.M))),
                nearest_preceding_timescale=(re.findall(r'^\s*`timescale\s+([^\r\n]+)', text[:match.start()], re.M) or [None])[-1],
                module_source_sha256=digest(body.encode('latin1')),
                module_line=text[:match.start()].count('\n') + 1,
                specify_sha256=digest(specify[0].group(0).encode('latin1')),
                timing_checks=timing, primitive_instances=udp, bounded_assign_relations=assigns,
                relation_parse_gaps=([x for x, absent in [('no_timing_check_recognized', not timing),
                                    ('no_local_UDP_instance_recognized', not udp)] if absent]),
                module_body_exported=False, udp_table_exported=False,
                interpretation='Syntactic relation metadata only; no notifier/unknown-causality or UDP behavioral proof.')


def inspect_log(text, returncode):
    lines = text.splitlines()
    markers = [x for x in lines if x.strip() == MARKER]
    need(returncode == 0 and len(markers) == 1, 'native returncode/completion marker differs')
    need('Version T-2022.03-SP5-1' in text, 'same original PT version not observed')
    need(not any(re.match(r'^XU177_FATAL:', x) for x in lines), 'query mandatory stage failed')
    context = None
    errors = []
    for line in lines:
        if line.startswith('XU177_REPORT_BEGIN '):
            context = line.split(' ', 1)[1]
        elif line.startswith('XU177_REPORT_END '):
            context = None
        elif line.startswith('Error:'):
            errors.append(dict(report=context, line=line))
    return dict(marker_count=len(markers), native_warning_count=sum(bool(re.match(r'^Warning:', x)) for x in lines),
                native_error_lines=[x['line'] for x in errors], native_error_context=errors)


REQUIRED = {'min-to-D.rpt', 'min-path-native.rpt', 'target-clock-reset.rpt', 'target-libpins.rpt',
            'check-timing.rpt', 'units.rpt', 'analysis-coverage.rpt', 'Q-first-state-boundaries.rpt'}
ESSENTIAL = REQUIRED | {'target-native.rpt', 'direct-connectivity.rpt', 'tool-version.rpt'}


def review_reports(out, log_review):
    statuses = (out / 'query-status.tsv').read_text().splitlines()
    need(statuses and statuses[0] == 'report\tcatch_code\tmessage', 'native report status table missing')
    reports = [line.split('\t', 2) for line in statuses[1:]]
    need(all(len(x) == 3 and x[1] in ('0', '1') for x in reports), 'malformed native report status')
    need(len(reports) == len({x[0] for x in reports}), 'duplicate native report status')
    need(REQUIRED.issubset({x[0] for x in reports if x[1] == '0'}), 'required read-only report is unavailable')
    need(all((out / name).is_file() and (out / name).stat().st_size > 0 for name in ESSENTIAL),
         'native required report file missing/empty')
    for name in ESSENTIAL:
        need(not re.search(r'^Error:', (out / name).read_text(errors='replace'), re.M),
             'native required report emitted Error: ' + name)
    need(not any(x['report'] is None or x['report'] in ESSENTIAL for x in log_review['native_error_context']),
         'native required/unattributed Error in pt.log; preserved as unavailable')
    return [dict(report=x[0], catch_code=int(x[1]), message=x[2]) for x in reports]


def run(out, timeout):
    out = Path(out).absolute()
    # Exclusive fresh root is the at-most-once contract; no --resume or overwrite.
    out.mkdir(parents=True, exist_ok=False)
    state = dict(schema='xu-s2c-readonly177-state-v1', status='PREPARING_NOT_QUALIFIED',
                 qualification='NOT_QUALIFIED', pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat(),
                 limitations=LIMITS, native_runs=0)
    write(out / 'state.json', state)
    before = None
    try:
        manifest = bundle()
        ref = read(HERE / 'references177.json')
        before = checked_inputs(ref)
        state['inputs_before'] = before
        state['runtime_before'] = [identity(HERE / x['name']) for x in manifest['runtime']] + [identity(HERE / 'manifest177.json')]
        query, method = render_query(ref)
        (out / 'query.tcl').write_text(query)
        (out / 'own-clock-method.tcl').write_text(method)
        model = model_summary(Path(ref['model']['path']).read_bytes())
        write(out / 'model-relations.json', model)
        argv = [ref['pt']['path'], '-f', 'query.tcl']
        env = os.environ.copy()
        env['SYNOPSYS_LC_ROOT'] = ref['library_compiler_root']
        env['PATH'] = ref['library_compiler_root'] + '/bin:' + env.get('PATH', '')
        state.update(status='RUNNING_NATIVE_NOT_QUALIFIED', command=argv, native_runs=1,
                     query=identity(out / 'query.tcl'), model_summary=identity(out / 'model-relations.json'))
        write(out / 'state.json', state)
        started = time.monotonic()
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
                    proc.kill()
                    proc.wait()
                raise ValueError('own177 native query timeout; partial logs preserved; never restart this root')
        state['returncode'] = code
        state['native_elapsed_seconds'] = time.monotonic() - started
        state['log_review'] = inspect_log((out / 'pt.log').read_text(errors='replace'), code)
        state['report_status'] = review_reports(out, state['log_review'])
        state['optional_report_gaps'] = [x['report'] for x in state['report_status'] if x['catch_code'] != 0]
        state['status'] = SUCCESS
    except BaseException as exc:
        state.update(status=FAILURE, error=str(exc), traceback=traceback.format_exc())
    finally:
        if before is not None:
            try:
                state['inputs_after'] = checked_inputs(read(HERE / 'references177.json'))
                need(state['inputs_after'] == before, 'frozen ownS2c inputs changed before/after query')
                state['runtime_after'] = [identity(x['path']) for x in state['runtime_before']]
                need(state['runtime_before'] == state['runtime_after'], 'runtime changed during native query')
                state['inputs_equal_before_after'] = True
            except BaseException as exc:
                state.update(status=FAILURE, identity_error=str(exc), inputs_equal_before_after=False)
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        state['artifacts'] = [identity(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'state.json']
        write(out / 'state.json', state)
        write(out / 'output-manifest177.json', dict(schema='xu-s2c-readonly177-output-v1',
              qualification='NOT_QUALIFIED', status=state['status'], vendor_bodies_exported=False,
              files=[dict(name=p.name, bytes=identity(p)['bytes'], sha256=identity(p)['sha256'])
                     for p in sorted(out.iterdir()) if p.is_file() and p.name != 'output-manifest177.json']))
    print(json.dumps(dict(status=state['status'], out=str(out), qualification='NOT_QUALIFIED')))
    return 0 if state['status'] == SUCCESS else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--describe', action='store_true')
    args = parser.parse_args()
    if args.describe:
        bundle()
        print(json.dumps(dict(status='DESCRIBED_NOT_RUN_NOT_QUALIFIED', success=SUCCESS, failure=FAILURE,
                              result_state='state.json', native=True, timeout_seconds=1800, limitations=LIMITS), indent=2))
        return 0
    need(args.out is not None and args.out.is_absolute(), 'fresh absolute --out required')
    need(1 <= args.timeout <= 7200, 'native timeout must be 1..7200 seconds')
    return run(args.out, args.timeout)


if __name__ == '__main__':
    sys.exit(main())
