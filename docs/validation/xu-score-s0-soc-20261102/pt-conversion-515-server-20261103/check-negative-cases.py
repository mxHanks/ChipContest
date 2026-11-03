#!/usr/bin/env python3
"""Meaningful negative checks of actual TC515 evidence, in disposable copies."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('xu_tc515_check',HERE/'check-evidence.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
PREFIX=c.NAME+'/tc515-witness-fs/'
def write(path,j):path.write_text(json.dumps(j,indent=2,sort_keys=True)+'\n')
def rebind(relative):
 identity=c.ident(c.HERE/'raw'/relative)
 for name in('selected-manifest.json','original-export-manifest.json'):
  path=c.HERE/name;items=c.load(path);next(r for r in items if r['path']==relative).update(identity);write(path,items)
def leaf(name,change):
 relative=PREFIX+name;path=c.HERE/'raw'/relative;change(path)
 state_path=c.HERE/'raw'/c.NAME/'result.json';j=c.load(state_path);g=j['groups'][0];g['artifacts'][name].update(c.ident(path))
 if name=='pt.log':g['execution']['log'].update(c.ident(path))
 write(state_path,j);rebind(relative);rebind(c.NAME+'/result.json')
def replace(path,old,new):
 raw=path.read_text();assert old in raw;path.write_text(raw.replace(old,new,1))
def known_tc(path):
 j=c.load(path);j['records'][0]['stats']['TC']=515;write(path,j)
def witness():
 def cases(path):
  j=c.load(path);j['records'][8]['stats']['T0']+=1;j['records'][8]['stats']['TX']-=1;write(path,j)
 leaf('cases.json',cases)
 def saif(path):
  replace(path,'(T0 506873333337)','(T0 506873333338)');replace(path,'(TX 2047446676666)','(TX 2047446676665)')
 leaf('synthetic.saif',saif)
def nonterminal():
 relative=c.NAME+'/result.json';path=c.HERE/'raw'/relative;j=c.load(path);j['status']='RUNNING_REVIEW_PENDING_NOT_QUALIFIED';write(path,j);rebind(relative)
CASES=[
 ('raw_bytes_changed',lambda:(c.HERE/'raw'/PREFIX/'pins.tsv').write_bytes((c.HERE/'raw'/PREFIX/'pins.tsv').read_bytes()+b' ')),
 ('known_tc_contrast_changed_resigned',lambda:leaf('cases.json',known_tc)),
 ('file_source_changed_to_default_resigned',lambda:leaf('pins.tsv',lambda p:replace(p,'\tfile\t','\tdefault\t'))),
 ('annotation_override_injected_resigned',lambda:leaf('probe.tcl',lambda p:replace(p,'close $xu_f','set_switching_activity -toggle_rate 0 [get_pins *]\nclose $xu_f'))),
 ('witness_stats_changed_consistently_in_case_and_saif_resigned',witness),
 ('nonterminal_server_receipt_resigned',nonterminal),
 ('original_measured_source_missing',lambda:(c.HERE/'recorded-frozen-inputs/measured-sram-pins.json.gz').unlink()),
 ('recorded_producer_missing',lambda:(c.HERE/'recorded-producers/probe_pt_activity_conversion515_03.py').unlink()),
]
def main():
 original=c.HERE;c.review();rejected=[]
 for label,change in CASES:
  with tempfile.TemporaryDirectory(prefix='xu-tc515-negative-')as temporary:
   destination=Path(temporary)/'archive';shutil.copytree(original,destination,ignore=shutil.ignore_patterns('__pycache__'));c.HERE=destination;change()
   try:c.review()
   except (ValueError,FileNotFoundError)as error:rejected.append(dict(case=label,diagnostic=str(error)))
   else:raise RuntimeError('corrupt evidence accepted: '+label)
   finally:c.HERE=original
 print(json.dumps(dict(schema='xu-tc515-evidence-negative-checks-v1',expected_rejections=len(CASES),actual_rejections=len(rejected),cases=rejected,qualification='NOT_QUALIFIED'),indent=2,sort_keys=True))
if __name__=='__main__':main()
