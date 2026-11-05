#!/usr/bin/env python3
"""Batch registration guards and concurrent reader; starts no experiment."""
from pathlib import Path
import json
import tempfile
import threading
import enroll152 as m

controller = Path(__file__).resolve().parents[1]/'xu-experiment-control150/xu_experiments.py'
api = m.module(controller, m.CONTROL_SHA)
checks = []
with tempfile.TemporaryDirectory(prefix='xu-enroll152-') as temp:
    root = Path(temp);out = root/'control';api.initialize(out)
    frozen = root/'input';frozen.write_text('fixed')
    def job(name, deps=None):
        dest = root/name
        return dict(schema='xu-experiment-control150-job-v1', qualification='NOT_QUALIFIED', id=name,
                    kind='launch', launch_mode='direct', dependencies=deps or [], output_root=str(dest),
                    process_contains=str(dest), result_state=str(dest/'result.json'), argv=['python3','worker.py','--out',str(dest)],
                    success_statuses=['COMPLETE_NOT_QUALIFIED'], failure_statuses=['FAILED_NOT_QUALIFIED'],
                    frozen_inputs=[api.identity(frozen)])
    a, b = job('a'), job('b', [dict(id='a', policy='success')])
    paths = []
    for value in (a,b):
        path=root/(value['id']+'.json');path.write_text(json.dumps(value));paths.append(path)
    m.enroll(controller,out,paths,root/'receipt.json')
    assert {p.stem for p in (out/'registrations').glob('*.json')} == {'a','b'}
    m.enroll(controller,out,paths,root/'retry.json')
    checks.append('complete batch and byte-identical retry')
    for title, incoming in [
            ('missing dependency rejected', {'b':job('b',[dict(id='absent',policy='success')])}),
            ('dependency cycle rejected', {'a':job('a',[dict(id='b',policy='terminal')]),'b':b}),
            ('shared process identity rejected', {'a':a,'b':dict(b,process_contains=a['process_contains'])})]:
        try:
            m.validate_batch(api,incoming,{})
        except ValueError:
            checks.append(title)
        else:
            raise AssertionError(title)
    a_path=paths[0];a_path.write_text(json.dumps(a,indent=2))
    try:
        m.enroll(controller,out,[a_path],root/'changed.json')
    except ValueError:
        checks.append('same ID with different bytes rejected')
    else:
        raise AssertionError('registration bytes replaced')
    # A continuously reading controller can see absent or complete, never partial.
    target=root/'atomic.json';raw=json.dumps(dict(payload='x'*2000000)).encode()
    errors=[];stop=threading.Event()
    def read_loop():
        while not stop.is_set():
            try:
                if target.exists():
                    assert json.loads(target.read_bytes())['payload']=='x'*2000000
            except BaseException as exc:
                errors.append(str(exc));return
    reader=threading.Thread(target=read_loop);reader.start()
    m.publish(target,raw)
    assert target.read_bytes()==raw
    stop.set();reader.join();assert not errors,errors
    checks.append('atomic publication exposes no partial JSON to live reader')
print(json.dumps(dict(status='HOST_ENROLL152_CHECKS_PASS_NO_EDA',checks=checks),sort_keys=True,indent=2))
