#!/usr/bin/env python3
"""Freeze PPA inputs from a completed CPU simulation; never launch synthesis/STA."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MAIN = 'u_soc/u_e203_subsys_top/u_e203_subsys_main'
DMA = MAIN + '/u_e203_subsys_perips/u_xu_matrix_dma'
REPLACEMENTS = {
    'rtl/general/sirv_sim_ram.v': ROOT / 'tools/ppa/xu_sirv_sram_adapter.sv',
    'rtl/perips/mem_1024x16.sv': ROOT / 'tools/ppa/xu_weight_sram_adapter.sv',
}
EXCLUDED = {'rtl/perips/generic_ramsp_non_ppa.sv',
            'rtl/perips/tile_physical_observer.sv'}
DEFINES = ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1', 'XU_MATRIX_DMA', 'XU_MATRIX_DMA64']
R2_DMA_SHA256 = '6aaa6927e211202acb65bb0ca22478e8e2b070b1f2fc0678db76dea3f21c9cf7'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--allow-partial', action='store_true',
                        help='prepare explicitly preliminary inputs from a single-layer PASS')
    parser.add_argument('--required-dma-sha256', default=R2_DMA_SHA256,
                        help='final selected DMA identity; default is committed CPU R2 error-code fix')
    parser.add_argument('--preflight', action='store_true',
                        help='local Verilator XML elaboration with generic functional macro only')
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    receipt = json.loads((candidate / 'result.json').read_text())
    check(receipt['status'] == 'PASS', 'candidate must have completed PASS')
    tasks = int(receipt['arguments']['tasks'])
    check(receipt.get('outputs') == tasks * 25344, 'candidate output count incomplete')
    check(bool(receipt.get('physical_clear')), 'candidate physical-clear proof absent')
    check(args.allow_partial or (tasks == 12 and receipt['arguments'].get('warmup')),
          'final PPA inputs require a complete12 warmup PASS; preliminary mode is explicit')
    source = candidate / 'source'
    expected = receipt['source_sha256']
    check(args.allow_partial or expected.get('rtl/perips/xu_matrix_dma64.sv')==args.required_dma_sha256,
          'final DMA identity differs from selected CPU R2 candidate')
    actual = {p.relative_to(source).as_posix(): sha(p)
              for p in sorted(source.rglob('*')) if p.is_file()}
    check(actual == expected, 'CPU frozen source drift')
    check(not any(p.is_symlink() for p in source.rglob('*')), 'source symlink not allowed')
    out = args.out.resolve()
    check(not out.exists(), 'output must be new; prior evidence is immutable')
    out.mkdir(parents=True)
    provenance = []
    for name, old_hash in sorted(expected.items()):
        if not name.startswith('rtl/') or name in EXCLUDED:
            continue
        origin = REPLACEMENTS.get(name, source / name)
        target = out / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
        provenance.append(dict(path='source/' + name, sha256=sha(target),
                               cpu_source_sha256=old_hash, origin=str(origin),
                               operation='macro_adapter_replacement' if name in REPLACEMENTS else 'byte_identical'))
    extra = {
        'source/tools/prepare.py': Path(__file__),
        'source/ppa/xu_soc_dma64_ppa_top.sv': HERE / 'xu_soc_dma64_ppa_top.sv',
        'source/ppa/hierarchy_contract.tcl': HERE / 'hierarchy_contract.tcl',
        'source/contracts/reference-full-soc.sdc': ROOT / 'tools/ppa/xu_full_soc.sdc',
        'source/contracts/reference-clock-review.tcl': ROOT / 'tools/ppa/xu_full_soc_clock_review.tcl',
    }
    for name, origin in extra.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)
        provenance.append(dict(path=name, sha256=sha(target), origin=str(origin),
                               operation='PPA_boundary_or_reference_contract'))
    files = [p.relative_to(out).as_posix() for p in sorted((out/'source/rtl').rglob('*'))
             if p.suffix in {'.v', '.sv'}]
    files += ['source/ppa/xu_soc_dma64_ppa_top.sv']
    (out/'rtl.f').write_text(''.join(name+'\n' for name in files))
    dump(out/'defines.json', DEFINES)
    manifest = dict(
        schema='s3-parallel4k-ppa-preparation-v1', status='PREPARED_NOT_SYNTHESIZED',
        prepared_at=datetime.now(timezone.utc).isoformat(),
        candidate=str(candidate), candidate_result_sha256=sha(candidate/'result.json'),
        candidate_tasks=tasks, candidate_outputs=receipt['outputs'],
        partial=args.allow_partial or tasks != 12 or not receipt['arguments'].get('warmup'),
        required_dma_sha256=args.required_dma_sha256,
        preparation_complete=False, preflight_status='NOT_RUN',
        preparer_sha256=sha(Path(__file__)), parent_source_files=len(expected),
        top='xu_soc_dma64_ppa_top', defines=DEFINES, sources=files,
        rtl_f_sha256=sha(out/'rtl.f'), provenance=provenance,
        excluded_simulation_only=sorted(EXCLUDED),
        expected_geometry=dict(itcm=32, dtcm=32, shared=256, weights=16, bias=1,
                               total_macros=337, engines=8, mac_pe=64,
                               shared_bits=4194304, internal_macro_bits=278528),
        charged_area_scopes=[
            dict(path=DMA, include='all standard cells plus its17 internal SRAM macros'),
            dict(path=MAIN+'/u_xu_dma_shared_arb', include='all new arbiter/width adaptation cells'),
            dict(path='u_shared', include='all endpoint standard cells, conservative full changed endpoint logic charge',
                 exclude='256 reused shared SRAM macros; list separately')],
        same_configuration_obligations=[
            'All unmodified production RTL bytes match the sealed CPU candidate.',
            'Two SRAM model replacements need candidate-level functional equivalence/real-macro verification.',
            'Future mapped leaf inventory must uniquely account for all337 SRAM macros and added interface logic.',
            'Bind final tool/library/constraints/netlist identities to this same frozen candidate.',
        ],
        unresolved=[
            'No synthesis or STA is run by this preparation script.',
            'Official shared-SRAM64/rebank/interface eligibility remains unverified.',
            'Library area dimension and organizer SRAM price table are not authoritatively verified;2.25mm2 verdict unavailable.',
            'Reference SDC is provisional, not final signed-off clock/reset/IO contract.',
            'HF150MHz system target, LF32.768kHz; externalHF/PLL, JTAG, ERST/POR electrical specifications remain incomplete.',
            'No clock groups, false paths, multicycle exceptions, ideal networks, or relaxed checks are introduced here.',
        ])
    dump(out/'manifest.json', manifest)
    if args.preflight:
        # This model is deliberately NOT in rtl.f and must not enter synthesis.
        model = out/'preflight/generic_ramsp_non_ppa.sv'
        model.parent.mkdir()
        shutil.copy2(ROOT/'tools/ppa/generic_ramsp_non_ppa.sv', model)
        command = ['verilator', '--xml-only', '--timing', '-Wno-fatal',
                   '--top-module', manifest['top'], '--Mdir', 'preflight/obj',
                   '--xml-output', 'preflight/elaborated.xml',
                   *['-D'+name for name in DEFINES],
                   '-Isource/rtl/core', '-Isource/rtl/perips', '-Isource/rtl/perips/apb_i2c',
                   '-f', 'rtl.f', 'preflight/generic_ramsp_non_ppa.sv']
        dump(out/'preflight/command.json', dict(command=command, cwd=str(out),
             tool_version=subprocess.check_output(['verilator','--version'],text=True).strip(),
             generic_model_sha256=sha(model), scope='local elaboration only; not synthesis/STA'))
        with (out/'preflight/elaboration.log').open('w') as log:
            result = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        check(result.returncode == 0, 'local elaboration failed; see preflight/elaboration.log')
        xml = ET.parse(out/'preflight/elaborated.xml')
        cells = xml.findall('./cells//cell')
        counts = {}
        for cell in cells:
            ref = cell.attrib.get('submodname', '')
            counts[ref] = counts.get(ref, 0) + 1
        macro_cells = [cell for cell in cells if cell.attrib.get('submodname','').startswith('RAMSP1024X16')]
        macros = len(macro_cells)
        engines = sum(n for ref,n in counts.items() if ref.startswith('DotProductEngine'))
        pes = sum(n for ref,n in counts.items() if ref.startswith('MacPE') and not ref.startswith('MacPEArray'))
        patterns = dict(itcm='.u_e203_itcm_ram.', dtcm='.u_e203_dtcm_ram.',
                        shared='.u_shared.banks', weights='.u_core.weights.', bias='.u_core.bias.memory.')
        groups = {name:sum(pattern in cell.attrib.get('hier','') for cell in macro_cells)
                  for name,pattern in patterns.items()}
        unique = all(sum(pattern in cell.attrib.get('hier','') for pattern in patterns.values())==1
                     for cell in macro_cells)
        expected_groups = dict(itcm=32,dtcm=32,shared=256,weights=16,bias=1)
        good = (macros,engines,pes)==(337,8,64) and groups==expected_groups and unique
        preflight = dict(status='PASS' if good else 'FAIL',
                         macros=macros, engines=engines, mac_pe=pes, cell_reference_counts=counts,
                         macro_groups=groups, macro_scopes_unique=unique,
                         xml_sha256=sha(out/'preflight/elaborated.xml'),
                         log_sha256=sha(out/'preflight/elaboration.log'),
                         scope='generic functional macro local elaboration, not mapped PPA or functional equivalence')
        dump(out/'preflight/result.json', preflight)
        manifest['preflight_status']=preflight['status']
        dump(out/'manifest.json',manifest)
        check(preflight['status']=='PASS', 'elaborated geometry differs from337macros/8engines/64PE')
    # Recheck both the immutable candidate and all prepared inputs after elaboration.
    check(actual == {p.relative_to(source).as_posix():sha(p)
                     for p in sorted(source.rglob('*')) if p.is_file()}, 'CPU source changed during preparation')
    check(all(sha(out/item['path'])==item['sha256'] for item in provenance), 'prepared source changed')
    manifest['preparation_complete']=True
    dump(out/'manifest.json',manifest)
    print(json.dumps(dict(status=manifest['status'], out=str(out), rtl_files=len(files),
                          candidate_tasks=tasks, synthesis_run=False, sta_run=False,
                          preflight='PASS' if args.preflight else 'NOT_RUN'), indent=2))


if __name__ == '__main__':
    main()
