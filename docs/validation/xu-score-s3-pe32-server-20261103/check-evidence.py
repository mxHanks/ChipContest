#!/usr/bin/env python3
"""Strict read-only replay of actual S3 full12 VCS evidence, not physical qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import types

H=Path(__file__).resolve().parent
ROOT=next(p for p in H.parents if (p/'tests/e203/vectors/kwt-silence-v1.json').is_file())
MAIN='94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114'
CHILD='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5'
SUB='third-party/e203_hbirdv2'
WIDE='bias-hw-pe32-autogroup-window'
AUTO='bias-hw-autogroup-window'
def need(v,m):
    if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(p.read_bytes())
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);a=p.parse_args()
original=read(H/'original-export-manifest.json');selected=read(H/'selected-manifest.json')
need(len(original)==174 and len({r['path']for r in original})==174,'original manifest uniqueness differs')
need(len(selected)==129 and len({r['path']for r in selected})==129,'selected raw uniqueness differs')
for r in selected:
    need([x for x in original if x['path']==r['path']]==[r],'raw selection differs')
    path=Path(r['path']);need(not path.is_absolute()and '..'not in path.parts,'unsafe raw path')
    raw=H/'raw'/path;need(raw.stat().st_size==r['bytes']and sha(raw)==r['sha256'],'raw bytes differ: '+str(path))
need({x.relative_to(H/'raw').as_posix()for x in(H/'raw').rglob('*')if x.is_file()}=={r['path']for r in selected},'extra/missing raw payload')
audit=read(H/'git-source-audit.json');need(audit['main_commit']==MAIN and audit['e203_commit']==CHILD,'Git pins differ')
need(audit['full_tracked_source_paths_verified']==2510 and len(read(H/'deployment/source-files.json'))==2510 and sha(H/'deployment/source-files.json')==audit['full_tracked_source_manifest_sha256'],'full-source manifest differs')
need(audit['transport']==dict(bytes=279572,sha256='5330f5c8b03d9a8f8077f1dbc51908881bb9d472ebad3c3b4fd73d81aa180336'),'transport receipt differs')
need(audit['child_changed_from_f49']==[
    'rtl/e203/perips/LinearAutoGroupCore.sv','rtl/e203/perips/XuParallelAutoGroupCore32.sv',
    'rtl/e203/perips/XuParallelBiasCache32.sv','rtl/e203/perips/XuParallelComputeCore32.sv',
    'rtl/e203/perips/XuParallelWeightBank32.sv','rtl/e203/perips/accel_icb_slave.v',
    'rtl/e203/perips/xu_pe32_icb_slave.v','rtl/e203/subsys/e203_subsys_perips.v','vsim/bin/run.makefile'],'exact child delta differs')
package=read(H/'deployment/package-files.json')
for name in ['source-identity.json','source-files.json','launch.py','README.md']:
    raw=H/'deployment'/name;need(raw.stat().st_size==package[name]['bytes']and sha(raw)==package[name]['sha256'],'deployment original differs: '+name)
receipt=read(H/'deployment/packaging-receipt.json')
need(receipt['sha256']=='c3c50ffc24e1cd2c3f7eaaf1a293162f103ee04d875bc25778309cf4a3fef997'and receipt['bytes']==245598 and receipt['launcher_sha256']==sha(H/'deployment/launch.py')and receipt['package_manifest_sha256']==sha(H/'deployment/package-files.json'),'deployment receipt differs')
with tarfile.open(H/'frozen-git-sources.tar.xz','r:xz')as t:
    ms=t.getmembers();need(len(ms)==len({m.name for m in ms})and all(m.isfile()and not Path(m.name).is_absolute()and '..'not in Path(m.name).parts for m in ms),'unsafe/duplicate source archive')
    sources={m.name:t.extractfile(m).read()for m in ms}
need({n:digest(v)for n,v in sources.items()}==audit['source_sha256'],'frozen source archive differs')
full_source=read(H/'deployment/source-files.json')
for n,raw in sources.items():need(digest(raw)==full_source[n.replace(SUB+'/vsim/install/rtl/',SUB+'/rtl/e203/')],'source not bound to full deployment')
contract=types.ModuleType('xu_firmware_contract');exec(compile(sources['tools/scripts/xu_firmware_contract.py'],'<frozen-contract>','exec'),contract.__dict__);sys.modules['xu_firmware_contract']=contract
soc=types.ModuleType('xu_s3_frozen');soc.__file__=str(ROOT/'tools/scripts/e203_soc.py');exec(compile(sources['tools/scripts/e203_soc.py'],'<frozen-runner>','exec'),soc.__dict__)
R=H/'raw/s3-pe32-accept-01';state=read(R/'state.json');accept=read(R/'acceptance/acceptance.json')
names=['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12','pe32-autogroup-control-real12','pe8-autogroup-control-real12']
need(state['status']==accept['status']=='VCS_ACCEPTED_NOT_RETAINED'and state['acceptance_status']==accept['acceptance_status']=='PASS','actual acceptance terminal state differs')
need(state['main_commit']==accept['main_commit']==MAIN and state['e203_commit']==accept['e203_commit']==CHILD and state['verified_source_paths']==2510,'accepted frozen pin differs')
need(state['steps']==accept['steps']and [s['name']for s in state['steps']]==names and all(s['status']=='PASS'for s in state['steps']),'complete ten steps differ')
for step in state['steps']:
    need((R/'acceptance'/(step['name']+'.log')).is_file(),'step log missing')
    if step['name']in names[2:]:
        argv=step['argv'];variant='pe8'if step['name'].startswith('pe8-')else'pe32';schedule=AUTO if 'control' in step['name']else WIDE
        need(argv[argv.index('--sim')+1]=='vcs'and argv[argv.index('--firmware-schedule')+1]==schedule and argv[argv.index('--accel-variant')+1]==variant and '--firmware-opt=-O2'in argv and argv[argv.index('--firmware-experiment')+1]=='both-unroll-no-masks','actual backend/config argv differs')
host=(R/'acceptance/host.log').read_text();numeric=(R/'acceptance/numeric.log').read_text()
need(re.search(r'Ran 62 tests in [0-9.]+s\s+OK \(skipped=3\)\s*$',host)is not None and state['steps'][0]['tests']==62 and state['steps'][0]['skipped']==3,'host62/skipped3 differs')
need(re.search(r'Ran 42 tests in [0-9.]+s\s+OK\s*$',numeric)is not None,'numeric42 differs')
need(state['steps'][0]['required_actual_vcs']==['cached-wrapper','pe32-wide','pe32-compat'],'required actual wrapper selection differs')
fixture=read(ROOT/'tests/e203/vectors/kwt-silence-v1.json');need(sha(ROOT/'tests/e203/vectors/kwt-silence-v1.tar.gz')==fixture['archive_sha256'],'local fixed fixture archive differs')
with tempfile.TemporaryDirectory(prefix='xu-s3-server-fixed-integer-')as tmp:
    soc.load_fixture(Path(tmp),12);integer_layers=soc.check_vectors(Path(tmp),12)
logs_checked=0;source_checks=0;runs={};rejected=[];not_retrieved=[]
def validate_text(text,tasks,schedule,variant):
    layers=soc.check_log(text,tasks)
    for layer,perf in zip(layers,soc.check_performance(text,layers,schedule,variant)):layer['performance']=perf
    return layers,soc.check_autogroup_activity(text,layers,schedule),soc.check_pe_activity(text,layers,schedule,variant)
for name in names[2:]:
    D=R/'acceptance'/name;j=read(D/'result.json');variant='pe8'if name.startswith('pe8-')else'pe32';schedule=AUTO if 'control'in name else WIDE
    need(j['status']=='PASS'and j['main_commit']==MAIN and(name=='vectors'or j['e203_commit']==CHILD),'actual result pin/status differs: '+name)
    need(j['simulator']=='vcs'and j['accel_variant']==variant and j['firmware_schedule']==schedule and j['firmware_opt']=='-O2'and j['firmware_experiment']=='both-unroll-no-masks','actual configuration differs: '+name)
    need(j['transaction_contract']==contract.task_contract(schedule)and digest(sources['tools/scripts/xu_firmware_contract.py'])==j['contract_sha256'],'contract identity differs')
    if 'runner_sha256'in j:need(digest(sources['tools/scripts/e203_soc.py'])==j['runner_sha256'],'runner identity differs')
    for n,v in j.get('source_sha256',{}).items():need(digest(sources[n])==v,'measured source differs: '+n);source_checks+=1
    for n,v in j.get('log_sha256',{}).items():need((D/n).is_file()and sha(D/n)==v,'declared log missing/differs: '+name+'/'+n);logs_checked+=1
    if 'firmware_build'in j:
        need(j['firmware_build']['configuration']==contract.configuration(schedule,'-O2','both-unroll-no-masks'),'built firmware config differs')
        need(j['firmware_sha256']==j['firmware_build']['source_sha256']and all(digest(sources['tests/e203/firmware/'+n])==v for n,v in j['firmware_sha256'].items()),'firmware source differs')
        need(j['firmware_elf_sha256']==j['firmware_build']['elf_sha256']and j['firmware_image_sha256']==j['firmware_build']['image_sha256'],'ELF/image declarations disagree')
        not_retrieved.extend([name+'/accel_soc',name+'/accel_soc.verilog'])
    if name=='vectors':need(j['layers']==integer_layers and j['outputs']==304128,'independent fixed integer recomputation differs')
    if name=='baseline':
        need(j['tests']==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],'legacy5 differs')
        for legacy in j['tests']:
            text=(D/(legacy+'.log')).read_text();argv=json.loads(text.split('\n',1)[0]);need('SIM=vcs'in argv and 'XU_ACCEL_PE32=1'in argv and 'TEST_PASS'in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:',text),'actual PE32 legacy log differs')
    if name in ['vectors','doctor','baseline']:continue
    tasks={'synthetic1':1,'synthetic2':2}.get(name,12);text=(D/'simulation.log').read_text();layers,auto,pe=validate_text(text,tasks,schedule,variant)
    need(j['layers']==layers and j['autogroup_activity']==auto and j['pe_activity']==pe and j['tasks']==tasks and j['outputs']==tasks*25344 and j['write_words']==tasks*50688 and len(j['source_sha256'])==157,'actual task/performance/activity scope differs: '+name)
    if tasks==12:need(j['fixture']==fixture and j['vectors']==fixture['files'],'full12 fixed vectors differ')
    runs[name]=j
    bads=[('missing_TASK',re.sub(r'^TASK_PASS[^\n]*\n','',text,count=1,flags=re.M)),
        ('duplicate_TASK',text+next(l for l in text.splitlines()if l.startswith('TASK_PASS '))+'\n'),
        ('missing_PERF',re.sub(r'^PERF_TASK[^\n]*\n','',text,count=1,flags=re.M)),
        ('duplicate_PERF',text+next(l for l in text.splitlines()if l.startswith('PERF_TASK '))+'\n'),
        ('wrong_MMIO',text.replace('mmio_writes='+str(layers[0]['performance']['mmio_writes']),'mmio_writes=0',1)),
        ('wrong_MAC_beats',text.replace('mac_fire='+str(layers[0]['performance']['mac_fire']),'mac_fire=0',1)),
        ('wrong_shared_reads',text.replace('shared_reads=23232','shared_reads=23231',1)),
        ('missing_SOC',re.sub(r'^SOC_PASS[^\n]*\n','',text,flags=re.M)),('appended_FATAL',text+'\nFATAL corruption\n'),
        ('missing_AUTO',re.sub(r'^AUTO_TASK[^\n]*\n','',text,count=1,flags=re.M)),
        ('duplicate_AUTO',text+next(l for l in text.splitlines()if l.startswith('AUTO_TASK '))+'\n'),
        ('wrong_POP_retirement',text.replace('pops_retired='+str(auto[0]['pops_retired']),'pops_retired=0',1)),
        ('zero_overlap',re.sub(r'compute_writeback_overlap=\d+','compute_writeback_overlap=0',text,count=1))]
    if variant=='pe32':
        bads.extend([('missing_PE',re.sub(r'^PE_TASK[^\n]*\n','',text,count=1,flags=re.M)),
            ('duplicate_PE',text+next(l for l in text.splitlines()if l.startswith('PE_TASK '))+'\n'),
            ('wrong_physical_PEs',text.replace('physical_pes=32','physical_pes=8',1)),
            ('wrong_lane_MACs',text.replace('lane_macs=1622016','lane_macs=405504',1)),
            ('wrong_useful_MACs',text.replace('useful_macs=1622016','useful_macs=405504',1))])
    else:bads.append(('unexpected_PE',text+'PE_TASK layer=0 physical_pes=32 mac_beats=202752 lane_macs=1622016 useful_macs=1622016\n'))
    for label,bad in bads:
        need(bad!=text,'ineffective corruption: '+label)
        try:validate_text(bad,tasks,schedule,variant)
        except ValueError:rejected.append(name+'/'+label)
        else:raise ValueError('corrupt actual log accepted: '+name+'/'+label)
direct={}
for kind,expected in [('wide',[16,190,27,27,11124,11124]),('compat',[64,958,99,99,11737,11737])]:
    d=state['direct_vcs'][kind];need(d['status']=='PASS'and d['backend']=='vcs'and d['counts']==expected,'actual direct receipt differs')
    for location in [R/'direct-pe32-vcs'/kind,R/'acceptance/host-pe32-wrapper-vcs'/kind]:
        text=(location/'simulation.log').read_text();compile_meta=json.loads((location/'compile.log').read_text().split('\n',1)[0])
        need(Path(compile_meta['argv'][0]).name=='vcs'and 'Compiler version Q-2020.03-SP2-6_Full64'in text,'actual direct backend differs')
        marker='XU_PE32'+('_COMPAT'if kind=='compat'else'')+'_WRAPPER_PASS'
        values=re.findall(r'^'+marker+r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)$',text,re.M)
        need(len(values)==1 and list(map(int,values[0]))==expected and not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b',text),'actual direct work/retirement differs')
        need(re.findall(r'^XU_PE32_DIRECT_ACTIVITY physical_pes=32 mac_beats=(\d+) lane_macs=(\d+)$',text,re.M)==([('1728','53760')]if kind=='wide'else[('6336','50688')]),'actual direct enabled-lane activity differs')
        for rawpath in compile_meta['argv']:
            if str(rawpath).startswith(state['source']+'/'):
                relative=rawpath[len(state['source'])+1:]
                installed=relative.replace(SUB+'/rtl/e203/',SUB+'/vsim/install/rtl/')
                need(relative in sources or installed in sources,'direct compiled source not frozen')
    for n,v in d['logs'].items():need(sha(R/'direct-pe32-vcs'/kind/n)==v,'direct declared log differs');logs_checked+=1
    direct[kind]=d
cached=R/'acceptance/host-wrapper-vcs'
need('Version Q-2020.03-SP2-6_Full64' in (cached/'compile.log').read_text()and
    'Compiler version Q-2020.03-SP2-6_Full64'in(cached/'simulation.log').read_text()and
    re.findall(r'^XU_CACHED_WRAPPER_PASS accepted=(\d+) retired=(\d+)$',(cached/'simulation.log').read_text(),re.M)==[('4909','4909')],
    'actual cached wrapper VCS missing')
wide=runs['real12'];same=runs['pe32-autogroup-control-real12'];old=runs['pe8-autogroup-control-real12']
common=['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture','firmware_sha256','firmware_opt','firmware_experiment']
for key in common:need(wide[key]==same[key]==old[key],'three-way common identity differs: '+key)
need(wide['simulator_sha256']==same['simulator_sha256']!=old['simulator_sha256'],'same32/distinct8 executable declaration differs')
need(all(x['performance']==y['performance']for x,y in zip(same['layers'],old['layers'])),'old-auto PERF controls differ')
rows=[dict(layer=w['layer'],pe32_wide_cycles=w['cycles'],pe32_auto_cycles=s['cycles'],pe8_auto_cycles=o['cycles'])for w,s,o in zip(wide['layers'],same['layers'],old['layers'])]
totals={k:sum(row[k]for row in rows)for k in ['pe32_wide_cycles','pe32_auto_cycles','pe8_auto_cycles']}
need(totals==dict(pe32_wide_cycles=11376501,pe32_auto_cycles=11842200,pe8_auto_cycles=11842200),'actual full12 totals differ')
need([r['pe32_wide_cycles']for r in rows]==[948039]+[948042]*11 and all(r['pe32_auto_cycles']==r['pe8_auto_cycles']==986850 for r in rows),'per-layer cycle comparison differs')
reduction=100*(totals['pe32_auto_cycles']-totals['pe32_wide_cycles'])/totals['pe32_auto_cycles']
comparison=read(R/'full12-comparison.json')
need(comparison['status']=='PASS'and comparison['identities_identical']==common and comparison['rows']==rows and comparison['totals']==totals and comparison['wide_reduction_vs_pe32_auto_percent']==reduction and comparison['same_pe32_simulator_sha256']==wide['simulator_sha256']and comparison['pe8_simulator_sha256']==old['simulator_sha256']and comparison['result_sha256']=={n:sha(R/'acceptance'/n/'result.json')for n in ['real12','pe32-autogroup-control-real12','pe8-autogroup-control-real12']},'server comparison is not exact recomputation')
report=dict(status='VERIFIED_VCS_DEVELOPMENT_RESULTS_NOT_QUALIFIED',main_commit=MAIN,e203_commit=CHILD,
    unique_raw_payloads=129,full_tracked_source_paths_preparation_verified=2510,archived_source_blobs=len(sources),
    measured_rtl_tb_paths_per_simulation=157,source_hash_checks=source_checks,declared_logs_verified=logs_checked,
    host=dict(tests=62,skipped=3),numeric_tests=42,integer_outputs_recomputed=304128,legacy_cases=5,
    comparison=dict(rows=rows,totals=totals,delta_cycles=465699,wide_cycle_reduction_percent=reduction),
    full12_performance={n:runs[n]for n in ['real12','pe32-autogroup-control-real12','pe8-autogroup-control-real12']},
    direct=direct,rejected_actual_log_corruptions=rejected,retained=False,
    limitations=['Original development4ns HF/66ns LF, first shared-source acceptance to final Y response retirement; no candidate formal-clear/first-request measurement',
        'ELF/image/simulator executable and actual server vector bytes were not retrieved; their declaration SHA values are not locally rehashed',
        'No mapped consistency, complete150MHz STA, same-config area, fullSoC task energy or contest qualification/score assertion'])
if a.out:a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print('PASS129 raw;2510 Git-source hashes;157 measured RTL/TB;three full12 VCS;wide11376501/controls11842200;NOT_QUALIFIED')
