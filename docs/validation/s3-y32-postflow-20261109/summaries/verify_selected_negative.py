#!/usr/bin/env python3
"""Record deliberate rejection checks against the final full12 loaded evidence.
Never rewrites a campaign or starts a simulator; mutations stay in Python values.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('selected_postflow_verifier',HERE/'postflow_compare.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
basepath=ROOT/'build/writeback-v2-20261108/direct-full12/result.json'
candpath=HERE/'selected-full12/result.json'
pins=v.read_json(HERE/'baseline8-full12-sourcepins.json')
pairs=v.read_json(HERE/'selected-full12-sourcepairs.json')
cpins=v.pinned_candidate_sources(pins,pairs)
base=v.load_campaign(basepath,'direct-pe8',pins)
candidate=v.load_campaign(candpath,'stream32-pe8',cpins)
result=v.compare(base,candidate,pairs)
raw=v.read_json(candpath)
log=(candpath.parent/'task-00/simulation.log').read_text()
api=v.load_pinned_parser(candpath.parent,cpins)
receipt=[]

def rejected(name,callback):
    try:
        callback()
    except (ValueError,KeyError,TypeError,StopIteration) as exc:
        receipt.append(dict(name=name,status='EXPECTED_REJECTION',reason=str(exc)))
    else:
        raise AssertionError('Verifier accepted deliberately invalid evidence: '+name)


def changed_compare(name,mutate):
    value=copy.deepcopy(candidate)
    mutate(value)
    rejected(name,lambda:v.compare(base,value,pairs))

badpins=dict(cpins)
badpins['rtl/subsys/xu_nice_drain8.v']='0'*64
rejected('unreviewed_source_pin',lambda:v.load_campaign(candpath,'stream32-pe8',badpins))
rejected('wrong_physical_profile',lambda:v.load_campaign(candpath,'stream32-pe16',cpins))
rejected('wrong_instruction_profile',lambda:v.load_campaign(candpath,'batch16-pe8',cpins))
incomplete=dict(pairs)
incomplete.pop('rtl/subsys/xu_nice_drain8.v')
rejected('undeclared_nice_rtl_change',lambda:v.compare(base,candidate,incomplete))
changed_compare('extra_compile_macro',lambda x:next(s for s in x['conditions']['commands']
    if s['name']=='firmware-build')['command'].append('-DXU_NICE_DRAIN16=1'))
changed_compare('extra_runtime_selector',lambda x:next(s for s in x['conditions']['commands']
    if s['name']=='task-00/simulation')['command'].append('+NICE_BATCH16=1'))
changed_compare('missing_stream_selector',lambda x:next(s for s in x['conditions']['commands']
    if s['name']=='task-00/simulation')['command'].remove('+NICE_STREAM=1'))
changed_compare('changed_clock_configuration',lambda x:x['conditions']['clock_configuration'].update(profile='development'))
changed_compare('changed_physical_clear_recipe',lambda x:x['conditions']['clear_recipe_configuration'].update(reset='warm cache'))
changed_compare('changed_physical_clear_work',lambda x:x['rows'][0]['clear'].update(writes='32929'))
changed_compare('changed_tensor_identity',lambda x:x['rows'][0]['vectors'].update({'layer_00/x.mem':'0'*64}))
changed_compare('changed_startup_reset_semantics',lambda x:x['rows'][0]['startup_observations'][1].update(held_ns='121.000000'))
changed_compare('changed_generated_clear_program',lambda x:x['generated_clear_c_identity'].update(normalized_sha256='0'*64))
changed_compare('elf_image_byte_mismatch',lambda x:x['firmware_loaded_elf']['load_segments'][0].update(bytes_sha256='0'*64))
changed_compare('reordered_result_layer',lambda x:x['rows'][0].update(original_layer=1))
marker=next(line for line in log.splitlines() if line.startswith('STREAM_TASK '))
for name,broken in [
    ('duplicate_stream_marker',log+'\n'+marker+'\n'),
    ('missing_stream_marker',log.replace(marker+'\n','')),
    ('completion_before_final_response',log.replace('final_response_before_completion=1','final_response_before_completion=0')),
    ('wrong_group_count',log.replace('groups=3168','groups=3167')),
    ('wrong_nice_request_count',log.replace('NICE_TASK layer=0 requests=99','NICE_TASK layer=0 requests=98'))]:
    rejected(name,lambda broken=broken:v.profile_markers(broken,raw['task_results'][0],v.STREAM_SCHEDULE,
                                                      v.PROFILES['stream32-pe8'],api))
output=dict(schema='s3-postflow-verifier-negative-receipt-v1',status='ALL_EXPECTED_REJECTIONS',
    scope='in-memory negative checks against revalidated final full12 evidence; no new simulation',
    verifier_sha256=hashlib.sha256((HERE/'postflow_compare.py').read_bytes()).hexdigest(),
    baseline_result_sha256=hashlib.sha256(basepath.read_bytes()).hexdigest(),
    candidate_result_sha256=hashlib.sha256(candpath.read_bytes()).hexdigest(),
    positive_result=dict(status=result['status'],layers=len(result['layers']),totals=result['totals']),
    rejected_cases=receipt,count=len(receipt))
with (HERE/'selected-verifier-negative-receipt.json').open('x') as stream:
    json.dump(output,stream,indent=2,sort_keys=True)
    stream.write('\n')
print('SELECTED_VERIFIER_NEGATIVE_PASS cases='+str(len(receipt)))
