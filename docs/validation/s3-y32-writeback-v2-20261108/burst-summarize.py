from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
baseline=root.parent/'writeback-20261108/read-pop-full12'
candidate=root/'burst-full12'
b=json.loads((baseline/'result.json').read_text());c=json.loads((candidate/'result.json').read_text())
assert c['status']=='DEVELOPMENT_PASS_POLICY_PENDING', c['status']
assert len(c['task_results'])==len(b['task_results'])==12
assert c['configuration']['schedule']=='bias-hw-autogroup-y32-packed16-nice-drainn-read-pop-window'
assert c['clock_configuration']==b['clock_configuration']
assert c['startup_configuration']==b['startup_configuration']
assert c['simulator_evidence']==b['simulator_evidence']
assert all(s['native_exit']==0 and s['waitpid_completed'] for s in c['steps'])
allowed={'rtl/subsys/xu_nice_drain8.v','tests/e203/firmware/accel.c','tests/e203/tb_accel_soc.sv',
         'tools/scripts/xu_firmware_contract.py','tools/scripts/e203_soc.py'}
changed={p:(v,c['original_source_sha256'].get(p)) for p,v in b['original_source_sha256'].items() if c['original_source_sha256'].get(p)!=v}
assert set(changed)==allowed, changed
extra_generated_caches=sorted(set(c['original_source_sha256'])-set(b['original_source_sha256']))
assert not set(b['original_source_sha256'])-set(c['original_source_sha256'])
assert all('/__pycache__/' in p and p.endswith('.pyc') for p in extra_generated_caches), extra_generated_caches
items=[]
for x,y in zip(b['task_results'],c['task_results']):
    assert x['original_layer']==y['original_layer']
    assert x['clear']['clear_cycles']==y['clear']['clear_cycles']=='198403'
    assert x['window']['first_request_wait']==y['window']['first_request_wait']==0
    assert y['cycles']==542635
    n=y['nice_activity'];old=x['nice_activity']
    assert n=={**old,'requests':99,'responses':99,'oitf_retired':99}, (old,n)
    assert n['status_polls']==5049 and n['result_reads']==25344 and n['pops_retired']==3168 and n['shared_writes']==25344
    assert y['performance']['mac_fire']==202752
    assert y['performance']['mmio_writes']==12329
    assert y['performance']['shared_reads']==15040 and y['performance']['shared_writes']==25344
    assert y['performance']['starts']==3168 and y['performance']['dones']==3168
    saved=x['cycles']-y['cycles'];inclusive=x['cycles']+198403
    items.append(dict(layer=y['original_layer'],baseline_cycles=x['cycles'],candidate_cycles=y['cycles'],
        clear_cycles=198403,saved_cycles=saved,payload_reduction_pct=100*saved/x['cycles'],
        including_clear_reduction_pct=100*saved/inclusive))
summary=dict(status='DEVELOPMENT_PASS_POLICY_PENDING',scope='same-condition original 12 layers; 2-state Verilator, not official acceptance/STA/PPA',
             configuration=c['configuration'],tasks=items,changed_production_sources=changed,
             counts_per_task=c['task_results'][0]['nice_activity'],
             added_generated_python_caches=extra_generated_caches,
             evidence_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [baseline/'result.json',candidate/'result.json',candidate/'plan.json',root/'burst-unit/extended-result.json',root/'burst-legacy-task0/run.json']},
             limitations=['No VCS/vendor-SVA signoff: vcs executable unavailable.','No mapped area, STA, power, energy or official task-policy qualification.','No direct channel, polling-backoff, CPU-unroll or DMA changes combined.'])
(root/'burst-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
