#!/usr/bin/env python3
"""xu verify returned raw91 subset; omitted installed manuals retain identities."""
import argparse,csv,hashlib,io,json,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
SHA='92a994c6d401d582f94653a68f709fb9a4f41658286860997016db18d4fa8bd8'
def need(x,msg):
 if not x:raise ValueError(msg)
def sha(x):return hashlib.sha256(x).hexdigest()
def verify(extract=None):
 archive=ROOT/'payload.tar.xz';need(archive.stat().st_size==295708 and sha(archive.read_bytes())==SHA,'immutable derivative differs');manifest=json.loads((ROOT/'payload-manifest.json').read_text());expected={r['path']:r for r in manifest};original=json.loads((ROOT/'source-manifest.json').read_text());source={r['path']:r for r in original};omit=json.loads((ROOT/'source-omissions.json').read_text());need(len(expected)==len(manifest)==83 and sum(r['bytes']for r in manifest)==22295520 and len(source)==len(original)==112 and len(omit)==29,'source/subset dimensions differ')
 need(set(expected).isdisjoint({r['path']for r in omit})and set(expected)|{r['path']for r in omit}==set(source),'unaccounted original body');need(all(source[n]==r for n,r in expected.items())and all(source[r['path']]=={k:r[k]for k in ['path','bytes','sha256']}for r in omit),'source identity differs');found={}
 if extract:extract.mkdir(exist_ok=False)
 with tarfile.open(archive,'r|xz')as t:
  for m in t:
   p=PurePosixPath(m.name);need(m.isfile()and not p.is_absolute()and '..'not in p.parts and m.name not in found and m.size<64000000,'unsafe raw member');d=t.extractfile(m).read();need(dict(path=m.name,bytes=len(d),sha256=sha(d))==expected.get(m.name),'raw bytes differ');found[m.name]=d
   if extract:
    p=extract/m.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(d)
 need(set(found)==set(expected),'missing raw body')
 def obj(p):return json.loads(found[p])
 c='full-soc-unloaded-cell-cleanup-20261104-79/';state=obj(c+'state.json');need(state['status']=='EXECUTED_NOT_QUALIFIED'and state['candidate_count']==33 and state['mapped_netlist_sha256']=='5a1e30ca4c9f14a8eabb349575a9f3069038c15ec38577edeacf0c9613cfa048','actual79 identity differs')
 for label,run in zip(['dc','pt'],state['runs']):
  need(run['returncode']==0 and run['marker_count']==1 and run['errors']==[] and sha(found[c+label+'.log'])==run['log_sha256']and sha(found[c+('repair.tcl'if label=='dc'else'sta.tcl')])==run['script_sha256'],'actual79 execution differs')
 for n,r in dict(state['reports'],**state['audits']).items():need(len(found[c+n])==r['bytes']and sha(found[c+n])==r['sha256'],'actual79 audit/report differs')
 def rows(name):return list(csv.DictReader(io.StringIO(found[name].decode()),delimiter='\t'))
 preflight=rows(c+'removal-preflight.tsv');removed=rows(c+'removed-cells.tsv');upstream=rows(c+'post-cleanup-upstream.tsv');need(len(preflight)==len(removed)==33 and all(r['is_sequential']=='false'for r in preflight)and all(r['removed']=='1'for r in removed),'exact33 combinational removal differs');unloaded=[r for r in upstream if r['source_only']=='1'];need(len(upstream)==66 and len(unloaded)==20,'next20 source-only inventory differs');cap=found[c+'constraints.rpt'].decode().split('    Pin: ')[1:];need(len(cap)==20 and {x.splitlines()[0]for x in cap}=={r['driver']for r in unloaded},'actual20 min-cap pins differ');need(b'294473    267344' in found[c+'analysis-coverage.rpt']and b'27124' in found[c+'analysis-coverage.rpt'],'actual coverage differs')
 r='pmu-reset-clock-expansion-20261104-86/';s=obj(r+'state.json');need(s['status']=='EXECUTED_READ_ONLY_CLOCK_DIAGNOSTIC_NOT_QUALIFIED'and s['input_sha256_before']==s['input_sha256_after'],'actual86 read-only freeze differs');paths=rows(r+'paths.tsv');need(len(paths)==16 and len([x for x in paths if x['source_kind']=='HF_RESET'and x['check']=='recovery'and x['count']=='0'and x['status']=='NO_PATH_UNKNOWN'])==5 and len([x for x in paths if x['source_kind']=='LF_WATCHDOG'and x['check']=='recovery'and x['count']=='1'])==3,'actual86 five HF recovery gaps differ');need(len(s['runs'])==3 and [len(x['errors'])for x in s['runs']]==[0,0,2],'actual86 original errors not preserved')
 failure=obj('s2c-native-pin-stream-20261104-88/state.json');need(failure['status']=='FAIL'and failure['error']=='required native attributes missing: relative_toggle_rate'and failure['tasks']==[],'actual88 failure must remain failure')
 return dict(status='PASS',qualification='NOT_QUALIFIED',archive_sha256=SHA,source_payload_count=112,returned_payload_count=83,omitted_manual_bodies=29,cleanup79_removed=33,cleanup79_remaining_min_cap=20,cleanup79_reset_removal_violations=5,reset86_HF_recovery_no_path=5,reset86_LF_recovery_positive_controls=3,reset86_original_errors=2,pin_stream88_status='FAIL_PRESERVED')
def main():
 p=argparse.ArgumentParser();p.add_argument('--extract',type=Path);a=p.parse_args();print(json.dumps(verify(a.extract),sort_keys=True,indent=2))
if __name__=='__main__':main()
