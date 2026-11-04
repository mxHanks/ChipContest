#!/usr/bin/env python3
"""Verify actual mapped structure only, not functional/task or energy evidence."""
import argparse,hashlib,json,re,tarfile
from collections import Counter
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parent
SHA='940fd1f01f23a32e023b4d1b1d98a32f330430663ebb40bebc7f4e1c7e64d944'
def need(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def verify(extract=None):
 a=ROOT/'payload.tar.xz';need(a.stat().st_size==35464 and sha(a.read_bytes())==SHA,'raw archive differs');manifest=json.loads((ROOT/'original-manifest.json').read_text());expected={r['path']:r for r in manifest};need(len(expected)==len(manifest)==21 and sum(r['bytes']for r in manifest)==576557,'actual source dimensions differ');found={};inner=None
 if extract:extract.mkdir(exist_ok=False)
 with tarfile.open(a,'r|xz')as t:
  for m in t:
   p=PurePosixPath(m.name);need(m.isfile()and not p.is_absolute()and '..'not in p.parts and m.name not in found and m.size<64000000,'unsafe member');d=t.extractfile(m).read()
   if m.name=='manifest.json':need(inner is None,'duplicate manifest');inner=json.loads(d);continue
   need(dict(path=m.name,bytes=len(d),sha256=sha(d))==expected.get(m.name),'raw payload differs');found[m.name]=d
   if extract:
    p=extract/m.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(d)
 need(set(found)==set(expected)and inner==manifest,'missing actual raw body')
 def obj(n):return json.loads(found[n])
 p='mapped-elaboration-probe-20261104-97/';l=obj('mapped-elaboration-launch-20261104-97/state.json');r=obj(p+'review.json');need(l['status']=='EXECUTED_STRUCTURE_PROBE_ONLY_NOT_FUNCTIONAL_ACTIVITY_OR_ENERGY'and l['returncode']==0 and l['review_sha256']==sha(found[p+'review.json']),'actual97 wrapper terminal differs');need(r['status']=='EXECUTED_STRUCTURE_PROBE_ONLY'and r['build_returncode']==r['simulation_returncode']==0 and r['qualification']=='NOT_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_PROOF','structure-only result differs');need(r['required_mapped_sha256']=='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892','wrong physical netlist');need(r['required_vpi_preload_shapes']==dict(itcm=32,shared=256,mem_words=256,word_bits=64,no_other_preload=True),'original preload geometry differs');need(all(r['input_sha256_after'][x['path']]==x['sha256']for x in r['inputs']),'actual source before/after differs')
 log=found[p+'simulation.log'].decode();lines=[x for x in log.splitlines()if x.startswith('XU_MAPPED_MACRO ')];need(len(lines)==336 and len(set(lines))==336 and all(x.endswith('ports=10 signal_bits=67 mem_words=256 word_bits=64')for x in lines),'actual336 native macro inventory differs');marker='XU_MAPPED_INVENTORY_RESULT macros=336 pin_bits=22512 preload_macros=288 shared_interfaces=1 accelerator_interfaces=1 modules=127549 status=PASS NOT_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY_PROOF';need(log.splitlines().count(marker)==1 and 'XU_MAPPED_PROBE_ERROR'not in log,'native metadata marker differs');warnings=Counter(re.findall(r'Warning-\[([^]]+)\]',found[p+'build.log'].decode()));need(warnings==dict(OPD=2,TFIPC=148),'original warning scope differs')
 models=obj('standard-cell-model-private-20261104-90/state.json');need(models['status']=='EXTRACTED_FOUR_VENDOR_MODELS_NOT_SIMULATED'and len(models['models'])==4 and models['archive']['stat_before']==models['archive']['stat_after'],'actual four-model extraction differs');normal=[x for x in models['models']if x['path'].endswith('/scc40nll_vhsc40_rvt.v')];need(len(normal)==1 and normal[0]['sha256']=='9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'and normal[0]['include_dependencies']==[]and len(normal[0]['module_names'])==1270,'actual standard model differs')
 failure=obj('s2c-native-pin-failure-20261104-92/state.json');f=failure['failure'];raw=found['s2c-native-pin-failure-20261104-92/first-failing-block.original.txt'];need(failure['status']=='LOCATED_ORIGINAL_PARSE_FAILURE_NOT_FIXED_NOT_QUALIFIED'and f['block_index']==29 and f['report_byte_start']==906580 and f['report_byte_end']==937158 and len(raw)==f['block_bytes']and sha(raw)==f['block_sha256'],'actual92 original failure differs');need('relative_toggle_rate'not in raw.decode()and 'toggle_rate' in raw.decode(),'native omission evidence differs');need(failure['original_report_actual']==failure['source_current']and failure['original_report_actual']['sha256']==failure['original_report_recorded']['sha256'],'actual92 original full report hash differs')
 for n,h in [('xu_prepare_mapped_probe74.py','db2898f0e2f11537eb8868b53e6e8eb7f5eab94e499e72ff7b1d23a148617b50'),('xu_mapped_inventory74.c','3febc2f02a59514d78d6e9358988b8b4aabdc3d383c0db7e058fa5192acb42ce')]:need(sha((ROOT/'tools'/n).read_bytes())==h,'actual probe helper differs')
 return dict(status='PASS',qualification='STRUCTURE_ONLY_NOT_FUNCTIONAL_OR_ACTIVITY_OR_ENERGY',archive_sha256=SHA,payload_count=21,payload_bytes=576557,macros=336,pin_bits=22512,preload_macro_handles=288,actual_build_warnings=dict(warnings),native_attribute_failure_block=29,vendor_bodies_returned=False)
def main():
 p=argparse.ArgumentParser();p.add_argument('--extract',type=Path);a=p.parse_args();print(json.dumps(verify(a.extract),sort_keys=True,indent=2))
if __name__=='__main__':main()
