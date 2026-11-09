#!/usr/bin/env python3
"""Corrupt atomic-replacement fixture copies; retain only changed artifacts.

These are verifier corruption checks, never native simulation evidence.
All original campaign inodes remain unchanged despite read-only hardlinks.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bias_demand_compare',HERE/'compare_bias_demand.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
OLD_TEST=C.LOADER_PATH.with_name('test_packed_clear_compare.py')
assert C.digest(OLD_TEST)=='eae8094fe916580c2f960ee86ee9b33d109943047ed64a9b13f3dc69a4e200f7'
spec=importlib.util.spec_from_file_location('inherited_corruption_helpers',OLD_TEST)
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)


def mutate_result(root,change):
    report=C.read_json(root/'result.json');change(report);T.save_json(root/'result.json',report)


def mutate_log(root,before,after):
    report=C.read_json(root/'result.json')
    step=next(s for s in report['steps'] if s['name']=='task-00/simulation')
    path=root/(step['name']+'.log')
    T.replace_once(path,before,after)
    step['log_sha256']=C.digest(path);T.save_json(root/'result.json',report)


def duplicate_pass(root):
    report=C.read_json(root/'result.json');step=next(s for s in report['steps'] if s['name']=='task-00/simulation')
    path=root/(step['name']+'.log');data=path.read_bytes()
    line=next(x for x in data.splitlines(keepends=True) if x.startswith(b'TASK_PASS '))
    T.write(path,data+line);step['log_sha256']=C.digest(path);T.save_json(root/'result.json',report)


def append_nonloaded_elf(root):
    path=root/'accel_soc';T.write(path,path.read_bytes()+b'CORRUPT-NONLOADED-METADATA')
    mutate_result(root,lambda r:r.update(firmware_elf_sha256=C.digest(path)))


def changed_version(root):
    report=C.read_json(root/'result.json')
    step=next(s for s in report['steps'] if s['name'].startswith('version-'))
    path=root/(step['name']+'.log');raw=path.read_text();command,sep,text=raw.partition('\n')
    text+='\nCORRUPT TOOL VERSION\n';T.write(path,(command+sep+text).encode())
    step['log_sha256']=C.digest(path);report['versions'][step['command'][0]]=text
    T.save_json(root/'result.json',report)


def change_manifest(root):
    for name in ('result.json','plan.json'):
        value=C.read_json(root/name);value['original_source_sha256'][C.CORE]='0'*64;T.save_json(root/name,value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--source-pairs',type=Path,required=True)
    parser.add_argument('--identity',action='store_true')
    parser.add_argument('--layers',type=C.V.parse_layers)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    pairs=C.read_json(args.source_pairs);pins=C.candidate_pins(pairs,args.identity)
    positive=C.verify(args.baseline,args.candidate,pairs,args.layers,args.identity)
    before=C.load_campaign(args.baseline,C.baseline_pins())
    selected=list(range(12)) if args.layers is None else args.layers
    before=C.V.project_layers(before,selected,'full12-to-full12' if args.layers is None else 'explicit-common-layer-projection')
    args.out.mkdir(parents=True,exist_ok=False)
    cases=[
        ('unreviewed-core-byte',lambda r:T.replace_once(r/'source'/C.CORE,b'module LinearAutoGroupCore(',b'module LinearAutoGroupCore(/*corrupt*/'),'artifact SHA differs'),
        ('cpu-control-byte',lambda r:T.write(r/'source/rtl/core/e203_cpu.v',(r/'source/rtl/core/e203_cpu.v').read_bytes()+b'\n// corrupt\n'),'artifact SHA differs'),
        ('tensor-byte',lambda r:T.write(r/'task-00/vectors/layer_00/w.mem',(r/'task-00/vectors/layer_00/w.mem').read_bytes()+b'\n0000\n'),'artifact SHA differs'),
        ('missing-physical-write-c',T.mutate_clear_c,'generated clear C differs from exact selected helper regeneration'),
        ('firmware-padding-c',T.mutate_padding_c,'generated clear C differs from exact selected helper regeneration'),
        ('disabled-payload-observer',T.mutate_tb,'generated TB differs from exact old payload seams'),
        ('weakened-clear-observer',T.mutate_observer,'saved clear observer differs from exact selected helper'),
        ('loaded-image-byte',T.mutate_image,'firmware image bytes differ from ELF PT_LOAD'),
        ('nonloaded-elf-byte',append_nonloaded_elf,'ELF differs beyond one exact nonloaded GCC temporary-object FILE symbol'),
        ('missing-physical-w-marker',lambda r:T.alter_raw_and_saved_clear(r,'physical_w','16383'),'fixed clear protocol/physical-work/policy differs'),
        ('clear-commands-marker',lambda r:T.alter_raw_and_saved_clear(r,'commands','8259'),'fixed clear protocol/physical-work/policy differs'),
        ('fifo-policy-promotion',lambda r:T.alter_raw_and_saved_clear(r,'fifo_payload_physical_zero','PROVEN'),'fixed clear protocol/physical-work/policy differs'),
        ('early-clear-timing',lambda r:T.alter_raw_and_saved_clear(r,'response_end_cycle','1'),'clear observer local/global timing relation differs'),
        ('duplicate-task-pass',duplicate_pass,'complete numerical task markers missing or inconsistent'),
        ('wrong-numeric-output-count',lambda r:mutate_log(r,b'SOC_PASS tasks=1 outputs=25344 writes=25344',b'SOC_PASS tasks=1 outputs=25343 writes=25344'),'complete numerical task markers missing or inconsistent'),
        ('selfconsistent-tool-version',changed_version,'conditions differ'),
        ('nonempty-source-drift',lambda r:mutate_result(r,lambda j:j.update(source_drift=['cpu-control'])),'source drift is missing/nonempty'),
        ('selfconsistent-manifest-core',change_manifest,'source manifest differs from externally pinned exact source SHA map'),
    ]
    receipts=[]
    for name,mutation,expected in cases:
        root=args.out/(name+'-fixture');T.fixture_copy(args.candidate.resolve().parent,root)
        old={str(p.relative_to(root)):C.digest(p) for p in root.rglob('*') if p.is_file()}
        mutation(root);error=None
        try:
            after=C.load_campaign(root/'result.json',pins)
            after=C.V.project_layers(after,selected,before['selection_mode'])
            C.compare(before,after,pairs,args.identity)
        except (OSError,ValueError,KeyError,TypeError,StopIteration,AttributeError) as exc:error=str(exc)
        assert error is not None and expected in error,(name,error,expected)
        changes=[]
        for path in root.rglob('*'):
            if path.is_file() and C.digest(path)!=old.get(str(path.relative_to(root))):
                rel=path.relative_to(root);dest=args.out/(name+'-changed-artifacts')/rel;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,dest);changes.append(dict(path=str(rel),original_sha256=old.get(str(rel)),mutant_sha256=C.digest(path)))
        receipts.append(dict(name=name,expected_rejection=expected,actual_rejection=error,changed_artifacts=changes))
        shutil.rmtree(root);print('REJECTED',name,error)
    # Pure source/condition checks do not require copying immutable artifacts.
    checks=[('unreviewed-pair',lambda:C.candidate_pins({C.CORE:[C.BASELINE_CORE_SHA,'1'*64]}),'reviewed changed-core SHA pair is invalid'),
            ('added-cpu-pair',lambda:C.candidate_pins({**{C.CORE:[C.BASELINE_CORE_SHA,C.CANDIDATE_CORE_SHA]},'rtl/core/e203_cpu.v':['2'*64,'3'*64]}),'only one reviewed LinearAutoGroupCore.sv SHA pair is allowed')]
    for name,operation,expected in checks:
        error=None
        try:operation()
        except ValueError as exc:error=str(exc)
        assert error is not None and expected in error,(name,error)
        receipts.append(dict(name=name,expected_rejection=expected,actual_rejection=error,changed_artifacts=[]));print('REJECTED',name,error)
    result=dict(schema='s3-bias-demand-verifier-corruption-tests-v1',status='ALL_EXPECTED_REJECTIONS',
        scope='atomic replacement of copied evidence; no native simulation; no original artifact mutation',
        positive_status=positive['status'],positive_result_sha256=C.digest(args.candidate),
        positive_layers=selected,verifier_sha256=C.digest(HERE/'compare_bias_demand.py'),
        inherited_fixture_helper_sha256=C.digest(OLD_TEST),cases=receipts)
    (args.out/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('BIAS_DEMAND_COMPARATOR_NEGATIVES_PASS',len(receipts))


if __name__=='__main__':main()
