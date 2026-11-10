#!/usr/bin/env python3
"""Local rejection tests; Popen is forbidden throughout."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
from unittest import mock


def main():
    here = Path(__file__).resolve().parent
    original = Path.cwd()
    checks = []
    with tempfile.TemporaryDirectory(prefix='p4k-server-guard-') as td:
        root = Path(td)
        runner = root / 'run_once.py'
        shutil.copy2(here / 'run_once.py', runner)
        payload = root / 'rtl.f'
        payload.write_text('frozen\n')
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [runner, payload]}
        (root / 'package-files.json').write_text(json.dumps(files))
        spec = importlib.util.spec_from_file_location('p4k_runner', runner)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        def invoke(args=(), jobs=None, expected=None, expired=False):
            try:
                with contextlib.ExitStack() as stack:
                    stack.enter_context(mock.patch('sys.argv', [str(runner)] + list(args)))
                    stack.enter_context(mock.patch.object(mod.subprocess, 'Popen', side_effect=AssertionError('EDA launch forbidden')))
                    stack.enter_context(mock.patch.object(mod.time, 'time', return_value=mod.DEADLINE + (1 if expired else -100)))
                    if jobs is not None:
                        stack.enter_context(mock.patch.object(mod, 'heavy_jobs', return_value=jobs))
                    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    try:
                        result = mod.main()
                    except ValueError as e:
                        assert expected and expected in str(e), (expected, str(e))
                        return 'PASS'
                    assert expected is None and result == 0
                    return 'PASS'
            finally:
                os.chdir(str(original))

        def check(name, *a, **kw):
            checks.append({'name': name, 'status': invoke(*a, **kw)})

        check('default_review_never_launches')
        payload.write_text('drift\n')
        check('source_drift_blocks', expected='drift')
        payload.write_text('frozen\n')
        check('deadline_blocks_new_execution', ['--run'], expected='deadline', expired=True)
        (root / 'WORK').mkdir()
        check('existing_output_blocks', ['--run'], expected='overwrite')
        (root / 'WORK').rmdir()
        sim = {'pid': 90373, 'comm': 'simv', 'exe': 'simv',
               'cwd_basename': 'xu-gls-cen-local-strict', 'starttime': '1'}
        check('uncoordinated_simv_blocks', ['--run'], [sim], 'uncoordinated')
        allowed_args = ['--run', '--coordinated-simv-pid', '90373']
        check('coordinated_allow_rejects_other_pid', allowed_args, [dict(sim, pid=90374)], 'uncoordinated')
        check('reused_pid_wrong_cwd_blocks', allowed_args, [dict(sim, cwd_basename='other-job')], 'uncoordinated')
        check('coordinated_allow_rejects_eda', allowed_args, [dict(sim, comm='pt_shell', exe='pt_shell')], 'uncoordinated')
        for bad in ['a{b', 'a}b', 'a\\b', 'a\nb']:
            try:
                mod.tcl(bad)
            except ValueError:
                pass
            else:
                raise AssertionError('unsafe Tcl accepted')
        checks.append({'name': 'unsafe_tcl_literals_rejected', 'status': 'PASS'})
    print(json.dumps({'status': 'PASS', 'tests': checks, 'test_count': len(checks),
                      'eda_launched': False}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
