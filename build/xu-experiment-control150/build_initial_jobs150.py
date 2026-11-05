#!/usr/bin/env python3
"""Generate original-host registrations; no remote operations or task launch."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
B='/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102'
D='/storage2/2026contest/server4/s4_23usr/Desktop'
out=HERE/'jobs'
out.mkdir(exist_ok=True)
common=dict(schema='xu-experiment-control150-job-v1',qualification='NOT_QUALIFIED',native=True)
jobs=[
 dict(common,id='s2e_power130',kind='adopt',dependencies=[],process_contains='xu_s2e_full_soc_power130.py',result_state=B+'/s2e-full-soc-power12-20261105-130/execution.json',success_statuses=['EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING'],failure_statuses=['FAIL']),
 dict(common,id='eight_freeze138',kind='adopt',native=False,dependencies=[],process_contains='batch138.py',result_state=B+'/eight-candidate-freeze-queue-20261105-138/state.json',success_statuses=['INPUTS_AND_ADOPTIONS_COMPLETE_REMAINING_PHASES_PENDING_NOT_QUALIFIED'],failure_statuses=[]),
 dict(common,id='s2e_timing134',kind='launch',dependencies=[dict(id='s2e_power130',policy='terminal')],process_contains='xu_s2e_timing134.py',result_state=B+'/s2e-own-timing-repair-20261105-134/state.json',success_statuses=['EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED'],failure_statuses=['FAILED_NOT_QUALIFIED'],argv=['/bin/python3','-B',D+'/xu-s2e-timing134/launch_timing134.py'],output_root=B+'/s2e-own-timing-repair-20261105-134',launch_receipt=B+'/s2e-own-timing-repair-launch-20261105-134/state.json',pid_keys=['pid'],frozen_inputs=[dict(path=D+'/xu-s2e-timing134/'+n,sha256=h) for n,h in [('xu_s2e_timing134.py','dcf5341fb9c09cb7db545fb2a208a1c204e2a14309c4741a4c5cd63c0f8364ef'),('reset134.tcl','8e50f0559a0f443cc4359b28cf55d7e0e54e6778ca8490bce4aac91b157ac33c'),('launch_timing134.py','a8ada3d3814f82023c45b7ffdbcbbfdbd7518567b34672a74ef578bc65f5eff2')]]),
 dict(common,id='baseline_rdc142',kind='launch',dependencies=[dict(id='s2e_timing134',policy='terminal')],process_contains='xu_rdc_next142.py',result_state=B+'/full-soc-rdc-next-20261105-142/state.json',success_statuses=['EXECUTED_SAME116_READ_ONLY_RECOVERY_VISIBILITY_NOT_QUALIFIED'],failure_statuses=['FAILED_NOT_QUALIFIED'],argv=['/bin/python3','-B',D+'/launch_rdc_next142.py'],output_root=B+'/full-soc-rdc-next-20261105-142',launch_receipt=B+'/full-soc-rdc-next-launch-20261105-142/state.json',pid_keys=['worker_pid'],frozen_inputs=[dict(path=D+'/xu_rdc_next142.py',sha256='b004c17af3370f5a872c91cd71dfd93fbefeb772e17139e51ac35a642c39a4e7'),dict(path=D+'/launch_rdc_next142.py',sha256='388874824312dfbe201e994f02ca7dd58277ff73bfb015b73908a6a2ed44590c')]),
]
for job in jobs:
    (out/(job['id']+'.json')).write_text(json.dumps(job,sort_keys=True,indent=2)+'\n')
print('INITIAL150_JOBS',len(jobs))
