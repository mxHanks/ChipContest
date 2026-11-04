#!/usr/bin/env python3
"""Prepare actual86: read-only clock-expansion diagnosis; no analysis overrides.

Run on the same server as actual80. Writes a new output directory, preserves
actual61/80, and never changes any clock, library, SDC, exception, case value,
or timing-engine variable. Python 3.6 compatible; no network/credentials.
Manual text remains private; export its identity rather than the whole text.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
D = Path.home() / 'Desktop'
PARENT = B / 'full-soc-reset-buffer-20261104-61-from50-n4'
ACTUAL80 = B / 'pmu-reset-condition-20261104-80'
O = B / 'pmu-reset-clock-expansion-20261104-86'
SDC = B / 'full-soc-pt-compatible-05/constraints.sdc'
PROPOSAL = D / 'xu-ts16.tcl'
FROZEN = {
    PARENT / 'state.json': '1163c63ba568db5040177f844bb4c3d0518029f4e3e85f58d376950a4f646df1',
    PARENT / 'mapped.v': '502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597',
    PARENT / 'repair.svf': '5cfc2a56aec461f1759442308ed3212d138231738d586a2dfedeec10de39a807',
    SDC: '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98',
    PROPOSAL: '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e',
    ACTUAL80 / 'diagnosis.log': 'ec99e9900a8504a11f3139fdcffa4bbf34be59cf96a5105ea36cbe203c4c5faf',
    ACTUAL80 / 'state.json': '371d6be2dbd1bfd056ab3a3a68e229aafe7ce8e288e05a555f0758532c680677',
}
LIB_SHA = {
    'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
    'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f',
}
BASE = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
SINKS = [(BASE + 'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg', 'SDN', 'DSNQV0_12TR40'),
         (BASE + 'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg', 'SDN', 'DSNQNV0_12TR40')]
SINKS += [(BASE + 'aonrst_catch/reset_n_catch_reg/reg_%d/q_reg' % i, 'RDN', 'DRNQV0_12TR40') for i in range(3)]
HF_SOURCE = 'io_pads_aon_erst_n_i_ival'
LF_SOURCE = BASE + 'u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q'
VARIABLE_PATTERNS = ['*expand*', '*waveform*', '*base_period*', '*repeat*', '*clock*', '*unconstrained*', '*recovery*']
COMMANDS = ['report_clock', 'report_clock_timing', 'get_clocks', 'get_timing_paths',
            'report_timing', 'printvar', 'report_analysis_coverage', 'get_nets', 'get_attribute']


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tq(value):
    value = str(value)
    if any(c in value for c in '{}\r\n\t'):
        raise ValueError('unsafe Tcl literal')
    return '{' + value + '}'


def guard(body, marker):
    return ('if {[catch {\n' + body + '\n} xu_error xu_options]} {\n'
            ' puts stderr "XU_FATAL: $xu_error"\n'
            ' if {[dict exists $xu_options -errorinfo]} {puts stderr [dict get $xu_options -errorinfo]}\n'
            ' exit 1\n}\nputs ' + tq(marker) + '\nexit 0\n')


def document_tcl():
    body = 'set f [open docs-index.tsv w]\nputs $f "kind\\tname\\tcatch_rc\\tmessage"\n'
    for name in COMMANDS + ['PTE-052']:
        for method in ('help', 'man'):
            body += ('set rc [catch {redirect -file ' + tq(method + '-' + name + '.txt') +
                     ' {' + method + ' ' + name + '}} msg]\n'
                     'puts $f [join [list ' + tq(method) + ' ' + tq(name) + ' $rc $msg] "\\t"]\n')
    body += 'close $f\n'
    body += 'redirect -file attributes-clock.txt {list_attributes -application -class clock}\n'
    for index, pattern in enumerate(VARIABLE_PATTERNS):
        body += 'redirect -file ' + tq('defaults-%02d.txt' % index) + ' {printvar ' + tq(pattern) + '}\n'
    return guard(body, 'XU_RESET86_INSTALLED_DOCS_DONE_NOT_QUALIFIED')


def diagnostic_tcl(libraries, attributes):
    docs = '\n'.join((O / ('man-' + command + '.txt')).read_text(errors='replace') for command in ('get_timing_paths', 'report_timing'))
    for flag in ('-from', '-to', '-delay_type', '-max_paths', '-slack_lesser_than'):
        if flag not in docs:
            raise ValueError('installed timing-path documentation missing ' + flag)
    report_docs = (O / 'man-report_timing.txt').read_text(errors='replace')
    full_clock = '-path_type full_clock_expanded' if 'full_clock_expanded' in report_docs else ''
    body = ('set_app_var link_path [list * ' + ' '.join(tq(path) for path in libraries) + ']\n'
            'read_verilog ' + tq(PARENT / 'mapped.v') + '\n'
            'if {![link_design xu_soc_ppa_top]} {error {exact actual61 link failed}}\n'
            'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + tq(SDC) + '\n'
            'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' + tq(PROPOSAL) + '\n'
            'set rows [open paths.tsv w]\nputs $rows "source_kind\\tindex\\tcheck\\tcatch_rc\\tcount\\tworst_slack\\tstatus"\n'
            'set attrs [open clock-properties.tsv w]\nputs $attrs "clock\\tattribute\\tcatch_rc\\tvalue"\n'
            'set calls [open tagged-net-queries.tsv w]\nputs $calls "pin\\tcatch_rc\\tcount\\tnames_or_error"\n'
            'set hf [get_ports -quiet ' + tq(HF_SOURCE) + ']\n'
            'set lf [get_pins -quiet ' + tq(LF_SOURCE) + ']\n'
            'if {[sizeof_collection $hf]!=1 || [sizeof_collection $lf]!=1} {error {source identity missing}}\n')
    # Read, never set, installed expansion defaults in the loaded design session.
    for index, pattern in enumerate(VARIABLE_PATTERNS):
        body += 'redirect -file ' + tq('loaded-defaults-%02d.txt' % index) + ' {printvar ' + tq(pattern) + '}\n'
    body += 'redirect -file clocks.rpt {report_clock -attributes}\n'
    for name in ('xu_hfextclk', 'xu_lfextclk'):
        body += 'set c [get_clocks -quiet ' + tq(name) + ']\nif {[sizeof_collection $c]!=1} {error {clock identity missing}}\n'
        for attr in attributes:
            body += ('set rc [catch {get_attribute -quiet $c ' + tq(attr) + '} value]\n'
                     'puts $attrs [join [list ' + tq(name) + ' ' + tq(attr) + ' $rc $value] "\\t"]\n')
    for index, (cell, pin, reference) in enumerate(SINKS):
        body += ('set c [get_cells -quiet ' + tq(cell) + ']\n'
                 'if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne ' + tq(reference) + '} {error {endpoint identity differs}}\n'
                 'set p [get_pins -quiet ' + tq(cell + '/' + pin) + ']\n'
                 'if {[sizeof_collection $p]!=1} {error {reset endpoint missing}}\n')
        for kind in (['HF_RESET', 'LF_WATCHDOG'] if index >= 2 else ['HF_RESET']):
            source = '$hf' if kind == 'HF_RESET' else '$lf'
            for delay, check in (('max', 'recovery'), ('min', 'removal')):
                filename = '%s-%d-%s.rpt' % (kind.lower(), index, check)
                body += ('puts ' + tq('XU_PATH_QUERY_BEGIN ' + filename) + '\n'
                         'redirect -file ' + tq(filename) + ' {report_timing -delay_type ' + delay + ' -from ' + source +
                         ' -to $p -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 ' + full_clock + '}\n'
                         'set rc [catch {get_timing_paths -delay_type ' + delay + ' -from ' + source +
                         ' -to $p -slack_lesser_than 1000000 -max_paths 10} paths]\n'
                         'set n UNKNOWN\nset slack UNKNOWN\nset status QUERY_ERROR_NOT_PASS\n'
                         'if {!$rc} {set n [sizeof_collection $paths];set status NO_PATH_UNKNOWN;'
                         'if {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATHS_PRESENT_DIAGNOSTIC_ONLY}}\n'
                         'puts $rows [join [list ' + tq(kind) + ' ' + str(index) + ' ' + tq(check) + ' $rc $n $slack $status] "\\t"]\n'
                         'puts ' + tq('XU_PATH_QUERY_END ' + filename) + '\n')
    tagged = [SINKS[0][0] + '/D', SINKS[4][0] + '/D', SINKS[0][0] + '/SDN', SINKS[1][0] + '/SDN']
    for pin in tagged:
        body += ('set p [get_pins -quiet ' + tq(pin) + ']\n'
                 'if {[sizeof_collection $p]!=1} {error {tagged pin identity missing}}\n'
                 'puts ' + tq('XU_NET_QUERY_BEGIN ' + pin) + '\n'
                 'set rc [catch {get_nets -of_objects $p} nets]\n'
                 'set n QUERY_ERROR\nset names $nets\n'
                 'if {!$rc} {set n [sizeof_collection $nets];set names {};if {$n>0} {set names [get_object_name $nets]}}\n'
                 'puts $calls [join [list ' + tq(pin) + ' $rc $n $names] "\\t"]\n'
                 'puts ' + tq('XU_NET_QUERY_END ' + pin) + '\n')
    body += ('redirect -file analysis-coverage.rpt {report_analysis_coverage -status_details untested}\n'
             'close $rows\nclose $attrs\nclose $calls\n')
    return guard(body, 'XU_RESET86_READ_ONLY_CLOCK_DIAGNOSIS_DONE_NOT_QUALIFIED')


def main():
    worker = len(sys.argv) == 2 and sys.argv[1] == 'run'
    if not worker:
        for path, expected in FROZEN.items():
            if sha(path) != expected:
                raise ValueError('frozen input differs: ' + str(path))
        O.mkdir(exist_ok=False)
        with (O / 'driver.log').open('x') as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'], stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print('XU_RESET86_READ_ONLY_CLOCK_DIAGNOSIS_STARTED', process.pid)
        return
    state = dict(status='RUNNING_READ_ONLY_DIAGNOSTIC_NOT_QUALIFIED', pid=os.getpid(), started_epoch=time.time(),
                 hypothesis='PTE-052 may suppress HF-reset to LF-capture recovery; not proved',
                 scope='exact actual61, actual80 identities, original SDC/proposal and libraries; read-only engine/default queries; no overrides')
    def save():
        (O / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    environment = os.environ.copy()
    environment['SYNOPSYS_LC_ROOT'] = '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'
    environment['PATH'] = environment['SYNOPSYS_LC_ROOT'] + '/bin:' + environment.get('PATH', '')
    def run_script(name, content, marker):
        script = O / name
        script.write_text(content)
        logfile = O / (script.stem + '.log')
        with logfile.open('x') as log:
            run = subprocess.run(['pt_shell', '-f', str(script)], cwd=str(O), env=environment, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, timeout=21600)
        raw = logfile.read_text(errors='replace')
        errors = [line for line in raw.splitlines() if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)', line)]
        state.setdefault('runs', []).append(dict(script=name, returncode=run.returncode, errors=errors,
              marker_count=raw.splitlines().count(marker), script_sha256=sha(script), log_sha256=sha(logfile)))
        save()
        if run.returncode or raw.splitlines().count(marker) != 1:
            raise ValueError(name + ' execution failed; raw errors retained')
    save()
    try:
        for path, expected in FROZEN.items():
            if sha(path) != expected:
                raise ValueError('frozen input differs: ' + str(path))
        parent = json.loads((PARENT / 'state.json').read_text())
        libraries = [Path(path) for path in parent['input_sha256'] if path.endswith('.db')]
        if len(libraries) != 2 or {sha(path) for path in libraries} != LIB_SHA:
            raise ValueError('actual two SS libraries differ')
        inputs = list(FROZEN) + libraries + [Path(__file__).resolve()]
        state['input_sha256_before'] = {str(path): sha(path) for path in inputs}
        save()
        run_script('installed-docs.tcl', document_tcl(), 'XU_RESET86_INSTALLED_DOCS_DONE_NOT_QUALIFIED')
        variables = set()
        for path in O.glob('defaults-*.txt'):
            for name in re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=', path.read_text(errors='replace'), re.M):
                if re.search(r'(expand|waveform|base_period|repeat|period)', name):
                    variables.add(name)
        state['documented_variable_names_requested'] = sorted(variables)
        body = 'set f [open variable-doc-index.tsv w]\nputs $f "variable\\tcatch_rc\\tmessage"\n'
        for name in sorted(variables):
            body += ('set rc [catch {redirect -file ' + tq('man-var-' + name + '.txt') + ' {man ' + name + '}} msg]\n'
                     'puts $f [join [list ' + tq(name) + ' $rc $msg] "\\t"]\n')
        body += 'close $f\n'
        run_script('variable-docs.tcl', guard(body, 'XU_RESET86_VARIABLE_DOCS_DONE_NOT_QUALIFIED'), 'XU_RESET86_VARIABLE_DOCS_DONE_NOT_QUALIFIED')
        types = r'(?:boolean|integer|float|string|double|collection|object|list)'
        clockattrs = re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)\s+clock\s+' + types + r'\b', (O / 'attributes-clock.txt').read_text(errors='replace'), re.M)
        selected = sorted(name for name in clockattrs if re.search(r'(period|waveform|sources|master_clock|is_generated)', name))
        state['documented_clock_attribute_names'] = selected
        run_script('diagnosis.tcl', diagnostic_tcl(libraries, selected), 'XU_RESET86_READ_ONLY_CLOCK_DIAGNOSIS_DONE_NOT_QUALIFIED')
        after = {str(path): sha(path) for path in inputs}
        if after != state['input_sha256_before']:
            raise ValueError('frozen inputs changed during read-only probe')
        state['input_sha256_after'] = after
        state['outputs'] = {path.name: dict(bytes=path.stat().st_size, sha256=sha(path)) for path in O.iterdir()
                            if path.is_file() and path.name not in ('state.json', 'driver.log')}
        state['paths'] = (O / 'paths.tsv').read_text()
        state['tagged_net_queries'] = (O / 'tagged-net-queries.tsv').read_text()
        state['status'] = 'EXECUTED_READ_ONLY_CLOCK_DIAGNOSTIC_NOT_QUALIFIED'
    except BaseException as error:
        state.update(status='FAIL_NOT_QUALIFIED', error=repr(error))
        raise
    finally:
        state['finished_epoch'] = time.time()
        save()


if __name__ == '__main__':
    main()
