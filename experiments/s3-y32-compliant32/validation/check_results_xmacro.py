#!/usr/bin/env python3
"""Reject incomplete32bit CPU traces, source loading omissions and early completion."""
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



def check_records(log,tasks,rows,prefix='C32'):
    groups={
      'layers':records(log,prefix+'_TASK_PASS',['layer','rows','outputs','total','load_to_y','loading','clear','dma_payload','firmware_cycles','start_to_done']),
      'windows':records(log,prefix+'_WINDOW',['layer','load_begin','load_finish','first_request','first_accept','last_y_response','clear_request','clear_done','start','done']),
      'counts':records(log,prefix+'_COUNTS',['layer','reads','w_reads','bias_reads','x_reads','writes','write_responses','requests','responses','pops','macs','mmio_reads','mmio_writes']),
      'endpoints':records(log,prefix+'_ENDPOINT',['layer','requests','responses','outstanding','source_reads','source_writes','y_writes','y_write_responses']),
      'channels':records(log,prefix+'_CHANNEL',['layer','wb_cycles','xy_window','dma_stall','source_stall','write_stall','max_outstanding','endpoint_first_offer','endpoint_first_accept','forced_wait','load_endpoint_offer','load_endpoint_accept','forced_load_wait']),
    }
    if any(len(v)!=tasks for v in groups.values()):raise ValueError('missing/duplicate full-load layer evidence')
    for i,(item,window,count,endpoint,channel) in enumerate(zip(*groups.values())):
        if any(r['layer']!=i for r in [item,window,count,endpoint,channel]):raise ValueError('task identity/order mismatch')
        if item['rows']!=rows or item['outputs']!=25344:raise ValueError('mode/output scope mismatch')
        if item['total']!=window['last_y_response']-window['clear_request']+1:raise ValueError('full load-through-retirement timing boundary')
        if item['load_to_y']!=window['last_y_response']-window['load_begin']+1:raise ValueError('load-to-lastY boundary')
        if item['loading']!=window['load_finish']-window['load_begin']+1:raise ValueError('source load boundary')
        if item['clear']!=window['clear_done']-window['clear_request']+1:raise ValueError('clear boundary')
        if item['dma_payload']!=window['last_y_response']-window['first_request']+1:raise ValueError('DMA boundary')
        if not (window['clear_request']<=window['clear_done']<window['load_begin']<=window['load_finish']<window['start']<=window['first_request']<=window['first_accept']<=window['last_y_response']<window['done']):raise ValueError('ownership/timing order')
        if item['total']<item['loading']+item['clear']+item['dma_payload']:raise ValueError('load/clear/work omitted')
        if item['start_to_done']!=window['done']-window['start']+1:raise ValueError('start/done duration')
        if item['firmware_cycles']<window['done']-window['clear_request']+1:raise ValueError('firmware duration excludes internal work')
        if i and window['clear_request']<=groups['windows'][i-1]['done']:raise ValueError('overlapping task windows')
        expected=dict(reads=15040,w_reads=8192,bias_reads=512,x_reads=6336,writes=25344,write_responses=25344,requests=40384,responses=40384,pops=3168,macs=((99+rows-1)//rows)*32*64,mmio_writes=6)
        if any(count[k]!=v for k,v in expected.items()):raise ValueError('transaction/MAC count mismatch')
        if count['mmio_reads']<=0 or channel['max_outstanding']!=1:raise ValueError('CPU polling or DMA occupancy differs')
        if channel['load_endpoint_accept']-channel['load_endpoint_offer']<channel['forced_load_wait']:raise ValueError('forced source loading wait omitted')
        if channel['load_endpoint_offer']<window['load_begin']:raise ValueError('loading timestamp after actual source offer')
        if channel['endpoint_first_accept']-channel['endpoint_first_offer']<channel['forced_wait']:raise ValueError('forced endpoint wait omitted')
        if endpoint['requests']-endpoint['responses']!=endpoint['outstanding'] or endpoint['outstanding'] not in [0,1] or endpoint['source_reads']!=15040 or endpoint['source_writes']!=15040 or endpoint['y_writes']!=50688 or endpoint['y_write_responses']!=50688:raise ValueError('endpoint transaction retirement/coverage')
        item.update(window=window,counters=count,endpoint=endpoint,channel=channel)
    total=sum(x['total'] for x in groups['layers'])
    return dict(layers=groups['layers'],outputs=tasks*25344,total_cycles=total,load_to_y_cycles=sum(x['load_to_y'] for x in groups['layers']),source_loading_cycles=sum(x['loading'] for x in groups['layers']),clear_cycles=sum(x['clear'] for x in groups['layers']),dma_payload_cycles=sum(x['dma_payload'] for x in groups['layers']),task_per_second_at_assumed_150mhz=150000000*tasks/total,timing_status='LOCAL_CPU_FULL_LOAD_STIMULUS_NO_STA_OR_OFFICIAL_SDK_SIGNOFF')

def check_physical_clear(log,tasks,warmup,x_macros=False):
    starts=records(log,'C32_PHYSICAL_CLEAR_BEGIN',['call','warmup','nonzero_W','nonzero_BIAS','nonzero_X','observed_last_public_writes'])
    end_fields=['call','warmup','W','BIAS','X','total16bit_writes','physical_cycles','X_REGS','ACC','ENGINE_RESULT','FIFO','BIAS_CACHE','DMA_SNAPSHOT','all_addresses','all_payload_zero']
    if x_macros:
        index=end_fields.index('X_REGS')+1;end_fields[index:index]=['X_MACROS','X_USED_WORDS']
    ends=records(log,'C32_PHYSICAL_CLEAR_PASS',end_fields)
    if len(starts)!=tasks+int(warmup) or len(ends)!=len(starts):raise ValueError('physical-clear evidence missing/duplicate')
    expected=dict(W=16384,BIAS=768,X=1024,total16bit_writes=18176,X_REGS=1024,ACC=64,
                  ENGINE_RESULT=64,FIFO=128,BIAS_CACHE=16,DMA_SNAPSHOT=1,all_addresses=1,all_payload_zero=1)
    if x_macros:expected.update(X=16384,total16bit_writes=33536,X_REGS=0,X_MACROS=16,X_USED_WORDS=1024)
    for i,(begin,end) in enumerate(zip(starts,ends)):
        if begin['call']!=i+1 or end['call']!=i+1 or begin['warmup']!=int(warmup and i==0) or end['warmup']!=begin['warmup']:
            raise ValueError('physical-clear call identity')
        if any(end[k]!=v for k,v in expected.items()) or not end['physical_cycles'] or begin['observed_last_public_writes']!=1:
            raise ValueError('physical-clear address/payload totals')
        if i>0 and any(begin[k]==0 for k in ['nonzero_W','nonzero_BIAS','nonzero_X']):raise ValueError('missing publicly dirtied prestate')
        end['dirty_before']=begin
    return ends


def check_log(log,tasks,rows,warmup=True,x_macros=False):
    if re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout|^Error(?:\s|:)',log,re.I|re.M):raise ValueError('failure marker in simulation')
    result=check_records(log,tasks,rows)
    expected=f'C32_SOC_PASS tasks={tasks} rows={rows} outputs={tasks*25344} writes={tasks*25344}'
    if re.findall(r'^C32_SOC_PASS.*$',log,re.M)!=[expected]:raise ValueError('missing complete real-CPU marker')
    if warmup:
        result['warmup']=check_records(log,1,rows,'C32_WARMUP')
        if result['warmup']['layers'][0]['window']['done']>=result['layers'][0]['window']['clear_request']:raise ValueError('warmup overlaps counted task')
        if re.findall(r'^C32_WARMUP_DONE.*$',log,re.M)!=['C32_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1']:raise ValueError('warmup completion missing')
    elif re.search(r'^C32_WARMUP',log,re.M):raise ValueError('unexpected warmup')
    clocks=records(log,'C32_CLOCK',['measured_hf_period_fs','measured_lf_period_fs','hf_edges','lf_edges'])
    if len(clocks)!=1 or clocks[0]['measured_hf_period_fs']!=6666666 or clocks[0]['measured_lf_period_fs']!=30517578126 or min(clocks[0]['hf_edges'],clocks[0]['lf_edges'])<2:raise ValueError('measured clock identity differs')
    result['measured_clock']=clocks[0];result['physical_clear']=check_physical_clear(log,tasks,warmup,x_macros)
    loaders=records(log,'C32_SYSTEMBUS_LOAD_PASS',['call','layer','source_writes','poison_writes','readbacks','ready_sequence'])
    if len(loaders)!=tasks+int(warmup):raise ValueError('SystemBus source loading missing/duplicate')
    for call,item in enumerate(loaders,1):
        if item!=dict(call=call,layer=max(0,call-1-int(warmup)),source_writes=15040,poison_writes=25344,readbacks=25344,ready_sequence=call):raise ValueError('source transaction coverage/identity differs')
    result['systembus_loader']=loaders
    result['scope']='Local original-SystemBus stimulus, complete input/parameter load through last Y response. Official SDK loader compatibility not verified.'
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('--tasks',type=int,required=True);p.add_argument('--rows',type=int,choices=[1,8],default=8);p.add_argument('--no-warmup',action='store_true');a=p.parse_args()
    print(json.dumps(check_log(a.log.read_text(),a.tasks,a.rows,not a.no_warmup),indent=2))
