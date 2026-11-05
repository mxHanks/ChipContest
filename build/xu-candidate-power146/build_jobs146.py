#!/usr/bin/env python3
"""Generate eight exact power146 direct registrations; never run/register a job."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common146 import identity, need, read, write


def bundle_records(local, remote, manifest_name):
    manifest = read(local/manifest_name)
    records = []
    for row in manifest['files']:
        relative = Path(row['path'])
        need(not relative.is_absolute() and '..' not in relative.parts, 'unsafe bundle member')
        actual = identity(local/relative)
        need(actual['sha256'] == row['sha256'] and actual['bytes'] == row['bytes'], 'bundle payload differs: '+str(relative))
        records.append(dict(path=str(remote/relative), sha256=actual['sha256'], bytes=actual['bytes']))
    actual = identity(local/manifest_name)
    records.append(dict(path=str(remote/manifest_name), sha256=actual['sha256'], bytes=actual['bytes']))
    return records


def build(args):
    for path in (args.bundle_root, args.activity_tools, args.output_root, args.activity_root, args.freeze_root):
        need(path.is_absolute(), 'absolute deployed/output paths required')
    need(not args.jobs_out.exists() and not args.jobs_out.is_symlink(), 'fresh jobs directory required')
    need(args.python and args.timeout > 0 and args.inventory_timeout > 0, 'valid Python and positive native timeouts required')
    inventory, queue = read(HERE/'inventory137.snapshot.json'), read(HERE/'queue138.snapshot.json')
    frozen = bundle_records(HERE, args.bundle_root, 'bundle-manifest146.json')
    frozen += bundle_records(args.local_activity_tools, args.activity_tools, 'bundle-manifest145.json')
    profiles = [row['id'] for row in inventory['candidates']]
    need(len(profiles) == 8 and len(set(profiles)) == 8, 'exact eight independent inventory137 profiles required')
    args.jobs_out.mkdir(parents=True)
    plan = []
    for selected in inventory['candidates']:
        cid = selected['id']; jobid = 'power146_'+cid
        local = args.receipt_snapshot/cid; remote = args.freeze_root/cid
        frozen_receipt, adopted = read(local/'freeze.json'), read(local/'adopt-own-fm.json')
        planned = next(c for c in queue['candidates'] if c['id'] == cid)
        need(frozen_receipt['candidate'] == cid and frozen_receipt['status'] == 'FROZEN_REVIEW_PENDING_NOT_QUALIFIED' and
             frozen_receipt['before'] == frozen_receipt['after'] and not frozen_receipt.get('errors'), 'actual138 complete freeze required')
        need(adopted['status'] == 'OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING' and
             frozen_receipt['selected_mapped'] == adopted['selected_mapped'] == planned['selected_mapped'] == selected['formal']['mapped'] and
             frozen_receipt['ordered_svf_inputs'] == adopted['ordered_svf_inputs'] == planned['ordered_svf_inputs'], 'actual138 own map/SVF chain differs')
        need(len(frozen_receipt['after']) == len(planned['freeze_inputs']) and
             all(a['path'] == b['path'] and a['sha256'] == b['sha256'] for a, b in zip(frozen_receipt['after'], planned['freeze_inputs'])),
             'actual138 complete ordered frozen input set differs')
        own = list(frozen)
        for name in ('freeze.json', 'adopt-own-fm.json'):
            row = identity(local/name)
            own.append(dict(path=str(remote/name), sha256=row['sha256'], bytes=row['bytes']))
        out, activity = args.output_root/cid, args.activity_root/cid
        argv = [args.python, '-B', str(args.bundle_root/'power146.py'), 'campaign', '--profile', cid,
            '--freeze-receipt', str(remote/'freeze.json'), '--adoption-receipt', str(remote/'adopt-own-fm.json'),
            '--source-root', selected['source']['server_root'], '--activity-root', str(activity),
            '--activity-tools', str(args.activity_tools), '--out', str(out), '--pt', args.pt, '--lc-root', args.lc_root,
            '--timeout', str(args.timeout), '--inventory-timeout', str(args.inventory_timeout)]
        job = dict(schema='xu-experiment-control150-job-v1', qualification='NOT_QUALIFIED', id=jobid, kind='launch', native=True,
            launch_mode='direct', dependencies=[dict(id='eight_freeze138', policy='success'), dict(id='activity145_'+cid, policy='success')],
            process_contains=str(out), result_state=str(out/'execution.json'), output_root=str(out),
            success_statuses=['EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'], failure_statuses=['FAIL_DIAGNOSTIC_NOT_QUALIFIED'],
            argv=argv, frozen_inputs=own)
        write(args.jobs_out/(jobid+'.json'), job)
        plan.append(dict(profile=cid, job_id=jobid, depends_on='activity145_'+cid, output_root=str(out),
            selected_mapped=selected['formal']['mapped'], analysis_sdc=selected['ppa']['analysis_sdc'],
            argv=argv, resume_argv=[args.python, '-B', str(args.bundle_root/'power146.py'), 'resume', '--out', str(out)],
            audit_argv=[args.python, '-B', str(args.bundle_root/'power146.py'), 'audit', '--out', str(out), '--audit-out', str(out)+'-audit'],
            qualification='NOT_QUALIFIED'))
    result = dict(schema='xu-power-plan146-v1', status='GENERATED_NOT_REGISTERED_NOT_QUALIFIED', candidate_count=8,
        qualification='NOT_QUALIFIED', native_policy='CONTROLLER150_SINGLE_NATIVE_SLOT_NO_SPARE_LICENSE_CLAIM', jobs=plan)
    write(args.jobs_out/'power-plan146.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle-root', 'activity-tools', 'output-root', 'activity-root', 'freeze-root', 'receipt-snapshot', 'jobs-out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--local-activity-tools', type=Path, default=HERE.parent/'xu-profile-activity145')
    p.add_argument('--python', default='/bin/python3')
    p.add_argument('--pt', default='/eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell')
    p.add_argument('--lc-root', default='/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5')
    p.add_argument('--timeout', type=int, default=21600)
    p.add_argument('--inventory-timeout', type=int, default=900)
    args = p.parse_args(); result = build(args)
    print('GENERATED_%d_POWER_JOBS_NOT_REGISTERED %s' % (result['candidate_count'], args.jobs_out))


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('FAIL146: '+type(exc).__name__+': '+str(exc), file=sys.stderr); sys.exit(1)
