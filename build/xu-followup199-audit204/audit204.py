#!/usr/bin/env python3
"""Audit actual199 registration bytes. Offline; does not launch server workers."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

import frozen171

SHA199 = '3c611c7363caa21f4bed62ec4f2b5001a1ac0962ffee56b3b57d04d80e6e89e5'
SHA198 = '745bb90101f26e968d75f4f1a77bba8cb0e789750d0856df8fe90a4458c01407'
D = '/storage2/2026contest/server4/s4_23usr/Desktop'
B = D + '/xu-score-optimization-20261102'
C = B + '/unified-experiment-control-20261105-150'
Q = 'unified-experiment-control-20261105-150'
IDS = ['s2e_coverage186', 's2c_common_preflight190', 's2c_common_full12_190', 'two_candidate_finalpack191']
DEPS = [
    [('s2c_readonly177', 'terminal'), ('s2e_final155_preflight166', 'success')],
    [('s2e_coverage186', 'terminal')],
    [('s2c_common_preflight190', 'success')],
    [('s2c_readonly177', 'terminal'), ('s2e_coverage186', 'terminal'), ('s2c_common_full12_190', 'terminal')],
]
ANCESTORS = {
    'scope163': ('d301a3287acdebf2d13bb85bf17e5702d6138c150600d0a0b6997a51d5945696', 8248),
    'registration182': ('07423f6b8be00a886fee38a5239b8ff020b98166b34f0c9ed9e33fb5100fed48', 8284),
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def identity(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def load(raw):
    return frozen171.unique_json(raw)


def record(raw, path):
    return dict(path=path, **identity(raw))


def same_process(recorded, observed):
    return recorded is not None and observed is not None and observed.get('process_state') != 'Z' and all(
        recorded.get(k) == observed.get(k) for k in ['pid', 'uid', 'start_ticks', 'argv'])


def read_runtime(archive):
    need(identity(archive.read_bytes()) == dict(bytes=158795, sha256=SHA198), 'runtime198 archive identity differs')
    payload = {}
    with tarfile.open(str(archive), 'r:gz') as t:
        for m in t:
            name = frozen171.safe_name(m.name)
            need(m.isfile() and not m.issym() and not m.islnk() and not m.sparse and
                 name not in payload and m.size <= 4000000, 'unsafe runtime member')
            raw = t.extractfile(m).read()
            need(len(raw) == m.size, 'truncated runtime member')
            payload[name] = raw
    manifest = load(payload.pop('manifest198.json'))
    rows = manifest['files']
    need(manifest['schema'] == 'xu-runtime198-transport-v1' and manifest['qualification'] == 'NOT_QUALIFIED', 'runtime manifest schema')
    need(len(rows) == len(payload) == 24 and len({r['name'] for r in rows}) == 24, 'runtime inventory differs')
    need({r['name']: dict(bytes=r['bytes'], sha256=r['sha256']) for r in rows} ==
         {n: identity(raw) for n, raw in payload.items()}, 'runtime manifest bytes differ')
    return payload, manifest


def audit(payload, runtime, runtime_manifest, workspace):
    manifest = load(payload['manifest.json'])
    declared = {r['path']: r for r in manifest['files']}
    need(len(declared) == 21 and manifest['payload_bytes'] == 2125299, 'actual199 inventory differs')
    need(declared == {n: record(raw, n) for n, raw in payload.items() if n != 'manifest.json'}, 'extracted payload differs')
    snapshot = load(payload['snapshot171.json'])
    need(snapshot['status'] == 'EXPORTED_READ_ONLY_SNAPSHOT_NOT_QUALIFIED' and
         snapshot['all_copies_are_observations_not_terminal_freezes'] is True and
         snapshot['qualification'] == 'NOT_QUALIFIED', 'live snapshot semantics differ')
    need(not snapshot['omitted_originals'] and not snapshot['rejected_sources'], 'omitted or rejected originals')
    captures = snapshot['captures']
    need(len(captures) == 20 and len({r['archive_path'] for r in captures}) == 20, 'snapshot capture inventory differs')
    for row in captures:
        name = row['archive_path']
        need(name in declared and row['metadata_unchanged_during_read'] is True and
             row['fd_before'] == row['fd_after'] == row['path_after'], 'source changed during capture')
        need(declared[name]['bytes'] == row['bytes_observed'] and
             declared[name]['sha256'] == row['observed_bytes_sha256'], 'capture digest differs')
    need({r['archive_path'] for r in captures} == set(declared) - {'snapshot171.json'}, 'snapshot does not cover payload')
    need(snapshot['exporter']['sha256'] == '9c72cfa8ef45b0b2cfba865af1914728077e63a4fb62c940ad7dacaa81300263', 'exporter identity differs')
    need(snapshot['started_epoch'] <= snapshot['finished_observation_epoch'] and
         snapshot['started_epoch'] == 1793871769.0010915, 'expected historical observation time differs')

    receipt = load(payload['two-candidate-followup-registration-20261105-198.json'])
    need(receipt['schema'] == 'xu-two-candidate-control198-receipt-v1' and
         receipt['status'] == 'REGISTERED_TWO_CANDIDATE_FOLLOWUP198_NOT_QUALIFIED' and
         receipt['qualification'] == 'NOT_QUALIFIED', 'actual registration receipt differs')
    need(receipt['workers_signalled'] == receipt['workers_restarted'] == receipt['experiments_directly_launched'] == 0,
         'registration performed direct work or signalled/restarted workers')
    before = receipt['frozen_before']
    need(len(before) == 48 and len({r['path'] for r in before}) == 48 and before == receipt['frozen_after'],
         '48 server frozen-input records changed or duplicate')
    bypath = {r['path']: r for r in before}
    for name, (sha, size) in ANCESTORS.items():
        r = receipt[name]
        need(r['sha256'] == sha and r['bytes'] == size and bypath.get(r['path']) == r, 'ancestor receipt identity differs: ' + name)
    guard_name = 'desktop/xu-two-candidate-control198/frozen-jobs198.json'
    register_name = 'desktop/xu-two-candidate-control198/register198.py'
    for key, name in [('guard', guard_name), ('register', register_name)]:
        need(receipt[key] == record(payload[name], D + '/' + name[len('desktop/'):]), 'actual guard/registration source differs')
        need(bypath.get(receipt[key]['path']) == receipt[key], 'guard absent from before/after records')

    install = load(payload['followup198-install.json'])
    need(install['status'] == 'INSTALLED_REVIEWED_RUNTIME_NOT_RUN_NOT_QUALIFIED' and
         install['schema'] == 'xu-runtime198-install-v1' and install['new_native_runs'] == 0,
         'runtime installer receipt differs')
    need(install['archive'] == dict(path=D+'/xu-followup-runtime198-745bb90101f2.tar.gz', bytes=158795, sha256=SHA198) and
         install['manifest'] == runtime_manifest, 'installed runtime manifest/archive differs')
    old_install = load(payload['followup192-install.json'])
    need(old_install['status'] == 'INSTALLED_REVIEWED_RUNTIME_NOT_RUN_NOT_QUALIFIED' and
         old_install['new_native_runs'] == 0 and old_install['archive']['sha256'] ==
         'a08459ff2b43c94cb1dc8f06ede235b0e36e23ef304fe2d04e2da71503ce1ea2', 'old192 installation history differs')

    current_sources = []
    for name, raw in sorted(runtime.items()):
        folder, tail = name.split('/', 1)
        local_folder = 'xu-s2c-common-power190' if folder == 'xu-s2c-common-power198' else folder
        relative = 'build/' + local_folder + '/' + tail
        local = workspace / relative
        need(local.is_file() and not local.is_symlink() and local.read_bytes() == raw, 'current runtime source differs: ' + relative)
        current_sources.append(dict(path=relative, **identity(raw)))
        if D+'/'+name in bypath:
            need(bypath[D+'/'+name] == record(raw, D+'/'+name), 'runtime versus registered input differs')
    for name in [guard_name, register_name]:
        need(payload[name] == runtime[name[len('desktop/'):]], 'returned source versus runtime differs')
    local_manifest = workspace / 'build/xu-two-candidate-control198/manifest198.json'
    need(load(local_manifest.read_bytes()) == runtime_manifest, 'current runtime manifest differs')
    installer = workspace / 'build/xu-two-candidate-control198/install198.py'
    transport = load((workspace / 'build/xu-two-candidate-control198/transport198.json').read_bytes())
    expected_installer = dict(bytes=2093, sha256='915cec3e21bea761789518d6548b377659922645da9e93b971889cfe0bcee81b')
    need(identity(installer.read_bytes()) == expected_installer ==
         {k: transport['installer'][k] for k in ['bytes', 'sha256']}, 'installer source identity differs')

    guard = load(payload[guard_name])
    need(guard['schema'] == 'xu-two-candidate-control198-v1' and len(guard['jobs']) == 4, 'four-job guard differs')
    queue = load(payload[Q+'/state.json'])
    need(queue['worker'] == dict(path=D+'/xu-campaign-batch154/control153/xu_experiments.py', bytes=19039,
        sha256='877a1624d45bdae7dd5095809f69e3e9c95eafafac17f354fe52f9781c9ef025'), 'controller153 frozen runtime differs')
    need(bypath.get(queue['worker']['path']) == queue['worker'], 'controller runtime absent from frozen records')
    need(same_process(receipt['controller_identity'], queue['controller_identity']) and
         queue['controller_pid'] == 27671 and queue['controller_identity']['uid'] == 14023 and
         queue['controller_identity']['start_ticks'] == 118631998, 'recorded controller process identity differs')
    observations = {r['name']: r for r in snapshot['live_process_observations']}
    need(same_process(receipt['controller_identity'], observations['controller153']['actual']) and
         same_process(receipt['controller_identity'], observations['controller153']['recorded_identity']),
         'controller not the same live process at historical observation')
    regs = receipt['registrations']
    need(len(regs) == 4, 'four actual registrations required')
    rows = []
    for index, job_id in enumerate(IDS):
        name = job_id+'.json'
        raw = payload[Q+'/registrations/'+name]
        need(guard['jobs'][index] == dict(name=name, **identity(raw)), 'job guard differs')
        need(runtime['xu-two-candidate-control198/'+name] == raw and
             regs[index] == record(raw, C+'/registrations/'+name), 'actual registered job bytes differ')
        job = load(raw)
        need(job['id'] == job_id and job['kind'] == 'launch' and job['launch_mode'] == 'direct' and
             job['native'] is True and job['qualification'] == 'NOT_QUALIFIED', 'job launch identity differs')
        need(job['dependencies'] == [dict(id=i, policy=p) for i, p in DEPS[index]], 'dependency chain differs')
        need(job['argv'][:3] == ['/bin/python3', '-B', '-u'] and
             job['argv'][-2:] == ['--out', job['output_root']] and
             job['process_contains'] == job['output_root'] and PurePosixPath(job['output_root']).parent.as_posix() == B and
             PurePosixPath(job['result_state']).parent.as_posix() == job['output_root'], 'foreground unique output semantics differ')
        for r in job['frozen_inputs']:
            actual = bypath.get(r['path'])
            need(actual is not None and set(r) <= {'path', 'bytes', 'sha256'} and
                 all(actual.get(k) == v for k, v in r.items()), 'job input absent from before/after records')
        q = queue['jobs'][job_id]
        need(q['registration'] == regs[index] and q['status'] == 'WAIT_DEPENDENCY' and not q['live_processes'],
             'historical queued/waiting status differs')
        need(observations[job_id]['actual'] is None and observations[job_id]['queue_status'] == 'WAIT_DEPENDENCY',
             'historical waiting job had live worker')
        rows.append(dict(id=job_id, status_at_174249_cst=q['status'], dependencies=job['dependencies'],
                         output_root=job['output_root'], registration_sha256=identity(raw)['sha256']))
    need(len({r['output_root'] for r in rows}) == 4, 'unique outputs required')
    own177 = payload[Q+'/registrations/s2c_readonly177.json']
    need(identity(own177) == dict(bytes=4326, sha256='a86e46ab86453c48e8dbf57df4ef40c3401e824448c4bb8ec0510457869bba8d'), 'existing177 registration changed')
    r166 = load(payload['s2e-final155-power12-20261105-166/result.json'])
    q166 = queue['jobs']['s2e_final155_power12_166']
    need(r166['status'] == 'RUNNING166_NOT_QUALIFIED' and r166['phase'] == 'power' and r166['current_task_id'] == 11 and
         q166['status'] == 'RUNNING' and same_process(q166['worker_identity'], observations['s2e_final155_power12_166']['actual']),
         'historical166 running observation differs')
    need(r166.get('total_energy_j') is None, 'historical partial measurement cannot provide final energy')
    return dict(schema='xu-followup199-independent-audit204-v1',
        status='ACTUAL_FOUR_JOB_REGISTRATION_VERIFIED_HISTORICAL_NOT_QUALIFIED', qualification='NOT_QUALIFIED',
        archive199=dict(bytes=85220, sha256=SHA199), payload_files=21, payload_bytes=2125299,
        metadata_stable_source_copies=20, missing_optional_at_observation=len(snapshot['missing_at_observation']),
        omitted_originals=0, rejected_sources=0, observation_started_cst='2026-11-05T17:42:49.001091+08:00',
        observation_finished_epoch=snapshot['finished_observation_epoch'],
        receipt_epoch=receipt['epoch'], controller_live_at_observation=receipt['controller_identity'],
        registration_frozen_input_records_unchanged=48, workers_signalled=0, workers_restarted=0,
        experiments_directly_launched=0, runtime198=dict(bytes=158795, sha256=SHA198, payload_files=24),
        installer_current_source=dict(path='build/xu-two-candidate-control198/install198.py', **identity(installer.read_bytes())),
        current_runtime_sources=current_sources, registrations=rows,
        ancestor_identities=ANCESTORS,
        evidence_limits=[
            '199 is a historical live snapshot at 17:42:49 CST, not a current status query or terminal qualification.',
            'All four new jobs were WAIT_DEPENDENCY then;166 was power task11 RUNNING, with final energy unavailable.',
            '48 server-side before/after hashes are receipt evidence; unreturned remote libraries/netlist/ancestor bodies were not rehashed locally.',
            'Local byte checks cover the full199 archive and all24 runtime198 bodies against current source; installer execution history is a server receipt.',
            'Controller153 observed PID/uid/start_ticks/argv match only proves the same live process at snapshot time.',
            'No remote operations, retries, signals, new native launches, model edits, RTL edits or numerical scoring performed by this audit.',
        ])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and not a.out.is_symlink(), 'fresh output directory required')
    frozen171.inspect(a.archive, SHA199)
    with tarfile.open(str(a.archive), 'r:xz') as t:
        payload = {m.name: t.extractfile(m).read() for m in t}
    runtime, manifest = read_runtime(a.workspace/'build/xu-two-candidate-control198/runtime198.tar.gz')
    result = audit(payload, runtime, manifest, a.workspace)
    frozen171.inspect(a.archive, SHA199)
    a.out.mkdir(parents=True)
    (a.out/'audit204.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    text = io.StringIO()
    writer = csv.writer(text, lineterminator='\n')
    writer.writerow(['id', 'status_at_2026-11-05_17:42:49_CST', 'dependencies', 'registration_sha256', 'output_root'])
    for r in result['registrations']:
        writer.writerow([r['id'], r['status_at_174249_cst'], json.dumps(r['dependencies'], sort_keys=True), r['registration_sha256'], r['output_root']])
    (a.out/'registrations204.csv').write_text(text.getvalue())
    print(json.dumps(dict(status=result['status'], payload_files=21, registered_jobs=4, remote_actions=0), sort_keys=True))


if __name__ == '__main__':
    main()
