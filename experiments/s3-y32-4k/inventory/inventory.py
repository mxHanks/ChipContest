#!/usr/bin/env python3
"""Read-only RTL storage inventory. Does not invoke EDA or simulation.

Count each declared variable targeted by a clocked nonblocking assignment once
per elaborated instance, using Verilator XML dtypes. This is raw RTL state,
not mapped flip-flops, area, clock load, or SRAM output-register overhead.
Exclude RAMSP bodies, and report capacities independently.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

FINAL = 'a80dd184536e0f2312c62768d5acf4ba1b01c34e'
FALLBACK = '45e61b6101ad6f0aaa7583098294ffb1550f1f2d'
FALLBACK_PARENT = '655713b304597ca5b2810a0940ac3f1850072d63'
ROOT = Path(__file__).resolve().parents[3]
CHILD = ROOT / 'third-party/e203_hbirdv2'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def number(text):
    if "'" not in text: return int(text)
    width, value = text.split("'", 1)
    value = value.lower().removeprefix('s')
    return int(value[1:], {'h':16,'b':2,'o':8,'d':10}[value[0]])

def xml_inventory(path):
    root = ET.parse(path).getroot()
    netlist = root.find('netlist')
    modules = {m.get('name'):m for m in netlist.findall('module')}
    types = {t.get('id'):t for t in netlist.find('typetable')}
    def width(dtype):
        t=types[dtype]
        if t.tag=='basicdtype': return abs(int(t.get('left','0'))-int(t.get('right','0')))+1
        if t.tag in ('packarraydtype','unpackarraydtype'):
            a,b=[number(x.get('name')) for x in t.find('range')]
            return (abs(a-b)+1)*width(t.get('sub_dtype_id'))
        if t.tag in ('refdtype','enumdtype','constdtype'): return width(t.get('sub_dtype_id'))
        raise ValueError('unsupported dtype '+ET.tostring(t,encoding='unicode'))
    def targets(lhs):
        if lhs.tag=='varref': return {lhs.get('name')}
        if lhs.tag in ('sel','arraysel','wordsel'): return targets(lhs[0])
        if lhs.tag=='concat': return set.union(*(targets(x) for x in lhs))
        raise ValueError('unsupported LHS '+ET.tostring(lhs,encoding='unicode'))
    def module_state(module):
        vs={v.get('name'):v for v in module.findall('var')}
        names=set(); blocking=[]
        for a in module.findall('always'):
            if not any(s.get('edgeType') in ('POS','NEG') for s in a.findall('./sentree/senitem')): continue
            for assignment in a.iter('assigndly'): names |= targets(assignment[-1])
            for assignment in a.iter('assign'):
                blocking.extend(sorted(targets(assignment[-1])))
        undeclared=names-set(vs)
        if undeclared: raise ValueError('undeclared clocked state '+repr(undeclared))
        state=[dict(name=n,bits=width(vs[n].get('dtype_id')),dtype_id=vs[n].get('dtype_id'),loc=vs[n].get('loc')) for n in sorted(names)]
        return dict(bits=sum(v['bits'] for v in state),variables=state,blocking_procedural_targets=sorted(set(blocking)))
    wanted={'xu_matrix_dma64','xu_dma64_shared_arb','xu_shared_icb_sram64'}
    top_roots=[c for c in root.find('cells').iter('cell') if c.get('submodname') in wanted]
    if len(top_roots)!=3: raise ValueError('charged inventory roots differ')
    rows=[]; excluded=[]
    for top in top_roots:
        scope={'xu_matrix_dma64':'DMA_and_core','xu_dma64_shared_arb':'arbiter','xu_shared_icb_sram64':'shared_endpoint'}[top.get('submodname')]
        for cell in top.iter('cell'):
            name=cell.get('submodname')
            if name.startswith('RAMSP1024X16'):
                excluded.append(dict(path=cell.get('hier'),module=name,capacity_bits=16384)); continue
            m=modules[name]; state=module_state(m)
            rows.append(dict(path=cell.get('hier'),module=name,orig_module=m.get('origName'),scope=scope,**state))
    return rows,excluded

def strip_comments(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/','',text,flags=re.S)

def sv_module_state(text):
    """Fallback cross-check for these fixed-width, generated source modules.

    Sequential blocks are identified by posedge/negedge sensitivities. Only
    NBA operators outside parentheses are assignments; comparisons inside if
    conditions are excluded. Loops assign only elaboration/procedural indices.
    Fail on unknown target or unsupported declarations instead of guessing.
    """
    text=strip_comments(text)
    declarations={}
    body=text[text.index(');')+2:]
    for m in re.finditer(r'\breg\s+(?:signed\s+)?(?:\[(\d+)\s*:\s*(\d+)\]\s*)?([^;]+);',body):
        bits=abs(int(m[1])-int(m[2]))+1 if m[1] is not None else 1
        for item in m[3].split(','):
            item=item.strip()
            if not re.fullmatch(r'\w+',item): raise ValueError('unsupported fallback reg '+item)
            declarations[item]=bits
    # ANSI output reg declarations are needed for both DMA and old endpoint.
    for m in re.finditer(r'\boutput\s+reg\s+(?:\[(\d+)\s*:\s*(\d+)\]\s*)?(\w+)',text):
        declarations[m[3]]=abs(int(m[1])-int(m[2]))+1 if m[1] is not None else 1
    names=set()
    tokens=list(re.finditer(r'\b\w+\b|<=|\(|\)|\[|\]|;|:',text))
    sequential=False; depth=0; paren=0; sensitivity=False; block_started=False
    for i,t in enumerate(tokens):
        word=t.group()
        if word=='always':
            # All studied source sequential always blocks use an explicit begin.
            end=text.find('begin',t.end()); fragment=text[t.end():end]
            sequential=('posedge' in fragment or 'negedge' in fragment)
            depth=0;paren=0;sensitivity=True;block_started=False
        if not sequential: continue
        if word=='begin': depth+=1;block_started=True;sensitivity=False
        elif word=='end':
            depth-=1
            if block_started and depth==0: sequential=False
        elif block_started and word=='(': paren+=1
        elif block_started and word==')': paren-=1
        elif block_started and word=='<=' and paren==0:
            before=text[:t.start()]
            m=re.search(r'(\w+)\s*(?:\[[^\]]+\])?\s*$',before)
            if not m: raise ValueError('cannot identify NBA target')
            name=m[1]
            if name not in declarations: raise ValueError('NBA target not declared reg '+name)
            names.add(name)
    return dict(bits=sum(declarations[n] for n in names),variables=[dict(name=n,bits=declarations[n]) for n in sorted(names)])

def baseline_inventory(final_rows):
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',FALLBACK,'rtl/e203/perips'],cwd=CHILD,text=True).splitlines()
    sources={}
    for path in paths:
        if not path.endswith(('.sv','.v')): continue
        data=subprocess.check_output(['git','show',FALLBACK+':'+path],cwd=CHILD)
        text=data.decode();match=re.search(r'\bmodule\s+(\w+)',strip_comments(text))
        if match: sources[match[1]]=(path,text,hashlib.sha256(data).hexdigest())
    # Verify the lightweight fallback parser against XML for every shared final
    # module, using current child files and actual XML counts (not assumptions).
    crosschecks=[]
    by_module={x['orig_module']:x for x in final_rows}
    adapter_path='tools/ppa/xu_weight_sram_adapter.sv'
    adapter=subprocess.check_output(['git','show',FALLBACK_PARENT+':'+adapter_path],cwd=ROOT)
    prepared=ROOT/'build/parallel4k-20261110/ppa-final-prepared-r2/source/rtl/perips/mem_1024x16.sv'
    if adapter!=prepared.read_bytes(): raise ValueError('baseline/final physical SRAM adapter changed')
    adapter_state=by_module['mem_1024x16']
    if adapter_state['bits']!=1 or adapter_state['variables'][0]['name']!='valid_read': raise ValueError('adapter state scope changed')
    for name in sorted(set(sources)&set(by_module)):
        if name in ('mem_1024x16','RAMSP1024X16'): continue
        path=CHILD/sources[name][0]
        current=sv_module_state(path.read_text())
        expected=by_module[name]
        if {x['name']:x['bits'] for x in current['variables']}!={x['name']:x['bits'] for x in expected['variables']}:
            raise ValueError('SV parser/XML mismatch '+name)
        crosschecks.append(dict(module=name,bits=current['bits'],status='EXACT_VARIABLE_WIDTH_MATCH'))
    rows=[];seen=[]
    def walk(name,hier):
        if name=='RAMSP1024X16': return
        if name=='mem_1024x16':
            rows.append(dict(path=hier,module=name,source=FALLBACK_PARENT+':'+adapter_path,
                source_sha256=hashlib.sha256(adapter).hexdigest(),bits=adapter_state['bits'],variables=adapter_state['variables'],
                evidence='Identical pinned baseline/current PPA adapter bytes; sequential width from final elaborated XML'))
            return
        if name not in sources: raise ValueError('unknown fallback hierarchy '+name)
        path,text,digest=sources[name];state=sv_module_state(text)
        rows.append(dict(path=hier,module=name,source=path,source_sha256=digest,**state))
        body=strip_comments(text)
        for m in re.finditer(r'(?m)^\s*(\w+)\s+(\w+)\s*\(',body):
            if m[1] in sources or m[1] in ('mem_1024x16','RAMSP1024X16'): walk(m[1],hier+'.'+m[2])
    walk('xu_matrix_dma','u_xu_matrix_dma')
    walk('xu_dma_shared_arb','u_xu_dma_shared_arb')
    old_endpoint_path='tools/ppa/xu_shared_icb_sram.sv'
    old_endpoint=subprocess.check_output(['git','show',FALLBACK_PARENT+':'+old_endpoint_path],cwd=ROOT)
    old_endpoint_state=sv_module_state(old_endpoint.decode())
    if old_endpoint_state['bits']!=5: raise ValueError('baseline endpoint state differs')
    return rows,crosschecks,dict(path='u_shared',module='xu_shared_icb_sram',source=FALLBACK_PARENT+':'+old_endpoint_path,
        source_sha256=hashlib.sha256(old_endpoint).hexdigest(),**old_endpoint_state)

def grouped(rows):
    out={}
    for row in rows:
        name=row['module']; entry=out.setdefault(name,dict(instances=0,bits_per_instance=row['bits'],total_bits=0))
        if entry['bits_per_instance']!=row['bits']: raise ValueError('same module different bits')
        entry['instances']+=1;entry['total_bits']+=row['bits']
    return out

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--xml',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists()
    rows,excluded=xml_inventory(args.xml)
    baseline,crosschecks,baseline_endpoint=baseline_inventory(rows)
    # Exact capacities and special payload subsets are checked from named RTL
    # state, not inferred from module names alone.
    named={r['path']:r for r in rows}
    x_bits=sum(r['bits'] for r in rows if r['orig_module']=='TileXRowBuffer')
    fifo_bits=sum(v['bits'] for r in rows if r['orig_module']=='LinearTileDmaCore' for v in r['variables'] if v['name'].startswith('results_'))
    acc_bits=sum(v['bits'] for r in rows if r['orig_module']=='MacPE' for v in r['variables'] if v['name']=='ACC')
    result_bits=sum(v['bits'] for r in rows if r['orig_module']=='DotProductEngine' for v in r['variables'] if v['name'].startswith('resultReg_'))
    assert (x_bits,fifo_bits,acc_bits,result_bits)==(16384,6144,3072,3072)
    baseline_x=sum(r['bits'] for r in baseline if r['module']=='XRowBuffer')
    baseline_fifo=sum(v['bits'] for r in baseline if r['module']=='LinearRowPairDmaCore' for v in r['variables'] if v['name'].startswith('results_'))
    baseline_acc=sum(v['bits'] for r in baseline if r['module']=='MacPE' for v in r['variables'] if v['name']=='ACC')
    baseline_result=sum(v['bits'] for r in baseline if r['module']=='DotProductEngine' for v in r['variables'] if v['name'].startswith('resultReg_'))
    assert (baseline_x,baseline_fifo,baseline_acc,baseline_result)==(4096,1536,768,768)
    macro_counts=Counter('owned_W_bias' if '.u_xu_matrix_dma.' in r['path'] else 'shared_512KiB' for r in excluded)
    assert macro_counts==dict(owned_W_bias=17,shared_512KiB=256)
    final_nonendpoint=sum(r['bits'] for r in rows if r['scope']!='shared_endpoint')
    result=dict(schema='parallel4k_rtl_storage_inventory_v1',status='PASS_RAW_DECLARED_SEQUENTIAL_BITS',
        created_at=datetime.now(timezone.utc).isoformat(),new_simulation_or_eda=False,
        final_child=FINAL,fallback_child=FALLBACK,xml_sha256=sha(args.xml),inventory_script_sha256=sha(Path(__file__)),
        scope='Raw declared width of each distinct clocked nonblocking-assignment target per instance; RAMSP macro internals excluded. Unoptimized RTL state, never mapped flop count or area.',
        final_total_raw_logic_state_bits=sum(r['bits'] for r in rows),
        final_dma_core_arb_bits=final_nonendpoint,
        final_endpoint_control_bits=sum(r['bits'] for r in rows if r['scope']=='shared_endpoint'),
        baseline_dma_core_arb_bits=sum(r['bits'] for r in baseline),
        dma_core_arb_delta_bits=final_nonendpoint-sum(r['bits'] for r in baseline),
        baseline_endpoint_control=baseline_endpoint,
        baseline_total_raw_logic_state_bits=sum(r['bits'] for r in baseline)+baseline_endpoint['bits'],
        total_raw_logic_state_delta_bits=sum(r['bits'] for r in rows)-sum(r['bits'] for r in baseline)-baseline_endpoint['bits'],
        known_payload_subsets=dict(final_X_bits=x_bits,baseline_X_bits=baseline_x,X_delta_bits=x_bits-baseline_x,
            final_FIFO_raw48_bits=fifo_bits,baseline_FIFO_raw48_bits=baseline_fifo,FIFO_delta_bits=fifo_bits-baseline_fifo,
            final_PE_ACC_bits=acc_bits,baseline_PE_ACC_bits=baseline_acc,PE_ACC_delta_bits=acc_bits-baseline_acc,
            final_engine_result_bits=result_bits,baseline_engine_result_bits=baseline_result,engine_result_delta_bits=result_bits-baseline_result),
        fixed_macro_capacity=dict(W=dict(instances=16,bits=16*1024*16,logical_bytes=32768,change=0),
            bias=dict(instances=1,bits=1024*16,used_words=768,used_bits=768*16,change=0),
            shared=dict(instances=256,bits=512*1024*8,bytes=512*1024,change=0,organization='64 depth banks x 4 lanes x1024x16; prior128x2 equivalent capacity')),
        exclusions=['RAMSP internal array and Q storage','retained old accelerator fallback not instantiated by XU_MATRIX_DMA64','CPU and original SoC control','combinational reg declarations and procedural loop indices','synthesis optimization, clock tree, tie cells and physical implementation'],
        final_by_module=grouped(rows),baseline_by_module=grouped(baseline),
        fallback_sv_parser_xml_crosschecks=crosschecks,
        final_instances=rows,baseline_instances=baseline,excluded_macro_instances=excluded)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','final_total_raw_logic_state_bits','final_dma_core_arb_bits','final_endpoint_control_bits','baseline_dma_core_arb_bits','dma_core_arb_delta_bits','known_payload_subsets','final_by_module')},indent=2))

if __name__=='__main__':main()
