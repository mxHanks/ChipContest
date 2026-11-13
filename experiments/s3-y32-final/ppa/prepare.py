#!/usr/bin/env python3
"""Freeze DMA4/storage21 production inputs, or bind actual CPU12 into a NEW copy.

This tool neither starts EDA nor copies old mapped results. CPU12 consumes the
first immutable source package; the final EDA package keeps exactly those RTL
bytes/defines and adds raw CPU evidence. This avoids a circular package hash.
"""
import argparse
import difflib
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from controls import BASE_SHA, DEFINES, GEOMETRY, OVERLAYS, PROFILE, check_inputs, check_cpu_full12, sha, require

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOLS = ['controls.py', 'preflight.py', 'README.md', 'run_once.py', 'synth.tcl',
         'pt_collect.tcl', 'area_components.tcl', 'review_native.py', 'prepare.py']


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def copy(source, target):
    require(source.is_file() and not source.is_symlink(), 'missing/linked source: ' + str(source))
    before = sha(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    require(sha(source) == before == sha(target), 'source drift while copying: ' + str(source))


def seal(out):
    pinned = {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*'))
              if p.is_file() and p.name != 'package-files.json'}
    dump(out / 'package-files.json', pinned)
    check_inputs(out)
    return pinned


def bind_cpu(a, out):
    source = a.source_package.resolve()
    pinned, m = check_inputs(source)
    require(not m.get('cpu_full12_result_sha256'), 'CPU source must be original pre-CPU source package')
    runpath = a.cpu_full12.resolve()
    run = json.loads(runpath.read_text())
    require(run['ppa_binding']['package_files_sha256'] == sha(source / 'package-files.json'),
            'CPU did not execute selected immutable source package')
    for name in pinned:
        copy(source / name, out / name)
    # Flow reviewers may improve while CPU runs. Refresh only non-RTL tools;
    # production RTL, defines, source order and SDC remain the initial freeze.
    for name in TOOLS:
        copy(HERE / name, out / name)
    cpu_root = runpath.parent
    artifacts = [('simulation.log', 'cpu-full12-simulation.log'),
                 ('source/check_results.py', 'cpu-full12-checker.py'),
                 ('firmware/dma_day_soc', 'cpu-full12.elf'),
                 ('firmware/dma_day_soc.verilog', 'cpu-full12.image')]
    for original, target in artifacts:
        copy(cpu_root / original, out / 'evidence' / target)
    copy(runpath, out / 'evidence/cpu-full12.json')
    copy(source / 'package-files.json', out / 'evidence/cpu-source-package-files.json')
    m.update(cpu_full12_result_sha256=sha(runpath),
             cpu_source_package_files_sha256=sha(source / 'package-files.json'),
             cpu_full12_evidence={name: sha(out / 'evidence' / name) for _, name in artifacts},
             final_flow_tool_sha256={name: sha(out / name) for name in TOOLS},
             status='SEALED_FINAL_CPU12_BOUND_EDA_NOT_EXECUTED_NOT_QUALIFIED')
    m['cpu_source_git_identity'] = {name: m.get(name) for name in
        ['final_parent_commit', 'final_child_commit', 'final_parent_status', 'final_child_status']}
    root = a.root.resolve()
    child = root / 'third-party/e203_hbirdv2'
    m.update(final_parent_commit=subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
        final_child_commit=subprocess.check_output(['git', '-C', str(child), 'rev-parse', 'HEAD'], text=True).strip(),
        final_parent_status=subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True).splitlines(),
        final_child_status=subprocess.check_output(['git', '-C', str(child), 'status', '--porcelain'], text=True).splitlines())
    m['compile_policy']['new_synthesis_sha256'] = sha(out / 'synth.tcl')
    dump(out / 'manifest.json', m)
    seal(out)
    check_cpu_full12(out)


def initial(a, out):
    root, base = a.root.resolve(), a.base.resolve()
    require(sha(base / 'package-files.json') == BASE_SHA, 'not pinned353 source-order/library reference')
    bp = json.loads((base / 'package-files.json').read_text())
    for name, digest in bp.items():
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and '\\' not in name, 'unsafe base name')
        require(sha(base / name) == digest and not (base / name).is_symlink(), 'base input drift: ' + name)
        copy(base / name, out / name)
    names = (base / 'rtl.f').read_text().splitlines()
    origins = {}
    for name in names:
        if name == 'source/rtl/general/sirv_sim_ram.v':
            origin = root / 'tools/ppa/xu_sirv_sram_adapter.sv'
        elif name == 'source/rtl/perips/mem_1024x16.sv':
            origin = root / 'tools/ppa/xu_weight_sram_adapter.sv'
        elif name.startswith('source/rtl/'):
            origin = root / 'third-party/e203_hbirdv2/rtl/e203' / name.removeprefix('source/rtl/')
        elif name == 'source/ppa/xu_soc_sysbus32_ppa_top.sv':
            origin = root / 'experiments/s3-y32-compliant32/structure/xu_soc_sysbus32_ppa_top.sv'
        elif name == 'source/ppa/xu_shared_icb_sram.sv':
            origin = root / 'tools/ppa/xu_shared_icb_sram.sv'
        else:
            raise ValueError('unreviewed compile source origin: ' + name)
        copy(origin, out / name)
        origins[name] = dict(origin=str(origin.relative_to(root)), sha256=sha(out / name),
            bytes=(out / name).stat().st_size, base353_sha256=bp[name],
            role='final_dma4_storage21_ingress_overlay' if name in OVERLAYS else 'unchanged_production_platform')
    require({n for n in names if sha(out / n) != bp[n]} == OVERLAYS,
            'unexpected source delta; final candidate requires exactly core+DMA4+ingress overlays')
    for name in TOOLS:
        copy(HERE / name, out / name)
    copy(HERE / 'hierarchy_contract.tcl', out / 'source/ppa/hierarchy_contract.tcl')
    copy(base / 'package-files.json', out / 'evidence/base-package-files.json')
    copy(base / 'source/contracts/reference-full-soc.sdc', out / 'evidence/original-full-soc.sdc')
    # Macro wrapper model is explicitly local-only, absent from rtl.f/native PPA.
    copy(root / 'tools/ppa/generic_ramsp_non_ppa.sv', out / 'local-only/generic_ramsp_non_ppa.sv')
    dump(out / 'defines.json', DEFINES)
    (out / 'source/ppa/geometry-profile.tcl').write_text(
        '# Final exact DMA4/storage21 profile. Original constraints unchanged.\n'
        'set sysbus32_hardware_profile {' + PROFILE + '}\n'
        'set sysbus32_production_defines [list ' + ' '.join(DEFINES) + ']\n'
        'set sysbus32_expected_total_macros 374\nset sysbus32_expected_x_macros 16\n'
        'set sysbus32_expected_internal_macros 54\nset sysbus32_expected_result_macros 21\n')
    policy = json.loads((base / 'area-charge-policy.json').read_text())
    policy.update(charged_internal_macro_groups=dict(weights=16, bias=1, x=16, result=21),
                  timing_scope='full digital SoC including all374 SRAMs',
                  result_storage=dict(all_physical_macros_charged=True, logical_bits=5248,
                                      physical_bits=344064, physical_macro_count=21))
    policy['conservative_upper_bound']['internal_SRAM_macros'] = 54
    for row in policy['charged_scopes']:
        if row['scope'] == 'dma':
            row['policy'] = 'all standard cells plus all54 internal RAMSP1024X16 macros'
            row['components'] = ['dma4_frontend_and_scheduler', 'rows_64pe', 'core_control', 'x_physical_sram_buffers',
                                 'weights', 'bias_physical_sram', 'result_physical_sram']
    dump(out / 'area-charge-policy.json', policy)
    sm = dict(schema='sysbus32-exact-per-source-v1', hardware_profile=PROFILE,
        top='xu_soc_sysbus32_ppa_top', defines=DEFINES,
        local_only_source='local-only/generic_ramsp_non_ppa.sv',
        ordered_compile_sources=[dict(path=n, sha256=sha(out / n), bytes=(out / n).stat().st_size) for n in names],
        all_staged_inputs=origins)
    dump(out / 'source-manifest.json', sm)
    commands = ['set_host_options -max_cores 2',
        'set_boundary_optimization [get_cells -hierarchical -filter {is_hierarchical == true}] false',
        'set_dont_touch [get_cells -hierarchical -filter {ref_name == RAMSP1024X16}] true',
        'set_fix_hold [all_clocks]', 'compile_ultra -no_autoungroup',
        'set XU_CLOCK_MODE envelope', 'set XU_PLL_DIV 0', 'source source/contracts/reference-full-soc.sdc']
    for command in commands:
        require((base / 'synth.tcl').read_text().count(command) == 1, 'reference compile policy drift: ' + command)
    patch = ''.join(''.join(difflib.unified_diff((base / n).read_text().splitlines(True),
        (out / n).read_text().splitlines(True), fromfile='base353/' + n, tofile='final/' + n))
        for n in sorted(OVERLAYS | {'synth.tcl', 'pt_collect.tcl'}))
    (out / 'final-vs-base.patch').write_text(patch)
    m = json.loads((base / 'manifest.json').read_text())
    child = root / 'third-party/e203_hbirdv2'
    m.update(hardware_profile=PROFILE, defines=DEFINES, expected_geometry=GEOMETRY,
        expected_internal_macros=54, production_test_loader=False,
        status='SEALED_FINAL_PRODUCTION_SOURCE_CPU12_PENDING_EDA_FORBIDDEN',
        base_package_files_sha256=BASE_SHA, source_manifest_sha256=sha(out / 'source-manifest.json'),
        rtl_f_sha256=sha(out / 'rtl.f'), source_count=len(names),
        production_rtl_files={n: sha(out / n) for n in sorted(names)},
        production_overlays={n: sha(out / n) for n in sorted(OVERLAYS)},
        staged_core_sha256=sha(out / 'source/rtl/perips/LinearTileDmaCore.sv'),
        final_parent_commit=subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
        final_child_commit=subprocess.check_output(['git', '-C', str(child), 'rev-parse', 'HEAD'], text=True).strip(),
        final_parent_status=subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True).splitlines(),
        final_child_status=subprocess.check_output(['git', '-C', str(child), 'status', '--porcelain'], text=True).splitlines(),
        cpu_full12_result_sha256=None, cpu_source_package_files_sha256=None, cpu_full12_evidence=None,
        qualification='No final area, STA, mapped equivalence or power result exists; old353/374 results are historical only')
    m['compile_policy'] = dict(retained_commands=commands, original_sdc_byte_identical=True,
        new_synthesis_sha256=sha(out / 'synth.tcl'), own_svf='final.svf',
        source_delta_patch_sha256=sha(out / 'final-vs-base.patch'),
        changed_flow='geometry/area guards, complete source and CPU binding, report precision, own SVF; compile policy unchanged')
    dump(out / 'manifest.json', m)
    seal(out)
    require(sha(base / 'package-files.json') == BASE_SHA, 'reference changed during seal')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--base', type=Path, help='pinned353 inputs only; never mapped results')
    p.add_argument('--source-package', type=Path, help='initial final production source package to copy unchanged')
    p.add_argument('--cpu-full12', type=Path, help='actual same-package complete12 result.json')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    require(bool(a.base) != bool(a.source_package), 'select --base OR --source-package')
    require(bool(a.source_package) == bool(a.cpu_full12), '--source-package and --cpu-full12 required together')
    out = a.out.resolve()
    require(not out.exists(), 'new output required; never overwrite')
    out.mkdir(parents=True)
    if a.source_package:
        bind_cpu(a, out)
    else:
        initial(a, out)
    print(json.dumps(dict(out=str(out), package_files_sha256=sha(out / 'package-files.json'),
        cpu_full12_bound=bool(a.cpu_full12), source_count=json.loads((out / 'manifest.json').read_text())['source_count'],
        status='SEALED_OFFLINE_NOT_EXECUTED_NOT_QUALIFIED'), sort_keys=True))


if __name__ == '__main__':
    main()
