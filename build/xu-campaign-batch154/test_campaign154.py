#!/usr/bin/env python3
"""Mixed complete/failed/missing report fixtures; starts no experiment."""
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import campaign154 as m

with tempfile.TemporaryDirectory(prefix='xu-report154-') as temp:
    root=Path(temp);m.BASE=root;m.CONTROL=root/'control';m.CONTROL.mkdir()
    m.write(m.CONTROL/'state.json',dict(jobs={'power146_s1_h2_only':dict(status='BLOCKED_DEPENDENCY_NOT_QUALIFIED')}))
    profile=m.PROFILES[0]
    activity=root/'eight-formal-activity12-20261105-145'/profile;activity.mkdir(parents=True)
    m.write(activity/'result.json',dict(status='COLLECTED_12_REVIEW_PENDING_NOT_QUALIFIED',taskset_complete=True,tasks=[
        dict(task_id=i,activity_window=dict(formal_elapsed_cycles=100+i,duration_ticks=1000000+i),boundary_log=dict(sha256='vcs'+str(i))) for i in range(12)]))
    power=root/'eight-full-soc-power12-20261105-146'/profile;power.mkdir(parents=True)
    m.write(power/'execution.json',dict(status='EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED'))
    m.write(power/'summary.json',dict(elapsed_cycles12=1266,sum_diagnostic_energy_j='0.002',time_weighted_mean_reported_power_w='0.035',
        selected_mapped=dict(path='own-map',sha256='own'),analysis_sdc=dict(sha256='sdc'),area=dict(accelerator=dict(area_mm2_diagnostic='0.30',diagnostic_within_limit=True)),
        layers=[dict(task_id=i,power_components=dict(total_power_w='0.035'),diagnostic_energy_j='0.0001',log_sha256='pt'+str(i)) for i in range(12)]))
    result=m.report(root/'report')
    assert result['status']=='COLLECTED_CAMPAIGN_DIAGNOSTICS_NOT_QUALIFIED' and all(r['qualification']=='NOT_QUALIFIED' for r in result['candidates'])
    assert result['candidates'][0]['elapsed_cycles12']==1266 and result['candidates'][0]['accelerator_area_mm2_diagnostic']=='0.30'
    assert result['candidates'][1]['power_status']=='BLOCKED_DEPENDENCY_NOT_QUALIFIED' and result['candidates'][1]['diagnostic_energy12_j'] is None
    with (root/'report/layer-comparison.csv').open() as source:rows=list(csv.DictReader(source))
    assert len(rows)==96 and rows[0]['vcs_log_sha256']=='vcs0' and rows[0]['pt_log_sha256']=='pt0'
    assert rows[12]['diagnostic_energy_j']==''
    for receipt in result['input_receipts']+[result['controller_state']]:
        raw=Path(receipt['snapshot']).read_bytes()
        assert len(raw)==receipt['bytes'] and hashlib.sha256(raw).hexdigest()==receipt['sha256']
    m.write(activity/'result.json',dict(status='NEXT_LIVE_CHECKPOINT'))
    captured=next(r for r in result['input_receipts'] if r['source_path']==str(activity/'result.json'))
    assert json.loads(Path(captured['snapshot']).read_text())['taskset_complete'] is True
    try:m.report(root/'report')
    except ValueError:pass
    else:raise AssertionError('existing report overwritten')
print('HOST154_MIXED_RESULTS_AND_LOG_HASH_REPORT_PASS_NO_EDA')
