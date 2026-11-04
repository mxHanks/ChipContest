from pathlib import Path
import hashlib,json,tarfile,os,re,sys,subprocess,time
B=Path.home()/'Desktop/xu-score-optimization-20261102';O=B/'standard-cell-model-private-20261104-90';S=Path('/storage1/admin_public_dir/SMIC40_2025/S40.tar.gz');P='S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/verilog/';names=[P+'scc40nll_vhsc40_rvt'+x+'.v'for x in ['','_neg','_neg_pg','_pg']]
if len(sys.argv)==1:
 O.mkdir(mode=0o700,exist_ok=False)
 with(O/'driver.log').open('xb')as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'run'],stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('MODEL90_STARTED',p.pid,flush=True);sys.exit(0)
state=dict(status='RUNNING_PRIVATE_EXTRACTION',pid=os.getpid(),started_epoch=time.time(),scope='Extract four exact vendor Verilog members for private same-library mapped simulation; source bodies not exported',models=[])
def save():
 t=O/'state.tmp';t.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');os.replace(str(t),str(O/'state.json'))
def stamp(p):
 s=p.stat();return dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino)
save()
try:
 pre=stamp(S);state['archive']=dict(path=str(S),stat_before=pre);save()
 with tarfile.open(str(S),'r|gz')as tar:
  for member in tar:
   if member.name not in names:continue
   assert member.isfile()and member.size<80000000 and member.name not in [x['archive_member']for x in state['models']]
   data=tar.extractfile(member).read();assert len(data)==member.size;p=O/Path(member.name).name
   with p.open('xb')as f:f.write(data)
   p.chmod(0o600);text=data.decode('latin1');row=dict(archive_member=member.name,path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),module_names=sorted(set(re.findall(r'(?m)^\s*module\s+([\w$]+)',text))),primitive_names=sorted(set(re.findall(r'(?m)^\s*primitive\s+([\w$]+)',text))),include_dependencies=sorted(set(re.findall(r'`include\s+"([^"]+)"',text))),conditional_symbols=sorted(set(re.findall(r'`(?:ifdef|ifndef)\s+([\w$]+)',text))))
   state['models'].append(row);save();print('MODEL90_MEMBER',p.name,row['bytes'],row['sha256'],flush=True)
   if len(state['models'])==len(names):break
 post=stamp(S);assert pre==post and len(state['models'])==4;state['archive']['stat_after']=post;state['status']='EXTRACTED_FOUR_VENDOR_MODELS_NOT_SIMULATED'
except BaseException as e:state.update(status='FAIL_EXTRACTION',error=type(e).__name__+': '+str(e));raise
finally:state['finished_epoch']=time.time();save()
print('MODEL90_DONE',state['status'],flush=True)
