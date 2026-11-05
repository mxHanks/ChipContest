#!/usr/bin/env python3
"""Read-only134 prerequisite/status inventory; never invokes licensed tools."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('xu134',str(HERE/'xu_s2e_timing134.py'))
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--full-preflight',action='store_true',help='rehash full actual own89/109/source/runtime context; no EDA or writes')
a=p.parse_args()
paths=[m.BASE/'s2e-ppa-campaign-20261104-89'/x for x in ['state.json','ppa/prepared.json','ppa/execution.json','ppa/mapped.v','ppa/default.svf','ppa/constraints.sdc','ppa/rtl.f','ppa/dc.log','formality/state.json','formality/verify.tcl','formality/fm.log']]
paths += [m.BASE/'s2e-own-formality-audit-20261104-109/state.json',Path.home()/'Desktop/xu-ts16.tcl',HERE/'reset134.tcl']
paths += [m.BASE/'ChipContest-s2e-activity-tools-109'/n for n in m.TOOLS]
paths += [Path(n) for n in m.BIN.values()]
missing=[];records={}
for path in paths:
    if path.is_file() and not path.is_symlink():records[str(path)]=dict(bytes=path.stat().st_size)
    else:missing.append(str(path))
prepared=m.BASE/'s2e-ppa-campaign-20261104-89/ppa/prepared.json'
if prepared.is_file():
    for row in m.read(prepared)['implementation']['libraries']:
        path=Path(row['path'])
        if path.is_file():records[str(path)]=m.ident(path)
        else:missing.append(str(path))
result=dict(schema='xu-s2e-readonly134-v1',qualification='NOT_QUALIFIED',missing=missing,available=records)
status=m.BASE/m.OUT/'state.json'
if status.is_file():result['existing134']=m.read(status)
if a.full_preflight:
    sys.argv=[str(HERE/'xu_s2e_timing134.py'),'--preflight-only']
    try:m.main();result['full_preflight']='PASSED_NOT_QUALIFIED'
    except BaseException as error:result['full_preflight']='REJECTED_NOT_QUALIFIED';result['error']=type(error).__name__+': '+str(error)
print(json.dumps(result,sort_keys=True,indent=2))
