#!/usr/bin/env python3
"""Expand sparse measured projections into actual 121-arc joint counters.

Integer exact invariants only. No simulator callback calibration, SAIF/PT
semantic equivalence or energy qualification is inferred from passing them.
Python 3.6+, standard library only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PORTS = [('A',10),('CEN',1),('CLK',1),('D',16),('EMA',3),('EMAW',2),('GWEN',1),('Q',16),('RET1N',1),('WEN',16)]
PINS = [name if width==1 else '%s[%d]'%(name,i) for name,width in PORTS for i in range(width)]
CONTROL = ['RET1N','CEN','GWEN','EMA[2]','EMA[1]','EMA[0]','EMAW[1]','EMAW[0]']
LEDGER = Path(__file__).with_name('xu_sram1024x16_arc_ledger.json')
SCHEMA = 'xu-sram-joint-projections-v1'
LEDGER_SHA256 = 'b950b6d0c8922073a2de6cc17a09aa66a5d7ae3d646acb6a5460bedfd440536b'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique_json(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'duplicate JSON field '+key)
        result[key]=value
    return result


def identity(path):
    p=Path(path)
    require(p.is_file() and not p.is_symlink(),'regular non-symlink input required')
    data=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def number(v):
    require(type(v) is int and 0<=v<2**64,'non-integer/negative/overflow counter')
    return v


def vector(v,n):
    require(type(v) is list and len(v)==n,'counter vector length differs')
    return [number(x) for x in v]


def four_not(x):
    return 1-x if x<2 else 2


def four_and(xs):
    return 0 if 0 in xs else (2 if any(x>1 for x in xs) else 1)


def condition(expression,state):
    if expression=='default':
        return 1
    values=[]
    for atom in expression.split(' & '):
        negative=atom.startswith('!')
        pin=atom[1:] if negative else atom
        require(pin in state,'condition state missing '+pin)
        value=state[pin]
        values.append(four_not(value) if negative else (value if value<2 else 2))
    return four_and(values)


def decode(p,key):
    if p in (0,1):
        result={name:(key>>(2*i))&3 for i,name in enumerate(CONTROL)}
        if p==1:result['CLK']=(key>>16)&3
        require(key < 2**(18 if p==1 else 16),'control projection key too wide')
        return result
    require(2<=p<34 and key<64,'D/Q projection key differs')
    if p<18:
        return {'WEN[%d]'%(p-2):key&3,'GWEN':(key>>2)&3,'D[%d]'%(p-2):(key>>4)&3}
    return {'RET1N':key&3,'GWEN':(key>>2)&3,'Q[%d]'%(p-18):(key>>4)&3}


def projection_for(pin):
    if pin=='CLK':return 1
    if pin=='RET1N' or pin is None:return 0
    if pin.startswith('D['):return 2+int(pin[2:-1])
    if pin.startswith('Q['):return 18+int(pin[2:-1])
    return None


def sparse(rows,transition):
    require(type(rows) is list,'sparse rows not list')
    out={p:{} for p in range(34)}
    seen=set()
    for row in rows:
        key,value=vector(row,2)
        require(key not in seen and value>0,'duplicate/zero sparse row')
        seen.add(key)
        p=key>>40
        require(p in out,'unexpected projection ID')
        packed=key&((1<<40)-1)
        if transition:
            previous,current=packed>>20,packed&((1<<20)-1)
            decode(p,previous);decode(p,current)
            require(previous!=current,'diagonal projection transition')
            out[p][(previous,current)]=value
        else:
            decode(p,packed);out[p][packed]=value
    return out


def state_text(text):
    require(type(text) is str and len(text)==67 and not (set(text)-set('01xz')),'invalid real pin state')
    return text


def audit_macro(record,duration,arcs):
    name=record['macro']
    require(type(name) is str and name,'macro name missing')
    state_text(record['final_state_lsb_ports']);number(record['callback_events'])
    require(len(record['pin_dwell'])==len(record['pin_transitions'])==67,'67 actual bits required')
    pin_dwell={n:vector(v,4) for n,v in zip(PINS,record['pin_dwell'])}
    pin_trans={n:vector(v,16) for n,v in zip(PINS,record['pin_transitions'])}
    for n in PINS:
        require(sum(pin_dwell[n])==duration,'raw pin dwell duration differs '+n)
        require(all(pin_trans[n][i*4+i]==0 for i in range(4)),'raw diagonal transition '+n)
    dwell=sparse(record['projection_dwell'],False)
    transitions=sparse(record['projection_transitions'],True)
    for p in range(34):
        require(sum(dwell[p].values())==duration,'projection dwell duration differs %d'%p)
        # Independent overlap invariant: every shared marginal must reproduce
        # the real direct pin observation, including X/Z and zero-dwell events.
        marginal={}
        for key,value in dwell[p].items():
            for n,s in decode(p,key).items():marginal.setdefault(n,[0]*4)[s]+=value
        for n,values in marginal.items():require(values==pin_dwell[n],'projection/direct pin dwell mismatch '+n)
        reconstructed={}
        for (old,new),value in transitions[p].items():
            a,b=decode(p,old),decode(p,new)
            for n,s in a.items():
                if s!=b[n]:reconstructed.setdefault(n,[0]*16)[s*4+b[n]]+=value
        for n in marginal:require(reconstructed.get(n,[0]*16)==pin_trans[n],'projection/direct transition mismatch '+n)
    arc_results=[]
    for arc in arcs:
        pin=arc['toggling_pin'];expression=arc['when'];p=projection_for(pin)
        cd=[0]*3;joint=[[0]*4 for _ in range(3)] if pin else None
        edges={}
        if p is None:
            require(expression=='default','unimplemented conditional pin')
            cd[1]=duration;joint[1]=pin_dwell[pin][:]
            for code,value in enumerate(pin_trans[pin]):
                if value:edges[(1,1,code//4,code%4)]=value
        else:
            for key,value in dwell[p].items():
                s=decode(p,key);c=condition(expression,s);cd[c]+=value
                if pin:joint[c][s[pin]]+=value
            if pin:
                for (old,new),value in transitions[p].items():
                    a,b=decode(p,old),decode(p,new)
                    if a[pin]!=b[pin]:
                        k=(condition(expression,a),condition(expression,b),a[pin],b[pin])
                        edges[k]=edges.get(k,0)+value
        require(sum(cd)==duration,'arc condition duration differs')
        if pin:
            require([sum(joint[c][s] for c in range(3)) for s in range(4)]==pin_dwell[pin],'arc joint/direct dwell mismatch')
            rebuilt=[0]*16
            for (_,_,old,new),value in edges.items():rebuilt[old*4+new]+=value
            require(rebuilt==pin_trans[pin],'arc transition/direct mismatch')
        arc_results.append(dict(arc_id=arc['arc_id'],kind=arc['kind'],toggling_pin=pin,when=expression,
            condition_dwell_false_true_unknown=cd,pin_joint_dwell=joint,
            conditional_transitions=[list(k)+[v] for k,v in sorted(edges.items())],
            leakage_default_policy='recorded fallback condition; not additive independent leakage' if arc['kind']=='leakage' and expression=='default' else None))
    return dict(macro=name,pin_dwell=pin_dwell,pin_transitions=pin_trans,
        control_joint_dwell=[[key,value] for key,value in sorted(dwell[0].items())],arcs=arc_results)


def audit(stats_path,sidecar_path):
    before=[identity(stats_path),identity(sidecar_path),identity(LEDGER)]
    require(before[2]['sha256']==LEDGER_SHA256,'frozen actual 121-arc ledger changed')
    ledger=json.loads(LEDGER.read_text(),object_pairs_hook=unique_json)
    arcs=ledger['arcs'];require(len(arcs)==121 and [a['arc_id'] for a in arcs]==list(range(121)),'actual ledger IDs differ')
    lines=[json.loads(line,object_pairs_hook=unique_json) for line in Path(stats_path).read_text().splitlines()]
    require(len(lines)>=3,'incomplete capture')
    header,footer=lines[0],lines[-1]
    require(header['schema']==SCHEMA and footer['complete'] is True,'capture schema/completion differs')
    duration=number(header['duration_ticks'])
    require(duration>0 and header['timescale_fs']==1 and number(header['end_tick'])-number(header['start_tick'])==duration,'capture duration differs')
    require(header['pin_bits_per_macro']==67 and header['liberty_arc_count']==121,'capture geometry differs')
    records=lines[1:-1];names=[r['macro'] for r in records]
    require(len(set(names))==len(names)==header['macro_count']==footer['macro_count'],'macro membership/count differs')
    results=[audit_macro(r,duration,arcs) for r in records]
    side=[json.loads(line,object_pairs_hook=unique_json) for line in Path(sidecar_path).read_text().splitlines()]
    begin,end,events={},{},[]
    seen_timestamps=set()
    for row in side:
        name=row['macro'];require(name in names,'sidecar extra macro')
        if 'begin_tick' in row:
            require(name not in begin and row['begin_tick']==header['start_tick'] and row['callback_ordinal']==header['begin_callback_ordinal'],'sidecar begin differs')
            begin[name]=state_text(row['initial_state_lsb_ports'])
        elif 'end_tick' in row:
            require(name not in end and row['end_tick']==header['end_tick'] and row['callback_ordinal']==header['end_callback_ordinal'],'sidecar end differs')
            end[name]=state_text(row['final_state_lsb_ports'])
        else:
            require(header['start_tick']<=number(row['tick'])<=header['end_tick'],'sidecar tick outside window')
            require((name,row['tick']) not in seen_timestamps,'duplicate sidecar macro timestamp')
            seen_timestamps.add((name,row['tick']))
            previous=0;state=list(state_text(row['pre_state_lsb_ports']))
            for event in row['events']:
                o=number(event['callback_ordinal']);require(o>previous,'sidecar callback ordering differs');previous=o
                require(event['port'] in dict(PORTS),'sidecar real port differs')
                start=0
                for port,width in PORTS:
                    if port==event['port']:break
                    start+=width
                require(event['old']==''.join(state[start:start+width]),'sidecar event old state differs')
                require(len(event['new'])==width and not(set(event['new'])-set('01xz')),'sidecar event new state differs')
                require(event['new']!=event['old'],'sidecar diagonal event')
                state[start:start+width]=event['new']
            events.append(row)
    require(set(begin)==set(end)==set(names) and len(events)==footer['simultaneous_records'],'sidecar completeness/count differs')
    for record in records:require(end[record['macro']]==record['final_state_lsb_ports'],'sidecar final direct state differs')
    require(before==[identity(stats_path),identity(sidecar_path),identity(LEDGER)],'inputs changed during audit')
    return dict(schema='xu-sram-joint-activity-audit-v1',status='INTEGER_INVARIANTS_PASS_NOT_SIMULATOR_SAIF_PT_OR_ENERGY_QUALIFIED',
        inputs=before,window=header,control_tuple_order=CONTROL,arc_ledger_report_sha256=ledger['report_sha256'],
        macro_count=len(names),arc_count_per_macro=121,simultaneous_records=len(events),macros=results,
        limitations=['Callback ordinal is observed VPI callback order; actual VCS active/NBA/readonly behavior must be calibrated.',
            'Simultaneous control/toggling and window-boundary events are retained; no unique effective PT energy condition is assumed.',
            'Macro membership must additionally match actual mapped inventory and producer/source provenance; no such identity is inferred here.',
            'No SAIF TC/TX/TZ/TB/IG or PT state_condition agreement, timing qualification or power/energy claim.'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stats',type=Path,required=True);p.add_argument('--sidecar',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    require(not args.out.exists(),'output exists')
    result=audit(args.stats,args.sidecar)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','macro_count','arc_count_per_macro','simultaneous_records')}))


if __name__=='__main__':main()
