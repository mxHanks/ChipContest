#!/usr/bin/env python3
"""Admit the strict CPU64 campaign into the existing FPT candidate slot."""
import argparse
import fcntl
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shlex
import socket
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
BASE=Path('/work/leo/chipcontest-xu-own155-diagnosis-20261105')
OLD=BASE/'s3-hw-sw-strict-20261109-r1'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def pinned(name,path,digest):
    if sha(path)!=digest:
        raise ValueError('Native helper changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module


def inputs(digest):
    manifest=ROOT/'INPUT.sha256'
    if sha(manifest)!=digest:
        raise ValueError('Input manifest changed')
    pins={}
    for line in manifest.read_text().splitlines():
        expected,name=line.split('  ',1)
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or (ROOT/path).is_symlink() or sha(ROOT/path)!=expected:
            raise ValueError('Input changed: '+name)
        pins[name]=expected
    return pins


def main(digest):
    if socket.gethostname().split('.')[0]!='t7920' or pwd.getpwuid(os.getuid()).pw_name!='leo' or ROOT.parent!=BASE:
        raise ValueError('Wrong owner host or workspace')
    pins=inputs(digest)
    guard=pinned('native_guard',OLD/'native_guard.py','b9bbcc31accc4b031430e49aebfcb32776a0e797ff8c3fd09561b5bbfcb42f61')
    resources=pinned('full_resources',OLD/'full_resources.py','12cb009b978a9bf3e30ec9313fe246c77834c532f820d467895b188d17d2e1a6')
    helper=guard.load('strict_native_helper',guard.pinned(guard.HELPER,guard.HELPER_SHA))
    with os.fdopen(os.open(BASE/'.s3-own-native.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600),'r+') as slot:
        fcntl.flock(slot,fcntl.LOCK_EX|fcntl.LOCK_NB)
        out=ROOT/'native-r1'
        out.mkdir(mode=0o700)
        control=out/'control'
        control.mkdir()
        result=dict(status='RUNNING',input_checksum_sha256=digest,qualification='DEVELOPMENT_RTL_ONLY')
        guard.save(out/'result.json',result)
        try:
            for attempt in range(1,guard.ADMISSION_ATTEMPTS+1):
                cpus=resources.admission(helper,out,control,attempt)['selected_cores'][:3]
                if len(cpus)==3:
                    break
            if len(cpus)!=3:
                raise ValueError('No three idle unpinned physical cores')
            args=[guard.PYTHON,'-E','-B',str(ROOT/'run_strict.py'),'--sim-cpu',str(cpus[0])]
            command=['bash','-lc','module load openEDA/verilator/v5.046 gcc/v13.5.0 && export CCACHE_DISABLE=1 && exec '+shlex.join(args)]
            guard.save(control/'plan.json',dict(cpus=cpus,command=command,memory_limit_bytes=guard.MEMORY,
                nice=10,timeout_seconds=3600,input_pins=pins))
            print('CPU64_NATIVE_START',cpus,flush=True)
            child=helper.run_child(command,out,control,lambda:guard.bounded(cpus),3600,guard.MEMORY)
            result['child']=child
            if child['native_exit']!=0 or not child['waitpid_completed'] or child['events'] or child['remaining_group'] or child['remaining_at_leader_exit']:
                raise ValueError('Strict CPU64 child failed or did not drain')
            if child['log_sha256']!=sha(control/'native.log') or inputs(digest)!=pins:
                raise ValueError('Log or input drift')
            campaign=guard.read(out/'campaign/result.json')
            if campaign['status']!='PASS_STRICT_CPU64_FULL12':
                raise ValueError('Missing strict full12 terminal result')
            result.update(status='PASS',campaign_sha256=sha(out/'campaign/result.json'))
        except Exception as error:
            result.update(status='FAIL',error=str(error))
        guard.save(out/'result.json',result)
        print('CPU64_NATIVE_END',result['status'],result.get('error',''),flush=True)
        return result['status']!='PASS'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-sha256',required=True)
    raise SystemExit(main(parser.parse_args().input_sha256))
