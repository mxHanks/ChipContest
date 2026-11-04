"""Offline proposal only: library and cross-hierarchy topology must be actual.
No netlist/library/constraint writes. The proposal still needs DC/PT and full FM.
"""
import argparse,csv,hashlib,json,re
from collections import defaultdict,Counter
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return list(csv.DictReader(p.open(),delimiter='\t'))
def check_outputs(d,required):
 s=json.loads((d/'state.json').read_text())
 assert s['status']==required,(d,s.get('status'))
 assert s['returncode']==0 and not s.get('errors'),s
 assert s['frozen_before']==s['frozen_after']
 for n,v in s['outputs'].items():
  assert Path(n).name==n,n
  p=d/n
  assert p.is_file()and p.stat().st_size==v['bytes']and sha(p)==v['sha256'],p
 return s

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--precision',type=Path,required=True);ap.add_argument('--palette',type=Path,required=True);ap.add_argument('--hier',type=Path);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
 assert not args.out.exists(),'preserve previous proposals'
 pstate=check_outputs(args.palette,'CELL_PALETTE_EXPORTED_REVIEW_PENDING_NOT_QUALIFIED')
 cap_report=args.precision/'constraints.rpt'
 precision_bindings=[v for n,v in pstate['frozen_before'].items()if n.endswith('/'+args.precision.name+'/constraints.rpt')]
 assert precision_bindings==[sha(cap_report)],'precision report differs from actual library query input freeze'
 net_bindings=[v for n,v in pstate['frozen_before'].items()if n.endswith('/full-soc-gating-margin-repair-20261103-09/mapped.v')]
 assert net_bindings==['5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca'],'original mapped net differs'

 caps={}
 for b in (args.precision/'constraints.rpt').read_text().split('    Pin: ')[1:]:
  pin=b.splitlines()[0]
  m=re.search(r'^\s*(min_capacitance|max_capacitance)\s+([\d.Ee+-]+)\s*\n\s*-\s+Capacitance\s+([\d.Ee+-]+)',b,re.M)
  assert m,(pin,b[:300]);assert pin not in caps
  caps[pin]={'kind':m[1],'limit':float(m[2]),'measured_load':float(m[3])}
 assert len(caps)==1460 and Counter(x['kind']for x in caps.values())=={'max_capacitance':56,'min_capacitance':1404}
 lib=defaultdict(dict)
 for r in rows(args.palette/'library-palette.tsv'):
  cell,pin=r['libcell'],r['libpin'].rsplit('/',1)[1]
  assert pin not in lib[cell]
  lib[cell][pin]=r
 def sig(c):return tuple(sorted((p,r['direction'],r['function'])for p,r in lib[c].items()))
 def number(s):
  try:return float(s)
  except ValueError:return None
 source=rows(args.palette/'source-pins.tsv');assert len(source)==1460
 assert len({r['pin']for r in source})==1460 and set(caps)=={r['pin']for r in source}
 proposals=[];unresolved=[]
 for r in source:
  if r['kind']!='max_capacitance':continue
  pin=r['pin'].rsplit('/',1)[1];cur=[c for c in lib if c.rsplit('/',1)[1]==r['ref']];assert len(cur)==1
  cur=cur[0];assert pin in lib[cur]
  assert lib[cur][pin]['direction']=='out'
  current_area=number(lib[cur][pin]['area']);assert current_area is not None
  candidates=[]
  for c in lib:
   if c==cur or sig(c)!=sig(cur):continue
   q=lib[c][pin];cap=number(q['max_capacitance']);area=number(q['area'])
   if cap is None or area is None or q['dont_use'] not in ('false','<ABSENT>'):continue
   # Choose only a measured same-function pin with >=5% electrical headroom.
   if cap<caps[r['pin']]['measured_load']*1.05:continue
   candidates.append({'libcell':c,'area':area,'max_capacitance':cap,'min_capacitance':number(q['min_capacitance'])})
  candidates.sort(key=lambda x:(x['area'],x['max_capacitance'],x['libcell']))
  base=dict(r,**caps[r['pin']],current_libcell=cur,current_area=current_area)
  if candidates:
   base.update(selected=candidates[0],alternatives=candidates[1:]);proposals.append(base)
  else:unresolved.append(base)
 hier_summary=None
 if args.hier:
  hstate=check_outputs(args.hier,'TOPOLOGY_EXPORTED_REVIEW_PENDING_NOT_QUALIFIED')
  assert hstate['frozen_before']==pstate['frozen_before'],'hierarchy and palette queries must use identical original inputs'

  grouped=defaultdict(list)
  for r in rows(args.hier/'topology.tsv'):grouped[r['source_pin']].append(r)
  assert set(grouped)==set(caps)
  dead=[];real_load=[]
  for pin,cap in caps.items():
   if cap['kind']!='min_capacitance':continue
   rs=grouped[pin]
   # This alone is insufficient for deletion: every other output on the owner
   # must separately be shown to have no reachable receiver as well.
   if len(rs)==1 and rs[0]['object']==pin and rs[0]['object_class']=='pin' and rs[0]['direction']=='out':dead.append(pin)
   else:real_load.append({'pin':pin,'connections':rs})
  dead_set=set(dead)
  bycell=defaultdict(list)
  for r in source:
   if r['kind']=='min_capacitance':bycell[r['cell']].append(r)
  removable=[];not_proven=[]
  for cell,rs in bycell.items():
   refs={r['ref']for r in rs};assert len(refs)==1
   cur=[c for c in lib if c.rsplit('/',1)[1]==next(iter(refs))];assert len(cur)==1
   outputs={cell+'/'+p for p,r in lib[cur[0]].items()if r['direction']=='out'}
   if outputs and outputs.issubset(dead_set):
    removable.append({'cell':cell,'libcell':cur[0],'outputs':sorted(outputs),'proof':'Every output pin in the actual library palette is independently source-only under actual all_connected -leaf across all segments.'})
   else:not_proven.append({'cell':cell,'libcell':cur[0],'unproven_outputs':sorted(outputs-dead_set)})
  hier_summary={'source_only_current_output_pins':dead,'other_connections':real_load,'whole_cell_removal_candidates':removable,'whole_cell_removal_not_proven':not_proven,'deletion_executed':False,'reason':'Candidates only: literal full-cell output-set evidence must be checked again in DC before removal; every post-edit PT, upstream new dangling output, and full formal proof remain required.'}
 result={'status':'PROPOSAL_ONLY_NOT_EXECUTED_NOT_QUALIFIED','inputs':{str(args.precision/'constraints.rpt'):sha(args.precision/'constraints.rpt'),str(args.palette/'state.json'):sha(args.palette/'state.json')},'same_pin_direction_function_signature':True,'max_cap_size_proposals':proposals,'max_cap_no_legal_candidate':unresolved,'total_proposed_area_delta_um2':sum(x['selected']['area']-x['current_area']for x in proposals),'cross_hierarchy_min_cap':hier_summary,'limitations':['Gate resizing can increase upstream load and change every delay; complete original-constraint PT and formal consistency are mandatory.','No set_load, library limit edit, false path, case-analysis, reset waiver or coverage substitution.','Source-only pin alone does not prove whole-cell removability. Candidates require all library outputs independently source-only; post-edit full formal proof remains required.']}
 if args.hier:result['inputs'][str(args.hier/'state.json')]=sha(args.hier/'state.json')
 args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print('PROPOSAL_ONLY',len(proposals),'max pins;',len(unresolved),'unresolved; area delta',result['total_proposed_area_delta_um2'])
if __name__=='__main__':main()
