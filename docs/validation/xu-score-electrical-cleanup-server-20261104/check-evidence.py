#!/usr/bin/env python3
"""Replay immutable actual60 electrical/FM evidence without EDA tools."""
import argparse
import csv
import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parent
def need(ok, message):
    if not ok:
        raise ValueError(message)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--source-export',type=Path);args=p.parse_args()
    m=json.loads((ROOT/'manifest.json').read_text());data={}
    for r in m['files']:
        path=PurePosixPath(r['path']);need(not path.is_absolute() and '..'not in path.parts,'unsafe path')
        need(r['path']not in data,'duplicate original path')
        stored=(ROOT/r['stored']).read_bytes();need(len(stored)==r['stored_bytes']and sha(stored)==r['stored_sha256'],'stored identity differs')
        raw=lzma.decompress(stored);need(len(raw)==r['bytes']and sha(raw)==r['sha256'],'expanded original identity differs')
        if args.source_export:need((args.source_export/r['path']).read_bytes()==raw,'actual export bytes differ')
        data[r['path']]=raw
    need(len(data)==44,'actual selected payload count differs')
    def raw(pre,name):return data[pre+'/'+name]
    def js(pre,name='state.json'):return json.loads(raw(pre,name))
    cleanup='full-soc-unloaded-cell-cleanup-20261103-50'
    fm='full-soc-electrical-formality-20261104-54-49'
    failed='full-soc-reset-buffer-20261104-55-from50-n4'
    state=js(cleanup);need(state['status']=='EXECUTED_NOT_QUALIFIED','cleanup status differs')
    need(state['mapped_netlist_sha256']=='9b7265e703ea62487c5b5c39c66adf245e720ac02f1066063cfd0eb4753f460c','cleanup netlist differs')
    for kind in ('reports','audits'):
        for name,r in state[kind].items():
            body=raw(cleanup,name);need(len(body)==r['bytes']and sha(body)==r['sha256'],'cleanup report/audit receipt differs')
    for label,r in zip(('dc','pt'),state['runs']):
        need(r['returncode']==0 and r['errors']==[] and r['marker_count']==1,'cleanup execution failed')
        need(sha(raw(cleanup,label+'.log'))==r['log_sha256'],'cleanup log receipt differs')
    csv.field_size_limit(16000000)
    def rows(name):return list(csv.DictReader(io.StringIO(raw(cleanup,name).decode()),delimiter='\t'))
    preflight=rows('removal-preflight.tsv');removed=rows('removed-cells.tsv');upstream=rows('post-cleanup-upstream.tsv')
    need(len(preflight)==len(removed)==1404,'cleanup removed count differs')
    need(len({r['cell']for r in preflight})==1404 and all(r['output']==r['leaf_connections']and r['parent_ref_instance_count']=='1'for r in preflight),'actual removal topology differs')
    need({r['cell']for r in preflight}=={r['cell']for r in removed}and all(r['removed']=='1'for r in removed),'actual removed cell membership differs')
    # The exact native TSV and SHA govern topology; do not infer absence of
    # hierarchical ports from an all_connected -leaf query.
    constraints=raw(cleanup,'constraints.rpt').decode()
    minpins=re.findall(r'^    Pin: (\S+)\n\n    Capacitance[^\n]*\n  - min_capacitance',constraints,re.M)
    need(len(minpins)==len(set(minpins))==187 and constraints.count('max_capacitance')==0,'final actual cap counts differ')
    need(len(upstream)==len({r['driver']for r in upstream})==1059,'actual upstream driver count differs')
    dangling={r['driver']for r in upstream if r['source_only']=='1'}
    need(dangling==set(minpins)and all(r['driver']==r['leaf_connections']for r in upstream if r['source_only']=='1'),'new dangling and actual min-cap sets differ')
    need(constraints.count('slack (VIOLATED)')==5,'actual removal violation count differs')
    coverage=raw(cleanup,'analysis-coverage.rpt').decode()
    match=re.search(r'^All Checks\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)',coverage,re.M)
    need(match and tuple(map(int,match.groups()))==(294473,267344,5,27124),'actual coverage differs')
    f=js(fm);need(f['status']=='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'and f['returncode']==0,'actual49 FM incomplete')
    need(f['frozen_before']==f['frozen_after']and len(f['frozen_before'])==169,'FM frozen inputs changed')
    need(f['target_netlist']['sha256']=='5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c','FM target differs')
    for field,name in [('log','fm.log'),('script','verify.tcl')]:
        body=raw(fm,name);need(len(body)==f[field]['bytes']and sha(body)==f[field]['sha256'],'FM executed artifact differs')
    log=raw(fm,'fm.log').decode();lines=log.splitlines()
    need(lines.count('Verification SUCCEEDED')==lines.count('XU_FULL_SOC_FORMALITY_PASS')==1,'actual FM unique success lines missing')
    need(re.search(r'^ 41462 Passing compare points$',log,re.M)and re.search(r'^Passing \(equivalent\)\s+17136\s+0\s+0\s+0\s+144\s+24143\s+39\s+41462$',log,re.M),'native FM points differ')
    need(re.search(r'^Failing \(not equivalent\)\s+(?:0\s+){7}0$',log,re.M),'native failing table differs')
    failure=js(failed);need(failure['status']=='FAIL'and failure['error']=='dc failed','original55 failure rewritten')
    failure_log=raw(failed,'dc.log').decode()
    need("Attribute 'dont_use' does not exist"in failure_log and 'expected boolean value but got ""'in failure_log,'actual55 failure differs')
    print(json.dumps(dict(status='PASS',qualification='NOT_QUALIFIED',raw_files=len(data),raw_bytes=sum(map(len,data.values())),cleanup_removed_cells=1404,remaining_min_cap=187,remaining_max_cap=0,removal_violations=5,coverage=dict(total=294473,met=267344,violated=5,untested=27124),formal49_passing=41462,formal49_frozen_inputs=169,reset55_actual='FAIL_BEFORE_INSERTION'),sort_keys=True,indent=2))
if __name__=='__main__':main()
