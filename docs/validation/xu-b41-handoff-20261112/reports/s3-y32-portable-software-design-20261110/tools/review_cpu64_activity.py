#!/usr/bin/env python3
"""Recompute actual CPU64 SAIF comparisons and normal-task evidence from files."""
import argparse
import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode=True
BASE=Path(__file__).resolve().parents[1]/'hardware64-r1'
sys.path.insert(0,str(BASE))
from inspect_cpu_saif import inspect


def sha(path):return sha256(path.read_bytes()).hexdigest()


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def review(evidence,out):
    native=json.loads((evidence/'native-r1/result.json').read_text())
    campaign=evidence/'native-r1/campaign'
    data=json.loads((campaign/'result.json').read_text());child=native['child']
    if (native['status']!='PASS' or data['status']!='PASS_CPU64_LOGICAL_ACTIVITY' or child['native_exit']!=0 or
        not child['waitpid_completed'] or child['events'] or child['remaining_group'] or child['remaining_at_leader_exit']):
        raise ValueError('CPU activity did not pass and drain')
    if native['campaign_sha256']!=sha(campaign/'result.json') or child['log_sha256']!=sha(evidence/'native-r1/control/native.log'):
        raise ValueError('Activity campaign or native log changed')
    if (data['accepted_strict']!=json.loads((BASE/'screen-input-r1/accepted-strict.json').read_text()) or
        data['accepted_full12']!=json.loads((BASE/'accepted-full12.json').read_text())):
        raise ValueError('Activity qualification binding changed')
    if '--assert' not in data['build_argv'] or any('DISABLE_SV_ASSERTION' in x for x in data['build_argv']):
        raise ValueError('CPU SVA disabled')
    preprocessed=campaign/'preprocessed.sv'
    if (len(re.findall(r'assert\s+property\b',preprocessed.read_text()))!=6 or
        data['preprocessed_assert_property_count']!=6 or sha(preprocessed)!=data['preprocessed_sha256']):
        raise ValueError('Activity CPU property evidence differs')
    checker=load('activity_review_checker',BASE/'strict-input-r2/source/check_results.py')
    runner=load('activity_review_runner',BASE/'strict-input-r2/run_strict.py')
    full=json.loads((BASE/'full12-evidence-r1/native-r1/campaign/result.json').read_text())
    names={'published-gcc15-O2','tight-O2','backoff_8_256_fast4-O2'}
    if data['variants'].keys()!=names:raise ValueError('Incomplete activity comparison')
    checked={};inventory=None
    for name,row in data['variants'].items():
        work=campaign/name;log=work/'capture.log'
        if sha(log)!=row['capture_log_sha256'] or row['firmware_image_sha256']!=full['variants'][name]['firmware_image_sha256']:
            raise ValueError('Activity firmware/log differs: '+name)
        raw=log.read_text().split('\n',1)[1]
        measured=checker.check_log(raw,1,8,True)
        timeline=runner.measurements(checker,raw,measured)
        mac=checker.records(raw,'XU_CPU64_MAC',['layer','warmup','first','last','first_y'])
        if measured!=row['measurements'] or timeline!=row['timeline'] or mac!=row['mac_windows']:
            raise ValueError('Recomputed functional/time evidence differs: '+name)
        if len(mac)!=2 or [r['warmup'] for r in mac]!=[1,0] or any(r['layer']!=0 for r in mac):
            raise ValueError('MAC warmup/measured identity mismatch')
        for stamp,layer in zip(mac,(measured['warmup']['layers'][0],measured['layers'][0])):
            w=layer['window']
            if not (w['first_request']<=stamp['first']<=stamp['last']<=w['last_y_response'] and stamp['first']<=stamp['first_y']<=w['last_y_response']):
                raise ValueError('MAC/output timestamps inconsistent')
        windows=re.findall(r'^XU_CPU64_ACTIVITY_WINDOW begin_fs=(\d+) end_exclusive_fs=(\d+)$',raw,re.M)
        if len(windows)!=1 or list(map(int,windows[0]))!=row['window_fs']:
            raise ValueError('Raw activity boundaries differ')
        begin,end=row['window_fs'];cycles=measured['including_gap_cycles']
        if end-begin!=cycles*6666666:raise ValueError('Activity cycle duration differs')
        activity=inspect(work/'cpu-task.saif',end-begin,cycles)
        if activity!=row['activity']:raise ValueError('Recomputed SAIF differs')
        key=activity['traced_bits'],activity['paths_sha256']
        if inventory is not None and inventory!=key:raise ValueError('Compared CPU inventories differ')
        inventory=key
        checked[name]=dict(activity=activity,cycles=cycles,measured_task=measured['layers'][0],
            timeline=timeline[1],mac_windows=mac,firmware_image_sha256=row['firmware_image_sha256'])
    baseline=checked['published-gcc15-O2']['activity']['sum_tc']
    comparisons=[dict(config=name,window_cycles=row['cycles'],cpu_traced_bits=row['activity']['traced_bits'],
        cpu_sum_tc=row['activity']['sum_tc'],cpu_tc_change_percent=100*(row['activity']['sum_tc']/baseline-1))
        for name,row in checked.items()]
    out.mkdir()
    with (out/'comparison.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
    result=dict(status='PASS_RAW_CPU64_LOGICAL_ACTIVITY_REVIEW',variants=checked,comparison=comparisons,
        native_sha256=sha(evidence/'native-r1/result.json'),campaign_sha256=sha(campaign/'result.json'),
        simulator_sha256=data['simulator_sha256'],native_seconds=child['seconds'],reviewer_sha256=sha(Path(__file__)),
        inspector_sha256=sha(BASE/'inspect_cpu_saif.py'),physical_energy=None,official_score=None,
        scope='One task0 after warmup. Exact same CPU logical trace inventory, two-state SAIF, aliases retained, clear+gap+payload half-open window. No full-SoC/SRAM macro-pin or power claim.')
    (out/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=result['status'],comparison=comparisons,native_seconds=child['seconds']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();review(args.evidence,args.out)
