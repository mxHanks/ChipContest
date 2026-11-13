#!/usr/bin/env python3
"""Stage and seal a NEW full-SoC SYSBUS32 experiment; never launch EDA.

The old selected B is a source/library/command reference only. No old simulation,
area, mapped netlist, STA status, or qualification result is copied as new proof.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

sys.dont_write_bytecode = True
from profiles import PROFILES, REGISTER_X, SRAM_X

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PIN = 'ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1'
REFERENCE_ARCHIVE = 'docs/validation/s3-y32-area-opt-20261111/candidate-b-ppa-inputs-r3.tar.xz'
REFERENCE_ARCHIVE_SHA = '8a03367cda442aff22d9e7806c82964f454934d0c80cb299420de436f68a5d48'
NATIVE_ARCHIVE = 'docs/validation/s3-y32-area-opt-20261111/candidate-native-reports-r4.tar.xz'
NATIVE_ARCHIVE_SHA = 'fd235de2b63b06b321d9940641937e1a29a35c6497ca6ba3ed89687be13fd763'
PT_MEMBER = 'b/pt/baseline.tcl'
PT_EXECUTION_MEMBER = 'b/pt/execution.json'
NATIVE_HASHES = {
    PT_MEMBER: '14d5518b98a9cd31a24576361be2c36f8f2947335b0fee96daf05e2b60367434',
    PT_EXECUTION_MEMBER: '38f08abedabaa838d8b86e9e895bb07007e24217e2863126f66fb9d8aa8e32a3',
}
TOP = 'xu_soc_sysbus32_ppa_top'
DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA', 'XU_MATRIX_DMA_SYSBUS32']
CORE_SHA = '710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb'
X_MANIFEST_SHA = '5a7ae65ece333666fdf15c6c717bc9a102892d3d36a0fcc04305b0f6a780abdd'
SDC_SHA = 'c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c'
REFERENCE_HASHES = {
    'rtl.f': 'd0c7b7a0a44de9fa042e3494b5c21e37d0049b8dbf55f41e3c5c1f05f7dd5ad6',
    'package-files.json': 'a6ac0c36ecf3616cee2aa80b547f187929b48ec01fa1b4df6a50145d81a9cf3c',
    'synth.tcl': 'fdd787ddc78897359d76071cd8fe9db6fec77c7280300a4738b8e2a32d697529',
    'run_once.py': '14be33ffcb8b21ccc3391d34fae7226e4d150115cd093f24fea500d221bc5917',
    'area_components.tcl': '6ea8d141ad8e5d035a9e8a49b16ddca002dbf40fd2413d421572bd6f1e4f1a6d',
    'source/contracts/reference-full-soc.sdc': SDC_SHA,
    'source/contracts/reference-clock-review.tcl': '6c203da71ce398851a9985699d4cfce1708bec8251b8f47a0e1bbb8c03fa5a1e',
}
WRAPPERS = {'soc/e203_soc_top.v', 'subsys/e203_subsys_main.v',
            'subsys/e203_subsys_perips.v', 'subsys/e203_subsys_top.v'}
REMOVED = {'perips/xu_dma64_shared_arb.sv', 'perips/xu_matrix_dma64.sv',
           'perips/xu_shared_icb_sram64.sv'}
MAIN = 'u_soc/u_e203_subsys_top/u_e203_subsys_main'
DMA = MAIN + '/u_e203_subsys_perips/u_xu_matrix_dma'
NICE = MAIN + '/u_e203_cpu_top/u_e203_cpu/u_e203_nice_core'
PLATFORM_BASE = 'f64a430f172c701df43e3d63afaf9dc0178096e1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def require(value, message):
    if not value:
        raise ValueError(message)


def safe_name(name):
    p = PurePosixPath(name)
    require(name and not p.is_absolute() and '..' not in p.parts and '\\' not in name,
            'unsafe package path: ' + name)
    require(not (len(name) > 1 and name[1] == ':') and p.as_posix() == name.rstrip('/'),
            'noncanonical package path: ' + name)
    return Path(p)


def archive_members(bundle):
    """Validate the entire archive before reading or extracting any member."""
    result = {}
    total = 0
    for member in bundle.getmembers():
        safe_name(member.name)
        require(member.name not in result, 'duplicate archive member: ' + member.name)
        require(member.isfile() or member.isdir(), 'archive links/special nodes forbidden: ' + member.name)
        require(0 <= member.size <= 128 * 1024 * 1024, 'oversized archive member: ' + member.name)
        total += member.size
        require(total <= 1024 * 1024 * 1024, 'reference archive size bound exceeded')
        result[member.name] = member
    return result


def restore_reference(archive, expected_sha, cache, hashes, source_manifest=False):
    """Restore only pinned reference files; never use tar.extract/extractall."""
    require(archive.is_file() and sha(archive) == expected_sha, 'reference archive SHA256 mismatch: ' + str(archive))
    with tarfile.open(archive, 'r:*') as bundle:
        members = archive_members(bundle)
        wanted = dict(hashes)
        if source_manifest:
            for name in ['rtl.f', 'package-files.json']:
                require(name in members and members[name].isfile(), 'missing reference metadata: ' + name)
                raw = bundle.extractfile(members[name]).read()
                require(hashlib.sha256(raw).hexdigest() == hashes[name], 'reference metadata SHA mismatch: ' + name)
            manifest = json.loads(bundle.extractfile(members['package-files.json']).read())
            names = bundle.extractfile(members['rtl.f']).read().decode().splitlines()
            for name in names:
                safe_name(name)
                require(name in manifest, 'reference source absent from manifest: ' + name)
                wanted[name] = manifest[name]
        for name, digest in wanted.items():
            require(name in members and members[name].isfile(), 'missing required reference file: ' + name)
            require(hashlib.sha256(bundle.extractfile(members[name]).read()).hexdigest() == digest, 'reference member SHA mismatch: ' + name)
        if cache.exists():
            require(cache.is_dir() and not cache.is_symlink(), 'unsafe existing reference cache')
            for path in cache.rglob('*'):
                require(not path.is_symlink(), 'symlink in reference cache: ' + str(path))
            actual = {p.relative_to(cache).as_posix(): sha(p) for p in cache.rglob('*') if p.is_file()}
            require(actual == wanted, 'existing reference cache differs; refuse overwrite: ' + str(cache))
        else:
            cache.mkdir(parents=True)
            for name in sorted(wanted):
                target = cache / safe_name(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(bundle.extractfile(members[name]).read())
        require(sha(archive) == expected_sha, 'reference archive changed during recovery')
    return dict(archive=str(archive), archive_sha256=expected_sha, restored_files=len(wanted),
                restored_directory=str(cache), extraction='PINNED_REGULAR_FILES_ONLY_NO_LINKS_OR_TRAVERSAL')


def check_x_candidate(root, candidate, expected_manifest_sha):
    """Bind an explicit overlay to its independently pinned manifest and origins."""
    require(candidate.is_dir() and not candidate.is_symlink(), 'unsafe X candidate directory')
    for path in candidate.rglob('*'):
        require(not path.is_symlink() and (path.is_file() or path.is_dir()),
                'X candidate links/special nodes forbidden: ' + str(path))
    manifest = candidate / 'manifest.json'
    require(sha(manifest) == expected_manifest_sha, 'X candidate manifest SHA256 mismatch')
    value = json.loads(manifest.read_text())
    require(value['schema'] == 'compliant32_xmacro_candidate_v1' and value['production_core_sha256'] == CORE_SHA,
            'X candidate is not the B41 overlay')
    require(value['required_defines'] == ['XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM'],
            'X candidate define contract mismatch')
    expected_files = {'LinearTileDmaCore.sv', 'Sram1024x16.sv', 'TileWeightBank.sv',
                      'TileWeightBankArray.sv', 'DmaBiasSramPrefetch.sv', 'MacController.sv',
                      'TileXRowBuffer.sv', 'TileXMacroRowBuffer.sv', 'mem_1024x16.sv',
                      'generic_ramsp_non_ppa.sv'}
    require(set(value['candidate_files']) == expected_files, 'unexpected X candidate file set')
    actual_files = {p.relative_to(candidate).as_posix() for p in candidate.rglob('*') if p.is_file()}
    require(actual_files == {'manifest.json'} | {'rtl/' + n for n in expected_files}, 'unmanifested X candidate input')
    for name, digest in value['candidate_files'].items():
        require(len(digest) == 64 and sha(candidate / 'rtl' / safe_name(name)) == digest,
                'X candidate source SHA256 mismatch: ' + name)
    for name, digest in value['origins'].items():
        if name == 'third-party/e203_hbirdv2/rtl/e203/perips/LinearTileDmaCore.sv':
            published = subprocess.check_output(['git', '-C', str(root / 'third-party/e203_hbirdv2'),
                'show', PIN + ':rtl/e203/perips/LinearTileDmaCore.sv'])
            require(digest == CORE_SHA and hashlib.sha256(published).hexdigest() == CORE_SHA,
                    'X original B41 core differs from published child')
            require(sha(root / name) in {CORE_SHA, value['candidate_files']['LinearTileDmaCore.sv']},
                    'installed core is neither original B41 nor this exact X overlay')
            continue
        path = root / safe_name(name)
        require(path.is_file() and not path.is_symlink() and sha(path) == digest,
                'X candidate original source drift: ' + name)
    expected_storage = dict(x_logical_bits=16384, x_physical_bits=262144, x_macros=16,
        internal_macros_before=17, internal_macros_after=33, shared_bytes=524288,
        weight_macros=16, bias_macros=1)
    require(value['storage'] == expected_storage, 'X storage/macro accounting mismatch')
    require(value['clear'] == dict(weight_writes=16384, bias_writes=768, x_writes=16384,
            total16bit_writes=33536, parallel_address_steps=1024), 'X physical clear contract mismatch')
    require(sha(manifest) == expected_manifest_sha, 'X manifest changed while validating')
    return value


def stage(root, out, old, native, profile, x_candidate=None):
    """Reuse B's proven source order/adapters, with explicit new32 inputs."""
    for name, digest in REFERENCE_HASHES.items():
        require(sha(old / name) == digest, 'old B reference drift: ' + name)
    for name, digest in NATIVE_HASHES.items():
        require(sha(native / name) == digest, 'old native PT reference drift: ' + name)
    child = root / 'third-party/e203_hbirdv2'
    rtl = child / 'rtl/e203'
    replacements = {'general/sirv_sim_ram.v': root / 'tools/ppa/xu_sirv_sram_adapter.sv',
                    'perips/mem_1024x16.sv': root / 'tools/ppa/xu_weight_sram_adapter.sv'}
    origins = {}
    source_names = []
    old_manifest = json.loads((old / 'package-files.json').read_text())
    def copy(name, origin, role, reference=None):
        require(name not in origins, 'duplicate staged input: ' + name)
        require(origin.is_file() and not origin.is_symlink(), 'missing/symlink input: ' + str(origin))
        before = sha(origin)
        target = out / safe_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        require(sha(target) == before, 'input changed during copy: ' + str(origin))
        label = str(origin.relative_to(root)) if origin.is_relative_to(root) else str(origin)
        origins[name] = dict(origin=label, sha256=before,
                             bytes=target.stat().st_size, role=role,
                             reference_B_sha256=reference)
    for name in (old / 'rtl.f').read_text().splitlines():
        safe_name(name)
        if name == 'source/ppa/xu_soc_dma64_ppa_top.sv':
            name = 'source/ppa/' + TOP + '.sv'
            copy(name, root / 'experiments/s3-y32-compliant32/structure' / (TOP + '.sv'), 'new_production32_full_soc_boundary')
        else:
            require(name.startswith('source/rtl/'), 'unreviewed B input: ' + name)
            rel = name.removeprefix('source/rtl/')
            if rel in REMOVED:
                continue
            origin = replacements.get(rel, rtl / rel)
            require(name in old_manifest and sha(old / name) == old_manifest[name], 'B source identity drift: ' + name)
            if rel in replacements:
                role = 'same_B_physical_macro_adapter'
                require(sha(origin) == sha(old / name), 'macro adapter changed from B: ' + rel)
            elif rel == 'perips/LinearTileDmaCore.sv':
                require(sha(old / name) == CORE_SHA, 'X overlay reference is not B41')
                if x_candidate is not None:
                    origin = x_candidate / 'rtl/LinearTileDmaCore.sv'
                    role = 'isolated_X16_macro_B41_core_overlay'
                else:
                    origin = old / name
                    role = 'exact_B41_reference_register_X_core'
            elif rel in WRAPPERS:
                role = 'new32_integration_wrapper'
            else:
                role = 'exact_B_unchanged_source'
                require(sha(origin) == sha(old / name), 'unreviewed non-interface RTL change: ' + rel)
            copy(name, origin, role, sha(old / name))
        source_names.append(name)
    for rel in ['subsys/xu_systembus_ingress32.v', 'perips/xu_matrix_dma_sysbus32.sv']:
        name = 'source/rtl/' + rel
        copy(name, rtl / rel, 'new32_ingress' if 'ingress' in rel else 'new32_dma_frontend')
        source_names.append(name)
    name = 'source/ppa/xu_shared_icb_sram.sv'
    copy(name, root / 'tools/ppa/xu_shared_icb_sram.sv', 'original32_shared_endpoint_logic_full_charge')
    source_names.append(name)
    if x_candidate is not None:
        name = 'source/rtl/perips/TileXMacroRowBuffer.sv'
        copy(name, x_candidate / 'rtl/TileXMacroRowBuffer.sv', 'isolated_X16_physical_macro_wrapper')
        source_names.append(name)
        copy('evidence/x-candidate/manifest.json', x_candidate / 'manifest.json', 'pinned_isolated_X_candidate_manifest')
    require(len(source_names) == len(set(source_names)), 'duplicate compile source')
    if x_candidate is None:
        require(sha(out / 'source/rtl/perips/LinearTileDmaCore.sv') == CORE_SHA, 'selected B41 core changed')
    # CPU core and original mem_fab file are byte-for-byte fixed to published B.
    pinned = {}
    names = subprocess.check_output(['git', '-C', str(child), 'ls-tree', '-r', '--name-only', PIN, 'rtl/e203/core'], text=True).splitlines()
    names.append('rtl/e203/subsys/e203_subsys_mems.v')
    for name in names:
        raw = subprocess.check_output(['git', '-C', str(child), 'show', PIN + ':' + name])
        require((child / name).read_bytes() == raw, 'fixed CPU/mem_fab source changed: ' + name)
        pinned[name] = hashlib.sha256(raw).hexdigest()
    for target, origin in {
        'source/contracts/reference-full-soc.sdc': old / 'source/contracts/reference-full-soc.sdc',
        'source/contracts/reference-clock-review.tcl': old / 'source/contracts/reference-clock-review.tcl',
        'local-only/generic_ramsp_non_ppa.sv': root / 'tools/ppa/generic_ramsp_non_ppa.sv',
    }.items():
        copy(target, origin, 'local_elaboration_only_excluded_from_synthesis' if target.startswith('local-only/') else 'exact_B_native_reference_contract')
    for name in ['run_once.py', 'preflight.py', 'profiles.py', 'README.md', 'synth.tcl', 'area_components.tcl', 'pt_collect.tcl']:
        copy(name, HERE / name, 'new32_flow_tool')
    copy('source/ppa/hierarchy_contract.tcl', HERE / 'hierarchy_contract.tcl', 'new32_geometry_guard')
    copy('source/tools/prepare.py', Path(__file__), 'stage_emitter_identity')
    expected = PROFILES[profile]
    (out / 'source/ppa/geometry-profile.tcl').write_text(
        '# Sealed exact hardware profile. No timing or constraint edits.\n' +
        'set sysbus32_hardware_profile {' + profile + '}\n' +
        'set sysbus32_production_defines [list ' + ' '.join(expected['defines']) + ']\n' +
        'set sysbus32_expected_total_macros ' + str(expected['geometry']['total_macros']) + '\n' +
        'set sysbus32_expected_x_macros ' + str(expected['geometry']['x']) + '\n' +
        'set sysbus32_expected_internal_macros ' + str(expected['internal_macros']) + '\n')
    # The original SDC stays byte-identical. PT makes only its native-proven
    # three -add substitutions in its own fresh output directory at run time.
    require(sha(out / 'source/contracts/reference-full-soc.sdc') == SDC_SHA, 'SDC changed')
    require(not any('generic_ramsp' in name or any(x in name for x in REMOVED) for name in source_names), 'nonproduction source in synthesis list')
    (out / 'rtl.f').write_text('\n'.join(source_names) + '\n')
    dump(out / 'defines.json', expected['defines'])
    return source_names, origins, pinned


def emit_policy(old, out, profile):
    """Record every departure from B; only interface/guards/accounting change."""
    before = (old / 'synth.tcl').read_text()
    new = (out / 'synth.tcl').read_text()
    # All synthesis/optimization and clock-setup commands remain identical.
    commands = ['set_host_options -max_cores 2', 'set_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false',
                'set_dont_touch [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}] true',
                'set_fix_hold [all_clocks]', 'compile_ultra -no_autoungroup',
                'set XU_CLOCK_MODE envelope', 'set XU_PLL_DIV 0',
                'source source/contracts/reference-full-soc.sdc']
    for command in commands:
        require(before.count(command) == new.count(command) == 1, 'native compile policy changed: ' + command)
    for token in ['set_false_path', 'set_multicycle_path', 'set_clock_groups', 'set_ideal_network', 'set_input_delay', 'set_output_delay']:
        require(token not in new, 'unexpected constraint command in new emitter: ' + token)
    require('XU_MATRIX_DMA64' not in new and 'XU_SYSBUS_TEST_LOADER' not in new, 'forbidden production define')
    require('analyze -format sverilog -define $sysbus32_production_defines $sources' in new and 'elaborate ' + TOP in new, 'wrong production top/defines')
    require('set sysbus32_production_defines [list ' + ' '.join(PROFILES[profile]['defines']) + ']' in
            (out / 'source/ppa/geometry-profile.tcl').read_text(), 'wrong sealed production profile defines')
    diff = ''.join(difflib.unified_diff(before.splitlines(True), new.splitlines(True), fromfile='reference-B/synth.tcl', tofile='new32/synth.tcl'))
    (out / 'synthesis-emitter-vs-B.patch').write_text(diff)
    return dict(reference_B_synthesis_sha256=sha(old / 'synth.tcl'), new_synthesis_sha256=sha(out / 'synth.tcl'),
                retained_commands=commands, patch_sha256=sha(out / 'synthesis-emitter-vs-B.patch'),
                allowed_differences=['production32 top and define', 'production32 hierarchy checks',
                                     'replace downstream wide arbiter accounting with upstream ingress accounting',
                                     'sealed exact337/353 macro profile and charge guards',
                                     'conservative complete NICE scope charge and full-SoC-standard-cell upper bound', 'new experiment labels'],
                sdc_byte_identical=True, false_or_multicycle_or_io_relaxation_added=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--x-candidate', type=Path, help='explicit isolated X16 SRAM overlay; production RTL stays unchanged')
    parser.add_argument('--x-candidate-manifest-sha256', default=X_MANIFEST_SHA,
                        help='independent exact overlay manifest SHA256; defaults to validated candidate-r2 identity')
    parser.add_argument('--reference-package', type=Path,
                        help='relocated exact tracked candidate-b-ppa-inputs-r3.tar.xz; SHA is fixed')
    parser.add_argument('--reference-native-package', type=Path,
                        help='relocated exact tracked candidate-native-reports-r4.tar.xz; SHA is fixed')
    parser.add_argument('--archive', action='store_true', help='also create a new sealed tar.gz sibling')
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    profile = SRAM_X if args.x_candidate else REGISTER_X
    expected = PROFILES[profile]
    defines = expected['defines']
    x_candidate = args.x_candidate.resolve() if args.x_candidate else None
    x_manifest = check_x_candidate(root, x_candidate, args.x_candidate_manifest_sha256) if x_candidate else None
    require(not out.exists(), 'refuse overwrite: ' + str(out))
    require(not args.archive or not out.with_suffix('.tar.gz').exists(), 'refuse archive overwrite')
    old = out.parent / ('reference-B-' + REFERENCE_ARCHIVE_SHA[:16])
    native = out.parent / ('reference-native-B-' + NATIVE_ARCHIVE_SHA[:16])
    require(out not in [old, native], 'output conflicts with reference cache')
    recovery = [restore_reference((args.reference_package or root / REFERENCE_ARCHIVE).resolve(),
                REFERENCE_ARCHIVE_SHA, old, REFERENCE_HASHES, source_manifest=True),
                restore_reference((args.reference_native_package or root / NATIVE_ARCHIVE).resolve(),
                NATIVE_ARCHIVE_SHA, native, NATIVE_HASHES)]
    out.mkdir(parents=True)
    sources, origins, pinned = stage(root, out, old, native, profile, x_candidate)
    policy = emit_policy(old, out, profile)
    old_pt = json.loads((native / PT_EXECUTION_MEMBER).read_text())
    dump(out / 'reference-recovery.json', dict(schema='sysbus32-tracked-reference-recovery-v1',
         private_build_tree_required=False, references=recovery))
    toolchain = dict(schema='sysbus32-exact-B-native-toolchain-v1', libraries=old_pt['libraries'],
        dc=dict(path='/eda/synopsys/dc/dc_2022.03-SP5-5/bin/dc_shell', sha256='23a4101c711fdb4747a57e6f9524d4989eb76a2b3120f0fa9766f4b25ae8e6d2'),
        pt=old_pt['tool'], library_compiler=old_pt['library_compiler'],
        sdc_sha256=SDC_SHA, sdc_pt_add_sha256='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98',
        local_library_files_examined=False, eligibility='ACTUAL_OLD_B_IDENTITIES_REUSED_NEW_RUN_MUST_REHASH')
    dump(out / 'toolchain.json', toolchain)
    dump(out / 'pinned-cpu-and-mem-fab.json', dict(reference_child=PIN, sha256=pinned, immutable=True))
    dump(out / 'source-manifest.json', dict(schema='sysbus32-exact-per-source-v1', top=TOP,
         defines=defines, hardware_profile=profile, ordered_compile_sources=[dict(index=i, path=n, **origins[n]) for i, n in enumerate(sources)],
         all_staged_inputs=origins, local_only_source='local-only/generic_ramsp_non_ppa.sv'))
    dump(out / 'reference-B.json', dict(scope='OLD_B_ONLY_NOT_NEW32_RESULT',
        package_manifest_sha256=REFERENCE_HASHES['package-files.json'], selected_core_sha256=CORE_SHA,
        native_pt_execution_sha256=sha(native / PT_EXECUTION_MEMBER), native_pt_script_sha256=sha(native / PT_MEMBER),
        native_dc_execution_sha256=old_pt['source_dc_execution_sha256'],
        old_mapped_v_sha256=old_pt['mapped_v_sha256'], old_status=old_pt['status'],
        old_coverage=dict(total=455190, violated=211, untested=27911),
        old_setup_slack_ns='-10.11695099', old_hold_slack_ns='-0.13472039',
        interpretation='Reference facts preserved. No old area, netlist, simulation or timing result qualifies this new32 candidate.',
        reference_archive_sha256=REFERENCE_ARCHIVE_SHA, native_reference_archive_sha256=NATIVE_ARCHIVE_SHA,
        reference_inputs={n: h for n, h in REFERENCE_HASHES.items()}))
    charge = [dict(scope='dma', path=DMA, policy='all standard cells plus all' + str(expected['internal_macros']) + ' internal RAMSP1024X16 macros',
                   components=['dma32_frontend_and_scheduler', 'engines_64pe', 'core_fifo_and_control',
                               'x_physical_sram_buffers' if x_candidate else 'x_double_buffers', 'weights', 'bias']),
              dict(scope='systembus32_ingress', path=MAIN + '/u_xu_systembus_ingress', policy='all new arbitration, owner state, data/control/address mux cells'),
              dict(scope='cpu_nice_interface', path=NICE, policy='all standard cells conservatively charged, including legacy NICE mux, drain8 and direct-interface logic if retained; reused logic is not subtracted'),
              dict(scope='endpoint_logic', path='u_shared', policy='all endpoint standard cells conservatively charged; all256 reused shared macros separately inventoried')]
    dump(out / 'area-charge-policy.json', dict(schema='sysbus32-conservative-disjoint-area-policy-v1', charged_scopes=charge,
        leaf_unit='raw_library_area_unit', official_mm2_conversion='UNRESOLVED', official_SRAM_area_table='UNRESOLVED',
        official_incremental_baseline_subtraction='PENDING_SEPARATE_MATCHED_BASELINE_COMPARISON',
        original_platform_baseline_child=PLATFORM_BASE,
        old_B_is_area_baseline=False,
        outside_charged_scope_positive_logic_growth='PENDING_SAME_LIBRARY_ORIGINAL_PLATFORM_BASELINE_COMPARISON; all retained nonplatform NICE/direct passthrough/mux/drain and other interface logic must be added, never credited against savings',
        conservative_upper_bound=dict(standard_cells='ALL_FULL_SOC_STANDARD_CELLS_INCLUDING_CPU_AND_REUSED_PERIPHERALS',
            internal_SRAM_macros=expected['internal_macros'], excluded_reused_SRAM_macros=320,
            official_formula='full_soc_standard_cell_area_mm2 + internal_macro_count * official_RAMSP1024X16_area_mm2',
            independent_of_precise_incremental_baseline=True,
            library_units_and_official_macro_pricing='UNRESOLVED_NO_NUMERIC_MM2_OR_VERDICT',
            interpretation='If verified official units/pricing later make this conservative bound <=2.25mm2, it proves only that bound, not an official area score or full qualification'),
        no_CPU_or_reused_SRAM_savings_credit=True, reused_macro_groups=dict(itcm=32, dtcm=32, shared=256),
        charged_internal_macro_groups=dict(weights=16, bias=1, x=expected['geometry']['x']),
        x_storage=dict(logical_bytes=2048, physical_bytes=32768 if x_candidate else 0,
                       physical_macro_count=expected['geometry']['x'], all_physical_macros_charged=True),
        timing_scope='full digital SoC including all' + str(expected['geometry']['total_macros']) + ' SRAMs'))
    manifest = dict(schema='sysbus32-sealed-synthesis-preparation-v1', status='SEALED_NOT_EXECUTED_NOT_QUALIFIED',
        top=TOP, defines=defines, hardware_profile=profile, source_count=len(sources), rtl_f_sha256=sha(out / 'rtl.f'),
        source_manifest_sha256=sha(out / 'source-manifest.json'), toolchain_sha256=sha(out / 'toolchain.json'),
        cpu_core_and_mem_fab_exact_unchanged=True, selected_B41_core_sha256=CORE_SHA,
        expected_geometry=expected['geometry'], expected_internal_macros=expected['internal_macros'],
        x_candidate_manifest_sha256=args.x_candidate_manifest_sha256 if x_candidate else None,
        staged_core_sha256=sha(out / 'source/rtl/perips/LinearTileDmaCore.sv'),
        production_test_loader=False, compile_policy=policy, synthesis_run=False, sta_run=False,
        area_result=None, timing_verdict='NOT_RUN', power_activity='PENDING_SEPARATE_SAME_NETLIST_SAME_WINDOW_ACTIVITY',
        mapped_equivalence='PENDING_NEW32_NETLIST', official_mm2_and_macro_pricing='UNRESOLVED',
        reference_recovery_sha256=sha(out / 'reference-recovery.json'), private_old_build_tree_required=False,
        report_collection='native-proven global/group setup/hold, all violators, recovery/removal, gating, min pulse, exceptions, coverage and clock-pin attribution; collection is not closure')
    dump(out / 'manifest.json', manifest)
    if x_candidate:
        require(check_x_candidate(root, x_candidate, args.x_candidate_manifest_sha256) == x_manifest,
                'X candidate changed during staging')
    # Rehash every original source after the full stage/emitter operation.
    for name, item in origins.items():
        require(sha(root / item['origin']) == item['sha256'], 'original input drift: ' + name)
        require(sha(out / name) == item['sha256'], 'staged input drift: ' + name)
    files = {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    dump(out / 'package-files.json', files)
    review = subprocess.run([sys.executable, str(out / 'run_once.py')], capture_output=True, text=True, check=True)
    receipt = dict(status=manifest['status'], out=str(out), package_files=len(files),
                   package_manifest_sha256=sha(out / 'package-files.json'), review=json.loads(review.stdout),
                   production_RTL_modified=False, new_EDA_launched=False)
    if args.archive:
        archive = out.with_suffix('.tar.gz')
        with tarfile.open(archive, 'w:gz') as bundle:
            bundle.add(out, arcname='candidate')
        receipt.update(archive=str(archive), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size)
    dump(out.with_suffix('.preparation.json'), receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        sys.exit(1)
