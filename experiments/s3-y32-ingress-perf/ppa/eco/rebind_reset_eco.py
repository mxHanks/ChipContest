#!/usr/bin/env python3
"""Rebind a sealed reset ECO package to actual next-seed map bytes, no EDA.

The original package stays untouched. All declared source bytes are verified;
17 reset roots, original receiver catalogue, exact macro names and group IDs
are retained while the old sealed planner reparses the new source map.
"""
import argparse,collections,gzip,hashlib,importlib.util,io,json,shutil,sys
from pathlib import Path
sys.dont_write_bytecode=True


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_package(directory):
    directory=Path(directory).resolve();seal=directory/'package-files.json';files=json.loads(seal.read_text())
    require({'reset_eco_plan.py','reset-eco-plan.json.gz','run_reset_eco_stage.py','pt_reset_eco.tcl'}<=set(files),'not sealed reset ECO tools/plan')
    for name,digest in files.items():
        rel=Path(name);require(not rel.is_absolute()and'..'not in rel.parts,'unsafe package member')
        path=directory/rel;require(path.is_file()and not path.is_symlink()and sha(path)==digest,'sealed reset package member drift: '+name)
    extras=[p.relative_to(directory).as_posix()for p in directory.rglob('*')if p.is_file()and'__pycache__'not in p.parts and p.name!='package-files.json'and p.relative_to(directory).as_posix()not in files]
    require(not extras,'unsealed ordinary files in old package: '+repr(extras))
    spec=importlib.util.spec_from_file_location('sealed_reset_eco_planner',directory/'reset_eco_plan.py');planner=importlib.util.module_from_spec(spec);spec.loader.exec_module(planner)
    plan=json.loads(gzip.decompress((directory/'reset-eco-plan.json.gz').read_bytes()));planner.validate(plan)
    return directory,files,plan,planner


def rebind(package,source_map,expected_sha,out):
    source,files,old,planner=load_package(package);source_map=Path(source_map).resolve();out=Path(out)
    require(source_map.is_file()and not source_map.is_symlink()and sha(source_map)==expected_sha,'actual seed map SHA does not match explicit expected identity')
    original_receivers=old.get('original_receiver_catalogue',old['receivers'])
    require(old.get('original_receiver_catalogue')is not None or not old['removed_original_reset_receivers'],'old plan omitted original deleted receiver identities; cannot reconstruct original catalogue')
    require(len({r['pin']for r in original_receivers})==len(original_receivers),'duplicate original receiver catalogue')
    byroot=collections.defaultdict(list)
    for group in old['groups']:byroot[group['net_id']].append(json.loads(json.dumps(group)))
    electrical=dict(mapped_sha256=planner.ORIGINAL,nets=[dict(net_id=r['net_id'],driver=r['driver'],reference=r['reference'],asynchronous_reset_net=True,groups=byroot[r['net_id']])for r in old['roots']])
    diagnostic=dict(original_mapped_sha256=planner.ORIGINAL,receivers=original_receivers)
    new=planner.build_static_plan(electrical,diagnostic,expected_sha,old['required_margin_ns'],source_map=source_map);planner.validate(new)
    require(new['original_SRAM_instances']==old['original_SRAM_instances'],'rebind changed original353 SRAM instance set')
    require([(r['net_id'],r['driver'],r['reference'])for r in new['roots']]==[(r['net_id'],r['driver'],r['reference'])for r in old['roots']],'rebind changed exact17 reset roots')
    require({g['id']for g in new['groups']}<={g['id']for g in old['groups']},'rebind invented new group IDs')
    require({r['pin']for r in new['receivers']}<={r['pin']for r in original_receivers},'rebind invented reset receivers')
    semantic_self_equal=None
    if expected_sha==old['seed_mapped_sha256']:
        compare={k:v for k,v in old.items()if k not in {'rebind_provenance','original_receiver_catalogue'}}
        require(new==compare,'same-map rebind does not reproduce old semantic plan');semantic_self_equal=True
    provenance=dict(schema='ingress1064-reset-eco-real-map-rebind-v1',old_package_sha256=sha(source/'package-files.json'),old_plan_compressed_sha256=sha(source/'reset-eco-plan.json.gz'),
        old_seed_mapped_sha256=old['seed_mapped_sha256'],new_seed_mapped_sha256=expected_sha,source_map_bytes=source_map.stat().st_size,
        same_map_semantic_plan_identical=semantic_self_equal,original_receiver_catalogue_sha256=hashlib.sha256(json.dumps(original_receivers,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        old_groups=len(old['groups']),new_groups=len(new['groups']),old_receiver_count=len(old['receivers']),new_receiver_count=len(new['receivers']),
        actual_map_reparsed=True,qualification=False,physical_pulse_signoff='UNRESOLVED')
    new['original_receiver_catalogue']=original_receivers;new['rebind_provenance']=provenance
    payload={mode:planner.emit(new,mode)for mode in ['probe','split','reload']}
    out.mkdir(mode=0o700,parents=True,exist_ok=False)
    for name in files:
        if name=='reset-eco-plan.json.gz':continue
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
    shutil.copyfile(Path(__file__).resolve(),out/'rebind_reset_eco.py')
    # Python3.6 on the native host lacks gzip.compress(mtime=...).
    stream=io.BytesIO()
    with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:
        compressed.write(json.dumps(new,sort_keys=True,separators=(',',':')).encode()+b'\n')
    (out/'reset-eco-plan.json.gz').write_bytes(stream.getvalue())
    (out/'rebind-provenance.json').write_text(json.dumps(provenance,sort_keys=True,indent=2)+'\n')
    manifest={p.relative_to(out).as_posix():sha(p)for p in sorted(out.rglob('*'))if p.is_file()}
    (out/'package-files.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return dict(status='SEALED_RESET_ECO_REBOUND_TO_ACTUAL_MAP_NOT_NATIVE_EXECUTED',out=str(out),package_sha256=sha(out/'package-files.json'),
        seed_mapped_sha256=expected_sha,roots=len(new['roots']),groups=len(new['groups']),receivers=len(new['receivers']),preserved_original_SRAM=len(new['original_SRAM_instances']),
        same_map_semantic_plan_identical=semantic_self_equal,generated_tcl_sha256={m:hashlib.sha256(b).hexdigest()for m,b in payload.items()},qualification=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,required=True);p.add_argument('--seed-map',type=Path,required=True)
    p.add_argument('--expected-seed-mapped-sha256',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    print(json.dumps(rebind(a.package,a.seed_map,a.expected_seed_mapped_sha256,a.out),sort_keys=True))


if __name__=='__main__':
    try:main()
    except(OSError,ValueError,KeyError)as error:print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
