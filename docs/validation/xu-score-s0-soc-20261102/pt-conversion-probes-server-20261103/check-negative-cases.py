#!/usr/bin/env python3
"""Corrupt temporary evidence copies; expected rejections are not EDA runs."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('xu_conversion_archive_check',HERE/'check-evidence.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def rebind(relative):
 """Re-sign manifests to ensure semantic checks, rather than SHA alone, reject."""
 identity=checker.ident(checker.HERE/'raw'/relative)
 for name in('selected-manifest.json','original-export-manifest.json'):
  path=checker.HERE/name;items=checker.load(path)
  rec=next(r for r in items if r['path']==relative)
  rec.update(identity);write(path,items)

def leaf(relative,change):
 path=checker.HERE/'raw'/relative;change(path)
 probe,group,name=relative.split('/')
 state_path=checker.HERE/'raw'/probe/'result.json';state=checker.load(state_path)
 g=next(g for g in state['groups']if g['label']==group)
 g['artifacts'][name].update(checker.ident(path))
 if name=='pt.log':g['execution']['log'].update(checker.ident(path))
 write(state_path,state);rebind(relative);rebind(probe+'/result.json')

def state_change(change):
 relative='pt-activity-conversion-probe-20261103-01/result.json'
 path=checker.HERE/'raw'/relative;state=checker.load(path);change(state);write(path,state);rebind(relative)

P='pt-activity-conversion-probe-20261103-01/known-fs/'
def replace(path,old,new):
 raw=path.read_text();assert old in raw;path.write_text(raw.replace(old,new,1))
def cases_dwell(path):
 j=checker.load(path);j['records'][0]['stats']['T0']+=1;write(path,j)
def ledger(path):
 j=checker.load(path);j['arcs'][13]['when']='RET1N';write(path,j)

CASES=[
 ('raw_byte_corruption',lambda:(checker.HERE/'raw'/P/'pins.tsv').write_bytes((checker.HERE/'raw'/P/'pins.tsv').read_bytes()+b' ')),
 ('missing_recorded_producer',lambda:(checker.HERE/'recorded-producers/probe_pt_activity_conversion.py').unlink()),
 ('file_source_changed_to_default_resigned',lambda:leaf(P+'pins.tsv',lambda p:replace(p,'\tfile\t','\tdefault\t'))),
 ('case_analysis_injected_resigned',lambda:leaf(P+'probe.tcl',lambda p:replace(p,'close $xu_f','set_case_analysis 0 [get_ports *]\nclose $xu_f'))),
 ('linked_database_changed_resigned',lambda:leaf(P+'probe.tcl',lambda p:replace(p,'xu-ramsp1024x16-ss-0p99v-125c.db','xu-other.db'))),
 ('case_and_saif_disagree_resigned',lambda:leaf(P+'cases.json',cases_dwell)),
 ('nonterminal_state_resigned',lambda:state_change(lambda j:j.update(status='RUNNING_REVIEW_PENDING_NOT_QUALIFIED'))),
 ('tool_version_changed_resigned',lambda:leaf(P+'tool-version.rpt',lambda p:p.write_text('T-2020.03\n'))),
 ('missing_query_file',lambda:(checker.HERE/'raw'/P/'pins.tsv').unlink()),
 ('liberty_condition_changed',lambda:ledger(checker.HERE/'liberty-arc-observer-plan.json')),
 ('frozen_producer_record_changed_resigned',lambda:state_change(lambda j:j['frozen_inputs'][j['probe']['path']].update(sha256='0'*64))),
]

def main():
 original=checker.HERE
 checker.review()
 rejected=[]
 for label,change in CASES:
  with tempfile.TemporaryDirectory(prefix='xu-conversion-negative-')as temporary:
   destination=Path(temporary)/'archive';shutil.copytree(original,destination,ignore=shutil.ignore_patterns('__pycache__'))
   checker.HERE=destination
   change()
   try:checker.review()
   except (ValueError,FileNotFoundError)as error:rejected.append(dict(case=label,diagnostic=str(error)))
   else:raise RuntimeError('corrupt evidence accepted: '+label)
   finally:checker.HERE=original
 print(json.dumps(dict(schema='xu-conversion-evidence-negative-checks-v1',expected_rejections=len(CASES),actual_rejections=len(rejected),cases=rejected,qualification='NOT_QUALIFIED'),indent=2,sort_keys=True))
if __name__=='__main__':main()
