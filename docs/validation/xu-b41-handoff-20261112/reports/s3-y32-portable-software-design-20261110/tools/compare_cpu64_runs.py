#!/usr/bin/env python3
"""Compare the accepted CPU64 firmware runs from raw logs, retaining task scope."""
import argparse
import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'hardware64-r1'
B41_INPUT=BASE/'b41-strict-input-r1'
B41_MANIFEST_SHA256='1d8cd861b75c377ecd7282edd1fa1bdb7dae7a166078d43d6308e3010335a6c6'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    instance=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


def verify_b41(native,campaign,data):
    if native['input_checksum_sha256']!=B41_MANIFEST_SHA256 or native['qualification']!='DEVELOPMENT_RTL_ONLY':
        raise ValueError('Native receipt does not bind the frozen B41 input')
    input_check=load('b41_native_input',B41_INPUT/'run_native.py')
    input_check.inputs(B41_MANIFEST_SHA256)
    prepared=json.loads((B41_INPUT/'prepared.json').read_text())
    if data['source_sha256']!=prepared['source_sha256'] or set(data['variants'])!=set(prepared['software']):
        raise ValueError('B41 RTL or firmware set differs from the frozen input')
    build=data['build_argv']
    if not {'--assert','--timing','-DXU_MATRIX_DMA','-DXU_MATRIX_DMA64'}<=set(build) or any(
            'DISABLE_SV_ASSERTION' in arg for arg in build):
        raise ValueError('B41 CPU assertions or DMA64 build options differ')
    binary_dir=PurePosixPath(build[build.index('-Mdir')+1])
    if not binary_dir.is_absolute() or binary_dir.parts[-3:]!=('native-r1','campaign','obj'):
        raise ValueError('B41 binary is outside the native campaign')
    preprocessed=campaign/'preprocessed.sv'
    count=len(re.findall(r'assert\s+property\b',preprocessed.read_text()))
    if count!=6 or count!=data['preprocessed_assert_property_count'] or sha(preprocessed)!=data['preprocessed_sha256']:
        raise ValueError('B41 preprocessed CPU assertion evidence differs')
    return prepared,binary_dir/'dma64_soc'


def summarize(measured,timeline):
    counted=[stamp for stamp in timeline if not stamp['warmup']]
    summary={k:measured[k] for k in (
        'principal_cycles','payload_cycles','clear_cycles','gap_cycles','including_gap_cycles')}
    for field in ('software_control_cycles','discovery_delay','report_delay',
                  'descriptor_submission_cycles','retired','itcm_accesses','clear_reads','compute_reads'):
        summary[field]=sum(task[field] for task in counted)
    summary['max_report_delay']=max(task['report_delay'] for task in counted)
    summary['firmware_cycles']=sum(layer['firmware_cycles'] for layer in measured['layers'])
    summary['mmio_reads']=sum(layer['counters']['mmio_reads'] for layer in measured['layers'])
    return summary


def compare(evidence,out,build_receipt,b41=False):
    native=json.loads((evidence/'native-r1/result.json').read_text())
    campaign=evidence/'native-r1/campaign'
    data=json.loads((campaign/'result.json').read_text())
    child=native['child']
    expected_status='PASS_STRICT_CPU64_FULL12' if b41 else 'PASS_CPU64_SOFTWARE_SCREEN'
    if (native['status']!='PASS' or data['status']!=expected_status or child['native_exit']!=0 or
        not child['waitpid_completed'] or child['remaining_group'] or child['remaining_at_leader_exit'] or child['events']):
        raise ValueError('Firmware campaign did not pass and drain')
    if native['campaign_sha256']!=sha(campaign/'result.json') or child['log_sha256']!=sha(evidence/'native-r1/control/native.log'):
        raise ValueError('Campaign or native log identity changed')
    if b41:
        prepared,binary=verify_b41(native,campaign,data)
        run_root=binary.parents[3]
        strict_input=B41_INPUT
        parent,child_revision=prepared['parent_revision'],prepared['child_revision']
        tasks,stall=12,0
    else:
        control=json.loads((BASE/'strict-control-review-r2.json').read_text())
        if data['accepted_strict']!=control['native_pins'] or data['simulator_sha256']!=control['simulator_sha256']:
            raise ValueError('Comparison does not use the accepted strict CPU64 design')
        strict_input=BASE/'strict-input-r2'
        parent='d60e0e00d79051747b8adcfa39fca273a6e7e309'
        child_revision='a80dd184536e0f2312c62768d5acf4ba1b01c34e'
        tasks,stall=data['tasks'],data['first_source_stall']
    builds=json.loads(build_receipt.read_text())
    checker=load('frozen_cpu64_checker',strict_input/'source/check_results.py')
    runner=load('frozen_cpu64_runner',strict_input/'run_strict.py')
    observations=[]
    summaries={}
    coverage={}
    for name,row in data['variants'].items():
        path=campaign/(name+'.log')
        if sha(path)!=row['log_sha256'] or builds['builds'][name]['image_sha256']!=row['firmware_image_sha256']:
            raise ValueError('Raw log or firmware identity changed: '+name)
        header,raw=path.read_text().split('\n',1)
        if b41:
            if row['firmware_image_sha256']!=prepared['software'][name]['image_sha256']:
                raise ValueError('B41 log firmware differs from the frozen candidate: '+name)
            argv=json.loads(header)['argv']
            if len(argv)<3 or not argv[2].isdigit() or argv!=row['argv'] or argv!=[
                'taskset','-c',argv[2],str(binary),
                f'+TESTCASE={run_root}/firmware/{name}/dma64_soc',f'+VECTORS={run_root}/vectors',
                '+TASKS=12','+ROWS=8','+WARMUP=1','+MAX_CYCLES=20000000',
                '+FIRST_SOURCE_STALL=0','+DUMPWAVE=0'
            ]:
                raise ValueError('B41 workload or candidate command differs: '+name)
        actual=checker.check_log(raw,tasks,8,True)
        timeline=runner.measurements(checker,raw,actual)
        if stall and any(stamp['source_accepted']-stamp['source_begin']<stall for stamp in timeline):
            raise ValueError('Requested first-source stall was not present in raw timing: '+name)
        if actual!=row['measurements'] or timeline!=row['timeline']:
            raise ValueError('Recomputed raw evidence differs: '+name)
        summaries[name]=summarize(actual,timeline) if b41 else row['summary']
        if b41:
            coverage[name]=dict(measured_outputs=actual['outputs'],warmup_outputs=actual['warmup']['outputs'],
                                physical_clears=len(actual['physical_clear']),target_cycles_met=actual['full12_target_met'])
        for stamp in timeline:
            layer=actual['warmup']['layers'][0] if stamp['warmup'] else actual['layers'][stamp['layer']]
            observations.append(dict(config=name,firmware_image_sha256=row['firmware_image_sha256'],
                **stamp,payload_cycles=layer['payload'],clear_cycles=layer['clear'],gap_cycles=layer['gap'],
                principal_cycles=layer['principal'],firmware_cycles=layer['firmware_cycles'],
                mmio_reads=layer['counters']['mmio_reads']))
    # These are unweighted operation/timing proxies, never a physical-energy rank.
    objectives=['software_control_cycles','max_report_delay','retired','itcm_accesses','mmio_reads']
    eligible={name:summary for name,summary in summaries.items() if not name.startswith('published-')}
    front=[]
    for name,a in eligible.items():
        if not any(all(other[k]<=a[k] for k in objectives) and
                   any(other[k]<a[k] for k in objectives)
                   for key,other in eligible.items() if key!=name):
            front.append(name)
    out.mkdir(parents=True,exist_ok=False)
    with (out/'tasks.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(observations[0]))
        writer.writeheader();writer.writerows(observations)
    record=dict(status='PASS_RAW_CPU64_COMPARISON',tasks_per_variant=tasks,first_source_stall=stall,
        parent_revision=parent,child_revision=child_revision,
        native_sha256=sha(evidence/'native-r1/result.json'),campaign_sha256=sha(campaign/'result.json'),
        simulator_sha256=data['simulator_sha256'],source_build_receipt_sha256=sha(build_receipt),
        tasks_csv_sha256=sha(out/'tasks.csv'),native_seconds=child['seconds'],
        summaries=summaries,
        timing_operation_proxy_front=front,proxy_objectives=objectives,
        physical_energy=None,official_score=None,
        scope='Real CPU64 execution with SVA and original functional checks. warmup separately tagged in CSV. Operation counts do not establish energy benefit or official eligibility.')
    if b41:
        record.update(input_manifest_sha256=B41_MANIFEST_SHA256,cpu_assert_properties=6,
            raw_preprocessed_sha256=data['preprocessed_sha256'],coverage=coverage)
    (out/'result.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=record['status'],tasks_per_variant=tasks,
        timing_operation_proxy_front=front,summaries=record['summaries']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--builds-receipt',type=Path,default=BASE/'candidates-r3/result.json')
    parser.add_argument('--b41',action='store_true',help='Review the frozen B41 full12 campaign')
    args=parser.parse_args()
    compare(args.evidence.resolve(),args.out.resolve(),args.builds_receipt.resolve(),args.b41)
