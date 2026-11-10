#!/usr/bin/env python3
"""Local generated 64PE RTL test, with read-only physical observer; no CPU/PPA claim."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generated', type=Path, required=True)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    generated = args.generated.resolve()
    vectors = args.vectors.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    generator = here.parent / 'validation/generate_observer.py'
    spec = importlib.util.spec_from_file_location('tile_observer', generator)
    observer_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer_module)
    observer = out / 'tile_physical_observer.sv'
    observer_module.generate(observer)
    rtl = sorted(generated.glob('*.sv'))
    if len(rtl) != 11:
        raise RuntimeError('unexpected generated RTL file count: %d' % len(rtl))
    sources = rtl + [here / 'LinearTileDmaCore.scala', here / 'GenerateTileCore.scala',
                     here / 'tile_dma_driver.cpp', Path(__file__).resolve(), generator, observer]
    inputs = [vectors / name for name in ('x.mem', 'w.mem', 'bias.mem', 'y.mem', 'y32.mem')]
    identity = {str(path): digest(path) for path in sources + inputs}
    records = []
    receipt = dict(schema='tile64_core_campaign_v1', status='RUNNING', inputs=identity,
                   scope='Local Verilator module RTL plus C++ raw48/RNE oracle; not CPU/SoC/PPA',
                   commands=records)
    def save():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    def run(command, name):
        save()
        begin = time.monotonic()
        result = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, universal_newlines=True)
        (out / (name + '.log')).write_text(result.stdout)
        records.append(dict(name=name, command=command, returncode=result.returncode,
                            elapsed_seconds=time.monotonic()-begin))
        save()
        if result.returncode:
            raise RuntimeError(name + ' failed; see preserved log')
    try:
        run(['verilator', '--version'], 'verilator-version')
        run(['verilator', '--cc', '--exe', '--build', '-j', '2', '--assert', '-Wno-fatal',
             '--top-module', 'LinearTileDmaCore', '--Mdir', str(out / 'obj'),
             '-CFLAGS', '-std=c++17', *map(str, rtl), str(observer),
             str(here / 'tile_dma_driver.cpp')], 'compile')
        for rows, stall in ((8, 0), (8, 31), (8, 255), (1, 0)):
            name = 'rows%d-stall%d' % (rows, stall)
            run([str(out / 'obj/VLinearTileDmaCore'), str(vectors), str(rows), str(stall),
                 str(out / (name + '.json'))], name)
        drift = [str(path) for path in sources + inputs if digest(path) != identity[str(path)]]
        if drift:
            raise RuntimeError('source/input drift: ' + repr(drift))
        receipt.update(status='PASS', source_drift=drift)
        print('TILE64_CORE_CAMPAIGN_PASS cases=4 exact_outputs_per_case=25344')
    except Exception as error:
        receipt.update(status='FAILED', error=str(error))
        raise
    finally:
        receipt['outputs'] = {path.relative_to(out).as_posix(): dict(bytes=path.stat().st_size,
                              sha256=digest(path)) for path in sorted(out.glob('*.log'))}
        save()


if __name__ == '__main__':
    main()
