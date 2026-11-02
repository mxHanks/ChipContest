#!/usr/bin/env python3
"""Compare the frozen SoC TB with an independent full-scope SRAM-macro top.

No make/install or shared simulator cache is used. Vendor models remain at their
supplied path; only their SHA and command line are recorded in the run output.
This is RTL functional development evidence, never mapped GLS or PPA evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[2]
RTL = ROOT / 'third-party/e203_hbirdv2/rtl/e203'
TB = ROOT / 'tests/e203/tb_accel_soc.sv'
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tools/scripts'))
import e203_soc as soc
import xu_firmware_contract as contract


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('frozen TB transformation anchor differs: ' + old[:100])
    return text.replace(old, new)


def preload_tasks(macro):
    """Vendor word A bit b resides in mem[A>>2][4*b+(A&3)].

    Each generated bank/lane index is constant. Only the row is variable, so the
    path works in VCS, Icarus and Verilator without variable generate indexing.
    Read the exact original TB shadow arrays, preserving X in untouched words.
    No backdoor is used to populate accelerator weights: the CPU uploads them.
    """
    lines = ['// Non-synthesizable preload: no force, no changes to live bus timing.']
    if macro:
        lines += ['function automatic [63:0] xu_pack_vendor_row;',
                  '  input [15:0] a0,a1,a2,a3;', '  integer b;', '  begin',
                  '    for (b=0;b<16;b=b+1)',
                  '      xu_pack_vendor_row[4*b +: 4]={a3[b],a2[b],a1[b],a0[b]};',
                  '  end', 'endfunction']
    for name, path, depth, width, source in [
        ('itcm', '`ITCM', 8192, 64, 'xu_program_words'),
        ('shared', 'dut.u_shared.storage', 131072, 32, 'ram')]:
        lines += ['task xu_preload_' + name + ';', '  integer row;', '  begin']
        if macro:
            for bank in range(depth // 1024):
                for lane in range(width // 16):
                    args = ','.join('%s[%d+4*row+%d][%d +: 16]' %
                                    (source, bank*1024, mux, lane*16) for mux in range(4))
                    lines += ['    for (row=0;row<256;row=row+1)',
                              '      %s.macro_storage.depth_bank[%d].width_lane[%d].macro.mem[row]=' % (path, bank, lane),
                              '        xu_pack_vendor_row(' + args + ');']
        else:
            lines += ['    for (row=0;row<%d;row=row+1)' % depth,
                      '      %s.mem_r[row]=%s[row];' % (path, source)]
        lines += ['  end', 'endtask']
    return '\n'.join(lines) + '\n'


def instrument_nominal_clock(text, wrapped):
    text = '`timescale 1ns/1fs\n' + text
    clock_path = 'dut.' + ('u_soc.' if wrapped else '') + 'u_e203_subsys_top.u_e203_subsys_main.u_e203_subsys_hclkgen'
    declarations = '''
  integer xu_half_index=0, xu_reset_edges=0, xu_static_checks=0;
  real xu_target_ns;
  `define XU_HCLK CLOCK_PATH
  always @(posedge clk) begin
    if (!rst_n) xu_reset_edges=xu_reset_edges+1;
    else begin
      if ({`XU_HCLK.test_mode,`XU_HCLK.pllbypass,`XU_HCLK.plloutdivby1,
           `XU_HCLK.plloutdiv,`XU_HCLK.pll_RESET,`XU_HCLK.pll_ASLEEP,
           `XU_HCLK.pll_OD,`XU_HCLK.pll_M,`XU_HCLK.pll_N} !==
          {1'b0,1'b1,1'b1,6'b0,1'b0,1'b0,2'd2,8'd50,5'd2})
        $fatal(1,"nominal150 clock controls departed from static reset bypass/divby1 mode");
      xu_static_checks=xu_static_checks+1;
    end
  end
'''.replace('CLOCK_PATH', clock_path)
    text = once(text, 'module tb_xu_soc_ppa;', 'module tb_xu_soc_ppa;' + declarations)
    text = once(text, '  always #2 clk = ~clk;', '''  initial forever begin
    xu_half_index=xu_half_index+1;
    xu_target_ns=xu_half_index*(10.0/3.0);
    #(xu_target_ns-$realtime);
    clk=~clk;
  end''')
    text = once(text, '  always #33 lfclk = ~lfclk;', '  always #15258.7890625 lfclk = ~lfclk;')
    text = once(text, '    #120 rst_n=1;', '''    #(200-$realtime);
    if (xu_reset_edges!=30) $fatal(1,"nominal150 reset HF edge count=%0d",xu_reset_edges);
    rst_n=1;
    $display("PPA_CLOCK mode=nominal150 hf_nominal_period_ns=6.666666666666667 precision_fs=1 reset_hf_edges=%0d",xu_reset_edges);''')
    text = once(text, '      if (in_window) begin\n        perf_active=1;', '''      if (in_window) begin
        if (!perf_active) begin
          $display("PPA_WINDOW_BEGIN layer=%0d cycle=%0d time_ns=%0.12f tick_fs=%0.0f",layer,cycles,$realtime,$realtime*1000000.0);
          $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",layer,$realtime*1000000.0);
        end
        perf_active=1;''')
    text = once(text, '        if (shared_retire && final_write_pending) begin\n          perf_active=0;', '''        if (shared_retire && final_write_pending) begin
          $display("PPA_WINDOW_END layer=%0d cycle=%0d time_ns=%0.12f tick_fs=%0.0f",layer,cycles,$realtime,$realtime*1000000.0);
          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",layer,$realtime*1000000.0);
          perf_active=0;''')
    text = once(text, '      writes = 0; first_cycle = -1; final_write_pending = 0;',
                '      $display("XU_CACHE_RELOAD task=%0d done_before_begin=1 scope=shared_fixture tick=%0.0f",index,$realtime*1000000.0);\n'
                '      writes = 0; first_cycle = -1; final_write_pending = 0;')
    text = once(text, '        $display("SOC_PASS tasks=%0d outputs=%0d writes=%0d",',
                '        $display("XU_CLOCK_STATIC_PASS checked_hf_edges=%0d",xu_static_checks);\n'
                '        $display("SOC_PASS tasks=%0d outputs=%0d writes=%0d",')
    return text


def generate_tb(macro, clock_mode='reference4ns', reference=False):
    text = TB.read_text()
    text = once(text, 'module tb_accel_soc;', 'module tb_xu_soc_ppa;')
    if reference:
        text = once(text, '$dumpvars(0,tb_accel_soc);', '$dumpvars(0,tb_xu_soc_ppa);')
        return '// Generated from original TB SHA256 ' + sha(TB) + '\n' + instrument_nominal_clock(text, False)
    text = once(text, '  reg rsp_valid = 0;', '  wire rsp_valid;')
    text = once(text, '  reg [31:0] rsp_rdata = 0;', '  wire [31:0] rsp_rdata;\n  wire rsp_err;')
    text = once(text, '  reg [7:0] program_bytes [0:65535];',
                '  reg [7:0] program_bytes [0:65535];\n  reg [63:0] xu_program_words [0:8191];')
    text = once(text, '  assign cmd_ready = (!rsp_valid || rsp_ready) && (cycles % 7 != 0);',
                '\n'.join('  assign %s=dut.ext_sysmem_%s;' % (n, n) for n in
                          ['cmd_ready','cmd_valid','cmd_read','cmd_addr','cmd_wdata','cmd_wmask',
                           'rsp_ready','rsp_valid','rsp_rdata','rsp_err']))
    text = once(text, '`define CPU dut.u_e203_subsys_top', '`define CPU dut.u_soc.u_e203_subsys_top')
    text = once(text, '`define ACCEL dut.u_e203_subsys_top', '`define ACCEL dut.u_soc.u_e203_subsys_top')
    text = once(text, '  e203_soc_top #(.EXTERNAL_SYSMEM(1)) dut (', '  xu_soc_ppa_top dut (')
    begin = text.index('    .ext_sysmem_cmd_valid(cmd_valid),')
    end = text.index('    .hfxoscen()', begin)
    text = text[:begin] + text[end:]
    text = once(text, '  task load_layer(input integer index);',
                preload_tasks(macro) + '\n  task load_layer(input integer index);')
    text = once(text, '      writes = 0; first_cycle = -1; final_write_pending = 0;',
                '      xu_preload_shared();\n      writes = 0; first_cycle = -1; final_write_pending = 0;')
    text = once(text, '      `ITCM.mem_r[i] = {program_bytes', '      xu_program_words[i] = {program_bytes')
    text = once(text, '    ram[HOST/4]=tasks;', '    xu_preload_itcm();\n    ram[HOST/4]=tasks;')
    # Vendor time-zero initialization can overwrite a same-slot backdoor.
    # Wait until t=1ns, before the first HF edge in either clock mode.
    text = once(text, '    for (i=0; i<65536; i=i+1) program_bytes[i]=0;',
                '    #1; // Finish vendor initialization before the first HF edge.\n'
                '    for (i=0; i<65536; i=i+1) program_bytes[i]=0;')
    text = once(text, '$dumpvars(0,`ACCEL);', '$dumpvars(0,dut);')
    text = once(text, '$dumpvars(0,tb_accel_soc);', '$dumpvars(0,tb_xu_soc_ppa);')
    text = once(text, '      // Response retirement is independent of accepting the next command.\n'
                '      if (rsp_valid && rsp_ready) rsp_valid <= 0;\n',
                '      if (rsp_valid && rsp_err) $fatal(1,"shared endpoint error");\n'
                '      if (cmd_ready !== ((!rsp_valid || rsp_ready) && (cycles % 7 != 0)))\n'
                '        $fatal(1,"shared endpoint backpressure phase differs cycle=%0d",cycles);\n')
    text = once(text, '        rsp_valid <= cmd_valid;\n', '')
    text = once(text, '            rsp_rdata <= ram[word_index];\n', '')
    text = once(text, '    if (cycles > max_cycles) $fatal',
                '    if (cycles>0 && cycles%1000000==0) begin\n'
                '      $display("PPA_PROGRESS cycles=%0d layer=%0d writes=%0d completed=%0d",cycles,layer,writes,completed);\n'
                '      $fflush();\n'
                '    end\n'
                '    if (cycles > max_cycles) $fatal')
    if clock_mode == 'nominal150':
        text = instrument_nominal_clock(text, True)
    else:
        # The preload delay must not shift the original absolute reset release.
        text = once(text, '    #120 rst_n=1;', '    #(120-$realtime) rst_n=1;')
    return '// Generated from original TB SHA256 ' + sha(TB) + '\n' + text


def check_windows(log, layers):
    records = {}
    for kind, layer, cycle, time_ns, tick in re.findall(
            r'^PPA_WINDOW_(BEGIN|END) layer=(\d+) cycle=(\d+) time_ns=([0-9.]+) tick_fs=(\d+)$', log, re.M):
        key = (int(layer), kind)
        if key in records:
            raise ValueError('duplicate nominal150 task boundary')
        records[key] = dict(cycle=int(cycle), time_ns=time_ns, tick=int(tick))
    if len(records) != 2*len(layers):
        raise ValueError('nominal150 task boundary count differs')
    result = []
    for layer in layers:
        begin, end = [records[(layer['layer'], kind)] for kind in ['BEGIN','END']]
        if end['cycle']-begin['cycle']+1 != layer['cycles']:
            raise ValueError('nominal150 final-response/inclusive-cycle boundary differs')
        span = end['tick']-begin['tick']
        ideal = Fraction((layer['cycles']-1)*20000000, 3)
        if abs(Fraction(span)-ideal) > 1:
            raise ValueError('nominal150 absolute clock phase accumulated more than 1fs')
        result.append(dict(layer=layer['layer'], begin=begin, end=end, duration_ticks=span,
                           timescale_seconds=1e-15, nominal_hf_period_seconds=20e-9/3,
                           interval='first input/parameter read accepted through final Y response retired; elapsed span excludes an extra inclusive cycle'))
    static = re.findall(r'^XU_CLOCK_STATIC_PASS checked_hf_edges=(\d+)$', log, re.M)
    if len(static) != 1 or int(static[0]) < sum(x['cycles'] for x in layers):
        raise ValueError('nominal150 static control assertions did not cover task intervals')
    return result


def build_command(sim, variant, directory, filelist, trace, clock_mode='reference4ns'):
    includes = [RTL / p for p in ['core', 'perips', 'perips/apb_i2c']]
    top = 'tb_accel_soc' if variant == 'reference' and clock_mode == 'reference4ns' else 'tb_xu_soc_ppa'
    timescale = '1ns/1fs' if clock_mode == 'nominal150' else '1ns/10ps'
    defines = ['DISABLE_SV_ASSERTION=1'] + (['ARM_UD_MODEL'] if variant == 'macro' else [])
    if sim == 'verilator':
        return ['verilator', '--binary', '--timing', '-j', '2', '-Wno-fatal',
                '--timescale', timescale, '--output-split', '20000',
                '--output-split-cfuncs', '500', *(['--trace'] if trace else []),
                '--top-module', top, '-Mdir', str(directory / 'obj'), '-o', 'soc',
                *['-D'+x for x in defines], *['-I'+str(x) for x in includes], '-f', str(filelist)]
    if sim == 'vcs':
        return ['vcs', '-full64', '-sverilog', '-timescale='+timescale, '-top', top,
                *(['-debug_access+all'] if trace else []),
                *['+define+'+x for x in defines], *['+incdir+'+str(x) for x in includes],
                '-f', str(filelist), '-Mdir='+str(directory / 'csrc'), '-o', str(directory / 'soc')]
    return ['iverilog', '-g2012', '-s', top, *['-D'+x for x in defines],
            *['-I'+str(x) for x in includes], '-o', str(directory / 'soc.vvp'), '-f', str(filelist)]


def run_variant(args, variant, out, firmware, vectors):
    dest = out / variant
    dest.mkdir()
    sources = sorted(p for p in RTL.rglob('*') if p.suffix in ['.v', '.sv'])
    if variant == 'macro':
        excluded = {RTL / 'general/sirv_sim_ram.v', RTL / 'perips/mem_1024x16.sv'}
        sources = [p for p in sources if p not in excluded]
        sources += [HERE / 'xu_sirv_sram_adapter.sv', args.weight_adapter, args.vendor_model]
    if variant == 'reference' and args.clock_mode == 'reference4ns':
        sources.append(TB)
    else:
        generated = dest / 'tb_xu_soc_ppa.sv'
        generated.write_text(generate_tb(variant == 'macro', args.clock_mode, variant == 'reference'))
        sources.append(generated)
        if variant != 'reference':
            sources += [HERE / 'xu_shared_icb_sram.sv', HERE / 'xu_soc_ppa_top.sv']
    filelist = dest / 'rtl.f'
    filelist.write_text('\n'.join(str(p) for p in sources) + '\n')
    identities = {str(p): sha(p) for p in sources}
    compile_command = build_command(args.sim, variant, dest, filelist, args.waves, args.clock_mode)
    soc.run(compile_command, dest, dest / 'build.log', timeout=args.build_timeout)
    if any(sha(p) != identities[str(p)] for p in sources):
        raise ValueError('source changed during simulator build: ' + variant)
    binary = dest / ('obj/soc' if args.sim == 'verilator' else 'soc.vvp' if args.sim == 'iverilog' else 'soc')
    command = (['vvp', str(binary)] if args.sim == 'iverilog' else [str(binary)])
    run_command = command + ['+TESTCASE='+str(firmware), '+VECTORS='+str(vectors),
                            '+TASKS='+str(args.tasks), '+MAX_CYCLES='+str(args.max_cycles),
                            '+DUMPWAVE='+str(2 if args.waves else 0)]
    log = soc.run(run_command, dest, dest / 'simulation.log', timeout=args.run_timeout)
    layers = soc.check_log(log, args.tasks)
    if any(sha(p) != identities[str(p)] for p in sources):
        raise ValueError('source changed during simulation: ' + variant)
    for layer, counters in zip(layers, soc.check_performance(log, layers, args.firmware_schedule)):
        layer['performance'] = counters
    result = dict(status='PASS', variant=variant, simulator=args.sim, tasks=args.tasks,
                  clock_mode=args.clock_mode,
                  outputs=args.tasks*25344, write_words=args.tasks*50688,
                  layers=layers, source_sha256=identities, binary_sha256=sha(binary),
                  build_command=compile_command, run_command=run_command,
                  log_sha256={p.name: sha(p) for p in dest.glob('*.log')})
    if args.clock_mode == 'nominal150':
        result['activity_windows'] = check_windows(log, layers)
    (dest / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS variant='+variant+' cycles='+str(sum(x['cycles'] for x in layers)), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--variants', nargs='+', choices=['reference','harness','macro'], default=['reference','macro'])
    p.add_argument('--sim', choices=['verilator','iverilog','vcs'], default='vcs')
    p.add_argument('--clock-mode', choices=['reference4ns','nominal150'], default='reference4ns')
    p.add_argument('--tasks', type=int, choices=range(1,13), default=1)
    p.add_argument('--vectors', type=Path)
    p.add_argument('--vendor-model', type=Path)
    p.add_argument('--weight-adapter', type=Path, default=HERE / 'xu_weight_sram_adapter.sv')
    p.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    p.add_argument('--max-cycles', type=int, help='default 3 million HF cycles per task, including startup')
    p.add_argument('--run-timeout', type=int, default=7200)
    p.add_argument('--build-timeout', type=int, default=1800)
    p.add_argument('--waves', action='store_true', help='full PPA top, measured task windows only')
    contract.add_arguments(p)
    args = p.parse_args()
    if args.max_cycles is None:
        args.max_cycles = 3000000 * args.tasks
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'runner-source.py').write_bytes(Path(__file__).read_bytes())
    report = dict(schema='xu-full-soc-rtl-compare-v1', status='RUNNING', tasks=args.tasks,
                  simulator=args.sim, runner_sha256=sha(__file__),
                  clock_mode=args.clock_mode,
                  hf_nominal_period_ns=20/3 if args.clock_mode == 'nominal150' else 4,
                  timeprecision_seconds=1e-15 if args.clock_mode == 'nominal150' else 1e-11,
                  helper_sha256={str(Path(m.__file__).resolve()): sha(m.__file__) for m in [soc, contract]},
                  original_tb_sha256=sha(TB), limitations=[
                      'RTL functional comparison; not gate-level equivalence, STA or power qualification',
                      'Verilator is two-state; use VCS/Icarus for four-state evidence',
                      'reference4ns preserves old 4ns/120ns TB; nominal150 is a separate clock configuration',
                      'shared_fixture preload marker does not prove physical accelerator cache clearing'])
    try:
        if 'macro' in args.variants:
            if args.sim == 'verilator':
                raise ValueError('vendor ARM_UD_MODEL requires a four-state simulator: use vcs or iverilog; Verilator is restricted to reference/harness development')
            for attr in ['vendor_model', 'weight_adapter']:
                path = getattr(args, attr)
                if path is None or not path.is_file():
                    raise ValueError('--'+attr.replace('_','-')+' regular file is required for macro')
                setattr(args, attr, path.resolve())
            vendor_text = args.vendor_model.read_text()
            if not re.search(r'reg\s*\[63:0\]\s*mem\s*\[0:255\]', vendor_text):
                raise ValueError('vendor physical preload geometry differs; review packing')
            report['vendor_model'] = dict(path=str(args.vendor_model), sha256=sha(args.vendor_model),
                                         selection='ARM_UD_MODEL fast functional; no timing checks')
        report['e203_commit'] = soc.verify_submodule(ROOT, ROOT / 'third-party/e203_hbirdv2')
        report['main_commit'] = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
        report['tool_versions'] = {}
        for tool in [args.sim, args.cross_prefix+'gcc']:
            flag = '-ID' if tool == 'vcs' else '-V' if tool == 'iverilog' else '--version'
            report['tool_versions'][tool] = soc.run([tool,flag], args.out, args.out/(tool+'-version.log')).splitlines()[:5]
        vectors = args.vectors.resolve() if args.vectors else args.out / 'vectors'
        if args.vectors is None:
            report['fixture'] = soc.load_fixture(vectors, args.tasks)
        report['vectors'] = soc.check_vectors(vectors, args.tasks)
        firmware = soc.compile_firmware(args.out, args.cross_prefix, args.firmware_schedule,
                                        args.firmware_opt, args.firmware_experiment, report)
        report['variants'] = []
        for variant in args.variants:
            report['variants'].append(run_variant(args, variant, args.out, firmware, vectors))
        first = report['variants'][0]['layers']
        if any(v['layers'] != first for v in report['variants'][1:]):
            raise ValueError('cycle/performance/firmware-cycle comparison differs; examine every variant result')
        report['status'] = 'PASS'
        report['comparison'] = 'all requested variants match numerical outputs and every measured cycle/performance counter'
    except Exception as exc:
        report.update(status='FAIL', error=str(exc))
        print('FAIL: '+str(exc), file=sys.stderr)
    (args.out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['status']+': '+str(args.out / 'result.json'), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
