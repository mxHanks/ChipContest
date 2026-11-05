#!/usr/bin/env python3
"""Read-only independent check of returned149 original bytes and receipts."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'server149-original.tar.xz'
assert ARCHIVE.stat().st_size == 96952
assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == '60c25e5ddcd243a924adf00278aacd47c546ed9aa33693aed9794642094b84e4'
with tarfile.open(str(ARCHIVE), 'r:xz') as t:
    members = t.getmembers()
    names = [m.name for m in members]
    assert len(names) == len(set(names))
    assert all(m.isfile() and not PurePosixPath(m.name).is_absolute() and '..' not in PurePosixPath(m.name).parts for m in members)
    data = {m.name: t.extractfile(m).read() for m in members}
manifest = json.loads(data['manifest.json'])
assert len(manifest) == 96 and sum(r['bytes'] for r in manifest) == 5719875
assert set(data) == {r['path'] for r in manifest} | {'manifest.json'}
for r in manifest:
    assert len(data[r['path']]) == r['bytes'] and hashlib.sha256(data[r['path']]).hexdigest() == r['sha256']
def load(name):
    return json.loads(data[name])
prefix = 'eight-candidate-freeze-queue-20261105-138/'
state = load(prefix + 'state.json')
assert state['status'] == 'INPUTS_AND_ADOPTIONS_COMPLETE_REMAINING_PHASES_PENDING_NOT_QUALIFIED'
assert state['qualification'] == 'NOT_QUALIFIED'
assert state['plan_sha256'] == hashlib.sha256(data[prefix + 'plan.json']).hexdigest()
counts = dict(baseline_h1_h2=369, s1_h2_only=320, s1_sram_bias=327, s2b=320, s2d=330, pe32=336, pe64=344, compact32_128=351)
assert set(state['candidates']) == set(counts)
summary = {}
for name, count in sorted(counts.items()):
    freeze = load(prefix + name + '/freeze.json')
    adopt = load(prefix + name + '/adopt-own-fm.json')
    row = state['candidates'][name]
    assert freeze['candidate'] == name and freeze['status'] == 'FROZEN_REVIEW_PENDING_NOT_QUALIFIED'
    assert freeze['errors'] == [] and len(freeze['before']) == count and freeze['before'] == freeze['after']
    assert freeze['qualification'] == adopt['qualification'] == 'NOT_QUALIFIED'
    assert freeze['source']['tracked_clean'] is True
    assert freeze['selected_mapped'] == adopt['selected_mapped']
    assert freeze['ordered_svf_inputs'] == adopt['ordered_svf_inputs']
    assert adopt['status'] == 'OWN_FM_ADOPTED_CONDITIONAL_REVIEW_PENDING'
    assert adopt['native_verification_succeeded_count'] == 1 and len(adopt['native_passing_counts']) == 1 and adopt['native_passing_counts'][0] > 0
    assert adopt['sram_internal'] == 'BLACK_BOX_NOT_PROVED'
    assert row['adopt_own_fm'] == adopt
    assert row['freeze']['receipt']['sha256'] == hashlib.sha256(data[prefix + name + '/freeze.json']).hexdigest()
    assert row['formal_activity12']['status'] == 'PENDING_IMPLEMENTATION'
    assert row['full_soc_power12']['status'] == row['qualification']['status'] == 'WAIT_DEPENDENCY'
    assert adopt['same_original_area_mapping'] is (name not in ['s2d', 'pe32'])
    summary[name] = dict(frozen_input_receipts=count, own_fm_points=adopt['native_passing_counts'][0], same_original_area_mapping=adopt['same_original_area_mapping'], qualification='NOT_QUALIFIED')
control = load('unified-experiment-control-20261105-150/state.json')
assert control['worker']['sha256'] == 'd7813ac3745ff1aa5b5efc92eef298a6577abef774259f9285aae605c466db2f'
assert control['controller_pid'] == 159584 and control['qualification'] == 'NOT_QUALIFIED'
assert set(control['jobs']) == {'s2e_power130', 'eight_freeze138', 's2e_timing134', 'baseline_rdc142'}
for name, row in control['jobs'].items():
    raw = data['unified-experiment-control-20261105-150/registrations/' + name + '.json']
    assert row['registration']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert json.loads(raw)['qualification'] == 'NOT_QUALIFIED'
assert control['jobs']['eight_freeze138']['status'] == 'COMPLETED_DIAGNOSTIC_NOT_QUALIFIED'
assert control['jobs']['s2e_power130']['status'] == 'RUNNING_ADOPTED'
assert control['jobs']['s2e_timing134']['status'] == control['jobs']['baseline_rdc142']['status'] == 'WAIT_DEPENDENCY'
live = load('live149-observation.json')['observations']
assert len(live) == 2 and all(r['alive_now'] is True for r in live)
assert live[0]['pid'] == 135097 and live[0]['current_task_id'] == 11 and live[0]['taskset_complete'] is False
assert live[1]['pid'] == 159584 and 'xu_experiments.py run' in live[1]['command']
power = load('s2e-full-soc-power12-20261105-130/execution.json')
assert power['status'] == 'RUNNING_REVIEW_PENDING' and power['current_task_id'] == 11 and len(power['tasks']) == 11
assert power['qualification'] == 'NOT_QUALIFIED'
res = control['resources']
assert res['license_capacity'] == 'UNKNOWN_NO_SPARE_SEATS_CLAIMED'
assert res['native_policy'] == 'EXCLUSIVE_SINGLE_EXISTING_JOB_OR_ONE_NEW_JOB'
assert res['cpu_count'] == 96 and res['disk_available_bytes'] == 1522007015424 and res['mem_available_bytes'] == 761591107584
for number, name in [(143, 'license-native-readonly-20261105-143'), (144, 'license-users-readonly-20261105-144')]:
    log = data[name + '/pt.log'].decode()
    assert 'Error:' not in log
print(json.dumps(dict(status='RETURNED149_BYTES_AND_SERVER_RECEIPTS_CHECKED_NOT_QUALIFIED', payload_files=96, payload_bytes=5719875, candidates=summary, controller_live_snapshot_pid=159584, s2e130_snapshot_task=11, license_spare_capacity='UNKNOWN', limitation='Frozen source bodies and native FM logs were rehashed on server; returned manifests are receipts, not local body rehashes.'), sort_keys=True, indent=2))
