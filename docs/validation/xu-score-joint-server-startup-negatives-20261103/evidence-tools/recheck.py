#!/usr/bin/env python3
"""xu exact actual-server failure subset review, never a simulation PASS."""
import hashlib,json,lzma
from pathlib import Path


def require(ok,message):
    if not ok:raise ValueError(message)


def unique(pairs):
    out={}
    for k,v in pairs:require(k not in out,'duplicate JSON key');out[k]=v
    return out


def read(p):return json.loads(p.read_text(),object_pairs_hook=unique)
def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    root=Path(__file__).resolve().parent.parent;rows=read(root/'manifest.json')['files']
    require(set(rows)=={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'},'archive membership differs')
    for name,row in rows.items():
        p=root/name;require(not p.is_symlink() and '..' not in Path(name).parts and not Path(name).is_absolute(),'unsafe archived input')
        data=p.read_bytes();require(len(data)==row['bytes'] and sha(data)==row['sha256'],'archive bytes differ: '+name)
    source={r['path']:r for r in read(root/'source-export33-manifest.json')};compressed={r['archived_path']:r for r in read(root/'compressed-originals.json')};raw={}
    prefixes=['vcs-joint-micro-saif-20261103-23','joint-activity-deploy-20261103-31','s2c-joint-activity-prepare-20261103-31']
    expected={n for n in source if any(n.startswith(pre+'/') for pre in prefixes)}
    for p in (root/'raw').rglob('*'):
        if not p.is_file():continue
        n=str(p.relative_to(root));data=p.read_bytes()
        if n in compressed:
            r=compressed[n];data=lzma.decompress(data);require(len(data)==r['bytes'] and sha(data)==r['sha256'],'lossless original mismatch');name=r['original_path']
        else:name=str(p.relative_to(root/'raw'))
        require(name not in raw,'duplicate original');raw[name]=data
        require(name in source and len(data)==source[name]['bytes'] and sha(data)==source[name]['sha256'],'source actual export subset mismatch')
    require(set(raw)==expected and len(raw)==23,'three complete actual failure groups differ')
    micro=json.loads(raw[prefixes[0]+'/state.json']);require(micro['status']=='FAIL' and micro['error']=='command failed: joint-build.log','actual micro terminal failure differs')
    steps=micro['steps'];require(len(steps)==5 and steps[-1]['returncode']==1 and all(r['returncode']==0 for r in steps[:-1]),'actual failed step ordering differs')
    cmd=steps[-1]['command'];require(cmd[0]=='gcc' and '-shared' in cmd and '-Werror' in cmd and '-Wstrict-prototypes' in cmd and '-I/eda/synopsys/vcs/vcs_2020.03-SP2-6/include' in cmd,'actual strict vendor-header compile command differs')
    require(not any('-full64' in r['command'] for r in steps),'unexpected VCS compile step')
    log=raw[prefixes[0]+'/joint-build.log'];require(b'vpi_user.h:1132:1:' in log and b'-Werror=strict-prototypes' in log,'actual vendor diagnostic differs')
    for record in micro['initial_input_identities']:
        name=Path(record['path']).name
        p=root/'evidence-tools'/name
        if p.exists():require(p.stat().st_size==record['bytes'] and sha(p.read_bytes())==record['sha256'],'actual micro source snapshot mismatch')
    deploy=json.loads(raw[prefixes[1]+'/state.json']);prepare=json.loads(raw[prefixes[2]+'/result.json'])
    require(deploy['status']==prepare['status']=='FAIL' and len(deploy['runs'])==1,'actual prepare failure lifecycle differs')
    run=deploy['runs'][0];cmd=run['command'];net=cmd[cmd.index('--netlist')+1]
    require(net.endswith('/s2c-ppa-campaign-20261103-01/ppa/mapped.v') and '/s2c/ppa/' not in net,'actual wrong-path trigger differs')
    require(prepare['error']=='joint input must be regular non-symlink file: '+net and run['returncode']==1 and prepare['tasks']==[] and prepare['taskset_complete'] is False,'actual wrong-path failure boundary differs')
    require(sha(raw[prefixes[2]+'/result.json'])==run['receipt_sha256'],'actual deploy/prepare result binding differs')
    print(json.dumps(dict(status='ACTUAL_FAILURES_PRESERVED_EXACT_NOT_VCS_CAPTURE_OR_ENERGY',files=len(rows),actual_raw_originals=len(raw),lossless_compressed=len(compressed)),sort_keys=True))

if __name__=='__main__':main()
