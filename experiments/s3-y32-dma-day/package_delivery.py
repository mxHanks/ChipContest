#!/usr/bin/env python3
"""Create a local, source-complete evidence package; never pushes or publishes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def keep(relative):
    parts = relative.parts
    if any(x in parts for x in ('.git', '.scala-build', '.bsp', '__pycache__', 'handoff')):
        return False
    if 'simulator' in parts:
        return relative.name in ('dma_day_soc', 'dma_day_soc.vvp')
    if any(x in parts for x in ('obj', 'verilator-obj')):
        return relative.name in ('soc_sim', 'VLinearRowPairDmaCore')
    return True


def copy_tree(source, destination):
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return
    for p in sorted(source.rglob('*')):
        relative = p.relative_to(source)
        if p.is_file() and keep(relative):
            q = destination/relative
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args],cwd=cwd,text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--baseline-parent',default='79d883300c7dfca7d129ff8e25daf34cf100250c')
    parser.add_argument('--baseline-child',default='dba1b5f82395b762f126387a1840e6a843e3a01a')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.is_relative_to(ROOT/'build/dma-day-20261109'):
        parser.error('package output must be outside the evidence tree being copied')
    if out.exists():
        parser.error('output must be new')
    out.mkdir(parents=True)
    stage = out/'s3-y32-dma-day'
    stage.mkdir()
    selected = ['project.scala','src/main/scala','experiments/s3-y32-dma-day',
                'tests/e203/dma_day_main.c','tests/e203/tb_dma_day_soc.sv',
                'tests/e203/firmware','tests/e203/vectors','model',
                'tools/model/export_s3_vectors.py','tools/ppa/xu_shared_icb_sram.sv',
                'third-party/e203_hbirdv2/rtl/e203','generated/LinearRowPairDmaCore',
                'docs/s3-y32-dma-day-plan.md','docs/s3-y32-dma-day-results.md',
                'docs/s3-y32-dma-day-storage.md','build/dma-day-20261109',
                'build/dma-core-checks-20261109','build/bias-demand-20261109/full12']
    for name in selected:
        copy_tree(ROOT/name,stage/name)
    delivery = stage/'delivery'
    delivery.mkdir()
    child = ROOT/'third-party/e203_hbirdv2'
    identities = dict(parent_base=args.baseline_parent,parent_tip=git('rev-parse','HEAD'),
                      child_base=args.baseline_child,child_tip=git('rev-parse','HEAD',cwd=child),
                      parent_branch=git('branch','--show-current'),child_branch=git('branch','--show-current',cwd=child),
                      created_at=datetime.now(timezone.utc).isoformat(),
                      scope='Local incremental bundles require the recorded baseline commits; full frozen RTL, tools and vectors are also included without git dependency.')
    for name,repo,base in [('parent',ROOT,args.baseline_parent),('e203',child,args.baseline_child)]:
        patch = subprocess.check_output(['git','diff','--binary',base,'HEAD'],cwd=repo)
        (delivery/(name+'.patch')).write_bytes(patch)
        subprocess.run(['git','bundle','create',str(delivery/(name+'.bundle')),'HEAD','^'+base],cwd=repo,check=True,capture_output=True)
        result = subprocess.run(['git','bundle','verify',str(delivery/(name+'.bundle'))],cwd=repo,check=True,capture_output=True,text=True)
        (delivery/(name+'-bundle-verify.log')).write_text(result.stdout+result.stderr)
    (delivery/'commits.json').write_text(json.dumps(identities,indent=2)+'\n')
    (stage/'START-HERE.md').write_text('''# Local DMA candidate evidence

Read `docs/s3-y32-dma-day-results.md` for engineering, performance and qualification decisions.

Verify the source/log/ELF/vector evidence without git:

```sh
python3 experiments/s3-y32-dma-day/verify_delivery.py --evidence-root build/dma-day-20261109 --baseline build/bias-demand-20261109/full12 --oracle --out /tmp/dma-delivery-audit.json
```

Rebuild the frozen real-CPU 12-task run in a new directory (Verilator, g++ required):

```sh
python3 experiments/s3-y32-dma-day/replay_frozen.py --sealed-run build/dma-day-20261109/cpu-dual-full12-r2 --out /tmp/dma-cpu-replay
```

This helper uses only packaged snapshots, with no git or original absolute paths. The default deadline is November9 23:59 Shanghai; a later operator must explicitly set a new deadline. `--reuse-binary` is only for a compatible Linux host.

`delivery/` contains local incremental parent/E203 bundles and binary patches. Their exact baseline prerequisites are in `commits.json`; they have not been pushed. Generated RTL, firmware ELF/image, original vectors, raw final and failed logs, storage inventory, mapped candidate netlist and local library are included. C++ build caches are omitted; source files and compiled simulation binaries are retained. No formal STA, gate-level, macro timing, official area delta, energy or contest qualification is claimed.
''')
    manifest = {str(p.relative_to(stage)):sha(p) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage/'PACKAGE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    archive = out/'s3-y32-dma-day-evidence.tar.gz'
    with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
        tar.add(stage,arcname=stage.name)
    result = dict(archive=str(archive),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
                  file_count=len(manifest),manifest_sha256=sha(stage/'PACKAGE-MANIFEST.json'),commits=identities)
    (out/'package.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
