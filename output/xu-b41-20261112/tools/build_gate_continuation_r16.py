"""Adapt the preserved R15 controller to finish only the two unstarted gates."""
from pathlib import Path
import ast
import hashlib
import json

R = Path('/tmp/xu-b41-close-20261111-r1')
parent = R / 'xu-run-gate-reset-r15.py'
parent_sha = 'e628acc007aa8ab969b6f2476ee2067cf62e882df50c0860c4d9767b0486ccdb'
assert hashlib.sha256(parent.read_bytes()).hexdigest() == parent_sha
lines = parent.read_text().splitlines()
assert len(lines) == 105
assert lines[63].startswith('POWER=')
assert lines[71].startswith("with (O/'full12-r15-preflight.json')")
assert lines[74].startswith("for variant in ['tight-O2',")
assert lines[97].strip() == 'while True:'
assert 'POWER_HANDOFF_COMPLETE' in lines[103]

preflight = '''
assert all(not Path('/proc/'+str(pid)).exists() for pid in [299096,316319]), 'Original controllers have not drained'
old_preflight=json.loads((O/'full12-r15-preflight.json').read_text())
assert old_preflight['pins']==pins and old_preflight['inputs']==inputs
tight_dir=O/'tight-O2-full12-r15'
tight_binding=json.loads((tight_dir/'verified-binding.json').read_text())
review_path=R/'xu-gate-independent-20261113-r2/tight-O2.json'
assert digest(review_path)=='f75f69aea0c3e9959ea92aa07e8d7e6cc5f0faad42f7ddebdd0f6407d5ee4a4e'
review=json.loads(review_path.read_text())
assert review['status']=='PASS_INDEPENDENT_GATE_FULL12_REVIEW'
assert tight_binding['pins']==pins and review['pins']==pins
assert tight_binding['firmware_image_sha256']==EXPECTED['tight-O2']
assert tight_binding['tasks']==12 and tight_binding['warmup']==1 and tight_binding['physical_clears']==13
assert digest(tight_dir/'native.log')==tight_binding['native_log_sha256']==review['native_log_sha256']
assert digest(tight_dir/'verified-binding.json')==review['binding_sha256']
assert (O/'tight-O2-r15-fullsoc.vcd').stat().st_size==tight_binding['vcd_bytes']==review['vcd_bytes']
assert tight_binding['vcd_sha256']==review['vcd_sha256_from_controller']=='44caf59b71ace97b6c7d32f947783e894727761d97be65cd4a7dcab743f28c64'
pending=['phased_64_fast4-O2','backoff_8_256_fast4-O2']
assert all(not (O/(v+'-full12-r15')).exists() and not (O/(v+'-r15-fullsoc.vcd')).exists() for v in pending)
with (O/'full12-r16-resume-preflight.json').open('x') as f:json.dump({'pins':pins,'inputs':inputs,'parent_controller_sha256':PARENT_CONTROLLER_SHA,'controller_sha256':digest(Path(__file__)),'reused_tight_review_sha256':digest(review_path),'reused_tight_binding_sha256':digest(tight_dir/'verified-binding.json'),'pending':pending,'policy':'Finish both pending gates serially; power follows the complete gate campaign; preserve all original checks and raw evidence.'},f,indent=2)
print('GATE_R16_RESUME_PREFLIGHT_PASS','tight-O2 reused','pending',pending,flush=True)
'''.strip().splitlines()

out = []
for number, line in enumerate(lines, 1):
    if 64 <= number <= 67 or 98 <= number <= 104:
        continue
    if number == 5:
        line = line.replace('xu-run-gate-reset-r15.log', 'xu-run-gate-reset-r16.log')
    if number == 72:
        out.append('PARENT_CONTROLLER_SHA='+repr(parent_sha))
        out.extend(preflight)
        continue
    if number == 75:
        line = 'for variant in pending:'
    if number == 105:
        line = "print('GATE_REMAINING_TWO_FULL12_PASS','tight-O2 reused from independently verified R15',flush=True)"
    out.append(line)
source = '\n'.join(out)+'\n'
tree = ast.parse(source)
parents = {}
for node in ast.walk(tree):
    for child in ast.iter_child_nodes(node):
        parents[child] = node
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'run']
assert len(calls) == 1
ancestor = calls[0]
ancestors = []
while ancestor in parents:
    ancestor = parents[ancestor]
    ancestors.append(ancestor)
lock_blocks = [n for n in ancestors if isinstance(n, ast.With)]
assert len(lock_blocks) == 1 and 'eda.lock' in out[lock_blocks[0].lineno-1]
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='flock' for n in ast.walk(lock_blocks[0]))
assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='heavy' for n in ast.walk(lock_blocks[0]))
assert 'power_proc' not in source and 'WAIT_EXISTING_POWER' not in source
assert '+MAX_CYCLES=20000000' in source and '+TASKS=12' in source and '+WARMUP=1' in source
target = R / 'xu-run-gate-reset-r16.py'
with target.open('x') as f:
    f.write(source)
metadata = {'parent_path':str(parent),'parent_sha256':parent_sha,'path':str(target),'sha256':hashlib.sha256(source.encode()).hexdigest(),'bytes':len(source.encode()),'pending':['phased_64_fast4-O2','backoff_8_256_fast4-O2'],'native_run_line':calls[0].lineno,'native_run_within_lock':True,'changes':['Reuse independently accepted tight-O2 instead of rerunning it','Remove dependency on naturally exited original power controller','Finish remaining gates before power','Use independent resume preflight and controller log'],'original_source_unchanged':True}
with (R/'xu-run-gate-reset-r16.adaptation.json').open('x') as f:
    json.dump(metadata,f,indent=2)
print(json.dumps(metadata,sort_keys=True))
