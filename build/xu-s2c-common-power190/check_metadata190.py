#!/usr/bin/env python3
"""Local actual-original metadata join only; unreturned server bytes are MOCKED."""
from pathlib import Path
import importlib.util,unittest.mock as m
root=Path(__file__).resolve().parents[2]
s=root/'build/xu-score-resume-20261103';p=root/'build/xu-s2c-common-power190/power190.py';sp=importlib.util.spec_from_file_location('p190',p);api=importlib.util.module_from_spec(sp);sp.loader.exec_module(api)
B='/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
def local(path):
 p=Path(path)
 if str(path)=='/storage2/2026contest/server4/s4_23usr/Desktop/xu-s2c-common-power198/frozen-fm190.json':
  return root/'build/xu-s2c-common-power190/frozen-fm190.json'
 if str(path).startswith(B):
  tail=str(path)[len(B):]
  for d in ['next-results-export-69','current-evidence-export-09','terminal-results-export-22']:
   q=s/d/tail
   if q.is_file():return q
 return p
actual_read=api.read;actual_inventory=api.base.inventory_rows;actual_log=api.base.checked_native_log
refs=actual_read(p.parent/'references190.json');old=actual_read(s/'next-results-export-69/s2c-full-soc-power12-20261104-57/prepared.json')
rows={}
def add(v):
 if isinstance(v,dict):
  if 'path'in v and 'sha256'in v:rows[v['path']]=v
  for x in v.values():add(x)
 elif isinstance(v,list):
  for x in v:add(x)
add(refs);add(old)
fm=actual_read(s/'current-evidence-export-09/candidate-formality-campaign-20261103-01/state.json');add(fm)
def remember(records,path,expected=None):
 text=str(path);q=local(path)
 if q.is_file():
  actual=api.identity(q)
  if expected is not None:api.need(actual['sha256']==expected,'actual returned hash differs')
  r=dict(path=text,sha256=actual['sha256'],bytes=actual['bytes'])
 else:
  r=rows.get(text,dict(path=text,sha256=expected))
  api.need(expected is None or r['sha256']==expected,'declared hash differs')
 records[text]=r['sha256'];return r
with m.patch.object(api,'read',side_effect=lambda path:actual_read(local(path))),m.patch.object(api,'Path',side_effect=local),m.patch.object(api.base,'remember',side_effect=remember),m.patch.object(api.base,'inventory_rows',side_effect=lambda path:actual_inventory(local(path))),m.patch.object(api.base,'checked_native_log',side_effect=lambda path,mark,rc:actual_log(local(path),mark,rc)):
 result=api.source_context({});print('METADATA_JOIN_ONLY_UNRETURNED_HASHES_MOCKED own42338 source/map/area/context compatible')
