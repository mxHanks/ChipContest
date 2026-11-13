#!/usr/bin/env python3
"""Sealed bounded ECO stages; read-only review unless --run is explicit.

This runner has no transport or credential code and never changes other jobs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
TOP = 'xu_soc_sysbus32_ppa_top'
STAGES = {'probe': ('pt', 'pt_probe.tcl', 'API_PROBE_COMPLETE_NOT_TIMING_CLOSURE.txt'),
          'edit': ('pt', 'pt_edit.tcl', 'EDIT_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt'),
          'apply': ('dc', 'dc_apply.tcl', 'DC_REPLAY_COMPLETE_NOT_TIMING_CLOSURE.txt'),
          'reload': ('pt', 'pt_reload.tcl', 'RELOAD_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE.txt')}
SDC_SHA = 'c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def verify(path, digest, external=False):
    path = Path(path)
    require(path.is_file() and (external or not path.is_symlink()), 'missing/unsafe file: ' + str(path))
    require(sha(path) == digest, 'SHA256 mismatch: ' + str(path))
    return dict(path=str(path), sha256=digest, bytes=path.stat().st_size)


def tcl(value):
    value = str(value)
    require(not any(c in value for c in '{}\\\r\n'), 'unsafe Tcl literal: ' + repr(value))
    return '{' + value + '}'


def bind_outputs(receipt, base, names):
    result = []
    for name in names:
        item = receipt.get('outputs', {}).get(name)
        require(item and item.get('sha256'), 'unbound native output: ' + name)
        result.append(verify(base / name, item['sha256']))
        require(result[-1]['bytes'] == item['bytes'], 'native output size mismatch: ' + name)
    return result


def baseline(root):
    require(root.is_dir(), 'missing baseline directory')
    files = json.loads((root / 'package-files.json').read_text())
    bindings = []
    for name, digest in files.items():
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts, 'unsafe baseline manifest path')
        bindings.append(verify(root / p, digest))
    m = json.loads((root / 'manifest.json').read_text())
    require(m.get('top') == TOP and m.get('expected_internal_macros') == 33 and
            m.get('expected_geometry', {}).get('total_macros') == 353 and
            'XU_MATRIX_DMA_SYSBUS32' in m.get('defines', []) and 'XU_MATRIX_X_SRAM' in m.get('defines', []) and
            m.get('production_test_loader') is False, 'not selected353 production32 candidate')
    r = json.loads((root / 'execution.json').read_text())
    require(r.get('schema') == 'sysbus32-same-source-dc-execution-v1' and
            r.get('status') == 'SYNTHESIS_COMPLETE_NOT_QUALIFIED' and r.get('returncode') == 0 and
            r.get('source_drift') == [] and r.get('native_tool_errors') == [] and
            r.get('completion_marker') is True and (root/'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt').is_file(), 'baseline DC not completed cleanly')
    require(r.get('manifest_sha256') == sha(root / 'package-files.json'), 'baseline DC package mismatch')
    bindings.append(verify(root / 'execution.json', sha(root / 'execution.json')))
    bindings.extend(bind_outputs(r, root, ['mapped.v', 'mapped.ddc', 'mapped.sdc', 'libraries.tcl']))
    verify(root / 'source/contracts/reference-full-soc.sdc', SDC_SHA)
    chain = json.loads((root / 'toolchain.json').read_text())
    require(r.get('libraries') == chain['libraries'], 'baseline libraries differ from native DC')
    return bindings, r, chain


def previous(root, stage, package_hash, baseline_hash):
    receipt = root / 'execution.json'
    r = json.loads(receipt.read_text())
    require(r.get('schema') == 'compliant32-bounded-eco-stage-v1' and r.get('stage') == stage and
            r.get('status') == 'NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' and
            r.get('returncode') == 0 and r.get('completion_marker') is True and
            r.get('source_drift') == [] and r.get('native_tool_errors') == [], 'prior stage incomplete or failed')
    require(r.get('package_sha256') == package_hash and r.get('baseline_execution_sha256') == baseline_hash,
            'prior stage has different package/baseline identity')
    files = ['changes.dctcl', 'original-clock-association.tsv'] if stage == 'edit' else ['mapped.v', 'mapped.ddc', 'original-clock-association.tsv'] if stage == 'apply' else ['changes.dctcl', 'buffer-functions.tsv']
    bindings = bind_outputs(r, root, files)
    bindings.append(verify(receipt, sha(receipt)))
    return r, bindings


def heavy_jobs():
    names = {'simv','vcs','vcs1','dc_shell','snps_shell','common_shell_ex','pt_shell','icc2_shell','fm_shell','lc_shell','verilator_bin'}
    jobs = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            if path.stat().st_uid != os.getuid():
                continue
            comm = (path / 'comm').read_text().strip()
            exe = Path(os.readlink(path / 'exe')).name
            if comm in names or exe in names:
                jobs.append(dict(pid=int(path.name), comm=comm, exe=exe))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return sorted(jobs, key=lambda row: row['pid'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', choices=STAGES, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--prior', type=Path)
    p.add_argument('--mode', choices=['bias','gating','bias-gating'], default='bias-gating')
    p.add_argument('--run', action='store_true')
    p.add_argument('--allow-coordinated-busy-jobs', action='store_true')
    p.add_argument('--coordination-note')
    p.add_argument('--timeout-seconds', type=int, default=1200)
    p.add_argument('--max-buffers', type=int, default=248)
    p.add_argument('--max-per-pin', type=int, default=8)
    p.add_argument('--max-added-area', type=float, default=1000.0, help='raw characterized library area, not mm2')
    a = p.parse_args()
    require(0 < a.timeout_seconds <= 3600 and 0 < a.max_buffers <= 512 and 0 < a.max_per_pin <= 16 and
            0 < a.max_added_area <= 10000, 'bounded experiment limits exceeded')
    package = Path(__file__).resolve().parent
    seal = package / 'package-files.json'
    require(seal.is_file(), 'first create a sealed package with prepare.py')
    entries = json.loads(seal.read_text())
    bindings = []
    for name, digest in entries.items():
        q = Path(name)
        require(not q.is_absolute() and '..' not in q.parts, 'unsafe ECO manifest path')
        bindings.append(verify(package / q, digest))
    require('run_stage.py' in entries, 'runner not sealed')
    base = a.baseline.resolve()
    base_bindings, base_receipt, chain = baseline(base)
    bindings += base_bindings
    baseline_hash = sha(base / 'execution.json')
    prior = None
    if a.stage != 'probe':
        require(a.prior is not None, 'prior native stage is mandatory')
        expected = {'edit':'probe','apply':'edit','reload':'apply'}[a.stage]
        prior_root = a.prior.resolve()
        prior, more = previous(prior_root, expected, sha(seal), baseline_hash)
        bindings += more
    if a.stage == 'edit':
        pt = base / 'pt/execution.json'
        require(pt.is_file(), 'native baseline PT collection required before editing')
        rr = json.loads(pt.read_text())
        require(rr.get('status') == 'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED' and rr.get('returncode') == 0 and
                rr.get('source_drift') == [] and rr.get('native_tool_errors') == [] and rr.get('completion_marker') is True and
                rr.get('source_dc', {}).get('execution_sha256') == baseline_hash, 'baseline PT collection is not complete cleanly')
        bindings.append(verify(pt, sha(pt)))
        bindings += bind_outputs(rr, pt.parent, ['reports/coverage.rpt', 'reports/setup.rpt', 'reports/hold.rpt',
                     'reports/all_violators.rpt', 'reports/clock_gating_hold.rpt', 'reports/removal.rpt'])
    record = dict(schema='compliant32-bounded-eco-stage-v1', stage=a.stage, mode=a.mode,
                  status='SEALED_INPUTS_REVIEWED_NOT_EXECUTED', package_sha256=sha(seal),
                  baseline_execution_sha256=baseline_hash, top=TOP, max_cores=2,
                  baseline_mapped_sha256=sha(base/'mapped.v'), run_requested=a.run,
                  qualification='NOT_QUALIFIED', timing_verdict='NOT_TIMING_CLOSURE',
                  prior_execution_sha256=sha(a.prior.resolve()/'execution.json') if a.prior else None)
    if not a.run:
        print(json.dumps(record, sort_keys=True)); return 0
    jobs = heavy_jobs()
    if jobs or a.allow_coordinated_busy_jobs:
        require(a.allow_coordinated_busy_jobs and a.coordination_note and len(a.coordination_note.strip()) >= 16,
                'explicit coordination note required while other jobs exist')
    toolrole, script, marker = STAGES[a.stage]
    tool = chain[toolrole]
    tool_identity = verify(tool['path'], tool['sha256'], external=True)
    tool_identity.update(is_symlink=Path(tool['path']).is_symlink(), resolved_path=str(Path(tool['path']).resolve()))
    libraries = [verify(x['path'], x['sha256'], external=True) for x in chain['libraries']]
    require([x['role'] for x in chain['libraries']] == ['standard_cell','sram'], 'library role order mismatch')
    out = a.out.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    mapped = prior_root/'mapped.v' if a.stage == 'reload' else base/'mapped.v'
    config = [
        'set ::eco_baseline '+tcl(base),
        'set ::eco_mapped '+tcl(mapped),
        'set ::eco_ddc '+tcl(base/'mapped.ddc'),
        'set ::eco_mode '+tcl('probe' if a.stage=='probe' else a.mode),
        'set ::eco_buffer_reference {BUFV2_12TR40}',
        'set ::eco_max_buffers '+str(a.max_buffers),
        'set ::eco_max_per_pin '+str(a.max_per_pin),
        'set ::eco_max_added_area '+repr(a.max_added_area),
        'set ::eco_hold_margin 0.03', 'set ::eco_setup_margin 0.03',
        'set ::eco_link_libraries [list * '+' '.join(tcl(x['path']) for x in chain['libraries'])+']',
        'set ::eco_library_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256']) for x in chain['libraries'])+']',
        'set ::eco_bindings [list '+' '.join(tcl(x['path'])+' '+tcl(x['sha256']) for x in bindings)+']']
    if a.stage == 'reload':
        config += ['set ::eco_reference_clocks '+tcl(prior_root/'original-clock-association.tsv')]
    if a.stage == 'apply':
        shutil.copyfile(prior_root/'original-clock-association.tsv', out/'original-clock-association.tsv')
        config += ['set ::eco_changes '+tcl(prior_root/'changes.dctcl'),
                   'set ::eco_changes_sha '+tcl(sha(prior_root/'changes.dctcl'))]
    configuration = out/'config.tcl'
    configuration.write_text('\n'.join(config)+'\n')
    env = os.environ.copy()
    env.update(XU_ECO_PACKAGE=str(package), XU_ECO_CONFIG=str(configuration))
    if toolrole == 'pt':
        lc=chain['library_compiler']
        verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'],external=True)
        env['SYNOPSYS_LC_ROOT']=lc['root']
        # This PT version exposes pin directions but not lib_pin.function.
        # Query the identical DB in native DC first; no compile or edits.
        dc_identity=verify(chain['dc']['path'],chain['dc']['sha256'],external=True)
        proof_root=out/'native-library-proof'; proof_root.mkdir(mode=0o700)
        proof_command=[chain['dc']['path'],'-f',str(package/'dc_library_proof.tcl')]
        proof_record=dict(tool=dc_identity,libraries=chain['libraries'],command=proof_command,
                          max_cores=2,config_sha256=sha(configuration),started_epoch=time.time())
        record.update(status='RUNNING_NATIVE_DC_FUNCTION_QUERY',native_dc_function=proof_record)
        dump(out/'execution.json',record)
        proof_timeout=False
        with (proof_root/'native.log').open('w') as log:
            proc=subprocess.Popen(proof_command,cwd=proof_root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            proof_record['pid']=proc.pid; dump(out/'execution.json',record)
            try: proof_code=proc.wait(timeout=min(a.timeout_seconds,300))
            except subprocess.TimeoutExpired:
                proof_timeout=True; os.killpg(proc.pid,signal.SIGTERM)
                try: proof_code=proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid,signal.SIGKILL); proof_code=proc.wait()
        proof_errors=re.findall(r'^(?:Error:|Fatal:).*$',(proof_root/'native.log').read_text(errors='replace'),re.M)
        proof_files={q.relative_to(proof_root).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)
                     for q in sorted(proof_root.rglob('*')) if q.is_file()}
        proof_complete=(proof_root/'DC_LIBRARY_FUNCTION_PROOF_COMPLETE.txt').is_file()
        proof_drift=[x['path']for x in bindings+libraries+[dc_identity]
                     if not Path(x['path']).is_file()or sha(x['path'])!=x['sha256']]
        proof_record.update(returncode=proof_code,finished_epoch=time.time(),tool_timed_out=proof_timeout,
                            completion_marker=proof_complete,native_tool_errors=proof_errors,
                            source_drift=proof_drift,outputs=proof_files)
        proof_ok=proof_code==0 and proof_complete and not proof_timeout and not proof_errors and not proof_drift and 'dc-library-proof.tsv' in proof_files
        if not proof_ok:
            record.update(status='NATIVE_STAGE_FAILED',returncode=proof_code,completion_marker=False,
                          native_tool_errors=proof_errors,source_drift=proof_drift,
                          failure_stage='native_dc_library_function_query',finished_epoch=time.time())
            dump(out/'execution.json',record)
            print(json.dumps(dict(stage=a.stage,status=record['status'],failure_stage=record['failure_stage']),sort_keys=True))
            return 1
        function_file=proof_root/'dc-library-proof.tsv'
        bindings.append(verify(function_file,sha(function_file)))
        configuration.write_text(configuration.read_text()+
            'set ::eco_dc_function_file '+tcl(function_file)+'\n'+
            'set ::eco_dc_function_sha '+tcl(sha(function_file))+'\n')
    if toolrole == 'pt':
        lc=chain['library_compiler']
        verify(Path(lc['root'])/'bin/lc_shell',lc['launcher_sha256'],external=True)
        env['SYNOPSYS_LC_ROOT']=lc['root']
    command=[tool['path'],'-f',str(package/script)]
    record.update(status='RUNNING', started_epoch=time.time(), command=command, tool=tool_identity,
                  libraries=chain['libraries'], config_sha256=sha(configuration), inputs=bindings,
                  observed_jobs=jobs, coordination_note=a.coordination_note,
                  preexisting_jobs_policy='OBSERVE_ONLY_NEVER_STOP_OR_MODIFY', timeout_seconds=a.timeout_seconds)
    receipt=out/'execution.json'; dump(receipt,record)
    timed_out=False
    with (out/'native.log').open('w') as log:
        process=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        record['pid']=process.pid; dump(receipt,record)
        try:
            code=process.wait(timeout=a.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out=True; os.killpg(process.pid,signal.SIGTERM)
            try: code=process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL); code=process.wait()
    drift=[x['path'] for x in bindings if not Path(x['path']).is_file() or sha(x['path'])!=x['sha256']]
    if sha(configuration)!=record['config_sha256']: drift.append(str(configuration))
    for entry in libraries+[tool_identity]:
        if not Path(entry['path']).is_file() or sha(entry['path'])!=entry['sha256']:
            drift.append(entry['path'])
    errors=re.findall(r'^(?:Error:|Fatal:).*$',(out/'native.log').read_text(errors='replace'),re.M)
    outputs={q.relative_to(out).as_posix():dict(sha256=sha(q),bytes=q.stat().st_size)
             for q in sorted(out.rglob('*')) if q.is_file() and q.name!='execution.json'}
    required=['changes.dctcl','changes.ptsh','changes.text','cell-delta.tsv','net-delta.tsv','buffer-functions.tsv','leaf-pin-directions.tsv'] if a.stage in ['probe','edit'] else ['mapped.v','mapped.ddc','area-upper-bound.tsv'] if a.stage=='apply' else ['persisted-coverage.rpt','persisted-all_violators.rpt','persisted-setup.rpt','persisted-hold.rpt','persisted-removal.rpt','persisted-gating_hold.rpt','persisted-min_pulse_width.rpt']
    missing=[x for x in required if x not in outputs]
    complete=(out/marker).is_file()
    ok=code==0 and complete and not drift and not errors and not missing and not timed_out
    record.update(status='NATIVE_COLLECTION_COMPLETE_NOT_TIMING_CLOSURE' if ok else 'NATIVE_STAGE_FAILED',
                  returncode=code,finished_epoch=time.time(),completion_marker=complete,source_drift=drift,
                  native_tool_errors=errors,missing_outputs=missing,tool_timed_out=timed_out,outputs=outputs)
    dump(receipt,record)
    if ok and a.stage in ['probe','edit','reload']:
        proof=dict(schema='xu-native-buffer-function-proof-v1',
                   native_execution=dict(path='execution.json',sha256=sha(receipt)),
                   report=dict(path='buffer-functions.tsv',sha256=sha(out/'buffer-functions.tsv')),
                   direction_report=dict(path='leaf-pin-directions.tsv',sha256=sha(out/'leaf-pin-directions.tsv')))
        dump(out/'function-proof.json',proof)
    print(json.dumps({k:record[k] for k in ['stage','status','returncode','completion_marker','source_drift','native_tool_errors','missing_outputs']},sort_keys=True))
    return 0 if ok else 1


if __name__=='__main__':
    try: sys.exit(main())
    except (OSError,ValueError,KeyError) as error:
        print('FAIL: '+str(error),file=sys.stderr); sys.exit(1)
