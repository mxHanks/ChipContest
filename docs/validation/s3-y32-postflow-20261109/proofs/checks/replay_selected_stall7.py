from pathlib import Path
import hashlib,json,subprocess,sys,time
root=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest');b=root/'build/postflow-20261108';c=b/'selected-full12';out=b/'selected-first-stall7';out.mkdir(exist_ok=False)
sys.path.insert(0,str(root/'tools/scripts'));import e203_soc as soc
r=json.loads((c/'result.json').read_text());cmd=next(s['command'] for s in r['steps'] if s['name']=='task-00/simulation');cmd=[x.replace('+FIRST_SOURCE_STALL=0','+FIRST_SOURCE_STALL=7') for x in cmd]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();start=time.monotonic()
with (out/'simulation.log').open('w') as f: run=subprocess.run(cmd,cwd=out,stdout=f,stderr=subprocess.STDOUT,timeout=180)
receipt={'scope':'fresh process additional request-window check, not main performance comparison','command':cmd,'cwd':str(out),'native_exit':run.returncode,'elapsed_seconds':time.monotonic()-start,'simulator_sha256':sha(cmd[0]),'firmware_image_sha256':sha(c/'accel_soc.verilog'),'log_sha256':sha(out/'simulation.log')}
try:
 assert run.returncode==0
 log=(out/'simulation.log').read_text();s=soc.contract.NICE_STREAM_SCHEDULE;layers=soc.check_log(log,1,s)
 receipt.update(layers=layers,performance=soc.check_performance(log,layers,s),windows=soc.check_task_windows(log,layers),stream=soc.check_stream_activity(log,layers,s),direct=soc.check_direct_activity(log,layers,s))
 assert layers[0]['cycles']==429697+7
 assert receipt['windows'][0]['first_request_wait']==7
 receipt['status']='DEVELOPMENT_BOUNDARY_PASS'
except Exception as exc:receipt.update(status='FAIL',error=str(exc))
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status']);sys.exit(receipt['status']=='FAIL')
