#!/usr/bin/env python3
"""Seal original1064 N3 development PPA inputs; no EDA, no candidate RTL edits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_SHA = 'b2a7727bbcefdcb41efd2b41889e8bcf323c69625360fd63a0f8cf047b4c7e9e'
FILES = ['profiles.py', 'run_once.py', 'synth.tcl', 'pt_collect.tcl', 'preflight.py', 'prepare.py', 'README.md']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base', type=Path, default=ROOT / 'build/ingress-perf-20261113/ppa-native-r1')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base, out = a.base.resolve(), a.out.resolve()
    assert not out.exists() and sha(base / 'package-files.json') == BASE_SHA
    pinned = json.loads((base / 'package-files.json').read_text())
    out.mkdir(parents=True)
    for name, digest in pinned.items():
        q = Path(name)
        assert not q.is_absolute() and '..' not in q.parts and '\\' not in name
        assert (base / q).is_file() and not (base / q).is_symlink() and sha(base / q) == digest
        target = out / q
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / q, target)
    for name in FILES:
        shutil.copyfile(HERE / name, out / name)
    for name in ['hierarchy_contract.tcl', 'xu_soc_sysbus32_ppa_top.sv']:
        shutil.copyfile(HERE / name, out / 'source/ppa' / name)
    from profiles import PROFILES, SRAM_X
    definitions = PROFILES[SRAM_X]['defines']
    dump(out / 'defines.json', definitions)
    (out / 'source/ppa/geometry-profile.tcl').write_text(
        '# Sealed exact hardware profile. No timing or constraint edits.\n'
        'set sysbus32_hardware_profile {' + SRAM_X + '}\n'
        'set sysbus32_production_defines [list ' + ' '.join(definitions) + ']\n'
        'set sysbus32_expected_total_macros 353\nset sysbus32_expected_x_macros 16\n'
        'set sysbus32_expected_internal_macros 33\n')
    m = json.loads((base / 'manifest.json').read_text())
    sm = json.loads((base / 'source-manifest.json').read_text())
    sm.update(hardware_profile=SRAM_X, defines=definitions)
    for row in sm['ordered_compile_sources']:
        row['sha256'] = sha(out / row['path'])
        row['bytes'] = (out / row['path']).stat().st_size
    names = [row['path'] for row in sm['ordered_compile_sources']]
    changed = {name for name in names if sha(out / name) != pinned[name]}
    assert changed == {'source/ppa/xu_soc_sysbus32_ppa_top.sv'}, changed
    for name, row in sm['all_staged_inputs'].items():
        if (out / name).is_file() and sha(out / name) != row['sha256']:
            row.update(prior_sha256=row['sha256'], sha256=sha(out / name), bytes=(out / name).stat().st_size,
                       role='explicit_N3_development_PPA_only_top_or_flow_update')
    dump(out / 'source-manifest.json', sm)
    cpu = ROOT / 'build/ingress-perf-20261113/cpu-campaign-r1/full12/result.json'
    cr = json.loads(cpu.read_text())
    assert cr['status'] == 'PASS' and cr['total_cycles'] == 1691172 and cr['outputs'] == 304128
    shutil.copyfile(cpu, out / 'evidence/development-cpu1064-full12.json')
    shutil.copyfile(base / 'package-files.json', out / 'evidence/original-N2-package-files.json')
    m.update(hardware_profile=SRAM_X, defines=definitions, production_test_loader=True,
        status='SEALED_N3_DEVELOPMENT_INPUTS_NOT_EXECUTED_NOT_QUALIFIED',
        source_manifest_sha256=sha(out / 'source-manifest.json'),
        original_N2_package_sha256=BASE_SHA, candidate_child_commit='5470c5650f2d11d16e7c52cc96626d21030a3973',
        candidate_parent_commit='1aceb3d607bb8e9fb0414b84a70eb0766c414bc3',
        resource_policy=dict(user_authorized_cap=8, requested_cores=8, linux_affinity_cores=8,
            source='User explicitly authorized multi-core for speed after prior2core preference',
            reserve_at_least_two_other_allowed_cpus=True, one_own_eda_stage_at_a_time=True),
        physical_profile=dict(ingress_sources=3, pointer_bits=2, owner_entries=4,
            full_soc_macros=353, cpu_macros=64, shared_macros=256, internal_macros=33,
            result_macros=0, exposed_loader_interface_bits=106),
        development_measurement=dict(result_sha256=sha(cpu), total_cycles=1691172, outputs=304128,
            assumed_clock_hz=150000000, conditional_tasks_per_second=1064.3506,
            CPU_actual_functional_RAMSP_models=289, CPU_behavioral_ITCM_DTCM=True,
            CPU_defines=['DISABLE_SV_ASSERTION=1','XU_MATRIX_DMA','XU_MATRIX_DMA_SYSBUS32',
                        'XU_SYSBUS_TEST_LOADER','XU_MATRIX_X_SRAM'],
            source_scope='Original source/core/DMA/ingress; PPA-only106bit direct loader top exposure and physical CPU SRAM adapters',
            production_or_SDK_throughput_certified=False),
        production_qualification='DEVELOPMENT_N3_LOADER_CANDIDATE_NOT_PRODUCTION1000_CERTIFICATION')
    m['compile_policy']['retained_commands'][0] = 'set_host_options -max_cores 8'
    m['compile_policy'].update(new_synthesis_sha256=sha(out / 'synth.tcl'), own_svf='final.svf',
        resource_change='Explicit new user authorization cap8; original other compile/SDC/library policy unchanged',
        PPA_only_compile_source_delta=sorted(changed))
    for command in m['compile_policy']['retained_commands']:
        assert (out / 'synth.tcl').read_text().count(command) == 1, command
    dump(out / 'manifest.json', m)
    files = {path.relative_to(out).as_posix(): sha(path) for path in sorted(out.rglob('*'))
             if path.is_file() and path.name != 'package-files.json'}
    dump(out / 'package-files.json', files)
    checked = subprocess.run(['python3', '-B', str(out / 'run_once.py')], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stderr
    print(json.dumps(dict(status='SEALED_N3_DEVELOPMENT_NOT_EDA_EXECUTED', out=str(out),
        package_files_sha256=sha(out / 'package-files.json'), inputs=len(files), source_count=len(names),
        PPA_only_source_delta=sorted(changed), review=json.loads(checked.stdout)), sort_keys=True))


if __name__ == '__main__':
    main()
