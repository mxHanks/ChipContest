#!/usr/bin/env python3
"""Generate eight frozen direct-CLI registrations for persistent controller150."""
import argparse
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from context145 import require,write_json,sha,identity,vendor_model_records


def receipt_inputs(evidence_root,remote_root,candidate,planned):
    """Freeze returned original receipts and their complete original input set."""
    cid=candidate['id'];directory=evidence_root/cid;remote=remote_root/cid
    receipts={name:json.loads((directory/name).read_text()) for name in ('freeze.json','adopt-own-fm.json')}
    frozen,adopted=[receipts[k] for k in ('freeze.json','adopt-own-fm.json')]
    require(frozen.get('candidate')==cid and frozen.get('status')=='FROZEN_REVIEW_PENDING_NOT_QUALIFIED' and
            frozen.get('before')==frozen.get('after') and not frozen.get('errors'),'complete own138 freeze required: '+cid)
    require(adopted.get('status')=='OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING','ownFM138 adoption required: '+cid)
    require(frozen['source']['main_commit']==candidate['source']['main_commit'] and
            frozen['source']['child_commit']==candidate['source']['child_commit'],'original138 source commits differ: '+cid)
    require(frozen['selected_mapped']==adopted['selected_mapped']==planned['selected_mapped'] and
            frozen['ordered_svf_inputs']==adopted['ordered_svf_inputs']==planned['ordered_svf_inputs'],
            'original138 mapping/SVF chain differs: '+cid)
    require(len(frozen['after'])==len(planned['freeze_inputs']),'original138 input count differs: '+cid)
    for actual,expected in zip(frozen['after'],planned['freeze_inputs']):
        require(actual['path']==expected['path'] and actual['sha256']==expected['sha256'] and
                ('bytes' not in expected or actual['bytes']==expected['bytes']) and actual.get('symlink_target') is None,
                'original138 frozen input differs: '+cid)
    inputs=[dict(path=r['path'],sha256=r['sha256'],bytes=r['bytes']) for r in frozen['after']]
    for name in ('freeze.json','adopt-own-fm.json'):
        item=identity(directory/name);item['path']=str(remote/name);inputs.append(item)
    return inputs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle-root',type=Path,required=True,help='absolute deployed145 bundle path')
    p.add_argument('--output-root',type=Path,required=True,help='absolute parent of eight new activity directories')
    p.add_argument('--freeze-root',type=Path,required=True,help='138 queue root')
    p.add_argument('--freeze-evidence-root',type=Path,help='local returned138 receipts, if freeze-root is remote')
    p.add_argument('--vendor-model1024',type=Path,required=True);p.add_argument('--vendor-model128',type=Path,required=True)
    p.add_argument('--jobs-out',type=Path,required=True,help='new local directory; registers nothing')
    p.add_argument('--vectors',type=Path);p.add_argument('--after-job',default='baseline_rdc142')
    p.add_argument('--python',default='/bin/python3');p.add_argument('--vcs',default='vcs')
    p.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    a=p.parse_args()
    for path in (a.bundle_root,a.output_root,a.freeze_root,a.vendor_model1024,a.vendor_model128,a.vectors):
        require(path is None or path.is_absolute(),'absolute paths required')
    require(not a.jobs_out.exists(),'new jobs directory required')
    manifest=json.loads((HERE/'bundle-manifest145.json').read_text())
    inventory=json.loads((HERE/'inventory137.snapshot.json').read_text())
    queue=json.loads((HERE/'queue-plan138.snapshot.json').read_text())
    evidence_root=a.freeze_evidence_root or a.freeze_root
    models=vendor_model_records()
    frozen=[dict(path=str(a.bundle_root/r['path']),sha256=r['sha256'],bytes=r['bytes']) for r in manifest['files']]
    frozen.append(dict(path=str(a.bundle_root/'bundle-manifest145.json'),sha256=sha(HERE/'bundle-manifest145.json')))
    previous=a.after_job;plan=[];jobs=[]
    for candidate in inventory['candidates']:
        cid=candidate['id'];jobid='activity145_'+cid;out=a.output_root/cid;froot=a.freeze_root/cid
        argv=[a.python,'-B',str(a.bundle_root/'activity145.py'),'run','--profile',cid,'--source-root',candidate['source']['server_root'],
              '--freeze-receipt',str(froot/'freeze.json'),'--adoption-receipt',str(froot/'adopt-own-fm.json'),
              '--vendor-model1024',str(a.vendor_model1024),'--netlist',candidate['formal']['mapped']['path'],
              '--constraints',candidate['ppa']['analysis_sdc']['path'],'--out',str(out),'--vcs',a.vcs,'--cross-prefix',a.cross_prefix]
        if any(g['macro_ref']=='RAMSP128X16' for g in candidate['ppa']['memory_groups']):argv+=['--vendor-model128',str(a.vendor_model128)]
        if a.vectors:argv+=['--vectors',str(a.vectors)]
        deps=[dict(id='eight_freeze138',policy='success')]
        if previous:deps.append(dict(id=previous,policy='terminal'))
        planned=next(c for c in queue['candidates'] if c['id']==cid)
        inputs=list(frozen)+receipt_inputs(evidence_root,a.freeze_root,candidate,planned)
        for ref,path in [('RAMSP1024X16',a.vendor_model1024)]+(
                [('RAMSP128X16',a.vendor_model128)] if any(g['macro_ref']=='RAMSP128X16' for g in candidate['ppa']['memory_groups']) else []):
            item=dict(path=str(path),sha256=models[ref]['sha256'])
            if 'bytes' in models[ref]:item['bytes']=models[ref]['bytes']
            inputs.append(item)
        # Original records can already contain the selected model. Deduplicate
        # byte-identical paths and reject two expected hashes for one path.
        unique={}
        for item in inputs:
            if item['path'] in unique:
                old=unique[item['path']]
                require(old['sha256']==item['sha256'] and
                        ('bytes' not in old or 'bytes' not in item or old['bytes']==item['bytes']),
                        'conflicting queued frozen input: '+item['path'])
                if 'bytes' in item:old['bytes']=item['bytes']
            else:unique[item['path']]=dict(item)
        job=dict(schema='xu-experiment-control150-job-v1',qualification='NOT_QUALIFIED',id=jobid,kind='launch',native=True,
                 launch_mode='direct',dependencies=deps,process_contains=str(out),result_state=str(out/'result.json'),
                 output_root=str(out),success_statuses=['COLLECTED_12_REVIEW_PENDING_NOT_QUALIFIED'],
                 failure_statuses=['FAIL_REVIEW_REQUIRED_NOT_QUALIFIED'],argv=argv,frozen_inputs=[unique[k] for k in sorted(unique)])
        jobs.append(job);plan.append(dict(profile=cid,job_id=jobid,result_state=job['result_state'],argv=argv))
        previous=jobid
    require(len(jobs)==8 and len({j['process_contains'] for j in jobs})==8,'eight independent process identities required')
    a.jobs_out.mkdir(parents=True)
    for job in jobs:write_json(a.jobs_out/(job['id']+'.json'),job)
    write_json(a.jobs_out/'activity-plan145.json',dict(schema='xu-activity-plan145-v1',status='GENERATED_NOT_REGISTERED_NOT_QUALIFIED',
               candidate_count=8,native_cap=1,original_tasks_per_candidate=12,jobs=plan))
    print('GENERATED_8_JOBS_NOT_REGISTERED '+str(a.jobs_out))


if __name__=='__main__':main()
