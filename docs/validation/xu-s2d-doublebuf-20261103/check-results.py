#!/usr/bin/env python3
"""Read-only audit of frozen xu S2d local actual logs, binaries and source identities."""
import hashlib,json,re,subprocess,sys,tarfile,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/scripts'))
import e203_soc as soc

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)
def blob(root,commit,path):return subprocess.check_output(['git','show',commit+':'+path],cwd=root)
def blob_sha(root,commit,path):return hashlib.sha256(blob(root,commit,path)).hexdigest()
manifest=json.loads((HERE/'sha256.json').read_text())
require(set(manifest)=={str(p.relative_to(HERE)) for p in HERE.rglob('*')
        if p.is_file() and p.name!='sha256.json'},'manifest file set differs')
for name,digest in manifest.items():require(sha(HERE/name)==digest,'changed raw/document: '+name)
child=ROOT/'third-party/e203_hbirdv2'
with tarfile.open(HERE/'raw/simulator.tar.xz') as tar:
    require(tar.getnames()==['accel_soc'],'unexpected simulator members')
    simulator_sha=hashlib.sha256(tar.extractfile('accel_soc').read()).hexdigest()
fixture=json.loads((ROOT/'tests/e203/vectors/kwt-silence-v1.json').read_text())
require(sha(ROOT/'tests/e203/vectors/kwt-silence-v1.tar.gz')==fixture['archive_sha256'],'fixture changed')
with tempfile.TemporaryDirectory(prefix='xu-s2d-verify-') as d:
    directory=Path(d)
    with tarfile.open(HERE/'raw/vectors.tar.xz') as tar:
        names={'layer_00/'+x+'.mem' for x in ['x','w','bias','y']}
        require(set(tar.getnames())==names,'vector members differ')
        for name in names:
            p=directory/name;p.parent.mkdir(exist_ok=True);p.write_bytes(tar.extractfile(name).read())
    checked=soc.check_vectors(directory,1)
vector_sha={'layer_00/'+name:digest for name,digest in checked[0]['sha256'].items()}
variants={}
for name,schedule in [('doublebuf-real1','bias-hw-doublebuf-window'),
                      ('autogroup-control-real1','bias-hw-autogroup-window'),
                      ('doublebuf-combined-tag-real1','bias-hw-doublebuf-window')]:
    d=HERE/'raw'/name;r=json.loads((d/'result.json').read_text())
    require(r['status']=='PASS' and r['mode']=='real' and r['tasks']==1 and
            r['firmware_schedule']==schedule and r['simulator']=='verilator','invalid measured result '+name)
    text=(d/'simulation.log').read_text().split('\n',1)[1]
    layers=soc.check_log(text,1);counters=soc.check_performance(text,layers,schedule)
    for layer,counter in zip(layers,counters):layer['performance']=counter
    require(layers==r['layers'],'actual TASK/PERF records differ '+name)
    if schedule=='bias-hw-doublebuf-window':
        require(soc.check_doublebuf_activity(text,layers,schedule)==r['doublebuf_activity'],'DB retirements differ')
    else:
        require(soc.check_autogroup_activity(text,layers,schedule)==r['autogroup_activity'],'AUTO retirements differ')
    require(r['vectors']==vector_sha and r['fixture']==fixture,'vectors or fixture differ')
    for path,digest in r['source_sha256'].items():
        prefix='third-party/e203_hbirdv2/vsim/install/rtl/'
        actual=(blob_sha(child,r['e203_commit'],'rtl/e203/'+path[len(prefix):]) if path.startswith(prefix)
                else blob_sha(ROOT,r['main_commit'],path))
        require(actual==digest,'frozen measured source differs '+path)
    require(blob_sha(ROOT,r['main_commit'],'tools/scripts/e203_soc.py')==r['runner_sha256'],'runner changed')
    require(blob_sha(ROOT,r['main_commit'],'tools/scripts/xu_firmware_contract.py')==r['contract_sha256'],'contract changed')
    for path,digest in r['firmware_sha256'].items():
        require(blob_sha(ROOT,r['main_commit'],'tests/e203/firmware/'+path)==digest,'frozen firmware source differs')
    require(sha(HERE/'raw/frozen-firmware-source'/(r['main_commit']+'.c'))==r['firmware_sha256']['accel.c'],
            'archived firmware snapshot differs')
    for path,digest in r['log_sha256'].items():require(sha(d/path)==digest,'log changed '+name+'/'+path)
    require(json.loads((d/'firmware-build.json').read_text())==r['firmware_build'],'firmware metadata differs')
    require(sha(d/'accel_soc')==r['firmware_elf_sha256']==r['firmware_build']['elf_sha256'],'ELF differs')
    require(sha(d/'accel_soc.verilog')==r['firmware_image_sha256']==r['firmware_build']['image_sha256'],'image differs')
    require(simulator_sha==r['simulator_sha256'],'simulator differs')
    variants[name]=r
common=['e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture',
        'simulator_sha256','firmware_opt','firmware_experiment']
for field in common:
    require(len({json.dumps(r[field],sort_keys=True) for r in variants.values()})==1,'comparison identity differs '+field)
comparison=json.loads((HERE/'comparison.json').read_text())
for name,r in variants.items():
    require(comparison['rows'][name]['cycles']==r['layers'][0]['cycles'],'comparison cycles differ')
require([variants[n]['layers'][0]['cycles'] for n in ['autogroup-control-real1','doublebuf-real1',
        'doublebuf-combined-tag-real1']]==[1013171,1018530,1003527],'unexpected measured cycles')
require(comparison['initial_minus_control']==5359 and comparison['final_minus_control']==-9644,
        'comparison delta differs')
compat=json.loads((HERE/'rtl-compatibility.json').read_text())
require(len(compat['default_files'])==13 and len(compat['new_files'])==2,'generated file matrix incomplete')
for name,row in compat['default_files'].items():
    p=child/'rtl/e203/perips'/name
    require(sha(p)==row['sha256'] and row['unchanged'] and
            p.read_bytes()==blob(child,'2b4b5dc','rtl/e203/perips/'+name),'old generated RTL changed '+name)
for name,digest in compat['new_files'].items():
    require(sha(child/'rtl/e203/perips'/name)==digest and
            blob_sha(child,comparison['measured_e203'],'rtl/e203/perips/'+name)==digest,
            'new generated RTL changed '+name)
generation=json.loads((HERE/'chisel-generation-final.json').read_text())
require(generation['status']=='PASS' and generation['returncode']==0 and
        generation['source_main_commit']=='0ad5e047a20df59f8211cbba9ef5bb77e8baffbb' and
        generation['source_child_commit']==comparison['measured_e203'] and
        len(generation['generated_sha256'])==12,'generation record incomplete')
for path,digest in generation['source_sha256'].items():
    require(blob_sha(ROOT,generation['source_main_commit'],path)==digest==sha(ROOT/path),
            'generation source identity differs '+path)
for name,digest in generation['generated_sha256'].items():
    require(sha(child/'rtl/e203/perips'/name)==digest,'generated/tracked RTL differs '+name)
require(sha(HERE/'raw/chisel-generation-final.log')==generation['log_sha256'],
        'generation log changed')
images=json.loads((HERE/'firmware-compatibility-final.json').read_text())
require(images['status']=='PASS' and len(images['comparisons'])==15,'historical image check incomplete')
with tarfile.open(HERE/'raw/historical-firmware-images.tar.xz') as tar:
    for i,row in enumerate(images['comparisons']):
        require(hashlib.sha256(tar.extractfile(str(i)+'/accel_soc.verilog').read()).hexdigest()==
                row['image_sha256']==row['actual_image_sha256'] and row['identical'],'historical image changed')
for logfile,count in [('host-tests-final.log',59),('numeric-tests.log',42),('hardware-contract-final.log',8)]:
    require(re.search(r'Ran '+str(count)+r' tests in [^\n]+\n\nOK\s*$',(HERE/'raw'/logfile).read_text()),
            'host completion missing '+logfile)
direct=(HERE/'raw/direct-doublebuf-boundary/simulation.log').read_text()
require(len(re.findall(r'^XU_DOUBLEBUF_WRAPPER_PASS rows=4 groups=128 lanes=1024 compute_read_overlap=1844 '
        r'x_compute_overlap=48 launches=131 dones=131 accepted=11862 retired=11862$',direct,re.M))==1,
        'direct complete/boundary counts differ')
legacy=HERE/'raw/legacy-baseline';r=json.loads((legacy/'result.json').read_text())
require(r['status']=='PASS' and r['tests']==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup',
        'accel_repeat_x'],'legacy five-case completion missing')
for name,digest in r['log_sha256'].items():require(sha(legacy/name)==digest,'legacy log changed')
print('PASS: raw SHA; 3 actual real1 windows/outputs/counters; frozen git/source/firmware/binary identities; '
      'default RTL and 15 images; host59/numeric42/contract8; DB retirement boundaries; legacy5. '
      'No server12/PPA/power/qualification claim.')
