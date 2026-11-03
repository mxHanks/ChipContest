#!/usr/bin/env python3
"""Create a hash-bound full-SoC implementation manifest for development DC/PT.

Uses only repository RTL/SDC and explicitly supplied standard-cell/SRAM .db
files. No vendor simulation model is copied or added to synthesis sources.
The mapping proof starts UNREVIEWED; use --allow-unqualified-mapping in the
PPA preparation command until real qualification evidence has been reviewed.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FROZEN_E203 = 'f49a5fc914971426bd4530db39e270a84b41139f'


def ppa_module(tool_root=ROOT):
    # Source --root is deliberately independent of the producer/tool assets.
    # Importing a candidate's old PPA module silently loses current guardrails.
    spec = importlib.util.spec_from_file_location('xu_soc_ppa', tool_root/'tools/scripts/xu_soc_ppa.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identity(ppa, path, expected=None):
    path = Path(path).absolute()
    ppa.require(path.is_file() and not path.is_symlink(), 'not a regular non-symlink file: '+str(path))
    actual = ppa.sha(path)
    if expected is not None:
        ppa.require(re.fullmatch('[0-9a-f]{64}', expected) is not None and actual == expected,
                    'supplied SHA256 differs: '+str(path))
    return dict(path=str(path), sha256=actual)


def review_identity(ppa, root, path, tool_root=ROOT):
    record = identity(ppa, path)
    review = json.loads(Path(record['path']).read_text())
    ppa.require(review.get('schema') == 'xu-full-soc-clock-review-v1' and review.get('status') == 'REVIEWED',
                'a real source-derived clock review is required')
    sources = review.get('source_files', {})
    required = ['tools/ppa/xu_soc_ppa_top.sv', 'tools/ppa/xu_shared_icb_sram.sv',
                'tools/ppa/xu_full_soc.sdc', 'tools/ppa/xu_review_full_soc_clocks.py']
    ppa.require(all(name in sources for name in required), 'clock review lacks current top/SDC/reviewer source identities')
    for relative, item in sources.items():
        ppa.require(not Path(relative).is_absolute() and '..' not in Path(relative).parts,
                    'clock review source key must be repository-relative')
        source=(tool_root if relative.startswith('tools/') else root)/relative
        ppa.require(identity(ppa, source)['sha256'] == item.get('sha256'),
                    'clock-reviewed source changed: '+relative)
        ppa.require(Path(item.get('path','')).resolve()==source.resolve(),
                    'clock-reviewed source origin differs: '+relative)
    ppa.require(review.get('constraints_sha256') == ppa.sha(tool_root/'tools/ppa/xu_full_soc.sdc'),
                'clock review SDC changed')
    return record


def topology_identity(ppa, root, tool_root=ROOT):
    # Source guards locate the hierarchy later checked against actual linked
    # cells/ref_names by DC/PT. They are not an elaboration/equivalence result.
    checks = [
        ('tools/ppa/xu_soc_ppa_top.sv', r'\be203_soc_top\s*#\s*\(\.EXTERNAL_SYSMEM\(1\)\)\s+u_soc\s*\(', 'full SoC boundary'),
        ('tools/ppa/xu_soc_ppa_top.sv', r'\bxu_shared_icb_sram\s+u_shared\s*\(', 'shared SRAM boundary'),
        (ppa.RTL+'/soc/e203_soc_top.v', r'\be203_subsys_top\s+u_e203_subsys_top\s*\(', 'SoC subsystem'),
        (ppa.RTL+'/subsys/e203_subsys_top.v', r'\be203_subsys_main\s+u_e203_subsys_main\s*\(', 'main subsystem'),
        (ppa.RTL+'/subsys/e203_subsys_main.v', r'\be203_cpu_top\s+u_e203_cpu_top\s*\(', 'CPU'),
        (ppa.RTL+'/subsys/e203_subsys_main.v', r'\be203_subsys_perips\s+u_e203_subsys_perips\s*\(', 'peripheral subsystem'),
        (ppa.RTL+'/subsys/e203_subsys_perips.v', r'\baccel_icb_slave\s+u_accel_icb_slave\s*\(', 'accelerator'),
        (ppa.RTL+'/subsys/e203_subsys_perips.v', r'\bsirv_icb1to16_bus\s*#\s*\(.*?\)\s*u_sirv_ppi_fab\s*\(', 'interconnect'),
        (ppa.RTL+'/core/e203_cpu_top.v', r'\be203_srams\s+u_e203_srams\s*\(', 'TCM SRAM hierarchy'),
        (ppa.RTL+'/core/e203_srams.v', r'\be203_itcm_ram\s+u_e203_itcm_ram\s*\(', 'ITCM'),
        (ppa.RTL+'/core/e203_srams.v', r'\be203_dtcm_ram\s+u_e203_dtcm_ram\s*\(', 'DTCM'),
        ('tools/ppa/xu_shared_icb_sram.sv', r'\bsirv_sim_ram\s*#\s*\(.*?\)\s*storage\s*\(', 'shared macro storage'),
    ]
    sources = {}
    for relative, pattern, label in checks:
        path = (tool_root if relative.startswith('tools/') else root)/relative
        ppa.require(re.search(pattern, ppa.comments(path.read_text()), re.S) is not None,
                    'current source hierarchy differs: '+label)
        sources[relative] = identity(ppa, path)
    return sources


def generate(root, out, standard_db, standard_sha, sram_db, sram_sha, clock_review=None,
             profile='baseline', bias_sram_db=None, bias_sram_sha=None):
    root = Path(root).resolve()
    out = Path(out).absolute()
    ppa = ppa_module()
    ppa.require(not out.exists(), 'output directory exists')
    libraries = [dict(identity(ppa, standard_db, standard_sha), role='standard_cell'),
                 dict(identity(ppa, sram_db, sram_sha), role='sram')]
    ppa.require(libraries[0]['path'] != libraries[1]['path'], 'standard-cell and SRAM library paths must differ')
    if profile=='sram-bias':
        ppa.require(bias_sram_db is not None and bias_sram_sha is not None,
                    'sram-bias profile requires --bias-sram-db and --bias-sram-sha256')
        libraries.append(dict(identity(ppa,bias_sram_db,bias_sram_sha),role='bias_sram'))
    else:
        ppa.require(bias_sram_db is None and bias_sram_sha is None,
                    'bias SRAM library is allowed only for sram-bias profile')
    ppa.require(len({record['path'] for record in libraries})==len(libraries),'library paths must differ')
    profile_identity=ppa.source_profile_identity(root,profile)
    inv = ppa.inventory(root)
    topology = topology_identity(ppa, root)
    if clock_review is not None:
        review = review_identity(ppa, root, clock_review)
    out.mkdir(parents=True)
    if clock_review is None:
        command = [sys.executable, str(ROOT/'tools/ppa/xu_review_full_soc_clocks.py'),
                   '--root',str(root),'--tool-root',str(ROOT),'--out', str(out/'clock-review')]
        result = subprocess.run(command, cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=120)
        (out/'clock-review-generation.log').write_text(json.dumps(command)+'\n'+result.stdout)
        ppa.require(result.returncode == 0, 'clock review failed; inspect '+str(out/'clock-review-generation.log'))
        review = review_identity(ppa, root, out/'clock-review/clock-review.json')
    impl = ppa.template(inv,profile)
    impl['tool_assets_root']=str(ROOT)
    impl['replacements'] = {
        ppa.RTL+'/general/sirv_sim_ram.v': identity(ppa, ROOT/'tools/ppa/xu_sirv_sram_adapter.sv'),
        ppa.RTL+'/perips/mem_1024x16.sv': identity(ppa, ROOT/'tools/ppa/xu_weight_sram_adapter.sv')}
    if profile=='sram-bias':
        impl['replacements'][ppa.BIAS_MEMORY]=identity(ppa,ROOT/'tools/ppa/xu_bias_sram_adapter.sv',ppa.BIAS_ADAPTER_SHA256)
    impl['added_sources'] = [identity(ppa, ROOT/'tools/ppa'/name)
                             for name in ['xu_soc_ppa_top.sv', 'xu_shared_icb_sram.sv']]
    impl['libraries'] = libraries
    impl['constraints'] = identity(ppa, ROOT/'tools/ppa/xu_full_soc.sdc')
    impl['clock_review'] = review
    impl['source_freeze'] = dict(main_commit=inv['main_commit'], e203_commit=inv['e203_commit'],
                                 profile=profile_identity,
                                 topology_sources=topology,
                                 memory_groups_sha256=ppa.digest(impl['memory_groups']),
                                 libraries_sha256=ppa.digest(libraries),
                                 source_manifest_sha256=inv['platform_source_manifest_sha256'])
    impl['tool_producer'] = dict(implementation_generator=identity(ppa,__file__),
                                ppa=identity(ppa,ppa.__file__),
                                clock_reviewer=identity(ppa,ROOT/'tools/ppa/xu_review_full_soc_clocks.py'))
    impl['note'] = ('Actual '+profile+' full-digital-SoC development configuration, exact 336 RAMSP1024X16 macros. '
                    +('Bias SRAM adds 24 RAMSP128X16: 10240 logical bits, 49152 physical bits including 38912 padding bits. '
                      if profile=='sram-bias' else '')+
                    'Mapping/PVT/netlist equivalence are unreviewed; no timing, power, or contest pass claimed. '
                    'No vendor simulation models are in the synthesis source list.')
    proof_path = out/'mapping-proof.json'
    ppa.write(proof_path, ppa.mapping_review_template(impl))
    impl['mapping_proof'] = identity(ppa, proof_path)
    _, _, gaps = ppa.checked_implementation(impl, inv, allow_unqualified=True)
    ppa.write(out/'inventory.json', inv)
    ppa.write(out/'implementation.json', impl)
    receipt = dict(schema='xu-full-soc-implementation-generation-v1', status='GENERATED_NOT_QUALIFIED',
                   implementation=identity(ppa, out/'implementation.json'), qualification_gaps=gaps,
                   macro_total=sum(group['count'] for group in impl['memory_groups']),
                   source_profile=profile_identity, tool_producer=impl['tool_producer'],
                   generator_sha256=ppa.sha(__file__))
    ppa.write(out/'generation.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--standard-cell-db', required=True, type=Path)
    parser.add_argument('--standard-cell-sha256', required=True)
    parser.add_argument('--sram-db', required=True, type=Path)
    parser.add_argument('--sram-sha256', required=True)
    parser.add_argument('--profile',choices=['baseline','h2-only','sram-bias','s2b-packed','s2c-autogroup'],default='baseline',
                        help='explicit approved child/source geometry; baseline remains strict f49a5fc')
    parser.add_argument('--bias-sram-db',type=Path,help='RAMSP128X16 library; required only for sram-bias')
    parser.add_argument('--bias-sram-sha256',help='supplied RAMSP128X16 library SHA256; required only for sram-bias')
    parser.add_argument('--clock-review', type=Path, help='existing source-derived review; otherwise generate one now')
    args = parser.parse_args()
    receipt = generate(args.root, args.out, args.standard_cell_db, args.standard_cell_sha256,
                       args.sram_db, args.sram_sha256, args.clock_review,
                       args.profile,args.bias_sram_db,args.bias_sram_sha256)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print('FAIL: '+str(exc), file=sys.stderr)
        sys.exit(1)
