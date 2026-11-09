#!/usr/bin/env python3
"""Revalidate moved saved campaigns without modifying them or simulating.

Campaign/result arguments are explicit archive-relative mappings. The stored
absolute command paths inside their original result files are left untouched.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path,PurePosixPath
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('relocated_bias_demand_verifier',HERE/'compare_bias_demand.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)


def archive_file(root,relative):
    p=PurePosixPath(relative)
    C.require(relative and not p.is_absolute() and '..' not in p.parts,'unsafe archive-relative path')
    path=root/relative
    C.require(path.is_file() and not path.is_symlink() and root in path.resolve().parents,
              'missing/unsafe relocated archive file: '+relative)
    return path


def comparable(result):
    # Every result field is retained except the running verifier's physical
    # location and two current result_path fields. Artifacts/source/firmware,
    # original identities/conditions, numerical coverage, raw timing, work and
    # complete per-layer/totals structures must remain byte-for-byte JSON equal.
    output={k:v for k,v in result.items() if k not in ('verifier','baseline_identity','candidate_identity')}
    for key in ('baseline_identity','candidate_identity'):
        output[key]={k:v for k,v in result[key].items() if k!='result_path'}
    output['verifier']={k:v for k,v in result['verifier'].items() if k not in ('path','inherited_loader_path')}
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--baseline',required=True,help='archive-relative original packed-full12 result.json')
    parser.add_argument('--pilot',required=True,help='archive-relative real layer0 candidate result.json')
    parser.add_argument('--full12',help='archive-relative real full12 candidate result.json')
    parser.add_argument('--saved-pilot',type=Path,default=HERE/'pilot-task0-comparison-final.json')
    parser.add_argument('--saved-full12',type=Path,default=HERE/'full12-comparison.json')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    try:
        archive=args.archive.resolve();C.require(archive.is_dir(),'archive root is missing')
        baseline=archive_file(archive,args.baseline)
        pairs=C.read_json(HERE/'reviewed-sourcepairs.json')
        requests=[('pilot',args.pilot,args.saved_pilot,[0])]
        if args.full12:requests.append(('full12',args.full12,args.saved_full12,None))
        receipts=[]
        for name,relative,saved_path,layers in requests:
            candidate=archive_file(archive,relative);saved=C.read_json(saved_path)
            fresh=C.verify(baseline,candidate,pairs,layers)
            C.require(comparable(fresh)==comparable(saved),name+' relocated comparison differs from saved strict result')
            receipts.append(dict(campaign=name,original_saved_comparison_sha256=C.digest(saved_path),
                baseline_archive_relative=args.baseline,candidate_archive_relative=relative,
                all_fields_equal_except_current_paths=True,
                compared_original_layers=fresh['layer_selection']['compared'],totals=fresh['totals'],
                source_changes=fresh['source_changes'],firmware_identity=fresh['firmware_identity'],
                baseline_result_sha256=C.digest(baseline),candidate_result_sha256=C.digest(candidate)))
        result=dict(schema='s3-bias-demand-relocated-revalidation-v1',status='RELOCATED_STRICT_REVALIDATION_PASS',
            scope='read-only original archived artifacts; no native simulation, source edit or result rewriting',
            archive_root=str(archive),script_sha256=C.digest(__file__),verifier_sha256=C.digest(HERE/'compare_bias_demand.py'),
            inherited_loader_sha256=C.LOADER_SHA,comparisons=receipts)
        with args.out.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
        print(result['status'],','.join(r['campaign'] for r in receipts));return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration,AttributeError) as error:
        print('RELOCATED_REVALIDATION_REJECTED:',error,file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
