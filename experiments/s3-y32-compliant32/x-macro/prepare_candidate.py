#!/usr/bin/env python3
"""Prepare a separate B41/16-X-macro candidate; never writes production RTL."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PERIPS = ROOT / 'third-party/e203_hbirdv2/rtl/e203/perips'
CORE_SHA = '710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_exact(text, before, after, count=1):
    if text.count(before) != count:
        raise ValueError(f'candidate seam differs: {before!r}; expected {count}')
    return text.replace(before, after)


def prepare(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rtl = out / 'rtl'
    rtl.mkdir()
    origin = PERIPS / 'LinearTileDmaCore.sv'
    installed_core_sha256=sha(origin)
    if installed_core_sha256==CORE_SHA:
        original_bytes=origin.read_bytes();origin_selection='installed frozen B41'
    else:
        original_bytes=subprocess.check_output(['git','show','ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1:rtl/e203/perips/LinearTileDmaCore.sv'],cwd=ROOT/'third-party/e203_hbirdv2')
        if hashlib.sha256(original_bytes).hexdigest()!=CORE_SHA:raise ValueError('published B41 reference identity differs')
        origin_selection='published B41 git blob; installed core retained untouched'
    before = original_bytes.decode()
    text = replace_exact(before,
        'wire        _io_clearXWrite_T = clearIndex < 11\'h40;',
        'wire        _io_clearXWrite_T = clearIndex < 11\'h400;')
    text = replace_exact(text,
        '.io_waddr   (clearing ? clearIndex[5:0] : io_xLoadAddr),',
        ".io_waddr   (clearing ? clearIndex[9:0] : {4'b0, io_xLoadAddr}),", 16)
    for set_index in range(2):
        for row in range(8):
            pattern = re.compile(r'(  TileXRowBuffer xs_' + str(set_index) + '_' + str(row) + r' \(.*?)(\n  \);)', re.S)
            matches = list(pattern.finditer(text))
            if len(matches) != 1:
                raise ValueError('X instance seam differs')
            block = matches[0][1].replace('TileXRowBuffer ', 'TileXMacroRowBuffer ')
            block = replace_exact(block,
                f'.io_raddr   (_engines_{row}_io_k),',
                f'.io_ren     (_engines_{row}_io_weightRen & ' +
                ('runSet' if set_index else '~runSet') + ' & ~clearing & ~io_abort),\n' +
                f'    .io_raddr   (_engines_{row}_io_weightReadK),')
            block = replace_exact(block,
                f'.io_rdata   (_xs_{set_index}_{row}_io_rdata)',
                f'.io_rdata   (_xs_{set_index}_{row}_io_rdata),\n    .io_rvalid  ()')
            text = text[:matches[0].start(1)] + block + text[matches[0].end(1):]
    # These assertions observe valid alignment; they do not add arithmetic state.
    checks = ['\n`ifndef SYNTHESIS', '  always @(posedge clock) if (!reset && !io_abort && !clearing) begin']
    for row in range(8):
        checks += [f'    if (engines_{row}.peArray.io_enable)',
                   f'      assert (runSet ? xs_1_{row}.io_rvalid : xs_0_{row}.io_rvalid)',
                   f'        else $fatal(1,"X/W synchronous alignment missing row {row}");']
    checks += ['  end', '`endif', '']
    end = text.rfind('endmodule')
    text = text[:end] + '\n'.join(checks) + text[end:]
    top_seam='module LinearTileDmaCore('
    if before.count(top_seam)!=1 or text.count(top_seam)!=1:
        raise ValueError('core top seam differs')
    original_start=before.index(top_seam)
    macro_start=text.index(top_seam)
    if before[:original_start]!=text[:macro_start]:
        raise ValueError('X candidate changed a shared PE/engine definition')
    # The original top body is retained verbatim, including the packed X path.
    select='\n`ifdef XU_MATRIX_DMA_SYSBUS32\n`ifdef XU_MATRIX_X_SRAM\n`define C32_X_SRAM_SELECTED\n`endif\n`endif\n'
    text=(before[:original_start]+select+'`ifdef C32_X_SRAM_SELECTED\n'+text[macro_start:]+
          '\n`else\n'+before[original_start:]+'\n`endif\n`ifdef C32_X_SRAM_SELECTED\n`undef C32_X_SRAM_SELECTED\n`endif\n')
    (rtl / origin.name).write_text(text)
    origins = {str(origin.relative_to(ROOT)): CORE_SHA}
    for name in ['Sram1024x16.sv', 'TileWeightBank.sv', 'TileWeightBankArray.sv',
                 'DmaBiasSramPrefetch.sv', 'MacController.sv', 'TileXRowBuffer.sv']:
        path = PERIPS / name
        origins[str(path.relative_to(ROOT))] = sha(path)
        shutil.copy2(path, rtl / name)
    for path, name in [(HERE / 'TileXMacroRowBuffer.sv', 'TileXMacroRowBuffer.sv'),
                       (ROOT / 'tools/ppa/xu_weight_sram_adapter.sv', 'mem_1024x16.sv'),
                       (ROOT / 'tools/ppa/generic_ramsp_non_ppa.sv', 'generic_ramsp_non_ppa.sv')]:
        origins[str(path.relative_to(ROOT))] = sha(path)
        shutil.copy2(path, rtl / name)
    manifest = dict(schema='compliant32_xmacro_candidate_v1', status='PREPARED_NOT_VERIFIED',
        production_core_sha256=CORE_SHA, origins=origins,
        reference_selection=origin_selection,installed_core_sha256_at_preparation=installed_core_sha256,
        required_defines=['XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM'],
        fallback='Original B41 top retained verbatim for every other define combination',
        candidate_files={p.name: sha(p) for p in sorted(rtl.glob('*.sv'))},
        changes=['16 register X rows replaced by 16 known single-port1024x16 macros',
                 'X requests use weightRen/weightReadK with unchanged MacController',
                 'X clear covers all1024 physical addresses in every macro',
                 'scalar16 X writes only; current32-bit DMA ties packed=0'],
        storage=dict(x_logical_bits=16384,x_physical_bits=262144,x_macros=16,
                     internal_macros_before=17,internal_macros_after=33,
                     shared_bytes=524288,weight_macros=16,bias_macros=1),
        clear=dict(weight_writes=16384,bias_writes=768,x_writes=16384,
                   total16bit_writes=33536,parallel_address_steps=1024),
        scope='Separate candidate only; generic functional SRAM model has no PPA eligibility')
    (out / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    result=prepare(args.out)
    print(json.dumps(dict(status=result['status'],out=str(args.out.resolve()),x_macros=16)))
