#!/usr/bin/env python3
"""Reference-only reset driver probe on an accepted STA macro-cut view.

Changes one BUF strength, writes the candidate, then re-reads it in a fresh
OpenSTA process with the exact original SDC. It is not a full mapped candidate,
functional qualification, an automatic hold fixer, or official ASIC signoff.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/verify'))
import sram_evidence as E
import run_memory_partial_sta as STA


def cell_body(lib,name):
    matches=list(re.finditer(r'\bcell\s*\(\s*'+re.escape(name)+r'\s*\)\s*\{',lib))
    if len(matches)!=1:raise ValueError('cell missing or ambiguous: '+name)
    start=matches[0].end();level=1
    for offset in range(start,len(lib)):
        if lib[offset]=='{':level+=1
        elif lib[offset]=='}':level-=1
        if not level:return lib[start:offset]
    raise ValueError('incomplete Liberty cell')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sta-report',type=Path,required=True)
    parser.add_argument('--buffer',choices=('BUF_X8','BUF_X16'),default='BUF_X8')
    parser.add_argument('--timeout',type=int,default=90)
    args=parser.parse_args()
    if args.timeout<=0:parser.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-reset-reference-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'kwt-reset-driver-reference-probe-v1','status':'RUNNING',
        'scope':'one-cell electrical experiment on macro-cut reference timing view only',
        'full_mapped_candidate':'NOT_CREATED','functional_validation':'NOT_RUN','official_ppa':'BLOCKED',
        'configuration':{'replacement_buffer':args.buffer,'rtl_changed':False,'sdc_changed':False},'inputs':[],'commands':[]}
    E.write_json(out/'result.json',report)
    try:
        original=args.sta_report.resolve();baseline=json.loads(original.read_text());base=original.parent
        if baseline.get('schema')!='kwt-sram-partial-sta-v1' or baseline.get('status')!='PASS':
            raise ValueError('accepted original reference STA execution required')
        E.verify_records(baseline['inputs']+baseline['outputs'])
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib'
        if E.record(lib)['sha256']!=STA.LIB_SHA256:raise ValueError('reference Liberty differs')
        source_net=base/'boundary.v';sdc=base/'reference.sdc';reset_report=(base/'reset_net.rpt').read_text()
        drivers=re.findall(r'^ (\S+)/Z output \(BUF_X1\)$',reset_report,re.M)
        if len(drivers)!=1 or not re.fullmatch(r'[A-Za-z0-9_]+',drivers[0]):
            raise ValueError('original reset is not uniquely driven by expected BUF_X1')
        driver=drivers[0];text=source_net.read_text()
        if len(re.findall(r'\bBUF_X1\s+'+re.escape(driver)+r'\s*\(',text))!=1:
            raise ValueError('original reset driver instance differs')
        library=lib.read_text();old=cell_body(library,'BUF_X1');new=cell_body(library,args.buffer)
        if any(not re.search(r'\bfunction\s*:\s*"A"\s*;',body) for body in (old,new)):
            raise ValueError('replacement is not the same non-inverting buffer function')
        area=lambda body:float(re.search(r'\barea\s*:\s*([\d.]+)\s*;',body)[1])
        report['reference_logic_area_delta_um2']=area(new)-area(old)
        report['driver_instance']=driver
        report['reference_buffer_max_capacitance_ff']=float(re.search(r'\bmax_capacitance\s*:\s*([\d.]+)',new)[1])
        report['reference_max_transition_ns']=float(re.search(r'\bdefault_max_transition\s*:\s*([\d.]+)',library)[1])
        sta=ROOT/'.tools/opensta/usr/bin/sta'
        deps=[Path(__file__),Path(E.__file__),Path(STA.__file__),original,lib,sta,source_net,sdc,base/'reset_net.rpt']
        report['identity']=E.source_identity(deps,report['configuration'],out/'source_identity.json')
        report['inputs']=list(report['identity']['inputs'])+baseline['inputs']+baseline['outputs']
        shutil.copyfile(source_net,out/'boundary.v');shutil.copyfile(sdc,out/'reference.sdc')
        (out/'edit.tcl').write_text('\n'.join([
            'read_liberty {'+str(lib)+'}','read_verilog boundary.v','link_design kwt_icb_slave_sram',
            'if {![replace_cell '+driver+' '+args.buffer+']} { error "reset replacement rejected" }',
            'write_verilog -sort candidate.v','puts KWT_RESET_EDIT_COMPLETE','exit','']))
        script=(base/'run.tcl').read_text().replace('read_verilog boundary.v','read_verilog candidate.v')
        (out/'run.tcl').write_text(script)
        report['inputs'] += [E.record(out/name) for name in ('boundary.v','reference.sdc','edit.tcl','run.tcl')]
        def execute(name,script,marker):
            command=E.run_command([str(sta),'-no_init','-exit',script],out,out/(name+'.log'),args.timeout,1)
            report['commands'].append(command);E.write_json(out/'result.json',report)
            error=E.completion_error(command,['^'+marker+'$'])
            if error:raise ValueError(name+' rejected: '+error)
            return (out/(name+'.log')).read_text()
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            execute('edit','edit.tcl','KWT_RESET_EDIT_COMPLETE')
            candidate=out/'candidate.v';emitted=candidate.read_text()
            if len(re.findall(r'\b'+args.buffer+r'\s+'+re.escape(driver)+r'\s*\(',emitted))!=1:
                raise ValueError('exported candidate lacks the actual replaced driver')
            report['inputs'].append(E.record(candidate))
            report['phase']='fresh_read_sta';E.write_json(out/'result.json',report)
            log=execute('sta','run.tcl',STA.MARKER)
        metrics=STA.timing_metrics(log,(out/'hold.rpt').read_text(),(out/'register_hold.rpt').read_text())
        report['reference_timing']=metrics
        reset=(out/'reset_net.rpt').read_text()
        if f'{driver}/Z output ({args.buffer})' not in reset:raise ValueError('fresh design did not retain replaced driver')
        cap=re.search(r'Total capacitance: r ([\d.]+) f ([\d.]+)',reset)
        if not cap:raise ValueError('missing reset capacitance')
        report['reset_total_capacitance_ff']={'rise':float(cap[1]),'fall':float(cap[2])}
        report['reset_capacitance_status']='PASS' if max(map(float,cap.groups()))<=report['reference_buffer_max_capacitance_ff'] else 'FAIL'
        report['baseline_reference_timing']={key:baseline.get(key) for key in metrics}
        report.update(status='PASS',phase='complete',acceptance='DIAGNOSTIC_ONLY; no complete design promotion')
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(report['inputs'])
        except (OSError,ValueError) as exc:report.update(status='FAIL',error=str(exc))
        report['outputs']=[E.record(p) for p in sorted(out.iterdir()) if p.is_file() and p.name not in ('result.json',)]
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
