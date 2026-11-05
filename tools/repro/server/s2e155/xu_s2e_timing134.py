#!/usr/bin/env python3
"""Independent S2e89 timing/electrical/reset diagnostic repair, own DC/PT/FM.

Python3.6+, standard library, no network. Fresh134 only. No baseline mapped/SVF
or repair ancestry is imported. Every completion remains NOT_QUALIFIED.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import traceback

BASE = Path.home() / 'Desktop/xu-score-optimization-20261102'
OUT = 's2e-own-timing-repair-20261105-134'
NET = '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
SVF = '1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
RESET = '8e50f0559a0f443cc4359b28cf55d7e0e54e6778ca8490bce4aac91b157ac33c'
TOOLS = {
 'tools/ppa/xu_s2e_activity_context.py': '0eedf615e6f6f196fb328407849e4973dff8e036b5ea583c833df260e58d5682',
 'tools/ppa/xu_s2e_formality_audit.py': 'fb468c230b528a364e2f013684e80b0135b7debc75746f90a62057f18aa91bbc',
}
DBS = {'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
       'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}
BIN = {'dc': '/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell',
       'pt': '/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell',
       'fm': '/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell'}
VERSION = {'dc': 'Version T-2022.03-SP5-5', 'pt': 'Version T-2022.03-SP5-1', 'fm': 'Version R-2020.09-SP5'}
AON = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
ENDPOINTS = [(AON+'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg','SDN','DSNQV0_12TR40'),
             (AON+'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg','SDN','DSNQNV0_12TR40')]
ENDPOINTS += [(AON+'aonrst_catch/reset_n_catch_reg/reg_%d/q_reg'%i,'RDN','DRNQV0_12TR40') for i in range(3)]
BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|FATAL:|XU_FATAL:|XU_S2E_TIMING134_(?:FAIL|SCRIPT_ERROR))',re.M)
LIMITS = [
 'NOT_QUALIFIED: limited pre-CTS ideal-clock/forwarded-clock method experiment; original propagated89 evidence retained.',
 'No baseline mapped target, synthesis SVF, proof or repair ancestry is used.',
 'Only native nonsequential whole-output no-consumer cells with unique owner can be deleted. Sequential min-cap debt is retained.',
 'DC0.12ns gating hold optimization margin is not the analysis constraint: every PT uses original SDC0.1ns.',
 'Unknown/no-path recovery, UART, macro modes, pulse-width, untested checks, reset/RDC and energy remain separate obligations.',
 'Full FM retains original SRAM blackboxes and auto-setup; neither SRAM internals nor contest numerical/power eligibility follows.',
]


def need(ok,message):
    if not ok: raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()


def ident(path):
    p=Path(path).absolute()
    need(p.is_file() and not p.is_symlink(),'regular non-symlink input required: '+str(p))
    return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))


def read(path):
    def pairs(items):
        d={}
        for k,v in items:
            need(k not in d,'duplicate JSON key: '+k); d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs)


def dump(path,data):
    p=Path(path);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n');os.replace(str(t),str(p))


def module(name,path):
    s=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def q(value):
    s=str(value)
    need(s and not any(c in s for c in '{}\\\t\r\n'),'unsafe Tcl literal')
    return '{'+s+'}'


def rows(path):
    with Path(path).open() as f:
        rr=csv.DictReader(f,delimiter='\t'); data=list(rr)
    need(rr.fieldnames and len(rr.fieldnames)==len(set(rr.fieldnames)) and
         all(None not in r and None not in r.values() for r in data),'malformed TSV: '+str(path))
    return data


def freeze(paths):
    return {str(Path(p).absolute()):ident(p) for p in sorted(set(map(str,paths)))}


def family(ref):
    m=re.fullmatch(r'(.+?)[0-9]+[^0-9_]*_12TR40',ref)
    return m.group(1) if m else None


def number(s):
    try: n=float(s)
    except (ValueError,TypeError): return None
    return n if math.isfinite(n) else None


def caps(text):
    """Parse native verbose max/min electrical rows; no baseline counts."""
    result={}
    for block in text.split('    Pin: ')[1:]:
        pin=block.splitlines()[0].strip();q(pin)
        kinds=re.findall(r'^\s*(?:-\s*)?(max_capacitance|min_capacitance)\s+',block,re.M)
        if not kinds: continue
        need(len(kinds)==1 and pin not in result,'ambiguous/duplicate electrical report pin')
        ma=re.search(r'^\s*max_capacitance\s+([\d.Ee+-]+)\s*\n\s*-\s+Capacitance\s+([\d.Ee+-]+)',block,re.M)
        mi=re.search(r'^\s*Capacitance\s+([\d.Ee+-]+)\s*\n\s*-\s+min_capacitance\s+([\d.Ee+-]+)',block,re.M)
        need(bool(ma)!=bool(mi),'unparsed native electrical rows: '+pin)
        limit,load=(ma[1],ma[2]) if ma else (mi[2],mi[1])
        need(number(limit) is not None and number(load) is not None,'invalid electrical number')
        result[pin]=dict(kind=kinds[0],limit=float(limit),load=float(load))
    # Prevent a changed report layout from appearing to have zero cap debt.
    mentioned=len(re.findall(r'^\s*(?:-\s*)?(?:max_capacitance|min_capacitance)\s+[\d.Ee+-]+',text,re.M))
    need(mentioned==len(result),'electrical report contains an unparsed constraint')
    return result


def plan(directory):
    """Only fresh native S2e inventory may propose repair cells."""
    directory=Path(directory);cap=caps((directory/'constraints.rpt').read_text())
    native=rows(directory/'native-cells.tsv');librows=rows(directory/'library-palette.tsv')
    bypin={};bycell={};libraries={}
    for r in native:
        need(r['output'] not in bypin,'duplicate native output')
        bypin[r['output']]=r;bycell.setdefault(r['cell'],[]).append(r)
    for r in librows:
        d=libraries.setdefault(r['libcell'],{});pn=r['libpin'].rsplit('/',1)[1]
        need(pn not in d,'duplicate library pin');d[pn]=r
    def signature(c): return sorted((p,r['direction']) for p,r in libraries[c].items())
    deletions={};blocked=[];sizing=[];seen=set()
    for pin,c in sorted(cap.items()):
        need(pin in bypin,'cap pin missing from fresh native ownmapped inventory: '+pin)
        r=bypin[pin];cell=r['cell'];rs=bycell[cell]
        if c['kind']=='min_capacitance':
            eligible=(all(x['all_outputs_unloaded']=='1' and x['sequential']=='false' and
                       x['owner_count']=='1' and x['inout_count']=='0' and x['owner_ref']!='<TOP>' for x in rs))
            if eligible: deletions[cell]=dict(cell=cell,ref=r['ref'],output=pin,owner_ref=r['owner_ref'])
            else: blocked.append(dict(pin=pin,cell=cell,sequential=r['sequential'],
                                      all_outputs_unloaded=r['all_outputs_unloaded'],reason='native nonsequential/no-consumer/unique-owner deletion gate not satisfied'))
            continue
        need(cell not in seen,'multiple maxcap outputs on one cell require explicit review');seen.add(cell)
        current=[k for k in libraries if k.rsplit('/',1)[1]==r['ref']]
        need(len(current)==1,'native current library identity ambiguous');old=current[0];pn=pin.rsplit('/',1)[1]
        need(pn in libraries[old] and libraries[old][pn]['direction']=='out','native cap libpin differs')
        candidates=[]
        for k,ps in libraries.items():
            if k==old or family(k.rsplit('/',1)[1])!=family(r['ref']) or not family(r['ref']) or signature(k)!=signature(old): continue
            p=ps[pn];area=number(p['area']);maximum=number(p['max_capacitance'])
            if area is None or maximum is None or maximum<c['load']*1.05 or p['dont_use'] not in ('false','<ABSENT>'):continue
            if any(v['function'] not in ('<ABSENT>','<UNAVAILABLE>','') and ps[n]['function'] not in ('<ABSENT>','<UNAVAILABLE>','') and v['function']!=ps[n]['function'] for n,v in libraries[old].items()):continue
            candidates.append(dict(libcell=k,area=area,max_capacitance=maximum))
        candidates.sort(key=lambda x:(x['area'],x['max_capacitance'],x['libcell']))
        need(candidates,'no same-family native-library maxcap proposal for '+pin)
        sizing.append(dict(cell=cell,pin=pin,ref=r['ref'],current_libcell=old,load=c['load'],selected=candidates[0],native_equivalence_required=True))
    need(len(sizing)<=256 and len(deletions)<=4096,'bounded repair cardinality exceeded')
    return dict(schema='xu-s2e-native-plan134-v1',qualification='NOT_QUALIFIED',
                inventory=freeze([directory/n for n in ('constraints.rpt','native-cells.tsv','library-palette.tsv','reset-library.tsv')]),
                maxcap=sizing,dead_initial=sorted(deletions.values(),key=lambda x:x['cell']),
                unresolved_mincap=blocked,cap_counts={k:sum(x['kind']==k for x in cap.values()) for k in ('min_capacitance','max_capacitance')},
                maximum_waves=24,maximum_deleted=8192,sequential_removal=False)


INVENTORY = r'''
proc xu134_optional {obj attr} {
 if {[catch {get_attribute -quiet $obj $attr} v]} {return <UNAVAILABLE>}
 if {$v eq ""} {return <ABSENT>}
 if {[regexp {[\t\r\n]} $v]} {error {non-tabular native attribute}}
 return $v
}
set owners [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr owners [get_attribute $h ref_name]}
set f [open native-cells.tsv w]
puts $f "cell\tref\tsequential\towner_ref\towner_count\tinout_count\toutput\tleaf_connections\tall_outputs_unloaded"
foreach_in_collection c [get_cells -hierarchical -filter {is_hierarchical == false}] {
 set cn [get_object_name $c]
 set owner [get_cells -quiet [file dirname $cn]]
 set oref <TOP>; set count 1
 if {[sizeof_collection $owner]==1} {set oref [get_attribute $owner ref_name];set count [dict get $owners $oref]}
 set outputs [get_pins -of_objects $c -filter {direction == out}]
 set unloaded [expr {[sizeof_collection $outputs]>0}]
 foreach_in_collection p $outputs {
  set ns [get_nets -of_objects $p]
  if {[sizeof_collection $ns]!=1} {set unloaded 0;continue}
  set con [all_connected -leaf $ns]
  if {[sizeof_collection $con]!=1 || [get_object_name $con] ne [get_object_name $p]} {set unloaded 0}
 }
 foreach_in_collection p $outputs {
  set con {};set ns [get_nets -of_objects $p]
  if {[sizeof_collection $ns]==1} {set con [get_object_name [all_connected -leaf $ns]]}
  puts $f [join [list $cn [get_attribute $c ref_name] [xu134_optional $c is_sequential] $oref $count [sizeof_collection [get_pins -of_objects $c -filter {direction == inout}]] [get_object_name $p] $con $unloaded] "\t"]
 }
}
close $f
set f [open library-palette.tsv w]
puts $f "libcell\tarea\tdont_use\tlibpin\tdirection\tfunction\tmax_capacitance\tmin_capacitance"
foreach_in_collection c [get_lib_cells -quiet */*] {
 foreach_in_collection p [get_lib_pins -of_objects $c] {
  puts $f [join [list [get_object_name $c] [xu134_optional $c area] [xu134_optional $c dont_use] [get_object_name $p] [get_attribute $p direction] [xu134_optional $p function] [xu134_optional $p max_capacitance] [xu134_optional $p min_capacitance]] "\t"]
 }
}
close $f
'''


def cleanup_tcl(proposals):
    front=' '.join(q(p['output']) for p in proposals)
    refs=' '.join(q(p['output'])+' '+q(p['ref']) for p in proposals)
    return r'''
set front [list @FRONT@]
set first_refs [dict create @REFS@]
set owners [dict create]
foreach_in_collection h [get_cells -hierarchical -filter {is_hierarchical == true}] {dict incr owners [get_attribute $h ref_name]}
set original_count [sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]
set total 0;set converged 0;set removed {}
set pf [open cleanup-preflight.tsv w];set rf [open removed-cells.tsv w];set wf [open cleanup-rounds.tsv w]
puts $pf "wave\tcell\tref\tsequential\toutput\tleaf_connections\towner_count"
puts $rf "wave\tcell\tref"
puts $wf "wave\tfrontier\tremoved\tupstream"
for {set wave 0} {$wave<24} {incr wave} {
 set planned [dict create];set upstream [dict create]
 foreach name [lsort -unique $front] {
  set p [get_pins -quiet $name]
  if {[sizeof_collection $p]!=1 || [get_attribute $p direction] ne "out"} {error {exact cleanup frontier output missing}}
  set c [get_cells -of_objects $p];set cn [get_object_name $c];set ref [get_attribute $c ref_name]
  if {[sizeof_collection $c]!=1 || [get_attribute $c is_hierarchical]} {error {cleanup candidate not leaf}}
  if {$wave==0 && $ref ne [dict get $first_refs $name]} {error {native inventory initial ref changed}}
  set outputs [get_pins -of_objects $c -filter {direction == out}];set unloaded [expr {[sizeof_collection $outputs]>0}]
  foreach_in_collection op $outputs {
   set ns [get_nets -of_objects $op]
   if {[sizeof_collection $ns]!=1} {set unloaded 0;continue}
   set con [all_connected -leaf $ns]
   if {[sizeof_collection $con]!=1 || [get_object_name $con] ne [get_object_name $op]} {set unloaded 0}
  }
  set seq [get_attribute -quiet $c is_sequential]
  if {!$unloaded || ![string is boolean -strict $seq] || $seq || [sizeof_collection [get_pins -of_objects $c -filter {direction == inout}]]!=0} {
   if {$wave==0} {error {initial native no-consumer/nonsequential gate changed}}
   continue
  }
  set owner [get_cells -quiet [file dirname $cn]]
  if {[sizeof_collection $owner]!=1} {if {$wave==0} {error {initial owner missing}};continue}
  set oref [get_attribute $owner ref_name]
  if {![dict exists $owners $oref] || [dict get $owners $oref]!=1} {if {$wave==0} {error {initial shared owner}};continue}
  if {[dict exists $planned $cn]} {continue}
  if {[lsearch -exact $removed $cn]>=0} {error {cleanup repeated cell}}
  foreach_in_collection op $outputs {
   set con [all_connected -leaf [get_nets -of_objects $op]]
   if {[get_attribute $con object_class] ne "pin" || [get_attribute $con direction] ne "out"} {error {cleanup terminal not exact output}}
   puts $pf [join [list $wave $cn $ref $seq [get_object_name $op] [get_object_name $con] 1] "\t"]
  }
  foreach_in_collection ip [get_pins -of_objects $c -filter {direction == in}] {
   foreach_in_collection n [get_nets -of_objects $ip] {
    foreach_in_collection d [all_connected -leaf $n] {
     if {[get_attribute $d object_class] eq "pin" && [get_attribute $d direction] eq "out"} {dict set upstream [get_object_name $d] 1}
    }
   }
  }
  dict set planned $cn $ref
 }
 if {$wave==0 && [dict size $planned]!=@COUNT@} {error {initial inventory deletion count changed}}
 if {$total+[dict size $planned]>8192} {error {bounded cleanup count exceeded}}
 foreach cn [lsort [dict keys $planned]] {
  remove_cell [get_cells -quiet $cn]
  if {[sizeof_collection [get_cells -quiet $cn]]!=0} {error {native cleanup failed}}
  lappend removed $cn;puts $rf [join [list $wave $cn [dict get $planned $cn]] "\t"]
 }
 incr total [dict size $planned]
 if {[sizeof_collection [get_cells -hierarchical -filter {is_hierarchical == false}]]!=$original_count-$total} {error {unexpected cleanup mutation}}
 puts $wf [join [list $wave [llength $front] [dict size $planned] [dict size $upstream]] "\t"]
 if {[dict size $planned]==0 || [dict size $upstream]==0} {set converged 1;break}
 set front [dict keys $upstream]
}
close $pf;close $rf;close $wf
if {!$converged} {error {bounded cleanup waves exhausted}}
'''.replace('@FRONT@',front).replace('@REFS@',refs).replace('@COUNT@',str(len(proposals)))


def sizing_tcl(proposals):
    text=r'''
proc xu134_lib_signature {c} {
 set s {}
 foreach_in_collection p [get_lib_pins -of_objects $c] {
  lappend s [list [lindex [split [get_object_name $p] /] end] [get_attribute $p direction] [get_attribute -quiet $p function]]
 }
 return [lsort $s]
}
set f [open sized-cells.tsv w]
puts $f "cell\tbefore_ref\tafter_ref\tmax_capacitance"
'''
    for p in proposals:
        cell,old,new,pin=p['cell'],p['current_libcell'],p['selected']['libcell'],p['pin'].rsplit('/',1)[1]
        text+='set c [get_cells -quiet '+q(cell)+']\nif {[sizeof_collection $c]!=1 || [get_attribute $c ref_name] ne '+q(p['ref'])+'} {error {sizing source identity differs}}\n'
        text+='set old [get_lib_cells -quiet '+q(old)+']\nset new [get_lib_cells -quiet '+q(new)+']\n'
        text+='if {[sizeof_collection $old]!=1 || [sizeof_collection $new]!=1 || [xu134_lib_signature $old] ne [xu134_lib_signature $new]} {error {sizing native pin/function signatures differ}}\n'
        text+='set allowed [get_alternative_lib_cells -quiet $c]\nif {[lsearch -exact [get_object_name $allowed] '+q(new)+']<0} {error {native logic/pin-number alternative compatibility rejected sizing}}\n'
        text+='set lp [get_lib_pins -quiet '+q(new+'/'+pin)+']\nif {[sizeof_collection $lp]!=1 || [get_attribute $lp max_capacitance]<'+repr(p['load']*1.05)+'} {error {sizing cap headroom differs}}\n'
        text+='set dont [get_attribute -quiet $new dont_use]\nif {$dont ne "" && (![string is boolean -strict $dont] || $dont)} {error {sizing candidate prohibited}}\n'
        text+='set sized [size_cell $c '+q(new)+']\nif {[sizeof_collection $sized]!=1 || [get_object_name $sized] ne [get_object_name $c] || [get_attribute $c ref_name] ne '+q(new.rsplit('/',1)[1])+'} {error {native sizing did not apply exact candidate}}\n'
        text+='puts $f [join [list [get_object_name $c] '+q(p['ref'])+' [get_attribute $c ref_name] [get_attribute $lp max_capacitance]] "\\t"]\n'
    return text+'close $f\n'


def source_tcl(sdc,scope):
    return 'set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource '+q(sdc)+'\nset XU_AUDIT_FORWARD_CLOCK_EXPERIMENT 1\nsource '+q(scope)+'\n'


def dc_prefix(net,impl,sdc,scope,svf=None):
    libs=[q(x['path']) for x in impl['libraries']];target=[q(x['path']) for x in impl['libraries'] if x['role']=='standard_cell']
    s='set_host_options -max_cores 2\nset_app_var target_library [list '+' '.join(target)+']\nset_app_var link_library [list * '+' '.join(libs)+']\n'
    if svf:s+='set_svf '+q(svf)+'\n'
    return s+'read_verilog '+q(net)+'\ncurrent_design xu_soc_ppa_top\nif {![link]} {error {DC link failed}}\n'+source_tcl(sdc,scope)


def pt_script(net,impl,sdc,scope,ppa):
    s='set_app_var link_path [list * '+' '.join(q(x['path']) for x in impl['libraries'])+']\nread_verilog '+q(net)+'\nif {![link_design xu_soc_ppa_top]} {error {PT link failed}}\n'+source_tcl(sdc,scope)+ppa.memory_checks(impl)
    s+=r'''
set inv [get_lib_cells -quiet {scc40nll_vhsc40_rvt_ss_v0p99_125c_basic/CLKINV0_12TR40}]
if {[sizeof_collection $inv]!=1 || [get_attribute $inv dont_use] ne "false"} {error {fresh PT reset library permission differs}}
set f [open reset-library.tsv w]
puts $f "libcell\tdont_use\tlibpin\tdirection"
foreach_in_collection p [get_lib_pins -of_objects $inv] {puts $f [join [list [get_object_name $inv] [get_attribute $inv dont_use] [get_object_name $p] [get_attribute $p direction]] "\t"]}
close $f
'''
    for file,cmd in [('units','report_units'),('check-timing','check_timing -verbose'),('setup','report_timing -delay_type max -slack_lesser_than 1000000 -max_paths 100 -significant_digits 12'),('hold','report_timing -delay_type min -slack_lesser_than 1000000 -max_paths 100 -significant_digits 12'),('constraints','report_constraint -all_violators -verbose -significant_digits 12'),('exceptions','report_exceptions'),('analysis-coverage','report_analysis_coverage -status_details untested'),('clocks','report_clock -attributes')]:
        s+='redirect -file '+file+'.rpt {'+cmd+'}\n'
    s+='set f [open timing-slack.tsv w]\nputs $f "delay_type\\tpath_count\\tworst_slack"\nforeach type {max min} {set paths [get_timing_paths -delay_type $type -slack_lesser_than 1000000 -max_paths 1];if {[sizeof_collection $paths]!=1} {error {global timing path missing}};puts $f [join [list $type 1 [get_attribute $paths slack]] "\\t"]}\nclose $f\n'
    s+='set f [open reset-paths.tsv w]\nputs $f "index\\tsource_kind\\tcheck\\tcount\\tworst_slack\\tstatus"\n'
    for i,(cell,pin,_) in enumerate(ENDPOINTS):
        sources=[('HF_RESET','[get_ports -quiet {io_pads_aon_erst_n_i_ival}]')]
        if i>=2:sources.append(('LF_WATCHDOG','[get_pins -quiet '+q(AON+'u_sirv_aon/wdog/AsyncResetRegVec_6_1/reg_0/q_reg/Q')+']'))
        for kind,src in sources:
            for check,delay in [('recovery','max'),('removal','min')]:
                s+='set src '+src+'\nset dst [get_pins -quiet '+q(cell+'/'+pin)+']\nif {[sizeof_collection $src]!=1 || [sizeof_collection $dst]!=1} {error {exact reset query identity differs}}\n'
                s+='set p [get_timing_paths -from $src -to $dst -delay_type '+delay+' -slack_lesser_than 1000000 -max_paths 1]\nset n [sizeof_collection $p];set slack UNKNOWN;set status NO_PATH_UNKNOWN\nif {$n>0} {set slack [get_attribute $p slack];set status PATH_PRESENT_DIAGNOSTIC_ONLY}\n'
                s+='puts $f [join [list '+str(i)+' '+kind+' '+check+' $n $slack $status] "\\t"]\n'
                s+='redirect -file reset-%d-%s-%s.rpt {report_timing -from $src -to $dst -delay_type %s -slack_lesser_than 1000000 -max_paths 10 -significant_digits 12}\n'%(i,kind.lower(),check,delay)
    return s+'close $f\n'


def outputs_tcl():
    return 'report_area -hierarchy > area.rpt\nreport_qor > qor.rpt\nreport_constraint -all_violators -verbose > dc-constraints.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite -format ddc -hierarchy -output mapped.ddc\nwrite_sdc mapped.sdc\n'


def native(out,state,kind,script,marker,env):
    out=Path(out);command=[BIN[kind],'-f',script];state['phase']=out.name+'/'+kind;state['command']=command;dump(state['_state_path'],state)
    with (out/(kind+'.log')).open('xb') as f:
        r=subprocess.run(command,cwd=str(out),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=21600 if kind!='fm' else 4200)
    text=(out/(kind+'.log')).read_text(errors='replace')
    rec=dict(directory=str(out),tool=kind,command=command,returncode=r.returncode,marker_count=sum(x.strip()==marker for x in text.splitlines()),errors=[line for line in text.splitlines() if BAD.match(line)],log=ident(out/(kind+'.log')),script=ident(out/script))
    state['runs'].append(rec);dump(state['_state_path'],state)
    need(r.returncode==0 and rec['marker_count']==1 and not rec['errors'] and VERSION[kind] in text,'native '+state['phase']+' failed')
    if kind=='fm':
        need(re.findall(r'^Verification (?:SUCCEEDED|FAILED)[ \t]*$',text,re.M)==['Verification SUCCEEDED'],'native full FM success required')
        need(not re.search(r'^[^\n]*(?:Verification FAILED|Aborted compare points|Failing compare points|Unverified compare points)[^\n]*$',text,re.M),'native incomplete/failing FM')
        need('Reference design: r:/WORK/xu_soc_ppa_top' in text and 'Implementation design: i:/WORK/xu_soc_ppa_top' in text,'full original top FM scope missing')
        passing=re.findall(r'^[ \t]*(\d+) Passing compare points[ \t]*$',text,re.M)
        need(len(passing)==1 and int(passing[0])>40000,'native full compare count missing');state['formal_passing']=int(passing[0])
        state['formal_scope_lines']=[line for line in text.splitlines() if re.search(r'Passing \(equivalent\)|Failing \(not equivalent\)|Unread|Unmatched reference',line)]


def preflight(args):
    source,tools,original,audit,scope=[p.resolve() for p in (args.source,args.tools,args.original,args.audit,args.scope)]
    need(sha(scope)==SCOPE,'fixed platform scope134 differs')
    for n,h in TOOLS.items():need(sha(tools/n)==h,'frozen tools109 helper differs: '+n)
    context=module('xu134_context',tools/'tools/ppa/xu_s2e_activity_context.py')
    tool_identity=context.tool_identity();source_identity=context.source_identity(source)
    checked=context.checked_mapped_context(source,original,audit)
    need(checked['netlist']['sha256']==NET and sha(original/'ppa/default.svf')==SVF and checked['constraints']['sha256']==SDC,'own89 mapped/SVF/SDC differs')
    impl=read(original/'ppa/prepared.json')['implementation']
    need({sha(p['path']) for p in impl['libraries']}==DBS,'exact original libraries differ')
    need(sha(Path(__file__).with_name('reset134.tcl'))==RESET,'frozen reset134 template differs')
    ppa=module('xu134_frozen_ppa',tools/'tools/scripts/xu_soc_ppa.py')
    paths=[Path(__file__).resolve(),Path(__file__).with_name('reset134.tcl'),scope,tools/'tools/scripts/xu_soc_ppa.py']
    paths += [Path(p['path']) for p in checked['inputs']]
    paths += [original/'ppa/mapped.v',original/'ppa/constraints.sdc',original/'ppa/default.svf']
    paths += [Path(p['path']) for p in tool_identity['frozen_common_tools']]
    return context,ppa,impl,checked,tool_identity,source_identity,freeze(paths)


def execute(args):
    out=args.out.resolve();need(out.name==OUT,'only new134 output name accepted')
    need(not out.exists(),'134 output exists; observe original recorded job, never restart')
    need(out.parent.resolve()==BASE.resolve(),'output must be new134 under original base')
    context,ppa,impl,checked,tool_id,source_id,before=preflight(args)
    if args.preflight_only:
        print(json.dumps(dict(status='PREFLIGHT_ONLY_NOT_QUALIFIED',source=source_id,mapped=checked['netlist'],frozen_count=len(before)),sort_keys=True,indent=2));return
    out.mkdir();state=dict(schema='xu-s2e-own-timing134-v1',status='RUNNING_NOT_QUALIFIED',qualification='NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),runs=[],limits=LIMITS,frozen_before=before,own89_context=checked,source=source_id,tools=tool_id,_state_path=str(out/'state.json'))
    dump(out/'state.json',state)
    env=os.environ.copy();env['SYNOPSYS_LC_ROOT']='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env['PATH']=env['SYNOPSYS_LC_ROOT']+'/bin:'+env.get('PATH','')
    generated={}
    def script(directory,name,body,marker):
        p=directory/name;p.write_text(ppa.guarded_tcl(body,marker));generated[str(p)]=ident(p)
    def inventory(directory,net):
        directory.mkdir()
        script(directory,'inventory.tcl',dc_prefix(net,impl,args.original/'ppa/constraints.sdc',args.scope)+ppa.memory_checks(impl)+INVENTORY,'XU_S2E_TIMING134_INVENTORY_DONE_NOT_QUALIFIED')
        native(directory,state,'dc','inventory.tcl','XU_S2E_TIMING134_INVENTORY_DONE_NOT_QUALIFIED',env)
        script(directory,'sta.tcl',pt_script(net,impl,args.original/'ppa/constraints.sdc',args.scope,ppa),'XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED')
        native(directory,state,'pt','sta.tcl','XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED',env)
        state.setdefault('diagnostics',{})[directory.name]=dict(mapped=ident(net),electrical_counts={k:sum(x['kind']==k for x in caps((directory/'constraints.rpt').read_text()).values()) for k in ('max_capacitance','min_capacitance')},reports=freeze(list(directory.glob('*.rpt'))+list(directory.glob('*.tsv'))));dump(out/'state.json',state)
    try:
        original=args.original/'ppa/mapped.v'
        inventory(out/'original-inventory',original)
        # This is a fresh own89 repair, not baseline08/09 mapped ancestry.
        hold=out/'hold-gating';hold.mkdir()
        body=dc_prefix(original,impl,args.original/'ppa/constraints.sdc',args.scope,'hold.svf')
        body+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\nset_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false\nset_clock_gating_check -hold 0.12 [all_clocks]\nset_fix_hold [all_clocks]\ncompile -incremental_mapping -only_hold_time\n'+ppa.memory_checks(impl)+outputs_tcl()
        script(hold,'repair.tcl',body,'XU_S2E_TIMING134_HOLD_DONE_NOT_QUALIFIED');native(hold,state,'dc','repair.tcl','XU_S2E_TIMING134_HOLD_DONE_NOT_QUALIFIED',env)
        hold_identity=freeze([hold/'mapped.v',hold/'hold.svf']);state['hold_outputs']=hold_identity
        inventory(out/'posthold-inventory',hold/'mapped.v')
        need(freeze(hold_identity)==hold_identity,'own hold mapped/SVF changed during inventory')
        need(freeze(state['diagnostics']['posthold-inventory']['reports'])==state['diagnostics']['posthold-inventory']['reports'],
             'fresh posthold diagnostic reports changed before selection')
        palette=rows(out/'posthold-inventory/reset-library.tsv')
        need(len(palette)==2 and all(r['dont_use']=='false' for r in palette) and
             {(r['libpin'].rsplit('/',1)[1],r['direction']) for r in palette}=={('I','in'),('ZN','out')},
             'fresh own posthold PT inverter palette differs')
        proposal=plan(out/'posthold-inventory');dump(out/'repair-plan.json',proposal);generated[str(out/'repair-plan.json')]=ident(out/'repair-plan.json');state['repair_plan']=proposal;dump(out/'state.json',state)
        final=out/'final';final.mkdir()
        body=dc_prefix(hold/'mapped.v',impl,args.original/'ppa/constraints.sdc',args.scope,'repair.svf')
        body+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n'+sizing_tcl(proposal['maxcap'])+cleanup_tcl(proposal['dead_initial'])+Path(__file__).with_name('reset134.tcl').read_text()+ppa.memory_checks(impl)+outputs_tcl()
        script(final,'repair.tcl',body,'XU_S2E_TIMING134_REPAIR_DONE_NOT_QUALIFIED');native(final,state,'dc','repair.tcl','XU_S2E_TIMING134_REPAIR_DONE_NOT_QUALIFIED',env)
        final_identity=freeze([final/'mapped.v',final/'repair.svf']);state['final_outputs']=final_identity
        script(final,'sta.tcl',pt_script(final/'mapped.v',impl,args.original/'ppa/constraints.sdc',args.scope,ppa),'XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED');native(final,state,'pt','sta.tcl','XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED',env)
        need(freeze(final_identity)==final_identity,'final own mapped/SVF changed during PT')
        chain=[args.original/'ppa/default.svf',hold/'hold.svf',final/'repair.svf']
        template=(args.original/'formality/verify.tcl').read_text()
        old='set_svf '+q(args.original/'ppa/default.svf');oldnet='read_verilog -i '+q(original)
        need(template.count(old)==1 and template.count(oldnet)==1,'original own89 full FM template differs')
        verify=template.replace(old,'set_svf [list '+' '.join(q(p) for p in chain)+']').replace(oldnet,'read_verilog -i '+q(final/'mapped.v'))
        verify=verify.replace('XU_S2E_FULL_SOC_FORMALITY','XU_S2E_TIMING134_FORMALITY')
        (final/'verify.tcl').write_text(verify);generated[str(final/'verify.tcl')]=ident(final/'verify.tcl');state['svf_chain']=[ident(p) for p in chain]
        native(final,state,'fm','verify.tcl','XU_S2E_TIMING134_FORMALITY_PASS',env)
        need(freeze(final_identity)==final_identity and freeze(hold_identity)==hold_identity,'own proof targets changed during FM')
        remaining=caps((final/'constraints.rpt').read_text());state['remaining_electrical']=remaining
        state['reports']=freeze(list(final.glob('*.rpt'))+list(final.glob('*.tsv')))
        state['reset_paths']=(final/'reset-paths.tsv').read_text();state['timing']=(final/'timing-slack.tsv').read_text()
        state['status']='EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED'
    except BaseException as error:
        state.update(status='FAILED_NOT_QUALIFIED',error=type(error).__name__+': '+str(error),traceback=traceback.format_exc());raise
    finally:
        errors=[]
        try:
            state['frozen_after']=freeze(before);need(state['frozen_after']==before,'original frozen input changed')
            need(context.tool_identity()==tool_id and context.source_identity(args.source)==source_id,'source/tool identity changed')
            need(context.checked_mapped_context(args.source,args.original,args.audit)==checked,'own89/109 actual proof context changed')
            need(freeze(generated)==generated,'generated script/plan changed')
            for diagnostic in state.get('diagnostics',{}).values():
                need(freeze(diagnostic['reports'])==diagnostic['reports'],'native inventory evidence changed')
        except BaseException as error:errors.append(type(error).__name__+': '+str(error));state['status']='FAILED_NOT_QUALIFIED'
        state.update(frozen_input_errors=errors,generated=generated,finished_epoch=time.time());dump(out/'state.json',state)
    need(state['status']=='EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED',
         'worker terminal integrity guard rejected completion')
    print(state['status'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=BASE/'ChipContest-s2e-74')
    p.add_argument('--tools',type=Path,default=BASE/'ChipContest-s2e-activity-tools-109')
    p.add_argument('--original',type=Path,default=BASE/'s2e-ppa-campaign-20261104-89')
    p.add_argument('--audit',type=Path,default=BASE/'s2e-own-formality-audit-20261104-109')
    p.add_argument('--scope',type=Path,default=Path.home()/'Desktop/xu-ts16.tcl')
    p.add_argument('--out',type=Path,default=BASE/OUT)
    p.add_argument('--preflight-only',action='store_true')
    args=p.parse_args()
    for n in ('source','tools','original','audit','scope','out'):setattr(args,n,getattr(args,n).resolve())
    execute(args)


if __name__=='__main__':main()
