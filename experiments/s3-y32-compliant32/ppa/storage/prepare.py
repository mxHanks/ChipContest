#!/usr/bin/env python3
"""Seal an isolated final374 storage PPA package; offline by default, no EDA.

Only two production RTL sources and the storage feature define differ from the
sealed353 reference. A complete same-source GPIO CPU12 PASS is mandatory before
this package's later --run may access a native tool or characterized library.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
from storage_controls import DEFINES, GEOMETRY, OVERLAYS, PROFILE, check_inputs, check_cpu_full12, sha, require

HERE = Path(__file__).resolve().parent
BASE_SHA = 'f697416ea83570b25ad9aa9ecfb37c915f7b93547cd8aa6297297e9092313555'
STORAGE_SHA = '9461237a61158e94544cd98d0db491db72cbed6530a98c48da9d78a8289a2f73'


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--storage-candidate', type=Path, required=True)
    p.add_argument('--cpu-full12', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base, candidate, out = a.base.resolve(), a.storage_candidate.resolve(), a.out.resolve()
    require(not out.exists(), 'new output required; no overwrite/restart')
    require(sha(base / 'package-files.json') == BASE_SHA, 'not pinned353 same-library reference package')
    require(sha(candidate / 'manifest.json') == STORAGE_SHA, 'not final storage21 r2 candidate')
    bp = json.loads((base / 'package-files.json').read_text())
    for name, digest in bp.items():
        q = Path(name)
        require(not q.is_absolute() and '..' not in q.parts, 'unsafe base path')
        require((base / q).is_file() and not (base / q).is_symlink() and sha(base / q) == digest, 'base drift: ' + name)
    cm = json.loads((candidate / 'manifest.json').read_text())
    for name, digest in cm['files'].items():
        require(not (candidate / 'rtl' / name).is_symlink() and sha(candidate / 'rtl' / name) == digest, 'candidate drift: ' + name)
    out.mkdir(parents=True)
    for name in bp:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / name, target)
    evidence = out / 'evidence'
    (evidence / 'storage-candidate').mkdir()
    shutil.copy2(candidate / 'manifest.json', evidence / 'storage-candidate/manifest.json')
    shutil.copy2(base / 'package-files.json', evidence / 'base-package-files.json')
    shutil.copy2(base / 'source/contracts/reference-full-soc.sdc', evidence / 'original-full-soc.sdc')
    for name in OVERLAYS:
        shutil.copy2(candidate / 'rtl' / Path(name).name, out / name)
    policy = json.loads((base / 'area-charge-policy.json').read_text())
    policy['charged_internal_macro_groups'] = dict(weights=16, bias=1, x=16, result=21)
    policy['conservative_upper_bound']['internal_SRAM_macros'] = 54
    policy['timing_scope'] = 'full digital SoC including all374 SRAMs'
    for scope in policy['charged_scopes']:
        if scope['scope'] == 'dma':
            scope['policy'] = 'all standard cells plus all54 internal RAMSP1024X16 macros'
            scope['components'] = ['dma32_frontend_and_scheduler', 'rows_64pe', 'core_fifo_and_control',
                'x_physical_sram_buffers', 'weights', 'bias_physical_sram', 'result_physical_sram']
    policy['result_storage'] = dict(all_physical_macros_charged=True, logical_bits=5248,
        physical_bits=344064, physical_macro_count=21)
    dump(out / 'area-charge-policy.json', policy)
    cpu_evidence = None
    if a.cpu_full12:
        cpu_root = a.cpu_full12.resolve().parent
        cpu = json.loads(a.cpu_full12.read_text())
        for original, target in [('simulation.log', 'cpu-full12-simulation.log'),
                ('source/check_results.py', 'cpu-full12-checker.py'),
                ('firmware/dma_day_soc', 'cpu-full12.elf'),
                ('firmware/dma_day_soc.verilog', 'cpu-full12.image')]:
            origin = cpu_root / original
            require(origin.is_file() and not origin.is_symlink(), 'missing real CPU full12 artifact: ' + str(origin))
            shutil.copy2(origin, evidence / target)
        shutil.copy2(a.cpu_full12, evidence / 'cpu-full12.json')
        cpu_evidence = {name: sha(evidence / name) for name in ('cpu-full12-simulation.log',
            'cpu-full12-checker.py', 'cpu-full12.elf', 'cpu-full12.image')}
        require(cpu_evidence['cpu-full12-checker.py'] == cpu['source_sha256']['check_results.py'], 'CPU frozen checker differs')
        require(cpu_evidence['cpu-full12.elf'] == cpu['firmware']['elf_sha256'] and
                cpu_evidence['cpu-full12.image'] == cpu['firmware']['image_sha256'], 'CPU actual ELF/image differs')
    definitions = DEFINES
    dump(out / 'defines.json', definitions)
    (out / 'source/ppa/geometry-profile.tcl').write_text(
        '# Sealed exact storage hardware profile. No timing or constraint edits.\n'
        'set sysbus32_hardware_profile {' + PROFILE + '}\n'
        'set sysbus32_production_defines [list ' + ' '.join(definitions) + ']\n'
        'set sysbus32_expected_total_macros 374\nset sysbus32_expected_x_macros 16\n'
        'set sysbus32_expected_internal_macros 54\nset sysbus32_expected_result_macros 21\n')
    shutil.copy2(HERE / 'hierarchy_contract.tcl', out / 'source/ppa/hierarchy_contract.tcl')
    shutil.copy2(HERE / 'storage_controls.py', out / 'storage_controls.py')
    shutil.copy2(HERE / 'preflight.py', out / 'preflight.py')
    shutil.copy2(HERE / 'README.md', out / 'README.md')
    # Keep the original run policy/process/receipt handling intact. Only replace
    # the configuration checker and insert the mandatory same-freeze12 gate.
    runner = (base / 'run_once.py').read_text()
    start, end = runner.index('def check_inputs(root):'), runner.index('\ndef heavy_jobs():')
    runner = runner[:start] + 'from storage_controls import check_inputs, check_cpu_full12\n\n' + runner[end:]
    marker = '    timeout_seconds = a.timeout_seconds or (14400 if a.stage == \'dc\' else 300)'
    require(runner.count(marker) == 1, 'native runner seam changed')
    runner = runner.replace(marker, "    cpu_full12_binding = check_cpu_full12(root)\n" + marker)
    runner = runner.replace("source_dc=dc_binding, timing_verdict=", "source_dc=dc_binding, cpu_full12_binding=cpu_full12_binding, timing_verdict=")
    (out / 'run_once.py').write_text(runner)
    profiles = (base / 'profiles.py').read_text() + '\nPROFILES[' + repr(PROFILE) + '] = ' + repr(dict(defines=DEFINES, internal_macros=54, geometry=GEOMETRY)) + '\n'
    (out / 'profiles.py').write_text(profiles)
    components = (base / 'area_components.tcl').read_text()
    components = components.replace('    if {[string match {u_core/bias/*} $xu_rel]} {set xu_component bias}',
        '    if {[string match {u_core/biasMemory/*} $xu_rel]} {set xu_component bias_physical_sram}')
    components = components.replace('    if {[string match {u_core/xs_*/*} $xu_rel]} {',
        '    if {[string match {u_core/resultSlices*} $xu_rel]} {set xu_component result_physical_sram}\n'
        '    if {[string match {u_core/xSets*} $xu_rel]} {')
    components = components.replace('{u_core/engines_*/*}', '{u_core/rows*}').replace('engines_64pe', 'rows_64pe')
    (out / 'area_components.tcl').write_text(components)
    for collector in ('synth.tcl', 'pt_collect.tcl'):
        text = (out / collector).read_text()
        lines = text.splitlines(True)
        lines = [line.replace('report_constraint ', 'report_constraint -significant_digits 8 ') if 'report_constraint ' in line and '-significant_digits' not in line else line for line in lines]
        (out / collector).write_text(''.join(lines))
    changed = [name for name in sorted(bp) if sha(out / name) != bp[name] and name not in ('manifest.json', 'source-manifest.json')]
    patch = ''.join(''.join(difflib.unified_diff((base / name).read_text().splitlines(True), (out / name).read_text().splitlines(True), fromfile='base353/' + name, tofile='storage374/' + name)) for name in changed)
    (out / 'storage-vs-base.patch').write_text(patch)
    sm = json.loads((base / 'source-manifest.json').read_text())
    sm['defines'], sm['hardware_profile'] = DEFINES, PROFILE
    for row in sm['ordered_compile_sources']:
        if row['path'] in OVERLAYS:
            row['sha256'] = sha(out / row['path'])
            if 'bytes' in row:
                row['bytes'] = (out / row['path']).stat().st_size
    # Every staged-input origin is kept, with explicit replacement metadata.
    for name, row in sm['all_staged_inputs'].items():
        if (out / name).is_file():
            if sha(out / name) != row['sha256']:
                row.update(prior_base_sha256=row['sha256'], sha256=sha(out / name), bytes=(out / name).stat().st_size,
                           role='explicit_storage_geometry_or_runner_overlay')
    for path in sorted(out.rglob('*')):
        if path.is_file():
            name = str(path.relative_to(out))
            if name not in sm['all_staged_inputs'] and name not in ('manifest.json', 'source-manifest.json', 'package-files.json'):
                sm['all_staged_inputs'][name] = dict(origin='storage-stage/' + name, sha256=sha(path), bytes=path.stat().st_size, role='explicit_storage_preparation_input', reference_B_sha256=None)
    sm['storage_overlay'] = dict(manifest_sha256=STORAGE_SHA, base_package_files_sha256=BASE_SHA,
                                production_overlays=sorted(OVERLAYS))
    dump(out / 'source-manifest.json', sm)
    m = json.loads((base / 'manifest.json').read_text())
    m.update(hardware_profile=PROFILE, defines=DEFINES, expected_geometry=GEOMETRY,
        expected_internal_macros=54, storage_candidate_manifest_sha256=STORAGE_SHA,
        base_package_files_sha256=BASE_SHA, staged_core_sha256=sha(out / 'source/rtl/perips/LinearTileDmaCore.sv'),
        source_manifest_sha256=sha(out / 'source-manifest.json'),
        status='SEALED_OFFLINE_STORAGE_NOT_EXECUTED_NOT_QUALIFIED',
        cpu_full12_result_sha256=None, cpu_full12_evidence=cpu_evidence,
        cpu_core_and_mem_fab_exact_unchanged=True,
        qualification='No new area, timing, mapped equivalence or power result exists for final374 configuration')
    m['compile_policy']['new_synthesis_sha256'] = sha(out / 'synth.tcl')
    m['compile_policy']['base353_to_storage374_patch_sha256'] = sha(out / 'storage-vs-base.patch')
    m['storage_overlay_sha256'] = {name: dict(base=bp[name], selected=sha(out / name)) for name in sorted(OVERLAYS)}
    m['storage_prepare_tool_sha256'] = sha(Path(__file__))
    m['compile_policy']['allowed_differences'] += ['two explicitly sealed storage RTL overlays',
        'XU_MATRIX_STORAGE_SRAM selection', 'exact374 macros/64 direct MAC geometry',
        'all54 internal SRAM charge and fullSoC-standard-cell plus54 macro upper bound',
        'same-freeze production GPIO complete12 mandatory EDA gate',
        'constraint report precision8 only; all actual thresholds unchanged']
    if a.cpu_full12:
        m['cpu_full12_result_sha256'] = sha(a.cpu_full12)
    dump(out / 'manifest.json', m)
    # Seal every input. No prior execution, mapped results, or licenses copied.
    pinned = {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob('*')) if path.is_file()}
    dump(out / 'package-files.json', pinned)
    check_inputs(out)
    if a.cpu_full12:
        check_cpu_full12(out)
    require(sha(base / 'package-files.json') == BASE_SHA and sha(candidate / 'manifest.json') == STORAGE_SHA, 'origins changed during preparation')
    print(json.dumps(dict(status=m['status'], inputs=len(pinned), package_files_sha256=sha(out / 'package-files.json'),
                         cpu_full12_bound=bool(a.cpu_full12), out=str(out))))


if __name__ == '__main__':
    main()
