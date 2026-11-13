#!/usr/bin/env python3
"""Preserve compact, byte-checked storage experiment evidence without build products."""
import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module_bytes(path, name):
    raw = path.read_bytes()
    start = raw.index(('module ' + name + '(').encode())
    return raw[start:raw.index(b'endmodule', start) + len(b'endmodule')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build = args.build.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    origins = {}

    def copy(source, relative):
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha(destination) != sha(source):
            raise ValueError('copied bytes differ: ' + str(source))
        origins[str(relative)] = {'source': str(source), 'sha256': sha(source)}

    summary = build / 'summary-final-r2.json'
    subprocess.run(['python3', '-B', str(HERE / 'summarize.py'), '--build', str(build),
                    '--require-wide', '--out', str(summary)], check=True, cwd=ROOT)
    copy(summary, Path('summary.json'))
    for name in ['overlay-review-r2.json', 'wide-overlay-review-r2.json',
                 'snapshot-inventory-r2.json']:
        copy(build / name, Path(name))
    for name in ['candidate-r2', 'wide-candidate-r2']:
        folder = build / name
        copy(folder / 'manifest.json', Path(name) / 'manifest.json')
        for source in sorted((folder / 'rtl').iterdir()):
            if source.is_file():
                copy(source, Path(name) / 'rtl' / source.name)
    for name in ['core-r2', 'dma-r2', 'wide-core-r2', 'wide-dma-r2']:
        folder = build / name
        for source in sorted(folder.iterdir()):
            if source.is_file() and source.suffix in ('.json', '.log'):
                copy(source, Path(name) / source.name)
        for source in sorted((folder / 'source').iterdir()):
            if source.is_file():
                copy(source, Path(name) / 'source' / source.name)
    # Keep early candidate identities and the real one-task result. Do not relabel
    # an early smoke pass as a full final campaign.
    for name in ['candidate-r1', 'wide-candidate-r1']:
        copy(build / name / 'manifest.json', Path('history') / name / 'manifest.json')
    for name in ['receipt.json', 'task0.json', 'task0.log']:
        copy(build / 'dma-r1' / name, Path('history/dma-r1') / name)
    for source in sorted(HERE.iterdir()):
        if source.is_file():
            copy(source, Path('tools') / source.name)
    copy(HERE / 'README.md', Path('README.md'))
    base = ROOT / 'build/compliant32-20261113/x-macro/candidate-r2/rtl'
    for source in sorted(base.iterdir()):
        if source.is_file():
            copy(source, Path('reference/x-macro/rtl') / source.name)
    copy(ROOT / 'third-party/e203_hbirdv2/rtl/e203/perips/xu_matrix_dma_sysbus32.sv',
         Path('reference/xu_matrix_dma_sysbus32.sv'))
    for name in ['profile.json', 'vectors-manifest.json']:
        copy(ROOT / 'build/compliant32-20261113/numeric/dev-vectors-r1' / name,
             Path('vectors') / name)

    original_pe = module_bytes(base / 'LinearTileDmaCore.sv', 'MacPE_Acc41')
    copied_pe = []
    for candidate in ['candidate-r2', 'wide-candidate-r2']:
        current = module_bytes(build / candidate / 'rtl/LinearTileDmaCore.sv', 'MacPE_Acc41')
        if current != original_pe:
            raise ValueError('arithmetic bytes changed')
        copied_pe.append({'candidate': candidate, 'bytes': len(current),
                          'sha256': hashlib.sha256(current).hexdigest(), 'exact_bytes': True})

    product_min = -(1 << 15) * ((1 << 15) - 1)
    product_max = 1 << 30
    bias_min, bias_max = -(1 << 39), (1 << 39) - 1
    signed41_min, signed41_max = -(1 << 40), (1 << 40) - 1
    prefix_bounds = [{'products': k, 'minimum': bias_min + k * product_min,
                      'maximum': bias_max + k * product_max} for k in range(65)]
    if not all(signed41_min <= b['minimum'] <= b['maximum'] <= signed41_max
               for b in prefix_bounds):
        raise ValueError('legal arithmetic exceeds signed41')
    proof = {'status': 'PASS_ARITHMETIC_INTERVAL_AND_BYTE_IDENTITY',
             'definition': 'signed16 X/W, signed40 bias, exactly64 products; every prefix0..64 fits signed41',
             'signed16_product': {'minimum': product_min, 'maximum': product_max},
             'signed40_bias': {'minimum': bias_min, 'maximum': bias_max},
             'signed41_range': {'minimum': signed41_min, 'maximum': signed41_max},
             'prefix_bounds': prefix_bounds, 'MacPE_Acc41': copied_pe,
             'Y32': 'Preserves existing RNE9 then low32bits semantics, including signed wrap; no saturation claim',
             'test_scope': '60 raw48/RNE cases per candidate include full signed endpoints2048 each, rows1/3/8, stalls0/31/255; DMA RTL RNE separately compared to Y32 vectors',
             'limitations': 'Interval proof is not a universal hardware formal-equivalence proof or precision acceptance on organizer data'}
    (out / 'arithmetic-proof.json').write_text(json.dumps(proof, indent=2) + '\n')

    inventory = {'schema': 'storage_macro_compact_evidence_v1',
                 'status': 'PASS_UNIT_EVIDENCE_ONLY', 'created_at': datetime.now(timezone.utc).isoformat(),
                 'parent_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                 'child_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT / 'third-party/e203_hbirdv2', text=True).strip(),
                 'origins': origins,
                 'omitted': ['obj directories and simulator binaries',
                             'large raw48/Y32 output files; retained original build receipts carry their bytes/SHA256',
                             'vector tensor bytes; preserved manifest carries the frozen sample/layer identities'],
                 'scope': 'Raw core and DMA+32bit endpoint module evidence. No CPU/System Bus whole-task, native macro timing, power, mapped equivalence, 150MHz or2.25mm2 qualification claim.'}
    (out / 'provenance.json').write_text(json.dumps(inventory, indent=2) + '\n')
    files = {str(p.relative_to(out)): {'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(out.rglob('*')) if p.is_file()}
    (out / 'files.json').write_text(json.dumps({'schema': 'sha256_files_v1', 'files': files}, indent=2) + '\n')
    print(json.dumps({'status': 'PACKAGED_UNIT_EVIDENCE_ONLY', 'out': str(out),
                      'files': len(files) + 1, 'bytes': sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),
                      'files_sha256': sha(out / 'files.json')}))


if __name__ == '__main__':
    main()
