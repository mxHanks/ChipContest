#!/usr/bin/env python3
"""Inventory and prepare explicit full-digital-SoC PPA; never substitute absent RAM by zero.

Python 3.6+; inventory needs only Git. prepare accepts independently validated memory
implementations and a top joining the fixed E203 SoC to its 512 KiB ICB RAM. Running
EDA is explicit. Generated DC/PT scripts reject missing macros and unresolved designs.
A successful tool invocation is not a timing, activity-coverage, or contest pass.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[2]
SUB = 'third-party/e203_hbirdv2'
RTL = SUB + '/rtl/e203'
REQUIRED_BITS = {'itcm': 65536*8, 'dtcm': 65536*8,
                 'shared': 524288*8, 'accelerator_weights': 32768*8}
REPLACEABLE = {RTL+'/general/sirv_sim_ram.v', RTL+'/perips/mem_1024x16.sv'}
MAPPING_CHECKS = ['macro_functional_model', 'byte_write_masks', 'read_latency_and_hold',
                  'bank_boundaries', 'write_read_collision', 'icb_backpressure_retirement',
                  'whole_soc_functional_equivalence', 'sram_pvt_timing_eligibility']
MAIN = 'u_soc/u_e203_subsys_top/u_e203_subsys_main'
MEMORY_SCOPES = {'itcm': MAIN+'/u_e203_cpu_top/u_e203_srams/u_e203_itcm_ram/*',
                 'dtcm': MAIN+'/u_e203_cpu_top/u_e203_srams/u_e203_dtcm_ram/*',
                 'shared': 'u_shared/storage/*',
                 'accelerator_weights': MAIN+'/u_e203_subsys_perips/u_accel_icb_slave/*'}
RETAINED = {'cpu': (MAIN+'/u_e203_cpu_top', 'e203_cpu_top*'),
            'accelerator': (MAIN+'/u_e203_subsys_perips/u_accel_icb_slave', 'accel_icb_slave*'),
            'interconnect': (MAIN+'/u_e203_subsys_perips/u_sirv_ppi_fab', 'sirv_icb1to16_bus*')}
S3_PROFILES = ('s3-y32-bias-sram', 's3-y32-bias-registers')
S3_SOURCE_ROOTS = ('src', 'model', 'tests', 'tools/scripts', 'tools/model', 'tools/ppa',
                   'project.scala', SUB+'/rtl', SUB+'/e203_core.core')
S3_MAPPING_CHECKS = ('nice_decode_and_bus_arbitration', 'nice_oitf_completion_and_errors',
                     's3_task_clear_protocol', 's3_numeric_layout_and_window')
S3_CLOCK_PROFILES = {
    'nominal150-balanced-v1': dict(name='nominal150-balanced-v1', period_fs_numerator=20000000,
                                   period_fs_denominator=3, max_window_phase_error_fs=1),
    'nominal150-quantized-half3333333fs-v1': dict(name='nominal150-quantized-half3333333fs-v1',
        period_fs_numerator=6666666, period_fs_denominator=1, max_window_phase_error_fs=1),
}


def s3_transaction_contract(root, schedule):
    path = Path(root)/'tools/scripts/xu_firmware_contract.py'
    spec = importlib.util.spec_from_file_location('_s3_ppa_firmware_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.task_contract(schedule)


def s3_activity_windows(impl, record, layers):
    name = impl.get('activity_clock_profile')
    require(name in S3_CLOCK_PROFILES and record.get('clock_profile') == S3_CLOCK_PROFILES[name],
            'S3 activity clock profile/budget differs')
    policy = S3_CLOCK_PROFILES[name]
    ticks = record.get('windows_fs', [])
    windows = record.get('windows_ns', [])
    require(len(ticks) == len(layers) and len(windows) == len(layers), 'S3 physical timestamp windows missing')
    last = -1
    period = Fraction(policy['period_fs_numerator'], policy['period_fs_denominator'])
    require(record.get('clock_period_ns') == float(period/1000000), 'S3 actual period differs from declared clock profile')
    for index, pair in enumerate(ticks):
        require(isinstance(pair, list) and len(pair) == 2 and
                all(type(value) is int for value in pair) and 0 <= pair[0] < pair[1] and pair[0] > last,
                'S3 timestamp ticks invalid/overlapping')
        expected = (layers[index]['cycles']-1)*period
        require(abs(Fraction(pair[1]-pair[0])-expected) <= policy['max_window_phase_error_fs'],
                'S3 request/final-response window differs from bounded actual clock phase')
        require(isinstance(windows[index], list) and len(windows[index]) == 2 and
                all(abs(Decimal(str(value))*1000000-tick) <= 1
                    for value,tick in zip(windows[index],pair)), 'S3 ns/fs timestamp conversion differs')
        last = pair[1]


def hardware_profile(name=None):
    """Explicit S3 opt-in; the historical default retains its exact contract."""
    if name is None:
        return dict(bits=REQUIRED_BITS, scopes=MEMORY_SCOPES, retained=RETAINED, area=[])
    require(name in S3_PROFILES, 'unknown hardware profile: '+str(name))
    accel = RETAINED['accelerator'][0]
    nice = MAIN+'/u_e203_cpu_top/u_e203_cpu/u_e203_nice_core'
    bits = dict(REQUIRED_BITS)
    scopes = dict(MEMORY_SCOPES,
                  accelerator_weights=accel+'/u_linear_compute_core/core/weightBanks/*')
    if name == 's3-y32-bias-sram':
        bits['accelerator_bias'] = 1024*16
        scopes['accelerator_bias'] = accel+'/u_linear_compute_core/biasCache/memory/*'
    retained = dict(RETAINED, nice=(nice, 'e203_subsys_nice_core*'))
    area = [dict(name='peripheral', pattern=accel, reference_pattern='accel_icb_slave*'),
            dict(name='nice_extension', pattern=nice, reference_pattern='e203_subsys_nice_core*')]
    return dict(bits=bits, scopes=scopes, retained=retained, area=area)


def s3_worktree_sources(root):
    """Bind all runtime, numeric, verification and PPA bytes, including untracked files."""
    root = Path(root).resolve()
    paths = set()
    for relative in S3_SOURCE_ROOTS:
        path = root/relative
        require(path.exists(), 'S3 freeze source path missing: '+relative)
        candidates = path.rglob('*') if path.is_dir() else [path]
        for candidate in candidates:
            if any(part in ('__pycache__', '.scala-build', '.bsp', '.git') for part in candidate.relative_to(root).parts):
                continue
            if candidate.suffix == '.pyc':
                continue
            require(not candidate.is_symlink(), 'S3 freeze source must not be a symlink: '+str(candidate))
            if candidate.is_file():
                paths.add(candidate)
    return dict(schema='s3-full-soc-worktree-freeze-v1',
                main_commit=git(root, 'rev-parse', 'HEAD'),
                e203_commit=git(root/SUB, 'rev-parse', 'HEAD'),
                source_roots=list(S3_SOURCE_ROOTS),
                source_files={p.relative_to(root).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size)
                              for p in sorted(paths)})


def check_s3_worktree_freeze(impl, inv):
    path = absolute_file(impl.get('worktree_freeze'), 'S3 worktree freeze')
    frozen = json.loads(path.read_text())
    current = s3_worktree_sources(inv['root'])
    require(frozen.get('hardware_profile') == impl['hardware_profile'], 'S3 frozen hardware profile differs')
    require(all(frozen.get(key) == value for key, value in current.items()),
            'S3 full worktree source freeze differs; freeze and prepare a fresh candidate')


def check_s3_storage(root, name):
    text = comments((Path(root)/RTL/'perips/LinearAutoGroupCore.sv').read_text())
    expected = '42530001' if name == 's3-y32-bias-sram' else '0'
    found = re.findall(r"\bassign\s+io_biasSramCapability\s*=\s*32'h([0-9a-fA-F]+)\s*;", text)
    require(len(found) == 1 and int(found[0], 16) == int(expected, 16),
            'installed generated bias capability differs from selected S3 profile')
    module = 'BiasSramPrefetch' if name == 's3-y32-bias-sram' else 'BiasBankCache'
    require(re.search(r'\b'+module+r'\s+biasCache\s*\(', text) is not None,
            'installed generated bias hierarchy differs from selected S3 profile')

def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def comments(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def git(root, *args):
    return subprocess.check_output(['git']+list(args), cwd=str(root)).decode().strip()


def inventory(root, profile=None):
    root = Path(root).resolve()
    config = hardware_profile(profile)
    bits = config['bits']
    if profile is not None:
        check_s3_storage(root, profile)
    paths = sorted(p for p in (root/RTL).rglob('*') if p.suffix in ['.v', '.sv'])
    source = {p.relative_to(root).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size)
              for p in paths}
    header_paths = [root/RTL/'core/config.v', root/RTL/'core/e203_defines.v']
    cfg = comments(header_paths[0].read_text())
    sizes = {}
    for name, word_bits in [('ITCM', 64), ('DTCM', 32)]:
        matches = re.findall(r'^\s*`define\s+E203_CFG_'+name+r'_ADDR_WIDTH\s+(\d+)\s*$', cfg, re.M)
        require(matches == ['16'], name+' differs from frozen 64 KiB configuration')
        require(re.search(r'^\s*`define\s+E203_CFG_HAS_'+name+r'\b', cfg, re.M), name+' disabled')
        sizes[name.lower()] = dict(bytes=2**int(matches[0]), bits=2**int(matches[0])*8,
                                   word_bits=word_bits, words=2**int(matches[0])*8//word_bits,
                                   byte_write_mask_bits=word_bits//8,
                                   implementation='sirv_gnrl_ram -> behavioral sirv_sim_ram')
    tb_path = root/'tests/e203/tb_accel_soc.sv'
    tb = comments(tb_path.read_text())
    found = re.findall(r'\breg\s*\[(\d+):0\]\s*ram\s*\[0:(\d+)\]', tb)
    require(found == [('31', '131071')], 'shared TB RAM capacity changed; inspect manually')
    require('e203_soc_top #(.EXTERNAL_SYSMEM(1))' in tb, 'external shared-memory boundary changed')
    sizes['shared'] = dict(bytes=524288, bits=524288*8, words=131072, word_bits=32,
                           byte_write_mask_bits=4, implementation='testbench reg array outside e203_soc_top',
                           synthesized_in_e203_soc_top=False,
                           response='one outstanding; response held until accepted; cmd_ready additionally cycles%7!=0',
                           write_behavior='TB accepts only fullword Y writes; HOST status writes handled by scoreboard')
    sizes['accelerator_weights'] = dict(bytes=32768, bits=32768*8, words=16384, word_bits=16,
                                        implementation='16 mem_1024x16 behavioral instances unless substituted',
                                        physical_1024x16_macros=16)
    if profile == 's3-y32-bias-sram':
        sizes['accelerator_bias'] = dict(bytes=2048, bits=16384, words=1024, word_bits=16,
                                        used_words=768, payload_bits=256*40,
                                        implementation='one mem_1024x16 instance plus two 8x40 staging groups',
                                        physical_1024x16_macros=1)
    arrays = []
    for path in paths:
        text = comments(path.read_text())
        for match in re.finditer(r'\b(reg|wire)\s*(\[[^\]\n]+\])?\s+(\w+)\s*\[([^;\n]+)\]\s*;', text):
            arrays.append(dict(path=path.relative_to(root).as_posix(), kind=match[1],
                               width=match[2], name=match[3], bounds=match[4],
                               note='source-level declaration only; elaboration determines live storage'))
    result = dict(schema='xu-full-soc-source-inventory-v1', status='INVENTORIED_NOT_QUALIFIED',
                created_utc=datetime.now(timezone.utc).isoformat(), root=str(root),
                main_commit=git(root, 'rev-parse', 'HEAD'), e203_commit=git(root/SUB, 'rev-parse', 'HEAD'),
                platform_source=source, platform_source_manifest_sha256=digest(source),
                testbench=dict(path=str(tb_path), sha256=sha(tb_path)), memories=sizes,
                total_required_sram_bits=sum(bits.values()),
                hypothetical_1024x16_macro_counts={k:v//16384 for k,v in bits.items()},
                hypothetical_1024x16_macro_total=sum(bits.values())//16384,
                other_storage_declarations=arrays,
                clocks=dict(reference_tb=dict(hf_period_ns=4, lf_period_ns=66),
                            nominal_hf_period_ns=20/3,
                            observed_rtl=['hfextclk / lfextclk', 'programmable divider',
                                          'glitch-free clock mux', 'latch-based clock gates', 'JTAG TCK'],
                            pll='e203_subsys_pll assigns reference through; no physical analog PLL model'),
                gaps=[
                    '512 KiB shared RAM exists only in TB; synthesize an explicit RAM+ICB endpoint in a full-scope top',
                    'ITCM/DTCM behavioral arrays need qualified SRAM mappings with byte writes and synchronous read semantics',
                    'TB task preload/scoreboard/HOST is not synthesizable hardware and must stay outside the PPA top',
                    'Register/FIFO/debug/bias/X storage still costs standard cells unless separately mapped; do not count as zero',
                    'Fixed clock/reset/gating topology needs full-SoC clocks, generated clocks, exceptions and analysis-coverage review',
                    'Wrapper-only VCD cannot measure CPU/interconnect/shared SRAM energy',
                    'Mapped gate/SRAM functional equivalence and twelve-task full-scope activity remain required'],
                scope='inventory only; no synthesized area, timing closure, power, or contest qualification assertion')
    if profile is not None:
        result['hardware_profile'] = profile
        result['accelerator_area_scopes'] = config['area']
    return result


def template(inv):
    profile = inv.get('hardware_profile')
    config = hardware_profile(profile)
    result = dict(schema='xu-full-soc-implementation-v1', top='xu_soc_ppa_top',
                platform_source_manifest_sha256=inv['platform_source_manifest_sha256'],
                replacements={name:dict(path='/absolute/qualified/replacement/'+Path(name).name, sha256='REQUIRED')
                              for name in sorted(REPLACEABLE)},
                added_sources=[dict(path='/absolute/qualified/xu_soc_ppa_top.sv', sha256='REQUIRED'),
                               dict(path='/absolute/qualified/xu_shared_icb_sram.sv', sha256='REQUIRED')],
                libraries=[dict(path='/absolute/same-corner/standard_cells.db', sha256='REQUIRED', role='standard_cell'),
                           dict(path='/absolute/same-corner/SRAM.db', sha256='REQUIRED', role='sram')],
                search_paths=[], defines=['SYNTHESIS', 'DISABLE_SV_ASSERTION=1'],
                constraints=dict(path='/absolute/reviewed/full-soc.sdc', sha256='REQUIRED'),
                memory_groups=[dict(name=name, logical_bits=bits, instance_pattern=config['scopes'][name],
                                    macro_ref='RAMSP1024X16', depth=1024, width=16, count=bits//16384)
                               for name,bits in config['bits'].items()],
                retained_instances=[dict(name=name,pattern=record[0],reference_pattern=record[1])
                                    for name,record in sorted(config['retained'].items())],
                mapping_proof=dict(path='/absolute/verified/mapping-proof.json', sha256='REQUIRED'),
                clock_review=dict(path='/absolute/reviewed/clock-review.json', sha256='REQUIRED'),
                activity=None,
                note='Fill actual paths/hashes after SRAM-model, byte-mask, timing, bus and whole-SoC functional checks. No defaults qualify.')
    if profile is not None:
        result.update(hardware_profile=profile, accelerator_area_scopes=config['area'],
                      accelerator_area_policy='conservative-whole-nice-including-historical-demo-v1',
                      firmware_schedule=None, transaction_contract=None,
                      activity_clock_profile='nominal150-balanced-v1',
                      worktree_freeze=dict(path='/absolute/frozen/source-freeze.json', sha256='REQUIRED'))
    return result


def absolute_file(record, label):
    require(isinstance(record, dict), label+' must be a file identity object')
    path = Path(record.get('path', ''))
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), label+' is not an absolute regular file')
    require(re.fullmatch(r'[0-9a-f]{64}', record.get('sha256', '')) is not None and sha(path)==record['sha256'],
            label+' SHA256 differs or is missing')
    return path


def tcl(value):
    value = str(value)
    require(not any(c in value for c in '{}\\\r\n'), 'unsupported Tcl path/name character')
    return '{'+value+'}'


def library_paths(impl):
    libraries=impl.get('libraries',[])
    require(isinstance(libraries,list) and len(libraries)>=2, 'standard cell and SRAM libraries are required')
    require(all(record.get('role') in ['standard_cell','sram'] for record in libraries),
            'each library needs an explicit standard_cell or sram role')
    files=[str(absolute_file(record, 'library '+str(n))) for n,record in enumerate(libraries)]
    require(len(set(files))==len(files), 'duplicate library paths/roles')
    target=[path for path,record in zip(files,libraries) if record['role']=='standard_cell']
    macros=[path for path,record in zip(files,libraries) if record['role']=='sram']
    require(target and macros, 'both standard_cell and sram library roles are required')
    return target,files


def mapping_review_template(impl):
    # This records no test result. Fill each check from a real, hash-bound log.
    for record in list(impl['replacements'].values())+impl['added_sources']:
        absolute_file(record,'mapping source')
    checks = list(MAPPING_CHECKS)
    if impl.get('hardware_profile') is not None:
        hardware_profile(impl['hardware_profile'])
        checks += list(S3_MAPPING_CHECKS)
        if impl['hardware_profile'] == 's3-y32-bias-sram':
            checks += ['bias_sram_partial_write_read', 'bias_prefetch_epoch_and_clear']
    return dict(schema='xu-full-soc-mapping-review-v1',status='UNREVIEWED',
                mapping_sha256=digest(dict(replacements=impl['replacements'],added_sources=impl['added_sources'])),
                checks={name:dict(status='NOT_RUN',log=None,review=None) for name in checks},
                mapped_equivalence=dict(status='NOT_RUN',netlist_sha256=None,log=None),
                note='No prefilled PASS. Whole-SoC RTL mapping checks do not substitute mapped-netlist equivalence or SRAM PVT timing eligibility.')


def checked_implementation(impl, inv, allow_unqualified=False):
    require(impl.get('schema')=='xu-full-soc-implementation-v1', 'implementation schema differs')
    profile = impl.get('hardware_profile')
    require(profile == inv.get('hardware_profile'), 'implementation/inventory hardware profile differs')
    config = hardware_profile(profile)
    require(impl.get('platform_source_manifest_sha256')==inv['platform_source_manifest_sha256'], 'platform source freeze differs')
    require(impl.get('top')=='xu_soc_ppa_top', 'fixed full-SoC PPA top must be xu_soc_ppa_top')
    require(set(impl.get('replacements',{}))==REPLACEABLE, 'only both known behavioral RAM definitions may be replaced')
    for name,record in impl['replacements'].items():
        absolute_file(record, 'replacement '+name)
    require(impl.get('added_sources'), 'full-scope top / shared RAM implementation is missing')
    for n,record in enumerate(impl['added_sources']):
        absolute_file(record, 'added source '+str(n))
    library_paths(impl)
    absolute_file(impl.get('constraints'), 'constraints')
    defines=impl.get('defines',[])
    require('SYNTHESIS' in defines and not any('FPGA_SOURCE' in x for x in defines), 'ASIC SYNTHESIS with actual clock gating is required')
    require(all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:=[A-Za-z0-9_]+)?', x) for x in defines), 'invalid defines')
    groups=impl.get('memory_groups',[])
    require({g.get('name') for g in groups}==set(config['bits']) and len(groups)==len(config['bits']),
            'all profile SRAM capacity groups are required')
    for g in groups:
        require(g.get('logical_bits')==config['bits'][g['name']], 'logical memory capacity differs: '+g['name'])
        for k in ['count','width','depth']:
            require(type(g.get(k)) is int and g[k]>0, 'bad SRAM geometry '+g['name'])
        require((g['count'],g['depth'],g['width'],g.get('macro_ref'))==(g['logical_bits']//16384,1024,16,'RAMSP1024X16'),
                'frozen RAMSP1024X16 geometry/count differs: '+g['name'])
        require(g.get('instance_pattern')==config['scopes'][g['name']], 'actual fixed SRAM scope differs: '+g['name'])
    retained=impl.get('retained_instances',[])
    require({x.get('name') for x in retained}==set(config['retained']) and len(retained)==len(config['retained']),
            'all profile CPU/accelerator/interconnect/NICE hierarchy checks required')
    require(all((x.get('pattern'),x.get('reference_pattern'))==config['retained'][x['name']] for x in retained),
            'actual fixed CPU/accelerator/interconnect hierarchy and reference guards required')
    if profile is not None:
        require(impl.get('accelerator_area_scopes') == config['area'],
                'S3 area must include disjoint peripheral and entire NICE extension')
        require(impl.get('accelerator_area_policy') == 'conservative-whole-nice-including-historical-demo-v1',
                'S3 conservative whole-NICE area must not be labeled official incremental area')
        check_s3_worktree_freeze(impl, inv)
        expected_work = s3_transaction_contract(inv['root'], impl.get('firmware_schedule'))
        require(impl.get('transaction_contract') == expected_work, 'S3 firmware schedule/transaction contract differs')
        require(impl.get('activity_clock_profile') in S3_CLOCK_PROFILES, 'S3 activity clock profile missing/unknown')
    proof_path=absolute_file(impl.get('mapping_proof'), 'mapping proof')
    proof=json.loads(proof_path.read_text())
    mapping_identity=dict(replacements=impl['replacements'],added_sources=impl['added_sources'])
    require(proof.get('mapping_sha256')==digest(mapping_identity), 'mapping proof is not bound to exact implementation sources')
    checks=proof.get('checks',{})
    gaps=[]
    required_checks = list(MAPPING_CHECKS)
    if profile is not None:
        required_checks += list(S3_MAPPING_CHECKS)
        if profile == 's3-y32-bias-sram':
            required_checks += ['bias_sram_partial_write_read', 'bias_prefetch_epoch_and_clear']
    for name in required_checks:
        check=checks.get(name,{})
        if check.get('status')=='PASS':
            absolute_file(check.get('log'), 'proof raw log '+name)
        else:
            gaps.append('mapping:'+name+':'+str(check.get('status','MISSING')))
    equivalence=proof.get('mapped_equivalence',{})
    if equivalence.get('status')=='PASS':
        absolute_file(equivalence.get('log'), 'mapped-equivalence raw log')
        require(re.fullmatch(r'[0-9a-f]{64}',equivalence.get('netlist_sha256','')) is not None,
                'mapped-equivalence PASS needs an actual netlist SHA256')
    else:
        gaps.append('mapped-equivalence:'+str(equivalence.get('status','MISSING')))
    if proof.get('status')!='PASS':gaps.append('mapping-review:'+str(proof.get('status','MISSING')))
    require(allow_unqualified or not gaps, 'memory/bus/SoC/PVT proof incomplete; explicit --allow-unqualified-mapping is required for development measurement')
    review_path=absolute_file(impl.get('clock_review'), 'clock review')
    review=json.loads(review_path.read_text())
    require(review.get('status')=='REVIEWED' and review.get('constraints_sha256')==impl['constraints']['sha256'], 'clock review does not bind reviewed SDC')
    for relative,record in review.get('source_files',{}).items():
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts,
                'clock review source key must be repository-relative')
        path=Path(inv['root'])/relative
        require(path.is_file() and sha(path)==record.get('sha256'), 'clock-reviewed source changed: '+relative)
    require(all(review.get(k) for k in ['primary_clocks','generated_clock_policy','reset_exceptions','clock_domain_crossings','untested_check_policy']), 'clock/reset/untested policy incomplete')
    return proof,review,gaps


def memory_checks(impl):
    config = hardware_profile(impl.get('hardware_profile'))
    macro_total = sum(config['bits'].values())//16384
    lines=['# Exact post-elaboration macro groups; overlapping matches and missing/extra cells fail.', 'set xu_seen [dict create]']
    for g in impl['memory_groups']:
        # -hierarchical patterns containing '/' differ between DC/PT releases.
        # Filter full_name explicitly and count actual macro leaves only.
        filt='full_name =~ '+g['instance_pattern']+' && ref_name == '+g['macro_ref']
        lines += ['set xu_cells [get_cells -quiet -hierarchical -filter '+tcl(filt)+']',
                  'if {[sizeof_collection $xu_cells] != '+str(g['count'])+'} {error '+tcl('wrong macro count: '+g['name'])+'}',
                  'foreach_in_collection xu_c $xu_cells {',
                  '  set xu_n [get_object_name $xu_c]',
                  '  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}',
                  '  dict set xu_seen $xu_n 1',
                  '  if {[get_attribute $xu_c ref_name] != '+tcl(g['macro_ref'])+'} {error "wrong SRAM reference: $xu_n"}',
                  '}',
                  'puts "XU_SRAM_GROUP '+g['name']+' count='+str(g['count'])+' logical_bits='+str(g['logical_bits'])+'"']
    lines += ['set xu_all_macros [get_cells -quiet -hierarchical -filter {ref_name == RAMSP1024X16}]',
              'if {[sizeof_collection $xu_all_macros] != '+str(macro_total)+' || [dict size $xu_seen] != '+str(macro_total)+'} {error {full-SoC RAMSP1024X16 total must be exactly '+str(macro_total)+'}}',
              'foreach_in_collection xu_c $xu_all_macros {if {![dict exists $xu_seen [get_object_name $xu_c]]} {error {ungrouped/unaccounted SRAM macro}}}']
    for x in impl['retained_instances']:
        filt='full_name == '+x['pattern']+' && ref_name =~ '+x['reference_pattern']
        lines.append('if {[sizeof_collection [get_cells -quiet -hierarchical -filter '+tcl(filt)+']] != 1} {error '+tcl('missing/wrong '+x['name'])+'}')
    return '\n'.join(lines)+'\n'


def accelerator_area_tcl(impl):
    """Classify every S3 leaf; physical area excludes only guarded native constants."""
    scopes = hardware_profile(impl.get('hardware_profile'))['area']
    if not scopes:
        return ''
    require(impl.get('accelerator_area_scopes') == scopes, 'S3 area scopes differ')
    lines = ['set xu_area_file [open accelerator-area.tsv w]',
             'puts $xu_area_file "component\\tinstance\\tleaf_count\\tarea_library_units"',
             'set xu_virtual_file [open virtual-constant.tsv w]',
             'puts $xu_virtual_file "component\\tinstance\\treference\\tclassification"',
             'set xu_area_seen [dict create]', 'set xu_area_total 0.0']
    for scope in scopes:
        hierarchy = 'full_name == '+scope['pattern']+' && ref_name =~ '+scope['reference_pattern']
        leaves = 'full_name =~ '+scope['pattern']+'/* && is_hierarchical == false'
        lines += ['if {[sizeof_collection [get_cells -quiet -hierarchical -filter '+tcl(hierarchy)+']] != 1} {error '+tcl('missing/wrong area scope: '+scope['name'])+'}',
                  'set xu_area_cells [get_cells -quiet -hierarchical -filter '+tcl(leaves)+']',
                  'if {[sizeof_collection $xu_area_cells] == 0} {error '+tcl('empty area scope: '+scope['name'])+'}',
                  'set xu_component_area 0.0',
                  'set xu_virtual_count 0',
                  'foreach_in_collection xu_c $xu_area_cells {',
                  '  set xu_n [get_object_name $xu_c]',
                  '  if {[dict exists $xu_area_seen $xu_n]} {error "double-counted accelerator area leaf: $xu_n"}',
                  '  dict set xu_area_seen $xu_n 1',
                  '  set xu_ref [get_attribute $xu_c ref_name]',
                  '  if {$xu_ref eq {**logic_0**} || $xu_ref eq {**logic_1**}} {',
                  '    set xu_mapped [get_attribute $xu_c is_mapped]',
                  '    set xu_lib_candidates [get_lib_cells -quiet */$xu_ref]',
                  '    if {![string is true -strict $xu_mapped] || [sizeof_collection $xu_lib_candidates] != 0} {error "invalid virtual constant classification: $xu_n"}',
                  '    puts $xu_virtual_file "'+scope['name']+'\\t$xu_n\\t$xu_ref\\tvirtual_constant:is_mapped=true;library_candidates=0"',
                  '    incr xu_virtual_count',
                  '    continue',
                  '  }',
                  '  set xu_a [get_attribute $xu_c area]',
                  '  if {![string is double -strict $xu_a] || $xu_a < 0 || $xu_a != $xu_a || abs($xu_a) == Inf} {error "invalid leaf area: $xu_n"}',
                  '  set xu_component_area [expr {$xu_component_area + $xu_a}]',
                  '}',
                  'if {$xu_component_area <= 0} {error '+tcl('nonpositive area scope: '+scope['name'])+'}',
                  'puts $xu_area_file "'+scope['name']+'\\t'+scope['pattern']+'\\t[sizeof_collection $xu_area_cells]\\t$xu_component_area"',
                  'puts "XU_AREA_LEAF_CLASSIFICATION component='+scope['name']+' total_leaf_count=[sizeof_collection $xu_area_cells] virtual_constant_count=$xu_virtual_count physical_leaf_count=[expr {[sizeof_collection $xu_area_cells] - $xu_virtual_count}]"',
                  'set xu_area_total [expr {$xu_area_total + $xu_component_area}]']
    lines += ['puts $xu_area_file "accelerator_total\\tdisjoint_peripheral_plus_entire_nice\\t[dict size $xu_area_seen]\\t$xu_area_total"',
              'close $xu_area_file', 'close $xu_virtual_file']
    return '\n'.join(lines)+'\n'


def guarded_tcl(body, marker):
    # Synopsys shells can otherwise continue past a Tcl failure and exit zero.
    return ('if {[catch {\n'+body+'\nputs '+tcl(marker)+'\n} xu_error]} {\n'
            '  puts stderr "XU_FATAL: $xu_error"\n  exit 1\n}\nexit 0\n')


def clock_contract_checks():
    return ('foreach xu_pair {{xu_hfextclk 6.666666667} {xu_lfextclk 30517.578125} {xu_jtag_tck 100.0}} {\n'
            '  set xu_clock [get_clocks -quiet [lindex $xu_pair 0]]\n'
            '  if {[sizeof_collection $xu_clock] != 1} {error "missing primary clock $xu_pair"}\n'
            '  if {abs([get_attribute $xu_clock period]-[lindex $xu_pair 1]) > 0.000001} {error "wrong clock period $xu_pair"}\n'
            '}\nif {[sizeof_collection [get_clocks -quiet xu_plldiv_envelope]] != 1} {error {default conservative divider clock is missing}}\n')


def prepare(root, out, impl, allow_unqualified=False):
    inv=inventory(root, impl.get('hardware_profile'))
    proof,review,gaps=checked_implementation(impl,inv,allow_unqualified)
    require(not out.exists(), 'output directory exists')
    out.mkdir(parents=True)
    source_dir=out/'rtl';source_dir.mkdir()
    inputs=[];origin={}
    for relative,record in inv['platform_source'].items():
        original=Path(root)/relative
        src=absolute_file(impl['replacements'][relative],relative) if relative in impl['replacements'] else original
        dst=source_dir/relative[len(RTL)+1:];dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(str(src),str(dst));inputs.append(dst)
        origin[str(dst.relative_to(out))]=dict(path=str(src),sha256=sha(src),original_platform_sha256=record['sha256'],replacement=relative in impl['replacements'])
    for index,record in enumerate(impl['added_sources']):
        src=absolute_file(record,'added source');dst=source_dir/'xu-added'/('%03d-'%index+src.name);dst.parent.mkdir(exist_ok=True)
        shutil.copyfile(str(src),str(dst));inputs.append(dst);origin[str(dst.relative_to(out))]=dict(path=str(src),sha256=sha(src),replacement=False)
    shutil.copyfile(str(absolute_file(impl['constraints'],'SDC')),str(out/'constraints.sdc'))
    reporter=Path(root)/'tools/ppa/xu_full_soc_clock_review.tcl'
    require(reporter.is_file(),'clock-report collector is missing')
    shutil.copyfile(str(reporter),str(out/'clock-review.tcl'))
    target_libs,libs=library_paths(impl)
    includes=sorted({str(p.parent) for p in inputs})+impl.get('search_paths',[])
    require(all(Path(p).is_dir() for p in includes), 'missing include/search directory')
    # Current platform includes only these .v headers, which are copied above.
    for src in inputs:
        for header in re.findall(r'^\s*`include\s+"([^"]+)"',src.read_text(),re.M):
            matches=[Path(directory)/header for directory in includes if (Path(directory)/header).is_file()]
            require(matches and all(str(p).startswith(str(out)+'/') for p in matches),
                    'include must resolve only inside frozen prepared RTL: '+header)
    libexpr='[list * '+' '.join(tcl(p) for p in libs)+']'
    common='set_app_var link_library '+libexpr+'\nset_app_var target_library [list '+' '.join(tcl(p) for p in target_libs)+']\n'
    synth=common+'set_app_var search_path [concat $search_path [list '+' '.join(tcl(p) for p in includes)+']]\n'
    synth+='define_design_lib WORK -path ./WORK\n'
    if impl.get('hardware_profile') in S3_PROFILES:
        synth+='set_svf '+tcl(out.resolve()/'default.svf')+'\n'
    synth+='analyze -format sverilog -define [list '+' '.join(tcl(x) for x in impl['defines'])+'] [list '+' '.join(tcl(p) for p in inputs)+']\n'
    synth+='elaborate '+tcl(impl['top'])+'\ncurrent_design '+tcl(impl['top'])+'\nif {![link]} {error {DC link failed}}\n'
    synth+='if {[sizeof_collection [current_design]] != 1} {error {no elaborated current design}}\n'
    synth+='foreach_in_collection xu_d [get_designs *] {\nset xu_blackbox [get_attribute $xu_d is_black_box]\nif {[string is true -strict $xu_blackbox]} {error "unresolved design [get_object_name $xu_d]"}\nif {$xu_blackbox ne "" && ![string is false -strict $xu_blackbox]} {error "unexpected black-box attribute [get_object_name $xu_d]: $xu_blackbox"}\n}\n'
    # This reviewed contract contains Tcl collection operations/procedures.
    # DC read_sdc uses its restricted SDC interpreter; source preserves the
    # normal shell commands/options used by this contract.
    synth+=memory_checks(impl)+'check_design > precheck.rpt\nset XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource constraints.sdc\n'+clock_contract_checks()
    synth+='set_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false\n'
    synth+='set_dont_touch [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}] true\n'
    synth+='set_fix_hold [all_clocks]\ncompile_ultra -no_autoungroup\n'
    synth+=memory_checks(impl)+accelerator_area_tcl(impl)+'check_design > postcheck.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_reference -hierarchy > references.rpt\nreport_qor > qor.rpt\nreport_clock > clocks.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite_sdc mapped.sdc\n'
    (out/'synth.tcl').write_text(guarded_tcl(synth,'XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED'))
    pt='set_app_var link_path '+libexpr+'\nread_verilog mapped.v\nif {![link_design '+tcl(impl['top'])+']} {error {PT link failed}}\nread_sdc mapped.sdc\n'+clock_contract_checks()+'set_propagated_clock [all_clocks]\nupdate_timing\n'
    pt+=memory_checks(impl)
    pt+='check_timing -verbose > check-timing.rpt\nreport_units > units.rpt\nreport_clock > pt-clocks.rpt\nreport_analysis_coverage -status_details untested > analysis-coverage.rpt\nreport_timing -delay_type max -max_paths 50 -significant_digits 8 > setup.rpt\nreport_timing -delay_type min -max_paths 50 -significant_digits 8 > hold.rpt\nreport_constraint -all_violators > violations.rpt\n'
    pt+='set XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nset XU_CLOCK_REVIEW_DIR clock-reports\nsource clock-review.tcl\n'
    pt+='set xu_f [open timing-slack.tsv w]\nputs $xu_f "delay_type\\tpath_count\\tworst_slack"\nforeach xu_type {max min} {\nset xu_paths [get_timing_paths -delay_type $xu_type -max_paths 1]\nif {[sizeof_collection $xu_paths] != 1} {error "no $xu_type timing path"}\nputs $xu_f "$xu_type\\t[sizeof_collection $xu_paths]\\t[get_attribute $xu_paths slack]"\n}\nclose $xu_f\n'
    (out/'sta.tcl').write_text(guarded_tcl(pt,'XU_SOC_STA_COMPLETE_NOT_QUALIFIED'))
    (out/'rtl.f').write_text('\n'.join(str(p) for p in inputs)+'\n')
    manifest=dict(schema='xu-full-soc-ppa-prepared-v1',status='PREPARED_NOT_QUALIFIED',inventory=inv,implementation=impl,
                  producer_sha256=sha(__file__),
                  mapping_proof=proof,clock_review=review,source_files=origin,
                  allow_unqualified_mapping=allow_unqualified,qualification_gaps=gaps,
                  input_manifest_sha256=digest(origin),
                  tools={x:shutil.which(x) for x in ['dc_shell','pt_shell']},
                  generated_sha256={p.name:sha(p) for p in [out/'synth.tcl',out/'sta.tcl',out/'constraints.sdc',out/'clock-review.tcl',out/'rtl.f']},
                  limitations=['pre-layout RC/SPEF absent unless separately supplied',
                               'source capacity/proof gates and macro counts do not prove timing closure or complete power coverage',
                               'no official score or qualified result until numerical/timing/energy gates pass'])
    if impl.get('hardware_profile') in S3_PROFILES:
        manifest['formality_guidance']=dict(status='CAPTURE_ON_NEW_DC_RUN',
            svf_path=str(out.resolve()/'default.svf'),synthesis_script_sha256=sha(out/'synth.tcl'))
    if impl.get('hardware_profile') is not None:
        check_s3_worktree_freeze(impl, inv)
    write(out/'prepared.json',manifest)
    return manifest


def run_tool(out, command, label, env):
    log=out/(label+'.log')
    require(not log.exists(), 'refuse existing run log: '+str(log))
    with log.open('x') as stream:
        stream.write(json.dumps(command)+'\n');stream.flush()
        result=subprocess.run(command,cwd=str(out),env=env,stdin=subprocess.DEVNULL,
                              stdout=stream,stderr=subprocess.STDOUT,timeout=21600)
    text=log.read_text(errors='replace')
    errors=re.findall(r'^\s*(?:Error(?:\s|:)|Fatal:|FATAL:|XU_FATAL:).*$',text,re.M)
    require(result.returncode==0 and not errors,'EDA execution failed: '+label+' '+str(errors))
    markers={'dc':'XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED',
             'pt-sta':'XU_SOC_STA_COMPLETE_NOT_QUALIFIED',
             'pt-power':'XU_SOC_POWER_COMPLETE_NOT_QUALIFIED'}
    marker=markers.get(label,markers['pt-power'] if label.startswith('pt-power-') else None)
    require(marker is not None and re.findall(r'^('+re.escape(marker)+r')[ \t]*$',text,re.M)==[marker],
            'EDA completion marker missing/duplicated: '+label)
    return dict(returncode=result.returncode,log_sha256=sha(log),scope='tool execution only; reports require coverage/hold/setup assessment')


def timing_execution_review(out):
    # This is a fail-closed *execution* review. Coverage is deliberately left
    # for a real report review; zero worst path slack does not prove no missing
    # clocks, no untested checks, recovery/removal safety, or PVT qualification.
    required=['check-timing.rpt','units.rpt','pt-clocks.rpt','analysis-coverage.rpt',
              'setup.rpt','hold.rpt','violations.rpt','timing-slack.tsv',
              'clock-reports/clock_endpoints.tsv','clock-reports/review_status.txt']
    for name in required:
        require((out/name).is_file() and (out/name).stat().st_size>0,'missing/empty STA report: '+name)
    rows=(out/'timing-slack.tsv').read_text().strip().splitlines()
    require(rows[0]=='delay_type\tpath_count\tworst_slack' and len(rows)==3,'invalid timing summary')
    slacks={}
    for row in rows[1:]:
        fields=row.split('\t')
        require(len(fields)==3 and fields[0] in ['max','min'] and fields[1]=='1','invalid timing path count')
        slack=float(fields[2]);require(math.isfinite(slack),'nonfinite timing slack')
        require(fields[0] not in slacks,'duplicate timing delay type')
        slacks[fields[0]]=slack
    require(set(slacks)=={'max','min'},'both setup and hold summaries required')
    status=(out/'clock-reports/review_status.txt').read_text()
    missing=re.search(r'^NO_CLOCK_ENDPOINTS=(\d+)\s*$',status,re.M)
    failures=re.search(r'^REPORT_COMMAND_FAILURES=(.*)$',status,re.M)
    require(missing and failures,'clock endpoint/report status is incomplete')
    violations=[]
    if slacks['max']<0:violations.append('setup_slack_negative')
    if slacks['min']<0:violations.append('hold_slack_negative')
    if int(missing[1]):violations.append('no_clock_endpoints')
    if failures[1].strip():violations.append('report_command_failures')
    return dict(status='VIOLATIONS_OR_MISSING_REPORTS' if violations else 'REPORT_REVIEW_REQUIRED',
                worst_slack_in_report_time_units=slacks,observed_issues=violations,
                qualification='NOT_QUALIFIED',
                pending='Inspect untested/check_timing/constraints, every endpoint/clock and recovery/removal/gating/pulse-width, exceptions, library units/corners, mapped equivalence, and all mapping qualification gaps')


def verify_prepared(root,out,manifest):
    require(manifest.get('producer_sha256')==sha(__file__),'PPA preparation tool changed; prepare a fresh candidate')
    for relative,record in manifest['source_files'].items():
        require(sha(out/relative)==record['sha256'],'prepared source changed: '+relative)
    for name,value in manifest['generated_sha256'].items():
        require(sha(out/name)==value,'generated control changed: '+name)
    impl = manifest['implementation']
    if impl.get('hardware_profile') in S3_PROFILES:
        require(manifest.get('formality_guidance') == dict(status='CAPTURE_ON_NEW_DC_RUN',
                svf_path=str(out.resolve()/'default.svf'),synthesis_script_sha256=sha(out/'synth.tcl')),
                'S3 Formality guidance capture identity differs; prepare a fresh candidate')
    checked_implementation(impl,inventory(root, impl.get('hardware_profile')),manifest.get('allow_unqualified_mapping',False))


def activity_power(out, record, env):
    prepared=json.loads((out/'prepared.json').read_text());impl=prepared['implementation']
    profile = impl.get('hardware_profile')
    hardware_profile(profile)
    words_per_task = 50688
    if profile is not None:
        expected_work = s3_transaction_contract(prepared['inventory']['root'], impl.get('firmware_schedule'))
        require(impl.get('transaction_contract') == expected_work, 'S3 firmware schedule/transaction contract differs')
        words_per_task = expected_work['shared_writes']
    execution=json.loads((out/'execution.json').read_text())
    require(execution.get('status')=='EXECUTED_NOT_QUALIFIED','DC/PT execution must complete before power')
    vcd=absolute_file(record.get('vcd'),'VCD')
    resultpath=absolute_file(record.get('result'),'whole-SoC numerical result')
    logpath=absolute_file(record.get('simulation_log'),'whole-SoC simulation log')
    result=json.loads(resultpath.read_text());log=logpath.read_text(errors='replace')
    if profile is not None:
        require(result.get('firmware_schedule') == impl['firmware_schedule'] and
                result.get('transaction_contract') == impl['transaction_contract'],
                'S3 activity result firmware schedule/transaction contract differs')
        require((result.get('firmware_build') or {}).get('configuration', {}).get('schedule') == impl['firmware_schedule'],
                'S3 compiled firmware schedule differs from measured work')
    require(result.get('status')=='PASS' and result.get('tasks')==12 and result.get('outputs')==304128 and result.get('write_words')==12*words_per_task,
            'activity must accompany complete twelve-task numerical verification')
    require(record.get('mapping_sha256')==digest(dict(replacements=impl['replacements'],added_sources=impl['added_sources'])), 'activity mapping source differs')
    require(record.get('source_manifest_sha256')==prepared['input_manifest_sha256'],'activity full source manifest differs')
    require(record.get('netlist_sha256')==sha(out/'mapped.v')==execution.get('netlist_sha256') and
            record.get('sdc_sha256')==sha(out/'mapped.sdc')==execution.get('sdc_sha256'),'activity netlist/SDC identity differs')
    require(not re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout|^\s*Error(?:\s|:)',log,re.I|re.M),'activity simulation log reports failure')
    layers=result.get('layers',[])
    require([r.get('layer') for r in layers]==list(range(12)),'all twelve distinct layers required')
    tasks=re.findall(r'^TASK_PASS layer=(\d+) outputs=25344 writes='+str(words_per_task)+r' cycles=(\d+) firmware_cycles=(\d+)$',log,re.M)
    require([(int(a),int(b),int(c)) for a,b,c in tasks]==[(x['layer'],x['cycles'],x['firmware_cycles']) for x in layers], 'raw numerical log/result differ')
    require(re.findall(r'^SOC_PASS.*$',log,re.M)==['SOC_PASS tasks=12 outputs=304128 writes='+str(12*words_per_task)],'missing full numerical SoC completion')
    require(result.get('log_sha256',{}).get('simulation.log')==sha(logpath), 'simulation log SHA differs')
    windows=record.get('windows_ns',[])
    require(len(windows)==12 and all(isinstance(x,list) and len(x)==2 for x in windows),'twelve measured activity windows required')
    if profile is not None:
        s3_activity_windows(impl, record, layers)
    else:
        last=-1.0
        for index,pair in enumerate(windows):
            begin,end=pair
            require(all(type(t) in [int,float] and math.isfinite(t) for t in pair) and 0<=begin<end and begin>last,'invalid/overlapping ns windows')
            require(abs((end-begin)-(layers[index]['cycles']-1)*(20/3))<=.03,
                    'window must span first-input to final-response edges at150MHz')
            last=end
        require(record.get('clock_period_ns')==20/3, 'wrong legacy clock period')
    require(record.get('scope')=='full-digital-soc-including-all-srams', 'incomplete activity scope')
    required_scopes = {'cpu','accelerator','interconnect','shared','itcm','dtcm'}
    if profile is not None:
        require(record.get('hardware_profile') == profile, 'S3 activity hardware profile differs')
        required_scopes.update(('nice_extension', 'accelerator_weights'))
        if profile == 's3-y32-bias-sram':
            required_scopes.add('accelerator_bias')
    require(set(record.get('scope_paths',{}))==required_scopes and
            all(isinstance(x,str) and x for x in record['scope_paths'].values()),'all full-power activity scopes required')
    strip=record.get('strip_path')
    require(isinstance(strip,str) and strip and 'u_accel' not in strip,'wrapper-only strip_path cannot qualify full-scope power')
    if profile is not None:
        config = hardware_profile(profile)
        expected = {'nice_extension': config['retained']['nice'][0],
                    'accelerator_weights': config['scopes']['accelerator_weights'][:-2]}
        if profile == 's3-y32-bias-sram':
            expected['accelerator_bias'] = config['scopes']['accelerator_bias'][:-2]
        require(all(record['scope_paths'][name] == strip+'/'+path for name, path in expected.items()),
                'S3 NICE/W/bias activity scope differs from retained full-SoC hierarchy')
    require(not (out/'power-run.json').exists() and not (out/'activity-input.json').exists(),'refuse existing power run')
    _,libs=library_paths(impl)
    common='set_app_var link_path [list * '+' '.join(tcl(x) for x in libs)+']\nset_app_var power_enable_analysis true\nset_app_var power_analysis_mode averaged\nread_verilog mapped.v\nif {![link_design '+tcl(impl['top'])+']} {error {PT power link failed}}\nread_sdc mapped.sdc\n'+clock_contract_checks()+'set_propagated_clock [all_clocks]\nupdate_timing\n'
    common+=memory_checks(impl)
    # Each process reads exactly one start/end pair, so all activity state and
    # probability propagation are independent across the twelve task windows.
    scripts=[]
    for index,pair in enumerate(windows):
        prefix='task-%02d'%index
        body=common+'read_vcd -rtl -strip_path '+tcl(strip)+' -time [list '+' '.join(str(x) for x in pair)+'] '+tcl(vcd)+'\n'
        body+='report_switching_activity > '+prefix+'-switching-before.rpt\nupdate_power\nreport_switching_activity > '+prefix+'-switching-after.rpt\nreport_switching_activity -list_not_annotated > '+prefix+'-unannotated.rpt\nreport_power > '+prefix+'-power.rpt\nreport_power -hierarchy > '+prefix+'-power-hierarchy.rpt\nreport_units > '+prefix+'-units.rpt\n'
        script=out/(prefix+'-power.tcl');require(not script.exists(),'power script exists')
        script.write_text(guarded_tcl(body,'XU_SOC_POWER_COMPLETE_NOT_QUALIFIED'));scripts.append(script)
    write(out/'activity-input.json',record)
    receipt=dict(schema='xu-full-soc-power-execution-v1',status='RUNNING_NOT_QUALIFIED',tasks=[],
                 activity_sha256=digest(record),method='twelve independent averaged PT windows; no mean-power or energy claim',
                 pending='Every task needs annotation propagation/default review and all SRAM power coverage, then sum(P_task*duration_task) via xu_soc_activity.py energy')
    write(out/'power-run.json',receipt)
    try:
        for index,script in enumerate(scripts):
            result=run_tool(out,['pt_shell','-f',script.name],'pt-power-%02d'%index,env)
            reports=sorted(out.glob('task-%02d-*.rpt'%index))
            require(len(reports)==6 and all(x.stat().st_size>0 for x in reports),'missing/empty per-task power report')
            receipt['tasks'].append(dict(task=index,window_ns=windows[index],execution=result,
                                         script_sha256=sha(script),reports={p.name:sha(p) for p in reports}))
            write(out/'power-run.json',receipt)
        receipt['status']='EXECUTED_NOT_QUALIFIED'
    except Exception as exc:
        receipt.update(status='FAIL',error=str(exc));write(out/'power-run.json',receipt);raise
    write(out/'power-run.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['inventory','review-template','prepare','run','power'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--implementation',type=Path)
    p.add_argument('--activity',type=Path)
    p.add_argument('--hardware-profile',choices=S3_PROFILES,
                   help='explicit S3 inventory only; prepare/run/power use the manifest profile')
    p.add_argument('--allow-unqualified-mapping',action='store_true',help='allow development PPA with real missing proof statuses; never qualifies the design')
    p.add_argument('--lc-root',type=Path,default=Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
    a=p.parse_args();out=a.out.resolve();root=a.root.resolve()
    require(a.hardware_profile is None or a.action=='inventory', '--hardware-profile is only valid for inventory')
    if a.action=='inventory':
        require(not out.exists(),'inventory output exists');out.mkdir(parents=True)
        inv=inventory(root,a.hardware_profile);write(out/'inventory.json',inv);write(out/'implementation-template.json',template(inv));print('INVENTORIED_NOT_QUALIFIED '+str(out));return 0
    if a.action=='review-template':
        require(a.implementation is not None,'--implementation required')
        require(not out.exists(),'review output exists');out.mkdir(parents=True)
        write(out/'mapping-proof-template.json',mapping_review_template(json.loads(a.implementation.read_text())))
        print('UNREVIEWED_MAPPING_TEMPLATE '+str(out));return 0
    if a.action=='prepare':
        require(a.implementation is not None,'--implementation required');prepare(root,out,json.loads(a.implementation.read_text()),a.allow_unqualified_mapping);print('PREPARED_NOT_QUALIFIED '+str(out));return 0
    require((out/'prepared.json').is_file(),'prepare first')
    manifest=json.loads((out/'prepared.json').read_text())
    verify_prepared(root,out,manifest)
    env=dict(os.environ,SYNOPSYS_LC_ROOT=str(a.lc_root));env['PATH']=str(a.lc_root/'bin')+os.pathsep+env.get('PATH','')
    if a.action=='run':
        if manifest['implementation'].get('hardware_profile') in S3_PROFILES:
            receipt=out/'execution.json'
            require(not receipt.exists() and not receipt.is_symlink(),'refuse existing S3 execution receipt: '+str(receipt))
        run=dict(schema='xu-full-soc-ppa-execution-v1',status='RUNNING_NOT_QUALIFIED',started_utc=datetime.now(timezone.utc).isoformat())
        write(out/'execution.json',run)
        try:
            if manifest['implementation'].get('hardware_profile') in S3_PROFILES:
                svf=out/'default.svf'
                require(not svf.exists() and not svf.is_symlink(),'refuse existing S3 synthesis SVF: '+str(svf))
            run['dc']=run_tool(out,['dc_shell','-f','synth.tcl'],'dc',env)
            if manifest['implementation'].get('hardware_profile') in S3_PROFILES:
                require(svf.is_file() and not svf.is_symlink() and svf.stat().st_size>0,
                        'missing/nonregular/empty S3 synthesis SVF: '+str(svf))
                run['formality_guidance']=dict(path=str(svf),sha256=sha(svf),bytes=svf.stat().st_size,
                    dc_log_sha256=sha(out/'dc.log'),synthesis_script_sha256=sha(out/'synth.tcl'),
                    prepared_input_manifest_sha256=manifest['input_manifest_sha256'],
                    scope='same DC run synthesis guidance only; not an equivalence proof')
                write(out/'execution.json',run)
            require((out/'mapped.v').is_file() and (out/'mapped.sdc').is_file(),'DC mapped outputs missing')
            run['pt']=run_tool(out,['pt_shell','-f','sta.tcl'],'pt-sta',env)
            verify_prepared(root,out,manifest)
            run.update(status='EXECUTED_NOT_QUALIFIED',netlist_sha256=sha(out/'mapped.v'),sdc_sha256=sha(out/'mapped.sdc'),
                       timing_review=timing_execution_review(out),qualification_gaps=manifest.get('qualification_gaps',[]))
        except Exception as exc:
            run.update(status='FAIL',error=str(exc));write(out/'execution.json',run);raise
        run['reports']={str(x.relative_to(out)):dict(sha256=sha(x),bytes=x.stat().st_size)
                        for x in out.rglob('*') if x.is_file() and x.suffix in ['.rpt','.tsv','.txt']}
        write(out/'execution.json',run);print('EXECUTED_NOT_QUALIFIED '+str(out));return 0
    require(a.activity is not None,'--activity required')
    activity_power(out,json.loads(a.activity.read_text()),env);verify_prepared(root,out,manifest);print('POWER_EXECUTED_NOT_QUALIFIED '+str(out));return 0

if __name__=='__main__':
    try:
        sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr);sys.exit(1)
