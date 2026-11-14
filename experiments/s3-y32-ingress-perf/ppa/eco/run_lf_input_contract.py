#!/usr/bin/env python3
"""Exercise qualified LF input obligations and reject deliberately invalid traces."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INGRESS = HERE.parents[1]
NEGATIVE = {
    'bootrom-change': 'BOOTROM_CHANGED', 'input-x': 'DWAKEUP_X',
    'early-release': 'ERST_MIN_LOW', 'wake-wrong-edge': 'DWAKEUP_EDGE_WINDOW',
    'wake-short-hold': 'DWAKEUP_MIN_HOLD', 'reset-wrong-edge': 'ERST_RELEASE_WINDOW',
    'reset-short-low': 'ERST_MIN_LOW', 'reset-stopped-release': 'ERST_RELEASE_WINDOW',
}


def record(path):
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT/'build/unknown4-20261114/lf-input-contract-run')
    args = p.parse_args(argv)
    out = args.out.resolve()
    if out.exists(): p.error('evidence directory must be new')
    out.mkdir(parents=True)
    report = dict(schema='lf-input-contract-regression-v1', status='RUNNING', started_at=datetime.now(timezone.utc).isoformat(),
                  qualification='QUALIFIED_DIGITAL_STIMULUS_ONLY_NOT_PHYSICAL_CDC_RDC_SIGNOFF',
                  STA_unknown_status='NOT_MARKED_MET_BY_DIGITAL_SIMULATION', cases={})
    try:
        spec=importlib.util.spec_from_file_location('real_async_runner', HERE/'run_async_contract.py')
        real=importlib.util.module_from_spec(spec);spec.loader.exec_module(real)
        child=real.git_identity(real.CHILD)
        selected=json.loads((ROOT/'submission/candidate.json').read_text())
        if child['commit']!=selected['rtl']['commit'] or child['status']:
            raise ValueError('Production RTL must be selected and clean')
        report['child']=child
        sources=[HERE/'tb_lf_input_contract.sv',INGRESS/'lf_input_contract.sv',Path(__file__).resolve(),
                 *[real.PRODUCTION/name for name in ['sirv_DeglitchShiftRegister.v','sirv_ResetCatchAndSync.v','sirv_AsyncResetRegVec_36.v','sirv_AsyncResetReg.v']]]
        report['sources']={str(path.relative_to(ROOT)):record(path) for path in sources}
        binary=out/'qualified.vvp'
        command=['iverilog','-g2012','-s','tb_lf_input_contract','-I'+str(INGRESS),'-o',str(binary),str(sources[0]),*[str(x) for x in sources[3:]]]
        report['compile_command']=command
        compiled=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
        (out/'compile.log').write_text(compiled.stdout+compiled.stderr)
        if compiled.returncode: raise ValueError('compile failed')
        for name,reason in {'none':None,**NEGATIVE}.items():
            command=['vvp',str(binary),'+BAD_CASE='+name]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
            log=result.stdout+result.stderr;(out/(name+'.log')).write_text(log)
            if reason is None:
                good=result.returncode==0 and 'LF_INPUT_CONTRACT_PASS cases=6 releases=2 wake_changes=4' in log
            else:
                good=result.returncode!=0 and 'LF_INPUT_CONTRACT_REJECT reason='+reason+' ' in log and 'LF_CONTRACT_NEGATIVE_WAS_NOT_REJECTED' not in log
            report['cases'][name]=dict(command=command,returncode=result.returncode,expected_rejection=reason,verdict='PASS' if good else 'FAIL')
            if not good: raise ValueError('unexpected verdict: '+name)
        # Retain the original arbitrary-phase, stopped-clock pulse and PMU cases.
        command=[sys.executable,'-B',str(HERE/'run_async_contract.py'),'--out',str(out/'legacy-arbitrary-phase')]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
        (out/'legacy-driver.log').write_text(result.stdout+result.stderr)
        if result.returncode: raise ValueError('original arbitrary-phase regression failed')
        report['legacy_result']=record(out/'legacy-arbitrary-phase/result.json')
        after={str(path.relative_to(ROOT)):record(path) for path in sources}
        if after!=report['sources'] or real.git_identity(real.CHILD)!=child: raise ValueError('source drift')
        report['source_drift']=[]
        report['status']='PASS_POSITIVE_AND_EIGHT_EXPECTED_REJECTIONS_NOT_PHYSICAL_SIGNOFF'
    except Exception as exc:
        report.update(status='FAIL',error=str(exc))
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    report['outputs']={path.name:record(path) for path in sorted(out.iterdir()) if path.is_file()}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],out=str(out),error=report.get('error'))))
    return 0 if report['status'].startswith('PASS_') else 1

if __name__=='__main__': sys.exit(main())
