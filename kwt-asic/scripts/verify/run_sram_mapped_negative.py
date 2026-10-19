#!/usr/bin/env python3
"""Deliberately wrong private Golden must be rejected by an accepted binary.

This qualifies checker sensitivity. EXPECTED_REJECTION is never a completed
accelerator task, a netlist PASS, or a change to the canonical Golden model.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
import sram_evidence as E
ROOT=Path(__file__).resolve().parents[2]


def flip_first_golden_bit(payload):
    lines=payload.splitlines(keepends=True)
    if len(lines)!=25344 or any(not re.fullmatch(rb'[0-9a-fA-F]{12}',line.rstrip(b'\r\n')) for line in lines):
        raise ValueError('negative control requires a complete known signed48 image')
    suffix=lines[0][12:]
    lines[0]=f'{int(lines[0][:12],16)^1:012x}'.encode()+suffix
    return b''.join(lines)


def accept_expected_rejection(command):
    if (command.get('status')!='EXITED' or command.get('exit_code') not in (1,-6)
        or command.get('timed_out') or command.get('interrupted')):
        raise ValueError('negative control did not terminate with the expected simulation failure')
    E.verify_records([command['log'],command['native_state']])
    native=json.loads(Path(command['native_state']['path']).read_text())
    if any(native.get(k)!=command.get(k) for k in ('status','exit_code','timed_out','interrupted','argv','log')):
        raise ValueError('negative native record changed')
    text=Path(command['log']['path']).read_text()
    if (len(re.findall(r'^MAPPED_RECOVERY_PASS soft_aborts=1 pending_resets=1$',text,re.M))!=1 or
        len(re.findall(r'Assertion failed[^\n]*: mapped Golden mismatch task=0 index=0$',text,re.M))!=1 or
        re.search(r'^MAPPED_(?:TASK|PAIR)_PASS',text,re.M)):
        raise ValueError('negative control failed for a different reason or accepted the wrong result')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--positive-report',type=Path,required=True)
    parser.add_argument('--timeout',type=int,default=120)
    args=parser.parse_args()
    if args.timeout<=0:parser.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-mapped-negative-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True)
    report={'schema':'kwt-mapped-negative-control-v1','status':'RUNNING',
        'scope':'checker sensitivity only; deliberately wrong private Golden',
        'accelerator_function':'NOT_ACCEPTED_BY_THIS_TEST','completed_tasks':0,'commands':[],'inputs':[]}
    E.write_json(out/'result.json',report)
    try:
        p=args.positive_report.resolve();positive=json.loads(p.read_text())
        if positive.get('schema')!='kwt-sram-mapped-functional-v1' or positive.get('status')!='PASS':
            raise ValueError('require a completed accepted positive replay')
        E.verify_records(positive['inputs']+[positive['binary']])
        report['inputs']=[E.record(Path(__file__)),E.record(Path(E.__file__)),E.record(p),*positive['inputs']]
        source_records={item['path']:item for item in positive['inputs']}
        vectors=out/'vectors/layer_00';vectors.mkdir(parents=True)
        for name in ('x','w','bias','y'):
            source=p.parent/'vectors/layer_00'/(name+'.mem')
            record=source_records[str(source)];E.verify_records([record])
            data=source.read_bytes()
            if name=='y':data=flip_first_golden_bit(data)
            target=vectors/(name+'.mem');target.write_bytes(data)
            report['inputs'].append(E.record(target))
        report['mutation']={'source':'private y.mem copy','task':0,'index':0,'bit':0,
                            'canonical_golden_modified':False,'dut_inputs_modified':False}
        E.write_json(out/'result.json',report)  # freeze inputs before consumption
        command=E.run_command([positive['binary']['path'],'+TASKS=1','+VECTORS='+str(vectors.parent)],ROOT,out/'run.log',args.timeout,1)
        report['commands'].append(command)
        accept_expected_rejection(command)
        report['status']='EXPECTED_REJECTION'
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(report['inputs'])
        except (OSError,ValueError) as exc:report.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return 0 if report['status']=='EXPECTED_REJECTION' else 1


if __name__=='__main__':raise SystemExit(main())
