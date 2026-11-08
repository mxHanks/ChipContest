#!/usr/bin/env python3
"""Replay isolated direct streaming NICE tests, without SoC or synthesis."""
from pathlib import Path
import hashlib
import json
import subprocess

repo = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent
rtl = repo / 'third-party/e203_hbirdv2/rtl/e203'
records = []
tests = [
    ('stream8', 'tb_nice_stream8_errors', out/'tb_nice_stream8_errors.sv',
     'NICE_STREAM8_PASS cases=118 success_counts=32 status_abort_groups=32 postpop_write_errors=24 resets=14'),
    ('disabled', 'tb_nice_stream8_disabled', out/'tb_nice_stream8_disabled.sv',
     'NICE_STREAM8_DISABLED_PASS compile_time_enable=0 no_side_effect=1'),
    ('legacy-direct', 'tb_nice_direct_errors', repo/'tests/e203/tb_nice_direct_errors.sv',
     'NICE_DIRECT_ERRORS_PASS cases=19 bus_error_positions=9 direct_status_errors=2 commit_error=1 shared_error_lanes=8 resets=4'),
]
for tag, top, fixture, marker in tests:
    commands = [
        ['iverilog', '-g2012', '-I'+str(rtl/'core'), '-s', top, '-o', str(out/(tag+'.vvp')),
         str(fixture), str(rtl/'subsys/xu_nice_drain8.v')],
        ['vvp', str(out/(tag+'.vvp'))],
    ]
    for phase, command in zip(['compile','simulation'],commands):
        result = subprocess.run(command, cwd=repo, text=True, capture_output=True, timeout=60)
        output = result.stdout+result.stderr
        (out/(tag+'-'+phase+'.log')).write_text(output)
        records.append(dict(tag=tag,phase=phase,command=command,returncode=result.returncode))
        if result.returncode or (phase=='simulation' and marker not in output):
            raise RuntimeError(output)
        if phase=='simulation':print(output.strip())
records.append(dict(source_sha256={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in [rtl/'subsys/xu_nice_drain8.v',repo/'tests/e203/firmware/accel.c',
                                            out/'tb_nice_stream8_errors.sv',out/'tb_nice_stream8_disabled.sv']}))
(out/'test-commands.json').write_text(json.dumps(records,indent=2)+'\n')
