#!/usr/bin/env python3
"""Read-only controller150 review; fixtures never invoke EDA or remote tools.

Expected results document two current failure boundaries. This is not a suite
claiming controller correctness. All files/processes used by the fixtures are
temporary and native worker stand-ins are ordinary short-lived Python sleepers.
"""
import argparse
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

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'xu-experiment-control150/xu_experiments.py'


def module():
    spec = importlib.util.spec_from_file_location('xu150_review147', str(SOURCE))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def job(name, base):
    output = base / ('worker-' + name)
    return dict(schema='xu-experiment-control150-job-v1', qualification='NOT_QUALIFIED',
                id=name, kind='launch', launch_mode='direct', dependencies=[],
                process_contains=str(output), result_state=str(output / 'state.json'),
                output_root=str(output), native=True,
                success_statuses=['COMPLETE'], failure_statuses=['FAIL'],
                argv=[sys.executable, '-c', 'import time;time.sleep(60)', str(output)],
                frozen_inputs=[dict(path=str(SOURCE), sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest())])


def registration_race():
    m = module()
    with tempfile.TemporaryDirectory(prefix='xu147-reg-review-') as temporary:
        base = Path(temporary); out = base / 'control'; state = m.initialize(out)
        registration = job('race', base); source = base / 'job.json'
        source.write_text(json.dumps(registration))
        target = out / 'registrations/race.json'
        created = threading.Event(); release = threading.Event(); errors = []
        original_open = Path.open

        class Gate:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def __getattr__(self, name): return getattr(self.stream, name)
            def write(self, data):
                created.set()
                if not release.wait(10): raise RuntimeError('review synchronization timeout')
                return self.stream.write(data)

        def gated_open(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return Gate(stream) if path == target and args and args[0] == 'xb' else stream

        def register():
            try: m.register(out, source)
            except BaseException as error: errors.append(type(error).__name__ + ': ' + str(error))

        Path.open = gated_open
        thread = threading.Thread(target=register)
        try:
            thread.start()
            assert created.wait(10), 'registration creation not reached'
            assert target.exists() and target.stat().st_size == 0
            try:
                m.tick(out, state)
            except Exception as error:
                outcome = dict(exception=type(error).__name__, message=str(error))
            else:
                raise AssertionError('expected current non-atomic registration exposure not reproduced')
        finally:
            release.set(); thread.join(10); Path.open = original_open
        assert not thread.is_alive() and not errors
        assert outcome['exception'] == 'JSONDecodeError'
        assert m.read(target) == registration
        return dict(status='REPRODUCED', scenario='register target exists before bytes become visible',
                    tick_outcome=outcome, registration_completed_after_release=True,
                    effects='Controller run loop propagates exception; worker tasks are not killed by this fixture.')


def spawn_persistence_error():
    m = module(); pids = []
    with tempfile.TemporaryDirectory(prefix='xu147-spawn-review-') as temporary:
        base = Path(temporary); out = base / 'control'; state = m.initialize(out)
        for name in ['a', 'b']:
            source = base / ('job-' + name + '.json'); source.write_text(json.dumps(job(name, base)))
            m.register(out, source)
        # Real Python stand-ins exercise the phase where registered native jobs
        # have a live worker but currently no pt_shell/dc_shell/VCS subprocess.
        m.resources = lambda location, ps: dict(mem_available_bytes=32 * 1024**3,
                                               disk_available_bytes=200 * 1024**3,
                                               native_processes=[])
        original_save = m.save

        def failed_spawn_receipt(path, value):
            if Path(path) == out / 'runs/a/spawn.json':
                raise OSError('injected review fixture: spawn receipt write unavailable')
            return original_save(path, value)

        m.save = failed_spawn_receipt
        try:
            m.tick(out, state)
            first = dict(state['jobs']['a']); pids.append(first['pid'])
            assert first['status'] == 'REJECTED_INPUT_REVIEW_REQUIRED'
            os.kill(first['pid'], 0)
            m.tick(out, state)
            second = dict(state['jobs']['b']); pids.append(second['pid'])
            assert second['status'] == 'RUNNING'
            os.kill(first['pid'], 0); os.kill(second['pid'], 0)
            live = [p for p in m.processes() if p['pid'] in pids]
            assert len(live) == 2
            return dict(status='REPRODUCED', scenario='Popen succeeds, then spawn receipt save fails',
                        first_job_status=first['status'], first_worker_pid=first['pid'],
                        first_worker_alive_at_second_dispatch=True,
                        second_job_status=second['status'], second_worker_pid=second['pid'],
                        live_worker_observations=live,
                        effects='DONE failure skips later observe and loses reservation during native phase gaps.')
        finally:
            for pid in pids:
                try: os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError: pass
            for pid in pids:
                try: os.waitpid(pid, 0)
                except ChildProcessError: pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'fresh evidence file required'
    report = dict(schema='xu.controller150.independent-review147.v1',
                  controller_source=str(SOURCE), controller_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  qualification='NOT_QUALIFIED', remote_operations=0, eda_operations=0,
                  registration_race=registration_race(),
                  post_spawn_persistence_failure=spawn_persistence_error())
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print('XU150_INDEPENDENT_REVIEW_147_TWO_FAILURE_BOUNDARIES_REPRODUCED_NO_EDA')


if __name__ == '__main__':
    main()
