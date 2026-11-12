#!/usr/bin/env python3
"""Recompute completed B41 stalls and faults from their frozen raw evidence."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re

from compare_cpu64_runs import load, sha

BASE = Path(__file__).resolve().parents[1] / 'hardware64-r1'
NORMAL = BASE / 'b41-strict-input-r1'
FOLLOWUP = BASE / 'b41-followup-input-r1'
NORMAL_SHA = '1d8cd861b75c377ecd7282edd1fa1bdb7dae7a166078d43d6308e3010335a6c6'
FOLLOWUP_SHA = '4ac437cd4ff2e480a4f33ae7c8c3b969949ebe151d195aa36b993ca9b47b5db4'
REMOTE = PurePosixPath('/work/leo/chipcontest-xu-own155-diagnosis-20261105')


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def drained(evidence, checksum):
    native = read(evidence / 'native-r1/result.json')
    child = native['child']
    campaign = evidence / 'native-r1/campaign/result.json'
    require(native['status'] == 'PASS' and native['qualification'] == 'DEVELOPMENT_RTL_ONLY'
            and native['input_checksum_sha256'] == checksum
            and child['native_exit'] == 0 and child['waitpid_completed']
            and not any(child[k] for k in ('events', 'remaining_group', 'remaining_at_leader_exit')),
            'Native campaign did not pass and drain with the frozen input')
    require(native['campaign_sha256'] == sha(campaign)
            and child['log_sha256'] == sha(evidence / 'native-r1/control/native.log'),
            'Native log or campaign identity differs')
    return native, read(campaign)


def review(evidence, full12, full12_review, out):
    load('b41_normal_input_guard', NORMAL / 'run_native.py').inputs(NORMAL_SHA)
    load('b41_followup_input_guard', FOLLOWUP / 'run_native.py').inputs(FOLLOWUP_SHA)
    frozen = load('frozen_b41_followup', FOLLOWUP / 'run_followup.py')
    prepared = read(NORMAL / 'prepared.json')
    normal_native, normal = drained(full12, NORMAL_SHA)
    accepted = read(full12_review)
    require(accepted['status'] == 'PASS_RAW_CPU64_COMPARISON'
            and accepted['native_sha256'] == sha(full12 / 'native-r1/result.json')
            and accepted['campaign_sha256'] == sha(full12 / 'native-r1/campaign/result.json')
            and accepted['input_manifest_sha256'] == NORMAL_SHA
            and accepted['cpu_assert_properties'] == 6,
            'Full12 raw review does not bind this B41 evidence')
    normal_binary = full12 / 'native-r1/campaign/obj/dma64_soc'
    require(sha(normal_binary) == normal['simulator_sha256'] == accepted['simulator_sha256'],
            'Accepted normal executable differs')
    native, data = drained(evidence, FOLLOWUP_SHA)
    require(data['status'] == frozen.PASS and data['accepted_full12'] == dict(
        native_sha256=sha(full12 / 'native-r1/result.json'),
        campaign_sha256=sha(full12 / 'native-r1/campaign/result.json'),
        input_manifest_sha256=NORMAL_SHA, simulator_sha256=sha(normal_binary)),
        'Follow-up does not use the accepted same-version full12 executable')
    names = set(prepared['software'])
    require(set(data['stall_cases']) == names and set(data['fault_cases']) == {
        name + '-' + operation for name in names for operation in ('read', 'write')},
        'Missing or extra firmware stall/fault cases')
    require(data['fault_fixture_sha256'] == sha(FOLLOWUP / 'tb_dma64_fault_soc.sv')
            == frozen.FAULT_TB_SHA, 'Fault fixture changed')
    campaign = evidence / 'native-r1/campaign'
    preprocessed = campaign / 'fault-preprocessed.sv'
    require(data['fault_preprocessed_sha256'] == sha(preprocessed)
            and data['fault_cpu_assert_properties'] == 6
            and len(re.findall(r'assert\s+property\b', preprocessed.read_text())) == 6,
            'Fault CPU assertion evidence differs')
    normal_remote = REMOTE / NORMAL.name
    followup_remote = REMOTE / FOLLOWUP.name
    fault_binary = followup_remote / 'native-r1/campaign/fault-obj/cpu64_fault'
    includes = [normal_remote / 'source/rtl' / p for p in
                ('core', 'perips', 'perips/apb_i2c')]
    includes.append(normal_remote / 'source/tests')
    expected_build = [
        'verilator', '--binary', '-CFLAGS', '-std=gnu++20', '-j', '2', '-Wno-fatal',
        '-Mdir', str(fault_binary.parent), '-o', fault_binary.name,
        '--timing', '--assert', '--top-module', 'tb_dma64_fault_soc',
        '-DXU_MATRIX_DMA', '-DXU_MATRIX_DMA64', '-DD4K_THROTTLE=7',
        *['-I' + str(p) for p in includes], '-f',
        str(followup_remote / 'native-r1/campaign/fault-rtl.f')]
    require(data['fault_build_argv'] == expected_build, 'Fault build options differ')
    rtl = NORMAL / 'source/rtl'
    files = sorted(p for p in rtl.rglob('*') if p.suffix in ('.v', '.sv'))
    expected_files = [normal_remote / 'source/rtl' / p.relative_to(rtl) for p in files]
    expected_files.append(followup_remote / 'tb_dma64_fault_soc.sv')
    require((campaign / 'fault-rtl.f').read_text() == ''.join('"%s"\n' % p for p in expected_files),
            'Fault RTL source list differs')
    require(sha(campaign / 'fault-obj/cpu64_fault') == data['fault_simulator_sha256'],
            'Fault executable differs')
    plan = read(evidence / 'native-r1/control/plan.json')
    cpus = plan['cpus']
    require(len(cpus) == 3 and len(set(cpus)) == 3, 'Missing guarded three-core allocation')
    checker = load('b41_raw_checker', NORMAL / 'source/check_results.py')
    runner = load('b41_raw_runner', NORMAL / 'run_strict.py')
    stalls, faults = {}, {}
    for kind, cases in (('stall', data['stall_cases']), ('fault', data['fault_cases'])):
        for label, saved in cases.items():
            name = label if kind == 'stall' else label.rsplit('-', 1)[0]
            log = campaign / (label + '-stall31.log' if kind == 'stall' else label + '.log')
            require(sha(log) == saved['log_sha256'], 'Raw log identity differs: ' + label)
            header, raw = log.read_text().split('\n', 1)
            image = normal_remote / 'firmware' / name / 'dma64_soc'
            mode = 1 if label.endswith('-read') else 2
            binary = normal_remote / 'native-r1/campaign/obj/dma64_soc' if kind == 'stall' else fault_binary
            workload = ['+WARMUP=1', '+FIRST_SOURCE_STALL=31', '+DUMPWAVE=0'] if kind == 'stall' else [
                '+WARMUP=0', '+FIRST_SOURCE_STALL=0', '+FAULT=' + str(mode)]
            argv = ['taskset', '-c', str(cpus[0]), str(binary), '+TESTCASE=' + str(image),
                    '+VECTORS=' + str(normal_remote / 'vectors'), '+TASKS=1', '+ROWS=8',
                    '+MAX_CYCLES=20000000', *workload]
            require(json.loads(header)['argv'] == saved['argv'] == argv
                    and saved['firmware_image_sha256'] == prepared['software'][name]['image_sha256'],
                    'Workload or frozen firmware differs: ' + label)
            actual = frozen.check_stall(checker, runner, raw) if kind == 'stall' else frozen.check_fault(checker, raw, mode)
            require(all(saved[k] == v for k, v in actual.items()), 'Raw recomputation differs: ' + label)
            if kind == 'stall':
                measured = actual['measurements']
                require(measured['outputs'] == 25344 and measured['warmup']['outputs'] == 25344
                        and len(measured['physical_clear']) == 2, 'Stall workload scope differs')
                stamps = [x for x in actual['timeline'] if not x['warmup']]
                stalls[name] = dict(first_source_wait_cycles=actual['first_source_wait_cycles'],
                                   measured_outputs=25344, warmup_outputs=25344, physical_clears=2,
                                   report_delay=stamps[0]['report_delay'])
            else:
                faults[label] = actual['terminal']
    sequence = read(evidence / 'sequence-result.json')
    steps = sequence['steps']
    require(sequence['status'] == 'PASS' and len(steps) == 2
            and [s['name'] for s in steps] == [NORMAL.name, FOLLOWUP.name]
            and all(s['native_exit'] == 0 for s in steps)
            and steps[0]['finished_epoch'] <= steps[1]['started_epoch'],
            'Native sequence did not complete in the required order')
    result = dict(status='PASS_RAW_B41_FOLLOWUP', qualification='DEVELOPMENT_RTL_ONLY',
        native_sha256=sha(evidence / 'native-r1/result.json'), campaign_sha256=sha(campaign / 'result.json'),
        input_manifest_sha256=FOLLOWUP_SHA, accepted_full12=data['accepted_full12'],
        cpu_assert_properties=6, fault_compile_units=len(expected_files),
        fault_simulator_sha256=data['fault_simulator_sha256'],
        frozen_checker_sha256=sha(FOLLOWUP / 'run_followup.py'), reviewer_sha256=sha(Path(__file__)),
        native_seconds=native['child']['seconds'], stall_cases=stalls, fault_cases=faults,
        sequence_sha256=sha(evidence / 'sequence-result.json'), physical_energy=None, official_score=None)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status=result['status'], stall_cases=stalls, fault_cases=faults), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--full12', type=Path, default=BASE / 'b41-full12-evidence-r1')
    parser.add_argument('--full12-review', type=Path, default=BASE / 'b41-full12-comparison-r1/result.json')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    review(args.evidence.resolve(), args.full12.resolve(), args.full12_review.resolve(), args.out.resolve())
