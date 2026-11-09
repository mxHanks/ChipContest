#!/usr/bin/env python3
"""Prepare inventory, or seal frozen ready-drain evidence after explicit --seal.

Default preparation never copies campaign/proof/source bytes or writes an archive.
Original evidence is copied with mode preservation and never hardlinked.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import tarfile

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
MAIN=BASE.parents[1]
STAGE=HERE/'s3-y32-ready-evidence'
SUCCESS='DEVELOPMENT_PASS_POLICY_PENDING'
CAMPAIGNS=[
 ('baseline-selected-full12', MAIN/'build/postflow-20261108/selected-full12'),
 ('ready-task0',BASE/'ready-task0'),
 ('ready-fenced-task0',BASE/'ready-fenced-task0'),
]
PROOFS=[('checks',BASE/'checks'),('rtl-checks',BASE/'rtl-checks')]
SOURCE_ADDITIONS=[
 'third-party/e203_hbirdv2/rtl/e203/subsys/xu_nice_drain8.v',
 'third-party/e203_hbirdv2/rtl/e203/perips/accel_icb_slave.v',
 'tests/e203/tb_nice_ready_errors.sv',
 'tests/e203/tb_nice_ready_disabled.sv',
 'tests/e203/tb_xu_nice_ready_wrapper.sv',
 'tests/e203/tb_ready_wrapper_disabled.sv',
 'tests/e203/test_nice_ready_wrapper.py',
 'tests/e203/firmware/accel.c',
 'tests/e203/firmware/accel.h',
 'tests/e203/tb_accel_soc.sv',
 'tools/scripts/xu_firmware_contract.py',
 'tools/scripts/e203_soc.py',
 'tools/ppa/s3_task_campaign.py',
 'tests/e203/test_y32_firmware_contract.py',
 'tests/ppa/test_s3_task_campaign.py',
]

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
 return h.hexdigest()

def load(path):return json.loads(Path(path).read_text())
def dump(path,obj):path.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')
def campaign_status(path):
 p=path/'result.json'
 if not p.is_file():return dict(status='MISSING',recorded_layers=0)
 d=load(p)
 return dict(status=d.get('status'),recorded_layers=len(d.get('task_results',[])),
             cycles=d.get('cycles'),source_drift=d.get('source_drift'),error=d.get('error'))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--seal',action='store_true')
 p.add_argument('--final-campaign',action='append',type=Path,default=[])
 p.add_argument('--final-report',type=Path)
 p.add_argument('--extra-campaign',action='append',type=Path,default=[])
 p.add_argument('--extra-proof',action='append',type=Path,default=[])
 a=p.parse_args()
 campaigns=CAMPAIGNS+[(x.name,x.resolve()) for x in a.final_campaign+a.extra_campaign]
 assert len({name for name,_ in campaigns})==len(campaigns),'duplicate campaign names'
 proofs=PROOFS+[(x.name,x.resolve()) for x in a.extra_proof]
 assert len({name for name,_ in proofs})==len(proofs),'duplicate proof names'
 inventory=dict(mode='seal' if a.seal else 'preparation',campaigns=[
  dict(name=name,original_path=str(path),**campaign_status(path)) for name,path in campaigns],
  proofs=[dict(name=name,original_path=str(path),exists=path.is_dir()) for name,path in proofs],
  final_report=str(a.final_report) if a.final_report else None,
  note='Inventory only until --seal after root freezes every campaign, proof and final report. Failed attempts remain NOTPASS.')
 dump(HERE/'planned-inventory.json',inventory)
 if not a.seal:
  print(json.dumps(inventory,indent=2));return
 assert a.final_report and a.final_report.is_file(),'final frozen report required'
 assert (BASE/'ready_compare.py').is_file(),'independent strict verifier required'
 assert campaign_status(BASE/'ready-task0')['status']=='FAIL','original unfenced ready attempt must remain FAIL'
 for name,path in campaigns:
  info=campaign_status(path)
  assert info['status'] in (SUCCESS,'FAIL'),(name,info)
  if info['status']==SUCCESS:assert info['source_drift']==[],(name,'source drift')
 for path in a.final_campaign:
  info=campaign_status(path)
  assert info['status']==SUCCESS and info['recorded_layers']==12 and info['source_drift']==[],path
 assert not STAGE.exists(),'staging already exists; never overwrite frozen evidence'
 archive=HERE/'s3-y32-ready-evidence.tar.gz'
 assert not archive.exists(),'archive already exists; never overwrite frozen evidence'
 STAGE.mkdir()
 origins={};mappings=[];excluded=[];generated=[]
 def emit(rel,text):
  dest=STAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text);generated.append(str(rel))
 def add(source,rel,required_sources=()):
  source=Path(source);rel=Path(rel)
  assert not rel.is_absolute() and '..' not in rel.parts,rel
  if source.is_dir():
   assert not source.is_symlink(),source
   for item in sorted(source.rglob('*')):
    if not item.is_file():continue
    local=item.relative_to(source)
    pinned_source=local.parts[:1]==('source',) and str(Path(*local.parts[1:])) in required_sources
    if not pinned_source:
     if '__pycache__' in local.parts or item.suffix in ('.pyc','.vcd','.fst'):
      excluded.append(str(item));continue
     if any(x in local.parts for x in ('verilator-obj','csrc','obj')) and item.name not in ('soc_sim','simv'):
      excluded.append(str(item));continue
    add(item,rel/local,required_sources)
   return
  assert source.is_file() and not source.is_symlink(),source
  dest=STAGE/rel;dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():assert sha(source)==sha(dest);return
  before=source.stat();identity=sha(source)
  shutil.copy2(source,dest)
  after=source.stat()
  assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),source
  assert sha(dest)==sha(source)==identity,('source changed during copy',source)
  assert stat.S_IMODE(dest.stat().st_mode)==stat.S_IMODE(before.st_mode),source
  assert (before.st_dev,before.st_ino)!=(dest.stat().st_dev,dest.stat().st_ino),source
  origins[str(rel)]=dict(original_path=str(source.resolve()),sha256=identity,bytes=before.st_size,
                        mode=stat.S_IMODE(before.st_mode))
 def tree(source,rel,required_sources=()):
  assert source.is_dir(),source
  mappings.append(dict(original_prefix=str(source.resolve()),relative_prefix=str(rel)))
  add(source,rel,required_sources)
 for name,path in campaigns:
  tree(path,Path('campaigns')/name,load(path/'result.json').get('original_source_sha256',{}))
 for name,path in proofs:tree(path,Path('proofs')/name)
 # Freeze root-level analysis, source pairs, failures, commands and reviews.
 for path in sorted(BASE.iterdir()):
  if path.is_file() and path.suffix in ('.py','.json','.log','.md','.patch'):
   add(path,Path('summaries')/path.name)
 for rel in SOURCE_ADDITIONS:add(BASE/'prototype-repo'/rel,Path('source-additions/prototype-repo')/rel)
 mappings.append(dict(original_prefix=str((BASE/'prototype-repo').resolve()),relative_prefix='source-additions/prototype-repo'))
 for name in ('assemble_evidence.py','verify_evidence.py','replay_saved_command.py','revalidate_comparisons.py'):
  add(HERE/name,name)
 add(a.final_report,Path('reports')/a.final_report.name)
 for path in sorted((MAIN/'docs').glob('s3-y32-*ready*.md')):add(path,Path('reports')/path.name)
 for name in ('freeze-receipt.json','helper-origin.json'):
  if (HERE/name).is_file():add(HERE/name,Path('packaging')/name)
 emit(Path('path-map.json'),json.dumps(sorted(mappings,key=lambda x:len(x['original_prefix']),reverse=True),indent=2)+'\n')
 emit(Path('campaign-inventory.json'),json.dumps(inventory,indent=2)+'\n')
 emit(Path('excluded-files.txt'),'\n'.join(excluded)+'\n')
 failures=[]
 for rel,record in origins.items():
  path=STAGE/rel
  if path.suffix=='.log':
   text=path.read_text(errors='replace')
   if any(token in text for token in ('FATAL:','FAILED (','FAIL:','Traceback (most recent call last):','%Error:')):
    failures.append(dict(relative_path=rel,classification='NOTPASS_OR_DIAGNOSTIC_RAW',
                         reason='Raw failure/traceback/negative-test diagnostic; inspect original context. Never certifies a failed campaign.'))
 emit(Path('failure-log-index.json'),json.dumps(failures,indent=2)+'\n')
 emit(Path('README.md'),(HERE/'README-evidence-template.md').read_text())
 emit(Path('provenance.json'),json.dumps(dict(scope='Byte-for-byte source evidence copies; generated packaging metadata listed separately.',
   files=origins,generated_files=generated+['provenance.json','sha256.json'],
   exclusion_policy=['Object/C++ intermediates excluded; soc_sim/simv executable retained',
                     'Waveforms and Python caches excluded unless exact source receipt pins them']),indent=2)+'\n')
 seen={};dedup=0;logical=0
 for path in sorted(STAGE.rglob('*')):
  if not path.is_file():continue
  logical+=path.stat().st_size;key=(sha(path),stat.S_IMODE(path.stat().st_mode))
  if key in seen:path.unlink();os.link(seen[key],path);dedup+=1
  else:seen[key]=path
 for rel,record in origins.items():
  source=Path(record['original_path']);dest=STAGE/rel
  assert (source.stat().st_dev,source.stat().st_ino)!=(dest.stat().st_dev,dest.stat().st_ino),rel
 manifest={str(path.relative_to(STAGE)):sha(path) for path in sorted(STAGE.rglob('*')) if path.is_file()}
 dump(STAGE/'sha256.json',manifest)
 with tarfile.open(archive,'w:gz',compresslevel=6) as tar:tar.add(STAGE,arcname=STAGE.name)
 (HERE/'archive.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
 result=dict(stage=str(STAGE),archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
  original_files=len(origins),manifest_files=len(manifest),logical_bytes=logical,
  unique_file_bytes=sum(path.stat().st_size for path in seen.values()),internal_hardlinks=dedup,
  original_inodes_linked=False,campaign_count=len(campaigns),failed_campaigns=[name for name,path in campaigns if campaign_status(path)['status']=='FAIL'],
  final_campaigns=[str(path) for path in a.final_campaign])
 dump(HERE/'assembly.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
