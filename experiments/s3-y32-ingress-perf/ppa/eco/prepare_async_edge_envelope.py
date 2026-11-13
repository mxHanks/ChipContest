#!/usr/bin/env python3
"""Seal reset/GPIO tools from an existing checkout or this standalone source bundle."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
FILES=['common.tcl','dc_library_proof.tcl','dc_apply.tcl','run_stage.py','plan.py','check_buffer_equivalence.py','parallel_reset_gpio_helpers.tcl','pt_async_edge_envelope.tcl','run_async_edge_envelope.py','prepare_async_edge_envelope.py']
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 s=Path(__file__).resolve().parent;origins={n:s/n for n in FILES}
 origins['development_controls.py']=s/'development_controls.py' if (s/'development_controls.py').is_file() else s.parent/'run_once.py'
 origins['profiles.py']=s/'profiles.py' if (s/'profiles.py').is_file() else s.parent/'profiles.py'
 for n,f in origins.items():
  raw=f.read_text()
  if n.endswith('.py'):compile(raw,n,'exec')
  if n.endswith('.tcl'):
   r=subprocess.run(['tclsh'],input='set f [open {'+str(f)+'} r]\nset s [read $f]\nclose $f\nif {![info complete $s]} {exit 2}\n',text=True,capture_output=True)
   if r.returncode:raise ValueError('incomplete Tcl: '+n)
 a.out.mkdir(mode=0o700,parents=True,exist_ok=False)
 for n,f in origins.items():shutil.copyfile(f,a.out/n)
 manifest={n:hashlib.sha256((a.out/n).read_bytes()).hexdigest()for n in origins}
 (a.out/'package-files.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 print(json.dumps(dict(status='SEALED_RESET_GPIO_TOOLS_NOT_NATIVE_EXECUTED',files=len(manifest),package_sha256=hashlib.sha256((a.out/'package-files.json').read_bytes()).hexdigest())))
if __name__=='__main__':main()
