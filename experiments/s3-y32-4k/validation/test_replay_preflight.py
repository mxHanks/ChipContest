#!/usr/bin/env python3
"""No simulation: test immutable endpoint/simulator replay arguments."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util,json,tempfile
p=Path(__file__).with_name('run_cpu.py');s=importlib.util.spec_from_file_location('runner',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
parent={'arguments':{'throttle':7,'sim':'verilator'}}
m.validate_replay_arguments(SimpleNamespace(throttle=7,sim='verilator'),parent)
for args in [SimpleNamespace(throttle=0,sim='verilator'),SimpleNamespace(throttle=7,sim='iverilog')]:
 try:m.validate_replay_arguments(args,parent)
 except ValueError:continue
 raise AssertionError('invalid replay accepted')
with tempfile.TemporaryDirectory(prefix='s3-4k-replay-guard-') as directory:
 root=Path(directory);replay=root/'parent';replay.mkdir();(replay/'result.json').write_text(json.dumps(parent));out=root/'must-not-exist'
 try:m.main(['--out',str(out),'--replay-from',str(replay),'--throttle','0'])
 except SystemExit as exc:assert exc.code==2
 else:raise AssertionError('CLI did not reject mismatch')
 assert not out.exists(),'rejected replay created experiment output'
print(json.dumps({'status':'PASS','valid_argument_case':1,'invalid_argument_cases':2,'invalid_cli_case':1,'new_simulations':0},sort_keys=True))
