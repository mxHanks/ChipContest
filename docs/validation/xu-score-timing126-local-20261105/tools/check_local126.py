#!/usr/bin/env python3
"""Host mechanism checks for126; artificial pin tables are never EDA evidence."""
import argparse
import ast
import csv
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('local126_worker',HERE/'xu_timing_coverage126.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


def write_tsv(path,columns,rows):
    with path.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=columns,delimiter='\t',lineterminator='\n');writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    args.out=args.out.resolve();args.out.mkdir(exist_ok=False)
    actual=ROOT/'build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116'
    result=[]
    def check(name,call):
        call();result.append(dict(name=name,status='PASS'))
    def rejects(call):
        try:call()
        except (ValueError,KeyError):return
        raise AssertionError('mutant incorrectly accepted')
    code=(HERE/'xu_timing_coverage126.py').read_text()
    check('python36_grammar',lambda:ast.parse(code,feature_version=(3,6)))
    text=(actual/'analysis-coverage.rpt').read_text()
    def native_coverage():
        rows=w.coverage_rows(text);assert len(rows)==27124
        period=[r for r in rows if r['check']=='min_period'];assert len(period)==10416
        assert len({r['pin'] for r in period})==336 and all(w.period_mode(r['condition']) is not None for r in period)
    check('actual116_full_coverage_27124_and_10416_labels',native_coverage)
    source=(actual/'sta.tcl').read_text();assert w.sha(actual/'sta.tcl')==w.STA_SHA
    prefix=source[len('if {[catch {\n'):source.index('redirect -file units.rpt {report_units}\n')]
    prefix=prefix.replace('read_verilog mapped.v\n','read_verilog {'+str((actual/'mapped.v').resolve())+'}\n')
    attrs={}
    old=ROOT/'build/xu-score-resume-20261103/next-results-export-82/pmu-reset-condition-20261104-80'
    for kind in ('pin','port','cell','clock','timing_arc','lib_timing_arc'):
        p=old/('attributes-'+kind+'.txt')
        attrs[kind]=[] if not p.exists() else sorted(set(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*)\s+'+kind+r'\s+(?:collection|boolean|float|string|double|integer)\b',p.read_text(),re.M)))
    script=w.diagnostic_tcl(prefix,dict(attributes=attrs,full_clock=True,period_detail=True))
    (args.out/'diagnosis-generated.tcl').write_text(script)
    (args.out/'installed-docs-generated.tcl').write_text(w.documentation_tcl())
    def tcl_complete():
        program='foreach p $argv {set f [open $p];set s [read $f];close $f;if {![info complete $s]} {error "incomplete Tcl"};puts COMPLETE}\n'
        p=args.out/'complete.tcl';p.write_text(program)
        r=subprocess.run(['tclsh',str(p),str(args.out/'diagnosis-generated.tcl'),str(args.out/'installed-docs-generated.tcl')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0 and r.stdout.splitlines()==[b'COMPLETE',b'COMPLETE'],r.stderr
    check('generated_tcl_complete_native_tcl_parser',tcl_complete)
    def no_cut():
        added=script[script.index(w.TCL_HELPERS):]
        assert not re.search(r'\b(?:set_false_path|set_case_analysis|set_clock_groups|set_disable_timing|create_clock|create_generated_clock|set_propagated_clock|set_input_delay|set_output_delay)\b',added)
        assert added.count('set_app_var timing_report_unconstrained_paths')==2
        assert 'set_app_var timing_report_unconstrained_paths $xu_report_original' in added
    check('no_new_constraint_clock_case_cut_propagation',no_cut)
    def helper_test():
        program=w.TCL_HELPERS.split('set xu_unknown')[0]
        program+='\nset f [open '+w.tq(args.out/'row.tsv')+' w]\nxu_row $f [list a b "x\\ty" "a\\nb" "a\\\\b"]\nclose $f\n'
        r=subprocess.run(['tclsh'],input=program.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0 and (args.out/'row.tsv').read_bytes()==b'a\tb\tx\\ty\ta\\nb\ta\\\\b\n',r.stderr
    check('tcl_tsv_escaping_roundtrip',helper_test)
    def structural_test():
        # An independent three-cell graph: clock-disabled comb output must not
        # hide the next sequential consumer. This mock proves helper mechanics.
        setup=r'''
proc sizeof_collection {x} {return [llength $x]}
proc get_object_name {x} {return $x}
proc get_pins {args} {if {[lsearch -exact $args -of_objects]>=0} {return comb/Z};return [lindex $args end]}
proc get_nets {args} {set p [lindex $args end];if {$p eq "first/Q"} {return n0};if {$p eq "comb/Z"} {return n1};error BADNET}
proc all_connected {args} {set n [lindex $args end];if {$n eq "n0"} {return {first/Q comb/A}};if {$n eq "n1"} {return {comb/Z second/D}};error BADCON}
proc get_cells {args} {if {[lindex $args end] eq "comb/A"} {return comb};return second}
proc get_attribute {object attribute} {
 if {$attribute eq "object_class"} {return pin}
 if {$attribute eq "direction"} {if {$object in {first/Q comb/Z}} {return out};return in}
 if {$attribute eq "is_hierarchical"} {return false}
 if {$attribute eq "is_sequential"} {if {$object eq "comb"} {return false};return true}
 if {$attribute eq "ref_name"} {return $object}
 error BADATTR
}
proc foreach_in_collection {variable collection body} {upvar 1 $variable v;foreach v $collection {uplevel 1 $body}}
'''
        helpers=w.TCL_HELPERS.replace('set xu_unknown [open unknown-queries.tsv w]','set xu_unknown [open '+w.tq(args.out/'mock-unknown.tsv')+' w]')
        program=setup+helpers+'\nset f [open '+w.tq(args.out/'structural.tsv')+' w]\nxu_structural_consumers $f 0 first/Q\nclose $f\n'
        r=subprocess.run(['tclsh'],input=program.encode(),cwd=str(args.out),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0 and not r.stderr,r.stderr
        raw=(args.out/'structural.tsv').read_text();assert 'second/D' in raw and 'comb/A' in raw
        mutant=program.replace('if {$object eq "comb"} {return false};return true','if {$object eq "comb"} {return UNKNOWN};return true')
        q=args.out/'structural-mutant.tcl';q.write_text(mutant)
        r=subprocess.run(['tclsh',str(q)],cwd=str(args.out),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode!=0 and b'classification unknown' in r.stderr
    check('structural_disabled_arc_independent_traversal_and_unknown_rejection',structural_test)
    # Synthetic native-like tables validate the independent analysis against
    # ORIGINAL116 coverage. No synthetic table is labeled a server result.
    scratch=args.out/'ARTIFICIAL_TABLES_NOT_NATIVE';scratch.mkdir()
    native=w.coverage_rows(text);names=sorted({r['pin'][:-4] for r in native if r['check']=='min_period'})
    mode=[]
    for n in names:
        for p,v in dict(w.MODE_BITS,CLK='',CEN='').items():mode.append(dict(macro=n,pin=p,constant_value=str(v),user_case_value='',clocks='xu_hfextclk' if p=='CLK' else '',nets='TEST_ONLY'))
    columns=['macro','pin','constant_value','user_case_value','clocks','nets']
    write_tsv(scratch/'macro-mode-pins.tsv',columns,mode)
    for filename in ('coverage-initial.rpt','coverage-final.rpt'):(scratch/filename).write_text(text)
    write_tsv(scratch/'macro-clock-arcs.tsv',['owner','index'],[dict(owner=n,index=0) for n in names])
    write_tsv(scratch/'reset-timing-paths.tsv',['index','source_kind','check','count','worst_slack','status'],
              [dict(index=i%5,source_kind='HF_RESET' if i<5 else 'TEST_ONLY',check='recovery',count=0,worst_slack='UNKNOWN',status='NO_PATH_UNKNOWN') for i in range(26)])
    write_tsv(scratch/'reset-q-consumers.tsv',['index','driver','net','consumer','ref_or_class','direction','sequential_or_endpoint'],
       [dict(index=i,driver='TEST_ONLY',net='TEST_ONLY',consumer=w.SINKS[j][0]+'/D',ref_or_class='TEST_ONLY',direction='in',sequential_or_endpoint='true') for i,j in [(0,1),(4,3)]])
    write_tsv(scratch/'report-display-policy.tsv',['field','value'],[dict(field='original',value='false'),dict(field='restored',value='false')])
    write_tsv(scratch/'unknown-queries.tsv',['scope','field','status','detail'],[])
    def analyse():return w.analyse(scratch,text)
    def positive():
        a=analyse();assert a['inactive_period_checks']==10416 and a['qualification']=='NOT_QUALIFIED'
        assert a['active_period_review']['status']=='NOT_PROVEN'
    check('actual_coverage_plus_artificial_constants_inactive_mode_proof_only',positive)
    def mutate_modes(kind):
        value=[dict(r) for r in mode]
        if kind=='flip':value[0]['constant_value']='0'
        if kind=='case':value[0]['user_case_value']='1'
        if kind=='missing':value.pop()
        if kind=='duplicate':value[-1]=dict(value[0])
        write_tsv(scratch/'macro-mode-pins.tsv',columns,value)
        try:rejects(analyse)
        finally:write_tsv(scratch/'macro-mode-pins.tsv',columns,mode)
    for kind in ('flip','case','missing','duplicate'):
        check('reject_'+kind+'_physical_mode_evidence',lambda kind=kind:mutate_modes(kind))
    def restore_mutant():
        write_tsv(scratch/'report-display-policy.tsv',['field','value'],[dict(field='original',value='false'),dict(field='restored',value='true')])
        rejects(analyse)
    check('reject_unrestored_report_display',restore_mutant)
    def missing_coverage():
        value=text.replace('untested  constant_disabled','untested  INJECTED_REASON',1)
        rejects(lambda:w.coverage_rows(value))
    check('reject_unowned_coverage_reason',missing_coverage)
    results=dict(status='LOCAL126_MECHANISM_CHECKS_PASS_NOT_SERVER_EXECUTION',qualification='NOT_QUALIFIED',checks=result,
                 actual_input_sha256={p.name:w.sha(p) for p in (actual/'state.json',actual/'analysis-coverage.rpt',actual/'sta.tcl')},
                 limits='Native collection/attribute semantics, actual mode const values, met detail, physical reset/RDC safety and all server126 execution remain unproven.')
    (args.out/'results.json').write_text(json.dumps(results,sort_keys=True,indent=2)+'\n')
    print(json.dumps(results,sort_keys=True,indent=2))


if __name__=='__main__':main()
