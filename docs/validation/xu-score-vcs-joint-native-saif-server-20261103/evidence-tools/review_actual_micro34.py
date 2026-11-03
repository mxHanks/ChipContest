"""xu actual-native-SAIF vs joint/probe field comparison, no fitted conversion."""
import argparse
from decimal import Decimal
import importlib.util
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def identity(path):
    p=Path(path);data=p.read_bytes()
    return dict(path=str(p.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def require(ok,message):
    if not ok:raise ValueError(message)


def probe_fields(log):
    boundary=re.compile(r'^XU_PROBE_(BEGIN|END) label=(\S+) tick=(\d+) width=(\d+) actual_fullname=(\S+) bits_lsb=([01xz]+)$',re.M)
    event=re.compile(r'^XU_PROBE_EVENT label=(\S+) tick=(\d+) ordinal=(\d+) callback_bits_lsb=([01xz]+) current_bits_lsb=([01xz]+)$',re.M)
    records={}
    for phase,label,tick,width,full,bits in boundary.findall(log):
        row=records.setdefault(label,dict(events=[]));require(phase not in row,'duplicate probe boundary')
        row[phase]=dict(tick=int(tick),width=int(width),full_name=full,bits=bits)
    for label,tick,ordinal,delivered,current in event.findall(log):
        require(label in records,'unknown probe event label')
        records[label]['events'].append(dict(tick=int(tick),ordinal=int(ordinal),delivered=delivered,current=current))
    require(len(records)==8,'probe geometry differs')
    for label,row in records.items():
        begin,end=row['BEGIN'],row['END'];width=begin['width']
        require(begin['full_name']==end['full_name'] and width==end['width'],'probe begin/end identity differs')
        require(len(begin['bits'])==len(end['bits'])==width,'probe boundary width differs')
        state=begin['bits'];tick=begin['tick'];dwell=[[0]*4 for _ in range(width)];transitions=[[0]*16 for _ in range(width)]
        for ev in row['events']:
            require(tick<=ev['tick']<=end['tick'] and len(ev['delivered'])==len(ev['current'])==width,'probe event outside geometry/window')
            for bit,old in enumerate(state):dwell[bit]['01xz'.index(old)]+=ev['tick']-tick
            for bit,(old,new) in enumerate(zip(state,ev['delivered'])):
                if old!=new:transitions[bit]['01xz'.index(old)*4+'01xz'.index(new)]+=1
            state=ev['delivered'];tick=ev['tick']
        for bit,old in enumerate(state):dwell[bit]['01xz'.index(old)]+=end['tick']-tick
        row.update(delivered_final_bits=state,delivered_end_matches=state==end['bits'],pin_dwell=dwell,
            pin_transitions=transitions,callback_current_difference_events=sum(ev['delivered']!=ev['current'] for ev in row['events']))
    return records


def review(root):
    activity=load('xu_micro34_saif_reader',ROOT/'tools/scripts/xu_soc_activity.py')
    auditor=load('xu_micro34_joint_auditor',ROOT/'tools/ppa/xu_joint_activity/xu_sram_joint_audit.py')
    collector=load('xu_micro34_joint_collector',ROOT/'tools/ppa/xu_candidate_joint_task_activity.py')
    state=json.loads((root/'state.json').read_text());require(state['status']=='MICRO_SAIF_EXECUTED_REVIEW_PENDING_NOT_QUALIFIED','actual micro not terminal executed')
    inputs={record['path']:record for record in state['input_identities_before_simulation']}
    require(state['input_identities_after']==state['input_identities_before_simulation'],'actual input identities changed')
    require(any(r['sha256']=='cbeadf216665fc0b212ab3e239f299f4c83a64f59df561d8715414e854ed8cb1' for r in inputs.values()),'mature cached observer missing')
    output=[]
    for mode in range(3):
        destination=root/('mode-%d'%mode);stats=destination/'joint.stats.jsonl';side=destination/'joint.simultaneous.jsonl';log=root/('mode-%d.log'%mode)
        joint=auditor.audit(stats,side);boundary=collector.check_boundary_sidecar(joint,side)
        native=activity.read_saif(destination/'native.saif');require(Decimal(native['timescale_seconds'])==Decimal('1e-15'),'native precision differs')
        require(native['duration_ticks']==joint['window']['duration_ticks'],'native/joint duration differs')
        probes=probe_fields(log.read_text());mac=joint['macros'][0];rows=[];byname={}
        for signal in native['signals']:byname.setdefault(signal['path'],[]).append(signal)
        for pin,dwell in sorted(mac['pin_dwell'].items()):
            name=mac['macro'].replace('.','/')+'/'+pin;found=byname.get(name,[]);require(found,'native SAIF missing actual port '+name)
            transition=mac['pin_transitions'][pin]
            fields=[dict(kind=r['kind'],**{k:r.get(k,0) for k in ('T0','T1','TX','TZ','TB','TC','IG')}) for r in found]
            rows.append(dict(pin=name,joint_dwell_0_1_x_z=dwell,joint_transition_16=transition,
                observed_known_binary_transition_count=transition[1]+transition[4],
                native_fields=fields,dwell_differences=[dict(kind=v['kind'],vpi_minus_native=[dwell[i]-v[k] for i,k in enumerate(('T0','T1','TX','TZ'))]) for v in fields]))
        for label,row in probes.items():
            name=row['BEGIN']['full_name'].replace('.','/');width=row['BEGIN']['width'];comparisons=[]
            for bit in range(width):
                full=name if width==1 else name+'[%d]'%bit
                candidates=byname.get(full,[])
                comparison=dict(pin=full,native_fields=[dict(kind=r['kind'],**{k:r.get(k,0) for k in ('T0','T1','TX','TZ','TB','TC','IG')}) for r in candidates])
                if label.startswith('actual_') or label=='owner_Q':
                    port={'actual_CLK':'CLK','actual_CEN':'CEN','actual_D':'D','owner_Q':'Q'}[label]
                    pin=port if width==1 else port+'[%d]'%bit
                    comparison.update(joint_dwell_matches=row['pin_dwell'][bit]==mac['pin_dwell'][pin],
                        joint_transition_matches=row['pin_transitions'][bit]==mac['pin_transitions'][pin])
                comparisons.append(comparison)
            row['native_and_joint_comparisons']=comparisons
        output.append(dict(mode=mode,window=joint['window'],joint_integer_audit=joint['status'],boundary_crosscheck=boundary,
            actual_port_fields=rows,probe_fields=probes,input_files=[identity(p) for p in (stats,side,log,destination/'native.saif')]))
    unfinished=(root/'mode-3.log').read_text();require('XU_JOINT_INCOMPLETE' in unfinished and 'XU_PROBE_INCOMPLETE' in unfinished,'unfinished negative not retained')
    return dict(status='ACTUAL_FIELDS_COMPARED_NOT_CALLBACK_SAIF_PT_OR_ENERGY_QUALIFIED',modes=output,unfinished_negative_retained=True,
        actual_state=identity(root/'state.json'),policy='No fitted conversion, edge insertion or deletion, probability independence, X-to-zero or cross-simulator equivalence assumption.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    result=review(args.directory);args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(result['status'])
