#!/usr/bin/env python3
"""Collect twelve isolated, nominal150 full-SoC VCS task SAIF files.

This is an RTL activity producer, not a power or contest qualification tool.
The existing frozen full-SoC generator, firmware and vector validators are used
without modifying them. Vendor sources stay at their supplied private paths.
Python 3.6+ and the standard library are sufficient for this runner.
"""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import xu_soc_ppa_verify as base
from xu_soc_ppa_verify import soc, contract
import xu_soc_activity as activity

TENSORS = ('x', 'w', 'bias', 'y')
SCOPE = 'tb_xu_soc_ppa.dut'
FROZEN_E203 = 'f49a5fc914971426bd4530db39e270a84b41139f'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    path = Path(path).resolve()
    require(path.is_file(), 'required regular file missing: ' + str(path))
    return dict(path=str(path), sha256=base.sha(path))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def unchanged(records):
    for path, digest in records.items():
        require(base.sha(path) == digest, 'frozen input changed: ' + path)


def verify_frozen_child(out):
    """Use closed-stdin git calls, also refusing dirty/untracked live RTL."""
    child = ROOT / 'third-party/e203_hbirdv2'
    require((child / '.git').exists(), 'E203 child is not initialized as its own repository')
    top = soc.run(['git', 'rev-parse', '--show-toplevel'], child, out / 'e203-root.log').strip()
    require(Path(top).resolve() == child.resolve(), 'E203 child repository root differs')
    commit = soc.run(['git', 'rev-parse', 'HEAD'], child, out / 'e203-commit.log').strip()
    require(commit == FROZEN_E203, 'E203 child differs from frozen f49a5fc')
    pin = soc.run(['git', 'ls-tree', 'HEAD', 'third-party/e203_hbirdv2'], ROOT,
                  out / 'e203-gitlink.log').split()
    require(len(pin) >= 3 and pin[0] == '160000' and pin[2] == commit,
            'E203 child differs from main repository gitlink')
    dirty = soc.run(['git', 'status', '--porcelain', '--untracked-files=all', '--', 'rtl/e203'], child,
                    out / 'e203-rtl-status.log').strip()
    require(not dirty, 'frozen E203 RTL has modified/untracked files')
    return commit


def materialize_task(vectors, destination, task_id, validated):
    """Map real layer_i to the single-task firmware's layer_00, byte for byte."""
    require(type(task_id) is int and 0 <= task_id < 12, 'invalid global task id')
    require(validated['layer'] == task_id, 'validated task identity differs')
    target = destination / 'layer_00'
    target.mkdir(parents=True, exist_ok=False)
    files = []
    for tensor in TENSORS:
        name = tensor + '.mem'
        source = vectors / ('layer_%02d' % task_id) / name
        original = identity(source)
        require(original['sha256'] == validated['sha256'][name],
                'original task changed after integer validation: ' + str(source))
        local = target / name
        shutil.copyfile(str(source), str(local))
        copied = identity(local)
        require(copied['sha256'] == original['sha256'], 'task materialization differs')
        files.append(dict(tensor=tensor, original=original, materialized=copied))
    result = dict(schema='xu-soc-single-task-input-v1', global_task_id=task_id,
                  original_layer='layer_%02d' % task_id, simulator_layer='layer_00',
                  mapping='four original tensor files copied byte-for-byte; +TASKS=1', files=files)
    write_json(destination / 'input-manifest.json', result)
    return result


# The observer is entirely passive. Its state is outside the monitored DUT.
# At START it proves actual accepted MMIO writes covered every W/cache-bias
# address and every X address for the current row, with fixture data and masks.
UPLOAD_DECLARATIONS = r'''
  integer xu_global_task, xu_saif_started=0, xu_saif_stopped=0;
  integer xu_w_count=0, xu_bias_count=0, xu_x_count=0, xu_rows=0, xu_starts=0;
  reg xu_w_seen [0:16383];
  reg [4:0] xu_bias_seen [0:255];
  reg [63:0] xu_x_seen=0;

  task xu_observe_upload;
    integer a, logical_index, row_index;
    reg [4:0] old_mask, new_mask;
    begin
      if (`ACCEL.cmd_valid && `ACCEL.cmd_ready && !`ACCEL.cmd_read) begin
        case (`ACCEL.cmd_addr[11:0])
          12'h024: begin
            if (!xu_saif_started || xu_saif_stopped)
              $fatal(1,"W upload outside activity window");
            if ((^{`ACCEL.w_bank_reg,`ACCEL.w_addr_reg})===1'bx)
              $fatal(1,"unknown W upload address");
            a=`ACCEL.w_bank_reg*2048+`ACCEL.w_addr_reg;
            logical_index=(`ACCEL.w_addr_reg%64)*256+
                          (`ACCEL.w_addr_reg/64)*8+`ACCEL.w_bank_reg;
            if (`ACCEL.cmd_wmask[1:0]!==2'b11 ||
                `ACCEL.cmd_wdata[15:0]!==w[logical_index] || xu_w_seen[a])
              $fatal(1,"incomplete/duplicate/incorrect W upload address=%0d",a);
            xu_w_seen[a]=1;
            xu_w_count=xu_w_count+1;
          end
          12'h048,12'h04c: begin
            if (!xu_saif_started || xu_saif_stopped || `ACCEL.cache_enable!==1'b0)
              $fatal(1,"bias cache upload outside disabled-cache task window");
            if ((^`ACCEL.cache_addr_reg)===1'bx)
              $fatal(1,"unknown bias upload address");
            a=`ACCEL.cache_addr_reg;
            old_mask=xu_bias_seen[a];
            if (`ACCEL.cmd_addr[11:0]==12'h048) begin
              if (`ACCEL.cmd_wmask!==4'hf || `ACCEL.cmd_wdata!==bias[a][31:0] ||
                  old_mask[3:0]!=0) $fatal(1,"incomplete/duplicate/incorrect bias low upload");
              new_mask=old_mask|5'b01111;
            end else begin
              if (`ACCEL.cmd_wmask[0]!==1'b1 || `ACCEL.cmd_wdata[7:0]!==bias[a][39:32] ||
                  old_mask[4]) $fatal(1,"incomplete/duplicate/incorrect bias high upload");
              new_mask=old_mask|5'b10000;
            end
            xu_bias_seen[a]=new_mask;
            if (new_mask==5'b11111 && old_mask!=5'b11111) xu_bias_count=xu_bias_count+1;
          end
          12'h018: begin
            if (!xu_saif_started || xu_saif_stopped || xu_rows>=99)
              $fatal(1,"X upload outside activity window/row range");
            if ((^`ACCEL.x_addr_reg)===1'bx) $fatal(1,"unknown X upload address");
            a=`ACCEL.x_addr_reg;
            row_index=xu_rows;
            if (`ACCEL.cmd_wmask[1:0]!==2'b11 ||
                `ACCEL.cmd_wdata[15:0]!==x[row_index*64+a] || xu_x_seen[a])
              $fatal(1,"incomplete/duplicate/incorrect X upload row=%0d addr=%0d",row_index,a);
            xu_x_seen[a]=1;
            xu_x_count=xu_x_count+1;
          end
          12'h008: if (`ACCEL.cmd_wdata[0] && !`ACCEL.busy) begin
            if (!xu_saif_started || xu_saif_stopped || xu_w_count!=16384 ||
                xu_bias_count!=256 || xu_x_seen!==64'hffffffffffffffff ||
                `ACCEL.cache_enable!==1'b1 || `ACCEL.group_reg!==xu_starts%32)
              $fatal(1,"START before complete W/bias/current-X upload or group order");
            xu_starts=xu_starts+1;
            if (xu_starts%32==0) begin
              xu_rows=xu_rows+1;
              xu_x_seen=0;
            end
          end
          default: begin end
        endcase
      end
    end
  endtask
'''


def generate_tb():
    text = base.generate_tb(True, 'nominal150')
    # Insert declarations after the frozen hierarchy macros, before tasks.
    text = base.once(text, '  // Observation only: these counters never drive',
                     UPLOAD_DECLARATIONS + '\n  // Observation only: these counters never drive')
    text = base.once(text, '    #1; // Finish vendor initialization before the first HF edge.', r'''
    if (!$value$plusargs("XU_GLOBAL_TASK=%d",xu_global_task) ||
        xu_global_task<0 || xu_global_task>11) $fatal(1,"missing/invalid XU_GLOBAL_TASK");
    if (tasks!=1) $fatal(1,"SAIF collector requires one task per fresh process");
    for (i=0;i<16384;i=i+1) xu_w_seen[i]=0;
    for (i=0;i<256;i=i+1) xu_bias_seen[i]=0;
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
    $set_gate_level_monitoring("rtl_on");
    $set_toggle_region(tb_xu_soc_ppa.dut);
`endif
    #1; // Finish vendor initialization before the first HF edge.''')
    text = base.once(text,
                    '          $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",layer,$realtime*1000000.0);', r'''
          if (xu_saif_started || xu_saif_stopped || `ACCEL.cache_enable!==1'b0 ||
              `ACCEL.busy!==1'b0 || `ACCEL.core_start!==1'b0 ||
              xu_w_count!=0 || xu_bias_count!=0 || xu_x_count!=0 || xu_starts!=0)
            $fatal(1,"task did not begin from fresh disabled idle state");
          xu_saif_started=1;
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_start();
`endif
          $display("XU_ACTIVITY_BEGIN task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
          $display("XU_CACHE_INITIAL task=%0d fresh_process=1 cache_enable=0 busy=0 prior_uploads=0 prior_starts=0",xu_global_task);''')
    text = base.once(text, '        phase_now=perf_phase;',
                     '        xu_observe_upload();\n        phase_now=perf_phase;')
    # Detect an accelerator upload before or after the single allowed window.
    text = base.once(text, '      if (in_window) begin\n',
                     '      if (!in_window) xu_observe_upload();\n      if (in_window) begin\n')
    text = base.once(text,
                    '          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",layer,$realtime*1000000.0);', r'''
          if (!xu_saif_started || xu_saif_stopped || xu_w_count!=16384 ||
              xu_bias_count!=256 || xu_x_count!=6336 || xu_rows!=99 || xu_starts!=3168)
            $fatal(1,"incomplete task upload/start coverage at final Y response");
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_stop();
`endif
          xu_saif_stopped=1;
          $display("XU_ACTIVITY_END task=%0d tick=%0.0f",xu_global_task,$realtime*1000000.0);
          $display("XU_CACHE_UPLOAD_PASS task=%0d w=16384 bias=256 x=6336 rows=99 starts=3168 window=inside checked_data=1",xu_global_task);
`ifndef XU_TASK_ACTIVITY_HOST_CHECK
          $toggle_report("task.saif",1.0e-15,"tb_xu_soc_ppa.dut");
`endif''')
    text = base.once(text,
                    '"XU_CACHE_RELOAD task=%0d done_before_begin=1 scope=shared_fixture tick=%0.0f",index,',
                    '"XU_CACHE_RELOAD task=%0d done_before_begin=1 scope=shared_fixture tick=%0.0f",xu_global_task,')
    text = base.once(text, '        $display("XU_CLOCK_STATIC_PASS',
                     '        if (!xu_saif_stopped) $fatal(1,"missing SAIF end");\n        $display("XU_CLOCK_STATIC_PASS')
    return text


def collect_sources(generated, vendor, weight_adapter):
    excluded = {base.RTL / 'general/sirv_sim_ram.v', base.RTL / 'perips/mem_1024x16.sv'}
    sources = sorted(p for p in base.RTL.rglob('*') if p.suffix in ('.v', '.sv') and p not in excluded)
    return sources + [HERE / 'xu_sirv_sram_adapter.sv', weight_adapter, vendor,
                      HERE / 'xu_shared_icb_sram.sv', HERE / 'xu_soc_ppa_top.sv', generated]


def checked_log(log, task_id, schedule):
    layers = soc.check_log(log, 1)
    layers[0]['performance'] = soc.check_performance(log, layers, schedule)[0]
    window = base.check_windows(log, layers)[0]
    for kind, value in (('BEGIN', window['begin']['tick']), ('END', window['end']['tick'])):
        expected = 'XU_ACTIVITY_%s task=%d tick=%d' % (kind, task_id, value)
        require(re.findall(r'^XU_ACTIVITY_' + kind + r'.*$', log, re.M) == [expected],
                'global task boundary identity differs')
    expected_initial = ('XU_CACHE_INITIAL task=%d fresh_process=1 cache_enable=0 busy=0 '
                        'prior_uploads=0 prior_starts=0') % task_id
    expected_upload = ('XU_CACHE_UPLOAD_PASS task=%d w=16384 bias=256 x=6336 rows=99 '
                       'starts=3168 window=inside checked_data=1') % task_id
    for expected in (expected_initial, expected_upload):
        require(log.splitlines().count(expected) == 1, 'passive cache/upload evidence missing')
    return layers[0], window


def inspect_activity(path, window):
    observed = activity.read_saif(path)
    expected = Decimal(window['duration_ticks']) * Decimal('1e-15')
    require(Decimal(observed['duration_seconds']) == expected,
            'SAIF DURATION differs from first-read/final-Y-retire physical timestamps')
    prefix = SCOPE.replace('.', '/')
    clocks = [s for s in observed['signals'] if s['path'] == prefix + '/hfextclk']
    require(clocks, 'full-SoC source clock missing from SAIF')
    expected_edges = expected * Decimal(300000000)
    require(all(abs(Decimal(s['TC']) - expected_edges) <= 2 and s['TX'] == 0 and
                s.get('TZ', 0) == 0 for s in clocks), 'SAIF source clock differs from nominal150')
    require(all(s['path'].startswith(prefix + '/') for s in observed['signals']),
            'SAIF scope includes objects outside full-SoC DUT')
    # Presence checks are deliberately separate from mapped PT coverage review.
    paths = [s['path'] for s in observed['signals']]
    groups = {
        'cpu': '/u_e203_cpu_top/', 'accelerator': '/u_accel_icb_slave/',
        'interconnect': '/u_e203_biu/', 'shared': '/u_shared/',
        'itcm': '/u_e203_itcm_ram/', 'dtcm': '/u_e203_dtcm_ram/'}
    coverage = {}
    for name, fragment in groups.items():
        signals = [s for s in observed['signals'] if fragment in s['path']]
        require(len(signals) > 1 and any(s['TC'] for s in signals), 'SAIF scope missing/inactive: ' + name)
        coverage[name] = dict(signal_count=len(signals), total_toggles=sum(s['TC'] for s in signals))
    macro_groups = {'shared': ('/u_shared/', 256), 'itcm': ('/u_e203_itcm_ram/', 32),
                    'dtcm': ('/u_e203_dtcm_ram/', 32),
                    'accelerator_weights': ('/u_linear_compute_core/core/', 16)}
    macros = {}
    for name, (fragment, count) in macro_groups.items():
        instances = sorted({p.rsplit('/macro/', 1)[0] + '/macro'
                            for p in paths if fragment in p and '/macro/' in p})
        require(len(instances) == count, 'SAIF SRAM macro count differs: ' + name)
        macros[name] = dict(expected_count=count, observed_count=len(instances), instances=instances,
                            pin_coverage_and_internal_power_status='REVIEW_PENDING')
    return dict(path=str(path), sha256=observed['sha256'],
                timescale_seconds=observed['timescale_seconds'],
                duration_ticks=observed['duration_ticks'], duration_seconds=observed['duration_seconds'],
                signal_count=len(paths), source_clock=clocks, scope_presence=coverage,
                macro_inventory=macros,
                mapped_coverage_status='REVIEW_PENDING')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--vendor-model', type=Path, required=True)
    parser.add_argument('--weight-adapter', type=Path, default=HERE / 'xu_weight_sram_adapter.sv')
    parser.add_argument('--vectors', type=Path)
    parser.add_argument('--vcs', default='vcs')
    parser.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    parser.add_argument('--netlist', type=Path, required=True, help='same frozen DC/PT target identity; not simulated')
    parser.add_argument('--constraints', type=Path, required=True, help='same frozen nominal150 SDC identity')
    parser.add_argument('--max-cycles', type=int, default=3000000)
    parser.add_argument('--build-timeout', type=int, default=1800)
    parser.add_argument('--run-timeout', type=int, default=7200)
    parser.add_argument('--initialize-vendor-memory', action='store_true',
                        help='add vendor-supported INITIALIZE_MEMORY define; records a distinct frozen recipe')
    parser.add_argument('--prepare-only', action='store_true', help='build firmware and materialize all inputs, skip VCS')
    contract.add_arguments(parser)
    parser.set_defaults(firmware_schedule='bias-hw-window', firmware_opt='-O2',
                        firmware_experiment='both-unroll-no-masks')
    next(action for action in parser._actions if action.dest == 'firmware_opt').help = (
        'compiler optimization; use --firmware-opt=-O2 (default: -O2)')
    args = parser.parse_args(argv)
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='xu-soc-isolated-task-activity-v1', status='RUNNING', nominal_hz=150000000,
                  clock_mode='nominal150', tasks=[], limitations=[
                      'RTL SAIF collection only; no mapped functional equivalence, STA or power result',
                      'initial physical data/parameter clearing and formal cache policy remain REVIEW_PENDING',
                      'shared fixture preload is not accelerator cache clearing',
                      'PT activity mapping and SRAM Liberty/internal-power review remain REVIEW_PENDING'])
    try:
        require(args.firmware_schedule in ('bias-hw', 'bias-hw-window'),
                'complete 256-entry pre-START bias proof requires bias-hw or bias-hw-window')
        args.vendor_model = args.vendor_model.resolve()
        args.weight_adapter = args.weight_adapter.resolve()
        vendor = identity(args.vendor_model)
        require(re.search(r'reg\s*\[63:0\]\s*mem\s*\[0:255\]', args.vendor_model.read_text()),
                'vendor preload geometry differs from frozen generator')
        report['vendor_model'] = vendor
        defines = ['ARM_UD_MODEL', 'DISABLE_SV_ASSERTION=1']
        if args.initialize_vendor_memory:
            defines.append('INITIALIZE_MEMORY')
        report['vendor_initialization'] = dict(
            status='REVIEW_PENDING', command_line_defines=defines,
            initialize_memory_requested=args.initialize_vendor_memory,
            note='Original vendor model is unchanged. INITIALIZE_MEMORY is optional and changes the frozen recipe; no force or DUT-driven physical clearing is added.')
        report['e203_commit'] = verify_frozen_child(args.out)
        report['main_commit'] = soc.run(['git', 'rev-parse', 'HEAD'], ROOT, args.out / 'main-commit.log').strip()
        report['helpers'] = [identity(m.__file__) for m in (base, soc, contract, activity)]
        report['runner'] = identity(__file__)
        early = {item['path']: item['sha256'] for item in report['helpers'] +
                 [report['runner'], vendor, identity(args.weight_adapter), identity(base.TB)]}
        firmware_sources = [p for p in (soc.TESTS / 'firmware').iterdir() if p.is_file()]
        early.update({str(p): base.sha(p) for p in firmware_sources})
        report['firmware_input_sources_sha256'] = {str(p): early[str(p)] for p in firmware_sources}
        (args.out / 'runner-source.py').write_bytes(Path(__file__).read_bytes())
        vectors = args.vectors.resolve() if args.vectors else args.out / 'original-vectors'
        if args.vectors is None:
            report['fixture'] = soc.load_fixture(vectors, 12)
        validated = soc.check_vectors(vectors, 12)
        report['original_task_vectors'] = validated
        firmware_dir = args.out / 'firmware'
        firmware_dir.mkdir()
        firmware = soc.compile_firmware(firmware_dir, args.cross_prefix, args.firmware_schedule,
                                        args.firmware_opt, args.firmware_experiment, report)
        unchanged(early)
        build = args.out / 'simulator'
        build.mkdir()
        generated = build / 'tb_xu_soc_task_activity.sv'
        generated.write_text(generate_tb())
        sources = collect_sources(generated, args.vendor_model, args.weight_adapter)
        frozen = {str(p): base.sha(p) for p in sources}
        config = dict(rtl_sources_sha256=frozen, original_tb=identity(base.TB),
                      firmware_image=identity(str(firmware) + '.verilog'),
                      firmware_elf=identity(firmware), testbench=identity(generated),
                      netlist=identity(args.netlist), constraints=identity(args.constraints),
                      vendor_model=vendor, nominal_hz=150000000, numeric_format='signed16/40/48',
                      firmware_configuration=contract.configuration(args.firmware_schedule, args.firmware_opt,
                                                                    args.firmware_experiment),
                      activity_scope=SCOPE, monitoring_policy='rtl_on',
                      simulator_defines=defines,
                      process_policy='one fresh simulation process and one activity window per actual task')
        report['configuration'] = config
        report['configuration_sha256'] = activity.canonical_hash(config)
        identities = dict(early)
        identities.update(frozen)
        for item in (config['netlist'], config['constraints'], config['firmware_image'], config['firmware_elf'],
                     config['original_tb']) + tuple(report['helpers']) + (report['runner'],):
            identities[item['path']] = item['sha256']
        filelist = build / 'rtl.f'
        filelist.write_text('\n'.join(str(p) for p in sources) + '\n')
        command = base.build_command('vcs', 'macro', build, filelist, True, 'nominal150')
        command[0] = args.vcs
        if args.initialize_vendor_memory:
            command.insert(1, '+define+INITIALIZE_MEMORY')
        report['build_command'] = command
        tasks = []
        for task_id in range(12):
            destination = args.out / ('task_%02d' % task_id)
            destination.mkdir()
            inputs = materialize_task(vectors, destination / 'vectors', task_id, validated[task_id])
            tasks.append((destination, inputs))
            for record in inputs['files']:
                for key in ('original', 'materialized'):
                    identities[record[key]['path']] = record[key]['sha256']
            manifest = identity(destination / 'vectors/input-manifest.json')
            identities[manifest['path']] = manifest['sha256']
        report['taskset_inputs_sha256'] = activity.canonical_hash({
            str(i): inputs for i, (_, inputs) in enumerate(tasks)})
        unchanged(identities)
        if args.prepare_only:
            report['status'] = 'PREPARED_NOT_SIMULATED'
            report['tasks'] = [dict(task_id=i, input_manifest=identity(d / 'vectors/input-manifest.json'))
                               for i, (d, _) in enumerate(tasks)]
        else:
            soc.run([args.vcs, '-ID'], build, build / 'vcs-version.log', args.build_timeout)
            log = soc.run(command, build, build / 'build.log', args.build_timeout)
            require(not re.search(r'Error-\[|undefined system task|unknown system task', log, re.I),
                    'VCS diagnostic failure; see simulator/build.log')
            binary = build / 'soc'
            identities[str(binary)] = base.sha(binary)
            report['binary'] = identity(binary)
            for task_id, (destination, inputs) in enumerate(tasks):
                unchanged(identities)
                for record in inputs['files']:
                    require(identity(record['original']['path']) == record['original'] and
                            identity(record['materialized']['path']) == record['materialized'],
                            'task source/materialization changed')
                run = [str(binary), '+TESTCASE=' + str(firmware), '+VECTORS=' + str(destination / 'vectors'),
                       '+TASKS=1', '+XU_GLOBAL_TASK=' + str(task_id),
                       '+MAX_CYCLES=' + str(args.max_cycles), '+DUMPWAVE=0']
                log = soc.run(run, destination, destination / 'simulation.log', args.run_timeout)
                layer, window = checked_log(log, task_id, args.firmware_schedule)
                saif = inspect_activity(destination / 'task.saif', window)
                unchanged(identities)
                result = dict(task_id=task_id, configuration_sha256=report['configuration_sha256'],
                              status='COLLECTED_REVIEW_PENDING', local_scoreboard_layer=0, layer=layer,
                              input_manifest=identity(destination / 'vectors/input-manifest.json'),
                              run_command=run, boundary_log=identity(destination / 'simulation.log'),
                              activity_window=window, saif=saif,
                              cache_policy=dict(status='REVIEW_PENDING', fresh_process=True,
                                                reset_cache_enable_zero_observed=True,
                                                complete_fixture_matched_uploads_inside_window_observed=True,
                                                no_prior_task_in_process=True,
                                                physical_initial_clearing_proven=False))
                write_json(destination / 'result.json', result)
                report['tasks'].append(result)
                write_json(args.out / 'result.json', report)
                print('COLLECTED task=%d duration_fs=%d' % (task_id, window['duration_ticks']), flush=True)
            report['status'] = 'COLLECTED_12_TASKS_REVIEW_PENDING'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        print('FAIL: ' + str(error), file=sys.stderr)
    write_json(args.out / 'result.json', report)
    print(report['status'] + ': ' + str(args.out / 'result.json'), flush=True)
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
