"""Revalidate bounded BACKEND=3 core/ICB evidence before a CPU entry.

No HDL is executed here. A development adapter remains development evidence;
the pinned real12 input is one zero-silence smoke, not dataset accuracy or PPA.
"""
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import run_sram_adapter_system as SYS

PLAN, C, E, ENGINE = SYS.PLAN, SYS.C, SYS.E, SYS.ENGINE
CONFIG = {'backend': 3, 'suite': 'both', 'result_buffers': 2, 'pipe_mul': 1}
require = PLAN._require


def _record(item):
    """Validate optional vector metadata, returning a canonical file record."""
    require(isinstance(item, dict) and {'path', 'sha256', 'size_bytes'} <= set(item), 'incomplete evidence record')
    require(not set(item)-{'path', 'sha256', 'size_bytes', 'project_relative_path', 'role', 'bits', 'count'}, 'unknown evidence record fields')
    base = {key: item[key] for key in ('path', 'sha256', 'size_bytes')}
    PLAN._verify_record(base)
    if 'project_relative_path' in item:
        relative = Path(item['project_relative_path'])
        require(not relative.is_absolute() and '..' not in relative.parts
                and (ROOT/relative).resolve() == Path(base['path']), 'project-relative evidence path differs')
    for key in ('bits', 'count'):
        if key in item:
            require(type(item[key]) is int and item[key] > 0, 'invalid vector '+key)
    return base


def _producer_paths():
    return [Path(SYS.__file__), Path(PLAN.__file__), Path(E.__file__), Path(C.__file__), Path(C.INTAKE.__file__),
            Path(ENGINE.__file__), Path(ENGINE.LINEAR.__file__), Path(ENGINE.EXPORTED.__file__), Path(ENGINE.BASE.__file__),
            ROOT/'scripts/verify/run_rowpair_benchmark.py', ROOT/'scripts/verify/run_checks.py', ROOT/'scripts/verify/sram_sources.py']


def _runtime_records(report, out):
    actual = PLAN._merge([_record(item) for item in report['runtime_inputs']])
    export_root = ROOT/'sim/vectors/kwt-silence-v1'
    model = ENGINE.LINEAR.load_module('kwt_adapter_system_evidence_numeric', ROOT/'model/fixed16_acc48.py')
    _, provenance, images = ENGINE.EXPORTED.validate_export(export_root, model, source_root=ROOT/'vendor/kwt1-237e4097')
    require(len(images) == 12, 'real12 export is incomplete')
    expected = [_record(item) for item in provenance]
    for task, image in enumerate(images):
        require(set(image) == {'x', 'w', 'bias', 'y'}, 'real12 image roles differ')
        for role, payload in image.items():
            path = out/'core-real/vectors'/f'task_{task:02d}_{"b" if role == "bias" else role}.mem'
            before = E.record(path)
            require(path.read_bytes() == payload, 'real12 runtime copy differs: '+str(path))
            PLAN._verify_record(before)
            expected.append(before)
    range_path = out/'core-range/vectors/manifest.json'
    range_record = E.record(range_path)
    ranges = PLAN._read_json(range_path)
    require(ranges.get('format') == 'fixed16_acc48_v1' and ranges.get('tasks') == 2
            and ranges.get('scope') == 'universal signed41 accumulation boundaries' and len(ranges['cases']) == 2,
            'signed41 range manifest differs')
    expected.append(range_record)
    for task, case in enumerate(ranges['cases']):
        x, w, bias = (-32768, -32768, (1 << 39)-1) if task == 0 else (-32768, 32767, -(1 << 39))
        endpoint = bias + 64*x*w
        require(case['task'] == task and case['category'] == ('signed41_max' if task == 0 else 'signed41_min')
                and case['endpoint'] == endpoint and len(case['files']) == 4, 'signed41 endpoint differs')
        specs = [('x',16,6336,x), ('w',16,16384,w), ('b',40,256,bias), ('y',48,25344,endpoint)]
        for item, (role, bits, count, value) in zip(case['files'], specs):
            path = out/'core-range/vectors'/f'task_{task:02d}_{role}.mem'
            record = _record(item)
            require(record['path'] == str(path) and (item.get('role'), item.get('bits'), item.get('count')) == (role,bits,count),
                    'signed41 vector role/shape differs')
            lines = path.read_text(encoding='ascii').splitlines()
            word = f'{value & ((1 << bits)-1):0{bits//4}x}'
            require(len(lines) == count and all(line.lower() == word for line in lines), 'signed41 runtime words differ')
            PLAN._verify_record(record)
            expected.append(record)
    PLAN._verify_record(range_record)
    expected = PLAN._merge(expected)
    require({r['path']: r for r in actual} == {r['path']: r for r in expected}, 'runtime input coverage differs')
    return actual


def _native(command, argv, cwd, out, name, timeout):
    C.clean_native(command, 0)
    require(command['argv'] == list(map(str, argv)) and command['cwd'] == str(cwd)
            and type(command.get('timeout_seconds')) is int and command['timeout_seconds'] == timeout, 'system native argv/cwd/timeout differs: '+name)
    require(command['log']['path'] == str(out/(name+'.log'))
            and command['native_state']['path'] == str(out/(name+'.command.json')), 'system native evidence path differs')
    for item in (command['log'], command['native_state']):
        _record(item)
    require(PLAN._read_json(command['native_state']['path']) == {k: v for k,v in command.items() if k != 'native_state'}, 'system native saved state differs')
    return C.verify_native(command)


def _finish(text, tb, verilator=False):
    lines = [line for line in text.splitlines() if '$finish' in line]
    pattern = (r'- '+re.escape(str(tb))+r':\d+: Verilog \$finish' if verilator else
               re.escape(str(tb))+r':\d+: \$finish called at \d+ \([^)]+\)')
    require(len(lines) == 1 and re.fullmatch(pattern, lines[0]), 'system testbench native finish absent')


def verify_system_report(report_path, plan, manifest, development=False):
    try:
        path = Path(report_path).resolve(); report_record = E.record(path); report = PLAN._read_json(path); out = path.parent
        require(report.get('schema') == 'kwt-sram-adapter-system-v1' and report.get('status') == 'PASS', 'system report is not a complete PASS')
        require(report.get('configuration') == CONFIG, 'system configuration differs')
        scope = 'development logical adapter' if development else 'supplied-model functional core/ICB only'
        require(report.get('scope') == scope, 'system report scope differs')
        require(report.get('official_validation') == 'NOT_RUN' and report.get('official_ppa') == 'BLOCKED'
                and all(report.get(k) == 'NOT_RUN' for k in ('cpu_soc','synthesis','timing','area','power')),
                'system report acceptance boundary differs')
        require(report.get('supplied_model_functional') == ('NOT_RUN' if development else 'PASS'), 'system supplied-model scope differs')
        require(isinstance(report.get('started_utc'), str) and isinstance(report.get('finished_utc'), str)
                and report['started_utc'] <= report['finished_utc'], 'system completion absent')
        prerequisite = PLAN.verify_primitive_report(report['primitive_prerequisite']['report']['path'], plan, manifest, development=development)
        require(report['primitive_prerequisite'] == {k:v for k,v in prerequisite.items() if k != 'dependency_paths'}, 'system primitive prerequisite differs')
        require(report['plan'] == {k:v for k,v in plan.items() if k not in ('sources','dependency_paths')}
                and report['selected_sources'] == list(map(str, plan['sources'])), 'system selected adapter plan differs')
        producers = _producer_paths()
        runner_identity = PLAN._read_json(out/'runner_identity.json')
        plan_identity = PLAN._read_json(out/'plan_identity.json')
        dependencies = PLAN._merge([E.record(__file__), report_record], prerequisite['dependencies'],
                                  PLAN._identity(runner_identity, out/'runner_identity.json'),
                                  PLAN._identity(plan_identity, out/'plan_identity.json'),
                                  PLAN._identity(report['identity'], out/'source_identity.json'))
        require(runner_identity['configuration'] == plan_identity['configuration'] == report['identity']['configuration'] == CONFIG,
                'system identity configuration differs')
        require(runner_identity['inputs'] == [E.record(p) for p in producers], 'system producer identity differs')
        plan_paths = list(dict.fromkeys([*producers, *[Path(r['path']) for r in plan['dependencies']]]))
        require(plan_identity['inputs'] == [E.record(p) for p in plan_paths], 'system plan identity differs')
        base = [ROOT/'src/rtl/memory/kwt_sram_1rw.sv', ROOT/'src/rtl/memory/kwt_sram_bank.sv', ROOT/'src/rtl/kwt_linear_engine_rowpair_sram.sv']
        core_tb = ROOT/'sim/tb_rowpair_sram.sv'
        icb = [ROOT/'soc/kwt_icb_slave_sram.sv', ROOT/'sim/tb_kwt_icb_slave_sram.sv', ROOT/'sim/tb_kwt_icb_backend3_checked.sv']
        sources = [*base, *plan['sources']]
        require(len(set(sources)) == len(sources), 'duplicate system compilation source')
        required = [E.record(p) for p in [*producers,*sources,core_tb,*icb,*SYS.tool_inputs(),ROOT/'model/fixed16_acc48.py',ROOT/'sim/vectors/kwt-silence-v1/manifest.json']]
        required += prerequisite['dependencies']
        identity_map = {r['path']:r for r in report['identity']['inputs']}
        require(all(identity_map.get(r['path']) == r for r in required), 'mandatory system source/prerequisite input differs')
        runtime = _runtime_records(report, out)
        commands, cases, binaries = report['commands'], report['cases'], report['binaries']
        require(len(commands) == 9 and len(cases) == 3 and len(binaries) == 3, 'system stage/native/binary count differs')
        for index, (name, option) in enumerate((('verilator','--version'),('iverilog','-V'),('vvp','-V'))):
            text = _native(commands[index], [ROOT/'.tools/bin'/name,option], out,out,name+'-version',20)
            require(not PLAN.FAILURE.search(text), 'system version failure diagnostic')
        verified = []
        for index, (label, tasks, work, binary, semantics) in enumerate((
                ('real12',12,out/'core-real',out/'core-real/obj/simulation','two-state'),
                ('signed41-range',2,out/'core-range',out/'core-range/simulation.vvp','four-state'),
                ('icb',None,out/'icb',out/'icb/simulation.vvp','four-state'))):
            if index == 0:
                build = [ROOT/'.tools/bin/verilator','--binary','--timing','--assert','-Wno-fatal','--top-module','tb_rowpair_sram',
                         '--Mdir',work/'obj','-o','simulation','-j','2','--threads','1','-GRESULT_BUFFERS=2','-GPIPE_MUL=1','-GSRAM_BACKEND=3',*sources,core_tb]
            else:
                top = 'tb_rowpair_sram' if index == 1 else 'tb_kwt_icb_backend3_checked'
                params = [f'-P{top}.{key}={value}' for key,value in (('RESULT_BUFFERS',2),('PIPE_MUL',1),('SRAM_BACKEND',3))] if index == 1 else []
                build = [ROOT/'.tools/bin/iverilog','-g2012','-s',top,'-o',binary,*params,*sources,*([core_tb] if index == 1 else icb)]
            text = _native(commands[3+2*index],build,work,out,label+'-build',180)
            require(not PLAN.FAILURE.search(text) and not re.search(r'\berror:|UNOPTFLAT',text,re.I), 'system build failure diagnostic')
            record = _record(binaries[index]);require(record['path'] == str(binary), 'system binary path differs')
            run = [binary] if index == 0 else [ROOT/'.tools/bin/vvp',binary]
            if tasks is not None:
                run += [f'+VECTORS={work/"vectors"}',f'+TASKS={tasks}','+SEED=20261015','+RANDOM_STALLS=1']
            command = commands[4+2*index]; text = _native(command,run,work,out,label+'-run',120)
            case = cases[index]
            require(case['name'] == (label if tasks else 'icb-four-state') and case['status'] == 'PASS' and case['command'] == command, 'system case/command differs')
            if tasks is not None:
                require(case['semantics'] == semantics, 'core logic semantics differs')
                config = {'engine':'rowpair','lanes':8,'tasks':tasks,'pipe_mul':1,'result_buffers':2,'stalls':'random'}
                coverage = SYS.accept_core(command,text,config)
                require(coverage['suite']['outputs'] == tasks*25344, 'core output conservation differs')
                _finish(text,core_tb,index == 0)
            else:
                coverage = SYS.accept_icb(command,text)
                require(coverage['accepted_core_outputs'] == 25348 and coverage['monitored_response_holds'] == 86
                        and coverage['reset_discarded_responses'] == 1, 'ICB observed coverage differs')
                _finish(text,icb[1])
            require(case['coverage'] == coverage, 'system saved coverage differs')
            verified.append({'name':case['name'],'semantics':semantics,'coverage':coverage})
        dependencies = PLAN._merge(dependencies,runtime,[_record(r) for r in binaries],
                                  [_record(r) for c in commands for r in (c['log'],c['native_state'])])
        for record in dependencies:
            PLAN._verify_record(record)
        return {'report':report_record,'dependencies':dependencies,'dependency_paths':[Path(r['path']) for r in dependencies],
                'scope':scope,'source_id':report['identity']['source_id'],'verified_cases':verified,'native_commands':9}
    except (KeyError,TypeError,IndexError,AttributeError) as exc:
        raise ValueError('incomplete system evidence: '+str(exc)) from exc
