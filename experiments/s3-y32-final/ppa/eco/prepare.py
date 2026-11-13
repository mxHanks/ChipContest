#!/usr/bin/env python3
"""Freeze exact final374 diagnosis/ECO tools; never access EDA or a server."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

FILES = ['common.tcl', 'dc_library_proof.tcl', 'pt_diagnose.tcl', 'pt_probe.tcl',
         'pt_edit.tcl', 'dc_apply.tcl', 'pt_reload.tcl', 'run_stage.py', 'plan.py',
         'check_buffer_equivalence.py', 'README.md', 'prepare.py']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    source = Path(__file__).resolve().parent
    origins = {name: source / name for name in FILES}
    origins['production_controls.py'] = source.parent / 'controls.py'
    for name, path in origins.items():
        text = path.read_text()
        if name.endswith('.py'):
            compile(text, name, 'exec')
        if name.endswith('.tcl'):
            checked = subprocess.run(['tclsh'], input='set f [open {' + str(path) + '} r]\n'
                'set s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n', text=True, capture_output=True)
            if checked.returncode:
                raise ValueError('Tcl incomplete: ' + name)
    a.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {}
    for name, origin in origins.items():
        shutil.copyfile(origin, a.out / name)
        manifest[name] = hashlib.sha256((a.out / name).read_bytes()).hexdigest()
    (a.out / 'package-files.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status='SEALED_FINAL374_TOOLS_NOT_NATIVE_EXECUTED', files=len(manifest),
        out=str(a.out), package_sha256=hashlib.sha256((a.out / 'package-files.json').read_bytes()).hexdigest()), sort_keys=True))


if __name__ == '__main__':
    main()
