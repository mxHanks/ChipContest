#!/usr/bin/env python3
"""Verify default preprocessing and explicit macro selection without synthesis."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PERIPS=ROOT/'third-party/e203_hbirdv2/rtl/e203/perips'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    text=re.sub(r'^\s*`line[^\n]*','',text,flags=re.M)
    return re.findall(r"\w+|[^\s\w]",text)


def preprocess(path,defines):
    done=subprocess.run(['verilator','-E','-P',*['-D'+d for d in defines],str(path)],
                        capture_output=True,text=True,check=True)
    return done.stdout


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();rtl=args.candidate.resolve()/'rtl'
    origin=PERIPS/'LinearTileDmaCore.sv';candidate=rtl/origin.name
    reference=subprocess.check_output(['git','show','ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1:rtl/e203/perips/LinearTileDmaCore.sv'],cwd=ROOT/'third-party/e203_hbirdv2')
    reference_sha=hashlib.sha256(reference).hexdigest()
    if reference_sha!='710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb':raise ValueError('published B41 original changed')
    with tempfile.TemporaryDirectory(prefix='compliant32-b41-overlay-') as directory:
        reference_file=Path(directory)/'LinearTileDmaCore.sv';reference_file.write_bytes(reference)
        expected=tokens(preprocess(reference_file,[]))
    checks=[]
    for defs in [[],['XU_MATRIX_DMA_SYSBUS32'],['XU_MATRIX_X_SRAM']]:
        actual=tokens(preprocess(candidate,defs))
        if actual!=expected:raise ValueError('default/fallback preprocessor changed: '+repr(defs))
        checks.append(dict(defines=defs,status='PASS',original_core_tokens_equal=True))
    selected=preprocess(candidate,['XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM'])
    if len(re.findall(r'\bTileXMacroRowBuffer\s+xs_[01]_[0-7]\s*\(',selected))!=16:
        raise ValueError('macro selection does not instantiate16 X macros')
    if re.search(r'\bTileXRowBuffer\s+xs_[01]_[0-7]\s*\(',selected):
        raise ValueError('selected macro branch still instantiates register X')
    unchanged=[]
    for name in ['Sram1024x16.sv','MacController.sv','TileWeightBank.sv',
                 'TileWeightBankArray.sv','DmaBiasSramPrefetch.sv','TileXRowBuffer.sv']:
        if sha(rtl/name)!=sha(PERIPS/name):raise ValueError('unexpected dependency change: '+name)
        unchanged.append(dict(name=name,sha256=sha(rtl/name)))
    if sha(rtl/'mem_1024x16.sv')!=sha(ROOT/'tools/ppa/xu_weight_sram_adapter.sv'):
        raise ValueError('SRAM macro adapter identity differs')
    report=dict(schema='compliant32_xmacro_overlay_review_v1',status='PASS',
        fallback=checks,macro_selection_defines=['XU_MATRIX_DMA_SYSBUS32','XU_MATRIX_X_SRAM'],
        selected_x_instances=16,unchanged_dependencies=unchanged,
        original_core_sha256=reference_sha,installed_core_sha256=sha(origin),candidate_core_sha256=sha(candidate),
        shared_pe_and_engine_definitions_unchanged=True,
        macro_adapter_sha256=sha(rtl/'mem_1024x16.sv'),
        scope='Preprocessor/token identity and exact dependency bytes; noCPU/PPA/physical timing claim')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status='PASS',fallbacks=3,x_macros=16)))


if __name__=='__main__':main()
