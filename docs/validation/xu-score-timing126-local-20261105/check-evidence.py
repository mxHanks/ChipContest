#!/usr/bin/env python3
"""Read-only verification of126 frozen tools and original host checks; no EDA."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

HERE = Path(__file__).resolve().parent
PARENT_ARCHIVE = HERE.parent / 'xu-score-timing116-terminal122-20261105/xu-server-terminal-20261105-122.tar.xz'
PARENT_SHA = '654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50'
PREFIX = 'full-soc-timing-combined-20261105-116/'
EXPECTED_TOOLS = {
    'xu_timing_coverage126.py': (33770, '64de7a24a25e03a6c132f844747fa059618c4a8c85c1b84da95838a7e1c2438a'),
    'launch_timing_coverage126.py': (2339, '8894234de27aeeb486b7e4b446f315d81c8b6d6c36c8f3e5158bde2a0c2eef7a'),
    'check_local126.py': (10268, '8e359ca34c40dd4ff532d5744d1a0fc76480fa32967c1ee66e25e015fc1907c3'),
}
EXPECTED_CHECKS = [
    'python36_grammar',
    'actual116_full_coverage_27124_and_10416_labels',
    'generated_tcl_complete_native_tcl_parser',
    'no_new_constraint_clock_case_cut_propagation',
    'tcl_tsv_escaping_roundtrip',
    'structural_disabled_arc_independent_traversal_and_unknown_rejection',
    'actual_coverage_plus_artificial_constants_inactive_mode_proof_only',
    'reject_flip_physical_mode_evidence',
    'reject_case_physical_mode_evidence',
    'reject_missing_physical_mode_evidence',
    'reject_duplicate_physical_mode_evidence',
    'reject_unrestored_report_display',
    'reject_unowned_coverage_reason',
]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def ident(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read_members(data):
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            need(member.isfile() and not name.is_absolute() and '..' not in name.parts and
                 member.name not in result, 'unsafe/duplicate archive entry')
            result[member.name] = archive.extractfile(member).read()
    return result


def parent_fixtures():
    raw = PARENT_ARCHIVE.read_bytes()
    need(ident(raw) == {'bytes': 1283388, 'sha256': PARENT_SHA}, 'original122 sibling archive differs')
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    members = read_members(raw)
    result = {}
    for name, expected in manifest['actual116_fixtures'].items():
        data = members[PREFIX + name]
        need(ident(data) == expected, 'actual116 fixture differs: ' + name)
        result[name] = data
    need(len(result) == 3, 'exact three actual116 fixture bodies required')
    return result


def verify():
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    found = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and
             '__pycache__' not in p.parts and p.name != 'input-manifest.json'}
    need(found == set(manifest['files']), 'delivery file inventory differs')
    for name, expected in manifest['files'].items():
        need(ident((HERE / name).read_bytes()) == expected, 'delivery bytes differ: ' + name)
    for name, (size, digest) in EXPECTED_TOOLS.items():
        need(ident((HERE / 'tools' / name).read_bytes()) == {'bytes': size, 'sha256': digest},
             'frozen original tool differs: ' + name)
    members = read_members((HERE / 'local-check-03.tar.xz').read_bytes())
    receipts = json.loads((HERE / 'hostcheck03-members.json').read_text())
    need(set(members) == set(receipts) and len(members) == 17, 'original03 member inventory differs')
    for name, data in members.items():
        need(ident(data) == receipts[name], 'original03 member differs: ' + name)
    result_raw = (HERE / 'hostcheck03-results.json').read_bytes()
    need(result_raw == members['results.json'], 'original03 results copy differs')
    need(ident(result_raw)['sha256'] == 'd22c75827cef16c3eb37fa4bb49bf9987645f88fbcab22b0790d6280d84ce17b',
         'final original03 results differ')
    result = json.loads(result_raw)
    need(result['checks'] == [{'name': name, 'status': 'PASS'} for name in EXPECTED_CHECKS],
         'exact13 hostcheck results required')
    need(result['qualification'] == 'NOT_QUALIFIED' and result['status'] ==
         'LOCAL126_MECHANISM_CHECKS_PASS_NOT_SERVER_EXECUTION', 'hostcheck scope differs')
    reproduction = json.loads((HERE / 'reproduction-receipt.json').read_text())
    need(reproduction['returncode'] == 0 and reproduction['qualification'] == 'NOT_QUALIFIED' and
         reproduction['reproduced_results_equal_original_bytes'] is True and
         reproduction['reproduced_result'] == reproduction['expected_original03_result'] == ident(result_raw),
         'independent reproduction receipt differs')
    fixtures = parent_fixtures()
    need(result['actual_input_sha256'] == {name: ident(data)['sha256'] for name, data in fixtures.items()},
         'hostcheck actual116 input hashes differ')
    handoff = json.loads((HERE / 'original-delivery/handoff126.json').read_text())
    for name, receipt in handoff['files'].items():
        if name in EXPECTED_TOOLS:
            data = (HERE / 'tools' / name).read_bytes()
        elif name == 'README.md':
            data = (HERE / 'original-delivery/README.md').read_bytes()
        elif name == 'local-check-03/results.json':
            data = result_raw
        else:
            raise ValueError('unexpected original handoff file')
        need(ident(data) == {key: receipt[key] for key in ('bytes', 'sha256')},
             'original handoff receipt differs: ' + name)
    return {'status': 'LOCAL126_FROZEN_TOOLS_AND_ORIGINAL13_HOSTCHECKS_VERIFIED',
            'qualification': 'NOT_QUALIFIED', 'original03_members': len(members),
            'hostchecks': len(EXPECTED_CHECKS), 'native126_results_in_this_archive': False}


if __name__ == '__main__':
    print(json.dumps(verify(), sort_keys=True, indent=2))
