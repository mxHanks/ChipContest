#!/usr/bin/env python3
"""BACKEND=3 core/ICB functional entry consuming a verified adapter plan.

No CPU, synthesis, official technology or PPA acceptance is inferred here.
The prior producers and source selector are intentionally left unchanged.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import sram_evidence as E
import run_official_sram_contract as C
import run_sram_engine as ENGINE
import sram_adapter_plan as PLAN

COMPLETE = 'KWT_SRAM_ADAPTER_SYSTEM_COMPLETE'


def accept_core(command, text, config):
    C.clean_native(command, 0)
    if sum('PASS ROWPAIR_BENCH_TASK ' in line for line in text.splitlines()) != config['tasks']:
        raise ValueError('extra/missing core task markers')
    if sum('PASS ROWPAIR_BENCH_SUITE ' in line for line in text.splitlines()) != 1:
        raise ValueError('extra/missing core suite markers')
    error, coverage = ENGINE.check_completion(command, text, config)
    if error: raise ValueError(error)
    return coverage


def accept_icb(command, text):
    C.clean_native(command, 0)
    old = re.findall(r'^ICB_ADAPTER_PASS transactions=(\d+) hold_checks=86 actual_core_outputs=25348 complete_tasks=1 aborted_tasks=1$', text, re.M)
    monitored = re.findall(r'^PASS ICB_BACKEND3_MONITOR accepted_outputs=25348 response_holds=86 accepted_commands=(\d+) accepted_responses=(\d+) reset_discarded_responses=1$', text, re.M)
    if len(old) != 1 or len(monitored) != 1 or int(old[0]) < 193889:
        raise ValueError('missing or inconsistent ICB/actual-handshake completion')
    commands, responses = map(int, monitored[0])
    if responses != int(old[0]) or commands != responses+1:
        raise ValueError('ICB independent command/response accounting differs')
    if sum('ICB_ADAPTER_PASS ' in line for line in text.splitlines()) != 1 or sum('PASS ICB_BACKEND3_MONITOR ' in line for line in text.splitlines()) != 1:
        raise ValueError('duplicate/malformed ICB completion family')
    if re.search(r'(?:^|\n)\s*(?:FATAL\b|ERROR\b|FAIL\b|%Error\b)|\b(?:Aborting|Assertion failed)\b', text, re.I):
        raise ValueError('failure diagnostic in ICB log')
    return {'transactions': int(old[0]), 'original_response_holds': 86,
            'monitored_response_holds': 86, 'accepted_core_outputs': 25348,
            'accepted_commands': commands, 'accepted_responses': responses, 'reset_discarded_responses': 1,
            'complete_tasks': 1, 'aborted_tasks': 1,
            'scope': 'four-state bus-driven real core with zero X/W and signed bias; no CPU/external writeback'}


def tool_inputs():
    paths = [ROOT/'.tools/bin'/name for name in ('verilator', 'iverilog', 'vvp')]
    paths += [ROOT/'.tools/eda/usr/bin'/name for name in ('verilator', 'verilator_bin', 'iverilog', 'vvp')]
    for name in ('make', 'g++'):
        path = shutil.which(name)
        if not path: raise FileNotFoundError(name+' missing; source env/activate.sh')
        paths.append(Path(path))
    for folder in (ROOT/'.tools/eda/usr/share/verilator/include', ROOT/'.tools/eda/usr/lib/x86_64-linux-gnu/ivl'):
        paths += sorted(path for path in folder.rglob('*') if path.is_file())
    return list(dict.fromkeys(path.resolve() for path in paths))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=ROOT/'configs/official-sram-package.json')
    p.add_argument('--primitive-report', type=Path, help='complete same-input primitive/bank contract PASS, independently revalidated')
    p.add_argument('--development-adapter', action='store_true', help='explicit logical fixture; never official validation')
    p.add_argument('--suite', choices=('core', 'icb', 'both'), default='both')
    args = p.parse_args(argv)
    out = ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-adapter-system-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'kwt-sram-adapter-system-v1', 'status': 'FAIL', 'started_utc': E.now(),
              'scope': 'development logical adapter' if args.development_adapter else 'supplied-model functional core/ICB only',
              'official_validation': 'NOT_RUN', 'official_ppa': 'BLOCKED', 'cpu_soc': 'NOT_RUN',
              'synthesis': 'NOT_RUN', 'timing': 'NOT_RUN', 'area': 'NOT_RUN', 'power': 'NOT_RUN',
              'configuration': {'backend': 3, 'suite': args.suite, 'result_buffers': 2, 'pipe_mul': 1},
              'commands': [], 'cases': [], 'binaries': [], 'runtime_inputs': [],
              'tool_scope': 'bound project binaries/runtime files and host make/g++; not a complete OS dependency image'}
    inputs = [Path(__file__), Path(PLAN.__file__), Path(E.__file__), Path(C.__file__), Path(C.INTAKE.__file__),
              Path(ENGINE.__file__), Path(ENGINE.LINEAR.__file__), Path(ENGINE.EXPORTED.__file__), Path(ENGINE.BASE.__file__),
              ROOT/'scripts/verify/run_rowpair_benchmark.py', ROOT/'scripts/verify/run_checks.py', ROOT/'scripts/verify/sram_sources.py']
    report['identity'] = E.source_identity(inputs, report['configuration'], out/'runner_identity.json')
    report['identity_scope'] = 'runner/helper identity; no HDL input collection completed'
    def native(argv, name, cwd, timeout=180):
        command = E.run_command(argv, cwd, out/(name+'.log'), timeout, 2)
        report['commands'].append(command)
        return command, C.verify_native(command)
    try:
        plan = PLAN.plan_inputs(args.manifest, development=args.development_adapter)
        report['plan'] = {key: value for key, value in plan.items() if key not in ('sources','dependency_paths')}
        report['selected_sources'] = [str(path) for path in plan['sources']]
        inputs += [Path(record['path']) for record in plan['dependencies']]
        report['identity'] = E.source_identity(list(dict.fromkeys(inputs)), report['configuration'], out/'plan_identity.json')
        report['identity_scope'] = 'runner and available adapter-plan inputs before HDL'
        if plan['status'] != 'FILES_VERIFIED':
            report['status'] = plan['status']; return finish(report, out)
        if args.primitive_report is None:
            report.update(status='BLOCKED', error='same-input primitive/bank PASS report is required; no implicit prerequisite bypass')
            return finish(report, out)
        prerequisite = PLAN.verify_primitive_report(args.primitive_report, plan, args.manifest, development=args.development_adapter)
        report['primitive_prerequisite'] = {key:value for key,value in prerequisite.items() if key!='dependency_paths'}
        inputs += [Path(record['path']) for record in prerequisite['dependencies']]
        base = [ROOT/'src/rtl/memory/kwt_sram_1rw.sv', ROOT/'src/rtl/memory/kwt_sram_bank.sv', ROOT/'src/rtl/kwt_linear_engine_rowpair_sram.sv']
        core_tb = ROOT/'sim/tb_rowpair_sram.sv'
        icb_sources = [ROOT/'soc/kwt_icb_slave_sram.sv', ROOT/'sim/tb_kwt_icb_slave_sram.sv', ROOT/'sim/tb_kwt_icb_backend3_checked.sv']
        sources = [*base, *plan['sources']]
        if len(set(sources)) != len(sources): raise ValueError('duplicate RTL in selected compilation set')
        model_path = ROOT/'model/fixed16_acc48.py'
        inputs += [*sources, *tool_inputs()]
        if args.suite in ('core','both'):
            inputs += [core_tb, model_path, ROOT/'sim/vectors/kwt-silence-v1/manifest.json']
        if args.suite in ('icb','both'): inputs += icb_sources
        report['identity'] = E.source_identity(list(dict.fromkeys(path.resolve() for path in inputs)), report['configuration'], out/'source_identity.json')
        report['identity_scope'] = 'selected RTL/helper/prerequisite/tool identities frozen before vectors/build/simulation'
        E.verify_records(report['identity']['inputs'])
        for name, tool, option in (('verilator', ROOT/'.tools/bin/verilator', '--version'),
                                   ('iverilog', ROOT/'.tools/bin/iverilog', '-V'), ('vvp', ROOT/'.tools/bin/vvp', '-V')):
            command, text = native([tool, option], name+'-version', out, 20); C.clean_native(command, 0)

        def build(top, files, work, label, simulator):
            if simulator == 'verilator':
                binary = work/'obj/simulation'
                argv = [ROOT/'.tools/bin/verilator', '--binary', '--timing', '--assert', '-Wno-fatal',
                        '--top-module', top, '--Mdir', work/'obj', '-o', 'simulation', '-j', '2', '--threads', '1',
                        '-GRESULT_BUFFERS=2', '-GPIPE_MUL=1', '-GSRAM_BACKEND=3', *files]
            else:
                binary = work/'simulation.vvp'
                params = [f'-P{top}.RESULT_BUFFERS=2',f'-P{top}.PIPE_MUL=1',f'-P{top}.SRAM_BACKEND=3'] if top=='tb_rowpair_sram' else []
                argv = [ROOT/'.tools/bin/iverilog', '-g2012', '-s', top, '-o', binary, *params, *files]
            E.verify_records(report['identity']['inputs']+report['runtime_inputs'])
            command, text = native(argv, label+'-build', work)
            C.clean_native(command, 0)
            error = E.completion_error(command, [])
            if error or 'UNOPTFLAT' in text: raise ValueError('build not accepted: '+str(error or 'UNOPTFLAT'))
            record = E.record(binary); report['binaries'].append(record)
            return binary, record

        if args.suite in ('core','both'):
            model = ENGINE.LINEAR.load_module('kwt_adapter_numeric', model_path)
            real = out/'core-real'; real.mkdir(); (real/'vectors').mkdir()
            export_root = ROOT/'sim/vectors/kwt-silence-v1'
            manifest_before = E.record(export_root/'manifest.json')
            manifest, provenance, images = ENGINE.EXPORTED.validate_export(export_root, model, source_root=ROOT/'vendor/kwt1-237e4097')
            E.verify_records([manifest_before, *provenance]); report['runtime_inputs'] += provenance
            for task, image in enumerate(images):
                for role in ('x','w','bias','y'):
                    target = real/'vectors'/f'task_{task:02d}_{"b" if role=="bias" else role}.mem'
                    target.write_bytes(image[role]); report['runtime_inputs'].append(E.record(target))
            for work, tasks, simulator, kind in ((real,12,'verilator','real12'),(out/'core-range',2,'iverilog','signed41-range')):
                if kind=='signed41-range':
                    work.mkdir(); vector_manifest, record = ENGINE.generate_range_vectors(work, tasks, model)
                    report['runtime_inputs'] += [record, *[file for case in vector_manifest['cases'] for file in case['files']]]
                config = {'engine':'rowpair', 'lanes':8, 'tasks': tasks, 'pipe_mul':1, 'result_buffers':2, 'stalls':'random'}
                binary, record = build('tb_rowpair_sram',[*sources,core_tb],work,kind,simulator)
                E.verify_records(report['identity']['inputs']+report['runtime_inputs']+[record])
                argv = [binary] if simulator=='verilator' else [ROOT/'.tools/bin/vvp',binary]
                argv += [f'+VECTORS={work/"vectors"}',f'+TASKS={tasks}','+SEED=20261015','+RANDOM_STALLS=1']
                command, text = native(argv,kind+'-run',work,120)
                coverage = accept_core(command,text,config)
                report['cases'].append({'name':kind,'status':'PASS','semantics':'two-state' if simulator=='verilator' else 'four-state',
                                        'coverage':coverage,'command':command})
            report['real_vector_scope'] = 'pinned real12 weights and zero-silence waveform smoke; not dataset or official600 precision'
        if args.suite in ('icb','both'):
            work = out/'icb'; work.mkdir()
            binary, record = build('tb_kwt_icb_backend3_checked',[*sources,*icb_sources],work,'icb','iverilog')
            E.verify_records(report['identity']['inputs']+report['runtime_inputs']+[record])
            command,text = native([ROOT/'.tools/bin/vvp',binary],'icb-run',work,120)
            report['cases'].append({'name':'icb-four-state','status':'PASS','coverage':accept_icb(command,text),'command':command})
        report.update(status='PASS', supplied_model_functional='PASS' if not args.development_adapter else 'NOT_RUN')
    except FileNotFoundError as exc: report.update(status='BLOCKED',error=str(exc))
    except (OSError, ValueError, KeyError, TypeError) as exc: report.update(status='FAIL',error=type(exc).__name__+': '+str(exc))
    return finish(report,out)


def finish(report,out):
    try:
        E.verify_records(report.get('identity',{}).get('inputs',[])+report['runtime_inputs']+report['binaries'])
        for command in report['commands']: C.verify_native(command)
    except (OSError,ValueError,KeyError) as exc: report.update(status='FAIL',evidence_error=str(exc))
    report['finished_utc']=E.now(); E.write_json(out/'result.json',report)
    print(COMPLETE)
    print(json.dumps({'status':report['status'],'official_validation':'NOT_RUN','report':str(out/'result.json')}))
    return 0 if report['status']=='PASS' else 2 if report['status']=='BLOCKED' else 1


if __name__=='__main__': raise SystemExit(main())
