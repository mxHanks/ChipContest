"""Select a logical adapter and revalidate its bounded primitive/bank evidence.

This helper neither authenticates a vendor nor compiles HDL. External auxiliary
inputs remain unsupported; the lexical refusal is not an HDL safety proof.
"""
import json
import hashlib
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import run_official_sram_contract as C

INTAKE = C.INTAKE
E = C.E
DEV_SCOPE = 'development_logical_adapter_only'
SUPPLIED_SCOPE = 'supplied_source_primitive_bank_contract_only'
EXTERNAL = re.compile(r'`include\b|\$(?:readmem[hb]|fopen|fread|fgets|fgetc|fscanf|ungetc|rewind|fseek|fread|system|sdf_annotate|load)\b|DPI-C')
FAILURE = re.compile(r'(?:^|\n)\s*(?:FATAL\b|ERROR\b|FAIL\b|%Error\b)|\b(?:Aborting|Assertion failed)\b', re.I)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _read_json(path):
    return json.loads(Path(path).read_text())


def _merge(*groups):
    records = {}
    for group in groups:
        for item in group:
            path = item['path']
            _require(path not in records or records[path] == item, 'conflicting dependency: '+path)
            records[path] = item
    return list(records.values())


def _verify_record(item):
    _require(isinstance(item, dict) and set(item) == {'path', 'sha256', 'size_bytes'}, 'malformed file record')
    _require(isinstance(item['path'], str) and Path(item['path']).is_absolute(), 'record path is not absolute')
    _require(type(item['size_bytes']) is int and item['size_bytes'] >= 0, 'invalid record size')
    _require(isinstance(item['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', item['sha256']), 'invalid record SHA256')
    _require(E.record(item['path']) == item, 'file identity differs: '+item['path'])


def _code_records():
    return [E.record(p) for p in (Path(__file__), Path(C.__file__), Path(INTAKE.__file__), Path(E.__file__))]


def plan_inputs(manifest, development=False):
    """Return an explicit file-only simulation plan; never provide a fallback."""
    result = {'status': 'FAIL', 'sources': [], 'dependencies': [], 'intake': None,
              'scope': DEV_SCOPE if development else SUPPLIED_SCOPE,
              'manifest': None, 'development': development}
    try:
        result['dependencies'] = _code_records()
        if development:
            fixture = E.record(C.FIXTURE)
            result['dependencies'] = _merge(result['dependencies'], [fixture])
            result['sources'] = [Path(fixture['path'])]
        else:
            path = Path(manifest)
            path = (ROOT/path if not path.is_absolute() else path).resolve()
            result['manifest'] = E.record(path)
            intake = INTAKE.inspect_package(ROOT, path)
            result['intake'] = intake
            result['dependencies'] = _merge(result['dependencies'], [result['manifest']], intake['dependencies'])
            stage = intake['stages']['simulation']
            if stage['status'] != 'FILES_VERIFIED':
                result['status'] = stage['status']
            else:
                result['sources'] = [Path(p) for p in stage['source_files']]
                for source in result['sources']:
                    text = source.read_text(errors='replace')
                    _require(source.resolve() != C.FIXTURE.resolve() and C.SENTINEL not in text,
                             'development logical adapter fixture forbidden in supplied-package mode')
                    _require(not EXTERNAL.search(text), 'external consumption needs explicit auxiliary-input support: '+str(source))
                result['status'] = 'FILES_VERIFIED'
        if development:
            result['status'] = 'FILES_VERIFIED'
        for record in result['dependencies']:
            _verify_record(record)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status='FAIL', sources=[], error=str(exc))
    result['dependency_paths'] = [Path(r['path']) for r in result['dependencies']]
    return result


def _identity(identity, path):
    identity_record = E.record(path)
    _require(isinstance(identity, dict) and identity.get('schema') == 'kwt-sram-source-identity-v1', 'invalid source identity schema')
    payload = {k: v for k, v in identity.items() if k != 'source_id'}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    _require(identity.get('source_id') == digest, 'canonical source_id differs')
    _require(_read_json(path) == identity, 'saved source identity differs')
    records = identity['inputs']
    _require(isinstance(records, list) and records, 'source identity inputs absent')
    _require(len({r['path'] for r in records}) == len(records), 'duplicate source identity input')
    for record in records:
        _verify_record(record)
    _verify_record(identity_record)
    return [identity_record, *records]


def _native(command, argv, exit_code, out, name):
    C.clean_native(command, exit_code)
    _require(command['argv'] == list(map(str, argv)) and command['cwd'] == str(ROOT), 'native argv/cwd differs: '+name)
    _require(command['log']['path'] == str(out/(name+'.log')), 'native log path differs: '+name)
    _require(command['native_state']['path'] == str(out/(name+'.command.json')), 'native state path differs: '+name)
    for record in (command['log'], command['native_state']):
        _verify_record(record)
    _require(_read_json(command['native_state']['path']) == {k: v for k, v in command.items() if k != 'native_state'},
             'native saved state differs: '+name)
    return C.verify_native(command)


def verify_primitive_report(report_path, plan, manifest, development=False):
    """Recheck every source, command and case; raise on missing or stale proof."""
    try:
        fresh = plan_inputs(manifest, development)
        _require(fresh['status'] == 'FILES_VERIFIED', 'current adapter plan is not FILES_VERIFIED')
        _require(isinstance(plan, dict), 'adapter plan is not a dictionary')
        for key in ('status', 'sources', 'dependencies', 'intake', 'scope', 'manifest', 'development'):
            _require(plan.get(key) == fresh[key], 'adapter plan differs from current inputs: '+key)
        path = Path(report_path).resolve()
        report_record = E.record(path)
        report = _read_json(path)
        _require(report.get('schema') == 'kwt-official-sram-contract-v1' and report.get('status') == 'PASS', 'primitive report is not a complete PASS')
        _require(type(report.get('backend')) is int and report['backend'] == 3, 'primitive report backend differs')
        _require(report.get('scope') == fresh['scope'], 'primitive report scope differs')
        _require(report.get('development_qualification') == ('good' if development else None), 'primitive report qualification differs')
        _require(report.get('official_validation') == ('NOT_RUN' if development else 'PRIMITIVE_BANK_ONLY'), 'primitive report official scope differs')
        _require(report.get('official_ppa') == 'BLOCKED' and report.get('primitive_bank_contract') == 'PASS', 'primitive report acceptance boundary differs')
        _require(all(report.get(k) == 'NOT_RUN' for k in ('core_validation', 'icb_validation', 'soc_validation', 'synthesis')), 'primitive report claims a different validation scope')
        _require(isinstance(report.get('started_utc'), str) and isinstance(report.get('finished_utc'), str)
                 and report['started_utc'] <= report['finished_utc'], 'primitive report completion absent')
        _require(report.get('positive_cases') == 8 and report.get('expected_rejections') == 15, 'primitive report counts differ')
        _require(not report.get('generated_inputs'), 'primitive PASS contains generated fault inputs')
        out = path.parent
        dependencies = _merge(fresh['dependencies'], [report_record],
                              _identity(report['initial_identity'], out/'runner_identity.json'),
                              _identity(report['identity'], out/'source_identity.json'))
        configuration = report['identity']['configuration']
        _require(configuration == report['initial_identity']['configuration'], 'initial configuration differs')
        _require(configuration.get('backend') == 3 and configuration.get('development_qualification') == ('good' if development else None)
                 and configuration.get('positive_plan') == C.positive_cases() and configuration.get('negative_plan') == C.negative_cases()
                 and configuration.get('scope') == 'primitive/bank logical contract only'
                 and type(configuration.get('timeout_seconds')) is int and 1 <= configuration['timeout_seconds'] <= 120,
                 'source identity configuration differs')
        base = [ROOT/'src/rtl/memory/kwt_sram_1rw.sv', ROOT/'src/rtl/memory/kwt_sram_bank.sv']
        tbs = [ROOT/'sim/tb_kwt_sram_1rw.sv', ROOT/'sim/tb_kwt_sram_bank.sv']
        compiler, runtime = ROOT/'.tools/bin/iverilog', ROOT/'.tools/bin/vvp'
        tools = [compiler, runtime, ROOT/'.tools/eda/usr/bin/iverilog', ROOT/'.tools/eda/usr/bin/vvp']
        tools += sorted(p for p in (ROOT/'.tools/eda/usr/lib/x86_64-linux-gnu/ivl').iterdir() if p.is_file())
        producer = [Path(C.__file__), Path(INTAKE.__file__), Path(E.__file__)]
        source_records = {r['path']: r for r in report['identity']['inputs']}
        required = [E.record(p) for p in [*producer, *base, *tbs, *tools]]
        required += [r for r in fresh['dependencies'] if r['path'] != str(Path(__file__).resolve())]
        for record in required:
            _require(source_records.get(record['path']) == record, 'mandatory source input differs: '+record['path'])
        _require(report['initial_identity']['inputs'] == [E.record(p) for p in producer], 'initial producer inputs differ')
        if not development:
            _require(configuration.get('manifest') == fresh['manifest']['path'], 'primitive report manifest path differs')
            saved_intake = report['intake']
            _require(saved_intake['dependencies'] == fresh['intake']['dependencies']
                     and saved_intake['stages']['simulation'] == fresh['intake']['stages']['simulation'], 'primitive report supplied package differs')
        commands, cases, binaries = report['commands'], report['cases'], report['binaries']
        _require(len(commands) == 33 and len(cases) == 23 and len(binaries) == 8, 'primitive native/case/binary count differs')
        for name, tool, index in (('iverilog', compiler, 0), ('vvp', runtime, 1)):
            text = _native(commands[index], [tool, '-V'], 0, out, name+'-version')
            _require(report['tool_versions'][name] == text, 'tool version log differs')
        for i, case in enumerate(C.positive_cases()):
            name = case['name']; target = out/(name+'.vvp')
            tb = tbs[0] if case['top'] == 'tb_kwt_sram_1rw' else tbs[1]
            argv = [compiler, '-g2012', '-s', case['top'], '-o', target]
            argv += [f'-P{case["top"]}.{k}={v}' for k, v in (('WIDTH', case['width']), ('DEPTH', case['depth']), ('BACKEND', 3))]
            argv += [*base, *fresh['sources'], tb]
            text = _native(commands[2+2*i], argv, 0, out, name+'-compile')
            _require(not FAILURE.search(text) and not re.search(r'\berror:', text, re.I), 'blocking compile diagnostic')
            binary = binaries[i]
            _verify_record(binary)
            _require(binary['path'] == str(target), 'primitive binary path differs')
            runtime_command = commands[3+2*i]
            text = _native(runtime_command, [runtime, target], 0, out, name)
            accepted = C.accept_case(case, runtime_command, text)
            _require(cases[i].get('command') == runtime_command and all(cases[i].get(k) == v for k, v in accepted.items()), 'positive case differs')
            finishes = [line for line in text.splitlines() if '$finish called at ' in line]
            _require(len(finishes) == 1 and re.fullmatch(re.escape(str(tb))+r':\d+: \$finish called at \d+ \([^)]+\)', finishes[0]), 'testbench native finish absent')
        for i, case in enumerate(C.negative_cases()):
            target = out/(case['binary_name']+'.vvp'); command = commands[18+i]
            text = _native(command, [runtime, target, f'+ERROR_CASE={case["error_case"]}'], 1, out, case['name'])
            accepted = C.accept_case(case, command, text, negative=True)
            _require(cases[8+i].get('command') == command and all(cases[8+i].get(k) == v for k, v in accepted.items()), 'negative case differs')
        dependencies = _merge(dependencies, binaries,
                              [r for command in commands for r in (command['log'], command['native_state'])])
        for record in dependencies:
            _verify_record(record)
        return {'report': report_record, 'dependencies': dependencies,
                'dependency_paths': [Path(r['path']) for r in dependencies],
                'scope': fresh['scope'], 'source_id': report['identity']['source_id'],
                'positive_cases': 8, 'expected_rejections': 15, 'native_commands': 33}
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError('incomplete primitive evidence: '+str(exc)) from exc
