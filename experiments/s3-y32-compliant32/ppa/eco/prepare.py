#!/usr/bin/env python3
"""Freeze an ECO tool package only. Does not launch EDA or access a server."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

FILES=['common.tcl','dc_library_proof.tcl','pt_probe.tcl','pt_edit.tcl','dc_apply.tcl','pt_reload.tcl','run_stage.py',
       'gate-anchors.txt','check_buffer_equivalence.py','README.md','prepare.py']

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    source=Path(__file__).resolve().parent
    for name in FILES:
        text=(source/name).read_text()
        if name.endswith('.py'): compile(text,name,'exec')
        if name.endswith('.tcl'):
            # Tcl's real parser verifies brace/quote completeness without
            # sourcing EDA commands or substituting any source text.
            checked=subprocess.run(['tclsh'],input='set f [open '+str(source/name)+' r]\nset text [read $f]\nclose $f\nif {![info complete $text]} {exit 2}\n',text=True,capture_output=True)
            if checked.returncode: raise ValueError('Tcl incomplete: '+name)
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    manifest={}
    for name in FILES:
        shutil.copyfile(source/name,a.out/name)
        manifest[name]=hashlib.sha256((a.out/name).read_bytes()).hexdigest()
    (a.out/'package-files.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status='SEALED_TOOLS_PREPARED_NOT_EXECUTED',files=len(manifest),out=str(a.out),
                         package_sha256=hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest()),sort_keys=True))

if __name__=='__main__': main()
