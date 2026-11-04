from pathlib import Path
import json,hashlib
B=Path.home()/'Desktop/xu-score-optimization-20261102';P=B/'s2c-full-soc-power12-20261104-57';O=B/'s2c-power-pin-sample-20261104-78';O.mkdir(exist_ok=False)
execution=json.loads((P/'execution.json').read_text());assert execution['status']=='EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING'
rows=[]
for phase in ('before','after'):
 relative='task_00/sram-pins-'+phase+'.rpt';source=P/relative;expected=execution['artifacts'][relative];assert source.stat().st_size==expected['bytes'];data=bytearray();markers=0
 with source.open('rb')as stream:
  for line in stream:
   if line.startswith(b'XU_SRAM_PIN name='):
    markers+=1
    if markers==2:break
   data.extend(line)
 assert markers==2 and len(data)<200000
 target=O/('first-pin-'+phase+'.txt');target.write_bytes(data);rows.append(dict(phase=phase,original_full_report_receipt=expected,original_full_report_rehashed=False,sample=dict(path=str(target),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())))
(O/'state.json').write_text(json.dumps(dict(status='FIRST_PIN_BYTES_EXTRACTED_NOT_FULL_REPORT_REPLAY',qualification='NOT_QUALIFIED',samples=rows),sort_keys=True,indent=2)+'\n');print('PIN_SAMPLE78_READY')
