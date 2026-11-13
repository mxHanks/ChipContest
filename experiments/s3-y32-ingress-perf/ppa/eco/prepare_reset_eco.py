#!/usr/bin/env python3
"""Seal bounded17-net reset ECO candidate on an exact completed integrated seed.

No EDA/transport. Probe and split both load the fresh same seed. Representative
min/max plus complete coverage/DRC guards retain original unknown/no_clock;
external pulse/physical/RDC signoff remains unresolved, never timing PASS.
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
from prepare_reset import emit as reset_emit
from reset_eco_plan import build_static_plan,emit,validate

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--electrical-plan-dir',type=Path,required=True)
    p.add_argument('--reset-diagnostic-package',type=Path,required=True)
    p.add_argument('--source-map',type=Path,required=True);p.add_argument('--seed-mapped-sha256',required=True);p.add_argument('--required-margin',type=float,default=0.03)
    a=p.parse_args();source=Path(__file__).resolve().parent
    if len(a.seed_mapped_sha256)!=64 or any(x not in '0123456789abcdef'for x in a.seed_mapped_sha256):raise ValueError('exact seed mapped SHA256 required')
    plan=json.loads((a.electrical_plan_dir/'electrical-targets.json').read_text());top=json.loads((a.electrical_plan_dir/'electrical-topology.json').read_text());refs={n['id']:n['reference']for n in top['nets']}
    for row in plan['nets']:row['reference']=refs[row['net_id']]
    diag=json.loads(gzip.decompress((a.reset_diagnostic_package/'reset-diagnostic-plan.json.gz').read_bytes()))
    selected=build_static_plan(plan,diag,a.seed_mapped_sha256,a.required_margin,source_map=a.source_map);validate(selected)
    origins={name:source/name for name in FILES}
    for name in ['prepare_reset_eco.py','run_reset_eco_stage.py','pt_reset_eco.tcl','reset_eco_plan.py']:origins[name]=source/name
    # Freeze the reviewed reset seed parser/native helpers, including prune partition fixes.
    for name in ['prepare_reset.py','run_reset_stage.py','pt_reset_diagnose.tcl']:origins[name]=a.reset_diagnostic_package/name
    origins['development_controls.py']=source.parent/'run_once.py';origins['profiles.py']=source.parent/'profiles.py'
    for name,path in origins.items():
        raw=path.read_text()
        if name.endswith('.py'):compile(raw,name,'exec')
        if name.endswith('.tcl'):
            tested=subprocess.run(['tclsh'],input='set f [open {'+str(path)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True)
            if tested.returncode:raise ValueError('incomplete Tcl: '+name)
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,path in origins.items():shutil.copyfile(path,a.out/name)
    (a.out/'reset-eco-plan.json.gz').write_bytes(gzip.compress(json.dumps(selected,sort_keys=True,separators=(',',':')).encode()+b'\n',mtime=0))
    manifest={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in sorted(a.out.iterdir())if f.is_file()}
    (a.out/'package-files.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(status='SEALED_BOUNDED_RESET_ECO_NOT_NATIVE_EXECUTED',out=str(a.out),package_sha256=hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest(),roots=len(selected['roots']),groups=len(selected['groups']),representative_queries=len(selected['receivers']),seed_mapped_sha256=a.seed_mapped_sha256,generated_tcl_sha256={k:hashlib.sha256(emit(selected,k)).hexdigest()for k in ['probe','split','reload']},qualification='NOT_QUALIFIED',pulse_physical_signoff='UNRESOLVED'),sort_keys=True))

if __name__=='__main__':main()
