"""Read-only exact-map structural clock fanout contract for native PT recheck."""
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import re

ORIGINAL_MAP_SHA='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'
PLAN_SCHEMA='ingress1064-persisted-clock-diagnostic-plan-v1'
CLOCK_SCHEMA='ingress1064-n3-clock-eco-stage-v1'
SEED_SCHEMAS={CLOCK_SCHEMA,'ingress1064-n3-electrical-eco-stage-v1','ingress1064-n3-dead-cone-stage-v1'}


def require(ok,message):
    if not ok:raise ValueError(message)


def literal(x):
    if isinstance(x,list):return '{'+' '.join(literal(v)for v in x)+'}'
    x=str(x);require(not any(c in x for c in '{}\\\r\n'),'unsafe diagnostic Tcl literal');return '{'+x+'}'


def tsv(path):
    return list(csv.DictReader(Path(path).read_text().replace(r'\t','\t').splitlines(),delimiter='\t'))


def scalar_graph(path):
    raw=Path(path).read_text();raw=re.sub(r'/\*.*?\*/','',raw,flags=re.S);raw=re.sub(r'//[^\n]*','',raw)
    mods={};ident=r'(?:\\\S+\s|[a-zA-Z_$][\w$]*)'
    for m in re.finditer(r'\bmodule\s+(\w+)\b(.*?)\bendmodule\b',raw,re.S):
        name,body=m.groups();inst=[];aliases=[];body=body[body.index(';')+1:]
        for stmt in body.split(';'):
            stmt=stmt.strip()
            if not stmt or re.match(r'(input|output|inout|wire|tri)\b',stmt):continue
            if stmt.startswith('assign '):
                a,b=stmt[7:].split('=',1);aliases.append((a.strip(),b.strip()));continue
            im=re.match(r'^(\w+)\s+('+ident+r')\s*\((.*)\)$',stmt,re.S)
            require(im is not None,'unparsed mapped statement in '+name+': '+stmt[:80])
            ref,ins,conn=im.groups();pins=[]
            for cm in re.finditer(r'\.('+ident+r')\s*\(([^()]*)\)',conn,re.S):pins.append((cm[1].strip(),cm[2].strip()))
            inst.append((ref,ins.strip().lstrip('\\'),pins))
        require(name not in mods,'duplicate mapped module');mods[name]=(inst,aliases)
    parent={};members=collections.defaultdict(list);instances={};pin_nets={}
    def find(x):
        parent.setdefault(x,x)
        if parent[x]!=x:parent[x]=find(parent[x])
        return parent[x]
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b:parent[b]=a
    def scalar(x):return bool(re.fullmatch(r'[a-zA-Z_$][\w$]*(?:\[\d+\])?',x))
    def walk(mod,path):
        instances[path]=mod
        for a,b in mods[mod][1]:
            if scalar(a)and scalar(b):union(path+'|'+a,path+'|'+b)
        for ref,ins,pins in mods[mod][0]:
            cp=(path+'/'if path else'')+ins
            if ref in mods:
                for p,x in pins:
                    if scalar(x):union(path+'|'+x,cp+'|'+p)
                walk(ref,cp)
            else:
                instances[cp]=ref
                for p,x in pins:
                    if scalar(x):
                        pn=cp+'/'+p;net=path+'|'+x;pin_nets[pn]=net
                        if p not in {'Z','ZN','Q','QN','Q_N','Q1','Q2','CO','S'}:members[net].append(pn)
    require('xu_soc_sysbus32_ppa_top'in mods,'expected mapped top absent');walk('xu_soc_sysbus32_ppa_top','')
    sinks=collections.defaultdict(list)
    for n,pins in members.items():sinks[find(n)].extend(pins)
    def fanout(pin):
        require(pin in pin_nets,'exact scalar driver missing: '+pin)
        return sorted(sinks[find(pin_nets[pin])])
    return instances,fanout


def static_contract(mapped,plan,removed):
    require(plan.get('schema')==PLAN_SCHEMA and plan.get('original_mapped_sha256')==ORIGINAL_MAP_SHA and
        len(plan['clock_buffers'])==1560 and len(set(plan['clock_buffers']))==1560,'not exact r7 persisted diagnostic plan')
    instances,fanout=scalar_graph(mapped);expected=set(plan['clock_buffers']);actual={n for n in instances if re.search(r'/XU_ECO_clock_g\d{4}$',n)}
    require(actual==expected-set(removed),'persisted clock buffer inventory differs from r7 minus explicit cleanup ledger')
    require(all(instances[n]=='BUFV2_12TR40'for n in actual),'persisted clock buffer reference changed')
    macros={n for n,r in instances.items()if r=='RAMSP1024X16'}
    require(macros==set(plan['original_macro_instances'])and len(macros)==353,'original353 macro instance set changed')
    outputs={n:fanout(n+'/Z')for n in sorted(actual)}
    require(all(1<=len(x)<=32 for x in outputs.values()),'persisted clock output has zero or >32 static leaf loads')
    root=fanout(plan['root_driver']);require(1<=len(root)<=32,'persisted root static fanout outside1..32')
    if not removed:require(len(root)==18,'unpruned persisted r7 root fanout differs from18')
    return dict(schema='ingress1064-persisted-clock-source-contract-v1',source_mapped_sha256=hashlib.sha256(Path(mapped).read_bytes()).hexdigest(),root_driver=plan['root_driver'],root_sinks=root,
        expected_clock_buffers=[dict(instance=n,reference='BUFV2_12TR40',sinks=outputs[n])for n in sorted(outputs)],removed_clock_buffers=sorted(removed),original_macro_instances=sorted(macros),original_macro_clocks=plan['original_macro_clocks'])


def emit(contract):
    lines=['set ::clock_persist_source_map_sha '+literal(contract['source_mapped_sha256']),
        'set ::clock_persist_root '+literal(contract['root_driver']),
        'set ::clock_persist_root_sinks '+literal(contract['root_sinks']),
        'set ::clock_persist_removed '+literal(contract['removed_clock_buffers']),
        'set ::clock_persist_macros '+literal(contract['original_macro_instances']),'set ::clock_persist_buffers {}','set ::clock_persist_original_macro_clocks [dict create '+' '.join(literal(k)+' '+literal(v)for k,v in sorted(contract['original_macro_clocks'].items()))+']']
    for row in contract['expected_clock_buffers']:
        lines.append('lappend ::clock_persist_buffers [dict create '+ ' '.join(literal(k)+' '+literal(row[k])for k in ['instance','reference','sinks'])+']')
    return ('\n'.join(lines)+'\n').encode()
