#!/usr/bin/env python3
"""Seal a small read-only native clock proof sidecar, without changing r7 tools."""
import argparse,csv,gzip,hashlib,json,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
from prepare import FILES
from clock_persisted_contract import PLAN_SCHEMA,ORIGINAL_MAP_SHA,require


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--clock-package',type=Path,required=True)
    p.add_argument('--baseline-pt-dir',type=Path,required=True);a=p.parse_args()
    src=Path(__file__).resolve().parent;cp=a.clock_package.resolve();seal=json.loads((cp/'package-files.json').read_text())
    for name,digest in seal.items():require(hashlib.sha256((cp/name).read_bytes()).hexdigest()==digest,'clock package drift: '+name)
    raw=gzip.decompress((cp/'clock-tree-targets.json.gz').read_bytes());clock=json.loads(raw)
    require(clock.get('mapped_sha256')==ORIGINAL_MAP_SHA and len(clock['groups'])==1560 and
        clock['excluded_structurally_dead_boundary_groups']==['g0032','g0034','g0052','g0546']and clock['predicted_root_flattened_sink_count']==18,'only exact r7 positive-load clock plan accepted')
    pt=a.baseline_pt_dir.resolve();receipt=json.loads((pt/'execution.json').read_text());name='reports/clock_endpoints.tsv';f=pt/name
    require(receipt['outputs'][name]==dict(sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size),'original macro clock catalogue unbound')
    rows=list(csv.DictReader(f.read_text().splitlines(),delimiter='\t'));macros=sorted(r['pin'][:-4]for r in rows if r['kind']=='SRAM'and r['pin'].endswith('/CLK'))
    require(len(macros)==len(set(macros))==353,'exact original353 native SRAM catalogue required')
    plan=dict(schema=PLAN_SCHEMA,original_mapped_sha256=ORIGINAL_MAP_SHA,clock_package_sha256=hashlib.sha256((cp/'package-files.json').read_bytes()).hexdigest(),clock_plan_sha256=hashlib.sha256(raw).hexdigest(),
        root_driver=clock['root_driver'],original_macro_instances=macros,original_macro_clocks={r['pin']:sorted(r['clocks'].split())for r in rows if r['kind']=='SRAM'},original_macro_catalogue_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
        baseline_pt_execution_sha256=hashlib.sha256((pt/'execution.json').read_bytes()).hexdigest(),
        clock_buffers=[(g['owner']+'/'if g['owner']else'')+g['new_cell_name']for g in clock['groups']],mutation_authorized=False,qualification=False)
    origins={name:src/name for name in FILES}
    for name in ['prepare_clock_persisted.py','run_clock_persisted.py','pt_clock_persisted.tcl','clock_persisted_contract.py']:origins[name]=src/name
    origins['development_controls.py']=src.parent/'run_once.py';origins['profiles.py']=src.parent/'profiles.py'
    for name,path in origins.items():
        raw=path.read_text()
        if name.endswith('.py'):compile(raw,name,'exec')
        if name.endswith('.tcl'):
            r=subprocess.run(['tclsh'],input='set f [open {'+str(path)+'} r]\nset x [read $f]\nclose $f\nif {![info complete $x]} {exit 2}\n',text=True,capture_output=True);require(r.returncode==0,'Tcl incomplete: '+name)
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name,path in origins.items():shutil.copyfile(path,a.out/name)
    (a.out/'clock-persisted-plan.json.gz').write_bytes(gzip.compress(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()+b'\n',mtime=0))
    seal={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in sorted(a.out.iterdir())if f.is_file()}
    (a.out/'package-files.json').write_text(json.dumps(seal,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status='SEALED_READ_ONLY_PERSISTED_CLOCK_DIAGNOSTICS_NOT_NATIVE_EXECUTED',out=str(a.out),package_sha256=hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest(),clock_buffers=1560,original_SRAM=353,plan_bytes=(a.out/'clock-persisted-plan.json.gz').stat().st_size),sort_keys=True))


if __name__=='__main__':main()
