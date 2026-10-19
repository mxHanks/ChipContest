#!/usr/bin/env python3
"""Prove a buffer-only ECO projects to the original mapped cell graph.

All original cells/ports and state elements must survive. Only added real
non-inverting buffers and equivalent BUF strength substitutions are allowed.
This proves this ECO's zero-delay graph identity, not RTL-to-ABC equivalence.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import sram_evidence as E


def project_buffers(base,candidate):
    old=base['modules']['kwt_icb_slave_sram'];new=candidate['modules']['kwt_icb_slave_sram']
    cells=old['cells'];current=new['cells']
    if not set(cells)<=set(current):raise ValueError('original cell lost')
    translation={}
    for name,net in old['netnames'].items():
        if name not in new['netnames']:raise ValueError('original named net lost')
        bits=new['netnames'][name]['bits']
        if len(bits)!=len(net['bits']):raise ValueError('original named net width changed')
        for original,actual in zip(net['bits'],bits):
            if isinstance(actual,int) and isinstance(original,int):
                if actual in translation and translation[actual]!=original:raise ValueError('original named nets shorted')
                translation[actual]=original
            elif original!=actual:raise ValueError('original constant changed')
    if len(set(translation.values()))!=len(translation):raise ValueError('original wire split')
    added=set(current)-set(cells);links={}
    for name in added:
        c=current[name]
        if (c['type']!='BUF_X1' or c['port_directions']!={'A':'input','Z':'output'} or
            c['parameters'] or len(c['connections'].get('A',[]))!=1 or len(c['connections'].get('Z',[]))!=1):
            raise ValueError('unexpected non-buffer cell added')
        source=c['connections']['A'][0];target=c['connections']['Z'][0]
        if target in links or target in translation:raise ValueError('buffer drives existing/duplicate bit')
        links[target]=source
    def resolve(bit):
        visited=set()
        while isinstance(bit,int) and bit in links:
            if bit in visited:raise ValueError('ECO buffer cycle')
            visited.add(bit);bit=links[bit]
        if isinstance(bit,int):
            if bit not in translation:raise ValueError('unidentified ECO source')
            return translation[bit]
        return bit
    resized=[]
    for name,before in cells.items():
        after=current[name]
        if (before['port_directions']!=after['port_directions'] or before['parameters']!=after['parameters'] or
            set(before['connections'])!=set(after['connections'])):
            raise ValueError('original cell interface/parameters changed')
        if before['type']!=after['type']:
            if (before['type'],after['type'])!=('BUF_X1','BUF_X16'):
                raise ValueError('original cell function changed')
            resized.append(name)
        for pin,bits in before['connections'].items():
            if bits!=[resolve(bit) for bit in after['connections'][pin]]:
                raise ValueError('projected original connection differs: '+name+'/'+pin)
    if set(old['ports'])!=set(new['ports']):raise ValueError('external ports differ')
    for name,port in old['ports'].items():
        other=new['ports'][name]
        if port['direction']!=other['direction'] or port['bits']!=[resolve(bit) for bit in other['bits']]:
            raise ValueError('external connection differs')
    return {'status':'PASS','original_cells_checked':len(cells),'added_noninverting_buffers':len(added),
            'equivalent_buffer_resizes':resized,'projected_original_named_bits':len(translation),
            'scope':'buffer-only ECO versus original mapped graph, zero-delay state/port identity; not RTL-to-synthesis proof'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-report',type=Path,required=True)
    parser.add_argument('--candidate-report',type=Path,required=True)
    args=parser.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-eco-identity-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    result={'schema':'kwt-sram-buffer-eco-identity-v1','status':'RUNNING','inputs':[]}
    try:
        paths=[];designs=[]
        for p in (args.base_report.resolve(),args.candidate_report.resolve()):
            report=json.loads(p.read_text())
            if report.get('status')!='PASS' or report.get('reference_logic_mapping')!='PASS':raise ValueError('mapping structure not accepted')
            E.verify_records(report['inputs']+report['outputs'])
            net=Path(report['run_directory'])/'mapped.json';paths += [p,net]
            designs.append(json.loads(net.read_text()))
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib'
        text=lib.read_text()
        expected_sha='8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1'
        if E.record(lib)['sha256']!=expected_sha:raise ValueError('reference Liberty differs')
        for cell in ('BUF_X1','BUF_X16'):
            match=re.search(r'\bcell\s*\(\s*'+cell+r'\s*\)\s*\{(.*?)(?=\n\s*cell\s*\(|\Z)',text,re.S)
            if not match or not re.search(r'\bfunction\s*:\s*"A"\s*;',match[1]):raise ValueError('reference buffer is not identity A')
        result['inputs']=[E.record(p) for p in [Path(__file__),Path(E.__file__),lib,*paths]]
        result.update(project_buffers(*designs))
    except Exception as exc:result.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(result['inputs'])
        except (OSError,ValueError) as exc:result.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',result)
    print(json.dumps({'status':result['status'],'report':str(out/'result.json'),'error':result.get('error')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
