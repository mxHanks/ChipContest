#!/usr/bin/env python3
"""Derive identical 150 MHz VCD events using buffered gzip writes; new output identity."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('raw',type=Path)
parser.add_argument('--simulation-log',required=True,type=Path)
parser.add_argument('--out',required=True,type=Path,help='new .vcd or .vcd.gz file')
parser.add_argument('--metadata',required=True,type=Path)
args=parser.parse_args()
if args.out.exists() or args.metadata.exists():raise ValueError('derived outputs must not exist')
markers={kind:[(int(layer),int(tick)) for layer,tick in re.findall(r'^ACTIVITY_'+kind+r' layer=(\d+) time=(\d+)$',args.simulation_log.read_text(),re.M)]
         for kind in ['BEGIN','END']}
if len(markers['BEGIN'])!=1 or len(markers['END'])!=1 or markers['BEGIN'][0][0]!=markers['END'][0][0]:
    raise ValueError('exactly one complete measured activity window is required')
begin,end=markers['BEGIN'][0][1],markers['END'][0][1]
raw_hash=hashlib.sha256()
unchanged_hash=hashlib.sha256()
derived_unchanged_hash=hashlib.sha256()
header=bytearray()
scopes=[]
timestamps=0
unchanged_lines=0
matched=set()
previous=-1
previous_scaled=-1
first,last=None,None
max_rounding_numerator=0
with args.raw.open('rb') as source,args.out.open('xb') as target:
    transformed=io.BufferedWriter(gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0),buffer_size=1024*1024) if args.out.name.endswith('.gz') else target
    try:
        for line in source:
            raw_hash.update(line)
            if len(header)<8192:header.extend(line[:8192-len(header)])
            if line.startswith(b'$scope '):scopes.append(line.decode('ascii').strip())
            if line.startswith(b'#'):
                original=int(line[1:].strip())
                scaled=(5*original+1)//3
                if original<previous or (original>previous and scaled<=previous_scaled):
                    raise ValueError('timestamp ordering would be lost')
                max_rounding_numerator=max(max_rounding_numerator,abs(3*scaled-5*original))
                if original in [begin,end]:matched.add(original)
                transformed.write(('#'+str(scaled)+'\n').encode('ascii'))
                previous,previous_scaled=original,scaled
                if first is None:first=original
                last=original
                timestamps+=1
            else:
                unchanged_hash.update(line)
                transformed.write(line)
                derived_unchanged_hash.update(line)
                unchanged_lines+=1
    finally:
        if transformed is not target:transformed.close()
if matched!={begin,end} or not begin<end:
    raise ValueError('ACTIVITY markers are not VCD ticks; do not infer an unverified time unit')
timescale=re.search(rb'\$timescale\s+(\d+)\s*(s|ms|us|ns|ps|fs)\s*\$end',bytes(header))
if timescale is None:raise ValueError('VCD timescale is missing')
number=int(timescale.group(1));unit=timescale.group(2).decode()
ns_per_tick=number*{'s':1e9,'ms':1e6,'us':1e3,'ns':1,'ps':1e-3,'fs':1e-6}[unit]
result=dict(schema='xu-derived-vcd-frequency-scale-v1',
    evidence_kind='derived timestamps only; raw activity preserved separately',
    raw=str(args.raw.resolve()),raw_sha256=raw_hash.hexdigest(),raw_bytes=args.raw.stat().st_size,
    derived=str(args.out.resolve()),derived_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest(),derived_bytes=args.out.stat().st_size,
    original_timescale=str(number)+unit,timescale_preserved=True,raw_clock_ns=4,derived_nominal_clock_ns=20/3,
    timestamp_rule='nearest integer tick to raw_tick * 5/3; ties cannot occur; (5*tick+1)//3',
    timestamp_lines=timestamps,non_timestamp_lines=unchanged_lines,
    unchanged_lines_sha256=unchanged_hash.hexdigest(),derived_unchanged_lines_sha256=derived_unchanged_hash.hexdigest(),
    max_rounding_error_ticks=max_rounding_numerator/3,event_lines_preserved=True,
    raw_first_tick=first,raw_last_tick=last,
    raw_window_ticks=[begin,end],raw_window_ns=[begin*ns_per_tick,end*ns_per_tick],
    derived_window_ticks=[(5*begin+1)//3,(5*end+1)//3],
    derived_window_ns=[((5*begin+1)//3)*ns_per_tick,((5*end+1)//3)*ns_per_tick],
    simulation_log=str(args.simulation_log.resolve()),simulation_log_sha256=hashlib.sha256(args.simulation_log.read_bytes()).hexdigest(),
    scope_declarations=scopes)
if max_rounding_numerator>1 or unchanged_hash.digest()!=derived_unchanged_hash.digest():
    raise ValueError('event preservation or <=0.5 tick error check failed')
with args.metadata.open('x') as stream:stream.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
print('DERIVED_VCD raw_sha256={} derived_sha256={} ticks={} max_error={} window_ns={}'.format(
    result['raw_sha256'],result['derived_sha256'],timestamps,result['max_rounding_error_ticks'],result['derived_window_ns']))
