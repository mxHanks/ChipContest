from pathlib import Path
import hashlib,subprocess,json,sys
B=Path.home()/'Desktop/xu-score-optimization-20261102';T=Path.home()/'Desktop/xu_extract_pt_pin_reports74.py';O=B/'s2c-native-pin-stream-20261104-88';L=B/'s2c-native-pin-launch-20261104-88';L.mkdir(exist_ok=False)
assert not O.exists();assert hashlib.sha256(T.read_bytes()).hexdigest()=='69bc0012acb3dffac04f752ab5c39f53d7326cfd26758333e109dfa835ebe1cc'
cmd=[sys.executable,str(T),'extract','--campaign',str(B/'s2c-full-soc-power12-20261104-57'),'--out',str(O)]
with(L/'driver.log').open('xb')as f:p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
s=dict(status='LAUNCHED_NOT_QUALIFIED',pid=p.pid,command=cmd);(L/'state.json').write_text(json.dumps(s,sort_keys=True,indent=2)+'\n');print(json.dumps(s,sort_keys=True))
