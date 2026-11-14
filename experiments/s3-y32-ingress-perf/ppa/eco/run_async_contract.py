#!/usr/bin/env python3
"""Four-state digital contracts for real production AON/PMU RTL; not STA closure."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
CHILD = ROOT / 'third-party/e203_hbirdv2'
PRODUCTION = CHILD / 'rtl/e203/perips'
SOURCES = ['sirv_DeglitchShiftRegister.v', 'sirv_ResetCatchAndSync.v',
           'sirv_AsyncResetRegVec_36.v', 'sirv_AsyncResetReg.v',
           'sirv_pmu.v', 'sirv_pmu_core.v', 'sirv_AsyncResetRegVec_1.v']


def file_record(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def git_identity(directory):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()
    return {'commit': git('rev-parse', 'HEAD'), 'status': git('status', '--porcelain')}


def execute(command, out, name):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
    (out / (name + '.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f'{name} exited {result.returncode}; see {out / (name + ".log")}')
    return result.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/unknown4-20261114/async-contract-run')
    args = parser.parse_args(argv)
    out = args.out.resolve()
    if out.exists():
        parser.error('output directory must be new; existing receipts are never overwritten')
    out.mkdir(parents=True)
    receipt = {'schema': 'ingress1064-async-digital-contract-v1', 'status': 'RUNNING',
               'started_at': datetime.now(timezone.utc).isoformat(),
               'qualification': 'DIGITAL_FOUR_STATE_FUNCTIONAL_CONTRACT_ONLY_NOT_CDC_RDC_SIGNOFF',
               'STA_unknown_status': 'UNCHANGED_NOT_MARKED_MET',
               'scope': 'Actual production deglitch, reset catcher and complete sirv_pmu with its real submodules',
               'internal_probes': ['PMU erst_reset_r and erst_reset_r_r for asynchronous capture/hold/release only'],
               'public_observations': ['two real deglitch outputs', 'real AON reset catcher output',
                                       'PMU public io_regs_cause_read[9:8]'],
               'limitations': [
                   'Zero-delay four-state RTL simulation does not prove analog metastability, MTBF, recovery/removal or physical minimum pulse width.',
                   'One-femtosecond pulse checks digital event capture only and is not an admissible physical reset specification.',
                   'Release offsets avoid exactly coincident simulator edges; no setup/recovery margin is inferred.',
                   'HF/LF periods match the CPU stimulus integer-femtosecond periods; clocks have no phase relation or STA exceptions.',
                   'Unit-level composition does not prove complete wrapper boot-vector consumption timing, board input protocol or full-SoC CDC/RDC.',
                   'No EDA, timing constraint, production RTL, mapped design or frozen throughput result is changed.']}
    paths = [PRODUCTION / name for name in SOURCES] + [HERE / 'tb_async_contract.sv', Path(__file__).resolve()]
    try:
        receipt['parent'] = git_identity(ROOT)
        receipt['child'] = git_identity(CHILD)
        selection_path = ROOT / 'submission/candidate.json'
        selection = json.loads(selection_path.read_text())
        receipt['selection'] = {'candidate_manifest': file_record(selection_path),
                                'candidate': selection['candidate'], 'rtl': selection['rtl']}
        if selection['rtl']['path'] != str(CHILD.relative_to(ROOT)):
            raise ValueError('Selected production RTL path differs from this regression')
        if receipt['child']['commit'] != selection['rtl']['commit'] or receipt['child']['status']:
            raise ValueError('Production RTL must match the selected candidate commit and be clean')
        receipt['sources'] = {str(path.relative_to(ROOT)): file_record(path) for path in paths}
        tools = {name: shutil.which(name) for name in ('iverilog', 'vvp')}
        if not all(tools.values()):
            raise ValueError('Icarus Verilog and vvp are required')
        receipt['tools'] = {}
        for name, executable in tools.items():
            version = subprocess.run([executable, '-V'], capture_output=True, text=True, timeout=10)
            receipt['tools'][name] = {'path': executable, **file_record(Path(executable)),
                                     'version_first_line': (version.stdout + version.stderr).splitlines()[0]}
        binary = out / 'async-contract.vvp'
        compile_command = [tools['iverilog'], '-g2012', '-s', 'tb_async_contract', '-o', str(binary),
                           str(HERE / 'tb_async_contract.sv'), *[str(PRODUCTION / name) for name in SOURCES]]
        run_command = [tools['vvp'], str(binary)]
        receipt['commands'] = {'compile': compile_command, 'simulate': run_command}
        execute(compile_command, out, 'compile')
        log = execute(run_command, out, 'simulation')
        matches = re.findall(r'^ASYNC_CONTRACT_PASS cases=(\d+) checks=(\d+) release_phases=(\d+) stopped_pulses=(\d+) priority_masks=(\d+) hf_edges=(\d+) lf_edges=(\d+)$', log, re.M)
        if len(matches) != 1 or re.search(r'ASYNC_CONTRACT_FAIL|FATAL|ERROR:', log):
            raise ValueError('Missing unique full-contract PASS marker or simulation failure')
        values = list(map(int, matches[0]))
        receipt['coverage'] = dict(zip(['cases', 'assertions', 'release_phases', 'stopped_pulses',
                                       'priority_masks', 'hf_edges', 'lf_edges'], values))
        case_ids = list(map(int, re.findall(r'^ASYNC_CONTRACT_CASE PASS index=(\d+) ', log, re.M)))
        if case_ids != list(range(1, values[0] + 1)) or values[2:5] != [10, 4, 14]:
            raise ValueError('Contract scenario coverage incomplete')
        if len(re.findall(r'^ASYNC_CONTRACT_PHASE ', log, re.M)) != 10 or len(re.findall(r'^ASYNC_CONTRACT_STOPPED ', log, re.M)) != 4:
            raise ValueError('Missing per-phase/stopped-clock observations')
        after = {str(path.relative_to(ROOT)): file_record(path) for path in paths}
        if after != receipt['sources'] or git_identity(CHILD) != receipt['child'] or file_record(selection_path) != receipt['selection']['candidate_manifest']:
            raise ValueError('Production or test source drift during simulation')
        receipt['source_drift'] = []
        receipt['status'] = 'PASS_DIGITAL_CONTRACT_ONLY_NOT_CDC_RDC_SIGNOFF'
    except Exception as exc:
        receipt['status'] = 'FAILED'
        receipt['error'] = str(exc)
    receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
    receipt['outputs'] = {path.name: file_record(path) for path in sorted(out.iterdir()) if path.is_file()}
    (out / 'result.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('status', 'qualification', 'STA_unknown_status')}, ensure_ascii=False))
    print(f'Receipt: {out / "result.json"}')
    if 'error' in receipt:
        print(receipt['error'], file=sys.stderr)
    return 0 if receipt['status'].startswith('PASS_') else 1


if __name__ == '__main__':
    raise SystemExit(main())
