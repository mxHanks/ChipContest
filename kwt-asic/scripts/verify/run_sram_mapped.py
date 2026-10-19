#!/usr/bin/env python3
"""Reference mapped standard-logic / RTL trace and Golden replay.

The exact accepted mapped.v is used, changing only its top module name.
Opaque SRAM instances receive the validated logical behavioral contract;
standard-cell functions are emitted from the same reference Liberty by Yosys.
This is zero-delay functional simulation, never official macro or timing proof.
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
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
sys.path.insert(0,str(ROOT/'scripts/synth'))
import sram_evidence as E
import sram_sources as SOURCES
import run_sram_soc as SOC
import run_linear as L
import run_exported_linear as EXPORTED
import run_memory_blackbox as MAPPING
import diagnose_mapped_alias as ALIAS
import run_mapped_checker_tests as CHECKER


def rename_mapped_top(text):
    pattern=r'\bmodule\s+kwt_icb_slave_sram\s*\('
    if len(re.findall(pattern,text))!=1:raise ValueError('expected exactly one mapped ICB top')
    return re.sub(pattern,'module kwt_icb_slave_sram_mapped(',text,count=1)


def mapped_alias_configuration():
    # Qualified by a real-tool fixture. No lint suppression or gate rewrite.
    return '`verilator_config\nsplit_var -module "kwt_icb_slave_sram_mapped" -var "y_snapshot"\n'


def accept_mapped_compile(text):
    forbidden=('UNOPTFLAT','SPLITVAR','UNSUPPORTED','PINMISSING','MODDUP','MULTIDRIVEN','IMPLICIT')
    if any(re.search(r'^%Warning-'+name+r':',text,re.M) for name in forbidden):
        raise ValueError('mapped compile contains unresolved structural/model diagnostic')


def _record_map(records):
    result={}
    for record in records:
        path=str(Path(record['path']).resolve())
        if path in result and result[path]!=record:raise ValueError('conflicting input identity: '+path)
        result[path]=record
    return result


def require_input_identity(value,required_paths,identity_path=None):
    """A valid self-declared hash list must also contain our mandatory sources."""
    reported=value.get('identity',{})
    if reported.get('schema')!='kwt-sram-source-identity-v1':raise ValueError('source identity missing')
    # Existing tiny probes shared their report/identity input list, then
    # appended binaries. The original manifest was durably saved before that
    # append. Validate that canonical material rather than trusting its copy.
    identity=json.loads(Path(identity_path).read_text()) if identity_path is not None else reported
    if (identity.get('schema')!='kwt-sram-source-identity-v1' or
            identity.get('source_id')!=reported.get('source_id') or
            identity.get('configuration')!=reported.get('configuration')):
        raise ValueError('canonical source identity differs from reported identity')
    material={key:identity[key] for key in ('schema','configuration','inputs')}
    if value.get('configuration')!=identity['configuration']:raise ValueError('source identity configuration differs')
    digest=hashlib.sha256(json.dumps(material,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if identity.get('source_id')!=digest:raise ValueError('source identity digest differs')
    records=_record_map(value.get('inputs',[]));sources=_record_map(identity['inputs'])
    if any(records.get(path)!=record for path,record in sources.items()):
        raise ValueError('source identity missing from consumed inputs')
    reported_sources=_record_map(reported['inputs'])
    if (any(reported_sources.get(path)!=record for path,record in sources.items()) or
            any(records.get(path)!=record for path,record in reported_sources.items())):
        raise ValueError('reported source inputs differ from canonical consumed identity')
    for path in required_paths:
        current=E.record(path)
        if sources.get(current['path'])!=current:raise ValueError('required source identity missing or stale: '+str(path))
    E.verify_records(value['inputs'])
    return records


def _require_records(value,required):
    records=_record_map(value['inputs'])
    for record in required:
        if records.get(record['path'])!=record:raise ValueError('required consumed identity missing: '+record['path'])


def _native_by_name(value,expected):
    commands=value['commands'];native={Path(c['log']['path']).stem:c for c in commands}
    if len(native)!=len(commands) or set(native)!=set(expected):
        raise ValueError('native command coverage missing, duplicate or unexpected')
    return native


def _expect_argv(command,argv,cwd=None):
    if command.get('argv')!=list(map(str,argv)) or (cwd is not None and Path(command.get('cwd','')).resolve()!=Path(cwd).resolve()):
        raise ValueError('native command differs from required source/variant invocation')


def accepted_alias_report(path):
    path=Path(path).resolve();out=path.parent;value=json.loads(path.read_text())
    if value.get('schema')!='kwt-mapped-alias-diagnostic-v1' or value.get('status')!='PASS':
        raise ValueError('alias fixture has not passed')
    tool=ROOT/'.tools/bin/verilator';fixture=ROOT/'sim/fixtures/kwt_mapped_alias.sv'
    config=out/'split_alias.vlt';docs=ROOT/'.tools/eda/usr/share/doc/verilator/html'
    require_input_identity(value,[Path(ALIAS.__file__),Path(E.__file__),fixture,tool,
        ROOT/'.tools/eda/usr/bin/verilator',ROOT/'.tools/eda/usr/bin/verilator_bin',config,
        *[docs/name for name in ('extensions.html','warnings.html','exe_verilator.html')]],out/'source_identity.json')
    if config.read_text()!='`verilator_config\nsplit_var -module "kwt_mapped_alias" -var "y_snapshot"\n':
        raise ValueError('alias probe used a different split configuration')
    variants={'baseline':[],'metacomment':['+define+KWT_ALIAS_SPLIT'],'configuration':[str(config)]}
    native=_native_by_name(value,['version',*[stage+'-'+variant for variant in variants for stage in ('lint','compile','run')]])
    _expect_argv(native['version'],[tool,'--version'],ROOT)
    for command in native.values():
        error=E.completion_error(command,[])
        if error:raise ValueError('alias evidence rejected: '+error)
    common=[tool,'--timing','--assert','-Wno-fatal','--top-module','tb_kwt_mapped_alias']
    if set(value['cases'])!=set(variants):raise ValueError('incomplete alias variants')
    for name,extra in variants.items():
        _expect_argv(native['lint-'+name],[*common,'--lint-only','--Mdir',out/('lint-'+name),*extra,fixture],ROOT)
        _expect_argv(native['compile-'+name],[*common,'--binary','--Mdir',out/('obj-'+name),'-o','simulation','-j','2','--threads','1',*extra,fixture],ROOT)
        binary=out/('obj-'+name)/'simulation';_require_records(value,[E.record(binary)])
        _expect_argv(native['run-'+name],[binary],ROOT)
        lint=ALIAS.accept_lint(Path(native['lint-'+name]['log']['path']).read_text(),name=='baseline')
        ALIAS.accept_lint(Path(native['compile-'+name]['log']['path']).read_text(),name=='baseline')
        log=Path(native['run-'+name]['log']['path']).read_text()
        if len(re.findall(ALIAS.MARKER,log,re.M))!=1 or len(re.findall(r'^- .*\$finish$',log,re.M))!=1:
            raise ValueError('alias behavior completion missing')
        expected={'lint':lint,'behavior':{'status':'PASS','checks':48,'positive_loads':4,
                  'negative_loads':3,'holds':7,'asynchronous_resets':2}}
        if value['cases'][name]!=expected:raise ValueError('alias metrics differ from native behavior')
    return value


def accepted_checker_report(path):
    path=Path(path).resolve();out=path.parent;value=json.loads(path.read_text())
    if value.get('schema')!='kwt-mapped-checker-tests-v1' or value.get('status')!='PASS':
        raise ValueError('four-state checker has not passed')
    tools={name:ROOT/'.tools/bin'/name for name in ('iverilog','vvp')}
    sources=[ROOT/'sim/kwt_icb_pair_checker.sv',ROOT/'sim/fixtures/tb_kwt_icb_pair_checker.sv']
    require_input_identity(value,[Path(CHECKER.__file__),Path(E.__file__),*sources,*tools.values(),
        ROOT/'.tools/eda/usr/bin/iverilog',ROOT/'.tools/eda/usr/bin/vvp'],out/'source_identity.json')
    expected_cases=set(CHECKER.POSITIVES)|set(CHECKER.NEGATIVES)
    if len(value['cases'])!=len(expected_cases) or {x['case'] for x in value['cases']}!=expected_cases:
        raise ValueError('checker case coverage incomplete')
    native=_native_by_name(value,['version','compile',*[x[0] for x in CHECKER.POSITIVES.values()],
                                 *[x[0] for x in CHECKER.NEGATIVES.values()]])
    binary=out/'checker.vvp';_require_records(value,[E.record(binary)])
    _expect_argv(native['version'],[tools['iverilog'],'-V'],ROOT)
    _expect_argv(native['compile'],[tools['iverilog'],'-g2012','-s','tb_kwt_icb_pair_checker','-o',binary,*sources],ROOT)
    for name in ('version','compile'):
        error=E.completion_error(native[name],[])
        if error:raise ValueError('checker preparation rejected: '+error)
    for case,(name,traces,commands,responses) in CHECKER.POSITIVES.items():
        _expect_argv(native[name],[tools['vvp'],binary,f'+CASE={case}'],ROOT)
        error=E.completion_error(native[name],[f'^CHECKER_FIXTURE_PASS case={case} traces={traces} commands={commands} responses={responses}$'])
        if error:raise ValueError('checker positive rejected: '+error)
    for case,(name,reason) in CHECKER.NEGATIVES.items():
        _expect_argv(native[name],[tools['vvp'],binary,f'+CASE={case}'],ROOT)
        CHECKER.accept_rejection(native[name],'MAPPED_CHECKER_'+reason)
    cases={entry['case']:entry for entry in value['cases']}
    for case,(name,traces,commands,responses) in CHECKER.POSITIVES.items():
        if cases[case]!={'case':case,'name':name,'status':'PASS','expectation':'known legal observer input',
                        'traces':traces,'accepted_commands':commands,'accepted_responses':responses}:
            raise ValueError('checker positive metrics differ')
    for case,(name,reason) in CHECKER.NEGATIVES.items():
        if cases[case]!={'case':case,'name':name,'status':'EXPECTED_REJECTION',
                        'expected_diagnostic':'MAPPED_CHECKER_'+reason,'native_exit_code':native[name]['exit_code']}:
            raise ValueError('checker rejection state differs')
    return value


def mapped_observable_report(top):
    required=('output_count','engine_busy','core_done_sticky','software_done','window_active','y_snapshot_last','rsp_pop_y')
    drivers={}
    for name,cell in top['cells'].items():
        for port,direction in cell['port_directions'].items():
            if direction=='output':
                for bit in cell['connections'][port]:
                    if isinstance(bit,int):drivers.setdefault(bit,set()).add((name,port,cell['type']))
    def describe(name):
        bits=top.get('netnames',{}).get(name,{}).get('bits',[])
        missing=[bit for bit in bits if isinstance(bit,int) and bit not in drivers]
        multiple=[bit for bit in bits if isinstance(bit,int) and len(drivers.get(bit,()))>1]
        return {'bits':bits,'undriven_bits':missing,'multiply_driven_bits':multiple,
                'driver_types':sorted({d[2] for bit in bits for d in drivers.get(bit,())})}
    states={name:describe(name) for name in required}
    for name,details in states.items():
        if not details['bits'] or details['undriven_bits'] or details['multiply_driven_bits']:
            raise ValueError('required mapped observable lacks a unique driver: '+name)
    return {'status':'PASS','scope':'connectivity of required TB state observations only',
            'required':states,'unused_aliases':{'engine_y_ready':describe('engine_y_ready')}}


def logical_macro_models(shapes):
    modules=[]
    if not shapes:raise ValueError('missing opaque SRAM shapes')
    for name,(width,depth) in sorted(shapes.items()):
        if width!=16 or depth not in (128,1024,4096) or re.search(r'\s',name):
            raise ValueError('unsupported opaque SRAM shape or name')
        aw=(depth-1).bit_length()
        modules.append(f'''module \\{name} (input clk,wr_en,rd_en,
input [{aw-1}:0] wr_addr,rd_addr,input [15:0] wr_data,output [15:0] rd_data);
wire unused_valid;
kwt_sram_1rw #(.WIDTH(16),.DEPTH({depth}),.BACKEND(0),.CHECKS(1)) storage
(.clk(clk),.rst_n(1'b1),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
 .rd_en(rd_en),.rd_addr(rd_addr),.rd_data(rd_data),.rd_valid(unused_valid));
endmodule
''')
    return '\n'.join(modules)


def validate_mapped_log(text,tasks):
    matches=re.findall(r'^MAPPED_TASK_PASS task=(\d+) outputs=(\d+)$',text,re.M)
    if [list(map(int,x)) for x in matches]!=[[i,25344] for i in range(tasks)]:
        raise ValueError('mapped per-task completion/count mismatch')
    suite=re.findall(r'^MAPPED_PAIR_PASS tasks=(\d+) outputs=(\d+) transactions=(\d+) trace_checks=(\d+)$',text,re.M)
    if len(suite)!=1:raise ValueError('mapped suite missing or duplicated')
    count,outputs,transactions,checks=map(int,suite[0])
    if count!=tasks or outputs!=tasks*25344 or min(transactions,checks)<=0:
        raise ValueError('mapped suite conservation mismatch')
    recovery=re.findall(r'^MAPPED_RECOVERY_PASS soft_aborts=(\d+) pending_resets=(\d+)$',text,re.M)
    protocol=re.findall(r'^MAPPED_PROTOCOL_PASS errors=(\d+) holds=(\d+) final_hi=(\d+) ack=(\d+) requests=(\d+) responses=(\d+)$',text,re.M)
    if recovery!=[('1','1')] or len(protocol)!=1:raise ValueError('mapped recovery/protocol completion missing')
    errors,holds,last_hi,ack,requests,responses=map(int,protocol[0])
    if (errors!=12 or holds!=24+811*tasks or last_hi!=tasks or ack!=tasks or
        responses!=transactions or requests!=responses+1 or
        transactions<(tasks+2)*46214+tasks*101376 or checks<transactions):
        raise ValueError('mapped protocol workload/handshake conservation mismatch')
    return {'tasks':count,'outputs':outputs,'transactions':transactions,'trace_checks':checks,
            'soft_aborts':1,'pending_response_resets':1,'error_cases':errors,'hold_checks':holds,
            'final_hi_holds':last_hi,'ack_holds':ack,'accepted_commands':requests,'accepted_responses':responses,
            'aborted_outputs':0}


def accepted_reused_build(path,mapping_path,required_paths,sources,tools,generated,_seen=None):
    """Validate the original compilation, not just an earlier PASS string.

    Task count and vectors are runtime inputs. All compiler sources, tools,
    model recipes, mapped logic and the executable must retain their identity.
    """
    path=Path(path).resolve();out=path.parent;seen=set() if _seen is None else set(_seen)
    if path in seen or len(seen)>=16:raise ValueError('cyclic or excessive reused build chain')
    seen.add(path);value=json.loads(path.read_text())
    if (value.get('schema')!='kwt-sram-mapped-functional-v1' or value.get('status')!='PASS'
            or value.get('phase')!='complete'):
        raise ValueError('reuse requires an accepted complete replay')
    require_input_identity(value,required_paths)
    config=value['configuration'];tasks=config.get('tasks')
    if (not isinstance(tasks,int) or isinstance(tasks,bool) or not 1<=tasks<=12 or
            config.get('top')!='tb_kwt_icb_mapped_pair' or config.get('jobs')!=2 or
            config.get('memory_model')!='validated logical 1RW behavior'):
        raise ValueError('reused build configuration is incompatible')
    mapping=E.record(mapping_path)
    if value.get('mapping_report')!=mapping:raise ValueError('reused build has different mapping')
    binary=E.record(value['binary']['path'])
    if binary!=value['binary']:raise ValueError('reused binary differs from recorded executable')
    _require_records(value,[mapping,binary])
    for name,validator in (('alias_probe',accepted_alias_report),('checker_probe',accepted_checker_report)):
        record=value[name];current=E.record(record['path'])
        if current!=record:raise ValueError('reused probe report changed')
        _require_records(value,[record]);validator(record['path'])
    commands=value['commands'];names=[Path(c['log']['path']).stem for c in commands]
    if not names or names[-1]!='run' or len(set(names))!=len(names):
        raise ValueError('reused native commands lack a unique final run')
    for command in commands:
        error=E.completion_error(command,[])
        if error:raise ValueError('reused build evidence rejected: '+error)
    _expect_argv(commands[-1],[binary['path'],f'+VECTORS={out/"vectors"}',f'+TASKS={tasks}'],out)
    validate_mapped_log(Path(commands[-1]['log']['path']).read_text(),tasks)
    if 'reused_build' in value:
        if names!=['run']:raise ValueError('reused replay contains unexpected compilation commands')
        origin=value['reused_build'];current=E.record(origin['path'])
        if current!=origin:raise ValueError('reused parent identity changed')
        _require_records(value,[origin])
        previous=accepted_reused_build(origin['path'],mapping_path,required_paths,sources,tools,generated,seen)
        if previous['binary']!=binary:raise ValueError('reused executable has no matching build origin')
    else:
        if not {'cells','compile','run'}.issubset(names) or set(names)-{'cells','compile','run','alias_probe','checker_probe'}:
            raise ValueError('reused build lacks original cell-model generation or compilation')
        native={Path(c['log']['path']).stem:c for c in commands}
        models=[out/name for name in ('mapped_top.v','logical_macros.sv','standard_cells.v','mapped_alias.vlt')]
        _require_records(value,[*[E.record(p) for p in models],E.record(out/'cells.ys')])
        for name,current in generated.items():
            previous=E.record(out/name)
            if any(previous[key]!=current[key] for key in ('sha256','size_bytes')):
                raise ValueError('reused generated logic/model recipe differs: '+name)
        if binary['path']!=str(out/'obj/simulation'):raise ValueError('reused executable is outside its compile output')
        _expect_argv(native['cells'],[tools['yosys'],'-Q','-s','cells.ys'],out)
        error=E.completion_error(native['cells'],[r'^KWT_SRAM_FUNCTIONAL_CELLS_COMPLETE$'])
        if error:raise ValueError('reused cell generation incomplete: '+error)
        _expect_argv(native['compile'],[tools['verilator'],'--binary','--timing','--assert','-Wno-fatal',
            '--top-module','tb_kwt_icb_mapped_pair','--Mdir',out/'obj','-o','simulation','-j','2','--threads','1',
            *sources,*models],out)
        accept_mapped_compile(Path(native['compile']['log']['path']).read_text())
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping-report',type=Path,required=True)
    parser.add_argument('--vectors-dir',type=Path,default=ROOT/'sim/vectors/kwt-silence-v1')
    parser.add_argument('--tasks',type=int,choices=range(1,13),default=1)
    parser.add_argument('--timeout',type=int,default=900)
    parser.add_argument('--alias-report',type=Path,help='reuse qualified tiny-tool probe; otherwise run it once')
    parser.add_argument('--checker-report',type=Path,help='reuse qualified four-state checker probe; otherwise run it once')
    parser.add_argument('--reuse-build',type=Path,help='accepted mapped replay result, same source/models/tools; tasks are runtime selected')
    args=parser.parse_args()
    if args.timeout<=0:parser.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-sram-mapped-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'kwt-sram-mapped-functional-v1','status':'RUNNING','phase':'prepare',
        'scope':'reference standard cells zero-delay functional replay; common logical 1RW SRAM models, not official macros or formal proof',
        'official_ppa':'BLOCKED','timing':'NOT_PROVEN_BY_SIMULATION','four_state_full_netlist':'NOT_RUN',
        'commands':[],'inputs':[],
        'configuration':{'tasks':args.tasks,'top':'tb_kwt_icb_mapped_pair','jobs':2,'memory_model':'validated logical 1RW behavior'}}
    def execute(argv,name,timeout,patterns=()):
        command=E.run_command(argv,out,out/(name+'.log'),timeout,2)
        report['commands'].append(command)
        E.write_json(out/'result.json',report)
        error=E.completion_error(command,list(patterns))
        if error:raise ValueError(name+' rejected: '+error)
        return command
    try:
        path=args.mapping_report.resolve();mapping=json.loads(path.read_text())
        if mapping.get('status')!='PASS' or mapping.get('reference_logic_mapping')!='PASS' or mapping['configuration']['top']!='kwt_icb_slave_sram':
            raise ValueError('require accepted full-interface mapped logic')
        E.verify_records(mapping['inputs'])
        directory=Path(mapping['run_directory']);net=directory/'mapped.json';verilog=directory/'mapped.v'
        records={x['path']:x for x in mapping['outputs']}
        E.verify_records([records[str(p)] for p in (net,verilog)])
        netlist=json.loads(net.read_text());top=netlist['modules']['kwt_icb_slave_sram']
        shapes={cell['type']:(cell['width'],cell['depth']) for cell in mapping['structure']['opaque_cells']}
        if sum(c['type'] in shapes for c in top['cells'].values())!=72:
            raise ValueError('expected exactly 72 retained SRAM instances')
        report['observables']=mapped_observable_report(top)
        lib=Path(mapping['reference_library']['path']) if 'path' in mapping['reference_library'] else ROOT/'ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib'
        if E.record(lib)['sha256']!=MAPPING.LIB_SHA256:raise ValueError('reference Liberty mismatch')
        backend=SOURCES.select_backend('behavioral','simulation')
        sources=[*backend['sources'],ROOT/'soc/kwt_icb_slave_sram.sv',ROOT/'sim/kwt_icb_pair_checker.sv',ROOT/'sim/tb_kwt_icb_mapped_pair.sv']
        tools={'yosys':shutil.which('yosys'),'verilator':shutil.which('verilator')}
        if not all(tools.values()):raise FileNotFoundError('source env/activate.sh; Yosys/Verilator required')
        dependencies=[Path(__file__),Path(E.__file__),Path(SOC.__file__),Path(L.__file__),Path(EXPORTED.__file__),
                      Path(L.COMMON.__file__),Path(MAPPING.__file__),*backend['dependencies'],*sources,path,net,verilog,lib,
                      ROOT/'model/fixed16_acc48.py',Path(ALIAS.__file__),ROOT/'sim/fixtures/kwt_mapped_alias.sv',
                      Path(CHECKER.__file__),ROOT/'sim/fixtures/tb_kwt_icb_pair_checker.sv',
                      *map(Path,tools.values()),ROOT/'.tools/synth/usr/bin/yosys',
                      ROOT/'.tools/eda/usr/bin/verilator',ROOT/'.tools/eda/usr/bin/verilator_bin']
        report['identity']=E.source_identity(dependencies,report['configuration'],out/'source_identity.json')
        report['inputs']=report['identity']['inputs']+mapping['inputs']
        model=L.load_module('kwt_mapped_numeric',ROOT/'model/fixed16_acc48.py')
        manifest,provenance,images=EXPORTED.validate_export(args.vectors_dir.resolve(),model,source_root=ROOT/'vendor/kwt1-237e4097')
        report['inputs']+=provenance+SOC.stage_verified_vectors(images[:args.tasks],out/'vectors')
        report['vector_scope']=manifest['input']['kind']
        report['workload_sha256']=hashlib.sha256(b''.join(image[k] for image in images[:args.tasks] for k in ('x','w','bias','y'))).hexdigest()
        (out/'mapped_top.v').write_text(rename_mapped_top(verilog.read_text()))
        (out/'logical_macros.sv').write_text(logical_macro_models(shapes))
        (out/'mapped_alias.vlt').write_text(mapped_alias_configuration())
        (out/'cells.ys').write_text('\n'.join(['read_liberty -ignore_miss_func -ignore_miss_dir "'+str(lib)+'"',
            'proc','opt_clean','write_verilog -noattr standard_cells.v','log KWT_SRAM_FUNCTIONAL_CELLS_COMPLETE','']))
        lock=ROOT/'.tools/synth/structural.lock'
        with lock.open('a') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if args.reuse_build:
                report['phase']='reuse_build';E.write_json(out/'result.json',report)
                previous_path=args.reuse_build.resolve()
                generated={name:E.record(out/name) for name in ('mapped_top.v','logical_macros.sv','mapped_alias.vlt','cells.ys')}
                previous=accepted_reused_build(previous_path,path,dependencies,sources,tools,generated)
                binary=Path(previous['binary']['path'])
                report['reused_build']=E.record(previous_path)
                report['inputs']+=[E.record(previous_path),*previous['inputs'],*generated.values()]
                report['alias_probe']=previous['alias_probe']
                report['checker_probe']=previous['checker_probe']
            else:
                alias_path=args.alias_report
                if alias_path is None:
                    command=execute([sys.executable,'-B',str(Path(ALIAS.__file__))],'alias_probe',120)
                    summary=json.loads(Path(command['log']['path']).read_text().strip())
                    alias_path=Path(summary['report'])
                alias=accepted_alias_report(alias_path)
                report['alias_probe']=E.record(alias_path)
                report['inputs']+=[E.record(alias_path),E.record(Path(alias_path).resolve().parent/'source_identity.json'),*alias['inputs']]
                checker_path=args.checker_report
                if checker_path is None:
                    command=execute([sys.executable,'-B',str(Path(CHECKER.__file__))],'checker_probe',120)
                    summary=json.loads(Path(command['log']['path']).read_text().strip())
                    checker_path=Path(summary['report'])
                checker=accepted_checker_report(checker_path)
                report['checker_probe']=E.record(checker_path)
                report['inputs']+=[E.record(checker_path),E.record(Path(checker_path).resolve().parent/'source_identity.json'),*checker['inputs']]
                report['phase']='cell_models';E.write_json(out/'result.json',report)
                execute([tools['yosys'],'-Q','-s','cells.ys'],'cells',120,[r'^KWT_SRAM_FUNCTIONAL_CELLS_COMPLETE$'])
                report['phase']='compile'
                generated=[out/'mapped_top.v',out/'logical_macros.sv',out/'standard_cells.v',out/'mapped_alias.vlt']
                report['inputs']+=[E.record(p) for p in [*generated,out/'cells.ys']]
                command=execute([tools['verilator'],'--binary','--timing','--assert','-Wno-fatal',
                    '--top-module','tb_kwt_icb_mapped_pair','--Mdir',str(out/'obj'),'-o','simulation','-j','2','--threads','1',
                    *map(str,[*sources,*generated])],'compile',300)
                accept_mapped_compile(Path(command['log']['path']).read_text())
                binary=out/'obj/simulation'
            report['binary']=E.record(binary);report['mapping_report']=E.record(path)
            report['inputs'].append(report['binary'])
            report['phase']='simulation';E.write_json(out/'result.json',report)
            command=execute([str(binary),f'+VECTORS={out/"vectors"}',f'+TASKS={args.tasks}'],'run',args.timeout)
            report['measurement']=validate_mapped_log(Path(command['log']['path']).read_text(),args.tasks)
            report.update(status='PASS',phase='complete')
    except FileNotFoundError as exc:report.update(status='BLOCKED',error=str(exc))
    except Exception as exc:report.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:E.verify_records(report['inputs'])
        except (OSError,ValueError) as exc:report.update(status='FAIL',error=str(exc))
        E.write_json(out/'result.json',report)
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return {'PASS':0,'FAIL':1,'BLOCKED':2}[report['status']]


if __name__=='__main__':raise SystemExit(main())
