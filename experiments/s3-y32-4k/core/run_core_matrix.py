#!/usr/bin/env python3
"""Extend a pinned, already compiled module screen; never claims CPU timing."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screen', type=Path, required=True)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    screen, vectors, out = (p.resolve() for p in (args.screen, args.vectors, args.out))
    original_path = screen / 'receipt.json'
    original = json.loads(original_path.read_text())
    if original['status'] != 'PASS':
        raise RuntimeError('base compilation screen was not PASS')
    identity = dict(original['inputs'])
    executable = screen / 'obj/VLinearTileDmaCore'
    for path in [original_path, executable, Path(__file__).resolve()]:
        identity[str(path)] = sha(path)
    layers = [vectors / ('layer_%02d' % i) for i in range(12)]
    for layer in layers:
        for name in ('x.mem', 'w.mem', 'bias.mem', 'y.mem', 'y32.mem'):
            path = layer / name
            identity[str(path)] = sha(path)
    def check_identity():
        bad = [name for name, digest in identity.items()
               if not Path(name).is_file() or sha(Path(name)) != digest]
        if bad:
            raise RuntimeError('input/source drift: ' + repr(bad))
    check_identity()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(schema='tile64_module_matrix_v1', status='RUNNING', inputs=identity,
                  scope='Local module RTL; C++ sink/RNE; not CPU, DMA, SoC or PPA', cases=[])
    def save():
        (out / 'receipt.json').write_text(json.dumps(record, indent=2) + '\n')
    cases = [('layer%02d-rows8' % i, layer, 8, 0) for i, layer in enumerate(layers)]
    cases += [('layer00-rows%d-stall7' % rows, layers[0], rows, 7) for rows in range(2, 8)]
    try:
        for name, layer, rows, stall in cases:
            command = [str(executable), str(layer), str(rows), str(stall), str(out / (name + '.json'))]
            start = time.monotonic()
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            (out / (name + '.log')).write_text(result.stdout)
            entry = dict(name=name, command=command, returncode=result.returncode,
                         elapsed_seconds=time.monotonic() - start)
            record['cases'].append(entry)
            save()
            if result.returncode:
                raise RuntimeError(name + ' failed; see preserved log')
            measured = json.loads((out / (name + '.json')).read_text())
            if measured['outputs_exact_raw48'] != 25344:
                raise RuntimeError('incomplete output count: ' + name)
            entry['measurement'] = measured
            print(name, 'PASS', 'active_cycles=%d' % measured['active_cycles'], flush=True)
        check_identity()
        record.update(status='PASS', source_drift=[], full12_module_raw48_outputs=304128,
                      full12_module_cpp_rne_outputs=304128, variable_rows_cases=6,
                      total_module_raw48_outputs=25344*len(cases))
    except Exception as error:
        record.update(status='FAILED', error=str(error))
        raise
    finally:
        record['outputs'] = {p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
                             for p in sorted(out.iterdir()) if p.name != 'receipt.json'}
        save()
    print('TILE64_MODULE_MATRIX_PASS cases=%d full12_raw48=304128 variable_rows=2..7' % len(cases))


if __name__ == '__main__':
    main()
