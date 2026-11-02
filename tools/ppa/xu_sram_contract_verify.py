#!/usr/bin/env python3
"""Four-state SRAM interface comparison using a caller-supplied vendor model.

No technology model is redistributed. This checks functional semantics only;
it does not establish timing, physical banking, power or SoC equivalence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-model', required=True, type=Path)
    parser.add_argument('--vendor-sha256', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-sram-functional-contract-v1', status='RUNNING',
                  limitations=['four-state functional model with ARM_UD_MODEL; no SDF/timing checks',
                               'module interface comparison; not full-SoC equivalence or power qualification'],
                  runner_sha256=sha(__file__), suites={})
    try:
        vendor = args.vendor_model.resolve()
        if not re.fullmatch('[0-9a-f]{64}', args.vendor_sha256) or sha(vendor) != args.vendor_sha256:
            raise ValueError('vendor model SHA256 differs')
        original = ROOT/'third-party/e203_hbirdv2/rtl/e203/general/sirv_sim_ram.v'
        adapter = HERE/'xu_sirv_sram_adapter.sv'
        text = original.read_text()
        anchor = 'module sirv_sim_ram '
        if text.count(anchor) != 1:
            raise ValueError('reference module transformation anchor differs')
        reference = out/'reference.sv'
        reference.write_text(text.replace(anchor, 'module xu_reference_sirv_sim_ram '))
        report['inputs'] = {str(p): sha(p) for p in [vendor, original, adapter, reference]}
        for label, top, marker, count in [
            ('exhaustive-2048', 'tb_xu_sram_adapter', 'XU_SRAM_ADAPTER_CONTRACT_PASS ', 2),
            ('platform-geometries', 'tb_xu_sram_geometry', 'XU_SRAM_GEOMETRY_PASS ', 6),
        ]:
            dest = out/label
            dest.mkdir()
            tb = HERE/(top+'.sv')
            report['inputs'][str(tb)] = sha(tb)
            commands = [
                ['iverilog', '-g2012', '-DARM_UD_MODEL', '-DXU_VENDOR_SRAM_MODEL',
                 '-s', top, '-o', str(dest/'simulation.vvp'), str(vendor),
                 str(adapter), str(reference), str(tb)],
                ['vvp', str(dest/'simulation.vvp')],
            ]
            result = dict(commands=commands, status='RUNNING')
            report['suites'][label] = result
            for name, command in zip(['compile', 'simulation'], commands):
                with (dest/(name+'.log')).open('x') as output:
                    subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output,
                                   stderr=subprocess.STDOUT, check=True, timeout=600)
            log = (dest/'simulation.log').read_text()
            if log.count(marker) != count:
                raise ValueError(label+' completion count differs')
            result.update(status='PASS', log_sha256={p.name: sha(p) for p in dest.glob('*.log')},
                          binary_sha256=sha(dest/'simulation.vvp'))
            print('PASS '+label, flush=True)
        report['status'] = 'PASS'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
    (out/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(report['status']+': '+str(out/'result.json'), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
