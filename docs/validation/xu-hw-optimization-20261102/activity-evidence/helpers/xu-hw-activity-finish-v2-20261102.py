#!/usr/bin/env python3
"""Audit activity images/work, complete missing candidate, and compute paired pre-layout power."""
import hashlib,json,os,re,signal,shutil,subprocess,sys,time
from pathlib import Path
D=Path.home()/'Desktop';B=D/'xu-hw-optimization-20261102';A=B/'activity-02';O=B/'activity-power-02';P=B/'ppa';C=B/'xu-vcs-hw-campaign-01';new=B/'ChipContest'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(j):(O/'job-state.json').write_text(json.dumps(j,indent=2,sort_keys=True)+'\n')
def run(c,cwd=None):subprocess.check_call(c,cwd=str(cwd) if cwd else None)
if sys.argv[1]=='start':
 O.mkdir(exist_ok=False)
 with (O/'driver.log').open('x') as f:p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'execute'],stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 print('STARTED_ACTIVITY_POWER pid='+str(p.pid),flush=True)
elif sys.argv[1]=='execute':
 s=dict(status='RUNNING',stage='wait-for-activity-02',started_epoch=time.time());save(s)
 try:
  deadline=time.time()+7200
  candidate=A/'candidate'
  while not (candidate/'result.json').exists():
   if time.time()>deadline:raise ValueError('candidate VCS timeout')
   time.sleep(2)
  candidate_result=json.loads((candidate/'result.json').read_text())
  candidate_reference=json.loads((C/'acceptance/real12/result.json').read_text())
  if candidate_result['status']!='PASS' or candidate_result['layers']!=[candidate_reference['layers'][0]] or candidate_result['firmware_image_sha256']!=candidate_reference['firmware_image_sha256']:
   raise ValueError('candidate real1 numerical/image/counter gate failed before stopping derived work')
  stop=dict(reason='replace redundant slow per-line gzip derivative with independently tested buffered helper; completed numerical VCS remains PASS',signal='SIGTERM only to original candidate scaling child',candidate_result_sha256=sha(candidate/'result.json'),original_scaler_sha256=sha(D/'xu-hw-scale-vcd-20261102.py'),buffered_scaler_sha256=sha(D/'xu-hw-scale-vcd-buffered-20261102.py'),recorded_epoch=time.time(),process=None)
  for attempt in range(20):
   for path in Path('/proc').iterdir():
    if not path.name.isdigit():continue
    try:
     args=(path/'cmdline').read_bytes().decode().strip('\0').split('\0')
     if str(D/'xu-hw-scale-vcd-20261102.py') not in args or str(candidate/'tb_accel_soc.vcd') not in args:continue
     fds={}
     for number in ['3','4']:
      try:fds[number]=dict(path=os.readlink(str(path/'fd'/number)),info=(path/'fdinfo'/number).read_text())
      except OSError:pass
     stop['process']=dict(pid=int(path.name),argv=args,fds=fds,ps=subprocess.check_output(['ps','-p',path.name,'-o','pid,etime,time,pcpu,args']).decode())
     os.kill(int(path.name),signal.SIGTERM)
     break
    except (OSError,UnicodeDecodeError):pass
   if stop['process'] is not None or (candidate/'activity-scale.json').exists():break
   time.sleep(.5)
  (O/'controlled-stop.json').write_text(json.dumps(stop,indent=2,sort_keys=True)+'\n')
  for attempt in range(120):
   previous=json.loads((A/'job-state.json').read_text())
   old_power=json.loads((B/'activity-power-01/job-state.json').read_text())
   if previous['status']!='RUNNING' and old_power['status']!='RUNNING':break
   time.sleep(1)
  if previous['status']=='RUNNING':raise ValueError('original supervisor did not settle after controlled derivative stop')
  s['prior_activity_job']=previous;s['controlled_stop']=stop;save(s)
  scopes='tb_accel_soc/dut/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'
  review=dict(schema='xu-workload-activity-power-v1',scope='paired wrapper averaged RTL activity mapped to fixed SS netlist; pre-layout estimate, not measured silicon power',limitations=['No extracted RC/SPEF or wire-load','Library area units unconfirmed','SRAM experimental adapter qualification not established','Hold violations and partially untested timing paths remain','RTL name mapping and propagated/default activity coverage reported; not gate-level measured power','Timestamp-derived 150MHz from original250MHz event sequence; all non-timestamp lines preserved'],prior_activity_job_state=previous,controlled_stop=stop,helper_sha256={str(Path(__file__).resolve()):sha(Path(__file__)),str(D/'xu-hw-scale-vcd-buffered-20261102.py'):sha(D/'xu-hw-scale-vcd-buffered-20261102.py')},cases={})
  campaign=json.loads((C/'experiments.json').read_text());config=campaign['selected']['configuration']
  for name,sourcefolder in [('baseline','baseline-ss-01'),('candidate','candidate-ss-02')]:
   wave=A/name
   if not (wave/'result.json').exists():
    if name=='baseline':raise ValueError('baseline VCS missing')
    wave=O/'candidate-vcs'
    cmd=[sys.executable,'tools/scripts/e203_soc.py','--mode','real','--tasks','1','--sim','vcs','--cross-prefix',str(D/'xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-'),'--firmware-schedule',config['schedule'],'--firmware-opt='+config['optimization'],'--firmware-experiment',config['experiment'],'--accel-waves','--out',str(wave)]
    s['stage']='candidate-vcs';save(s)
    with (O/'candidate-vcs-driver.log').open('x') as f:p=subprocess.run(cmd,cwd=str(new),stdout=f,stderr=subprocess.STDOUT,timeout=7200)
    if p.returncode:raise ValueError('candidate activity VCS process failed')
   r=json.loads((wave/'result.json').read_text());refpath=D/'xu-fw-optimization-20261102/xu-vcs-campaign-01/acceptance/real12/result.json' if name=='baseline' else C/'acceptance/real12/result.json';ref=json.loads(refpath.read_text())
   if r['status']!='PASS' or r['layers']!=[ref['layers'][0]] or r['firmware_image_sha256']!=ref['firmware_image_sha256']:raise ValueError(name+' wave work/counters/cycles/image mismatch')
   if sha(wave/'accel_soc')!=r['firmware_elf_sha256']:raise ValueError('current ELF differs from current self hash')
   if sha(wave/'simulation.log')!=r['log_sha256']['simulation.log']:raise ValueError('simulation log hash mismatch')
   scale=wave/('activity-scale.json' if name=='baseline' else 'activity-buffered-scale.json');vcd=wave/('activity-150MHz.vcd.gz' if name=='baseline' else 'activity-buffered-150MHz.vcd.gz')
   if not scale.exists():run([sys.executable,str(D/('xu-hw-scale-vcd-20261102.py' if name=='baseline' else 'xu-hw-scale-vcd-buffered-20261102.py')),str(wave/'tb_accel_soc.vcd'),'--simulation-log',str(wave/'simulation.log'),'--out',str(vcd),'--metadata',str(scale)])
   m=json.loads(scale.read_text());here=O/name;here.mkdir(exist_ok=False);source=P/sourcefolder;manifest=json.loads((source/'manifest.json').read_text());cell=next(p for p in manifest['libraries'] if p.endswith('_basic.db'));ram=next(p for p in manifest['libraries'] if p.endswith('.db') and p!=cell)
   begin,end=m['derived_window_ns'];s['stage']=name+'-pt-power';save(s)
   text='''set_app_var link_path [list * {%s} {%s}]
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
read_verilog {%s}
if {![link_design accel_icb_slave]} {exit 1}
read_sdc {%s}
update_timing
report_units > units.rpt
man report_switching_activity > man-report-switching-activity.txt
if {![read_vcd -rtl -strip_path {%s} -time {%s %s} {%s}]} {error {read_vcd failed}}
report_switching_activity > activity-before-propagation.rpt
update_power
report_switching_activity > activity-after-propagation.rpt
report_power -hierarchy > power-hierarchy.rpt
report_power > power.rpt
report_analysis_coverage > timing-analysis-coverage.rpt
puts "XU_ACTIVITY_POWER_PASS"
exit 0
'''%(cell,ram,source/'mapped.v',source/'mapped.sdc',scopes,begin,end,vcd)
   old_here=B/'activity-power-01'/name
   reused=(old_here/'power.rpt').is_file() and (old_here/'power.tcl').is_file() and (old_here/'power.tcl').read_text()==text and 'XU_ACTIVITY_POWER_PASS' in (old_here/'pt.log').read_text(errors='replace').splitlines() and not re.findall(r'^Error:.*$',(old_here/'pt.log').read_text(errors='replace'),re.M)
   if reused:
    for path in old_here.iterdir():
     if path.is_file() and path.suffix in ['.rpt','.tcl','.log']:shutil.copyfile(str(path),str(here/path.name))
    log=(here/'pt.log').read_text(errors='replace')
   else:
    (here/'power.tcl').write_text(text);lc='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5';env=dict(os.environ,SYNOPSYS_LC_ROOT=lc);env['PATH']=lc+'/bin:'+env.get('PATH','')
    with (here/'pt.log').open('x') as f:p=subprocess.run(['pt_shell','-f','power.tcl'],cwd=str(here),env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1800)
    log=(here/'pt.log').read_text(errors='replace');errors=re.findall(r'^Error:.*$',log,re.M)
    if p.returncode or errors or 'XU_ACTIVITY_POWER_PASS' not in log.splitlines():raise ValueError(name+' activity PT failed: '+str(errors))
   review['cases'][name]=dict(status='PASS',reused_identical_tcl_reports_from=str(old_here) if reused else None,wave_directory=str(wave),result_sha256=sha(wave/'result.json'),reference_result_sha256=sha(refpath),layers=r['layers'],firmware_image_sha256=r['firmware_image_sha256'],current_elf_sha256=r['firmware_elf_sha256'],historical_elf_equal=r['firmware_elf_sha256']==ref['firmware_elf_sha256'],elf_gate='current ELF exact self hash; historical random temporary-object FILE differences do not affect image/cycles gate',scale=m,source_netlist_sha256=sha(source/'mapped.v'),source_sdc_sha256=sha(source/'mapped.sdc'),strip_path=scopes,pt_log_sha256=sha(here/'pt.log'),reports={p.name:dict(sha256=sha(p),text=p.read_text(errors='replace')) for p in here.glob('*.rpt')})
  (O/'paired-power-summary.json').write_text(json.dumps(review,sort_keys=True,indent=2)+'\n');s.update(status='PASS',stage='complete',summary_sha256=sha(O/'paired-power-summary.json'))
 except Exception as e:s.update(status='FAIL',error=str(e));raise
 finally:s['finished_epoch']=time.time();save(s)
 print('WORKLOAD_POWER_'+s['status'],flush=True)
