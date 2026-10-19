#!/usr/bin/env python3
"""Audit official SRAM input files by purpose; never certify a macro or PPA.

This separate intake preserves accepted development producer/source identities.
It does not change the frozen backend selector, load code, compile Verilog, or
promote OFFICIAL_MACRO to READY. Actual module/port/timing checks remain gates.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import sys
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import sram_evidence as E

STAGES=('simulation','synthesis','timing','ppa')
KEYS={'schema','logical_adapter_module','provenance','pin_specification',
      'adapter_sources','functional_sources','synthesis_sources','liberty','area_table'}
REQUIRED={
    'simulation':('provenance','pin_specification','adapter_sources','functional_sources'),
    'synthesis':('provenance','pin_specification','adapter_sources','synthesis_sources','setup'),
    'timing':('provenance','pin_specification','adapter_sources','synthesis_sources','setup','hold'),
    'ppa':('provenance','pin_specification','adapter_sources','synthesis_sources','setup','hold','power','area_table'),
}


def inspect_package(root, manifest_path):
    root=Path(root).resolve();manifest_path=Path(manifest_path).resolve()
    issues=[];roles={};dependencies={}
    def issue(role,status,message):
        issues.append({'role':role,'status':status,'message':message})
    try:
        data=json.loads(manifest_path.read_text())
        if not isinstance(data,dict) or set(data)!=KEYS:
            raise ValueError('manifest must have exactly the documented explicit fields')
        if data['schema']!='kwt-official-sram-package-v1':raise ValueError('unsupported official input schema')
        if data['logical_adapter_module']!='kwt_official_sram_adapter':raise ValueError('logical adapter module differs from wrapper contract')
    except (OSError,ValueError) as exc:
        return {'status':'FAIL','stages':{s:{'status':'FAIL','source_files':[]} for s in STAGES},
                'dependencies':[],'issues':[{'role':'manifest','status':'FAIL','message':str(exc)}],
                'official_validation':'NOT_RUN','official_ppa':'BLOCKED',
                'scope':'input file inventory only; invalid manifest rejected'}

    def file_ref(value,role,suffixes=None):
        if value is None:
            issue(role,'BLOCKED','file reference not provided');return None
        if not isinstance(value,dict) or 'path' not in value or set(value)-{'path','sha256'}:
            issue(role,'FAIL','file reference needs only path and sha256');return None
        name=value['path'];expected=value.get('sha256')
        if name is None:
            issue(role,'BLOCKED','file path not provided');return None
        if not isinstance(name,str) or not name:
            issue(role,'FAIL','file path must be a relative string');return None
        if '\x00' in name:
            issue(role,'FAIL','file path contains a NUL byte');return None
        relative=PurePosixPath(name)
        if relative.is_absolute() or any(part in ('.','..') for part in name.split('/')) or '\\' in name:
            issue(role,'FAIL','file path must stay under the controlled project root');return None
        try:
            path=root
            for component in relative.parts:
                path=path/component
                if path.is_symlink():
                    issue(role,'FAIL','symlink technology/source input is not allowed');return None
            if not path.resolve().is_relative_to(root):
                issue(role,'FAIL','file escapes controlled root');return None
        except (OSError,ValueError) as exc:
            issue(role,'FAIL','invalid or inaccessible input path: '+str(exc));return None
        if suffixes and path.suffix.lower() not in suffixes:
            issue(role,'FAIL','wrong file type for this role');return None
        if expected in (None,''):
            issue(role,'BLOCKED','expected source SHA256 not provided');return None
        if not isinstance(expected,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',expected):
            issue(role,'FAIL','invalid SHA256 format');return None
        try:
            if not path.exists():
                issue(role,'BLOCKED','declared input has not arrived: '+name);return None
            if not path.is_file():
                issue(role,'FAIL','declared input is not a regular file');return None
            record=E.record(path)
            if record['size_bytes']==0:
                issue(role,'FAIL','empty input file');return None
            if record['sha256']!=expected.lower():
                issue(role,'FAIL','input SHA256 mismatch: '+name);return None
        except OSError as exc:
            issue(role,'FAIL','input could not be read: '+str(exc));return None
        if record['path'] in dependencies and dependencies[record['path']]!=record:
            issue(role,'FAIL','same file changed between role references');return None
        dependencies[record['path']]=record
        return record

    def file_list(value,role,suffixes):
        roles[role]=[]
        if not isinstance(value,list):
            issue(role,'FAIL','file set must be an explicit list');return
        if not value:
            issue(role,'BLOCKED','required file set not provided');return
        seen=set()
        for ref in value:
            item=file_ref(ref,role,suffixes)
            if item:
                if item['path'] in seen:issue(role,'FAIL','duplicate path within file role')
                seen.add(item['path']);roles[role].append(item)

    provenance=data['provenance'];roles['provenance']=[]
    if not isinstance(provenance,dict) or set(provenance)!={'provider','release','document'}:
        issue('provenance','FAIL','provenance needs provider, release and source document')
    else:
        for label in ('provider','release'):
            value=provenance[label]
            if value is None or isinstance(value,str) and not value.strip():issue('provenance','BLOCKED',label+' is not provided')
            elif not isinstance(value,str):issue('provenance','FAIL',label+' must be a string')
        ref=file_ref(provenance['document'],'provenance')
        if ref:roles['provenance'].append(ref)
    for role,suffix in (('pin_specification',None),('area_table',{'.json','.csv','.tsv'})):
        ref=file_ref(data[role],role,suffix);roles[role]=[ref] if ref else []
    for role in ('adapter_sources','functional_sources','synthesis_sources'):
        file_list(data[role],role,{'.v','.sv'})
    libs=data['liberty']
    if not isinstance(libs,dict) or set(libs)!={'setup','hold','power'}:
        for role in ('setup','hold','power'):
            roles[role]=[];issue(role,'FAIL','Liberty must explicitly name setup, hold and power roles')
    else:
        for role in ('setup','hold','power'):file_list(libs[role],role,{'.lib'})

    stages={}
    for stage in STAGES:
        required=REQUIRED[stage]
        selected=[r['path'] for role in ('adapter_sources','functional_sources' if stage=='simulation' else 'synthesis_sources') for r in roles[role]]
        stage_issues=[x for x in issues if x['role'] in required]
        if len(set(selected))!=len(selected):
            duplicate={'role':stage,'status':'FAIL','message':'duplicate RTL in selected compilation file set'}
            issues.append(duplicate);stage_issues.append(duplicate)
        status='FAIL' if any(x['status']=='FAIL' for x in stage_issues) else 'BLOCKED' if stage_issues else 'FILES_VERIFIED'
        stages[stage]={'status':status,'source_files':selected if status!='FAIL' else [],'required_roles':list(required),
                       'issues':stage_issues,'technology_files':{role:roles[role] for role in required if role in ('setup','hold','power','area_table')}}
    status='FAIL' if any(x['status']=='FAIL' for x in issues) else 'PASS' if all(s['status']=='FILES_VERIFIED' for s in stages.values()) else 'BLOCKED'
    return {'status':status,'stages':stages,'dependencies':sorted(dependencies.values(),key=lambda x:x['path']),
            'issues':issues,'logical_adapter_module':data['logical_adapter_module'],
            'scope':'file identity, purpose classification and controlled paths only; no HDL/module/function/technology authenticity/PVT acceptance',
            'official_validation':'NOT_RUN','official_ppa':'BLOCKED',
            'backend_selector_updated':False,'unverified_checks':['actual adapter/module/port elaboration','macro function/latency/collision','RTL/Golden bit agreement','macro/standard-cell PVT, units, timing arcs and area/power correctness']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'configs/official-sram-package.json')
    parser.add_argument('--stage',choices=('all',*STAGES),default='all')
    args=parser.parse_args()
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-official-sram-inputs-'+uuid.uuid4().hex[:8]);out.mkdir(parents=True)
    try:manifest_before=E.record(args.manifest)
    except OSError:manifest_before=None
    result=inspect_package(ROOT,args.manifest)
    stage_status=result['status'] if args.stage=='all' else result['stages'][args.stage]['status']
    status='PASS' if stage_status=='FILES_VERIFIED' else stage_status
    report={'schema':'kwt-official-sram-input-audit-v1',**result,'status':status,'requested_stage':args.stage,'inventory_status':result['status']}
    deps=[Path(__file__),Path(E.__file__),args.manifest,*[Path(r['path']) for r in result['dependencies']]]
    try:
        report['identity']=E.source_identity(deps,{'stage':args.stage,'scope':'intake files only'},out/'source_identity.json')
        E.verify_records(report['identity']['inputs']+result['dependencies']+([manifest_before] if manifest_before else []))
    except (OSError,ValueError) as exc:report.update(status='FAIL',error=str(exc))
    E.write_json(out/'result.json',report)
    print('KWT_OFFICIAL_SRAM_INPUT_AUDIT_COMPLETE')
    print(json.dumps({'status':report['status'],'scope':'input file inventory only','stage':args.stage,'report':str(out/'result.json'),'official_validation':'NOT_RUN'}))
    return 0 if report['status']=='PASS' else 2 if report['status']=='BLOCKED' else 1


if __name__=='__main__':raise SystemExit(main())
