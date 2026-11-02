#!/usr/bin/env python3
"""xu S1 source/RTL identity check; no synthesis or PPA conclusion."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
CHILD = ROOT/'third-party/e203_hbirdv2'
BASE = 'f49a5fc914971426bd4530db39e270a84b41139f'
ALLOWED = {'rtl/e203/perips/'+name for name in
           ['BiasSramCache.sv', 'LinearSramCachedCore.sv', 'accel_icb_slave.v', 'mem_32x40.sv']}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=CHILD)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    assert not git('status', '--porcelain', '--untracked-files=normal', '--', 'rtl').strip(), 'dirty child RTL'
    result = dict(schema='xu-s1-source-identity-v1', status='RUNNING', baseline_child=BASE,
                  candidate_child=git('rev-parse', 'HEAD').decode().strip(),
                  main_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                  default_top='LinearComputeCore', default_generated_rtl={},
                  sram_generated_rtl={}, unchanged_platform={}, chisel_sources={})
    changes = set(git('diff', '--name-only', BASE, 'HEAD').decode().splitlines())
    assert changes == ALLOWED, changes
    result['candidate_only_changes'] = sorted(changes)
    for p in sorted((ROOT/'generated/LinearComputeCore').glob('*.sv')):
        baseline = git('show', BASE+':rtl/e203/perips/'+p.name)
        assert p.read_bytes() == baseline, p
        result['default_generated_rtl'][p.name] = sha(baseline)
    assert len(result['default_generated_rtl']) == 10
    for p in sorted((ROOT/'generated/LinearSramCachedCore').glob('*.sv')):
        installed = CHILD/'rtl/e203/perips'/p.name
        assert p.read_bytes() == installed.read_bytes(), p
        assert installed.read_bytes() == git('show', 'HEAD:rtl/e203/perips/'+p.name), installed
        result['sram_generated_rtl'][p.name] = sha(p.read_bytes())
    assert len(result['sram_generated_rtl']) == 13
    for name in git('ls-tree', '-r', '--name-only', BASE).decode().splitlines():
        if name.startswith('rtl/') and name not in ALLOWED:
            baseline = git('show', BASE+':'+name)
            assert (CHILD/name).read_bytes() == baseline, name
            result['unchanged_platform'][name] = sha(baseline)
    for p in sorted((ROOT/'src/main/scala').rglob('*.scala')):
        result['chisel_sources'][p.relative_to(ROOT).as_posix()] = sha(p.read_bytes())
    cache = (CHILD/'rtl/e203/perips/BiasSramCache.sv').read_text()
    assert len(re.findall(r'^\s*mem_32x40\s+\w+\s*\(', cache, re.M)) == 8
    assert len(re.findall(r'^\s*reg\s+\[39:0\]\s+tile_\d;', cache, re.M)) == 8
    memory = (CHILD/'rtl/e203/perips/mem_32x40.sv').read_text()
    assert re.search(r'reg\s+\[39:0\]\s+Memory\[0:31\];', memory)
    adapter = ROOT/'tools/ppa/xu_bias_sram_adapter.sv'
    adapter_text = adapter.read_text()
    assert 'for (lane=0; lane<3; lane=lane+1)' in adapter_text
    assert len(re.findall(r'\bRAMSP128X16\s+macro\s*\(', adapter_text)) == 1
    result['adapter_sha256'] = sha(adapter.read_bytes())
    result['verifier_sha256'] = sha(Path(__file__).read_bytes())
    result.update(status='PASS', logical_sram_banks=8, logical_sram_depth=32,
                  logical_sram_width=40, tile_register_bits=320,
                  adapter_macros_per_bank=3, adapter_total_macro_instances=24,
                  macro_scope='adapter mapping cardinality; no DC/PPA result',
                  unchanged_platform_count=len(result['unchanged_platform']))
    with args.out.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print('PASS: '+str(args.out))


if __name__ == '__main__':
    main()
