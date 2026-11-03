#!/usr/bin/env python3
"""xu exact actual-VCS observed-field review; differences are not calibration PASS."""
import argparse,hashlib,importlib.util,json,re,shutil,tempfile
from pathlib import Path


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def unique(pairs):
    out={}
    for k,v in pairs:require(k not in out,'duplicate JSON field');out[k]=v
    return out

def read(p):return json.loads(p.read_text(),object_pairs_hook=unique)

def load(n,p):
    s=importlib.util.spec_from_file_location(n,str(p));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def observed(root,review):
    raw=root/'raw';result=review.review(raw);mode_summaries=[]
    for mode in result['modes']:
        rows=mode['actual_port_fields'];dwell=[p['pin'] for p in rows if any(any(r['vpi_minus_native']) for r in p['dwell_differences'])]
        tc=[p['pin'] for p in rows if any(p['observed_known_binary_transition_count']!=n['TC'] for n in p['native_fields'])]
        matches=[c for p in mode['probe_fields'].values() for c in p['native_and_joint_comparisons'] if 'joint_transition_matches' in c]
        require(len(matches)==34 and all(r['joint_dwell_matches'] and r['joint_transition_matches'] for r in matches),'independent actual-port probe/joint mismatch')
        require(all(p['delivered_end_matches'] and p['callback_current_difference_events']==0 for p in mode['probe_fields'].values()),'independent probe delivered/current or end-state mismatch')
        mode_summaries.append(dict(mode=mode['mode'],duration_ticks=mode['window']['duration_ticks'],actual_pin_bits=len(rows),different_dwell_pins=dwell,different_native_TC_vs_known_binary_pins=tc,independent_probe_matching_bits=len(matches),independent_probe_current_difference_events=0,independent_probes=8))
    require([len(r['different_dwell_pins']) for r in mode_summaries]==[3,0,0] and [len(r['different_native_TC_vs_known_binary_pins']) for r in mode_summaries]==[10,0,0],'actual counterexample counts changed')
    bypin={p['pin'].split('/')[-1]:p for p in result['modes'][0]['actual_port_fields']}
    examples={}
    for pin,expected in [('D[2]',(6,4,0)),('D[3]',(5,3,0)),('CLK',(514,513,1)),('CEN',(6,5,1))]:
        row=bypin[pin];require(len(row['native_fields'])==1,'actual micro native record count differs');native=row['native_fields'][0]
        value=(row['observed_known_binary_transition_count'],native['TC'],native['IG']);require(value==expected,'actual same-timestamp counterexample differs: '+pin)
        examples[pin]=dict(vpi_known_binary_edges=value[0],native_TC=value[1],native_IG=value[2])
    a=review.load('xu_micro34_correlation_audit',root/'evidence-tools/tools/ppa/xu_joint_activity/xu_sram_joint_audit.py');correlation=[]
    condition='RET1N & !CEN & GWEN & !EMA[2] & !EMA[1] & !EMA[0]'
    for i in [1,2]:
        d=raw/('mode-%d'%i);joint=a.audit(d/'joint.stats.jsonl',d/'joint.simultaneous.jsonl');macro=joint['macros'][0]
        arc=[r for r in macro['arcs'] if r['toggling_pin']=='CLK' and r['when']==condition];require(len(arc)==1,'actual library condition missing')
        correlation.append(dict(mode=i,condition=condition,condition_dwell_false_true_unknown=arc[0]['condition_dwell_false_true_unknown'],CEN_dwell=macro['pin_dwell']['CEN'],GWEN_dwell=macro['pin_dwell']['GWEN']))
    require(correlation[0]['CEN_dwell']==correlation[1]['CEN_dwell']==[2000000,2000000,0,0] and correlation[0]['GWEN_dwell']==correlation[1]['GWEN_dwell']==[2000000,2000000,0,0],'actual equal-marginal fixture changed')
    require(correlation[0]['condition_dwell_false_true_unknown']==[4000000,0,0] and correlation[1]['condition_dwell_false_true_unknown']==[2000000,2000000,0],'actual distinct joint condition changed')
    return dict(status='ACTUAL_VCS_INDEPENDENT_CALLBACK_PROBES_MATCH_JOINT_NATIVE_SAIF_DIFFERENCES_RETAINED_NOT_ENERGY_QUALIFIED',modes=mode_summaries,transition_counterexamples=examples,equal_marginal_distinct_joint=correlation,unfinished_negative_retained=True),result


def normalize_paths(value,prefix):
    if isinstance(value,dict):return {k:normalize_paths(v,prefix) for k,v in value.items()}
    if isinstance(value,list):return [normalize_paths(v,prefix) for v in value]
    if isinstance(value,str) and value.startswith(str(prefix)+'/'):return '<actual-micro-raw>/'+value[len(str(prefix))+1:]
    return value


def check(root):
    manifest=read(root/'manifest.json')['files'];actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json' and '__pycache__' not in p.parts}
    require(set(manifest)==actual,'archive membership differs')
    for n,r in manifest.items():
        p=root/n;require(not p.is_symlink() and not Path(n).is_absolute() and '..' not in Path(n).parts,'unsafe archived input')
        require(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'archive bytes changed: '+n)
    require(sha(root/'source-export41-manifest.json')=='9bb8a55aaf3ab3079c285999edd801b5354123ae8869d6d2d532ec68d5904b60','actual export41 manifest identity differs')
    source={r['path']:r for r in read(root/'source-export41-manifest.json')};prefix='vcs-joint-micro-saif-20261103-34/'
    raw=root/'raw';names={str(p.relative_to(raw)) for p in raw.rglob('*') if p.is_file()}
    require(names=={n[len(prefix):] for n in source if n.startswith(prefix)} and len(names)==27,'all actual micro34 raw membership differs')
    for n in names:
        r=source[prefix+n];p=raw/n;require(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'actual raw differs from strict export41')
    state=read(raw/'state.json');require(all(r['returncode']==0 for r in state['steps']),'actual tool command failed')
    for r in state['initial_input_identities']:
        p=root/'evidence-tools'/Path(r['path']).name
        if p.is_file():require(p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'actual executed helper/C/TB input mismatch')
    gcc=[r for r in state['steps'] if r['command'][0]=='gcc' and '-shared' in r['command']]
    require(len(gcc)==2,'actual joint/probe C builds missing')
    for row in gcc:
        cmd=row['command'];require('-isystem' in cmd and '-Werror' in cmd and '-Wstrict-prototypes' in cmd and '-Wall' in cmd,'actual vendor header classification / own diagnostics differs')
    for r in state['outputs']:
        marker='/vcs-joint-micro-saif-20261103-34/';require(marker in r['path'],'actual output outside micro scope');p=raw/r['path'].split(marker,1)[1]
        require(p.is_file() and p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],'actual helper output identity differs')
    review=load('xu_portable_micro34_review',root/'evidence-tools/review_actual_micro34.py');metrics,result=observed(root,review)
    require(metrics==read(root/'summary.json')['observations'],'archived observation summary differs from raw recomputation')
    old=read(root/'field-review.json');origin=Path(read(root/'summary.json')['original_export_raw_directory'])
    require(normalize_paths(old,origin)==normalize_paths(result,raw),'full per-pin diagnostic differs from raw recomputation')
    return dict(status=metrics['status'],archive_files=len(manifest),actual_raw_files=27,complete_modes=3,independent_joint_probe_matching_bits_per_mode=34,native_dwell_different_bits=3,native_TC_vs_binary_different_bits=10)


def negative_checks(root):
    results=[]
    for name in ['native-D2-TC','probe-delivered','joint-direct-transitions','unfinished','input-freeze']:
        with tempfile.TemporaryDirectory(prefix='xu-micro34-negative-') as t:
            r=Path(t)/'case';shutil.copytree(str(root),str(r),ignore=shutil.ignore_patterns('__pycache__'));raw=r/'raw'
            if name=='native-D2-TC':
                p=raw/'mode-0/native.saif';s=p.read_text();pattern=r'(\(D\\\[2\\\]\s+\(T0\s+\d+\)\s+\(T1\s+\d+\)\s+\(TX\s+\d+\)\s+\(TC\s+)4(\))'
                matches=list(re.finditer(pattern,s));require(len(matches)==2,'negative native owner/actual targets differ');found=matches[-1];s=s[:found.start()]+found.group(1)+'6'+found.group(2)+s[found.end():];p.write_text(s)
            elif name=='probe-delivered':
                p=raw/'mode-0.log';s=p.read_text();pattern=r'(XU_PROBE_EVENT label=actual_D tick=525000000 ordinal=\d+ callback_bits_lsb=)0';s,n=re.subn(pattern,r'\g<1>1',s,count=1);require(n==1,'negative probe target missing');p.write_text(s)
            elif name=='joint-direct-transitions':
                p=raw/'mode-0/joint.stats.jsonl';lines=p.read_text().splitlines();x=json.loads(lines[1]);x['pin_transitions'][11][1]+=1;lines[1]=json.dumps(x);p.write_text('\n'.join(lines)+'\n')
            elif name=='unfinished':
                p=raw/'mode-3.log';p.write_text(p.read_text().replace('XU_JOINT_INCOMPLETE','XU_HIDDEN_INCOMPLETE'))
            else:
                p=raw/'state.json';x=read(p);x['input_identities_after'][0]['sha256']='0'*64;p.write_text(json.dumps(x))
            # Deliberately bypass archive hashes to test the field/integer engine,
            # separately from the mandatory immutable-origin check above.
            try:observed(r,load('xu_micro34_negative_review_'+name,r/'evidence-tools/review_actual_micro34.py'))
            except (ValueError,KeyError,AssertionError) as error:results.append(dict(case=name,rejected=True,reason=str(error)))
            else:raise ValueError('semantic negative accepted: '+name)
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent);p.add_argument('--self-test',action='store_true');a=p.parse_args();result=check(a.root)
    if a.self_test:result['field_engine_negative_cases']=negative_checks(a.root)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()
