#!/usr/bin/env python3
"""Collect explicit frozen S2c nominal150, clear-first, isolated task SAIF.

The source root and producer assets are separate. This is RTL activity only;
neither host/RTL development tests nor a completed collection qualify power,
mapped equivalence, timing, SRAM power, or contest eligibility.
"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import xu_candidate_activity_context as context

SCOPE = 'tb_xu_soc_ppa.dut'
SCHEDULE = context.SCHEDULE
require, identity, sha = context.require, context.identity, context.sha


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def unchanged(records):
    for path, digest in records.items():
        require(sha(path) == digest, 'frozen run input changed: ' + path)


def common_collector():
    # This frozen module is used only for stateless task-copy/SAIF inspection
    # routines and the existing request-window template, never its root guard,
    # firmware build, upload observer, alias source guard, or main entry point.
    return context.load('xu_candidate_common_collector', HERE / 'xu_soc_task_activity.py')


def clear_observer(ctx):
    text = ctx.clear.observer_declarations().replace('source_accept', 'source_request')
    text = text.replace('source accept', 'source request')
    text = ctx.base.once(text, "`ACCEL.x_load_wen!==1'b0)",
                         "`ACCEL.x_load_wen!==1'b0 || `ACCEL.stream_pending!==1'b0 || `ACCEL.rsp_valid!==1'b0)")
    text = ctx.base.once(text, "`ACCEL.cmd_addr[11:0]!=12'h050)",
                         "`ACCEL.cmd_addr[11:0]!=12'h050 && `ACCEL.cmd_addr[11:0]!=12'h070 &&\n"
                         "                `ACCEL.cmd_addr[11:0]!=12'h074 && `ACCEL.cmd_addr[11:0]!=12'h078)")
    text = ctx.base.once(text, '          end else begin\n            if (`ACCEL.cmd_wmask',
                         '          end else begin\n            if (xu_clear_writes==33697)\n'
                         '              $fatal(1,"XU_CLEAR_REJECT candidate setup/data write before first source request");\n'
                         '            if (`ACCEL.cmd_wmask')
    text = ctx.base.once(text, '          xu_clear_complete=1;', '''          if (xu_clear_w_commits!=16384 || xu_clear_x_commits!=64 ||
              xu_clear_bias_commits!=256 || xu_clear_w_committed!=={16384{1'b1}} ||
              xu_clear_x_committed!==64'hffffffffffffffff || !xu_reset_checked ||
              `ACCEL.row_active || `ACCEL.row_running || `ACCEL.row_count!=0 ||
              `ACCEL.row_produced!=0 || `ACCEL.row_retired!=0 ||
              `ACCEL.u_linear_compute_core.head!==0 || `ACCEL.u_linear_compute_core.tail!==0 ||
              `ACCEL.stream_error || `ACCEL.w_cursor!=0 || `ACCEL.x_cursor!=0)
            $fatal(1,"XU_CLEAR_REJECT incomplete actual zero commits or nonempty FIFO/stream ownership");
          for (a=0;a<8;a=a+1) if (`ACCEL.bias_regs[a]!==40'b0)
            $fatal(1,"XU_CLEAR_REJECT actual legacy bias did not clear");
          xu_clear_complete=1;''')
    return ctx.base.once(text, 'drained=1 cache_enable=0 idle=1"',
                         'drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 actual_commits=1 fifo_reset_empty=1"')


def nominal_lf_clock():
    """Absolute 32768 Hz phase at 1 fs precision, without per-edge rounding drift."""
    return r'''  integer xu_lf_half_index=0, xu_lf_static_checks=0;
  real xu_lf_target_ns, xu_lf_phase_error_fs;
  initial forever begin
    xu_lf_half_index=xu_lf_half_index+1;
    xu_lf_target_ns=xu_lf_half_index*15258.7890625;
    #(xu_lf_target_ns-$realtime);
    xu_lf_phase_error_fs=($realtime-xu_lf_target_ns)*1000000.0;
    if (xu_lf_phase_error_fs>1.01 || xu_lf_phase_error_fs< -1.01)
      $fatal(1,"nominal32768 LF absolute phase drift exceeded 1fs");
    xu_lf_static_checks=xu_lf_static_checks+1;
    lfclk=~lfclk;
  end'''


def generate_tb(ctx):
    common = common_collector()
    text = ctx.base.generate_tb(True, 'nominal150')
    text = ctx.base.once(text, '  always #15258.7890625 lfclk = ~lfclk;', nominal_lf_clock())
    observer = (HERE / 'xu_s2c_activity_observer.svh').read_text()
    window = common.CLEAR_WINDOW_DECLARATIONS.replace('      if (xu_payload_phase) xu_observe_upload();\n', '')
    window = ctx.base.once(window, '      // Once per post-reset edge,',
                           '      xu_observe_candidate();\n      // Once per post-reset edge,')
    text = ctx.base.once(text, '  // Observation only: these counters never drive',
                         observer + clear_observer(ctx) + window + '\n  // Observation only: these counters never drive')
    text = ctx.base.once(text, '    #1; // Finish vendor initialization before the first HF edge.', '''    if (!$value$plusargs("XU_GLOBAL_TASK=%d",xu_global_task) ||
        xu_global_task<0 || xu_global_task>11 || tasks!=1)
      $fatal(1,"candidate requires valid global task and TASKS=1 fresh process");
    for (i=0;i<256;i=i+1) begin xu_bias_seen[i]=0; xu_clear_bias_committed[i]=0; end
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
    $set_gate_level_monitoring("rtl_on");
    $set_toggle_region(tb_xu_soc_ppa.dut);
`endif
    #1; // Finish vendor initialization before the first HF edge.''')
    text = ctx.base.once(text, '      // Match the existing inclusive first-input/final-Y-response interval.',
                         '      xu_observe_clear_window();\n      // Match the existing inclusive first-input/final-Y-response interval.')
    # The retained candidate TB still owns its legacy accept-based diagnostics.
    text = ctx.base.once(text, '          $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",layer,$realtime*1000000.0);', '')
    text = ctx.base.once(text, '          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",layer,$realtime*1000000.0);', '''          if (xu_request_cycle<0 || xu_accept_cycle<xu_request_cycle ||
              xu_formal_cycles!=cycles-xu_request_cycle+1 ||
              xu_formal_cycles!=perf_cycles+xu_initial_wait ||
              xu_w_count!=16384 || xu_bias_count!=256 || xu_x_count!=6336 ||
              xu_rows!=99 || xu_starts!=3168 || xu_dones!=3168 || xu_pops!=3168 ||
              xu_w_pairs!=8192 || xu_x_pairs!=3168 || xu_result_words!=0 ||
              xu_w_cursor_setups!=1 || xu_x_cursor_setups!=99 || xu_cache_mode_writes!=2 ||
              xu_result_response_pending ||
              `ACCEL.row_active || `ACCEL.row_running || `ACCEL.row_count!=0 ||
              `ACCEL.row_produced!=32 || `ACCEL.row_retired!=32 || `ACCEL.stream_pending ||
              !xu_saif_started || xu_saif_stopped)
            $fatal(1,"XU_CANDIDATE_REJECT incomplete actual task coverage/window/FIFO drain");
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_stop();
`endif
          xu_saif_stopped=1;
          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
          $display("XU_TASK_WINDOW task=%0d request_cycle=%0d accept_cycle=%0d end_cycle=%0d initial_wait_cycles=%0d legacy_inclusive_cycles=%0d formal_inclusive_cycles=%0d formal_elapsed_cycles=%0d",xu_global_task,xu_request_cycle,xu_accept_cycle,cycles,xu_initial_wait,perf_cycles,xu_formal_cycles,xu_formal_cycles-1);
          $display("XU_CANDIDATE_UPLOAD_PASS task=%0d w_commits=16384 bias=256 x_commits=6336 rows=99 starts=3168 dones=3168 pops_retired=3168 w_pack32=8192 x_pack32=3168 fifo_empty=1 checked_data=1",xu_global_task);
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut");
`endif''')
    text = ctx.base.once(text, '"XU_CACHE_RELOAD task=%0d done_before_begin=1 scope=shared_fixture tick=%0.0f",index,',
                         '"XU_CACHE_RELOAD task=%0d done_before_begin=1 scope=shared_fixture tick=%0.0f",xu_global_task,')
    return ctx.base.once(text, '        $display("XU_CLOCK_STATIC_PASS',
                         '        if (!xu_saif_stopped || xu_lf_static_checks<=0) $fatal(1,"missing candidate SAIF end/LF checks");\n'
                         '        $display("XU_LF_CLOCK_STATIC_PASS nominal_hz=32768 checked_edges=%0d max_phase_error_fs=1",xu_lf_static_checks);\n        $display("XU_CLOCK_STATIC_PASS')


def compile_firmware(ctx, out, prefix):
    main = ctx.soc.TESTS / 'firmware/main.c'
    wrapper = out / 'xu_s2c_clear_main.c'
    wrapper.write_text(ctx.clear.firmware_wrapper(main, sha(main)))
    target = out / 'accel_soc'
    sources = [ctx.soc.TESTS / 'firmware/start.S', wrapper, ctx.soc.TESTS / 'firmware/accel.c']
    inputs = [identity(p) for p in (ctx.soc.TESTS / 'firmware').iterdir() if p.is_file()]
    inputs += [identity(wrapper), identity(ctx.clear.__file__)]
    tools = []
    for tool in ('gcc', 'objcopy', 'objdump'):
        executable = shutil.which(prefix + tool)
        require(executable, 'RISC-V tool unavailable: ' + prefix + tool)
        tools.append(identity(executable))
    frozen = {x['path']: x['sha256'] for x in inputs + tools}
    ctx.soc.run([prefix + 'gcc', '--version'], out, out / 'gcc-version.log')
    command = [prefix + 'gcc', '-march=rv32imac_zicsr2p0_zifencei2p0', '-mabi=ilp32', '-O2'] + ctx.contract.compiler_defines(ctx.configuration) + [
        '-fstack-usage', '-ffreestanding', '-fno-builtin', '-msmall-data-limit=0', '-nostdlib',
        '-nostartfiles', '-static', '-mcmodel=medany', '-Wl,--no-relax', '-T',
        str(ctx.soc.TESTS / 'firmware/link.ld')] + [str(p) for p in sources] + ['-o', str(target)]
    ctx.soc.run(command, out, out / 'firmware-build.log')
    ctx.soc.run([prefix + 'objcopy', '-O', 'verilog', str(target), str(target) + '.verilog'], out, out / 'objcopy.log')
    image = Path(str(target) + '.verilog')
    image.write_text(image.read_text().replace('@800', '@000'))
    dump = ctx.soc.run([prefix + 'objdump', '--disassemble-all', str(target)], out, out / 'firmware.dump')
    require(re.search(r'80000086\s+<write_tohost>', dump), 'firmware completion address differs')
    sections = ctx.soc.run([prefix + 'objdump', '-h', str(target)], out, out / 'firmware-sections.log')
    symbols = ctx.soc.run([prefix + 'objdump', '-t', str(target)], out, out / 'firmware-symbols.log')
    unchanged(frozen)
    record = dict(configuration=ctx.configuration, command=command, cwd=str(out),
                  inputs=inputs, toolchain=tools, compiler_version=identity(out / 'gcc-version.log'),
                  frozen_main=identity(main), wrapper=identity(wrapper), elf=identity(target), image=identity(image),
                  memory=ctx.soc.firmware_memory(sections, symbols, sorted(out.glob('*.su'))),
                  recipe='s2c-cpu-legacy-33697-zero-clear-before-source-request-v1')
    write_json(out / 'firmware-build.json', record)
    return target, record


def checked_window(log, task_id, layer, legacy):
    """Candidate's own request/clear checks; raw diagnostics are never rewritten."""
    def boundary(name, suffix=''):
        rows = re.findall(r'^XU_' + name + r' task=(\d+) cycle=(\d+) tick=(\d+)' + suffix + r'$', log, re.M)
        require(len(rows) == 1 and int(rows[0][0]) == task_id,
                'candidate boundary missing/duplicate/global identity differs: ' + name)
        return dict(cycle=int(rows[0][1]), tick=int(rows[0][2]))
    request, accept = boundary('SOURCE_REQUEST'), boundary('SOURCE_ACCEPT')
    clear_begin = boundary('TASK_CLEAR_BEGIN')
    clear_end = boundary('TASK_CLEAR_LAST_WRITE', r' writes=33697')
    require(clear_begin['cycle'] <= clear_end['cycle'] < request['cycle'] <= accept['cycle'] and
            clear_begin['tick'] <= clear_end['tick'] < request['tick'] <= accept['tick'],
            'candidate clear/request/accept ordering differs')
    require(accept == {key: legacy['begin'][key] for key in ('cycle', 'tick')},
            'candidate source acceptance differs from retained legacy boundary')
    end = legacy['end']
    initial_wait, elapsed = accept['cycle'] - request['cycle'], end['cycle'] - request['cycle']
    require(elapsed >= 0 and abs(Fraction(end['tick']-request['tick']) -
            Fraction(elapsed*20000000, 3)) <= 1, 'candidate formal physical span differs from nominal150')
    require(abs(Fraction(accept['tick']-request['tick']) - Fraction(initial_wait*20000000, 3)) <= 1,
            'candidate initial source wait physical span differs from nominal150')
    expected = ('XU_TASK_WINDOW task=%d request_cycle=%d accept_cycle=%d end_cycle=%d '
                'initial_wait_cycles=%d legacy_inclusive_cycles=%d formal_inclusive_cycles=%d '
                'formal_elapsed_cycles=%d') % (task_id, request['cycle'], accept['cycle'], end['cycle'],
                    initial_wait, layer['cycles'], elapsed+1, elapsed)
    require(re.findall(r'^XU_TASK_WINDOW.*$', log, re.M) == [expected], 'candidate formal cycle accounting differs')
    return dict(layer=0, global_task_id=task_id, begin=request, end=end,
                duration_ticks=end['tick']-request['tick'], timescale_seconds=1e-15,
                nominal_hf_period_seconds=20e-9/3,
                interval='first valid input/parameter source read request through final Y response retired; physical [begin,end)',
                formal_elapsed_cycles=elapsed, formal_inclusive_cycles=elapsed+1,
                initial_source_wait_cycles=initial_wait, first_source_accept=accept,
                legacy_accept_window=legacy, legacy_task_pass_inclusive_cycles=layer['cycles'],
                legacy_performance_status='unchanged acceptance-based diagnostic',
                pretask_clear=dict(begin=clear_begin, last_write=clear_end, accepted_writes=33697,
                    verification_at_first_source_request=True, original_task_destination_setup_writes_before_source=0,
                    accepted_write_span_cycles=clear_end['cycle']-clear_begin['cycle'],
                    accepted_write_span_ticks=clear_end['tick']-clear_begin['tick'],
                    last_write_to_source_request_cycles=request['cycle']-clear_end['cycle'],
                    actual_internal_zero_commits_observed=dict(w=16384,x=64,bias=256),
                    fifo_logical_ownership_reset_and_empty_observed=True,
                    activity_status='outside task SAIF; no clear-phase SAIF measured'))


def checked_log(ctx, log, task_id):
    lf = re.findall(r'^XU_LF_CLOCK_STATIC_PASS nominal_hz=32768 checked_edges=(\d+) max_phase_error_fs=1$', log, re.M)
    require(len(lf)==1 and int(lf[0])>0, 'candidate LF phase assertions missing')
    layers = ctx.soc.check_log(log, 1)
    layers[0]['performance'] = ctx.soc.check_performance(log, layers, SCHEDULE)[0]
    auto = ctx.soc.check_autogroup_activity(log, layers, SCHEDULE)[0]
    legacy = ctx.base.check_windows(log, layers)[0]
    # The candidate has zero pre-source setup writes, checked directly.
    marker = ('XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 '
              'drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 actual_commits=1 fifo_reset_empty=1')
    require(re.findall(r'^XU_TASK_CLEAR_OBSERVED.*$', log, re.M) == [marker], 'candidate actual clear evidence differs')
    window = checked_window(log, task_id, layers[0], legacy)
    for kind, value in (('BEGIN', window['begin']['tick']), ('END', window['end']['tick'])):
        require(re.findall(r'^XU_ACTIVITY_' + kind + '.*$', log, re.M) ==
                ['XU_ACTIVITY_%s task=%d tick=%d' % (kind, task_id, value)], 'candidate global activity boundary differs')
    expected = ('XU_CANDIDATE_UPLOAD_PASS task=%d w_commits=16384 bias=256 x_commits=6336 rows=99 '
                'starts=3168 dones=3168 pops_retired=3168 w_pack32=8192 x_pack32=3168 fifo_empty=1 checked_data=1') % task_id
    require(re.findall(r'^XU_CANDIDATE_UPLOAD_PASS.*$', log, re.M) == [expected], 'candidate internal upload/FIFO proof missing')
    require(log.splitlines().count(('XU_CACHE_INITIAL task=%d fresh_process=1 cache_enable=0 busy=0 '
                                   'prior_uploads=0 prior_starts=0') % task_id) == 1, 'candidate fresh-process proof missing')
    return layers[0], window, auto


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', '--root', dest='root', required=True, type=Path, help='exact frozen S2c source root')
    parser.add_argument('--tool-root', type=Path, default=context.TOOL_ROOT, help='must identify this producer checkout')
    parser.add_argument('--profile', choices=[context.PROFILE], default=context.PROFILE)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--vendor-model', required=True, type=Path)
    parser.add_argument('--netlist', required=True, type=Path, help='supplied target identity; equivalence is not asserted')
    parser.add_argument('--constraints', required=True, type=Path)
    parser.add_argument('--vectors', type=Path)
    parser.add_argument('--vcs', default='vcs')
    parser.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    parser.add_argument('--max-cycles', type=int, default=4000000)
    parser.add_argument('--build-timeout', type=int, default=1800)
    parser.add_argument('--run-timeout', type=int, default=7200)
    parser.add_argument('--initialize-vendor-memory', action='store_true')
    parser.add_argument('--task-ids', default='0,1,2,3,4,5,6,7,8,9,10,11')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-s2c-isolated-task-activity-v1', status='RUNNING', tasks=[], limitations=[
        'RTL activity only; no equivalence, STA, power, energy or contest qualification result',
        'supplied netlist identity does not establish source/netlist equivalence',
        'mapped PT coverage and SRAM Liberty/internal-power remain REVIEW_PENDING',
        'FIFO payload registers are not physically reset: reset/clear establishes empty logical ownership; all 3168 groups are produced/read/retired afresh'])
    try:
        require(args.tool_root.resolve() == context.TOOL_ROOT, 'explicit tool root differs from this producer')
        ctx = context.Context(args.root)
        common = common_collector()
        task_ids = common.parse_task_ids(args.task_ids)
        require(args.max_cycles > 0 and args.build_timeout > 0 and args.run_timeout > 0, 'positive limits required')
        vendor = identity(args.vendor_model.resolve())
        require(re.search(r'reg\s*\[63:0\]\s*mem\s*\[0:255\]', Path(vendor['path']).read_text()), 'vendor preload geometry differs')
        report.update(source_context=ctx.source, tool_context=ctx.tool, requested_task_ids=task_ids,
                      taskset_complete=task_ids == list(range(12)))
        vectors = args.vectors.resolve() if args.vectors else args.out / 'original-vectors'
        if args.vectors is None:
            report['fixture'] = ctx.soc.load_fixture(vectors, 12)
        validated = ctx.soc.check_vectors(vectors, 12)
        report['original_task_vectors'] = validated
        fixture_sources = [identity(ctx.soc.TESTS / ('vectors/kwt-silence-v1.' + suffix)) for suffix in ('tar.gz','json')] if args.vectors is None else []
        firmware_dir = args.out / 'firmware'
        firmware_dir.mkdir()
        firmware, firmware_record = compile_firmware(ctx, firmware_dir, args.cross_prefix)
        report['firmware_build'] = firmware_record
        build = args.out / 'simulator'
        build.mkdir()
        tb = build / 'tb_xu_s2c_task_activity.sv'
        tb.write_text(generate_tb(ctx))
        excluded = {ctx.base.RTL / 'general/sirv_sim_ram.v', ctx.base.RTL / 'perips/mem_1024x16.sv'}
        sources = sorted(p for p in ctx.base.RTL.rglob('*') if p.suffix in ('.v', '.sv') and p not in excluded)
        sources += [HERE / name for name in ('xu_sirv_sram_adapter.sv', 'xu_weight_sram_adapter.sv',
                                              'xu_shared_icb_sram.sv', 'xu_soc_ppa_top.sv')]
        sources += [Path(vendor['path']), tb]
        import xu_candidate_sram_activity_alias as aliases
        alias_dir = build / 'sram-pin-alias'
        mapping = aliases.generate(ctx.root, alias_dir)
        mapping_path = alias_dir / 'xu_candidate_sram_activity_alias.mapping.json'
        checked, pairs = aliases.validate_mapping(mapping_path)
        require(checked == mapping and len(pairs) == 22512, 'candidate SRAM pin mapping differs')
        sources.append(Path(mapping['observer_source']['path']))
        defines = ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION=1']
        if args.initialize_vendor_memory:
            defines.append('INITIALIZE_MEMORY')
        config = dict(source_context=ctx.source, tool_context=ctx.tool,
                      producer_sources=[identity(p) for p in (Path(__file__), Path(context.__file__), Path(aliases.__file__),
                                        HERE / 'xu_s2c_activity_observer.svh')],
                      rtl_sources=[identity(p) for p in sources], original_tb=identity(ctx.base.TB),
                      candidate_contract=identity(ctx.contract.__file__), candidate_soc_helper=identity(ctx.soc.__file__),
                      fixture_sources=fixture_sources, firmware=firmware_record, firmware_build=identity(firmware_dir / 'firmware-build.json'),
                      netlist=identity(args.netlist.resolve()), constraints=identity(args.constraints.resolve()),
                      nominal_hz=150000000, lf_hz=32768, precision_fs=1, numeric_format='signed16/40/48',
                      activity_scope=SCOPE, monitoring_policy='rtl_on', simulator_defines=defines,
                      process_policy='one fresh process, TASKS=1 and one source-REQUEST/final-Y-response-RETIRE window per real task',
                      clear_policy='33697 CPU legacy actual-zero writes; all W/X/bias commits checked; no pre-source candidate setup writes',
                      sram_alias=mapping, sram_alias_mapping=identity(mapping_path))
        frozen = {}
        for item in config['rtl_sources'] + config['producer_sources'] + ctx.tool['frozen_common_tools'] + firmware_record['inputs'] + firmware_record['toolchain'] + fixture_sources:
            frozen[item['path']] = item['sha256']
        for item in (config['original_tb'], config['candidate_contract'], config['candidate_soc_helper'], config['netlist'],
                     config['constraints'], config['firmware_build'], firmware_record['elf'], firmware_record['image'],
                     firmware_record['compiler_version'], config['sram_alias_mapping']):
            frozen[item['path']] = item['sha256']
        report['configuration'] = config
        report['configuration_sha256'] = context.canonical(config)
        tasks = []
        for task_id in task_ids:
            destination = args.out / ('task_%02d' % task_id)
            destination.mkdir()
            inputs = common.materialize_task(vectors, destination / 'vectors', task_id, validated[task_id])
            tasks.append((task_id, destination, inputs))
            for record in inputs['files']:
                for kind in ('original', 'materialized'):
                    frozen[record[kind]['path']] = record[kind]['sha256']
            receipt = identity(destination / 'vectors/input-manifest.json')
            frozen[receipt['path']] = receipt['sha256']
        report['taskset_inputs_sha256'] = context.canonical({str(i): inputs for i, _, inputs in tasks})
        filelist = build / 'rtl.f'
        filelist.write_text('\n'.join(str(p) for p in sources) + '\n')
        frozen[str(filelist)] = sha(filelist)
        command = ctx.base.build_command('vcs', 'macro', build, filelist, True, 'nominal150')
        command[0] = args.vcs
        command.insert(1, '-debug_region+cell')
        if args.initialize_vendor_memory:
            command.insert(1, '+define+INITIALIZE_MEMORY')
        report['build_command'] = command
        ctx.recheck(); unchanged(frozen)
        if args.prepare_only:
            report['tasks'] = [dict(task_id=i, input_manifest=identity(d / 'vectors/input-manifest.json')) for i, d, _ in tasks]
            report['status'] = 'PREPARED_NOT_SIMULATED' if report['taskset_complete'] else 'PARTIAL_PREPARED_NOT_SIMULATED'
        else:
            vcs = shutil.which(args.vcs)
            require(vcs, 'VCS executable unavailable: ' + args.vcs)
            report['vcs_executable'] = identity(vcs)
            frozen[report['vcs_executable']['path']] = report['vcs_executable']['sha256']
            ctx.soc.run([args.vcs, '-ID'], build, build / 'vcs-version.log', args.build_timeout)
            log = ctx.soc.run(command, build, build / 'build.log', args.build_timeout)
            require(not re.search(r'Error-\[|undefined system task|unknown system task', log, re.I), 'VCS build diagnostic failure')
            ctx.recheck(); unchanged(frozen)
            binary = build / 'soc'
            report['binary'] = identity(binary)
            frozen[str(binary)] = sha(binary)
            for task_id, destination, _ in tasks:
                ctx.recheck(); unchanged(frozen); aliases.validate_mapping(mapping_path)
                run = [str(binary), '+TESTCASE=' + str(firmware), '+VECTORS=' + str(destination / 'vectors'),
                       '+TASKS=1', '+XU_GLOBAL_TASK=' + str(task_id), '+MAX_CYCLES=' + str(args.max_cycles), '+DUMPWAVE=0']
                log = ctx.soc.run(run, destination, destination / 'simulation.log', args.run_timeout)
                ctx.recheck(); unchanged(frozen)
                layer, window, auto = checked_log(ctx, log, task_id)
                raw = identity(destination / 'task.saif')
                receipt = aliases.normalize(destination / 'task.saif', mapping_path,
                                            destination / 'task-normalized.saif', destination / 'task-normalization.json')
                require(identity(raw['path']) == raw, 'raw candidate SAIF changed')
                saif = common.inspect_activity(destination / 'task-normalized.saif', window, common.STATIC_SCOPE_DECLARATIONS)
                ctx.recheck(); unchanged(frozen)
                result = dict(task_id=task_id, status='COLLECTED_REVIEW_PENDING', configuration_sha256=report['configuration_sha256'],
                              layer=layer, autogroup=auto, activity_window=window, run_command=run,
                              input_manifest=identity(destination / 'vectors/input-manifest.json'),
                              boundary_log=identity(destination / 'simulation.log'), raw_saif=raw,
                              saif=saif, normalization=receipt, cache_policy=dict(fresh_process=True,
                                  physical_zero_clear_observed=True, all_fixture_commits_inside_window=True,
                                  fifo_ownership_reset_and_fresh_production_observed=True, cross_task_reuse=False))
                write_json(destination / 'result.json', result)
                report['tasks'].append(result)
                write_json(args.out / 'result.json', report)
                print('COLLECTED_CANDIDATE task=%d duration_fs=%d' % (task_id, window['duration_ticks']), flush=True)
            report['status'] = 'COLLECTED_12_TASKS_REVIEW_PENDING' if report['taskset_complete'] else 'PARTIAL_COLLECTED_REVIEW_PENDING'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        print('FAIL: ' + str(error), file=sys.stderr)
    write_json(args.out / 'result.json', report)
    print(report['status'] + ': ' + str(args.out / 'result.json'), flush=True)
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
