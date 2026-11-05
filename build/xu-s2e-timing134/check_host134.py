#!/usr/bin/env python3
"""Host-only fail-closed checks. No licensed tools or server access."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('xu134',str(HERE/'xu_s2e_timing134.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]

def check(label,condition):
    if not condition:raise AssertionError(label)
    checks.append(label)

def rejected(label,fn):
    try:fn()
    except ValueError:checks.append(label);return
    raise AssertionError('unsafe case accepted: '+label)

maxblock='    Pin: top/U0/ZN\n    max_capacitance 0.010000\n    - Capacitance 0.020000\n'
minblock='    Pin: top/U1/ZN\n    Capacitance 0.000000\n    - min_capacitance 0.000100\n'
check('native verbose cap rows',m.caps(maxblock+minblock)=={'top/U0/ZN':dict(kind='max_capacitance',limit=.01,load=.02),'top/U1/ZN':dict(kind='min_capacitance',limit=.0001,load=0.)})
rejected('duplicate cap pin',lambda:m.caps(maxblock+maxblock))
rejected('changed cap report layout',lambda:m.caps(' max_capacitance 0.01\n'))
rejected('unsafe Tcl literal',lambda:m.q('x} ; exec bad'))
check('no baseline literal cells in cleanup',not m.cleanup_tcl([]).count('initial17'))
check('frozen reset template',m.sha(HERE/'reset134.tcl')==m.RESET)
check('reset exact five original selectors',all(cell+'/'+pin in (HERE/'reset134.tcl').read_text() for cell,pin,_ in m.ENDPOINTS))
check('reset exactly five native pair insertions',(HERE/'reset134.tcl').read_text().count('insert_buffer -inverter_pair -no_of_cells 4')==5)

with tempfile.TemporaryDirectory(prefix='xu134-host-') as td:
    t=Path(td)
    def tsv(name,headers,data):
        with (t/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=headers,delimiter='\t');w.writeheader();w.writerows(data)
    header=['cell','ref','sequential','owner_ref','owner_count','inout_count','output','leaf_connections','all_outputs_unloaded']
    native=[]
    for cell,seq,ref in [('U0','false','INV0_12TR40'),('U1','false','INV0_12TR40'),('U2','true','DRNQV0_12TR40')]:
        native.append(dict(cell='top/'+cell,ref=ref,sequential=seq,owner_ref='OWNER',owner_count='1',inout_count='0',output='top/'+cell+'/ZN',leaf_connections='top/'+cell+'/ZN',all_outputs_unloaded='1'))
    tsv('native-cells.tsv',header,native)
    lib=[]
    for ref,area,cap in [('INV0_12TR40','1.0','.01'),('INV1_12TR40','2.0','.025')]:
        for pin,direction,function in [('I','in',''),('ZN','out','!I')]:
            lib.append(dict(libcell='LIB/'+ref,area=area,dont_use='false',libpin='LIB/'+ref+'/'+pin,direction=direction,function=function,max_capacitance=cap,min_capacitance='.0001'))
    tsv('library-palette.tsv',['libcell','area','dont_use','libpin','direction','function','max_capacitance','min_capacitance'],lib)
    tsv('reset-library.tsv',['libcell','dont_use','libpin','direction'],[])
    (t/'constraints.rpt').write_text(maxblock+minblock+minblock.replace('U1','U2'))
    p=m.plan(t)
    check('fresh native maxcap measured 5pct headroom',p['maxcap'][0]['selected']['libcell']=='LIB/INV1_12TR40')
    check('native nonsequential whole-cell candidate only',[x['cell'] for x in p['dead_initial']]==['top/U1'])
    check('sequential mincap debt retained',[x['cell'] for x in p['unresolved_mincap']]==['top/U2'])
    s=m.sizing_tcl(p['maxcap'])
    check('native alternative compatibility mandatory','get_alternative_lib_cells -quiet $c' in s and 'xu134_lib_signature $old' in s)
    check('no user load or electrical limit fabrication',not any(x in s for x in ['set_load','set_max_capacitance','set_min_capacitance']))
    native[1]['owner_count']='2';tsv('native-cells.tsv',header,native)
    check('shared owner retained',not m.plan(t)['dead_initial'])
    native[1]['owner_count']='1';native[1]['all_outputs_unloaded']='0';tsv('native-cells.tsv',header,native)
    check('loaded cell retained',not m.plan(t)['dead_initial'])
    lib[2]['max_capacitance']='.0209';lib[3]['max_capacitance']='.0209';tsv('library-palette.tsv',['libcell','area','dont_use','libpin','direction','function','max_capacitance','min_capacitance'],lib)
    rejected('insufficient measured cap headroom',lambda:m.plan(t))
    # Test complete generated Tcl command structure without evaluating EDA calls.
    impl=dict(libraries=[dict(path='/frozen/standard.db',role='standard_cell'),dict(path='/frozen/sram.db',role='sram')])
    class Fake:
        @staticmethod
        def memory_checks(impl):return '# host-only memory checker placeholder\n'
    snippets=[m.INVENTORY,m.cleanup_tcl(p['dead_initial']),s,(HERE/'reset134.tcl').read_text(),m.pt_script('/frozen/ownmapped.v',impl,'/frozen/original.sdc','/frozen/scope.tcl',Fake()),m.dc_prefix('/frozen/ownmapped.v',impl,'/frozen/original.sdc','/frozen/scope.tcl','own.svf')]
    complete=t/'complete.tcl';complete.write_text('foreach p $argv {set f [open $p r];set s [read $f];close $f;if {![info complete $s]} {error "incomplete Tcl: $p"}}\nputs XU134_TCL_COMPLETE\n')
    paths=[]
    for i,s in enumerate(snippets):
        path=t/('fragment%d.tcl'%i);path.write_text(s);paths.append(str(path))
    r=subprocess.run(['tclsh',str(complete)]+paths,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    check('generated Tcl complete',r.returncode==0 and r.stdout.strip()=='XU134_TCL_COMPLETE')

# Real archived native report checks parser against report formatting, not S2e.
root=HERE.parents[1]
for rel,expected in [('build/xu-score-resume-20261103/terminal122/full-soc-timing-combined-20261105-116/constraints.rpt',0),('docs/validation/xu-score-s0-soc-20261102/hold-gating-repair-server-20261103/raw/full-soc-gating-margin-repair-20261103-09/constraints.rpt',1460)]:
    path=root/rel
    if path.is_file():check('archived native parser '+path.parent.name,len(m.caps(path.read_text()))==expected)
result=dict(schema='xu-s2e-hostcheck134-v1',status='HOSTCHECKS_PASS_NOT_QUALIFIED',count=len(checks),checks=checks,worker_sha256=m.sha(HERE/'xu_s2e_timing134.py'),reset_sha256=m.RESET,limits='Host parser/guard/Tcl structure checks only. No own89 native diagnostic, DC, PT or FM executed locally.')
print(json.dumps(result,sort_keys=True,indent=2))
