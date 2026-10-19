#!/usr/bin/env python3
"""Isolated, complete opaque-macro reference netlist ECO, never RTL #delay.

Uses real BUF_X1/BUF_X16 cells from the bound Liberty. This script only
qualifies connectivity/area; independent STA and functional replay are gates.
"""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/verify'))
sys.path.insert(0,str(Path(__file__).parent))
import sram_evidence as E
import run_memory_blackbox as M
from run_nangate_reference import library_areas

TOP='kwt_icb_slave_sram'


def minimum_eco(netlist,reset_stages=6,data_stages=1):
    if not (1<=reset_stages<=8 and 1<=data_stages<=4):raise ValueError('bounded positive buffer stages required')
    edited=deepcopy(netlist);top=edited['modules'][TOP];cells=top['cells'];nets=top['netnames']
    def driven_cell(signal):
        bits=nets[signal]['bits']
        if len(bits)!=1 or not isinstance(bits[0],int):raise ValueError('required scalar signal differs')
        drivers=[(name,cell) for name,cell in cells.items()
            for pin,direction in cell['port_directions'].items()
            if direction=='output' and bits[0] in cell['connections'][pin]]
        if len(drivers)!=1:raise ValueError('required signal must have unique driver')
        return bits[0],drivers[0]
    reset_bit,(reset_name,reset_cell)=driven_cell('u_engine.rst_n')
    if reset_cell['type']!='BUF_X1' or set(reset_cell['connections'])!={'A','Z'}:
        raise ValueError('expected original reset BUF_X1')
    valid_bit,(_,valid_cell)=driven_cell('u_engine.read_valid')
    _,(acc_name,acc_cell)=driven_cell('u_engine.accumulate_valid')
    if (valid_cell['type']!='DFFR_X1' or acc_cell['type']!='DFFR_X1' or
            acc_cell['connections'].get('D')!=[valid_bit]):
        raise ValueError('target data-hold path differs from accepted direct FF path')
    existing=[b for cell in cells.values() for bits in cell['connections'].values() for b in bits if isinstance(b,int)]
    existing += [b for net in list(nets.values())+list(top['ports'].values()) for b in net['bits'] if isinstance(b,int)]
    next_bit=max(existing)+1;changes=[]
    def chain(label,source,count):
        nonlocal next_bit
        for i in range(count):
            name=f'kwt_eco_{label}_{i:02d}'
            net_name=name+'_net'
            if any(n in cells or n in nets for n in (name,net_name)):raise ValueError('ECO name collision')
            target=next_bit;next_bit+=1
            cells[name]={'hide_name':0,'type':'BUF_X1','parameters':{},'attributes':{},
                'port_directions':{'A':'input','Z':'output'},'connections':{'A':[source],'Z':[target]}}
            nets[net_name]={'hide_name':0,'bits':[target],'attributes':{}}
            changes.append({'action':'insert','instance':name,'type':'BUF_X1','A':source,'Z':target})
            source=target
        return source
    old_reset_input=reset_cell['connections']['A'][0]
    reset_cell['connections']['A']=[chain('reset',old_reset_input,reset_stages)]
    reset_cell['type']='BUF_X16'
    acc_cell['connections']['D']=[chain('data_hold',valid_bit,data_stages)]
    changes += [{'action':'resize','instance':reset_name,'before':'BUF_X1','after':'BUF_X16','output_bit':reset_bit},
                {'action':'rewire_endpoint','instance':acc_name,'port':'D','original_bit':valid_bit,'new_bit':acc_cell['connections']['D'][0]}]
    if top['ports']!=netlist['modules'][TOP]['ports']:raise ValueError('external interface changed')
    return edited,changes


def verify_emitted_graph(expected,actual):
    """Yosys reassigns JSON bit IDs. Prove connectivity via every named bit."""
    old=expected['modules'][TOP];new=actual['modules'][TOP]
    if set(old['netnames'])!=set(new['netnames']) or set(old['cells'])!=set(new['cells']):
        raise ValueError('emission changed named net/cell inventory')
    translation={}
    for name,net in old['netnames'].items():
        emitted=new['netnames'][name]['bits']
        if len(net['bits'])!=len(emitted):raise ValueError('emission changed net width')
        for before,after in zip(net['bits'],emitted):
            if isinstance(before,int) and isinstance(after,int):
                if after in translation and translation[after]!=before:raise ValueError('emission shorted distinct bits')
                translation[after]=before
            elif before!=after:raise ValueError('emission changed a constant')
    if len(set(translation.values()))!=len(translation):raise ValueError('emission split one bit inconsistently')
    def restore(bits):
        return [translation[b] if isinstance(b,int) else b for b in bits]
    for name,cell in new['cells'].items():
        normalized=deepcopy(cell)
        normalized['connections']={pin:restore(bits) for pin,bits in cell['connections'].items()}
        if normalized!=old['cells'][name]:raise ValueError('emission changed specified cell: '+name)
    ports=deepcopy(new['ports'])
    for value in ports.values():value['bits']=restore(value['bits'])
    if ports!=old['ports']:raise ValueError('emission changed external ports')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-report',type=Path,required=True)
    parser.add_argument('--reset-stages',type=int,default=6)
    parser.add_argument('--data-stages',type=int,default=1)
    parser.add_argument('--timeout',type=int,default=90)
    args=parser.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-minimum-eco-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    result={'schema':'kwt-sram-reference-minimum-eco-v1','status':'RUNNING',
        'scope':'complete opaque-macro reference mapped netlist ECO; not accepted function/timing/official PPA',
        'run_directory':str(out),'reference_logic_mapping':'NOT_RUN','blackbox_structure':'NOT_RUN',
        'functional_simulation':'NOT_RUN','local_static_timing':'NOT_RUN','full_system_timing':'BLOCKED','official_ppa':'BLOCKED',
        'inputs':[],'commands':[],'configuration':{'top':TOP,'include_interface':True,'pipe_mul':1,'result_buffers':2,
        'sram_backend':'BLACKBOX','mapping_profile':'isolated-standard-cell-minimum-eco',
        'reset_stages':args.reset_stages,'data_stages':args.data_stages}}
    E.write_json(out/'result.json',result)
    try:
        parent_path=args.mapping_report.resolve();parent=json.loads(parent_path.read_text())
        if parent.get('status')!='PASS' or parent.get('reference_logic_mapping')!='PASS' or parent['configuration']['top']!=TOP:
            raise ValueError('accepted original full-interface mapping required')
        E.verify_records(parent['inputs']+parent['outputs'])
        net=Path(parent['run_directory'])/'mapped.json';original=json.loads(net.read_text())
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib'
        if E.record(lib)['sha256']!=M.LIB_SHA256:raise ValueError('reference Liberty mismatch')
        edited,changes=minimum_eco(original,args.reset_stages,args.data_stages)
        opaque=set(parent['mapped_logic']['opaque_cells_excluded'])
        original_macros={n:c for n,c in original['modules'][TOP]['cells'].items() if c['type'] in opaque}
        current_macros={n:c for n,c in edited['modules'][TOP]['cells'].items() if c['type'] in opaque}
        if original_macros!=current_macros or len(current_macros)!=72:raise ValueError('opaque macro connectivity changed')
        yosys=ROOT/'.tools/bin/yosys'
        deps=[Path(__file__),Path(E.__file__),Path(M.__file__),ROOT/'scripts/synth/run_nangate_reference.py',
            parent_path,net,lib,yosys,ROOT/'.tools/synth/usr/bin/yosys']
        result['identity']=E.source_identity(deps,result['configuration'],out/'source_identity.json')
        result['inputs']=list(result['identity']['inputs'])+parent['inputs']
        result['parent_mapping']=E.record(parent_path);result['eco_changes']=changes
        (out/'candidate-input.json').write_text(json.dumps(edited)+'\n')
        (out/'emit.ys').write_text('read_json candidate-input.json\ncheck -assert\nwrite_json mapped.json\nwrite_verilog -noattr -noexpr mapped.v\nlog KWT_MINIMUM_ECO_COMPLETE\n')
        result['inputs'] += [E.record(out/'candidate-input.json'),E.record(out/'emit.ys')]
        E.write_json(out/'result.json',result)
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            cmd=E.run_command([str(yosys),'-Q','-s','emit.ys'],out,out/'emit.log',args.timeout,1)
            result['commands'].append(cmd)
        error=E.completion_error(cmd,[r'^KWT_MINIMUM_ECO_COMPLETE$'])
        if error:raise ValueError('netlist emission rejected: '+error)
        emitted=json.loads((out/'mapped.json').read_text())
        verify_emitted_graph(edited,emitted)
        result['mapped_logic']=M.mapped_logic(emitted,opaque,library_areas(lib.read_text()),TOP)
        result['reference_library']=parent['reference_library'];result['structure']=parent['structure']
        result['structure_scope']='original unchanged macro/arithmetic inventory, not a fresh RTL synthesis'
        result['logic_area_delta_um2']=result['mapped_logic']['logic_area_um2']-parent['mapped_logic']['logic_area_um2']
        result.update(status='PASS',reference_logic_mapping='PASS',blackbox_structure='PASS',phase='structural_candidate_only')
    except Exception as exc:result.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(result['inputs'])
        except (OSError,ValueError) as exc:result.update(status='FAIL',error=str(exc))
        result['outputs']=[E.record(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='result.json']
        E.write_json(out/'result.json',result)
    print(json.dumps({'status':result['status'],'report':str(out/'result.json'),'error':result.get('error')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
