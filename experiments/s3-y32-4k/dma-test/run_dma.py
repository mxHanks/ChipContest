#!/usr/bin/env python3
"""Local real-interface DMA campaign. Does not establish CPU or PPA results."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--generated', type=Path,
                        default=root / 'build/parallel4k-20261110/core-generated-r1')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reuse-screen', type=Path)
    parser.add_argument('--deadline-utc', default='2026-11-10T15:59:00+00:00')
    args = parser.parse_args()
    deadline = datetime.fromisoformat(args.deadline_utc)
    if deadline.tzinfo is None:
        raise RuntimeError('deadline must include a UTC offset')
    def before_deadline():
        if datetime.now(timezone.utc) >= deadline:
            raise RuntimeError('experiment deadline reached; no new process started')
    before_deadline()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    generated, vectors = args.generated.resolve(), args.vectors.resolve()
    rtl = sorted(generated.glob('*.sv'))
    if len(rtl) != 11:
        raise RuntimeError('expected eleven generated core RTL files')
    rtl += [here.parent / 'xu_matrix_dma64.sv',
            here.parent / 'fabric/xu_dma64_shared_arb.sv',
            here.parent / 'fabric/xu_shared_icb_sram64.sv',
            root / 'tools/ppa/generic_ramsp_non_ppa.sv', here / 'dma64_test_top.sv']
    cpp = here / 'dma64_test.cpp'
    inputs = {str(p): sha(p) for p in rtl + [cpp, Path(__file__).resolve()]}
    for i in range(12):
        for name in ('x.mem', 'w.mem', 'bias.mem', 'y32.mem'):
            p = vectors / ('layer_%02d' % i) / name
            inputs[str(p)] = sha(p)
    snapshot = out / 'source'
    snapshot.mkdir()
    for p in rtl + [cpp, Path(__file__).resolve()]:
        shutil.copy2(p, snapshot / p.name)
    receipt = dict(schema='dma64_real_endpoint_campaign_v1', status='RUNNING',
                   scope='Local DMA, arbiter, generic functional 256-macro endpoint; not CPU/PPA',
                   inputs=inputs, commands=[], deadline_utc=deadline.isoformat())
    def save():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    def run(command, name):
        before_deadline()
        save()
        begin = time.monotonic()
        with (out / (name + '.log')).open('w') as log:
            result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        receipt['commands'].append(dict(name=name, command=command,
                                       returncode=result.returncode,
                                       elapsed_seconds=time.monotonic() - begin))
        save()
        if result.returncode:
            raise RuntimeError(name + ' failed; see preserved log')
    try:
        if args.reuse_screen:
            previous = args.reuse_screen.resolve()
            previous_receipt = json.loads((previous / 'compile-receipt.json').read_text())
            if previous_receipt['status'] != 'PASS':
                raise RuntimeError('reused compilation is not PASS')
            for name, digest in previous_receipt['inputs'].items():
                if inputs.get(name) != digest:
                    raise RuntimeError('reused compile source differs: ' + name)
            executable = previous / 'obj/Vdma64_test_top'
            receipt['reused_compile_receipt'] = dict(path=str(previous / 'compile-receipt.json'),
                                                     sha256=sha(previous / 'compile-receipt.json'))
        else:
            run(['verilator', '--version'], 'verilator-version')
            command = ['verilator', '--cc', '--exe', '--build', '-j', '2', '--assert',
                       '-Wno-fatal', '--top-module', 'dma64_test_top', '--Mdir', str(out / 'obj'),
                       '-CFLAGS', '-std=c++17']
            command += [str(snapshot / p.name) for p in rtl + [cpp]]
            run(command, 'compile')
            executable = out / 'obj/Vdma64_test_top'
        inputs[str(executable)] = sha(executable)
        for name, tasks, rows, faults, stall, final_hold in (
                ('task0', 1, 8, 0, 0, 0), ('full12', 12, 8, 0, 0, 0),
                ('faults-task0', 1, 8, 1, 0, 0), ('stall-task0', 1, 8, 0, 1, 0),
                ('rows1-task0', 1, 1, 0, 0, 0), ('last-y-hold-task0', 1, 8, 0, 0, 1)):
            run([str(executable), str(vectors), str(tasks), str(rows),
                 str(out / (name + '.json')), str(faults), str(stall), str(final_hold)], name)
            measurement = json.loads((out / (name + '.json')).read_text())
            if measurement.get('status') != 'PASS' or measurement['exact_y32'] != 25344*tasks:
                raise RuntimeError(name + ' has incomplete numeric evidence')
            print(name, 'PASS', 'principal_cycles=%d' % measurement['principal_cycles'], flush=True)
        drift = [name for name, digest in inputs.items() if sha(Path(name)) != digest]
        if drift:
            raise RuntimeError('source/input drift: ' + repr(drift))
        receipt.update(status='PASS', source_drift=[])
    except Exception as error:
        receipt.update(status='FAILED', error=str(error))
        raise
    finally:
        receipt['outputs'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
                              for p in sorted(out.iterdir())
                              if p.is_file() and p.name != 'receipt.json'}
        save()


if __name__ == '__main__':
    main()
