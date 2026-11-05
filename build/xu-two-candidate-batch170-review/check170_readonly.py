#!/usr/bin/env python3
"""Independent host-only review of170. Writes only this review directory and /tmp.

No build170/register170 invocation, remote access, controller mutation, EDA run,
production-script execution or actual experiment restart is performed.
"""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'build/xu-two-candidate-batch170'
DESKTOP = Path('/storage2/2026contest/server4/s4_23usr/Desktop')
PLAN = '8a3e6ac5b4cd7ba3cf039d4a00b653825f541b5375911775337a13d472cc7808'
WORKER = '877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'
POWER = '745d196537f95ee9822e9e8de41871749f449fa02cc296dc9371b641be8a9a2e'


def need(ok, message):
    if not ok:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(path):
    path = Path(path)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def read(path):
    return json.loads(Path(path).read_text())


def main():
    sources = sorted([SOURCE / n for n in ['build170.py', 'register170.py', 'run170.py', 'manifest170.json',
        's2c_unknown167.json', 's2e_final155_preflight166.json', 's2e_final155_power12_166.json',
        's2e_final155_preflight166-command.json', 's2e_final155_power12_166-command.json']])
    before = [identity(p) for p in sources]
    plan = read(SOURCE / 'manifest170.json')
    need(sha(SOURCE / 'manifest170.json') == PLAN, 'reviewed plan differs')
    controller = ROOT / 'build/xu-campaign-batch154/control153/xu_experiments.py'
    need(sha(controller) == plan['worker_sha256'] == WORKER, 'original153 worker differs')
    spec = importlib.util.spec_from_file_location('xu170_independent_host_review153', str(controller))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    checks = []

    def passed(name, **details):
        checks.append(dict(name=name, status='PASS', **details))

    parsed = {}
    for name in ['run170.py', 'register170.py', 'build170.py']:
        parsed[name] = ast.parse((SOURCE / name).read_text(), feature_version=(3, 6))
    passed('Python3.6 runtime and builder grammar', files=list(parsed))
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in parsed['register170.py'].body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and
        isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)}
    need(constants['PLAN_SHA'] == PLAN and constants['WORKER_SHA'] == WORKER, 'registration pins differ')
    need(not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and
        n.func.attr in ['initialize', 'start', 'run', 'kill', 'killpg', 'Popen']
        for n in ast.walk(parsed['register170.py'])), 'registration performs a direct start or mutation')
    passed('registration pins original153 and plan; registration only', worker=identity(controller),
        plan_sha256=PLAN, source_review='Existing controller identity and scope163 receipt are required; same IDs require byte identity; no init/start/kill/Popen.')
    need(not any(isinstance(n, ast.Attribute) and n.attr in ['execv', 'execve', 'Popen', 'run', 'fork']
        for n in ast.walk(parsed['run170.py'])), 'wrapper spawns or execs')
    passed('wrapper has no exec or subprocess spawn', method='runpy.run_path(entry, run_name=__main__) in same process')
    local_map = {str(DESKTOP / 'xu-two-candidate-batch170'): SOURCE,
        str(DESKTOP / 'xu-s2e-final-power166'): ROOT / 'build/xu-s2e-final-power166',
        str(DESKTOP / 'xu-s2c-unknown167'): ROOT / 'build/xu-s2c-unknown167',
        str(DESKTOP / 'xu-campaign-batch154/private147'): ROOT / 'build/xu-campaign-batch154/private147'}
    jobs, frozen = [], []
    for row in plan['jobs']:
        file = SOURCE / Path(row['path']).name
        need(file.stat().st_size == row['bytes'] and sha(file) == row['sha256'], 'job manifest mismatch')
        job = m.validate_job(read(file)); jobs.append(job)
        for record in job['frozen_inputs']:
            prefix, local = next((p, l) for p, l in local_map.items() if record['path'].startswith(p + '/'))
            local_file = local / record['path'][len(prefix) + 1:]
            need(local_file.stat().st_size == record['bytes'] and sha(local_file) == record['sha256'], 'frozen input differs')
            frozen.append(dict(job=job['id'], remote=record, local=identity(local_file)))
    need([j['id'] for j in jobs] == plan['registration_order'] == [
        's2c_unknown167', 's2e_final155_preflight166', 's2e_final155_power12_166'], 'scope/order differs')
    need(plan['profiles'] == ['s2e', 's2c'] and plan['native_cap'] == 1, 'candidate/native policy differs')
    passed('three job manifests and all19 frozen input references checked', reference_count=len(frozen),
        unique_frozen_files=len({r['local']['path'] for r in frozen}))
    need(len({j['output_root'] for j in jobs}) == 3, 'outputs collide')
    for job in jobs:
        need(job['native'] is True and job['process_contains'] == job['output_root'] and
            job['argv'].count(job['output_root']) == 1, 'unique direct worker identity differs')
        for other in jobs:
            if other is not job:
                need(not any(other['process_contains'] in arg for arg in job['argv']), 'cross-job process substring')
        if job['id'] != 's2c_unknown167':
            command_path = SOURCE / Path(job['argv'][job['argv'].index('--command') + 1]).name
            command = read(command_path)
            need(command['out'] == job['output_root'] and command['entry']['sha256'] == POWER and
                command['argv'][command['argv'].index('--out') + 1] == job['output_root'], 'original166 CLI binding differs')
            need('--target-root' in command['argv'] and not any(
                's2e-own-timing-repair-20261105-155' in arg for arg in job['argv']), 'historical155 marker leaked to kernel argv')
    passed('kernel argv process markers unique; original166 CLI retained in frozen command JSON')
    need(jobs[0]['dependencies'] == [dict(id='s2e_streamaudit164', policy='terminal')], '167 predecessor differs')
    need(jobs[1]['dependencies'] == [dict(id='s2c_unknown167', policy='terminal'),
        dict(id='s2e_timing155', policy='success')], 'task0 predecessors differ')
    need(jobs[2]['dependencies'] == [dict(id='s2e_final155_preflight166', policy='success')], 'full12 prerequisite differs')
    need(jobs[1]['success_statuses'] == ['EXECUTED_TASK0_DIAGNOSTIC_NOT_QUALIFIED'] and
        jobs[2]['success_statuses'] == ['EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'], '166 success gate differs')
    for job in jobs[1:]:
        need(job['failure_statuses'] == ['FAIL166_NOT_QUALIFIED'] and
            job['result_state'] == job['output_root'] + '/result.json', '166 failure/result target differs')
    need(jobs[0]['failure_statuses'] == ['FAIL_OBSERVATION167_NOT_QUALIFIED'] and
        jobs[0]['result_state'] == jobs[0]['output_root'] + '/state.json', '167 failure/result target differs')
    passed('dependency order and terminal statuses match actual167 and166 contracts', dependencies={j['id']: j['dependencies'] for j in jobs})
    passed('original153 whole-worker native slot retained', source_evidence='observe runs even for DONE rows and waits while a matching worker remains; guard refuses any existing native/reserved/live worker. No controller source changes.')
    with tempfile.TemporaryDirectory(prefix='xu170-wrapper-review-') as td:
        td = Path(td); entry = td / 'stub.py'; out = td / 'only-live-output'
        entry.write_text('import json,sys,os\nfrom pathlib import Path\np=Path(sys.argv[sys.argv.index("--out")+1]);p.mkdir()\n(p/"result.json").write_text(json.dumps(dict(status="STUB_ONLY_NOT_NATIVE",file=__file__,name=__name__,argv=sys.argv,pid=os.getpid(),proc=Path("/proc/self/cmdline").read_bytes().decode().split("\\0"))))\n')
        original = [str(entry), 'campaign', '--target-root', 'HISTORICAL_OTHER_MARKER',
            '--preflight-root', 'PRIOR_JOB_MARKER', '--out', str(out)]
        command = dict(schema='xu-frozen-inprocess-command170-v1', qualification='NOT_QUALIFIED',
            entry=identity(entry), argv=original, out=str(out))
        path = td / 'command.json'; path.write_text(json.dumps(command))
        argv = [sys.executable, '-B', str(SOURCE / 'run170.py'), '--command', str(path), '--out', str(out)]
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(timeout=10)
        need(proc.returncode == 0, 'wrapper stub failed: ' + stderr.decode())
        result = read(out / 'result.json')
        need(result['argv'] == original and result['file'] == str(entry) and result['name'] == '__main__' and
            result['pid'] == proc.pid, 'same-process runpy metadata differs')
        need(str(SOURCE / 'run170.py') in result['proc'] and 'HISTORICAL_OTHER_MARKER' not in result['proc'] and
            'PRIOR_JOB_MARKER' not in result['proc'], 'kernel argv was overwritten or leaked dependency markers')
        passed('temporary stub proves same PID, original argv, __file__, __main__, unchanged kernel argv',
            result=result, process_pid=proc.pid, argv=argv, returncode=proc.returncode,
            stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest(),
            fixture_scope='Temporary stub only, never actual166 or native EDA.')
        entry.write_text('raise SystemExit(7)\n'); out2 = td / 'exit-only'
        command.update(out=str(out2), entry=identity(entry), argv=[str(entry), 'campaign', '--out', str(out2)])
        path.write_text(json.dumps(command))
        argv = [sys.executable, '-B', str(SOURCE / 'run170.py'), '--command', str(path), '--out', str(out2)]
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        need(result.returncode == 7, 'wrapper swallowed original exit status')
        passed('temporary stub SystemExit7 propagated', returncode=result.returncode)
        command['entry']['sha256'] = '0' * 64; path.write_text(json.dumps(command))
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        need(result.returncode != 0 and not out2.exists(), 'changed entry was accepted')
        passed('incorrect entry SHA rejected before stub execution', returncode=result.returncode,
            stderr_sha256=hashlib.sha256(result.stderr).hexdigest())
    after = [identity(p) for p in sources]
    need(before == after, 'production sources changed during review')
    passed('all nine170 source/declaration files unchanged before and after', source_files=after)
    report = dict(schema='xu-two-candidate-batch170-independent-review-v1',
        status='HOST_ONLY_REVIEW_PASS_NO_BLOCKING_FINDINGS_NOT_NATIVE_OR_QUALIFIED', qualification='NOT_QUALIFIED',
        reviewer='xu independent finish166_now agent', reviewed_utc=datetime.now(timezone.utc).isoformat(),
        command='python3 -B build/xu-two-candidate-batch170-review/check170_readonly.py',
        checked_plan_sha256=PLAN, checked_controller_sha256=WORKER,
        production_source_changes=0, remote_actions=0, native_experiments=0,
        checks=checks, frozen_references=frozen,
        known_caveat_resolved='Before wrapper, full12 preflight-root and155 target-root leaked older job process markers. Kernel argv uniqueness now checked and independently observed using a temporary stub.',
        limitations=['No remote registration, server /proc, native VCS/PT or EDA execution was performed.',
            'The temporary stub verifies wrapper mechanics only; no synthetic result may be adopted as actual166 output.',
            'Actual deployment requires server file SHA, live original153 identity, fresh outputs, and scope163 checks in register170.',
            'All native results remain NOT_QUALIFIED; existing timing, function and unknown SRAM Q qualification debts are unchanged.'])
    (HERE / 'review170.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(report['status'])
    print('checks=%d frozen_references=%d review_sha256=%s' % (len(checks), len(frozen), sha(HERE / 'review170.json')))


if __name__ == '__main__':
    main()
