"""Derive the required payload measurement from the preserved native controller."""
from pathlib import Path
import ast
import hashlib
import json

R=Path('/tmp/xu-b41-close-20261111-r1')
parent=R/'xu-b41-power-r1.py'
source=parent.read_text()
lines=source.splitlines()
assert len(lines)==62
assert 'run=f.execute' in lines[55] and 'read_vcd ' in lines[47]
out=[]
for n,line in enumerate(lines,1):
    if n==6:
        out.append('import xu_payload_power_helpers_r3 as h')
        line=line.replace("O=R/'xu-power-20261112-r1'","O=R/'xu-power-payload-20261113-r3'")
    elif n==8:
        line=' h.launch(Path(__file__).resolve(),R);raise SystemExit(0)'
    elif n==13:
        out.append('h.wait_campaign()')
    elif n==14:
        line='heavy=h.heavy_jobs'
    elif n==42:
        line='  intervals.extend([str(c),str(d)]);duration=d-c;total+=duration'
    elif n==44:
        line=line.replace("'total_principal_ns'","'total_payload_ns'")
    elif n==48:
        continue
    elif n==55:
        out.append(line)
        out.extend(['  while heavy():',"   print('WAIT_EDA_SLOT',flush=True);time.sleep(15)",
                    '  activity_line=h.prepare(entry,O,libs,f)',
                    "  body=body.replace('redirect -file check-power.rpt',activity_line+'redirect -file check-power.rpt',1)+h.reports()"])
        continue
    elif n==56:
        line=line.replace(",body,heavy,2400)",",body,heavy,14400)")
    elif n==60:
        out.append(' h.finalize(entry,run)')
    elif n==62:
        line="print('PAYLOAD_POWER_ALL_THREE_NATIVE_COMPLETE_REVIEW_COVERAGE_AND_UNITS',flush=True)"
    out.append(line)
code='\n'.join(out)+'\n'
tree=ast.parse(code)
parents={}
for node in ast.walk(tree):
    for child in ast.iter_child_nodes(node):parents[child]=node
calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='execute']
assert len(calls)==1
ancestor=calls[0]; ancestors=[]
while ancestor in parents:
    ancestor=parents[ancestor];ancestors.append(ancestor)
withs=[n for n in ancestors if isinstance(n,ast.With)]
assert len(withs)==1 and 'eda.lock' in out[withs[0].lineno-1]
assert 'total_principal_ns' not in code and 'read_vcd ' not in code
target=R/'xu-b41-power-payload-r3.py'
with target.open('x') as f:f.write(code)
metadata={'parent_sha256':hashlib.sha256(source.encode()).hexdigest(),'path':str(target),
          'bytes':len(code.encode()),'sha256':hashlib.sha256(code.encode()).hexdigest(),
          'helper_sha256':hashlib.sha256((R/'xu_payload_power_helpers_r3.py').read_bytes()).hexdigest(),
          'native_run_line':calls[0].lineno,'native_run_inside_lock':True,
          'scope':'Only 12 payload intervals; same original physical netlist, SS libraries, SDC and native reports.',
          'native_timeout_seconds':14400,'old_files_unchanged':True}
with (R/'xu-b41-power-payload-r3.adaptation.json').open('x') as f:json.dump(metadata,f,indent=2)
print(json.dumps(metadata,sort_keys=True))
