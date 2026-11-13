#!/usr/bin/env python3
"""Verify a copied compact evidence tree; optionally rerun portable fallback checks."""
import argparse
import hashlib
import itertools
import json
import re
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pp(path, flags):
    text = subprocess.check_output(['verilator', '-E', '-P', *['-D' + d for d in flags], str(path)], text=True)
    return re.findall(r'\S+', re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--fallbacks', action='store_true')
    args = p.parse_args()
    bundle = args.bundle.resolve()
    index = json.loads((bundle / 'files.json').read_text())
    for name, wanted in index['files'].items():
        path = bundle / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != wanted['bytes'] or sha(path) != wanted['sha256']:
            raise ValueError('bundle identity differs: ' + name)
    actual = {str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file() and p.name != 'files.json'}
    if actual != set(index['files']):
        raise ValueError('unindexed or missing bundle files')
    missing_large = 0
    for name in ['core-r2', 'dma-r2', 'wide-core-r2', 'wide-dma-r2']:
        folder = bundle / name
        rec = json.loads((folder / 'receipt.json').read_text())
        if rec['status'] != 'PASS' or any(c['returncode'] for c in rec['commands']):
            raise ValueError('not a terminal clean campaign: ' + name)
        for filename, wanted in rec['outputs'].items():
            path = folder / filename
            if path.is_file():
                if path.stat().st_size != wanted['bytes'] or sha(path) != wanted['sha256']:
                    raise ValueError('campaign output differs: ' + str(path))
            else:
                if not filename.endswith(('.actual-raw48.mem', '.cpp-rne-y32.mem', '.actual-y32.mem')):
                    raise ValueError('undeclared omitted output: ' + filename)
                missing_large += 1
    summary = json.loads((bundle / 'summary.json').read_text())
    for candidate in summary['candidates']:
        name = 'candidate-r2' if candidate['name'] == 'three' else 'wide-candidate-r2'
        if sha(bundle / name / 'manifest.json') != candidate['manifest_sha256']:
            raise ValueError('candidate binding differs')
        manifest = json.loads((bundle / name / 'manifest.json').read_text())
        for filename, wanted in manifest['files'].items():
            if sha(bundle / name / 'rtl' / filename) != wanted:
                raise ValueError('candidate RTL differs')
        if candidate['full12']['exact_y32'] != 304128 or candidate['raw_cases'] != 60 or candidate['reset_recovery_exact_y32'] != 76032:
            raise ValueError('incomplete campaign coverage')
    fallback_count = 0
    if args.fallbacks:
        names = ['XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM', 'XU_MATRIX_STORAGE_SRAM']
        for candidate in ['candidate-r2', 'wide-candidate-r2']:
            for bits in itertools.product([False, True], repeat=3):
                if all(bits):
                    continue
                flags = [name for name, bit in zip(names, bits) if bit]
                for filename, reference in [('LinearTileDmaCore.sv', bundle / 'reference/x-macro/rtl/LinearTileDmaCore.sv'),
                                            ('xu_matrix_dma_sysbus32.sv', bundle / 'reference/xu_matrix_dma_sysbus32.sv')]:
                    if pp(bundle / candidate / 'rtl' / filename, flags) != pp(reference, flags):
                        raise ValueError('fallback differs: ' + candidate + str(flags))
                fallback_count += 1
    print(json.dumps({'status': 'PASS_COMPACT_IDENTITIES_AND_RECORDED_UNIT_EVIDENCE',
                      'indexed_files': len(index['files']), 'fallback_combinations_rechecked': fallback_count,
                      'large_output_files_not_in_bundle': missing_large,
                      'scope': 'Validates copied evidence, not a new simulation or PPA/contest qualification run'}))


if __name__ == '__main__':
    main()
