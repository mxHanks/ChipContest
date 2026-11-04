from pathlib import Path
import importlib.util,json,copy,hashlib,re
B=Path(__file__).resolve().parent;R=Path('/home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-score-resume-20261103/progress114/mapped-task00-public-diagnostic-20261104-111')
spec=importlib.util.spec_from_file_location('audit115',B/'xu_audit_mapped111_failure115.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
O=B/'local-audit115-v1';O.mkdir(exist_ok=False)
state=json.loads((R/'state.json').read_text());tb=(R/'tb_xu_mapped_task00111.sv').read_text();log=(R/'simulation.log').read_text()
report=m.parse_failure(log,tb,state);(O/'actual114-failure-review.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
assert report['public_task_complete']is False and report['native_timing_violation_count']==25 and report['before_original_source_request_fs']==480000000
mutations=[
 ('wrong-fatal-file',lambda t:t.replace('/tb_xu_mapped_task00111.sv", 216:', '/other.sv", 216:')),
 ('wrong-fatal-line',lambda t:t.replace('.sv", 216:', '.sv", 215:')),
 ('wrong-finish-line',lambda t:t.replace('.sv", line 216.', '.sv", line 217.')),
 ('wrong-fatal-scope',lambda t:t.replace(': tb_xu_soc_ppa.public_scoreboard: at time', ': tb_xu_soc_ppa.other: at time')),
 ('wrong-native-fatal-tick',lambda t:t.replace('at time 9359423333333 fs','at time 9359423333334 fs')),
 ('wrong-native-finish-tick',lambda t:t.replace('$finish at simulation time        9359423333333','$finish at simulation time        9359423333334')),
 ('wrong-native-message',lambda t:t.replace(m.FAILURE,'XU_MAPPED111_PROTOCOL_REJECT different')),
 ('invented-source-request',lambda t:t+'\nXU_MAPPED111_SOURCE_REQUEST forged\n'),
 ('invented-final-retire',lambda t:t+'\nXU_MAPPED111_FINAL_Y_RETIRE forged\n'),
 ('invented-public-complete',lambda t:t+'\nXU_MAPPED111_PUBLIC_DIAGNOSTIC_COMPLETE forged\n'),
 ('invented-private-pending',lambda t:t+'\nXU_MAPPED111_REQUIRED_GATE_PENDING forged\n'),
 ('invented-full-pass',lambda t:t+'\nSOC_PASS tasks=1\n'),
 ('missing-native-fatal',lambda t:re.sub(r'^Fatal:[^\n]*\n','',t,flags=re.M)),
 ('extra-native-fatal',lambda t:t+'\nFatal: invented\n'),
 ('missing-recent-hold',lambda t:re.sub(r'^"[^\n]*u_sirv_mem_fab[^\n]*\n[^\n]*\n','',t,flags=re.M)),
 ('geometry-row-count',lambda t:t.replace('rows=256 row_bits=64 unique=256','rows=255 row_bits=64 unique=256',1)),
 ('earlier-native-error',lambda t:'Error-[TEST] invented\n'+t)]
results=[]
for name,change in mutations:
 altered=change(log);assert altered!=log
 own=copy.deepcopy(state);own['steps'][-1]['log']['sha256']=hashlib.sha256(altered.encode()).hexdigest()
 try:m.parse_failure(altered,tb,own)
 except ValueError as exc:results.append(dict(name=name,rejection=str(exc)))
 else:raise AssertionError('accepted invalid native failure evidence: '+name)
# Original source/step identities are independently mandatory.
for name,change in [('wrong-raw-step-hash',lambda s:s['steps'][-1]['log'].__setitem__('sha256','0'*64)),('original-failure-promoted',lambda s:s.__setitem__('status','PASS')),('missing-input-record',lambda s:s['inputs_before'].pop()),('input-change-hidden',lambda s:s.__setitem__('inputs_equal_before_after',False))]:
 own=copy.deepcopy(state);change(own)
 try:m.parse_failure(log,tb,own)
 except ValueError as exc:results.append(dict(name=name,rejection=str(exc)))
 else:raise AssertionError('accepted invalid original state: '+name)
(O/'check-results.json').write_text(json.dumps(dict(status='EXISTING114_FAILURE_PARSED_AND_21_MUTATIONS_REJECTED_NOT_VCS_RERUN',positive=dict(status=report['status'],raw_log_sha256=hashlib.sha256(log.encode()).hexdigest(),native_returncode=0,public_complete=False),negative=results),sort_keys=True,indent=2)+'\n')
print('AUDIT115_LOCAL: actual114 failure + %d semantic/raw-identity mutants rejected; no VCS rerun'%len(results))
