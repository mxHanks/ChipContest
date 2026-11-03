#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,re
H=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def need(x,m):
 if not x:raise ValueError(m)
def read(p):return json.loads(p.read_text())
sel=read(H/'selected-manifest.json');orig=read(H/'original-export-manifest.json');need(len(sel)==11 and len({r['path']for r in sel})==11,'raw set differs')
for r in sel:
 need([x for x in orig if x['path']==r['path']]==[r],'original selection differs');p=H/'raw'/r['path'];need(p.stat().st_size==r['bytes']and sha(p)==r['sha256'],'raw bytes differ')
B=H/'raw/candidate-formality-campaign-20261103-01';j=read(B/'state.json');need(j['status']=='EXECUTED_REVIEW_PENDING_NOT_QUALIFIED','campaign incomplete')
prior=H.parent/'formality-and-area-server-20261103/result.json';areas=read(prior)['area']
for n,pes,bb,dff,unmatched in [('h2-only',31213,17136,13894,17),('sram-bias',32748,18288,14277,25)]:
 r=next(x for x in j['runs']if x['candidate']==n);need(r['status']=='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED'and r['returncode']==0 and r['frozen_before']==r['frozen_after'],'actual FM freeze/status differs')
 D=B/n;log=(D/'fm.log').read_text();need(r['log']['sha256']==sha(D/'fm.log')and log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS')==1 and 'Verification SUCCEEDED'in log,'actual FM log differs')
 need(re.search(r'Passing \(equivalent\)\s+'+str(bb)+r'\s+0\s+0\s+0\s+144\s+'+str(dff)+r'\s+39\s+'+str(pes),log),'FM point breakdown differs')
 need(re.search(r'Unread\s+0\s+0\s+0\s+0\s+0\s+511\s+0\s+511',log),'unread scope differs');u=(D/'unmatched.rpt').read_text();need(str(unmatched)+' Unmatched points'in u and u.count('valid_read_reg')==unmatched-1 and u.count('count_reg[15]')==1,'unmatched scope differs')
 need('set verification_set_undriven_signals synthesis'in log and 'set verification_verify_directly_undriven_output false'in log,'conditional setup differs')
 a=next(x for x in areas if x['candidate']==('h2'if n=='h2-only'else'sram'));net=[v for k,v in r['frozen_before'].items()if k.endswith('/mapped.v')];need(len(net)==1 and net[0]['sha256']==a['mapped_netlist_sha256'],'FM mapped target differs from actual area receipt')
 print(n,'PASS',pes,'points,',bb,'blackbox pins;',unmatched,'unmatched reference points; NOT_QUALIFIED')
print('PASS11 raw SHA/size, bothS1 same-library netlist targets and conditional FM scope; no timing/energy qualification')
