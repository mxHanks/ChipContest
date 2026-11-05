#!/usr/bin/env python3
"""Controller failure/recovery checks. Only temporary files/Python workers."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'xu-experiment-control150/xu_experiments.py'

def load(path):
    spec=importlib.util.spec_from_file_location('xu_control153_test_'+uuid.uuid4().hex,str(path))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def job(base,name='a',kind='launch',dependencies=None):
    output=base/('worker-'+name)
    result=dict(schema='xu-experiment-control150-job-v1',qualification='NOT_QUALIFIED',id=name,
        kind=kind,dependencies=dependencies or [],process_contains=str(output),result_state=str(output/'state.json'),
        native=True,success_statuses=['COMPLETE'],failure_statuses=['FAIL'])
    if kind=='launch':result.update(launch_mode='direct',output_root=str(output),
        argv=[sys.executable,'-c','import time;time.sleep(60)',str(output)],
        frozen_inputs=[dict(path=str(HERE/'xu_experiments.py'),sha256=hashlib.sha256((HERE/'xu_experiments.py').read_bytes()).hexdigest())])
    return result

class Checks(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='xu153-host-')
        self.base=Path(self.temporary.name);self.out=self.base/'controller'
        self.m=load(HERE/'xu_experiments.py');self.state=self.m.initialize(self.out)
        self.pids=[]
    def tearDown(self):
        for pid in self.pids:
            try:os.killpg(pid,signal.SIGTERM)
            except ProcessLookupError:pass
        for pid in self.pids:
            try:os.waitpid(pid,0)
            except ChildProcessError:pass
        self.temporary.cleanup()
    def register(self,value):
        p=self.base/(value['id']+'.json');p.write_text(json.dumps(value));self.m.register(self.out,p);return p
    def resource_stub(self):
        self.m.resources=lambda out,ps:dict(mem_available_bytes=32*1024**3,disk_available_bytes=200*1024**3,native_processes=[])
    def test_resource_limits_and_live_intent(self):
        res=dict(mem_available_bytes=32*1024**3,disk_available_bytes=200*1024**3,native_processes=[])
        self.assertTrue(self.m.guard(res,{},{}).startswith('ALLOW'))
        self.assertEqual(self.m.guard(dict(res,mem_available_bytes=0),{},{}),'WAIT_MEMORY')
        self.assertEqual(self.m.guard(dict(res,disk_available_bytes=0),{},{}),'WAIT_DISK')
        for row in [dict(status='RUNNING_ADOPTED',live_processes=[dict(pid=1)]),dict(status='START_INTENT_REVIEW_IF_ORPHAN'),dict(status='RUNNING')]:
            self.assertEqual(self.m.guard(res,{'a':row},{}),'WAIT_EXCLUSIVE_NATIVE_SLOT')
        self.assertEqual(self.m.guard(dict(res,native_processes=[dict(pid=1)]),{},{}),'WAIT_EXCLUSIVE_NATIVE_SLOT')
    def test_atomic_registration_not_visible_until_complete(self):
        value=job(self.base);source=self.base/'a.json';source.write_text(json.dumps(value))
        created=threading.Event();release=threading.Event();errors=[];original_open=Path.open
        class Gate:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def __getattr__(self,name):return getattr(self.stream,name)
            def write(self,data):
                created.set()
                if not release.wait(10):raise RuntimeError('host test barrier timeout')
                return self.stream.write(data)
        def gated(path,*args,**kwargs):
            stream=original_open(path,*args,**kwargs)
            return Gate(stream) if path.parent==self.out/'registrations' and '.pending.' in path.name and args and args[0]=='xb' else stream
        def register():
            try:self.m.register(self.out,source)
            except BaseException as error:errors.append(repr(error))
        Path.open=gated;thread=threading.Thread(target=register)
        try:
            thread.start();self.assertTrue(created.wait(10))
            self.assertEqual(list((self.out/'registrations').glob('*.json')),[])
            self.m.tick(self.out,self.state)
            self.assertEqual(self.state['jobs'],{})
        finally:
            release.set();thread.join(10);Path.open=original_open
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(self.m.read(self.out/'registrations/a.json'),value)
    def test_registration_idempotent_and_replacement_rejected(self):
        value=job(self.base);p=self.register(value);self.m.register(self.out,p)
        p.write_text(json.dumps(dict(value,process_contains='changed')))
        with self.assertRaises(ValueError):self.m.register(self.out,p)
    def test_duplicate_init_rejected(self):
        with self.assertRaises(ValueError):self.m.initialize(self.out)
    def test_duplicate_controller_file_lock(self):
        with (self.out/'controller.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            p=subprocess.run([sys.executable,'-B',str(HERE/'xu_experiments.py'),'run','--once','--out',str(self.out)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
            self.assertNotEqual(p.returncode,0)
            self.assertIn(b'BlockingIOError',p.stdout)
    def test_wrong_worker_run_refused_before_any_state_write(self):
        old=load(OLD);oldout=self.base/'old';old.initialize(oldout);before=(oldout/'state.json').read_bytes()
        p=subprocess.run([sys.executable,'-B',str(HERE/'xu_experiments.py'),'run','--once','--out',str(oldout)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        self.assertNotEqual(p.returncode,0);self.assertEqual((oldout/'state.json').read_bytes(),before)
    def test_input_change_rejected_before_any_spawn(self):
        source=self.base/'frozen';source.write_text('before');record=self.m.identity(source);source.write_text('after')
        with self.assertRaises(ValueError):self.m.check_records([record])
    def test_post_spawn_receipt_error_keeps_slot(self):
        self.resource_stub();self.register(job(self.base,'a'));self.register(job(self.base,'b'))
        original_save=self.m.save
        def fail(path,value):
            if Path(path)==self.out/'runs/a/spawn.json':raise OSError('injected post-Popen receipt failure')
            return original_save(path,value)
        self.m.save=fail;self.m.tick(self.out,self.state)
        a=self.state['jobs']['a'];self.pids.append(a['pid']);os.kill(a['pid'],0)
        self.assertEqual(a['status'],'START_INTENT_REVIEW_IF_ORPHAN')
        self.m.tick(self.out,self.state)
        self.assertEqual(a['status'],'RUNNING')
        self.assertEqual(self.state['jobs']['b']['status'],'WAIT_EXCLUSIVE_NATIVE_SLOT')
        self.assertFalse((self.out/'runs/b').exists())
    def test_done_row_with_live_worker_still_reserved(self):
        value=job(self.base,kind='adopt');Path(value['result_state']).parent.mkdir();Path(value['result_state']).write_text('{"status":"FAIL"}')
        row=dict(status='FAILED_REVIEW_REQUIRED')
        ps=[dict(pid=999,uid=os.getuid(),start_ticks=123,argv=['python3',value['process_contains']])]
        self.m.observe(value,row,ps)
        self.assertEqual(row['status'],'RUNNING_ADOPTED')
        self.m.observe(value,row,[]);self.assertEqual(row['status'],'FAILED_REVIEW_REQUIRED')
    def test_launcher_nonzero_after_spawn_keeps_slot(self):
        self.resource_stub();value=job(self.base,'a');launcher=self.base/'launcher.py';pidfile=self.base/'spawned.pid'
        launcher.write_text('import subprocess,sys\nfrom pathlib import Path\n'
            'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)",%r],start_new_session=True)\n'
            'Path(%r).write_text(str(p.pid))\nsys.exit(3)\n' % (value['output_root'],str(pidfile)))
        value.update(launch_mode='launcher',argv=[sys.executable,str(launcher)],
                     launch_receipt=str(self.base/'missing-launch-receipt/state.json'),pid_keys=['pid'])
        value['frozen_inputs'].append(self.m.identity(launcher))
        self.register(value);self.register(job(self.base,'b'));self.m.tick(self.out,self.state)
        self.pids.append(int(pidfile.read_text()));os.kill(self.pids[-1],0)
        self.assertEqual(self.state['jobs']['a']['status'],'START_INTENT_REVIEW_IF_ORPHAN')
        self.m.tick(self.out,self.state)
        self.assertEqual(self.state['jobs']['a']['status'],'RUNNING')
        self.assertEqual(self.state['jobs']['b']['status'],'WAIT_EXCLUSIVE_NATIVE_SLOT')
    def test_done_rows_are_observed_on_tick(self):
        value=job(self.base,kind='adopt');self.register(value);root=Path(value['result_state']).parent;root.mkdir();(root/'state.json').write_text('{"status":"FAIL"}')
        self.m.processes=lambda:[];self.m.tick(self.out,self.state)
        self.assertEqual(self.state['jobs']['a']['status'],'FAILED_REVIEW_REQUIRED')
        self.m.processes=lambda:[dict(pid=999,uid=os.getuid(),start_ticks=123,argv=['python3',value['process_contains']])]
        self.m.tick(self.out,self.state);self.assertEqual(self.state['jobs']['a']['status'],'RUNNING_ADOPTED')
    def test_terminal_requires_live_worker_exit(self):
        value=job(self.base,kind='adopt');p=Path(value['result_state']);p.parent.mkdir();p.write_text('{"status":"COMPLETE"}')
        row=dict(status='QUEUED');ps=[dict(pid=1,uid=os.getuid(),start_ticks=123,argv=['python3',value['process_contains']])]
        self.m.observe(value,row,ps);self.assertEqual(row['status'],'RUNNING_ADOPTED')
        self.m.observe(value,row,[]);self.assertEqual(row['status'],'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED')
    def test_orphan_not_restarted_and_independent_can_advance(self):
        self.resource_stub();value=job(self.base);self.register(value);self.m.processes=lambda:[]
        self.state['jobs']['a']=dict(status='START_INTENT_REVIEW_IF_ORPHAN',started_epoch=time.time()-121,start_intent=True,registration=self.m.identity(self.out/'registrations/a.json'))
        self.m.tick(self.out,self.state)
        self.assertEqual(self.state['jobs']['a']['status'],'ORPHAN_REVIEW_REQUIRED')
        self.assertFalse((self.out/'runs/a').exists())
        self.m.tick(self.out,self.state);self.assertFalse((self.out/'runs/a').exists())
    def test_failed_success_dependency_blocks_only_descendant(self):
        self.resource_stub();failed=job(self.base,'a_failed',kind='adopt');self.register(failed)
        p=Path(failed['result_state']);p.parent.mkdir();p.write_text('{"status":"FAIL"}')
        self.register(job(self.base,'b_child',dependencies=[dict(id='a_failed',policy='success')]))
        self.register(job(self.base,'c_independent'))
        started=[]
        def start(out,value,row,state):started.append(value['id']);row['status']='COMPLETED_DIAGNOSTIC_NOT_QUALIFIED'
        self.m.start=start;self.m.processes=lambda:[];self.m.tick(self.out,self.state)
        self.assertEqual(self.state['jobs']['b_child']['status'],'BLOCKED_DEPENDENCY_NOT_QUALIFIED')
        self.assertEqual(started,['c_independent'])
    def test_terminal_policy_allows_failure_but_success_does_not(self):
        self.resource_stub();failed=job(self.base,'a_failed',kind='adopt');self.register(failed)
        p=Path(failed['result_state']);p.parent.mkdir();p.write_text('{"status":"FAIL"}')
        self.register(job(self.base,'b_terminal',dependencies=[dict(id='a_failed',policy='terminal')]))
        started=[]
        self.m.start=lambda out,value,row,state:started.append(value['id'])
        self.m.processes=lambda:[];self.m.tick(self.out,self.state);self.assertEqual(started,['b_terminal'])
    def test_direct_spawn_identity_recovered_from_receipt(self):
        value=job(self.base);run=self.out/'runs/a';run.mkdir()
        token=dict(pid=123,uid=os.getuid(),start_ticks=987,argv=value['argv'])
        self.m.save(run/'spawn.json',dict(pid=123,worker_identity=token,argv=value['argv']))
        row=dict(status='START_INTENT_REVIEW_IF_ORPHAN',started_epoch=time.time(),run_dir=str(run))
        self.m.observe(value,row,[token]);self.assertEqual(row['worker_identity'],token);self.assertTrue(row['worker_identity_alive'])
    def test_reused_pid_is_not_rebound(self):
        value=job(self.base);original=dict(pid=123,uid=os.getuid(),start_ticks=987,argv=value['argv'])
        reused=dict(original,start_ticks=988)
        row=dict(status='RUNNING',started_epoch=time.time(),pid=123,worker_identity=original)
        self.m.observe(value,row,[reused]);self.assertEqual(row['worker_identity'],original)
        self.assertFalse(row['worker_identity_alive']);self.assertIn('pid_reuse_or_command_change',row)
    def test_changed_command_not_same_process(self):
        token=dict(pid=123,uid=os.getuid(),start_ticks=987,argv=['python3','old'])
        self.assertFalse(self.m.same_process(token,dict(token,argv=['python3','new'])))
        self.assertFalse(self.m.same_process(token,dict(token,start_ticks=988)))
        self.assertFalse(self.m.same_process(token,None));self.assertFalse(self.m.same_process(None,token))
    def test_changed_command_same_birth_keeps_slot(self):
        value=job(self.base);token=dict(pid=123,uid=os.getuid(),start_ticks=987,argv=value['argv'])
        changed=dict(token,argv=['python3','different-command'])
        p=Path(value['result_state']);p.parent.mkdir();p.write_text('{"status":"COMPLETE"}')
        row=dict(status='RUNNING',started_epoch=time.time(),pid=123,worker_identity=token)
        self.m.observe(value,row,[changed]);self.assertEqual(row['status'],'RUNNING')
        self.assertEqual(row['live_processes'],[changed]);self.assertFalse(row['worker_identity_alive'])
    def test_actual_process_identity_has_start_ticks_and_command(self):
        observed=self.m.process_identity(os.getpid());self.assertEqual(observed['pid'],os.getpid())
        self.assertGreater(observed['start_ticks'],0);self.assertTrue(observed['argv'])
        self.assertTrue(self.m.same_process(observed,self.m.process_identity(os.getpid())))
    def test_transient_empty_live_handle_not_promoted_to_exit(self):
        value=job(self.base);known=self.m.process_identity(os.getpid())
        p=Path(value['result_state']);p.parent.mkdir();p.write_text('{"status":"COMPLETE"}')
        row=dict(status='RUNNING',started_epoch=time.time(),pid=os.getpid(),worker_identity=known)
        self.m.process_identity=lambda pid:dict(known,argv=[])
        self.m.observe(value,row,[])
        self.assertEqual(row['status'],'RUNNING');self.assertTrue(row['unconfirmed_live_handle'])
    def test_migration_rejects_running_original_controller(self):
        old=load(OLD);oldout=self.base/'old';old.initialize(oldout)
        p=subprocess.Popen([sys.executable,'-B',str(OLD),'run','--out',str(oldout)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.pids.append(p.pid)
        for _ in range(50):
            if old.read(oldout/'state.json').get('controller_pid')==p.pid:break
            time.sleep(.02)
        migration=load(HERE/'migration153.py')
        with self.assertRaises((BlockingIOError,ValueError)):migration.migrate(oldout)
        self.assertEqual(old.read(oldout/'state.json')['worker']['sha256'],migration.ORIGINAL150)
    def test_migration_snapshots_preserves_jobs_runs_and_starts_one_new_controller(self):
        old=load(OLD);oldout=self.base/'old';state=old.initialize(oldout)
        (oldout/'runs/evidence.txt').write_text('preserve exact evidence\n')
        value=job(self.base,'original',kind='adopt');p=Path(value['result_state']);p.parent.mkdir();p.write_text('{"status":"COMPLETE"}')
        path=self.base/'original.json';path.write_text(json.dumps(value));old.register(oldout,path);old.tick(oldout,state)
        before=old.read(oldout/'state.json');migration=load(HERE/'migration153.py')
        receipt=migration.migrate(oldout);self.pids.append(receipt['spawn_pid'])
        self.assertEqual(receipt['status'],'MIGRATED_SAME_OUT_CONTROLLER153_RUNNING_NOT_QUALIFIED')
        snapshot=Path(receipt['snapshot']);self.assertEqual(old.read(snapshot/'state.json'),before)
        self.assertEqual((snapshot/'runs/evidence.txt').read_bytes(),(oldout/'runs/evidence.txt').read_bytes())
        self.assertEqual(old.read(oldout/'state.json')['jobs'],before['jobs'])
        self.assertEqual(receipt['workers_signalled'],0);self.assertEqual(receipt['workers_restarted'],0)
        self.assertEqual(old.read(oldout/'state.json')['worker']['sha256'],hashlib.sha256((HERE/'xu_experiments.py').read_bytes()).hexdigest())
        with self.assertRaises((BlockingIOError,ValueError)):migration.migrate(oldout)

if __name__=='__main__':unittest.main(verbosity=2)
