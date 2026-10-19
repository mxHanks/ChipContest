#!/usr/bin/env python3
"""One measured NOR4 slew repair on the complete reference netlist.

The Liberty pin functions must match. Every cell/pin except that cell's drive
strength is retained, including the 72 SRAM instances and all earlier buffers.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
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


def repair_measured_nor4(netlist):
    edited=deepcopy(netlist);top=edited['modules'][TOP];cells=top['cells'];sinks={}
    for name,c in cells.items():
        for pin,direction in c['port_directions'].items():
            if direction=='input':
                for bit in c['connections'][pin]:sinks.setdefault(bit,[]).append((name,c['type'],pin))
    matches=[]
    for name,c in cells.items():
        if c['type']=='NOR4_X1' and set(c['connections'])=={'A1','A2','A3','A4','ZN'}:
            bit=c['connections']['ZN'][0];loads=sinks.get(bit,[])
            if len(loads)==10 and sorted(x[1] for x in loads)==sorted(['BUF_X1']*2+['NAND2_X1']*8):matches.append((name,c,loads))
    if len(matches)!=1:raise ValueError('measured NOR4 topology is absent or ambiguous')
    name,c,loads=matches[0];before=deepcopy(c);c['type']='NOR4_X2'
    return edited,{'instance':name,'before':before,'after':deepcopy(c),'loads':[{'cell':n,'type':t,'pin':p} for n,t,p in loads]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-report',type=Path,required=True)
    args=parser.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-slew-eco-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    result={'schema':'kwt-sram-one-cell-slew-eco-v1','status':'RUNNING','inputs':[],'commands':[]}
    E.write_json(out/'result.json',result)
    try:
        path=args.mapping_report.resolve();parent=json.loads(path.read_text())
        if parent.get('schema')!='kwt-sram-counter-hold-eco-v1' or parent.get('status')!='PASS':raise ValueError('counter-hold parent required')
        E.verify_records(parent['inputs']+parent['outputs'])
        net=Path(parent['run_directory'])/'mapped.json';original=json.loads(net.read_text());edited,change=repair_measured_nor4(original)
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib';library=lib.read_text()
        functions=[]
        for name in ('NOR4_X1','NOR4_X2'):
            body=cell_body(library,name)
            functions.append(re.findall(r'\bfunction\s*:\s*"([^"]+)"\s*;',body))
        if functions[0]!=functions[1] or len(functions[0])!=1:raise ValueError('NOR4 strength substitution changed library function')
        result.update({k:deepcopy(v) for k,v in parent.items() if k not in ('schema','status','identity','inputs','commands','outputs','eco_changes','run_directory','phase','parent_mapping','logic_area_delta_um2','parent_logic_area_delta_um2')})
        result.update(schema='kwt-sram-one-cell-slew-eco-v1',status='RUNNING',run_directory=str(out),
            scope='complete reference netlist single NOR4 drive-strength ECO; pending independent function/STA/electrical acceptance',
            functional_simulation='NOT_RUN',local_static_timing='NOT_RUN',reference_logic_mapping='NOT_RUN')
        result['configuration']['mapping_profile']='isolated-NOR4-slew-eco'
        result['parent_mapping']=E.record(path);result['eco_changes']=[change]
        result['equivalent_liberty_function']=functions[0][0]
        yosys=ROOT/'.tools/bin/yosys'
        deps=[Path(__file__),Path(C.__file__),ROOT/'scripts/synth/run_sram_reset_probe.py',Path(E.__file__),Path(M.__file__),
              ROOT/'scripts/synth/run_nangate_reference.py',path,net,lib,yosys,ROOT/'.tools/synth/usr/bin/yosys']
        result['identity']=E.source_identity(deps,result['configuration'],out/'source_identity.json')
        result['inputs']=list(result['identity']['inputs'])+parent['inputs']
        (out/'candidate-input.json').write_text(json.dumps(edited)+'\n')
        (out/'emit.ys').write_text('read_json candidate-input.json\ncheck -assert\nwrite_json mapped.json\nwrite_verilog -noattr -noexpr mapped.v\nlog KWT_SLEW_ECO_COMPLETE\n')
        result['inputs'] += [E.record(out/'candidate-input.json'),E.record(out/'emit.ys')]
        E.write_json(out/'result.json',result)
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            command=E.run_command([str(yosys),'-Q','-s','emit.ys'],out,out/'emit.log',90,1);result['commands'].append(command)
        error=E.completion_error(command,[r'^KWT_SLEW_ECO_COMPLETE$'])
        if error:raise ValueError('slew candidate emission rejected: '+error)
        emitted=json.loads((out/'mapped.json').read_text());C.verify_emitted_graph(edited,emitted)
        result['mapped_logic']=M.mapped_logic(emitted,set(parent['mapped_logic']['opaque_cells_excluded']),C.library_areas(library),TOP)
        result['predecessor_logic_area_um2']=parent['mapped_logic']['logic_area_um2']
        result['incremental_logic_area_um2']=result['mapped_logic']['logic_area_um2']-parent['mapped_logic']['logic_area_um2']
        result.update(status='PASS',phase='structural_candidate_only',reference_logic_mapping='PASS')
    except Exception as exc:result.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(result['inputs'])
        except (OSError,ValueError) as exc:result.update(status='FAIL',error=str(exc))
        result['outputs']=[E.record(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='result.json']
        E.write_json(out/'result.json',result)
    print(json.dumps({'status':result['status'],'report':str(out/'result.json'),'error':result.get('error')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
