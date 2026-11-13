#!/usr/bin/env python3
"""Reject changes to frozen platform, arithmetic, SRAM organization or firmware."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
CHILD=ROOT/'third-party/e203_hbirdv2'
REF='bde23ba9d06c57f6536d9992b3cd3427daccd9f8'
def git(*args):return subprocess.check_output(['git',*args],cwd=CHILD)
def sha(b):return hashlib.sha256(b).hexdigest()
allowed={'rtl/e203/perips/xu_matrix_dma_sysbus32.sv','rtl/e203/subsys/xu_systembus_ingress32.v'}
files=git('ls-tree','-r','--name-only',REF,'rtl/e203').decode().splitlines()
current_files={str(p.relative_to(CHILD)) for p in (CHILD/'rtl/e203').rglob('*') if p.is_file()}
if current_files!=set(files):raise SystemExit('Production RTL file set changed')
changed=[];before={};after={}
for name in files:
 original=git('show',REF+':'+name);current=(CHILD/name).read_bytes()
 if original!=current:changed.append(name);before[name]=sha(original);after[name]=sha(current)
if set(changed)!=allowed:raise SystemExit('Unexpected production changes: '+repr(changed))
a=(ROOT/'experiments/s3-y32-compliant32/validation/sysbus32_main.c').read_bytes()
b=(ROOT/'experiments/s3-y32-ingress-perf/cpu_main.c').read_bytes()
if a!=b:raise SystemExit('Frozen CPU firmware changed')
print(json.dumps(dict(status='PASS',reference_child=REF,files_compared=len(files),allowed_changes=sorted(changed),before_sha256=before,after_sha256=after,firmware_sha256=sha(a),scope='Only DMA metadata scheduling and added ingress source-owner depth changed; original CPU/LSU/BIU/fabric and arithmetic/SRAM sources are byte-identical'),indent=2))
