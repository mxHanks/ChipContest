#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
d=json.loads((D/'candidates137.json').read_text())
expected=['baseline_h1_h2','s1_h2_only','s1_sram_bias','s2b','s2d','pe32','pe64','compact32_128']
assert [r['id'] for r in d['candidates']]==expected
assert d['candidate_count']==len(expected)==8
assert {r['id'] for r in d['existing_continuations']}=={'s2c','s2e'}
assert [r['id'] for r in d['excluded']]==['s2a']
for p,r in d['local_evidence_files'].items():
 b=(ROOT/p).read_bytes(); assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],p
for r in d['candidates']:
 assert r['qualification']=='NOT_QUALIFIED' and r['queue_status']=='PENDING_SERVER_INPUT_VERIFY'
 assert r['formal']['returncode']==0
 assert r['formal']['sram_internal']=='BLACK_BOX_NOT_PROVED'
 assert re.fullmatch('[a-f0-9]{40}',r['source']['child_commit'])
 assert re.fullmatch('[a-f0-9]{64}',r['ppa']['original_mapped']['sha256'])
 assert r['formal']['ordered_svf_inputs']
 assert float(r['ppa']['original_area_mm2'])<float(d['area_budget_mm2'])
 if r['formal']['mapped']['sha256']!=r['ppa']['original_mapped']['sha256']:
  assert r['id'] in ['s2d','pe32'] and 'ORIGINAL_AREA_MAP_DIFFERS_FROM_FORMALLY_PROVED_REPAIRED_MAP_SELECT_AND_REMEASURE' in r['missing']
assert d['candidates'][0]['source']['original_ppa_main_commit'] is None
print(json.dumps({'status':'PASS_LOCAL_DRAFT_CONSISTENCY_ONLY','candidates':8,'hashed_local_inputs':len(d['local_evidence_files']),'qualification':'NOT_QUALIFIED'}))
