#!/usr/bin/env python3
"""Check the masked 32x40 bias adapter using generated RTL and a vendor model.

The external vendor model is mandatory and hash-checked. No technology model
is distributed. This is a four-state functional check, not PPA qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-model', required=True, type=Path)
    parser.add_argument('--vendor-sha256', required=True)
    parser.add_argument('--reference-rtl', required=True, type=Path,
                        help='actual generated RTL defining mem_32x40')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-bias-sram-functional-contract-v1', status='RUNNING',
                  runner_sha256=sha(__file__), limitations=[
                      'ARM_UD_MODEL four-state functional simulation; no SDF/timing checks',
                      'known address/control/mask inputs; unknown data and unwritten cells checked',
                      'module contract only; not full-SoC equivalence, area, timing or power evidence'])
    try:
        vendor = args.vendor_model.resolve()
        if (not re.fullmatch('[0-9a-f]{64}', args.vendor_sha256) or
                sha(vendor) != args.vendor_sha256):
            raise ValueError('vendor model SHA256 differs')
        original = args.reference_rtl.resolve()
        source = original.read_text()
        anchor = r'(?m)^(\s*module\s+)mem_32x40\b'
        if len(re.findall(anchor, source)) != 1:
            raise ValueError('generated reference must define mem_32x40 exactly once')
        reference = out/'xu_reference_mem_32x40.sv'
        reference.write_text(re.sub(anchor, r'\1xu_reference_mem_32x40', source))
        adapter = HERE/'xu_bias_sram_adapter.sv'
        testbench = HERE/'tb_xu_bias_sram_adapter.sv'
        report['inputs'] = {str(p): sha(p) for p in
                            [vendor, original, reference, adapter, testbench]}
        commands = [
            ['iverilog', '-g2012', '-DARM_UD_MODEL', '-DXU_VENDOR_SRAM_MODEL',
             '-s', 'tb_xu_bias_sram_adapter', '-o', str(out/'simulation.vvp'),
             str(vendor), str(adapter), str(reference), str(testbench)],
            ['vvp', str(out/'simulation.vvp')],
        ]
        report['commands'] = commands
        for name, command in zip(['compile', 'simulation'], commands):
            with (out/(name+'.log')).open('x') as output:
                subprocess.run(command, stdin=subprocess.DEVNULL, stdout=output,
                               stderr=subprocess.STDOUT, check=True, timeout=120)
        log = (out/'simulation.log').read_text()
        marker = 'XU_BIAS_SRAM_CONTRACT_PASS '
        completions = [line for line in log.splitlines() if line.startswith(marker)]
        if len(completions) != 1:
            raise ValueError('contract completion count differs')
        report.update(status='PASS', completion=completions[0],
                      binary_sha256=sha(out/'simulation.vvp'))
    except Exception as error:
        report.update(status='FAIL', error=str(error))
    report['log_sha256'] = {p.name: sha(p) for p in out.glob('*.log')}
    (out/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(report['status']+': '+str(out/'result.json'), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
