#!/usr/bin/env python3
"""Exercise the ingress alone and with the unmodified platform fabric."""
import argparse
from pathlib import Path
import subprocess
import tempfile


here = Path(__file__).resolve().parent
root = here.parents[1]
rtl = root / 'third-party/e203_hbirdv2/rtl/e203'
parser = argparse.ArgumentParser()
parser.add_argument('--ingress', type=Path, default=rtl / 'subsys/xu_systembus_ingress32.v')
parser.add_argument('--fabric-only', action='store_true')
parser.add_argument('--allow-slow', action='store_true')
args = parser.parse_args()
common = [args.ingress, rtl / 'fab/sirv_icb1to8_bus.v', rtl / 'general/sirv_gnrl_icbs.v',
          rtl / 'general/sirv_gnrl_bufs.v', rtl / 'general/sirv_gnrl_dffs.v']
cases = [('tb_ingress32_fabric', ['-Ptb_ingress32_fabric.EXPECT_FAST=' + str(int(not args.allow_slow))])]
if not args.fabric_only:
    cases += [('tb_ingress32_pipeline', ['-Ptb_ingress32_pipeline.HAS_LOAD=' + str(load)]) for load in (0, 1)]
with tempfile.TemporaryDirectory(prefix='ingress32-regression-') as tmp:
    for top, params in cases:
        binary = Path(tmp) / (top + '.vvp')
        result = subprocess.run(['iverilog', '-g2012', '-DDISABLE_SV_ASSERTION', '-s', top,
                                 *params, '-o', str(binary), str(here / (top + '.sv')),
                                 *map(str, common)], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise SystemExit(result.stderr)
        result = subprocess.run(['vvp', str(binary)], capture_output=True, text=True, timeout=30)
        print(result.stdout, end='')
        if result.returncode:
            raise SystemExit(result.stderr or result.returncode)
