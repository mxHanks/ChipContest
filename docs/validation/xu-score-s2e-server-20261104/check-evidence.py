#!/usr/bin/env python3
"""Verify immutable full S2e server archive and exact same-RTL paired control."""
import argparse,csv,hashlib,importlib.util,io,json,tarfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
SHA='998b7e7622eda3e4e0934be395ed26f0a497d44a1af2c6a578eecb0b6a3deee9'
MAIN='5bf123bfead8f2a37f97f3234d4e40ce8201aae9';CHILD='a0767db69628ef30e53de2d1e93dd0360c0ccf76'
PREFIX='s2e-full-vcs-accept-20261104-74/'
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def verify(extract=None):
 p=ROOT/'payload.tar.xz';need(p.stat().st_size==5052380 and sha(p.read_bytes())==SHA,'raw archive differs');manifest=json.loads((ROOT/'original-manifest.json').read_bytes());expected={r['path']:r for r in manifest};need(len(manifest)==len(expected)==3752 and sum(r['bytes']for r in manifest)==29571463,'original manifest dimensions differ');found={};seen=set()
 if extract:extract.mkdir(exist_ok=False)
 with tarfile.open(p,'r|xz')as t:
  for m in t:
   q=PurePosixPath(m.name);need(m.isfile()and not q.is_absolute()and '..'not in q.parts and m.name not in seen and m.size<64000000,'unsafe raw member');seen.add(m.name);data=t.extractfile(m).read();need(len(data)==m.size,'raw member short')
   if m.name=='manifest.json':need(json.loads(data)==manifest,'inner original manifest differs')
   else:
    need(dict(path=m.name,bytes=len(data),sha256=sha(data))==expected.get(m.name),'raw payload SHA differs: '+m.name)
    if m.name.endswith(('.json','.csv','.log')):found[m.name]=data
   if extract:
    out=extract/m.name;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
 need(seen==set(expected)|{'manifest.json'},'missing raw payload')
 def obj(n):return json.loads(found[PREFIX+n])
 state=obj('state.json');a=obj('real12/result.json');b=obj('autogroup-control-real12/result.json')
 need(state['status']=='EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED'and state['expected_main']==MAIN and state['expected_e203']==CHILD,'wrong terminal source')
 need(len(state['frozen_before'])==271 and state['frozen_before']==state['frozen_after'],'271 runtime identities changed')
 need(obj('acceptance.json')['status']=='PASS','full acceptance missing');need(obj('baseline/result.json')['tests']==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],'legacy five VCS tests differ')
 legacy=obj('legacy-images/image-equality.json');need(legacy['status']=='PASS'and legacy['configurations']==192 and len(legacy['records'])==192 and all(r['equal']for r in legacy['records']),'192 actual old-image comparison missing')
 for r in [a,b]:
  need(r['status']=='PASS'and r['tasks']==12 and r['simulator']=='vcs'and r['main_commit']==MAIN and r['e203_commit']==CHILD,'complete same-source VCS real12 missing');need(r['outputs']==304128 and r['write_words']==608256 and [x['layer']for x in r['layers']]==list(range(12)),'canonical full work differs')
 for key in ['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture','simulator_sha256']:need(a[key]==b[key],'paired control identity differs: '+key)
 contract=ROOT/'tools/xu_firmware_contract.py';need(sha(contract.read_bytes())==a['contract_sha256'],'frozen production contract differs');sp=importlib.util.spec_from_file_location('xu_s2e_contract',contract);c=importlib.util.module_from_spec(sp);sp.loader.exec_module(c)
 for r in [a,b]:
  c.configuration_from_result(r);c.validate_result_activity(r['result_activity'],r['layers'],r['firmware_schedule'])
  for layer in r['layers']:c.validate_performance(layer['performance'],layer['cycles'],r['firmware_schedule'])
 need(a['firmware_schedule']==c.PAIRED_HI_SCHEDULE and b['firmware_schedule']=='bias-hw-autogroup-window','wrong schedule')
 rows=list(csv.DictReader(io.StringIO(found[PREFIX+'per-layer-comparison.csv'].decode())));need(len(rows)==12,'per-layer table incomplete')
 for i,row in enumerate(rows):need(row==dict(layer=str(i),paired_cycles='868345',control_cycles='986850',delta_cycles='-118505',paired_result_reads='38016',control_result_reads='50688'),'layer result differs')
 need((ROOT/'per-layer-comparison.csv').read_bytes()==found[PREFIX+'per-layer-comparison.csv'],'copied table differs');need(sum(x['cycles']for x in a['layers'])==state['paired_real12_cycles']==10420140 and sum(x['cycles']for x in b['layers'])==state['control_real12_cycles']==11842200 and state['delta_cycles']==-1422060,'complete actual cycle sum differs')
 omitted=json.loads(found['xu-s2e-server-full-export87/omitted-files.json']);need(omitted['count']==len(omitted['records'])==393,'explicit body omission count differs')
 return dict(status='PASS',qualification='DEVELOPMENT_VCS_ONLY_NOT_PPA_OR_ENERGY',archive_sha256=SHA,payload_count=3752,payload_bytes=29571463,omitted_bodies=393,runtime_identities=271,legacy_image_configurations=192,paired_cycles=10420140,control_cycles=11842200,delta_cycles=-1422060,chisel_changes='NONE_FOR_S2E')
def main():
 p=argparse.ArgumentParser();p.add_argument('--extract',type=Path);a=p.parse_args();print(json.dumps(verify(a.extract),sort_keys=True,indent=2))
if __name__=='__main__':main()
