#!/usr/bin/env python3
"""xu read-only local checks of transferred first-task logs and actual micro SAIF."""
from pathlib import Path
import json,hashlib,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools/ppa'));import xu_soc_task_activity as collector
activity=collector.activity;alias=collector.sram_alias
S=HERE/'raw'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def need(ok,message):
 if not ok:raise ValueError(message)
m=load(S/'manifest.json');need(len(m)==24 and len(m)==len({x['path']for x in m}),'archive unique payload inventory')
for x in m:
 p=S/x['path'];need(p.is_file()and p.stat().st_size==x['bytes']and sha(p)==x['sha256'],'original bytes '+x['path'])
p=S/'task-activity-clear-alias-20261103-01';j=load(p/'task00/result.json');task=j['tasks'][0];out=load(HERE/'result.json')
need(j['status']=='PARTIAL_COLLECTED_REVIEW_PENDING'and j['requested_task_ids']==[0]and len(j['tasks'])==1 and not j['taskset_complete'],'one actual task only')
need(j['clear_task_before_window']is True and j['sram_pin_alias']is True,'clear + macro observer enabled')
need(j['configuration_sha256']==activity.canonical_hash(j['configuration'])==out['configuration_sha256'],'configuration binding')
log=p/'task00/task_00/simulation.log';need(sha(log)==task['boundary_log']['sha256'],'boundary log')
layer,window=collector.checked_log(log.read_text(),0,j['configuration']['firmware_configuration']['schedule'],True)
need(layer==task['layer']==out['layer']and window==task['activity_window']==out['window'],'formal clear/request/retired window')
need(window['duration_ticks']==9139040000000 and window['formal_elapsed_cycles']==1370856 and window['formal_inclusive_cycles']==1370857,'actual task duration')
cap=task['sram_pin_alias_capture'];receipt=load(p/'task00/task_00/task-normalization.json');need(cap['normalization']==receipt,'server normalization receipt')
need(receipt['macro_count']==336 and receipt['alias_bit_count']==22512 and receipt['alias_name_encoding_counts']=={'hierarchical':0,'vcs_generate_net_atom':22512},'complete macro alias inventory')
need(receipt['raw_saif']==out['raw_saif']and receipt['normalized_saif']==out['normalized_saif'],'reported remote SAIF identities')
mapfile=p/'task00/simulator/sram-pin-alias/xu_sram_activity_alias.mapping.json';mapping=load(mapfile)
need(sha(mapfile)==receipt['mapping']['sha256']and len(mapping['macros'])==336 and sum(mapping['pin_widths'].values())==67,'observer mapping')
observer=p/'task00/simulator/sram-pin-alias/xu_sram_activity_alias.sv';need(sha(observer)==receipt['observer_source']['sha256'],'actual compiled observer')
need(sha(Path(collector.__file__))==j['runner']['sha256']and sha(Path(alias.__file__))==receipt['generator']['sha256'],'unchanged local collector and normalizer')
remote_root=j['configuration']['sram_pin_alias']['mapping']['root'];checked=0
for origin,expected in j['configuration']['rtl_sources_sha256'].items():
 if origin.startswith(remote_root+'/'):
  relative=origin[len(remote_root)+1:];local=ROOT/relative
  if local.is_file():need(sha(local)==expected,'captured source '+relative);checked+=1
need(checked>140,'captured source coverage')
saif=task['saif'];need({k:v['observed_count']for k,v in saif['macro_inventory'].items()}=={'shared':256,'itcm':32,'dtcm':32,'accelerator_weights':16},'physical macro groups')
d=saif['scope_presence']['dtcm'];need(d['state']=='OBSERVED_KNOWN_STATIC_DISABLED'and len(d['idle_control_evidence'])==96 and d['unknown_bit_ticks']>0,'disabled DTCM evidence, unknown retained')
for bit in d['idle_control_evidence']:
 pin=bit['path'].rsplit('/',1)[1];need(pin in ['CEN','CLK','RET1N']and bit['TC']==0 and bit['TX']==0 and bit['T1'if pin in ['CEN','RET1N']else'T0']==window['duration_ticks'],'measured DTCM control')
# Independent hand-count check of actually transferred raw + normalized VCS micro SAIF.
M=S/'saif-bind-probe-04';raw=activity.read_saif(M/'task.saif');norm=activity.read_saif(M/'normalized.saif');mr=load(S/'saif-bind-hand-review-20261103-02/result.json')
need(raw['duration_ticks']==norm['duration_ticks']==40000000 and raw['timescale_seconds']==norm['timescale_seconds']=='1E-15','40ns micro window')
rawpins={x['path'].split('macro_0000.',1)[1]:x for x in raw['signals']if'macro_0000.'in x['path']};pins={x['path'].rsplit('/',1)[1]:x for x in norm['signals']if x['path'].startswith('tb_xu_cell/dut/macro/')};need(len(rawpins)==len(pins)==67,'all micro pins')
widths={'CLK':1,'CEN':1,'WEN':16,'A':10,'D':16,'EMA':3,'EMAW':2,'GWEN':1,'RET1N':1,'Q':16};values={'CEN':0,'WEN':0,'A':0,'D':0x55aa,'EMA':2,'EMAW':0,'GWEN':1,'RET1N':1,'Q':0x55aa}
for pin,width in widths.items():
 for b in range(width):
  name=pin if width==1 else pin+'['+str(b)+']';measured=pins[name]
  if pin=='CLK':expected={'T0':20000000,'T1':20000000,'TX':0,'TC':8,'IG':0}
  else:
   dwell=36990000 if pin=='Q'else 40000000;high=(values[pin]>>b)&1;expected={'T0':0 if high else dwell,'T1':dwell if high else 0,'TX':3010000 if pin=='Q'else 0,'TC':0,'IG':0}
  need({k:v for k,v in measured.items()if k not in ['path','kind']}==expected,'micro expected state '+name)
  need(alias.equivalent(rawpins[name],measured),'micro raw alias preservation '+name)
need(mr['status']=='VERIFIED_67_PIN_HAND_EXPECTATIONS_REVIEW_PENDING'and mr['raw_sha256']==sha(M/'task.saif')and mr['normalized_sha256']==sha(M/'normalized.saif'),'actual micro receipt')
need(out['official_energy_or_score_computed']is False and out['full_task_saif_bytes_retrieved']is False,'qualification boundary')
print('PASS xu 24 raw payload hashes; %d captured source bytes; first-task formal log; 336 macro declarations; 96 DTCM control records; actual67pin micro unknown-aware SAIF; full task SAIF remains remote'%checked)
