#!/usr/bin/env python3
"""Actual DMA/core/arbiter/SRAM protocol and numeric screen; no CPU execution."""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
from datetime import datetime, timezone


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def readhex(path, bits, count):
    data = [int(s, 16) for s in path.read_text().split()]
    if len(data) != count:
        raise ValueError(f'{path}: count {len(data)} != {count}')
    return [x - (1 << bits) if x >> (bits - 1) else x for x in data]


def oracle(v):
    x = readhex(v / 'x.mem', 16, 6336)
    w = readhex(v / 'w.mem', 16, 16384)
    b = readhex(v / 'bias.mem', 40, 256)
    y = readhex(v / 'y32.mem', 32, 25344)
    packed = [int(s, 16) for s in (v / 'w_packed16.mem').read_text().split()]
    for i, value in enumerate(packed):
        assert value == ((w[2*i] & 65535) | ((w[2*i+1] & 65535) << 16)), f'packed W {i}'
    for r in range(99):
        for col in range(256):
            z = b[col] + sum(x[r*64+k] * w[k*256+col] for k in range(64))
            q, rem = divmod(z, 512)
            q += rem > 256 or (rem == 256 and q & 1)
            assert q & 0xffffffff == y[r*256+col] & 0xffffffff, f'golden oracle {r}, {col}'
    return {'independent_int16_signed40_rne_oracle_outputs': 25344, 'packed_weight_words': 8192}


def synthetic_vectors(out):
    out.mkdir()
    x = []
    for r in range(99):
        if r % 4 == 0:
            row = [-32768] * 64
        elif r % 4 == 1:
            row = [32767] * 64
        else:
            row = [0] * 64
            row[0], row[1] = (256, -256) if r % 4 == 2 else (-256, 256)
        x.extend(row)
    w = [0] * 16384
    b = []
    for j in range(256):
        m = j % 8
        b.append([(1 << 39)-1, -(1 << 39), 0, 0, 512, -512, (1 << 39)-1, -(1 << 39)][m])
        for k in range(64):
            w[k*256+j] = (-32768 if m == 0 else 32767 if m == 1 else
                          (1 if k == 0 else 0) if m == 2 else (3 if k == 0 else 0) if m == 3 else
                          (1 if k == 1 else 0) if m == 4 else (3 if k == 1 else 0) if m == 5 else
                          (-32768 if k % 2 else 32767) if m == 6 else (-1 if k == 0 else 0))
    y, y32 = [], []
    tie_positive = tie_negative = 0
    for r in range(99):
        for j in range(256):
            z = b[j] + sum(x[r*64+k]*w[k*256+j] for k in range(64))
            q, rem = divmod(z, 512)
            if rem == 256:
                tie_positive += z >= 0
                tie_negative += z < 0
            q += rem > 256 or (rem == 256 and q & 1)
            y.append(z)
            y32.append(q)
    packed = [(w[2*i] & 65535) | ((w[2*i+1] & 65535) << 16) for i in range(8192)]
    for name, data, bits in [('x.mem', x, 16), ('w.mem', w, 16), ('bias.mem', b, 40),
                              ('w_packed16.mem', packed, 32), ('y.mem', y, 48), ('y32.mem', y32, 32)]:
        (out / name).write_text(''.join(f'{v & ((1 << bits)-1):0{bits//4}x}\n' for v in data))
    return {'positive_halfway_values': tie_positive, 'negative_halfway_values': tie_negative,
            'min_raw48': min(y), 'max_raw48': max(y)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', required=True, type=pathlib.Path)
    ap.add_argument('--vectors', required=True, type=pathlib.Path)
    ap.add_argument('--out', required=True, type=pathlib.Path)
    ap.add_argument('--build-jobs', type=int, default=2)
    ap.add_argument('--run-jobs', type=int, default=2)
    args = ap.parse_args()
    repo, vectors, out = args.repo.resolve(), args.vectors.resolve(), args.out.resolve()
    if out.exists():
        raise SystemExit(f'refusing to overwrite {out}')
    out.mkdir(parents=True)
    names = [
        'experiments/s3-y32-dma-day/protocol/tb_dma_protocol.sv',
        'experiments/s3-y32-dma-day/protocol/generate_physical.py',
        'experiments/s3-y32-dma-day/protocol/run_protocol.py',
        'third-party/e203_hbirdv2/rtl/e203/perips/xu_matrix_dma.sv',
        'third-party/e203_hbirdv2/rtl/e203/perips/xu_dma_shared_arb.v',
        'tools/ppa/xu_shared_icb_sram.sv',
        'third-party/e203_hbirdv2/rtl/e203/general/sirv_sim_ram.v',
    ]
    names += [str(p.relative_to(repo)) for p in sorted((repo / 'generated/LinearRowPairDmaCore').glob('*.sv'))]
    pins = []
    for name in names:
        dst = out / 'source' / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, dst)
        pins.append({'path': name, 'sha256': sha(dst)})
    frozen_vectors = out / 'vectors'
    frozen_vectors.mkdir()
    vector_pins = []
    for name in ['x.mem', 'w.mem', 'w_packed16.mem', 'bias.mem', 'y.mem', 'y32.mem']:
        dst = frozen_vectors / name
        shutil.copy2(vectors / name, dst)
        vector_pins.append({'path': name, 'sha256': sha(dst)})
    oracle_result = oracle(frozen_vectors)
    gen = out / 'source/experiments/s3-y32-dma-day/protocol/generate_physical.py'
    spec = importlib.util.spec_from_file_location('dma_physical', gen)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    include = out / 'dma_physical_connections.svh'
    module.generate(include)
    obj = out / 'obj'
    sources = [str(out / 'source' / name) for name in names if name.endswith(('.sv', '.v'))]
    compile_cmd = ['verilator', '--binary', '--timing', '--assert', '-Wno-fatal', '--build-jobs', str(args.build_jobs),
                   '--top-module', 'tb_dma_protocol', '--Mdir', str(obj), '-I' + str(out)] + sources
    p = subprocess.run(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / 'compile.log').write_text(p.stdout)
    if p.returncode:
        raise SystemExit(p.returncode)
    synthetic = out / 'synthetic-vectors'
    synthetic_result = synthetic_vectors(synthetic)
    oracle(synthetic)
    synthetic_pins = [{'path': p.name, 'sha256': sha(p)} for p in sorted(synthetic.glob('*.mem'))]
    cases = [('numeric', 2), ('numeric', 1), ('descriptor', 2), ('stress', 2), ('readerror', 2),
             ('writeerror0', 2), ('writeerror_mid', 2), ('writeerror_last', 2), ('reset', 2),
             ('reset_bias', 2), ('reset_x', 2), ('reset_y0', 2), ('reset_y_mid', 2), ('reset_clear', 2)]
    cases += [(f'readerror-{i}', 2) for i in [8191, 8192, 8193, 8704, 15039]]
    cases += [('synthetic', 2), ('synthetic', 1)]

    def run(case):
        name, mode = case
        selected_vectors = synthetic if name == 'synthetic' else frozen_vectors
        selected_case = 'numeric' if name == 'synthetic' else 'readerror' if name.startswith('readerror-') else name
        command = [str(obj / 'Vtb_dma_protocol'), '+vectors=' + str(selected_vectors), '+case=' + selected_case, '+mode=' + str(mode)]
        if name.startswith('readerror-'):
            command.append('+inject_index=' + name.split('-')[1])
        q = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        log = out / f'{name}-mode{mode}.log'
        log.write_text(q.stdout)
        records = []
        for line in q.stdout.splitlines():
            if line.startswith(('DMA_NUMERIC_PASS ', 'DMA_CLEAR_PASS ', 'DMA_ABORT_PASS ', 'DMA_RESET_PASS ', 'DMA_PROTOCOL_PASS ')):
                records.append({'kind': line.split()[0], 'values': dict(re.findall(r'(\w+)=(\S+)', line))})
        passed = q.returncode == 0 and 'DMA_PROTOCOL_PASS ' in q.stdout
        return {'case': name, 'mode': mode, 'passed': passed, 'returncode': q.returncode,
                'command': command, 'log': log.name, 'log_sha256': sha(log), 'records': records}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.run_jobs) as pool:
        jobs = list(pool.map(run, cases))
    drift = [p['path'] for p in pins if sha(repo / p['path']) != p['sha256']]
    passed = all(job['passed'] for job in jobs) and not drift
    tool = subprocess.run(['verilator', '--version'], stdout=subprocess.PIPE, text=True)
    result = {
        'status': 'PASS' if passed else 'FAIL', 'scope': __doc__,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_files': pins, 'vector_files': vector_pins, 'source_drift': drift,
        'verilator': {'path': shutil.which('verilator'), 'version': tool.stdout.strip()},
        'compile_command': compile_cmd, 'observer_sha256': sha(include), 'oracle': oracle_result,
        'synthetic_vectors': {'generation': synthetic_result, 'files': synthetic_pins},
        'jobs': jobs, 'limits': {'cpu_executed': False, 'full12_verified': False, 'sta_or_area_verified': False,
                                'initial_physical_clear_dirty_prestate_proven': False},
    }
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'jobs': [{'case': j['case'], 'mode': j['mode'], 'passed': j['passed']} for j in jobs], 'source_drift': drift, 'out': str(out)}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
