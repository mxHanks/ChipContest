#!/usr/bin/env python3
"""Verify all returned174 bytes and review164/control receipts; no EDA execution."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import tarfile

HERE=Path(__file__).resolve().parent
SHA='df0166018b47d6ad78917928f23fc77c5a32213b8f386b56610f4e67fa64dfd4'
CONTROL='unified-experiment-control-20261105-150'
AUDIT='s2e-native-pin-streamaudit-20261105-164'


def need(ok,message):
    if not ok:raise ValueError(message)


def analyze(archive):
    spec=importlib.util.spec_from_file_location('xu174_checked171',str(HERE/'check-package.py'))
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    checked,declared=checker.inspect(archive,SHA)
    need(checked['payload_files']==74 and checked['payload_bytes']==5260127,'actual174 totals differ')
    with tarfile.open(str(archive),'r:xz')as tf:
        def read(name):return checker.unique_json(tf.extractfile(name).read())
        snap=read('snapshot171.json');state=read(CONTROL+'/state.json');audit=read(AUDIT+'/state.json')
        need(snap['rejected_sources']==snap['omitted_originals']==[],'174 source rejected/omitted')
        need(all(r['metadata_unchanged_during_read'] for r in snap['captures']),'source changed during copy')
        controller=snap['live_process_observations'][0]
        def same(row):
            left,right=row.get('recorded_identity'),row.get('actual')
            return isinstance(left,dict) and isinstance(right,dict) and all(left.get(k)==right.get(k) for k in ['pid','uid','start_ticks','argv'])
        need(controller['name']=='controller153' and same(controller),'original controller actual identity differs')
        need(state['worker']['sha256']=='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025','controller source differs')
        need(len(state['jobs'])==29 and [k for k,v in state['jobs'].items() if v['status'] in ['RUNNING','RUNNING_ADOPTED']]==
             ['s2e_final155_preflight166'],'actual174 queue active scope differs')
        receipt=read('two-candidate-registration-20261105-170.json')
        need(receipt['status']=='REGISTERED_TWO_CANDIDATE_FOLLOWUPS_NOT_QUALIFIED' and
             receipt['workers_signalled']==receipt['workers_restarted']==0,'170 enrollment differs')
        expected=['s2c_unknown167','s2e_final155_preflight166','s2e_final155_power12_166']
        need([r['job'] for r in receipt['jobs']]==expected,'two-candidate job set differs')
        for row in receipt['jobs']:
            need(row['frozen_before']==row['frozen_after'],'runtime changed during enrollment')
            name=CONTROL+'/registrations/'+row['job']+'.json'
            need(all(row['registration'][k]==declared[name][k] for k in ['bytes','sha256']),'170 registration bytes differ')
        auto=read(CONTROL+'/registrations/two_candidate_autopack173.json')
        need(declared[CONTROL+'/registrations/two_candidate_autopack173.json']['sha256']==
             'a79b39149053169415020e4d17446e321e7dd21c63c23e379cb9805714c8d598','173 registration differs')
        need(auto['native'] is True and auto['process_contains']==auto['output_root'],'173 slot/marker differs')
        need(auto['dependencies']==[dict(id='s2c_unknown167',policy='terminal'),
             dict(id='s2e_final155_power12_166',policy='terminal'),dict(id='s2e_streamaudit164',policy='success')],'173 dependency gates differ')
        need(audit['status']=='STREAM_AUDITED_24_ORIGINAL_REPORTS_NOT_QUALIFIED' and audit['qualification']=='NOT_QUALIFIED','164 terminal differs')
        frozen=audit['original_frozen_inputs_before']
        need(frozen==audit['original_frozen_inputs_after'] and frozen['count']==554 and frozen['all_original_paths_rehashed'],'original130 freeze differs')
        need(audit['native_pin_blocks']==540288 and audit['original_reports_streamed']==24 and
             audit['total_formal_elapsed_cycles']==10420116,'164 counts/cycle scope differs')
        need([r['task_id'] for r in audit['tasks']]==list(range(12)),'164 task set differs')
        rows=[];bytes_replayed=0
        for task in audit['tasks']:
            need(task['status']=='AUDITED_TWO_ORIGINAL_REPORTS_NOT_QUALIFIED' and
                 task['originals_before']==task['originals_after'],'task164 terminal/source differs')
            window=task['activity_window'];measure=task['measured_summary']
            need(window['formal_elapsed_cycles']==868343 and window['duration_ticks']==5788953333333 and
                 measure['duration_ticks']==window['duration_ticks'] and measure['pin_count']==22512,'own S2e window/pin scope differs')
            need([r['phase'] for r in task['phases']]==['before','after'],'two original reports required')
            row=dict(task_id=task['task_id'],elapsed_cycles=window['formal_elapsed_cycles'],duration_fs=window['duration_ticks'],
                q_tx_positive=measure['q_tx_positive'],q_tx_full_window=measure['q_tx_full_window'],pt_log_sha256=task['pt_log']['sha256'])
            for phase in task['phases']:
                first,second=phase['primary'],phase['independent_raw_replay']
                need(first['status']=='EXTRACTED_DIAGNOSTIC_NOT_QUALIFIED' and
                     second['status']=='REPLAYED_EVERY_ORIGINAL_BLOCK_NOT_QUALIFIED' and
                     second['raw_block_sha_and_selected_attribute_text_verified'] is True,'native replay terminal differs')
                need(first['pin_count']==second['pin_count']==22512,'native replay pin scope differs')
                for key in ['original_before','original_after','before_after_counts','measured_native_cross_counts','native_diagnostic_counts','selected_attribute_counts']:
                    need(first[key]==second[key],'independent replay disagrees: '+key)
                need(first['original_before']==first['original_after'] and
                     second['complete_original_bytes_replayed']==first['original_before']['bytes'],'original report identity/byte count differs')
                bytes_replayed+=second['complete_original_bytes_replayed']
                need(first['selected_attribute_counts']['x_probability:NATIVE_ZERO']==22512,'actual native getter count differs')
                row[phase['phase']+'_native_report_sha256']=first['original_before']['sha256']
                if phase['phase']=='after':
                    need(all(k.endswith(':UNCHANGED') and v==22512 for k,v in first['before_after_counts'].items()),'native getter change requires review')
            rows.append(row)
        preflight=read('s2e-final155-power-preflight-20261105-166/result.json')
        jobs={name:dict(status=state['jobs'][name]['status'],reported_status=state['jobs'][name].get('reported_status'),pid=state['jobs'][name].get('pid'))
              for name in ['s2e_streamaudit164']+expected+['two_candidate_autopack173']}
        result=dict(schema='xu-returned-progress174-analysis-v1',qualification='NOT_QUALIFIED',
            archive=dict(bytes=checked['archive']['bytes'],sha256=SHA),payload_files=74,payload_bytes=5260127,
            all_74_returned_bodies_verified=True,source_copy_metadata_unchanged=True,missing_optional_files=len(snap['missing_at_observation']),
            controller_actual_identity_matches=True,jobs=jobs,original130_frozen=frozen,
            audit164=dict(tasks=12,original_reports=24,pin_blocks=540288,server_original_bytes_replayed=bytes_replayed,
                total_elapsed_cycles=10420116,q_tx_positive_per_task=[r['q_tx_positive'] for r in rows],
                q_tx_full_window_per_task=[r['q_tx_full_window'] for r in rows],original_large_reports_returned=False),
            preflight166_status=preflight['status'],new155_full12_energy_j=None,
            limitations=['All source copies are observations, not automatic terminal qualification.',
                'Original large native pin reports remain on server; local replay checks returned independent audit receipts, not their20GB bodies.',
                'Measured unknown Q remains; native x_probability=0 does not prove known physical Q.',
                '167 original unknown fatal remains. Complete mapped function,150MHz and contest energy are not qualified.'])
        return result,rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,default=HERE/'progress174.tar.xz');p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();need(not args.out.exists(),'fresh analysis directory required')
    result,rows=analyze(args.archive);args.out.mkdir(parents=True)
    (args.out/'analysis174.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    with (args.out/'per-layer164.csv').open('w',newline='')as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('VERIFIED174_ALL_BYTES_AND_RECEIPTS_NOT_QUALIFIED',len(rows))


if __name__=='__main__':main()
