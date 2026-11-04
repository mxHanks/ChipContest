"""xu reset80: read-only diagnosis of actual61 conditional reset timing.

Run on server: python3 launch_reset_condition80.py
Writes a new isolated output only.  No RTL, library, SDC, netlist, SVF, timing
exception, case analysis, disabled arc, or clock setting is changed.  Missing
paths remain UNKNOWN and do not stop the other nine reports.
Python 3.6 compatible.  No credential handling or network access.
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
O = B / 'pmu-reset-condition-20261104-80'
EXPECTED = {
    'state.json': '1163c63ba568db5040177f844bb4c3d0518029f4e3e85f58d376950a4f646df1',
    'mapped.v': '502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597',
    'repair.svf': '5cfc2a56aec461f1759442308ed3212d138231738d586a2dfedeec10de39a807',
}
SDC = B / 'full-soc-pt-compatible-05/constraints.sdc'
PROPOSAL = D / 'xu-ts16.tcl'
LIB_SHA = {
    'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
    'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f',
}
BASE = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
SINKS = [
    (BASE + 'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg', 'SDN', 'DSNQV0_12TR40'),
    (BASE + 'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg', 'SDN', 'DSNQNV0_12TR40'),
] + [(BASE + 'aonrst_catch/reset_n_catch_reg/reg_' + str(i) + '/q_reg',
      'RDN', 'DRNQV0_12TR40') for i in range(3)]
COMMANDS = [
    'get_timing_arcs', 'get_lib_timing_arcs', 'get_timing_paths',
    'report_timing', 'report_disable_timing', 'report_case_analysis',
    'report_lib', 'report_cell', 'report_net', 'get_clocks', 'all_fanin',
    'list_attributes', 'get_attribute', 'report_analysis_coverage',
]
CLASSES = ['pin', 'cell', 'timing_arc', 'lib_timing_arc', 'lib_pin', 'lib_cell']


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def tq(value):
    value = str(value)
    if any(c in value for c in '{}\r\n\t'):
        raise ValueError('unquotable Tcl value')
    return '{' + value + '}'


def guard(body, marker):
    return ('if {[catch {\n' + body + '\n} xu_error xu_options]} {\n'
            ' puts stderr "XU_FATAL: $xu_error"\n'
            ' if {[dict exists $xu_options -errorinfo]} {puts stderr [dict get $xu_options -errorinfo]}\n'
            ' exit 1\n}\nputs ' + tq(marker) + '\nexit 0\n')


def docs_tcl():
    # Index first.  Optional command/attribute syntax is used only after the
    # installed tool has documented it; unsupported commands remain evidence.
    body = 'set xu_f [open docs-index.tsv w]\nputs $xu_f "kind\\tname\\tstatus"\n'
    for command in COMMANDS:
        for method in ('help', 'man'):
            filename = method + '-' + command + '.txt'
            body += ('set xu_rc [catch {redirect -file ' + tq(filename) + ' {' + method + ' ' + command + '}} xu_msg]\n'
                     'puts $xu_f [join [list ' + tq(method) + ' ' + tq(command) + ' $xu_rc $xu_msg] "\\t"]\n')
    for cls in CLASSES:
        body += ('set xu_rc [catch {redirect -file ' + tq('attributes-' + cls + '.txt') +
                 ' {list_attributes -application -class ' + cls + '}} xu_msg]\n'
                 'puts $xu_f [join [list attributes ' + tq(cls) + ' $xu_rc $xu_msg] "\\t"]\n')
    body += 'close $xu_f\n'
    return guard(body, 'XU_RESET80_INSTALLED_DOCS_DONE_NOT_QUALIFIED')


def documented_text(directory, command):
    return '\n'.join((directory / (kind + '-' + command + '.txt')).read_text(errors='replace')
                     for kind in ('help', 'man')
                     if (directory / (kind + '-' + command + '.txt')).is_file())


def actual_attributes(directory, cls):
    path = directory / ('attributes-' + cls + '.txt')
    if not path.is_file():
        return []
    text = path.read_text(errors='replace')
    types = '(?:boolean|integer|float|string|double|collection|object|list)'
    return sorted(set(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)\s+' + re.escape(cls) + r'\s+' + types + r'\b', text, re.M)))


def reset_reports_tcl():
    body = ''
    for i, (cell, async_pin, reference) in enumerate(SINKS):
        body += ('set xu_c [get_cells -quiet ' + tq(cell) + ']\n'
                 'if {[sizeof_collection $xu_c]!=1 || [get_attribute $xu_c ref_name] ne ' + tq(reference) + '} {error {actual61 endpoint identity changed}}\n'
                 'set xu_p [get_pins -quiet ' + tq(cell + '/' + async_pin) + ']\n')
        for delay, label in (('max', 'recovery'), ('min', 'removal')):
            filename = 'reset-' + str(i) + '-' + label + '.rpt'
            body += ('xu_capture ' + tq(filename) + ' [list report_timing -delay_type ' + delay +
                     ' -to $xu_p -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8] ' + tq(cell + '/' + label) + '\n'
                     'set xu_count UNKNOWN\nset xu_slack UNKNOWN\nset xu_status UNKNOWN\n'
                     'if {[catch {get_timing_paths -delay_type ' + delay + ' -to $xu_p -slack_lesser_than 1000000 -max_paths 10} xu_ps]} {\n'
                     ' puts $xu_unknown [join [list ' + tq(cell + '/' + label) + ' paths_QUERY_ERROR $xu_ps] "\\t"]\n'
                     '} else {\n'
                     ' set xu_count [sizeof_collection $xu_ps]\n'
                     ' if {$xu_count>0} {set xu_slack [get_attribute [index_collection $xu_ps 0] slack];set xu_status PATHS_PRESENT_DIAGNOSTIC_ONLY} else {\n'
                     '  puts $xu_unknown [list ' + tq(cell + '/' + label) + ' no_path_NOT_PASS]\n }\n}\n'
                     'puts $xu_paths [join [list ' + str(i) + ' [get_object_name $xu_p] ' + label + ' $xu_count $xu_slack $xu_status] "\\t"]\n')
    return body + 'flush $xu_paths\nflush $xu_unknown\n'


def diagnostic_tcl(libraries, directory):
    docs = {c: documented_text(directory, c) for c in COMMANDS}
    attrs = {c: actual_attributes(directory, c) for c in CLASSES}
    capabilities = {
        'design_arcs_of_objects': '-of_objects' in docs['get_timing_arcs'],
        'library_arcs_of_objects': '-of_objects' in docs['get_lib_timing_arcs'],
        'library_report_cell_pattern': all(x in docs['report_lib'] for x in ('-cell_pattern', '-timing_arcs')),
        'clocks_of_objects': '-of_objects' in docs['get_clocks'],
        'fanin_flat_startpoints': all(x in docs['all_fanin'] for x in ('-flat', '-startpoints_only', '-to')),
        'disable_timing_report': 'report_disable_timing' in docs['report_disable_timing'] and 'Error:' not in docs['report_disable_timing'],
        'case_analysis_report': 'report_case_analysis' in docs['report_case_analysis'] and 'Error:' not in docs['report_case_analysis'],
    }
    body = ('set_app_var link_path [list * ' + ' '.join(tq(p) for p in libraries) + ']\n'
            'read_verilog ' + tq(PARENT / 'mapped.v') + '\n'
            'if {![link_design xu_soc_ppa_top]} {error {actual61 mapped PT link failed}}\n'
            'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource ' + tq(SDC) + '\n'
            'set XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource ' + tq(PROPOSAL) + '\n'
            'set xu_unknown [open unknowns.tsv w]\nputs $xu_unknown "scope\\tdetail"\n'
            'set xu_pins [open pins.tsv w]\nputs $xu_pins "cell\\tpin\\tfield\\tvalue"\n'
            'set xu_arcs [open timing-arcs.tsv w]\nputs $xu_arcs "cell\\tobject_class\\tarc\\tfield\\tvalue"\n'
            'set xu_library [open library-properties.tsv w]\nputs $xu_library "cell\\tobject_class\\tobject\\tfield\\tvalue"\n'
            'set xu_paths [open reset-paths.tsv w]\nputs $xu_paths "index\\tpin\\tcheck\\tpath_count\\tworst_slack\\tstatus"\n'
            'proc xu_safe_value {o a} {\n'
            ' if {[catch {get_attribute -quiet $o $a} v]} {return [list QUERY_ERROR $v]}\n'
            ' if {[regexp {^(from_pin|to_pin|from_lib_pin|to_lib_pin|clocks|launch_clocks|constrained_launch_clocks|dynamic_clocks)$} $a]} {\n'
            '  if {[catch {get_object_name $v} xu_names]} {return [list COLLECTION_NAME_ERROR $xu_names]}\n'
            '  return [list VALUE_NAMES $xu_names]\n }\n'
            ' return [list VALUE $v]\n}\n'
            'proc xu_capture {filename command scope} {\n'
            ' global xu_unknown\n'
            ' if {[catch {redirect -file $filename {uplevel #0 $command}} v]} {\n'
            '  puts $xu_unknown [join [list $scope QUERY_ERROR $v] "\\t"]\n'
            '  set f [open $filename a];puts $f "XU_QUERY_ERROR: $v";close $f\n'
            ' }\n}\n')
    # Read exact installed defaults only. Never set a timing variable or waive
    # a check merely to obtain a report.
    for pattern in ('*recovery*', '*removal*', '*negative*', '*constraint*'):
        filename = 'installed-vars-' + pattern.strip('*') + '.txt'
        body += 'xu_capture ' + tq(filename) + ' [list printvar ' + tq(pattern) + '] installed_timing_defaults\n'
    body += 'xu_capture timing-exceptions.rpt {report_exceptions} exact_original_scope\n'
    # Preserve all ten checks before optional library/arc introspection.  Any
    # optional query failure cannot hide a later endpoint's timing report.
    body += reset_reports_tcl()
    # All relevant actual index attributes are recorded.  Never probe invented
    # attribute names and never convert an unavailable property into false.
    pin_attrs = [a for a in attrs['pin'] if re.search(r'(constant|case|clock|disable|direction|full_name|signal|reset|async|arrival|slack)', a)]
    library_attrs = {cls: [a for a in attrs[cls] if re.search(r'(function|direction|clock|constant|case|sdf|signal|timing|related|full_name|sequential|latch|flip_flop)', a)]
                     for cls in ('lib_pin', 'lib_cell')}
    arc_attrs = {cls: [a for a in attrs[cls] if re.search(r'(when|condition|sdf|type|sense|disable|from_|to_|related|lib_|delay|constraint)', a)]
                 for cls in ('timing_arc', 'lib_timing_arc')}
    for i, (cell, async_pin, reference) in enumerate(SINKS):
        body += ('set xu_c [get_cells -quiet ' + tq(cell) + ']\n'
                 'if {[sizeof_collection $xu_c]!=1 || [get_attribute $xu_c ref_name] ne ' + tq(reference) + '} {error {actual61 endpoint identity changed}}\n'
                 'set xu_cp [get_pins -of_objects $xu_c]\n'
                 'foreach_in_collection xu_p $xu_cp {\n'
                 ' set xu_pn [get_object_name $xu_p]\n')
        for attr in pin_attrs:
            body += (' puts $xu_pins [join [list ' + tq(cell) + ' $xu_pn ' + tq(attr) + ' [xu_safe_value $xu_p ' + tq(attr) + ']] "\\t"]\n')
        body += (' if {[catch {get_nets -of_objects $xu_p} xu_ns]} {\n'
                 '  puts $xu_unknown [join [list $xu_pn nets_QUERY_ERROR $xu_ns] "\\t"]\n'
                 ' } else {\n'
                 '  puts $xu_pins [join [list ' + tq(cell) + ' $xu_pn nets [get_object_name $xu_ns]] "\\t"]\n'
                 '  foreach_in_collection xu_n $xu_ns {\n'
                 '   if {[catch {all_connected -leaf $xu_n} xu_con]} {puts $xu_unknown [join [list $xu_pn connections_QUERY_ERROR $xu_con] "\\t"]} else {\n'
                 '    foreach_in_collection xu_o $xu_con {puts $xu_pins [join [list ' + tq(cell) + ' $xu_pn leaf_connection [get_object_name $xu_o] [xu_safe_value $xu_o direction]] "\\t"]}\n'
                 '   }\n  }\n }\n')
        if capabilities['clocks_of_objects']:
            body += (' if {[catch {get_clocks -of_objects $xu_p} xu_clocks]} {puts $xu_unknown [join [list $xu_pn clocks_QUERY_ERROR $xu_clocks] "\\t"]} else {puts $xu_pins [join [list ' + tq(cell) + ' $xu_pn clocks [get_object_name $xu_clocks]] "\\t"]}\n')
        if capabilities['fanin_flat_startpoints']:
            body += (' if {[get_attribute $xu_p direction] eq "in"} {\n'
                     '  if {[catch {all_fanin -flat -startpoints_only -to $xu_p} xu_starts]} {puts $xu_unknown [join [list $xu_pn fanin_QUERY_ERROR $xu_starts] "\\t"]} else {puts $xu_pins [join [list ' + tq(cell) + ' $xu_pn fanin_startpoints [get_object_name $xu_starts]] "\\t"]}\n }\n')
        body += '}\n'
        body += 'xu_capture ' + tq('cell-' + str(i) + '-all-design-arcs.rpt') + ' [list report_attribute -application [get_timing_arcs -of_objects $xu_c]] ' + tq(cell) + '\n'
        if not pin_attrs:
            body += 'puts $xu_unknown [list ' + tq(cell) + ' pin_attribute_index_unparsed]\n'
        body += ('set xu_lc [get_lib_cells -of_objects $xu_c]\n'
                 'set xu_lps [get_lib_pins -of_objects $xu_lc]\n')
        for cls, collection in (('lib_cell', '$xu_lc'), ('lib_pin', '$xu_lps')):
            body += 'foreach_in_collection xu_lo ' + collection + ' {\n'
            for attr in library_attrs[cls]:
                body += (' puts $xu_library [join [list ' + tq(cell) + ' ' + tq(cls) + ' [get_object_name $xu_lo] ' +
                         tq(attr) + ' [xu_safe_value $xu_lo ' + tq(attr) + ']] "\\t"]\n')
            body += '}\n'
            if not library_attrs[cls]:
                body += 'puts $xu_unknown [list ' + tq(cell) + ' ' + tq(cls + '_attribute_index_unparsed') + ']\n'
        for cls, command, supported in (
                ('timing_arc', 'get_timing_arcs', capabilities['design_arcs_of_objects']),
                ('lib_timing_arc', 'get_lib_timing_arcs', capabilities['library_arcs_of_objects'])):
            if not supported:
                body += 'puts $xu_unknown [list ' + tq(cell) + ' ' + tq(command + '_of_objects_not_documented') + ']\n'
                continue
            if cls == 'lib_timing_arc':
                body += 'set xu_owner [get_lib_cells -of_objects $xu_c]\n'
            else:
                body += 'set xu_owner $xu_c\n'
            body += ('if {[catch {' + command + ' -of_objects $xu_owner} xu_as]} {\n'
                     ' puts $xu_unknown [join [list ' + tq(cell) + ' ' + tq(command + '_QUERY_ERROR') + ' $xu_as] "\\t"]\n'
                     '} else {\n'
                     ' puts $xu_arcs [join [list ' + tq(cell) + ' ' + tq(cls) + ' ARC_COUNT [sizeof_collection $xu_as]] "\\t"]\n'
                     ' set xu_arc_index 0\n'
                     ' foreach_in_collection xu_a $xu_as {\n'
                     '  set xu_an [format {arc_%03d} $xu_arc_index]; incr xu_arc_index\n')
            for attr in arc_attrs[cls]:
                body += '  puts $xu_arcs [join [list ' + tq(cell) + ' ' + tq(cls) + ' $xu_an ' + tq(attr) + ' [xu_safe_value $xu_a ' + tq(attr) + ']] "\\t"]\n'
            body += ' }\n}\n'
            if not arc_attrs[cls]:
                body += 'puts $xu_unknown [list ' + tq(cell) + ' ' + tq(cls + '_attribute_index_unparsed') + ']\n'
        if capabilities['disable_timing_report']:
            body += 'xu_capture ' + tq('cell-' + str(i) + '-disabled.rpt') + ' [list report_disable_timing $xu_c] ' + tq(cell) + '\n'
        if capabilities['library_report_cell_pattern']:
            body += ('set xu_lc [get_lib_cells -of_objects $xu_c]\n'
                     'set xu_ln [lindex [split [get_object_name $xu_lc] /] 0]\n'
                     'xu_capture ' + tq('cell-' + str(i) + '-library-timing.rpt') +
                     ' [list report_lib -timing_arcs -cell_pattern ' + tq(reference) + ' $xu_ln] ' + tq(cell) + '\n')
    if capabilities['case_analysis_report']:
        body += 'xu_capture case-analysis.rpt {report_case_analysis} whole_design\n'
    body += ('xu_capture analysis-coverage.rpt {report_analysis_coverage -status_details untested} whole_design\n'
             'xu_capture clocks.rpt {report_clock -attributes} whole_design\n'
             'xu_capture setup.rpt {report_timing -delay_type max -slack_lesser_than 1000000 -max_paths 50 -significant_digits 8} whole_design\n'
             'xu_capture hold.rpt {report_timing -delay_type min -slack_lesser_than 1000000 -max_paths 50 -significant_digits 8} whole_design\n'
             'xu_capture constraints.rpt {report_constraint -all_violators -verbose -significant_digits 8} whole_design\n'
             'close $xu_pins\nclose $xu_arcs\nclose $xu_library\nclose $xu_paths\nclose $xu_unknown\n')
    return guard(body, 'XU_RESET80_READ_ONLY_DIAGNOSIS_DONE_NOT_QUALIFIED'), capabilities, attrs


def execute(script, marker, state, environment):
    logpath = O / (script.stem + '.log')
    with logpath.open('x') as log:
        run = subprocess.run(['pt_shell', '-f', str(script)], cwd=str(O), env=environment,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             timeout=21600)
    raw = logpath.read_text(errors='replace')
    errors = [line for line in raw.splitlines() if re.match(r'^\s*(?:Error:|Error-|XU_FATAL:)', line)]
    record = dict(tool='pt_shell', returncode=run.returncode,
                  marker_count=raw.splitlines().count(marker), errors=errors,
                  script_sha256=sha(script), log_sha256=sha(logpath))
    state.setdefault('runs', []).append(record)
    (O / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    if run.returncode or raw.splitlines().count(marker) != 1:
        raise ValueError(script.name + ' execution failed')
    return record


def main():
    # Reject an incorrectly transcribed identity before making an output
    # directory or spawning a worker, including on an older Python runtime.
    for name, digest in EXPECTED.items():
        if not re.match(r'^[0-9a-f]{64}$', digest):
            raise ValueError('expected SHA-256 length/encoding invalid: ' + name)
    worker = len(sys.argv) == 2 and sys.argv[1] == 'run'
    if not worker:
        O.mkdir(exist_ok=False)
        with (O / 'driver.log').open('x') as log:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'],
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
        print('XU_RESET80_READ_ONLY_DIAGNOSIS_STARTED', proc.pid)
        return
    state = dict(status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED', pid=os.getpid(),
                 started_epoch=time.time(), experiment='read-only conditional recovery/removal diagnosis of exact actual61',
                 scope='original SDC and proposal unchanged; no case analysis, disable timing or exception edits; missing paths remain UNKNOWN')
    def save():
        (O / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    save()
    try:
        for name, digest in EXPECTED.items():
            if not re.match(r'^[0-9a-f]{64}$', digest):
                raise ValueError('expected SHA-256 length/encoding invalid: ' + name)
            if sha(PARENT / name) != digest:
                raise ValueError('actual61 identity differs: ' + name)
        parent = json.loads((PARENT / 'state.json').read_text())
        if parent['status'] != 'FAIL' or parent['error'] != 'pt failed':
            raise ValueError('actual61 terminal state differs')
        if len(parent['runs']) != 2 or parent['runs'][0]['returncode'] != 0 or parent['runs'][0]['errors'] or parent['runs'][0]['marker_count'] != 1:
            raise ValueError('actual61 DC execution incomplete')
        if parent['runs'][1]['errors'] != ['XU_FATAL: reset recovery path missing; cannot claim analysis']:
            raise ValueError('actual61 PT failure changed; review original evidence')
        for label, run in zip(('dc', 'pt'), parent['runs']):
            if sha(PARENT / (label + '.log')) != run['log_sha256']:
                raise ValueError('actual61 tool log identity differs')
        libraries = [Path(p) for p in parent['input_sha256'] if p.endswith('.db')]
        if len(libraries) != 2 or {sha(p) for p in libraries} != LIB_SHA:
            raise ValueError('actual61 exact two libraries differ')
        if sha(SDC) != '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98' or sha(PROPOSAL) != '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e':
            raise ValueError('original SDC/proposal differs')
        inputs = [Path(__file__).resolve(), SDC, PROPOSAL] + libraries + [PARENT / p for p in EXPECTED] + [PARENT / 'dc.log', PARENT / 'pt.log']
        state['input_sha256'] = {str(p): sha(p) for p in inputs}
        state['reset_sinks'] = [dict(cell=c, pin=p, ref=r) for c, p, r in SINKS]
        save()
        environment = os.environ.copy()
        environment['SYNOPSYS_LC_ROOT'] = '/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'
        environment['PATH'] = environment['SYNOPSYS_LC_ROOT'] + '/bin:' + environment.get('PATH', '')
        (O / 'installed-docs.tcl').write_text(docs_tcl())
        execute(O / 'installed-docs.tcl', 'XU_RESET80_INSTALLED_DOCS_DONE_NOT_QUALIFIED', state, environment)
        content, capabilities, attrs = diagnostic_tcl(libraries, O)
        state['documented_capabilities'] = capabilities
        state['documented_attribute_names'] = attrs
        (O / 'diagnosis.tcl').write_text(content)
        save()
        execute(O / 'diagnosis.tcl', 'XU_RESET80_READ_ONLY_DIAGNOSIS_DONE_NOT_QUALIFIED', state, environment)
        for p in inputs:
            if sha(p) != state['input_sha256'][str(p)]:
                raise ValueError('frozen input changed during read-only diagnosis')
        missing = [str(i) + '-' + label for i in range(5) for label in ('recovery', 'removal')
                   if not (O / ('reset-' + str(i) + '-' + label + '.rpt')).is_file()]
        if missing:
            raise ValueError('diagnosis did not preserve all ten reset reports: ' + ','.join(missing))
        state.update(status='EXECUTED_DIAGNOSTIC_NOT_QUALIFIED',
                     outputs={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in O.iterdir()
                              if p.is_file() and p.name not in ('state.json', 'driver.log')},
                     reset_paths=(O / 'reset-paths.tsv').read_text(), unknowns=(O / 'unknowns.tsv').read_text())
    except Exception as exc:
        state.update(status='FAIL', error=str(exc))
        raise
    finally:
        state['finished_epoch'] = time.time()
        save()


if __name__ == '__main__':
    main()
