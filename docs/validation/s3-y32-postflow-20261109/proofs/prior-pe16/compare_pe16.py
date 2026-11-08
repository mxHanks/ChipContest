#!/usr/bin/env python3
"""Read-only saved-evidence comparison for this explicit 8-PE -> 16-PE experiment.

Never runs a simulator or modifies a campaign. This is a separate physical-PE
loader, not a PASS from the production 8-PE writeback reporter. Artifact, log,
source, vector, ELF/image, command, clock, reset and clear checks were copied
from s3_writeback_report.py and retained. Only the exact 16-PE physical work
profile is added; both control streams require their independent PE16_TASK.
"""

# Copied verifier source SHA256: 61f8a79741a801d389e10b2cc9b3c0bee5eb75726a87dbba3ba0a5a003c7a523
import argparse
import copy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys


PHASES = ('w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other')
PERFORMANCE = (*PHASES, 'busy', 'mac_fire', 'mmio_reads', 'mmio_writes',
               'shared_reads', 'shared_writes', 'shared_stall', 'mmio_stall', 'starts', 'dones')
NICE = ('requests', 'responses', 'oitf_retired', 'status_polls', 'result_reads',
        'pops_retired', 'shared_writes')
AUTO = ('rows', 'pops_retired', 'compute_writeback_overlap', 'fifo_full_wait')
WINDOW = ('first_request', 'first_accept', 'final_y_response', 'first_request_wait')
SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-window'
READ_POP_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-read-pop-window'
DIRECT_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-direct-window'
DIRECT_SOURCE_PATHS = frozenset((
    'rtl/core/e203_cpu.v', 'rtl/core/e203_cpu_top.v',
    'rtl/perips/accel_icb_slave.v', 'rtl/subsys/e203_subsys_main.v',
    'rtl/subsys/e203_subsys_nice_core.v', 'rtl/subsys/e203_subsys_perips.v',
    'rtl/subsys/xu_nice_drain8.v', 'tests/e203/firmware/accel.c',
    'tests/e203/tb_accel_soc.sv', 'tools/scripts/e203_soc.py',
    'tools/scripts/xu_firmware_contract.py'))
DIRECT_REQUIRED_CHANGES = frozenset(('rtl/perips/accel_icb_slave.v',
    'rtl/subsys/xu_nice_drain8.v', 'tests/e203/firmware/accel.c',
    'tools/scripts/xu_firmware_contract.py'))
PASS = 'DEVELOPMENT_PASS_POLICY_PENDING'
SHA = re.compile(r'[0-9a-f]{64}\Z')
HISTORICAL_STARTUP = dict(profile='historical', version='historical-single-release',
                          counter_origin='historical TB clock origin',
                          scope='original external pad reset stimulus')
EXTERNAL_RESET_STARTUP = dict(profile='external-reset', version='external-pad-double-reset-v1',
    external_reset_low_ns=120, prewarm_watchdog_ns=10000000,
    counter_origin='after_final_external_reset_release',
    scope='Verilator development only; external pad reset, no internal state initialization',
    prewarm='wait actual CPU rst_core high, then assert external reset on next HF falling edge; any source/NICE/MMIO/shared request fails')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def loaded_elf_identity(path):
    """ELF32 little-endian RISC-V load contract, excluding nonloaded metadata."""
    data = path.read_bytes()
    require(len(data) >= 52, 'truncated ELF32 header')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    ident, elf_type, machine, version, entry, phoff, _, flags, ehsize, phentsize, phnum, _, _, _ = header
    require(ident[:7] == b'\x7fELF\x01\x01\x01' and elf_type == 2 and machine == 243 and version == 1,
            'requires ELF32 little-endian executable RISC-V')
    require(ehsize == 52 and phentsize == 32 and 0 < phnum < 65535 and
            phoff >= ehsize and phoff + phnum * phentsize <= len(data),
            'invalid ELF32 program-header table')
    segments = []
    for index in range(phnum):
        kind, offset, vaddr, paddr, filesz, memsz, permissions, alignment = struct.unpack_from(
            '<IIIIIIII', data, phoff + index * phentsize)
        if kind != 1:
            continue
        require(memsz >= filesz and offset + filesz <= len(data) and
                vaddr + memsz <= 2 ** 32 and paddr + memsz <= 2 ** 32,
                'invalid ELF32 PT_LOAD bounds')
        require(alignment in (0, 1) or (alignment & (alignment - 1) == 0 and
                offset % alignment == vaddr % alignment), 'invalid ELF32 PT_LOAD alignment')
        segments.append(dict(vaddr=vaddr, paddr=paddr, filesz=filesz, memsz=memsz,
                             flags=permissions, align=alignment,
                             bytes_sha256=hashlib.sha256(data[offset:offset + filesz]).hexdigest()))
    require(segments and any(segment['flags'] & 1 and
            segment['vaddr'] <= entry < segment['vaddr'] + segment['memsz'] for segment in segments),
            'ELF32 entry is outside executable PT_LOAD segments')
    return dict(header=dict(e_type=elf_type, e_machine=machine, e_entry=entry, e_flags=flags),
                load_segments=segments)


def read_json(path):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=no_duplicates)


def verify_loaded_image(campaign):
    """Match the actual 64KiB ITCM byte image to every file-backed ELF load byte.

    The campaign's objcopy seam rewrites @800... to @000..., and the TB loads
    those bytes into program_bytes[0:65535]. Nonloaded ELF metadata and BSS do
    not contribute image bytes. Never run objcopy or trust a claimed mapping.
    """
    path = artifact(Path(campaign['result_path']).parent, 'accel_soc.verilog',
                    campaign['firmware_image_sha256'])
    memory, address = {}, None
    for token in path.read_text().split():
        if re.fullmatch(r'@[0-9a-fA-F]+', token):
            address = int(token[1:], 16)
        else:
            require(address is not None and re.fullmatch(r'[0-9a-fA-F]{2}', token),
                    'malformed firmware Verilog load image')
            require(0 <= address < 65536 and address not in memory,
                    'firmware image address outside ITCM or duplicated')
            memory[address] = int(token, 16)
            address += 1
    expected_addresses = set()
    for segment in campaign['firmware_loaded_elf']['load_segments']:
        if not segment['filesz']:
            continue
        first = segment['paddr'] - 0x80000000
        last = first + segment['filesz']
        require(0 <= first < last <= 65536, 'ELF file-backed load outside campaign ITCM mapping')
        addresses = set(range(first, last))
        require(not (addresses & expected_addresses) and addresses <= memory.keys(),
                'ELF load bytes overlap or are missing from firmware image')
        loaded = bytes(memory[index] for index in range(first, last))
        require(hashlib.sha256(loaded).hexdigest() == segment['bytes_sha256'],
                'firmware image bytes differ from ELF PT_LOAD')
        expected_addresses.update(addresses)
    require(expected_addresses and set(memory) == expected_addresses,
            'firmware image contains bytes outside ELF PT_LOAD')
    return dict(verified=True, mapping='ELF physical 0x80000000 -> 64KiB ITCM offset0',
                loaded_bytes=len(memory), image_sha256=campaign['firmware_image_sha256'])


def generated_clear_c_identity(path, old_out):
    """Normalize only the known frozen-main include, preserving all other bytes."""
    data = path.read_bytes()
    include = ('#include "' + str(old_out / 'source/tests/e203/firmware/main.c') + '"').encode()
    require(data.splitlines().count(include) == 1 and data.count(include) == 1,
            'generated clear C lacks its one exact frozen-main snapshot include')
    normalized = data.replace(include,
        b'#include "@CAMPAIGN_SOURCE@/tests/e203/firmware/main.c"', 1)
    return dict(normalized_sha256=hashlib.sha256(normalized).hexdigest(),
                normalization='only exact frozen-main snapshot include path; all other bytes unchanged')


def artifact(root, relative, expected):
    """Reject path escapes and symlinks instead of following arbitrary evidence."""
    require(isinstance(relative, str) and relative and
            not PurePosixPath(relative).is_absolute() and
            '..' not in PurePosixPath(relative).parts, 'unsafe artifact path: ' + str(relative))
    require(isinstance(expected, str) and SHA.fullmatch(expected), 'invalid SHA: ' + relative)
    path = root / relative
    require(path.is_file() and not path.is_symlink() and root.resolve() in path.resolve().parents,
            'missing/unsafe artifact: ' + str(path))
    require(digest(path) == expected, 'artifact SHA differs: ' + str(path))
    return path


def record(log, marker, fields, integers=True):
    lines = re.findall(r'^' + re.escape(marker) + r'\b.*$', log, re.M)
    require(len(lines) == 1, 'missing/duplicate ' + marker)
    result = {}
    for token in lines[0].split()[1:]:
        require(token.count('=') == 1, 'malformed ' + marker)
        key, value = token.split('=', 1)
        require(key not in result, 'duplicate field in ' + marker)
        if integers:
            require(re.fullmatch(r'\d+', value) is not None, 'noninteger ' + marker + '.' + key)
            value = int(value)
        result[key] = value
    require(set(result) == set(fields), 'fields differ in ' + marker)
    return result


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid ' + name)
    return value


def normalized_command(command, out, repo):
    require(isinstance(command, list) and command and all(isinstance(x, str) for x in command),
            'invalid saved command')
    # Replace longer prefixes first when a campaign lives inside its repository.
    replacements = sorted([(str(out), '@CAMPAIGN@'), (str(repo), '@REPO@')],
                          key=lambda row: len(row[0]), reverse=True)
    result = []
    for value in command:
        for old, new in replacements:
            value = value.replace(old, new)
        result.append(value)
    return result


def clock_configuration(profile):
    require(profile in ('development', '150mhz'), 'unknown platform clock profile')
    requested = {'hf': '3.333333333', 'lf': '15258.7890625'} if profile == '150mhz' else {'hf': '2', 'lf': '33'}
    result = dict(profile=profile, requested_half_period_ns=requested,
                  scope='testbench clock stimulus, not STA or mapped-clock qualification')
    if profile == 'development':
        result['timescale'] = 'historical tool/source inheritance; unchanged'
    else:
        result['timescale'] = '1ns/1fs'
        result['quantized_expected'] = {}
        for domain, value in requested.items():
            half_fs = int((Decimal(value) * 1000000).to_integral_value(rounding=ROUND_HALF_UP))
            result['quantized_expected'][domain] = dict(half_period_fs=half_fs,
                period_fs=2 * half_fs, frequency_hz=str(Decimal(10) ** 15 / (2 * half_fs)))
    return result


def clock_records(log, configuration):
    require(configuration == clock_configuration(configuration['profile']), 'platform clock configuration differs')
    lines = re.findall(r'^S3_CLOCK_PROFILE\b.*$', log, re.M)
    if configuration['profile'] == 'development':
        require(not lines, 'unexpected clock observations in development profile')
        return []
    matches = re.findall(r'^S3_CLOCK_PROFILE domain=(hf|lf) requested_half_ns=([0-9.]+) '
        r'measured_half_ns=([0-9.]+) period_ns=([0-9.]+) frequency_hz=([0-9.]+) precision_fs=1$', log, re.M)
    require(len(lines) == len(matches) == 2 and {row[0] for row in matches} == {'hf', 'lf'},
            'missing, duplicate or malformed measured clocks')
    result = []
    for domain, requested, half, period, frequency in matches:
        expected = configuration['quantized_expected'][domain]
        require(requested == configuration['requested_half_period_ns'][domain] and
                Decimal(half) * 1000000 == expected['half_period_fs'] and
                Decimal(period) * 1000000 == expected['period_fs'] and
                abs(Decimal(frequency) - Decimal(expected['frequency_hz'])) <= Decimal('0.00001'),
                'actual platform clock rounding/frequency differs')
        result.append(dict(domain=domain, requested_half_period_ns=requested,
                           measured_half_period_ns=half, measured_period_ns=period,
                           measured_frequency_hz=frequency, precision_fs=1))
    return result


def startup_records(log, profile):
    """Recheck reset observations, retaining absolute times as measurements."""
    lines = re.findall(r'^S3_STARTUP_PROFILE\b.*$', log, re.M)
    if profile == 'historical':
        require(not lines, 'unexpected external-reset startup records in historical profile')
        return []
    patterns = [r'event=second_assert time_ns=([0-9.]+) cpu_reset_n=1',
                r'event=second_release time_ns=([0-9.]+) held_ns=([0-9.]+) cpu_reset_n=0',
                r'event=measurement_begin time_ns=([0-9.]+) external_reset_n=1 cycle=0']
    matches = [re.fullmatch('S3_STARTUP_PROFILE ' + pattern, line)
               for pattern, line in zip(patterns, lines)]
    require(len(lines) == len(matches) == 3 and all(matches),
            'missing, unordered, duplicate or malformed external-reset startup observations')
    asserted, released, begin = (Decimal(row.group(1)) for row in matches)
    held = Decimal(matches[1].group(2))
    require(asserted > 0 and held >= 120 and released - asserted == held and begin == released,
            'startup reset observation interval differs')
    return [dict(item.split('=', 1) for item in line.split()[1:]) for line in lines]


def startup_signature(observations):
    """Compare event/reset semantics; absolute event times are not conditions."""
    result = []
    for observation in observations:
        signature = {key: value for key, value in observation.items() if key != 'time_ns'}
        if 'held_ns' in signature:
            signature['held_ns'] = str(Decimal(signature['held_ns']).normalize())
        result.append(signature)
    return result


def load_campaign(path, physical_pes=8):
    require(physical_pes in (8, 16), 'physical PE profile must be exactly 8 or 16')
    physical_fires, physical_groups = {8: (202752, 3168), 16: (101376, 1584)}[physical_pes]
    path = Path(path).resolve()
    report, plan = read_json(path), read_json(path.parent / 'plan.json')
    root = path.parent
    require(report.get('status') == PASS, 'campaign has not passed: ' + str(path))
    require(report.get('source_drift') == [], 'source drift is missing/nonempty')
    args = plan['arguments']
    # The artifact folder may have been moved after the run. Saved commands use
    # the original path, while file integrity is checked under the current root.
    old_out, repo = Path(args['out']), Path(args['repo'])
    require(old_out.is_absolute() and repo.is_absolute(), 'nonabsolute saved campaign/repository')
    schedule = report['configuration']['schedule']
    require(schedule in (SCHEDULE, READ_POP_SCHEDULE, DIRECT_SCHEDULE),
            'requires a supported Y32 packed16 NICE schedule')
    read_pop = schedule == READ_POP_SCHEDULE
    direct = schedule == DIRECT_SCHEDULE
    for key in ('configuration', 'bias_kind', 'original_layers', 'clock_configuration',
                'platform_assertions', 'chisel_procedural_assertions', 'original_source_sha256'):
        require(report[key] == plan[key], 'plan/result differ: ' + key)
    require(report.get('simulator_evidence') == plan.get('simulator_evidence'),
            'plan/result differ: simulator_evidence')
    require(report.get('startup_configuration') == plan.get('startup_configuration'),
            'plan/result differ: startup_configuration')
    startup_profile = args.get('startup_profile', 'historical')
    require(startup_profile in ('historical', 'external-reset'), 'unknown startup profile')
    startup = report.get('startup_configuration')
    if startup is None:
        require(startup_profile == 'historical', 'nonhistorical startup lacks configuration')
        startup = copy.deepcopy(HISTORICAL_STARTUP)
    else:
        require(startup == (HISTORICAL_STARTUP if startup_profile == 'historical' else EXTERNAL_RESET_STARTUP),
                'startup arguments/profile/seam version disagree')
    require(startup_profile != 'external-reset' or args['simulator'] == 'verilator',
            'external-reset startup requires the explicit Verilator profile')
    require(report['configuration']['schedule'] == args['schedule'] and
            report['bias_kind'] == args['bias_kind'] and
            report['clock_configuration']['profile'] == args['platform_clocks'] and
            args['simulator'] == plan['simulator'], 'plan arguments disagree with report')
    require(report['bias_kind'] in ('sram', 'registers'), 'unknown bias kind')
    require(report['chisel_procedural_assertions'] == 'retained', 'procedural assertions omitted')
    layers = report['original_layers']
    require(isinstance(layers, list) and layers and len(set(layers)) == len(layers) and
            all(type(x) is int and 0 <= x < 12 for x in layers), 'invalid layer selection')
    require(args['layers'] == ','.join(map(str, layers)), 'layer arguments disagree')
    require([row['original_layer'] for row in report['task_results']] == layers,
            'task layer coverage/order differs')

    sources = report['original_source_sha256']
    require(isinstance(sources, dict) and sources, 'empty source identity')
    for relative, expected in sources.items():
        artifact(root / 'source', relative, expected)
    require(report['clock_configuration'] == clock_configuration(args['platform_clocks']),
            'platform clock configuration differs')
    recipe_path = root / 'clear-recipe.json'
    require(recipe_path.is_file() and not recipe_path.is_symlink(), 'missing/unsafe clear recipe')
    recipe = read_json(recipe_path)
    require(recipe['frozen_main_sha256'] == sources['tests/e203/firmware/main.c'] and
            recipe['helper_sha256'] == sources['tools/ppa/s3_task_clear_protocol.py'],
            'clear recipe main/helper identity differs from source pins')
    require(recipe['tasks_per_process'] == 1 and recipe['reset'] == 'fresh native process' and
            recipe['policy'] == report['cache_policy'] and
            recipe['fifo_payload_physical_zero'] == report['fifo_payload_physical_zero'],
            'clear recipe process/reset/policy differs')
    generated_c = artifact(root, 's3_clear_main.c', recipe['generated_c_sha256'])
    clear_c_identity = generated_clear_c_identity(generated_c, old_out)
    artifact(root, 'tb.sv', recipe['generated_tb_sha256'])
    filelist_path = root / 'rtl.f'
    require(filelist_path.is_file() and not filelist_path.is_symlink(), 'missing/unsafe RTL filelist')
    expected_rtl = [str(old_out / 'source' / relative) for relative in sorted(sources)
                    if relative.startswith('rtl/') and Path(relative).suffix in ('.v', '.sv')]
    expected_rtl.append(str(old_out / 'tb.sv'))
    require(filelist_path.read_text().splitlines() == expected_rtl,
            'RTL filelist differs from complete pinned RTL plus generated testbench')
    for key in ('firmware_elf_sha256', 'firmware_image_sha256', 'simulator_sha256'):
        require(isinstance(report.get(key), str) and SHA.fullmatch(report[key]), 'missing ' + key)
    elf = artifact(root, 'accel_soc', report['firmware_elf_sha256'])
    loaded_elf = loaded_elf_identity(elf)
    artifact(root, 'accel_soc.verilog', report['firmware_image_sha256'])
    sim_step = next((step for step in report['steps'] if step['name'] == 'simulator-build'), None)
    require(sim_step is not None, 'missing simulator build step')
    # Simulator executables differ by backend; identify the saved run program.
    first_run = next((step for step in report['steps'] if step['name'].endswith('/simulation')), None)
    require(first_run is not None, 'missing simulation step')
    binary = first_run['command'][1] if args['simulator'] == 'iverilog' else first_run['command'][0]
    require(Path(binary).is_relative_to(old_out), 'simulator executable outside campaign')
    artifact(root, str(Path(binary).relative_to(old_out)), report['simulator_sha256'])

    steps, logs, observed_versions = [], {}, {}
    for step in report['steps']:
        name = step['name']
        require(name not in logs and step['native_exit'] == 0 and step['waitpid_completed'] is True,
                'duplicate/failed/incomplete native step: ' + name)
        logpath = artifact(root, name + '.log', step['log_sha256'])
        raw = logpath.read_text(errors='replace')
        command, separator, output = raw.partition('\n')
        require(separator and json.loads(command) == step['command'], 'log command differs: ' + name)
        logs[name] = output
        if name.startswith('version-'):
            tool = step['command'][0]
            require(tool not in observed_versions, 'duplicate tool version step: ' + tool)
            observed_versions[tool] = output
        if 'command_sha256' in step:
            require(step['command_sha256'] == hashlib.sha256(
                json.dumps(step['command'], separators=(',', ':')).encode()).hexdigest(),
                'saved command hash differs: ' + name)
        inferred_cwd = old_out / Path(name).parent if name.endswith('/simulation') else old_out
        cwd = step.get('cwd', str(inferred_cwd))
        require(isinstance(cwd, str) and Path(cwd).is_absolute(), 'invalid saved step cwd')
        steps.append(dict(name=name, command=normalized_command(step['command'], old_out, repo),
                          cwd=normalized_command([cwd], old_out, repo)[0]))
    expected_tasks = {'task-%02d/simulation' % layer for layer in layers}
    require({name for name in logs if name.endswith('/simulation')} == expected_tasks,
            'simulation step coverage differs')
    if direct:
        require(sum(step['name'] == 'firmware-build' for step in steps) == 1,
                'direct firmware requires one saved firmware-build step')
    for step in steps:
        if read_pop and step['name'].endswith('/simulation'):
            require([arg for arg in step['command'] if arg.startswith('+NICE_READ_POP')] == ['+NICE_READ_POP=1'],
                    'read-pop run lacks its exact runtime selector')
        if direct:
            command = step['command']
            selectors = [arg for arg in command if arg.startswith(('+NICE_DIRECT', '+NICE_READ_POP'))]
            require(selectors == (['+NICE_DIRECT=1'] if step['name'].endswith('/simulation') else []),
                    'direct run lacks its exact exclusive runtime selector')
            macros = [arg for arg in command if arg.startswith('-DXU_NICE_DIRECT')]
            require(macros == (['-DXU_NICE_DIRECT=1'] if step['name'] == 'firmware-build' else []),
                    'direct firmware build lacks its exact compiler macro')
    require(isinstance(report.get('versions'), dict) and report['versions'], 'missing tool versions')
    require(report['versions'] == observed_versions, 'saved/raw tool versions differ')

    rows = []
    for task in report['task_results']:
        layer = task['original_layer']
        require(task['native_layer'] == 0, 'not a fresh single task mapping')
        log = logs['task-%02d/simulation' % layer]
        observed_startup = startup_records(log, startup_profile)
        require(task.get('startup_observations', []) == observed_startup,
                'saved/raw startup observations differ')
        require(task['measured_clocks'] == clock_records(log, report['clock_configuration']),
                'saved/raw measured clocks differ')
        require(not re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout|^Error(?:\s|:)', log, re.I | re.M),
                'failure in raw simulation log')
        cycles = integer(task['cycles'], 'payload_cycles', 1)
        passes = re.findall(r'^TASK_PASS layer=0 outputs=25344 writes=25344 cycles=(\d+) '
                            r'firmware_cycles=(\d+)$', log, re.M)
        require(len(passes) == 1 and int(passes[0][0]) == cycles and
                re.findall(r'^SOC_PASS\b.*$', log, re.M) == ['SOC_PASS tasks=1 outputs=25344 writes=25344'],
                'complete numerical task markers missing or inconsistent')
        performance = record(log, 'PERF_TASK', ('layer', 'cycles', *PERFORMANCE))
        require(performance.pop('layer') == 0 and performance.pop('cycles') == cycles and
                performance == task['performance'], 'saved/raw performance differs')
        require(sum(performance[key] for key in PHASES) == cycles, 'phase sum differs')
        require(all(value <= cycles for value in performance.values()) and
                performance['mac_fire'] <= performance['busy'] <= cycles,
                'performance counter/busy bounds differ')
        for key, expected in dict(mac_fire=physical_fires, starts=physical_groups, dones=physical_groups,
                                  shared_reads=15040, shared_writes=25344).items():
            require(performance[key] == expected, 'performance work count differs: ' + key)
        nice = record(log, 'NICE_TASK', ('layer', *NICE))
        require(nice == task['nice_activity'] and nice.pop('layer') == 0, 'saved/raw NICE differs')
        for key, expected in dict(requests=3168, responses=3168, oitf_retired=3168,
                                  result_reads=0 if direct else 25344,
                                  pops_retired=3168, shared_writes=25344).items():
            require(nice[key] == expected, 'NICE protocol count differs: ' + key)
        require(nice['status_polls'] >= 3168, 'NICE status coverage incomplete')
        if direct:
            require(performance['mmio_reads'] == nice['status_polls'] + 2,
                    'direct MMIO reads differ from status polls plus Y32/DIRECT capability probes')
            transport_record = record(log, 'DIRECT_TASK',
                ('layer', 'snapshots', 'lanes', 'pops_retired', 'result_mmio_reads'))
            require(transport_record == dict(layer=0, snapshots=3168, lanes=25344,
                    pops_retired=3168, result_mmio_reads=0), 'direct transaction coverage differs')
            if 'direct_activity' in task:
                require(task['direct_activity'] == transport_record, 'saved/raw direct activity differs')
            require(not re.search(r'^READ_POP_TASK\b', log, re.M), 'unexpected read-pop activity in direct schedule')
            transport = dict(alias_reads=0, explicit_pops=0,
                direct_snapshots=transport_record['snapshots'], direct_lanes=transport_record['lanes'],
                direct_pops=transport_record['pops_retired'], result_mmio_reads=transport_record['result_mmio_reads'])
        else:
            require(performance['mmio_reads'] >= nice['status_polls'] + nice['result_reads'] + 1,
                    'MMIO reads omit NICE work or the in-window Y32 capability read')
            require(not re.search(r'^DIRECT_TASK\b', log, re.M), 'unexpected direct activity in old schedule')
        if read_pop:
            transport_record = record(log, 'READ_POP_TASK', ('layer', 'alias_reads', 'explicit_pops'))
            require(transport_record == dict(layer=0, alias_reads=3168, explicit_pops=0),
                    'read-pop transaction coverage differs')
            if 'read_pop_activity' in task:
                require(task['read_pop_activity'] == transport_record, 'saved/raw read-pop activity differs')
            transport = {key: value for key, value in transport_record.items() if key != 'layer'}
        elif not direct:
            require(not re.search(r'^READ_POP_TASK\b', log, re.M), 'unexpected read-pop activity in old schedule')
            # The old observer checks explicit POP order before counting this
            # NICE retirement; no alias transactions belong to that transport.
            transport = dict(alias_reads=0, explicit_pops=nice['pops_retired'])
        require(performance['mmio_writes'] == (12330 if direct else 12329 if read_pop else 15497),
                'MMIO transaction count differs from selected transport')
        auto = record(log, 'AUTO_TASK', ('layer', *AUTO))
        require(auto.pop('layer') == 0 and auto['rows'] == 99 and auto['pops_retired'] == 3168 and
                0 < auto['compute_writeback_overlap'] <= cycles and
                0 <= auto['fifo_full_wait'] <= cycles, 'autonomous activity differs')
        window = record(log, 'WINDOW_TASK', ('layer', *WINDOW))
        require(window == task['window'] and window.pop('layer') == 0, 'saved/raw window differs')
        require(window['final_y_response'] - window['first_request'] + 1 == cycles and
                window['first_accept'] - window['first_request'] == window['first_request_wait'] and
                window['first_request_wait'] >= args['first_source_stall'], 'request window differs')
        clear = task['clear']
        require(record(log, 'S3_TASK_CLEAR_OBSERVED', clear, integers=False) == clear,
                'saved/raw clear differs')
        clear_cycles = integer(int(clear['clear_cycles']), 'clear_cycles', 1)
        gap = integer(int(clear['gap_to_source_request']), 'clear_to_source_gap', 1)
        arm = record(log, 'S3_CLEAR_OBSERVER_ARM', ('cycle', 'actual_accel_reset_n'))
        require(arm['actual_accel_reset_n'] == 1 and
                arm['cycle'] + int(clear['response_end_cycle']) + gap - 1 == window['first_request'] and
                clear_cycles <= int(clear['response_end_cycle']),
                'clear observer local/global timing relation differs')
        require(clear['commands'] == clear['responses'] and clear['nice_idle'] == '1' and
                int(clear['mode_sram']) == int(report['bias_kind'] == 'sram') and
                int(clear['writes']) == (32930 if report['bias_kind'] == 'sram' else 33697),
                'clear protocol differs')
        # Check the exact remapped tensors/profile, plus exporter/model identity.
        vectors = task['vectors']
        required_vectors = {'profile.json', *('layer_00/' + name + '.mem' for name in
                            ('x', 'w', 'bias', 'y', 'y32', 'w_packed16'))}
        require(isinstance(vectors, dict) and required_vectors <= set(vectors),
                'missing vector identities')
        for relative, expected in vectors.items():
            artifact(root / ('task-%02d/vectors' % layer), relative, expected)
        if physical_pes == 16:
            physical = record(log, 'PE16_TASK', PE16_FIELDS)
            require(physical == dict(layer=0, pes=16, engines=2,
                physical_groups=1584, physical_mac_cycles=101376, logical_macs=1622016,
                lo_starts=1584, hi_starts=1584, lo_init=1584, hi_init=1584,
                lo_mac_fire=101376, hi_mac_fire=101376, lo_done=1584, hi_done=1584,
                checked_cycles=cycles, sync_errors=0), 'physical 16-PE work/control differs')
            require(task.get('pe16_activity') == physical, 'saved/raw physical 16-PE activity differs')
        else:
            require(not re.search(r'^PE16_TASK\b', log, re.M), 'baseline unexpectedly contains PE16 marker')
            require('pe16_activity' not in task, 'baseline claims PE16 activity')
            physical = dict(pes=8, engines=1, physical_groups=3168,
                physical_mac_cycles=202752, logical_macs=1622016,
                observation='legacy PERF_TASK counters; fixed 8-lane baseline source')
        rows.append(dict(original_layer=layer, payload_cycles=cycles, clear_cycles=clear_cycles,
                         physical=physical,
                         payload_plus_clear_cycles=cycles + clear_cycles,
                         clear_to_source_gap=gap,
                         phases={key: performance[key] for key in PHASES},
                         bus_counters={key: value for key, value in performance.items() if key not in PHASES},
                         nice=nice, auto=auto, transport=transport,
                         startup_observations=observed_startup,
                         window=window, clear=clear, measured_clocks=task['measured_clocks'],
                         vectors=vectors, vector_profile=task['vector_profile'],
                         profile_source_sha256=task['profile_source_sha256']))
    require(report['cycles'] == sum(row['payload_cycles'] for row in rows) and
            report['outputs'] == 25344 * len(rows), 'campaign totals differ')
    # Unknown arguments/identity fields remain visible and must match too.
    conditions = {key: value for key, value in args.items() if key not in ('repo', 'out')}
    conditions['startup_profile'] = startup_profile
    conditions['startup_configuration'] = startup
    conditions['clear_recipe_configuration'] = {key: recipe[key] for key in (
        'clear_counts', 'tasks_per_process', 'reset', 'policy', 'fifo_payload_physical_zero')}
    conditions.update({key: report.get(key) for key in (
        'configuration', 'bias_kind', 'original_layers', 'clock_configuration',
        'platform_assertions', 'chisel_procedural_assertions', 'simulator_evidence', 'versions', 'fixture',
        'integer_reference', 'activity_extension', 'cache_policy', 'fifo_payload_physical_zero')})
    conditions['commands'] = steps
    campaign = dict(result_path=str(path), result_sha256=digest(path), conditions=conditions,
                source_sha256=sources, firmware_elf_sha256=report['firmware_elf_sha256'],
                firmware_loaded_elf=loaded_elf,
                firmware_image_sha256=report['firmware_image_sha256'],
                simulator_sha256=report['simulator_sha256'],
                clear_recipe_sha256=digest(recipe_path), generated_tb_sha256=recipe['generated_tb_sha256'],
                generated_c_sha256=recipe['generated_c_sha256'], generated_clear_c_identity=clear_c_identity,
                rtl_filelist_sha256=digest(filelist_path), rows=rows,
                physical_pes=physical_pes,
                raw_log_sha256={step['name']: step['log_sha256'] for step in report['steps']})
    if direct:
        campaign['firmware_image_load_identity'] = verify_loaded_image(campaign)
    return campaign


PE16_FIELDS = ('layer', 'pes', 'engines', 'physical_groups', 'physical_mac_cycles',
    'logical_macs', 'lo_starts', 'hi_starts', 'lo_init', 'hi_init', 'lo_mac_fire',
    'hi_mac_fire', 'lo_done', 'hi_done', 'checked_cycles', 'sync_errors')

# Reviewed frozen snapshot pairs. Additions are explicit; no deleted source or
# other source change is permitted. Firmware, buses, CPU controls and memory
# configuration are outside this whitelist and must remain byte-identical.
EXPECTED_SOURCE_CHANGES = {
    'campaign.py': (
        '622a6b34e16e923aef5ddd5cf0bcd3e455fad0094c83df560fc397f1d89fcaaa',
        '951980c768505bfb225a576cde585b83461caf4d49f4d4d4570df7ebef8dd7c6'),
    'rtl/perips/LinearAutoGroupCore.sv': (
        'ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4',
        '17b950a5be0c34f28758e265d425841a97e474cb413a820ccda0f9932ab22542'),
    'rtl/perips/PairComputeCore.sv': (
        None,
        '4cf41e661b6c18f5ff848069b62e36c905e9ea90ccc120ca4093483644c4b24c'),
    'tests/e203/tb_accel_soc.sv': (
        'cb3ed917542acdc16934380388480b8ae97b0478cb884138d98f5f028c149b0d',
        'c74e40d08a9f20d2f9c466b9bd62dee80e16cc19fac05d26fb9cc8b099b13e80'),
    'tools/scripts/e203_soc.py': (
        '03afff21bc9935dc29e55473f98a686154c62c3d4a8aa84fdbdbefc370dfcab8',
        'a75df19bfa71ca268ea714118c05ca825796a79b2556071d928f4b82e0fd71b1'),
    'tools/scripts/xu_firmware_contract.py': (
        '5032da5cbc605877db8ebeb053198fdc763385585a35699857382fc2f15ad719',
        'eae891fa9878d72b0b98f5e4f31aec4940eb2930313abf870d2439332f575b76'),
}
SOURCE_CHANGE_REASONS = {
    'campaign.py': 'Save the already mandatory PE16_TASK record in per-layer JSON.',
    'rtl/perips/LinearAutoGroupCore.sv': 'Compute two adjacent groups in parallel, then publish the original eight-lane groups.',
    'rtl/perips/PairComputeCore.sv': 'New physical pair of eight-lane engines and split even/odd weight storage.',
    'tests/e203/tb_accel_soc.sv': 'Independently observe both physical engine controls and retain all external checks.',
    'tools/scripts/e203_soc.py': 'Require and save exact physical 16-PE activity; retain original parser checks.',
    'tools/scripts/xu_firmware_contract.py': 'Explicit pes=16, 1584 physical groups and 101376 MAC cycles; same firmware defines.',
}


def totals(rows):
    keys = ('payload_cycles', 'clear_cycles', 'payload_plus_clear_cycles', 'clear_to_source_gap')
    result = {key: sum(row[key] for row in rows) for key in keys}
    for category in ('phases', 'bus_counters', 'nice', 'auto', 'transport'):
        result[category] = {key: sum(row[category][key] for row in rows) for key in rows[0][category]}
    return result


def differences(before, after):
    return {key: differences(value, after[key]) if isinstance(value, dict) else after[key] - value
            for key, value in before.items()}


def compare_pe16(base, candidate):
    require(base['physical_pes'] == 8 and candidate['physical_pes'] == 16,
            'requires explicit directed 8-PE to 16-PE profiles')
    require(base['conditions']['original_layers'] == candidate['conditions']['original_layers'] == [0],
            'this low-cost experiment requires exactly original layer 0')
    require(base['conditions']['configuration']['schedule'] == DIRECT_SCHEDULE and
            candidate['conditions']['configuration']['schedule'] == DIRECT_SCHEDULE,
            'requires unchanged NICE direct schedule')
    require(base['conditions'] == candidate['conditions'],
            'conditions differ: inputs, tools, clocks, startup, clear recipe, assertions, argv or macros')
    bsource, csource = base['source_sha256'], candidate['source_sha256']
    observed = {key: (bsource.get(key), csource.get(key)) for key in set(bsource) | set(csource)
                if bsource.get(key) != csource.get(key)}
    require(observed == EXPECTED_SOURCE_CHANGES,
            'source change/addition differs from the exact reviewed physical-PE whitelist')
    require(base['generated_clear_c_identity'] == candidate['generated_clear_c_identity'],
            'generated clear C differs beyond the frozen-main include path')
    require(base['firmware_image_sha256'] == candidate['firmware_image_sha256'] and
            base['firmware_loaded_elf'] == candidate['firmware_loaded_elf'],
            'loaded firmware/image differs; this experiment permits no firmware change')
    loaded_checks = dict(baseline=verify_loaded_image(base), candidate=verify_loaded_image(candidate))
    before, after = base['rows'][0], candidate['rows'][0]
    require(before['original_layer'] == after['original_layer'] == 0, 'layer pairing differs')
    for key in ('vectors', 'vector_profile', 'profile_source_sha256', 'measured_clocks'):
        require(before[key] == after[key], 'task input/clock differs: '+key)
    require(startup_signature(before['startup_observations']) ==
            startup_signature(after['startup_observations']), 'startup/reset semantics differ')
    timing = {'clear_cycles', 'response_end_cycle', 'gap_to_source_request'}
    require({k: v for k, v in before['clear'].items() if k not in timing} ==
            {k: v for k, v in after['clear'].items() if k not in timing}, 'physical clear work differs')
    b, a = totals([before]), totals([after])
    change = differences(b, a)
    return dict(schema='s3-pe16-single-layer-comparison-v1',
        status='EXPLICIT_PE16_SAVED_EVIDENCE_COMPARED',
        production_reporter_status='NOT_APPLICABLE_8PE_REPORTER_WAS_NOT_USED',
        scope='saved fresh-process CPU/RTL evidence, original layer 0 only; no new simulation',
        metric='payload request-to-final-Y-response plus separately observed physical clear cycles',
        delta_convention='candidate minus baseline; negative cycles are an improvement',
        improvement_percent={key: str((Decimal(b[key]-a[key])*100/b[key]).quantize(Decimal('0.000001')))
            for key in ('payload_cycles', 'payload_plus_clear_cycles')},
        gap_semantics='clear-to-source gap is reported separately and excluded from the main metric',
        overlap_semantics='FIFO full wait and compute/writeback overlap overlap phase counters; do not add them',
        identity_checks=dict(conditions_equal=True, normalized_argv_equal=True, macros_equal=True,
            vectors_equal=True, clocks_equal=True, startup_semantics_equal=True, clear_work_equal=True,
            loaded_image_equal=True, elf_load_contract_equal=True,
            raw_elf_sha256_equal=base['firmware_elf_sha256']==candidate['firmware_elf_sha256'],
            nonloaded_elf_metadata_may_differ=base['firmware_elf_sha256']!=candidate['firmware_elf_sha256'],
            independent_image_load_verification=loaded_checks),
        source_changes={key: dict(baseline_sha256=pair[0], candidate_sha256=pair[1],
            reason=SOURCE_CHANGE_REASONS[key]) for key, pair in sorted(observed.items())},
        physical=dict(baseline=before['physical'], candidate=after['physical']),
        totals=dict(baseline=b, candidate=a, delta=change),
        windows=dict(baseline=before['window'], candidate=after['window']),
        startup_observations=dict(baseline=before['startup_observations'], candidate=after['startup_observations']),
        baseline_identity={k: v for k, v in base.items() if k != 'rows'},
        candidate_identity={k: v for k, v in candidate.items() if k != 'rows'},
        limitations=['One original layer; no full12 scaling claim.',
            'Verilator 2-state development evidence; vendor SVA disabled, Chisel procedural assertions retained with --assert.',
            'No synthesis, mapped area, power, STA, gate-level or official qualification evidence.',
            'Saved hashes establish local artifact consistency, not an independent authenticity attestation.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument('baseline', nargs='?', type=Path,
        default=here.parent/'writeback-v2-20261108/direct-task0-phase/result.json')
    parser.add_argument('candidate', nargs='?', type=Path, default=here/'pe16-task0/result.json')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare_pe16(load_campaign(args.baseline, 8), load_campaign(args.candidate, 16))
        if args.out:
            with args.out.open('x') as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
                stream.write('\n')
        values = result['totals']
        print('PE16_SAVED_EVIDENCE_COMPARED')
        for key in ('payload_cycles', 'clear_cycles', 'payload_plus_clear_cycles', 'clear_to_source_gap'):
            print(key, values['baseline'][key], values['candidate'][key], values['delta'][key])
        print('improvement_percent', json.dumps(result['improvement_percent'], sort_keys=True))
        if args.out:
            print('saved', args.out.resolve())
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print('PE16_COMPARISON_REJECTED:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

