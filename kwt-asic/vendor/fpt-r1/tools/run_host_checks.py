#!/usr/bin/env python3
"""Small, portable software checks for imported reference files; not KWT acceptance."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def record(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--cc', default='gcc')
    args = ap.parse_args()
    out = args.output.resolve()
    if out.is_relative_to(ROOT):
        ap.error('Use a fresh output directory outside the immutable bundle')
    out.mkdir(parents=True, exist_ok=False)
    result = {'status': 'FAIL', 'scope': 'host numeric helpers and fake-MMIO C reader only',
              'hdl_simulation': 'NOT_RUN', 'kwt_precision': 'NOT_RUN', 'commands': []}
    try:
        verifier = load('reuse_bundle_verify', ROOT / 'tools/verify_bundle.py')
        result['integrity_before'] = verifier.verify()
        ref = ROOT / 'reference/fpt'
        paths = [ref / 'python/flash_attention_tile_model.py',
                 ref / 'tests/check_cats_r4_fp32_reference.py',
                 ref / 'vitis/src/cats_r4_core_service.h',
                 ref / 'tests/cats_r4_core_service_coherence_fixture.c']
        result['inputs'] = [record(p) for p in paths]
        numeric = load('fpt_numeric_reference', paths[0])
        exact = load('fpt_fraction_reference', paths[1])
        checked = 0
        for bits in range(65536):
            if ((bits >> 7) & 255) == 255:
                continue
            value = numeric.bf16_bits_to_f32(bits)
            if numeric.f32_bits(value) != bits << 16 or numeric.f32_to_bf16_bits(value) != bits:
                raise ValueError('finite BF16 roundtrip failed: ' + hex(bits))
            checked += 1
        rounding = [(0x3f808000, 0x3f80), (0x3f818000, 0x3f82),
                    (0x3f807fff, 0x3f80), (0x3f808001, 0x3f81),
                    (0xbf808000, 0xbf80), (0xbf818000, 0xbf82)]
        for source, want in rounding:
            if numeric.f32_to_bf16_bits(numeric.bits_to_f32(source)) != want:
                raise ValueError('RNE directed vector failed')
        finite_fp32 = [0, 1, 0x007fffff, 0x00800000, 0x3f800000, 0x3f800001,
                       0xbf800000, 0x7f7fffff, 0xff7fffff, 0x80000000]
        for bits in finite_fp32:
            if exact.encode(exact.decode(bits), zero_sign=bits >> 31) != bits:
                raise ValueError('Fraction FP32 roundtrip failed')
        if exact.encode(Fraction(1) + Fraction(1, 2**24)) != 0x3f800000:
            raise ValueError('Fraction tie-to-even failed')
        result['numeric_helpers'] = {'status': 'PASS', 'finite_bf16_roundtrips': checked,
                                     'bf16_rne_vectors': len(rounding),
                                     'fraction_fp32_vectors': len(finite_fp32) + 1}
        cc = shutil.which(args.cc)
        if cc is None:
            raise RuntimeError('C compiler unavailable: ' + args.cc)
        result['compiler'] = record(Path(cc).resolve())
        exe = out / ('coherence.exe' if sys.platform == 'win32' else 'coherence')
        commands = [('compile', [cc, '-std=c11', '-O0', '-Wall', '-Wextra', '-Werror',
                                str(paths[3]), '-I', str(ref / 'vitis/src'), '-o', str(exe)]),
                    ('run', [str(exe)])]
        for phase, argv in commands:
            p = subprocess.run(argv, cwd=out, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=30)
            log = out / (phase + '.log')
            log.write_text(p.stdout)
            result['commands'].append({'phase': phase, 'argv': argv, 'exit_code': p.returncode,
                                       'log': record(log)})
            if p.returncode != 0:
                raise RuntimeError(phase + ' failed; see preserved log')
            if phase == 'run' and 'PASS CORE_SERVICE_COHERENCE cases=16' not in p.stdout:
                raise RuntimeError('C fixture completion marker missing')
        result['c_reader'] = {'status': 'PASS', 'cases': 16, 'real_mmio': False}
        result['integrity_after'] = verifier.verify()
        result['status'] = 'PASS'
    except Exception as exc:
        result['error'] = str(exc)
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['status', 'scope', 'hdl_simulation', 'kwt_precision']},
                     ensure_ascii=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
