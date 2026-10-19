#!/usr/bin/env python3
"""Narrow read-only build recovery for legacy bytes/size_bytes record spelling.

The frozen producer and its failed reuse report remain untouched. All of its
native command, source, recipe, probe and binary checks are reused. Only file
record representation is normalized; differing hashes or lengths still fail.
No synthesis or compilation is run here.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).parent))
import run_sram_mapped as P
E=P.E
ROOT=P.ROOT


def compatible_record_map(records):
    normalized={}
    for item in records:
        if not {'path','sha256'}<=set(item) or not set(item)<={'path','sha256','bytes','size_bytes','project_relative_path'}:
            raise ValueError('unsupported file record schema')
        sizes=[item[name] for name in ('bytes','size_bytes') if name in item]
        if (not sizes or any(type(size) is not int or size<0 for size in sizes) or len(set(sizes))!=1 or
            not re.fullmatch(r'[0-9a-f]{64}',item['sha256'])):
            raise ValueError('missing or conflicting file record size/hash')
        path=str(Path(item['path']).resolve())
        if 'project_relative_path' in item:
            relative=Path(item['project_relative_path'])
            if relative.is_absolute() or '..' in relative.parts or str((ROOT/relative).resolve())!=path:
                raise ValueError('relative source alias differs from actual path')
        value={'path':path,'sha256':item['sha256'],'size_bytes':sizes[0]}
        if path in normalized and normalized[path]!=value:
            raise ValueError('conflicting file identity: '+path)
        normalized[path]=value
    return normalized


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-report',type=Path,required=True)
    parser.add_argument('--reuse-build',type=Path,required=True)
    parser.add_argument('--vectors-dir',type=Path,default=ROOT/'sim/vectors/kwt-silence-v1')
    parser.add_argument('--tasks',type=int,choices=range(1,13),default=12)
    parser.add_argument('--timeout',type=int,default=900)
    args=parser.parse_args()
    if args.timeout<=0:parser.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-mapped-replay-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'kwt-mapped-replay-reader-v1','status':'RUNNING','phase':'validate_original_build',
        'scope':'same reference zero-delay mapped binary; common logical SRAM; no formal/official timing claim',
        'normalization':'bytes/size_bytes require equal SHA/length; optional project_relative_path must resolve to same file',
        'synthesis':'REUSED','compilation':'REUSED','official_ppa':'BLOCKED','four_state_full_netlist':'NOT_RUN',
        'configuration':{'tasks':args.tasks,'top':'tb_kwt_icb_mapped_pair','jobs':1},'inputs':[],'commands':[]}
    E.write_json(out/'result.json',report)
    try:
        mapping_path=args.mapping_report.resolve();mapping=json.loads(mapping_path.read_text())
        if mapping.get('status')!='PASS' or mapping.get('reference_logic_mapping')!='PASS' or mapping['configuration']['top']!='kwt_icb_slave_sram':
            raise ValueError('accepted full-interface mapping required')
        E.verify_records(mapping['inputs'])
        directory=Path(mapping['run_directory']);net=directory/'mapped.json';verilog=directory/'mapped.v'
        map_outputs=compatible_record_map(mapping['outputs'])
        E.verify_records([map_outputs[str(p)] for p in (net,verilog)])
        shapes={cell['type']:(cell['width'],cell['depth']) for cell in mapping['structure']['opaque_cells']}
        top=json.loads(net.read_text())['modules']['kwt_icb_slave_sram']
        if sum(c['type'] in shapes for c in top['cells'].values())!=72:raise ValueError('opaque SRAM count differs')
        report['observables']=P.mapped_observable_report(top)
        backend=P.SOURCES.select_backend('behavioral','simulation')
        sources=[*backend['sources'],ROOT/'soc/kwt_icb_slave_sram.sv',ROOT/'sim/kwt_icb_pair_checker.sv',ROOT/'sim/tb_kwt_icb_mapped_pair.sv']
        tools={name:shutil.which(name) for name in ('yosys','verilator')}
        if not all(tools.values()):raise FileNotFoundError('source env/activate.sh')
        lib=ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib'
        if E.record(lib)['sha256']!=P.MAPPING.LIB_SHA256:raise ValueError('reference Liberty differs')
        # Current producer dependencies, required independently of a report's
        # self-declared inventory; this reader is additionally frozen below.
        dependencies=[Path(P.__file__),Path(E.__file__),Path(P.SOC.__file__),Path(P.L.__file__),
            Path(P.EXPORTED.__file__),Path(P.L.COMMON.__file__),Path(P.MAPPING.__file__),
            *backend['dependencies'],*sources,mapping_path,net,verilog,lib,ROOT/'model/fixed16_acc48.py',
            Path(P.ALIAS.__file__),ROOT/'sim/fixtures/kwt_mapped_alias.sv',
            Path(P.CHECKER.__file__),ROOT/'sim/fixtures/tb_kwt_icb_pair_checker.sv',
            *map(Path,tools.values()),ROOT/'.tools/synth/usr/bin/yosys',
            ROOT/'.tools/eda/usr/bin/verilator',ROOT/'.tools/eda/usr/bin/verilator_bin']
        original=args.reuse_build.resolve()
        report['identity']=E.source_identity([Path(__file__),*dependencies,original],report['configuration'],out/'source_identity.json')
        report['inputs']=list(report['identity']['inputs'])
        (out/'mapped_top.v').write_text(P.rename_mapped_top(verilog.read_text()))
        (out/'logical_macros.sv').write_text(P.logical_macro_models(shapes))
        (out/'mapped_alias.vlt').write_text(P.mapped_alias_configuration())
        (out/'cells.ys').write_text('\n'.join(['read_liberty -ignore_miss_func -ignore_miss_dir "'+str(lib)+'"',
            'proc','opt_clean','write_verilog -noattr standard_cells.v','log KWT_SRAM_FUNCTIONAL_CELLS_COMPLETE','']))
        generated={name:E.record(out/name) for name in ('mapped_top.v','logical_macros.sv','mapped_alias.vlt','cells.ys')}
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            # Exact compatibility adapter around an immutable production
            # validator. This process never edits its source or old reports.
            P._record_map=compatible_record_map
            accepted=P.accepted_reused_build(original,mapping_path,dependencies,sources,tools,generated)
            binary=accepted['binary'];report['binary']=binary
            report['original_build']=E.record(original)
            report['inputs'] += accepted['inputs']+list(generated.values())
            # Rehash the canonical union now, before consuming the binary.
            canonical=compatible_record_map(report['inputs'])
            E.verify_records(canonical.values())
            model=P.L.load_module('kwt_mapped_replay_numeric',ROOT/'model/fixed16_acc48.py')
            manifest,provenance,images=P.EXPORTED.validate_export(args.vectors_dir.resolve(),model,source_root=ROOT/'vendor/kwt1-237e4097')
            report['inputs'] += provenance+P.SOC.stage_verified_vectors(images[:args.tasks],out/'vectors')
            report['vector_scope']=manifest['input']['kind']
            report['workload_sha256']=hashlib.sha256(b''.join(image[k] for image in images[:args.tasks] for k in ('x','w','bias','y'))).hexdigest()
            report['phase']='simulation';E.write_json(out/'result.json',report)
            command=E.run_command([binary['path'],f'+VECTORS={out/"vectors"}',f'+TASKS={args.tasks}'],out,out/'run.log',args.timeout,1)
            report['commands'].append(command)
            error=E.completion_error(command,[])
            if error:raise ValueError('native replay rejected: '+error)
            report['measurement']=P.validate_mapped_log(Path(command['log']['path']).read_text(),args.tasks)
            report.update(status='PASS',phase='complete')
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(compatible_record_map(report['inputs']).values())
        except (OSError,ValueError,KeyError) as exc:report.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
