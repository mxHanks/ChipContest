import hashlib, importlib.util, json, pathlib, subprocess, sys, time
root=pathlib.Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest')
sys.path.insert(0,str(root/'tools/scripts'))
import e203_soc as soc
campaign=root/'build/writeback-v2-20261108/direct-full12'
out=root/'build/writeback-v2-20261108/direct-first-stall7'
out.mkdir(exist_ok=False)
data=json.loads((campaign/'result.json').read_text())
command=next(s['command'] for s in data['steps'] if s['name']=='task-00/simulation')
command=[arg.replace('+FIRST_SOURCE_STALL=0','+FIRST_SOURCE_STALL=7') for arg in command]
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
receipt=dict(scope='additional fresh-process boundary check; not primary comparison',command=command,cwd=str(out),simulator_sha256=sha(command[0]),firmware_image_sha256=sha(campaign/'accel_soc.verilog'),requested_first_stall=7)
start=time.monotonic()
with (out/'simulation.log').open('w') as log:
 result=subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=180)
receipt.update(native_exit=result.returncode,elapsed_seconds=time.monotonic()-start,log_sha256=sha(out/'simulation.log'))
try:
 assert result.returncode==0, 'nonzero simulator exit'
 log=(out/'simulation.log').read_text()
 schedule=soc.contract.NICE_DIRECT_SCHEDULE
 layers=soc.check_log(log,1,schedule)
 receipt['layers']=layers
 for key,fn in [('performance',soc.check_performance),('autogroup',soc.check_autogroup_activity),('results',soc.check_result_activity),('weights',soc.check_weight_activity),('nice',soc.check_nice_activity),('direct',soc.check_direct_activity),('read_pop',soc.check_read_pop_activity)]:
  receipt[key]=fn(log,layers,schedule)
 receipt['windows']=soc.check_task_windows(log,layers)
 assert layers[0]['cycles']==data['task_results'][0]['cycles']+7
 assert receipt['windows'][0]['first_request_wait']==7
 receipt['status']='DEVELOPMENT_BOUNDARY_PASS'
except Exception as exc:
 receipt['status']='FAIL'
 receipt['error']=str(exc)
finally:
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(receipt['status'],receipt.get('layers'),flush=True)
if receipt['status']=='FAIL': sys.exit(1)
