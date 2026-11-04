#!/usr/bin/env python3
"""Review native full-SoC FM50/57 proofs from the immutable shared archive."""
import argparse,hashlib,importlib.util,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def need(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def review(data):
    results=[]
    cases=[('full-soc-electrical-formality-20261104-54-50','9b7265e703ea62487c5b5c39c66adf245e720ac02f1066063cfd0eb4753f460c',176,[17136,0,0,0,144,24143,39,41462],508,'XU_FULL_SOC_FORMALITY_PASS'),('pe32-bank128-formality-20261104-57','7a69a1219561ca7a2e162ac84007f9fb32f34264132d1e6999e34c990cabe628',346,[22464,0,0,0,144,29687,39,52334],511,'XU_BANK128_FULL_SOC_FORMALITY_PASS_REVIEW_PENDING')]
    for name,mapped,n,passing,unread,marker in cases:
        state=json.loads(data[name+'/state.json']);log=data[name+'/fm.log'];text=log.decode();script=data[name+'/verify.tcl']
        need(state['status']=='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'and state['returncode']==0,'actual full FM status differs')
        need(state['frozen_before']==state['frozen_after']and len(state['frozen_before'])==n,'frozen FM inputs changed')
        need(state['target_netlist']['sha256']==mapped,'actual FM mapped identity differs')
        for field,body in [('log',log),('script',script)]:need(len(body)==state[field]['bytes']and sha(body)==state[field]['sha256'],'executed FM log/Tcl identity differs')
        need(text.splitlines().count('Verification SUCCEEDED')==text.splitlines().count(marker)==1,'native unique success lines missing')
        need(not re.search(r'^\s*(?:Error:|Error-|XU_\S*(?:FAIL|SCRIPT_ERROR))',text,re.M),'native FM error')
        row=re.findall(r'^Passing \(equivalent\)\s+(.*)$',text,re.M);need(len(row)==1 and list(map(int,row[0].split()))==passing,'native passing table differs')
        row=re.findall(r'^Failing \(not equivalent\)\s+(.*)$',text,re.M);need(len(row)==1 and set(map(int,row[0].split()))=={0},'native failing table differs')
        row=re.findall(r'^\s*Unread\s+(.*)$',text,re.M);need(len(row)==1 and list(map(int,row[0].split()))==[0,0,0,0,0,unread,0,unread],'native unread table differs')
        dbs=[r for p,r in state['frozen_before'].items()if p.endswith('.db')]
        expected={'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723','c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}
        if name.startswith('pe32'):
            expected.add('821c9344b787ecaae7ce222b9c5ab339b223759411dc20812f06210448a71bbe')
            need(state['defines']==['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_ACCEL_PE32=1','XU_ACCEL_PE32_BANK128=1'],'bank128 exact defines differ')
            need(state['reference_source_count']==164 and state['vendor128_read_by_formality']is False,'bank128 original reference boundary changed')
            need(len(state['svf_chain'])==1 and state['svf_chain'][0]['path'].endswith('/s3-pe32-bank128-ppa-campaign-20261103-01/ppa/default.svf'),'bank128 own original SVF chain differs')
        else:need(len(state['svf_chain'])==5,'50 full original SVF ancestry differs')
        need(len(dbs)==len(expected)and{r['sha256']for r in dbs}==expected,'actual exact technology DB identities differ')
        results.append(dict(experiment=name,passing=passing[-1],unread=unread,frozen_inputs=n,libraries=len(dbs),mapped_sha256=mapped,qualification='NOT_QUALIFIED'))
    return results
def main():
    p=argparse.ArgumentParser();p.add_argument('--source-export',type=Path);args=p.parse_args();selected=json.loads((ROOT/'selected-manifest.json').read_text())
    need(len(selected)==17 and len({r['path']for r in selected})==17,'selected native manifest differs')
    if args.source_export:data={r['path']:(args.source_export/r['path']).read_bytes()for r in selected}
    else:
        path=ROOT.parent/'xu-score-server-export69-20261104/check-evidence.py';spec=importlib.util.spec_from_file_location('shared69',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);data=m.verify([r['path']for r in selected])
    for r in selected:need(len(data[r['path']])==r['bytes']and sha(data[r['path']])==r['sha256'],'original selected byte identity differs')
    result=review(data)
    mutated=dict(data);key='pe32-bank128-formality-20261104-57/state.json';state=json.loads(mutated[key]);state['defines']=state['defines'][:-1];mutated[key]=(json.dumps(state)+'\n').encode()
    try:review(mutated)
    except ValueError:pass
    else:raise ValueError('missing bank128 define was accepted')
    print(json.dumps(dict(status='PASS',qualification='NOT_QUALIFIED',raw_files=17,raw_bytes=sum(r['bytes']for r in selected),proofs=result,negative_missing_bank_define='REJECTED'),sort_keys=True,indent=2))
if __name__=='__main__':main()
