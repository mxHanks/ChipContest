"""Durable, bounded native execution for the SRAM candidate runners.

EXITED is a process observation, never a design PASS. A RUNNING file is not
proof of liveness: inspect_command checks Linux boot and process start identity.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import socket
import subprocess
import threading
import time
import uuid


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def record(path):
    path = Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'size_bytes':path.stat().st_size}


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as stream:
            stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def verify_records(items):
    for item in items:
        path = Path(item['path'])
        if not path.is_file() or record(path)['sha256'] != item['sha256']:
            raise ValueError('input or evidence changed: '+str(path))


def source_identity(paths, configuration, output):
    identity = {'schema':'kwt-sram-source-identity-v1','configuration':configuration,
                'inputs':[record(path) for path in paths]}
    identity['source_id'] = hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    write_json(output,identity)
    return identity


def process_identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        if fields[0] == 'Z': return None
        return {'pid':pid,'process_start_ticks':fields[19],
                'pid_namespace':str(Path(f'/proc/{pid}/ns/pid').readlink()),
                'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    except (FileNotFoundError, ProcessLookupError):
        return None


def inspect_command(path):
    try:
        value = json.loads(Path(path).read_text())
        if value.get('status') != 'RUNNING': return value.get('status','UNKNOWN')
        if value.get('host') not in (None,socket.gethostname()): return 'UNKNOWN'
        # Separate command sandboxes may share hostname and boot ID but have
        # different PID namespaces. A missing PID in ours says nothing about
        # such a job; legacy records without this scope are also unverified.
        if value.get('pid_namespace') != str(Path('/proc/self/ns/pid').readlink()): return 'UNKNOWN'
        actual = process_identity(value['pid'])
        if actual is None: return 'NOT_RUNNING'
        return 'RUNNING' if all(actual[k] == value[k] for k in ('pid','process_start_ticks','boot_id')) else 'NOT_RUNNING'
    except (OSError, ValueError, KeyError, IndexError):
        return 'UNKNOWN'


class _RunSignal(BaseException):
    def __init__(self, number): self.number = number


def run_command(argv, cwd, log, timeout, jobs):
    log = Path(log).resolve()
    state_path = log.with_suffix('.command.json')
    if log.exists() or state_path.exists():
        raise FileExistsError('refusing to overwrite native evidence: '+str(log))
    state = {'schema':'kwt-sram-command-v1','status':'STARTING','argv':list(map(str,argv)),
             'cwd':str(cwd),'host':socket.gethostname(),'supervisor':process_identity(os.getpid()),
             'started_utc':now(),'timeout_seconds':timeout,'timed_out':False,'interrupted':False,'exit_code':None}
    started = time.monotonic()
    environment = os.environ.copy()
    environment.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='1',
                       OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',MAKEFLAGS=f'-j{jobs}')
    process = None
    handlers = {}

    def save():
        write_json(state_path,state)
        write_json(log.parent/'run_state.json',{'schema':'kwt-sram-run-progress-v1','updated_utc':now(),
                   'last_command':str(state_path),'native_status':state['status'],
                   'note':'native command state only; inspect PID identity before declaring live'})

    def terminate_owned_child():
        if process is None or process.poll() is not None: return
        # Legacy nested runners can create their own sessions. Capture only
        # descendants of this live owned process before signalling its group;
        # compare start identity again before signalling each detached child.
        parents={}
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                fields=entry.joinpath('stat').read_text().rsplit(')',1)[1].split()
                parents[int(entry.name)]=int(fields[1])
            except (OSError,ValueError,IndexError):continue
        descendants={process.pid}
        while True:
            expanded=descendants|{pid for pid,parent in parents.items() if parent in descendants}
            if expanded==descendants:break
            descendants=expanded
        identities=[process_identity(pid) for pid in descendants if pid!=process.pid]
        identities=[item for item in identities if item is not None]
        def signal_descendants(number):
            for item in identities:
                if process_identity(item['pid'])!=item:continue
                try:os.kill(item['pid'],number)
                except ProcessLookupError:pass
        try: os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError: pass
        signal_descendants(signal.SIGTERM)
        try: process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
        signal_descendants(signal.SIGKILL)

    def on_signal(number, frame):
        raise _RunSignal(number)

    def child_limits():
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))

    save()
    try:
        with log.open('x') as stream:
            if threading.current_thread() is threading.main_thread():
                for number in (signal.SIGINT,signal.SIGTERM):
                    handlers[number] = signal.getsignal(number)
                    signal.signal(number,on_signal)
            process = subprocess.Popen(state['argv'],cwd=cwd,env=environment,stdout=stream,
                                       stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=child_limits)
            state.update(process_identity(process.pid) or {'pid':process.pid})
            state['status']='RUNNING'
            save()
            try:
                state['exit_code']=process.wait(timeout=timeout)
                state['status']='EXITED'
            except subprocess.TimeoutExpired:
                terminate_owned_child()
                state.update(status='TIMED_OUT',timed_out=True,exit_code=process.returncode)
            except (_RunSignal,KeyboardInterrupt) as exc:
                terminate_owned_child()
                state.update(status='INTERRUPTED',interrupted=True,exit_code=process.returncode,
                             received_signal=getattr(exc,'number',int(signal.SIGINT)))
    except (_RunSignal,KeyboardInterrupt) as exc:
        terminate_owned_child()
        state.update(status='INTERRUPTED',interrupted=True,exit_code=process.returncode if process else None,
                     received_signal=getattr(exc,'number',int(signal.SIGINT)))
    except OSError as exc:
        state.update(status='LAUNCH_FAILED',error=str(exc))
    finally:
        terminate_owned_child()
        for number,handler in handlers.items(): signal.signal(number,handler)
        state.update(finished_utc=now(),elapsed_seconds=round(time.monotonic()-started,3))
        if log.is_file(): state['log']=record(log)
        save()
    return {**state,'native_state':record(state_path)}


def completion_error(command, patterns):
    if command.get('status') != 'EXITED' or command.get('exit_code') != 0:
        return 'native process did not exit cleanly'
    if command.get('timed_out') or command.get('interrupted'): return 'incomplete native run'
    try:
        verify_records([command['log'],command['native_state']])
        saved = json.loads(Path(command['native_state']['path']).read_text())
        if any(saved.get(key) != command.get(key) for key in ('status','exit_code','timed_out','interrupted','argv','log')):
            return 'reported command differs from saved native evidence'
        text = Path(command['log']['path']).read_text(errors='replace')
    except (OSError,KeyError,ValueError) as exc:
        return str(exc)
    if re.search(r'(?:^|\n)\s*(?:%Error\b|FATAL\b|ERROR\b|FAIL\b)|\b(?:Aborting|Assertion failed)\b',text,re.I):
        return 'failure diagnostic in log'
    for pattern in patterns:
        if len(re.findall(pattern,text,re.M)) != 1: return 'missing or duplicate complete marker: '+pattern
    return None
