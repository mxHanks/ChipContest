#!/usr/bin/env python3
"""Review sealed SYSBUS32 inputs, or explicitly run one DC or PT stage.

No subprocess/tool/library access occurs in default review mode. This file has
no SSH/transfer operation. Execution is a later, separately authorized action.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from profiles import PROFILES, REGISTER_X, SRAM_X, CORE_B41_SHA

TOP = 'xu_soc_sysbus32_ppa_top'
DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA', 'XU_MATRIX_DMA_SYSBUS32']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def check(path, digest):
    require(Path(path).is_file() and not Path(path).is_symlink() and sha(path) == digest, 'input identity mismatch: ' + str(path))


def check_external(path, digest):
    # Vendor launchers are intentional symlinks. Verify actual bytes while
    # retaining the original path/argv0 when executing (never resolve-launch).
    p = Path(path)
    require(p.is_file() and sha(p) == digest, 'external tool/library identity mismatch: ' + str(p))
    return dict(path=str(p), resolved_path=str(p.resolve()), is_symlink=p.is_symlink(), sha256=sha(p))


def check_inputs(root):
    files = json.loads((root / 'package-files.json').read_text())
    for name, digest in files.items():
        q = Path(name)
        require(not q.is_absolute() and '..' not in q.parts, 'unsafe input path')
        check(root / q, digest)
    m = json.loads((root / 'manifest.json').read_text())
    profile = m.get('hardware_profile', REGISTER_X)
    require(profile in PROFILES, 'unknown hardware profile')
    expected = PROFILES[profile]
    require(m['schema'] == 'sysbus32-sealed-synthesis-preparation-v1' and m['top'] == TOP and m['defines'] == expected['defines'], 'not the exact production32 profile')
    require(m['expected_geometry'] == expected['geometry'], 'profile geometry mismatch')
    require(m['expected_internal_macros'] == expected['internal_macros'], 'profile internal macro count mismatch')
    require(json.loads((root / 'defines.json').read_text()) == expected['defines'], 'production define mismatch')
    require(m['production_test_loader'] is False, 'production loader forbidden')
    require(sha(root / 'source-manifest.json') == m['source_manifest_sha256'], 'source manifest binding mismatch')
    names = (root / 'rtl.f').read_text().splitlines()
    s = json.loads((root / 'source-manifest.json').read_text())
    require(sha(root / 'rtl.f') == m['rtl_f_sha256'] and len(names) == m['source_count'], 'compile list identity/count mismatch')
    require(s['defines'] == expected['defines'] and s['hardware_profile'] == profile, 'source manifest profile mismatch')
    require(names == [x['path'] for x in s['ordered_compile_sources']], 'compile source order mismatch')
    require(not any('generic_ramsp' in n or any(x in n for x in ['xu_matrix_dma64', 'xu_dma64_shared_arb', 'xu_shared_icb_sram64']) for n in names), 'nonproduction compile source')
    for source in s['ordered_compile_sources']:
        check(root / source['path'], source['sha256'])
    core = root / 'source/rtl/perips/LinearTileDmaCore.sv'
    check(core, m['staged_core_sha256'])
    require(m['selected_B41_core_sha256'] == CORE_B41_SHA and m['cpu_core_and_mem_fab_exact_unchanged'] is True,
            'immutable platform/core origin contract mismatch')
    profile_tcl = '# Sealed exact hardware profile. No timing or constraint edits.\n' + \
        'set sysbus32_hardware_profile {' + profile + '}\n' + \
        'set sysbus32_production_defines [list ' + ' '.join(expected['defines']) + ']\n' + \
        'set sysbus32_expected_total_macros ' + str(expected['geometry']['total_macros']) + '\n' + \
        'set sysbus32_expected_x_macros ' + str(expected['geometry']['x']) + '\n' + \
        'set sysbus32_expected_internal_macros ' + str(expected['internal_macros']) + '\n'
    require((root / 'source/ppa/geometry-profile.tcl').read_text() == profile_tcl, 'Tcl profile differs from sealed hardware profile')
    if profile == SRAM_X:
        evidence = root / 'evidence/x-candidate/manifest.json'
        check(evidence, m['x_candidate_manifest_sha256'])
        x = json.loads(evidence.read_text())
        require(x['production_core_sha256'] == CORE_B41_SHA, 'X candidate origin B41 mismatch')
        require(x['storage'] == dict(x_logical_bits=16384, x_physical_bits=262144, x_macros=16,
            internal_macros_before=17, internal_macros_after=33, shared_bytes=524288, weight_macros=16, bias_macros=1),
            'X physical storage accounting mismatch')
        for name, digest in x['candidate_files'].items():
            target = root / ('local-only/' + name if name == 'generic_ramsp_non_ppa.sv' else 'source/rtl/perips/' + name)
            check(target, digest)
        require('source/rtl/perips/TileXMacroRowBuffer.sv' in names, 'X physical wrapper missing from compile list')
    else:
        check(core, CORE_B41_SHA)
    return files, m


def heavy_jobs():
    names = {'simv', 'vcs', 'vcs1', 'dc_shell', 'snps_shell', 'common_shell_ex',
             'pt_shell', 'icc2_shell', 'fm_shell', 'lc_shell', 'verilator_bin'}
    jobs = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            comm = (path / 'comm').read_text().strip()
            exe = Path(os.readlink(str(path / 'exe'))).name
            if comm in names or exe in names:
                jobs.append(dict(pid=int(path.name), comm=comm, exe=exe))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return sorted(jobs, key=lambda row: row['pid'])


def tcl(value):
    require(not any(x in str(value) for x in '{}\\\r\n'), 'unsafe Tcl literal')
    return '{' + str(value) + '}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=['dc', 'pt'], default='dc')
    p.add_argument('--run', action='store_true')
    p.add_argument('--allow-coordinated-busy-jobs', action='store_true', help='Only after explicit user coordination of this independent max2core job; existing jobs are never altered')
    p.add_argument('--coordination-note', help='Concrete authorization and resource arrangement recorded in the execution receipt')
    p.add_argument('--timeout-seconds', type=int, help='bounded tool lifetime; default DC14400/PT300')
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    files, manifest = check_inputs(root)
    defines = manifest['defines']
    toolchain = json.loads((root / 'toolchain.json').read_text())
    record = dict(schema='sysbus32-same-source-' + a.stage + '-execution-v1',
                  status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED', stage=a.stage,
                  top=TOP, defines=defines, hardware_profile=manifest['hardware_profile'], inputs=len(files), run_requested=a.run,
                  manifest_sha256=sha(root / 'package-files.json'), max_cores=2,
                  qualification='NOT_QUALIFIED', timing_verdict='NOT_RUN')
    if not a.run:
        print(json.dumps(record, sort_keys=True))
        return 0
    timeout_seconds = a.timeout_seconds or (14400 if a.stage == 'dc' else 300)
    require(timeout_seconds > 0, 'timeout must be positive')
    busy = heavy_jobs()
    if busy:
        require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip())>=16, 'same-account heavy jobs exist without explicit coordination: ' + json.dumps(busy))
    if a.allow_coordinated_busy_jobs:
        require(a.coordination_note and len(a.coordination_note.strip())>=16, 'coordination note required')
    tool = toolchain[a.stage]
    external_identities = [check_external(tool['path'], tool['sha256'])]
    for lib in toolchain['libraries']:
        external_identities.append(check_external(lib['path'], lib['sha256']))
    env = os.environ.copy()
    dc_binding = None
    if a.stage == 'dc':
        out = root
        for name in ['execution.json', 'WORK', 'dc.log', 'libraries.tcl', 'mapped.v', 'mapped.ddc',
                     'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt', 'SYNTHESIS_FAILED.txt']:
            require(not (root / name).exists(), 'refuse DC restart/overwrite: ' + name)
        libs = toolchain['libraries']
        require([x['role'] for x in libs] == ['standard_cell', 'sram'], 'library roles/order changed')
        (root / 'libraries.tcl').write_text('set_app_var target_library [list ' + tcl(libs[0]['path']) + ']\n' +
             'set_app_var link_library [list * ' + ' '.join(tcl(x['path']) for x in libs) + ']\n')
        command, logname = [tool['path'], '-f', 'synth.tcl'], 'dc.log'
        marker = 'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt'
    else:
        dc = json.loads((root / 'execution.json').read_text())
        require(dc.get('schema') == 'sysbus32-same-source-dc-execution-v1' and dc.get('top') == TOP and dc.get('defines') == defines and dc.get('hardware_profile') == manifest['hardware_profile'], 'PT requires this exact new32 profile DC receipt')
        require(dc.get('status') == 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' and dc.get('returncode') == 0 and dc.get('source_drift') == [] and dc.get('native_tool_errors') == [], 'PT requires completed clean same-package DC collection')
        require(dc.get('manifest_sha256') == record['manifest_sha256'], 'DC package identity mismatch')
        require(dc.get('libraries') == toolchain['libraries'], 'DC library identities changed')
        dc_binding = dict(execution_sha256=sha(root / 'execution.json'), outputs={})
        for name in ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'libraries.tcl', 'leaf-inventory.tsv', 'leaf-area-summary.txt', 'area-components.tsv', 'area-upper-bound.tsv']:
            item = dc.get('outputs', {}).get(name, {})
            require(item.get('sha256'), 'DC output not bound: ' + name)
            check(root / name, item['sha256'])
            require((root / name).stat().st_size == item['bytes'], 'DC output size mismatch: ' + name)
            dc_binding['outputs'][name] = item
        check(root / 'source/contracts/reference-full-soc.sdc', toolchain['sdc_sha256'])
        lc = toolchain['library_compiler']
        external_identities.append(check_external(Path(lc['root']) / 'bin/lc_shell', lc['launcher_sha256']))
        env['SYNOPSYS_LC_ROOT'] = lc['root']
        env['XU_BASELINE_ROOT'] = str(root)
        env['XU_MAPPED_SHA256'] = dc_binding['outputs']['mapped.v']['sha256']
        out = root / 'pt'
        require(not out.exists(), 'refuse PT restart/overwrite')
        out.mkdir(mode=0o700)
        command, logname = [tool['path'], '-f', str(root / 'pt_collect.tcl')], 'pt.log'
        marker = 'SYSBUS32_PT_COLLECTION_COMPLETE_NOT_QUALIFIED.txt'
    record.update(status='RUNNING', command=command, libraries=toolchain['libraries'], external_identities=external_identities,
                  tool=tool, started_epoch=time.time(), timeout_seconds=timeout_seconds,
                  observed_jobs=busy, resource_policy='USER_COORDINATED_INDEPENDENT_MAX2CORE_JOB' if a.allow_coordinated_busy_jobs else 'REFUSE_ALL_SAME_ACCOUNT_HEAVY_JOBS',
                  coordination_note=a.coordination_note if a.allow_coordinated_busy_jobs else None,
                  preexisting_jobs_policy='READ_ONLY_OBSERVATION_NEVER_STOP_OR_MODIFY',
                  source_dc=dc_binding, timing_verdict='UNREVIEWED_NOT_A_TIMING_PASS')
    receipt = out / 'execution.json'
    dump(receipt, record)
    timed_out = False
    with (out / logname).open('w') as log:
        job = subprocess.Popen(command, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        record['pid'] = job.pid
        dump(receipt, record)
        try:
            code = job.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(job.pid, signal.SIGTERM)
            try:
                code = job.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(job.pid, signal.SIGKILL)
                code = job.wait()
    drift = [name for name, digest in files.items() if not (root / name).is_file() or sha(root / name) != digest]
    if dc_binding:
        if sha(root / 'execution.json') != dc_binding['execution_sha256']:
            drift.append('source_dc/execution.json')
        drift += ['source_dc/' + name for name, item in dc_binding['outputs'].items() if sha(root / name) != item['sha256']]
    errors = re.findall(r'^(?:Error:|Fatal:).*$', (out / logname).read_text(errors='replace'), re.MULTILINE)
    complete = (out / marker).is_file()
    required_reports = []
    if a.stage == 'dc':
        required_reports = ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'leaf-inventory.tsv',
                            'leaf-area-summary.txt', 'area-components.tsv', 'area-upper-bound.tsv', 'dc-clock-reports/review_status.txt']
        rp = root / 'dc-clock-reports/review_status.txt'
        complete = complete and rp.is_file() and bool(re.search(r'^REQUIRED_REPORT_FAILURE_COUNT=0$', rp.read_text(), re.MULTILINE))
    else:
        required_reports = ['reports/' + name for name in ['coverage.rpt', 'all_violators.rpt', 'setup.rpt', 'hold.rpt',
                            'recovery.rpt', 'removal.rpt', 'clock_gating_setup.rpt', 'clock_gating_hold.rpt',
                            'min_pulse_width.rpt', 'exceptions.rpt', 'clock_endpoints.tsv']]
    missing = [name for name in required_reports if not (out / name).is_file()]
    record.update(returncode=code, finished_epoch=time.time(), tool_timed_out=timed_out,
                  source_drift=drift, native_tool_errors=errors, completion_marker=complete,
                  missing_required_outputs=missing, mapping_or_timing_qualification=False)
    desired = 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' if a.stage == 'dc' else 'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED'
    record['status'] = desired if code == 0 and complete and not timed_out and not drift and not errors and not missing else 'FAILED'
    record['outputs'] = {f.relative_to(out).as_posix(): dict(bytes=f.stat().st_size, sha256=sha(f))
                         for f in sorted(out.rglob('*')) if f.is_file() and f != receipt
                         and (a.stage == 'pt' or (f.relative_to(root).as_posix() not in files and f.name != 'package-files.json'))}
    dump(receipt, record)
    print(record['status'])
    return 0 if record['status'] == desired else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        sys.exit(1)
