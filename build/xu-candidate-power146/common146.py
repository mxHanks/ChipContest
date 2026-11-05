"""Small immutable-file and native-process primitives, Python 3.6+."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

BAD = re.compile(r'^[ \t]*(?:Error:|Error-|Fatal:|XU_FATAL:)|\b[1-9][0-9]* errors?\b', re.I)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def identity(path):
    path = Path(path).absolute()
    need(path.is_file() and not path.is_symlink(), 'regular non-symlink input required: '+str(path))
    before = path.stat()
    digest = sha(path)
    after = path.stat()
    need((before.st_size, before.st_mtime_ns, before.st_ino) ==
         (after.st_size, after.st_mtime_ns, after.st_ino), 'file changed during hash: '+str(path))
    return dict(path=str(path), bytes=before.st_size, sha256=digest)


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp.%d' % os.getpid())
    with temporary.open('w') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(path))


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def record(value, records):
    need(isinstance(value, dict) and Path(value.get('path', '')).is_absolute() and
         re.fullmatch('[0-9a-f]{64}', value.get('sha256', '')), 'actual absolute input identity required')
    actual = identity(value['path'])
    need(actual['sha256'] == value['sha256'] and ('bytes' not in value or actual['bytes'] == value['bytes']),
         'actual input identity changed: '+value['path'])
    need(actual['path'] not in records or records[actual['path']] == actual['sha256'], 'conflicting input identity')
    records[actual['path']] = actual['sha256']
    return actual


def collect(value, records):
    if isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            record(value, records)
        for key, item in value.items():
            if isinstance(key, str) and key.startswith('/') and isinstance(item, str) and re.fullmatch('[0-9a-f]{64}', item):
                record(dict(path=key, sha256=item), records)
            else:
                collect(item, records)
    elif isinstance(value, list):
        for item in value:
            collect(item, records)


def verify(records):
    for path, digest in sorted(records.items()):
        need(identity(path)['sha256'] == digest, 'frozen input changed: '+path)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tcl(value):
    value = str(value)
    need(not any(c in value for c in '{}\\\r\n'), 'unsupported Tcl character: '+value)
    return '{'+value+'}'


def checked_log(path, marker, rc):
    count, version = 0, False
    with Path(path).open(errors='replace') as source:
        for line in source:
            need(not BAD.search(line), 'native PT diagnostic failure: '+str(path))
            count += line.rstrip('\r\n') == marker
            version = version or 'Version T-2022.03-SP5-1' in line
    need(rc == 0 and count == 1 and version, 'PT return code/version/unique marker failed: '+str(path))


def environment(lc_root):
    root = Path(lc_root).resolve()
    need(root.is_dir() and (root/'bin').is_dir(), 'Library Compiler root/bin missing')
    result = os.environ.copy()
    result['SYNOPSYS_LC_ROOT'] = str(root)
    result['PATH'] = str(root/'bin')+os.pathsep+result.get('PATH', '')
    return result


def execute(command, directory, marker, timeout, env, resume=False):
    """Persist child PID before waiting; recover completed output without a rerun.

    An orphaned live child is monitored, never replaced. An incomplete dead child
    is a recorded failure; its logs are never overwritten or treated as complete.
    """
    directory = Path(directory)
    path, log = directory/'native-state.json', directory/'pt.log'
    if path.exists():
        need(resume, 'native execution exists; explicit resume required')
        state = read(path)
        need(state['command'] == command and state['marker'] == marker, 'native recovery command/marker differs')
        if state.get('returncode') == 0:
            checked_log(log, marker, 0)
            return state
        need(state['status'] == 'RUNNING_DIAGNOSTIC_NOT_QUALIFIED', 'native failed; preserve attempt and investigate')
        deadline = state['deadline_epoch']
        while True:
            # /proc start time prevents PID-reuse adoption on the Linux server.
            proc = Path('/proc/%d/stat' % state['pid'])
            try:
                parts = proc.read_text().rsplit(')', 1)[1].split()
                alive = parts[0] != 'Z' and parts[19] == state['proc_start_ticks']
            except FileNotFoundError:
                alive = False
            if not alive:
                break
            need(time.time() < deadline, 'orphan PT exceeded recorded timeout; investigate original process')
            time.sleep(2)
        # The marker is inside guarded Tcl before exit; recovery still requires
        # reports/audit and checks the absence of every native error below.
        checked_log(log, marker, 0)
        state.update(returncode=0, status='RECOVERED_COMPLETED_DIAGNOSTIC_NOT_QUALIFIED',
                     exit_status_provenance='orphan exit status unavailable; guarded completion marker and reports checked')
    else:
        need(not log.exists(), 'unreceipted PT log exists; refusing overwrite')
        with log.open('x') as stream:
            stream.write(json.dumps(dict(command=command, cwd=str(directory), started_utc=now()))+'\n')
            stream.flush()
            process = subprocess.Popen(command, cwd=str(directory), stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            proc = Path('/proc/%d/stat' % process.pid)
            state = dict(status='RUNNING_DIAGNOSTIC_NOT_QUALIFIED', command=command, marker=marker,
                         pid=process.pid, proc_start_ticks=proc.read_text().rsplit(')', 1)[1].split()[19],
                         started_utc=now(), deadline_epoch=time.time()+timeout)
            write(path, state)
            try:
                rc = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                rc = process.wait()
                stream.write('\nXU_FATAL: PT timeout; original process group killed\n')
            state.update(returncode=rc, status='EXITED_DIAGNOSTIC_NOT_QUALIFIED')
    state.update(finished_utc=now(), log=identity(log))
    write(path, state)
    checked_log(log, marker, state['returncode'])
    return state
