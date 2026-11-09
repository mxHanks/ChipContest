#!/usr/bin/env python3
"""Candidate-specific server synthesis runner, Python 3.6+; no credential access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def tcl(value):
    value = str(value)
    if any(x in value for x in ['{', '}', '\\', '\n', '\r']):
        raise ValueError('unsafe Tcl path')
    return '{'+value+'}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--standard-db', required=True)
    parser.add_argument('--standard-sha256', required=True)
    parser.add_argument('--sram-db', required=True)
    parser.add_argument('--sram-sha256', required=True)
    parser.add_argument('--dc-shell', default='dc_shell')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    os.chdir(str(root))
    receipt_path = root/'execution.json'
    if receipt_path.exists() or (root/'WORK').exists() or (root/'dc.log').exists():
        raise ValueError('refuse restart/overwrite of an existing synthesis experiment')
    manifest = json.loads((root/'package-files.json').read_text())
    for name, digest in manifest.items():
        if sha(root/name) != digest:
            raise ValueError('prepared input source drift: '+name)
    libraries = []
    for role, path, digest in [('standard_cell',args.standard_db,args.standard_sha256),('sram',args.sram_db,args.sram_sha256)]:
        library = Path(path).resolve()
        if not library.is_file() or sha(library)!=digest:
            raise ValueError('library identity mismatch: '+str(library))
        libraries.append(dict(role=role,path=str(library),sha256=digest))
    dc = shutil.which(args.dc_shell)
    if not dc:
        raise ValueError('dc_shell not found')
    dc = str(Path(dc).absolute())
    dc_resolved = str(Path(dc).resolve())
    (root/'libraries.tcl').write_text('set_app_var target_library [list '+tcl(libraries[0]['path'])+']\nset_app_var link_library [list * '+' '.join(tcl(x['path']) for x in libraries)+']\n')
    command = [dc,'-f','synth.tcl']
    receipt = dict(schema='xu-dma-server-synth-execution-v1',status='RUNNING',command=command,
       started_epoch=time.time(),tool=dict(path=dc,resolved_path=dc_resolved,sha256=sha(dc)),libraries=libraries,
       input_manifest_sha256=sha(root/'package-files.json'),qualification='NOT_QUALIFIED')
    receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    with (root/'dc.log').open('w') as log:
        process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        receipt['pid'] = process.pid
        receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        code = process.wait()
    drift = [name for name,digest in manifest.items() if not (root/name).is_file() or sha(root/name)!=digest]
    receipt.update(returncode=code,finished_epoch=time.time(),source_drift=drift,
       completion_marker=(root/'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt').is_file(),
       logfile_sha256=sha(root/'dc.log'))
    receipt['status'] = 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' if code==0 and receipt['completion_marker'] and not drift else 'FAILED'
    receipt['outputs'] = {p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in root.iterdir() if p.is_file() and p.name not in manifest and p.name not in ['execution.json']}
    receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(receipt['status'])
    return 0 if receipt['status']=='SYNTHESIS_COMPLETE_NOT_QUALIFIED' else 1

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr)
        sys.exit(1)
