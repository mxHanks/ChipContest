#!/usr/bin/env python3
"""Directed overwrite/reset contract regression, with isolated fault injection.

This is functional development evidence, not an official macro or PPA result.
The accepted previous runners and their source identities remain unchanged.
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
import sram_evidence as E
import run_official_sram_contract as C

BACKENDS = {'behavioral': 0, 'ff': 2, 'development-adapter': 3}
COMPLETE = 'KWT_SRAM_UPDATE_RESET_COMPLETE'


def shape_plan():
    return [dict(name=f'unit-w16-d{d}', bank=0, width=16, depth=d)
            for d in (128, 1024, 4096)] + [
        dict(name=f'bank-w{w}-d{d}', bank=1, width=w, depth=d)
        for w, d in ((16, 3136), (16, 3200), (16, 2048), (40, 32), (41, 512))]


def accept_case(case, command, text):
    C.clean_native(command, 0)
    if re.search(r'(?:^|\n)\s*(?:FATAL\b|ERROR\b|FAIL\b|%Error\b)|\b(?:Aborting|Assertion failed)\b', text, re.I):
        raise ValueError('failure diagnostic despite a possible completion marker')
    lines = [line for line in text.splitlines() if 'PASS KWT_SRAM_UPDATE_RESET' in line]
    prefix = (rf'PASS KWT_SRAM_UPDATE_RESET backend={case["backend"]} bank={case["bank"]} '
              rf'width={case["width"]} depth={case["depth"]} ')
    pattern = prefix + (r'overwrite_checks=(\d+) reset_write_checks=(\d+) reset_read_checks=(\d+) '
                        r'async_reset_checks=(\d+) release_checks=(\d+) signature=([0-9a-fA-F]{16})')
    match = re.fullmatch(pattern, lines[0]) if len(lines) == 1 else None
    if match is None:
        raise ValueError('missing, duplicate or malformed directed completion')
    names = ('overwrite_checks', 'reset_write_checks', 'reset_read_checks', 'async_reset_checks', 'release_checks')
    counts = dict(zip(names, map(int, match.groups()[:5])))
    expected = expected_counts(case)
    if counts != expected:
        raise ValueError('directed coverage counters differ from fixed plan')
    return {'name': case['name'], 'status': 'PASS', **counts, 'signature': match.group(6).lower()}


def expected_counts(case):
    depth = case['depth']
    addresses = {0, depth-1}
    if case['bank']:
        base = 0
        while base < depth:
            if base:
                addresses.update((base-1, base))
            left = depth-base
            base += 4096 if left >= 4096 else 1024 if left >= 1024 else 128
    n = len(addresses)
    return {'overwrite_checks': 2*n, 'reset_write_checks': 3*n+2, 'reset_read_checks': 2*n,
            'async_reset_checks': n+3, 'release_checks': 4}


def mutate_primitive(original, fault):
    """Return a private invalid implementation, never modify accepted sources."""
    if fault not in ('overwrite-dropped', 'reset-write-leak', 'reset-read-leak'):
        raise ValueError('unsupported injected fault')
    if fault == 'overwrite-dropped':
        declaration = 'logic [WIDTH-1:0] storage [0:DEPTH-1];'
        write = 'if (rst_n && wr_en && wr_addr < DEPTH) storage[wr_addr] <= wr_data;'
        if original.count(declaration) != 1 or original.count(write) != 1:
            raise ValueError('overwrite fault anchor is not unique')
        original = original.replace(declaration, declaration+'''
    reg fault_written [0:DEPTH-1];
    initial for (integer f=0; f<DEPTH; f=f+1) fault_written[f]=0;
''')
        return original.replace(write, '''if (rst_n && wr_en && wr_addr < DEPTH) begin
            if (!fault_written[wr_addr]) storage[wr_addr] <= wr_data;
            fault_written[wr_addr] <= 1;
        end''')
    begin = original.index('end else if (BACKEND == 3)')
    end = original.index('end else begin : g_bad_backend', begin)
    block = original[begin:end]
    old, new = (('.wr_en(wr_en && rst_n)', '.wr_en(wr_en)') if fault == 'reset-write-leak'
                else ('.rd_en(rd_en && rst_n)', '.rd_en(rd_en)'))
    if block.count(old) != 1:
        raise ValueError('reset fault anchor is not unique')
    return original[:begin]+block.replace(old, new)+original[end:]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development-adapter', action='store_true', help='also qualify the explicit development BACKEND=3 fixture')
    parser.add_argument('--inject-fault', choices=('overwrite-dropped', 'reset-write-leak', 'reset-read-leak'))
    args = parser.parse_args(argv)
    if args.inject_fault and not args.development_adapter:
        parser.error('fault injection requires explicit --development-adapter')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-sram-update-reset-'+uuid.uuid4().hex[:8]
    out = ROOT/'artifacts/runs'/run_id; out.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'kwt-sram-update-reset-v1', 'run_id': run_id, 'status': 'FAIL',
              'scope': 'directed functional development SRAM overwrite/reset behavior only',
              'official_validation': 'NOT_RUN', 'official_ppa': 'BLOCKED',
              'core_validation': 'NOT_RUN', 'soc_validation': 'NOT_RUN', 'synthesis': 'NOT_RUN',
              'started_utc': E.now(), 'commands': [], 'cases': [], 'binaries': [], 'generated_inputs': []}
    try:
        primitive = ROOT/'src/rtl/memory/kwt_sram_1rw.sv'
        bank = ROOT/'src/rtl/memory/kwt_sram_bank.sv'
        tb = ROOT/'sim/tb_kwt_sram_update_reset.sv'
        fixture = C.FIXTURE
        compiler = ROOT/'.tools/bin/iverilog'; runtime = ROOT/'.tools/bin/vvp'
        inputs = [Path(__file__), Path(C.__file__), Path(C.INTAKE.__file__), Path(E.__file__), primitive, bank, tb,
                  compiler, runtime, ROOT/'.tools/eda/usr/bin/iverilog', ROOT/'.tools/eda/usr/bin/vvp']
        inputs += sorted(p for p in (ROOT/'.tools/eda/usr/lib/x86_64-linux-gnu/ivl').iterdir() if p.is_file())
        if args.development_adapter: inputs.append(fixture)
        result['identity'] = E.source_identity(inputs, {'development_adapter': args.development_adapter,
                 'injected_fault': args.inject_fault, 'shapes': shape_plan()}, out/'source_identity.json')
        E.verify_records(result['identity']['inputs'])
        actual_primitive = primitive
        if args.inject_fault:
            actual_primitive = out/'private_fault_primitive.sv'
            actual_primitive.write_text(mutate_primitive(primitive.read_text(), args.inject_fault))
            result['generated_inputs'].append(E.record(actual_primitive))
            E.verify_records(result['identity']['inputs'])

        def native(argv, name):
            item = E.run_command(argv, ROOT, out/(name+'.log'), 30, 1)
            result['commands'].append(item)
            return item, C.verify_native(item)

        for name, tool in (('iverilog', compiler), ('vvp', runtime)):
            item, text = native([tool, '-V'], name+'-version'); C.clean_native(item, 0)
        backends = [0, 2, 3] if args.development_adapter else [0, 2]
        plan = [dict(shape, backend=backend, name=f'b{backend}-{shape["name"]}')
                for shape in shape_plan() for backend in backends]
        if args.inject_fault:
            plan = [dict(shape_plan()[0], backend=3, name='fault-'+args.inject_fault)]
        result['requested_cases'] = plan
        for case in plan:
            E.write_json(out/'case_progress.json', {'current_case': case['name'], 'updated_utc': E.now()})
            binary = out/(case['name']+'.vvp')
            argv = [compiler, '-g2012', '-s', 'tb_kwt_sram_update_reset', '-o', binary]
            argv += [f'-Ptb_kwt_sram_update_reset.{key}={value}' for key, value in
                     (('WIDTH', case['width']), ('DEPTH', case['depth']), ('BACKEND', case['backend']), ('USE_BANK', case['bank']))]
            argv += [actual_primitive, bank, *([fixture] if case['backend'] == 3 else []), tb]
            item, text = native(argv, case['name']+'-compile'); C.clean_native(item, 0)
            if re.search(r'\berror:|(?:^|\n)\s*(?:FATAL|ERROR)\b', text, re.I):
                raise ValueError('blocking compile diagnostic')
            record = E.record(binary); result['binaries'].append(record)
            E.verify_records(result['identity']['inputs']+result['generated_inputs']+[record])
            item, text = native([runtime, binary], case['name'])
            result['cases'].append({**case, **accept_case(case, item, text), 'command': item})
        groups = []
        for shape in shape_plan():
            family = [case for case in result['cases'] if case['bank'] == shape['bank']
                      and case['width'] == shape['width'] and case['depth'] == shape['depth']]
            signatures = {case['signature'] for case in family}
            if len(family) != len(backends) or len(signatures) != 1:
                raise ValueError('backend comparison differs for '+shape['name'])
            groups.append({'shape': shape['name'], 'backends': backends, 'status': 'MATCH', 'signature': signatures.pop()})
        result.update(status='PASS', backend_comparisons=groups, positive_cases=len(plan))
    except (OSError, ValueError, KeyError, NotImplementedError) as exc:
        result.update(status='FAIL', error=str(exc))
    try:
        E.verify_records(result.get('identity', {}).get('inputs', [])+result['generated_inputs']+result['binaries'])
        for command in result['commands']: C.verify_native(command)
    except (OSError, ValueError, KeyError) as exc:
        result.update(status='FAIL', evidence_error=str(exc))
    result['finished_utc'] = E.now(); E.write_json(out/'result.json', result)
    print(COMPLETE)
    print(json.dumps({'status': result['status'], 'official_validation': 'NOT_RUN', 'report': str(out/'result.json')}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
