#!/usr/bin/env python3
"""Seal electrical ECO tools and one compact deterministic original1064 plan.

No EDA or transport. The generated native plan contains only nonreset edits;
all 17 reset roots remain measured and explicitly unresolved at every PT stage.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
from prepare import FILES

MAPPED_SHA='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'
SCHEMA='ingress1064-hierarchy-local-electrical-static-plan-v1'
GROUP_KEYS=['id','net_id','driver','owner','expected_local_net','allowed_local_net_aliases','loads','load_kinds','max_loads','phase','new_cell_name','asynchronous_reset_net']
ROOT_KEYS=['net_id','driver','reference','original_flattened_sink_count','predicted_final_root_sink_count','predicted_max_new_buffer_sink_count','asynchronous_reset_net','check_types']

def need(value,message):
    if not value:raise ValueError(message)

def literal(value):
    if isinstance(value,list):return '{'+' '.join(literal(x)for x in value)+'}'
    if isinstance(value,bool):return '1' if value else '0'
    value=str(value)
    need(not any(c in value for c in '{}\\\r\n'),'unsafe explicit electrical Tcl literal')
    return '{'+value+'}'

def validate_plan(plan):
    need(plan.get('schema')==SCHEMA and plan.get('mapped_sha256')==MAPPED_SHA and plan.get('qualification') is False,'not the explicit original1064 electrical plan')
    need(plan.get('max_group_loads')==16 and plan.get('nonreset_net_count')==51 and plan.get('nonreset_group_count')==198 and plan.get('asynchronous_reset_net_count')==17 and plan.get('asynchronous_reset_groups_NOT_AUTHORIZED_BY_THIS_PLAN')==128,'unsupported electrical plan bounds')
    nets=plan['nets'];need(len(nets)==68 and len({n['net_id']for n in nets})==68,'electrical root catalogue incomplete')
    reset=[n for n in nets if n['asynchronous_reset_net']];normal=[n for n in nets if not n['asynchronous_reset_net']]
    need(len(reset)==17 and len(normal)==51 and sum(len(n['groups'])for n in normal)==198 and sum(len(n['groups'])for n in reset)==128,'electrical/reset classification does not reconcile')
    seen=set();targeted=set();ids=set()
    for net in nets:
        need(bool(net.get('reference')) and net['driver'].endswith(('/Z','/ZN','/Q','/QN')) and net['original_flattened_sink_count']>0,'missing exact original driver identity')
        need(1<=net['predicted_final_root_sink_count']<=16 and 1<=net['predicted_max_new_buffer_sink_count']<=16,'unbounded predicted electrical fanout')
        for group in net['groups']:
            names=group['loads'];kinds=group['load_kinds'];owner=group['owner'];cell=(owner+'/'if owner else'')+group['new_cell_name']
            need(group['id']not in ids and cell not in seen,'duplicate electrical cell/group');ids.add(group['id'])
            need(group['net_id']==net['net_id'] and group['driver']==net['driver'] and group['asynchronous_reset_net']==net['asynchronous_reset_net'],'group/root classification mismatch')
            need(group['max_loads']==16 and 1<=len(names)<=16 and len(names)==len(set(names))==len(kinds),'invalid bounded electrical group')
            need(all(x.rsplit('/',2)[0]==owner for x in names),'electrical plan crosses immediate hierarchy owners')
            need(group['expected_local_net']in group['allowed_local_net_aliases'],'missing allowed mapped local alias')
            need(re.fullmatch(r'XU_ECO_electrical_e\d{3}_g\d{3}',group['new_cell_name'])is not None,'unexpected electrical cell name')
            for name,kind in zip(names,kinds):
                need(kind in {'leaf','hier_input','new_buffer_input'},'unexpected electrical load kind')
                need(name not in targeted,'electrical pin selected twice');targeted.add(name)
                if kind=='new_buffer_input':need(name.rsplit('/',1)[0]in seen,'aggregation refers to uncreated buffer')
                if not net['asynchronous_reset_net']:need(name.rsplit('/',1)[-1]not in {'CK','CLK','EN','RDN','SDN'},'clock/reset pin in nonreset edit plan')
            seen.add(cell)
    probe=plan['probe_group'];n0=next(n for n in nets if n['net_id']=='e000')
    need(n0['original_flattened_sink_count']==213 and n0['predicted_final_root_sink_count']==14 and n0['reference']=='CLKBUFV2_12TR40' and n0['driver'].endswith('/u_core/U2548/Z'),'U2548 probe root differs')
    need(probe['net_id']=='e000' and probe['driver']==n0['driver'] and probe['asynchronous_reset_net'] is False and probe['new_cell_name']=='XU_ECO_electrical_probe4' and len(probe['loads'])==len(set(probe['loads']))==4 and set(probe['load_kinds'])=={'leaf'} and all(x.endswith('/A2')for x in probe['loads']),'first probe must be exactly four direct nonreset AO32 A2 loads')
    for net in nets:
        for key in ROOT_KEYS:need(key in net,'missing explicit root field: '+key)
    return plan

def emit(plan,action):
    validate_plan(plan)
    need(action in {'topology','probe','split','reload'},'unsupported electrical action')
    lines=['set ::eco_electrical_schema '+literal(plan['schema']),
        'set ::eco_electrical_origin_map_sha '+literal(plan['mapped_sha256']),
        'set ::eco_electrical_roots {}','set ::eco_electrical_groups {}']
    for row in plan['nets']:
        lines.append('lappend ::eco_electrical_roots [dict create '+' '.join(literal(k)+' '+literal(row[k])for k in ROOT_KEYS)+']')
    groups=[plan['probe_group']]if action=='probe'else [g for n in plan['nets']if not n['asynchronous_reset_net']for g in n['groups']]if action in {'split','reload'}else[]
    for row in groups:
        need(not row['asynchronous_reset_net'],'reset mutation is not authorized')
        lines.append('lappend ::eco_electrical_groups [dict create '+' '.join(literal(k)+' '+literal(row[k])for k in GROUP_KEYS)+']')
    return ('\n'.join(lines)+'\n').encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--electrical-plan-dir',type=Path,required=True);a=p.parse_args()
    source=Path(__file__).resolve().parent;plans=a.electrical_plan_dir.resolve()
    raw=(plans/'electrical-targets.json').read_bytes();topraw=(plans/'electrical-topology.json').read_bytes()
    plan=json.loads(raw);topology=json.loads(topraw)
    need(topology.get('mapped_sha256')==MAPPED_SHA and topology.get('census_sha256')==plan['census_sha256'],'topology and plan source identities differ')
    references={row['driver']:row['reference']for row in topology['nets']}
    for row in plan['nets']:row['reference']=references[row['driver']]
    plan['source_electrical_targets_sha256']=hashlib.sha256(raw).hexdigest();plan['source_electrical_topology_sha256']=hashlib.sha256(topraw).hexdigest()
    validate_plan(plan)
    origins={name:source/name for name in FILES}
    for name in ['run_electrical_stage.py','pt_electrical_edit.tcl','prepare_electrical.py']:origins[name]=source/name
    origins['development_controls.py']=source.parent/'run_once.py';origins['profiles.py']=source.parent/'profiles.py'
    for name,path in origins.items():
        text=path.read_text()
        if name.endswith('.py'):compile(text,name,'exec')
        if name.endswith('.tcl'):
            checked=subprocess.run(['tclsh'],input='set f [open {'+str(path)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True)
            need(checked.returncode==0,'Tcl incomplete: '+name)
    generated={action:hashlib.sha256(emit(plan,action)).hexdigest()for action in ['topology','probe','split','reload']}
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,path in origins.items():shutil.copyfile(path,a.out/name)
    (a.out/'electrical-targets.json.gz').write_bytes(gzip.compress(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()+b'\n',mtime=0))
    manifest={q.name:hashlib.sha256(q.read_bytes()).hexdigest()for q in sorted(a.out.iterdir())if q.is_file()}
    (a.out/'package-files.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':'SEALED_N3_ELECTRICAL_TOOLS_AND_STATIC_PLAN_NOT_NATIVE_EXECUTED','files':len(manifest),'nonreset_groups':198,'nonreset_nets':51,'reset_nets_visible_unresolved':17,'out':str(a.out),'package_sha256':hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest(),'generated_tcl_sha256':generated},sort_keys=True))

if __name__=='__main__':main()
