#!/usr/bin/env python3
"""Re-run strict saved-evidence comparisons after relocation. No simulation."""
from pathlib import Path
import argparse,importlib.util,json

def module(path):
 spec=importlib.util.spec_from_file_location('portable_postflow_verifier',path)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--out',type=Path)
 a=p.parse_args();root=Path(__file__).resolve().parent
 maps=json.loads((root/'path-map.json').read_text())
 def resolve(saved):
  for row in maps:
   old=row['original_prefix']
   if saved==old or saved.startswith(old+'/'):
    path=root/row['relative_prefix']/saved[len(old):].lstrip('/')
    assert path.is_file(),saved
    return path
  raise ValueError('unmapped saved artifact '+saved)
 verifier=module(root/'summaries/postflow_compare.py');records=[]
 for path in sorted((root/'summaries').glob('*comparison*.json')):
  saved=json.loads(path.read_text())
  if saved.get('schema')!='s3-postflow-strict-comparison-v1':continue
  before_path=resolve(saved['baseline_identity']['result_path'])
  after_path=resolve(saved['candidate_identity']['result_path'])
  before=verifier.load_campaign(before_path,saved['profiles']['baseline'],saved['baseline_identity']['source_sha256'])
  after=verifier.load_campaign(after_path,saved['profiles']['candidate'],saved['candidate_identity']['source_sha256'])
  pairs={k:(v['baseline_sha256'],v['candidate_sha256']) for k,v in saved['source_changes'].items()}
  current=verifier.compare(before,after,pairs)
  for key in ('totals','source_changes','firmware_identity','profiles','condition_normalization'):
   assert current[key]==saved[key],(path.name,key)
  records.append(dict(comparison=path.name,status=current['status'],totals=current['totals']))
 assert records,'no strict postflow comparisons'
 receipt=dict(status='PASS',scope='Read-only relocated strict comparison; no simulator/EDA launched',comparisons=records)
 if a.out:
  assert root not in a.out.resolve().parents,'receipt must be outside evidence tree'
  a.out.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
