#!/usr/bin/env python3
"""Recreate actual132 Tcl/analysis from original bytes, without running EDA."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    e=load('xu135_evidence',HERE/'check-evidence.py')
    payload=e.original135(); audit=e.audit(payload)
    source=HERE.parent/'xu-score-timing132-local-20261105/tools/xu_timing_coverage132.py'
    e.need(e.ident(source.read_bytes())=={'bytes':39436,'sha256':e.WORKER_SHA}, 'archived original132 worker differs')
    worker=load('xu132_frozen_original',source)
    out=args.out.resolve(); out.mkdir(exist_ok=False)
    for name,data in payload.items():
        if name.startswith(e.PREFIX):
            relative=name[len(e.PREFIX):]; path=out/relative
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    expected_analysis=(out/'analysis.json').read_bytes()
    parent=e.sibling122(); original_sta=parent['full-soc-timing-combined-20261105-116/sta.tcl'].decode()
    state=json.loads((out/'state.json').read_text())
    prefix=original_sta[len('if {[catch {\n'):original_sta.index('redirect -file units.rpt {report_units}\n')]
    prefix=prefix.replace('read_verilog mapped.v\n','read_verilog '+worker.tq(state['parent']['mapped']['path'])+'\n')
    expected_tcl=worker.diagnostic_tcl(prefix,json.loads((out/'installed-options.json').read_text()))
    e.need(expected_tcl.encode()==(out/'diagnosis.tcl').read_bytes(), 'frozen worker does not regenerate actual132 diagnosis Tcl')
    e.need(worker.documentation_tcl().encode()==(out/'installed-docs.tcl').read_bytes(), 'frozen worker does not regenerate actual132 docs Tcl')
    worker.analyse(out,parent['full-soc-timing-combined-20261105-116/analysis-coverage.rpt'].decode())
    e.need((out/'analysis.json').read_bytes()==expected_analysis, 'regenerated analysis differs from actual132 original bytes')
    result={'status':'ACTUAL132_TCL_AND_ANALYSIS_REPRODUCED_FROM_FROZEN_ORIGINALS_NOT_EDA_RERUN',
            'qualification':'NOT_QUALIFIED','diagnosis_tcl_sha256':e.ident((out/'diagnosis.tcl').read_bytes())['sha256'],
            'docs_tcl_sha256':e.ident((out/'installed-docs.tcl').read_bytes())['sha256'],
            'analysis_sha256':e.ident(expected_analysis)['sha256'],
            'independent_report_audit_status':audit['status']}
    (out/'reproduction-receipt.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__': main()
