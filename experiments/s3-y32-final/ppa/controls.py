"""One exact DMA4/storage21 production profile; no old PPA result inheritance."""
import hashlib
import importlib.util
import json
from pathlib import Path

PROFILE = 'sysbus32-dma4-storage-sram-374-final'
DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA',
           'XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM', 'XU_MATRIX_STORAGE_SRAM']
GEOMETRY = dict(itcm=32, dtcm=32, shared=256, weights=16, bias=1, x=16,
                result=21, total_macros=374, engines=0, mac_pe=64)
OVERLAYS = {'source/rtl/perips/LinearTileDmaCore.sv',
            'source/rtl/perips/xu_matrix_dma_sysbus32.sv',
            'source/rtl/subsys/xu_systembus_ingress32.v'}
BASE_SHA = 'f697416ea83570b25ad9aa9ecfb37c915f7b93547cd8aa6297297e9092313555'
SDC_SHA = 'c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def production_files(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted((root / 'source').rglob('*'))
            if p.is_file() and p.suffix in {'.v', '.sv'}}


def check_inputs(root):
    root = Path(root)
    pinned = json.loads((root / 'package-files.json').read_text())
    for name, digest in pinned.items():
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and '\\' not in name, 'unsafe package path')
        item = root / p
        require(item.is_file() and not item.is_symlink() and sha(item) == digest, 'sealed input drift: ' + name)
    m = json.loads((root / 'manifest.json').read_text())
    require(m['schema'] == 'sysbus32-sealed-synthesis-preparation-v1' and
            m['hardware_profile'] == PROFILE and m['top'] == 'xu_soc_sysbus32_ppa_top' and
            m['defines'] == DEFINES and m['expected_geometry'] == GEOMETRY and
            m['expected_internal_macros'] == 54 and m['production_test_loader'] is False,
            'not exact DMA4 production N2/storage21 profile')
    require(json.loads((root / 'defines.json').read_text()) == DEFINES, 'selected defines differ')
    profile_tcl = ('# Final exact DMA4/storage21 profile. Original constraints unchanged.\n'
        'set sysbus32_hardware_profile {' + PROFILE + '}\n'
        'set sysbus32_production_defines [list ' + ' '.join(DEFINES) + ']\n'
        'set sysbus32_expected_total_macros 374\nset sysbus32_expected_x_macros 16\n'
        'set sysbus32_expected_internal_macros 54\nset sysbus32_expected_result_macros 21\n')
    require((root / 'source/ppa/geometry-profile.tcl').read_text() == profile_tcl,
            'native Tcl production profile differs')
    require(sha(root / 'source-manifest.json') == m['source_manifest_sha256'], 'source manifest binding differs')
    sm = json.loads((root / 'source-manifest.json').read_text())
    names = (root / 'rtl.f').read_text().splitlines()
    require(sha(root / 'rtl.f') == m['rtl_f_sha256'] and len(names) == m['source_count'] and
            names == [x['path'] for x in sm['ordered_compile_sources']], 'source order/count differs')
    require(len(names) == len(set(names)) and sm['defines'] == DEFINES and sm['hardware_profile'] == PROFILE,
            'source profile or duplicate source differs')
    actual = production_files(root)
    require(actual == m['production_rtl_files'] == {x['path']: x['sha256'] for x in sm['ordered_compile_sources']},
            'complete production source SET differs')
    require(all(pinned[name] == digest for name, digest in actual.items()), 'production source not sealed')
    require(not any(any(t in n for t in ('generic_ramsp', 'dma64', 'shared_icb_sram64')) for n in names),
            'nonproduction source selected')
    require(sha(root / 'source/contracts/reference-full-soc.sdc') == SDC_SHA and
            (root / 'source/contracts/reference-full-soc.sdc').read_bytes() ==
            (root / 'evidence/original-full-soc.sdc').read_bytes(), 'original SDC changed')
    b = json.loads((root / 'evidence/base-package-files.json').read_text())
    require(sha(root / 'evidence/base-package-files.json') == BASE_SHA == m['base_package_files_sha256'],
            'base source-order/library reference differs')
    require(set(actual) == {n for n in b if n.startswith('source/') and n.endswith(('.v', '.sv'))},
            'production source SET differs from original physical platform')
    require({n for n, digest in actual.items() if b[n] != digest} == OVERLAYS,
            'unreviewed production RTL change or missing DMA4/storage/ingress overlay')
    require(m['production_overlays'] == {n: actual[n] for n in sorted(OVERLAYS)}, 'explicit overlays differ')
    policy = json.loads((root / 'area-charge-policy.json').read_text())
    require(policy['charged_internal_macro_groups'] == dict(weights=16, bias=1, x=16, result=21) and
            policy['conservative_upper_bound']['internal_SRAM_macros'] == 54 and
            policy['timing_scope'] == 'full digital SoC including all374 SRAMs', 'physical macro accounting differs')
    synth = (root / 'synth.tcl').read_text()
    require(sha(root / 'synth.tcl') == m['compile_policy']['new_synthesis_sha256'],
            'manifest/native synthesis emitter differs')
    require(synth.count('set_svf final.svf') == 1 and synth.count('set_svf -off') == 1,
            'must produce own flushed final.svf')
    for command in m['compile_policy']['retained_commands']:
        require(synth.count(command) == 1, 'original compile policy changed: ' + command)
    require(not any(token in synth for token in ('set_false_path', 'set_multicycle_path', 'set_clock_groups',
            'set_ideal_network', 'set_input_delay', 'set_output_delay')), 'constraint relaxation forbidden')
    return pinned, m


def check_cpu_full12(root):
    """Runs before tool/library access; full raw checker replay and exact RTL SET."""
    root = Path(root)
    m = json.loads((root / 'manifest.json').read_text())
    expected = m.get('cpu_full12_result_sha256')
    require(expected, 'EDA forbidden until same production GPIO full12 PASS is sealed into a NEW package')
    require(sha(root / 'evidence/cpu-full12.json') == expected, 'CPU result identity differs')
    run = json.loads((root / 'evidence/cpu-full12.json').read_text())
    require(run.get('schema') == 's3-final-production-gpio-cpu-v1' and run.get('status') == 'PASS' and
            run.get('definitions') == DEFINES and run.get('actual_generic_macro_instances') == 374 and
            run.get('outputs') == 304128 and len(run.get('layers', [])) == 12,
            'requires actual same-production GPIO full12 PASS')
    require(run['ppa_binding']['package_files_sha256'] == m['cpu_source_package_files_sha256'],
            'CPU initial source package differs')
    require(sha(root / 'evidence/cpu-source-package-files.json') == m['cpu_source_package_files_sha256'],
            'initial immutable source-package receipt differs')
    initial_receipt = json.loads((root / 'evidence/cpu-source-package-files.json').read_text())
    require(initial_receipt['manifest.json'] == run['ppa_binding']['manifest_sha256'],
            'CPU initial production manifest differs')
    require(run['ppa_binding']['production_rtl_files'] == m['production_rtl_files'] == production_files(root) and
            run.get('source_drift') == [], 'CPU/PPA complete production source SET differs')
    sm = json.loads((root / 'source-manifest.json').read_text())
    require(run['ppa_binding']['definitions_exact'] == DEFINES and
            run['ppa_binding']['hardware_profile'] == PROFILE and
            run['ppa_binding']['source_manifest_sha256'] == sha(root / 'source-manifest.json') and
            run['ppa_binding']['ordered_compile_sources'] ==
            [dict(path=row['path'], sha256=row['sha256']) for row in sm['ordered_compile_sources']],
            'CPU/PPA define/profile/compile order identity differs')
    require(run['production_topology'] == dict(ingress_sources=2, pointer_bits=1,
            cpu_macros=64, shared_macros=256, internal_macros=54, total_macros=374),
            'CPU production topology differs')
    require([layer['layer'] for layer in run['layers']] == list(range(12)) and
            sum(layer['outputs'] for layer in run['layers']) == 304128 and
            sum(layer['total'] for layer in run['layers']) == run['total_cycles'], 'CPU count/cycle reconciliation differs')
    evidence = m.get('cpu_full12_evidence')
    require(evidence and set(evidence) == {'cpu-full12-simulation.log', 'cpu-full12-checker.py',
            'cpu-full12.elf', 'cpu-full12.image'}, 'CPU raw artifacts missing')
    for name, digest in evidence.items():
        require(sha(root / 'evidence' / name) == digest, 'CPU raw artifact identity differs: ' + name)
    require(evidence['cpu-full12-checker.py'] == run['source_sha256']['check_results.py'] and
            evidence['cpu-full12.elf'] == run['firmware']['elf_sha256'] and
            evidence['cpu-full12.image'] == run['firmware']['image_sha256'], 'CPU checker/firmware differs')
    spec = importlib.util.spec_from_file_location('sealed_final_cpu12_checker', root / 'evidence/cpu-full12-checker.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checked = checker.check_log((root / 'evidence/cpu-full12-simulation.log').read_text(), 12, 8,
        'warmup' in run, x_macros=True, storage_configuration=run['storage_binding'])
    require(all(run.get(name) == value for name, value in checked.items()), 'CPU raw log checker replay differs')
    return dict(result_sha256=expected, initial_source_package_sha256=m['cpu_source_package_files_sha256'],
                production_rtl_files=m['production_rtl_files'], total_cycles=run['total_cycles'], outputs=304128,
                firmware=run['firmware'], vectors=run['vector_byte_sha256'])
