"""Shared xu firmware identities and fixed development-task work contracts."""

PHASES = ['w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other']
PERFORMANCE_FIELDS = ['layer', 'cycles', *PHASES, 'busy', 'mac_fire',
                      'mmio_reads', 'mmio_writes', 'shared_reads', 'shared_writes',
                      'shared_stall', 'mmio_stall', 'starts', 'dones']
PES = 8
MACS_PER_TASK = 99 * 64 * 256
OUTPUTS_PER_TASK = 99 * 256
SCHEDULES = ('baseline', 'bias-dtcm', 'bias-hw', 'bias-dtcm-window', 'bias-hw-window',
             'bias-hw-stream16-window')
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
    # Keep every legacy command line unchanged; stream is explicitly opt-in.
    if config['schedule'] == 'bias-hw-stream16-window':
        values['XU_HARDWARE_STREAM16'] = True
    return ['-D' + name + '=' + str(int(value)) for name, value in values.items()]


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
    return dict(w_shared_reads=w_reads, x_shared_reads=x_reads, bias_shared_reads=bias_reads,
                shared_reads=w_reads + x_reads + bias_reads, shared_writes=50688,
                bias_mmio_writes=bias_writes, mmio_writes=mmio_writes,
                starts=99 * 32, dones=99 * 32,
                mac_fire=MACS_PER_TASK // PES, macs=MACS_PER_TASK, outputs=OUTPUTS_PER_TASK)


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
