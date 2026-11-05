#!/usr/bin/env python3
"""Atomically publish a reviewed batch into the already running controller150.

One-time enrollment only: no EDA launch, controller restart, or output rewrite.
Daily observation and dispatch remain xu_experiments.py on the server.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import uuid

CONTROL_SHA = 'd7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f'


def need(value, message):
    if not value:
        raise ValueError(message)


def decode(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result,'duplicate JSON key: '+key)
            result[key]=value
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique)


def module(path, expected_sha):
    need(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected_sha, 'reviewed frozen controller differs')
    spec = importlib.util.spec_from_file_location('xu_original150', str(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def validate_graph(jobs):
    visiting, visited = set(), set()
    def visit(name):
        need(name not in visiting, 'dependency cycle: ' + name)
        if name in visited:
            return
        visiting.add(name)
        for dep in jobs[name]['dependencies']:
            need(dep['id'] in jobs, 'missing dependency: ' + dep['id'])
            visit(dep['id'])
        visiting.remove(name)
        visited.add(name)
    for name in sorted(jobs):
        visit(name)


def validate_batch(control, incoming, existing):
    combined = dict(existing)
    for name, job in incoming.items():
        control.validate_job(job)
        need(name == job['id'], 'job ID and filename differ')
        need(job['kind'] == 'launch' and job.get('launch_mode') == 'direct', 'new batch requires direct workers')
        out = Path(job['output_root'])
        need(out.is_absolute() and '..' not in out.parts and str(out) == job['process_contains'], 'unique exact absolute output/process identity required')
        need(str(Path(job['result_state']).parent) == str(out), 'result must be directly inside own output')
        need(set(job['success_statuses']).isdisjoint(job['failure_statuses']), 'success and failure statuses overlap')
        if name in combined:
            need(combined[name] == job, 'existing job cannot be changed')
        combined[name] = job
    outputs, states, processes = {}, {}, {}
    for name, job in sorted(combined.items()):
        for value, seen, label in [(job.get('output_root'), outputs, 'output'),
                                   (job['result_state'], states, 'result'),
                                   (job['process_contains'], processes, 'process')]:
            if value is None:
                continue
            need(value not in seen, 'duplicate ' + label + ': ' + name)
            seen[value] = name
    validate_graph(combined)


def publish(target, raw):
    """Hidden non-json temp cannot be observed by controller glob('*.json')."""
    temporary = target.with_name('.' + target.name + '.tmp.' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(target))
        descriptor = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()


def enroll(controller, out, job_paths, receipt, expected_sha=CONTROL_SHA):
    controller = Path(controller).resolve()
    control = module(controller, expected_sha)
    out, receipt = Path(out).resolve(), Path(receipt).resolve()
    need(not receipt.exists() and receipt.parent.is_dir(), 'fresh receipt in an existing directory required')
    need(out.is_dir() and (out/'state.json').is_file(), 'existing controller state required; never initializes')
    state = control.read(out/'state.json')
    need(state['worker'] == control.identity(controller), 'controller state does not bind original deployed bytes')
    files = [Path(p).resolve() for p in job_paths]
    need(files and len(files) == len(set(files)), 'one or more distinct job files required')
    incoming, bodies = {}, {}
    for path in files:
        need(path.is_file() and not path.is_symlink(), 'regular job file required')
        raw = path.read_bytes()
        job = decode(raw)
        name = path.stem
        need(name not in incoming, 'duplicate batch ID')
        incoming[name], bodies[name] = job, raw
    record = dict(schema='xu-atomic-enrollment152-v1', status='VALIDATING_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
                  controller=control.identity(controller), controller_out=str(out), started_epoch=time.time(), jobs={})
    with (out/'register.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing_paths = sorted((out/'registrations').glob('*.json'))
        existing = {p.stem: control.validate_job(control.read(p)) for p in existing_paths}
        validate_batch(control, incoming, existing)
        # Verify the entire batch before the first job becomes visible.
        for name, job in sorted(incoming.items()):
            target = out/'registrations'/(name+'.json')
            if target.exists():
                need(target.read_bytes() == bodies[name], 'same ID requires byte-identical registration')
            else:
                need(not Path(job['output_root']).exists(), 'output already exists; inspect/adopt original instead')
            checked = control.check_records(job['frozen_inputs'])
            record['jobs'][name] = dict(registration_sha256=hashlib.sha256(bodies[name]).hexdigest(),
                                      frozen_input_count=len(checked), already_registered=target.exists())
        for name in sorted(incoming):
            target = out/'registrations'/(name+'.json')
            if not target.exists():
                publish(target, bodies[name])
            need(target.read_bytes() == bodies[name], 'published bytes differ')
    record.update(status='REGISTERED_ATOMIC_BATCH_NOT_QUALIFIED', finished_epoch=time.time(), job_count=len(incoming))
    publish(receipt, (json.dumps(record, sort_keys=True, indent=2)+'\n').encode())
    print(json.dumps(record, sort_keys=True, indent=2), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controller', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--jobs-root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--expected-controller-sha', default=CONTROL_SHA)
    args = parser.parse_args()
    files = sorted(args.jobs_root.glob('*.json'))
    # Only explicit job schema files belong in this dedicated jobs directory.
    enroll(args.controller, args.out, files, args.receipt, args.expected_controller_sha)


if __name__ == '__main__':
    main()
