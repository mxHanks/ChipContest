#!/usr/bin/env python3
"""Re-run development acceptance on a new Linux server; standard library only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import e203_soc as soc


def execute_steps(steps, out):
    if not steps: raise ValueError('acceptance must contain at least one step')
    result={'status':'RUNNING','started_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'development acceptance; official SRAM/PPA/600-sample accuracy still required',
            'steps':[]}
    try:
        for name, command, timeout in steps:
            step={'name':name,'command':[str(c) for c in command],'status':'RUNNING'}
            result['steps'].append(step)
            print('Starting '+name,flush=True)
            soc.run(command,soc.ROOT,out/(name+'.log'),timeout)
            step['status']='PASS'
        result['status']='PASS'
    except Exception as exc:
        step['status']='FAIL'
        result.update(status='FAIL',failed_step=name,error=str(exc))
    result['finished_utc']=datetime.now(timezone.utc).isoformat()
    (out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    parser.add_argument('--full',action='store_true',help='also run Icarus real1 and all Chisel tests')
    parser.add_argument('--offline',action='store_true',help='use pre-populated Scala dependency cache with --full')
    args=parser.parse_args()
    out=(args.out or soc.ROOT/'build/acceptance'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    out.mkdir(parents=True,exist_ok=False)
    steps=[('host',[sys.executable,'-m','unittest','discover','-s','tests/e203','-p','test_*.py'],180)]
    for name,mode,tasks,sim in [('vectors','check-vectors',12,'verilator'),
            ('doctor','doctor',1,'verilator'),('baseline','baseline',1,'iverilog'),
            ('synthetic1','synthetic',1,'verilator'),('real12','real',12,'verilator')]:
        steps.append((name,[sys.executable,str(soc.ROOT/'tools/scripts/e203_soc.py'),
            '--mode',mode,'--tasks',str(tasks),'--sim',sim,'--cross-prefix',args.cross_prefix,
            '--out',str(out/name)],10800))
    if args.full:
        steps.append(('icarus1',[sys.executable,str(soc.ROOT/'tools/scripts/e203_soc.py'),
            '--mode','real','--sim','iverilog','--tasks','1','--cross-prefix',args.cross_prefix,
            '--out',str(out/'icarus1')],10800))
        steps.append(('chisel',['scala-cli',*(['--power'] if args.offline else []),
            'test','.',*(['--offline'] if args.offline else []),'--server=false','--jvm','system'],7200))
    result=execute_steps(steps,out)
    print(f'{result["status"]}: {out / "acceptance.json"}',flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
