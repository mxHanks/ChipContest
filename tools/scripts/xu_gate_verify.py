#!/usr/bin/env python3
"""Replay one public-port wrapper test against RTL and a synthesized netlist.

Default: actual local Yosys generic-gate synthesis, retaining only the SRAM
behavioral module as an explicit memory boundary. --netlist supplies a DC mapped
netlist with --cell-model inputs for same-test technology-mapped functional replay.
No SDF, timing closure, formal equivalence, full SoC or numerical accuracy claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ['LinearDoubleBufferCore.sv', 'LinearBufferedComputeCore.sv', 'BiasBankCache.sv', 'LinearAutoGroupCore.sv', 'LinearCachedCore.sv', 'LinearComputeCore.sv',
           'DotProductEngine.sv', 'MacController.sv', 'MacPEArray.sv', 'MacPE.sv',
           'XRowBuffer.sv', 'WeightBankArray.sv', 'WeightBank.sv', 'Sram1024x16.sv',
           'mem_1024x16.sv', 'accel_icb_slave.v']
PASS = re.compile(r'^XU_GATE_WRAPPER_PASS accepted=(\d+) retired=(\d+)$', re.M)
FAIL = re.compile(r'(?im)^\s*(?:Error:|%Error|FATAL:)|\b(?:XU_GATE_WRAPPER_FAIL|TEST_FAIL|FAILED|FAILURE)\b')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def snapshot(paths):
    return {str(path.resolve()): dict(bytes=path.stat().st_size, sha256=sha(path)) for path in sorted(set(paths))}


def tool(name):
    found = shutil.which(name)
    require(found is not None, 'required tool is unavailable: '+name)
    return str(Path(found).resolve())


def run(command, cwd, logfile, timeout):
    started = time.monotonic()
    with logfile.open('x') as stream:
        stream.write(json.dumps([str(arg) for arg in command])+'\n'); stream.flush()
        completed = subprocess.run(command, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    record = dict(command=[str(arg) for arg in command], cwd=str(cwd), returncode=completed.returncode,
                  elapsed_seconds=time.monotonic()-started, log_sha256=sha(logfile))
    return record


def include_dependencies(paths, includes):
    """Capture actual local Verilog include bytes; reject missing quoted includes."""
    inventory = set(paths)
    pending = list(paths)
    while pending:
        parent = pending.pop()
        for name in re.findall(r'^\s*`include\s+"([^"]+)"', parent.read_text(errors='replace'), re.M):
            choices = [parent.parent/name]+[directory/name for directory in includes]
            found = next((candidate.resolve() for candidate in choices if candidate.is_file()), None)
            require(found is not None, 'unresolved model include: '+str(parent)+':'+name)
            if found not in inventory:
                inventory.add(found); pending.append(found)
    return inventory


def simulation_commands(simulator, directory, inputs, includes, defines):
    if simulator == 'vcs':
        binary = directory/'simv'
        compile_command = [tool('vcs'), '-full64', '-sverilog', '-timescale=1ns/1ps',
                           '+nospecify', '+notimingcheck',
                           '-top', 'tb_xu_gate_wrapper', '+define+DISABLE_SV_ASSERTION=1',
                           '-Mdir='+str(directory/'csrc'), '-o', str(binary)]
        compile_command += ['+incdir+'+str(path) for path in includes]
        compile_command += ['+define+'+value for value in defines]
        execute_command = [str(binary)]
    else:
        binary = directory/'wrapper.vvp'
        compile_command = [tool('iverilog'), '-g2012', '-s', 'tb_xu_gate_wrapper', '-o', str(binary)]
        compile_command += ['-I'+str(path) for path in includes]
        compile_command += ['-D'+value for value in defines]
        execute_command = [tool('vvp'), str(binary)]
    return compile_command+[str(path) for path in inputs], execute_command+['+TRACE='+str(directory/'transactions.trace')]


def check_simulation(directory):
    log = (directory/'simulation.log').read_text(errors='replace')
    matches = PASS.findall(log)
    require(len(matches) == 1 and not FAIL.search(log), 'missing/duplicate PASS or failure marker: '+str(directory))
    accepted, retired = map(int, matches[0])
    require(accepted == retired and accepted > 10000, 'incomplete wrapper transaction workload')
    trace = directory/'transactions.trace'
    require(trace.is_file() and trace.stat().st_size > 0, 'transaction trace missing')
    lines = trace.read_text().splitlines()
    for index, line in enumerate(lines):
        require(re.fullmatch(r'\d+ [01] [0-9a-f]{3} [0-9a-f]{8} [0-9a-f] [0-9a-f]{8}', line) and
                int(line.split()[0]) == index, 'malformed, unknown or nonsequential transaction response')
    require(len(lines)+2 == accepted, 'trace plus two pipelined requests differs from accepted count')
    return dict(status='PASS', accepted=accepted, retired=retired, traced_transfers=len(lines),
                transaction_trace_sha256=sha(trace), simulation_log_sha256=sha(directory/'simulation.log'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    parser.add_argument('--sim', choices=['iverilog', 'vcs'], default='iverilog')
    parser.add_argument('--netlist', type=Path, help='existing mapped netlist; default synthesizes real RTL with Yosys')
    parser.add_argument('--netlist-sha256', help='expected existing mapped netlist identity')
    parser.add_argument('--cell-model', action='append', type=Path, default=[], help='standard-cell/SRAM functional Verilog model; repeatable')
    parser.add_argument('--model-support', action='append', type=Path, default=[], help='additional model files to hash without compiling')
    parser.add_argument('--include', action='append', type=Path, default=[])
    parser.add_argument('--define', action='append', default=[], help='model compiler define, e.g. FUNCTIONAL; repeatable')
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    out = args.out.resolve()
    require(not out.exists(), 'refusing to overwrite gate verification output')
    require(args.timeout > 0, '--timeout must be positive')
    if args.netlist:
        if args.netlist_sha256:
            require(args.netlist.is_file() and sha(args.netlist) == args.netlist_sha256, 'existing mapped netlist SHA differs')
        require(args.cell_model, '--netlist requires explicit functional --cell-model inputs')
    else:
        require(not args.cell_model and not args.model_support and not args.include and not args.define,
                'external cell model options require --netlist')
    perips = ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'
    rtl = [perips/name for name in SOURCES]
    testbench = ROOT/'tests/host/tb_xu_gate_wrapper.sv'
    external = [path.resolve() for path in args.cell_model+args.model_support]
    if args.netlist:
        external.append(args.netlist.resolve())
    includes = [path.resolve() for path in args.include]
    for path in rtl+[testbench]+external:
        require(path.is_file(), 'input file missing: '+str(path))
    external = include_dependencies(external, includes)
    inputs = snapshot(rtl+[testbench, Path(__file__).resolve()]+list(external))
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-wrapper-gate-replay-v1', status='RUNNING', simulator=args.sim,
                  scope='public ICB-port wrapper functional replay; zero delay, no SDF; SRAM model boundary explicit',
                  flow='external-technology-netlist' if args.netlist else 'local-yosys-generic-gates',
                  inputs=inputs, tool_identities={}, steps=[], simulations={},
                  limits=['Finite directed/randomized functional replay is not formal equivalence.',
                          'This wrapper test does not establish full-SoC post-synthesis functionality.',
                          'No physical timing, power, area or 600-sample accuracy claim.'])
    def save():
        report['log_sha256'] = {str(path.relative_to(out)): sha(path) for path in out.rglob('*.log') if path.is_file()}
        (out/'result.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    def execute(command, directory, name):
        record = run(command, directory, directory/(name+'.log'), args.timeout)
        report['steps'].append(record); save()
        require(record['returncode'] == 0, 'command failed; see '+str(directory/(name+'.log')))
        return record
    try:
        commands = [('iverilog', ['-V']), ('vvp', ['-V'])] if args.sim == 'iverilog' else [('vcs', ['-ID'])]
        if not args.netlist:
            commands.append(('yosys', ['-V']))
        for name, options in commands:
            executable = Path(tool(name))
            report['tool_identities'][name] = dict(path=str(executable), sha256=sha(executable))
            execute([str(executable)]+options, out, name+'-version')
        reference = out/'rtl'; reference.mkdir()
        compile_command, simulate_command = simulation_commands(args.sim, reference, [testbench]+rtl, [], [])
        execute(compile_command, reference, 'compile'); execute(simulate_command, reference, 'simulation')
        report['simulations']['rtl'] = check_simulation(reference); save()
        if args.netlist:
            netlist = args.netlist.resolve()
            gate_models = [path.resolve() for path in args.cell_model]
            report['cell_model_scope'] = 'caller supplied technology standard-cell / SRAM functional models; hashes retained'
        else:
            netlist = out/'mapped-generic.v'
            synth = out/'synth.ys'
            def quote(path):
                require('"' not in str(path) and '\n' not in str(path), 'unsupported Yosys path')
                return '"'+str(path)+'"'
            synth.write_text('read_verilog -sv -DSYNTHESIS '+ ' '.join(quote(path) for path in rtl)+'\n'+
                'blackbox mem_1024x16\n'+
                'synth -top accel_icb_slave -flatten\n'+
                'delete t:$scopeinfo\n'+
                'check -assert\n'+
                'write_json '+quote(out/'mapped-generic.json')+'\n'+
                'write_verilog -noattr '+quote(netlist)+'\n')
            execute([tool('yosys'), '-Q', '-T', '-s', str(synth)], out, 'synthesis')
            gate_models = [perips/'mem_1024x16.sv']
            report['cell_model_scope'] = 'Yosys generic logic gates emitted as Verilog primitives; only 16 SRAM behavior instances remain unsynthesized'
            mapped = json.loads((out/'mapped-generic.json').read_text())['modules']['accel_icb_slave']['cells']
            counts = {}
            for cell in mapped.values():
                counts[cell['type']] = counts.get(cell['type'], 0)+1
            require(counts.get('mem_1024x16') == 16 and all(name.startswith('$_') or name == 'mem_1024x16' for name in counts),
                    'generic netlist retains unsupported coarse cells or differs SRAM count')
            report['generic_cell_counts'] = counts
        report['netlist'] = dict(path=str(netlist), sha256=sha(netlist), bytes=netlist.stat().st_size)
        gate = out/'gate'; gate.mkdir()
        compile_command, simulate_command = simulation_commands(args.sim, gate, [testbench, netlist]+gate_models, includes, args.define)
        execute(compile_command, gate, 'compile'); execute(simulate_command, gate, 'simulation')
        report['simulations']['gate'] = check_simulation(gate)
        require((reference/'transactions.trace').read_bytes() == (gate/'transactions.trace').read_bytes(),
                'RTL/gate transaction response traces differ')
        require(report['simulations']['rtl']['accepted'] == report['simulations']['gate']['accepted'],
                'RTL/gate accepted transaction counts differ')
        require(snapshot([Path(path) for path in inputs]) == inputs, 'input bytes changed during replay')
        report.update(status='PASS', transaction_trace_byte_identical=True)
    except Exception as error:
        report.update(status='FAIL', error=str(error)); raise
    finally:
        save()
    print(json.dumps(dict(status=report['status'], flow=report['flow'], simulations=report['simulations'],
                          netlist=report['netlist'], result=str(out/'result.json')), indent=2))


if __name__ == '__main__':
    main()
