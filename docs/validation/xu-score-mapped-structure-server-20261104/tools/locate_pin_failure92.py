from pathlib import Path
import importlib.util,hashlib,json,os,sys,subprocess,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'s2c-native-pin-failure-20261104-92';T=Path.home()/'Desktop/xu_extract_pt_pin_reports74.py';R=B/'s2c-full-soc-power12-20261104-57'
if len(sys.argv)==1:
 O.mkdir(exist_ok=False)
 with(O/'driver.log').open('xb')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('PIN_FAILURE92_STARTED',p.pid,flush=True);sys.exit(0)
s=dict(status='RUNNING_READ_ONLY',pid=os.getpid(),started_epoch=time.time())
def save():(O/'state.json').write_text(json.dumps(s,sort_keys=True,indent=2)+'\n')
save()
try:
 assert hashlib.sha256(T.read_bytes()).hexdigest()=='69bc0012acb3dffac04f752ab5c39f53d7326cfd26758333e109dfa835ebe1cc'
 sp=importlib.util.spec_from_file_location('xu_pin74',str(T));m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
 ep=R/'execution.json';assert m.identity(ep)['sha256']==m.EXECUTION_SHA;e=json.loads(ep.read_text());p=R/'task_00/sram-pins-before.rpt';rec=e['artifacts']['task_00/sram-pins-before.rpt'];actual=m.identity(p);assert actual['sha256']==rec['sha256']and actual['bytes']==rec['bytes'];s.update(original_report_actual=actual,original_report_recorded=rec,original_execution=m.identity(ep));h=hashlib.sha256();count=0;previous=None;failure=None
 with p.open('rb')as f:
  for raw,start in m.block_reader(f,h):
   count+=1
   try:row=m.parse_block(raw,start)
   except Exception as error:
    failure=dict(block_index=count,report_byte_start=start,report_byte_end=start+len(raw),block_bytes=len(raw),block_sha256=hashlib.sha256(raw).hexdigest(),pin_marker=raw.splitlines()[0].decode('utf-8',errors='replace'),error=type(error).__name__+': '+str(error));(O/'first-failing-block.original.txt').write_bytes(raw)
    if previous is not None:(O/'previous-good-block.original.txt').write_bytes(previous)
    break
   previous=raw
 assert failure is not None
 s.update(status='LOCATED_ORIGINAL_PARSE_FAILURE_NOT_FIXED_NOT_QUALIFIED',failure=failure,source_current=m.identity(p));assert s['source_current']==actual
except BaseException as e:s.update(status='FAIL_LOCATOR',error=type(e).__name__+': '+str(e));raise
finally:s['finished_epoch']=time.time();save()
print(json.dumps(s,sort_keys=True),flush=True)
