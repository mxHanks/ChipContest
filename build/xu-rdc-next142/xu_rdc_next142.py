#!/usr/bin/env python3
"""Read-only142 same116 native recovery-report visibility differential.

Only the documented report DISPLAY variable changes, then is restored.
No graph/constraint/horizon edits; no absent or unconstrained path is MET.
Python 3.6 compatible. Licensed manual bodies are read privately, never copied.
"""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import traceback

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
PARENT = B / 'full-soc-timing-combined-20261105-116'
OUT = B / 'full-soc-rdc-next-20261105-142'
PT = Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell')
LC = Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5')
STATUS = 'EXECUTED_SAME116_READ_ONLY_RECOVERY_VISIBILITY_NOT_QUALIFIED'
PARENT_STATUS = 'EXECUTED_SAME_MAPPED_DC_PT_AND_FULL_FM_NOT_QUALIFIED'
STATE_SHA = '7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f'
FAILED126 = B / 'full-soc-coverage-rdc-20261105-126'
FAILED126_SHA = 'e6b6bd0ede831b18db2ed30633802ac88db8035e8198edf38f66fd18c88237fa'
MAPPED_SHA = '16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292'
SVF_SHA = '2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a'
STA_SHA = '7f344a3c017b6de915b522aef798be5fcae06119592391008f16e75841b2aed3'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE_SHA = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
DB_SHAS = {'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
           'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}
BASE = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
SINKS = [(BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg','SDN','DSNQV0_12TR40'),
         (BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg','SDN','DSNQNV0_12TR40')]
SINKS += [(BASE+'aonrst_catch/reset_n_catch_reg/reg_%d/q_reg'%i,'RDN','DRNQV0_12TR40') for i in range(3)]
# Exact same116 instance ports: the second PMU cell is DSNQNV, with QN.
SINK_OUTPUTS = ['Q', 'QN', 'Q', 'Q', 'Q']
HF_SOURCE = 'io_pads_aon_erst_n_i_ival'
LF_SOURCE = BASE+'u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q'
MODE_BITS = {'RET1N':1,'EMA[2]':0,'EMA[1]':1,'EMA[0]':0,'EMAW[1]':0,'EMAW[0]':0}
CHECK_TYPES = 'setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):
            h.update(data)
    return h.hexdigest()


def ident(path):
    path = Path(path)
    need(path.is_file(), 'required input missing: '+str(path))
    a = path.stat(); digest = sha(path); z = path.stat()
    need((a.st_size,a.st_mtime_ns,a.st_ino)==(z.st_size,z.st_mtime_ns,z.st_ino), 'input changed during hash')
    return dict(path=str(path),bytes=a.st_size,sha256=digest)


def load(path):
    def unique(items):
        value = {}
        for key, item in items:
            need(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    return json.loads(Path(path).read_text(),object_pairs_hook=unique)


def dump(path,value):
    Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def tq(value):
    value = str(value)
    need(not any(c in value for c in '{}\r\n\t'), 'unsafe Tcl literal')
    return '{'+value+'}'


def guarded(body, marker):
    return ('if {[catch {\n'+body+'\n} xu_error xu_options]} {\n'
            'puts stderr "XU_FATAL: $xu_error"\n'
            'if {[dict exists $xu_options -errorinfo]} {puts stderr [dict get $xu_options -errorinfo]}\n'
            'exit 1\n}\nputs '+tq(marker)+'\nexit 0\n')


def checked_receipt(record):
    need(isinstance(record,dict) and set(record)=={'path','bytes','sha256'}, 'invalid original identity record')
    need(ident(record['path'])==record,'original bytes/hash differ: '+record['path'])
    return record


def preflight116(parent=PARENT):
    parent = Path(parent)
    need(sha(parent/'state.json')==STATE_SHA,'actual116 final state differs')
    state = load(parent/'state.json')
    need(state['status']==PARENT_STATUS and state['qualification']=='NOT_QUALIFIED' and
         state['frozen_inputs_unchanged'] is True and not state['frozen_after_observation_errors'] and
         state['frozen_before']==state['frozen_after'] and len(state['frozen_before'])==274,
         'actual116 complete own DC/PT/FM freeze required')
    records = {str(parent/'state.json'):ident(parent/'state.json')}
    for name, record in state['frozen_before'].items():
        need(record['path']==name,'original path/key differs')
        records[name]=checked_receipt(record)
    for key,digest in [('final_mapped',MAPPED_SHA),('final_svf',SVF_SHA)]:
        need(state[key]['sha256']==digest,'same final116 target differs')
        record = checked_receipt(state[key]); records[record['path']]=record
    labels = [('dc','XU_COMBINED116_DC_DONE_NOT_QUALIFIED'),
              ('pt','XU_COMBINED116_PT_DIAGNOSTIC_DONE_NOT_QUALIFIED'),('fm','XU_FULL_SOC_FORMALITY_PASS')]
    need([r['label'] for r in state['runs']]==[x[0] for x in labels],'116 native run ordering differs')
    for run,(label,marker) in zip(state['runs'],labels):
        need(run['returncode']==0 and not run['errors'] and run['marker_count']==1,'116 native receipt failed')
        for key in ('log','script'):
            r=checked_receipt(run[key]); records[r['path']]=r
        log=Path(run['log']['path']).read_text(errors='replace')
        need(sum(line.strip()==marker for line in log.splitlines())==1 and
             not re.search(r'^\s*(?:Error:|Error-|XU_FATAL:|XU_FULL_SOC_FORMALITY_FAIL|XU_FULL_SOC_FORMALITY_SCRIPT_ERROR)',log,re.M),
             '116 original native log failed: '+label)
        if label=='fm':
            need(sum(s.strip()=='Verification SUCCEEDED' for s in log.splitlines())==1 and
                 re.findall(r'^\s*(\d+) Passing compare points\s*$',log,re.M)==['41462'],'116 own full FM success differs')
    for group in ('reports','audits'):
        for record in state[group].values():
            r=checked_receipt(record); records[r['path']]=r
    need(sha(parent/'sta.tcl')==STA_SHA,'actual executed116 STA script differs')
    libs=[r for r in records.values() if r['path'].endswith('.db')]
    need(len(libs)==2 and {r['sha256'] for r in libs}==DB_SHAS,'exact two SS libraries required')
    source=(parent/'sta.tcl').read_text()
    wrapper='if {[catch {\n'; boundary='redirect -file units.rpt {report_units}\n'
    need(source.startswith(wrapper) and source.count(boundary)==1 and source.count('read_verilog mapped.v\n')==1,
         'exact116 STA preamble boundary differs')
    prefix=source[len(wrapper):source.index(boundary)]
    prefix=prefix.replace('read_verilog mapped.v\n','read_verilog '+tq(parent/'mapped.v')+'\n')
    sources=re.findall(r'^source \{([^{}]+)\}$',prefix,re.M)
    need(len(sources)==2 and {sha(p) for p in sources}=={SDC_SHA,SCOPE_SHA},'original116 SDC/scope source differs')
    need(not re.search(r'\b(?:set_false_path|set_case_analysis|create_clock|set_disable_timing|set_propagated_clock)\b',prefix),
         'unexpected constraint mutation in original preamble')
    need(sha(FAILED126/'state.json')==FAILED126_SHA,'original failed126 terminal differs')
    failed=load(FAILED126/'state.json')
    need(failed['status']=='FAILED_NOT_QUALIFIED' and failed['qualification']=='NOT_QUALIFIED' and
         failed['frozen_inputs_unchanged'] is True and not failed['frozen_after_observation_errors'] and
         failed['frozen_before']==failed['frozen_after'],'original failed126 freeze differs')
    need(len(failed['runs'])==2 and failed['runs'][0]['returncode']==0 and
         failed['runs'][0]['marker_count']==1 and not failed['runs'][0]['errors'] and
         failed['runs'][1]['returncode']==1 and failed['runs'][1]['marker_count']==0,
         'exact failed126 native run receipts differ')
    expected_missing='XU_FATAL: exact pin identity missing: '+SINKS[1][0]+'/Q'
    need(failed['runs'][1]['errors'].count('Error: Nothing matched for -of_objects collection (SEL-005)')==2017 and
         failed['runs'][1]['errors'].count(expected_missing)==1 and
         len(failed['runs'][1]['errors'])==2018,'exact failed126 native symptoms differ')
    records[str(FAILED126/'state.json')]=ident(FAILED126/'state.json')
    for record in list(failed['frozen_before'].values())+list(failed['outputs'].values())+[failed['producer']]:
        actual=checked_receipt(record)
        need(actual['path'] not in records or records[actual['path']]==actual,'failed126/116 shared input receipt differs')
        records[actual['path']]=actual
    return state,records,prefix


def coverage_rows(text):
    """Parse wrapped PT coverage details; require every status line be owned."""
    blocks=[]; current=None
    for line in text.splitlines():
        if line and not line[0].isspace():
            if current is not None: blocks.append(current)
            current=[line]
        elif current is not None: current.append(line)
    if current is not None: blocks.append(current)
    result=[]
    for block in blocks:
        if not (block[0].startswith('u_soc/') or block[0].startswith('u_shared/')): continue
        pin=block[0].split()[0]; rest=' '.join(block[1:])
        check=re.search(r'\b('+CHECK_TYPES+r')\b',rest)
        status=re.search(r'\b(untested|violated|met)\b',rest,re.I)
        need(check is not None,'unparsed native coverage check: '+pin)
        cond=re.search(r'sdf_cond\(([^()]*)\)',rest)
        before=rest[:check.start()].split()
        related,clock=(before if len(before)==2 else (None,None))
        if status is not None:
            reason=rest[status.end():].strip().split()
            parsed_status=status.group(1).lower(); slack=None; reason=reason[0] if reason else None
        else:
            # Native -status_details met rows carry numeric Slack and Reason,
            # without a literal "met" word. Rounded zero is kept ambiguous.
            tail=next((s for s in reversed(block[1:]) if s.strip()),'')
            numeric=re.fullmatch(r'\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s+(-|\w+)\s*',tail)
            need(numeric is not None and len(before)==2,'unparsed native numeric coverage detail: '+pin)
            slack=numeric.group(1); value=float(slack)
            need(math.isfinite(value),'nonfinite native numeric coverage slack: '+pin)
            parsed_status='met' if value>0 else ('violated' if value<0 else 'ROUNDED_ZERO_UNKNOWN')
            reason=numeric.group(2)
        result.append(dict(pin=pin,check=check.group(1),status=parsed_status,
                           condition=cond.group(1) if cond else None,reason=reason,
                           related_pin=related,clock=clock,reported_slack=slack))
    need(len(result)==len(re.findall(r'\buntested\s+(?:constant_disabled|false_paths|no_endpoint_clock|no_clock|unknown)\b',text))
         or any(r['status']!='untested' for r in result),'coverage detail ownership/count differs')
    return result


ACTUAL132 = B / 'full-soc-coverage-rdc-20261105-132'
ACTUAL132_SHA = '2f6b6147e384851f194c1f46cb21dfb8c574d1ea3abab136f80d32bd2a21a5b5'
WORKER132_SHA = 'd40a163adf3fe13cbce0a9ecee9258929a07eb53068781a7ce9054694c152f91'
OPTIONS132_SHA = '36aac9b70fb7d089ddba3ffba7e5a49e1486932eedb785d3e84288528a9434fb'
MARKER = 'XU_RDC142_SAME116_READ_ONLY_VISIBILITY_DONE_NOT_QUALIFIED'
ARC_FIELDS = ['sense', 'when', 'sdf_cond', 'is_disabled', 'is_user_disabled', 'is_db_inherited_disabled']


def preflight(parent=PARENT, actual132=ACTUAL132):
    original, records, prefix = preflight116(parent)
    actual132 = Path(actual132)
    need(sha(actual132/'state.json') == ACTUAL132_SHA, 'exact actual132 terminal differs')
    s = load(actual132/'state.json')
    need(s['status'] == 'EXECUTED_SAME116_READ_ONLY_COVERAGE_RDC_NOT_QUALIFIED' and
         s['qualification'] == 'NOT_QUALIFIED' and s['frozen_inputs_unchanged'] is True and
         not s['frozen_after_observation_errors'] and s['frozen_before'] == s['frozen_after'] and
         len(s['frozen_before']) == 359 and len(s['outputs']) == 83,
         'actual132 original terminal/freeze inventory differs')
    need(s['parent']['state']['sha256'] == STATE_SHA and
         s['parent']['mapped']['sha256'] == MAPPED_SHA and s['parent']['svf']['sha256'] == SVF_SHA,
         'actual132 same116 parent differs')
    need(len(s['runs']) == 2, 'actual132 two native runs required')
    for run, marker in zip(s['runs'], ['XU_COVERAGE132_INSTALLED_DOCS_DONE_NOT_QUALIFIED',
                                     'XU_COVERAGE132_SAME116_READ_ONLY_DIAGNOSTIC_DONE_NOT_QUALIFIED']):
        need(run['returncode'] == 0 and run['marker_count'] == 1 and not run['errors'],
             'actual132 native receipt differs')
        raw = Path(run['log']['path']).read_text(errors='replace')
        need(sum(x.strip() == marker for x in raw.splitlines()) == 1 and not native_errors(raw),
             'actual132 original native log failed')
    need(s['producer']['sha256'] == WORKER132_SHA, 'actual132 original worker differs')
    records[str(actual132/'state.json')] = ident(actual132/'state.json')
    for record in list(s['frozen_before'].values()) + list(s['outputs'].values()) + [s['producer']]:
        r = checked_receipt(record)
        need(r['path'] not in records or records[r['path']] == r, '132/116 shared receipt differs')
        records[r['path']] = r
    need(sha(actual132/'installed-options.json') == OPTIONS132_SHA, 'original installed options differ')
    options = load(actual132/'installed-options.json')
    for r in options['manual_sha256'].values():
        r = checked_receipt(r); records[r['path']] = r
    manual = Path(options['manual_sha256']['man-report_timing.txt']['path']).read_text(errors='replace')
    for flag in ('-from', '-to', '-delay_type', '-exceptions', '-slack_lesser_than', '-max_paths', '-nworst'):
        need(flag in manual, 'installed report_timing manual lacks ' + flag)
    need(re.search(r'\bunconstrained\b', manual, re.I) is not None,
         'installed report_timing unconstrained documentation absent')
    display_manual = Path(options['manual_sha256']['man-timing_report_unconstrained_paths.txt']['path']).read_text()
    need('timing_report_unconstrained_paths' in display_manual, 'installed DISPLAY manual absent')
    need(set(['from_pin','to_pin'] + ARC_FIELDS) <= set(options['attributes']['timing_arc']),
         'original native arc attributes absent')
    return original, s, records, prefix


def native_errors(raw):
    return [s for s in raw.splitlines() if re.match(r'^\s*(?:Error:|Error-|Fatal:|XU_FATAL:)', s)]


def query_inventory():
    result = []
    for i in range(5):
        result.append(dict(index=i, source_kind='HF_RESET', original='unconstrained-hf-%d-recovery.rpt' % i))
    for i in range(2):
        result.append(dict(index=i, source_kind='ANY_ENDPOINT_SOURCE', original='any_endpoint_source-%d-recovery.rpt' % i))
    return result


def report_command(source, endpoint, variant):
    command = 'report_timing' + (' -from ' + source if source else '') + ' -to ' + endpoint + ' -delay_type max'
    if variant == 'original132_filtered':
        return command + ' -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded'
    need(variant in ('matched_filtered', 'unfiltered'), 'unknown report variant')
    command += ' -exceptions all'
    if variant == 'matched_filtered':
        command += ' -slack_lesser_than 1000000'
    return command


TCL_HELPERS = r'''
proc xu_row {f values} {
 set clean {}
 foreach value $values {lappend clean [string map [list "\\" "\\\\" "\t" "\\t" "\r" "\\r" "\n" "\\n"] $value]}
 puts $f [join $clean "\t"]
 flush $f
}
proc xu_pin {name} {
 set p [get_pins -quiet $name]
 if {[sizeof_collection $p]!=1 || [get_object_name $p] ne $name} {error "exact pin identity missing: $name"}
 return $p
}
proc xu_arc_rows {f owner arcs} {
 set index 0
 foreach_in_collection arc $arcs {
  # Native timing_arc has no full_name. Only name the from/to pin collections.
  set from [get_attribute $arc from_pin]
  set to [get_attribute $arc to_pin]
  if {[sizeof_collection $from]!=1 || [sizeof_collection $to]!=1} {error {arc endpoints not exact}}
  set fn [get_object_name $from]; set tn [get_object_name $to]
  set scope [join [list $owner $index $fn $tn] {|}]
  set values [list $owner $index $fn $tn $scope]
  foreach field {sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled} {
   lappend values [get_attribute $arc $field]
  }
  xu_row $f $values
  incr index
 }
}
'''


def differential_tcl():
    body = ''
    for item in query_inventory():
        i = item['index']; tag = '%s-%d' % (item['source_kind'].lower(), i)
        body += 'set xu_to [xu_pin ' + tq(SINKS[i][0] + '/' + SINKS[i][1]) + ']\n'
        endpoint = '$xu_to'
        source = '$hf' if item['source_kind'] == 'HF_RESET' else None
        for variant in ('original132_filtered', 'matched_filtered', 'unfiltered'):
            name = tag + '-' + variant + '.rpt'
            command = report_command(source, endpoint, variant)
            canonical = report_command('[get_object_name $hf]' if source else None, '[get_object_name '+endpoint+']', variant)
            body += 'puts ' + tq('XU142_REPORT_BEGIN ' + name) + '\n'
            body += 'set xu_command [list ' + command + ']\n'
            body += 'xu_row $qf [list ' + str(i) + ' ' + item['source_kind'] + ' ' + variant + ' ' + tq(name) + ' [list ' + canonical + '] $xu_command]\n'
            body += 'redirect -file ' + tq(name) + ' $xu_command\n'
            body += 'puts ' + tq('XU142_REPORT_END ' + name) + '\n'
    return body


def diagnostic_tcl(prefix):
    body = prefix + TCL_HELPERS
    body += 'redirect -file coverage-initial.rpt {report_analysis_coverage -status_details untested}\n'
    body += 'redirect -file exceptions-initial.rpt {report_exceptions}\nredirect -file case-initial.rpt {report_case_analysis -all}\n'
    body += 'redirect -file clocks-initial.rpt {report_clock -attributes}\n'
    body += 'set hf [get_ports -quiet ' + tq(HF_SOURCE) + ']\n'
    body += 'if {[sizeof_collection $hf]!=1 || [get_object_name $hf] ne ' + tq(HF_SOURCE) + '} {error {exact HF reset port missing}}\n'
    body += 'set af [open reset-ck-async-arcs.tsv w]\nxu_row $af {owner index from_pin to_pin scope sense when sdf_cond is_disabled is_user_disabled is_db_inherited_disabled}\n'
    for i, (cell, apin, ref) in enumerate(SINKS):
        body += 'set c [get_cells -quiet ' + tq(cell) + ']\n'
        body += 'if {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne ' + tq(ref) + '} {error {same116 cell differs}}\n'
        body += 'set outputs [get_pins -of_objects $c -filter {direction == out}]\n'
        body += 'if {[sizeof_collection $outputs]!=1 || [get_object_name $outputs] ne ' + tq(cell+'/'+SINK_OUTPUTS[i]) + '} {error {same116 output differs}}\n'
        body += 'xu_arc_rows $af ' + tq(cell) + ' [get_timing_arcs -from [xu_pin ' + tq(cell+'/CK') + '] -to [xu_pin ' + tq(cell+'/'+apin) + ']]\n'
    body += 'close $af\nset qf [open query-commands.tsv w]\nxu_row $qf {index source_kind variant report command native_invocation}\n'
    body += display_queries_tcl()
    body += 'redirect -file coverage-final.rpt {report_analysis_coverage -status_details untested}\n'
    body += 'redirect -file exceptions-final.rpt {report_exceptions}\nredirect -file case-final.rpt {report_case_analysis -all}\n'
    body += 'redirect -file clocks-final.rpt {report_clock -attributes}\n'
    return guarded(body, MARKER)



def display_queries_tcl():
    body = ''
    body += 'set df [open report-display-policy.tsv w]\nxu_row $df {field value}\n'
    body += 'set xu_report_original [get_app_var timing_report_unconstrained_paths]\nxu_row $df [list original $xu_report_original]\n'
    body += 'set xu_display_rc [catch {\nset_app_var timing_report_unconstrained_paths true\n'
    body += 'set xu_display_active [get_app_var timing_report_unconstrained_paths]\nxu_row $df [list active $xu_display_active]\n'
    body += 'if {$xu_display_active ne "true"} {error {DISPLAY not true}}\n'
    body += differential_tcl()
    body += '} xu_display_error xu_display_options]\nset_app_var timing_report_unconstrained_paths $xu_report_original\n'
    body += 'set xu_restored [get_app_var timing_report_unconstrained_paths]\nxu_row $df [list restored $xu_restored]\nclose $df\nclose $qf\n'
    body += 'if {$xu_restored ne $xu_report_original} {error {DISPLAY not restored}}\n'
    body += 'if {$xu_display_rc} {return -options $xu_display_options $xu_display_error}\n'
    return body


def tsv(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f, delimiter='\t'))


def normalized_report(text):
    return '\n'.join(line for line in text.splitlines() if not re.match(r'^Date\s*:', line))


def report_observation(raw):
    # Report visibility only. Text alone cannot establish a finite recovery check.
    unconstrained = len(re.findall(r'\(Path is unconstrained\)', raw))
    starts = re.findall(r'^\s*Startpoint:\s*(.+)$', raw, re.M)
    endpoints = re.findall(r'^\s*Endpoint:\s*(.+)$', raw, re.M)
    slacks = re.findall(r'^\s*slack\s+\(([^)]+)\)\s+([^\s]+)', raw, re.M)
    empty = bool(re.search(r'^\s*No constrained paths\.\s*$', raw, re.M))
    if unconstrained:
        status = 'UNCONSTRAINED_PATH_DISPLAY_ONLY_NOT_RECOVERY_PROOF'
    elif starts and endpoints:
        status = 'PATH_TEXT_PRESENT_DIAGNOSTIC_ONLY'
    elif empty:
        status = 'NO_PATH_UNKNOWN'
    else:
        status = 'UNRECOGNIZED_REPORT_UNKNOWN'
    return dict(status=status, unconstrained_markers=unconstrained, startpoints=starts,
                endpoints=endpoints, reported_slacks=slacks, no_constrained_paths=empty,
                qualification='NOT_QUALIFIED')


def analyse(out, parent=PARENT, actual132=ACTUAL132):
    out = Path(out); parent = Path(parent); actual132 = Path(actual132)
    original = coverage_rows((parent/'analysis-coverage.rpt').read_text())
    initial = coverage_rows((out/'coverage-initial.rpt').read_text())
    final = coverage_rows((out/'coverage-final.rpt').read_text())
    canonical = lambda rows: sorted(json.dumps(r, sort_keys=True) for r in rows)
    need(len(original) == 27124 and canonical(original) == canonical(initial) == canonical(final),
         'full 27124 untested field multiset changed')
    for kind in ('exceptions', 'case', 'clocks'):
        first = (out/(kind+'-initial.rpt')).read_text(); last = (out/(kind+'-final.rpt')).read_text()
        need(normalized_report(first) == normalized_report(last), kind+' report changed')
        history = actual132 / (kind+'.rpt' if kind == 'clocks' else kind+'-final.rpt')
        need(normalized_report(first) == normalized_report(history.read_text()), kind+' differs from actual132')
    display = tsv(out/'report-display-policy.tsv')
    need([r['field'] for r in display] == ['original','active','restored'] and
         display[0]['value'] == display[2]['value'] and display[1]['value'] == 'true',
         'DISPLAY active/restoration receipt differs')
    arcs = tsv(out/'reset-ck-async-arcs.tsv')
    need(len(arcs) == 10, 'exact 10 CK/async native arcs required')
    historical = tsv(actual132/'reset-design-arcs.tsv')
    for cell, apin, ref in SINKS:
        target = cell+'/'+apin
        current = [r for r in arcs if r['owner'] == cell]
        old = [r for r in historical if r['from_pin'] == cell+'/CK' and r['to_pin'] == target]
        fields = ['from_pin','to_pin'] + ARC_FIELDS
        signature = lambda rows: sorted(tuple(r[k] for k in fields) for r in rows)
        need(len(current) == 2 and {r['sense'] for r in current} == {'setup_rise_clk_rise','hold_rise_clk_rise'} and
             all(r['is_disabled'] == 'false' and r['is_user_disabled'] == 'false' for r in current) and
             signature(current) == signature(old), 'native async check arcs differ: '+cell)
        for r in current:
            need(r['scope'] == '|'.join([r['owner'], r['index'], r['from_pin'], r['to_pin']]), 'arc scope invalid')
    commands = tsv(out/'query-commands.tsv')
    need(len(commands) == 21, 'exact 21 report queries required')
    observations = []
    for item in query_inventory():
        i = item['index']; kind = item['source_kind']; tag = '%s-%d' % (kind.lower(), i)
        history = report_observation((actual132/item['original']).read_text())
        need(history['status'] == 'NO_PATH_UNKNOWN', 'historical unknown control differs')
        variants = {}
        for variant in ('original132_filtered','matched_filtered','unfiltered'):
            rows = [r for r in commands if r['index'] == str(i) and r['source_kind'] == kind and r['variant'] == variant]
            need(len(rows) == 1, 'query command duplicate/missing')
            command = rows[0]['command']; expected = report_command(HF_SOURCE if kind == 'HF_RESET' else None,
                                                                     SINKS[i][0]+'/'+SINKS[i][1], variant)
            need(command == expected, 'executed report command differs')
            name = tag+'-'+variant+'.rpt'; need(rows[0]['report'] == name, 'query filename differs')
            raw = (out/name).read_text(); need(not native_errors(raw), 'native error inside report')
            variants[variant] = dict(report=ident(out/name), observation=report_observation(raw))
        matched = variants['matched_filtered']['observation']; unfiltered = variants['unfiltered']['observation']
        gap = matched['status'] == 'NO_PATH_UNKNOWN' and unfiltered['unconstrained_markers'] > 0
        verdict = 'FILTER_HID_UNCONSTRAINED_DISPLAY_ONLY_NOT_RECOVERY_PROOF' if gap else 'FILTER_DISPLAY_HYPOTHESIS_NOT_ESTABLISHED'
        observations.append(dict(index=i, source_kind=kind, historical132=history,
                                 variants=variants, visibility_verdict=verdict, recovery_qualification='NOT_PROVEN'))
    result = dict(schema='xu-rdc142-visibility-analysis-v1', qualification='NOT_QUALIFIED',
                  full_untested_multiset_equal_116_132_initial_final=True, untested_rows=27124,
                  case_exceptions_clocks_same_as132_and_unchanged=True, async_ck_check_arcs=10,
                  query_count=21, reports=observations,
                  limitations=['Unconstrained report text explains display visibility only; no recovery MET or release-phase qualification follows.',
                               'No clock, case, cut, exception, propagation, edge/horizon or scope is changed.',
                               'PTE-052 is retained; co-occurrence does not establish sole causality.',
                               'The 416 active macro min-period MET and 10416 inactive constant-disabled checks are actual132 evidence, not whole-SoC150MHz qualification.',
                               'Arbitrary asynchronous release, reset pulse/skew, metastability, UART and full150MHz eligibility remain open.'])
    dump(out/'analysis.json', result)
    return result


def run_native(out, state, content, environment):
    script = out/'diagnosis.tcl'; script.write_text(content)
    log = out/'diagnosis.log'
    state['phase'] = 'native-read-only-visibility'; dump(out/'state.json', state)
    started = time.time()
    with log.open('xb') as f:
        p = subprocess.Popen([str(PT), '-f', script.name], cwd=str(out), stdin=subprocess.DEVNULL,
                             stdout=f, stderr=subprocess.STDOUT, env=environment, start_new_session=True)
        state['native_pid'] = p.pid; dump(out/'state.json', state)
        try:
            rc = p.wait(timeout=21600)
        except BaseException:
            os.killpg(p.pid, signal.SIGKILL); p.wait(); raise
    raw = log.read_text(errors='replace')
    record = dict(command=[str(PT), '-f', script.name], returncode=rc, started_epoch=started,
                  finished_epoch=time.time(), errors=native_errors(raw),
                  marker_count=sum(s.strip() == MARKER for s in raw.splitlines()), script=ident(script), log=ident(log))
    state['runs'].append(record); state.pop('native_pid', None); dump(out/'state.json', state)
    need(rc == 0 and record['marker_count'] == 1 and not record['errors'], 'native142 read-only query failed')
    need(not re.search(r'\(ATTR-1\)', raw), '142 must not query timing_arc full_name')
    for item in query_inventory():
        tag = '%s-%d' % (item['source_kind'].lower(), item['index'])
        for variant in ('original132_filtered','matched_filtered','unfiltered'):
            name = tag+'-'+variant+'.rpt'
            for boundary in ('BEGIN', 'END'):
                need(sum(s.strip() == 'XU142_REPORT_'+boundary+' '+name for s in raw.splitlines()) == 1,
                     'report boundary receipt missing/duplicated')


def main():
    OUT.mkdir(exist_ok=False)
    state = dict(schema='xu-rdc142-execution-v1', status='RUNNING_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                 pid=os.getpid(), started_epoch=time.time(), runs=[], producer=ident(Path(__file__).resolve()), frozen_capture_complete=False,
                 scope='Exact actual116 whole-SoC mapped/SS/SDC/scope/ideal-clock context; seven unknown recovery report visibility probes',
                 constraints_policy='Only documented report DISPLAY true then restore; no graph/clock/case/cut/exception/propagation/edge/horizon/scope edits.')
    dump(OUT/'state.json', state); frozen = {}
    try:
        parent, actual132, frozen, prefix = preflight()
        for p in (Path(__file__).resolve(), PT): frozen[str(p)] = ident(p)
        state['parent116'] = dict(state=ident(PARENT/'state.json'), mapped=parent['final_mapped'], svf=parent['final_svf'])
        state['actual132_state'] = ident(ACTUAL132/'state.json')
        state['frozen_before'] = dict(frozen); state['frozen_capture_complete'] = True; dump(OUT/'state.json', state)
        environment = os.environ.copy(); environment['SYNOPSYS_LC_ROOT'] = str(LC)
        environment['PATH'] = str(LC/'bin') + os.pathsep + environment.get('PATH', '')
        need((LC/'bin').is_dir(), 'original Library Compiler runtime required')
        run_native(OUT, state, diagnostic_tcl(prefix), environment)
        analysis = analyse(OUT)
        state['analysis'] = ident(OUT/'analysis.json'); state['status'] = STATUS
        state['summary'] = dict(untested_rows=27124, report_queries=21,
                               visibility_gaps=sum(r['visibility_verdict'].startswith('FILTER_HID_') for r in analysis['reports']),
                               recovery_qualification='NOT_PROVEN')
    except BaseException as error:
        state.update(status='FAILED_NOT_QUALIFIED', error=type(error).__name__+': '+str(error), traceback=traceback.format_exc())
        raise
    finally:
        observed = {}; errors = []
        for name in frozen:
            try: observed[name] = ident(name)
            except BaseException as error: errors.append(name+': '+repr(error))
        state['frozen_after'] = observed; state['frozen_after_observation_errors'] = errors
        state['frozen_inputs_unchanged'] = state['frozen_capture_complete'] and observed == frozen and not errors
        if not state['frozen_capture_complete']:
            state['integrity_observation_status'] = 'PRECHECK_FAILED_NO_COMPLETE_FREEZE'
        elif not state['frozen_inputs_unchanged']:
            state.update(status='FAILED_NOT_QUALIFIED', integrity_error='input identities changed')
        state['finished_epoch'] = time.time()
        state['outputs'] = {str(p.relative_to(OUT)):ident(p) for p in sorted(OUT.rglob('*'))
                            if p.is_file() and p.name not in ('state.json','driver.log')}
        dump(OUT/'state.json', state); print(state['status'], flush=True)


if __name__ == '__main__':
    main()
