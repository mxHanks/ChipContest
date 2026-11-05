#!/usr/bin/env python3
"""S2e104 task00 then full12 formal RTL activity, bound to actual S2e89 mapped context.

No remote access or credentials. Collection is not an energy/timing qualification.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import xu_s2e_activity_context as context

BASE=Path.home()/'Desktop/xu-score-optimization-20261102'
VCS='/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs'
VENDOR='/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v'
CROSS=str(Path.home()/'Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-')


def checked_task00(path,ctx,mapped):
    path=Path(path)
    result=json.loads((path/'result.json').read_text())
    context.require(result.get('status')=='PARTIAL_COLLECTED_REVIEW_PENDING' and
                    result.get('requested_task_ids')==[0] and len(result.get('tasks',[]))==1,
                    'actual completed isolated S2e task00 required before12')
    config=result['configuration']
    context.require(config.get('source_context')==ctx.source and config.get('tool_context')==ctx.tool and
                    config.get('mapped_context')==mapped,'task00 source/tool/own-mapped context differs')
    task=result['tasks'][0]
    context.require(task.get('task_id')==0 and task.get('status')=='COLLECTED_REVIEW_PENDING',
                    'task00 actual activity result incomplete')
    for item in [task['boundary_log'],task['raw_saif'],task['saif'],task['input_manifest']]:
        context.require(context.identity(item['path'])=={k:item[k] for k in ('path','sha256')},'task00 raw activity identity changed')
    return context.identity(path/'result.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['task00','tasks12'])
    parser.add_argument('--source-root',type=Path,default=BASE/'ChipContest-s2e-74')
    parser.add_argument('--ppa-root',type=Path,default=BASE/'s2e-ppa-campaign-20261104-89')
    parser.add_argument('--formality-root',type=Path,help='explicit completed109 own-native-FM audit, rechecked against original89')
    parser.add_argument('--task00-proof',type=Path,default=BASE/'s2e-formal-activity-task00-20261104-104')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--foreground',action='store_true')
    args=parser.parse_args()
    ctx=context.Context(args.source_root)
    mapped=context.checked_mapped_context(ctx.root,args.ppa_root,args.formality_root)
    task00=checked_task00(args.task00_proof,ctx,mapped) if args.action=='tasks12' else None
    out=(args.out or BASE/('s2e-formal-activity-task00-20261104-104' if args.action=='task00' else 's2e-formal-activity12-20261104-104')).resolve()
    context.require(not out.exists(),'fresh isolated activity output required')
    command=[sys.executable,str(HERE/'xu_s2e_task_activity.py'),'--source-root',str(ctx.root),'--tool-root',str(context.TOOL_ROOT),
             '--profile',context.PROFILE,'--ppa-root',str(args.ppa_root.resolve()),'--out',str(out),'--vendor-model',VENDOR,
             '--vcs',VCS,'--cross-prefix',CROSS,'--task-ids','0' if args.action=='task00' else ','.join(map(str,range(12)))]
    if args.prepare_only:command.append('--prepare-only')
    if args.formality_root:command+=['--formality-root',str(args.formality_root.resolve())]
    log=out.with_name(out.name+'-driver.log')
    context.require(not log.exists(),'fresh activity driver log required')
    with log.open('x') as stream:
        stream.write(json.dumps(dict(command=command,source=ctx.source,mapped=mapped,task00_prior=task00))+'\n');stream.flush()
        if args.foreground:
            actual=subprocess.run(command,cwd=str(context.TOOL_ROOT),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
            return actual.returncode
        process=subprocess.Popen(command,cwd=str(context.TOOL_ROOT),stdin=subprocess.DEVNULL,stdout=stream,
                                 stderr=subprocess.STDOUT,start_new_session=True)
    print('XU_S2E_ACTIVITY104_STARTED',args.action,process.pid,str(out),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
