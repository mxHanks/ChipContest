#!/usr/bin/env python3
"""Review one or more CPU64 profiles replayed on accepted fault/SAIF binaries."""
import argparse
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


def receipts(root,status,pin=None):
    nf=root/'native-r1/result.json';cf=root/'native-r1/campaign/result.json'
    if pin and (sha(nf)!=pin['native_sha256'] or sha(cf)!=pin['campaign_sha256']):
        raise ValueError('Pinned native/campaign identity differs: '+str(root))
    native=json.loads(nf.read_text());campaign=json.loads(cf.read_text());child=native['child']
    if (native['status']!='PASS' or campaign['status']!=status or child['native_exit']!=0 or
        not child['waitpid_completed'] or child['events'] or child['remaining_group'] or child['remaining_at_leader_exit']):
        raise ValueError('Native run did not pass and drain: '+str(root))
    if native['campaign_sha256']!=sha(cf) or child['log_sha256']!=sha(root/'native-r1/control/native.log'):
        raise ValueError('Campaign/native log identity differs')
    return native,campaign


def manifest(root,digest):
    if sha(root/'INPUT.sha256')!=digest:raise ValueError('Input manifest identity differs')
    for line in (root/'INPUT.sha256').read_text().splitlines():
        expected,name=line.split('  ',1);p=Path(name)
        if p.is_absolute() or '..' in p.parts or (root/p).is_symlink() or sha(root/p)!=expected:
            raise ValueError('Input payload differs: '+name)


def review(kind,evidence,input_root,names,out,full12_evidence):
    status={'fault':'PASS_CPU64_SOFTWARE_FAULTS','activity':'PASS_CPU64_LOGICAL_ACTIVITY'}[kind]
    native,data=receipts(evidence,status);campaign=evidence/'native-r1/campaign'
    manifest(input_root,native['input_checksum_sha256'])
    strict_pin=json.loads((input_root/'accepted-strict.json').read_text())
    if data['normal_control' if kind=='fault' else 'accepted_strict']!=strict_pin:
        raise ValueError('Strict design qualification differs from frozen input')
    key='accepted_fault_reuse' if kind=='fault' else 'accepted_activity_reuse'
    reuse_pin=json.loads((input_root/('accepted-'+kind+'-reuse.json')).read_text())
    if data[key]!=reuse_pin:raise ValueError('Reuse binding differs from frozen input')
    old_local={'fault':'fault-evidence-r1','activity':'cpu-activity-evidence-r2'}[kind]
    _,old=receipts(BASE/old_local,status,reuse_pin)
    if (data['build_argv']!=old['build_argv'] or data['simulator_sha256']!=reuse_pin['simulator_sha256'] or
        data['simulator_sha256']!=old['simulator_sha256'] or '--assert' not in data['build_argv'] or
        any('DISABLE_SV_ASSERTION' in s for s in data['build_argv'])):
        raise ValueError('Reused executable/build flags differ')
    preprocessed=campaign/'preprocessed.sv'
    if (data['preprocessed_assert_property_count']!=6 or sha(preprocessed)!=data['preprocessed_sha256'] or
        sha(preprocessed)!=old['preprocessed_sha256'] or len(re.findall(r'assert\s+property\b',preprocessed.read_text()))!=6):
        raise ValueError('Reused CPU property proof differs')
    fixture='tb_dma64_fault_soc.sv' if kind=='fault' else 'tb_dma64_soc.sv'
    if data['fixture_sha256']!=sha(input_root/fixture):raise ValueError('Input fixture differs')
    checker=load('reuse_review_checker',BASE/'strict-input-r2/source/check_results.py')
    runner=load('reuse_review_runner',BASE/'strict-input-r2/run_strict.py')
    builds=json.loads((input_root/'firmware/result.json').read_text())
    checked={}
    if kind=='fault':
        expected={name+'-'+mode for name in names for mode in ('read','write')}
        if set(data['cases'])!=expected:raise ValueError('Requested fault coverage incomplete')
        fields=['mode','error_publications','requests','responses','return_code','busy','pending','locked','ack','done']
        for label,row in data['cases'].items():
            profile,mode=label.rsplit('-',1);path=campaign/(label+'.log')
            if sha(path)!=row['log_sha256'] or row['firmware_image_sha256']!=builds['builds'][profile]['image_sha256']:
                raise ValueError('Fault log/firmware identity differs')
            raw=path.read_text().split('\n',1)[1];records=checker.records(raw,'XU_CPU64_FAULT_PASS',fields)
            if len(records)!=1 or records[0]!=row['result'] or re.search(r'FATAL|%Error|D4K_SOC_PASS',raw):
                raise ValueError('Fault terminal differs')
            r=records[0]
            if (r['mode']!={'read':1,'write':2}[mode] or r['error_publications']!=1 or r['return_code']!=5 or
                r['requests']!=r['responses'] or any(r[k] for k in ('busy','pending','locked','ack','done'))):
                raise ValueError('Fault retirement/CPU contract failed')
            checker.check_physical_clear(raw,1,False)
            checked[label]=dict(**r,firmware_image_sha256=row['firmware_image_sha256'],raw_log_sha256=sha(path))
    else:
        if full12_evidence is None:raise ValueError('Activity review needs --full12-evidence')
        full_pin=json.loads((input_root/'accepted-full12.json').read_text())
        _,full=receipts(full12_evidence,'PASS_CPU64_SOFTWARE_SCREEN',full_pin)
        if data['accepted_full12']!=full_pin or full['tasks']!=12 or full['first_source_stall']!=0:
            raise ValueError('Activity full12 qualification differs')
        if set(data['variants'])!=set(names):raise ValueError('Requested activity coverage incomplete')
        identities={(r['activity']['traced_bits'],r['activity']['paths_sha256']) for r in old['variants'].values()}
        if len(identities)!=1:raise ValueError('Accepted CPU inventories differ')
        expected_inventory=next(iter(identities))
        baseline=old['variants']['published-gcc15-O2']['activity']['sum_tc']
        for name,row in data['variants'].items():
            work=campaign/name;log=work/'capture.log'
            if sha(log)!=row['capture_log_sha256'] or row['firmware_image_sha256']!=builds['builds'][name]['image_sha256'] or row['firmware_image_sha256']!=full['variants'][name]['firmware_image_sha256']:
                raise ValueError('Activity log/firmware identity differs')
            raw=log.read_text().split('\n',1)[1];actual=checker.check_log(raw,1,8,True)
            timeline=runner.measurements(checker,raw,actual)
            mac=checker.records(raw,'XU_CPU64_MAC',['layer','warmup','first','last','first_y'])
            if actual!=row['measurements'] or timeline!=row['timeline'] or mac!=row['mac_windows']:
                raise ValueError('Recomputed activity functional/time evidence differs')
            if len(mac)!=2 or [r['warmup'] for r in mac]!=[1,0] or any(r['layer']!=0 for r in mac):
                raise ValueError('MAC task identity differs')
            prior=full['variants'][name]['measurements']
            for layer,reference,stamp in zip((actual['warmup']['layers'][0],actual['layers'][0]),(prior['warmup']['layers'][0],prior['layers'][0]),mac):
                for field in ('clear','gap','payload','including_gap','outputs','counters','firmware_cycles'):
                    if layer[field]!=reference[field]:raise ValueError('Activity versus full12 exact task0 differs: '+field)
                w=layer['window']
                if not (w['first_request']<=stamp['first']<=stamp['last']<=w['last_y_response'] and stamp['first']<=stamp['first_y']<=w['last_y_response']):
                    raise ValueError('MAC/output order differs')
            windows=re.findall(r'^XU_CPU64_ACTIVITY_WINDOW begin_fs=(\d+) end_exclusive_fs=(\d+)$',raw,re.M)
            if len(windows)!=1 or list(map(int,windows[0]))!=row['window_fs']:raise ValueError('Activity window differs')
            begin,end=row['window_fs'];cycles=actual['including_gap_cycles']
            if end-begin!=cycles*6666666:raise ValueError('Activity clock duration differs')
            activity=inspect(work/'cpu-task.saif',end-begin,cycles)
            if activity!=row['activity'] or (activity['traced_bits'],activity['paths_sha256'])!=expected_inventory:
                raise ValueError('Recomputed SAIF/inventory differs')
            checked[name]=dict(activity=activity,cycles=cycles,measurements=actual,timeline=timeline,mac_windows=mac,
                firmware_image_sha256=row['firmware_image_sha256'],cpu_tc_change_percent=100*(activity['sum_tc']/baseline-1))
    result=dict(status='PASS_RAW_CPU64_REUSE_REVIEW',kind=kind,names=names,results=checked,
        native_sha256=sha(evidence/'native-r1/result.json'),campaign_sha256=sha(campaign/'result.json'),
        simulator_sha256=data['simulator_sha256'],reuse=reuse_pin,native_seconds=native['child']['seconds'],
        reviewer_sha256=sha(Path(__file__)),physical_energy=None,official_score=None,
        scope='Raw replay review on accepted strict executables; error cases do not claim successful outputs. Activity is one task0 after warmup, CPU-only two-state alias-inclusive SAIF, not physical power.')
    with out.open('x') as stream:stream.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=result['status'],kind=kind,names=names,native_seconds=result['native_seconds']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=('fault','activity'),required=True)
    p.add_argument('--evidence',type=Path,required=True);p.add_argument('--input-root',type=Path,required=True)
    p.add_argument('--names',nargs='+',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--full12-evidence',type=Path)
    args=p.parse_args();review(args.kind,args.evidence,args.input_root,args.names,args.out,args.full12_evidence)
