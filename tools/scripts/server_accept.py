#!/usr/bin/env python3
"""Re-run development acceptance on a new Linux server; standard library only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import e203_soc as soc


DEFAULT_SCOPE='development acceptance; official SRAM/PPA/600-sample accuracy still required'
VCS_SCOPE=('VCS four-state development platform acceptance; Icarus and Chisel not run; '
           'official platform/SRAM/PPA/600-sample accuracy still required')


def execute_steps(steps, out, scope=DEFAULT_SCOPE, profile='development-standard', not_run=None,
                  firmware_config=None, accel_variant='pe8'):
    if not steps: raise ValueError('acceptance must contain at least one step')
    result={'status':'RUNNING','started_utc':datetime.now(timezone.utc).isoformat(),
            'scope':scope,'profile':profile,'not_run':not_run or [],
            'steps':[],'accel_variant':accel_variant}
    if firmware_config is not None:
        result['firmware_configuration']=firmware_config
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


def acceptance_steps(out, cross_prefix, sim='verilator', full=False, offline=False,
                     firmware_schedule='baseline', firmware_opt='-Os', firmware_experiment='none', accel_variant='pe8'):
    config=soc.contract.configuration(firmware_schedule,firmware_opt,firmware_experiment)
    firmware_args=['--firmware-schedule',config['schedule'],
                   '--firmware-opt='+config['optimization'],
                   '--firmware-experiment',config['experiment']]
    soc.contract.physical_pes(accel_variant, firmware_schedule)
    if accel_variant != 'pe8': firmware_args += ['--accel-variant', accel_variant]
    if sim=='vcs' and full:
        raise ValueError('VCS platform acceptance is separate from --full Icarus/Chisel acceptance')
    host_command=[sys.executable,'-m','unittest','discover','-s','tests/e203','-p','test_*.py']
    if sim=='vcs':
        # The additive cache/window interface test also uses the chosen backend.
        host_command=['env','XU_WRAPPER_SIM=vcs',
                      'XU_WRAPPER_LOG_DIR='+str(out/'host-wrapper-vcs'),*host_command]
    if sim=='vcs' and accel_variant=='pe32':
        host_command=['env','XU_PE32_WRAPPER_SIM=vcs',
                      'XU_PE32_WRAPPER_LOG_DIR='+str(out/'host-pe32-wrapper-vcs'),*host_command]
    if sim=='vcs' and accel_variant=='pe64':
        host_command=['env','XU_PE64_WRAPPER_SIM=vcs',
                      'XU_PE64_WRAPPER_LOG_DIR='+str(out/'host-pe64-wrapper-vcs'),*host_command]
    steps=[('host',host_command,1200 if accel_variant=='pe64' else (900 if accel_variant=='pe32' else 300)),
           ('numeric',[sys.executable,'-m','unittest','discover','-s','tests/numeric','-v'],240)]
    for name,mode,tasks,backend in [('vectors','check-vectors',12,sim),
            ('doctor','doctor',1,sim),('baseline','baseline',1,'vcs' if sim=='vcs' else 'iverilog'),
            ('synthetic1','synthetic',1,sim),('synthetic2','synthetic',2,sim),('real12','real',12,sim)]:
        steps.append((name,[sys.executable,str(soc.ROOT/'tools/scripts/e203_soc.py'),
            '--mode',mode,'--tasks',str(tasks),'--sim',backend,'--cross-prefix',cross_prefix,
            '--out',str(out/name),*firmware_args],10800))
    if full:
        steps.append(('icarus1',[sys.executable,str(soc.ROOT/'tools/scripts/e203_soc.py'),
            '--mode','real','--sim','iverilog','--tasks','1','--cross-prefix',cross_prefix,
            '--out',str(out/'icarus1'),*firmware_args],10800))
        steps.append(('chisel',['scala-cli',*(['--power'] if offline else []),
            'test','.',*(['--offline'] if offline else []),'--server=false','--jvm','system'],7200))
    return steps


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    parser.add_argument('--sim',choices=['verilator','vcs'],default='verilator',
                        help='vcs selects a separate platform flow without Icarus or Chisel')
    parser.add_argument('--full',action='store_true',help='also run Icarus real1 and all Chisel tests')
    parser.add_argument('--offline',action='store_true',help='use pre-populated Scala dependency cache with --full')
    parser.add_argument('--accel-variant', choices=['pe8', 'pe32', 'pe64'], default='pe8')
    soc.contract.add_arguments(parser)
    args=parser.parse_args()
    if args.sim=='vcs' and args.full:
        parser.error('--sim vcs cannot be combined with --full; Icarus/Chisel remain a separate acceptance')
    if args.sim=='vcs' and args.offline:
        parser.error('--offline controls Scala dependencies and does not apply to --sim vcs')
    out=(args.out or soc.ROOT/'build/acceptance'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    out.mkdir(parents=True,exist_ok=False)
    steps=acceptance_steps(out,args.cross_prefix,args.sim,args.full,args.offline,
                           args.firmware_schedule,args.firmware_opt,args.firmware_experiment,args.accel_variant)
    result=execute_steps(steps,out,VCS_SCOPE if args.sim=='vcs' else DEFAULT_SCOPE,
                         'vcs-platform' if args.sim=='vcs' else 'development-full' if args.full else 'development-standard',
                         ['icarus1','chisel'] if args.sim=='vcs' else [],
                         soc.contract.configuration(args.firmware_schedule,args.firmware_opt,args.firmware_experiment),args.accel_variant)
    print(f'{result["status"]}: {out / "acceptance.json"}',flush=True)
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
