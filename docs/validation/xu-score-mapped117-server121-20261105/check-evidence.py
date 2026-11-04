#!/usr/bin/env python3
"""Rehash actual117 and reparse raw native events; no EDA or remote execution."""
from pathlib import Path
import hashlib,json,re
B=Path(__file__).resolve().parent
def need(ok,m):
 if not ok:raise ValueError(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads((B/p).read_text())
m=load('manifest.json');rows=m['files'];names={r['path']for r in rows}
need(len(names)==len(rows),'duplicate archived identity')
need(names=={str(p.relative_to(B))for p in B.rglob('*')if p.is_file()and p.name!='manifest.json'},'archive membership differs')
for row in rows:
 p=B/row['path'];need(p.stat().st_size==row['bytes']and sha(p)==row['sha256'],'raw bytes changed: '+row['path'])
export={r['path']:r for r in load('source-export121-manifest.json')}
for p in(B/'raw').rglob('*'):
 if p.is_file():
  row=export[str(p.relative_to(B/'raw'))];need(row['sha256']==sha(p)and row['bytes']==p.stat().st_size,'actual117 differs from121 export')
P='raw/mapped-causal-native-20261105-117/';s=load(P+'state.json');r=load(P+'passive-event-review.json');log=(B/P/'causal-simulation.log').read_text()
status='NATIVE117_PASSIVE_EVENTS_COLLECTED_NOT_FUNCTIONAL_OR_TIMING_OR_ENERGY_QUALIFIED'
need(s['status']==r['status']==status and s['qualification']==r['qualification']=='NOT_QUALIFIED','actual117 scope changed')
need(s['inputs_equal_before_after']and not s['identity_errors']and s['inputs_before']==s['inputs_after']and len(s['inputs_before'])==636,'actual117636 frozen input records differ')
need(s['original_compilation_preserved_except_outputs_and_passive_vpi']and s['native_simulation_returncode']==0,'original compilation/native outcome differs')
for row in s['steps']:
 p=B/P/(row['name']+'.log');need(row['status']=='EXITED'and row['returncode']==0 and row['log']['sha256']==sha(p),'native step failed or log changed')
events=[]
for q in re.finditer(r'^XU_CAUSAL117_EVENT serial=(\d+) tick_fs=(\d+) reason=(\S+) role=(\S+) bits=(\d+) aval=([0-9a-f]+) bval=([0-9a-f]+) name=(\S+)$',log,re.M):
 events.append(dict(serial=int(q[1]),tick_fs=int(q[2]),reason=q[3],role=q[4],bits=int(q[5]),aval=q[6],bval=q[7],name=q[8]))
need(events==r['events']and len(events)==453 and [e['serial']for e in events]==list(range(1,454)),'raw453 event records differ')
need(sum(e['reason']=='value_change'for e in events)==336 and sum(e['reason']=='end_snapshot'for e in events)==117,'native event/snapshot counts differ')
need('observed_nodes=117 failed=0'in log and 'events_in_slice=336 observed_nodes=117 failed=0'in log,'native targets were not bound')
need(len(re.findall(r'^Fatal:',log,re.M))==1 and 'at time 9359423333333 fs\nXU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake\n'in log and log.count('Timing violation in')==25,'native111 failure/timing facts differ')
need(all(x not in log for x in ['SOC_PASS','XU_MAPPED111_SOURCE_REQUEST','XU_MAPPED111_FINAL_Y_RETIRE','XU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE','XU_MAPPED111_REQUIRED_GATE_PENDING']),'unfinished gate promoted')
selection=load('event-selection.json');need(selection['qualification']=='NOT_QUALIFIED'and all(e==events[e['serial']-1]for e in selection['events']),'selected native fields changed')
E={e['serial']:e for e in events}
for serial,suffix,tick,bval in [(175,'.rsp_ready',9359383413333,1),(181,'.cmd_ready',9359383433333,1),(224,'.NOTIFIER',9359390050000,0),(225,'.n0',9359390050000,1),(250,'.Q',9359390060000,1),(251,'.o_vld',9359390060000,1),(312,'.cmd_valid',9359416766667,1),(315,'.rsp_ready',9359416776667,1),(444,'.cmd_valid',9359423333333,1),(451,'.rsp_ready',9359423333333,1)]:
 e=E[serial];need(e['name'].endswith(suffix)and e['tick_fs']==tick and int(e['bval'],16)==bval,'key four-state event differs')
need(E[175]['tick_fs']<E[224]['tick_fs'],'earlier handshake X was hidden')
help_text=(B/P/'actual111-runtime-help.log').read_text();need('Unsupported option' in help_text and 'XU_MAPPED111_REJECT only_frozen_task00'in help_text,'failed runtime-help limitation changed')
launch=load('raw/mapped-causal-launch-20261105-117/state.json');need(launch['status']==status and launch['child_returncode']==0 and launch['helpers_equal']and launch['helpers_before']==launch['helpers_after'],'actual117 launcher did not finish cleanly')
print('PASS actual117453 native events/117 nodes/636 input receipts; earlier transient handshake X and later notifier/Q/FIFO X retained; native fatal unchanged; NOT COMPLETE CAUSALITY OR QUALIFICATION')
