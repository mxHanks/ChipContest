#!/usr/bin/env python3
"""Inspect the independent dual-row candidate without mapping payload RAM to flops."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import uuid
import run_structural as BASE

ROOT = BASE.ROOT
MARKER = 'KWT_ROWPAIR_STRUCTURAL_COMPLETE'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pipe-mul', type=int, choices=(0, 1), default=1)
    p.add_argument('--result-buffers', type=int, choices=(1, 2), default=2)
    p.add_argument('--timeout', type=int, default=180)
    args = p.parse_args()
    if args.timeout <= 0:
        p.error('timeout must be positive')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    out = ROOT/'artifacts/runs'/(stamp+'-rowpair-structure-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    top = 'kwt_linear_engine_rowpair'
    source = ROOT/'src/rtl'/(top+'.sv')
    tool = ROOT/'.tools/bin/yosys'
    report = {'schema': 'kwt-rowpair-structure-v1', 'status': 'FAIL',
              'configuration': {'top': top, 'macs': 16, 'rows': 2, 'columns': 8,
                                'pipe_mul': args.pipe_mul, 'result_buffers': args.result_buffers},
              'scope': 'RAM-preserving RTLIL structure only, not mapped gate area, delay, power or equivalence',
              'physical_area': 'NOT_RUN', 'physical_timing': 'NOT_RUN', 'physical_power': 'NOT_RUN',
              'sram_macro_mapping': 'NOT_RUN', 'gate_equivalence': 'NOT_RUN', 'soc': 'NOT_RUN',
              'inputs': [], 'commands': []}
    try:
        report['inputs'] = [BASE.record(path) for path in (source, Path(__file__), Path(BASE.__file__), tool,
                              ROOT/'.tools/synth/usr/bin/yosys', ROOT/'.tools/synth/usr/bin/yosys-abc')]
        (out/'input.sv').write_bytes(source.read_bytes())
        script = out/'run.ys'
        script.write_text('\n'.join(['read_verilog -sv -defer input.sv',
            f'chparam -set PIPE_MUL {args.pipe_mul} -set RESULT_BUFFERS {args.result_buffers} {top}',
            f'hierarchy -check -top {top}', 'proc', 'opt', 'memory_dff', 'memory_collect',
            'opt_clean', 'check -assert', 'stat -width', 'tee -o stats.json stat -json',
            'write_json netlist.json', 'log '+MARKER, '']))
        report['script'] = BASE.record(script)
        with (ROOT/'.tools/synth/structural.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run = BASE.run_command([str(tool), '-Q', '-s', 'run.ys'], out, out/'synthesis.log', args.timeout)
            report['commands'].append(run)
        log = (out/'synthesis.log').read_text()
        if run['exit_code'] or run['timed_out'] or len(re.findall('^'+MARKER+'$',log,re.M)) != 1:
            raise ValueError('synthesis failed or incomplete; inspect original log')
        structure = BASE.summarize(json.loads((out/'netlist.json').read_text()), top)
        report['structure'] = structure
        # Confirm exact bank boundaries as well as total retained payload bits.
        # No physical inference is made from these structural counts.
        expected = 373760 + args.result_buffers*512*41
        if structure['memory_bits'] != expected:
            raise ValueError(f'retained memory {structure["memory_bits"]} differs from expected {expected}')
        actual_banks = Counter((m['words'], m['width']) for m in structure['memories'])
        expected_banks = Counter({(3200,16):1, (3136,16):1, (2048,16):8, (32,40):8, (512,41):args.result_buffers})
        if actual_banks != expected_banks:
            raise ValueError('retained bank shapes do not match the intended access architecture')
        multiply = structure['multipliers']
        if len(multiply) != 16 or any((m['a_width'],m['b_width'],m['y_width'],m['a_signed'],m['b_signed']) != (16,16,32,True,True) for m in multiply):
            raise ValueError('expected exactly sixteen signed16x16-to32 multipliers')
        if structure['mapping_warnings']:
            raise ValueError('multiport or asynchronous memory requires explicit architecture review')
        report['outputs'] = [BASE.record(out/name) for name in ('netlist.json','stats.json')]
        for item in report['inputs']:
            if BASE.record(item['path'])['sha256'] != item['sha256']:
                raise ValueError('source/tool changed during synthesis')
        report['status'] = 'PASS'
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'report':str(out/'result.json'),'error':report.get('error')}))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
