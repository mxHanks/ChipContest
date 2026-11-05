#!/usr/bin/env python3
"""Read-only byte verification for132 tools and actual failed126/export131."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = 'xu-server-coverage-progress-20261105-131.tar.xz'
ARCHIVE_SHA = '64f1b81c1615bfe0708c902342ebb5551baa5eb67358307c9ebdf4d6816398b3'
PREFIX = 'full-soc-coverage-rdc-20261105-126/'
FAILED_STATE_SHA = 'e6b6bd0ede831b18db2ed30633802ac88db8035e8198edf38f66fd18c88237fa'
WORKER_SHA = 'd40a163adf3fe13cbce0a9ecee9258929a07eb53068781a7ce9054694c152f91'
LAUNCHER_SHA = 'aa7fae3cf83b0892cf4c542572e87c91bd7c1ea6c51b6438ee4304bdc2eade2d'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def ident(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def members(data):
    result = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:xz') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            need(member.isfile() and not name.is_absolute() and '..' not in name.parts and
                 member.name not in result and 'private-manuals' not in name.parts,
                 'unsafe/duplicate/private archive member')
            result[member.name] = archive.extractfile(member).read()
    return result


def actual131():
    raw = (HERE / ARCHIVE).read_bytes()
    need(ident(raw) == {'bytes': 305944, 'sha256': ARCHIVE_SHA}, 'original131 archive differs')
    payload = members(raw)
    manifest = json.loads(payload.pop('manifest.json'))
    need(len(payload) == len(manifest) == 49 and sum(map(len, payload.values())) == 21058148,
         'original131 payload count/bytes differ')
    need({r['path'] for r in manifest} == set(payload), 'original131 inventory differs')
    for record in manifest:
        need(ident(payload[record['path']]) == {key: record[key] for key in ('bytes', 'sha256')},
             'original131 member differs: ' + record['path'])
    return payload


def verify():
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    found = {p.relative_to(HERE).as_posix() for p in HERE.rglob('*') if p.is_file() and
             '__pycache__' not in p.parts and p.name != 'input-manifest.json'}
    need(found == set(manifest['files']), 'local132 tool delivery inventory differs')
    for name, expected in manifest['files'].items():
        need(ident((HERE / name).read_bytes()) == expected, 'local132 delivery bytes differ: ' + name)
    need(ident((HERE / 'tools/xu_timing_coverage132.py').read_bytes()) ==
         {'bytes': 39436, 'sha256': WORKER_SHA}, 'frozen132 worker differs')
    need(ident((HERE / 'tools/launch_timing_coverage132.py').read_bytes()) ==
         {'bytes': 2339, 'sha256': LAUNCHER_SHA}, 'frozen132 launcher differs')
    handoff = json.loads((HERE / 'original-delivery/handoff132.json').read_text())
    for name, record in handoff['files'].items():
        if name.endswith('.py'):
            path = HERE / 'tools' / name
        else:
            path = HERE / 'original-delivery' / name
        need(ident(path.read_bytes()) == {key: record[key] for key in ('bytes', 'sha256')},
             'original132 handoff file differs: ' + name)
    payload = actual131()
    get = lambda name: payload[PREFIX + name]
    state = json.loads(get('state.json'))
    need(ident(get('state.json'))['sha256'] == FAILED_STATE_SHA and
         state['status'] == 'FAILED_NOT_QUALIFIED' and state['qualification'] == 'NOT_QUALIFIED',
         'actual126 failed state differs')
    need(state['frozen_before'] == state['frozen_after'] and state['frozen_inputs_unchanged'] is True and
         not state['frozen_after_observation_errors'], 'actual126 original input freeze differs')
    for run in state['runs']:
        for kind in ('log', 'script'):
            record = run[kind]
            name = Path(record['path']).name
            need(ident(get(name)) == {key: record[key] for key in ('bytes', 'sha256')},
                 'actual126 native script/log receipt differs: ' + name)
    docs, diagnosis = state['runs']
    need(len(state['runs']) == 2 and docs['returncode'] == 0 and docs['marker_count'] == 1 and
         not docs['errors'] and diagnosis['returncode'] == 1 and diagnosis['marker_count'] == 0,
         'actual126 run status differs')
    fatal = ('XU_FATAL: exact pin identity missing: u_soc/u_e203_subsys_top/u_sirv_aon_top/'
             'u_sirv_aon_wrapper/u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/Q')
    native_errors = [line for line in get('diagnosis.log').decode().splitlines()
                     if re.match(r'^\s*(?:Error:|Error-|Fatal:|XU_FATAL:)', line)]
    need(diagnosis['errors'] == native_errors and len(native_errors) == 2018 and
         native_errors.count('Error: Nothing matched for -of_objects collection (SEL-005)') == 2017 and
         native_errors[-1] == fatal, 'actual126 exact native failure symptoms differ')
    for name, record in state['outputs'].items():
        need(ident(get(name)) == {key: record[key] for key in ('bytes', 'sha256')},
             'actual126 native output differs: ' + name)
    local13 = json.loads((HERE / 'original-delivery/local-check-final/mechanism13-results.json').read_text())
    regression = json.loads((HERE / 'original-delivery/local-check-final/regression-results.json').read_text())
    need(len(local13['checks']) == 13 and all(r['status'] == 'PASS' for r in local13['checks']) and
         local13['qualification'] == 'NOT_QUALIFIED', 'original132 local13 results differ')
    need(len(regression['checks']) == 10 and all(r['status'] == 'PASS' for r in regression['checks']) and
         regression['worker_sha256'] == WORKER_SHA and regression['qualification'] == 'NOT_QUALIFIED',
         'original132 regression results differ')
    return {'status': 'LOCAL132_FROZEN_TOOLS_AND_ACTUAL126_FAILURE_BYTES_VERIFIED',
            'qualification': 'NOT_QUALIFIED', 'original131_payload_files': 49,
            'actual126_native_errors': 2018, 'mechanism_checks': 13, 'regression_checks': 10,
            'native132_terminal_in_this_archive': False,
            'companion128_130_scope': 'bytes only; no semantic/power qualification claim'}


if __name__ == '__main__':
    print(json.dumps(verify(), sort_keys=True, indent=2))
