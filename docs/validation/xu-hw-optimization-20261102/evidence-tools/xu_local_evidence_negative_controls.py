#!/usr/bin/env python3
"""Exercise corruption rejection using in-memory or temporary copies of evidence."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.dont_write_bytecode=True
parser=argparse.ArgumentParser()
parser.add_argument('--repo', required=True)
parser.add_argument('--evidence', required=True)
parser.add_argument('--out')
args=parser.parse_args()
repo=Path(args.repo).resolve()
evidence=Path(args.evidence).resolve()
spec=importlib.util.spec_from_file_location('audit',evidence/'evidence-tools/xu_verify_local_evidence.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
with tempfile.TemporaryDirectory(prefix='xu-negative-original-') as original:
 raw,_=audit.checked_archive(evidence/'local-artifacts/xu-hw-local-screening.tar.xz',Path(original),'xu-hw-local-screening')
 result=json.loads((raw/'H1H2-real1/result.json').read_text())
 log=(raw/'H1H2-real1/simulation.log').read_text()
records=[]
def reject(name,invoke):
 try:
  invoke()
 except ValueError as error:
  records.append(dict(name=name,status='PASS rejected corruption',error=str(error)))
 else:
  raise AssertionError('did not reject: '+name)
reject('changed mmio write count in raw PERF',lambda:audit.validate_run(result,log.replace('mmio_writes=55720','mmio_writes=55721'),'bias-hw-window','real',1))
reject('duplicated TASK event',lambda:audit.validate_run(result,log.replace('PERF_TASK ',next(line for line in log.splitlines() if line.startswith('TASK_PASS '))+'\nPERF_TASK '),'bias-hw-window','real',1))
# Full-bundle provenance check also rejects wrong archive bytes before any event claims.
with tempfile.TemporaryDirectory(prefix='xu-negative-control-') as temporary:
 target=Path(temporary)
 (target/'local-artifacts').mkdir();(target/'evidence-tools').mkdir()
 shutil.copyfile(evidence/'evidence-tools/runtime-source-97b3542.json',target/'evidence-tools/runtime-source-97b3542.json')
 shutil.copyfile(evidence/'local-artifacts/archives-sha256.json',target/'local-artifacts/archives-sha256.json')
 for path in (evidence/'local-artifacts').glob('*.tar.xz'):
  if path.name=='xu-hw-local-screening.tar.xz':
   shutil.copyfile(path,target/'local-artifacts'/path.name)
   with (target/'local-artifacts'/path.name).open('ab') as output:output.write(b'corrupt-evidence')
  else:(target/'local-artifacts'/path.name).symlink_to(path)
 reject('appended bytes to original screening archive',lambda:audit.verify_bundle(target,repo))
output=dict(status='PASS',scope='in-memory / temporary-file negative controls; no runtime source or original artifact changed',verifier_sha256=audit.sha256(evidence/'evidence-tools/xu_verify_local_evidence.py'),checks=records)
if args.out:
 Path(args.out).write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
