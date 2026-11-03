#!/usr/bin/env python3
"""Check this exact S2d server evidence; never issue timing/energy qualification."""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
MAIN = '3af4db98b893edd2103771fa132d69350b82ba96'
CHILD = 'dd692c190dadafd9baa6dffe8514a3f684e7fbf5'
PRODUCER = 'cf836cf677d120d046d366c4b4b0a0bc33ba48ff'
NETLIST = '025240541e4c58318c9fa44e816b54cbcc78f29cd8b5ea8672343a3840118137'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SERVER_BASE = '/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
SERVER_SOURCE = SERVER_BASE+'ChipContest-s2d-01'
SERVER_TOOLS = SERVER_BASE+'ChipContest-ppa-tools-20261103-03'
SERVER_OUT = SERVER_BASE+'s2d-ppa-campaign-20261103-02/s2d'
ORIGINALS = {
    'export15': 'ff1502b37c5557c4c2bb6a3d2bf951a78201bf4284cdd651c2340dfa86d9f6e5',
    'export12': '5938eb6fbdb83798814c61b88a3b75458afbeecdaa0dfbbf0cbf0393f2adb3cb',
    'export13': 'a0afc56a5136024100c6f05581a8d11b8243010cd5a4b5a04839f60fc054cad8',
}
PRODUCER_FILES = {
    'tools/scripts/xu_soc_ppa.py': 'b1a36b656f34526639ee968daf970e2748eab346b2aa5dc10fbb842a33d8e389',
    'tools/ppa/xu_soc_implementation.py': 'ec0ae7b3c8eeb93672740b734da6b1870eccc25c9f77189716e400847f110c76',
    'tools/ppa/xu_review_full_soc_clocks.py': '8d5d78be3bee507d9b037916a6a2b1c8604477cef91ae6fab2afdba583f1d098',
    'tools/ppa/xu_full_soc.sdc': SDC,
    'tools/ppa/xu_full_soc_clock_review.tcl': '10e118b2c131b46a9f26cd27b00f30018737bd73da552c7ae13379d8ccd5d0ee',
    'tools/ppa/xu_sirv_sram_adapter.sv': 'b2b2baaa1e105ed794382886439cd2c16fd280a0f29b54c4d925351e6f90a0c5',
    'tools/ppa/xu_weight_sram_adapter.sv': '86b49e6279e9e9ac2c91467028608be8e3ca1caadb811ddd09d379311730d707',
    'tools/ppa/xu_soc_ppa_top.sv': '8d0e5fd38f2425e7ea8041dd5b8c3a8fd4ce7fa171afb1bf0ebeb6f53446f28a',
    'tools/ppa/xu_shared_icb_sram.sv': '2ebad6ec1870806cb4b770610213aa4d3318e272f6433bf68e6175b15fa25e9d',
}
FINAL = 'raw/export15/s2d-ppa-campaign-20261103-02/'
CASE = FINAL+'s2d/'
EARLY = 'raw/export12/s2d-ppa-campaign-20261103-01/'


def require(value, message):
    if not value:
        raise ValueError(message)


def pairs(items):
    result = {}
    for name, value in items:
        require(name not in result, 'duplicate JSON key: '+name)
        result[name] = value
    return result


def load(path):
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii'))


def data(root, relative):
    path = Path(relative)
    require(not path.is_absolute() and path.parts and '..' not in path.parts and '.' not in path.parts,
            'unsafe evidence relative path: '+str(relative))
    require(path.as_posix() == relative, 'noncanonical evidence relative path')
    for index in range(1, len(path.parts)+1):
        require(not (root/Path(*path.parts[:index])).is_symlink(), 'evidence symlink: '+relative)
    target = root/path
    require(target.is_file(), 'missing evidence file: '+relative)
    return target.read_bytes()


def git(root, *args):
    return subprocess.check_output(['git', '--no-replace-objects']+list(args), cwd=str(root)).decode().strip()


def selected_name(label, name):
    return ((label == 'export15' and name.startswith('s2d-ppa-campaign-20261103-02/')) or
            (label == 'export12' and name.startswith('s2d-ppa-campaign-20261103-01/')) or
            (label == 'export13' and name.startswith('s2d-ppa-campaign-20261103-02/s2d/ppa/rtl/')))


def verify(root=HERE, candidate=None, archive15=None):
    root = Path(root)
    selection = json.loads(data(root, 'selected-manifest.json'), object_pairs_hook=pairs)
    require(selection['schema'] == 'xu-s2d-actual-ppa-selected-v1' and
            selection['status'] == 'EXECUTED_NOT_QUALIFIED', 'selected manifest scope/status differs')
    require(selection['archive15'] == dict(bytes=603824, sha256='75d76d05b6492ebc79442b51c90bb9a1fe2b8cae39fa866747f17ecafe61cf98'),
            'archive15 identity differs')
    if archive15 is not None:
        raw = Path(archive15).read_bytes()
        require(len(raw) == 603824 and sha(raw) == selection['archive15']['sha256'], 'archive15 bytes/hash differ')
    originals = {}
    expected = {}
    for label, expected_hash in ORIGINALS.items():
        name = 'original-'+label+'-manifest.json'
        raw = data(root, name)
        require(sha(raw) == expected_hash, 'original export manifest changed: '+label)
        require(selection['original_manifests'][label] == dict(path=name, sha256=expected_hash, bytes=len(raw)),
                'original export identity differs: '+label)
        entries = json.loads(raw, object_pairs_hook=pairs)
        seen = set()
        for record in entries:
            relative = record['path']
            require(relative not in seen, 'duplicate original payload path')
            seen.add(relative)
            if selected_name(label, relative):
                target = 'raw/'+label+'/'+relative
                expected[target] = dict(path=target, original_path=relative, export=label,
                                        bytes=record['bytes'], sha256=record['sha256'])
        originals[label] = len(entries)
    require(len(expected) == 73 and Counter(r['export'] for r in expected.values()) ==
            Counter(export15=52, export12=3, export13=18), 'selected original payload set differs')
    listed = {}
    for record in selection['files']:
        require(record['path'] not in listed, 'duplicate selected payload path')
        listed[record['path']] = record
    require(listed == expected, 'selected files are not the exact original S2d subset')
    actual = {p.relative_to(root).as_posix() for p in (root/'raw').rglob('*') if p.is_file() or p.is_symlink()}
    require(actual == set(expected), 'extra/missing raw payload')
    for name, record in expected.items():
        raw = data(root, name)
        require(len(raw) == record['bytes'] and sha(raw) == record['sha256'], 'raw SHA/size differs: '+name)
    require(selection['producer']['commit'] == PRODUCER and set(selection['producer']['files']) == set(PRODUCER_FILES),
            'producer commit/file set differs')
    for name, expected_hash in PRODUCER_FILES.items():
        raw = data(root, 'producer/'+name)
        require(sha(raw) == expected_hash and selection['producer']['files'][name] == dict(bytes=len(raw), sha256=expected_hash),
                'frozen producer asset differs: '+name)
    spec = importlib.util.spec_from_file_location('xu_s2d_frozen_ppa_evidence', root/'producer/tools/scripts/xu_soc_ppa.py')
    ppa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ppa)
    state = load(root/(FINAL+'state.json'))
    initial = load(root/(EARLY+'state.json'))
    execution = load(root/(CASE+'ppa/execution.json'))
    prepared = load(root/(CASE+'ppa/prepared.json'))
    impl = load(root/(CASE+'implementation/implementation.json'))
    inv = load(root/(CASE+'implementation/inventory.json'))
    generation = load(root/(CASE+'implementation/generation.json'))
    require(state['status'] == 'EXECUTED_NOT_QUALIFIED' and len(state['runs']) == 1 and
            state['runs'][0]['status'] == 'EXECUTED_NOT_QUALIFIED', 'actual campaign did not complete')
    run = state['runs'][0]
    require(run['candidate'] == 's2d' and run['profile'] == 's2d-doublebuf' and run['source'] == SERVER_SOURCE and
            run['acceptance_sha256'] == 'c2d685bc5cbeef760170e2c315802063676778dac4d7155203a427832f98fa72',
            'candidate/acceptance identity differs')
    require(inv['main_commit'] == MAIN and inv['e203_commit'] == CHILD and inv['root'] == SERVER_SOURCE and
            impl['source_profile'] == 's2d-doublebuf' and
            {k: v for k, v in prepared['inventory'].items() if k != 'created_utc'} ==
            {k: v for k, v in inv.items() if k != 'created_utc'} and prepared['implementation'] == impl,
            'main/child/profile/prepared identity differs')
    freeze = impl['source_freeze']
    require(freeze['main_commit'] == MAIN and freeze['e203_commit'] == CHILD and
            freeze['source_manifest_sha256'] == digest(inv['platform_source']) == inv['platform_source_manifest_sha256'] and
            inv['platform_source_manifest_sha256'] == 'f983e4f3d394f1fbe5ddefd2e186ee5fe5cfaffa73023a98b87535f4e3685636',
            'frozen measured source manifest differs')
    require(len(inv['platform_source']) == 153 and len(prepared['source_files']) == 155 and
            prepared['input_manifest_sha256'] == digest(prepared['source_files']), 'prepared source inventory differs')
    profile = freeze['profile']
    require(profile['e203_commit'] == CHILD and profile['name'] == 's2d-doublebuf' and
            profile['actual_child_tree_manifest_sha256'] == '60d47049f3ebca98a524f1d737e960897322ed419e20ea5a6190f27a7befe49b' and
            profile['changed_files'] == ppa.SOURCE_PROFILES['s2d-doublebuf']['changed_files'] and
            profile['fixed_tree_file_count'] == 1064, 'approved complete child tree/delta differs')
    require(freeze['memory_groups_sha256'] == digest(impl['memory_groups']) and
            freeze['libraries_sha256'] == digest(impl['libraries']) and generation['macro_total'] == 336 and
            impl['memory_groups'] == ppa.template(inv, 's2d-doublebuf')['memory_groups'] and
            impl['defines'] == ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1'], 'macro geometry/defines freeze differs')
    require([(x['role'], x['sha256']) for x in impl['libraries']] == [
        ('standard_cell', 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'),
        ('sram', 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f')], 'same-library identity differs')
    require(impl['constraints'] == dict(path=SERVER_TOOLS+'/tools/ppa/xu_full_soc.sdc', sha256=SDC) and
            execution['analysis_sdc_sha256'] == SDC and execution['netlist_sha256'] == NETLIST,
            'analysis SDC or mapped netlist receipt differs')
    for role, name in [('ppa', 'tools/scripts/xu_soc_ppa.py'),
                       ('implementation_generator', 'tools/ppa/xu_soc_implementation.py'),
                       ('clock_reviewer', 'tools/ppa/xu_review_full_soc_clocks.py')]:
        require(impl['tool_producer'][role] == dict(path=SERVER_TOOLS+'/'+name, sha256=PRODUCER_FILES[name]) and
                generation['tool_producer'] == impl['tool_producer'], 'producer receipt differs')
    require(prepared['producer_sha256'] == PRODUCER_FILES['tools/scripts/xu_soc_ppa.py'] and
            generation['generator_sha256'] == PRODUCER_FILES['tools/ppa/xu_soc_implementation.py'], 'producer SHA differs')
    require(generation['implementation']['sha256'] == sha(data(root, CASE+'implementation/implementation.json')),
            'generation implementation SHA differs')
    replacement_names = {ppa.RTL+'/general/sirv_sim_ram.v': 'tools/ppa/xu_sirv_sram_adapter.sv',
                         ppa.RTL+'/perips/mem_1024x16.sv': 'tools/ppa/xu_weight_sram_adapter.sv'}
    require(set(impl['replacements']) == set(replacement_names), 'replacement set differs')
    for relative, name in replacement_names.items():
        require(impl['replacements'][relative] == dict(path=SERVER_TOOLS+'/'+name, sha256=PRODUCER_FILES[name]),
                'frozen RAM adapter identity differs')
    require(impl['added_sources'] == [dict(path=SERVER_TOOLS+'/'+name, sha256=PRODUCER_FILES[name])
            for name in ['tools/ppa/xu_soc_ppa_top.sv', 'tools/ppa/xu_shared_icb_sram.sv']],
            'full-SoC top/shared asset identity differs')
    proof = load(root/(CASE+'implementation/mapping-proof.json'))
    require(proof['status'] == 'UNREVIEWED' and prepared['mapping_proof'] == proof and
            all(record['status'] == 'NOT_RUN' for record in proof['checks'].values()) and
            proof['mapped_equivalence']['status'] == 'NOT_RUN' and
            execution['qualification_gaps'] == generation['qualification_gaps'] == prepared['qualification_gaps'],
            'original qualification gaps were altered')
    require(load(root/(CASE+'step-0.log')) == generation and
            data(root, CASE+'step-1.log').decode().strip() == 'PREPARED_NOT_QUALIFIED '+SERVER_OUT+'/ppa' and
            data(root, CASE+'step-2.log').decode().strip() == 'EXECUTED_NOT_QUALIFIED '+SERVER_OUT+'/ppa',
            'actual outer step completion differs')
    for name, expected_hash in prepared['generated_sha256'].items():
        content = data(root, CASE+'ppa/'+name) if name != 'constraints.sdc' else data(root, 'producer/tools/ppa/xu_full_soc.sdc')
        require(sha(content) == expected_hash, 'generated Tcl/source list changed: '+name)
    consumed = prepared['source_files']
    for relative, record in inv['platform_source'].items():
        key = 'rtl/'+relative[len(ppa.RTL)+1:]
        mapped = consumed[key]
        require(mapped['original_platform_sha256'] == record['sha256'], 'origin source SHA differs')
        if relative in impl['replacements']:
            require(mapped['replacement'] and {k: mapped[k] for k in ['path', 'sha256']} == impl['replacements'][relative],
                    'replacement source differs')
        else:
            require(not mapped['replacement'] and mapped['sha256'] == record['sha256'] and
                    mapped['path'] == SERVER_SOURCE+'/'+relative, 'frozen original source differs')
    for name, record in expected.items():
        if record['export'] == 'export13':
            relative = record['original_path'].split('/s2d/ppa/', 1)[1]
            require(relative in consumed and sha(data(root, name)) == consumed[relative]['sha256'],
                    'actual exported prepared RTL differs from final consumed source')
    report_checked = 0
    for name, record in execution['reports'].items():
        key = CASE+'ppa/'+name
        if key in expected:
            raw = data(root, key)
            require(len(raw) == record['bytes'] and sha(raw) == record['sha256'], 'execution report receipt differs: '+name)
            report_checked += 1
    for label, filename, marker in [('dc', 'dc.log', 'XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED'),
                                    ('pt', 'pt-sta.log', 'XU_SOC_STA_COMPLETE_NOT_QUALIFIED')]:
        raw = data(root, CASE+'ppa/'+filename)
        require(execution[label]['returncode'] == 0 and execution[label]['log_sha256'] == sha(raw), 'actual tool/log receipt differs')
        text = raw.decode()
        require(len(re.findall('^'+marker+'$', text, re.M)) == 1, 'actual tool completion marker missing/duplicate')
        groups = re.findall(r'^XU_SRAM_GROUP (\w+) count=(\d+) macro_ref=RAMSP1024X16 logical_bits=(\d+) physical_bits=(\d+) padding_bits=0$', text, re.M)
        counts = Counter((name, int(count), int(logical), int(physical)) for name, count, logical, physical in groups)
        require(counts == Counter({(g['name'], g['count'], g['logical_bits'], g['logical_bits']): 2 if label == 'dc' else 1
                                   for g in impl['memory_groups']}), 'actual linked macro marker counts differ')
    area_text = data(root, CASE+'ppa/area.rpt').decode()
    accel_path = ppa.RETAINED['accelerator'][0]
    match = re.findall('^'+re.escape(accel_path)+r'\n\s+([0-9.]+)\s+[^\n]+\saccel_icb_slave\s*$', area_text, re.M)
    require(match == ['303630.2710'], 'actual accelerator area differs')
    total = re.findall(r'^Total cell area:\s+([0-9.]+)$', area_text, re.M)
    require(total == ['3374602.731896'], 'actual whole-SoC cell area differs')
    coverage = data(root, CASE+'ppa/analysis-coverage.rpt').decode()
    rows = re.findall(r'^(setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold|All Checks)\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)', coverage, re.M)
    parsed = {name: dict(zip(['total', 'met', 'violated', 'untested'], map(int, values))) for name, *values in rows}
    require(parsed['All Checks'] == dict(total=314592, met=246839, violated=40790, untested=26963), 'coverage summary differs')
    slack = execution['timing_review']['worst_slack_in_report_time_units']
    require(slack == dict(max=-20.981373, min=-22.642344) and
            execution['status'] == 'EXECUTED_NOT_QUALIFIED' and execution['timing_review']['qualification'] == 'NOT_QUALIFIED' and
            execution['timing_review']['observed_issues'] == ['setup_slack_negative', 'hold_slack_negative', 'no_clock_endpoints', 'report_command_failures'],
            'original timing failure was hidden or relabeled')
    require("Error: unknown option '-verbose' (CMD-010)" in data(root, CASE+'ppa/clock-reports/exceptions.rpt').decode(),
            'unsupported report failure lost')
    require('Warning: There are 24 register clock pins with no clock.' in data(root, CASE+'ppa/check-timing.rpt').decode(),
            'actual unclocked UART latch check changed')
    require(initial['status'] == 'FAIL' and initial['error'] == 's2d step0 failed' and
            "invalid choice: 's2d-doublebuf'" in data(root, EARLY+'s2d/step-0.log').decode(), 'initial CLI failure lost')
    candidate_audit = None
    if candidate is not None:
        candidate = Path(candidate).resolve()
        require(git(candidate, 'rev-parse', 'HEAD') == MAIN and
                git(candidate/ppa.SUB, 'rev-parse', 'HEAD') == CHILD, 'local candidate main/child differs')
        require(ppa.source_profile_identity(candidate, 's2d-doublebuf') == profile, 'actual local child worktree differs')
        actual_inventory = ppa.inventory(candidate)
        require(actual_inventory['platform_source'] == inv['platform_source'] and
                actual_inventory['testbench']['sha256'] == inv['testbench']['sha256'], 'local candidate RTL/TB differs from server receipts')
        count = 0
        for entry in subprocess.check_output(['git', '--no-replace-objects', 'ls-tree', '-rz', MAIN], cwd=str(candidate)).split(b'\0'):
            if not entry:
                continue
            meta, name = entry.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            path = candidate/os.fsdecode(name)
            if kind == 'commit':
                require(mode == '160000' and os.fsdecode(name) == ppa.SUB and oid == CHILD, 'main gitlink differs')
                continue
            require(kind == 'blob', 'unsupported local main tree entry')
            if mode == '120000':
                require(path.is_symlink(), 'local tracked symlink changed')
                content = os.fsencode(os.readlink(str(path)))
            else:
                require(path.is_file() and not path.is_symlink() and bool(path.stat().st_mode & 0o111) == (mode == '100755'),
                        'local tracked main file/mode changed')
                content = path.read_bytes()
            require(hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest() == oid, 'local tracked main bytes changed')
            count += 1
        candidate_audit = dict(status='LOCAL_FROZEN_SOURCE_AND_SERVER_MANIFEST_MATCH', main_blob_count=count,
                               actual_child_entries=profile['fixed_tree_file_count']+len(profile['changed_files']),
                               platform_source_files=len(inv['platform_source']))
    return dict(schema='xu-s2d-actual-ppa-review-v1', status='EVIDENCE_CHECKED_NOT_QUALIFIED',
                selected_payloads=len(expected), actual_final_payloads=52, initial_failure_payloads=3, actual_prepared_rtl_payloads=18,
                verified_report_receipts=report_checked, main_commit=MAIN, child_commit=CHILD, producer_commit=PRODUCER,
                mapped_netlist_sha256=NETLIST, analysis_sdc_sha256=SDC, macro_count=336,
                accelerator_area_um2=match[0], accelerator_area_mm2=str(Decimal(match[0])/Decimal(1000000)),
                whole_soc_cell_area_um2=total[0], coverage=parsed, original_propagated_uncts_slack_ns=slack,
                qualification='NOT_QUALIFIED', not_proven=['mapped equivalence', 'complete150MHz timing', 'fullSoC task energy', 'retention'],
                local_candidate=candidate_audit,
                not_exported_reports={name: record for name, record in execution['reports'].items() if CASE+'ppa/'+name not in expected},
                not_exported_artifacts=['mapped.v', 'mapped.sdc', 'remaining137 prepared RTL files', 'vendor DB bytes'])


def self_test(root):
    cases = []
    with tempfile.TemporaryDirectory(prefix='xu-s2d-evidence-negative-') as temporary:
        clone = Path(temporary)/'evidence'
        shutil.copytree(str(root), str(clone))
        targets = [CASE+'ppa/area.rpt', CASE+'ppa/dc.log', CASE+'ppa/pt-sta.log', CASE+'ppa/analysis-coverage.rpt',
                   CASE+'ppa/execution.json', CASE+'implementation/implementation.json',
                   EARLY+'s2d/step-0.log', 'producer/tools/scripts/xu_soc_ppa.py', 'original-export15-manifest.json']
        for relative in targets:
            path = clone/relative
            original = path.read_bytes()
            path.write_bytes(original+b'\nXU_NEGATIVE_CORRUPTION\n')
            try:
                verify(clone)
            except (ValueError, json.JSONDecodeError):
                cases.append(relative)
            else:
                raise AssertionError('corrupted evidence accepted: '+relative)
            path.write_bytes(original)
        selection_path = clone/'selected-manifest.json'
        original = selection_path.read_bytes()
        selection = load(selection_path)
        selection['files'].append(dict(selection['files'][0]))
        selection_path.write_text(json.dumps(selection))
        try:
            verify(clone)
        except ValueError:
            cases.append('duplicate selected path')
        else:
            raise AssertionError('duplicate selected path accepted')
        selection_path.write_bytes(original)
        target = clone/(CASE+'ppa/area.rpt')
        original_area = target.read_bytes()
        target.write_bytes(original_area.replace(b'303630.2710', b'000001.0000'))
        selection = load(selection_path)
        for record in selection['files']:
            if record['path'] == CASE+'ppa/area.rpt':
                record.update(bytes=target.stat().st_size, sha256=sha(target.read_bytes()))
        selection_path.write_text(json.dumps(selection))
        try:
            verify(clone)
        except ValueError:
            cases.append('area corruption with selected manifest resigned')
        else:
            raise AssertionError('resigned area corruption accepted')
    return dict(status='HOST_CORRUPTION_REJECTED', count=len(cases), cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=HERE)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--archive15', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = verify(args.evidence, args.candidate, args.archive15)
    if args.self_test:
        result['negative_tests'] = self_test(args.evidence)
    text = json.dumps(result, indent=2, sort_keys=True)+'\n'
    if args.out:
        require(not args.out.exists(), 'new output path required')
        args.out.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
