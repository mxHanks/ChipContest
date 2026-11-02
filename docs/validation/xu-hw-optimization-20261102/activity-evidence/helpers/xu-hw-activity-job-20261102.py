#!/usr/bin/env python3
"""Independent true-real1 wrapper activity, with observation-only legacy patches."""
import hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
D=Path.home()/'Desktop'; B=D/'xu-hw-optimization-20261102'; A=B/'activity-01'; new=B/'ChipContest'; old=D/'xu-fw-optimization-20261102/ChipContest'
def run(cmd,cwd=None):subprocess.check_call(cmd,cwd=str(cwd) if cwd else None)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def patch(p,a,b):
 t=p.read_text()
 if t.count(a)!=1:raise ValueError('patch count: '+str(p)+' '+a)
 p.write_text(t.replace(a,b))
def query(c,p):return subprocess.check_output(c,cwd=str(p)).decode().strip()
def save(s):(A/'job-state.json').write_text(json.dumps(s,indent=2,sort_keys=True)+'\n')
if sys.argv[1]=='start':
 A.mkdir(exist_ok=False)
 with (A/'driver.log').open('x') as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'execute'],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('STARTED_ACTIVITY pid='+str(p.pid),flush=True)
elif sys.argv[1]=='execute':
 s=dict(status='RUNNING',stage='setup',started_epoch=time.time());save(s)
 try:
  legacy=A/'old-RTL-clone'
  run(['git','clone','--no-hardlinks','--no-checkout',str(old),str(legacy)])
  run(['git','checkout','8a7640787423a73a0751454de47893406f85e604'],legacy)
  sub=legacy/'third-party/e203_hbirdv2';sub.rmdir()
  run(['git','clone','--no-hardlinks','--no-checkout',str(old/'third-party/e203_hbirdv2'),str(sub)])
  run(['git','checkout','e36d34a52e6eef93fd0bdfed1b13009e1056bea3'],sub);run(['git','submodule','init'],legacy)
  tb=legacy/'tests/e203/tb_accel_soc.sv';runner=legacy/'tools/scripts/e203_soc.py';orig={str(p.relative_to(legacy)):sha(p) for p in [tb,runner]}
  patch(tb,'      if (in_window) begin','      if (dumpwave==2 && !perf_active && in_window) begin\n        $dumpon;\n        $display("ACTIVITY_BEGIN layer=%0d time=%0t",layer,$time);\n      end\n      if (in_window) begin')
  patch(tb,'if (shared_retire && final_write_pending) perf_active=0;','if (shared_retire && final_write_pending) begin\n          perf_active=0;\n          if (dumpwave==2) begin\n            $display("ACTIVITY_END layer=%0d time=%0t",layer,$time);\n            $dumpoff;\n          end\n        end')
  patch(tb,'      $dumpvars(0,tb_accel_soc);','      if (dumpwave==2) begin\n        $dumpvars(0,`ACCEL);\n        $dumpoff;\n      end else $dumpvars(0,tb_accel_soc);')
  patch(runner,"    parser.add_argument('--waves',action='store_true')","    parser.add_argument('--waves',action='store_true')\n    parser.add_argument('--accel-waves',action='store_true')")
  patch(runner,"    out=(args.out or ROOT/", "    trace_enabled = args.waves or args.accel_waves\n    out=(args.out or ROOT/")
  patch(runner,'build_key(report,selected_sim,args.waves)','build_key(report,selected_sim,trace_enabled)')
  patch(runner,'build_simulator(selected_sim,cache,filelist,includes,args.waves,out)','build_simulator(selected_sim,cache,filelist,includes,trace_enabled,out)')
  patch(runner,'int(args.waves)','2 if args.accel_waves else int(args.waves)')
  (A/'legacy-observation.patch').write_bytes(subprocess.check_output(['git','diff','--','tests/e203/tb_accel_soc.sv','tools/scripts/e203_soc.py'],cwd=str(legacy)))
  (A/'observation-manifest.json').write_text(json.dumps(dict(scope='legacy observer and wave CLI only; RTL/firmware unchanged',original=orig,patched={str(p.relative_to(legacy)):sha(p) for p in [tb,runner]},legacy_commit=query(['git','rev-parse','HEAD'],legacy),legacy_e203_commit=query(['git','rev-parse','HEAD'],sub)),indent=2,sort_keys=True)+'\n')
  campaign=json.loads((B/'xu-vcs-hw-campaign-01/experiments.json').read_text());config=campaign['selected']['configuration']
  configs=[('baseline',legacy,dict(schedule='bias-dtcm',optimization='-O2',experiment='both-unroll-no-masks')),('candidate',new,config)]
  for name,repo,c in configs:
   s['stage']=name+'-vcs';save(s)
   cmd=[sys.executable,'tools/scripts/e203_soc.py','--mode','real','--tasks','1','--sim','vcs','--cross-prefix',str(D/'xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-'),'--firmware-schedule',c['schedule'],'--firmware-opt='+c['optimization'],'--firmware-experiment',c['experiment'],'--accel-waves','--out',str(A/name)]
   with (A/(name+'-driver.log')).open('x') as f:
    p=subprocess.run(cmd,cwd=str(repo),stdout=f,stderr=subprocess.STDOUT,timeout=7200)
   r=json.loads((A/name/'result.json').read_text())
   if p.returncode or r['status']!='PASS':raise ValueError(name+' activity simulation failed: '+str(r.get('error')))
   ref=json.loads((D/'xu-fw-optimization-20261102/xu-vcs-campaign-01/acceptance/real12/result.json' if name=='baseline' else B/'xu-vcs-hw-campaign-01/acceptance/real12/result.json').read_text())
   if r['layers'][0]!=ref['layers'][0] or r['firmware_image_sha256']!=ref['firmware_image_sha256'] or r['firmware_elf_sha256']!=ref['firmware_elf_sha256']:raise ValueError(name+' wave changed cycles, counters or image')
   s.setdefault('cases',{})[name]=dict(status='PASS',command=cmd,cycles=r['layers'][0]['cycles'],image=r['firmware_image_sha256'],raw_vcd_sha256=sha(A/name/'tb_accel_soc.vcd'),raw_vcd_bytes=(A/name/'tb_accel_soc.vcd').stat().st_size);save(s)
   run([sys.executable,str(D/'xu-hw-scale-vcd-20261102.py'),str(A/name/'tb_accel_soc.vcd'),'--simulation-log',str(A/name/'simulation.log'),'--out',str(A/name/'activity-150MHz.vcd.gz'),'--metadata',str(A/name/'activity-scale.json')])
  s.update(status='PASS',stage='complete')
 except Exception as e:s.update(status='FAIL',error=str(e));raise
 finally:s['finished_epoch']=time.time();save(s)
 print('ACTIVITY_'+s['status'],flush=True)
