#!/usr/bin/env python3
"""Read-only complete native coverage211 catalog + finite detailed-path evidence."""
import argparse,collections,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
 reports=ROOT/'build/area-opt-20261111/native/reports-r4/extracted/b/pt/reports';p=reports/'coverage.rpt';s=p.read_text();checks=[]
 for m in re.finditer(r'(?m)^(u_\S+|io_\S+)\n((?:[ \t].*\n|\n)+)',s):
  b=m[0];sl=re.search(r'(-[0-9]+\.[0-9]+)\s+-\s*$',b)
  if not sl:continue
  typ=re.search(r'\b(out_setup|out_hold|clock_gating_setup|clock_gating_hold|hold|setup|removal|recovery)\b',b);assert typ
  pin=m[1];kind=typ[1]
  if '/u_core/bias/'in pin:family='bias_data_hold'
  elif kind=='clock_gating_hold':family='gate_enable_hold'
  elif kind=='removal':family='aon_reset_removal'
  elif kind=='out_setup':family='debug_clock_output_setup'
  elif '/r_gpio_sync0_reg'in pin:family='async_GPIO_first_stage_hold'
  elif '/r_ls_clk_sync_reg'in pin:family='LF_to_HF_PWM_first_stage_hold'
  elif '/u_sirv_flash_qspi/'in pin:family='QSPI_data_hold'
  elif '/bootrom_deglitch/'in pin or'/dwakeup_deglitch/'in pin:family='AON_pad_first_stage_hold'
  elif '/jtag_dtm_gen.'in pin:family='JTAG_data_hold'
  else:family='unclassified_hold'
  line=s.count('\n',0,m.start())+1
  checks.append(dict(kind=kind,family=family,pin=pin,cell=pin.rsplit('/',1)[0]if'/'in pin else None,slack_low_print_precision_ns=sl[1],coverage_line=line,coverage_block_sha256=hashlib.sha256(b.encode()).hexdigest(),coverage_block=b,inside_cpu_hierarchy='/u_e203_cpu_top/u_e203_cpu/'in pin))
 counts=collections.Counter(c['kind']for c in checks);assert counts=={'hold':178,'clock_gating_hold':27,'removal':5,'out_setup':1},counts
 detailed=[]
 for name in ['setup.rpt','hold.rpt','clock_gating_hold.rpt','removal.rpt']:
  path=reports/name;raw=path.read_text()
  for m in re.finditer(r'(?s)  Startpoint:.*?(?=\n\n  Startpoint:|\Z)',raw):
   b=m[0];sl=re.search(r'slack \(VIOLATED\)\s+(-?[\d.]+)',b)
   if not sl:continue
   pins=[]
   for pm in re.finditer(r'(?m)^\s+(\S+) \(([A-Za-z][^ ]*)\)\s*$',b):
    if pm[2]not in ['net','out','in']:pins.append(dict(pin=pm[1],reference=pm[2]))
   detailed.append(dict(report=name,start_line=raw.count('\n',0,m.start())+1,startpoint=re.search(r'Startpoint:\s*(.*)',b)[1],endpoint=re.search(r'Endpoint:\s*(.*)',b)[1],slack_ns=sl[1],pins=pins,block_sha256=hashlib.sha256(b.encode()).hexdigest()))
 receipts=[ROOT/'build/area-opt-20261111/audit/b-native-pt-review-r1.json',ROOT/'build/timing-opt-20261109/native/pt-bias-hold-eco-r2/extracted/pt-bias-hold-eco-r2/execution.json',ROOT/'build/timing-opt-20261109/native/pt-clock-tree-eco-r1/extracted/xu-timing-opt-20261109/pt-clock-tree-eco-r1/execution.json',ROOT/'build/timing-opt-20261109/native/pt-clock-tree-eco-r2/extracted/xu-timing-opt-20261109/pt-clock-tree-eco-r2/execution.json']
 files=[reports/n for n in ['coverage.rpt','setup.rpt','hold.rpt','clock_gating_hold.rpt','removal.rpt','all_violators.rpt']]+receipts
 record=dict(schema='compliant32-oldB-native-complete211-catalog-v1',scope='Read-only old published64PE B native reports; new32 candidate not mapped/timed; names are old diagnostic anchors only',status='COMPLETE_211_COVERAGE_CHECKS_CATALOGED_NOT_FIXED',new_eda_or_simulation=False,counts=dict(counts),families={f:dict(checks=sum(c['family']==f for c in checks),unique_pins=len(set(c['pin']for c in checks if c['family']==f)))for f in sorted(set(c['family']for c in checks))},checks=checks,detailed_path_samples=detailed,files={str(p.relative_to(ROOT)):sha(p)for p in files})
 (out/'native-b-211-catalog.json').write_text(json.dumps(record,indent=2)+'\n')
 with(out/'native-b-211-pins.tsv').open('w')as f:
  f.write('family\tkind\tslack_printed_ns\tpin\told_coverage_line\tinside_cpu_hierarchy\n')
  for c in checks:f.write('\t'.join(str(c[k])for k in ['family','kind','slack_low_print_precision_ns','pin','coverage_line','inside_cpu_hierarchy'])+'\n')
 for kind in ['hold','clock_gating_hold','removal','out_setup']:
  pins=sorted(set(c['pin']for c in checks if c['kind']==kind));(out/(kind+'-unique-pins.txt')).write_text('\n'.join(pins)+'\n')
 print(json.dumps(dict(counts=record['counts'],families=record['families'])))
if __name__=='__main__':main()
