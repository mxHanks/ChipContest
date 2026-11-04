#!/usr/bin/env python3
"""Verify actual61's successful DC edit and explicitly incomplete PT run."""
import argparse,collections,csv,hashlib,io,json,lzma,re
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
def need(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--source-export',type=Path);args=p.parse_args()
    m=json.loads((ROOT/'manifest.json').read_text());data={}
    for r in m['files']:
        path=PurePosixPath(r['path']);need(not path.is_absolute()and '..'not in path.parts and r['path']not in data,'unsafe/duplicate path')
        packed=(ROOT/r['stored']).read_bytes();need(len(packed)==r['stored_bytes']and sha(packed)==r['stored_sha256'],'stored identity differs')
        raw=lzma.decompress(packed);need(len(raw)==r['bytes']and sha(raw)==r['sha256'],'actual original bytes differ')
        if args.source_export:need((args.source_export/r['path']).read_bytes()==raw,'source export differs')
        data[r['path']]=raw
    need(len(data)==26,'actual61 selected payload count differs')
    prefix='full-soc-reset-buffer-20261104-61-from50-n4/'
    def raw(name):return data[prefix+name]
    def text(name):return raw(name).decode()
    s=json.loads(raw('state.json'));need(s['status']=='FAIL'and s['error']=='pt failed','original61 failure must be preserved')
    need(s['parent_stage']=='50'and s['pairs_per_sink']==4 and len(s['runs'])==2,'original61 experiment differs')
    dc,pt=s['runs'];need(dc['returncode']==0 and dc['marker_count']==1 and dc['errors']==[],'actual DC insertion did not pass')
    need(pt['returncode']==1 and pt['marker_count']==0 and pt['errors']==['XU_FATAL: reset recovery path missing; cannot claim analysis'],'actual PT failure changed')
    for label,r in zip(('dc','pt'),s['runs']):
        need(r['tool']==label+'_shell'and sha(raw(label+'.log'))==r['log_sha256'],'actual tool/log identity differs')
        need(sha(raw('repair.tcl'if label=='dc'else'sta.tcl'))==r['script_sha256'],'actual executed Tcl differs')
    producer=(ROOT/'tools/launch_reset_buffer61.py').read_bytes();producer_sha=sha(producer)
    need(producer_sha=='ce16e8e6f0e4cd1746a29c786b3cd3fccbb92713470ef5895420e5ab2a475339','actual producer differs')
    need(any(path.endswith('/launch_reset_buffer61.py')and digest==producer_sha for path,digest in s['input_sha256'].items()),'actual producer not bound to run')
    rows=list(csv.DictReader(io.StringIO(text('inserted-reset-cells.tsv')),delimiter='\t'))
    need(len(rows)==len({r['cell']for r in rows})==40,'native inserted cell count differs')
    need(set(collections.Counter(r['endpoint']for r in rows).values())=={8}and len({r['endpoint']for r in rows})==5,'exact five eight-cell branches required')
    need(all(r['ref']=='CLKINV0_12TR40'for r in rows),'inserted actual library reference differs')
    pre=list(csv.DictReader(io.StringIO(text('reset-library-preflight.tsv')),delimiter='\t'))
    need(len(pre)==1 and pre[0]['dc_dont_use_raw']==''and pre[0]['acceptance_basis']=='dc_absent_with_frozen_PT_palette_false_native_validation_required','native missing-attribute acceptance record differs')
    need(raw('reset-slack.tsv')==b'','incomplete per-sink report unexpectedly populated')
    c=text('analysis-coverage.rpt');match=re.search(r'^All Checks\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)',c,re.M)
    need(match and tuple(map(int,match.groups()))==(294473,267349,0,27124),'actual coverage differs')
    need(re.search(r'^removal\s+17597\s+17597\s+\(100%\)\s+0',c,re.M),'actual removal checks not all met')
    need(re.search(r'^recovery\s+17597\s+17595\s+\(100%\)\s+0\s+\(\s*0%\)\s+2',c,re.M),'actual two untested recovery checks changed')
    need(c.count('sdf_cond(ENABLE_NOT_D===1\'b1)')==2,'actual unknown recovery condition count differs')
    constraints=text('constraints.rpt');need(constraints.count('min_capacitance')==187 and constraints.count('max_capacitance')==0 and 'slack (VIOLATED)'not in constraints,'actual remaining constraints differ')
    slacks=re.findall(r'^\s+slack\s+\(MET\)\s+([-+0-9.Ee]+)$',text('hold.rpt'),re.M)
    need(slacks and slacks[0]=='0.00601495','actual worst reported min slack differs')
    print(json.dumps(dict(status='PASS',qualification='NOT_QUALIFIED',raw_files=26,raw_bytes=sum(map(len,data.values())),original_state='FAIL',dc_status='COMPLETE',inserted_cells=40,removal_checks_met=17597,recovery_checks_untested=2,all_checks=dict(total=294473,met=267349,violated=0,untested=27124),max_cap_violations=0,min_cap_violations=187,worst_reported_min_slack_ns='0.00601495'),sort_keys=True,indent=2))
if __name__=='__main__':main()
