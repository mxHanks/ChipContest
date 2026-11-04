#!/usr/bin/env python3
"""Check actual114 raw identities and narrow conclusions; no EDA re-execution."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path(__file__).resolve().parent
ARCHIVE_SHA = 'bc3188abb1448f993e71eb2e7e08a8aa76eac40c8be115806fc0697ae41618ab'
CORE107_SHA = 'b21734f9957a35feeb847b8a5d2a03c1934c2f3ff7e5270001822e9630faeb58'
NET = '0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
SVF = '1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9'
LOG = 'db12cfc23725e1ebfbacad6d8c4a0253487cb066ac47eea41b9e5648d789b174'
P109 = 's2e-own-formality-audit-20261104-109/'
P113 = 'mapped-udp-occurrence-20261104-113/'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def unpack(directory, archive_sha, archive_bytes, count, payload_bytes):
    archive = directory / 'payload.tar.xz'
    need(archive.stat().st_size == archive_bytes and sha(archive.read_bytes()) == archive_sha,
         'archive identity differs: ' + str(directory))
    manifest = json.loads((directory / 'payload-manifest.json').read_text())
    expected = {row['path']: row for row in manifest}
    need(len(expected) == len(manifest) == count and sum(row['bytes'] for row in manifest) == payload_bytes,
         'manifest dimensions differ: ' + str(directory))
    found, internal = {}, None
    with tarfile.open(archive, 'r|xz') as stream:
        for member in stream:
            path = PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in found and member.size < 8000000, 'unsafe/duplicate tar member')
            body = stream.extractfile(member).read()
            if member.name == 'manifest.json':
                need(internal is None, 'duplicate internal manifest')
                internal = json.loads(body)
                continue
            need(dict(path=member.name, bytes=len(body), sha256=sha(body)) == expected.get(member.name),
                 'original member differs: ' + member.name)
            found[member.name] = body
    need(internal == manifest and set(found) == set(expected), 'missing/unaccounted original payload')
    return found


def verify(extract=None):
    raw = unpack(ROOT, ARCHIVE_SHA, 167364, 40, 5371538)
    # The independent109 receipt does not contain the FM log body. Re-read its
    # hash-frozen original107 archive instead of trusting the new status alone.
    core = unpack(ROOT.parent / 'xu-score-server-core107-20261104', CORE107_SHA, 49904, 13, 1066360)
    tools = json.loads((ROOT / 'tools-manifest.json').read_text())
    expected_tools = {
        'tools/export114.py': (2672, '71760aa7ffd46d3d877ce083a9cbd9847e210ee698127bb68d80ce865450547f'),
        'tools/launch_formal_audit109.py': (832, '39e1d14fa15a03283795541bb0f8c5ce5b014940c07643f39362d80385bfc8de'),
        'tools/xu_s2e_formality_audit109.py': (12123, 'fb468c230b528a364e2f013684e80b0135b7debc75746f90a62057f18aa91bbc'),
        'tools/xu_udp_occurrence113.py': (9834, '5563c46e3e2036c687eeee0c223c630120730e32c9ce530064b9028cf9b91c68'),
        'tools/xu_udp_review108.py': (22054, '53edd2c4da4e2a335d8332f7909918d43fc77dfd79078d96229f5a45bec30991')}
    need(len(tools) == len(expected_tools) == 5, 'tool manifest dimensions differ')
    for row in tools:
        need(row['path'] in expected_tools and (row['bytes'], row['sha256']) == expected_tools[row['path']],
             'expected tool identity differs')
        body = (ROOT / row['path']).read_bytes()
        need(len(body) == row['bytes'] and sha(body) == row['sha256'], 'archived producer bytes differ')

    def obj(name):
        return json.loads(raw[name])

    original = 's2e-ppa-campaign-20261104-89/'
    campaign = json.loads(core[original + 'state.json'])
    formal = json.loads(core[original + 'formality/state.json'])
    receipt = obj(P109 + 'state.json')
    context = receipt['context']
    need(receipt['schema'] == 'xu-s2e-native-own-fm-audit-v1' and
         receipt['status'] == 'AUDITED_ORIGINAL_FULL_SOC_FORMALITY_PASS_NOT_QUALIFIED' and
         receipt['started_epoch'] < receipt['finished_epoch'] and
         receipt['producer']['sha256'] == expected_tools['tools/xu_s2e_formality_audit109.py'][1],
         'actual109 terminal producer/scope differs')
    need(receipt['frozen_before'] == receipt['frozen_after'] == context['frozen_inputs'] and
         len(receipt['frozen_before']) == 181, 'actual109 original-input audit receipt differs')
    frozen = receipt['frozen_before']
    need(context['original_status'] == campaign['status'] == 'EXECUTED_FORMALITY_FAILED_NOT_QUALIFIED' and
         context['original_formality_status'] == formal['status'] == 'FAIL' and
         formal['returncode'] == 0 and formal['frozen_before'] == formal['frozen_after'] and
         len(formal['frozen_before']) == 159 and
         campaign['inputs_before'] == campaign['inputs_after'] and len(campaign['inputs_before']) == 15,
         'original89 false-failure receipt must remain unchanged')
    for records in [formal['frozen_before'], campaign['inputs_before']]:
        need(all(frozen.get(path) == record for path, record in records.items()),
             'actual109 original159/15-input scope differs')
    need(context['source_profile'] == campaign['source_before'] == campaign['source_after'] and
         context['source_profile']['name'] == 's2e-paired-hi' and
         context['source_profile']['e203_commit'] == 'a0767db69628ef30e53de2d1e93dd0360c0ccf76' and
         context['source_profile']['main_source_freeze']['main_commit'] == '5bf123bfead8f2a37f97f3234d4e40ce8201aae9',
         'actual109 exact accepted S2e source profile differs')
    need(context['netlist'] == campaign['netlist'] and context['netlist']['sha256'] == NET and
         context['own_svf'] == campaign['own_svf'] and context['own_svf']['sha256'] == SVF and
         context['acceptance'] == campaign['acceptance_before'] == campaign['acceptance_after'] and
         context['acceptance']['raw_files_checked'] == 4138 and
         context['acceptance']['paired_real12_cycles'] == 10420140 and
         context['acceptance']['control_real12_cycles'] == 11842200,
         'actual109 own mapped/SVF/runtime acceptance binding differs')
    # Every original107 body that109 says it audited must match locally available
    # original bytes. Bodies unavailable here remain server rehash receipt data.
    for name, body in core.items():
        if name.startswith(original):
            absolute = str(Path(context['original_root']).parent / name)
            if absolute in frozen:
                need(frozen[absolute] == dict(path=absolute, bytes=len(body), sha256=sha(body)),
                     'actual109 bound original107 body differs: ' + name)
    log_body = core[original + 'formality/fm.log']
    need(sha(log_body) == LOG == formal['log']['sha256'], 'actual native original FM log differs')
    text = log_body.decode()
    marker = 'XU_S2E_FULL_SOC_FORMALITY_PASS'
    need('Version R-2020.09-SP5' in text and re.findall(r'^' + marker + r'[ \t]*$', text, re.M) == [marker] and
         re.findall(r'^Verification (?:SUCCEEDED|FAILED)[ \t]*$', text, re.M) == ['Verification SUCCEEDED'] and
         re.findall(r'^[ \t]*(\d+) Passing compare points[ \t]*$', text, re.M) == ['42338'] and
         not re.search(r'^\s*(?:Error:|Fatal:|FATAL:|XU_S2E_FULL_SOC_FORMALITY_(?:FAIL|SCRIPT_ERROR))', text, re.M),
         'actual original native full-FM success/unique marker differs')
    for label, values in [('Passing (equivalent)', [17136, 0, 0, 0, 144, 25019, 39, 42338]),
                          ('Failing (not equivalent)', [0] * 8), ('  Unread', [0, 0, 0, 0, 0, 511, 0, 511])]:
        rows = re.findall(r'^' + re.escape(label) + r'[ \t]+([0-9 \t]+)$', text, re.M)
        need(len(rows) == 1 and list(map(int, rows[0].split())) == values, 'actual native FM breakdown differs')
    for top in ['Reference design: r:/WORK/xu_soc_ppa_top', 'Implementation design: i:/WORK/xu_soc_ppa_top']:
        need(len(re.findall(r'^[ \t]*' + re.escape(top) + r'[ \t]*$', text, re.M)) == 1,
             'actual native full-SoC proof scope differs')
    need(set(re.findall(r'^[ \t]*(\d+)\((\d+)\) Unmatched reference\(implementation\) compare points[ \t]*$', text, re.M)) == {('17', '0')} and
         not re.search(r'^.*(?:Aborted compare points|Failing compare points|Unverified compare points).*$', text, re.M) and
         re.findall(r'^' + marker + r'\s*$', text, re.M) == [marker + '\n'],
         'original proof coverage/newline-only false-failure mechanism differs')
    need({key: value for key, value in context['native'].items() if key != 'limits'} == dict(
         black_box_pins=17136, dff=25019, latches=39, passing=42338, ports=144,
         unmatched_implementation=0, unmatched_reference_dff=17, unread_dff=511),
         'actual109 returned native counts differ from independent original-log review')

    state = obj(P113 + 'state.json')
    counts = obj(P113 + 'occurrences.json')
    need(state['status'] == 'EXECUTED_READONLY_LEXICAL_COUNTS_NOT_QUALIFIED' and
         state['qualification'] == counts['qualification'] == 'NOT_QUALIFIED' and
         state['input_sha256_before'] == state['input_sha256_after'] and state['inputs_unchanged'] and
         not state['vendor_body_exported'] and not counts['vendor_body_exported'],
         'actual113 terminal scope/input freeze differs')
    before = state['input_sha256_before']
    need([(row['bytes'], row['sha256']) for row in before] == [
         (2198450, '9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581'),
         expected_tools['tools/xu_udp_review108.py'], expected_tools['tools/xu_udp_occurrence113.py']],
         'actual113 fixed source/helper/producer differs')
    need(counts['source_identity'] == before[0] and counts['preprocessing_helper_identity'] == before[1] and
         state['report']['bytes'] == len(raw[P113 + 'occurrences.json']) and
         state['report']['sha256'] == sha(raw[P113 + 'occurrences.json']) and
         counts['status'] == 'LEXICAL_COUNTS_ONLY_NOT_QUALIFIED', 'actual113 original report binding differs')
    need([(mode['mode'], mode['additional_defines']) for mode in counts['modes']] == [
         ('full_clean_source_no_conditional_selection', []), ('actual_default', []),
         ('FUNCTIONAL', ['FUNCTIONAL']), ('functional', ['functional']),
         ('both_functional_symbols', ['FUNCTIONAL', 'functional'])], 'actual113 selected-source scope differs')
    expected_clean = [
        (197088, 'f5a45ed428e7b2f9c088e19b7e5639a8fdd7ced6821a73d9a9899626e63b063a'),
        (184388, '8954583c037f8953a8ab85caa63224b60f80333ade3b2b6ee7d8bd62ead20712'),
        (184388, '8954583c037f8953a8ab85caa63224b60f80333ade3b2b6ee7d8bd62ead20712'),
        (49576, 'fefdbf30ae980e1bfe99d9fcb592af398d4ecaf6c199975b487ab663d278ca4b'),
        (49576, 'fefdbf30ae980e1bfe99d9fcb592af398d4ecaf6c199975b487ab663d278ca4b')]
    for mode, (tokens, digest) in zip(counts['modes'], expected_clean):
        need(mode['clean_source_bytes'] == 2198450 and mode['all_identifier_token_count'] == tokens and
             mode['clean_source_sha256'] == digest and len(mode['targets']) == 2,
             'actual113 original complete-source count/identity differs')
        for target, name, lines in zip(mode['targets'], ['udp_tlatrf', 'udp_tlatrf2'],
                                       [[101797, 101923], [101830, 101946]]):
            need(target['name'] == name and target['total_identifier_occurrences'] ==
                 target['primitive_definition_count'] == len(target['occurrence_lines']) ==
                 len(target['primitive_definition_lines']) == 2 and
                 target['occurrence_lines'] == target['primitive_definition_lines'] == lines and
                 target['escaped_occurrence_count'] == target['nondefinition_occurrence_count'] == 0 and
                 target['nondefinition_occurrence_lines'] == [] and
                 target['no_other_lexical_reference_in_this_selected_source'] is True,
                 'actual113 lexical occurrences are not exhausted by the two definition names')
    need(counts['no_other_lexical_reference_in_all_five_sources'] is True,
         'actual113 local-source lexical conclusion differs')

    # Keep unrelated progress from the same immutable114 export, with its actual
    # state at that time. A live snapshot never becomes a completed energy claim.
    diagnostic = obj('mapped-task00-public-diagnostic-20261104-111/state.json')
    sim = raw['mapped-task00-public-diagnostic-20261104-111/simulation.log'].decode()
    need(diagnostic['status'] == 'FAIL_PUBLIC_DIAGNOSTIC_NOT_QUALIFIED' and
         diagnostic['error']['message'] == 'required private gate unexpectedly returned zero' and
         [step['returncode'] for step in diagnostic['steps']] == [0, 0, 0] and
         'XU_MAPPED111_PROTOCOL_REJECT unknown_shared_handshake' in sim and
         '$finish at simulation time        9359423333333' in sim and
         not re.search(r'^XU_MAPPED111_(?:SOURCE|FINAL|PUBLIC_COMPLETE)', sim, re.M),
         'actual111 original protocol rejection/driver failure must remain visible')
    audit = obj('s2c-native-pin-audit-20261104-112/state.json')
    need(audit['status'] == 'RUNNING' and [task['task_id'] for task in audit['tasks']] == list(range(10)),
         'actual112 snapshot is10 tasks, not a terminal12-task claim')
    observed = {row['prefix']: row for row in obj('live114-observation.json')['observed']}
    need(observed['s2e-own-formality-audit-20261104-109']['pid_alive_now'] is False and
         observed['mapped-task00-public-diagnostic-20261104-111']['pid_alive_now'] is False and
         observed['s2c-native-pin-audit-launch-20261104-112']['pid_alive_now'] is True and
         observed['s2c-native-pin-audit-launch-20261104-112']['pid'] == 2501 and
         'xu_native_pin_audit112.py' in observed['s2c-native-pin-audit-launch-20261104-112']['command'] and
         obj('omitted114-bodies.json') == [], 'actual114 specific process/body scope differs')
    need(obj('s2e-activity-deploy-20261104-109/state.json')['status'] == 'TOOLS_READY_AUDIT_AND_ACTIVITY_NOT_RUN',
         'activity tool deployment is not a task run')
    if extract:
        extract.mkdir(exist_ok=False)
        for name, body in raw.items():
            target = extract / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    return dict(status='PASS', qualification='NOT_QUALIFIED', archive_sha256=ARCHIVE_SHA,
                payload_count=40, payload_bytes=5371538, actual109_passing_compare_points=42338,
                actual109_server_frozen_receipt_files=181,
                actual113_scope='FIVE_SELECTED_SOURCES_EACH_TWO_DEFINITION_NAMES_NO_OTHER_LEXICAL_REFERENCE',
                actual111='REAL_UNKNOWN_HANDSHAKE_FATAL_AND_DRIVER_ERROR_PRESERVED',
                actual112='LIVE10_TASK_SNAPSHOT_NOT_COMPLETION')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.extract), sort_keys=True, indent=2))
