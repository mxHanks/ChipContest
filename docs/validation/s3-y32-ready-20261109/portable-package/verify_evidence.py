#!/usr/bin/env python3
"""Read-only relocated byte/hash/source/image/vector/log verification; no simulation."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import stat

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def load(path):return json.loads(Path(path).read_text())
def artifact(root,rel,expected=None):
 assert isinstance(rel,str) and rel and not PurePosixPath(rel).is_absolute() and '..' not in PurePosixPath(rel).parts,rel
 p=root/rel
 assert p.is_file() and not p.is_symlink() and root.resolve() in p.resolve().parents,rel
 if expected:assert sha(p)==expected,rel
 return p

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
 parser.add_argument('--out',type=Path)
 args=parser.parse_args();root=args.root.resolve()
 manifest=load(root/'sha256.json');assert manifest
 for rel,expected in manifest.items():artifact(root,rel,expected)
 actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
 assert actual==set(manifest)|{'sha256.json'},'unexpected/missing files'
 provenance=load(root/'provenance.json')
 for rel,record in provenance['files'].items():
  p=artifact(root,rel,record['sha256'])
  assert manifest[rel]==record['sha256'] and p.stat().st_size==record['bytes'],rel
  assert stat.S_IMODE(p.stat().st_mode)==record['mode'],rel
 campaigns=[]
 for result_path in sorted((root/'campaigns').glob('*/result.json')):
  d=load(result_path);campaign=result_path.parent
  assert d.get('status') not in ('RUNNING',None),'unfinished campaign'
  for rel,expected in d.get('original_source_sha256',{}).items():artifact(campaign,'source/'+rel,expected)
  for key,rel in [('firmware_elf_sha256','accel_soc'),('firmware_image_sha256','accel_soc.verilog'),
                   ('simulator_sha256','verilator-obj/soc_sim')]:
   if key in d:artifact(campaign,rel,d[key])
  for step in d.get('steps',[]):
   if 'log_sha256' in step:artifact(campaign,step['name']+'.log',step['log_sha256'])
   if 'command_sha256' in step:
    identity=hashlib.sha256(json.dumps(step['command'],separators=(',',':')).encode()).hexdigest()
    assert identity==step['command_sha256'],(campaign,step['name'],'command hash')
  recipe=load(campaign/'clear-recipe.json')
  artifact(campaign,'s3_clear_main.c',recipe['generated_c_sha256'])
  artifact(campaign,'tb.sv',recipe['generated_tb_sha256'])
  artifact(campaign,'source/tests/e203/firmware/main.c',recipe['frozen_main_sha256'])
  artifact(campaign,'source/tools/ppa/s3_task_clear_protocol.py',recipe['helper_sha256'])
  for task in d.get('task_results',[]):
   original=task['original_layer'];vectors=campaign/f'task-{original:02d}/vectors'
   for rel,expected in task.get('vectors',{}).items():artifact(vectors,rel,expected)
  campaigns.append(dict(relative_path=str(result_path.relative_to(root)),status=d['status'],
     recorded_layers=len(d.get('task_results',[])),payload_cycles=d.get('cycles'),
     source_drift=d.get('source_drift'),classification='PASS_DEVELOPMENT_ONLY' if
     d['status']=='DEVELOPMENT_PASS_POLICY_PENDING' else 'NOTPASS_OR_DIAGNOSTIC'))
 maps=load(root/'path-map.json')
 def relocated(saved):
  for row in maps:
   old=row['original_prefix']
   if saved==old or saved.startswith(old+'/'):
    return root/row['relative_prefix']/saved[len(old):].lstrip('/')
  raise ValueError('unmapped receipt artifact '+saved)
 replays=[]
 for receipt_path in sorted((root/'proofs').glob('*/receipt.json')):
  saved=load(receipt_path)
  if 'log_sha256' in saved:
   artifact(receipt_path.parent,'simulation.log',saved['log_sha256'])
   assert saved.get('native_exit')==0,receipt_path
   if 'simulator_sha256' in saved:
    assert sha(relocated(saved['command'][0]))==saved['simulator_sha256'],receipt_path
   if 'firmware_image_sha256' in saved:
    tests=[x.split('=',1)[1] for x in saved['command'] if x.startswith('+TESTCASE=')]
    assert len(tests)==1 and sha(relocated(tests[0]+'.verilog'))==saved['firmware_image_sha256'],receipt_path
   replays.append(dict(relative_path=str(receipt_path.relative_to(root)),status=saved.get('status')))
 receipt=dict(replays=replays,status='PASS',scope='Relocated immutable bytes and saved source/ELF/image/simulator/vector/command/log receipts; no simulation, PPA or official qualification',
     files_hashed=len(manifest),original_copied_files=len(provenance['files']),campaigns=campaigns,
     failure_log_index='failure-log-index.json')
 if args.out:
  assert root not in args.out.resolve().parents,'write receipt outside immutable evidence tree'
  args.out.write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
