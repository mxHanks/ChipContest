"""Shared xu firmware identities and fixed development-task work contracts."""

PHASES = ['w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other']
PERFORMANCE_FIELDS = ['layer', 'cycles', *PHASES, 'busy', 'mac_fire',
                      'mmio_reads', 'mmio_writes', 'shared_reads', 'shared_writes',
                      'shared_stall', 'mmio_stall', 'starts', 'dones']
PES = 8
MACS_PER_TASK = 99 * 64 * 256
OUTPUTS_PER_TASK = 99 * 256
SCHEDULES = ('baseline', 'bias-dtcm', 'bias-hw', 'bias-dtcm-window', 'bias-hw-window',
             'bias-hw-stream16-window', 'bias-hw-pack32-window', 'bias-hw-autogroup-window',
             'bias-hw-autogroup-paired-hi-window', 'bias-hw-autogroup-y32-window',
             'bias-hw-autogroup-paired-hi-packed16-window',
             'bias-hw-autogroup-y32-packed16-window',
             'bias-hw-autogroup-y32-packed16-nice-window',
             'bias-hw-autogroup-y32-packed16-nice-read-pop-window',
             'bias-hw-autogroup-y32-packed16-nice-direct-window',
             'bias-hw-autogroup-y32-packed16-nice-direct-stream-window')
PAIRED_HI_SCHEDULE = 'bias-hw-autogroup-paired-hi-window'
PAIRED_HI_PACKED16_SCHEDULE = 'bias-hw-autogroup-paired-hi-packed16-window'
PAIRED_HI_SCHEDULES = (PAIRED_HI_SCHEDULE, PAIRED_HI_PACKED16_SCHEDULE)
Y32_SCHEDULE = 'bias-hw-autogroup-y32-window'
Y32_PACKED16_SCHEDULE = 'bias-hw-autogroup-y32-packed16-window'
NICE_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-window'
NICE_READ_POP_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-read-pop-window'
NICE_DIRECT_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-direct-window'
NICE_STREAM_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-direct-stream-window'
DIRECT_SCHEDULES = (NICE_DIRECT_SCHEDULE, NICE_STREAM_SCHEDULE)
NICE_SCHEDULES = (NICE_SCHEDULE, NICE_READ_POP_SCHEDULE) + DIRECT_SCHEDULES
Y32_SCHEDULES = (Y32_SCHEDULE, Y32_PACKED16_SCHEDULE) + NICE_SCHEDULES
PACKED16_SCHEDULES = (PAIRED_HI_PACKED16_SCHEDULE, Y32_PACKED16_SCHEDULE) + NICE_SCHEDULES
AUTOGROUP_SCHEDULES = ('bias-hw-autogroup-window',) + PAIRED_HI_SCHEDULES + Y32_SCHEDULES
OPTIMIZATIONS = ('-Os', '-O2', '-O3')
EXPERIMENTS = ('none', 'bias-unroll', 'result-unroll', 'both-unroll', 'no-masks',
               'bias-unroll-no-masks', 'result-unroll-no-masks', 'both-unroll-no-masks')


def configuration(schedule='baseline', optimization='-Os', experiment='none'):
    if schedule not in SCHEDULES:
        raise ValueError('unknown firmware schedule: ' + str(schedule))
    if optimization not in OPTIMIZATIONS:
        raise ValueError('unknown firmware optimization: ' + str(optimization))
    if experiment not in EXPERIMENTS:
        raise ValueError('unknown firmware experiment: ' + str(experiment))
    return dict(schedule=schedule, optimization=optimization, experiment=experiment)


def configuration_from_result(result):
    # Reports predating explicit configuration describe the historical -Os path.
    config = configuration(result.get('firmware_schedule', 'baseline'),
                           result.get('firmware_opt', '-Os'),
                           result.get('firmware_experiment', 'none'))
    built = (result.get('firmware_build') or {}).get('configuration')
    if built is not None and built != config:
        raise ValueError('firmware build and run configuration differ')
    if ('transaction_contract' in result and
            result['transaction_contract'] != task_contract(config['schedule'])):
        raise ValueError('firmware transaction contract differs from the schedule')
    if config['schedule'] in NICE_SCHEDULES and result.get('mode') == 'real':
        validate_nice_activity(result.get('nice_activity', []), result.get('layers', []),
                               config['schedule'])
    return config


def add_arguments(parser):
    parser.add_argument('--firmware-schedule', choices=SCHEDULES, default='baseline')
    parser.add_argument('--firmware-opt', choices=OPTIMIZATIONS, default='-Os',
                        help='compiler optimization; use --firmware-opt=-O2 (default: -Os)')
    parser.add_argument('--firmware-experiment', choices=EXPERIMENTS, default='none')


def compiler_defines(config):
    config = configuration(**config)
    experiment = config['experiment']
    values = {'XU_FIRMWARE_BIAS_DTCM': config['schedule'].startswith('bias-dtcm'),
              'XU_HARDWARE_BIAS_CACHE': config['schedule'].startswith('bias-hw'),
              'XU_HARDWARE_RESULT_WINDOW': config['schedule'].endswith('-window'),
              'XU_FIRMWARE_BIAS_UNROLL': experiment.startswith(('bias-unroll', 'both-unroll')),
              'XU_FIRMWARE_RESULT_UNROLL': experiment.startswith(('result-unroll', 'both-unroll')),
              'XU_FIRMWARE_NO_MASKS': experiment.endswith('no-masks')}
    # Keep every legacy command line unchanged; streaming modes are opt-in.
    if config['schedule'] == 'bias-hw-stream16-window':
        values['XU_HARDWARE_STREAM16'] = True
    if config['schedule'] in ('bias-hw-pack32-window',) + AUTOGROUP_SCHEDULES:
        values['XU_HARDWARE_PACK32'] = True
    if config['schedule'] in AUTOGROUP_SCHEDULES:
        values['XU_HARDWARE_AUTO_GROUP'] = True
    if config['schedule'] in PAIRED_HI_SCHEDULES:
        values['XU_HARDWARE_PAIRED_HI'] = True
    if config['schedule'] in Y32_SCHEDULES:
        values['XU_HARDWARE_Y32'] = True
    if config['schedule'] in PACKED16_SCHEDULES:
        values['XU_SHARED_W_PACKED16'] = True
    if config['schedule'] in NICE_SCHEDULES:
        values['XU_NICE_DRAIN8'] = True
    if config['schedule'] in DIRECT_SCHEDULES:
        values['XU_NICE_DIRECT'] = True
    if config['schedule'] == NICE_STREAM_SCHEDULE:
        values['XU_NICE_DRAINN'] = True
    return ['-D' + name + '=' + str(int(value)) for name, value in values.items()]


def simulator_arguments(schedule='baseline'):
    configuration(schedule)
    arguments = ['+OUTPUT_Y32=1'] if schedule in Y32_SCHEDULES else []
    if schedule in PACKED16_SCHEDULES:
        arguments.append('+SHARED_W_PACKED16=1')
    if schedule in NICE_SCHEDULES:
        arguments.append('+NICE_DRAIN8=1')
    # This selects the observer/contract for the matching RTL snapshot. It
    # does not switch hardware behavior or change the custom instruction ABI.
    if schedule == NICE_READ_POP_SCHEDULE:
        arguments.append('+NICE_READ_POP=1')
    if schedule in DIRECT_SCHEDULES:
        arguments.append('+NICE_DIRECT=1')
    if schedule == NICE_STREAM_SCHEDULE:
        arguments.append('+NICE_STREAM=1')
    return arguments


def task_contract(schedule='baseline'):
    configuration(schedule)
    w_reads, x_reads = 16384, 6336
    bias_reads = 99 * 512 if schedule == 'baseline' else 512
    bias_writes = 768 if schedule.startswith('bias-hw') else 76032
    control_writes = 2 if schedule.startswith('bias-hw') else 0
    result_index_writes = 0 if schedule.endswith('-window') else OUTPUTS_PER_TASK
    mmio_writes = 156326 - 76032 + bias_writes + control_writes - OUTPUTS_PER_TASK + result_index_writes
    if schedule == 'bias-hw-stream16-window':
        # W: cursor + 16384 data; X: 99*(cursor + 64 data).
        # Unlike legacy BANK=0/ADDR=0, the stream W cursor is inside the window.
        mmio_writes = (1 + w_reads) + 99 * (1 + 64) + 768 + 2 + 3 * 99 * 32
    if schedule == 'bias-hw-pack32-window':
        # Pack two signed 16-bit source values into each W/X data write.
        mmio_writes = (1 + w_reads // 2) + 99 * (1 + 32) + 768 + 2 + 3 * 99 * 32
    if schedule in AUTOGROUP_SCHEDULES:
        # One STARTROW and 32 response-retired POPs per row. No GROUP/W1C.
        mmio_writes = (1 + w_reads // 2) + 99 * (1 + 32) + 768 + 2 + 99 * (1 + 32)
    if schedule in (NICE_READ_POP_SCHEDULE,) + DIRECT_SCHEDULES:
        # Direct or lane7 read response retires each POP, removing 32 writes per row.
        mmio_writes -= 99 * 32
    if schedule in DIRECT_SCHEDULES:
        # One measured DIRECT_CTRL mode write. Eight lane reads disappear;
        # the frozen ROW_STATUS polling still uses the real LSU.
        mmio_writes += 1
    # Source packing does not change the 8192 W_PACK32 upload transactions.
    if schedule in PACKED16_SCHEDULES:
        w_reads = 8192
    result = dict(w_shared_reads=w_reads, x_shared_reads=x_reads, bias_shared_reads=bias_reads,
                shared_reads=w_reads + x_reads + bias_reads,
                shared_writes=OUTPUTS_PER_TASK if schedule in Y32_SCHEDULES else 50688,
                bias_mmio_writes=bias_writes, mmio_writes=mmio_writes,
                starts=99 * 32, dones=99 * 32,
                mac_fire=MACS_PER_TASK // PES, macs=MACS_PER_TASK, outputs=OUTPUTS_PER_TASK)
    if schedule in PAIRED_HI_SCHEDULES:
        result.update(result_mmio_reads=38016, paired_hi_mmio_reads=12672)
    if schedule in Y32_SCHEDULES:
        result.update(result_mmio_reads=OUTPUTS_PER_TASK, y32_mmio_reads=OUTPUTS_PER_TASK,
                      w_mmio_upload_words=8192, rows=99, pops_retired=3168)
    if schedule in NICE_SCHEDULES:
        result.update(nice_requests=3168, nice_responses=3168, nice_oitf_retired=3168)
    if schedule in DIRECT_SCHEDULES:
        result.update(result_mmio_reads=0, y32_mmio_reads=0,
                      direct_snapshots=3168, direct_lanes=OUTPUTS_PER_TASK)
    if schedule == NICE_STREAM_SCHEDULE:
        result.update(nice_requests=99, nice_responses=99, nice_oitf_retired=99,
                      stream_groups=3168)
    return result


def validate_result_activity(records, layers, schedule):
    """Count real output responses separately from MMIO polling reads."""
    required = schedule in PAIRED_HI_SCHEDULES or schedule in Y32_SCHEDULES
    if not records and not required:
        return
    if schedule not in AUTOGROUP_SCHEDULES or len(records) != len(layers):
        raise ValueError('missing or unexpected result activity records')
    if schedule in Y32_SCHEDULES:
        for record, layer in zip(records, layers):
            if (set(record) != {'layer', 'words', 'logical_results'} or
                    any(type(v) is not int or v < 0 for v in record.values()) or
                    record != dict(layer=layer['layer'], words=OUTPUTS_PER_TASK,
                                   logical_results=OUTPUTS_PER_TASK)):
                raise ValueError('Y32 response work or result coverage differs')
        return
    packed = 12672 if required else 0
    legacy = 25344 if required else 50688
    for record, layer in zip(records, layers):
        if (set(record) != {'layer', 'legacy_words', 'packed_words', 'logical_words'} or
                any(type(v) is not int or v < 0 for v in record.values()) or
                record != dict(layer=layer['layer'], legacy_words=legacy,
                               packed_words=packed, logical_words=50688)):
            raise ValueError('result response work or canonical word coverage differs')


def validate_performance(perf, cycles, schedule='baseline'):
    expected = set(PERFORMANCE_FIELDS) - {'layer', 'cycles'}
    if set(perf) != expected or any(type(v) is not int or v < 0 for v in perf.values()):
        raise ValueError('missing or invalid performance counters')
    if type(cycles) is not int or cycles <= 0 or sum(perf[p] for p in PHASES) != cycles:
        raise ValueError('performance phases do not cover the task window')
    if not perf['mac_fire'] <= perf['busy'] <= cycles:
        raise ValueError('invalid MAC/busy activity')
    contract = task_contract(schedule)
    if any(perf[k] != contract[k] for k in ['mac_fire', 'starts', 'dones', 'mmio_writes',
                                            'shared_reads', 'shared_writes']):
        raise ValueError('performance work counters differ from the firmware schedule')
    if any(value > cycles for value in perf.values()):
        raise ValueError('performance counter exceeds measured window')


def validate_nice_activity(records, layers, schedule):
    names = {'layer', 'requests', 'responses', 'oitf_retired', 'status_polls',
             'result_reads', 'pops_retired', 'shared_writes'}
    expected = len(layers) if schedule in NICE_SCHEDULES else 0
    if len(records) != expected:
        raise ValueError('missing or unexpected NICE activity')
    for record, layer in zip(records, layers):
        if (set(record) != names or any(type(v) is not int or v < 0 for v in record.values()) or
                record['layer'] != layer['layer'] or
                any(record[key] != (99 if schedule == NICE_STREAM_SCHEDULE else 3168)
                    for key in ['requests', 'responses', 'oitf_retired']) or
                record['pops_retired'] != 3168 or
                record['result_reads'] != (0 if schedule in DIRECT_SCHEDULES else OUTPUTS_PER_TASK) or
                record['shared_writes'] != OUTPUTS_PER_TASK or
                not 3168 <= record['status_polls'] <= layer['cycles']):
            raise ValueError('NICE instruction retirement or payload coverage differs')
