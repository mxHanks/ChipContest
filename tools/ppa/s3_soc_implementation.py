#!/usr/bin/env python3
"""Freeze a dirty S3 worktree and prepare an explicitly unqualified full-SoC manifest.

No EDA task is launched. The historical xu_soc_implementation generator and its
f49a5fc gate remain unchanged. S3 uses its own fixed baseline revisions and exact
runtime/verification/PPA source-byte manifest, including untracked source files.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
BASELINE_MAIN = 'ddccdc95b9aa1521c3e404b9d9f95b788fdae8a5'
BASELINE_E203 = 'a0767db69628ef30e53de2d1e93dd0360c0ccf76'


def load(root, relative):
    spec = importlib.util.spec_from_file_location('s3_'+Path(relative).stem, Path(root)/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ppa_module(root):
    return load(root, 'tools/scripts/xu_soc_ppa.py')


def baseline_identity(ppa, source):
    ppa.require(source['main_commit'] == BASELINE_MAIN and source['e203_commit'] == BASELINE_E203,
                'S3 baseline revision differs; review a new S3 baseline explicitly')


def freeze(root, out, profile):
    root, out = Path(root).resolve(), Path(out).absolute()
    ppa = ppa_module(root)
    ppa.require(not out.exists(), 'output directory exists')
    ppa.inventory(root, profile)  # actual generated storage identity and geometry
    source = ppa.s3_worktree_sources(root)
    baseline_identity(ppa, source)
    ppa.require(source == ppa.s3_worktree_sources(root), 'source changed while freezing S3 worktree')
    source.update(hardware_profile=profile,
                  status='FROZEN_NOT_QUALIFIED',
                  note='Dirty/untracked source bytes are deliberately included; no Git commit or qualification asserted.')
    out.mkdir(parents=True)
    ppa.write(out/'source-freeze.json', source)
    receipt = dict(schema='s3-full-soc-freeze-generation-v1', status='FROZEN_NOT_QUALIFIED',
                   hardware_profile=profile, file_count=len(source['source_files']),
                   source_manifest_sha256=ppa.digest(source['source_files']),
                   worktree_freeze=dict(path=str(out/'source-freeze.json'), sha256=ppa.sha(out/'source-freeze.json')),
                   qualification='NOT_QUALIFIED')
    ppa.write(out/'freeze-generation.json', receipt)
    return receipt


def s3_topology(ppa, root, legacy):
    sources = legacy.topology_identity(ppa, root)
    checks = [
        (ppa.RTL+'/core/e203_cpu_top.v', r'\be203_cpu\s*#\s*\(.*?\)\s*u_e203_cpu\s*\(', 'CPU/NICE parent'),
        (ppa.RTL+'/core/e203_cpu.v', r'\be203_subsys_nice_core\s+u_e203_nice_core\s*\(', 'entire NICE extension'),
        (ppa.RTL+'/subsys/e203_subsys_nice_core.v', r'\bxu_nice_drain8\s+u_drain8\s*\(', 'NICE drain8'),
        (ppa.RTL+'/perips/LinearAutoGroupCore.sv', r'\bLinearComputeCore\s+core\s*\(', 'weight core parent'),
        (ppa.RTL+'/perips/LinearComputeCore.sv', r'\bWeightBankArray\s+weightBanks\s*\(', 'weight bank parent'),
    ]
    for relative, pattern, label in checks:
        path = root/relative
        ppa.require(re.search(pattern, ppa.comments(path.read_text()), re.S), 'S3 source hierarchy differs: '+label)
        sources[relative] = legacy.identity(ppa, path)
    return sources


def generate(root, out, worktree_freeze, freeze_sha, standard_db, standard_sha,
             sram_db, sram_sha, clock_review, firmware_schedule=None,
             activity_clock_profile='nominal150-balanced-v1'):
    root, out = Path(root).resolve(), Path(out).absolute()
    ppa = ppa_module(root)
    legacy = load(root, 'tools/ppa/xu_soc_implementation.py')
    ppa.require(not out.exists(), 'output directory exists')
    frozen_identity = legacy.identity(ppa, worktree_freeze, freeze_sha)
    frozen = json.loads(Path(frozen_identity['path']).read_text())
    baseline_identity(ppa, frozen)
    profile = frozen.get('hardware_profile')
    ppa.require(profile in ppa.S3_PROFILES, 'explicit frozen S3 profile is required')
    inv = ppa.inventory(root, profile)
    ppa.check_s3_worktree_freeze(dict(hardware_profile=profile, worktree_freeze=frozen_identity), inv)
    libraries = [dict(legacy.identity(ppa, standard_db, standard_sha), role='standard_cell'),
                 dict(legacy.identity(ppa, sram_db, sram_sha), role='sram')]
    ppa.require(libraries[0]['path'] != libraries[1]['path'], 'standard-cell and SRAM library paths must differ')
    # An explicit, source-bound clock review is mandatory. No fabricated review
    # or library/PVT/mapped-equivalence PASS is generated here.
    review = legacy.review_identity(ppa, root, clock_review)
    topology = s3_topology(ppa, root, legacy)
    impl = ppa.template(inv)
    impl['firmware_schedule'] = firmware_schedule
    impl['transaction_contract'] = ppa.s3_transaction_contract(root, firmware_schedule)
    ppa.require(activity_clock_profile in ppa.S3_CLOCK_PROFILES, 'unknown S3 activity clock profile')
    impl['activity_clock_profile'] = activity_clock_profile
    impl['worktree_freeze'] = frozen_identity
    impl['replacements'] = {
        ppa.RTL+'/general/sirv_sim_ram.v': legacy.identity(ppa, root/'tools/ppa/xu_sirv_sram_adapter.sv'),
        ppa.RTL+'/perips/mem_1024x16.sv': legacy.identity(ppa, root/'tools/ppa/xu_weight_sram_adapter.sv')}
    impl['added_sources'] = [legacy.identity(ppa, root/'tools/ppa'/name)
                             for name in ['xu_soc_ppa_top.sv', 'xu_shared_icb_sram.sv']]
    impl['libraries'] = libraries
    impl['constraints'] = legacy.identity(ppa, root/'tools/ppa/xu_full_soc.sdc')
    impl['clock_review'] = review
    impl['source_freeze'] = dict(main_commit=frozen['main_commit'], e203_commit=frozen['e203_commit'],
                                 topology_sources=topology,
                                 worktree_source_manifest_sha256=ppa.digest(frozen['source_files']))
    count = sum(g['count'] for g in impl['memory_groups'])
    impl['note'] = ('S3 development only, exact %d RAMSP1024X16 macros. Accelerator area includes disjoint '
                    'peripheral and entire CPU NICE extension (routing/control/demo/drain8); energy scope is '
                    'the full digital SoC and all SRAMs. Including the historical demo is conservative and '
                    'is not the official net-added area: baseline subtraction and integration attribution '
                    'remain pending. Register bias costs standard cells. Mapping, PVT, '
                    'STA, task clear, mapped activity and qualification remain unreviewed.' % count)
    out.mkdir(parents=True)
    proof_path = out/'mapping-proof.json'
    ppa.write(proof_path, ppa.mapping_review_template(impl))
    impl['mapping_proof'] = legacy.identity(ppa, proof_path)
    _, _, gaps = ppa.checked_implementation(impl, inv, allow_unqualified=True)
    ppa.write(out/'inventory.json', inv)
    ppa.write(out/'implementation.json', impl)
    receipt = dict(schema='s3-full-soc-implementation-generation-v1', status='GENERATED_NOT_QUALIFIED',
                   hardware_profile=profile, implementation=legacy.identity(ppa, out/'implementation.json'),
                   worktree_freeze=frozen_identity, macro_total=count, qualification_gaps=gaps,
                   accelerator_area_scopes=impl['accelerator_area_scopes'], energy_scope='full-digital-soc-including-all-srams',
                   accelerator_area_policy=impl['accelerator_area_policy'],
                   official_incremental_area_review='PENDING: whole NICE includes historical demo; no baseline subtraction claimed',
                   generator_sha256=ppa.sha(__file__),
                   pending=['No DC/PT or mapped replay has run.', 'No library/PVT eligibility or timing/area/energy result.',
                            'NICE and bias activity, clear policy and all qualification gaps require original evidence.'])
    ppa.write(out/'generation.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action')
    freeze_parser = sub.add_parser('freeze', help='bind current S3 source bytes, without requiring EDA libraries')
    freeze_parser.add_argument('--root', type=Path, default=ROOT)
    freeze_parser.add_argument('--out', type=Path, required=True)
    freeze_parser.add_argument('--profile', choices=('s3-y32-bias-sram', 's3-y32-bias-registers'), required=True)
    generate_parser = sub.add_parser('generate', help='generate manifest only with explicit real library/clock-review inputs')
    generate_parser.add_argument('--root', type=Path, default=ROOT)
    generate_parser.add_argument('--out', type=Path, required=True)
    generate_parser.add_argument('--firmware-schedule', required=True)
    generate_parser.add_argument('--activity-clock-profile', default='nominal150-balanced-v1')
    for flag in ['worktree-freeze', 'standard-cell-db', 'sram-db', 'clock-review']:
        generate_parser.add_argument('--'+flag, type=Path, required=True)
    for flag in ['worktree-freeze-sha256', 'standard-cell-sha256', 'sram-sha256']:
        generate_parser.add_argument('--'+flag, required=True)
    args = parser.parse_args(argv)
    if args.action is None:
        parser.error('freeze or generate action is required')
    if args.action == 'freeze':
        receipt = freeze(args.root, args.out, args.profile)
    else:
        receipt = generate(args.root, args.out, args.worktree_freeze, args.worktree_freeze_sha256,
                           args.standard_cell_db, args.standard_cell_sha256, args.sram_db, args.sram_sha256,
                           args.clock_review, args.firmware_schedule, args.activity_clock_profile)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print('FAIL: '+str(exc), file=sys.stderr)
        sys.exit(1)
