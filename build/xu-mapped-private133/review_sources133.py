#!/usr/bin/env python3
"""Inventory all60 source strategies without modifying source or original checks."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import extract_private133 as xu

ROOT = Path('/home/mxhanks/Projects/ChipContest-xu-score-opt')
SOURCE = Path('/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup/third-party/e203_hbirdv2')
PPA = ROOT / 'docs/validation/xu-score-s0-soc-20261102/s2bc-area-formality-server-20261103/raw/s2c-ppa-campaign-20261103-01/s2c/ppa/prepared.json'


def find_records(tree, key):
    found = []
    if isinstance(tree, dict):
        for name, item in tree.items():
            if name == key and isinstance(item, dict) and 'sha256' in item:
                found.append(item)
            found += find_records(item, key)
    elif isinstance(tree, list):
        for item in tree:
            found += find_records(item, key)
    return found


def choose_source(row):
    macro, signal = row['original_macro'], row['original_path']
    if macro == 'XU_HCLK':
        return 'rtl/e203/subsys/e203_subsys_hclkgen.v', signal
    if macro == 'EXU':
        return ('rtl/e203/core/e203_exu_regfile.v' if signal.endswith('rf_r') else
                'rtl/e203/core/e203_exu_commit.v'), signal.rsplit('.', 1)[-1]
    if '.peArray.' in signal:
        return 'rtl/e203/perips/MacPEArray.sv', signal.rsplit('.', 1)[-1]
    if '.core.io_group' in signal:
        return 'rtl/e203/perips/LinearCachedCore.sv', 'io_group'
    if signal.startswith('u_linear_compute_core.'):
        return 'rtl/e203/perips/LinearAutoGroupCore.sv', signal.rsplit('.', 1)[-1]
    return 'rtl/e203/perips/accel_icb_slave.v', signal


def priority(row):
    signal = row['original_path']
    if row['original_macro'] == 'XU_HCLK':
        return 'PLL_NINE_CONTROLS'
    if row['original_macro'] == 'EXU':
        return 'EXU_ORIGINAL_HALT'
    if any(s in signal for s in ['bias', 'cache', 'x_load', 'xLoad', 'x_addr']):
        return 'X_BIAS_CLEAR'
    if any(s in signal for s in ['row', 'head', 'tail', 'core_done', 'core_start', 'compute_start', 'busy']):
        return 'FIFO_STORAGE_OWNERSHIP'
    return 'OPERAND_STREAM_COMMIT_OWNERSHIP'


def run(out):
    out = Path(out)
    outputs = [out / 'source-review133.json', out / 'private60-source-table.md']
    xu.need(not any(p.exists() for p in outputs), 'source evidence output already exists')
    manifest = json.loads(PPA.read_text())
    refs = xu.load_references()
    identities = {}
    for r in refs:
        relative, token = choose_source(r)
        p = SOURCE / relative
        if relative not in identities:
            identity = xu.parser.identity(p)
            matches = find_records(manifest, 'third-party/e203_hbirdv2/' + relative)
            xu.need(matches and all(m['sha256'] == identity['sha256'] for m in matches),
                    'candidate source differs from actual S2c manifest: ' + relative)
            identities[relative] = dict(identity=identity, actual_s2c_manifest_sha_matches=True)
        lines = p.read_text().splitlines()
        hits = [dict(line=i, text=line) for i, line in enumerate(lines, 1)
                if re.search(r'(?<![A-Za-z0-9_$])' + re.escape(token) + r'(?![A-Za-z0-9_$])', line)]
        xu.need(hits, 'source token missing: ' + relative + ' ' + token)
        r.update(target_mapping_status='PENDING_TARGET9C16_BODY_UNAVAILABLE',
                 source_strategy=xu.source_strategy(r), priority=priority(r),
                 source_file=relative, source_token=token,
                 source_occurrence_count=len(hits), source_evidence=hits[:12])
    for relative, item in identities.items():
        xu.need(item['identity'] == xu.parser.identity(SOURCE / relative),
                'source mutated while reviewing')
    builder = ROOT / 'build/xu-mapped-task00-111/xu_build_mapped_task00111.py'
    builder_text = builder.read_text()
    xu.need('Mandatory final $fatal;60 required private state paths remain pending; no bypass option' in builder_text and
            'XU_MAPPED111_REQUIRED_GATE_PENDING' in builder_text, 'original111 hard gate missing')
    record = dict(status='SOURCE_STRATEGIES_ONLY_ALL60_TARGET_BINDINGS_PENDING',
                  original72_private60_preserved=True, private_gates_discharged=0,
                  source_category_counts=dict(Counter(r['category'] for r in refs)),
                  source_port_lookup_strategy_count=sum(r['category'] in xu.SOURCE1 for r in refs),
                  original111_builder=xu.parser.identity(builder),
                  ppa_manifest=xu.parser.identity(PPA), source_identities=identities,
                  references=refs)
    out.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    table = ['# xu all60 private source observations', '',
             '**Every target9c16 binding remains pending.** The category below is source-only lookup strategy, not mapped proof.', '',
             '| Original macro.path | Candidate/source strategy | Width × lanes | Original TB lines | Source evidence |',
             '|---|---|---:|---|---|']
    for r in refs:
        evidence = ','.join(str(e['line']) for e in r['source_evidence'])
        table.append('| `{0}.{1}` | `{2}`; {3} | {4} × {5} | {6} | `{7}`:{8} |'.format(
            r['original_macro'], r['original_path'], r['candidate'], r['category'],
            r['width_each'], r['lanes'], ','.join(map(str, r['original_tb_lines'])),
            r['source_file'], evidence))
    outputs[1].write_text('\n'.join(table) + '\n')
    print(json.dumps(dict(status=record['status'], references=len(refs),
                          port_lookup_strategy=record['source_port_lookup_strategy_count'],
                          manifest_matched_source_files=len(identities))))


if __name__ == '__main__':
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--out', type=Path, required=True)
    args = arg.parse_args()
    run(args.out)
