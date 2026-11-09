#!/usr/bin/env python3
"""Re-run strict packed clear comparisons after relocation, with no simulation or writes inside evidence."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys
sys.dont_write_bytecode=True

def module(path):
 spec=importlib.util.spec_from_file_location('portable_packed_clear_verifier',path)
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
 verifier=module(root/'summaries/packed_clear_compare.py');records=[]
 for path in sorted((root/'summaries').glob('*comparison*.json')):
  saved=json.loads(path.read_text())
  if saved.get('schema')!='s3-packed-clear-strict-comparison-v1':continue
  before_path=resolve(saved['baseline_identity']['result_path'])
  after_path=resolve(saved['candidate_identity']['result_path'])
  assert hashlib.sha256(before_path.read_bytes()).hexdigest()==verifier.BASELINE_RESULT_SHA256,'fixed baseline result differs'
  assert hashlib.sha256((root/'summaries/ready-baseline-sources.json').read_bytes()).hexdigest()==verifier.BASELINE_SOURCES_SHA256
  before=verifier.load_campaign(before_path,saved['profiles']['baseline'],saved['baseline_identity']['source_sha256'])
  after=verifier.load_campaign(after_path,saved['profiles']['candidate'],saved['candidate_identity']['source_sha256'])
  selection=saved['layer_selection']
  before=verifier.project_layers(before,selection['compared'],selection['mode'])
  after=verifier.project_layers(after,selection['compared'],selection['mode'])
  pairs={key:(value['baseline_sha256'],value['candidate_sha256']) for key,value in saved['source_changes'].items()}
  current=verifier.compare(before,after,pairs)
  for key in ('totals','layers','source_changes','firmware_identity','profiles','condition_normalization','layer_selection'):
   assert current[key]==saved[key],(path.name,key)
  records.append(dict(comparison=path.name,status=current['status'],totals=current['totals'],layer_selection=current['layer_selection']))
 assert records,'no strict packed clear comparisons; failed experiments cannot create PASS comparisons'
 receipt=dict(status='PASS',scope='Read-only relocated public-PACK32 strict comparison; no simulator/EDA launched',comparisons=records)
 if a.out:
  assert root not in a.out.resolve().parents,'receipt must be outside evidence tree'
  a.out.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
