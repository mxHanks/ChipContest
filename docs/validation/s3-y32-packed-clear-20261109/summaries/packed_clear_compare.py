#!/usr/bin/env python3
"""Read-only strict READY scalar -> READY packed-MMIO clear comparison.

Based on the production writeback verifier. All artifact, source, binary, log,
command, clock/reset, clear, numerical-marker and image checks are retained.
Only the fixed eight-PE READY payload, scalar baseline and packed clear are accepted.
Exact reviewed SHA pairs must be supplied; no simulation or source edit occurs.
"""

import argparse
import copy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import importlib.util


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


def load_verified_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def function_bytes(path,names):
    import ast
    text=path.read_text()
    tree=ast.parse(text)
    found={node.name:ast.get_source_segment(text,node)
           for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names}
    require(set(found)==set(names), 'generation seam function missing')
    return found


def verify_clear_generation(root,old_out,sources,profile,recipe,generated_c,generated_tb,args):
    """Recreate C and TB exactly from pinned helper, original main and old seam.

    C changes are explicitly allowed only through this selected helper. The
    generated C is never equated across algorithms by erasing/replacing code.
    The one path normalization is the exact frozen-main include. TB regeneration
    uses the unchanged scalar campaign's exact instrument_tb/clock/reset seam.
    """
    helper_path=artifact(root/'source',profile['helper'],sources[profile['helper']])
    helper=load_verified_module('packed_clear_pinned_helper',helper_path)
    require(recipe['clear_counts']==helper.CLEAR_COUNTS, 'clear count recipe differs from pinned helper')
    frozen_main=artifact(root/'source','tests/e203/firmware/main.c',sources['tests/e203/firmware/main.c'])
    reconstructed=helper.firmware_wrapper(frozen_main,sources['tests/e203/firmware/main.c']).encode()
    current_include=('#include "'+str(frozen_main.resolve())+'"').encode()
    old_include=('#include "'+str(old_out/'source/tests/e203/firmware/main.c')+'"').encode()
    require(reconstructed.count(current_include)==1, 'reconstructed main include is not exact/unique')
    reconstructed=reconstructed.replace(current_include,old_include,1)
    require(generated_c.read_bytes()==reconstructed, 'generated clear C differs from exact selected helper regeneration')
    campaign_path=artifact(root/'source','campaign.py',sources['campaign.py'])
    baseline_seams=Path(__file__).resolve().parent/'baseline-campaign-seams.json'
    require(baseline_seams.is_file() and not baseline_seams.is_symlink() and digest(baseline_seams)=='da526d089ed85dd254b0b6d3dd84b5ea26c6085c0143ae1d21dd4361c5e6abaa', 'missing/different independent baseline campaign seam pins')
    frozen_seams=read_json(baseline_seams)
    # These literal functions were extracted from BASELINE_CAMPAIGN_SHA and are
    # data, not candidate claims. Generated payload text must match byte-for-byte.
    seam_names=('instrument_tb','apply_platform_clocks','apply_startup_profile',
                'clock_configuration','startup_configuration')
    require(function_bytes(campaign_path,seam_names)==frozen_seams, 'candidate campaign generation seam differs')
    # Execute the independently pinned baseline seam literals, never candidate
    # campaign code. Their globals are the fixed standard-library dependencies.
    seam_namespace={'Decimal':Decimal,'ROUND_HALF_UP':ROUND_HALF_UP,'re':re}
    exec('\n\n'.join(frozen_seams[name] for name in seam_names),seam_namespace)
    original_tb=artifact(root/'source','tests/e203/tb_accel_soc.sv',sources['tests/e203/tb_accel_soc.sv'])
    observer=(helper.observer_declarations(use_bias_sram=args['bias_kind']=='sram')
              if profile['clear_profile']=='packed16-mmio' else helper.observer_declarations())
    observer_path=root/'s3_clear_observer.svh'
    require(observer_path.is_file() and not observer_path.is_symlink() and
            observer_path.read_bytes()==observer.encode(), 'saved clear observer differs from exact selected helper')
    expected_tb=seam_namespace['instrument_tb'](original_tb.read_text(),observer,args['platform_clocks'],args.get('startup_profile','historical'))
    require(generated_tb.read_bytes()==expected_tb.encode(), 'generated TB differs from exact old payload seams and selected preclear observer')
    return dict(verified=True,selected_helper=profile['helper'],helper_sha256=sources[profile['helper']],
        generated_c_exactly_regenerated=True,generated_tb_exactly_regenerated=True,
        original_payload_observer_sha256=sources['tests/e203/tb_accel_soc.sv'],
        generated_c_normalization='only exact frozen-main snapshot include path for relocation',
        pinned_campaign_seams_sha256=digest(baseline_seams))


SCALAR_CLEAR_FIELDS=frozenset(('mode_sram','writes','w','x','legacy_bias','bias_entries',
    'sram_clear_commands','sram_done','commands','responses','clear_cycles','response_end_cycle',
    'gap_to_source_request','preflight_commands','preflight_responses','nice_idle',
    'fifo_payload_physical_zero','policy'))
PACKED_EXTRA_FIELDS=frozenset(('reads','physical_w','physical_x','physical_bias','w_packs','x_packs','clear_transport'))


def validate_clear_marker(clear,clear_profile,bias_kind):
    packed=clear_profile=='packed16-mmio'
    sram=bias_kind=='sram'
    require(set(clear)==SCALAR_CLEAR_FIELDS|(PACKED_EXTRA_FIELDS if packed else frozenset()), 'clear marker fields differ')
    expected=dict(mode_sram=str(int(sram)),w='16384',x='64',legacy_bias='8',bias_entries='0' if sram else '256',
        sram_clear_commands='1' if sram else '0',sram_done='1' if sram else '0',nice_idle='1',
        fifo_payload_physical_zero='UNPROVEN',policy='REVIEW_PENDING')
    writes=(8252 if sram else 9019) if packed else (32930 if sram else 33697)
    commands=writes+(8 if packed else 5)
    expected.update(writes=str(writes),commands=str(commands),responses=str(commands),
                    preflight_commands='6',preflight_responses='6')
    if packed:
        expected.update(reads='8',physical_w='16384',physical_x='64',physical_bias='768' if sram else '0',
                        w_packs='8192',x_packs='32',clear_transport='public-pack32')
    require(all(clear.get(key)==value for key,value in expected.items()), 'fixed clear protocol/physical-work/policy differs')
    for key in ('clear_cycles','response_end_cycle','gap_to_source_request'):
        require(re.fullmatch(r'[1-9][0-9]*',clear[key]) is not None, 'invalid clear marker timing: '+key)



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



VERIFIER_ORIGIN_SHA256 = '8ef9a679422c06437a6c64ffbe35527f6a39b72af621e09fcb15c47b08c43336'
BASELINE_RESULT_SHA256 = '0e57d26b7493cfc8a98846346bb5183b5d6132d089000782972adfe199a58a28'
BASELINE_SOURCES_SHA256 = '72995228ff13f91112dc148c059dd873838a912e53a95f95b6857106d5f7f3f9'
BASELINE_SOURCE_COUNT = 170
BATCH_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-direct-batch16-window'
STREAM_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-direct-stream-window'
READY_SCHEDULE = 'bias-hw-autogroup-y32-packed16-nice-direct-stream-ready-window'
PROFILES = {
    name: dict(transport='ready32', schedule=READY_SCHEDULE,
        clear_profile=clear_profile, helper=helper,
        requests=99, extra_macro='-DXU_NICE_DRAINN=1', extra_selector='+NICE_STREAM=1',
        pes=8, groups=3168, fires=202752)
    for name,clear_profile,helper in (
        ('ready32-scalar','scalar','tools/ppa/s3_task_clear_protocol.py'),
        ('ready32-packed','packed16-mmio','tools/ppa/s3_task_packed_clear_protocol.py'))}
PE8_CORE_SHA = 'ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4'
NEW_HELPER = 'tools/ppa/s3_task_packed_clear_protocol.py'
ALLOWED_SOURCE_CHANGES = frozenset(('campaign.py', NEW_HELPER))
REQUIRED_SOURCE_CHANGES = ALLOWED_SOURCE_CHANGES
BASELINE_CAMPAIGN_SHA = '9d04abeb87ed1d0d8da1870f8faf2e11c9c116a9b5c3f63019ae818b380f0f2f'


def profile_arguments(profile, kind, step):
    if kind == 'selector':
        if not step.endswith('/simulation'):
            return []
        result = [profile['extra_selector']]
        return result + (['+NICE_READY=1'] if profile['transport']=='ready32' else [])
    if step != 'firmware-build':
        return []
    result = [profile['extra_macro']]
    return result + (['-DXU_NICE_READY=1'] if profile['transport']=='ready32' else [])


def load_pinned_parser(root, sources):
    """Import only the already rehashed, exactly source-pinned local parser pair."""
    def module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result
    contract_path = artifact(root/'source', 'tools/scripts/xu_firmware_contract.py',
                             sources['tools/scripts/xu_firmware_contract.py'])
    parser_path = artifact(root/'source', 'tools/scripts/e203_soc.py',
                           sources['tools/scripts/e203_soc.py'])
    saved_contract = sys.modules.get('xu_firmware_contract')
    try:
        contract = module('postflow_pinned_contract', contract_path)
        sys.modules['xu_firmware_contract'] = contract
        result = module('postflow_pinned_parser', parser_path)
    finally:
        if saved_contract is None:
            sys.modules.pop('xu_firmware_contract', None)
        else:
            sys.modules['xu_firmware_contract'] = saved_contract
    return result


def profile_markers(log, task, schedule, profile, parser):
    layers = [dict(layer=0,cycles=task['cycles'])]
    # The campaign's exact pinned parser provides an independent second check.
    parser.check_nice_activity(log,layers,schedule)
    parser.check_direct_activity(log,layers,schedule)
    marker_data = {}
    marker_specs = {
        'batch16': ('BATCH16_TASK', 'batch16_activity', 'check_batch16_activity',
            dict(layer=0,requests=1584,snapshots=3168,pops_retired=3168,
                 blocks_written=1584,lanes=25344,no_write_before_both_pops=1)),
        'stream32': ('STREAM_TASK', 'stream_activity', 'check_stream_activity',
            dict(layer=0,requests=99,groups=3168,snapshots=3168,pops_retired=3168,
                 shared_writes=25344,final_response_before_completion=1))}
    for transport, (marker, saved, checker, expected) in marker_specs.items():
        if profile['transport']==transport or (transport=='stream32' and profile['transport']=='ready32'):
            observed=record(log,marker,expected)
            require(observed==expected and task.get(saved)==observed, 'saved/raw exact '+marker+' differs')
            require(getattr(parser,checker)(log,layers,schedule)==[observed], 'pinned parser differs for '+marker)
            marker_data[saved]=observed
        else:
            require(not re.search(r'^'+marker+r'\b',log,re.M), 'unexpected '+marker)
            require(saved not in task, 'unexpected saved '+saved)
    if profile['transport']=='ready32':
        ready_fields=('layer','requests','groups','ready_edges','ready_wait_cycles',
            'status_polls','snapshots','pops_retired','shared_writes','final_response_before_completion')
        ready=record(log,'READY_TASK',ready_fields)
        expected=dict(layer=0,requests=99,groups=3168,ready_edges=3168,
            ready_wait_cycles=ready['ready_wait_cycles'],status_polls=0,snapshots=3168,
            pops_retired=3168,shared_writes=25344,final_response_before_completion=1)
        require(ready==expected and 3168<=ready['ready_wait_cycles']<=task['cycles'] and
                task.get('ready_activity')==ready, 'saved/raw exact READY_TASK differs')
        require(parser.check_ready_activity(log,layers,schedule)==[ready],
                'pinned parser differs for READY_TASK')
        marker_data['ready_activity']=ready
    else:
        require(not re.search(r'^READY_TASK\b',log,re.M) and 'ready_activity' not in task,
                'unexpected READY_TASK/activity in legacy stream profile')
    if profile['pes']==16:
        fields=('layer','pes','engines','physical_groups','physical_mac_cycles','logical_macs',
            'lo_starts','hi_starts','lo_init','hi_init','lo_mac_fire','hi_mac_fire',
            'lo_done','hi_done','checked_cycles','sync_errors')
        expected=dict(layer=0,pes=16,engines=2,physical_groups=1584,
            physical_mac_cycles=101376,logical_macs=1622016,
            lo_starts=1584,hi_starts=1584,lo_init=1584,hi_init=1584,
            lo_mac_fire=101376,hi_mac_fire=101376,lo_done=1584,hi_done=1584,
            checked_cycles=task['cycles'],sync_errors=0)
        physical=record(log,'PE16_TASK',fields)
        require(physical==expected and task.get('pe16_activity')==physical,
                'saved/raw physical 16-PE work differs')
        require(parser.check_pe16_activity(log,layers,schedule)==[physical],
                'pinned physical 16-PE parser differs')
        require(not re.search(r'^PE8_TASK\b',log,re.M), 'unexpected PE8 marker')
    else:
        require(not re.search(r'^PE16_TASK\b',log,re.M) and 'pe16_activity' not in task,
                'unexpected physical 16-PE marker/activity in 8-PE profile')
        physical=dict(pes=8,physical_groups=3168,physical_mac_cycles=202752,logical_macs=1622016)
        if re.search(r'^PE8_TASK\b',log,re.M):
            observed=record(log,'PE8_TASK',('layer',*physical,'checked_cycles'))
            require(observed==dict(layer=0,**physical,checked_cycles=task['cycles']) and
                    task.get('pe8_activity')==observed,'saved/raw physical eight-PE marker differs')
            require(parser.check_pe8_activity(log,layers,schedule)==[observed], 'pinned PE8 parser differs')
            physical=observed
        else:
            require('pe8_activity' not in task, 'saved PE8 activity lacks raw marker')
            physical['observation']='fixed original 8-PE core SHA plus exact PERF work counters'
    return dict(physical=physical,additional_markers=marker_data)


def load_campaign(path, profile_name, source_pins):
    require(profile_name in PROFILES, "unknown explicit postflow profile")
    profile = PROFILES[profile_name]
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
    require(schedule == profile['schedule'], 'schedule differs from explicit profile')
    read_pop = False
    direct = True
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
    require(sources == source_pins, 'source manifest differs from externally pinned exact source SHA map')
    for relative, expected in sources.items():
        artifact(root / 'source', relative, expected)
    parser_api = load_pinned_parser(root, sources)
    require(sources.get('rtl/perips/LinearAutoGroupCore.sv') ==
            (PE8_CORE_SHA if profile['pes']==8 else PE16_CORE_SHA), 'physical core source SHA differs')
    if profile['pes']==16:
        require(sources.get('rtl/perips/PairComputeCore.sv') == PE16_PAIR_SHA, 'physical pair source SHA differs')
    else:
        require('rtl/perips/PairComputeCore.sv' not in sources, 'unexpected pair core in fixed 8-PE profile')
    require(report['clock_configuration'] == clock_configuration(args['platform_clocks']),
            'platform clock configuration differs')
    recipe_path = root / 'clear-recipe.json'
    require(recipe_path.is_file() and not recipe_path.is_symlink(), 'missing/unsafe clear recipe')
    recipe = read_json(recipe_path)
    require(recipe['frozen_main_sha256'] == sources['tests/e203/firmware/main.c'] and
            recipe['helper_sha256'] == sources[profile['helper']],
            'clear recipe main/selected helper identity differs from source pins')
    require(args.get('clear_profile','scalar') == profile['clear_profile'], 'clear-profile argument differs')
    if profile['clear_profile']=='packed16-mmio':
        for document in (report,plan):
            require(document.get('clear_profile')==profile['clear_profile'] and
                    document.get('clear_helper_source_path')==profile['helper'] and
                    document.get('clear_helper_sha256')==sources[profile['helper']],
                    'packed selected helper identity is missing/different')
        require(recipe.get('clear_profile')==profile['clear_profile'] and
                recipe.get('helper_source_path')==profile['helper'], 'packed clear recipe selector differs')
    else:
        require('clear_profile' not in args and 'clear_profile' not in report and
                'clear_profile' not in recipe, 'fixed historical scalar schema differs')
    require(recipe['policy']=='REVIEW_PENDING' and recipe['fifo_payload_physical_zero']=='UNPROVEN' and
            report['cache_policy']=='REVIEW_PENDING' and report['fifo_payload_physical_zero']=='UNPROVEN',
            'pending clear policy or FIFO UNPROVEN cannot be promoted by this experiment')
    require(recipe['tasks_per_process'] == 1 and recipe['reset'] == 'fresh native process' and
            recipe['policy'] == report['cache_policy'] and
            recipe['fifo_payload_physical_zero'] == report['fifo_payload_physical_zero'],
            'clear recipe process/reset/policy differs')
    generated_c = artifact(root, 's3_clear_main.c', recipe['generated_c_sha256'])
    clear_c_identity = generated_clear_c_identity(generated_c, old_out)
    generated_tb = artifact(root, 'tb.sv', recipe['generated_tb_sha256'])
    regeneration = verify_clear_generation(root, old_out, sources, profile, recipe,
                                           generated_c, generated_tb, args)
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
            extras = [arg for arg in command if arg.startswith(('+NICE_BATCH16', '+NICE_STREAM', '+NICE_READY'))]
            require(extras == profile_arguments(profile,'selector',step['name']), 'exact profile runtime selector differs')
            extra_macros = [arg for arg in command if arg.startswith(('-DXU_NICE_DRAIN16', '-DXU_NICE_DRAINN', '-DXU_NICE_READY'))]
            require(extra_macros == profile_arguments(profile,'macro',step['name']), 'exact profile compiler macro differs')
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
        for key, expected in dict(mac_fire=profile['fires'], starts=profile['groups'], dones=profile['groups'],
                                  shared_reads=15040, shared_writes=25344).items():
            require(performance[key] == expected, 'performance work count differs: ' + key)
        nice = record(log, 'NICE_TASK', ('layer', *NICE))
        require(nice == task['nice_activity'] and nice.pop('layer') == 0, 'saved/raw NICE differs')
        for key, expected in dict(requests=profile['requests'], responses=profile['requests'], oitf_retired=profile['requests'],
                                  result_reads=0 if direct else 25344,
                                  pops_retired=3168, shared_writes=25344).items():
            require(nice[key] == expected, 'NICE protocol count differs: ' + key)
        if profile['transport']=='ready32':
            require(nice['status_polls']==0, 'ready profile issued ROW_STATUS poll')
        else:
            require(nice['status_polls'] >= 3168, 'legacy stream NICE status coverage incomplete')
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
        validate_clear_marker(clear, profile['clear_profile'], report['bias_kind'])
        extra_activity = profile_markers(log,task,schedule,profile,parser_api)
        # Check the exact remapped tensors/profile, plus exporter/model identity.
        vectors = task['vectors']
        required_vectors = {'profile.json', *('layer_00/' + name + '.mem' for name in
                            ('x', 'w', 'bias', 'y', 'y32', 'w_packed16'))}
        require(isinstance(vectors, dict) and required_vectors <= set(vectors),
                'missing vector identities')
        for relative, expected in vectors.items():
            artifact(root / ('task-%02d/vectors' % layer), relative, expected)
        rows.append(dict(original_layer=layer, payload_cycles=cycles, clear_cycles=clear_cycles,
                         **extra_activity,
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
    conditions['clear_profile'] = profile['clear_profile']
    conditions['clear_helper_source_path'] = profile['helper']
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
                postflow_profile=profile_name,
                source_sha256=sources, firmware_elf_sha256=report['firmware_elf_sha256'],
                firmware_loaded_elf=loaded_elf,
                firmware_image_sha256=report['firmware_image_sha256'],
                simulator_sha256=report['simulator_sha256'],
                clear_recipe_sha256=digest(recipe_path), generated_tb_sha256=recipe['generated_tb_sha256'],
                generated_c_sha256=recipe['generated_c_sha256'], generated_clear_c_identity=clear_c_identity,
                clear_regeneration=regeneration,
                rtl_filelist_sha256=digest(filelist_path), rows=rows)
    if direct:
        campaign['firmware_image_load_identity'] = verify_loaded_image(campaign)
    return campaign


def source_expectation(value):
    try:
        relative, pair = value.split('=', 1)
        before, after = pair.split(':')
    except ValueError as exc:
        raise argparse.ArgumentTypeError('expected PATH=BASE_SHA:CANDIDATE_SHA') from exc
    if not relative or not SHA.fullmatch(before) or not SHA.fullmatch(after) or before == after:
        raise argparse.ArgumentTypeError('expected one changed path and two different SHA256 values')
    return relative, (before, after)


def totals(rows):
    keys = ('payload_cycles', 'clear_cycles', 'payload_plus_clear_cycles', 'clear_to_source_gap')
    result = {key: sum(row[key] for row in rows) for key in keys}
    for category in ('phases', 'bus_counters', 'nice', 'auto', 'transport'):
        result[category] = {key: sum(row[category][key] for row in rows) for key in rows[0][category]}
    for marker in ('ready_activity','stream_activity'):
        result[marker]={key:sum(row['additional_markers'][marker][key] for row in rows)
                        for key in rows[0]['additional_markers'][marker] if key!='layer'}
    return result


def differences(before, after):
    return {key: differences(value, after[key]) if isinstance(value, dict) else after[key] - value
            for key, value in before.items()}


def canonical_conditions(campaign):
    """Normalize only the exact explicitly selected transport macro/selector."""
    conditions = copy.deepcopy(campaign['conditions'])
    profile = PROFILES[campaign['postflow_profile']]
    require(conditions['schedule'] == conditions['configuration']['schedule'] == profile['schedule'],
            'profile/saved schedule differs before normalization')
    conditions['schedule'] = conditions['configuration']['schedule'] = STREAM_SCHEDULE
    changes = []
    require(conditions['clear_profile']==profile['clear_profile'] and
            conditions['clear_helper_source_path']==profile['helper'], 'clear identity differs before normalization')
    for key in ('clear_profile','clear_helper_source_path'):
        changes.append(dict(field=key,removed_exact_value=conditions.pop(key)))
    # Work counts are different MMIO strategies; exact helper/recipe and marker
    # checks validate each independently. Physical logical work remains fixed.
    changes.append(dict(field='clear_recipe_configuration.clear_counts',
                        removed_exact_value=conditions['clear_recipe_configuration'].pop('clear_counts')))
    for step in conditions['commands']:
        command = step['command']
        extras = [x for x in command if x.startswith(('+NICE_BATCH16', '+NICE_STREAM', '+NICE_READY'))]
        expected = profile_arguments(profile,'selector',step['name'])
        require(extras == expected, 'unexpected/missing exact transport runtime selector at '+step['name'])
        macros = [x for x in command if x.startswith(('-DXU_NICE_DRAIN16', '-DXU_NICE_DRAINN', '-DXU_NICE_READY'))]
        expected_macros = profile_arguments(profile,'macro',step['name'])
        require(macros == expected_macros, 'unexpected/missing exact transport compiler macro at '+step['name'])
        for value in extras + macros:
            command.remove(value)
            changes.append(dict(step=step['name'], removed_exact_argument=value))
    return conditions, changes


def c_noncomment_bytes(data):
    """Remove C comments only, preserving strings and every noncomment byte."""
    pattern=rb'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|/\*.*?\*/|//[^\n]*'
    return re.sub(pattern,lambda m:m.group(1) if m.group(1) is not None else b'',data,flags=re.S)


def compare(base, candidate, expected_source_changes):
    bprofile, aprofile = (PROFILES[x['postflow_profile']] for x in (base,candidate))
    require(base['postflow_profile']=='ready32-scalar' and candidate['postflow_profile']=='ready32-packed',
            'only fixed READY scalar -> READY packed-clear comparison is supported')
    require(bprofile['pes']==aprofile['pes']==8 and bprofile['transport']==aprofile['transport']=='ready32',
            'payload architecture/transport differs')
    bc,bn=canonical_conditions(base)
    ac,an=canonical_conditions(candidate)
    require(bc==ac, 'conditions differ beyond explicit clear helper/profile/work-count normalization')
    before_sources,after_sources=base['source_sha256'],candidate['source_sha256']
    observed={key:(before_sources.get(key),after_sources.get(key))
              for key in set(before_sources)|set(after_sources)
              if before_sources.get(key)!=after_sources.get(key)}
    expected={key:tuple(value) for key,value in expected_source_changes.items()}
    require(observed==expected, 'source changes differ from exact reviewed SHA pairs')
    require(set(observed)==REQUIRED_SOURCE_CHANGES, 'only campaign.py and one new helper must change')
    require(observed[NEW_HELPER][0] is None and observed[NEW_HELPER][1] is not None,
            'new packed helper must be the only source addition')
    require(observed['campaign.py'][0]==BASELINE_CAMPAIGN_SHA and observed['campaign.py'][1] is not None,
            'campaign exact source pair differs')
    require(len(before_sources)==170 and len(after_sources)==171, 'fixed source count differs')
    image_checks=dict(baseline=verify_loaded_image(base),candidate=verify_loaded_image(candidate))
    same_firmware=(base['firmware_image_sha256']==candidate['firmware_image_sha256'] and
                   base['firmware_loaded_elf']==candidate['firmware_loaded_elf'])
    comparisons=[]
    require(len(base['rows'])==len(candidate['rows']), 'layer count differs')
    for before,after in zip(base['rows'],candidate['rows']):
        require(before['original_layer']==after['original_layer'], 'layer ordering differs')
        for key in ('vectors','vector_profile','profile_source_sha256','measured_clocks'):
            require(before[key]==after[key], 'task input/clock differs: '+key)
        require(startup_signature(before['startup_observations'])==startup_signature(after['startup_observations']),
                'startup reset semantics differ')
        physical_keys=('mode_sram','w','x','legacy_bias','bias_entries','sram_clear_commands','sram_done',
                       'nice_idle','fifo_payload_physical_zero','policy')
        require({k:before['clear'][k] for k in physical_keys}==
                {k:after['clear'][k] for k in physical_keys}, 'logical physical-clear work/policy differs')
        work_keys=('mac_fire','mmio_reads','mmio_writes','shared_reads','shared_writes','starts','dones')
        require({key:before['bus_counters'][key] for key in work_keys}==
                {key:after['bus_counters'][key] for key in work_keys} and
                before['nice']==after['nice'] and before['transport']==after['transport'] and
                {key:before['auto'][key] for key in ('rows','pops_retired')}==
                {key:after['auto'][key] for key in ('rows','pops_retired')},
                'frozen READY payload work/transaction count changed')
        b,a=totals([before]),totals([after])
        comparisons.append(dict(original_layer=before['original_layer'], baseline=b,candidate=a,
            delta=differences(b,a), physical=dict(baseline=before['physical'],candidate=after['physical']),
            additional_markers=dict(baseline=before['additional_markers'],candidate=after['additional_markers']),
            windows=dict(baseline=before['window'],candidate=after['window']),
            startup_observations=dict(baseline=before['startup_observations'],candidate=after['startup_observations'])))
    b,a=totals(base['rows']),totals(candidate['rows'])
    return dict(schema='s3-packed-clear-strict-comparison-v1',status='SAVED_CAMPAIGNS_COMPARED',
        scope='read-only development saved-evidence analysis; no new simulation, PPA or official qualification',
        verifier_origin_sha256=VERIFIER_ORIGIN_SHA256,verifier_sha256=digest(Path(__file__).resolve()),
        fixed_baseline_source_count=BASELINE_SOURCE_COUNT,fixed_baseline_sources_sha256=BASELINE_SOURCES_SHA256,
        metric='payload request-to-final-Y-response plus separately observed physical clear cycles',
        delta_convention='candidate minus baseline; negative cycle delta is an improvement',
        gap_semantics='clear-to-source gap retained separately, excluded from the main metric',
        overlap_semantics='overlap and FIFO wait overlap phase counters; never add them to phases',
        timing_semantics='all measured payload timing/phase/stall/READY_WAIT deltas retained; no padding or phase adjustment',
        physical_clear_evidence=dict(baseline='pinned scalar helper exact C and per-address MMIO observer with unchanged RTL; historical logs did not sample all 16 macro write pins',
            candidate='pinned packed helper exact C/TB with actual core and all 16 W macro edge/address/data coverage, bias edge/staging/post-state checks'),
        profiles=dict(baseline=base['postflow_profile'],candidate=candidate['postflow_profile']),
        condition_normalization=dict(baseline=bn,candidate=an,normalized_conditions_equal=True),
        source_changes={k:dict(baseline_sha256=v[0],candidate_sha256=v[1]) for k,v in sorted(observed.items())},
        firmware_identity=dict(raw_elf_sha256_equal=base['firmware_elf_sha256']==candidate['firmware_elf_sha256'],
            loaded_image_sha256_equal=base['firmware_image_sha256']==candidate['firmware_image_sha256'],
            elf_load_contract_equal=base['firmware_loaded_elf']==candidate['firmware_loaded_elf'],
            loaded_firmware_change_allowed=True,
            loaded_firmware_change_reason='exact regenerated selected public-MMIO clear helper; frozen main/accel sources unchanged; helper code changes may relocate payload code',
            independent_load_verification=image_checks),
        baseline_identity={k:v for k,v in base.items() if k!='rows'},
        candidate_identity={k:v for k,v in candidate.items() if k!='rows'},
        layer_selection=dict(baseline_original=base['original_layer_coverage'],
            candidate_original=candidate['original_layer_coverage'],compared=[r['original_layer'] for r in base['rows']],
            mode=base['selection_mode'],original_results_unmodified=True),
        layers=comparisons,totals=dict(baseline=b,candidate=a,delta=differences(b,a)))


def pinned_candidate_sources(base_sources,pairs):
    require(set(pairs)==REQUIRED_SOURCE_CHANGES, 'exact campaign+new-helper source pairs required')
    result=dict(base_sources)
    for key,pair in pairs.items():
        require(isinstance(pair,(list,tuple)) and len(pair)==2, 'invalid exact source pair: '+key)
        before,after=pair
        require(result.get(key)==before and isinstance(after,str) and SHA.fullmatch(after) and before!=after,
                'source pair baseline/candidate SHA differs: '+key)
        require((key==NEW_HELPER)==(before is None), 'only the new helper may be added')
        result[key]=after
    return result


def project_layers(campaign, selected, mode):
    """Project only already fully verified evidence, retaining original identities."""
    result=copy.deepcopy(campaign)
    original=[row['original_layer'] for row in campaign['rows']]
    require(set(selected)<=set(original), 'selected layers missing from verified campaign')
    result['original_layer_coverage']=original
    result['selection_mode']=mode
    result['rows']=[row for row in result['rows'] if row['original_layer'] in selected]
    require([r['original_layer'] for r in result['rows']]==selected, 'selected layer order differs')
    conditions=result['conditions']
    conditions['layers']=','.join(map(str,selected))
    conditions['original_layers']=selected
    selected_steps={'task-%02d/simulation'%layer for layer in selected}
    conditions['commands']=[step for step in conditions['commands']
        if not step['name'].endswith('/simulation') or step['name'] in selected_steps]
    return result


def parse_layers(value):
    try:
        layers=[int(x) for x in value.split(',')]
    except ValueError as exc:
        raise argparse.ArgumentTypeError('layers must be comma-separated integers') from exc
    if not layers or len(set(layers))!=len(layers) or any(not 0<=x<12 for x in layers):
        raise argparse.ArgumentTypeError('layers must be distinct values in 0..11')
    return layers


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path)
    parser.add_argument('candidate',type=Path)
    parser.add_argument('--baseline-profile',choices=('ready32-scalar',),default='ready32-scalar')
    parser.add_argument('--candidate-profile',choices=('ready32-packed',),default='ready32-packed')
    parser.add_argument('--baseline-sources',type=Path,required=True,
                        help='exact complete fixed 170-source ready-full12 map')
    parser.add_argument('--source-pairs',type=Path,required=True,
                        help='reviewed exact changes, path -> [before SHA,after SHA]')
    parser.add_argument('--layers',type=parse_layers,
                        help='explicit common-layer projection; no original result is changed')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        require(digest(args.baseline)==BASELINE_RESULT_SHA256, 'baseline is not the pinned ready-full12 result')
        require(digest(args.baseline_sources)==BASELINE_SOURCES_SHA256, 'fixed baseline source map file differs')
        pins=read_json(args.baseline_sources)
        require(len(pins)==BASELINE_SOURCE_COUNT, 'fixed baseline source count differs')
        pairs=read_json(args.source_pairs)
        candidate_pins=pinned_candidate_sources(pins,pairs)
        before=load_campaign(args.baseline,args.baseline_profile,pins)
        after=load_campaign(args.candidate,args.candidate_profile,candidate_pins)
        require([r['original_layer'] for r in before['rows']]==list(range(12)),
                'fixed baseline does not cover all original twelve layers')
        candidate_layers=[r['original_layer'] for r in after['rows']]
        if args.layers is None:
            selected=list(range(12))
            require(candidate_layers==selected, 'full12 comparison requires twelve candidate layers; use explicit --layers for a partial experiment')
            mode='full12-to-full12'
        else:
            selected=args.layers
            require(candidate_layers==selected, 'partial comparison must include every original candidate layer in order')
            mode='explicit-common-layer-projection'
        before=project_layers(before,selected,mode)
        after=project_layers(after,selected,mode)
        result=compare(before,after,pairs)
        with args.out.open('x') as stream:
            json.dump(result,stream,indent=2,sort_keys=True)
            stream.write('\n')
        print('PACKED_CLEAR_SAVED_EVIDENCE_COMPARED')
        for key in ('payload_cycles','clear_cycles','payload_plus_clear_cycles','clear_to_source_gap'):
            print(key,result['totals']['baseline'][key],result['totals']['candidate'][key],result['totals']['delta'][key])
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration,AttributeError) as exc:
        print('PACKED_CLEAR_COMPARISON_REJECTED:',exc,file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
