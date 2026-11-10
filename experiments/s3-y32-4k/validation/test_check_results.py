#!/usr/bin/env python3
"""Negative evidence tests: valid-looking summaries cannot hide missing work."""
import importlib.util,json
from pathlib import Path
p=Path(__file__).with_name('check_results.py');sp=importlib.util.spec_from_file_location('checker',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
base='''D4K_TASK_PASS layer=0 rows=8 outputs=25344 payload=35000 clear=1028 principal=36028 gap=100 including_gap=36128 firmware_cycles=36200 start_to_done=35002
D4K_WINDOW layer=0 first_request=1200 first_accept=1201 last_y_response=36199 clear_request=72 clear_done=1099 start=1199 done=36200
D4K_COUNTS layer=0 reads=7520 w_reads=4096 bias_reads=256 x_reads=3168 writes=12672 write_responses=12672 requests=20192 responses=20192 pops=3168 macs=26624 mmio_reads=1200 mmio_writes=6
D4K_CHANNEL layer=0 wb_cycles=5100 xy_window=29000 dma_stall=1 source_stall=1 write_stall=0 max_outstanding=1
D4K_CLOCK measured_hf_period_fs=6666666 measured_lf_period_fs=30517578126 hf_edges=10 lf_edges=3
D4K_PHYSICAL_CLEAR_BEGIN call=1 warmup=0 nonzero_W=0 nonzero_BIAS=0 nonzero_X=0 observed_last_public_writes=1
D4K_PHYSICAL_CLEAR_PASS call=1 warmup=0 W=16384 BIAS=768 X=1024 total16bit_writes=18176 physical_cycles=1028 X_REGS=1024 ACC=64 ENGINE_RESULT=64 FIFO=128 BIAS_CACHE=16 DMA_SNAPSHOT=1 all_addresses=1 all_payload_zero=1
D4K_PUBLIC_FIXTURE_PASS call=1 layer=0 source_writes=15040 poison_writes=25344 readbacks=25344 ready_sequence=1
D4K_SOC_PASS tasks=1 rows=8 outputs=25344 writes=12672
'''
assert m.check_log(base,1,8,False)['outputs']==25344
cases={
'missing_layer':base.replace('D4K_TASK_PASS','IGNORED_TASK_PASS'),
'duplicate_layer':base+base.splitlines()[0]+'\n',
'wrong_mac':base.replace('macs=26624','macs=25600'),
'wrong_w_count':base.replace('w_reads=4096','w_reads=2048'),
'early_completion':base.replace('done=36200','done=36199'),
'omit_clear':base.replace('clear=1028','clear=0'),
'bad_gap':base.replace('gap=100 ','gap=99 '),
'bad_occupancy':base.replace('max_outstanding=1','max_outstanding=2'),
'incomplete_physical':base.replace('W=16384 BIAS','W=8192 BIAS'),
'missing_readback':base.replace('readbacks=25344','readbacks=25343'),
'failure_tail':base+'TEST_FAIL hidden\n',
'malformed_count':base.replace('requests=20192','requests=20192x'),
'wrong_clock':base.replace('hf_period_fs=6666666','hf_period_fs=6666667'),
'missing_summary':base.replace('D4K_SOC_PASS','SKIPPED_SOC_PASS'),
}
for name,log in cases.items():
 try:m.check_log(log,1,8,False)
 except ValueError:continue
 raise AssertionError('accepted invalid evidence: '+name)
# A fast layer must not cancel one layer exceeding37,500 cycles.
import re
layers=[]
for i in range(12):
 lines=base.splitlines()[:4]
 lines=[line.replace('layer=0',f'layer={i}') for line in lines]
 lines[1]=re.sub(r'(first_request|first_accept|last_y_response|clear_request|clear_done|start|done)=(\d+)',lambda x:f'{x[1]}={int(x[2])+i*1000000}',lines[1])
 layers.append('\n'.join(lines)+'\n')
valid12=''.join(layers)
assert m.check_records(valid12,12,8)['full12_target_met']
bad12=valid12.replace('payload=35000 clear=1028 principal=36028 gap=100 including_gap=36128 firmware_cycles=36200 start_to_done=35002',
'payload=36972 clear=1028 principal=38000 gap=100 including_gap=38100 firmware_cycles=38200 start_to_done=36974',1).replace('last_y_response=36199','last_y_response=38171',1).replace('done=36200','done=38172',1)
rejected=m.check_records(bad12,12,8)
assert rejected['principal_cycles']<450000 and not rejected['full12_target_met']
print(json.dumps({'status':'PASS','positive':2,'negative':len(cases)+1},sort_keys=True))
