#!/usr/bin/env python3
"""Bounded BACKEND=3 primitive/bank contract tests, never official PPA acceptance.

Default operation consumes only the simulation file plan from the staged intake.
The explicitly selected development fixture qualifies this runner and checker;
it is rejected in supplied-package mode and never added to synthesis sources.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import official_sram_inputs as INTAKE
import sram_evidence as E

SENTINEL = 'KWT_DEVELOPMENT_LOGICAL_ADAPTER_FIXTURE'
FIXTURE = ROOT / 'sim/fixtures/kwt_logical_adapter_qualification.sv'
COMPLETE = 'KWT_OFFICIAL_SRAM_CONTRACT_COMPLETE'


def positive_cases():
    return [dict(name=f'unit-w16-d{d}', top='tb_kwt_sram_1rw', width=16, depth=d)
            for d in (128, 1024, 4096)] + [
        dict(name=f'bank-w{w}-d{d}', top='tb_kwt_sram_bank', width=w, depth=d)
        for w, d in ((16, 3136), (16, 3200), (16, 2048), (40, 32), (41, 512))]


def negative_cases():
    unit = {1: ['KWT_SRAM_SINGLE_PORT_CONFLICT'], 2: ['KWT_SRAM_SINGLE_PORT_CONFLICT'],
            3: ['KWT_SRAM_UNINITIALIZED_READ'], 6: ['KWT_SRAM_UNKNOWN_ENABLE'],
            7: ['KWT_SRAM_READ_ADDRESS_INVALID'], 8: ['KWT_SRAM_UNKNOWN_WRITE_DATA'],
            9: ['KWT_SRAM_WRITE_ADDRESS_INVALID']}
    bank = {**{i: ['KWT_SRAM_BANK_UNKNOWN_ENABLE'] for i in range(1, 5)},
            5: ['KWT_SRAM_BANK simultaneous read/write forbidden'],
            6: ['KWT_SRAM_BANK address out of logical range'],
            7: ['KWT_SRAM_BANK address out of logical range'],
            8: ['KWT_SRAM_BANK unknown address', 'KWT_SRAM_UNKNOWN_ENABLE']}
    return [dict(name=f'{binary}-illegal-{i}', binary_name=binary, error_case=i,
                 diagnostics=diags) for binary, plan in
            (('unit-w16-d128', unit), ('bank-w16-d3200', bank)) for i, diags in plan.items()]


def clean_native(command, expected_exit):
    if (command.get('status') != 'EXITED' or type(command.get('exit_code')) is not int
            or command['exit_code'] != expected_exit or command.get('timed_out') is not False
            or command.get('interrupted') is not False):
        raise ValueError('native execution did not finish with the required exit status')


def accept_case(case, command, text, negative=False):
    """Pure parser; native record/log identities are checked separately by caller."""
    clean_native(command, 1 if negative else 0)
    family = [line for line in text.splitlines() if 'PASS KWT_SRAM_' in line]
    if negative:
        fatal = re.findall(r'^FATAL: [^\n]*:\d+: (.+)$', text, re.M)
        remaining = '\n'.join(line for line in text.splitlines()
                              if not re.fullmatch(r'FATAL: [^\n]*:\d+: (.+)', line))
        if (family or 'EXPECTED_DIAGNOSTIC_NOT_TRIGGERED' in text or not fatal
                or any(message not in case['diagnostics'] for message in fatal)
                or re.search(r'(?:^|\n)\s*(?:FATAL\b|ERROR\b|FAIL\b|%Error\b)|\b(?:Aborting|Assertion failed)\b', remaining, re.I)):
            raise ValueError('expected precise fatal diagnostic was not observed alone')
        return {'name': case['name'], 'status': 'EXPECTED_REJECTION', 'diagnostics': fatal}
    if re.search(r'(?:^|\n)\s*(?:FATAL\b|ERROR\b|FAIL\b|%Error\b)|\b(?:Aborting|Assertion failed)\b', text, re.I):
        raise ValueError('failure diagnostic in positive log')
    w, d = case['width'], case['depth']
    if case['top'] == 'tb_kwt_sram_1rw':
        checks = d + 16
        pattern = rf'PASS KWT_SRAM_UNIT width={w} depth={d} checks={checks} signature=([0-9a-fA-F]{{16}})'
        if len(family) != 1 or not re.fullmatch(pattern, family[0]):
            raise ValueError('missing, duplicate or malformed unit completion')
        return {'name': case['name'], 'status': 'PASS', 'checks': checks,
                'signature': re.fullmatch(pattern, family[0]).group(1).lower()}
    checks = 2*d + 5
    expected = [f'PASS KWT_SRAM_BANK_WIDTH_COVERAGE width={w} bits_both={w}',
                f'PASS KWT_SRAM_BANK backend=3 width={w} depth={d} checks={checks}']
    if family != expected:
        raise ValueError('bank completion or complete width-bit coverage differs')
    return {'name': case['name'], 'status': 'PASS', 'checks': checks, 'bits_both': w}


def verify_native(command):
    E.verify_records([command['log'], command['native_state']])
    saved = json.loads(Path(command['native_state']['path']).read_text())
    for key in ('status', 'exit_code', 'timed_out', 'interrupted', 'argv', 'cwd', 'log'):
        if saved.get(key) != command.get(key):
            raise ValueError('native record differs from reported command: '+key)
    return Path(command['log']['path']).read_text(errors='replace')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'configs/official-sram-package.json')
    parser.add_argument('--development-qualification', choices=('good', 'bad-data', 'missing-adapter', 'duplicate-adapter'))
    parser.add_argument('--timeout', type=int, default=30, help='per native command, 1..120 seconds')
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 120:
        parser.error('--timeout must be between 1 and 120 seconds')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-official-contract-'+uuid.uuid4().hex[:8]
    out = ROOT/'artifacts/runs'/run_id
    out.mkdir(parents=True, exist_ok=False)
    development = args.development_qualification is not None
    result = {'schema': 'kwt-official-sram-contract-v1', 'run_id': run_id,
              'started_utc': E.now(), 'status': 'FAIL', 'commands': [], 'cases': [],
              'scope': 'development_logical_adapter_only' if development else 'supplied_source_primitive_bank_contract_only',
              'development_qualification': args.development_qualification,
              'backend': 3, 'official_validation': 'NOT_RUN', 'official_ppa': 'BLOCKED',
              'core_validation': 'NOT_RUN', 'icb_validation': 'NOT_RUN', 'soc_validation': 'NOT_RUN',
              'synthesis': 'NOT_RUN', 'tool_versions': {}, 'binaries': [],
              'note': 'No vendor pin, technology authenticity, PVT, area or power acceptance; no implicit fallback.'}
    inputs = [Path(__file__), Path(INTAKE.__file__), Path(E.__file__)]
    generated = []
    result['initial_identity'] = E.source_identity(inputs, vars_for_identity(args), out/'runner_identity.json')
    result['identity'] = result['initial_identity']
    result['identity_scope'] = 'runner only; source-plan collection not completed'

    def native(command, name):
        item = E.run_command(command, ROOT, out/(name+'.log'), args.timeout, 1)
        result['commands'].append(item)
        return item, verify_native(item)

    try:
        base = [ROOT/'src/rtl/memory/kwt_sram_1rw.sv', ROOT/'src/rtl/memory/kwt_sram_bank.sv']
        tbs = [ROOT/'sim/tb_kwt_sram_1rw.sv', ROOT/'sim/tb_kwt_sram_bank.sv']
        if development:
            supplied = [] if args.development_qualification == 'missing-adapter' else [FIXTURE]
            inputs += [*base, *tbs, FIXTURE]
            if args.development_qualification == 'duplicate-adapter':
                fixture_before = E.record(FIXTURE)
                duplicate = out/'duplicate_qualification_adapter.sv'
                duplicate.write_bytes(FIXTURE.read_bytes())
                E.verify_records([fixture_before])
                generated.append(E.record(duplicate)); supplied.append(duplicate)
        else:
            # Freeze the manifest before intake reads it, and check after source collection.
            manifest_before = E.record(args.manifest)
            intake = INTAKE.inspect_package(ROOT, args.manifest)
            result['intake'] = intake
            inputs += [args.manifest, *[Path(r['path']) for r in intake['dependencies']]]
            E.verify_records([manifest_before, *intake['dependencies']])
            stage = intake['stages']['simulation']
            if stage['status'] != 'FILES_VERIFIED':
                result['status'] = stage['status']
                result['identity'] = E.source_identity(inputs, vars_for_identity(args), out/'source_identity.json')
                result['identity_scope'] = 'runner, manifest and available declared dependencies; no HDL execution'
                E.verify_records(result['identity']['inputs'])
                return finish(result, out)
            supplied = [Path(p) for p in stage['source_files']]
            inputs += [*base, *tbs]
        # Use the controlled project toolchain, not an unbound PATH executable.
        compiler = ROOT/'.tools/bin/iverilog'
        runtime = ROOT/'.tools/bin/vvp'
        tool_dir = ROOT/'.tools/eda/usr/lib/x86_64-linux-gnu/ivl'
        tool_inputs = [compiler, runtime, ROOT/'.tools/eda/usr/bin/iverilog', ROOT/'.tools/eda/usr/bin/vvp']
        tool_inputs += sorted(p for p in tool_dir.iterdir() if p.is_file())
        inputs += tool_inputs
        # Order-preserving deduplication; the generated duplicate is independently bound.
        inputs = list(dict.fromkeys(p.resolve() for p in inputs))
        result['identity'] = E.source_identity(inputs, vars_for_identity(args), out/'source_identity.json')
        result['identity_scope'] = 'runner, selected inputs, tool binaries and available project runtime files before HDL execution'
        E.verify_records(result['identity']['inputs']+generated)
        if not development:
            for path in supplied:
                source_text = path.read_text(errors='replace')
                if path.resolve() == FIXTURE.resolve() or SENTINEL in source_text:
                    raise ValueError('development logical adapter fixture forbidden in supplied-package mode')
                # No auxiliary include/data/SDF/DPI inventory is supported yet.
                # This is a conservative support gate, not an HDL safety proof.
                if re.search(r'`include\b|\$(?:readmem[hb]|fopen|fread|fgets|fgetc|fscanf|ungetc|rewind|fseek|fread|system|sdf_annotate|load)\b|DPI-C', source_text):
                    raise ValueError('external include/data/SDF/DPI consumption needs explicit auxiliary-input support: '+str(path))
        for name, executable in (('iverilog', compiler), ('vvp', runtime)):
            item, text = native([executable, '-V'], name+'-version')
            clean_native(item, 0)
            result['tool_versions'][name] = text
        binaries = {}
        for case in positive_cases():
            E.write_json(out/'case_progress.json', {'current_case': case['name'], 'stage': 'compile', 'updated_utc': E.now()})
            target = out/(case['name']+'.vvp')
            tb = tbs[0] if case['top'] == 'tb_kwt_sram_1rw' else tbs[1]
            command = [compiler, '-g2012', '-s', case['top'], '-o', target]
            command += [f'-P{case["top"]}.{key}={value}' for key, value in
                        (('WIDTH', case['width']), ('DEPTH', case['depth']), ('BACKEND', 3))]
            if args.development_qualification == 'bad-data':
                command += ['-DKWT_QUALIFICATION_BAD_READ_DATA']
            command += [*base, *supplied, tb]
            item, text = native(command, case['name']+'-compile')
            clean_native(item, 0)
            if re.search(r'(?:^|\n)\s*(?:FATAL\b|ERROR\b)|\berror:', text, re.I):
                raise ValueError('blocking compile diagnostic: '+case['name'])
            binary = E.record(target)
            result['binaries'].append(binary); binaries[case['name']] = binary
            E.verify_records(result['identity']['inputs']+generated+[binary])
            item, text = native([runtime, target], case['name'])
            accepted = accept_case(case, item, text)
            result['cases'].append({**accepted, 'command': item})
        for case in negative_cases():
            E.write_json(out/'case_progress.json', {'current_case': case['name'], 'stage': 'expected_rejection', 'updated_utc': E.now()})
            binary = binaries[case['binary_name']]
            E.verify_records([binary])
            item, text = native([runtime, binary['path'], f'+ERROR_CASE={case["error_case"]}'], case['name'])
            result['cases'].append({**accept_case(case, item, text, negative=True), 'command': item})
        E.verify_records(result['identity']['inputs']+generated+result['binaries'])
        for item in result['commands']:
            verify_native(item)
        result.update(status='PASS', positive_cases=8, expected_rejections=15,
                      primitive_bank_contract='PASS', official_validation='NOT_RUN' if development else 'PRIMITIVE_BANK_ONLY')
    except (OSError, ValueError, KeyError) as exc:
        result.update(status='FAIL', error=str(exc))
    try:
        E.verify_records(result.get('identity', {}).get('inputs', [])+generated+result['binaries'])
        for item in result['commands']:
            verify_native(item)
    except (OSError, ValueError, KeyError) as exc:
        result.update(status='FAIL', evidence_error=str(exc))
    result['generated_inputs'] = generated
    return finish(result, out)


def vars_for_identity(args):
    return {'manifest': str(args.manifest.resolve()), 'development_qualification': args.development_qualification,
            'timeout_seconds': args.timeout, 'backend': 3, 'positive_plan': positive_cases(),
            'negative_plan': negative_cases(), 'scope': 'primitive/bank logical contract only'}


def finish(result, out):
    result['finished_utc'] = E.now()
    E.write_json(out/'result.json', result)
    print(COMPLETE)
    print(json.dumps({'status': result['status'], 'scope': result['scope'],
                      'official_validation': result['official_validation'], 'report': str(out/'result.json')}))
    return 0 if result['status'] == 'PASS' else 2 if result['status'] == 'BLOCKED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
