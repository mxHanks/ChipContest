#!/usr/bin/env python3
"""xu read-only duplicate UDP and missing mapped port review, exact actual inputs.

No vendor source body is exported. Native VCS lint logs are kept unchanged.
PASS means collection completed, never functional/timing/power qualification.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

NET='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
LIB='9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'
RAM='81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51'
TOKEN=re.compile(r'"(?:\\.|[^"\\])*"|\\[^\s]+|[A-Za-z_$][\w$]*|\d+(?:\s*\'\s*[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+)?|\'\s*[01xXzZ]|===|!==|==|!=|<=|>=|&&|\|\||<<|>>|[^\s]')
COMMENT=re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',re.S)
NAME=re.compile(r'^(?:[A-Za-z_$][\w$]*|\\[^\s]+)$')
def need(ok,msg):
    if not ok:raise ValueError(msg)
def digest(body):return hashlib.sha256(body).hexdigest()
def identity(path):
    path=Path(path).resolve();body=path.read_bytes();return dict(path=str(path),bytes=len(body),sha256=digest(body))
def dump(path,value):Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def clean(text):
    return COMMENT.sub(lambda m:m.group()if m.group().startswith('"')else ''.join('\n'if c=='\n'else' 'for c in m.group()),text)
def tokens(text):return [m.group()for m in TOKEN.finditer(text)]
def balanced(t,i,op='(',cl=')'):
    need(i<len(t)and t[i]==op,'expected balanced opener '+op);level=1;j=i+1
    while j<len(t):
        if t[j]==op:level+=1
        if t[j]==cl:level-=1
        if level==0:return j
        j+=1
    raise ValueError('unterminated balanced '+op)
def conditional_text(text,initial=('ARM_UD_MODEL','DISABLE_SV_ASSERTION')):
    defined=set(initial);stack=[];active=True;result=[]
    for line in text.splitlines(keepends=True):
        match=re.match(r'^[ \t]*`(ifdef|ifndef|elsif|else|endif|define|undef)\b[ \t]*([A-Za-z_$][\w$]*)?',line)
        if match:
            directive,symbol=match.groups()
            if directive in ['ifdef','ifndef']:
                test=(symbol in defined)if directive=='ifdef'else(symbol not in defined)
                stack.append([active,test]);active=active and test
            elif directive=='elsif':
                need(stack,'unmatched conditional elsif');parent,taken=stack[-1];test=not taken and symbol in defined;stack[-1][1]=taken or test;active=parent and test
            elif directive=='else':
                need(stack,'unmatched conditional else');parent,taken=stack[-1];active=parent and not taken;stack[-1][1]=True
            elif directive=='endif':
                need(stack,'unmatched conditional endif');active=stack.pop()[0]
            elif directive=='define'and active:defined.add(symbol)
            elif directive=='undef'and active:defined.discard(symbol)
            result.append(''.join('\n'if c=='\n'else' 'for c in line))
        else:result.append(line if active else ''.join('\n'if c=='\n'else' 'for c in line))
    need(not stack,'unclosed conditional compile block');return ''.join(result)

def definitions(source,role):
    text=source.read_text();stripped=conditional_text(clean(text));result={}
    for m in re.finditer(r'\bmodule\s+(\\[^\s]+|[A-Za-z_$][\w$]*)\b(.*?)\bendmodule\b',stripped,re.S):
        name=m.group(1);t=tokens(m.group());need(name not in result,'duplicate module definition needs review: '+name)
        i=2
        if t[i]=='#':i=balanced(t,i+1)+1
        need(t[i]=='(','module header lacks port list: '+name);end=balanced(t,i)
        header=t[i+1:end];ports=[]
        for token in header:
            if NAME.match(token)and token not in ['input','output','inout','wire','reg','logic','signed','unsigned','tri','supply0','supply1']:
                ports.append(token)
        need(len(ports)==len(set(ports)),'ambiguous declared header ports '+name)
        directions={};j=0
        while j<len(t):
            if t[j]in ['input','output','inout']:
                direction=t[j];k=j+1
                while k<len(t)and t[k]!=';':
                    if t[k]in ports:directions[t[k]]=direction
                    k+=1
                j=k
            j+=1
        need(set(directions)==set(ports),'unclassified direction in original model/module '+name)
        result[name]=dict(name=name,ports=ports,directions=directions,line=stripped.count('\n',0,m.start())+1,role=role,tokens=t,offset=m.start())
    need(result,'no module definitions in '+str(source));return result

def udp_review(source):
    raw=source.read_bytes();text=raw.decode('utf-8');stripped=clean(text);groups={}
    for match in re.finditer(r'\bprimitive\s+([A-Za-z_$][\w$]*)\b.*?\bendprimitive\b',stripped,re.S):
        name=match.group(1);ts=tokens(match.group());body=json.dumps(ts,separators=(',',':')).encode();start_line=stripped.count('\n',0,match.start())+1;end_line=start_line+match.group().count('\n')
        groups.setdefault(name,[]).append(dict(name=name,start_line=start_line,end_line=end_line,complete_definition_token_count=len(ts),complete_definition_token_sha256=digest(body),token_hash_definition='SHA256 of compact JSON array of complete primitive..endprimitive lexical tokens; comments/whitespace excluded, declaration/name/table tokens included'))
    duplicates=[]
    for name,rows in sorted(groups.items()):
        if len(rows)>1:duplicates.append(dict(name=name,definitions=rows,complete_definition_tokens_identical=len({r['complete_definition_token_sha256']for r in rows})==1))
    return dict(status='ORIGINAL_SOURCE_LEXICAL_DUPLICATE_REVIEW_ONLY',source=identity(source),primitive_definition_count=sum(len(x)for x in groups.values()),unique_primitive_names=len(groups),duplicates=duplicates,source_body_exported=False,qualification='NOT_QUALIFIED')

def missing_review(mapped,standard,vendor):
    libdefs=definitions(standard,'standard_cell');ramdefs=definitions(vendor,'vendor_memory');mappeddefs=definitions(mapped,'mapped_netlist')
    all_defs={}
    for d in [libdefs,ramdefs,mappeddefs]:
        for name,row in d.items():need(name not in all_defs,'cross-file duplicate module '+name);all_defs[name]=row
    rows=[];counts=Counter();examined=0
    for parent,pdef in mappeddefs.items():
        t=pdef['tokens'];j=0
        while j+2<len(t):
            ref=t[j]
            if ref not in all_defs:j+=1;continue
            if j>0 and t[j-1]=='module':j+=1;continue
            k=j+1
            if t[k]=='#':k=balanced(t,k+1)+1
            if not NAME.match(t[k]):j+=1;continue
            instance=t[k];k+=1
            if t[k]=='[':k=balanced(t,k,'[',']')+1
            if t[k]!='(':j+=1;continue
            end=balanced(t,k);args=t[k+1:end];target=all_defs[ref];connected={};q=0
            while q<len(args):
                if args[q]==',':q+=1;continue
                need(q+2<len(args)and args[q]=='.'and NAME.match(args[q+1])and args[q+2]=='(','non-named port binding needs explicit parser review: '+parent+'/'+instance)
                port=args[q+1];rend=balanced(args,q+2);need(port in target['directions']and port not in connected,'unknown/duplicate mapped named port '+parent+'/'+instance+'/'+port);connected[port]=args[q+3:rend];q=rend+1
            examined+=1;missing=[dict(name=p,direction=target['directions'][p])for p in target['ports']if p not in connected];empty=[dict(name=p,direction=target['directions'][p])for p,expr in connected.items()if not expr]
            if missing or empty:
                # Native VCS +lint provides its own precise file/line location.
                row=dict(parent_module=parent,instance=instance,reference=ref,reference_role=target['role'],reference_declaration_line=target['line'],declared_port_count=len(target['ports']),connected_named_port_count=len(connected),missing_ports=missing,explicit_empty_ports=empty)
                rows.append(row)
                if missing:counts['instances_with_omitted_ports']+=1
                if empty:counts['instances_with_explicit_empty_ports']+=1
                for pin in missing:counts['omitted_'+pin['direction']]+=1
                for pin in empty:counts['explicit_empty_'+pin['direction']]+=1
            j=end+1
    return dict(status='EXACT_SOURCE_NAMED_PORT_DIRECTION_REVIEW_ONLY',mapped=identity(mapped),standard=identity(standard),vendor=identity(vendor),declared_modules=dict(mapped=len(mappeddefs),standard=len(libdefs),vendor=len(ramdefs)),instances_parsed=examined,counts=dict(counts),instances=rows,qualification='NOT_QUALIFIED',limitations=['Source syntax only; native VCS +lint log is independent authoritative elaboration observation.','An omitted output is not by itself proof of functional equivalence; omitted input/inout requires explicit justification.','No absent port is connected or assigned by this tool.'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=Path.home()/'Desktop/xu-score-optimization-20261102');p.add_argument('--out',type=Path);p.add_argument('--vcs',type=Path,default=Path('/eda/synopsys/vcs/vcs_2020.03-SP2-6/bin/vcs'));a=p.parse_args()
    base=a.base.resolve();out=a.out.resolve()if a.out else base/'mapped-warning-audit-20261104-101';need(not out.exists(),'new output directory required');out.mkdir(parents=True)
    mapped=base/'s2c-ppa-campaign-20261103-01/s2c/ppa/mapped.v';standard=base/'standard-cell-model-private-20261104-90/scc40nll_vhsc40_rvt.v';vendor=Path('/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v');previous=base/'mapped-elaboration-probe-20261104-97';inputs=[identity(x)for x in [mapped,standard,vendor,previous/'review.json',previous/'mapped-probe.f',previous/'tb_xu_mapped_inventory74.sv']]
    state=dict(status='RUNNING_READ_ONLY_REVIEW',qualification='NOT_QUALIFIED',tool=identity(__file__),inputs_before=inputs,started_epoch=time.time(),steps=[]);dump(out/'state.json',state)
    try:
        need([r['sha256']for r in inputs[:3]]==[NET,LIB,RAM],'exact original mapped/cell/vendor identities differ')
        udp=udp_review(standard);dump(out/'duplicate-udp-token-review.json',udp)
        # Preserve original immutable actual97 build warnings and identities.
        previous_log=previous/'build.log';state['original97_build']=identity(previous_log);state['original97_warning_counts']=dict(Counter(re.findall(r'Warning-\[([^\]]+)\]',previous_log.read_text())))
        binding=None
        try:
            binding=missing_review(mapped,standard,vendor);dump(out/'missing-port-source-direction-review.json',binding)
        except ValueError as parser_error:
            state['source_direction_parser_error']=str(parser_error)
            dump(out/'missing-port-source-direction-review.json',dict(status='SOURCE_PARSER_INCOMPLETE',error=str(parser_error),qualification='NOT_QUALIFIED'))
        command=[str(a.vcs),'-full64','-sverilog','-timescale=1ns/1fs','-top','tb_xu_soc_ppa','-debug_access+all','-debug_region+cell','+lint=TFIPC-L','+define+ARM_UD_MODEL','+define+DISABLE_SV_ASSERTION=1','-f',str(previous/'mapped-probe.f'),'-Mdir='+str(out/'csrc'),'-o',str(out/'lint-probe')]
        # Only compile/lint. The original metadata fixture contains its old VPI
        # call; missing registration is avoided by the proven original .so.
        native=json.loads((previous/'review.json').read_text());original_load=native['build_command'][native['build_command'].index('-load')+1];library=Path(original_load.split(':',1)[0]);state['vpi_library']=identity(library);command[1:1]=['-load',original_load]
        state['steps'].append(dict(command=command,status='RUNNING'));dump(out/'state.json',state)
        with(out/'vcs-lint.log').open('xb')as output:run=subprocess.run(command,cwd=str(out),stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,timeout=1800)
        state['steps'][-1].update(status='RETURNED',returncode=run.returncode,log=identity(out/'vcs-lint.log'))
        log=(out/'vcs-lint.log').read_text(errors='replace');state['actual_lint_warning_counts']=dict(Counter(re.findall(r'Warning-\[([^\]]+)\]',log)));state['actual_lint_error_counts']=dict(Counter(re.findall(r'Error-\[([^\]]+)\]',log)))
        state['inputs_after']=[identity(r['path'])for r in inputs];need(state['inputs_before']==state['inputs_after'],'original input changed during read-only audit');need(run.returncode==0 and not state['actual_lint_error_counts'],'native lint compilation failed; original log retained')
        state['status']='EXECUTED_LINT_AND_SOURCE_REVIEW_NOT_FUNCTIONAL_QUALIFIED';state['udp_duplicate_names']=len(udp['duplicates']);state['udp_complete_token_equal']={r['name']:r['complete_definition_tokens_identical']for r in udp['duplicates']};state['source_missing_port_counts']=binding['counts']if binding else None;state['runtime_simulation_executed']=False
        if binding is None:state['status']='EXECUTED_NATIVE_LINT_SOURCE_DIRECTION_REVIEW_INCOMPLETE'
    except Exception as error:
        state['status']='FAIL';state['error']=str(error);dump(out/'state.json',state);raise
    state['finished_epoch']=time.time();dump(out/'state.json',state);print(state['status'],flush=True)
if __name__=='__main__':main()
