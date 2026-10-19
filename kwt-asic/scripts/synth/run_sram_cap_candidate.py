#!/usr/bin/env python3
"""Resize only the four measured max-cap drivers in an independent full netlist.

Targets bind the measured report and complete original cell objects. This
qualifies graph/function identity and area only; STA and replay are separate.
Missing real SRAM pin capacitance remains unknown after this reference repair.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
import run_sram_minimum_candidate as C
from run_sram_reset_probe import cell_body
E=C.E;M=C.M;ROOT=C.ROOT;TOP=C.TOP


def resize_measured_cells(netlist, targets):
    if len(targets)!=4 or len({t['instance'] for t in targets})!=4:
        raise ValueError('exactly four unique measured drivers required')
    edited=deepcopy(netlist);changes=[]
    for target in targets:
        name=target['instance'];before=edited['modules'][TOP]['cells'].get(name)
        if before!=target['expected_cell']:
            raise ValueError('measured original cell changed: '+name)
        after_type=target['replacement_type']
        if (before['type'],after_type) not in (('NOR3_X1','NOR3_X2'),('NOR4_X1','NOR4_X2')):
            raise ValueError('unsupported measured strength substitution')
        previous=deepcopy(before);before['type']=after_type
        changes.append({'instance':name,'measured_driver_pin':target['measured_driver_pin'],
                        'before':previous,'after':deepcopy(before)})
    return edited,changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-report',type=Path,required=True)
    parser.add_argument('--cap-report',type=Path,required=True)
    parser.add_argument('--targets',type=Path,required=True)
    args=parser.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-cap-eco-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    report={'schema':'kwt-sram-four-cell-cap-eco-v1','status':'RUNNING','inputs':[],'commands':[],
            'scope':'complete reference netlist four measured max-cap strength changes; function/STA/electrical pending',
            'official_ppa':'BLOCKED','full_system_timing':'BLOCKED','functional_simulation':'NOT_RUN','local_static_timing':'NOT_RUN'}
    E.write_json(out/'result.json',report)
    try:
        parent_path=args.mapping_report.resolve();parent=json.loads(parent_path.read_text())
        cap_path=args.cap_report.resolve();cap=json.loads(cap_path.read_text())
        plan_path=args.targets.resolve();plan=json.loads(plan_path.read_text())
        if parent.get('schema')!='kwt-sram-one-cell-slew-eco-v1' or parent.get('status')!='PASS':raise ValueError('accepted structural slew parent required')
        if cap.get('tool_status')!='PASS' or cap.get('measurement',{}).get('known_load_violating_drivers')!=4:raise ValueError('four measured max-cap failures required')
        E.verify_records(parent['inputs']+parent['outputs']+cap['inputs']+cap['outputs'])
        if plan['mapping_report']!=E.record(parent_path) or plan['cap_report']!=E.record(cap_path):raise ValueError('target plan source identity differs')
        drivers={f['driver_pin'] for f in cap['measurement']['failures']}
        if drivers!={t['measured_driver_pin'] for t in plan['targets']}:raise ValueError('target selection differs from actual violations')
        if not any(r['path']==str(parent_path) and r['sha256']==E.record(parent_path)['sha256'] for r in cap['inputs']):raise ValueError('cap report is not bound to selected parent')
        net=Path(parent['run_directory'])/'mapped.json';original=json.loads(net.read_text())
        edited,changes=resize_measured_cells(original,plan['targets'])
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib';library=lib.read_text()
        for change in changes:
            types=[change[k]['type'] for k in ('before','after')]
            functions=[re.findall(r'\bfunction\s*:\s*"([^"]+)"\s*;',cell_body(library,t)) for t in types]
            if len(functions[0])!=1 or functions[0]!=functions[1]:raise ValueError('Liberty function mismatch')
            change['bound_liberty_function']=functions[0][0]
        report.update(configuration=deepcopy(parent['configuration']),structure=deepcopy(parent['structure']),
                      reference_library=deepcopy(parent['reference_library']),parent_mapping=E.record(parent_path),
                      measured_cap_report=E.record(cap_path),target_plan=E.record(plan_path),eco_changes=changes,
                      run_directory=str(out),reference_logic_mapping='NOT_RUN',blackbox_structure='PASS')
        report['configuration']['mapping_profile']='isolated-four-cell-max-cap-eco'
        yosys=ROOT/'.tools/bin/yosys'
        deps=[Path(__file__),Path(C.__file__),ROOT/'scripts/synth/run_sram_reset_probe.py',Path(E.__file__),Path(M.__file__),
              ROOT/'scripts/synth/run_nangate_reference.py',parent_path,cap_path,plan_path,net,lib,yosys,ROOT/'.tools/synth/usr/bin/yosys']
        report['identity']=E.source_identity(deps,report['configuration'],out/'source_identity.json')
        report['inputs']=list(report['identity']['inputs'])+parent['inputs']
        (out/'candidate-input.json').write_text(json.dumps(edited)+'\n')
        (out/'emit.ys').write_text('read_json candidate-input.json\ncheck -assert\nwrite_json mapped.json\nwrite_verilog -noattr -noexpr mapped.v\nlog KWT_CAP_ECO_COMPLETE\n')
        report['inputs'] += [E.record(out/'candidate-input.json'),E.record(out/'emit.ys')]
        E.write_json(out/'result.json',report)
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            command=E.run_command([str(yosys),'-Q','-s','emit.ys'],out,out/'emit.log',90,1);report['commands'].append(command)
        error=E.completion_error(command,[r'^KWT_CAP_ECO_COMPLETE$'])
        if error:raise ValueError('max-cap candidate emission rejected: '+error)
        emitted=json.loads((out/'mapped.json').read_text());C.verify_emitted_graph(edited,emitted)
        report['mapped_logic']=M.mapped_logic(emitted,set(parent['mapped_logic']['opaque_cells_excluded']),C.library_areas(library),TOP)
        report['predecessor_logic_area_um2']=parent['mapped_logic']['logic_area_um2']
        report['incremental_logic_area_um2']=round(report['mapped_logic']['logic_area_um2']-parent['mapped_logic']['logic_area_um2'],6)
        report.update(status='PASS',phase='structural_candidate_only',reference_logic_mapping='PASS')
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(report['inputs'])
        except (OSError,ValueError) as exc:report.update(status='FAIL',error=str(exc))
        report['outputs']=[E.record(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='result.json']
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
