"""Strict storage-only package checks and full12 production GPIO execution gate."""
import hashlib
import importlib.util
import json
from pathlib import Path

PROFILE = 'sysbus32-storage-sram-374'
DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA',
           'XU_MATRIX_DMA_SYSBUS32', 'XU_MATRIX_X_SRAM', 'XU_MATRIX_STORAGE_SRAM']
GEOMETRY = dict(itcm=32, dtcm=32, shared=256, weights=16, bias=1, x=16,
                result=21, total_macros=374, engines=0, mac_pe=64)
OVERLAYS = {'source/rtl/perips/LinearTileDmaCore.sv', 'source/rtl/perips/xu_matrix_dma_sysbus32.sv'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def check_inputs(root):
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
            'not exact production N2/374 selected configuration')
    require(json.loads((root / 'defines.json').read_text()) == DEFINES, 'selected defines differ')
    policy = json.loads((root / 'area-charge-policy.json').read_text())
    require(policy['charged_internal_macro_groups'] == dict(weights=16, bias=1, x=16, result=21) and
            policy['conservative_upper_bound']['internal_SRAM_macros'] == 54 and
            policy['timing_scope'] == 'full digital SoC including all374 SRAMs' and
            policy['result_storage'] == dict(all_physical_macros_charged=True, logical_bits=5248,
                physical_bits=344064, physical_macro_count=21), 'storage charge policy differs from exact54/374 geometry')
    dma_policy = [scope for scope in policy['charged_scopes'] if scope['scope'] == 'dma']
    require(len(dma_policy) == 1 and dma_policy[0]['policy'] == 'all standard cells plus all54 internal RAMSP1024X16 macros' and
            'result_physical_sram' in dma_policy[0]['components'], 'DMA area policy misses result macro scope')
    require(sha(root / 'source-manifest.json') == m['source_manifest_sha256'], 'source manifest binding differs')
    sm = json.loads((root / 'source-manifest.json').read_text())
    names = (root / 'rtl.f').read_text().splitlines()
    require(sha(root / 'rtl.f') == m['rtl_f_sha256'] and len(names) == m['source_count'] and
            names == [x['path'] for x in sm['ordered_compile_sources']], 'source order/count differs')
    require(sm['defines'] == DEFINES and sm['hardware_profile'] == PROFILE, 'source profile differs')
    for source in sm['ordered_compile_sources']:
        require(pinned[source['path']] == source['sha256'], 'compile manifest differs')
    require(not any(any(t in n for t in ('generic_ramsp', 'dma64', 'shared_icb_sram64')) for n in names), 'nonproduction source selected')
    overlay = json.loads((root / 'evidence/storage-candidate/manifest.json').read_text())
    require(sha(root / 'evidence/storage-candidate/manifest.json') == m['storage_candidate_manifest_sha256'], 'storage manifest identity differs')
    require(overlay['storage']['internal_macros'] == 54 and overlay['storage']['full_soc_macros'] == 374 and
            overlay['storage']['result_macros'] == 21 and overlay['clear']['total16bit_writes'] == 55040,
            'storage or physical clear geometry differs')
    for name, digest in overlay['files'].items():
        target = root / ('local-only/' + name if name == 'generic_ramsp_non_ppa.sv' else 'source/rtl/perips/' + name)
        require(sha(target) == digest, 'storage dependency differs: ' + name)
    b = json.loads((root / 'evidence/base-package-files.json').read_text())
    require(sha(root / 'evidence/base-package-files.json') == m['base_package_files_sha256'], 'base package receipt differs')
    source_names = [n for n in b if n.startswith('source/') and n.endswith(('.v', '.sv'))]
    require({n for n in source_names if sha(root / n) != b[n]} == OVERLAYS, 'only two production RTL overlays are allowed')
    require(m['staged_core_sha256'] == sha(root / 'source/rtl/perips/LinearTileDmaCore.sv'), 'selected core differs')
    require((root / 'source/contracts/reference-full-soc.sdc').read_bytes() ==
            (root / 'evidence/original-full-soc.sdc').read_bytes(), 'original SDC changed')
    return pinned, m


def check_cpu_full12(root):
    """Executed before any native tool/library access; review does not require it."""
    m = json.loads((root / 'manifest.json').read_text())
    expected = m.get('cpu_full12_result_sha256')
    require(expected, 'EDA forbidden until same frozen production GPIO complete12 PASS is sealed into a NEW package')
    path = root / 'evidence/cpu-full12.json'
    require(sha(path) == expected, 'CPU complete12 receipt identity differs')
    run = json.loads(path.read_text())
    require(run.get('schema') == 's3-compliant32-production-gpio-cpu-v1' and run.get('status') == 'PASS' and
            run.get('definitions') == DEFINES and run.get('actual_generic_macro_instances') == 374 and
            run.get('outputs') == 304128 and len(run.get('layers', [])) == 12,
            'requires actual final production GPIO CPU complete12 PASS')
    require(run['ppa_binding']['package_files_sha256'] == m['base_package_files_sha256'] and
            run['storage_binding']['manifest_sha256'] == m['storage_candidate_manifest_sha256'],
            'CPU freeze is not this base plus selected overlay')
    require(run['production_topology'] == dict(ingress_sources=2, pointer_bits=1,
            cpu_macros=64, shared_macros=256, internal_macros=54, total_macros=374),
            'CPU topology differs from final production N2')
    pinned = json.loads((root / 'package-files.json').read_text())
    production = {name: digest for name, digest in pinned.items() if name.startswith('source/') and name.endswith(('.v', '.sv'))}
    require(run['ppa_binding']['production_rtl_files'] == production and run.get('source_drift') == [], 'CPU complete production source SET or runtime identity check differs')
    require([layer['layer'] for layer in run['layers']] == list(range(12)), 'complete12 layer identity/order differs')
    for name, digest in run['ppa_binding']['production_rtl_files'].items():
        require(sha(root / name) == digest, 'CPU/PPA production RTL differs: ' + name)
    require(sum(layer['outputs'] for layer in run['layers']) == 304128 and
            sum(layer['total'] for layer in run['layers']) == run['total_cycles'],
            'complete12 count/cycle reconciliation differs')
    evidence = m.get('cpu_full12_evidence')
    require(evidence and set(evidence) == {'cpu-full12-simulation.log', 'cpu-full12-checker.py', 'cpu-full12.elf', 'cpu-full12.image'}, 'complete actual CPU artifacts must be sealed')
    for name, digest in evidence.items():
        require(sha(root / 'evidence' / name) == digest, 'CPU raw artifact identity differs: ' + name)
    require(evidence['cpu-full12-checker.py'] == run['source_sha256']['check_results.py'] and
            evidence['cpu-full12.elf'] == run['firmware']['elf_sha256'] and
            evidence['cpu-full12.image'] == run['firmware']['image_sha256'], 'CPU checker/ELF/image binding differs')
    checker_path = root / 'evidence/cpu-full12-checker.py'
    spec = importlib.util.spec_from_file_location('sealed_cpu12_checker', checker_path)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checked = checker.check_log((root / 'evidence/cpu-full12-simulation.log').read_text(), 12, 8,
        'warmup' in run, x_macros=True, storage_configuration=run['storage_binding'])
    require(all(run.get(name) == value for name, value in checked.items()), 'raw CPU full12 checker replay differs from result')
    return dict(result_sha256=expected, total_cycles=run['total_cycles'], outputs=304128,
                firmware=run['firmware'], vectors=run['vector_byte_sha256'])
