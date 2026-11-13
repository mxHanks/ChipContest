#!/usr/bin/env python3
"""Seal read-only reset-receiver diagnostics; never authorize reset edits.

The 128 static reset groups remain candidates only. Native per-receiver max/min,
release spread and pulse contracts must exist before a separate edit tool can be
reviewed. Unknown values are retained and never substituted with zero.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
from prepare import FILES

MAPPED_SHA='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'
SCHEMA='ingress1064-reset-receiver-diagnostic-plan-v1'

def require(value,message):
    if not value:raise ValueError(message)

def literal(value):
    if isinstance(value,list):return '{'+' '.join(literal(x)for x in value)+'}'
    value=str(value);require(not any(c in value for c in '{}\\\r\n'),'unsafe reset diagnostic Tcl literal')
    return '{'+value+'}'

def validate(plan):
    require(plan.get('schema')==SCHEMA and plan.get('original_mapped_sha256')==MAPPED_SHA and
        plan.get('mutation_authorized') is False and plan.get('qualification') is False,'unsupported reset diagnostic plan')
    require(len(plan['roots'])==17 and len({r['net_id']for r in plan['roots']})==17 and
        sum(r['original_electrical_sink_count']for r in plan['roots'])==1478 and
        sum(r['unauthorized_static_group_count']for r in plan['roots'])==128,'reset root catalogue must be exact17nets/1478electricalsinks/128unauthorizedgroups')
    receivers=plan['receivers'];require(len(receivers)==1477 and len({r['pin']for r in receivers})==1477,'exact1477 actual async receiver catalogue required')
    rootids={r['net_id']for r in plan['roots']}
    for row in receivers:
        require(row['pin'].endswith(('/RDN','/SDN')) and row['reference'] and row['net_ids'] and set(row['net_ids'])<=rootids,'nonasync/unknown receiver in reset catalogue')
    return plan

def emit(plan):
    validate(plan)
    lines=['set ::reset_diagnostic_schema '+literal(plan['schema']),
        'set ::reset_origin_map_sha '+literal(plan['original_mapped_sha256']),
        'set ::reset_mutation_authorized 0','set ::reset_roots {}','set ::reset_receivers {}']
    for row in plan['roots']:
        lines.append('lappend ::reset_roots [dict create '+' '.join(literal(k)+' '+literal(row[k])for k in ['net_id','driver','reference','original_electrical_sink_count','unauthorized_static_group_count'])+']')
    for row in plan['receivers']:
        lines.append('lappend ::reset_receivers [dict create '+' '.join(literal(k)+' '+literal(row[k])for k in ['pin','reference','net_ids'])+']')
    return ('\n'.join(lines)+'\n').encode()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--electrical-plan-dir',type=Path,required=True);a=p.parse_args()
    source=Path(__file__).resolve().parent;directory=a.electrical_plan_dir.resolve()
    raw=(directory/'electrical-topology.json').read_bytes();pr=(directory/'electrical-targets.json').read_bytes()
    topology=json.loads(raw);electrical=json.loads(pr)
    require(topology['mapped_sha256']==electrical['mapped_sha256']==MAPPED_SHA and topology['census_sha256']==electrical['census_sha256'],'not the fixed original1064 reset source')
    groups={n['net_id']:len(n['groups'])for n in electrical['nets']if n['asynchronous_reset_net']}
    roots=[];receivers={};references={s['pin']:s['reference']for n in topology['nets']for s in n['sinks']}
    for net in topology['nets']:
        if not net['asynchronous_reset_net']:continue
        roots.append(dict(net_id=net['id'],driver=net['driver'],reference=net['reference'],original_electrical_sink_count=net['flattened_sink_count'],unauthorized_static_group_count=groups[net['id']]))
        for pin in net['downstream_async_sinks_via_unary_cells']:
            row=receivers.setdefault(pin,dict(pin=pin,reference=references[pin],net_ids=[]));row['net_ids'].append(net['id'])
    plan=dict(schema=SCHEMA,original_mapped_sha256=MAPPED_SHA,mutation_authorized=False,qualification=False,
        roots=roots,receivers=[receivers[k]for k in sorted(receivers)],source_topology_sha256=hashlib.sha256(raw).hexdigest(),source_targets_sha256=hashlib.sha256(pr).hexdigest(),
        excluded_scope='Different raw ERST AON/PMU5removal and AON2T8D unknownsetup endpoints are outside these17 distribution nets.',
        missing_evidence=['Exact current integrated-map native per-receiver recovery max and removal min for every queryable clock/edge context',
          'Before/after nonregressed recovery/removal margins and release arrival spread, both polarities',
          'Native pulse coverage and unresolved no_clock reasons; external assertion pulse and physical reset/RDC contract',
          'Separate guarded probe/edit tool plus own DC replay, retained seed SVFs, fresh PT and connectivity proof'])
    validate(plan)
    origins={name:source/name for name in FILES}
    for name in ['prepare_reset.py','run_reset_stage.py','pt_reset_diagnose.tcl']:origins[name]=source/name
    origins['development_controls.py']=source.parent/'run_once.py';origins['profiles.py']=source.parent/'profiles.py'
    for name,path in origins.items():
        data=path.read_text()
        if name.endswith('.py'):compile(data,name,'exec')
        if name.endswith('.tcl'):
            test=subprocess.run(['tclsh'],input='set f [open {'+str(path)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True)
            require(test.returncode==0,'incomplete Tcl: '+name)
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,path in origins.items():shutil.copyfile(path,a.out/name)
    (a.out/'reset-diagnostic-plan.json.gz').write_bytes(gzip.compress(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()+b'\n',mtime=0))
    manifest={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in sorted(a.out.iterdir())if f.is_file()}
    (a.out/'package-files.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(status='SEALED_RESET_DIAGNOSTICS_ONLY_NO_RESET_EDIT_AUTHORIZED',out=str(a.out),package_sha256=hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest(),native_plan_tcl_sha256=hashlib.sha256(emit(plan)).hexdigest(),roots=17,electrical_sinks=1478,async_receivers=1477,unauthorized_groups=128),sort_keys=True))

if __name__=='__main__':main()
