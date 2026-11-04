"""xu FM66: full original-RTL proof for actual61's completed DC mapped output.

The exact61 parent remains FAIL because PT lacks a PMU recovery path. This
separate FM execution cannot change that state or qualify timing/electrical.
Run only after both target identities have been bound to actual server bytes.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import time

B = Path.home() / 'Desktop/xu-score-optimization-20261102'
PPA = B / 'full-soc-campaign-03-ppa/ppa-ss-01'
FM49 = B / 'full-soc-electrical-formality-20261104-54-49'
EDIT49 = B / 'full-soc-cap-size-repair-20261103-49'
EDIT50 = B / 'full-soc-unloaded-cell-cleanup-20261103-50'
TARGET = B / 'full-soc-reset-buffer-20261104-61-from50-n4'
OUT = B / 'full-soc-electrical-formality-20261104-66-reset61'
FM49_STATE_SHA = '9d1664ecad99d038cacd6db017a9b79f480f788d7c946dc3df0590d7c652ba06'
STATE50_SHA = '7aea258d2d83d6c8d10815f8a612b16948ab3e0e5e8ea8674b90652b47e76ad7'
STATE61_SHA = '1163c63ba568db5040177f844bb4c3d0518029f4e3e85f58d376950a4f646df1'
MAPPED50_SHA = '9b7265e703ea62487c5b5c39c66adf245e720ac02f1066063cfd0eb4753f460c'
MAPPED61_SHA = '502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597'
SVF61_SHA = '5cfc2a56aec461f1759442308ed3212d138231738d586a2dfedeec10de39a807'
KNOWN_PT_FAILURE = 'XU_FATAL: reset recovery path missing; cannot claim analysis'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ident(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def validate_target_state(state):
    if state['status'] != 'FAIL' or state['error'] != 'pt failed' or state['parent_stage'] != '50' or state['pairs_per_sink'] != 4:
        raise ValueError('only the exact61 known PT-failed case is permitted')
    runs = state.get('runs', [])
    if len(runs) != 2:
        raise ValueError('actual61 must have exactly DC and PT attempts')
    dc, pt = runs
    if dc['tool'] != 'dc_shell' or dc['returncode'] != 0 or dc['errors'] or dc['marker_count'] != 1:
        raise ValueError('actual61 DC did not complete successfully')
    if pt['tool'] != 'pt_shell' or pt['returncode'] != 1 or pt['marker_count'] != 0 or pt['errors'] != [KNOWN_PT_FAILURE]:
        raise ValueError('actual61 PT has an unexpected failure; inspect it before FM')


def validate_runs(directory, state, target=False):
    if target:
        validate_target_state(state)
    elif state['status'] != 'EXECUTED_NOT_QUALIFIED' or len(state.get('runs', [])) != 2 or any(r['returncode'] or r['errors'] or r['marker_count'] != 1 for r in state['runs']):
        raise ValueError('prior DC/PT execution incomplete: ' + str(directory))
    for label, run in zip(('dc', 'pt'), state['runs']):
        if run['tool'] != label + '_shell' or sha(directory / (label + '.log')) != run['log_sha256'] or sha(directory / ('repair.tcl' if label == 'dc' else 'sta.tcl')) != run['script_sha256']:
            raise ValueError('actual DC/PT evidence identity differs: ' + str(directory))


def main():
    # Refuse an accidentally uploaded draft before creating an output directory.
    if not all(re.fullmatch(r'[0-9a-f]{64}', x) for x in (MAPPED61_SHA, SVF61_SHA)):
        raise ValueError('bind actual61 mapped and SVF SHA before launching FM66')
    worker = len(sys.argv) == 2 and sys.argv[1] == 'run'
    if not worker:
        if len(sys.argv) != 1:
            raise ValueError('no arguments, or internal worker run')
        OUT.mkdir(exist_ok=False)
        with (OUT / 'driver.log').open('x') as stream:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'], stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        print('XU_FM66_STARTED_FOR_DC61_PT_REMAINS_FAILED', process.pid)
        return
    def save(state):
        (OUT / 'state.json').write_text(json.dumps(state, sort_keys=True, indent=2) + '\n')
    state = dict(status='RUNNING_NOT_QUALIFIED', started_epoch=time.time(), pid=os.getpid(), target61_original_status='FAIL', target61_pt_status='FAIL_KNOWN_MISSING_RECOVERY', experiment='full original RTL mapped equivalence only; never rewrites or promotes actual61 PT state')
    save(state)
    try:
        baseline_path = FM49 / 'state.json'
        if sha(baseline_path) != FM49_STATE_SHA:
            raise ValueError('exact actual FM49 proof state differs')
        baseline = json.loads(baseline_path.read_text())
        if baseline['status'] != 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED' or baseline['returncode'] != 0 or baseline['frozen_before'] != baseline['frozen_after'] or len(baseline['frozen_before']) != 169:
            raise ValueError('full actual49 original-RTL169-input proof is not valid')
        # Retain the entire original169-file whitelist, including RTL, original
        # mapped/SVFs, DBs, original template and all actual49 execution inputs.
        inputs = []
        for name, receipt in baseline['frozen_before'].items():
            path = Path(name)
            if ident(path) != receipt:
                raise ValueError('an original169 frozen input changed: ' + name)
            inputs.append(path)
        for key, filename in (('log', 'fm.log'), ('script', 'verify.tcl')):
            path = FM49 / filename
            if ident(path) != baseline[key]:
                raise ValueError('actual FM49 output evidence differs')
            inputs.append(path)
        baseline_log = (FM49 / 'fm.log').read_text(errors='replace')
        if baseline_log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS') != 1 or baseline_log.splitlines().count('Verification SUCCEEDED') != 1:
            raise ValueError('actual FM49 complete success markers differ')
        if sha(EDIT50 / 'state.json') != STATE50_SHA or sha(TARGET / 'state.json') != STATE61_SHA:
            raise ValueError('actual50/61 terminal evidence differs')
        edit49 = json.loads((EDIT49 / 'state.json').read_text())
        edit50 = json.loads((EDIT50 / 'state.json').read_text())
        target = json.loads((TARGET / 'state.json').read_text())
        validate_runs(EDIT49, edit49)
        validate_runs(EDIT50, edit50)
        validate_runs(TARGET, target, target=True)
        if sha(EDIT50 / 'mapped.v') != MAPPED50_SHA or edit50['mapped_netlist_sha256'] != MAPPED50_SHA or sha(TARGET / 'mapped.v') != MAPPED61_SHA or sha(TARGET / 'repair.svf') != SVF61_SHA:
            raise ValueError('exact actual50/61 mapped or61 SVF identity differs')
        if edit50['input_sha256'].get(str(EDIT49 / 'mapped.v')) != edit49['mapped_netlist_sha256'] or target['input_sha256'].get(str(EDIT50 / 'mapped.v')) != MAPPED50_SHA:
            raise ValueError('49-to50-to61 mapped ancestry differs')
        if target['input_sha256'].get(str(EDIT50 / 'state.json')) != STATE50_SHA:
            raise ValueError('61 did not use this exact50 state')
        for directory, evidence in ((EDIT49, edit49), (EDIT50, edit50), (TARGET, target)):
            # Check every original edit input SHA, then freeze its current byte
            # size/SHA again for this FM. None is substituted by a later stage.
            for name, digest in evidence['input_sha256'].items():
                path = Path(name)
                if sha(path) != digest:
                    raise ValueError('a mapped edit frozen input changed: ' + name)
                inputs.append(path)
            inputs.extend(directory / name for name in ('state.json', 'mapped.v', 'repair.svf', 'repair.tcl', 'sta.tcl', 'dc.log', 'pt.log'))
        chain = [PPA / 'default.svf', B / 'full-soc-hold-repair-20261103-08/repair.svf', B / 'full-soc-gating-margin-repair-20261103-09/repair.svf', EDIT49 / 'repair.svf', EDIT50 / 'repair.svf', TARGET / 'repair.svf']
        if baseline['svf_chain'] != [str(p) for p in chain[:4]]:
            raise ValueError('original-through49 SVF proof chain differs')
        script = (FM49 / 'verify.tcl').read_text()
        old_svf = 'set_svf [list ' + ' '.join('{' + str(p) + '}' for p in chain[:4]) + ']'
        old_net = 'read_verilog -i {' + str(EDIT49 / 'mapped.v') + '}'
        if script.count(old_svf) != 1 or script.count(old_net) != 1:
            raise ValueError('exact actual FM49 script commands differ')
        script = script.replace(old_svf, 'set_svf [list ' + ' '.join('{' + str(p) + '}' for p in chain) + ']').replace(old_net, 'read_verilog -i {' + str(TARGET / 'mapped.v') + '}')
        (OUT / 'verify.tcl').write_text(script)
        dbs = [Path(p) for p in re.findall(r'read_db -technology_library \{([^}]+)\}', script)]
        if len(dbs) != 2 or {sha(p) for p in dbs} != {'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723', 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}:
            raise ValueError('exact two original SS libraries differ')
        inputs.extend([Path(__file__).resolve(), baseline_path, OUT / 'verify.tcl'] + dbs + chain)
        inputs = list(dict.fromkeys(inputs))
        state.update(frozen_before={str(p): ident(p) for p in inputs}, command=['fm_shell', '-f', 'verify.tcl'], svf_chain=[str(p) for p in chain], target_netlist=ident(TARGET / 'mapped.v'), target_svf=ident(TARGET / 'repair.svf'), target61_scope_limit=target['scope_limit'])
        save(state)
        with (OUT / 'fm.log').open('x') as stream:
            run = subprocess.run(state['command'], cwd=str(OUT), stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=4200)
        log = (OUT / 'fm.log').read_text(errors='replace')
        state.update(returncode=run.returncode, log=ident(OUT / 'fm.log'), script=ident(OUT / 'verify.tcl'), frozen_after={str(p): ident(p) for p in inputs})
        if state['frozen_before'] != state['frozen_after']:
            raise ValueError('a frozen original/chain input changed during FM66')
        if run.returncode or log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS') != 1 or log.splitlines().count('Verification SUCCEEDED') != 1 or re.search(r'^\s*(?:Error:|Error-|XU_FULL_SOC_FORMALITY_FAIL|XU_FULL_SOC_FORMALITY_SCRIPT_ERROR)', log, re.M):
            raise ValueError('full original-RTL mapped equivalence did not pass')
        state.update(status='VERIFIED_REVIEW_PENDING_NOT_QUALIFIED', scope='Conditional full-SoC RTL equivalence for exact completed DC61 mapped: original default→08→09→49→50→61 SVFs, same original RTL and two frozen SS DBs. Actual61 PT stays FAIL with missing recovery; all reset/electrical/untested/physical150MHz qualification remains separate.')
    except Exception as error:
        state.update(status='FAIL', error=str(error))
        raise
    finally:
        state['finished_epoch'] = time.time()
        save(state)


if __name__ == '__main__':
    main()
