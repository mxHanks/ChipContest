#!/usr/bin/env python3
"""Sequential SRAM candidate matrix; independent baseline and Golden are preserved."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import uuid
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import run_linear as L
import sram_evidence as E
import run_sram_engine as ENGINE
import run_sram_soc as SOC
import run_sram_icb as ICB
C=L.COMMON


def verify_child_result(command,run_root=ROOT/'artifacts/runs',expected=None):
    error=E.completion_error(command,[])
    if error:raise ValueError('child native evidence rejected: '+error)
    entries=[]
    for line in Path(command['log']['path']).read_text().splitlines():
        try:item=json.loads(line)
        except ValueError:continue
        if isinstance(item,dict) and item.get('status')=='PASS':entries.append(item)
    if len(entries)!=1:raise ValueError('child lacks exactly one completion summary')
    entry=entries[0]
    path=Path(entry.get('report') or entry.get('output') or '').resolve()
    if path.is_dir():path=path/'result.json'
    if not path.is_relative_to(Path(run_root).resolve()) or not path.is_file():
        raise ValueError('child report is missing or outside the run root')
    report=json.loads(path.read_text())
    if report.get('status')!='PASS':raise ValueError('child report did not pass')
    schema=report.get('schema')
    if expected:
        if schema!=expected['schema']:raise ValueError('child schema differs from requested stage')
        for key,value in expected.get('configuration',{}).items():
            if report.get('configuration',{}).get(key)!=value:
                raise ValueError('child configuration differs from request: '+key)
    def check_commands(commands):
        for native in commands:
            if 'native_state' in native:error=E.completion_error(native,[])
            else:error=C.completion_error(native,C.log_text(native),[])
            if error:raise ValueError('child internal command rejected: '+error)
    check_commands(report.get('commands',[]))
    if schema in (ENGINE.SCHEMA,'kwt-rowpair-benchmark-v1'):
        # Reuses the independent full-shape/cycle/marker verifier, including
        # all commands, vector identities and source bindings.
        ENGINE.comparison_report([path])
    elif schema=='kwt-engine-comparison-v1':
        entries=report.get('runs',[])
        if len(entries)<2:raise ValueError('comparison lacks independent runs')
        for entry in entries:
            check_commands(json.loads(Path(entry['result']['path']).read_text()).get('commands',[]))
        recomputed=ENGINE.comparison_report([x['result']['path'] for x in entries])
        if recomputed['runs']!=entries:raise ValueError('comparison metrics differ from native evidence')
    elif schema in ('kwt-sram-soc-v2','kwt-sram-icb-v1'):
        commands=report.get('commands',[])
        if not commands:raise ValueError('child lacks native commands')
        for native in commands:
            error=E.completion_error(native,[])
            if error:raise ValueError('child internal command rejected: '+error)
        if schema=='kwt-sram-soc-v2':
            SOC.accept_soc_command(commands[-1],report['configuration']['tasks'],report.get('inputs',[]))
        else:
            cases=report.get('cases',[])
            if len(cases)!=2 or {x.get('backend') for x in cases}!={'behavioral','ff'}:
                raise ValueError('ICB regression requires both backends')
            runs=[c for c in commands if Path(c['log']['path']).name=='run.log']
            if len(runs)!=2:raise ValueError('ICB native run count mismatch')
            for case,native in zip(cases,runs):
                if case.get('status')!='PASS' or case.get('actual_core_outputs')!=25348 or case.get('complete_tasks')!=1 or case.get('aborted_tasks')!=1:
                    raise ValueError('ICB protocol counts incomplete')
                error=E.completion_error(native,[ICB.MARKER])
                if error:raise ValueError('ICB protocol completion rejected: '+error)
    else:raise ValueError('unsupported or missing child schema')
    records=[]
    def visit(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):records.append(value)
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(report)
    records.append(E.record(path))
    E.verify_records(records)
    return {'result':E.record(path),'records':records}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vectors-dir',type=Path,default=ROOT/'sim/vectors/kwt-silence-v1')
    p.add_argument('--include-soc',action='store_true',help='also run all 12 CPU-driven tasks (can take minutes)')
    a=p.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-sram-regression-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    r={'schema':'kwt-sram-regression-v2','status':'RUNNING','commands':[],'runs':[],
       'scope':'functional/cycle regression, not official physical acceptance','official_ppa':'BLOCKED'}
    identity=E.source_identity([Path(__file__),Path(E.__file__),Path(L.__file__),Path(C.__file__)],
        {'vectors_dir':str(a.vectors_dir.resolve()),'include_soc':a.include_soc},out/'source_identity.json')
    r['identity']=identity
    verified=[]
    E.write_json(out/'result.json',r)
    try:
        def run(script,args,name,timeout=600):
            cmd=E.run_command([sys.executable,str(ROOT/'scripts/verify'/script),*args],ROOT,out/(name+'.log'),timeout,2)
            r['commands'].append(cmd)
            schema={'run_rowpair_benchmark.py':'kwt-rowpair-benchmark-v1','run_sram_soc.py':'kwt-sram-soc-v2',
                    'run_sram_icb.py':'kwt-sram-icb-v1','run_sram_engine.py':ENGINE.SCHEMA}[script]
            configuration={}
            if '--compare' in args:schema='kwt-engine-comparison-v1'
            else:
                for option,key in (('--tasks','tasks'),('--pipe-mul','pipe_mul'),('--result-buffers','result_buffers')):
                    if option in args:configuration[key]=int(args[args.index(option)+1])
                if script=='run_sram_engine.py':
                    configuration.update(memory_backend=args[args.index('--backend')+1] if '--backend' in args else 'behavioral',
                        pipe_mul=configuration.get('pipe_mul',1),result_buffers=configuration.get('result_buffers',2))
                if script=='run_sram_soc.py':configuration['backend']=args[args.index('--backend')+1] if '--backend' in args else 'behavioral'
            child=verify_child_result(cmd,expected={'schema':schema,'configuration':configuration})
            verified.extend(child['records'])
            path=Path(child['result']['path'])
            r['runs'].append({'name':name,'result':child['result'],'verified_records':len(child['records'])})
            r['last_completed_stage']=name
            E.write_json(out/'result.json',r)
            print(name+': PASS',flush=True)
            return path
        # All four pipeline/buffer configurations on six arithmetic categories,
        # both implementations, backpressure, resets and consecutive tasks.
        for pipe in (0,1):
            for buffers in (1,2):
                runs=[]
                for backend in ('behavioral','ff'):
                    runs.append(run('run_sram_engine.py',['--backend',backend,'--pipe-mul',str(pipe),'--result-buffers',str(buffers),
                        '--tasks','6','--stalls','random'],f'synthetic-p{pipe}-b{buffers}-{backend}'))
                run('run_sram_engine.py',['--compare',*map(str,runs)],f'equivalence-p{pipe}-b{buffers}')
        real=[]
        for script,backend in [('run_rowpair_benchmark.py',None),('run_sram_engine.py','behavioral'),('run_sram_engine.py','ff')]:
            args=['--tasks','12','--vectors-dir',str(a.vectors_dir.resolve()),'--stalls','random']
            if backend: args+=['--backend',backend]
            real.append(run(script,args,'real12-'+(backend or 'original')))
        run('run_sram_engine.py',['--compare',*map(str,real)],'original-behavioral-ff-equivalence')
        for backend in ('behavioral','ff'):
            run('run_sram_engine.py',['--backend',backend,'--vectors','range','--tasks','2','--simulator','iverilog'],f'range-four-state-{backend}')
        run('run_sram_icb.py',[],'icb-protocol')
        if a.include_soc:
            run('run_sram_soc.py',['--tasks','12','--vectors-dir',str(a.vectors_dir.resolve())],'soc12',2100)
        r['status']='PASS'
    except Exception as exc:r.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(identity['inputs']+verified)
        except (ValueError,OSError) as exc:r.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',r)
    print(json.dumps({'status':r['status'],'report':str(out/'result.json'),'error':r.get('error')}))
    return 0 if r['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
