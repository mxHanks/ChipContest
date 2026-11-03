#!/usr/bin/env python3
"""Strict replay of xu32 local screening records; no physical qualification claim."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,required=True)
parser.add_argument('--raw',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();root=args.root.resolve();raw=args.raw.resolve()
sys.path.insert(0,str(root/'tools/scripts'))
import e203_soc as soc
MAIN='d46486c9820e909ab9469a5fa1f10eee022988c3'
CHILD='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5'
def require(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def readrun(name,variant,schedule):
 directory=raw/'screen'/name;r=json.loads((directory/'result.json').read_text());log=(directory/'simulation.log').read_text().split('\n',1)[1]
 layers=soc.check_log(log,1)
 for layer,perf in zip(layers,soc.check_performance(log,layers,schedule,variant)):layer['performance']=perf
 require(r['status']=='PASS' and r['main_commit']==MAIN and r['e203_commit']==CHILD and r['accel_variant']==variant and r['firmware_schedule']==schedule and r['simulator']=='verilator' and r['layers']==layers,'identity/counter failure '+name)
 require(r['firmware_opt']=='-O2' and r['firmware_experiment']=='both-unroll-no-masks','effective compiler flags '+name)
 require(r.get('pe_activity')==soc.check_pe_activity(log,layers,schedule,variant),'PE observation '+name)
 require(r.get('autogroup_activity')==soc.check_autogroup_activity(log,layers,schedule),'row observation '+name)
 require(sha(root/'tools/scripts/e203_soc.py')==r['runner_sha256'] and sha(root/'tools/scripts/xu_firmware_contract.py')==r['contract_sha256'],'runner changed')
 for name,digest in r['source_sha256'].items():
  prefix='third-party/e203_hbirdv2/vsim/install/rtl/'
  p=root/'third-party/e203_hbirdv2/rtl/e203'/name[len(prefix):] if name.startswith(prefix) else root/name
  require(sha(p)==digest,'measured source changed '+name)
 for name,digest in r['log_sha256'].items():require(sha(directory/name)==digest,'log changed '+name)
 for name,digest in r['firmware_sha256'].items():require(sha(root/'tests/e203/firmware'/name)==digest,'firmware source changed')
 require(sha(directory/'accel_soc')==r['firmware_elf_sha256'] and sha(directory/'accel_soc.verilog')==r['firmware_image_sha256'],'firmware output changed')
 return r
for path,record in json.loads((raw/'manifest.json').read_text()).items():
 p=raw/path;require(p.stat().st_size==record['bytes'] and sha(p)==record['sha256'],'raw identity changed '+path)
wide=readrun('wide-real1','pe32','bias-hw-pe32-autogroup-window')
auto32=readrun('pe32-auto-real1','pe32','bias-hw-autogroup-window')
auto8=readrun('pe8-auto-real1','pe8','bias-hw-autogroup-window')
common=['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture','firmware_sha256','firmware_opt','firmware_experiment']
for key in common:require(wide[key]==auto32[key]==auto8[key],'common identity differs '+key)
require(wide['simulator_sha256']==auto32['simulator_sha256']!=auto8['simulator_sha256'],'same32/different8 binary identity')
for label in ['wide','compat']:
 text=(raw/'host03/pe32'/label/'simulation.log').read_text().split('\n',1)[1]
 marker='XU_PE32'+('_COMPAT' if label=='compat' else '')+'_WRAPPER_PASS'
 matches=re.findall(marker+r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)',text)
 require(len(matches)==1,'direct marker '+label)
 values=list(map(int,matches[0]));expected=[16,27,27,11124,11124] if label=='wide' else [64,99,99,11737,11737]
 require(values[1]>0 and [values[0]]+values[2:]==expected,'direct counts '+label)
 require(re.findall(r'XU_PE32_DIRECT_ACTIVITY physical_pes=32 mac_beats=(\d+) lane_macs=(\d+)',text)==([('1728','53760')] if label=='wide' else [('6336','50688')]),'direct physical activity '+label)
 require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b',text),'direct failure '+label)
legacy=json.loads((raw/'screen/pe32-legacy5/result.json').read_text())
require(legacy['status']=='PASS' and legacy['main_commit']==MAIN and legacy['e203_commit']==CHILD and legacy['accel_variant']=='pe32' and legacy['tests']==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],'actual legacy5 incomplete')
for name in legacy['tests']:
 text=(raw/'screen/pe32-legacy5'/(name+'.log')).read_text()
 require('TEST_PASS' in text and 'XU_ACCEL_PE32=1' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:',text),'legacy physical variant/completion '+name)
require(re.search(r'Ran 62 tests in [^\n]+\n\nOK\s*$',(raw/'host03/host.log').read_text()),'host62 completion')
require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$',(raw/'numeric/numeric.log').read_text()),'numeric42 completion')
require('All tests passed.' in (raw/'chisel/test.log').read_text() and json.loads((raw/'chisel/result.json').read_text())['status']=='PASS','Chisel completion')
old=json.loads((raw/'default-compatibility.json').read_text())
require(old['all_bytes_identical'],'default source comparison missing')
for name,digest in old['sha256'].items():
 path=Path('rtl/e203/perips')/name
 original=subprocess.check_output(['git','show',old['original_child']+':'+path.as_posix()],cwd=root/'third-party/e203_hbirdv2')
 require(hashlib.sha256(original).hexdigest()==digest==sha(root/'third-party/e203_hbirdv2'/path),'default changed '+name)
for name,digest in json.loads((raw/'source-sha256.json').read_text()).items():require(sha(root/name)==digest,'frozen source differs '+name)
rows=[dict(case=name,variant=r['accel_variant'],schedule=r['firmware_schedule'],cycles=r['layers'][0]['cycles'],performance=r['layers'][0]['performance'],pe_activity=r['pe_activity'],autogroup_activity=r['autogroup_activity']) for name,r in [('pe8_auto',auto8),('pe32_auto',auto32),('pe32_wide',wide)]]
wc=wide['layers'][0]['cycles'];ac=auto32['layers'][0]['cycles']
result=dict(status='LOCAL_SCREEN_PASS_NOT_QUALIFIED',scope='one real layer00, local GCC14.2/Verilator5.032 at historical development clocks; clear/request-window/server12/physical qualification pending',main_commit=MAIN,e203_commit=CHILD,rows=rows,wide_reduction_vs_same_pe32_auto_percent=100.0*(ac-wc)/ac,common_identity=common,same_pe32_simulator_sha256=wide['simulator_sha256'],pe8_simulator_sha256=auto8['simulator_sha256'],actual_lane_macs_per_task=1622016,host_tests=62,numeric_tests=42,chisel_tests=1,legacy_cases=5,raw_payloads=len(json.loads((raw/'manifest.json').read_text())),retained=False)
args.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],cycles={row['case']:row['cycles'] for row in rows},reduction_percent=result['wide_reduction_vs_same_pe32_auto_percent']),indent=2))
