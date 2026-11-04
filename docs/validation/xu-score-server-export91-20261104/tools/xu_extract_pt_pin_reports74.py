#!/usr/bin/env python3
"""xu stream the original 24 native PT attribute reports without loading them whole.

Read-only to the campaign. Compact rows preserve native attribute spelling/text,
block byte ranges/SHA, whole-report actual SHA, original recorded SHA and lazy
attribute-getter diagnostics. No x-to-zero or inferred annotation source.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import lzma
from pathlib import Path
import re
import tempfile

EXECUTION_SHA='45acb972f44b2a3009dca012836db6f2bde0a95d1de538d085fa27f882c6a3b9'
PREPARED_SHA='cb363beafeac51329aab8f04843999021c17cf05dd22a1d1f3ee505ceb70a103'
CORE={'activity_checker_status':'string','full_name':'string','glitch_rate':'double','relative_toggle_rate':'double','static_probability':'float','toggle_rate':'double','x_probability':'float'}
OPTIONAL=['actual_fall_transition_max','actual_fall_transition_min','actual_rise_transition_max','actual_rise_transition_min','actual_transition_max','actual_transition_min','pin_capacitance_max','pin_capacitance_min','fanout_load','total_capacitance_max','total_capacitance_min','wire_capacitance_max','wire_capacitance_min']
SELECTED=list(CORE)+OPTIONAL
ROW=re.compile(rb'(?m)^[ \t]+(string|float|double|boolean|integer)[ \t]+('+b'|'.join(x.encode()for x in SELECTED)+rb')\b[ \t]*([^\r\n]*)\r?$')
DIAGNOSTIC=re.compile(rb'(?m)^(?:(?:Information|Warning|Error|Fatal):[^\r\n]*|[ \t]*Running (?:switching activity propagation|averaged power analysis|power calculation)[^\r\n]*)(?:\r?\n|$)')
MARKER=b'XU_SRAM_PIN name='


def need(ok,message):
    if not ok: raise ValueError(message)


def dump(path,value):
    Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def sha(data): return hashlib.sha256(data).hexdigest()


def identity(path):
    path=Path(path); h=hashlib.sha256();n=0
    with path.open('rb')as src:
        for block in iter(lambda:src.read(1024*1024),b''):h.update(block);n+=len(block)
    return dict(path=str(path.resolve()),bytes=n,sha256=h.hexdigest())


def numeric(raw):
    try:
        value=Decimal(raw)
        return value if value.is_finite() else None
    except (InvalidOperation,ValueError): return None


def native_class(name,attribute):
    if attribute is None:return 'ABSENT_FROM_ORIGINAL_REPORT'
    value=numeric(attribute['value'])
    if attribute['type']=='string':return 'NATIVE_STRING_NOT_ANNOTATION_SOURCE'
    if value is None:return 'NONFINITE_OR_NOT_NUMERIC_NATIVE_TEXT'
    if name in ['static_probability','x_probability']:
        if not Decimal(0)<=value<=Decimal(1):return 'OUTSIDE_PROBABILITY_RANGE_NATIVE_SENTINEL'
        return 'NATIVE_ZERO' if value==0 else ('NATIVE_ONE' if value==1 else 'NATIVE_INTERIOR_PROBABILITY')
    if name in ['toggle_rate','relative_toggle_rate','glitch_rate']:
        if value<0:return 'NEGATIVE_NATIVE_SENTINEL_NOT_MEASURED_RATE'
        return 'NATIVE_ZERO' if value==0 else 'NATIVE_POSITIVE'
    return 'NATIVE_FINITE_VALUE_UNIT_NOT_INFERRED'


def parse_block(raw,start):
    lines=raw.splitlines(keepends=True)
    need(lines and lines[0].startswith(MARKER),'block lacks native SRAM pin marker')
    pin=lines[0][len(MARKER):].strip().decode('utf-8')
    need(pin and b'\n'+MARKER not in raw,'nested or empty pin marker')
    need(re.search(rb'(?m)^Design\s*:\s*xu_soc_ppa_top\s*$',raw) is not None,'native attribute report SoC scope differs')
    attributes={}
    for match in ROW.finditer(raw):
        typ,key,value=[x.decode('utf-8')for x in match.groups()]
        need(key not in attributes,'duplicate selected native attribute '+key)
        end=match.end()
        # Long native names may have their scalar value on the following line.
        if not value.strip():
            newline=raw.find(b'\n',end)
            next_start=newline+1 if newline>=0 else len(raw)
            next_end=raw.find(b'\n',next_start)
            if next_end<0:next_end=len(raw)
            continuation=raw[next_start:next_end]
            need(continuation[:1] in [b' ',b'\t'] and continuation.strip() and
                 re.match(rb'^[ \t]+(?:string|float|double|boolean|integer)[ \t]',continuation) is None,'missing wrapped native attribute value '+key)
            value=continuation.strip().decode('utf-8');end=next_end
        raw_line_start=raw.rfind(b'\n',0,match.start())+1
        raw_line_end=raw.find(b'\n',end)
        if raw_line_end<0:raw_line_end=len(raw)
        else:raw_line_end+=1
        attributes[key]=dict(type=typ,value=value.strip(),raw_text=raw[raw_line_start:raw_line_end].decode('utf-8'),report_byte_start=start+raw_line_start,report_byte_end=start+raw_line_end)
    need(set(CORE).issubset(attributes),'required native attributes missing: '+','.join(sorted(set(CORE)-set(attributes))))
    need(all(attributes[k]['type']==typ for k,typ in CORE.items()),'native core attribute types differ')
    need(attributes['full_name']['value']==pin,'native full_name differs from marker')
    for name in ['toggle_rate','relative_toggle_rate','glitch_rate','static_probability','x_probability']:
        need(attributes[name]['value'],'empty native activity value')
    diagnostics=[dict(report_byte_start=start+m.start(),report_byte_end=start+m.end(),raw_text=m.group(0).decode('utf-8'))for m in DIAGNOSTIC.finditer(raw)]
    return dict(pin=pin,report_byte_start=start,report_byte_end=start+len(raw),block_bytes=len(raw),block_sha256=sha(raw),attributes=attributes,
                classes={name:native_class(name,attributes.get(name))for name in SELECTED},native_diagnostics=diagnostics,
                annotation_source='NOT_PRESENT_IN_SAVED_ATTRIBUTE_REPORT; activity_checker_status is not file/default/propagated source')


def signature(row):return {name:(r['type'],r['value'])for name,r in row['attributes'].items()}


def block_reader(source,whole):
    position=0;start=None;buffer=bytearray()
    for line in source:
        whole.update(line)
        if line.startswith(MARKER):
            if start is not None:yield bytes(buffer),start
            else:need(not buffer,'unexpected data before first native pin marker')
            start=position;buffer=bytearray(line)
        else:buffer.extend(line)
        need(len(buffer)<2*1024*1024,'native pin block exceeds guarded 2MiB; original source retained')
        position+=len(line)
    need(start is not None,'empty/no-marker native report')
    yield bytes(buffer),start


def stream_report(path,receipt,measured,destination,phase,previous=None,expected_count=22512):
    path=Path(path);stat_before=path.stat();h=hashlib.sha256();seen=set();current={};counts=Counter();diagnostic_count=Counter();changes=Counter();n=0
    need(stat_before.st_size==receipt['bytes'],'native report size differs before streaming')
    with path.open('rb')as source,lzma.open(str(destination),'wt',encoding='utf-8',preset=3)as output:
        for raw,start in block_reader(source,h):
            row=parse_block(raw,start);pin=row['pin'];need(pin in measured and pin not in seen,'unlisted/duplicate native pin block: '+pin);seen.add(pin);n+=1
            row['phase']=phase;row['phase_semantics']='before/after EXPLICIT update_power; report_attribute getters may lazily propagate/compute power'
            stats=measured[pin];row['mapped_saif_measured_input']={k:stats[k]for k in ['T0','T1','TX','TC','IG']};row['pin_role']='SRAM_OUTPUT_Q'if pin.rsplit('/',1)[-1].startswith('Q[')else'SRAM_INPUT'
            for name,category in row['classes'].items():counts[name+':'+category]+=1
            counts['pin_role:'+row['pin_role']]+=1
            if stats['TX']:counts['measured_input_TX_positive']+=1
            if stats['TX']==6604373333334:counts['measured_input_TX_whole_window']+=1
            for diagnostic in row['native_diagnostics']:
                label=diagnostic['raw_text'].strip();diagnostic_count[label]+=1
                if 'switching activity propagation'in label or 'averaged power analysis'in label or 'power calculation'in label:counts['lazy_activity_or_power_engine_diagnostic']+=1
            sig=signature(row);current[pin]=sig
            if previous is not None:
                need(pin in previous,'before/after native pin bijection differs')
                delta={}
                for name in SELECTED:
                    a=previous[pin].get(name);b=sig.get(name)
                    if a==b:changes[name+':RAW_UNCHANGED']+=1
                    else:
                        changes[name+':RAW_CHANGED']+=1
                        av=numeric(a[1])if a else None;bv=numeric(b[1])if b else None
                        equal=av is not None and bv is not None and av==bv
                        if equal:changes[name+':NUMERIC_EQUAL_TEXT_CHANGED']+=1
                        delta[name]=dict(before_native_type_value=a,after_native_type_value=b,decimal_equal_when_finite=equal)
                row['comparison_to_before_explicit_update']=delta
            output.write(json.dumps(row,sort_keys=True,separators=(',',':'))+'\n')
            if n%4096==0:print('XU_PT_PIN_STREAM phase=%s pins=%d bytes=%d'%(phase,n,start+len(raw)),flush=True)
    stat_after=path.stat();need((stat_before.st_size,stat_before.st_mtime_ns,stat_before.st_ino)==(stat_after.st_size,stat_after.st_mtime_ns,stat_after.st_ino),'original report changed during full stream')
    need(n==expected_count and seen==set(measured),'native report pin count or exact inventory differs')
    need(h.hexdigest()==receipt['sha256'],'whole original native report SHA differs after full stream')
    if previous is not None:need(set(previous)==set(current),'before/after exact native pin set differs')
    summary=dict(status='FULL_ORIGINAL_NATIVE_REPORT_STREAM_REHASHED',source_recorded_receipt=receipt,
        source_actual=dict(path=str(path.resolve()),bytes=stat_after.st_size,sha256=h.hexdigest()),source_stat_before_after_equal=True,
        pin_blocks=n,selected_attribute_counts=dict(counts),native_diagnostics=[dict(raw_text=k,count=v)for k,v in sorted(diagnostic_count.items())],
        before_after_comparison_counts=dict(changes),before_after_comparison_scope='Exact native selected type/value at original getter evaluation times, matched by pin. Not two synchronized pre/post engine snapshots; no inference of measured Q state, activity source or absence of getter side effects.',compact_rows=identity(destination),phase=phase,
        qualification='NOT_QUALIFIED',limits='Native values at getter evaluation time, not measured original-Q state or proven annotation source; exact report text only, no invented numeric tolerance')
    return summary,current


def checked_pins(path,receipt):
    need(identity(path)['sha256']==receipt['sha256'],'measured mapped-SAIF input JSON differs');data=json.loads(Path(path).read_text());pins={r['mapped_path']:r for r in data['pins']};need(len(pins)==22512 and len(data['pins'])==22512,'measured pin bijection differs');return pins


def extract(campaign,out):
    campaign=Path(campaign).resolve();out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    state=dict(status='RUNNING',qualification='NOT_QUALIFIED',tasks=[],tool=identity(__file__),limitations=['Original attribute getters can trigger lazy switching propagation/power analysis; before means before explicit update_power only.','Compact extraction does not rerun PT or validate missing mapped SAIF body, conditional power engine semantics, unknown-Q physical state, timing or contest score.'])
    dump(out/'state.json',state)
    try:
        epath=campaign/'execution.json';ppath=campaign/'prepared.json';need(identity(epath)['sha256']==EXECUTION_SHA and identity(ppath)['sha256']==PREPARED_SHA,'exact original 12-task prepared/execution receipt differs')
        execution=json.loads(epath.read_text());prepared=json.loads(ppath.read_text());need(execution['status']=='EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and execution['requested_task_ids']==list(range(12)),'original full campaign not terminal diagnostic')
        state['execution']=identity(epath);state['prepared']=identity(ppath)
        for i in range(12):
            task=out/('task_%02d'%i);task.mkdir();base='task_%02d/'%i
            pins=checked_pins(campaign/base/'measured-sram-pins.json',execution['artifacts'][base+'measured-sram-pins.json'])
            before,before_values=stream_report(campaign/base/'sram-pins-before.rpt',execution['artifacts'][base+'sram-pins-before.rpt'],pins,task/'native-before.jsonl.xz','before')
            after,_=stream_report(campaign/base/'sram-pins-after.rpt',execution['artifacts'][base+'sram-pins-after.rpt'],pins,task/'native-after.jsonl.xz','after',previous=before_values)
            summary=dict(task_id=i,before=before,after=after,measured_input=execution['artifacts'][base+'measured-sram-pins.json'],qualification='NOT_QUALIFIED');dump(task/'summary.json',summary);state['tasks'].append(summary);dump(out/'state.json',state)
            print('XU_PT_PIN_TASK_COMPLETE task=%d native_blocks=45024 original_SHA_rehashed=2 NOT_QUALIFIED'%i,flush=True)
        need(identity(epath)['sha256']==EXECUTION_SHA and identity(ppath)['sha256']==PREPARED_SHA,'original receipts changed during extraction')
        state['status']='EXTRACTED_24_ORIGINAL_REPORTS_NOT_QUALIFIED';state['original_reports_streamed']=24;state['native_pin_blocks']=12*2*22512;state['original_bytes_streamed']=sum(t[p]['source_actual']['bytes']for t in state['tasks']for p in ['before','after'])
    except Exception as error:
        state['status']='FAIL';state['error']=str(error);dump(out/'state.json',state);raise
    dump(out/'state.json',state);print(state['status'],flush=True)


def samples(before,after,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);rows=[]
    for phase,path in [('before',Path(before)),('after',Path(after))]:
        raw=path.read_bytes();row=parse_block(raw,0);row['phase']=phase;row['sample']=identity(path);row['original_full_report_rehashed']=False;rows.append(row)
    need(rows[0]['pin']==rows[1]['pin'],'native samples concern different pins');dump(out/'sample-parsed.json',rows)
    tests=[]
    engine_words=['switching activity propagation','averaged power analysis','power calculation']
    need(all(any(word in d['raw_text']for d in rows[0]['native_diagnostics'])for word in engine_words),'actual prefixed native lazy engine diagnostics lost')
    tests.append('actual-prefixed-lazy-engine-lines-preserved')
    bare=Path(before).read_bytes().replace(b'Information: Running ',b'Running ')
    bare_diags=parse_block(bare,0)['native_diagnostics']
    need(all(any(d['raw_text'].startswith('Running ')and word in d['raw_text']for d in bare_diags)for word in engine_words),'bare Running engine diagnostic positive control lost')
    tests.append('bare-Running-lazy-engine-lines-preserved')
    def rejected(label,body):
        try:parse_block(body,0)
        except (ValueError,UnicodeError):tests.append(label)
        else:raise ValueError('negative mutation accepted: '+label)
    raw=Path(before).read_bytes();rejected('missing-native-marker',raw.replace(MARKER,b'BAD_MARKER=',1));rejected('native-full-name-object-mismatch',raw.replace(b'string    full_name ',b'string    bad_name  ',1));rejected('duplicate-native-toggle-attribute',raw+b'                                   double    toggle_rate             0\n');rejected('missing-native-x-probability',re.sub(rb'(?m)^.*float[ \t]+x_probability.*\n?',b'',raw))
    wrapped=re.sub(rb'(?m)^([ \t]+float[ \t]+static_probability)[ \t]+([^\r\n]+)',rb'\1\n                                                                     \2',raw);need(parse_block(wrapped,0)['attributes']['static_probability']['value']==rows[0]['attributes']['static_probability']['value'],'wrapped native scalar value parser differs');tests.append('wrapped-native-value-positive-control')
    # Whole-report streaming positive/negative fixture has two real-layout blocks.
    second=raw.replace(rows[0]['pin'].encode(),(rows[0]['pin']+'__probe').encode());fixture=raw+second
    with tempfile.TemporaryDirectory(prefix='xu-pin74-')as temp:
        path=Path(temp)/'source.rpt';path.write_bytes(fixture);pins={name:{'T0':1,'T1':0,'TX':0,'TC':0,'IG':0}for name in [rows[0]['pin'],rows[0]['pin']+'__probe']};receipt=identity(path)
        a,prev=stream_report(path,receipt,pins,Path(temp)/'before.xz','before',expected_count=2);b,_=stream_report(path,receipt,pins,Path(temp)/'after.xz','after',previous=prev,expected_count=2);need(a['pin_blocks']==b['pin_blocks']==2 and all(not k.endswith(':RAW_CHANGED')for k in b['before_after_comparison_counts']),'streaming comparison positive control failed');tests.append('two-native-layout-block-stream-positive-control')
        corrupt=dict(receipt,sha256='0'*64)
        try:stream_report(path,corrupt,pins,Path(temp)/'corrupt.xz','before',expected_count=2)
        except ValueError:tests.append('whole-source-SHA-corruption-rejected')
        else:raise ValueError('corrupt whole source identity accepted')
    dump(out/'sample-review.json',dict(status='SAMPLE_LAYOUT_TESTED_NOT_FULL_REPORT_REPLAY',sample_identity=[identity(before),identity(after)],selected_core_native_values=[{k:v['value']for k,v in r['attributes'].items()if k in CORE}for r in rows],before_sample_lazy_engine_diagnostics=rows[0]['native_diagnostics'],tests=tests,qualification='NOT_QUALIFIED'))
    print('SAMPLE_LAYOUT_TESTED_NOT_FULL_REPORT_REPLAY',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode');s=sub.add_parser('sample');s.add_argument('--before',required=True,type=Path);s.add_argument('--after',required=True,type=Path);s.add_argument('--out',required=True,type=Path);e=sub.add_parser('extract');e.add_argument('--campaign',required=True,type=Path);e.add_argument('--out',required=True,type=Path);a=p.parse_args();need(a.mode in ['sample','extract'],'choose sample or extract');samples(a.before,a.after,a.out)if a.mode=='sample'else extract(a.campaign,a.out)
if __name__=='__main__':main()
