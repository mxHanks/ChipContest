"""Current-seed reset distribution plan and full-report regression guard.

Only same-library identity buffer additions are proposed. Native worst-context
and global guards do not establish external reset pulse/RDC/physical signoff.
"""
import collections
import hashlib
import json
from pathlib import Path
import re

SCHEMA='ingress1064-current-map-bounded-reset-eco-plan-v1'
ORIGINAL='882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e'

def need(x,message):
    if not x:raise ValueError(message)

def lit(x):
    if isinstance(x,list):return '{'+' '.join(lit(v)for v in x)+'}'
    x=str(x);need(not any(c in x for c in '{}\\\r\n'),'unsafe reset Tcl literal');return '{'+x+'}'

def graph(path):
    raw=Path(path).read_text();raw=re.sub(r'/\*.*?\*/','',raw,flags=re.S);raw=re.sub(r'//[^\n]*','',raw)
    mods={};ident=r'(?:\\\S+\s|[a-zA-Z_$][\w$]*)'
    for m in re.finditer(r'\bmodule\s+(\w+)\b(.*?)\bendmodule\b',raw,re.S):
        name,body=m.groups();body=body[body.index(';')+1:];cells=[];aliases=[];dirs={}
        for stmt in body.split(';'):
            stmt=stmt.strip()
            if not stmt:continue
            dr=re.match(r'^(input|output|inout)\s+(.*)$',stmt,re.S)
            if dr:
                for p in re.sub(r'\[[^\]]+\]','',dr[2]).split(','):dirs[p.strip()]=dr[1]
                continue
            if re.match(r'^(wire|tri)\b',stmt):continue
            if stmt.startswith('assign '):a,b=stmt[7:].split('=',1);aliases.append((a.strip(),b.strip()));continue
            im=re.match(r'^(\w+)\s+('+ident+r')\s*\((.*)\)$',stmt,re.S);need(im is not None,'unparsed seed mapped statement: '+stmt[:80])
            ref,ins,con=im.groups();pins=[(p.strip(),x.strip())for p,x in re.findall(r'\.('+ident+r')\s*\(([^()]*)\)',con,re.S)];cells.append((ref,ins.strip().lstrip('\\'),pins))
        mods[name]=(cells,aliases,dirs)
    instances={};edges=[];aliases=[];pin_net={};leafs=[];hier_pins={}
    scalar=lambda x:bool(re.fullmatch(r'[a-zA-Z_$][\w$]*(?:\[\d+\])?',x))
    def walk(mod,path):
        instances[path]=mod
        for a,b in mods[mod][1]:
            if scalar(a)and scalar(b):aliases.append((path+'|'+a,path+'|'+b))
        for ref,ins,pins in mods[mod][0]:
            cp=(path+'/'if path else'')+ins
            if ref in mods:
                for p,x in pins:
                    if scalar(x):
                        edges.append((path+'|'+x,cp+'|'+p,cp+'/'+p));hier_pins[cp+'/'+p]=(path+'|'+x,cp+'|'+p,mods[ref][2].get(p))
                walk(ref,cp)
            else:
                instances[cp]=ref
                for p,x in pins:
                    if scalar(x):
                        pn=cp+'/'+p;net=path+'|'+x;pin_net[pn]=net
                        if p not in {'Z','ZN','Q','QN','Q_N','Q1','Q2','CO','S'}:leafs.append((pn,net,ref))
    walk('xu_soc_sysbus32_ppa_top','')
    def connectivity(groups):
        parent={}
        def find(x):
            parent.setdefault(x,x)
            if parent[x]!=x:parent[x]=find(parent[x])
            return parent[x]
        def union(a,b):
            a,b=find(a),find(b)
            if a!=b:parent[b]=a
        hc={p:g for g in groups for p,k in zip(g['loads'],g['load_kinds'])if k=='hier_input'}
        lc={p:g for g in groups for p,k in zip(g['loads'],g['load_kinds'])if k=='leaf'}
        ic={p:g for g in groups for p,k in zip(g['loads'],g['load_kinds'])if k=='new_buffer_input'}
        for a,b in aliases:union(a,b)
        for a,b,p in edges:union('NEW|'+hc[p]['id']if p in hc else a,b)
        sinks=collections.defaultdict(list)
        for p,n,ref in leafs:sinks[find('NEW|'+lc[p]['id']if p in lc else n)].append(p)
        for g in groups:
            pin=(g['owner']+'/'if g['owner']else'')+g['new_cell_name']+'/I'
            n=g['owner']+'|'+g['expected_local_net'];sinks[find('NEW|'+ic[pin]['id']if pin in ic else n)].append(pin)
        return find,sinks
    return instances,edges,aliases,pin_net,leafs,hier_pins,connectivity


def build_static_plan(electrical,diagnostic,seed_sha,margin,source_map=None):
    need(source_map is not None,'explicit --source-map is required; a SHA alone cannot rebind deleted reset receivers')
    source_map=Path(source_map);need(hashlib.sha256(source_map.read_bytes()).hexdigest()==seed_sha,'explicit seed map SHA mismatch')
    need(electrical['mapped_sha256']==ORIGINAL and diagnostic['original_mapped_sha256']==ORIGINAL,'reset source catalogue differs from original1064')
    need(0.03<=margin<=0.5,'reset margin outside reviewed engineering bounds')
    ins,edges,aliases,pn,leafs,hp,connect=graph(source_map)
    macros=sorted(n for n,r in ins.items()if r=='RAMSP1024X16');need(len(macros)==353,'seed must retain353 SRAM')
    selected=[n for n in electrical['nets']if n['asynchronous_reset_net']];need(len(selected)==17,'exact17 reset distribution roots required')
    baseline_find,baseline_sinks=connect([]);roots=[];groups=[];removed=[]
    original_receivers=diagnostic['receivers'];receivers=[r for r in original_receivers if r['pin']in pn]
    removed_receivers=[r['pin']for r in original_receivers if r['pin']not in pn]
    need(len(removed_receivers)<=36 and all(r.endswith(('/RDN','/SDN'))for r in removed_receivers),'unexpected missing reset receiver outside pruned-state envelope')
    for row in selected:
        driver=row['driver'];need(driver in pn and ins.get(driver.rsplit('/',1)[0])==row['reference'],'reset root missing/reference changed in seed')
        old=baseline_sinks[baseline_find(pn[driver])]
        need(old and all(not x.endswith(('/CK','/CLK','/EN'))for x in old),'reset catalogue points to empty/clock net')
        rid=row['net_id'];candidate=[];available=set()
        for original in row['groups']:
            g=json.loads(json.dumps(original));loads=[];kinds=[]
            for name,kind in zip(g['loads'],g['load_kinds']):
                keep=True
                if kind=='leaf':keep=name in pn and baseline_find(pn[name])==baseline_find(pn[driver])
                elif kind=='hier_input':
                    keep=name in hp and hp[name][2]=='input'
                    if keep:
                        child=name.rsplit('/',1)[0]
                        keep=any(p.startswith(child+'/')for p in old)
                elif kind=='new_buffer_input':keep=name.rsplit('/',1)[0]in available
                else:raise ValueError('unsupported reset group load kind')
                if keep:loads.append(name);kinds.append(kind)
            if not loads:removed.append(g['id']);continue
            g['loads']=loads;g['load_kinds']=kinds;g['new_cell_name']='XU_ECO_reset_'+g['id'];g['net_id']=rid
            # Bind actual source-map local spellings, rather than inheriting
            # original-map net aliases after DC persistence/pruning.
            targetnets=[pn[name]if kind=='leaf'else hp[name][0]for name,kind in zip(loads,kinds)if kind!='new_buffer_input']
            if targetnets:
                need(all(n.split('|',1)[0]==g['owner']for n in targetnets),'rebound reset target owner differs')
                g['expected_local_net']=targetnets[0].split('|',1)[1]
            localnodes=set(pn.values())|{x for a,b,_ in edges for x in [a,b]}|{x for a,b in aliases for x in [a,b]}
            g['allowed_local_net_aliases']=sorted({n.split('|',1)[1]for n in localnodes if n.split('|',1)[0]==g['owner']and baseline_find(n)==baseline_find(pn[driver])})
            need(g['expected_local_net']in g['allowed_local_net_aliases'],'rebound reset local net missing')
            # Rewrite earlier electrical candidate names into reset-specific names.
            g['loads']=[x.replace('/XU_ECO_electrical_','/XU_ECO_reset_')if k=='new_buffer_input'else x for x,k in zip(loads,kinds)]
            candidate.append(g);available.add((g['owner']+'/'if g['owner']else'')+original['new_cell_name'])
        groups+=candidate
        roots.append(dict(net_id=rid,driver=driver,reference=row['reference'],original_flattened_sink_count=len(old),predicted_final_root_sink_count=None))
    need(groups,'no live reset groups')
    find,sinks=connect(groups)
    # Remove added outputs that were only feeding deleted-state branches; their
    # absence must also be removed from any planned aggregation load list.
    for _ in range(64):
        dead={g['id']for g in groups if not sinks[find('NEW|'+g['id'])]}
        if not dead:break
        gone={(g['owner']+'/'if g['owner']else'')+g['new_cell_name']+'/I'for g in groups if g['id']in dead}
        removed+=sorted(dead);groups=[g for g in groups if g['id']not in dead]
        for g in groups:
            kept=[(p,k)for p,k in zip(g['loads'],g['load_kinds'])if p not in gone]
            g['loads']=[x[0]for x in kept];g['load_kinds']=[x[1]for x in kept]
        need(all(g['loads']for g in groups),'empty aggregation after reset current-map rebind; explicit regroup required')
        find,sinks=connect(groups)
    else:raise ValueError('reset current-map pruning exceeded64 rounds')
    need(all(1<=len(sinks[find('NEW|'+g['id'])])<=16 for g in groups),'reset rebind output outside1..16')
    for row in roots:row['predicted_final_root_sink_count']=len(sinks[find(pn[row['driver']])])
    probe_source=next(g for g in groups if all(k=='leaf'for k in g['load_kinds'])and len(g['loads'])>=4 and all(x.endswith(('/RDN','/SDN'))for x in g['loads']))
    probe=dict(probe_source,id='reset_probe4',new_cell_name='XU_ECO_reset_probe4',loads=probe_source['loads'][:4],load_kinds=['leaf']*4)
    plan=dict(schema=SCHEMA,original_mapped_sha256=ORIGINAL,seed_mapped_sha256=seed_sha,required_margin_ns=margin,roots=roots,groups=groups,
        receivers=receivers,removed_original_reset_receivers=removed_receivers,excluded_dead_groups=sorted(set(removed)),probe_group=probe,probe_root=probe['net_id'],
        query_scope='SEVENTEEN_ROOT_WORST64_CONTEXTS_PLUS_COMPLETE_GLOBAL_COVERAGE',physical_pulse_signoff='UNRESOLVED',qualification=False,original_SRAM_instances=macros)
    validate(plan);return plan


def validate(plan):
    need(plan.get('schema')==SCHEMA and plan.get('original_mapped_sha256')==ORIGINAL and len(plan.get('seed_mapped_sha256',''))==64,'wrong reset plan identity')
    need(len(plan['roots'])==17 and len({r['net_id']for r in plan['roots']})==17 and len(plan['original_SRAM_instances'])==353,'reset root/macro count differs')
    need(0.03<=plan['required_margin_ns']<=0.5 and 1<=len(plan['groups'])<=128,'bounded reset group/margin differs')
    made=set();names=set()
    for g in plan['groups']:
        need(1<=len(g['loads'])<=16 and len(g['loads'])==len(set(g['loads']))==len(g['load_kinds']),'invalid reset group size')
        need(g['id']not in names and all(p.rsplit('/',2)[0]==g['owner']for p in g['loads']),'reset group duplicate/cross-owner')
        for p,k in zip(g['loads'],g['load_kinds']):
            need(k in{'leaf','hier_input','new_buffer_input'}and not p.endswith(('/CK','/CLK','/EN')),'reset load kind/clock invalid')
            if k=='new_buffer_input':need(p.rsplit('/',1)[0]in made,'reset aggregation references future/missing buffer')
        made.add((g['owner']+'/'if g['owner']else'')+g['new_cell_name']);names.add(g['id'])
    need(len(plan['probe_group']['loads'])==4 and plan['probe_root']in{r['net_id']for r in plan['roots']},'fourload reset probe invalid')
    return plan


def emit(plan,stage):
    validate(plan);need(stage in{'probe','split','reload'},'unsupported reset stage')
    groups=[plan['probe_group']]if stage=='probe'else plan['groups']
    lines=['set ::reset_eco_roots {}','set ::reset_eco_groups {}','set ::reset_eco_probe_root '+lit(plan['probe_root'])]
    for row in plan['roots']:lines.append('lappend ::reset_eco_roots [dict create '+' '.join(lit(k)+' '+lit(row[k])for k in ['net_id','driver','reference','original_flattened_sink_count','predicted_final_root_sink_count'])+']')
    for g in groups:lines.append('lappend ::reset_eco_groups [dict create '+' '.join(lit(k)+' '+lit(g[k])for k in ['id','owner','loads','load_kinds','allowed_local_net_aliases','new_cell_name','net_id'])+']')
    return ('\n'.join(lines)+'\n').encode()


def _untested(raw):
    rows={}
    for m in re.finditer(r'(?m)^(\S+)\n((?:[ \t].*\n|\n)+)',raw):
        if 'untested'not in m[0]:continue
        reason=re.search(r'untested\s+(\w+)',m[0]);need(reason,'unparsed untested reason')
        kind=re.search(r'\b(setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold)\b',m[2]);need(kind,'unparsed untested check kind')
        key=(m[1],kind[1],re.sub(r'\s+',' ',m[2]).strip());need(key not in rows,'duplicate untested identity');rows[key]=reason[1]
    return rows


def _drc(raw):
    result={}
    for block in re.split(r'(?m)^    Pin: ',raw)[1:]:
        name=block.splitlines()[0].strip();kind=re.findall(r'\b(max_capacitance|min_capacitance|max_transition)\b',block);slack=re.search(r'(?m)^    Slack\s+(-?[0-9.eE+-]+) \(VIOLATED\)',block)
        need(len(kind)==1 and slack is not None,'unparsed native DRC block');key=(name,kind[0]);need(key not in result,'duplicate native DRC');result[key]=float(slack[1])
    need(len(result)==len(re.findall(r'(?m)^    Slack\s+.*\(VIOLATED\)',raw)),'native DRC reconciliation differs');return result


def report_guard(before_cov,after_cov,before_drc,after_drc):
    from plan import catalog
    before_raw=Path(before_cov).read_text();after_raw=Path(after_cov).read_text();b,bc=catalog(before_raw);a,ac=catalog(after_raw)
    need({k:v['total']for k,v in b.items()}=={k:v['total']for k,v in a.items()},'reset ECO changed coverage total/type counts')
    key=lambda r:(r['pin'],r['kind'],re.sub(r'-?[0-9]+(?:\.[0-9]+)?\s+-\s*$','<slack>',re.sub(r'\s+',' ',r['native_block']).strip()))
    bv={key(r):float(r['slack_printed_ns'])for r in bc};av={key(r):float(r['slack_printed_ns'])for r in ac}
    need(set(av)<=set(bv),'reset ECO introduced new timing violation identity')
    need(all(v>=bv[k]-0.00001 for k,v in av.items()),'reset ECO worsened existing timing violation')
    bu,au=_untested(before_raw),_untested(after_raw);need(au==bu,'reset ECO changed/removed unknown/no_clock/untested identity or reason')
    bd,ad=_drc(Path(before_drc).read_text()),_drc(Path(after_drc).read_text());need(set(ad)<=set(bd),'reset ECO introduced new electrical violation')
    need(all(v>=bd[k]-0.00001 for k,v in ad.items()),'reset ECO worsened existing electrical violation')
    return dict(status='FULL_COVERAGE_AND_DRC_NO_NEW_OR_WORSE_CHECKS',before=b['All Checks'],after=a['All Checks'],before_electrical=len(bd),after_electrical=len(ad),untested_identity_count=len(bu),unknown_identity_count=sum(v=='unknown'for v in bu.values()),untested_unchanged=True,qualification=False,physical_pulse_signoff='UNRESOLVED')
