from pathlib import Path
import json,sys,hashlib
B=Path.home()/'Desktop/xu-score-optimization-20261102';P=B/'saif-bind-probe-04';O=B/'saif-bind-hand-review-20261103';O.mkdir(exist_ok=False)
sys.path.insert(0,str(B/'alias-tools-02/tools/scripts'));import xu_soc_activity as a
j=dict(status='REVIEWING_NOT_QUALIFIED')
try:
 observed=a.read_saif(P/'normalized.saif');duration=40000000
 if observed['timescale_seconds']!='1E-15'and float(observed['timescale_seconds'])!=1e-15:raise ValueError('timescale')
 if observed['duration_ticks']!=duration:raise ValueError('duration')
 ss={x['path'].rsplit('/',1)[1]:x for x in observed['signals']if x['path'].startswith('tb_xu_cell/dut/macro/')}
 widths={'CLK':1,'CEN':1,'WEN':16,'A':10,'D':16,'EMA':3,'EMAW':2,'GWEN':1,'RET1N':1,'Q':16};values={'CEN':0,'WEN':0,'A':0,'D':0x55aa,'EMA':2,'EMAW':0,'GWEN':1,'RET1N':1,'Q':0x55aa};checked=[]
 for pin,w in widths.items():
  for bit in range(w):
   name=pin if w==1 else pin+'['+str(bit)+']';s=ss[name]
   if pin=='CLK':expected=dict(T0=duration//2,T1=duration//2,TX=0,TC=8)
   else:
    level=(values[pin]>>bit)&1;expected=dict(T0=0 if level else duration,T1=duration if level else 0,TX=0,TC=0)
   if any(s.get(k,0)!=expected.get(k,0)for k in set(s)-{'path','kind'}|set(expected)):raise ValueError('handcountstats '+name+' '+str(s))
   checked.append(dict(pin=name,expected=expected,observed=s))
 if len(ss)!=67 or len(checked)!=67:raise ValueError('67pins')
 j.update(status='VERIFIED_67_PIN_HAND_EXPECTATIONS_REVIEW_PENDING',checked=checked,source_sha256=a.sha(P/'probe.sv'),raw_sha256=a.sha(P/'task.saif'),normalized_sha256=observed['sha256'],normalization=json.loads((P/'normalization.json').read_text()),limits='Actual VCS bound macro alias DUT-only SAIF; hand expectations for deterministic40ns probe, not fullSoC mapping/internal-power qualification. Prior directcelldefineVCDattempts failed and remain immutable.')
except Exception as e:j.update(status='FAIL',error=str(e));raise
finally:(O/'result.json').write_text(json.dumps(j,sort_keys=True,indent=2)+'\n')
print('HANDPROBE',j['status'])
