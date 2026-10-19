"""Reusable reader of actual partial-STA known-load electrical checks.

Input is the actual partial-STA report; previous reports/bindings stay
immutable. Logs stay under artifacts/runs. No fake SRAM load, no relaxed SDC,
no synthesis or automatic retry.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import importlib.util
import json
from pathlib import Path
import re
import shutil
import uuid

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('qualified_cap',HERE/'qualified_cap_model.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)
E=V.E;ROOT=V.ROOT


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sta-report',type=Path,required=True)
    args=p.parse_args();source=args.sta_report.resolve();sta=json.loads(source.read_text())
    if sta.get('schema')!='kwt-sram-partial-sta-v1' or sta.get('status')!='PASS':raise ValueError('completed partial STA source required')
    V.checked_records(sta['inputs']+sta['outputs'])
    base=source.parent;lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib'
    tool=ROOT/'.tools/opensta/usr/bin/sta'
    limits,inventory=V.inventory(json.loads((base/'boundary.json').read_text()),lib.read_text())
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-reference-electrical-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    r={'schema':'kwt-reference-followup-electrical-v1','status':'RUNNING','tool_status':'NOT_RUN',
       'scope':'known modeled capacitance and reported transition/clock on actual reference macro-cut; unknown macros remain blocked',
       'official_ppa':'BLOCKED','full_design_capacitance':'BLOCKED','inputs':[],'commands':[],
       'expected_inventory':inventory,'configuration':{'original_sdc':True,'wire_load_model':'5K_hvratio_1_1','additional_set_load':'NONE','timeout_seconds':120}}
    E.write_json(out/'result.json',r)
    try:
        for n in ('boundary.v','reference.sdc'):shutil.copyfile(base/n,out/n)
        (out/'limits.tsv').write_text(''.join(k+'\t'+str(v)+'\n' for k,v in sorted(limits.items())))
        tcl=V.TCL.replace('@LIB@',str(lib)).replace('@HEADER@','\t'.join(V.COLUMNS)).replace('@COUNT@',str(inventory['standard_output_driver_bits']))
        tcl=tcl.replace('file delete net.tmp','file delete net.tmp\nreport_check_types -max_transition -all_violators -verbose -digits 6 > transition.rpt\nreport_check_types -min_pulse_width -min_period -all_violators -verbose -digits 6 > clock_checks.rpt')
        (out/'run.tcl').write_text(tcl)
        deps=[Path(__file__),Path(V.__file__),Path(E.__file__),source,base/'boundary.json',lib,tool,
              *[out/n for n in ('boundary.v','reference.sdc','limits.tsv','run.tcl')]]
        r['identity']=E.source_identity(deps,r['configuration'],out/'source_identity.json')
        r['inputs']=list(r['identity']['inputs'])+sta['inputs']+sta['outputs']
        E.write_json(out/'result.json',r)
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            c=E.run_command([str(tool),'-no_init','-exit','run.tcl'],out,out/'sta.log',120,1);r['commands'].append(c)
        err=E.completion_error(c,[r'^KWT_REFERENCE_CAP_COMPLETE$',r'^KWT_REFERENCE_CAP_ROWS '+str(inventory['standard_output_driver_bits'])+'$'])
        if err:raise ValueError(err)
        r['tool_status']='PASS';r['measurement']=V.parse_table((out/'capacitance.tsv').read_text(),limits,inventory)
        r['reported_transition_violations']=len(re.findall(r'\bVIOLATED\b',(out/'transition.rpt').read_text()))
        r['reported_clock_violations']=len(re.findall(r'\bVIOLATED\b',(out/'clock_checks.rpt').read_text()))
        r['status']='PASS' if r['measurement']['known_load_status']=='PASS' and r['reported_transition_violations']==r['reported_clock_violations']==0 else 'FAIL'
    except Exception as ex:r.update(status='FAIL',error=type(ex).__name__+': '+str(ex))
    finally:
        try:V.checked_records(r['inputs'])
        except Exception as ex:r.update(status='FAIL',error=str(ex))
        r['outputs']=[E.record(f) for f in sorted(out.iterdir()) if f.is_file() and f.name!='result.json']
        E.write_json(out/'result.json',r)
    print(json.dumps({'status':r['status'],'report':str(out/'result.json'),'error':r.get('error')}))
    return 0 if r['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
