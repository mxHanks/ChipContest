#!/usr/bin/env python3
"""Inventory and prepare explicit full-digital-SoC PPA; never substitute absent RAM by zero.

Python 3.6+; inventory needs only Git. prepare accepts independently validated memory
implementations and a top joining the fixed E203 SoC to its 512 KiB ICB RAM. Running
EDA is explicit. Generated DC/PT scripts reject missing macros and unresolved designs.
A successful tool invocation is not a timing, activity-coverage, or contest pass.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SUB = 'third-party/e203_hbirdv2'
RTL = SUB + '/rtl/e203'
FROZEN_E203 = 'f49a5fc914971426bd4530db39e270a84b41139f'
SOURCE_PROFILES = {
    'baseline': dict(commit=FROZEN_E203, changed_files=[]),
    'h2-only': dict(commit='434628c1525931c15dfaf06b5586118eb530ccba', changed_files=[
        'rtl/e203/perips/LinearCachedCore.sv', 'rtl/e203/perips/accel_icb_slave.v']),
    'sram-bias': dict(commit='eee41507965d562066af3335192e3ef93ef36d31', changed_files=[
        'rtl/e203/perips/BiasSramCache.sv', 'rtl/e203/perips/LinearSramCachedCore.sv',
        'rtl/e203/perips/accel_icb_slave.v', 'rtl/e203/perips/mem_32x40.sv']),
    's2b-packed': dict(commit='d5faa5e8c857fa35df62a68de667bdb8a6e954f7', changed_files=[
        'rtl/e203/perips/accel_icb_slave.v']),
    's2c-autogroup': dict(commit='49a9436e01ea8ceeead94242e4a99c16e31a0865', changed_files=[
        'rtl/e203/perips/LinearAutoGroupCore.sv', 'rtl/e203/perips/accel_icb_slave.v']),
    's2e-paired-hi': dict(commit='a0767db69628ef30e53de2d1e93dd0360c0ccf76', changed_files=[
        'rtl/e203/perips/LinearAutoGroupCore.sv', 'rtl/e203/perips/accel_icb_slave.v']),
    's2d-doublebuf': dict(commit='dd692c190dadafd9baa6dffe8514a3f684e7fbf5', changed_files=[
        'rtl/e203/perips/LinearAutoGroupCore.sv', 'rtl/e203/perips/LinearBufferedComputeCore.sv',
        'rtl/e203/perips/LinearDoubleBufferCore.sv', 'rtl/e203/perips/accel_icb_slave.v']),
    's3-pe32': dict(commit='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5', changed_files=[
        'rtl/e203/perips/LinearAutoGroupCore.sv',
        'rtl/e203/perips/XuParallelAutoGroupCore32.sv',
        'rtl/e203/perips/XuParallelBiasCache32.sv',
        'rtl/e203/perips/XuParallelComputeCore32.sv',
        'rtl/e203/perips/XuParallelWeightBank32.sv',
        'rtl/e203/perips/accel_icb_slave.v', 'rtl/e203/perips/xu_pe32_icb_slave.v',
        'rtl/e203/subsys/e203_subsys_perips.v', 'vsim/bin/run.makefile']),
    's3-pe64': dict(commit='7aae96776e116d5e95d6ebb49d29a5fccce04ab9', changed_files=[
        'rtl/e203/perips/LinearAutoGroupCore.sv',
        'rtl/e203/perips/XuParallelAutoGroupCore32.sv', 'rtl/e203/perips/XuParallelAutoGroupCore64.sv',
        'rtl/e203/perips/XuParallelBiasCache32.sv', 'rtl/e203/perips/XuParallelBiasCache64.sv',
        'rtl/e203/perips/XuParallelComputeCore32.sv', 'rtl/e203/perips/XuParallelComputeCore64.sv',
        'rtl/e203/perips/XuParallelWeightBank32.sv', 'rtl/e203/perips/XuParallelWeightBank64.sv',
        'rtl/e203/perips/accel_icb_slave.v', 'rtl/e203/perips/xu_pe32_icb_slave.v',
        'rtl/e203/perips/xu_pe64_icb_slave.v', 'rtl/e203/subsys/e203_subsys_perips.v', 'vsim/bin/run.makefile']),
    's3-pe32-bank128': dict(commit='52cfbea1f79f10e44f7d1696f54015797f886b96', changed_files=[
        'rtl/e203/perips/LinearAutoGroupCore.sv', 'rtl/e203/perips/Sram128x16.sv',
        'rtl/e203/perips/XuParallelAutoGroupCore32.sv', 'rtl/e203/perips/XuParallelAutoGroupCore32Bank128.sv',
        'rtl/e203/perips/XuParallelBiasCache32.sv',
        'rtl/e203/perips/XuParallelComputeCore32.sv', 'rtl/e203/perips/XuParallelComputeCore32Bank128.sv',
        'rtl/e203/perips/XuParallelWeightBank32.sv', 'rtl/e203/perips/XuParallelWeightBank32Bank128.sv',
        'rtl/e203/perips/accel_icb_slave.v', 'rtl/e203/perips/mem_128x16.sv',
        'rtl/e203/perips/xu_pe32_bank128_icb_slave.v', 'rtl/e203/perips/xu_pe32_icb_slave.v',
        'rtl/e203/subsys/e203_subsys_perips.v', 'vsim/bin/run.makefile']),
}
BIAS_MEMORY = RTL+'/perips/mem_32x40.sv'
BIAS_ADAPTER_SHA256 = '019f86f6acc3bdf0e3d2678de1b90540deac1ec50850c010d0263e3d2231c2fd'
BANK128_MEMORY = RTL+'/perips/mem_128x16.sv'
BANK128_ADAPTER_SHA256 = '13e1077201f8eb751d34eee718b34d350cc5dfbc58cf0d853933b010c29faa79'
S2E_MAIN_COMMIT = '5bf123bfead8f2a37f97f3234d4e40ce8201aae9'
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
BIAS_GROUP = dict(name='accelerator_bias', logical_bits=8*32*40,
                  instance_pattern=MAIN+'/u_e203_subsys_perips/u_accel_icb_slave/u_linear_compute_core/cache/*',
                  macro_ref='RAMSP128X16', depth=128, width=16, count=24,
                  logical_banks=8, logical_depth=32, logical_width=40, width_lanes=3,
                  physical_bits=24*128*16, padding_bits=24*128*16-8*32*40)
RETAINED = {'cpu': (MAIN+'/u_e203_cpu_top', 'e203_cpu_top*'),
            'accelerator': (MAIN+'/u_e203_subsys_perips/u_accel_icb_slave', 'accel_icb_slave*'),
            'interconnect': (MAIN+'/u_e203_subsys_perips/u_sirv_ppi_fab', 'sirv_icb1to16_bus*')}
PE32_MAIN_COMMIT = '94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114'
PE32_DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_ACCEL_PE32=1']
PE32_CONFIGURATION = dict(accel_variant='pe32', physical_pes=32, wrapper_reference='xu_pe32_icb_slave',
                          logical_weight_bytes=32768, logical_weight_banks=32,
                          logical_weight_depth=512, weight_word_bits=16,
                          weight_macros=32, physical_weight_depth=1024,
                          physical_weight_bytes=65536, weight_padding_bytes=32768,
                          fixed_soc_macros=320, full_soc_macros=352)
PE32_WEIGHT_GROUP = dict(name='accelerator_weights', logical_bits=32768*8,
                         instance_pattern=MAIN+'/u_e203_subsys_perips/u_accel_icb_slave/u_linear_compute_core/core/banks_*',
                         macro_ref='RAMSP1024X16', depth=1024, width=16, count=32,
                         logical_banks=32, logical_depth=512, logical_width=16,
                         physical_bits=65536*8, padding_bits=32768*8)


PE64_MAIN_COMMIT = '3443fad8945577626d226b1cd53eadec89331a20'
PE64_DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_ACCEL_PE64=1']
PE64_CONFIGURATION = dict(accel_variant='pe64', physical_pes=64, wrapper_reference='xu_pe64_icb_slave',
                          logical_weight_bytes=32768, logical_weight_banks=64,
                          logical_weight_depth=256, weight_word_bits=16,
                          weight_macros=64, physical_weight_depth=1024,
                          physical_weight_bytes=131072, weight_padding_bytes=98304,
                          fixed_soc_macros=320, full_soc_macros=384)
PE64_WEIGHT_GROUP = dict(name='accelerator_weights', logical_bits=32768*8,
                         instance_pattern=MAIN+'/u_e203_subsys_perips/u_accel_icb_slave/u_linear_compute_core/core/banks_*',
                         macro_ref='RAMSP1024X16', depth=1024, width=16, count=64,
                         logical_banks=64, logical_depth=256, logical_width=16,
                         physical_bits=131072*8, padding_bits=98304*8)

BANK128_MAIN_COMMIT = 'f75880d4f06ccb7f1c16115bee501f53d9a2abb7'
BANK128_DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_ACCEL_PE32=1', 'XU_ACCEL_PE32_BANK128=1']
BANK128_CONFIGURATION = dict(accel_variant='pe32-bank128', physical_pes=32,
    wrapper_reference='xu_pe32_bank128_icb_slave', logical_weight_bytes=32768,
    logical_weight_banks=32, logical_weight_depth=512, weight_word_bits=16,
    weight_macros=128, weight_depth_slices=4, physical_weight_depth=128,
    physical_weight_bytes=32768, weight_padding_bytes=0, read_latency_cycles=1,
    single_rw=True, fixed_soc_macros=320, full_soc_macros=448)
BANK128_WEIGHT_GROUP = dict(name='accelerator_weights', logical_bits=32768*8,
    instance_pattern=MAIN+'/u_e203_subsys_perips/u_accel_icb_slave/u_linear_compute_core/core/banks_*',
    macro_ref='RAMSP128X16', depth=128, width=16, count=128,
    logical_banks=32, logical_depth=512, logical_width=16, depth_slices=4,
    read_latency_cycles=1, single_rw=True, physical_bits=32768*8, padding_bits=0)


def retained_instances(profile):
    retained = dict(RETAINED)
    if profile == 's3-pe32':
        retained['accelerator'] = (RETAINED['accelerator'][0], 'xu_pe32_icb_slave*')
    if profile == 's3-pe64':
        retained['accelerator'] = (RETAINED['accelerator'][0], 'xu_pe64_icb_slave*')
    if profile == 's3-pe32-bank128':
        retained['accelerator'] = (RETAINED['accelerator'][0], 'xu_pe32_bank128_icb_slave*')
    return retained


def mapping_identity(impl):
    identity = dict(replacements=impl['replacements'], added_sources=impl['added_sources'])
    if impl.get('source_profile') in ('s3-pe32', 's3-pe64', 's3-pe32-bank128'):
        identity.update(source_profile=impl['source_profile'], defines=impl['defines'],
                        accelerator_configuration=impl['accelerator_configuration'],
                        source_freeze=impl.get('source_freeze', {}))
    return identity

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
    return subprocess.check_output(['git','--no-replace-objects']+list(args), cwd=str(root)).decode().strip()


def parallel_main_identity(root, profile, approved_main, label):
    """Bind an approved parallel candidate main worktree to its approved Git objects, not the index.

    The original profile checked the main HEAD only. Git index flags can hide
    changed TB/runner/firmware bytes from status, while a replacement object can
    present another tree under the same commit name. Read the original objects
    and check every actual tracked blob, mode, symlink and gitlink instead.
    """
    root = Path(root)
    require(not root.is_symlink(), label+' main source root is a symlink')
    require(git(root, 'rev-parse', 'HEAD') == approved_main,
            label+' main commit differs from the approved pin')
    output = subprocess.check_output(
        ['git', '--no-replace-objects', 'ls-tree', '-rz', approved_main], cwd=str(root))
    selected = {}
    for entry in output.split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode('ascii').split()
        selected[os.fsdecode(name)] = (mode, kind, oid)
    require({name for name, value in selected.items() if value[1] == 'commit'} == {SUB},
            label+' main gitlink set differs from the approved single E203 child')
    worktree = {}
    for name, (mode, kind, oid) in selected.items():
        path = root / name
        # A symlinked directory can otherwise redirect regular tracked files
        # outside the frozen tree without changing the leaf's bytes or mode.
        require(all(not (root / Path(*Path(name).parts[:index])).is_symlink()
                    for index in range(1, len(Path(name).parts))),
                label+' main source parent is a symlink: ' + name)
        if kind == 'commit':
            require(mode == '160000' and name == SUB and oid == SOURCE_PROFILES[profile]['commit'],
                    label+' main approved child gitlink differs: ' + name)
            require(path.is_dir() and not path.is_symlink() and git(path, 'rev-parse', 'HEAD') == oid,
                    label+' main actual child gitlink differs: ' + name)
            worktree[name] = dict(mode=mode, commit=oid)
            continue
        require(kind == 'blob', 'unsupported '+label+' main tree entry: ' + name)
        if mode == '120000':
            require(path.is_symlink(), label+' main tree symlink changed: ' + name)
            content = os.fsencode(os.readlink(str(path)))
        else:
            require(path.is_file() and not path.is_symlink(), label+' main tree file missing/changed: ' + name)
            require(mode in ['100644', '100755'] and bool(path.stat().st_mode & 0o111) == (mode == '100755'),
                    label+' main tree file mode changed: ' + name)
            content = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(content)).encode('ascii') + b'\0' + content).hexdigest()
        require(blob == oid, label+' main tree worktree bytes differ from approved pin: ' + name)
        worktree[name] = dict(mode=mode, sha256=hashlib.sha256(content).hexdigest())
    # These are the main-repository namespaces from which the candidate's
    # source, firmware, TB, vectors and runner can be discovered. Include
    # ignored files: .gitignore is not a source-freeze exemption. Build/report
    # output directories and bytecode caches do not become source inputs.
    untracked = []
    for options in [[], ['--ignored']]:
        output = subprocess.check_output(
            ['git', '--no-replace-objects', 'ls-files', '--others', '-z', '--exclude-standard'] + options,
            cwd=str(root))
        untracked += [os.fsdecode(name) for name in output.split(b'\0') if name]
    active_roots = {'src', 'tools', 'tests', 'model'}
    source_suffixes = {'.scala', '.sbt', '.v', '.sv', '.vh', '.svh', '.py', '.c', '.h', '.sh', '.mk'}
    extras = []
    for name in sorted(set(untracked)):
        relative = Path(name)
        bytecode = '__pycache__' in relative.parts and relative.suffix in {'.pyc', '.pyo'}
        if not bytecode and (relative.parts[0] in active_roots or
                             len(relative.parts) == 1 and relative.suffix in source_suffixes):
            extras.append(name)
    require(not extras, label+' main untracked active source files: ' + ', '.join(extras))
    return dict(main_commit=approved_main, approved_main_tree=git(root, 'rev-parse', approved_main + '^{tree}'),
                tracked_main_entries=len(selected), actual_main_tree_manifest_sha256=digest(worktree))


def pe32_main_identity(root):
    return parallel_main_identity(root, 's3-pe32', PE32_MAIN_COMMIT, 'PE32')


def pe64_main_identity(root):
    return parallel_main_identity(root, 's3-pe64', PE64_MAIN_COMMIT, 'PE64')


def bank128_main_identity(root):
    return parallel_main_identity(root, 's3-pe32-bank128', BANK128_MAIN_COMMIT, 'BANK128')

def s2e_main_identity(root):
    return parallel_main_identity(root, 's2e-paired-hi', S2E_MAIN_COMMIT, 'S2E')

def source_profile_identity(root, profile='baseline'):
    """Check approved commit, its complete delta, and actual child worktree bytes.

    Checking Git object trees also covers fixed files outside the source-level
    hierarchy regexes. Hash every tracked worktree file independently of index
    flags; ignored/untracked RTL files cannot enter inventory unnoticed.
    """
    require(profile in SOURCE_PROFILES, 'unknown source profile: '+str(profile))
    child=Path(root)/SUB
    approved=SOURCE_PROFILES[profile]
    actual=git(child,'rev-parse','HEAD')
    require(actual==approved['commit'], 'E203 child commit differs from approved '+profile+' pin')
    def tree(commit):
        output=subprocess.check_output(['git','--no-replace-objects','ls-tree','-rz',commit],cwd=str(child))
        records={}
        for entry in output.split(b'\0'):
            if not entry:continue
            metadata,name=entry.split(b'\t',1)
            mode,kind,oid=metadata.decode('ascii').split()
            records[os.fsdecode(name)]=(mode,kind,oid)
        return records
    baseline=tree(FROZEN_E203);selected=tree(actual)
    changed=sorted(name for name in set(baseline)|set(selected) if baseline.get(name)!=selected.get(name))
    require(changed==sorted(approved['changed_files']), 'approved profile changes files outside its exact fixed-platform delta')
    worktree={}
    for name,(mode,kind,oid) in selected.items():
        path=child/name
        require(kind=='blob', 'unsupported child tree entry: '+name)
        if mode=='120000':
            require(path.is_symlink(), 'child tree symlink changed: '+name)
            content=os.fsencode(os.readlink(str(path)))
        else:
            require(path.is_file() and not path.is_symlink(), 'child tree file missing/changed: '+name)
            require(mode in ['100644','100755'] and bool(path.stat().st_mode & 0o111)==(mode=='100755'),
                    'child tree file mode changed: '+name)
            content=path.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(content)).encode('ascii')+b'\0'+content).hexdigest()
        require(blob==oid, 'child tree worktree bytes differ from approved pin: '+name)
        worktree[name]=dict(mode=mode,sha256=hashlib.sha256(content).hexdigest())
    rtl_names={name for name in selected if name.startswith('rtl/e203/')}
    actual_rtl={p.relative_to(child).as_posix() for p in (child/'rtl/e203').rglob('*') if p.is_file() or p.is_symlink()}
    require(actual_rtl==rtl_names, 'untracked/missing fixed-platform RTL files')
    identity = dict(name=profile, baseline_e203_commit=FROZEN_E203, e203_commit=actual,
                baseline_tree=git(child,'rev-parse',FROZEN_E203+'^{tree}'),
                approved_tree=git(child,'rev-parse',actual+'^{tree}'),
                changed_files=changed, fixed_tree_file_count=len(selected)-len(changed),
                actual_child_tree_manifest_sha256=digest(worktree))
    if profile == 's3-pe32':
        identity['main_source_freeze'] = pe32_main_identity(root)
    elif profile == 's3-pe64':
        identity['main_source_freeze'] = pe64_main_identity(root)
    elif profile == 's3-pe32-bank128':
        identity['main_source_freeze'] = bank128_main_identity(root)
    elif profile == 's2e-paired-hi':
        identity['main_source_freeze'] = s2e_main_identity(root)
    return identity


def inventory(root):
    root = Path(root).resolve()
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
    child_commit = git(root/SUB, 'rev-parse', 'HEAD')
    pe32 = child_commit == SOURCE_PROFILES['s3-pe32']['commit']
    pe64 = child_commit == SOURCE_PROFILES['s3-pe64']['commit']
    bank128 = child_commit == SOURCE_PROFILES['s3-pe32-bank128']['commit']
    if pe32:
        sizes['accelerator_weights'].update(
            implementation='32 banks, one mem_1024x16 each; upper512 rows per macro unreachable',
            physical_1024x16_macros=32, logical_banks=32, logical_depth=512,
            physical_depth=1024, physical_bits=65536*8, padding_bits=32768*8)
    if pe64:
        sizes['accelerator_weights'].update(
            implementation='64 banks, one mem_1024x16 each; upper768 rows per macro unreachable',
            physical_1024x16_macros=64, logical_banks=64, logical_depth=256,
            physical_depth=1024, physical_bits=131072*8, padding_bits=98304*8)
    if bank128:
        sizes['accelerator_weights'].update(
            implementation='32 banks, each4 single-RW mem_128x16 depths; sampled return-depth, one-cycle read',
            physical_1024x16_macros=0, physical_128x16_macros=128,
            logical_banks=32, logical_depth=512, depth_slices=4,
            physical_depth=128, physical_bits=32768*8, padding_bits=0)
    arrays = []
    for path in paths:
        text = comments(path.read_text())
        for match in re.finditer(r'\b(reg|wire)\s*(\[[^\]\n]+\])?\s+(\w+)\s*\[([^;\n]+)\]\s*;', text):
            arrays.append(dict(path=path.relative_to(root).as_posix(), kind=match[1],
                               width=match[2], name=match[3], bounds=match[4],
                               note='source-level declaration only; elaboration determines live storage'))
    result = dict(schema='xu-full-soc-source-inventory-v1', status='INVENTORIED_NOT_QUALIFIED',
                created_utc=datetime.now(timezone.utc).isoformat(), root=str(root),
                main_commit=git(root, 'rev-parse', 'HEAD'), e203_commit=child_commit,
                platform_source=source, platform_source_manifest_sha256=digest(source),
                testbench=dict(path=str(tb_path), sha256=sha(tb_path)), memories=sizes,
                total_required_sram_bits=sum(REQUIRED_BITS.values()),
                hypothetical_1024x16_macro_counts={k:v//16384 for k,v in REQUIRED_BITS.items()},
                hypothetical_1024x16_macro_total=sum(REQUIRED_BITS.values())//16384,
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
    if pe32:
        result.update(source_profile='s3-pe32', accelerator_configuration=dict(PE32_CONFIGURATION),
                      required_compile_defines=list(PE32_DEFINES),
                      total_physical_sram_bits=352*1024*16,
                      hypothetical_1024x16_macro_counts=dict(itcm=32, dtcm=32, shared=256, accelerator_weights=32),
                      hypothetical_1024x16_macro_total=352)
    if pe64:
        result.update(source_profile='s3-pe64', accelerator_configuration=dict(PE64_CONFIGURATION),
                      required_compile_defines=list(PE64_DEFINES),
                      total_physical_sram_bits=384*1024*16,
                      hypothetical_1024x16_macro_counts=dict(itcm=32, dtcm=32, shared=256, accelerator_weights=64),
                      hypothetical_1024x16_macro_total=384)
    if bank128:
        result.update(source_profile='s3-pe32-bank128', accelerator_configuration=dict(BANK128_CONFIGURATION),
            required_compile_defines=list(BANK128_DEFINES), total_physical_sram_bits=320*1024*16+128*128*16,
            hypothetical_1024x16_macro_counts=dict(itcm=32,dtcm=32,shared=256,accelerator_weights=0),
            hypothetical_1024x16_macro_total=320, hypothetical_128x16_macro_counts=dict(accelerator_weights=128),
            hypothetical_128x16_macro_total=128, hypothetical_total_macros=448,
            expected_macro_counts_by_reference={'RAMSP1024X16':320,'RAMSP128X16':128})
    return result


def template(inv, profile='baseline'):
    require(profile in SOURCE_PROFILES, 'unknown source profile: '+str(profile))
    replacements=REPLACEABLE|({BIAS_MEMORY} if profile=='sram-bias' else set())
    if profile == 's3-pe32-bank128':
        replacements = replacements | {BANK128_MEMORY}
    result = dict(schema='xu-full-soc-implementation-v1', top='xu_soc_ppa_top',
                source_profile=profile,
                platform_source_manifest_sha256=inv['platform_source_manifest_sha256'],
                replacements={name:dict(path='/absolute/qualified/replacement/'+Path(name).name, sha256='REQUIRED')
                              for name in sorted(replacements)},
                added_sources=[dict(path='/absolute/qualified/xu_soc_ppa_top.sv', sha256='REQUIRED'),
                               dict(path='/absolute/qualified/xu_shared_icb_sram.sv', sha256='REQUIRED')],
                libraries=[dict(path='/absolute/same-corner/standard_cells.db', sha256='REQUIRED', role='standard_cell'),
                           dict(path='/absolute/same-corner/SRAM.db', sha256='REQUIRED', role='sram')]+
                          ([dict(path='/absolute/same-corner/RAMSP128X16.db', sha256='REQUIRED', role='bias_sram')]
                           if profile=='sram-bias' else []),
                search_paths=[], defines=['SYNTHESIS', 'DISABLE_SV_ASSERTION=1'],
                constraints=dict(path='/absolute/reviewed/full-soc.sdc', sha256='REQUIRED'),
                memory_groups=[dict(name=name, logical_bits=bits, instance_pattern=MEMORY_SCOPES[name],
                                    macro_ref='RAMSP1024X16', depth=1024, width=16, count=bits//16384)
                               for name,bits in REQUIRED_BITS.items()]+([dict(BIAS_GROUP)] if profile=='sram-bias' else []),
                retained_instances=[dict(name=name,pattern=record[0],reference_pattern=record[1])
                                    for name,record in sorted(retained_instances(profile).items())],
                mapping_proof=dict(path='/absolute/verified/mapping-proof.json', sha256='REQUIRED'),
                clock_review=dict(path='/absolute/reviewed/clock-review.json', sha256='REQUIRED'),
                activity=None,
                note='Fill actual paths/hashes after SRAM-model, byte-mask, timing, bus and whole-SoC functional checks. No defaults qualify.')
    if profile == 's3-pe32':
        result.update(accel_variant='pe32', accelerator_configuration=dict(PE32_CONFIGURATION),
                      defines=list(PE32_DEFINES))
        result['memory_groups'][-1] = dict(PE32_WEIGHT_GROUP)
    if profile == 's3-pe64':
        result.update(accel_variant='pe64', accelerator_configuration=dict(PE64_CONFIGURATION),
                      defines=list(PE64_DEFINES))
        result['memory_groups'][-1] = dict(PE64_WEIGHT_GROUP)
    if profile == 's3-pe32-bank128':
        result.update(accel_variant='pe32-bank128', accelerator_configuration=dict(BANK128_CONFIGURATION),
                      defines=list(BANK128_DEFINES))
        result['memory_groups'][-1] = dict(BANK128_WEIGHT_GROUP)
        result['libraries'].append(dict(path='/absolute/same-corner/RAMSP128X16.db',sha256='REQUIRED',role='weight_sram128'))
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
    require(all(record.get('role') in ['standard_cell','sram','bias_sram','weight_sram128'] for record in libraries),
            'each library needs an explicit standard_cell, sram, bias_sram or weight_sram128 role')
    weight_count=sum(record.get('role')=='weight_sram128' for record in libraries)
    require(weight_count==(1 if impl.get('source_profile')=='s3-pe32-bank128' else 0),
            'exactly one weight_sram128 library is required only for s3-pe32-bank128 profile')
    if impl.get('source_profile') == 's3-pe32-bank128':
        require(sorted(record.get('role') for record in libraries)==['sram','standard_cell','weight_sram128'],
                'bank128 requires exactly one standard, one1024 SRAM and one128 W SRAM library')
    bias_count=sum(record.get('role')=='bias_sram' for record in libraries)
    require(bias_count==(1 if impl.get('source_profile','baseline')=='sram-bias' else 0),
            'exactly one bias_sram library is required only for sram-bias profile')
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
    return dict(schema='xu-full-soc-mapping-review-v1',status='UNREVIEWED',
                mapping_sha256=digest(mapping_identity(impl)),
                checks={name:dict(status='NOT_RUN',log=None,review=None) for name in MAPPING_CHECKS},
                mapped_equivalence=dict(status='NOT_RUN',netlist_sha256=None,log=None),
                note='No prefilled PASS. Whole-SoC RTL mapping checks do not substitute mapped-netlist equivalence or SRAM PVT timing eligibility.')


def checked_implementation(impl, inv, allow_unqualified=False):
    require(impl.get('schema')=='xu-full-soc-implementation-v1', 'implementation schema differs')
    require(impl.get('platform_source_manifest_sha256')==inv['platform_source_manifest_sha256'], 'platform source freeze differs')
    require(impl.get('top')=='xu_soc_ppa_top', 'fixed full-SoC PPA top must be xu_soc_ppa_top')
    profile=impl.get('source_profile','baseline')
    profile_identity=source_profile_identity(inv['root'],profile)
    freeze=impl.get('source_freeze',{})
    if freeze:
        require(freeze.get('profile')==profile_identity, 'source freeze profile differs from actual approved child tree')
        require(freeze.get('e203_commit')==inv['e203_commit'] and freeze.get('main_commit')==inv['main_commit'],
                'source freeze main/child commit differs')
        require(freeze.get('memory_groups_sha256')==digest(impl.get('memory_groups')) and
                freeze.get('libraries_sha256')==digest(impl.get('libraries')),
                'source freeze memory/library configuration differs')
    replaceable=REPLACEABLE|({BIAS_MEMORY} if profile=='sram-bias' else set())
    if profile == 's3-pe32-bank128':
        replaceable = replaceable | {BANK128_MEMORY}
    require(set(impl.get('replacements',{}))==replaceable, 'only exact profile behavioral RAM definitions may be replaced')
    for name,record in impl['replacements'].items():
        absolute_file(record, 'replacement '+name)
    if profile=='sram-bias':
        require(impl['replacements'][BIAS_MEMORY]['sha256']==BIAS_ADAPTER_SHA256,
                'sram-bias requires the exact approved bias SRAM adapter')
    if profile=='s3-pe32-bank128':
        require(impl['replacements'][BANK128_MEMORY]['sha256']==BANK128_ADAPTER_SHA256,
                'bank128 requires the exact approved single-RW W SRAM adapter')
    require(impl.get('added_sources'), 'full-scope top / shared RAM implementation is missing')
    for n,record in enumerate(impl['added_sources']):
        absolute_file(record, 'added source '+str(n))
    library_paths(impl)
    absolute_file(impl.get('constraints'), 'constraints')
    defines=impl.get('defines',[])
    require('SYNTHESIS' in defines and not any('FPGA_SOURCE' in x for x in defines), 'ASIC SYNTHESIS with actual clock gating is required')
    require(all(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(?:=[A-Za-z0-9_]+)?', x) for x in defines), 'invalid defines')
    if profile == 's3-pe32':
        require(inv.get('main_commit') == PE32_MAIN_COMMIT,
                's3-pe32 requires the exact approved candidate main commit')
        require(defines == PE32_DEFINES, 's3-pe32 requires the exact frozen PE32 compile defines')
        require(impl.get('accel_variant') == 'pe32' and
                encoded(impl.get('accelerator_configuration')) == encoded(PE32_CONFIGURATION),
                's3-pe32 accelerator variant/geometry/padding differs')
        require(inv.get('source_profile') == 's3-pe32' and
                encoded(inv.get('accelerator_configuration')) == encoded(PE32_CONFIGURATION),
                's3-pe32 source inventory must describe the same physical variant')
        require(freeze and freeze.get('defines_sha256') == digest(defines) and
                freeze.get('accelerator_configuration_sha256') == digest(PE32_CONFIGURATION),
                's3-pe32 source freeze must bind exact defines and accelerator configuration')
    elif profile == 's3-pe64':
        require(inv.get('main_commit') == PE64_MAIN_COMMIT,
                's3-pe64 requires the exact approved candidate main commit')
        require(defines == PE64_DEFINES, 's3-pe64 requires the exact frozen PE64 compile defines')
        require(impl.get('accel_variant') == 'pe64' and
                encoded(impl.get('accelerator_configuration')) == encoded(PE64_CONFIGURATION),
                's3-pe64 accelerator variant/geometry/padding differs')
        require(inv.get('source_profile') == 's3-pe64' and
                encoded(inv.get('accelerator_configuration')) == encoded(PE64_CONFIGURATION),
                's3-pe64 source inventory must describe the same physical variant')
        require(freeze and freeze.get('defines_sha256') == digest(defines) and
                freeze.get('accelerator_configuration_sha256') == digest(PE64_CONFIGURATION),
                's3-pe64 source freeze must bind exact defines and accelerator configuration')
    elif profile == 's3-pe32-bank128':
        require(inv.get('main_commit') == BANK128_MAIN_COMMIT,
                's3-pe32-bank128 requires the exact approved candidate main commit')
        require(defines == BANK128_DEFINES, 'bank128 requires the exact frozen compile defines')
        require(impl.get('accel_variant') == 'pe32-bank128' and
                encoded(impl.get('accelerator_configuration')) == encoded(BANK128_CONFIGURATION),
                'bank128 accelerator variant/geometry/single-RW/latency differs')
        require(inv.get('source_profile') == 's3-pe32-bank128' and
                encoded(inv.get('accelerator_configuration')) == encoded(BANK128_CONFIGURATION),
                'bank128 source inventory must describe the same physical variant')
        require(freeze and freeze.get('defines_sha256') == digest(defines) and
                freeze.get('accelerator_configuration_sha256') == digest(BANK128_CONFIGURATION),
                'bank128 source freeze must bind exact defines and accelerator configuration')
    else:
        require(not any(x.split('=')[0] == 'XU_ACCEL_PE32' for x in defines),
                'PE32 compile define is allowed only for s3-pe32 profile')
    if profile != 's3-pe64':
        require(not any(x.split('=')[0] == 'XU_ACCEL_PE64' for x in defines),
                'PE64 compile define is allowed only for s3-pe64 profile')
    if profile != 's3-pe32-bank128':
        require(not any(x.split('=')[0]=='XU_ACCEL_PE32_BANK128' for x in defines),
                'BANK128 compile define is allowed only for s3-pe32-bank128 profile')
    groups=impl.get('memory_groups',[])
    expected_names=set(REQUIRED_BITS)|({'accelerator_bias'} if profile=='sram-bias' else set())
    require({g.get('name') for g in groups}==expected_names and len(groups)==len(expected_names),
            'exact profile SRAM capacity groups are required')
    for g in groups:
        if g['name']=='accelerator_bias':
            require(g==BIAS_GROUP, 'frozen bias SRAM geometry/count/scope/padding differs')
            continue
        if g['name']=='accelerator_weights' and profile=='s3-pe32':
            require(encoded(g)==encoded(PE32_WEIGHT_GROUP), 'frozen PE32 weight macro geometry/scope/padding differs')
            continue
        if g['name']=='accelerator_weights' and profile=='s3-pe64':
            require(encoded(g)==encoded(PE64_WEIGHT_GROUP), 'frozen PE64 weight macro geometry/scope/padding differs')
            continue
        if g['name']=='accelerator_weights' and profile=='s3-pe32-bank128':
            require(encoded(g)==encoded(BANK128_WEIGHT_GROUP), 'frozen BANK128 weight macro geometry/scope/single-RW/latency differs')
            continue
        require(g.get('logical_bits')==REQUIRED_BITS[g['name']], 'logical memory capacity differs: '+g['name'])
        for k in ['count','width','depth']:
            require(type(g.get(k)) is int and g[k]>0, 'bad SRAM geometry '+g['name'])
        require((g['count'],g['depth'],g['width'],g.get('macro_ref'))==(g['logical_bits']//16384,1024,16,'RAMSP1024X16'),
                'frozen RAMSP1024X16 geometry/count differs: '+g['name'])
        require(g.get('instance_pattern')==MEMORY_SCOPES[g['name']], 'actual fixed SRAM scope differs: '+g['name'])
    retained=impl.get('retained_instances',[])
    require({x.get('name') for x in retained}=={'cpu','accelerator','interconnect'} and len(retained)==3,
            'CPU/accelerator/interconnect hierarchy checks required')
    require(all((x.get('pattern'),x.get('reference_pattern'))==retained_instances(profile)[x['name']] for x in retained),
            'actual fixed CPU/accelerator/interconnect hierarchy and reference guards required')
    proof_path=absolute_file(impl.get('mapping_proof'), 'mapping proof')
    proof=json.loads(proof_path.read_text())
    require(proof.get('mapping_sha256')==digest(mapping_identity(impl)), 'mapping proof is not bound to exact implementation sources')
    checks=proof.get('checks',{})
    gaps=[]
    for name in MAPPING_CHECKS:
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
        tools_root=Path(impl.get('tool_assets_root',inv['root']))
        path=(tools_root if relative.startswith('tools/') else Path(inv['root']))/relative
        require(path.is_file() and sha(path)==record.get('sha256'), 'clock-reviewed source changed: '+relative)
        if 'path' in record:
            require(Path(record['path']).resolve()==path.resolve(), 'clock-reviewed source origin differs: '+relative)
    require(all(review.get(k) for k in ['primary_clocks','generated_clock_policy','reset_exceptions','clock_domain_crossings','untested_check_policy']), 'clock/reset/untested policy incomplete')
    return proof,review,gaps


def memory_checks(impl):
    lines=['# Exact post-elaboration macro groups; overlapping matches and missing/extra cells fail.', 'set xu_seen [dict create]']
    for g in impl['memory_groups']:
        # -hierarchical patterns containing '/' differ between DC/PT releases.
        # Filter full_name explicitly and count actual macro leaves only.
        filt='full_name =~ '+g['instance_pattern']+' && ref_name == '+g['macro_ref']+' && is_hierarchical == false'
        lines += ['set xu_cells [get_cells -quiet -hierarchical -filter '+tcl(filt)+']',
                  'if {[sizeof_collection $xu_cells] != '+str(g['count'])+'} {error '+tcl('wrong macro count: '+g['name'])+'}',
                  'foreach_in_collection xu_c $xu_cells {',
                  '  set xu_n [get_object_name $xu_c]',
                  '  if {[dict exists $xu_seen $xu_n]} {error "overlapping SRAM group: $xu_n"}',
                  '  dict set xu_seen $xu_n 1',
                  '  if {[get_attribute $xu_c ref_name] != '+tcl(g['macro_ref'])+'} {error "wrong SRAM reference: $xu_n"}',
                  '}',
                  'puts "XU_SRAM_GROUP '+g['name']+' count='+str(g['count'])+' macro_ref='+g['macro_ref']+
                  ' logical_bits='+str(g['logical_bits'])+' physical_bits='+str(g['count']*g['depth']*g['width'])+
                  ' padding_bits='+str(g['count']*g['depth']*g['width']-g['logical_bits'])+'"']
    total=sum(g['count'] for g in impl['memory_groups'])
    refs=sorted({g['macro_ref'] for g in impl['memory_groups']})
    lines += ['# RAMSP is the explicit technology SRAM namespace; reject every extra leaf/reference.',
              'set xu_allowed_refs [list '+' '.join(tcl(ref) for ref in refs)+']',
              'set xu_all_macros [get_cells -quiet -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}]',
              'if {[sizeof_collection $xu_all_macros] != '+str(total)+' || [dict size $xu_seen] != '+str(total)+'} {error '+tcl('full-SoC SRAM total must be exactly '+str(total))+'}',
              'foreach_in_collection xu_c $xu_all_macros {',
              '  if {[lsearch -exact $xu_allowed_refs [get_attribute $xu_c ref_name]] < 0} {error {unexpected SRAM reference}}',
              '  if {![dict exists $xu_seen [get_object_name $xu_c]]} {error {ungrouped/unaccounted SRAM macro}}',
              '}']
    for x in impl['retained_instances']:
        filt='full_name == '+x['pattern']+' && ref_name =~ '+x['reference_pattern']
        lines.append('if {[sizeof_collection [get_cells -quiet -hierarchical -filter '+tcl(filt)+']] != 1} {error '+tcl('missing/wrong '+x['name'])+'}')
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
    inv=inventory(root)
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
    reporter=Path(impl.get('tool_assets_root',root))/'tools/ppa/xu_full_soc_clock_review.tcl'
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
    synth+='analyze -format sverilog -define [list '+' '.join(tcl(x) for x in impl['defines'])+'] [list '+' '.join(tcl(p) for p in inputs)+']\n'
    synth+='elaborate '+tcl(impl['top'])+'\ncurrent_design '+tcl(impl['top'])+'\nif {![link]} {error {DC link failed}}\n'
    synth+='if {[sizeof_collection [current_design]] != 1} {error {no elaborated current design}}\n'
    synth+='foreach_in_collection xu_d [get_designs *] {\nset xu_blackbox [get_attribute $xu_d is_black_box]\nif {[string is true -strict $xu_blackbox]} {error "unresolved design [get_object_name $xu_d]"}\nif {$xu_blackbox ne "" && ![string is false -strict $xu_blackbox]} {error "unexpected black-box attribute [get_object_name $xu_d]: $xu_blackbox"}\n}\n'
    # This reviewed contract contains Tcl collection operations/procedures.
    # DC read_sdc uses its restricted SDC interpreter; source preserves the
    # normal shell commands/options used by this contract.
    synth+=memory_checks(impl)+'check_design > precheck.rpt\nset XU_CLOCK_MODE envelope\nset XU_PLL_DIV 0\nsource constraints.sdc\n'+clock_contract_checks()
    synth+='set_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false\n'
    synth+='set_dont_touch [get_cells -hierarchical -filter {ref_name =~ RAMSP* && is_hierarchical == false}] true\n'
    synth+='set_fix_hold [all_clocks]\ncompile_ultra -no_autoungroup\n'
    synth+=memory_checks(impl)+'check_design > postcheck.rpt\nreport_units > dc-units.rpt\nreport_area -hierarchy > area.rpt\nreport_reference -hierarchy > references.rpt\nreport_qor > qor.rpt\nreport_clock > clocks.rpt\nwrite -format verilog -hierarchy -output mapped.v\nwrite_sdc mapped.sdc\n'
    (out/'synth.tcl').write_text(guarded_tcl(synth,'XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED'))
    pt='set_app_var link_path '+libexpr+'\nread_verilog mapped.v\nif {![link_design '+tcl(impl['top'])+']} {error {PT link failed}}\nsource constraints.sdc\n'+clock_contract_checks()+'set_propagated_clock [all_clocks]\nupdate_timing\n'
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
    errors=re.findall(r'^\s*(?:Error:|Fatal:|FATAL:|XU_FATAL:).*$',text,re.M)
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
    checked_implementation(manifest['implementation'],inventory(root),manifest.get('allow_unqualified_mapping',False))


def activity_power(out, record, env):
    prepared=json.loads((out/'prepared.json').read_text());impl=prepared['implementation']
    require(impl.get('source_profile') != 's3-pe32',
            'PE32 energy requires candidate-specific clear/request-window activity; legacy VCD power is not supported')
    require(impl.get('source_profile') != 's3-pe64',
            'PE64 energy requires candidate-specific clear/request-window activity; legacy VCD power is not supported')
    require(impl.get('source_profile') != 's3-pe32-bank128',
            'BANK128 energy requires candidate-specific clear/request-window activity; legacy VCD power is not supported')
    execution=json.loads((out/'execution.json').read_text())
    require(execution.get('status')=='EXECUTED_NOT_QUALIFIED','DC/PT execution must complete before power')
    vcd=absolute_file(record.get('vcd'),'VCD')
    resultpath=absolute_file(record.get('result'),'whole-SoC numerical result')
    logpath=absolute_file(record.get('simulation_log'),'whole-SoC simulation log')
    result=json.loads(resultpath.read_text());log=logpath.read_text(errors='replace')
    require(result.get('status')=='PASS' and result.get('tasks')==12 and result.get('outputs')==304128 and result.get('write_words')==608256,
            'activity must accompany complete twelve-task numerical verification')
    require(record.get('mapping_sha256')==digest(mapping_identity(impl)), 'activity mapping source differs')
    require(record.get('source_manifest_sha256')==prepared['input_manifest_sha256'],'activity full source manifest differs')
    # Preserve DC's mapped SDC identity separately from the exact contract sourced by PT.
    require(record.get('netlist_sha256')==sha(out/'mapped.v')==execution.get('netlist_sha256') and
            record.get('sdc_sha256')==sha(out/'mapped.sdc')==execution.get('sdc_sha256'),'activity netlist/SDC identity differs')
    analysis_sdc=out/'constraints.sdc'
    require(analysis_sdc.is_file() and not analysis_sdc.is_symlink(),'analysis SDC must be a regular prepared file')
    analysis_sdc_sha256=sha(analysis_sdc)
    require(record.get('analysis_sdc_sha256')==analysis_sdc_sha256==execution.get('analysis_sdc_sha256')==
            prepared.get('generated_sha256',{}).get('constraints.sdc')==impl.get('constraints',{}).get('sha256'),
            'activity analysis SDC identity differs')
    require(not re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout',log,re.I),'activity simulation log reports failure')
    layers=result.get('layers',[])
    require([r.get('layer') for r in layers]==list(range(12)),'all twelve distinct layers required')
    tasks=re.findall(r'^TASK_PASS layer=(\d+) outputs=25344 writes=50688 cycles=(\d+) firmware_cycles=(\d+)$',log,re.M)
    require([(int(a),int(b),int(c)) for a,b,c in tasks]==[(x['layer'],x['cycles'],x['firmware_cycles']) for x in layers], 'raw numerical log/result differ')
    require(re.findall(r'^SOC_PASS.*$',log,re.M)==['SOC_PASS tasks=12 outputs=304128 writes=608256'],'missing full numerical SoC completion')
    require(result.get('log_sha256',{}).get('simulation.log')==sha(logpath), 'simulation log SHA differs')
    windows=record.get('windows_ns',[])
    require(len(windows)==12 and all(isinstance(x,list) and len(x)==2 for x in windows),'twelve measured activity windows required')
    last=-1.0
    for index,pair in enumerate(windows):
        begin,end=pair
        require(all(type(t) in [int,float] and math.isfinite(t) for t in pair) and 0<=begin<end and begin>last,'invalid/overlapping ns windows')
        require(abs((end-begin)-(layers[index]['cycles']-1)*(20/3))<=.03,
                'window must span first-input to final-response edges at150MHz')
        last=end
    require(record.get('clock_period_ns')==20/3 and record.get('scope')=='full-digital-soc-including-all-srams', 'wrong clock or incomplete activity scope')
    require(set(record.get('scope_paths',{}))=={'cpu','accelerator','interconnect','shared','itcm','dtcm'} and
            all(isinstance(x,str) and x for x in record['scope_paths'].values()),'all full-power activity scopes required')
    strip=record.get('strip_path')
    require(isinstance(strip,str) and strip and 'u_accel' not in strip,'wrapper-only strip_path cannot qualify full-scope power')
    require(not (out/'power-run.json').exists() and not (out/'activity-input.json').exists(),'refuse existing power run')
    _,libs=library_paths(impl)
    common='set_app_var link_path [list * '+' '.join(tcl(x) for x in libs)+']\nset_app_var power_enable_analysis true\nset_app_var power_analysis_mode averaged\nread_verilog mapped.v\nif {![link_design '+tcl(impl['top'])+']} {error {PT power link failed}}\nsource constraints.sdc\n'+clock_contract_checks()+'set_propagated_clock [all_clocks]\nupdate_timing\n'
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
                 netlist_sha256=record['netlist_sha256'],sdc_sha256=record['sdc_sha256'],
                 analysis_sdc_sha256=analysis_sdc_sha256,
                 activity_sha256=digest(record),method='twelve independent averaged PT windows; no mean-power or energy claim',
                 pending='Every task needs annotation propagation/default review and all SRAM power coverage, then sum(P_task*duration_task) via xu_soc_activity.py energy')
    write(out/'power-run.json',receipt)
    try:
        for index,script in enumerate(scripts):
            require(analysis_sdc.is_file() and not analysis_sdc.is_symlink() and sha(analysis_sdc)==analysis_sdc_sha256,
                    'analysis SDC changed before power execution')
            result=run_tool(out,['pt_shell','-f',script.name],'pt-power-%02d'%index,env)
            require(analysis_sdc.is_file() and not analysis_sdc.is_symlink() and sha(analysis_sdc)==analysis_sdc_sha256,
                    'analysis SDC changed during power execution')
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
    p.add_argument('action',choices=['inventory','review-template','prepare','verify','run','power'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--implementation',type=Path)
    p.add_argument('--activity',type=Path)
    p.add_argument('--allow-unqualified-mapping',action='store_true',help='allow development PPA with real missing proof statuses; never qualifies the design')
    p.add_argument('--lc-root',type=Path,default=Path('/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5'))
    a=p.parse_args();out=a.out.resolve();root=a.root.resolve()
    if a.action=='inventory':
        require(not out.exists(),'inventory output exists');out.mkdir(parents=True)
        inv=inventory(root);write(out/'inventory.json',inv);write(out/'implementation-template.json',template(inv,inv.get('source_profile','baseline')));print('INVENTORIED_NOT_QUALIFIED '+str(out));return 0
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
    if a.action=='verify':
        print('VERIFIED_PREPARED_NOT_QUALIFIED '+str(out));return 0
    env=dict(os.environ,SYNOPSYS_LC_ROOT=str(a.lc_root));env['PATH']=str(a.lc_root/'bin')+os.pathsep+env.get('PATH','')
    if a.action=='run':
        run=dict(schema='xu-full-soc-ppa-execution-v1',status='RUNNING_NOT_QUALIFIED',started_utc=datetime.now(timezone.utc).isoformat())
        write(out/'execution.json',run)
        try:
            run['dc']=run_tool(out,['dc_shell','-f','synth.tcl'],'dc',env)
            require((out/'mapped.v').is_file() and (out/'mapped.sdc').is_file(),'DC mapped outputs missing')
            run['pt']=run_tool(out,['pt_shell','-f','sta.tcl'],'pt-sta',env)
            verify_prepared(root,out,manifest)
            run.update(status='EXECUTED_NOT_QUALIFIED',netlist_sha256=sha(out/'mapped.v'),sdc_sha256=sha(out/'mapped.sdc'),
                       analysis_sdc_sha256=sha(out/'constraints.sdc'),
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
