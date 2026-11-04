#!/usr/bin/env python3
"""Check retained raw bytes and complete local screening; no EDA qualification."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/scripts'))
import e203_soc as soc

def need(ok,message):
    if not ok: raise ValueError(message)

manifest=json.loads((HERE/'manifest.json').read_text())
archive=(HERE/'raw.tar.xz').read_bytes()
need(hashlib.sha256(archive).hexdigest()==manifest['archive_sha256'],'archive SHA differs')
raw={}
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:xz') as tar:
    for member in tar:
        name=member.name
        need(member.isfile() and name not in raw and not name.startswith('/') and
             '..' not in Path(name).parts,'non-plain/duplicate/unsafe member')
        data=tar.extractfile(member).read()
        expected=manifest['records'].get(name)
        need(expected is not None and expected['bytes']==len(data) and
             expected['sha256']==hashlib.sha256(data).hexdigest(),'raw identity differs: '+name)
        raw[name]=data
need(set(raw)==set(manifest['records']) and len(raw)==manifest['files'] and
     sum(map(len,raw.values()))==manifest['bytes'],'incomplete raw manifest')
paired=json.loads(raw['paired-real12/result.json'])
control=json.loads(raw['control-real12-fresh-v3/result.json'])
summary=json.loads((HERE/'summary.json').read_text())
need(summary['chisel_changed'] is False and summary['generated_compute_sv_changed'] is False,'wrong change scope')
for field in summary['identical_measured_inputs']:
    need(paired[field]==control[field],'same measured inputs differ: '+field)
need(paired['main_commit']==summary['paired_main'] and control['main_commit']==summary['control_main'],
     'actual distinct local main identities were altered')
need(paired['main_commit']!=control['main_commit'],'this archive must retain its documented main metadata limitation')
rows=[]
for result,prefix in [(paired,'paired-real12'),(control,'control-real12-fresh-v3')]:
    need(result['status']=='PASS' and result['tasks']==12 and result['simulator']=='verilator' and
         result['mode']=='real' and result['outputs']==304128 and result['write_words']==608256,'incomplete real12')
    log=raw[prefix+'/simulation.log'].decode()
    layers=soc.check_log(log,12)
    perf=soc.check_performance(log,layers,result['firmware_schedule'])
    need([x['cycles'] for x in layers]==[x['cycles'] for x in result['layers']],'result cycles differ from raw log')
    need(perf==[x['performance'] for x in result['layers']],'performance records differ from raw log')
    need(soc.check_result_activity(log,layers,result['firmware_schedule'])==result['result_activity'],
         'result read record differs from raw log')
    need(result['firmware_opt']=='-O2' and result['firmware_experiment']=='both-unroll-no-masks','compiler profile differs')
for a,b,pa,ca in zip(paired['layers'],control['layers'],paired['result_activity'],control['result_activity']):
    need(pa['legacy_words']+pa['packed_words']==38016 and ca['legacy_words']+ca['packed_words']==50688,
         'wrong actual result MMIO work')
    rows.append(dict(layer=a['layer'],paired_cycles=a['cycles'],control_cycles=b['cycles'],delta_cycles=a['cycles']-b['cycles'],
                     paired_result_reads=38016,control_result_reads=50688))
with (HERE/'per-layer-comparison.csv').open() as stream:
    saved=[{k:int(v) for k,v in row.items()} for row in csv.DictReader(stream)]
need(saved==rows,'per-layer CSV differs')
need(sum(r['paired_cycles'] for r in rows)==summary['paired_cycles']==10827459,'paired total differs')
need(sum(r['control_cycles'] for r in rows)==summary['control_cycles']==12158052,'control total differs')
need(b'Ran 64 tests' in raw['host-v4.log'] and raw['host-v4.log'].rstrip().endswith(b'OK'),'host acceptance incomplete')
need(b'Ran 42 tests' in raw['numeric.log'] and raw['numeric.log'].rstrip().endswith(b'OK'),'numeric screening incomplete')
direct=raw['direct-paired-hi-v4/simulation.log'].decode()
need(len(re.findall(r'^XU_PAIRED_HI_WRAPPER_PASS real_rows=2 real_groups=64 real_lanes=512 real_paired_reads=256\b',direct,re.M))==1,
     'real compute direct marker missing')
mutants=json.loads(raw['rtl-mutants-v3/summary.json'])
need(mutants['status']=='PASS' and len(mutants['records'])==5,'mutation set incomplete')
for record in mutants['records']:
    base='rtl-mutants-v3/'+record['name']+'/'
    need(hashlib.sha256(raw[base+'accel_icb_slave.v']).hexdigest()==record['source_sha256'],'mutant source differs')
    need(hashlib.sha256(raw[base+'simulation.log']).hexdigest()==record['simulation_log_sha256'],'mutant log differs')
    need(record['compile_exit']==0,'compile failure is not a behavioral rejection')
    if record['name']=='original-positive-control':
        need(record['simulation_exit']==0,'positive control failed')
    else:
        need(record['simulation_exit']!=0 and b'FATAL:' in raw[base+'simulation.log'],'mutant was not rejected')
legacy=json.loads(raw['legacy-full-domain-v4/image-equality.json'])
need(legacy['status']=='PASS' and legacy['configurations']==len(legacy['records'])==192,'legacy domain incomplete')
configs=set()
for record in legacy['records']:
    cfg=record['configuration'];configs.add((cfg['schedule'],cfg['optimization'],cfg['experiment']))
    need(record['equal'] and len(record['images'])==2 and
         record['images'][0]['image']['sha256']==record['images'][1]['image']['sha256'],'legacy load image changed')
    name=cfg['schedule']+'-'+cfg['optimization'][1:]+'-'+cfg['experiment']
    for image in record['images']:
        body=raw['legacy-full-domain-v4/'+name+'/'+image['kind']+'/accel_soc.verilog']
        need(hashlib.sha256(body).hexdigest()==image['image']['sha256'],'legacy image body differs')
need(len(configs)==192,'duplicate legacy configurations')
print('XU_S2E_LOCAL_EVIDENCE_PASS files={} real12=2 legacy_images=384 mutants_rejected=4 scope=LOCAL_NOT_SERVER_QUALIFIED'.format(len(raw)))
