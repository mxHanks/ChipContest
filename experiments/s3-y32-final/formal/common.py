"""Offline final-profile source/map checks. No EDA, network or library access."""
import hashlib,importlib.util,json,re,sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PROFILE='sysbus32-dma4-storage-sram-374-final'
TOP='xu_soc_sysbus32_ppa_top'
DEFINES=['SYNTHESIS','DISABLE_SV_ASSERTION=1','XU_MATRIX_DMA','XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM','XU_MATRIX_STORAGE_SRAM']
REPORTS=['resources','assumptions','unmatched','matched','failing','aborted','unverified','dont_verify','constants','unread','black_boxes','guidance','hdlin_mismatches']
PORTS={'Q':['output',16],'CLK':['input',1],'CEN':['input',1],'WEN':['input',16],'GWEN':['input',1],'A':['input',10],'D':['input',16],'EMA':['input',3],'EMAW':['input',2],'RET1N':['input',1]}
GEOMETRY={'itcm':32,'dtcm':32,'shared':256,'weights':16,'bias':1,'x':16,'result':21}
COMMANDS=['set_host_options','report_host_options','read_db','read_sverilog','read_verilog','set_top','set_svf','match','verify','report_unmatched_points','report_failing_points']
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def record(p):return {'sha256':sha(p),'bytes':Path(p).stat().st_size}
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def safe(p):
 need(not any(x in str(p) for x in '{}\\\r\n\t'),'unsafe Tcl path');return '{'+str(p)+'}'
def package_check(package,cpu=False):
 p=Path(package).resolve()
 # Use sealed source-package controls; identity is checked before importing it.
 pins=json.loads((p/'package-files.json').read_text())
 need('controls.py' in pins and sha(p/'controls.py')==pins['controls.py'],'unsealed PPA control')
 for n,h in pins.items():
  q=Path(n);need(not q.is_absolute() and '..' not in q.parts and '\\' not in n,'unsafe package entry')
  need((p/q).is_file() and not (p/q).is_symlink() and sha(p/q)==h,'package input drift:'+n)
 spec=importlib.util.spec_from_file_location('final_fm_sealed_ppa_controls',p/'controls.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 _,m=mod.check_inputs(p)
 need(m['hardware_profile']==PROFILE and m['top']==TOP and m['defines']==DEFINES and m['source_count']==159,'requires final DMA4/storage21 sealed159 source profile')
 need(m['compile_policy']['own_svf']=='final.svf','must use own final.svf')
 sm=json.loads((p/'source-manifest.json').read_text());names=(p/'rtl.f').read_text().splitlines()
 need(names==[r['path'] for r in sm['ordered_compile_sources']],'formal compile order mismatch')
 need(all('generic_ramsp' not in n for n in names),'no simulation SRAM models allowed')
 cpu_binding=mod.check_cpu_full12(p) if cpu else None
 return m,sm,cpu_binding

def native_check(package,native):
 p,n=Path(package).resolve(),Path(native).resolve();m,_,cpu=package_check(p,cpu=True)
 r=json.loads((n/'execution.json').read_text())
 need(r['schema']=='sysbus32-same-source-dc-execution-v1' and r['hardware_profile']==PROFILE and r['top']==TOP and r['defines']==DEFINES,'wrong DC profile/top/defines')
 need(r['manifest_sha256']==sha(p/'package-files.json'),'map came from different package')
 need(r['status']=='SYNTHESIS_COMPLETE_NOT_QUALIFIED' and r['returncode']==0 and r['completion_marker'] is True and r['source_drift']==[] and r['native_tool_errors']==[] and not r['missing_required_outputs'],'DC collection incomplete')
 toolchain=json.loads((p/'toolchain.json').read_text());need(r['libraries']==toolchain['libraries'],'DC library identities differ')
 outputs={}
 for name in ['mapped.v','mapped.ddc','final.svf','leaf-inventory.tsv']:
  need(name in r['outputs'] and record(n/name)==r['outputs'][name] and (n/name).stat().st_size>0,'own native output identity:'+name)
  outputs[name]=record(n/name)
 return dict(directory=str(n),execution=record(n/'execution.json'),outputs=outputs,cpu_binding=cpu)

def probe_sections(text):
 begin=re.findall(r'^XU_FINAL374_FM_API_BEGIN\t([^\t\n]+)\t([^\t\n]+)$',text,re.M)
 ends=re.findall(r'^XU_FINAL374_FM_API_END\t([^\t\n]+)\t([^\t\n]+)\t([01])\t([0-9]+)$',text,re.M)
 need(len(begin)==len(ends)>0 and len(set(begin))==len(begin),'probe markers incomplete/duplicated')
 need(begin==[(k,n) for k,n,_,_ in ends],'probe begin/end order differs')
 need(len(re.findall(r'^XU_FINAL374_FM_API_DOCUMENTATION_COLLECTED\tmissing=\d+$',text,re.M))>=1,'probe terminal marker absent')
 result={}
 for k,n,e,rc in ends:
  body=re.search(r'^XU_FINAL374_FM_API_BEGIN\t'+re.escape(k)+r'\t'+re.escape(n)+r'\n(.*?)^XU_FINAL374_FM_API_END\t'+re.escape(k)+r'\t'+re.escape(n)+r'\t',text,re.M|re.S)[1]
  errors=re.findall(r'^(?:Error:|Fatal:).*$',body,re.M)
  result[k,n]=dict(exists=e=='1',returncode=int(rc),native_errors=errors)
 return result

def api_check(contract_path,adapter_path,probe_path):
 c=json.loads(Path(contract_path).read_text());need(c['schema']=='final374-fm-native-api-contract-v1' and c['status']=='REVIEWED_NATIVE_API_ADAPTER' and c['hardware_profile']==PROFILE,'unreviewed API contract')
 need(c['adapter_sha256']==sha(adapter_path) and c['probe_log_sha256']==sha(probe_path),'API adapter/probe identity differs')
 sections=probe_sections(Path(probe_path).read_text())
 need(c['max_cores']==2 and c['all_report_signatures_reviewed'] is True and c['hdl_assumptions_explicitly_reviewed'] is True and len(c['reviewer'].strip())>5,'resource/assumption/API review incomplete')
 need(set(c['reports'])==set(REPORTS),'all report roles must be collected')
 names=c['documented_commands'];need(set(COMMANDS)<=set(names),'core native API evidence missing')
 for name in names:
  for kind in ['help','man']:
   need((kind,name) in sections and sections[kind,name]['exists'] and sections[kind,name]['returncode']==0 and not sections[kind,name]['native_errors'],'unsupported/undocumented native API:'+kind+' '+name)
 need(c['launcher']['native_version'] and len(c['launcher']['sha256'])==64,'actual FM launcher identity required')
 need(c['launcher'].get('historical_hint_only',False) is False,'historical launcher hint has not been replaced by current native identity')
 versions=re.findall(r'^\s*Version (\S+)',Path(probe_path).read_text(),re.M)
 need(versions and versions[0]==c['launcher']['native_version'],'API contract version is not actual native probe version')
 need(Path(c['launcher']['path']).name=='fm_shell','retain actual vendor entry name')
 need(c['required_attributes']=={'cell':['full_name','ref_name'],'pin':['full_name','direction']},'actual required FM attributes not specified')
 for cls,names in c['required_attributes'].items():
  for name in names:
   key=('attribute_help',cls+'.'+name)
   need(key in sections and sections[key]['returncode']==0 and not sections[key]['native_errors'],'native attribute documentation missing:'+str(key))
   body=re.search(r'^XU_FINAL374_FM_API_BEGIN\tattribute_help\t'+re.escape(cls+'.'+name)+r'\n(.*?)^XU_FINAL374_FM_API_END',Path(probe_path).read_text(),re.M|re.S)[1]
   need(re.search(r'^\s*'+re.escape(name)+r'\s+#',body,re.M),'attribute help did not actually define:'+cls+'.'+name)
 text=Path(adapter_path).read_text()
 need('UNCONFIRMED_NATIVE_API' not in text and 'set ::final_fm_native_adapter_pending 1' not in text,'adapter template cannot execute')
 for proc in ['final_fm_configure_resources','final_fm_configure_assumptions','final_fm_collect','final_fm_assert_boundaries']:
  need(re.search(r'\bproc\s+'+proc+r'\s+\{',text),'missing adapter procedure:'+proc)
 need(not any(x in text for x in ['set_false_path','set_multicycle_path','set_dont_verify','set_black_box','set_user_match','set_constant','hdlin_unresolved_modules black_box']),'adapter may not hide logic or invent matching')
 return c
