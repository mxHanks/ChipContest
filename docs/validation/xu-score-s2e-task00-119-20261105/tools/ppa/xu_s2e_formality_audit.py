#!/usr/bin/env python3
"""Re-audit actual S2e89 native proof without rerunning EDA or rewriting89.

Only the original terminal marker's newline parsing is corrected. All actual
source, DC, own SVF, full-FM inputs and acceptance runtime bytes are rechecked.
Python3.6+, no network/credentials.
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

BASE=Path.home()/'Desktop/xu-score-optimization-20261102'
MAIN='5bf123bfead8f2a37f97f3234d4e40ce8201aae9'
CHILD='a0767db69628ef30e53de2d1e93dd0360c0ccf76'
ORIGINAL_TOOLS='554267f0d34de30289ddd43babeb450da0d1dfc9'
PROFILE='s2e-paired-hi'
STATUS='AUDITED_ORIGINAL_FULL_SOC_FORMALITY_PASS_NOT_QUALIFIED'
NET_SHA='0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
SVF_SHA='1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9'
LOG_SHA='db12cfc23725e1ebfbacad6d8c4a0253487cb066ac47eea41b9e5648d789b174'
TCL_SHA='aa3a42cd56e5d0426acddd3683fe9f4b73e8fe9f5794399d6caaa5d5253aee5b'


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def identity(path):
    path=Path(path).absolute()
    need(path.is_file() and not path.is_symlink(),'regular original file required: '+str(path))
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))


def checked_records(records,label):
    need(isinstance(records,dict) and records,label+' missing')
    for path,record in records.items():need(record==identity(path),label+' actual file changed: '+path)


def native_result(text,returncode=0):
    """Explicit horizontal whitespace cannot consume terminal newline bytes."""
    marker='XU_S2E_FULL_SOC_FORMALITY_PASS'
    need(returncode==0,'native FM return code differs')
    need('Version R-2020.09-SP5' in text,'same native FM version required')
    need(re.findall(r'^('+marker+r')[ \t]*$',text,re.M)==[marker],
         'native full-FM terminal marker missing/duplicated')
    need(not re.search(r'^\s*(?:Error:|Fatal:|FATAL:|XU_S2E_FULL_SOC_FORMALITY_(?:FAIL|SCRIPT_ERROR))',text,re.M),
         'native FM error/failure present')
    need(re.findall(r'^Verification (?:SUCCEEDED|FAILED)[ \t]*$',text,re.M)==['Verification SUCCEEDED'],
         'unique native verification success required')
    need(re.findall(r'^[ \t]*(\d+) Passing compare points[ \t]*$',text,re.M)==['42338'],
         'native full-SoC passing compare point count differs')
    def row(prefix,expected):
        found=re.findall(r'^'+re.escape(prefix)+r'[ \t]+([0-9 \t]+)$',text,re.M)
        need(len(found)==1 and list(map(int,found[0].split()))==expected,'native '+prefix+' scope/statistics differ')
    row('Passing (equivalent)',[17136,0,0,0,144,25019,39,42338])
    row('Failing (not equivalent)',[0]*8)
    row('  Unread',[0,0,0,0,0,511,0,511])
    for prefix in ('Reference design: r:/WORK/xu_soc_ppa_top','Implementation design: i:/WORK/xu_soc_ppa_top'):
        need(len(re.findall(r'^[ \t]*'+re.escape(prefix)+r'[ \t]*$',text,re.M))==1,'native full top scope differs')
    unmatched=re.findall(r'^[ \t]*(\d+)\((\d+)\) Unmatched reference\(implementation\) compare points[ \t]*$',text,re.M)
    need(unmatched and set(unmatched)=={('17','0')},'native unmatched compare-point scope differs')
    need(not re.search(r'^.*(?:Verification FAILED|Aborted compare points|Failing compare points|Unverified compare points).*$',text,re.M),
         'native nonpassing proof coverage present')
    return dict(passing=42338,black_box_pins=17136,ports=144,dff=25019,latches=39,
                unread_dff=511,unmatched_reference_dff=17,unmatched_implementation=0,
                limits='Native full proof with original SRAM blackboxes and synopsys_auto_setup assumptions; not timing or energy qualification')


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def git(root,*argv):
    return subprocess.check_output(['git','--no-replace-objects']+list(argv),cwd=str(root),universal_newlines=True).strip()


def audit(source,tools,original):
    source,tools,original=[Path(path).resolve() for path in (source,tools,original)]
    need(git(tools,'rev-parse','HEAD')==ORIGINAL_TOOLS,'exact immutable original89 producer required')
    need(git(source,'rev-parse','HEAD')==MAIN and git(source/'third-party/e203_hbirdv2','rev-parse','HEAD')==CHILD,
         'exact accepted frozen S2e source required')
    state=json.loads((original/'state.json').read_text())
    need(state.get('status')=='EXECUTED_FORMALITY_FAILED_NOT_QUALIFIED','preserved actual terminal misclassified89 required')
    need(state.get('inputs_before') and state['inputs_before']==state.get('inputs_after'),'original89 tool/library freeze differs')
    checked_records(state['inputs_before'],'original89 tool/library inputs')
    ppa=load('xu_original89_ppa_audit',tools/'tools/scripts/xu_soc_ppa.py')
    profile=ppa.source_profile_identity(source,PROFILE)
    need(state.get('source_before')==state.get('source_after')==profile,'original89 source freeze differs')
    prepared_path=original/'ppa/prepared.json';prepared=json.loads(prepared_path.read_text())
    ppa.verify_prepared(source,original/'ppa',prepared)
    impl=prepared['implementation']
    need(impl.get('source_profile')==PROFILE and impl.get('defines')==['SYNTHESIS','DISABLE_SV_ASSERTION=1'] and
         impl.get('source_freeze',{}).get('profile')==profile,'actual own original prepared source differs')
    need(sum(group['count'] for group in impl['memory_groups'])==336 and
         all(group['macro_ref']=='RAMSP1024X16' for group in impl['memory_groups']),'original fixed336 macro geometry differs')
    libraries=impl['libraries']
    need(len(libraries)==2 and {item['role']:item['sha256'] for item in libraries}=={
         'standard_cell':'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
         'sram':'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'},'same two original libraries required')
    for item in libraries:need(sha(item['path'])==item['sha256'],'actual original library bytes changed')
    netlist,svf=identity(original/'ppa/mapped.v'),identity(original/'ppa/default.svf')
    need(netlist==state.get('netlist') and netlist['sha256']==NET_SHA and svf==state.get('own_svf') and
         svf['sha256']==SVF_SHA,'actual own mapped/SVF bytes differ')
    dc_log=original/'ppa/dc.log';text=dc_log.read_text(errors='replace')
    need(state.get('dc',{}).get('returncode')==0 and state['dc'].get('log_sha256')==sha(dc_log) and
         'Version T-2022.03-SP5-5' in text and
         re.findall(r'^XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED[ \t]*$',text,re.M)==['XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED'] and
         not re.search(r'^\s*(?:Error:|Fatal:|FATAL:|XU_FATAL:)',text,re.M),'actual own original DC incomplete')
    failed_path=original/'formality/state.json';failed=json.loads(failed_path.read_text())
    need(failed==state.get('formality') and failed.get('status')=='FAIL' and
         failed.get('error')=='ValueError: complete own-SVF formal proof failed or incomplete',
         'preserved original misclassification context differs')
    need(failed.get('frozen_before') and failed['frozen_before']==failed.get('frozen_after') and
         len(failed['frozen_before'])==159,'all159 native full-FM frozen inputs required')
    expected={str(original/'ppa'/name) for name in ['mapped.v','default.svf','rtl.f']}
    expected|={str(Path(item['path'])) for item in libraries}
    expected|={str(path) for path in (original/'ppa/rtl').rglob('*') if path.is_file()}
    expected.add(str(original/'formality/verify.tcl'))
    need(set(failed['frozen_before'])==expected,'complete original native full-FM input scope differs')
    checked_records(failed['frozen_before'],'all159 original full-FM inputs')
    fm_log=original/'formality/fm.log';need(failed.get('log')==identity(fm_log) and sha(fm_log)==LOG_SHA,
                                          'actual native original full-FM log changed')
    need(sha(original/'formality/verify.tcl')==TCL_SHA,'actual original full-FM Tcl changed')
    native=native_result(fm_log.read_text(),failed.get('returncode'))
    legacy=re.findall(r'^XU_S2E_FULL_SOC_FORMALITY_PASS\s*$',fm_log.read_text(),re.M)
    need(legacy==['XU_S2E_FULL_SOC_FORMALITY_PASS\n'],'original newline-only false-failure mechanism differs')
    old=load('xu_original89_full_ppa_audit',tools/'tools/ppa/xu_s2e_ppa_server.py')
    acceptance=old.checked_acceptance(source,Path(state['acceptance_before']['state']['path']).parent)
    need(acceptance==state.get('acceptance_before')==state.get('acceptance_after') and
         acceptance['raw_files_checked']==4138,'original source/runtime VCS acceptance changed')
    execution_path=original/'ppa/execution.json';execution=json.loads(execution_path.read_text())
    need(execution.get('dc')==state['dc'] and execution.get('formality')==failed and
         execution.get('netlist_sha256')==NET_SHA and execution.get('analysis_sdc_sha256')==
         '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98',
         'actual original execution/DC/own proof binding differs')
    inputs=dict(state['inputs_before']);inputs.update(failed['frozen_before'])
    for path in [original/'state.json',prepared_path,execution_path,dc_log,failed_path,fm_log,
                 original/'ppa/mapped.sdc',original/'ppa/constraints.sdc',Path(acceptance['state']['path'])]:
        inputs[str(path)]=identity(path)
    return dict(schema='xu-s2e-native-own-fm-audit-context-v1',source_profile=profile,netlist=netlist,own_svf=svf,
                original_root=str(original),original_tools=str(tools),source_root=str(source),native=native,
                acceptance=acceptance,original_status=state['status'],original_formality_status=failed['status'],
                correction='Original regex consumed one terminal newline; native proof succeeded. No EDA rerun or original rewrite.',
                frozen_inputs=inputs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=BASE/'ChipContest-s2e-74')
    parser.add_argument('--original-tools',type=Path,default=BASE/'ChipContest-s2e-ppa-tools-89')
    parser.add_argument('--original',type=Path,default=BASE/'s2e-ppa-campaign-20261104-89')
    parser.add_argument('--out',type=Path,default=BASE/'s2e-own-formality-audit-20261104-109')
    args=parser.parse_args();out=args.out.resolve();need(not out.exists(),'fresh independent109 receipt output required')
    out.mkdir(parents=True)
    state=dict(schema='xu-s2e-native-own-fm-audit-v1',status='RUNNING_NOT_QUALIFIED',started_epoch=time.time(),
               pid=os.getpid(),producer=identity(Path(__file__).resolve()))
    def save():
        target=out/'state.json';temp=out/'state.json.tmp';temp.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');os.replace(str(temp),str(target))
    save()
    try:
        before=audit(args.source,args.original_tools,args.original)
        state['context']=before;save()
        after=audit(args.source,args.original_tools,args.original)
        need(before==after,'actual source/DC/SVF/native proof/runtime changed during109 audit')
        state.update(status=STATUS,frozen_before=before['frozen_inputs'],frozen_after=after['frozen_inputs'],
                     limitations='Re-audit of original native FM only. Original89 failure receipt remains immutable. No timing or energy qualification.')
    except BaseException as error:state.update(status='FAIL',error=type(error).__name__+': '+str(error))
    finally:state['finished_epoch']=time.time();save()
    print(json.dumps(dict(status=state['status'],out=str(out)),sort_keys=True),flush=True)
    return 0 if state['status']==STATUS else 1


if __name__=='__main__':sys.exit(main())
