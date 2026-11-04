#!/usr/bin/env python3
"""xu bounded-memory audit of original actual36 sidecar; never load its rows.

Retains only 336 macro boundary states and sparse-event pin transition totals.
Each original line contributes to SHA256; original boundary lines are copied
verbatim. The sidecar omits ordinary timestamps, so this is a subset audit.
"""
import argparse,hashlib,json,re
from pathlib import Path
import xu_sram_joint_actual_review as actual

audit=actual.audit
require=audit.require

def stat_record(path):
    s=path.stat();return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,ctime_ns=s.st_ctime_ns)

def review_stream(path,meta,macros,expected_records,boundary_path):
    by_name={m['macro']:m for m in macros};require(len(by_name)==len(macros),'duplicate macro')
    offsets={};offset=0
    for port,width in audit.PORTS:offsets[port]=(offset,width);offset+=width
    begin,end,last_tick,counts={},{},{},{}
    totals={name:[[0]*16 for _ in audit.PINS] for name in by_name}
    event_rows=events=lines=0;digest=hashlib.sha256();observed_bytes=0
    before=stat_record(path)
    with path.open('rb') as stream,boundary_path.open('xb') as boundaries:
        for raw in stream:
            digest.update(raw);observed_bytes+=len(raw);lines+=1
            row=json.loads(raw.decode('ascii'),object_pairs_hook=audit.unique_json)
            name=row['macro'];require(name in by_name,'sidecar extra macro')
            if 'begin_tick' in row:
                require(name not in begin and name not in end and row['begin_tick']==meta['start_tick'] and row['callback_ordinal']==meta['begin_callback_ordinal'],'sidecar begin differs')
                begin[name]=audit.state_text(row['initial_state_lsb_ports']);boundaries.write(raw);continue
            if 'end_tick' in row:
                require(name in begin and name not in end and row['end_tick']==meta['end_tick'] and row['callback_ordinal']==meta['end_callback_ordinal'],'sidecar end differs')
                end[name]=audit.state_text(row['final_state_lsb_ports']);boundaries.write(raw);continue
            require(name in begin and name not in end,'event outside boundary row order')
            tick=audit.number(row['tick']);require(meta['start_tick']<=tick<=meta['end_tick'] and tick>last_tick.get(name,-1),'sidecar timestamp outside window or not increasing per macro')
            last_tick[name]=tick;state=list(audit.state_text(row['pre_state_lsb_ports']))
            boundary=tick in (meta['start_tick'],meta['end_tick']);require(type(row['boundary']) is bool and row['boundary']==boundary,'sidecar boundary flag differs')
            if tick==meta['start_tick']:require(''.join(state)==begin[name],'begin event prestate differs')
            controls=toggling=False;previous=0
            require(type(row['events']) is list and row['events'],'empty sidecar event row')
            for event in row['events']:
                ordinal=audit.number(event['callback_ordinal']);require(ordinal>previous,'row callback ordinal not increasing');previous=ordinal
                require(tick!=meta['start_tick'] or ordinal>meta['begin_callback_ordinal'],'event before begin ordinal')
                require(tick!=meta['end_tick'] or ordinal<meta['end_callback_ordinal'],'event after end ordinal')
                port=event['port'];require(port in offsets,'unknown event port');start,width=offsets[port]
                old,new=event['old'],event['new'];require(type(old) is str and type(new) is str and len(old)==len(new)==width and not (set(old+new)-set('01xz')) and old!=new,'invalid event states')
                require(''.join(state[start:start+width])==old,'event old state differs from replay')
                for i,(a,b) in enumerate(zip(old,new)):
                    if a!=b:totals[name][start+i]['01xz'.index(a)*4+'01xz'.index(b)]+=1
                state[start:start+width]=new;events+=1;counts[name]=counts.get(name,0)+1
                controls|=port in ('CEN','EMA','EMAW','GWEN','RET1N','WEN');toggling|=port in ('CLK','D','Q','RET1N')
            require(boundary or (controls and toggling),'row neither boundary nor simultaneous control/toggling')
            if tick==meta['end_tick']:
                require(''.join(state)==by_name[name]['final_state_lsb_ports'],'end event final state differs')
            event_rows+=1
    require(before==stat_record(path) and observed_bytes==before['bytes'],'sidecar file metadata/length changed while streaming')
    require(set(begin)==set(end)==set(by_name) and event_rows==expected_records,'sidecar boundary membership/record count differs')
    for name,m in by_name.items():
        require(end[name]==m['final_state_lsb_ports'],'direct/sidecar final state differs')
        require(counts.get(name,0)<=m['callback_events'],'sparse callback events exceed total')
        for i,pin in enumerate(audit.PINS):
            direct=m['pin_transitions'][i]
            require(all(a<=b for a,b in zip(totals[name][i],direct)),'sparse subset exceeds direct pin transitions')
            for state in range(4):
                incoming=sum(direct[previous*4+state] for previous in range(4));outgoing=sum(direct[state*4+following] for following in range(4))
                require(incoming-outgoing==int(end[name][i]=='01xz'[state])-int(begin[name][i]=='01xz'[state]),'direct pin transition boundary flow differs')
    return dict(status='STREAMED_BOUNDARY_BALANCE_AND_SPARSE_SUBSET_PASS_NOT_FULL_TRACE_OR_ENERGY',path=str(path.resolve()),bytes=observed_bytes,sha256=digest.hexdigest(),metadata_before_after=before,
        line_count=lines,macro_count=len(macros),boundary_lines=len(begin)+len(end),event_rows=event_rows,sparse_callback_events=events,
        limitations=['Only one line and per-macro counters retained; no 12.3GB read_text or all-events list.',
            'Global duplicate callback ordinals across different macros/timestamps are not exhaustively indexed. Per-row order and per-macro timestamps are checked.',
            'Ordinary single-port timestamps are absent from this sparse sidecar; it is not a full waveform or complete callback trace.',
            'No PT effective same-timestamp condition or energy equivalence is inferred.'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stats',type=Path,required=True);p.add_argument('--sidecar',type=Path,required=True);p.add_argument('--out-dir',type=Path,required=True)
    p.add_argument('--expected-stats-sha256',default='7873dd56bdd18592cb9162f05a6f6e53906a8071da6b4e5104e1edfc484fc3aa');p.add_argument('--expected-sidecar-bytes',type=int,default=12303644205);a=p.parse_args()
    require(a.stats.is_file() and not a.stats.is_symlink() and a.sidecar.is_file() and not a.sidecar.is_symlink(),'regular original inputs required')
    raw=a.stats.read_bytes();require(hashlib.sha256(raw).hexdigest()==a.expected_stats_sha256,'original stats SHA differs')
    meta,macros,footer,header=actual.stats_parts(raw);require(a.sidecar.stat().st_size==a.expected_sidecar_bytes,'original sidecar size differs')
    a.out_dir.mkdir(parents=True,exist_ok=False)
    receipt=review_stream(a.sidecar,meta,macros,footer['simultaneous_records'],a.out_dir/'boundaries.original.jsonl')
    receipt['stats']=dict(path=str(a.stats.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());receipt['transaction_header']=header
    require(a.stats.read_bytes()==raw,'original stats changed while streaming')
    receipt['boundary_original']=dict(path=str((a.out_dir/'boundaries.original.jsonl').resolve()),bytes=(a.out_dir/'boundaries.original.jsonl').stat().st_size,sha256=hashlib.sha256((a.out_dir/'boundaries.original.jsonl').read_bytes()).hexdigest())
    (a.out_dir/'review.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__':main()
