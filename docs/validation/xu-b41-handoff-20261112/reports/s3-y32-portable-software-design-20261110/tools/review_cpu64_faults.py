#!/usr/bin/env python3
"""Recompute expected CPU64 fault terminals and physical clears from raw logs."""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parents[1]/'hardware64-r1'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def review(evidence,out):
    native=json.loads((evidence/'native-r1/result.json').read_text())
    campaign=evidence/'native-r1/campaign'
    result=json.loads((campaign/'result.json').read_text())
    child=native['child']
    if (native['status']!='PASS' or result['status']!='PASS_CPU64_SOFTWARE_FAULTS' or
        child['native_exit']!=0 or not child['waitpid_completed'] or child['events'] or
        child['remaining_group'] or child['remaining_at_leader_exit']):
        raise ValueError('Fault validation did not pass and drain')
    if sha(campaign/'result.json')!=native['campaign_sha256'] or sha(evidence/'native-r1/control/native.log')!=child['log_sha256']:
        raise ValueError('Fault campaign or native log identity changed')
    control=json.loads((BASE/'strict-control-review-r2.json').read_text())
    if result['normal_control']!=control['native_pins']:
        raise ValueError('Fault design differs from accepted normal control')
    if '--assert' not in result['build_argv'] or any('DISABLE_SV_ASSERTION' in x for x in result['build_argv']):
        raise ValueError('Fault CPU assertions disabled')
    preprocessed=campaign/'preprocessed.sv'
    count=len(re.findall(r'assert\s+property\b',preprocessed.read_text()))
    if count!=6 or count!=result['preprocessed_assert_property_count'] or sha(preprocessed)!=result['preprocessed_sha256']:
        raise ValueError('Fault CPU property proof changed')
    spec=importlib.util.spec_from_file_location('frozen_fault_checker',BASE/'strict-input-r2/source/check_results.py')
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    builds=json.loads((BASE/'candidates-r3/result.json').read_text())
    cases={}
    fields=['mode','error_publications','requests','responses','return_code','busy','pending','locked','ack','done']
    for name,row in result['cases'].items():
        raw_file=campaign/(name+'.log')
        if sha(raw_file)!=row['log_sha256']:
            raise ValueError('Fault raw log changed: '+name)
        raw=raw_file.read_text().split('\n',1)[1]
        parsed=checker.records(raw,'XU_CPU64_FAULT_PASS',fields)
        if len(parsed)!=1 or parsed[0]!=row['result'] or re.search(r'FATAL|%Error|D4K_SOC_PASS',raw):
            raise ValueError('Fault terminal differs: '+name)
        r=parsed[0];profile,mode=name.rsplit('-',1)
        if (r['mode']!={'read':1,'write':2}[mode] or r['error_publications']!=1 or r['return_code']!=5 or
            r['requests']!=r['responses'] or any(r[k] for k in ('busy','pending','locked','ack','done')) or
            row['firmware_image_sha256']!=builds['builds'][profile]['image_sha256']):
            raise ValueError('Fault CPU/retirement contract failed: '+name)
        checker.check_physical_clear(raw,1,False)
        cases[name]=dict(**r,firmware_image_sha256=row['firmware_image_sha256'],raw_log_sha256=sha(raw_file))
    if set(cases)!={n+'-'+m for n in ('tight-O2','backoff_8_256_fast4-O2') for m in ('read','write')}:
        raise ValueError('Priority fault coverage incomplete')
    receipt=dict(status='PASS_RAW_CPU64_FAULT_REVIEW',cases=cases,cpu_assert_properties=count,
        native_sha256=sha(evidence/'native-r1/result.json'),campaign_sha256=sha(campaign/'result.json'),
        simulator_sha256=result['simulator_sha256'],native_seconds=child['seconds'],
        scope='Dedicated expected-error CPU/DMA tests; successful task outputs are not claimed. Software budget is not a hardware watchdog.')
    with out.open('x') as stream:stream.write(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    review(args.evidence,args.out)
