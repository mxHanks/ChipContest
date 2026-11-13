#!/usr/bin/env python3
"""Seal exact final-prune zero-clock-buffer proof and cleanup tools, no EDA."""
import argparse,gzip,hashlib,json,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
from prepare import FILES
from run_clock_cleanup import static_plan,emit,require,sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['out','source-map','source-review','clock-persisted-package']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();src=Path(__file__).resolve().parent;cp=a.clock_persisted_package.resolve()
    entries=json.loads((cp/'package-files.json').read_text())
    for n,d in entries.items():require(sha(cp/n)==d,'persisted clock package drift')
    clock=json.loads(gzip.decompress((cp/'clock-persisted-plan.json.gz').read_bytes()));review=json.loads(a.source_review.read_text());plan=static_plan(a.source_map,clock,review)
    origins={n:src/n for n in FILES}
    for n in ['run_clock_cleanup.py','prepare_clock_cleanup.py','dc_clock_cleanup.tcl','pt_clock_cleanup_reload.tcl','clock_persisted_contract.py','run_clock_persisted.py']:origins[n]=src/n
    origins['development_controls.py']=src.parent/'run_once.py';origins['profiles.py']=src.parent/'profiles.py'
    for n,f in origins.items():
        text=f.read_text()
        if n.endswith('.py'):compile(text,n,'exec')
        if n.endswith('.tcl'):
            r=subprocess.run(['tclsh'],input='set f [open {'+str(f)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True);require(r.returncode==0,'Tcl incomplete: '+n)
    a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for n,f in origins.items():shutil.copyfile(f,a.out/n)
    shutil.copyfile(cp/'clock-persisted-plan.json.gz',a.out/'clock-persisted-plan.json.gz')
    for name,j in [('clock-cleanup-plan.json.gz',plan),('zero-clock-review.json.gz',review)]:
        (a.out/name).write_bytes(gzip.compress(json.dumps(j,sort_keys=True,separators=(',',':')).encode()+b'\n',mtime=0))
    seal={q.name:sha(q)for q in sorted(a.out.iterdir())if q.is_file()};(a.out/'package-files.json').write_text(json.dumps(seal,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(status='SEALED_EXACT34_NEW_CLOCK_CLEANUP_NOT_NATIVE_EXECUTED',out=str(a.out),package_sha256=sha(a.out/'package-files.json'),source_mapped_sha256=plan['source_map_sha256'],initial_zero=34,total_removed=len(plan['removed']),waves=len(plan['waves']),remaining=len(plan['remaining_clock_outputs']),root_fanout=len(plan['root_sinks']),preserved_SRAM=353),sort_keys=True))


if __name__=='__main__':main()
