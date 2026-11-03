#!/usr/bin/env python3
"""xu: require actual frozen64PE full12 VCS acceptance, then run fresh same-library DC/PT.

This launcher does not contact a server or read credentials. Run it on the EDA
server after deploying the frozen candidate and this producer/tool commit.
All outputs remain NOT_QUALIFIED; energy and retention are separate work.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

TOOLS = Path(__file__).resolve().parents[2]
BASE = Path.home()/'Desktop/xu-score-optimization-20261102'
MAIN = '3443fad8945577626d226b1cd53eadec89331a20'
CHILD = '7aae96776e116d5e95d6ebb49d29a5fccce04ab9'
STANDARD_SHA = 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
SRAM_SHA = 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def git(path,*args):
    return subprocess.check_output(['git','--no-replace-objects']+list(args),cwd=str(path),universal_newlines=True).strip()


def checked_acceptance(source, acceptance, producer=TOOLS):
    state_path = acceptance/'state.json'
    require(state_path.is_file() and not state_path.is_symlink(), 'regular acceptance state required')
    state_data = state_path.read_bytes()
    state = json.loads(state_data)
    require(state['status'] == 'VCS_ACCEPTED_NOT_RETAINED' and state['main_commit'] == MAIN and state['e203_commit'] == CHILD,
            'frozen complete actual64PE VCS acceptance required before PPA')
    require(Path(state['source']).resolve() == source.resolve(), 'accepted source origin differs')
    require(git(source,'rev-parse','HEAD') == MAIN and git(source/'third-party/e203_hbirdv2','rev-parse','HEAD') == CHILD,
            'source commit differs from accepted candidate')
    require(not git(source,'status','--porcelain') and not git(source/'third-party/e203_hbirdv2','status','--porcelain'),
            'accepted source is dirty')
    expected_steps = ['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12',
                      'same64-schedule32-control-real12','same64-schedule8-control-real12',
                      'physical32-wide32-control-real12','physical8-auto8-control-real12']
    require([step['name'] for step in state['steps']] == expected_steps and all(step['status'] == 'PASS' for step in state['steps']),
            'eight acceptance steps plus four full12 controls required')
    require(set(state['direct_vcs']) == {'wide64','compat32','compat8','boundary'} and
            all(record['status'] == 'PASS' and record['backend'] == 'vcs' for record in state['direct_vcs'].values()),
            'three mandatory physical64 direct VCS modes and boundary test required')
    spec = importlib.util.spec_from_file_location('xu_pe64_gate_ppa', producer/'tools/scripts/xu_soc_ppa.py')
    ppa = importlib.util.module_from_spec(spec); spec.loader.exec_module(ppa)
    # Actual complete blobs/modes/symlink/gitlink checks, independently of status/index flags.
    freeze = ppa.source_profile_identity(source, 's3-pe64')
    observed = {str(state_path.resolve()):hashlib.sha256(state_data).hexdigest()}

    def observe(path):
        require(path.is_file() and not path.is_symlink(), 'regular acceptance artifact required: ' + str(path))
        data = path.read_bytes()
        value = hashlib.sha256(data).hexdigest()
        key = str(path.resolve())
        require(key not in observed or observed[key] == value, 'acceptance artifact changed during review')
        observed[key] = value
        return data.decode('utf-8')

    def observed_hash(path):
        observe(path)
        return observed[str(path.resolve())]

    def log(path):
        return observe(path).split('\n',1)[1]

    for kind, lanes, expected in [('wide64',64,[8,15,15,11031,11031]),
                                  ('compat32',32,[16,27,27,11131,11131]),
                                  ('compat8',8,[64,99,99,11731,11731])]:
        directory = acceptance/'direct-pe64-vcs'/kind
        require(set(state['direct_vcs'][kind]['logs']) == {'compile.log','simulation.log'}, 'direct log inventory differs')
        for filename,digest in state['direct_vcs'][kind]['logs'].items():
            require(observed_hash(directory/filename) == digest, 'direct VCS log changed: ' + kind+'/'+filename)
        text = log(directory/'simulation.log')
        found = re.findall('XU_PE64_WRAPPER_PASS mode_lanes='+str(lanes)+r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)',text)
        require(len(found) == 1, 'direct VCS completion missing/duplicate: ' + kind)
        values = list(map(int,found[0]))
        require(values[1] > 0 and [values[0]]+values[2:] == expected and values == state['direct_vcs'][kind]['counts'], 'direct VCS work/retirement differs')
        require(re.findall(r'XU_PE64_DIRECT_ACTIVITY physical_pes=64 mac_beats=(\d+) lane_macs=(\d+)',text) == [(str(expected[1]*64),str(49664+128*lanes))], 'direct enabled-lane work differs')
        command = json.loads(observe(directory/'compile.log').split('\n',1)[0])['argv']
        require(command[0] == 'vcs' and '-full64' in command and '-sverilog' in command, 'direct compiler is not actual VCS')
        require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b',text),'direct failure marker')
    directory = acceptance/'direct-pe64-vcs/boundary'
    require(set(state['direct_vcs']['boundary']['logs']) == {'compile.log','simulation.log'}, 'boundary log inventory differs')
    for filename,digest in state['direct_vcs']['boundary']['logs'].items():
        require(observed_hash(directory/filename) == digest, 'boundary VCS log changed')
    command = json.loads(observe(directory/'compile.log').split('\n',1)[0])['argv']
    require(command[0] == 'vcs', 'boundary compiler is not actual VCS')
    boundary = log(directory/'simulation.log')
    require(re.findall(r'XU_PE64_BOUNDARY_PASS mode=(\d) unknown_reads=14 mode_error=1 pop_retired=1',boundary) == ['0','1','2'] and
            boundary.count('XU_PE64_BOUNDARIES_PASS modes=3') == 1, 'three-mode boundary VCS completion differs')
    stock = acceptance/'acceptance'
    require(re.search(r'Ran 68 tests in [^\n]+\n\nOK(?: \(skipped=\d+\))?\s*$',log(stock/'host.log')) is not None, 'stock actual host68 completion required')
    require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$',log(stock/'numeric.log')) is not None, 'stock numeric42 completion required')
    for name in ['vectors','doctor','baseline']:
        directory = stock/name
        report = json.loads(observe(directory/'result.json'))
        require(report['status'] == 'PASS' and report['main_commit'] == MAIN and report['accel_variant'] == 'pe64' and
                report['firmware_schedule'] == 'bias-hw-pe64-autogroup-window', 'stock preflight identity differs: ' + name)
        if name != 'vectors': require(report['e203_commit'] == CHILD, 'stock preflight child differs')
        if name == 'vectors': require(report['outputs'] == 304128 and len(report['layers']) == 12, 'stock fixed-vector12 incomplete')
        if name == 'baseline':
            require(report['simulator'] == 'vcs' and report['tests'] == ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'], 'actual physical64 legacy5 incomplete')
            for filename,digest in report['log_sha256'].items(): require(observed_hash(directory/filename) == digest,'legacy raw log changed')
            for test in report['tests']:
                text = observe(directory/(test+'.log'))
                require('TEST_PASS' in text and 'XU_ACCEL_PE64=1' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:',text), 'actual physical64 legacy execution differs')
    sys.path.insert(0,str(source/'tools/scripts'))
    import e203_soc as soc
    results = {}
    cases = [('synthetic1','synthetic',1,'pe64','bias-hw-pe64-autogroup-window'),
             ('synthetic2','synthetic',2,'pe64','bias-hw-pe64-autogroup-window'),
             ('real12','real',12,'pe64','bias-hw-pe64-autogroup-window'),
             ('same64-schedule32-control-real12','real',12,'pe64','bias-hw-pe32-autogroup-window'),
             ('same64-schedule8-control-real12','real',12,'pe64','bias-hw-autogroup-window'),
             ('physical32-wide32-control-real12','real',12,'pe32','bias-hw-pe32-autogroup-window'),
             ('physical8-auto8-control-real12','real',12,'pe8','bias-hw-autogroup-window')]
    for name,mode,tasks,variant,schedule in cases:
        directory = stock/name
        report = json.loads(observe(directory/'result.json'))
        text = log(directory/'simulation.log')
        layers = soc.check_log(text,tasks)
        for layer,performance in zip(layers,soc.check_performance(text,layers,schedule,variant)): layer['performance'] = performance
        require(report['status'] == 'PASS' and report['mode'] == mode and report['tasks'] == tasks and report['layers'] == layers and
                report['main_commit'] == MAIN and report['e203_commit'] == CHILD and report['simulator'] == 'vcs' and
                report['accel_variant'] == variant and report['firmware_schedule'] == schedule and report['firmware_opt'] == '-O2' and
                report['firmware_experiment'] == 'both-unroll-no-masks', 'actual run identity/counters differ: '+name)
        require(report['pe_activity'] == soc.check_pe_activity(text,layers,schedule,variant) and
                report['autogroup_activity'] == soc.check_autogroup_activity(text,layers,schedule), 'PE/FIFO/row work differs: '+name)
        require(report['versions']['vcs'][0] == 'vcs script version : Q-2020.03' and
                'Compiler version = VCS Q-2020.03-SP2-6_Full64' in report['versions']['vcs'], 'actual VCS version differs')
        require(any(value and value[0] == 'riscv64-unknown-elf-gcc (SiFive GCC-Metal 10.2.0-2020.12.8) 10.2.0'
                    for key,value in report['versions'].items() if key.endswith('riscv64-unknown-elf-gcc')), 'actual SiFive GCC version differs')
        for relative,digest in report['source_sha256'].items():
            prefix = 'third-party/e203_hbirdv2/vsim/install/rtl/'
            path = source/'third-party/e203_hbirdv2/rtl/e203'/relative[len(prefix):] if relative.startswith(prefix) else source/relative
            require(sha(path) == digest, 'measured source changed: '+relative)
        require(sha(source/'tools/scripts/e203_soc.py') == report['runner_sha256'] and
                sha(source/'tools/scripts/xu_firmware_contract.py') == report['contract_sha256'], 'runner/contract changed')
        for filename,digest in report['firmware_sha256'].items(): require(sha(source/'tests/e203/firmware'/filename) == digest,'firmware source changed')
        for filename,digest in report['log_sha256'].items(): require(observed_hash(directory/filename) == digest,'measured log changed: '+filename)
        require(sha(directory/'accel_soc') == report['firmware_elf_sha256'] and sha(directory/'accel_soc.verilog') == report['firmware_image_sha256'], 'ELF/image changed')
        simulator = source/'build/e203'/('sim-'+soc.build_key(report,'vcs',False))/'accel_soc'
        argv = json.loads(observe(directory/'simulation.log').split('\n',1)[0])
        require(Path(argv[0]).resolve() == simulator.resolve() and simulator.is_file() and not simulator.is_symlink() and
                sha(simulator) == report['simulator_sha256'], 'actual accepted VCS simulator binary changed')
        receipt = json.loads(observe(simulator.parent/'vcs-build.json'))
        require(receipt['binary_sha256'] == report['simulator_sha256'], 'actual VCS build receipt changed')
        results[name] = report
    real = {name:result for name,result in results.items() if result['mode'] == 'real'}
    wide = real['real12']; same32 = real['same64-schedule32-control-real12']; same8 = real['same64-schedule8-control-real12']
    old32 = real['physical32-wide32-control-real12']; old8 = real['physical8-auto8-control-real12']
    for key in ['source_sha256','versions','tools','fixture','vectors','firmware_sha256','runner_sha256','contract_sha256']:
        require(all(value[key] == wide[key] for value in real.values()), 'five-way common identity mismatch: '+key)
    require(wide['simulator_sha256'] == same32['simulator_sha256'] == same8['simulator_sha256'] and
            len({wide['simulator_sha256'],old32['simulator_sha256'],old8['simulator_sha256']}) == 3, 'same64/distinct32/8 executable identities required')
    require(same32['layers'] == old32['layers'] and same8['layers'] == old8['layers'], 'same-schedule physical controls differ')
    observe(acceptance/'state.json')
    for name,digest in observed.items(): require(sha(Path(name)) == digest, 'acceptance artifact changed during review: '+name)
    require(ppa.source_profile_identity(source,'s3-pe64') == freeze, 'accepted complete source changed during review')
    return dict(state_sha256=sha(acceptance/'state.json'), source_profile=freeze,
                reviewed_artifacts_sha256=observed,
                result_sha256={name:sha(stock/name/'result.json') for name in results},
                measured_total_cycles={name:sum(layer['cycles'] for layer in result['layers']) for name,result in results.items()})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=BASE/'ChipContest-s3-pe64-02')
    p.add_argument('--acceptance',type=Path,default=BASE/'s3-pe64-accept-02')
    p.add_argument('--producer-root',type=Path,default=TOOLS)
    p.add_argument('--out',type=Path,default=BASE/'s3-pe64-ppa-campaign-20261103-02')
    p.add_argument('--standard-cell-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db')
    p.add_argument('--sram-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db')
    p.add_argument('--foreground',action='store_true',help='run directly; otherwise detach with durable PID/log')
    a=p.parse_args();out=a.out.resolve();producer=a.producer_root.resolve();source=a.source.resolve()
    checked_acceptance(source,a.acceptance.resolve(),producer)
    if not a.foreground:
        require(not out.exists(),'fresh output directory required')
        # Verify acceptance before creating any output or detached process.
        checked_acceptance(source,a.acceptance.resolve(),producer)
        out.mkdir(parents=True)
        command=[sys.executable,str(Path(__file__).resolve())]+sys.argv[1:]+['--foreground']
        with (out/'driver.log').open('xb') as stream:
            process=subprocess.Popen(command,cwd=str(producer),env=dict(os.environ,PWD=str(producer)),stdin=subprocess.DEVNULL,
                stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        boot=dict(status='LAUNCHED_NOT_QUALIFIED',pid=process.pid,argv=command,launcher_sha256=sha(Path(__file__)))
        (out/'boot.json').write_text(json.dumps(boot,indent=2)+'\n');print(json.dumps(boot),flush=True);return
    if out.exists():
        require({path.name for path in out.iterdir()} <= {'driver.log','boot.json'}, 'foreground output is not fresh')
    else:
        out.mkdir(parents=True)
    require(not (out/'state.json').exists(),'fresh foreground campaign required')
    state=dict(status='RUNNING_NOT_QUALIFIED',source=str(source),producer_root=str(producer),profile='s3-pe64',steps=[])
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat()
        (out/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    try:
        state['acceptance']=checked_acceptance(source,a.acceptance.resolve(),producer);save()
        require(sha(a.standard_cell_db)==STANDARD_SHA and sha(a.sram_db)==SRAM_SHA,'same-server frozen library SHA differs')
        spec=importlib.util.spec_from_file_location('xu_pe64_implementation',producer/'tools/ppa/xu_soc_implementation.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);ppa=module.ppa_module()
        require(ppa.SOURCE_PROFILES['s3-pe64']['commit']==CHILD and ppa.PE64_CONFIGURATION['full_soc_macros']==384,
                'producer lacks approved complete PE64 geometry profile')
        commands=[
            [sys.executable,producer/'tools/ppa/xu_soc_implementation.py','--root',source,'--profile','s3-pe64','--out',out/'implementation',
             '--standard-cell-db',a.standard_cell_db,'--standard-cell-sha256',STANDARD_SHA,'--sram-db',a.sram_db,'--sram-sha256',SRAM_SHA],
            [sys.executable,producer/'tools/scripts/xu_soc_ppa.py','prepare','--root',source,'--implementation',out/'implementation/implementation.json',
             '--out',out/'ppa','--allow-unqualified-mapping'],
            [sys.executable,producer/'tools/scripts/xu_soc_ppa.py','run','--root',source,'--out',out/'ppa']]
        state['tool_sha256']={name:sha(producer/name) for name in ['tools/ppa/xu_soc_implementation.py','tools/scripts/xu_soc_ppa.py']}
        for index,command in enumerate(commands):
            record=dict(index=index,argv=[str(x) for x in command],status='RUNNING');state['steps'].append(record);save()
            with (out/('step-%d.log'%index)).open('x') as stream:
                stream.write(json.dumps(dict(argv=record['argv'],cwd=str(producer)))+'\n');stream.flush()
                result=subprocess.run(record['argv'],cwd=str(producer),env=dict(os.environ,PWD=str(producer)),stdin=subprocess.DEVNULL,
                    stdout=stream,stderr=subprocess.STDOUT,timeout=21600)
            record.update(returncode=result.returncode,status='PASS' if result.returncode==0 else 'FAIL');save()
            require(result.returncode==0,'PPA step%d failed; preserve actual raw DC/PT reports'%index)
        execution=json.loads((out/'ppa/execution.json').read_text());require(execution['status']=='EXECUTED_NOT_QUALIFIED','PPA execution incomplete')
        for name,digest in state['tool_sha256'].items():require(sha(producer/name)==digest,'producer changed during execution')
        checked_acceptance(source,a.acceptance.resolve(),producer)
        state.update(status='EXECUTED_NOT_QUALIFIED',execution_sha256=sha(out/'ppa/execution.json'),
            not_run=['candidate-specific formal clear/request activity','mapped consistency','fullSoC task energy','retention'])
    except Exception as error:
        state.update(status='FAIL',error=str(error));save();raise
    save();print('XU_PE64_PPA_DONE '+state['status'],flush=True)


if __name__=='__main__':
    main()
