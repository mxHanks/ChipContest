#!/usr/bin/env python3
"""Mutate saved evidence copies; never simulate or edit measured evidence.

Every negative starts from the same independently verified real candidate. Only
one stated artifact is changed and hashes needed to reach the deeper invariant
are updated. This is corruption testing of the verifier, not fabricated native
PASS evidence. Each changed byte stream and actual rejection is retained.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('packed_clear_compare',ROOT/'packed_clear_compare.py')
VERIFY=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def write(path,data):
    # Existing test copies can share read-only hardlinks with original evidence.
    # Atomic replacement is mandatory: never mutate a linked original inode.
    temporary=path.with_name(path.name+'.negative-tmp')
    temporary.write_bytes(data)
    os.replace(temporary,path)


def save_json(path,value):
    write(path,(json.dumps(value,indent=2)+'\n').encode())


def replace_once(path,before,after):
    data=path.read_bytes()
    assert data.count(before)==1,(path,before,data.count(before))
    write(path,data.replace(before,after,1))


def fixture_copy(source,target):
    report=VERIFY.read_json(source/'result.json')
    plan=VERIFY.read_json(source/'plan.json')
    paths={'result.json','plan.json','clear-recipe.json','s3_clear_main.c','s3_clear_observer.svh','tb.sv','rtl.f',
           'accel_soc','accel_soc.verilog'}
    paths|={'source/'+name for name in report['original_source_sha256']}
    paths|={step['name']+'.log' for step in report['steps']}
    first=next(step for step in report['steps'] if step['name'].endswith('/simulation'))
    binary=first['command'][0]
    paths.add(str(Path(binary).relative_to(Path(plan['arguments']['out']))))
    for task in report['task_results']:
        paths|={'task-%02d/vectors/'%task['original_layer']+name for name in task['vectors']}
    for name in sorted(paths):
        destination=target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        os.link(source/name,destination)


def alter_raw_and_saved_clear(root,field,value):
    report=VERIFY.read_json(root/'result.json')
    task=report['task_results'][0]
    step=next(step for step in report['steps'] if step['name']=='task-%02d/simulation'%task['original_layer'])
    log=root/(step['name']+'.log')
    before=(field+'='+task['clear'][field]).encode()
    # Select only the exact clear marker; the token can appear in other markers.
    data=log.read_bytes().splitlines(keepends=True)
    changed=[]
    for line in data:
        if line.startswith(b'S3_TASK_CLEAR_OBSERVED '):
            assert line.count(before)==1
            line=line.replace(before,(field+'='+value).encode(),1)
        changed.append(line)
    write(log,b''.join(changed))
    task['clear'][field]=value
    step['log_sha256']=VERIFY.digest(log)
    save_json(root/'result.json',report)


def mutate_clear_c(root):
    replace_once(root/'s3_clear_main.c',b'pair < 8192',b'pair < 8191')
    recipe=VERIFY.read_json(root/'clear-recipe.json')
    recipe['generated_c_sha256']=VERIFY.digest(root/'s3_clear_main.c')
    save_json(root/'clear-recipe.json',recipe)


def mutate_padding_c(root):
    replace_once(root/'s3_clear_main.c',b'int main(void) {',b'int main(void) {\n    __asm__ volatile ("nop");')
    recipe=VERIFY.read_json(root/'clear-recipe.json')
    recipe['generated_c_sha256']=VERIFY.digest(root/'s3_clear_main.c')
    save_json(root/'clear-recipe.json',recipe)


def mutate_tb(root):
    replace_once(root/'tb.sv',b'if (nice_drain8) observe_nice();',b'if (1\'b0 && nice_drain8) observe_nice();')
    recipe=VERIFY.read_json(root/'clear-recipe.json')
    recipe['generated_tb_sha256']=VERIFY.digest(root/'tb.sv')
    save_json(root/'clear-recipe.json',recipe)


def mutate_observer(root):
    replace_once(root/'s3_clear_observer.svh',b's3_physical_w_count!=16384',b's3_physical_w_count!=0')


def mutate_image(root):
    path=root/'accel_soc.verilog'
    tokens=path.read_text().split()
    index=next(i for i,t in enumerate(tokens) if not t.startswith('@'))
    tokens[index]='%02X'%((int(tokens[index],16)^1)&255)
    write(path,(' '.join(tokens)+'\n').encode())
    report=VERIFY.read_json(root/'result.json')
    report['firmware_image_sha256']=VERIFY.digest(path)
    save_json(root/'result.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--source-pairs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    basepins=VERIFY.read_json(ROOT/'ready-baseline-sources.json')
    pairs=VERIFY.read_json(args.source_pairs)
    pins=VERIFY.pinned_candidate_sources(basepins,pairs)
    source=args.candidate.resolve().parent
    good=VERIFY.load_campaign(args.candidate,'ready32-packed',pins)
    args.out.mkdir(parents=True,exist_ok=False)
    cases=[
        ('changed-rtl',lambda r:replace_once(r/'source/rtl/perips/LinearAutoGroupCore.sv',b'module LinearAutoGroupCore(',b'module LinearAutoGroupCore(/*corrupt*/'), 'artifact SHA differs'),
        ('changed-old-scalar-helper',lambda r:write(r/'source/tools/ppa/s3_task_clear_protocol.py',(r/'source/tools/ppa/s3_task_clear_protocol.py').read_bytes()+b'\n# corrupt\n'),'artifact SHA differs'),
        ('changed-tensor',lambda r:write(r/'task-00/vectors/layer_00/w.mem',(r/'task-00/vectors/layer_00/w.mem').read_bytes()+b'\n0000\n'),'artifact SHA differs'),
        ('omitted-physical-write-generated-c',mutate_clear_c,'generated clear C differs from exact selected helper regeneration'),
        ('added-padding-generated-c',mutate_padding_c,'generated clear C differs from exact selected helper regeneration'),
        ('payload-observer-disabled-generated-tb',mutate_tb,'generated TB differs from exact old payload seams'),
        ('physical-observer-weakened',mutate_observer,'saved clear observer differs from exact selected helper'),
        ('loaded-image-byte',mutate_image,'firmware image bytes differ from ELF PT_LOAD'),
        ('missing-physical-w-marker',lambda r:alter_raw_and_saved_clear(r,'physical_w','16383'),'fixed clear protocol/physical-work/policy differs'),
        ('premature-proof-marker',lambda r:alter_raw_and_saved_clear(r,'commands','8259'),'fixed clear protocol/physical-work/policy differs'),
        ('fifo-policy-promotion-marker',lambda r:alter_raw_and_saved_clear(r,'fifo_payload_physical_zero','PROVEN'),'fixed clear protocol/physical-work/policy differs'),
        ('early-proof-timing-marker',lambda r:alter_raw_and_saved_clear(r,'response_end_cycle','1'),'clear observer local/global timing relation differs'),
        ('duplicate-clear-marker',None,'missing/duplicate S3_TASK_CLEAR_OBSERVED'),
    ]
    receipts=[]
    for label,mutation,expected in cases:
        root=args.out/(label+'-fixture')
        fixture_copy(source,root)
        before={str(p.relative_to(root)):VERIFY.digest(p) for p in root.rglob('*') if p.is_file()}
        if label=='duplicate-clear-marker':
            report=VERIFY.read_json(root/'result.json');step=next(s for s in report['steps'] if s['name']=='task-00/simulation')
            log=root/(step['name']+'.log');data=log.read_bytes();line=next(l for l in data.splitlines(keepends=True) if l.startswith(b'S3_TASK_CLEAR_OBSERVED '))
            write(log,data+line);step['log_sha256']=VERIFY.digest(log);save_json(root/'result.json',report)
        else: mutation(root)
        rejected=None
        try: VERIFY.load_campaign(root/'result.json','ready32-packed',pins)
        except (OSError,ValueError,KeyError,TypeError,StopIteration,AttributeError) as error: rejected=str(error)
        assert rejected is not None and expected in rejected,(label,rejected,expected)
        changes=[]
        destination=args.out/(label+'-changed-artifacts')
        for p in root.rglob('*'):
            if p.is_file() and VERIFY.digest(p)!=before[str(p.relative_to(root))]:
                rel=p.relative_to(root);q=destination/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
                changes.append(dict(path=str(rel),baseline_sha256=before[str(rel)],mutant_sha256=VERIFY.digest(p)))
        receipts.append(dict(name=label,actual_rejection=rejected,expected_rejection=expected,changed_artifacts=changes))
        shutil.rmtree(root)
        print('REJECTED',label,rejected)
    result=dict(schema='s3-packed-clear-verifier-corruption-tests-v1',status='ALL_EXPECTED_REJECTIONS',
        scope='corrupted hardlinked copies with atomic replacement; no native simulation, no original artifact mutation',
        verifier_sha256=VERIFY.digest(ROOT/'packed_clear_compare.py'),candidate_result_sha256=VERIFY.digest(args.candidate),
        positive_candidate_layers=[r['original_layer'] for r in good['rows']],cases=receipts)
    (args.out/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('PACKED_CLEAR_COMPARATOR_NEGATIVES_PASS',len(cases))


if __name__=='__main__':main()
