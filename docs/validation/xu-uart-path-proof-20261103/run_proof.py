#!/usr/bin/env python3
"""xu: reproduce the real UART boundary simulation and source-derived miter.

The combinational miter expands the actual RTL cells' one-edge next-state
functions. It is a functional sampling-boundary proof, not a latch timing model.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RTL = ROOT / 'third-party/e203_hbirdv2/rtl/e203'
SOURCES = [
    HERE / 'uart_boundary.sv',
    RTL / 'general/sirv_gnrl_icbs.v', RTL / 'general/sirv_gnrl_bufs.v',
    RTL / 'general/sirv_gnrl_dffs.v', RTL / 'perips/sirv_ResetCatchAndSync_2.v',
    RTL / 'perips/sirv_AsyncResetRegVec_129.v', RTL / 'perips/sirv_AsyncResetReg.v',
] + sorted((RTL / 'perips/apb_uart').glob('*.v'))
CONTEXT = [RTL / 'subsys/e203_subsys_main.v', RTL / 'subsys/e203_subsys_perips.v']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(argv, output, expected=0):
    with output.open('wb') as f:
        run = subprocess.run(argv, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
    result = dict(argv=[str(x) for x in argv], exit_code=run.returncode,
                  log=str(output.relative_to(ROOT)), sha256=sha(output),
                  bytes=output.stat().st_size)
    if expected is not None and run.returncode != expected:
        raise RuntimeError(f'unexpected exit {run.returncode}: {output}')
    return result


class Miter:
    def __init__(self, original, fault=None):
        self.original = original
        self.n = 2
        self.m = dict(attributes={}, ports={}, cells={}, netnames={})
        self.counter = 0
        self.seq = {}
        self.comb = {}
        self.shared = {}
        self.next_by_q = [dict(), dict()]
        self.latches = []
        allowed = {'$adff', '$adffe', '$sdffce'}
        for name, cell in original['cells'].items():
            if cell['type'] in allowed:
                if cell['connections']['CLK'] != original['ports']['clk']['bits'] or int(cell['parameters']['CLK_POLARITY'], 2) != 1:
                    raise ValueError('source has a different clock/edge; one-edge model must be reviewed')
                self.seq[name] = cell
            elif cell['type'] == '$dlatch':
                self.latches.append(cell)
            elif cell['type'] == '$scopeinfo':
                pass
            elif any(k in cell['port_directions'] and cell['port_directions'][k] == 'output'
                     for k in ['Q']):
                raise ValueError('unhandled state cell: ' + cell['type'])
            else:
                self.comb[name] = cell
        if len(self.latches) != 1 or self.latches[0]['connections']['Q'] != self.bits('uart.fifo_tx_data'):
            raise ValueError('expected exactly the real eight-bit UART latch')
        for name, port in original['ports'].items():
            if port['direction'] == 'input':
                bits = self.input(name, len(port['bits']))
                self.shared.update(zip(port['bits'], bits))
        qbits = sorted(set(b for c in self.seq.values() for b in c['connections']['Q']))
        if any(x in self.shared for x in qbits):
            raise ValueError('state overlaps primary input')
        self.shared.update(zip(qbits, self.input('xu_shared_current_state', len(qbits))))
        driven = set(b for c in original['cells'].values()
                     for p, bits in c['connections'].items() if c['port_directions'].get(p) == 'output'
                     for b in bits if isinstance(b, int))
        named = set(b for n in original['netnames'].values() for b in n['bits'] if isinstance(b, int))
        undriven = sorted(named - driven - set(self.shared))
        if undriven:
            self.shared.update(zip(undriven, self.input('xu_shared_undriven_unused_bits', len(undriven))))
        self.maps = []
        self.nexts = []
        self.write_checks = []
        for side in range(2):
            mapping = dict(self.shared)

            def map_bit(b):
                if isinstance(b, str):
                    return b
                if b not in mapping:
                    mapping[b] = self.alloc(1)[0]
                return mapping[b]

            self.maps.append(mapping)
            for name, cell in self.comb.items():
                c = copy.deepcopy(cell)
                c['connections'] = {p: [map_bit(b) for b in v]
                                    for p, v in cell['connections'].items()}
                self.m['cells'][f's{side}_{name}'] = c
            lat = self.latches[0]
            lc = {k: [map_bit(b) for b in v] for k, v in lat['connections'].items()}
            active = self.polar(lc['EN'], lat['parameters']['EN_POLARITY'])
            if fault == 'inverted_latch_enable':
                active = self.not_(active)
            old = self.input(f'xu_old_latch_{side}', 8)
            self.mux(old, lc['D'], active, y=lc['Q'])
            nexts = []
            for name, cell in self.seq.items():
                cc = {k: [map_bit(b) for b in v] for k, v in cell['connections'].items()}
                p = cell['parameters']
                d = cc['D']
                if cell['type'] == '$sdffce':
                    d = self.mux(d, list(reversed(p['SRST_VALUE'])), self.polar(cc['SRST'], p['SRST_POLARITY']))
                if 'EN' in cc:
                    ena = self.polar(cc['EN'], p['EN_POLARITY'])
                    if fault == 'fifo_memory_always_writes' and cell['connections']['Q'] in self.tx_memories():
                        ena = ['1']
                    d = self.mux(cc['Q'], d, ena)
                if 'ARST' in cc:
                    d = self.mux(d, list(reversed(p['ARST_VALUE'])), self.polar(cc['ARST'], p['ARST_POLARITY']))
                for q, nxt in zip(cell['connections']['Q'], d):
                    self.next_by_q[side][q] = nxt
                nexts.extend(d)
                if cell['connections']['Q'] in self.tx_memories():
                    # Actual memory samples D only on its real enable, outside reset.
                    wr = self.and_(self.polar(cc['EN'], p['EN_POLARITY']),
                                   self.not_(self.polar(cc['ARST'], p['ARST_POLARITY'])))
                    self.write_checks.append(self.or_(self.not_(wr), self.eq(cc['D'], self.signal(side, 'cmd_wdata')[:8])))
            self.nexts.append(nexts)
        self.output('next_state_equal', self.eq(*self.nexts))
        obs = [[], []]
        for side in range(2):
            for name, port in original['ports'].items():
                if port['direction'] == 'output':
                    obs[side].extend(self.mapbits(side, port['bits']))
        self.output('observable_equal', self.eq(*obs))
        self.output('every_fifo_write_current_byte', self.all_(self.write_checks))
        valid = self.signal(0, 'uart.fifo_tx_valid')
        current = self.eq(self.signal(0, 'uart.fifo_tx_data'), self.signal(0, 'cmd_wdata')[:8])
        self.output('valid_data_current_byte', self.or_(self.not_(valid), current))
        apb = self.signal(0, 'bridge.apb_enable_r')
        rsp = self.signal(0, 'rsp_valid')
        self.output('bridge_invariant_pre', self.not_(self.and_(apb, rsp)))
        apb_n = [self.next_by_q[0][self.bits('bridge.apb_enable_r')[0]]]
        rsp_n = [self.next_by_q[0][self.bits('rsp_valid')[0]]]
        self.output('bridge_invariant_next', self.not_(self.and_(apb_n, rsp_n)))
        self.output('bridge_reset_base', self.or_(self.signal(0, 'main_rst_n'),
                    self.and_(self.not_(apb_n), self.not_(rsp_n))))
        accepted_thr = self.all_([
            self.signal(0, 'cmd_valid'), self.signal(0, 'cmd_ready'),
            self.not_(self.signal(0, 'cmd_read')),
            self.eq(self.signal(0, 'cmd_addr')[2:5], ['0'] * 3),
            self.not_([self.signal(0, 'uart.regs_q')[31]]),
        ])
        self.output('fifo_valid_is_accepted_thr', self.eq(valid, accepted_thr))
        self.model = dict(creator='xu actual-source sampling-boundary miter',
                          modules={'xu_uart_miter': self.m})

    def bits(self, name):
        return self.original['netnames'][name]['bits']

    def tx_memories(self):
        return [self.bits(f'uart.uart_tx_fifo_i.buffer[{i}]') for i in range(16)]

    def alloc(self, width):
        bits = list(range(self.n, self.n + width)); self.n += width
        return bits

    def input(self, name, width):
        bits = self.alloc(width)
        self.m['ports'][name] = dict(direction='input', bits=bits)
        self.m['netnames'][name] = dict(hide_name=0, bits=bits, attributes={})
        return bits

    def output(self, name, bits):
        self.m['ports'][name] = dict(direction='output', bits=bits)
        self.m['netnames'][name] = dict(hide_name=0, bits=bits, attributes={})

    def mapbits(self, side, bits):
        return [self.maps[side][b] if isinstance(b, int) else b for b in bits]

    def signal(self, side, name):
        return self.mapbits(side, self.bits(name))

    def cell(self, typ, conn, pars):
        self.counter += 1
        self.m['cells'][f'xu_{self.counter}'] = dict(hide_name=0, type=typ,
            parameters=pars, attributes={}, connections=conn,
            port_directions={p: 'output' if p == 'Y' else 'input' for p in conn})
        return conn['Y']

    def unary(self, typ, a):
        return self.cell(typ, dict(A=a, Y=self.alloc(1)), dict(A_WIDTH=len(a), A_SIGNED=0, Y_WIDTH=1))

    def not_(self, a): return self.unary('$logic_not', a)

    def binary(self, typ, a, b):
        return self.cell(typ, dict(A=a, B=b, Y=self.alloc(1)),
                         dict(A_WIDTH=len(a), B_WIDTH=len(b), A_SIGNED=0, B_SIGNED=0, Y_WIDTH=1))

    def and_(self, a, b): return self.binary('$logic_and', a, b)
    def or_(self, a, b): return self.binary('$logic_or', a, b)
    def eq(self, a, b): return self.binary('$eqx', a, b)

    def all_(self, xs):
        result = ['1']
        for x in xs: result = self.and_(result, x)
        return result

    def polar(self, bits, polarity):
        return bits if int(polarity, 2) else self.not_(bits)

    def mux(self, a, b, s, y=None):
        return self.cell('$mux', dict(A=a, B=b, S=s, Y=y or self.alloc(len(a))), dict(WIDTH=len(a)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    records = []
    frozen_paths = SOURCES + CONTEXT + [HERE / 'tb_uart_path.sv', Path(__file__).resolve()]
    snapshot = {str(p.relative_to(ROOT)): dict(sha256=sha(p), bytes=p.stat().st_size) for p in frozen_paths}
    records.append(invoke(['iverilog', '-V'], out / 'iverilog-version.log'))
    records.append(invoke(['yosys', '-V'], out / 'yosys-version.log'))
    # Only the counterfactual copy is edited. The production source stays frozen.
    # It changes the *invalid* latch value every cycle; valid data is unchanged.
    uart = (RTL / 'perips/apb_uart/apb_uart.v').read_text()
    assert uart.count('module apb_uart_sv ') == 1
    assert uart.count('    input  wire                        CLK,') == 1
    assert uart.count("        fifo_tx_valid   = 1'b0;") == 1
    poisoned_uart = out / 'xu_uart_counterfactual.v'
    poisoned_uart.write_text(uart.replace('module apb_uart_sv ', 'module xu_uart_counterfactual_sv ', 1)
        .replace('    input  wire                        CLK,', '    input wire [7:0] xu_invalid_data,\n    input  wire                        CLK,', 1)
        .replace("        fifo_tx_valid   = 1'b0;", "        fifo_tx_data = xu_invalid_data;\n        fifo_tx_valid   = 1'b0;", 1))
    boundary = (HERE / 'uart_boundary.sv').read_text()
    poisoned_boundary = out / 'xu_counterfactual_boundary.sv'
    poisoned_boundary.write_text(boundary.replace('module xu_uart_boundary(', 'module xu_counterfactual_boundary(\n  input wire [7:0] xu_invalid_data,', 1)
        .replace('  apb_uart_sv #', '  xu_uart_counterfactual_sv #', 1)
        .replace('    .CLK(clk),.RSTN(main_rst_n)', '    .xu_invalid_data(xu_invalid_data),.CLK(clk),.RSTN(main_rst_n)', 1))
    executable = out / 'uart.vvp'
    records.append(invoke(['iverilog', '-g2012', '-DDISABLE_SV_ASSERTION=1', '-s', 'tb_xu_uart_path', '-o', str(executable),
                           str(HERE / 'tb_uart_path.sv'), *map(str, SOURCES), str(poisoned_uart), str(poisoned_boundary)], out / 'compile.log'))
    for seed in [1, 7, 13, 42, 12345, 987654321, 2654435769, 4294967295]:
        path = out / f'seed-{seed}.log'
        records.append(invoke(['vvp', str(executable), f'+SEED={seed}'], path))
        if path.read_bytes().count(b'XU_UART_REAL_SOURCE_PASS') != 1:
            raise ValueError('missing unique four-state PASS')
    negative = out / 'negative-illegal-stall.log'
    records.append(invoke(['vvp', str(executable), '+SEED=1', '+XU_CORRUPT_STALLED'], negative, expected=1))
    if b'illegal stimulus changed a stalled ICB request' not in negative.read_bytes():
        raise ValueError('illegal stimulus checker did not trigger')
    # Deliberately corrupt a current valid byte in a derived copy of the fixed
    # source, and require the independently maintained memory scoreboard to fail.
    old = 'fifo_tx_data  = PWDATA[7:0];'
    assert uart.count(old) == 1
    mutant = out / 'xu_mutant_current_byte.v'
    mutant.write_text(uart.replace(old, "fifo_tx_data  = PWDATA[7:0] ^ 8'h01;", 1))
    mutant_executable = out / 'mutant.vvp'
    mutant_sources = [mutant if p == RTL / 'perips/apb_uart/apb_uart.v' else p for p in SOURCES]
    records.append(invoke(['iverilog', '-g2012', '-DDISABLE_SV_ASSERTION=1', '-s', 'tb_xu_uart_path', '-o', str(mutant_executable),
        str(HERE / 'tb_uart_path.sv'), *map(str, mutant_sources), str(poisoned_uart), str(poisoned_boundary)], out / 'mutant-compile.log'))
    negative = out / 'negative-current-byte.log'
    records.append(invoke(['vvp', str(mutant_executable), '+SEED=1'], negative, expected=1))
    if b'FIFO sampled stale byte' not in negative.read_bytes():
        raise ValueError('current byte checker did not trigger')
    source_json = out / 'actual-boundary.json'
    script = out / 'extract.ys'
    script.write_text('read_verilog -sv -D DISABLE_SV_ASSERTION=1 ' + ' '.join(map(str, SOURCES)) +
                      f'\nhierarchy -check -top xu_uart_boundary\nproc\nflatten\nopt\nmemory_map\nopt\nwrite_json {source_json}\n')
    records.append(invoke(['yosys', '-Q', '-T', '-s', str(script)], out / 'extract.log'))
    design = json.loads(source_json.read_text())['modules']['xu_uart_boundary']
    common = ['next_state_equal', 'observable_equal', 'every_fifo_write_current_byte', 'valid_data_current_byte', 'bridge_reset_base']
    for fault in [None, 'inverted_latch_enable', 'fifo_memory_always_writes']:
        tag = fault or 'positive'
        miter = Miter(design, fault)
        model_path = out / f'miter-{tag}.json'; model_path.write_text(json.dumps(miter.model, sort_keys=True))
        checks = common if not fault else ['next_state_equal']
        ys = out / f'miter-{tag}.ys'
        ys.write_text(f'read_json {model_path}\nhierarchy -check -top xu_uart_miter\nopt\ncheck -assert\n'
                      'sat -verify -enable_undef -set-def-inputs ' + ' '.join(f'-prove {p} 1' for p in checks) +
                      f' -show-inputs -show-outputs -dump_vcd {out / (tag + ".vcd")}\n')
        record = invoke(['yosys', '-Q', '-T', '-s', str(ys)], out / f'miter-{tag}.log', expected=None)
        records.append(record)
        success = b'SAT proof finished - no model found: SUCCESS!' in (out / f'miter-{tag}.log').read_bytes()
        if (fault is None) != success or (fault is None and record['exit_code'] != 0) or (fault and record['exit_code'] == 0):
            raise ValueError('unexpected formal result: ' + tag)
        if fault and (b'SAT proof finished - model found: FAIL!' not in (out / f'miter-{tag}.log').read_bytes()
                      or not (out / (tag + '.vcd')).is_file() or not (out / (tag + '.vcd')).stat().st_size):
            raise ValueError('negative formal run did not produce a real counterexample: ' + tag)
        if fault is None:
            ind = out / 'bridge-induction.ys'
            ind.write_text(f'read_json {model_path}\nhierarchy -check -top xu_uart_miter\nopt\n'
                           'sat -verify -enable_undef -set-def-inputs -set bridge_invariant_pre 1 '
                           '-prove bridge_invariant_next 1 -prove fifo_valid_is_accepted_thr 1 -show-outputs\n')
            records.append(invoke(['yosys', '-Q', '-T', '-s', str(ind)], out / 'bridge-induction.log'))
            if (out / 'bridge-induction.log').read_bytes().count(b'SAT proof finished - no model found: SUCCESS!') != 1:
                raise ValueError('missing unique bridge induction proof')
    if snapshot != {str(p.relative_to(ROOT)): dict(sha256=sha(p), bytes=p.stat().st_size) for p in frozen_paths}:
        raise ValueError('source changed during proof')
    result = dict(schema='xu-uart-source-boundary-proof-v1', status='FUNCTIONAL_BOUNDARY_PROVED_NOT_TIMING_QUALIFIED',
                  source_snapshot=snapshot, commands=records, seeds=8,
                  expanded_state_cells=len(Miter(design).seq),
                  expanded_state_bits=sum(len(c['connections']['Q']) for c in Miter(design).seq.values()),
                  simulation_clock_period_ns=10,
                  source_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  rtl_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT / 'third-party/e203_hbirdv2', text=True).strip(),
                  limitations=['two-state one-step functional induction with an ideal transparent-latch sampling boundary',
                               'four-state simulation is finite coverage, not a four-state exhaustive proof',
                               'selected UART boundary omits CPU/fabric/clock gating and is not a full-SoC proof',
                               'no STA exemption, transparent-latch timing, CDC, RDC, metastability, or MTBF claim'])
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], result=str(out / 'result.json')), ensure_ascii=False))


if __name__ == '__main__':
    main()
