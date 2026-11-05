#!/usr/bin/env python3
"""Build a frozen final diagnostic export job, never registers or launches."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
D=Path('/storage2/2026contest/server4/s4_23usr/Desktop')
B=D/'xu-score-optimization-20261102'


def record(path,remote):
    raw=path.read_bytes()
    return dict(path=str(remote),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def build():
    out=B/'two-candidate-finalpack-20261105-209'
    script=D/'xu-query-autopack209/autopack209.py'
    frozen=[record(HERE/'autopack209.py',script),
            dict(path=str(D/'exporter171.py'),bytes=13392,
                 sha256='9c72cfa8ef45b0b2cfba865af1914728077e63a4fb62c940ad7dacaa81300263')]
    job=dict(schema='xu-experiment-control150-job-v1',id='two_candidate_finalpack209',
        kind='launch',launch_mode='direct',native=True,
        argv=['/bin/python3','-B','-u',str(script),'--out',str(out)],
        dependencies=[dict(id=i,policy='terminal') for i in
                      ['native_query207']],
        output_root=str(out),process_contains=str(out),result_state=str(out/'state.json'),
        success_statuses=['EXPORTED_TWO_CANDIDATE_FINAL209_NOT_QUALIFIED'],
        failure_statuses=['FAIL_FINALPACK209_NOT_QUALIFIED'],frozen_inputs=frozen,
        qualification='NOT_QUALIFIED')
    (HERE/'two_candidate_finalpack209.json').write_text(json.dumps(job,sort_keys=True,indent=2)+'\n')
    paths=['autopack209.py','build209.py','two_candidate_finalpack209.json','test209.py','README.md']
    rows=[record(HERE/p,p)for p in paths]
    (HERE/'manifest209.json').write_text(json.dumps(dict(schema='xu-finalpack209-manifest-v1',
        qualification='NOT_QUALIFIED',files=rows),sort_keys=True,indent=2)+'\n')


if __name__=='__main__':build()
