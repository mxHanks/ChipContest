#!/usr/bin/env python3
"""Strict read-only saved-campaign comparison for the frozen bias-only experiments.

8 PE uses the production saved-evidence loader and comparator unchanged.
16 PE uses the prior physical-PE loader on EACH side, then the production
condition/source/ELF/image comparator plus exact unchanged physical-work checks.
This never invokes a simulator, rewrites a campaign, or relaxes its assertions.
"""
from pathlib import Path
import importlib.util
import json
import hashlib

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REPORTER = ROOT / 'tools/analysis/s3_writeback_report.py'
PE16_LOADER = ROOT / 'build/pe16-20261108/compare_pe16.py'
BIAS_PAIR = ('27ab6d4b57588a3b93367b497dd3b6f4b67cef24d283885b8284ad235636cc88',
             '93e20943133e78dbc73b715b85c9cf4a2b04ecbee0da9f4ce64fa2a6a1ec9da9')
PARSER_PAIR = ('03afff21bc9935dc29e55473f98a686154c62c3d4a8aa84fdbdbefc370dfcab8',
               '00ae2ccbf94b8f8856836aada16d2ee6e16bda239c54525d389d7ca139f85832')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save(path, obj):
    with path.open('x') as stream:
        json.dump(obj, stream, indent=2, sort_keys=True)
        stream.write('\n')


report = load_module('production_writeback_verifier', REPORTER)
physical = load_module('frozen_pe16_verifier', PE16_LOADER)


def compare16(before_path, after_path):
    before = physical.load_campaign(before_path, 16)
    after = physical.load_campaign(after_path, 16)
    report.require(before['physical_pes'] == after['physical_pes'] == 16,
                   'this comparison requires 16 PE on both sides')
    report.require(before['conditions']['original_layers'] == after['conditions']['original_layers'] == [0],
                   'this experiment requires exactly original layer 0')
    report.require(before['conditions']['configuration']['schedule'] ==
                   after['conditions']['configuration']['schedule'] == report.DIRECT_SCHEDULE,
                   'this experiment requires the unchanged NICE direct schedule')
    report.require(before['generated_clear_c_identity'] == after['generated_clear_c_identity'],
                   'generated clear C differs beyond the exact normalized snapshot include')
    # No source addition/deletion, no firmware/parser/PE-core/CPU/bus change.
    result = report.compare(before, after, {'rtl/perips/BiasSramPrefetch.sv': BIAS_PAIR})
    result['schema'] = 's3-bias-pipeline-16to16-single-layer-comparison-v1'
    result['physical_profile_loader'] = dict(path=str(PE16_LOADER),
        sha256=hashlib.sha256(PE16_LOADER.read_bytes()).hexdigest(),
        baseline_profile=16, candidate_profile=16,
        validation='strict original load_campaign(..., 16) independently revalidated each raw physical marker')
    result['physical_work'] = []
    for b, a in zip(before['rows'], after['rows']):
        work_before = {k: v for k, v in b['physical'].items() if k != 'checked_cycles'}
        work_after = {k: v for k, v in a['physical'].items() if k != 'checked_cycles'}
        report.require(work_before == work_after, 'physical PE work/control changed')
        result['physical_work'].append(dict(original_layer=b['original_layer'],
            baseline=b['physical'], candidate=a['physical'], unchanged_except_measured_cycles=True))
    result['firmware_identity']['independent_load_verification'] = dict(
        baseline=report.verify_loaded_image(before), candidate=report.verify_loaded_image(after))
    return result


def main():
    baseline8 = ROOT / 'build/writeback-v2-20261108/direct-task0-phase/result.json'
    candidate8 = HERE / 'bias8-task0/result.json'
    base = report.load_campaign(baseline8)
    candidate = report.load_campaign(candidate8)
    # Reviewed final parser delta is exactly one existing direct-marker check.
    old_parser = (baseline8.parent / 'source/tools/scripts/e203_soc.py').read_text()
    new_parser = (candidate8.parent / 'source/tools/scripts/e203_soc.py').read_text()
    needle = "    contract.validate_nice_activity(records, layers, schedule)\n"
    addition = ("    if schedule == contract.NICE_DIRECT_SCHEDULE:\n"
                "        check_direct_activity(log, layers, schedule)\n")
    report.require(old_parser.count(needle) == 1 and
                   new_parser == old_parser.replace(needle, needle + addition, 1),
                   'baseline/candidate parser differs beyond the reviewed final direct-marker validation')
    report.require(base['generated_clear_c_identity'] == candidate['generated_clear_c_identity'],
                   '8 PE generated clear C differs beyond snapshot include')
    expected8 = {'rtl/perips/BiasSramPrefetch.sv': BIAS_PAIR,
                 'tools/scripts/e203_soc.py': PARSER_PAIR}
    result8 = report.compare(base, candidate, expected8)
    result8['firmware_identity']['independent_load_verification'] = dict(
        baseline=report.verify_loaded_image(base), candidate=report.verify_loaded_image(candidate))
    result8['source_review'] = {
        'rtl/perips/BiasSramPrefetch.sv': '24 consecutive SRAM reads plus final capture drain; group-fill only.',
        'tools/scripts/e203_soc.py': 'Exactly two final parser lines call the existing strict direct marker validator; no simulator or firmware change.'}
    save(HERE / 'bias8-comparison.json', result8)
    save(HERE / 'bias8-sourcepairs.json', expected8)
    result16 = compare16(ROOT / 'build/pe16-20261108/pe16-task0/result.json',
                         HERE / 'bias16-task0/result.json')
    save(HERE / 'bias16-comparison.json', result16)
    save(HERE / 'bias16-sourcepairs.json', {'rtl/perips/BiasSramPrefetch.sv': BIAS_PAIR})
    for name, result in [('bias8', result8), ('bias16', result16)]:
        totals = result['totals']
        print(name, result['status'])
        for key in ('payload_cycles', 'clear_cycles', 'payload_plus_clear_cycles', 'clear_to_source_gap'):
            print(key, totals['baseline'][key], totals['candidate'][key], totals['delta'][key])


if __name__ == '__main__':
    main()
