#!/usr/bin/env python3
"""Read-only actual116 macro-mode, recovery and structural reset diagnostics.

Never edits RTL, mapped netlists, libraries or constraints. The sole additional
set_app_var is the installed/documented unconstrained-path DISPLAY option,
restored before final coverage collection. No missing path is called MET.
Python 3.6 compatible. Server manual bodies stay in a private subdirectory.
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
OUT = B / 'full-soc-coverage-rdc-20261105-132'
PT = Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell')
LC = Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5')
STATUS = 'EXECUTED_SAME116_READ_ONLY_COVERAGE_RDC_NOT_QUALIFIED'
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


def preflight(parent=PARENT):
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


def documentation_tcl():
    body='file mkdir private-manuals\nset f [open docs-index.tsv w]\nputs $f "command\\tcatch_rc\\tmessage"\n'
    commands=['get_timing_arcs','get_lib_timing_arcs','report_analysis_coverage','report_timing',
              'get_timing_paths','report_disable_timing','all_fanin','report_case_analysis',
              'report_clock','get_app_var','timing_report_unconstrained_paths','PTE-052',
              'get_attribute','get_object_name','get_pins','get_cells','get_nets','all_connected','sizeof_collection']
    for name in commands:
        body+='set rc [catch {redirect -file '+tq('private-manuals/man-'+name+'.txt')+' {man '+name+'}} msg]\n'
        body+='puts $f [join [list '+tq(name)+' $rc $msg] "\\t"]\n'
    body+='close $f\n'
    for kind in ('pin','port','cell','clock','timing_arc','lib_timing_arc'):
        body+='redirect -file '+tq('attributes-'+kind+'.txt')+' {list_attributes -application -class '+kind+'}\n'
    return guarded(body,'XU_COVERAGE132_INSTALLED_DOCS_DONE_NOT_QUALIFIED')


TCL_HELPERS = r'''
proc xu_row {f values} {
 set clean {}
 foreach value $values {lappend clean [string map [list "\\" "\\\\" "\t" "\\t" "\r" "\\r" "\n" "\\n"] $value]}
 puts $f [join $clean "\t"]
 flush $f
}
set xu_unknown [open unknown-queries.tsv w]
xu_row $xu_unknown {scope field status detail}
set xu_collections [open collection-observations.tsv w]
xu_row $xu_collections {scope attribute count status names}
proc xu_names {value} {
 if {[sizeof_collection $value]==0} {return {}}
 return [get_object_name $value]
}
proc xu_collection {object attribute value} {
 global xu_collections
 set n [sizeof_collection $value]
 set names [xu_names $value]
 set status NONEMPTY
 if {$n==0} {set status EMPTY_COLLECTION}
 xu_row $xu_collections [list [get_object_name $object] $attribute $n $status $names]
 return $names
}
proc xu_nets {pin} {
 # Native pin.net is a collection. Literal constants may have no net object;
 # preserve emptiness rather than call get_nets on an unmatched selection.
 set ns [get_attribute -quiet $pin net]
 xu_collection $pin net $ns
 return $ns
}
proc xu_attr {object attribute collection} {
 global xu_unknown
 if {[catch {get_attribute -quiet $object $attribute} value]} {
  xu_row $xu_unknown [list [get_object_name $object] $attribute QUERY_ERROR $value]
  return QUERY_ERROR
 }
 if {$collection} {
  if {[catch {xu_collection $object $attribute $value} names]} {
   xu_row $xu_unknown [list [get_object_name $object] $attribute COLLECTION_NAME_ERROR $names]
   return COLLECTION_NAME_ERROR
  }
  return $names
 }
 if {$value eq {} && [regexp {^(max|min)_(rise|fall)_(arrival|slack)$} $attribute]} {
  xu_row $xu_unknown [list [get_object_name $object] $attribute ABSENT_NATIVE_ATTRIBUTE NOT_INFERRED]
  return ABSENT_NATIVE_ATTRIBUTE
 }
 return $value
}
proc xu_capture {name command} {
 global xu_unknown
 if {[catch {redirect -file $name {uplevel #0 $command}} message]} {
  xu_row $xu_unknown [list $name command QUERY_ERROR $message]
  set f [open ${name}.unavailable.txt w]; puts $f $message; close $f
 }
}
proc xu_pin {name} {
 set p [get_pins -quiet $name]
 if {[sizeof_collection $p]!=1 || [get_object_name $p] ne $name} {error "exact pin identity missing: $name"}
 return $p
}
proc xu_arcs {f owner arcs fromfield tofield attributes} {
 set index 0
 foreach_in_collection arc $arcs {
  set values [list $owner $index]; incr index
  foreach field $attributes {
   set collection [expr {$field eq $fromfield || $field eq $tofield}]
   lappend values [xu_attr $arc $field $collection]
  }
  xu_row $f $values
 }
}
proc xu_connections {f tag pin} {
 set ns [xu_nets $pin]
 foreach_in_collection net $ns {
  foreach_in_collection object [all_connected -leaf $net] {
   xu_row $f [list $tag [get_object_name $pin] [get_object_name $net] [get_object_name $object] [get_attribute $object object_class] [get_attribute $object direction]]
  }
 }
}
proc xu_fanin {pin} {
 puts [xu_names [all_fanin -flat -startpoints_only -to $pin]]
}
proc xu_structural_consumers {f tag start} {
 # Structural all_connected traversal; never stops at timing-disabled arcs.
 # Sequential cells terminate the trace; every combination output is followed.
 set front [list [get_object_name $start]]; set visited [dict create]; set count 0
 while {[llength $front]>0} {
  set next {}
  foreach name $front {
   if {[dict exists $visited $name]} {continue}
   dict set visited $name 1
   incr count
   if {$count>4096} {error {bounded reset consumer traversal exceeded4096 outputs}}
   set p [xu_pin $name]
   foreach_in_collection net [xu_nets $p] {
    foreach_in_collection object [all_connected -leaf $net] {
     set on [get_object_name $object]; set class [get_attribute $object object_class]
     set direction [get_attribute $object direction]
     if {$on eq $name} {continue}
     if {$class eq "port"} {xu_row $f [list $tag $name [get_object_name $net] $on $class $direction PORT_ENDPOINT]; continue}
     if {$class ne "pin" || $direction ne "in"} {error {unexpected reset Q leaf connection}}
     set c [get_cells -of_objects $object]
     if {[sizeof_collection $c]!=1 || [get_attribute $c is_hierarchical]} {error {reset Q consumer is not exact leaf}}
     set sequential [get_attribute $c is_sequential]
     if {![string is boolean -strict $sequential]} {error {reset Q consumer sequential classification unknown}}
     xu_row $f [list $tag $name [get_object_name $net] $on [get_attribute $c ref_name] $direction $sequential]
     if {!$sequential} {
      foreach_in_collection op [get_pins -of_objects $c -filter {direction == out}] {lappend next [get_object_name $op]}
     }
    }
   }
  }
  set front $next
 }
}
'''


def installed_options(out):
    out=Path(out)
    def manual(command): return (out/'private-manuals'/('man-'+command+'.txt')).read_text(errors='replace')
    for command in ('get_timing_arcs','get_lib_timing_arcs'):
        for flag in ('-from','-to','-of_objects'):
            need(flag in manual(command),'installed command documentation missing '+command+' '+flag)
    need('timing_report_unconstrained_paths' in manual('timing_report_unconstrained_paths'),
         'installed report-only flag documentation missing')
    for flag in ('-from','-to','-delay_type','-slack_lesser_than','-max_paths'):
        need(flag in manual('report_timing') and flag in manual('get_timing_paths'),'installed path flags missing')
    attrs={}
    for kind in ('pin','port','cell','clock','timing_arc','lib_timing_arc'):
        raw=(out/('attributes-'+kind+'.txt')).read_text(errors='replace')
        attrs[kind]=set(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)\s+'+kind+r'\s+(?:collection|boolean|float|string|double|integer)\b',raw,re.M))
    for kind,required in [('pin',{'constant_value','clocks','user_case_value','net'}),
                          ('cell',{'is_sequential','is_hierarchical','ref_name'}),
                          ('timing_arc',{'from_pin','to_pin','sense','when','sdf_cond','is_disabled','is_user_disabled'}),
                          ('lib_timing_arc',{'from_lib_pin','to_lib_pin','sense','when','sdf_cond'})]:
        need(required<=attrs[kind],'mandatory installed attribute missing: '+kind+' '+str(sorted(required-attrs[kind])))
    need(re.search(r'^net\s+pin\s+collection\b',(out/'attributes-pin.txt').read_text(),re.M) is not None,
         'installed pin.net must be a native collection')
    need('-quiet' in manual('get_attribute'),'installed get_attribute quiet option required')
    return dict(full_clock='full_clock_expanded' in manual('report_timing'),
                period_detail='-check_type' in manual('report_analysis_coverage'),
                attributes={k:sorted(v) for k,v in attrs.items()},
                manual_sha256={p.name:ident(p) for p in sorted((out/'private-manuals').glob('*.txt'))})


def diagnostic_tcl(prefix, options):
    attributes=options['attributes']
    arc_fields=[x for x in ('from_pin','to_pin','sense','when','sdf_cond','is_disabled','is_user_disabled',
        'is_db_inherited_disabled','delay_min','delay_max','delay_min_rise','delay_max_rise','delay_min_fall','delay_max_fall')
                if x in attributes['timing_arc']]
    lib_fields=[x for x in ('from_lib_pin','to_lib_pin','sense','when','sdf_cond','is_disabled','is_user_disabled')
                if x in attributes['lib_timing_arc']]
    pin_fields=[x for x in ('constant_value','case_value','user_case_value','clocks','launch_clocks',
        'constrained_launch_clocks','dynamic_clocks','is_async_pin','is_clock_pin',
        'max_rise_arrival','max_fall_arrival','min_rise_arrival','min_fall_arrival',
        'max_rise_slack','max_fall_slack','min_rise_slack','min_fall_slack','disable_timing') if x in attributes['pin']]
    collection_attrs={'clocks','launch_clocks','constrained_launch_clocks','dynamic_clocks'}
    body=prefix+TCL_HELPERS
    body+='redirect -file coverage-initial.rpt {report_analysis_coverage -status_details untested}\n'
    body+='redirect -file check-timing-initial.rpt {check_timing -verbose}\nredirect -file clocks.rpt {report_clock -attributes}\n'
    body+='redirect -file exceptions-initial.rpt {report_exceptions}\nredirect -file case-initial.rpt {report_case_analysis -all}\n'
    if options['period_detail']:
        body+='xu_capture period-all-status.rpt {report_analysis_coverage -check_type min_period -status_details {met violated untested}}\n'
    else:
        body+='xu_row $xu_unknown {period-all-status.rpt check_type ABSENT_FROM_INSTALLED_MANUAL NOT_INFERRED}\n'
    body+='set mf [open macro-mode-pins.tsv w]\nxu_row $mf {macro pin constant_value user_case_value clocks nets}\n'
    body+='set af [open macro-clock-arcs.tsv w]\nxu_row $af [list owner index '+' '.join(arc_fields)+']\n'
    body+='set lf [open macro-lib-clock-arcs.tsv w]\nxu_row $lf [list owner index '+' '.join(lib_fields)+']\n'
    body+='set seenlibs [dict create]\nset macrocount 0\n'
    body+='''foreach_in_collection c $xu_all_macros {
 incr macrocount
 set name [get_object_name $c]
 foreach pinname {RET1N EMA[2] EMA[1] EMA[0] EMAW[1] EMAW[0] CEN CLK} {
  set p [xu_pin ${name}/$pinname]
  if {[get_attribute $p direction] ne "in"} {error {macro mode/clock pin direction differs}}
  xu_row $mf [list $name $pinname [xu_attr $p constant_value 0] [xu_attr $p user_case_value 0] [xu_attr $p clocks 1] [xu_names [xu_nets $p]]]
 }
 set clk [xu_pin ${name}/CLK]
 set arcs [get_timing_arcs -from $clk -to $clk]
 if {[sizeof_collection $arcs]<32} {xu_row $xu_unknown [list $name CLK_SELF_ARCS COUNT_BELOW32 [sizeof_collection $arcs]]}
'''
    body+=' xu_arcs $af $name $arcs from_pin to_pin [list '+' '.join(arc_fields)+']\n'
    body+=''' set lc [get_lib_cells -of_objects $c]
 if {[sizeof_collection $lc]!=1} {error {macro actual library cell missing/ambiguous}}
 set ln [get_object_name $lc]
 if {![dict exists $seenlibs $ln]} {
  dict set seenlibs $ln 1
  set lp [get_lib_pins -quiet ${ln}/CLK]
  if {[sizeof_collection $lp]!=1} {error {macro actual library CLK missing}}
  set arcs [get_lib_timing_arcs -from $lp -to $lp]
'''
    body+='  xu_arcs $lf $ln $arcs from_lib_pin to_lib_pin [list '+' '.join(lib_fields)+']\n }\n}\n'
    body+='if {$macrocount!=336} {error {must visit exact336 actual macros}}\nclose $mf\nclose $af\nclose $lf\n'
    body+='set pf [open reset-pin-properties.tsv w]\nxu_row $pf {index pin attribute value}\n'
    body+='set nf [open reset-leaf-connections.tsv w]\nxu_row $nf {index pin net connected class direction}\n'
    body+='set cf [open reset-q-consumers.tsv w]\nxu_row $cf {index driver net consumer ref_or_class direction sequential_or_endpoint}\n'
    body+='set rf [open reset-design-arcs.tsv w]\nxu_row $rf [list owner index '+' '.join(arc_fields)+']\n'
    body+='set rlf [open reset-lib-arcs.tsv w]\nxu_row $rlf [list owner index '+' '.join(lib_fields)+']\n'
    body+='set tf [open reset-timing-paths.tsv w]\nxu_row $tf {index source_kind check count worst_slack status}\n'
    body+='set hf [get_ports -quiet '+tq(HF_SOURCE)+']\nset wdog [xu_pin '+tq(LF_SOURCE)+']\n'
    body+='if {[sizeof_collection $hf]!=1} {error {exact external reset port missing}}\n'
    body+='xu_capture external-reset-port.rpt [list report_attribute -application $hf]\n'
    full=' -path_type full_clock_expanded' if options['full_clock'] else ''
    for i,(cell,apin,ref) in enumerate(SINKS):
        body+='set c [get_cells -quiet '+tq(cell)+']\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne '+tq(ref)+'} {error {exact116 reset endpoint identity differs}}\n'
        output=SINK_OUTPUTS[i]
        body+='set actual_outputs [get_pins -of_objects $c -filter {direction == out}]\n'
        body+='if {[sizeof_collection $actual_outputs]!=1 || [get_object_name $actual_outputs] ne '+tq(cell+'/'+output)+'} {error {same116 exact reset output pin differs}}\n'
        body+='foreach pn {D CK '+output+' '+apin+'} {\n set p [xu_pin '+tq(cell+'/')+'$pn]\n'
        # Tcl does not concatenate braced literal+variable as a single word.
        body=body.replace('set p [xu_pin '+tq(cell+'/')+'$pn]', 'set p [xu_pin [format {%s/%s} '+tq(cell)+' $pn]]')
        for attr in pin_fields:
            body+=' xu_row $pf [list '+str(i)+' [get_object_name $p] '+tq(attr)+' [xu_attr $p '+tq(attr)+' '+str(int(attr in collection_attrs))+']]\n'
        body+=' xu_connections $nf '+str(i)+' $p\n}\n'
        if i in (0,4):
            body+='xu_structural_consumers $cf '+str(i)+' [xu_pin '+tq(cell+'/'+output)+']\n'
        body+='xu_arcs $rf '+tq(cell)+' [get_timing_arcs -of_objects $c] from_pin to_pin [list '+' '.join(arc_fields)+']\n'
        body+='xu_arcs $rlf '+tq(cell)+' [get_lib_timing_arcs -of_objects [get_lib_cells -of_objects $c]] from_lib_pin to_lib_pin [list '+' '.join(lib_fields)+']\n'
        body+='xu_capture reset-%d-disabled.rpt [list report_disable_timing $c]\n'%i
        body+='set p [xu_pin '+tq(cell+'/'+apin)+']\n'
        body+='xu_capture reset-%d-fanin.rpt [list xu_fanin $p]\n'%i
        for source_kind,src in [('HF_RESET','$hf'),('ANY_ENDPOINT_SOURCE',None)]+([('LF_WATCHDOG','$wdog')] if i>=2 else []):
            for check,delay in [('recovery','max'),('removal','min')]:
                frm=' -from '+src if src else ''
                tag='%s-%d-%s'%(source_kind.lower(),i,check)
                body+='puts '+tq('XU132_PATH_BEGIN '+tag)+'\n'
                body+='set paths [get_timing_paths'+frm+' -to $p -delay_type '+delay+' -slack_lesser_than 1000000 -max_paths 1]\n'
                body+='set n [sizeof_collection $paths]\nset slack UNKNOWN\nset status NO_PATH_UNKNOWN\nif {$n>0} {set slack [get_attribute [index_collection $paths 0] slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}\n'
                body+='xu_row $tf [list '+str(i)+' '+source_kind+' '+check+' $n $slack $status]\n'
                body+='xu_capture '+tag+'.rpt [list report_timing'+frm+' -to $p -delay_type '+delay+' -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8'+full+']\n'
                body+='puts '+tq('XU132_PATH_END '+tag)+'\n'
    # Three ordinary synchronous stage-to-stage D paths remain fully timed.
    for i,(source,target) in enumerate([(0,1),(4,3),(3,2)]):
        for delay in ('min','max'):
            body+='xu_capture stage-%d-%s.rpt [list report_timing -from [xu_pin '%(i,delay)+tq(SINKS[source][0]+'/'+SINK_OUTPUTS[source])+'] -to [xu_pin '+tq(SINKS[target][0]+'/D')+'] -delay_type '+delay+' -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8'+full+']\n'
    body+='close $pf\nclose $nf\nclose $cf\nclose $rf\nclose $rlf\nclose $tf\n'
    # Documented report DISPLAY only. Restore even if an optional query throws.
    body+='set xu_report_original [get_app_var timing_report_unconstrained_paths]\n'
    body+='set df [open report-display-policy.tsv w]\nxu_row $df {field value}\nxu_row $df [list original $xu_report_original]\n'
    body+='set xu_display_rc [catch {\nset_app_var timing_report_unconstrained_paths true\n'
    for i,(cell,apin,_) in enumerate(SINKS):
        body+='xu_capture unconstrained-hf-%d-recovery.rpt [list report_timing -from $hf -to [xu_pin '%i+tq(cell+'/'+apin)+'] -delay_type max -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8'+full+']\n'
    body+='} xu_display_error]\nset_app_var timing_report_unconstrained_paths $xu_report_original\n'
    body+='set xu_restored [get_app_var timing_report_unconstrained_paths]\nxu_row $df [list restored $xu_restored]\nclose $df\n'
    body+='if {$xu_restored ne $xu_report_original} {error {report display value not restored}}\nif {$xu_display_rc} {error $xu_display_error}\n'
    body+='redirect -file coverage-final.rpt {report_analysis_coverage -status_details untested}\n'
    body+='redirect -file exceptions-final.rpt {report_exceptions}\nredirect -file case-final.rpt {report_case_analysis -all}\n'
    body+='close $xu_unknown\nclose $xu_collections\n'
    return guarded(body,'XU_COVERAGE132_SAME116_READ_ONLY_DIAGNOSTIC_DONE_NOT_QUALIFIED')


def tsv(path):
    with Path(path).open() as f: return list(csv.DictReader(f,delimiter='\t'))


def period_mode(condition):
    pattern=r'RET1Neq1aEMA2eq([01])aEMA1eq([01])aEMA0eq([01])aEMAW1eq([01])aEMAW0eq([01])aCENeq0'
    m=re.fullmatch(pattern,condition or '')
    return tuple(map(int,m.groups())) if m else None


def analyse(out, original_coverage):
    out=Path(out)
    modes=tsv(out/'macro-mode-pins.tsv')
    names=sorted({r['macro'] for r in modes})
    need(len(names)==336 and len(modes)==336*8 and len({(r['macro'],r['pin']) for r in modes})==336*8,
         'actual336 macro mode/clock pin inventory differs')
    byname={n:{r['pin']:r for r in modes if r['macro']==n} for n in names}
    constants=[]
    for name in names:
        row=byname[name]
        need(set(row)==set(MODE_BITS)|{'CLK','CEN'},'actual macro mode pin set differs')
        values={p:row[p]['constant_value'] for p in MODE_BITS}
        need(all(values[p]==str(v) for p,v in MODE_BITS.items()),'actual macro constant mode differs: '+name)
        need(all(row[p]['user_case_value'] in ('','-','undefined') for p in MODE_BITS),
             'mode unexpectedly relies on explicit user case analysis')
        constants.append(dict(macro=name,values=values,clocks=row['CLK']['clocks']))
    original=coverage_rows(original_coverage)
    fresh=coverage_rows((out/'coverage-initial.rpt').read_text())
    final=coverage_rows((out/'coverage-final.rpt').read_text())
    canonical=lambda rows:sorted(json.dumps(r,sort_keys=True) for r in rows)
    need(canonical(original)==canonical(fresh)==canonical(final) and len(original)==27124,
         'same116 original/initial/final coverage detail multiset differs')
    periods=[r for r in fresh if r['check']=='min_period']
    need(len(periods)==10416 and all(r['status']=='untested' and r['reason']=='constant_disabled' for r in periods),
         'actual inactive period coverage differs')
    expected_modes={(a,b,c,d,e) for a in (0,1) for b in (0,1) for c in (0,1) for d in (0,1) for e in (0,1)}
    selected=(0,1,0,0,0)
    per=[]
    for name in names:
        rs=[r for r in periods if r['pin']==name+'/CLK']
        encoded=[period_mode(r['condition']) for r in rs]
        need(len(rs)==31 and None not in encoded and set(encoded)==expected_modes-{selected},
             'per-macro exact31 inactive conditions differ: '+name)
        per.append(dict(macro=name,actual_mode=list(selected),excluded_modes=[list(x) for x in sorted(encoded)],
                        inactive_checks=31,reason='physical constant-mode mismatch; no new case analysis'))
    arcs=tsv(out/'macro-clock-arcs.tsv')
    need({r['owner'] for r in arcs}==set(names),'actual macro clock arcs missing a macro')
    active_report=out/'period-all-status.rpt'
    active_review=dict(status='NOT_PROVEN',reason='native met detail absent or incomplete')
    if active_report.is_file():
        details=coverage_rows(active_report.read_text())
        detail_periods=[r for r in details if r['check']=='min_period']
        bound=[]
        for name in names:
            rs=[r for r in detail_periods if r['pin']==name+'/CLK']
            met=[r for r in rs if r['status']=='met' and period_mode(r['condition'])==selected]
            expected_clocks=byname[name]['CLK']['clocks'].split()
            need(expected_clocks and len(expected_clocks)==len(set(expected_clocks)),
                 'actual macro CLK clock collection empty/duplicate')
            clocks=[r['clock'] for r in met]
            exact=(len(met)==len(expected_clocks) and sorted(clocks)==sorted(expected_clocks) and
                   len(rs)==31+len(expected_clocks))
            bound.append(dict(macro=name,all_period_details=len(rs),active_met_details=len(met),
                              expected_clocks=expected_clocks,active_met_clocks=clocks,
                              exact_per_clock_details=exact,reported_slacks=[r['reported_slack'] for r in met]))
        summary=re.findall(r'^min_period\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)',active_report.read_text(),re.M)
        native_counts={s:sum(r['status']==s for r in detail_periods) for s in ('met','violated','untested')}
        exact_summary=(len(summary)==1 and list(map(int,summary[0]))==
                       [len(detail_periods),native_counts['met'],native_counts['violated'],native_counts['untested']])
        need(exact_summary,'native min-period full detail/summary counts differ')
        active_review=dict(status='ACTIVE_MODE_MET_DETAILS_PRESENT' if all(r['exact_per_clock_details'] for r in bound) else 'NOT_PROVEN',
                           native_detail_counts=native_counts,exact_native_summary=True,macros=bound)
    reset_paths=tsv(out/'reset-timing-paths.tsv')
    need(len(reset_paths)==26,'reset source/check query inventory differs')
    hf=[r for r in reset_paths if r['source_kind']=='HF_RESET' and r['check']=='recovery']
    need(len(hf)==5,'five HF reset recovery queries missing')
    consumers=tsv(out/'reset-q-consumers.tsv')
    first=[]
    for index,target in [(0,SINKS[1][0]+'/D'),(4,SINKS[3][0]+'/D')]:
        rs=[r for r in consumers if r['index']==str(index)]
        endpoints=[r for r in rs if r['sequential_or_endpoint'] in ('true','PORT_ENDPOINT')]
        first.append(dict(index=index,expected_next_D=target,endpoint_consumers=endpoints,
                          sole_expected_sequential_consumer=len(endpoints)==1 and endpoints[0]['consumer']==target))
    display=tsv(out/'report-display-policy.tsv')
    need(len(display)==2 and display[0]['field']=='original' and display[1]['field']=='restored' and display[0]['value']==display[1]['value'],
         'report-only display setting not restored')
    result=dict(schema='xu-same116-coverage-rdc-analysis-v1',qualification='NOT_QUALIFIED',
        actual_macro_count=336,mode_pin_rows=len(modes),inactive_period_checks=10416,
        actual_constant_mode=dict(MODE_BITS),inactive_conditions=per,active_period_review=active_review,
        original_initial_final_untested_row_multisets_equal=True,untested_rows=27124,
        first_stage_q_consumers=first,reset_path_queries=reset_paths,
        unknown_queries=tsv(out/'unknown-queries.tsv'),
        limitations=['Native enabled/disabled/when/arrival and unconstrained-path display are evidence, not recovery safety.',
          'PTE-052 presence plus missing paths is not a proof of sole causation; no horizon or timing override is introduced.',
          'No arbitrary asynchronous-release phase safety, conditional reset skew, analogue metastability, or pulse contract is established.',
          'UART fixed RTL and 24 latch clocks remain unchanged. Baseline116 is not S2e qualification.'])
    dump(out/'analysis.json',result)
    return result


def run_native(out,state,name,content,marker,environment):
    script=out/name; script.write_text(content)
    log=out/(script.stem+'.log')
    state['phase']=script.stem; state['native_command']=[str(PT),'-f',name]
    dump(out/'state.json',state)
    started=time.time()
    with log.open('xb') as f:
        p=subprocess.Popen([str(PT),'-f',name],cwd=str(out),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,
                           env=environment,start_new_session=True)
        state['native_pid']=p.pid; dump(out/'state.json',state)
        try: rc=p.wait(timeout=21600)
        except BaseException:
            os.killpg(p.pid,signal.SIGKILL);p.wait();raise
    raw=log.read_text(errors='replace')
    errors=[s for s in raw.splitlines() if re.match(r'^\s*(?:Error:|Error-|Fatal:|XU_FATAL:)',s)]
    record=dict(command=[str(PT),'-f',name],returncode=rc,started_epoch=started,finished_epoch=time.time(),
                marker_count=sum(s.strip()==marker for s in raw.splitlines()),errors=errors,log=ident(log),script=ident(script))
    state['runs'].append(record);state.pop('native_pid',None);dump(out/'state.json',state)
    need(rc==0 and record['marker_count']==1 and not errors,'native PT diagnostic failed: '+name)


def main():
    OUT.mkdir(exist_ok=False)
    state=dict(schema='xu-same116-coverage-rdc-execution-v1',status='RUNNING_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
               pid=os.getpid(),started_epoch=time.time(),runs=[],scope='Exact actual116 original analysis context; additional read-only macro/coverage/reset structural reports',
               constraints_policy='No new clock, cut, case, exception, propagation or timing horizon setting. Only documented report DISPLAY toggle restored.',
               producer=ident(Path(__file__).resolve()))
    dump(OUT/'state.json',state)
    frozen={}
    try:
        parent,frozen,prefix=preflight()
        for p in (Path(__file__).resolve(),PT): frozen[str(p)]=ident(p)
        state['parent']=dict(state=ident(PARENT/'state.json'),mapped=parent['final_mapped'],svf=parent['final_svf'])
        state['original_failed126']=ident(FAILED126/'state.json')
        state['frozen_before']=dict(frozen);dump(OUT/'state.json',state)
        environment=os.environ.copy();environment['SYNOPSYS_LC_ROOT']=str(LC)
        environment['PATH']=str(LC/'bin')+os.pathsep+environment.get('PATH','')
        need((LC/'bin').is_dir(),'original Library Compiler runtime required')
        run_native(OUT,state,'installed-docs.tcl',documentation_tcl(),'XU_COVERAGE132_INSTALLED_DOCS_DONE_NOT_QUALIFIED',environment)
        options=installed_options(OUT);dump(OUT/'installed-options.json',options)
        state['private_manuals_policy']='Do not export licensed manual bodies; installed-options.json preserves their byte/hash identities.'
        run_native(OUT,state,'diagnosis.tcl',diagnostic_tcl(prefix,options),'XU_COVERAGE132_SAME116_READ_ONLY_DIAGNOSTIC_DONE_NOT_QUALIFIED',environment)
        analysis=analyse(OUT,(PARENT/'analysis-coverage.rpt').read_text())
        state['analysis']=ident(OUT/'analysis.json');state['status']=STATUS
        state['summary']=dict(macros=336,inactive_period_checks=10416,untested_checks=27124,
                              active_mode=analysis['active_period_review']['status'])
    except BaseException as error:
        state.update(status='FAILED_NOT_QUALIFIED',error=type(error).__name__+': '+str(error),traceback=traceback.format_exc())
        raise
    finally:
        observed={};errors=[]
        for name in frozen:
            try:observed[name]=ident(name)
            except BaseException as error:errors.append(name+': '+repr(error))
        state['frozen_after']=observed;state['frozen_after_observation_errors']=errors
        state['frozen_inputs_unchanged']=observed==frozen and not errors
        if not state['frozen_inputs_unchanged']:
            state.update(status='FAILED_NOT_QUALIFIED',integrity_error='input identities changed')
        state['finished_epoch']=time.time()
        state['outputs']={str(p.relative_to(OUT)):ident(p) for p in sorted(OUT.rglob('*'))
             if p.is_file() and p.name not in ('state.json','driver.log') and 'private-manuals' not in p.parts}
        dump(OUT/'state.json',state)
        print(state['status'],flush=True)


if __name__=='__main__':
    main()
