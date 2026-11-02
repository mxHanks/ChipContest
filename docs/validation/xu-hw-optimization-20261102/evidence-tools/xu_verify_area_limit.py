#!/usr/bin/env python3
"""Independent physical-library unit and corrected 2.25 mm2 budget audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root = args.report
    requirement_raw = (root/'area-requirement.json').read_bytes()
    requirement = json.loads(requirement_raw.decode())
    limit = requirement['accelerator_area_limit_mm2']
    check(limit == 2.25, 'latest user-corrected area requirement differs')
    raw = (root/'area-compliance.json').read_bytes()
    proof = json.loads(raw.decode())
    paired_raw = (root/'ppa/paired-exact-summary.json').read_bytes()
    paired = json.loads(paired_raw.decode())
    # Preserve the original server receipt and its then-current 2.5 mm2 limit.
    # Physical area inputs remain valid after the user corrects the budget.
    source_limit = proof['requirement']['accelerator_area_limit_mm2']
    check(proof['status'] == 'PASS' and source_limit == 2.5, 'original area receipt identity differs')
    check(proof['paired_summary']['sha256'] == sha(paired_raw), 'synthesis evidence identity differs')
    with tarfile.open(str(root/'artifacts/xu-ppa-reproducibility.tar.xz')) as archive:
        name = 'xu-ppa-reproducibility/ppa/baseline-ss-01/references.rpt'
        references = archive.extractfile(name).read()
    check(sha(references) == proof['source_references_report']['sha256'], 'mapped reference report hash differs')
    text = references.decode()
    samples = proof['physical_standard_cells']['checks']
    check(len(samples) == 4, 'physical standard-cell sample inventory incomplete')
    for cell in samples:
        physical = cell['width_microns'] * cell['height_microns']
        values = re.findall(r'^'+re.escape(cell['cell'])+r'\s+\S+\s*\n\s*([\d.]+)\s+\d+\s+[\d.]+', text, re.M)
        check(values and all(abs(float(value) - physical) < 1e-5 for value in values), 'physical/library cell area differs')
        check(abs(physical - cell['physical_area_um2']) < 1e-9, 'physical area multiplication differs')
    ram = proof['physical_sram']
    physical = ram['cells'][0]['width_microns'] * ram['cells'][0]['height_microns']
    check(abs(physical - ram['lib_cell_area']) < 1e-6, 'physical SRAM size differs from exact Liberty cell area')
    libs = paired['cases']['baseline']['manifest']['libraries']
    check(libs[ram['lib_path']]['sha256'] == ram['lib_sha256'], 'physical SRAM proof uses another Liberty library')
    results = {}
    for name in ['baseline', 'candidate']:
        source, reported = paired['cases'][name], proof['cases'][name]
        check(source['macro_count'] == reported['sram_macro_count'] == 16, 'macro count differs')
        check(abs(source['macro_area'] - 16 * physical) < .01, 'mapped macro sum differs beyond DB float precision')
        area = source['total_cell_area'] / 1000000
        check(abs(area - reported['total_cell_area_mm2']) < 1e-12, 'um2 to mm2 conversion differs')
        check(source['total_cell_area'] == reported['total_cell_area_um2'], 'synthesis cell area differs')
        check(reported['limit_mm2'] == source_limit, 'original receipt budget differs')
        check(abs(reported['headroom_mm2'] - (source_limit-area)) < 1e-12, 'original reported headroom differs')
        check(reported['within_limit'] == (area <= source_limit), 'original area budget decision differs')
        results[name] = dict(area_mm2=area, limit_mm2=limit, headroom_mm2=limit-area,
                             limit_fraction=area/limit, synthesis_cell_plus_macro_budget_pass=area<=limit)
    value = dict(status='PASS', evidence_kind='independent derived numerical and original reference-byte audit',
                 current_requirement_sha256=sha(requirement_raw),
                 source_receipt_historical_limit_mm2=source_limit,
                 requirement_note='Latest user correction sets 2.25 mm2; original 2.5 mm2 server receipt preserved byte-for-byte.',
                 area_proof_sha256=sha(raw), paired_summary_sha256=sha(paired_raw), cases=results,
                 unit_basis='Four mapped standard-cell areas equal LEF SIZE products in um2; exact SRAM Liberty area equals its LEF footprint',
                 lef_syntax_reference='Cadence LEF/DEF 5.7 Language Reference p183: https://www.ispd.cc/contests/18/lefdefref.pdf',
                 limitations=proof['limitations'])
    with args.out.open('x') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True)+'\n')
    print('PASS: candidate {:.9f} mm2 <= {} mm2 (synthesized cell plus SRAM footprint)'.format(results['candidate']['area_mm2'], limit))


if __name__ == '__main__':
    main()
