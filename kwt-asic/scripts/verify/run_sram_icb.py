#!/usr/bin/env python3
"""ICB protocol regression against the real storage-isolated rowpair engine."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
import sram_evidence as E
import sram_sources as SOURCES

MARKER = (r'^ICB_ADAPTER_PASS transactions=([1-9][0-9]*) hold_checks=([1-9][0-9]*) '
          r'actual_core_outputs=25348 complete_tasks=1 aborted_tasks=1$')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=('behavioral','ff','both'), default='both')
    p.add_argument('--timeout', type=int, default=180)
    a = p.parse_args()
    if a.timeout <= 0: p.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-sram-icb-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'kwt-sram-icb-v1','status':'FAIL','scope':'ICB adapter + real core protocol; not CPU/platform/PPA',
            'commands':[],'cases':[],'official_ppa':'BLOCKED'}
    try:
        backend_config=SOURCES.select_backend('behavioral' if a.backend=='both' else a.backend,'simulation')
        sources=[*backend_config['sources'],ROOT/'soc/kwt_icb_slave_sram.sv',ROOT/'sim/tb_kwt_icb_slave_sram.sv']
        simulator=shutil.which('verilator')
        if not simulator: raise FileNotFoundError('verilator missing; source env/activate.sh')
        identity=E.source_identity([Path(__file__),Path(E.__file__),*backend_config['dependencies'],*sources],{'top':'tb_kwt_icb_slave_sram','backend':a.backend},out/'source_identity.json')
        report['identity']=identity
        report['tools']=[E.record(simulator)]
        version=E.run_command([simulator,'--version'],out,out/'version.log',15,2)
        report['commands'].append(version)
        if version['exit_code']: raise RuntimeError('simulator version probe failed')
        backends=('behavioral','ff') if a.backend=='both' else (a.backend,)
        for backend in backends:
            value=SOURCES.select_backend(backend,'simulation')['value']
            work=out/backend;work.mkdir()
            compile_argv=[simulator,'--binary','--timing','--assert','-Wno-fatal','--top-module','tb_kwt_icb_slave_sram',
                          '--Mdir',str(work/'obj'),'-o','simulation','-j','2','--threads','1',
                          f'-GSRAM_BACKEND={value}',*map(str,sources)]
            command=E.run_command(compile_argv,work,work/'compile.log',a.timeout,2);report['commands'].append(command)
            error=E.completion_error(command,[])
            if error: raise ValueError('compilation failed: '+error)
            if 'UNOPTFLAT' in Path(command['log']['path']).read_text():
                raise ValueError('combinational feedback reported by Verilator; not accepted')
            binary=work/'obj/simulation'
            if not binary.is_file():raise ValueError('simulation binary missing')
            command=E.run_command([str(binary)],work,work/'run.log',a.timeout,2);report['commands'].append(command)
            error=E.completion_error(command,[MARKER])
            if error:raise ValueError(error)
            text=Path(command['log']['path']).read_text()
            counts=list(map(int,re.findall(MARKER,text,re.M)[0]))
            report['cases'].append({'backend':backend,'status':'PASS','transactions':counts[0],'response_hold_checks':counts[1],
                                    'actual_core_outputs':25348,'complete_tasks':1,'aborted_tasks':1,'binary':E.record(binary)})
            E.verify_records(identity['inputs'])
            print(backend+': protocol PASS',flush=True)
        report['status']='PASS'
    except FileNotFoundError as exc:report.update(status='BLOCKED',error=str(exc))
    except Exception as exc:report['error']=f'{type(exc).__name__}: {exc}'
    finally:
        if 'identity' in report:
            try:E.verify_records(report['identity']['inputs'])
            except (ValueError,OSError) as exc:report.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return {'PASS':0,'FAIL':1,'BLOCKED':2}[report['status']]


if __name__=='__main__':raise SystemExit(main())
