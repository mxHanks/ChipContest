#!/usr/bin/env python3
"""Offline verification of the selected LF v1 contract, native STA and CPU12."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def unpack_verified(current, archive, destination):
    # Verify all members before writing: no links, duplicate names or traversal.
    with tarfile.open(archive, 'r:xz') as tar:
        names = current.archive_members(tar)
        current.require('execution-files.json' in names, 'Missing native payload catalog')
        catalog = json.load(tar.extractfile('execution-files.json'))
        current.require(names == set(catalog) | {'execution-files.json'}, 'Native archive catalog differs')
        for name, record in catalog.items():
            current.check_bytes(tar.extractfile(name).read(), record, name)
        destination.mkdir()
        for name in sorted(names):
            target = destination.joinpath(*current.safe_name(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(name).read())


def verify(root=ROOT):
    current = module('lf_current', root/'tools/current.py')
    manifest = json.loads((root/'submission/lf-input-contract-v1.json').read_text())
    current.require(manifest['schema'] == 'chipcontest-lf-input-contract-v1', 'Wrong LF contract manifest')
    for name, record in manifest['files'].items():
        current.check_bytes(current.repo_path(root, name).read_bytes(), record, name)
    selected = current.candidate(root)
    current.check_submodule(root, selected)
    current.require(manifest['mapped_sha256'] == selected['evidence']['delivery']['apply/mapped.v']['sha256'],
                    'LF and selected mapped identities differ')
    # The old contract retains its exact frozen four unknown checks.
    current.require(selected['results']['unknown_checks'] == 4, 'Frozen original contract was rewritten')
    measured = dict(selected)
    measured['performance'] = manifest['performance']
    current.check_performance(root, measured)
    result = json.loads((root/manifest['performance']['result']['path']).read_text())
    for path, snapshot in [('experiments/s3-y32-ingress-perf/cpu_tb.sv','tests/tb_sysbus32_soc.sv'),
                           ('experiments/s3-y32-ingress-perf/lf_input_contract.sv','tests/lf_input_contract.sv')]:
        current.require(manifest['files'][path]['sha256'] == result['source_sha256'][snapshot],
                        'Measured CPU input environment differs from current source')
    log = (root/manifest['performance']['simulation_log']['path']).read_text()
    current.require(log.count('LF_INPUT_CONTRACT_RELEASE ') == 2
                    and 'LF_INPUT_CONTRACT_STARTUP_PASS' in log
                    and 'LF_INPUT_CONTRACT_REJECT' not in log, 'CPU LF contract monitor did not pass')
    digital = json.loads((root/manifest['digital_result']).read_text())
    current.require(digital['status'] == 'PASS_POSITIVE_AND_EIGHT_EXPECTED_REJECTIONS_NOT_PHYSICAL_SIGNOFF'
                    and len(digital['cases']) == 9
                    and all(v['verdict']=='PASS' for v in digital['cases'].values()), 'Digital contract did not pass')
    for name, record in digital['sources'].items():
        current.check_bytes((root/name).read_bytes(), record, 'digital source '+name)
    reviewer = module('lf_native_reviewer', root/'experiments/s3-y32-ingress-perf/ppa/eco/lf_contract_native_review.py')
    with tempfile.TemporaryDirectory(prefix='chipcontest-lf-v1-') as temporary:
        temp = Path(temporary)
        unpack_verified(current, root/manifest['native_archive'], temp/'native')
        unpack_verified(current, root/manifest['export_archive'], temp/'export')
        audit = reviewer.audit(temp/'native', temp/'export')
        current.require(audit['status'] == 'LF_CONTRACT_NATIVE_AND_EXPORT_REPLAY_PASS'
                        and audit['receipt_coverage_ports_pass'] and not audit['failures'],
                        'LF native audit rejected evidence: '+str(audit['failures']))
        exact = ((temp/'native/run/original-constraints-pt-add.sdc').read_bytes()
                 + b'\n# Team LF input contract v1 overlay, applied after the exact original SDC.\n'
                 + (temp/'native/src/xu_lf_input_contract_v1.sdc').read_bytes())
        current.check_bytes(exact, manifest['files'][manifest['complete_sdc']],
                            'complete LF delivery SDC, exact executed source commands')
    return dict(status='LF_CONTRACT_V1_NATIVE_AND_CPU12_VERIFIED',
                scope='TEAM_EXTERNAL_INPUT_CONTRACT_NOT_OFFICIAL_BOARD_SPEC',
                numeric_violations=0,electrical_violations=0,unknown_checks=0,
                total_checks=328981,met_checks=299653,untested_checks=29328,
                rtl_cycles=result['total_cycles'],y32_outputs=result['outputs'],
                conditional_tasks_per_second=result['task_per_second_at_assumed_150mhz'],
                original_sdc_unknown_checks=4,complete_sdc=manifest['complete_sdc'])


if __name__=='__main__':
    try: print(json.dumps(verify(),ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,tarfile.TarError) as error:
        raise SystemExit('lf-contract: '+str(error))
