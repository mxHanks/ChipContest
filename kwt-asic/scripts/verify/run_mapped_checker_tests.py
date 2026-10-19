#!/usr/bin/env python3
"""Four-state unit tests of the mapped ICB observer, never accelerator acceptance."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import sram_evidence as E

POSITIVES={0:('normal-handshakes',7,2,2),1:('invalid-response-x',3,0,0),
           2:('invalid-response-z',3,0,0)}
NEGATIVES={
    10:('cmd-valid-x','UNKNOWN_CONTROL'),11:('cmd-valid-z','UNKNOWN_CONTROL'),
    12:('rsp-ready-x','UNKNOWN_CONTROL'),13:('rsp-ready-z','UNKNOWN_CONTROL'),
    14:('common-ready-x','UNKNOWN_CONTROL'),15:('common-ready-z','UNKNOWN_CONTROL'),
    16:('common-rsp-valid-x','UNKNOWN_CONTROL'),17:('common-rsp-valid-z','UNKNOWN_CONTROL'),
    20:('common-data-x','UNKNOWN_RESPONSE'),21:('common-data-z','UNKNOWN_RESPONSE'),
    22:('common-error-x','UNKNOWN_RESPONSE'),23:('common-error-z','UNKNOWN_RESPONSE'),
    30:('ready-mismatch','PROTOCOL_MISMATCH'),31:('rsp-valid-mismatch','PROTOCOL_MISMATCH'),
    32:('data-mismatch','RESPONSE_MISMATCH'),33:('error-mismatch','RESPONSE_MISMATCH'),
    40:('reset-x','UNKNOWN_RESET'),41:('reset-z','UNKNOWN_RESET'),
}


def accept_rejection(command,diagnostic):
    """Expected nonzero is accepted only with exactly the intended checker fatal."""
    if (command.get('status')!='EXITED' or command.get('exit_code') in (None,0)
            or command.get('timed_out') or command.get('interrupted')):
        raise ValueError('negative fixture did not exit with an ordinary nonzero status')
    E.verify_records([command['log'],command['native_state']])
    saved=json.loads(Path(command['native_state']['path']).read_text())
    if any(saved.get(k)!=command.get(k) for k in ('status','exit_code','timed_out','interrupted','argv','log')):
        raise ValueError('negative command differs from durable native evidence')
    text=Path(command['log']['path']).read_text()
    fatals=re.findall(r'^FATAL: [^\n]*: ([^\n]+)$',text,re.M)
    if fatals!=[diagnostic] or 'CHECKER_FIXTURE_PASS' in text:
        raise ValueError('negative fixture fatal differs from expected reason: '+diagnostic)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout',type=int,default=30)
    args=parser.parse_args()
    if args.timeout<=0:parser.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-mapped-checker-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'kwt-mapped-checker-tests-v1','status':'RUNNING',
        'scope':'four-state checker unit fixture only; expected rejection is not a completed design task',
        'accelerator_function':'NOT_RUN','full_netlist_compilation':'NOT_RUN',
        'configuration':{'simulator':'Icarus four-state','jobs':1},'commands':[],
        'inputs':[],'cases':[]}
    E.write_json(out/'result.json',report)
    try:
        tools={name:shutil.which(name) for name in ('iverilog','vvp')}
        if not all(tools.values()):raise FileNotFoundError('source env/activate.sh; Icarus/vvp required')
        sources=[ROOT/'sim/kwt_icb_pair_checker.sv',ROOT/'sim/fixtures/tb_kwt_icb_pair_checker.sv']
        dependencies=[Path(__file__),Path(E.__file__),*sources,*map(Path,tools.values()),
            ROOT/'.tools/eda/usr/bin/iverilog',ROOT/'.tools/eda/usr/bin/vvp']
        identity=E.source_identity(dependencies,report['configuration'],out/'source_identity.json')
        report['identity']=identity;report['inputs']=identity['inputs']
        def execute(argv,name):
            command=E.run_command(argv,ROOT,out/(name+'.log'),args.timeout,1)
            report['commands'].append(command);E.write_json(out/'result.json',report)
            return command
        version=execute([tools['iverilog'],'-V'],'version')
        error=E.completion_error(version,[])
        if error:raise ValueError('Icarus version command rejected: '+error)
        version_text=Path(version['log']['path']).read_text()
        if not re.search(r'^Icarus Verilog version 12\.0\b',version_text,re.M):
            raise ValueError('requires project Icarus 12.0')
        report['tool_version']=version_text.splitlines()[0]
        binary=out/'checker.vvp'
        compiled=execute([tools['iverilog'],'-g2012','-s','tb_kwt_icb_pair_checker',
                          '-o',str(binary),*map(str,sources)],'compile')
        error=E.completion_error(compiled,[])
        if error:raise ValueError('checker compile rejected: '+error)
        report['inputs'].append(E.record(binary))
        for case_id,(name,traces,commands,responses) in POSITIVES.items():
            command=execute([tools['vvp'],str(binary),f'+CASE={case_id}'],name)
            marker=f'^CHECKER_FIXTURE_PASS case={case_id} traces={traces} commands={commands} responses={responses}$'
            error=E.completion_error(command,[marker])
            if error:raise ValueError(name+' rejected: '+error)
            report['cases'].append({'case':case_id,'name':name,'status':'PASS',
                'expectation':'known legal observer input','traces':traces,
                'accepted_commands':commands,'accepted_responses':responses})
        for case_id,(name,reason) in NEGATIVES.items():
            diagnostic='MAPPED_CHECKER_'+reason
            command=execute([tools['vvp'],str(binary),f'+CASE={case_id}'],name)
            accept_rejection(command,diagnostic)
            report['cases'].append({'case':case_id,'name':name,'status':'EXPECTED_REJECTION',
                'expected_diagnostic':diagnostic,'native_exit_code':command['exit_code']})
        report['coverage']={'legal_cases':len(POSITIVES),'expected_rejections':len(NEGATIVES),
                            'completed_accelerator_tasks':0}
        report['status']='PASS'
    except FileNotFoundError as exc:report.update(status='BLOCKED',error=str(exc))
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(report['inputs'])
        except (OSError,ValueError) as exc:report.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),
                      'error':report.get('error')}))
    return {'PASS':0,'FAIL':1,'BLOCKED':2}[report['status']]


if __name__=='__main__':raise SystemExit(main())
