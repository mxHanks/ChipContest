#!/usr/bin/env python3
"""Reproduce host-only PE64 preparation; dummy DBs never run through EDA."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--candidate', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
standard = out/'standard.db'
sram = out/'sram.db'
standard.write_text('HOST ONLY DUMMY STANDARD LIBRARY\n')
sram.write_text('HOST ONLY DUMMY SRAM LIBRARY\n')
import hashlib
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
commands = [
    ('generate', [sys.executable, ROOT/'tools/ppa/xu_soc_implementation.py',
        '--root', a.candidate, '--profile', 's3-pe64', '--out', out/'implementation',
        '--standard-cell-db', standard, '--standard-cell-sha256', sha(standard),
        '--sram-db', sram, '--sram-sha256', sha(sram)]),
    ('prepare', [sys.executable, ROOT/'tools/scripts/xu_soc_ppa.py', 'prepare',
        '--root', a.candidate, '--out', out/'prepared', '--implementation', out/'implementation/implementation.json',
        '--allow-unqualified-mapping']),
    ('verify', [sys.executable, ROOT/'tools/scripts/xu_soc_ppa.py', 'verify',
        '--root', a.candidate, '--out', out/'prepared'])]
records = []
for name, argv in commands:
    argv = [str(item) for item in argv]
    with (out/(name+'.log')).open('x') as stream:
        stream.write(json.dumps(dict(argv=argv, cwd=str(ROOT)))+'\n')
        stream.flush()
        subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)
    records.append(dict(name=name, argv=argv, returncode=0))
receipt = json.loads((out/'implementation/generation.json').read_text())
impl = json.loads((out/'implementation/implementation.json').read_text())
assert receipt['macro_total'] == 384
assert impl['defines'] == ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_ACCEL_PE64=1']
assert impl['accelerator_configuration']['physical_weight_bytes'] == 131072
assert impl['accelerator_configuration']['weight_padding_bytes'] == 98304
result = dict(status='PASS_HOST_ONLY_NOT_QUALIFIED', commands=records,
              source_profile=receipt['source_profile'], macro_total=receipt['macro_total'],
              accelerator_configuration=impl['accelerator_configuration'])
(out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(result['status'])
