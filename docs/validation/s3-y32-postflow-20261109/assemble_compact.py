#!/usr/bin/env python3
"""Copy compact saved postflow evidence; never run simulations or modify originals."""
from pathlib import Path
import hashlib,json,shutil

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
BASE=ROOT/'build/postflow-20261108'
SUCCESS='DEVELOPMENT_PASS_POLICY_PENDING'
SUFFIXES={'.log','.json','.md','.py','.patch','.diff','.sv'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')

def main():
 origins={};pending=[];campaigns=[]
 def add(src,relative):
  assert src.is_file() and not src.is_symlink(),src
  dst=OUT/relative;dst.parent.mkdir(parents=True,exist_ok=True)
  before=src.stat();identity=sha(src)
  shutil.copy2(src,dst)
  after=src.stat()
  assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),src
  assert sha(dst)==identity,src
  origins[str(relative)]=dict(original_path=str(src.resolve()),sha256=identity,bytes=before.st_size)
 def tree(src,rel):
  if not src.is_dir():pending.append(str(src));return
  for p in sorted(src.rglob('*')):
   if p.is_file() and p.suffix in SUFFIXES and '__pycache__' not in p.parts:
    add(p,rel/p.relative_to(src))
 cases=[('baseline8-direct-full12',ROOT/'build/writeback-v2-20261108/direct-full12'),
        ('baseline8-direct-task0',ROOT/'build/writeback-v2-20261108/direct-task0-phase'),
        ('baseline16-direct-task0',ROOT/'build/pe16-20261108/pe16-task0')]
 cases +=[(n,BASE/n) for n in ('bias8-full12','selected-full12','bias8-task0','bias16-task0',
   'bias16-task0-diagnostic','batch8-task0','batch16-task0','batch8-legacy-task0',
   'combo8-task0','combo16-task0','stream8-task0','stream-bias8-task0',
   'transport-task0','transport-observed-task0')]
 for label,src in cases:
  result=src/'result.json'
  if not result.exists():pending.append(str(result));continue
  r=load(result)
  if r.get('status') in (None,'RUNNING'):
   pending.append(str(result));continue
  campaigns.append(dict(label=label,status=r.get('status'),
      original_path=str(src),layers=len(r.get('task_results',[])),cycles=r.get('cycles'),
      source_drift=r.get('source_drift'),scope='development only; PASS never implies official qualification'))
  dst=Path('campaigns')/label
  for name in ('plan.json','result.json','clear-recipe.json','s3_clear_main.c'):
   p=src/name
   if p.exists():add(p,dst/name)
  for p in sorted(src.glob('task-*/simulation.log')):
   add(p,dst/p.relative_to(src))
 # Flat summaries, strict comparisons, exact source pins/pairs and assessment scripts.
 for p in sorted(BASE.iterdir()):
  if p.is_file() and p.suffix in SUFFIXES:
   if ('selected-full12' in p.name or 'selected-task0' in p.name) and any('selected-full12/result.json' in x for x in pending):
    continue
   add(p,Path('summaries')/p.name)
 for name in ('checks','source-review','batch-proof','bias8-logs','bias16-logs','bias-rollback'):
  tree(BASE/name,Path('proofs')/name)
 tree(BASE/'selected-first-stall7',Path('proofs/selected-first-stall7'))
 for repo,folder,label in [('batch16-repo','batch16-unit','batch16-unit'),
        ('batch16-repo','batch16-wrapper','batch16-wrapper'),
        ('batch8-repo','batch16-wrapper','batch8-wrapper'),
        ('stream8-repo','stream8-unit','stream8-unit'),
        ('stream8-repo','stream-wrapper','stream8-wrapper')]:
  tree(BASE/repo/'build'/folder,Path('proofs')/label)
 # Prior physical-PE independent source delta, reviewed pins and diagnostics.
 for name in ('compare_pe16.py','comparison-notes.md','source-changes.json','pe16-prototype.patch'):
  p=ROOT/'build/pe16-20261108'/name
  if p.exists():add(p,Path('proofs/prior-pe16')/name)
 # The large portable archive supplies frozen RTL/vectors/ELF/native binary.
 for name in ('assembly.json','archive.sha256','archive-verification.json',
      'final-seal-receipt.json','README-evidence.md','helper-repair-note.json',
      'staging-verification.json','staging-verification.log',
      'relocated-verification.json','relocated-verification.log',
      'relocated-comparisons.json','relocated-comparisons.log',
      'root-relocated-verification.json','root-relocated-verification.log',
      'root-relocated-comparisons.json','root-relocated-comparisons.log',
      'root-independent-receipt.json'):
  p=BASE/'handoff'/name
  if p.exists():add(p,Path('portable-package')/name)
 tree(BASE/'handoff/packaging-diagnostics',Path('portable-package/packaging-diagnostics'))
 required=['selected-full12-comparison.json','selected-full12-comparison.log',
   'selected-full12-sourcepairs.json','baseline8-full12-sourcepins.json',
   'selected-verifier-negative-receipt.json','selected-verifier-negative.log',
   'strict-comparison-evidence-sha256.json']
 for name in required:
  if not (BASE/name).is_file():pending.append(str(BASE/name))
 for name in ('README-evidence-template.md','verify_evidence.py','revalidate_comparisons.py','replay_saved_command.py'):
  p=BASE/'handoff'/name
  if p.exists():add(p,Path('portable-package')/name)
 failures=[]
 for rel,record in origins.items():
  p=OUT/rel
  if p.suffix=='.log' and any(x in p.read_text(errors='replace') for x in
     ('FATAL:','FAILED (','FAIL:','Traceback (most recent call last):','%Error:','TIMEOUT')):
   failures.append(dict(path=rel,classification='NOTPASS_OR_DIAGNOSTIC_RAW',
     note='Preserved original diagnostics. Expected injected errors need original context; no failed run is counted as PASS.'))
 dump(OUT/'campaign-inventory.json',campaigns)
 dump(OUT/'failure-log-index.json',failures)
 dump(OUT/'provenance.json',dict(files=origins,pending_originals=pending,
      policy='Byte copies only; no binary, vector or source snapshot; originals unmodified.'))
 manifest={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*'))
           if p.is_file() and p.name not in ('sha256.json','collection-summary.json')}
 dump(OUT/'sha256.json',manifest)
 summary=dict(status='PENDING_FINAL_EVIDENCE' if pending else 'COMPACT_EVIDENCE_COLLECTED',
     files=len(manifest)+2,bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),
     campaigns=len(campaigns),copied_originals=len(origins),diagnostic_logs=len(failures),
     pending_originals=pending,portable_archive=str(BASE/'handoff/s3-y32-postflow-evidence.tar.gz'))
 summary['portable_archive_sealed']=(BASE/'handoff/archive.sha256').is_file()
 dump(OUT/'collection-summary.json',summary)
 for _ in range(3):
  actual=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
  if summary['bytes']==actual:break
  summary['bytes']=actual
  dump(OUT/'collection-summary.json',summary)
 print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
