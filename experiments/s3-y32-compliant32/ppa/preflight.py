#!/usr/bin/env python3
"""Check sealed32 production preprocessing and optional one-core XML geometry.

Local Verilator only. No simulation, DC/PT, area, power or mapped equivalence.
All outputs go to a new directory outside the sealed experiment.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from run_once import check_inputs, sha, require, dump, TOP
from profiles import PROFILES, SRAM_X


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--elaborate', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parent
    out = a.out.resolve()
    require(not out.exists() and root not in out.parents and root != out, 'preflight output must be new and outside sealed experiment')
    files, manifest = check_inputs(root)
    profile = manifest['hardware_profile']
    expected = PROFILES[profile]
    defines = expected['defines']
    out.mkdir(parents=True)
    verilator = shutil.which('verilator')
    require(verilator, 'verilator unavailable')
    flags = ['-D' + define for define in defines]
    includes = ['-Isource/rtl/core', '-Isource/rtl/perips', '-Isource/rtl/perips/apb_i2c']
    record = dict(schema='sysbus32-sealed-local-preflight-v1', status='LOCAL_CHECK_INCOMPLETE',
                  top=TOP, defines=defines, hardware_profile=profile, package_manifest_sha256=sha(root / 'package-files.json'),
                  tool=dict(path=verilator, sha256=sha(Path(verilator).resolve()),
                            version=subprocess.check_output([verilator, '--version'], text=True).strip()),
                  commands=[], failures=[], synthesis_run=False, sta_run=False,
                  simulation_run=False, max_local_cores=1, official_qualification=False)
    # Preprocess each integration boundary independently so the real platform
    # widths and absence of production test ports can be inspected directly.
    boundaries = ['subsys/e203_subsys_main.v', 'subsys/e203_subsys_perips.v',
                  'subsys/e203_subsys_top.v', 'soc/e203_soc_top.v', 'perips/LinearTileDmaCore.sv']
    if profile == SRAM_X:
        boundaries.append('perips/TileXMacroRowBuffer.sv')
    for rel in boundaries:
        cmd = [verilator, '-E', '-P', *flags, *includes, 'source/rtl/' + rel]
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=60)
        name = Path(rel).stem
        (out / (name + '.pp.v')).write_text(r.stdout)
        (out / (name + '.stderr')).write_text(r.stderr)
        record['commands'].append(dict(argv=cmd, returncode=r.returncode))
        if r.returncode != 0:
            record['failures'].append('preprocess failed: ' + rel)
        if 'sysbus_load_' in r.stdout or 'xu_matrix_dma64 u_xu_matrix_dma' in r.stdout:
            record['failures'].append('production test/wide branch active: ' + rel)
    maintext = (out / 'e203_subsys_main.pp.v').read_text()
    perips = (out / 'e203_subsys_perips.pp.v').read_text()
    compact = lambda text: ''.join(text.split())
    if 'xu_matrix_dma_sysbus32u_xu_matrix_dma(' not in compact(perips):
        record['failures'].append('new32 DMA not selected')
    for name in ['xu_dma64_shared_arb', 'xu_dma_shared_arb']:
        if name + 'u_xu_dma_shared_arb(' in compact(maintext):
            record['failures'].append('downstream arbiter active: ' + name)
    if '.TEST_LOADER(0)' not in compact(maintext):
        record['failures'].append('production ingress test parameter not zero')
    coretext = compact((out / 'LinearTileDmaCore.pp.v').read_text())
    xmacro_rows = sum(coretext.count('TileXMacroRowBufferxs_' + str(s) + '_' + str(r) + '(')
                      for s in range(2) for r in range(8))
    xregister_rows = sum(coretext.count('TileXRowBufferxs_' + str(s) + '_' + str(r) + '(')
                         for s in range(2) for r in range(8))
    record['preprocessed_x_rows'] = dict(macro=xmacro_rows, register=xregister_rows)
    if (xmacro_rows, xregister_rows) != (expected['geometry']['x'], 16 - expected['geometry']['x']):
        record['failures'].append('wrong production X buffer branch')
    if profile == SRAM_X and 'Sram1024x16memory(' not in compact((out / 'TileXMacroRowBuffer.pp.v').read_text()):
        record['failures'].append('X SRAM physical adapter not selected')
    if a.elaborate and not record['failures']:
        cmd = [verilator, '--xml-only', '--timing', '-Wno-fatal', '-j', '1',
               '--top-module', TOP, '--Mdir', str(out / 'obj'), '--xml-output', str(out / 'elaborated.xml'),
               *flags, *includes, '-f', 'rtl.f', 'local-only/generic_ramsp_non_ppa.sv']
        with (out / 'elaboration.log').open('w') as log:
            r = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=180)
        record['commands'].append(dict(argv=cmd, returncode=r.returncode))
        if r.returncode != 0:
            record['failures'].append('full-SoC XML elaboration failed')
        else:
            xml = ET.parse(out / 'elaborated.xml')
            cells = xml.findall('./cells//cell')
            refs = collections.Counter(c.get('submodname', '') for c in cells)
            def count(prefix):
                return sum(v for k, v in refs.items() if k.startswith(prefix))
            macros = [c for c in cells if c.get('submodname', '').startswith('RAMSP1024X16')]
            patterns = dict(itcm='.u_e203_itcm_ram.', dtcm='.u_e203_dtcm_ram.',
                            shared='.u_shared.storage.', weights='.u_core.weights.', bias='.u_core.bias.memory.', x='.u_core.xs_')
            groups = {n: sum(pattern in c.get('hier', '') for c in macros) for n, pattern in patterns.items()}
            unique = all(sum(pattern in c.get('hier', '') for pattern in patterns.values()) == 1 for c in macros)
            pes = sum(v for k, v in refs.items() if k.startswith('MacPE') and not k.startswith('MacPEArray'))
            forbidden = sum(count(n) for n in ['xu_matrix_dma64', 'xu_dma64_shared_arb', 'xu_dma_shared_arb', 'xu_shared_icb_sram64'])
            geometry = dict(macros=len(macros), macro_groups=groups, unique_macro_scopes=unique,
                            engines=count('DotProductEngine'), mac_pe=pes, ingress32=count('xu_systembus_ingress32'),
                            dma32=count('xu_matrix_dma_sysbus32'), endpoint32=count('xu_shared_icb_sram'),
                            x_macro_rows=count('TileXMacroRowBuffer'), x_register_rows=count('TileXRowBuffer'),
                            internal_macros=groups['weights'] + groups['bias'] + groups['x'],
                            forbidden_wide_or_downstream_instances=forbidden)
            record['geometry'] = geometry
            expected_groups = {n: expected['geometry'][n] for n in patterns}
            if ((len(macros), count('DotProductEngine'), pes, count('xu_systembus_ingress32'), count('xu_matrix_dma_sysbus32'), count('xu_shared_icb_sram'), forbidden) != (expected['geometry']['total_macros'], 8, 64, 1, 1, 1, 0)
                or groups != expected_groups or not unique
                or geometry['internal_macros'] != expected['internal_macros']
                or (geometry['x_macro_rows'], geometry['x_register_rows']) != (expected['geometry']['x'], 16 - expected['geometry']['x'])):
                record['failures'].append('full-SoC geometry mismatch')
            record['cell_reference_counts'] = dict(refs)
            record['xml_sha256'] = sha(out / 'elaborated.xml')
    # Tcl parser completeness without evaluating any EDA command.
    tclcheck = 'foreach f $argv {set s [open $f r]; set raw [read $s]; close $s; if {![info complete $raw]} {exit 1}}\n'
    (out / 'check-tcl-syntax.tcl').write_text(tclcheck)
    cmd = ['tclsh', str(out / 'check-tcl-syntax.tcl'), *[str(root / n) for n in ['synth.tcl', 'area_components.tcl', 'pt_collect.tcl', 'source/ppa/hierarchy_contract.tcl', 'source/ppa/geometry-profile.tcl']]]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    record['commands'].append(dict(argv=cmd, returncode=r.returncode))
    if r.returncode != 0:
        record['failures'].append('Tcl script is incomplete')
    record['source_drift'] = [name for name, digest in files.items() if not (root / name).is_file() or sha(root / name) != digest]
    record['status'] = 'LOCAL_CHECK_FAILED' if record['failures'] or record['source_drift'] else ('LOCAL32_ELABORATION_VERIFIED_NOT_SIGNOFF' if a.elaborate else 'LOCAL32_PREPROCESS_VERIFIED_NOT_SIGNOFF')
    record['outputs'] = {f.relative_to(out).as_posix(): dict(bytes=f.stat().st_size, sha256=sha(f)) for f in sorted(out.rglob('*')) if f.is_file()}
    dump(out / 'result.json', record)
    print(json.dumps({k: record[k] for k in ['status', 'failures', 'source_drift']}, sort_keys=True))
    return bool(record['failures'] or record['source_drift'])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        sys.exit(1)
