#!/usr/bin/env python3
"""xu: require actual frozen compact-W32 full12 VCS acceptance, then run fresh same-library DC/PT.

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
MAIN = 'f75880d4f06ccb7f1c16115bee501f53d9a2abb7'
CHILD = '52cfbea1f79f10e44f7d1696f54015797f886b96'
STANDARD_SHA = 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
SRAM_SHA = 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'

SRAM128_SHA = '821c9344b787ecaae7ce222b9c5ab339b223759411dc20812f06210448a71bbe'
DESIGNATED_MODEL_PATH = Path('/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP128X16/verilog/RAMSP128X16.v')
DESIGNATED_MODEL_SHA = 'f9d6d881746681dacd4f3851467561e441ee7190776ab566b1f0a729aa3ddb4d'
DESIGNATED_MODEL_BYTES = 89548


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def git(path,*args):
    return subprocess.check_output(['git','--no-replace-objects']+list(args),cwd=str(path),universal_newlines=True).strip()


def checked_designated_model(record, observed_hash):
    model = Path(record['path'])
    require(model == DESIGNATED_MODEL_PATH and record['sha256'] == DESIGNATED_MODEL_SHA and
            record['bytes'] == DESIGNATED_MODEL_BYTES, 'designated official128 model pin differs')
    require(model.is_file() and not model.is_symlink() and model.stat().st_size == DESIGNATED_MODEL_BYTES and
            observed_hash(model) == DESIGNATED_MODEL_SHA, 'designated actual128 model changed')
    return model


def checked_acceptance(source, acceptance, producer=TOOLS):
    state_path = acceptance/'state.json'
    require(state_path.is_file() and not state_path.is_symlink(), 'regular acceptance state required')
    state_data = state_path.read_bytes()
    state = json.loads(state_data)
    require(state['status'] == 'VCS_ACCEPTED_NOT_RETAINED' and state['main_commit'] == MAIN and state['e203_commit'] == CHILD,
            'frozen complete actual compact-W32 VCS acceptance required before PPA')
    require(Path(state['source']).resolve() == source.resolve(), 'accepted source origin differs')
    require(git(source,'rev-parse','HEAD') == MAIN and git(source/'third-party/e203_hbirdv2','rev-parse','HEAD') == CHILD,
            'source commit differs from accepted candidate')
    require(not git(source,'status','--porcelain') and not git(source/'third-party/e203_hbirdv2','status','--porcelain'),
            'accepted source is dirty')
    expected_steps = ['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12',
                      'old32-wide-real12','bank128-oldauto-real12']
    require([step['name'] for step in state['steps']] == expected_steps and all(step['status'] == 'PASS' for step in state['steps']),
            'eight acceptance steps plus two full12 controls required')
    kinds = ['bank-generated','bank-designated-macro','wide','compat','wide-designated-macro','compat-designated-macro']
    require(set(state['direct_vcs']) == set(kinds), 'all six mandatory actual VCS run records required')
    spec = importlib.util.spec_from_file_location('xu_bank128_gate_ppa', producer/'tools/scripts/xu_soc_ppa.py')
    ppa = importlib.util.module_from_spec(spec); spec.loader.exec_module(ppa)
    # Actual complete blobs/modes/symlink/gitlink checks, independently of status/index flags.
    freeze = ppa.source_profile_identity(source, 's3-pe32-bank128')
    observed = {str(state_path.resolve()):hashlib.sha256(state_data).hexdigest()}

    def observe_bytes(path):
        require(path.is_file() and not path.is_symlink(), 'regular acceptance artifact required: ' + str(path))
        data = path.read_bytes()
        value = hashlib.sha256(data).hexdigest()
        key = str(path.resolve())
        require(key not in observed or observed[key] == value, 'acceptance artifact changed during review')
        observed[key] = value
        return data

    def observe(path):
        return observe_bytes(path).decode('utf-8')

    def observed_hash(path):
        observe_bytes(path)
        return observed[str(path.resolve())]

    def log(path):
        return observe(path).split('\n',1)[1]

    model_record = state['designated_ramsp128_model']
    model = checked_designated_model(model_record,observed_hash)
    require(sha(source/'tools/ppa/xu_weight128_sram_adapter.sv') == ppa.BANK128_ADAPTER_SHA256,
            'direct designated adapter differs from synthesis replacement')
    direct = log(acceptance/'direct-bank128-vcs.log')
    require(re.search(r'Ran 7 tests in [^\n]+\n\nOK\s*$',direct) is not None,
            'all seven direct tests must pass without skips')
    for kind in kinds:
        directory = acceptance/'direct-bank128-vcs'/kind
        require(set(state['direct_vcs'][kind]) == {'compile.log','simulation.log'}, 'direct log inventory differs')
        for filename,digest in state['direct_vcs'][kind].items():
            require(observed_hash(directory/filename) == digest, 'direct VCS log changed: '+kind+'/'+filename)
        text = log(directory/'simulation.log')
        metadata = json.loads(observe(directory/'compile.log').split('\n',1)[0])
        command = metadata['argv']
        require(command[0] == 'vcs' and '-full64' in command and '-sverilog' in command,
                'direct compiler is not actual VCS')
        require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b',text), 'direct failure marker')
        if kind.startswith('bank-'):
            require(text.count('XU_PE32_BANK128_PASS logical_words=512 depths=4 writes=520 reads=524 unknown_reads=4 selected_enable=1 latency=1') == 1,
                    'full512 bank test completion differs')
        else:
            compat = kind.startswith('compat')
            marker = 'XU_PE32_COMPAT_WRAPPER_PASS' if compat else 'XU_PE32_WRAPPER_PASS'
            found = re.findall(marker+r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)',text)
            require(len(found) == 1, 'direct wrapper completion missing/duplicate')
            groups,overlap,launches,dones,accepted,retired = map(int,found[0])
            require((groups,launches,dones) == ((64,99,99) if compat else (16,27,27)) and
                    overlap > 0 and accepted == retired and accepted > 0, 'wrapper work/retirement differs')
            require(re.findall(r'XU_PE32_DIRECT_ACTIVITY physical_pes=32 mac_beats=(\d+) lane_macs=(\d+)',text) ==
                    ([('6336','50688')] if compat else [('1728','53760')]), 'direct enabled-lane work differs')
        generated = str(source/'third-party/e203_hbirdv2/rtl/e203/perips/mem_128x16.sv')
        if 'designated-macro' in kind:
            require(metadata['designated_model'] == dict(path=str(model),sha256=model_record['sha256']),
                    'direct actual128 model provenance differs')
            require('+define+ARM_UD_MODEL' in command and str(model) in command and
                    str(source/'tools/ppa/xu_weight128_sram_adapter.sv') in command and
                    not any(value.endswith('/mem_128x16.sv') for value in command),
                    'designated run used a behavioral shadow instead of actual SRAM model')
        else:
            require(generated in command and str(model) not in command and '+define+ARM_UD_MODEL' not in command,
                    'generated-memory control compilation differs')
    stock = acceptance/'acceptance'
    require(re.search(r'Ran 69 tests in [^\n]+\n\nOK(?: \(skipped=\d+\))?\s*$',log(stock/'host.log')) is not None, 'stock actual host69 completion required')
    require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$',log(stock/'numeric.log')) is not None, 'stock numeric42 completion required')
    for name in ['vectors','doctor','baseline']:
        directory = stock/name
        report = json.loads(observe(directory/'result.json'))
        require(report['status'] == 'PASS' and report['main_commit'] == MAIN and report['accel_variant'] == 'pe32-bank128' and
                report['firmware_schedule'] == 'bias-hw-pe32-autogroup-window', 'stock preflight identity differs: ' + name)
        if name != 'vectors': require(report['e203_commit'] == CHILD, 'stock preflight child differs')
        if name == 'vectors': require(report['outputs'] == 304128 and len(report['layers']) == 12, 'stock fixed-vector12 incomplete')
        if name == 'baseline':
            require(report['simulator'] == 'vcs' and report['tests'] == ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'], 'actual compact-W32 legacy5 incomplete')
            for filename,digest in report['log_sha256'].items(): require(observed_hash(directory/filename) == digest,'legacy raw log changed')
            for test in report['tests']:
                text = observe(directory/(test+'.log'))
                require('TEST_PASS' in text and 'XU_ACCEL_PE32_BANK128=1' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:',text), 'actual compact-W32 legacy execution differs')
    sys.path.insert(0,str(source/'tools/scripts'))
    import e203_soc as soc
    results = {}
    cases = [('synthetic1','synthetic',1,'pe32-bank128','bias-hw-pe32-autogroup-window'),
             ('synthetic2','synthetic',2,'pe32-bank128','bias-hw-pe32-autogroup-window'),
             ('real12','real',12,'pe32-bank128','bias-hw-pe32-autogroup-window'),
             ('old32-wide-real12','real',12,'pe32','bias-hw-pe32-autogroup-window'),
             ('bank128-oldauto-real12','real',12,'pe32-bank128','bias-hw-autogroup-window')]
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
        require(observed_hash(directory/'accel_soc') == report['firmware_elf_sha256'] and observed_hash(directory/'accel_soc.verilog') == report['firmware_image_sha256'], 'ELF/image changed')
        simulator = source/'build/e203'/('sim-'+soc.build_key(report,'vcs',False))/'accel_soc'
        argv = json.loads(observe(directory/'simulation.log').split('\n',1)[0])
        require(Path(argv[0]).resolve() == simulator.resolve() and simulator.is_file() and not simulator.is_symlink() and
                observed_hash(simulator) == report['simulator_sha256'], 'actual accepted VCS simulator binary changed')
        receipt = json.loads(observe(simulator.parent/'vcs-build.json'))
        require(receipt['binary_sha256'] == report['simulator_sha256'], 'actual VCS build receipt changed')
        results[name] = report
    real = {name:result for name,result in results.items() if result['mode'] == 'real'}
    wide = real['real12']; old32 = real['old32-wide-real12']; compat = real['bank128-oldauto-real12']
    for key in ['source_sha256','versions','tools','fixture','vectors','firmware_sha256','runner_sha256','contract_sha256']:
        require(all(value[key] == wide[key] for value in real.values()), 'three-way common identity mismatch: '+key)
    require(wide['simulator_sha256'] == compat['simulator_sha256'] != old32['simulator_sha256'],
            'same compact-W/different original-W executable identities required')
    require(wide['firmware_image_sha256'] == old32['firmware_image_sha256'], 'same-wide firmware image differs')
    # No improvement is assumed: retain independently measured layers and work.
    comparison = json.loads(observe(acceptance/'full12-comparison.json'))
    rows = [dict(layer=left['layer'],bank128_wide_cycles=left['cycles'],old32_wide_cycles=middle['cycles'],
                 bank128_oldauto_cycles=right['cycles'])
            for left,middle,right in zip(wide['layers'],old32['layers'],compat['layers'])]
    totals = {key:sum(row[key] for row in rows) for key in ['bank128_wide_cycles','old32_wide_cycles','bank128_oldauto_cycles']}
    require(comparison['status'] == 'VCS_ACCEPTED_NOT_RETAINED' and comparison['rows'] == rows and
            comparison['totals'] == totals and comparison['designated_model'] == model_record,
            'three-way measured full12 comparison differs')
    require(comparison['result_sha256'] == {name:sha(stock/name/'result.json') for name in real},
            'comparison result provenance differs')
    observe(acceptance/'state.json')
    for name,digest in observed.items(): require(sha(Path(name)) == digest, 'acceptance artifact changed during review: '+name)
    require(ppa.source_profile_identity(source,'s3-pe32-bank128') == freeze, 'accepted complete source changed during review')
    return dict(state_sha256=sha(acceptance/'state.json'), source_profile=freeze,
                reviewed_artifacts_sha256=observed,
                result_sha256={name:sha(stock/name/'result.json') for name in results},
                measured_total_cycles={name:sum(layer['cycles'] for layer in result['layers']) for name,result in results.items()})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=BASE/'ChipContest-bank128-02')
    p.add_argument('--acceptance',type=Path,default=BASE/'s3-pe32-bank128-accept-02')
    p.add_argument('--producer-root',type=Path,default=TOOLS)
    p.add_argument('--out',type=Path,default=BASE/'s3-pe32-bank128-ppa-campaign-20261103-01')
    p.add_argument('--standard-cell-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db')
    p.add_argument('--sram-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db')
    p.add_argument('--weight-sram128-db',type=Path,default=BASE/'s1-ppa-campaign-01/xu-ramsp128x16-ss-0p99v-125c.db')
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
    state=dict(status='RUNNING_NOT_QUALIFIED',source=str(source),producer_root=str(producer),profile='s3-pe32-bank128',steps=[])
    def save():
        state['updated_utc']=datetime.now(timezone.utc).isoformat()
        (out/'state.json').write_text(json.dumps(state,indent=2)+'\n')
    try:
        state['acceptance']=checked_acceptance(source,a.acceptance.resolve(),producer);save()
        libraries = [(a.standard_cell_db,STANDARD_SHA),(a.sram_db,SRAM_SHA),(a.weight_sram128_db,SRAM128_SHA)]
        for path,digest in libraries:
            require(path.is_file() and not path.is_symlink() and sha(path)==digest,'same-server frozen library SHA differs: '+str(path))
        state['libraries'] = [dict(path=str(path.resolve()),sha256=digest,bytes=path.stat().st_size) for path,digest in libraries]
        save()
        spec=importlib.util.spec_from_file_location('xu_bank128_implementation',producer/'tools/ppa/xu_soc_implementation.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);ppa=module.ppa_module()
        require(ppa.SOURCE_PROFILES['s3-pe32-bank128']['commit']==CHILD and ppa.BANK128_CONFIGURATION['full_soc_macros']==448,
                'producer lacks approved complete mixed448 geometry profile')
        commands=[
            [sys.executable,producer/'tools/ppa/xu_soc_implementation.py','--root',source,'--profile','s3-pe32-bank128','--out',out/'implementation',
             '--standard-cell-db',a.standard_cell_db,'--standard-cell-sha256',STANDARD_SHA,'--sram-db',a.sram_db,'--sram-sha256',SRAM_SHA,
             '--weight-sram128-db',a.weight_sram128_db,'--weight-sram128-sha256',SRAM128_SHA],
            [sys.executable,producer/'tools/scripts/xu_soc_ppa.py','prepare','--root',source,'--implementation',out/'implementation/implementation.json',
             '--out',out/'ppa','--allow-unqualified-mapping'],
            [sys.executable,producer/'tools/scripts/xu_soc_ppa.py','run','--root',source,'--out',out/'ppa']]
        state['tool_sha256']={name:sha(producer/name) for name in ['tools/ppa/xu_soc_implementation.py','tools/scripts/xu_soc_ppa.py','tools/ppa/xu_weight128_sram_adapter.sv']}
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
        for record in state['libraries']:
            path=Path(record['path'])
            require(path.is_file() and not path.is_symlink() and path.stat().st_size==record['bytes'] and sha(path)==record['sha256'], 'library changed during campaign')
        checked_acceptance(source,a.acceptance.resolve(),producer)
        state.update(status='EXECUTED_NOT_QUALIFIED',execution_sha256=sha(out/'ppa/execution.json'),
            not_run=['candidate-specific formal clear/request activity','mapped consistency','fullSoC task energy','retention'])
    except Exception as error:
        state.update(status='FAIL',error=str(error));save();raise
    save();print('XU_BANK128_PPA_DONE '+state['status'],flush=True)


if __name__=='__main__':
    main()
