#!/usr/bin/env python3
"""One-core local XML proof of exact final374 production geometry, not PPA."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from storage_controls import check_inputs, DEFINES, GEOMETRY, sha, require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = a.out.resolve()
    require(not out.exists() and root not in out.parents, 'new external output required')
    pinned, manifest = check_inputs(root)
    out.mkdir(parents=True)
    command = ['verilator', '--xml-only', '--timing', '-Wno-fatal', '-j', '1',
        '--top-module', manifest['top'], '--Mdir', str(out / 'obj'), '--xml-output', str(out / 'elaborated.xml'),
        *['-D' + name for name in DEFINES], '-Isource/rtl/core', '-Isource/rtl/perips',
        '-Isource/rtl/perips/apb_i2c', '-f', 'rtl.f', 'local-only/generic_ramsp_non_ppa.sv']
    with (out / 'elaboration.log').open('w') as stream:
        code = subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT, timeout=240).returncode
    result = dict(schema='storage374-local-xml-preflight-v1', status='FAIL', command=command, returncode=code,
                  package_files_sha256=sha(root / 'package-files.json'), synthesis_run=False, sta_run=False,
                  qualification='Strict local elaboration only; no mapped functional, area, timing or power claim')
    try:
        require(code == 0, 'XML elaboration failed')
        cells = ET.parse(out / 'elaborated.xml').findall('./cells//cell')
        count = Counter(cell.get('submodname', '') for cell in cells)
        macros = [cell for cell in cells if cell.get('submodname', '').startswith('RAMSP1024X16')]
        patterns = dict(itcm='.u_e203_itcm_ram.', dtcm='.u_e203_dtcm_ram.', shared='.u_shared.storage.',
                        weights='.u_core.weights.', bias='.u_core.biasMemory.', x='.u_core.xSets', result='.u_core.resultSlices')
        groups = {label: sum(pattern in cell.get('hier', '') for cell in macros) for label, pattern in patterns.items()}
        require(groups == {label: GEOMETRY[label] for label in patterns}, 'exact macro group geometry differs: ' + repr(groups))
        require(all(sum(pattern in cell.get('hier', '') for pattern in patterns.values()) == 1 for cell in macros), 'overlapping or unclassified macro')
        require(len(macros) == 374 and sum(groups[k] for k in ('weights', 'bias', 'x', 'result')) == 54, 'full/internal macro count differs')
        starts = lambda name: sum(n for ref, n in count.items() if ref.startswith(name))
        require(starts('MacPE_Acc41') == 64 and starts('DotProductEngine') == 0 and starts('TileXMacroRowBuffer') == 16, 'MAC/X core geometry differs')
        require(starts('xu_systembus_ingress32') == starts('xu_matrix_dma_sysbus32') == starts('xu_shared_icb_sram') == 1, 'production fabric interface geometry differs')
        require(not any(starts(name) for name in ('xu_matrix_dma64', 'xu_dma64_shared_arb', 'xu_shared_icb_sram64', 'xu_dma_shared_arb')), 'forbidden bypass/wide instance')
        # Check the active exact ingress N=2 rather than infer from an unused parameter.
        xmlroot = ET.parse(out / 'elaborated.xml')
        modules = {m.get('name'): m for m in xmlroot.findall('./netlist/module')}
        ingress = next(c for c in cells if c.get('submodname', '').startswith('xu_systembus_ingress32'))
        m = modules[ingress.get('submodname')]
        local_arbiters = [c for c in m.findall('.//instance') if c.get('defName', '').startswith('sirv_gnrl_icb_arbt')]
        require(len(local_arbiters) == 1, 'unique production ingress arbiter missing')
        arbitration = modules[local_arbiters[0].get('defName')]
        ports = {v.get('name'): v for v in arbitration.findall('./var')}
        dtypes = {v.get('id'): v for v in xmlroot.findall('./netlist/typetable/*')}
        def width(node):
            value = dtypes[node.get('dtype_id')]
            return abs(int(value.get('left', 0)) - int(value.get('right', 0))) + 1
        observed = {key: width(ports[key]) for key in ('i_bus_icb_cmd_valid', 'i_bus_icb_cmd_addr', 'i_bus_icb_cmd_wdata')}
        require(observed == dict(i_bus_icb_cmd_valid=2, i_bus_icb_cmd_addr=64, i_bus_icb_cmd_wdata=64), 'N2 arbiter physical widths differ')
        result.update(status='PASS_EXACT374_N2_XML_NOT_PPA', macro_groups=groups, internal_macros=54,
                      mac_pe=64, engines=0, ingress_port_widths=observed,
                      macro_paths=sorted(c.get('hier') for c in macros), xml_sha256=sha(out / 'elaborated.xml'))
        syntax = out / 'tcl-completeness.tcl'
        syntax.write_text('foreach f $argv {set h [open $f r];set s [read $h];close $h;if {![info complete $s]} {exit 1}}\n')
        tc = subprocess.run(['tclsh', str(syntax), *[str(root / n) for n in ('synth.tcl', 'pt_collect.tcl', 'area_components.tcl', 'source/ppa/hierarchy_contract.tcl', 'source/ppa/geometry-profile.tcl')]], capture_output=True, text=True)
        require(tc.returncode == 0, 'Tcl parser incomplete')
        require(all(sha(root / name) == digest for name, digest in pinned.items()), 'sealed source drift during XML')
    except Exception as error:
        result.update(status='FAIL', error=str(error))
    (out / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: result.get(k) for k in ('status', 'error', 'macro_groups', 'ingress_port_widths')}))
    return result['status'] == 'FAIL'


if __name__ == '__main__':
    raise SystemExit(main())
