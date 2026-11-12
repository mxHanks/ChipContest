#!/usr/bin/env python3
"""Fast regression for joined begin/end tokens in the generated activity TB.

This checks lexical block balance at the real generated-file seam; the complete
Verilator parse/build remains authoritative for all other SystemVerilog syntax.
"""
import argparse
from pathlib import Path
import re


def check(path):
    text=path.read_text()
    text=re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"','',text)
    depth=0
    for token in re.findall(r'\b(?:begin|end)\b',text):
        depth+=1 if token=='begin' else -1
        if depth<0:raise ValueError('closing block without begin')
    if depth:raise ValueError('unclosed blocks='+str(depth))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture',type=Path);args=parser.parse_args()
    try:check(args.fixture)
    except ValueError as error:
        print('ACTIVITY_BLOCK_BALANCE_FAIL',error);raise SystemExit(1)
    print('ACTIVITY_BLOCK_BALANCE_PASS')
