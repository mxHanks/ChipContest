#!/usr/bin/env python3
"""Seal current N3 ECO tools and an explicit same-map clock segmentation plan."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from prepare import FILES
from clock_plan_bytes import emit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--clock-plan-dir',type=Path,required=True)
    a=p.parse_args()
    source=Path(__file__).resolve().parent
    origins={name:source/name for name in FILES}
    for name in ['run_clock_stage.py','pt_clock_probe.tcl','prepare_clock.py','clock_plan_bytes.py']:
        origins[name]=source/name
    origins['development_controls.py']=source.parent/'run_once.py'
    origins['profiles.py']=source.parent/'profiles.py'
    plans=a.clock_plan_dir.resolve()
    plan=json.loads((plans/'clock-tree-targets.json').read_text())
    if plan.get('schema')!='ingress1064-hierarchy-local-clock-tree-static-plan-v1' or plan.get('mapped_sha256')!='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e':
        raise ValueError('not the explicit original1064 fixed-map clock plan')
    for name,path in origins.items():
        raw=path.read_text()
        if name.endswith('.py'):compile(raw,name,'exec')
        if name.endswith('.tcl'):
            checked=subprocess.run(['tclsh'],input='set f [open {'+str(path)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True)
            if checked.returncode:raise ValueError('Tcl incomplete: '+name)
    for name,kind in [('clock-tree-probe.tcl','probe'),('clock-tree-full.tcl','full')]:
        path=plans/name
        if emit(plan,kind)!=path.read_bytes():raise ValueError('clock Tcl/JSON mismatch: '+name)
        checked=subprocess.run(['tclsh'],input='set f [open {'+str(path)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True)
        if checked.returncode:raise ValueError('Tcl incomplete: '+name)
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,path in origins.items():shutil.copyfile(path,a.out/name)
    for name in ['clock-tree-targets.json']:
        (a.out/(name+'.gz')).write_bytes(gzip.compress((plans/name).read_bytes(),mtime=0))
    manifest={q.name:hashlib.sha256(q.read_bytes()).hexdigest()for q in sorted(a.out.iterdir())if q.is_file()}
    (a.out/'package-files.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'SEALED_N3_CLOCK_TOOLS_AND_STATIC_PLAN_NOT_NATIVE_EXECUTED','files':len(manifest),'clock_groups':len(plan['groups']),'out':str(a.out),'package_sha256':hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest()},sort_keys=True))


if __name__=='__main__':main()
