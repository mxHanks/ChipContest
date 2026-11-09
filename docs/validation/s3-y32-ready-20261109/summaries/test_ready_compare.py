#!/usr/bin/env python3
"""Adversarial saved-evidence checks; never launch a hardware simulator.

Each file mutation is an atomic replacement in a temporary hardlink clone.
The measured campaign bytes are never modified. Negative fixtures are labelled
as synthetic corruption tests, not hardware experiment results.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ready_compare',ROOT/'ready_compare.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


def replace_bytes(path,data):
    temporary=path.with_name(path.name+'.replacement')
    temporary.write_bytes(data)
    temporary.replace(path)


def save_json(path,data):
    replace_bytes(path,(json.dumps(data,indent=2)+'\n').encode())


def clone_campaign(source,destination):
    report=M.read_json(source/'result.json');plan=M.read_json(source/'plan.json')
    old_out=Path(plan['arguments']['out'])
    required={'result.json','plan.json','clear-recipe.json','s3_clear_main.c','tb.sv',
              'rtl.f','accel_soc','accel_soc.verilog'}
    required.update('source/'+p for p in report['original_source_sha256'])
    required.update(step['name']+'.log' for step in report['steps'])
    first=next(s for s in report['steps'] if s['name'].endswith('/simulation'))
    binary=first['command'][0]
    required.add(str(Path(binary).relative_to(old_out)))
    for task in report['task_results']:
        prefix='task-%02d/vectors/'%task['original_layer']
        required.update(prefix+p for p in task['vectors'])
    for relative in required:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        os.link(source/relative,target)
    return report


def mutate_log(folder,report,transform,command_transform=None):
    step=next(s for s in report['steps'] if s['name'].endswith('/simulation'))
    path=folder/(step['name']+'.log')
    first,_,output=path.read_text().partition('\n')
    if command_transform:
        command_transform(step['command'])
        step['command_sha256']=hashlib.sha256(json.dumps(step['command'],separators=(',',':')).encode()).hexdigest()
    data=(json.dumps(step['command'])+'\n'+transform(output)).encode()
    replace_bytes(path,data)
    step['log_sha256']=hashlib.sha256(data).hexdigest()
    save_json(folder/'result.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--source-pairs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    args.candidate=args.candidate.resolve();args.baseline=args.baseline.resolve()
    pins=ROOT/'selected-baseline-sources.json'
    candidate_layers=M.read_json(args.candidate)['original_layers']
    full12=candidate_layers==list(range(12))
    layer_arguments=[] if full12 else ['--layers',','.join(map(str,candidate_layers))]
    cases=[]
    def reject(label,mutate,expected,*,source_pairs=None,extra=None):
        with tempfile.TemporaryDirectory(prefix='ready-evidence-negative-',dir=ROOT) as temp:
            folder=Path(temp)/'candidate';report=clone_campaign(args.candidate.parent,folder)
            mutate(folder,report)
            command=[sys.executable,'-E','-B',str(ROOT/'ready_compare.py'),str(args.baseline),
                str(folder/'result.json'),'--baseline-sources',str(pins),'--source-pairs',
                str(source_pairs or args.source_pairs),*layer_arguments,'--out',str(Path(temp)/'comparison.json')]
            if extra: command=extra(command)
            result=subprocess.run(command,text=True,capture_output=True)
            diagnostic=result.stdout+result.stderr
            if result.returncode!=1 or expected not in diagnostic:
                raise AssertionError(label+': expected rejection '+expected+'; got '+diagnostic)
            cases.append(dict(case=label,status='EXPECTED_REJECTION',diagnostic=diagnostic.strip()))
    # Campaign status is a hard precondition even when every artifact exists.
    def status(folder,report):report['status']='FAIL';save_json(folder/'result.json',report)
    reject('failed_campaign',status,'campaign has not passed')
    def source_bytes(folder,report):
        path=folder/'source/rtl/subsys/xu_nice_drain8.v'
        replace_bytes(path,path.read_bytes()+b'\n// synthetic corruption\n')
    reject('unhashed_source_byte',source_bytes,'artifact SHA differs')
    def image(folder,report):
        path=folder/'accel_soc.verilog';data=path.read_text().split()
        index=next(i for i,t in enumerate(data) if len(t)==2 and not t.startswith('@'))
        data[index]='00' if data[index]!='00' else '01'
        replace_bytes(path,(' '.join(data)+'\n').encode());report['firmware_image_sha256']=M.digest(path)
        save_json(folder/'result.json',report)
    reject('image_rehashed_but_not_ELF_load',image,'firmware image bytes differ from ELF PT_LOAD')
    def missing_ready(folder,report):
        mutate_log(folder,report,lambda s:'\n'.join(line for line in s.split('\n') if not line.startswith('READY_TASK ')))
    reject('missing_raw_READY_marker',missing_ready,'ready activity')
    def duplicate_ready(folder,report):
        def add(s):return s+next(line for line in s.splitlines() if line.startswith('READY_TASK '))+'\n'
        mutate_log(folder,report,add)
    reject('duplicate_raw_READY_marker',duplicate_ready,'ready activity')
    def poll_ready(folder,report):
        mutate_log(folder,report,lambda s:s.replace('status_polls=0 snapshots=3168','status_polls=1 snapshots=3168'))
        report['task_results'][0]['ready_activity']['status_polls']=1;save_json(folder/'result.json',report)
    reject('READY_marker_claims_bus_poll',poll_ready,'ready wait/group/POP/final-response coverage differs')
    def numeric(folder,report):
        mutate_log(folder,report,lambda s:s.replace('TASK_PASS layer=0 outputs=25344','TASK_PASS layer=0 outputs=25343'))
    reject('numerical_output_coverage',numeric,'complete numerical task markers missing or inconsistent')
    def selector(folder,report):
        mutate_log(folder,report,lambda s:s,lambda command:command.remove('+NICE_READY=1'))
    reject('missing_exact_READY_runtime_selector',selector,'exact profile runtime selector differs')
    def clear_c(folder,report):
        path=folder/'s3_clear_main.c';replace_bytes(path,path.read_bytes()+b'\n/* synthetic semantic identity drift */\n')
        recipe=M.read_json(folder/'clear-recipe.json');recipe['generated_c_sha256']=M.digest(path)
        save_json(folder/'clear-recipe.json',recipe)
    reject('rehashed_generated_clear_C_drift',clear_c,'generated clear C differs beyond')
    def vectors(folder,report):
        task=report['task_results'][0];relative=next(p for p in task['vectors'] if p.endswith('/x.mem'))
        path=folder/('task-%02d/vectors/'%task['original_layer'])/relative
        replace_bytes(path,path.read_bytes()+b'\n');task['vectors'][relative]=M.digest(path)
        save_json(folder/'result.json',report)
    reject('rehashed_input_vector_identity',vectors,'task input/clock differs: vectors')
    # A partial experiment cannot silently become a full12 claim; a final
    # twelve-layer candidate cannot silently project away eleven layers.
    if full12:
        reject('full12_cannot_silently_drop_candidate_layers',lambda f,r:None,
            'partial comparison must include every original candidate layer',extra=lambda cmd:cmd+['--layers','0'])
    else:
        reject('partial_requires_explicit_layer_projection',lambda f,r:None,
            'full12 comparison requires twelve candidate layers',extra=lambda cmd:cmd[:cmd.index('--layers')]+cmd[cmd.index('--layers')+2:])
    pairs=M.read_json(args.source_pairs)
    for label,change,expected in (
        ('unauthorized_core_source_pair',lambda p:p.update({'rtl/core/e203_lsu.v':[M.read_json(pins)['rtl/core/e203_lsu.v'],'0'*64]}),'invalid/unreviewable source pair'),
        ('missing_declared_firmware_pair',lambda p:p.pop('tests/e203/firmware/accel.c'),'source manifest differs'),
        ('wrong_baseline_source_pair_SHA',lambda p:p['rtl/subsys/xu_nice_drain8.v'].__setitem__(0,'0'*64),'source pair baseline SHA or candidate SHA differs')):
        with tempfile.TemporaryDirectory(prefix='ready-negative-pairs-',dir=ROOT) as temp:
            changed=json.loads(json.dumps(pairs));change(changed);path=Path(temp)/'pairs.json';save_json(path,changed)
            reject(label,lambda f,r:None,expected,source_pairs=path)
    # A reviewed header pair can document the ABI but cannot alter it.
    with tempfile.TemporaryDirectory(prefix='ready-negative-header-',dir=ROOT) as temp:
        relative='tests/e203/firmware/accel.h'
        original=(args.candidate.parent/'source'/relative).read_bytes()
        changed=original.replace(b'int accel_linear(',b'long accel_linear(',1)
        assert changed!=original
        header_sha=hashlib.sha256(changed).hexdigest()
        header_pairs=json.loads(json.dumps(pairs));header_pairs[relative][1]=header_sha
        pair_path=Path(temp)/'pairs.json';save_json(pair_path,header_pairs)
        def header_noncomment(folder,report):
            replace_bytes(folder/'source'/relative,changed)
            report['original_source_sha256'][relative]=header_sha
            plan=M.read_json(folder/'plan.json');plan['original_source_sha256'][relative]=header_sha
            save_json(folder/'plan.json',plan);save_json(folder/'result.json',report)
        reject('header_noncomment_change_even_with_exact_pair',header_noncomment,
            'accel.h changes beyond documentation comments are prohibited',source_pairs=pair_path)
    # This directly exercises the independent loader's legacy profile guard,
    # beyond the CLI's separately fixed baseline-result identity.
    with tempfile.TemporaryDirectory(prefix='ready-negative-legacy-',dir=ROOT) as temp:
        folder=Path(temp)/'legacy';report=clone_campaign(args.baseline.parent,folder)
        task=report['task_results'][0];old_polls=task['nice_activity']['status_polls']
        old_mmio=task['performance']['mmio_reads']
        task['nice_activity']['status_polls']=0;task['performance']['mmio_reads']=2
        mutate_log(folder,report,lambda s:s.replace('status_polls='+str(old_polls),'status_polls=0').replace('mmio_reads='+str(old_mmio),'mmio_reads=2'))
        try:
            M.load_campaign(folder/'result.json','stream32-pe8',M.read_json(pins))
        except ValueError as error:
            assert 'legacy stream NICE status coverage incomplete' in str(error),str(error)
            cases.append(dict(case='legacy_profile_cannot_accept_zero_status_polls',
                status='EXPECTED_REJECTION',diagnostic=str(error)))
        else:
            raise AssertionError('legacy profile silently accepted zero status polls')
    args.out.write_text(json.dumps(dict(status='NEGATIVE_COMPARATOR_CHECKS_PASS',count=len(cases),
        candidate=str(args.candidate),candidate_result_sha256=M.digest(args.candidate),
        baseline=str(args.baseline),baseline_result_sha256=M.digest(args.baseline),
        comparator_sha256=M.digest(ROOT/'ready_compare.py'),original_candidate_layers=candidate_layers,full12=full12,
        scope='synthetic saved-evidence corruption; no simulator or synthesis invoked; originals untouched',cases=cases),indent=2)+'\n')
    print('READY_COMPARATOR_NEGATIVES_PASS',len(cases))
if __name__=='__main__':main()
