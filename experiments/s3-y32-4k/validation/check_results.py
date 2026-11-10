#!/usr/bin/env python3
"""Strict DMA64 CPU evidence parser; no execution and no result generation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re


def records(log, marker, fields):
    pattern=r'^'+re.escape(marker)+' '+r' '.join(re.escape(f)+r'=(\d+)' for f in fields)+r'$'
    found=[dict(zip(fields,map(int,m))) for m in re.findall(pattern,log,re.M)]
    if len(found)!=len(re.findall(r'^'+re.escape(marker)+r'\b',log,re.M)):
        raise ValueError('malformed '+marker)
    return found


def check_records(log,tasks,rows,prefix='D4K'):
    groups={
      'layers':records(log,prefix+'_TASK_PASS',['layer','rows','outputs','payload','clear','principal','gap','including_gap','firmware_cycles','start_to_done']),
      'windows':records(log,prefix+'_WINDOW',['layer','first_request','first_accept','last_y_response','clear_request','clear_done','start','done']),
      'counts':records(log,prefix+'_COUNTS',['layer','reads','w_reads','bias_reads','x_reads','writes','write_responses','requests','responses','pops','macs','mmio_reads','mmio_writes']),
      'channels':records(log,prefix+'_CHANNEL',['layer','wb_cycles','xy_window','dma_stall','source_stall','write_stall','max_outstanding']),
    }
    if any(len(v)!=tasks for v in groups.values()):raise ValueError('missing/duplicate layer evidence')
    for i,(item,window,count,channel) in enumerate(zip(*groups.values())):
        if any(r['layer']!=i for r in [item,window,count,channel]):raise ValueError('layer identity/order mismatch')
        if item['rows']!=rows or item['outputs']!=25344:raise ValueError('mode/output scope mismatch')
        if item['payload']!=window['last_y_response']-window['first_request']+1:raise ValueError('payload boundary')
        if item['clear']!=window['clear_done']-window['clear_request']+1:raise ValueError('clear boundary')
        if item['principal']!=item['payload']+item['clear']:raise ValueError('principal sum')
        if item['gap']!=window['first_request']-window['clear_done']-1:raise ValueError('gap boundary')
        if item['including_gap']!=item['principal']+item['gap']:raise ValueError('including-gap sum')
        if not (window['clear_request']<=window['clear_done']<window['start']<=window['first_request']<=window['first_accept']<=window['last_y_response']<window['done']):
            raise ValueError('ownership/timing order')
        if item['start_to_done']!=window['done']-window['start']+1:raise ValueError('start/done duration')
        if item['firmware_cycles']<item['including_gap']:raise ValueError('firmware duration excludes measured work')
        if i and window['clear_request']<=groups['windows'][i-1]['done']:raise ValueError('overlapping/reused task windows')
        expected=dict(reads=7520,w_reads=4096,bias_reads=256,x_reads=3168,writes=12672,
                      write_responses=12672,requests=20192,responses=20192,pops=3168,
                      macs=((99+rows-1)//rows)*32*64,mmio_writes=6)
        if any(count[k]!=v for k,v in expected.items()):raise ValueError('transaction/MAC count mismatch')
        if count['mmio_reads']<=0 or channel['max_outstanding']!=1:raise ValueError('CPU polling or endpoint occupancy differs')
        item.update(window=window,counters=count,channel=channel)
    total=sum(x['principal'] for x in groups['layers'])
    included=sum(x['including_gap'] for x in groups['layers'])
    return dict(layers=groups['layers'],outputs=tasks*25344,principal_cycles=total,
                payload_cycles=sum(x['payload'] for x in groups['layers']),
                clear_cycles=sum(x['clear'] for x in groups['layers']),
                gap_cycles=sum(x['gap'] for x in groups['layers']),including_gap_cycles=included,
                task_per_second_at_assumed_150mhz=150000000*tasks/total,
                including_gap_task_per_second_at_assumed_150mhz=150000000*tasks/included,
                full12_target_met=tasks==12 and total<=450000 and all(x['principal']<=37500 for x in groups['layers']),
                each_layer_target_met=all(x['principal']<=37500 for x in groups['layers']),
                timing_status='DEVELOPMENT_STIMULUS_ONLY_NO_STA_PASS')


def check_physical_clear(log,tasks,warmup):
    starts=records(log,'D4K_PHYSICAL_CLEAR_BEGIN',['call','warmup','nonzero_W','nonzero_BIAS','nonzero_X','observed_last_public_writes'])
    ends=records(log,'D4K_PHYSICAL_CLEAR_PASS',['call','warmup','W','BIAS','X','total16bit_writes','physical_cycles','X_REGS','ACC','ENGINE_RESULT','FIFO','BIAS_CACHE','DMA_SNAPSHOT','all_addresses','all_payload_zero'])
    if len(starts)!=tasks+int(warmup) or len(ends)!=len(starts):raise ValueError('physical-clear evidence missing/duplicate')
    expected=dict(W=16384,BIAS=768,X=1024,total16bit_writes=18176,X_REGS=1024,ACC=64,
                  ENGINE_RESULT=64,FIFO=128,BIAS_CACHE=16,DMA_SNAPSHOT=1,all_addresses=1,all_payload_zero=1)
    for i,(begin,end) in enumerate(zip(starts,ends)):
        if begin['call']!=i+1 or end['call']!=i+1 or begin['warmup']!=int(warmup and i==0) or end['warmup']!=begin['warmup']:
            raise ValueError('physical-clear call identity')
        if any(end[k]!=v for k,v in expected.items()) or not end['physical_cycles'] or begin['observed_last_public_writes']!=1:
            raise ValueError('physical-clear address/payload totals')
        if i>0 and any(begin[k]==0 for k in ['nonzero_W','nonzero_BIAS','nonzero_X']):raise ValueError('missing publicly dirtied prestate')
        end['dirty_before']=begin
    return ends


def check_log(log,tasks,rows,warmup=True):
    if re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout|^Error(?:\s|:)',log,re.I|re.M):raise ValueError('failure marker in simulation')
    result=check_records(log,tasks,rows)
    result['full12_target_met']=result['full12_target_met'] and warmup
    expected=f'D4K_SOC_PASS tasks={tasks} rows={rows} outputs={tasks*25344} writes={tasks*12672}'
    if re.findall(r'^D4K_SOC_PASS.*$',log,re.M)!=[expected]:raise ValueError('missing complete real-CPU marker')
    if warmup:
        result['warmup']=check_records(log,1,rows,'D4K_WARMUP')
        if result['warmup']['layers'][0]['window']['done']>=result['layers'][0]['window']['clear_request']:raise ValueError('warmup overlaps counted task')
        if re.findall(r'^D4K_WARMUP_DONE.*$',log,re.M)!=['D4K_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1']:
            raise ValueError('warmup completion missing')
    elif re.search(r'^D4K_WARMUP',log,re.M):raise ValueError('unexpected warmup')
    clocks=records(log,'D4K_CLOCK',['measured_hf_period_fs','measured_lf_period_fs','hf_edges','lf_edges'])
    if len(clocks)!=1 or clocks[0]['measured_hf_period_fs']!=6666666 or clocks[0]['measured_lf_period_fs']!=30517578126 or min(clocks[0]['hf_edges'],clocks[0]['lf_edges'])<2:
        raise ValueError('measured clock identity differs')
    result['measured_clock']=clocks[0]
    result['physical_clear']=check_physical_clear(log,tasks,warmup)
    fixtures=records(log,'D4K_PUBLIC_FIXTURE_PASS',['call','layer','source_writes','poison_writes','readbacks','ready_sequence'])
    if len(fixtures)!=tasks+int(warmup):raise ValueError('public fixture records missing/duplicate')
    for call,item in enumerate(fixtures,1):
        expected_layer=max(0,call-1-int(warmup))
        if item!=dict(call=call,layer=expected_layer,source_writes=15040,poison_writes=25344,readbacks=25344,ready_sequence=call):
            raise ValueError('public fixture transaction coverage/identity differs')
    result['public_fixture']=fixtures
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path)
    p.add_argument('--tasks',type=int,required=True);p.add_argument('--rows',type=int,choices=[1,8],required=True)
    p.add_argument('--no-warmup',action='store_true');args=p.parse_args()
    print(json.dumps(check_log(args.log.read_text(),args.tasks,args.rows,not args.no_warmup),indent=2))
