#!/usr/bin/env python3
"""Second isolated reference ECO: two measured counter feedback D branches.

Parent reset/read-valid candidate stays immutable. No RTL, count function,
clock/SDC or SRAM connectivity is changed; real BUF_X1 cells add min delay.
"""
from copy import deepcopy
from datetime import datetime,timezone
import argparse
import fcntl
import json
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
import run_sram_minimum_candidate as C
E=C.E;M=C.M;ROOT=C.ROOT;TOP=C.TOP


def counter_eco(netlist):
    edited=deepcopy(netlist);top=edited['modules'][TOP];cells=top['cells'];nets=top['netnames']
    all_bits=[b for cell in cells.values() for bits in cell['connections'].values() for b in bits if isinstance(b,int)]
    all_bits += [b for net in list(nets.values())+list(top['ports'].values()) for b in net['bits'] if isinstance(b,int)]
    next_bit=max(all_bits)+1;changes=[]
    for label in ('b_loaded','x_loaded'):
        signal='u_engine.'+label;bits=nets[signal]['bits']
        if not bits or not isinstance(bits[0],int):raise ValueError('counter signal geometry differs')
        drivers=[(name,cell) for name,cell in cells.items()
                 if cell['type']=='DFFR_X1' and cell['connections'].get('Q')==[bits[0]]]
        if len(drivers)!=1:raise ValueError('counter Q driver missing or ambiguous')
        target_name,target=drivers[0];before=target['connections']['D']
        if len(before)!=1 or not isinstance(before[0],int):raise ValueError('counter D source differs')
        name='kwt_eco_counter_'+label;net_name=name+'_net'
        if any(n in cells or n in nets for n in (name,net_name)):raise ValueError('counter ECO name collision')
        cells[name]={'hide_name':0,'type':'BUF_X1','parameters':{},'attributes':{},
                     'port_directions':{'A':'input','Z':'output'},'connections':{'A':before.copy(),'Z':[next_bit]}}
        nets[net_name]={'hide_name':0,'bits':[next_bit],'attributes':{}}
        target['connections']['D']=[next_bit]
        changes.append({'counter':signal,'bit':0,'endpoint':target_name,'inserted_buffer':name,
                        'original_D':before[0],'new_D':next_bit,'type':'BUF_X1'})
        next_bit+=1
    return edited,changes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-report',type=Path,required=True)
    args=parser.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-counter-hold-eco-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    report={'schema':'kwt-sram-counter-hold-eco-v1','status':'RUNNING','inputs':[],'commands':[]}
    E.write_json(out/'result.json',report)
    try:
        path=args.mapping_report.resolve();parent=json.loads(path.read_text())
        if parent.get('status')!='PASS' or parent.get('reference_logic_mapping')!='PASS' or parent.get('schema')!='kwt-sram-reference-minimum-eco-v1':
            raise ValueError('require structurally accepted reset/read-valid candidate')
        E.verify_records(parent['inputs']+parent['outputs'])
        net=Path(parent['run_directory'])/'mapped.json';original=json.loads(net.read_text())
        edited,changes=counter_eco(original)
        report.update({k:deepcopy(v) for k,v in parent.items() if k not in ('schema','status','identity','inputs','commands','outputs','eco_changes','run_directory','phase','parent_mapping')})
        report.update(schema='kwt-sram-counter-hold-eco-v1',status='RUNNING',run_directory=str(out),
            scope='complete reference netlist counter feedback hold ECO; function/timing not yet accepted',
            functional_simulation='NOT_RUN',local_static_timing='NOT_RUN',reference_logic_mapping='NOT_RUN')
        report['configuration']['mapping_profile']='isolated-counter-minimum-eco'
        report['configuration']['counter_endpoints']=['u_engine.b_loaded[0]','u_engine.x_loaded[0]']
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib';yosys=ROOT/'.tools/bin/yosys'
        deps=[Path(__file__),Path(C.__file__),Path(E.__file__),Path(M.__file__),
              ROOT/'scripts/synth/run_nangate_reference.py',path,net,lib,yosys,ROOT/'.tools/synth/usr/bin/yosys']
        report['identity']=E.source_identity(deps,report['configuration'],out/'source_identity.json')
        report['inputs']=list(report['identity']['inputs'])+parent['inputs']
        report['parent_mapping']=E.record(path);report['eco_changes']=changes
        (out/'candidate-input.json').write_text(json.dumps(edited)+'\n')
        (out/'emit.ys').write_text('read_json candidate-input.json\ncheck -assert\nwrite_json mapped.json\nwrite_verilog -noattr -noexpr mapped.v\nlog KWT_COUNTER_ECO_COMPLETE\n')
        report['inputs'] += [E.record(out/'candidate-input.json'),E.record(out/'emit.ys')]
        E.write_json(out/'result.json',report)
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            cmd=E.run_command([str(yosys),'-Q','-s','emit.ys'],out,out/'emit.log',90,1)
            report['commands'].append(cmd)
        error=E.completion_error(cmd,[r'^KWT_COUNTER_ECO_COMPLETE$'])
        if error:raise ValueError('counter emission rejected: '+error)
        emitted=json.loads((out/'mapped.json').read_text());C.verify_emitted_graph(edited,emitted)
        opaque=set(parent['mapped_logic']['opaque_cells_excluded'])
        if {n:c for n,c in original['modules'][TOP]['cells'].items() if c['type'] in opaque}!={n:c for n,c in edited['modules'][TOP]['cells'].items() if c['type'] in opaque}:
            raise ValueError('macro connectivity changed')
        report['mapped_logic']=M.mapped_logic(emitted,opaque,C.library_areas(lib.read_text()),TOP)
        report['parent_logic_area_delta_um2']=report['mapped_logic']['logic_area_um2']-parent['mapped_logic']['logic_area_um2']
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
