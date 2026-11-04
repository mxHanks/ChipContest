#!/usr/bin/env python3
"""Frozen S2e same-library DC area, own-SVF full Formality and PT development run.

No deployment/network/credentials. Python 3.6 and Git 1.8 compatible.
The candidate main/child remain independent of this producer/tool checkout.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

TOOLS = Path(__file__).resolve().parents[2]
BASE = Path.home()/'Desktop/xu-score-optimization-20261102'
MAIN = '5bf123bfead8f2a37f97f3234d4e40ce8201aae9'
CHILD = 'a0767db69628ef30e53de2d1e93dd0360c0ccf76'
PROFILE = 's2e-paired-hi'
STANDARD_SHA = 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
SRAM_SHA = 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
DC = Path('/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell')
PT = Path('/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell')
FM = Path('/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell')
ASSETS = {'tools/ppa/xu_full_soc.sdc':SDC_SHA,
          'tools/ppa/xu_soc_ppa_top.sv':'8d0e5fd38f2425e7ea8041dd5b8c3a8fd4ce7fa171afb1bf0ebeb6f53446f28a',
          'tools/ppa/xu_shared_icb_sram.sv':'2ebad6ec1870806cb4b770610213aa4d3318e272f6433bf68e6175b15fa25e9d',
          'tools/ppa/xu_sirv_sram_adapter.sv':'b2b2baaa1e105ed794382886439cd2c16fd280a0f29b54c4d925351e6f90a0c5',
          'tools/ppa/xu_weight_sram_adapter.sv':'86b49e6279e9e9ac2c91467028608be8e3ca1caadb811ddd09d379311730d707'}
LIMITS = ('Same S2c libraries/top/geometry/nominal150MHz SDC; development DC area and own-SVF full mapping proof. '
          'PT propagated pre-CTS constraints/coverage/warnings retained; no full150MHz closure, official accuracy, '
          'clear activity, full-SoC task energy, score or retention assertion. Accelerator area limit 2.25mm^2.')


def need(ok,message):
    if not ok: raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def identity(path):
    path=Path(path)
    need(path.is_file() and not path.is_symlink(),'regular immutable input required: '+str(path))
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def write(path,value):
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');os.replace(str(temp),str(path))


def checked_acceptance(source,acceptance):
    state=json.loads((acceptance/'state.json').read_text())
    need(state.get('status')=='EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED' and
         state.get('expected_main')==MAIN and state.get('expected_e203')==CHILD,
         'complete frozen S2e VCS acceptance required')
    need(state.get('frozen_before') and state.get('frozen_before')==state.get('frozen_after'),
         'acceptance runtime freeze differs')
    raw=state.get('raw_files',{})
    need(raw,'complete acceptance raw manifest required')
    for name,expected in raw.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe acceptance raw path')
        actual=identity(acceptance/name)
        need(actual['bytes']==expected['bytes'] and actual['sha256']==expected['sha256'],
             'acceptance raw bytes changed: '+name)
    acceptance_result=json.loads((acceptance/'acceptance.json').read_text())
    names=['host','numeric','vectors','doctor','baseline','synthetic1','synthetic2','real12','autogroup-control-real12']
    need(acceptance_result.get('status')=='PASS' and
         [s['name'] for s in acceptance_result.get('steps',[])]==names and
         all(s['status']=='PASS' for s in acceptance_result['steps']), 'all full VCS steps and same-RTL control required')
    baseline=json.loads((acceptance/'baseline/result.json').read_text())
    need(baseline.get('tests')==['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x'],
         'all five legacy VCS tests required')
    direct=(acceptance/'host-paired-hi-vcs/simulation.log').read_text()
    need(len(re.findall(r'^XU_PAIRED_HI_WRAPPER_PASS\b.*$',direct,re.M))==1 and
         not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b',direct,re.I),'mandatory direct VCS wrapper result required')
    legacy=json.loads((acceptance/'legacy-images/image-equality.json').read_text())
    need(legacy.get('status')=='PASS' and legacy.get('configurations')==len(legacy.get('records',[]))==192,
         'complete same-compiler old firmware image domain required')
    contract=load_module('xu_s2e_accepted_contract',source/'tools/scripts/xu_firmware_contract.py')
    results=[]
    for name,schedule in [('real12','bias-hw-autogroup-paired-hi-window'),
                          ('autogroup-control-real12','bias-hw-autogroup-window')]:
        result=json.loads((acceptance/name/'result.json').read_text())
        need(result.get('status')=='PASS' and result.get('tasks')==12 and result.get('simulator')=='vcs' and
             result.get('mode')=='real' and result.get('main_commit')==MAIN and result.get('e203_commit')==CHILD and
             result.get('outputs')==304128 and result.get('write_words')==608256 and
             result.get('firmware_schedule')==schedule and result.get('firmware_opt')=='-O2' and
             result.get('firmware_experiment')=='both-unroll-no-masks','complete frozen real12 differs: '+name)
        contract.configuration_from_result(result)
        layers=result['layers'];need([r['layer'] for r in layers]==list(range(12)),'incomplete/reordered layers')
        contract.validate_result_activity(result['result_activity'],layers,schedule)
        for row in layers: contract.validate_performance(row['performance'],row['cycles'],schedule)
        text=(acceptance/name/'simulation.log').read_text()
        found=re.findall(r'^TASK_PASS layer=(\d+) outputs=25344 writes=50688 cycles=(\d+) firmware_cycles=(\d+)$',text,re.M)
        need([(int(a),int(b),int(c)) for a,b,c in found]==[(r['layer'],r['cycles'],r['firmware_cycles']) for r in layers] and
             re.findall(r'^SOC_PASS.*$',text,re.M)==['SOC_PASS tasks=12 outputs=304128 writes=608256'],
             'raw complete real12 disagrees with accepted result')
        results.append(result)
    shared=['main_commit','e203_commit','source_sha256','runner_sha256','contract_sha256','versions','tools','vectors','fixture','simulator_sha256']
    for name in shared:need(results[0][name]==results[1][name],'same physical RTL/control differs: '+name)
    return dict(state=identity(acceptance/'state.json'),raw_files_checked=len(raw),
                paired_real12_cycles=sum(r['cycles'] for r in results[0]['layers']),
                control_real12_cycles=sum(r['cycles'] for r in results[1]['layers']))


def formal_script(prepared,ppa_dir):
    impl=prepared['implementation']
    files=[Path(p) for p in (ppa_dir/'rtl.f').read_text().splitlines()]
    need(files and all(p.is_file() for p in files),'complete prepared RTL list required')
    includes=sorted({str(p.parent) for p in files})
    quote=lambda value:'{'+str(value)+'}'
    need(all(not any(c in str(p) for c in '{}\\\r\n') for p in files+list(map(Path,includes))),
         'unsupported formal input path')
    body='set synopsys_auto_setup true\nset hdlin_unresolved_modules black_box\nset verification_timeout_limit 3600\n'
    body+='set_svf '+quote(ppa_dir/'default.svf')+'\n'
    for library in impl['libraries']:body+='read_db -technology_library '+quote(library['path'])+'\n'
    body+='read_sverilog -r -define {'+' '.join(impl['defines'])+'} -vcs {'+' '.join('+incdir+'+p for p in includes)+' -f '+str(ppa_dir/'rtl.f')+'}\n'
    body+='set_top r:/WORK/xu_soc_ppa_top\nread_verilog -i '+quote(ppa_dir/'mapped.v')+'\nset_top i:/WORK/xu_soc_ppa_top\nmatch\nreport_unmatched_points > unmatched.rpt\n'
    body+='if {[verify]} {puts "XU_S2E_FULL_SOC_FORMALITY_PASS";exit 0} else {report_failing_points > failing.rpt;puts "XU_S2E_FULL_SOC_FORMALITY_FAIL";exit 1}\n'
    return 'if {[catch {\n'+body+'} xu_error]} {puts stderr "XU_S2E_FULL_SOC_FORMALITY_SCRIPT_ERROR $xu_error";exit 1}\n'


def run_formal(out,ppa_dir,prepared,env):
    out.mkdir(exist_ok=False)
    script=out/'verify.tcl';script.write_text(formal_script(prepared,ppa_dir))
    inputs=[ppa_dir/'mapped.v',ppa_dir/'default.svf',ppa_dir/'rtl.f',script]+[Path(x['path']) for x in prepared['implementation']['libraries']]
    inputs+=sorted(p for p in (ppa_dir/'rtl').rglob('*') if p.is_file())
    before={str(p):identity(p) for p in inputs}
    result=dict(status='RUNNING_NOT_QUALIFIED',frozen_before=before,command=[str(FM),'-f','verify.tcl'])
    write(out/'state.json',result)
    try:
        with (out/'fm.log').open('x') as stream:
            actual=subprocess.run(result['command'],cwd=str(out),env=env,stdin=subprocess.DEVNULL,
                                  stdout=stream,stderr=subprocess.STDOUT,timeout=4200)
        text=(out/'fm.log').read_text(errors='replace')
        result.update(returncode=actual.returncode,log=identity(out/'fm.log'))
        need('Version R-2020.09-SP5' in text,'same original Formality2020.09-SP5 required')
        need(actual.returncode==0 and re.findall(r'^XU_S2E_FULL_SOC_FORMALITY_PASS\s*$',text,re.M)==['XU_S2E_FULL_SOC_FORMALITY_PASS'] and
             not re.search(r'^\s*(?:Error:|Fatal:|XU_S2E_FULL_SOC_FORMALITY_(?:FAIL|SCRIPT_ERROR))',text,re.M),
             'complete own-SVF formal proof failed or incomplete')
        result['status']='VERIFIED_FULL_SOC_REVIEW_PENDING_NOT_QUALIFIED'
    except BaseException as error:result.update(status='FAIL',error=type(error).__name__+': '+str(error))
    finally:
        try:
            result['frozen_after']={str(p):identity(p) for p in inputs}
            need(result['frozen_after']==before,'formal frozen input changed')
        except BaseException as error:result.update(status='FAIL',integrity_error=type(error).__name__+': '+str(error))
        result['finished_epoch']=time.time();write(out/'state.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=BASE/'ChipContest-s2e-74')
    parser.add_argument('--acceptance',type=Path,default=BASE/'s2e-full-vcs-accept-20261104-74')
    parser.add_argument('--out',type=Path,default=BASE/'s2e-ppa-campaign-20261104-89')
    parser.add_argument('--standard-cell-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db')
    parser.add_argument('--sram-db',type=Path,default=Path.home()/'Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db')
    parser.add_argument('--lc-root',type=Path,default=Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
    parser.add_argument('--foreground',action='store_true')
    args=parser.parse_args();out=args.out.resolve();source=args.source.resolve()
    implementation=load_module('xu_s2e_implementation',TOOLS/'tools/ppa/xu_soc_implementation.py')
    ppa=implementation.ppa_module()
    need(not out.exists(),'fresh independent PPA output required')
    # Refuse missing/dirty candidate or incomplete acceptance before launching EDA.
    freeze=ppa.source_profile_identity(source,PROFILE)
    acceptance=checked_acceptance(source,args.acceptance.resolve())
    if not args.foreground:
        command=[sys.executable,str(Path(__file__).resolve()),'--foreground']+sys.argv[1:]
        log=out.with_name(out.name+'-driver.log');need(not log.exists(),'fresh driver log required')
        with log.open('x') as stream:
            process=subprocess.Popen(command,cwd=str(TOOLS),stdin=subprocess.DEVNULL,stdout=stream,
                                     stderr=subprocess.STDOUT,start_new_session=True)
        print('XU_S2E_PPA_STARTED',process.pid,flush=True);return 0
    out.mkdir(parents=True)
    state=dict(status='RUNNING_NOT_QUALIFIED',pid=os.getpid(),started_epoch=time.time(),source=str(source),
               source_before=freeze,acceptance_before=acceptance,limitations=LIMITS,steps=[])
    save=lambda:write(out/'state.json',state)
    tools=[TOOLS/name for name in ASSETS]+[Path(__file__),TOOLS/'tools/ppa/xu_soc_implementation.py',
           TOOLS/'tools/scripts/xu_soc_ppa.py',TOOLS/'tools/ppa/xu_review_full_soc_clocks.py',TOOLS/'tools/ppa/xu_full_soc_clock_review.tcl',
           args.standard_cell_db,args.sram_db]
    before=None;save()
    try:
        tools += [DC.resolve(),PT.resolve(),FM.resolve()]
        before={str(p):identity(p) for p in tools};state['inputs_before']=before;save()
        for name,digest in ASSETS.items():need(sha(TOOLS/name)==digest,'same S2c tool asset differs: '+name)
        need(sha(args.standard_cell_db)==STANDARD_SHA and sha(args.sram_db)==SRAM_SHA,'same server library bytes differ')
        env=dict(os.environ,SYNOPSYS_LC_ROOT=str(args.lc_root));env['PATH']=os.pathsep.join([str(args.lc_root/'bin'),str(DC.parent),str(PT.parent),str(FM.parent),env.get('PATH','')])
        implementation.generate(source,out/'implementation',args.standard_cell_db,STANDARD_SHA,args.sram_db,SRAM_SHA,profile=PROFILE)
        impl=json.loads((out/'implementation/implementation.json').read_text())
        need(sum(g['count'] for g in impl['memory_groups'])==336 and
             all(g['macro_ref']=='RAMSP1024X16' for g in impl['memory_groups']) and
             impl['defines']==['SYNTHESIS','DISABLE_SV_ASSERTION=1'],'same S2c macro geometry/defines differ')
        prepared=ppa.prepare(source,out/'ppa',impl,True)
        # prepare writes its receipt and returns None in this shared pipeline.
        prepared=json.loads((out/'ppa/prepared.json').read_text());save()
        ppa_dir=out/'ppa'
        state['dc']=ppa.run_tool(ppa_dir,[str(DC),'-f','synth.tcl'],'dc',env)
        need('Version T-2022.03-SP5-5' in (ppa_dir/'dc.log').read_text(errors='replace'),'same original DC2022.03-SP5-5 required')
        need((ppa_dir/'mapped.v').is_file() and (ppa_dir/'default.svf').is_file(),'actual mapped netlist/own SVF missing')
        state['netlist']=identity(ppa_dir/'mapped.v');state['own_svf']=identity(ppa_dir/'default.svf');save()
        # Prioritize actual area + own-SVF equivalence independently of PT gaps.
        state['formality']=run_formal(out/'formality',ppa_dir,prepared,env);save()
        try:
            state['pt']=ppa.run_tool(ppa_dir,[str(PT),'-f','sta.tcl'],'pt-sta',env)
            need('Version T-2022.03-SP5-1' in (ppa_dir/'pt-sta.log').read_text(errors='replace'),'same original PT2022.03-SP5-1 required')
            state['timing_review']=ppa.timing_execution_review(ppa_dir)
        except BaseException as error:
            state['pt']=dict(status='FAIL_OR_INCOMPLETE',error=type(error).__name__+': '+str(error))
        ppa.verify_prepared(source,ppa_dir,prepared)
        execution=dict(schema='xu-full-soc-ppa-execution-v1',
                       status='EXECUTED_NOT_QUALIFIED' if 'timing_review' in state else 'DC_EXECUTED_PT_INCOMPLETE_NOT_QUALIFIED',
                       dc=state['dc'],pt=state['pt'],formality=state['formality'],
                       netlist_sha256=sha(ppa_dir/'mapped.v'),sdc_sha256=sha(ppa_dir/'mapped.sdc'),
                       analysis_sdc_sha256=sha(ppa_dir/'constraints.sdc'),
                       timing_review=state.get('timing_review'),qualification_gaps=prepared.get('qualification_gaps',[]),
                       reports={str(p.relative_to(ppa_dir)):identity(p) for p in ppa_dir.rglob('*') if p.is_file() and p.suffix in ['.rpt','.tsv','.txt']})
        write(ppa_dir/'execution.json',execution)
        state['status']='EXECUTED_NOT_QUALIFIED' if state['formality']['status']=='VERIFIED_FULL_SOC_REVIEW_PENDING_NOT_QUALIFIED' else 'EXECUTED_FORMALITY_FAILED_NOT_QUALIFIED'
    except BaseException as error:state.update(status='FAIL',error=type(error).__name__+': '+str(error))
    finally:
        try:
            state['source_after']=ppa.source_profile_identity(source,PROFILE)
            state['acceptance_after']=checked_acceptance(source,args.acceptance.resolve())
            state['inputs_after']={str(p):identity(p) for p in tools} if before is not None else None
            need(state['source_after']==freeze and state['acceptance_after']==acceptance and (before is None or state['inputs_after']==before),
                 'source/acceptance/tool/library identity changed')
        except BaseException as error:state.update(status='FAIL',integrity_error=type(error).__name__+': '+str(error))
        state['finished_epoch']=time.time();save()
    print('XU_S2E_PPA_DONE '+state['status'],flush=True)
    return 0 if state['status']=='EXECUTED_NOT_QUALIFIED' else 1


if __name__=='__main__':sys.exit(main())
