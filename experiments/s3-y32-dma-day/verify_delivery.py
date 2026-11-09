#!/usr/bin/env python3
"""Recompute delivery results from sealed sources, logs, binaries and vectors.

This verifies evidence integrity and scope; it does not turn RTL simulation into
physical timing, official qualification or a proof against forged evidence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

# Importing the sealed checker must not create a cache inside its source tree.
sys.dont_write_bytecode = True


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def require(value, reason):
    if not value:
        raise ValueError(reason)


def module(p):
    spec = importlib.util.spec_from_file_location('sealed_dma_runner', p)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def verify_cpu(folder, tasks, dual, oracle=False):
    report = read(folder/'result.json')
    require(report['status'] == 'PASS', f'{folder}: not PASS')
    require(report['arguments']['tasks'] == tasks and report['arguments']['dual'] == dual,
            'CPU run scope differs')
    require(report['arguments']['warmup'] is True, 'public dirty preconditioning missing')
    manifest = report['source_sha256']
    require(manifest == read(folder/'source-manifest.json')['files'], 'source manifest differs')
    actual = {str(p.relative_to(folder/'source')): sha(p)
              for p in sorted((folder/'source').rglob('*')) if p.is_file()}
    require(actual == manifest, 'frozen source drift')
    require(sha(folder/'firmware/dma_day_soc') == report['firmware']['elf_sha256'], 'ELF drift')
    require(sha(folder/'firmware/dma_day_soc.verilog') == report['firmware']['image_sha256'], 'image drift')
    require(sha(folder/'simulator/dma_day_soc') == report['simulator_sha256'], 'simulator drift')
    checker = module(folder/'source/run_soc.py')
    log = (folder/'simulation.log').read_text()
    recomputed = checker.check_log(log, tasks, dual, True)
    for key, value in recomputed.items():
        require(report[key] == value, f'raw log differs from result: {key}')
    physical = checker.check_physical_clear(log, tasks, True)
    require(report['physical_clear'] == physical, 'physical clear differs')
    for item in report['vectors']:
        for name, digest in item['sha256'].items():
            require(sha(folder/'vectors'/f'layer_{item["layer"]:02d}'/name) == digest,
                    'task vector identity differs')
    require(report['outputs'] == tasks*25344 and report['source_drift'] == [], 'incomplete outputs or source drift')
    require(report['clock']['throughput_conversion_hz'] == 150000000, 'clock conversion changed')
    if oracle:
        require(checker.check_vectors(folder/'vectors', tasks) == report['vectors'], 'independent oracle differs')
    # Damage the original raw log in memory, never change sealed evidence.
    negatives = []
    mutations = {
        'missing_final_task': re.sub(r'^DMA_TASK_PASS layer='+str(tasks-1)+r'.*\n', '', log, flags=re.M),
        'wrong_payload': re.sub(r'(DMA_TASK_PASS layer=0 .*?payload=)\d+', r'\g<1>1', log, count=1),
        'wrong_mac_count': re.sub(r'(DMA_COUNTS layer=0 .*?macs=)\d+', r'\g<1>1', log, count=1),
        'missing_soc_completion': re.sub(r'^DMA_SOC_PASS.*\n', '', log, flags=re.M),
        'missing_warmup': re.sub(r'^DMA_WARMUP_DONE.*\n', '', log, flags=re.M),
        'missing_clear_address': re.sub(r'(DMA_PHYSICAL_CLEAR_PASS .*?W=)16384', r'\g<1>16383', log, count=1),
        'missing_clear_payload': log.replace('all_payload_zero=1', 'all_payload_zero=0', 1),
    }
    for name, damaged in mutations.items():
        rejected = False
        try:
            checker.check_log(damaged, tasks, dual, True)
            checker.check_physical_clear(damaged, tasks, True)
        except (ValueError, KeyError):
            rejected = True
        require(rejected, 'damaged evidence accepted: '+name)
        negatives.append(name)
    return report, negatives


def verify(args):
    root = args.evidence_root.resolve()
    dual, dn = verify_cpu(root/args.dual, 12, 1, args.oracle)
    single, sn = verify_cpu(root/args.single, 12, 0, False)
    require(dual['source_sha256'] == single['source_sha256'], 'modes use different sources')
    require(dual['simulator_sha256'] == single['simulator_sha256'], 'modes use different simulator')
    require(dual['firmware']['elf_sha256'] == single['firmware']['elf_sha256'], 'modes use different ELF')
    baseline = args.baseline.resolve()
    old = read(baseline/'result.json')
    freeze = read(root/'baseline/freeze.json')
    require(sha(baseline/'result.json') == freeze['baseline_result_sha256'], 'baseline changed')
    require(old['status'] == 'DEVELOPMENT_PASS_POLICY_PENDING' and old['outputs'] == 304128 and len(old['task_results']) == 12,
            'baseline incomplete')
    for relative, digest in old['original_source_sha256'].items():
        require(sha(baseline/'source'/relative) == digest, 'baseline source drift: '+relative)
    baseline_sum = 0
    for i, task in enumerate(old['task_results']):
        require(task['original_layer'] == i and task['cycles'] == 422768, 'baseline task changed')
        require(int(task['clear']['clear_cycles']) == 66802, 'baseline clear changed')
        require(int(task['clear']['gap_to_source_request']) == 102, 'baseline gap changed')
        baseline_sum += task['cycles']+int(task['clear']['clear_cycles'])
        raw = (baseline/f'task-{i:02d}/simulation.log').read_text()
        require(re.search(r'^TASK_PASS layer=0 outputs=25344 writes=25344 cycles=422768 ', raw, re.M),
                'baseline raw output marker absent')
        for name, digest in old['integer_reference'][i]['sha256'].items():
            require(dual['vectors'][i]['sha256'][name] == digest, 'baseline/candidate task identity differs')
    require(baseline_sum == 5874840, 'baseline principal changed')
    cpu_files = []
    for relative, digest in dual['source_sha256'].items():
        if relative.startswith('rtl/core/'):
            require(sha(baseline/'source'/relative) == digest, 'CPU/LSU/BIU/config modified: '+relative)
            cpu_files.append(relative)
    require(len(cpu_files) >= 42, 'CPU source set incomplete')
    fallback = read(root/'fallback-task0-r1/result.json')
    require(fallback['status'] == 'PASS' and fallback['principal'] == 489570, 'fallback not proved')
    protocol = read(root/args.protocol/'result.json')
    require(protocol['status'] == 'PASS' and protocol['source_drift'] == [], 'protocol not proved')
    fabric = read(root/'fabric-preflight/result.json')
    require(fabric['status'] == 'PASS', 'fabric probe failed')
    for record in protocol['source_files']:
        if record['path'].endswith('xu_matrix_dma.sv'):
            require(dual['source_sha256']['rtl/perips/xu_matrix_dma.sv'] == record['sha256'], 'protocol/CPU DMA differs')
    table = []
    for i, (one, two) in enumerate(zip(single['layers'], dual['layers'])):
        # Check each task independently; do not allow cancellation between layers.
        require(two['principal'] < one['principal'] < 489570, f'no per-layer gain: {i}')
        table.append(dict(layer=i,baseline=489570,single=one['principal'],dual=two['principal'],
                          clear=two['clear'],gap=two['gap'],including_gap=two['including_gap'],
                          payload=two['payload']))
    return dict(status='PASS',scope='independently revalidated delivery evidence; RTL simulation only',
                inputs={str(p):sha(p) for p in [root/args.dual/'result.json',root/args.single/'result.json',baseline/'result.json',root/args.protocol/'result.json']},
                engineering_scope='CPU full12 modes, numerical outputs, real clear, interfaces and local evidence; PPA/qualification separate',
                baseline_principal=baseline_sum,single_principal=single['principal_cycles'],
                dual_principal=dual['principal_cycles'],dual_including_gap=dual['including_gap_cycles'],
                dual_task_per_second=dual['task_per_second_at_150mhz'],
                performance_target_met=dual['principal_cycles']<=1800000,
                clock_condition_hz=150000000,unchanged_cpu_files=len(cpu_files),
                outputs_per_mode=304128,negative_log_checks={'dual':dn,'single':sn},layers=table,
                area_sta_official='Not established by this verifier; inspect separate area report and limitations.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--dual',default='cpu-dual-full12-r2')
    parser.add_argument('--single',default='cpu-single-full12-r2')
    parser.add_argument('--protocol',default='protocol-r4')
    parser.add_argument('--oracle',action='store_true')
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    try:
        result = verify(args)
    except Exception as exc:
        print('DELIVERY_FAIL: '+str(exc),file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print('DELIVERY_PASS principal='+str(result['dual_principal'])+' outputs=304128')
    return 0


if __name__ == '__main__':
    sys.exit(main())
