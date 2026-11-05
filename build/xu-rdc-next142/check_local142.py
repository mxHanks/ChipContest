#!/usr/bin/env python3
"""Offline142 contract/mechanism checks; never runs EDA or server launcher."""
import argparse
import ast
import csv
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ACTUAL = ROOT/'build/xu-score-resume-20261103/progress135/full-soc-coverage-rdc-20261105-132'
PARENT = ROOT/'build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116'
DOCS = ROOT/'docs/validation/xu-score-coverage132-server135-20261105'
spec = importlib.util.spec_from_file_location('xu142_worker', HERE/'xu_rdc_next142.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)


def write_tsv(path, fields, rows):
    with path.open('w') as f:
        writer=csv.DictWriter(f, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); a=p.parse_args()
    out=a.out.resolve(); out.mkdir(exist_ok=False); checks=[]
    def check(name, call):
        call(); checks.append(dict(name=name, status='PASS'))
    def rejects(call, kinds=(ValueError, AssertionError)):
        try: call()
        except kinds: return
        raise AssertionError('negative case incorrectly accepted')
    def grammar():
        for path in HERE.glob('*.py'): ast.parse(path.read_text(), feature_version=(3,6))
    check('python36_grammar', grammar)
    def frozen_evidence():
        assert w.sha(ACTUAL/'state.json')==w.ACTUAL132_SHA
        assert w.sha(ACTUAL/'installed-options.json')==w.OPTIONS132_SHA
        assert w.sha(PARENT/'state.json')==w.STATE_SHA and w.sha(PARENT/'sta.tcl')==w.STA_SHA
        assert w.sha(PARENT/'mapped.v')==w.MAPPED_SHA and w.sha(PARENT/'repair.svf')==w.SVF_SHA
        failed=ROOT/'build/xu-score-resume-20261103/coverage131/full-soc-coverage-rdc-20261105-126/state.json'
        assert w.sha(failed)==w.FAILED126_SHA
        state=w.load(failed)
        assert state['status']=='FAILED_NOT_QUALIFIED' and state['frozen_before']==state['frozen_after']
        assert [(r['returncode'],r['marker_count'],len(r['errors'])) for r in state['runs']]==[(0,1,0),(1,0,2018)]
        archive=DOCS/'xu-server-coverage-power-progress-20261105-135.tar.xz'
        assert w.sha(archive)=='7972967f569bdc76794e79fe8a112d43fb9ce0bd8d3c85aed8c589f9d5c1c19f'
        with tarfile.open(str(archive)) as t:
            for name in ('state.json','diagnosis.tcl','installed-options.json','reset-design-arcs.tsv'):
                assert t.extractfile('full-soc-coverage-rdc-20261105-132/'+name).read()==(ACTUAL/name).read_bytes()
    check('original_tar_and_exported_same116_132_input_bytes', frozen_evidence)
    source=(PARENT/'sta.tcl').read_text()
    prefix=source[len('if {[catch {\n'):source.index('redirect -file units.rpt {report_units}\n')]
    original_mapped=json.loads((ACTUAL/'state.json').read_text())['parent']['mapped']['path']
    prefix=prefix.replace('read_verilog mapped.v\n','read_verilog '+w.tq(original_mapped)+'\n')
    script=w.diagnostic_tcl(prefix); (out/'diagnosis-generated142.tcl').write_text(script)
    def tcl_complete():
        helper=out/'complete.tcl'
        helper.write_text('set f [open [lindex $argv 0]]; set s [read $f]; close $f; if {![info complete $s]} {error INCOMPLETE}; puts COMPLETE\n')
        r=subprocess.run(['tclsh',str(helper),str(out/'diagnosis-generated142.tcl')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0 and r.stdout.strip()==b'COMPLETE', r.stderr
    check('generated_full_tcl_native_parser_complete',tcl_complete)
    def no_mutation():
        added=script[script.index(w.TCL_HELPERS):]
        assert not re.search(r'\b(?:set_false_path|set_case_analysis|set_clock_groups|set_disable_timing|create_clock|create_generated_clock|set_propagated_clock|set_input_delay|set_output_delay|set_max_delay|set_min_delay|set_sense)\b',added)
        assert added.count('set_app_var ')==2
        assert 'set_app_var timing_report_unconstrained_paths true' in added
        assert 'set_app_var timing_report_unconstrained_paths $xu_report_original' in added
        assert not re.search(r'get_object_name\s+\$arc\b',added) and 'full_name' not in re.sub(r'#.*','',added)
        assert added.count('redirect -file {hf_reset-')==15 and added.count('redirect -file {any_endpoint_source-')==6
    check('no_constraint_graph_horizon_scope_mutation_or_arc_full_name', no_mutation)
    def contract(command, variant):
        words=command.split()
        assert words[:1]==['report_timing'] and '-delay_type max' in command
        if variant=='unfiltered':
            assert '-exceptions all' in command
            assert not {'-slack_lesser_than','-slack_greater_than','-nworst','-max_paths'} & set(words)
    def red_green():
        old=(ACTUAL/'diagnosis.tcl').read_text()
        line=next(x for x in old.splitlines() if x.startswith('xu_capture unconstrained-hf-0-recovery.rpt'))
        oldcmd=line[line.index('report_timing'):line.rindex(']')]
        rejects(lambda:contract(oldcmd,'unfiltered'))
        (out/'red132-original-query.txt').write_text(line+'\nREJECTED: old call still filters unconstrained candidates\n')
        for item in w.query_inventory():
            src='HF' if item['source_kind']=='HF_RESET' else None
            matched=w.report_command(src,'ASYNC','matched_filtered')
            unfiltered=w.report_command(src,'ASYNC','unfiltered')
            contract(unfiltered,'unfiltered')
            assert matched.replace(' -slack_lesser_than 1000000','')==unfiltered
            rejects(lambda:contract(unfiltered+' -slack_lesser_than 1000000','unfiltered'))
            rejects(lambda:contract(unfiltered+' -max_paths 1','unfiltered'))
    check('actual132_call_site_red_and142_single_variable_query_green',red_green)
    def native_arc_evidence():
        rows=w.tsv(ACTUAL/'reset-design-arcs.tsv')
        found=[]
        for c,a,r in w.SINKS:
            current=[x for x in rows if x['from_pin']==c+'/CK' and x['to_pin']==c+'/'+a]
            assert len(current)==2 and {x['sense'] for x in current}=={'setup_rise_clk_rise','hold_rise_clk_rise'}
            assert all(x['is_disabled']=='false' for x in current)
            found.extend(current)
        (out/'actual132-enabled-async-arc-review.json').write_text(json.dumps(found,sort_keys=True,indent=2)+'\n')
    check('actual132_all10_async_arcs_enabled_not_ck_d_constant_disabled',native_arc_evidence)
    def helper_scope():
        # Artificial native collections: naming an arc explicitly throws ATTR-1.
        mock=r'''
proc foreach_in_collection {var collection body} {upvar 1 $var value; foreach value $collection {uplevel 1 $body}}
proc sizeof_collection {x} {return [llength $x]}
proc get_object_name {x} {if {[string match ARC* $x]} {error {ATTR-1 full_name unsupported}}; return $x}
proc get_attribute {object field} {
 switch -- $field {
  from_pin {return OWNER/CK}
  to_pin {return OWNER/SDN}
  sense {return setup_rise_clk_rise}
  when {return !D}
  sdf_cond {return ENABLE_NOT_D}
  is_disabled - is_user_disabled - is_db_inherited_disabled {return false}
  default {error BAD_ATTRIBUTE}
 }
}
'''
        program=mock+w.TCL_HELPERS+'\nset f [open '+w.tq(out/'mock-arc.tsv')+' w]\nxu_arc_rows $f OWNER {ARC0}\nclose $f\n'
        p=out/'arc-scope-mock.tcl';p.write_text(program)
        r=subprocess.run(['tclsh',str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode==0 and not r.stderr,r.stderr
        assert 'OWNER|0|OWNER/CK|OWNER/SDN' in (out/'mock-arc.tsv').read_text()
        mutant=program.replace('set fn [get_object_name $from]','set fn [get_object_name $arc]')
        p=out/'arc-full-name-negative.tcl';p.write_text(mutant)
        r=subprocess.run(['tclsh',str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert r.returncode!=0 and b'ATTR-1' in r.stderr
    check('native_arc_scope_mock_green_and_full_name_red',helper_scope)
    def display_lifecycle():
        mock=r'''
set display false
proc get_app_var {name} {global display; return $display}
proc set_app_var {name value} {global display; set display $value; set f [open display-current.txt w]; puts $f $value; close $f}
proc sizeof_collection {x} {return [llength $x]}
set handle_index 0
array set handle_names {}
proc get_pins {args} {global handle_index handle_names; incr handle_index; set token PIN::$handle_index; set handle_names($token) [lindex $args end]; return $token}
proc get_object_name {x} {global handle_names; if {[info exists handle_names($x)]} {return $handle_names($x)}; return [regsub {^PORT::} $x {}]}
proc report_timing {args} {set f [open actual-native-commands.txt a]; puts $f [linsert $args 0 report_timing]; close $f; return {No constrained paths.}}
proc redirect {flag name command} {
 if {[string match *unfiltered.rpt $name] && [info exists ::inject_failure]} {error INJECTED_QUERY_FAILURE}
 set value [uplevel #0 $command]; set f [open $name w]; puts $f $value; close $f
}
'''
        setup='set hf PORT::'+w.HF_SOURCE+'\nset qf [open query-commands.tsv w]\nxu_row $qf {index source_kind variant report command native_invocation}\n'
        for failure in (False, True):
            target=out/('MOCK_DISPLAY_FAILURE' if failure else 'MOCK_DISPLAY_SUCCESS');target.mkdir()
            p=target/'display.tcl'
            body=mock+('set inject_failure 1\n' if failure else '')+w.TCL_HELPERS+setup+w.display_queries_tcl()
            p.write_text(w.guarded(body,'MOCK_DISPLAY_DONE'))
            r=subprocess.run(['tclsh',str(p)],cwd=str(target),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            assert (target/'display-current.txt').read_text().strip()=='false'
            rows=w.tsv(target/'report-display-policy.tsv')
            assert [x['value'] for x in rows]==['false','true','false']
            if failure:
                assert r.returncode!=0 and b'INJECTED_QUERY_FAILURE' in r.stderr
                assert b'MOCK_DISPLAY_DONE' not in r.stdout
            else:
                assert r.returncode==0 and not r.stderr,r.stderr
                rows=w.tsv(target/'query-commands.tsv'); assert len(rows)==21
                actual_commands=(target/'actual-native-commands.txt').read_text().splitlines()
                assert [row['native_invocation'] for row in rows]==actual_commands
                assert len({re.search(r' -to (PIN::\d+)',row['native_invocation']).group(1) for row in rows})==7
                for row in rows:
                    i=int(row['index']);src=w.HF_SOURCE if row['source_kind']=='HF_RESET' else None
                    assert row['command']==w.report_command(src,w.SINKS[i][0]+'/'+w.SINKS[i][1],row['variant'])
                    assert 'PIN::' in row['native_invocation']
    check('production_display_lifecycle_and_native_collection_logging_success_and_error',display_lifecycle)
    def observations():
        for i in range(5): assert w.report_observation((ACTUAL/('unconstrained-hf-%d-recovery.rpt'%i)).read_text())['status']=='NO_PATH_UNKNOWN'
        for raw in ('(Path is unconstrained)','Startpoint: HF\nEndpoint: ASYNC\n(Path is unconstrained)\nslack (MET) INFINITY'):
            r=w.report_observation(raw)
            assert r['status']=='UNCONSTRAINED_PATH_DISPLAY_ONLY_NOT_RECOVERY_PROOF' and r['qualification']=='NOT_QUALIFIED'
        r=w.report_observation('Startpoint: HF\nEndpoint: ASYNC\nslack (MET) 1.0')
        assert r['status']=='PATH_TEXT_PRESENT_DIAGNOSTIC_ONLY' and r['qualification']=='NOT_QUALIFIED'
        assert w.report_observation('incomplete output')['status']=='UNRECOGNIZED_REPORT_UNKNOWN'
    check('actual_no_path_and_artificial_unconstrained_never_recovery_met',observations)
    def same_coverage():
        rows=w.coverage_rows((PARENT/'analysis-coverage.rpt').read_text())
        other=w.coverage_rows((ACTUAL/'coverage-final.rpt').read_text())
        assert len(rows)==27124
        assert sorted(json.dumps(x,sort_keys=True) for x in rows)==sorted(json.dumps(x,sort_keys=True) for x in other)
    check('full27124_116_132_field_multiset_equal',same_coverage)
    def analysis_mechanism():
        target=out/'ARTIFICIAL_REPORTS_NOT_NATIVE';target.mkdir()
        for suffix in ('initial','final'):
            (target/('coverage-'+suffix+'.rpt')).write_bytes((ACTUAL/'coverage-final.rpt').read_bytes())
            for kind in ('case','exceptions','clocks'):
                history=ACTUAL/(kind+'.rpt' if kind=='clocks' else kind+'-final.rpt')
                (target/(kind+'-'+suffix+'.rpt')).write_bytes(history.read_bytes())
        fields=['owner','index','from_pin','to_pin','scope']+w.ARC_FIELDS
        arcs=[]
        for cell,apin,ref in w.SINKS:
            old=[r for r in w.tsv(ACTUAL/'reset-design-arcs.tsv') if r['from_pin']==cell+'/CK' and r['to_pin']==cell+'/'+apin]
            for i,row in enumerate(old):
                item={k:row[k] for k in fields if k not in ('index','scope')}
                item['index']=str(i);item['scope']='|'.join([cell,str(i),row['from_pin'],row['to_pin']]);arcs.append(item)
        write_tsv(target/'reset-ck-async-arcs.tsv',fields,arcs)
        write_tsv(target/'report-display-policy.tsv',['field','value'],[dict(field=f,value=v) for f,v in [('original','false'),('active','true'),('restored','false')]])
        commands=[]
        for item in w.query_inventory():
            i=item['index'];kind=item['source_kind'];tag='%s-%d'%(kind.lower(),i)
            for variant in ('original132_filtered','matched_filtered','unfiltered'):
                name=tag+'-'+variant+'.rpt'
                raw='No constrained paths.\n' if variant!='unfiltered' else 'Startpoint: MOCK_HF\nEndpoint: MOCK_ASYNC\n(Path is unconstrained)\n'
                (target/name).write_text(raw)
                commands.append(dict(index=i,source_kind=kind,variant=variant,report=name,
                                     command=w.report_command(w.HF_SOURCE if kind=='HF_RESET' else None,w.SINKS[i][0]+'/'+w.SINKS[i][1],variant),native_invocation='ARTIFICIAL_ONLY'))
        write_tsv(target/'query-commands.tsv',['index','source_kind','variant','report','command','native_invocation'],commands)
        result=w.analyse(target,PARENT,ACTUAL)
        assert len(result['reports'])==7 and all(r['recovery_qualification']=='NOT_PROVEN' for r in result['reports'])
        assert all(r['visibility_verdict']=='FILTER_HID_UNCONSTRAINED_DISPLAY_ONLY_NOT_RECOVERY_PROOF' for r in result['reports'])
        def mutate_command():
            bad=[dict(r) for r in commands];bad[2]['command']+=' -max_paths 1'
            write_tsv(target/'query-commands.tsv',['index','source_kind','variant','report','command','native_invocation'],bad)
            rejects(lambda:w.analyse(target,PARENT,ACTUAL))
        mutate_command()
        write_tsv(target/'query-commands.tsv',['index','source_kind','variant','report','command','native_invocation'],commands)
        bad=[dict(r) for r in arcs];bad[0]['is_disabled']='true'
        write_tsv(target/'reset-ck-async-arcs.tsv',fields,bad)
        rejects(lambda:w.analyse(target,PARENT,ACTUAL))
    check('full_analysis_artificial_visibility_gap_never_qualified_and_mutants_rejected',analysis_mechanism)
    def launcher_guards():
        spec=importlib.util.spec_from_file_location('xu142_launcher',HERE/'launch_rdc_next142.py')
        launch=importlib.util.module_from_spec(spec);spec.loader.exec_module(launch)
        assert launch.EXPECTED_WORKER==w.sha(HERE/'xu_rdc_next142.py')
        launch.OUT=out/'existing-output';launch.OUT.mkdir()
        launch.LAUNCH=out/'not-created-launch';launch.WORKER=out/'missing-worker'
        rejects(launch.main)
        assert not launch.LAUNCH.exists()
    check('launcher_frozen_worker_and_existing_output_no_spawn',launcher_guards)
    def failed_preflight_freeze():
        original_out=w.OUT; original_preflight=w.preflight
        w.OUT=out/'FAILED_PREFLIGHT_NO_NATIVE_RUN'
        def fail(): raise ValueError('ARTIFICIAL_PREFLIGHT_FAILURE')
        w.preflight=fail
        try:
            with contextlib.redirect_stdout(io.StringIO()): rejects(w.main)
            state=w.load(w.OUT/'state.json')
            assert state['status']=='FAILED_NOT_QUALIFIED' and state['frozen_inputs_unchanged'] is False
            assert state['frozen_capture_complete'] is False and state['runs']==[]
            assert state['integrity_observation_status']=='PRECHECK_FAILED_NO_COMPLETE_FREEZE'
        finally:
            w.OUT=original_out;w.preflight=original_preflight
    check('preflight_failure_never_claims_empty_freeze_verified',failed_preflight_freeze)
    result=dict(status='LOCAL142_MECHANISM_PASS_NOT_SERVER_EXECUTION',qualification='NOT_QUALIFIED',checks=checks,
                generated_tcl_sha256=w.sha(out/'diagnosis-generated142.tcl'),
                actual132_state_sha256=w.ACTUAL132_SHA, same116_mapped_sha256=w.MAPPED_SHA,
                scope_sha256=w.SCOPE_SHA,
                limits='Offline Tcl/parser/contract and actual-byte evidence checks only. No native142 path result, recovery qualification, or whole-SoC150MHz qualification exists.')
    w.dump(out/'results.json',result);print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
