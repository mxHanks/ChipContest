#!/usr/bin/env python3
"""xu: replay exact PE64 VCS development evidence; no physical qualification."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import types

H = Path(__file__).resolve().parent
MAIN = '3443fad8945577626d226b1cd53eadec89331a20'
CHILD = '7aae96776e116d5e95d6ebb49d29a5fccce04ab9'
OLD = '6f47746a916e14d0bbdcbb799c6338acd5c979a7'
SUB = 'third-party/e203_hbirdv2'
S64, S32, S8 = ['bias-hw-' + x + 'autogroup-window' for x in ['pe64-', 'pe32-', '']]
FULL = ['real12', 'same64-schedule32-control-real12', 'same64-schedule8-control-real12',
        'physical32-wide32-control-real12', 'physical8-auto8-control-real12']
SCHEDULES = dict(zip(FULL, [S64, S32, S8, S32, S8]))
VARIANTS = dict(zip(FULL, ['pe64', 'pe64', 'pe64', 'pe32', 'pe8']))
TOTALS = dict(zip(FULL, [11301600, 11376501, 11842200, 11376501, 11842200]))


def need(value, message):
    if not value:
        raise ValueError(message)


def digest(b):
    return hashlib.sha256(b).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def read(path):
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def sha(path):
    return digest(path.read_bytes())


def sources_from(path):
    with tarfile.open(path, 'r:xz') as tar:
        members = tar.getmembers()
        need(len(members) == len({m.name for m in members}) and all(m.isfile() and not Path(m.name).is_absolute()
             and '..' not in Path(m.name).parts for m in members), 'unsafe/duplicate frozen source')
        return {m.name: tar.extractfile(m).read() for m in members}


def audit(root=H):
    selected = read(root / 'selected-manifest.json')
    transports = read(root / 'transports.json')
    expected_transports = [
        ('next-results-export-28', 188, 265524, 'b5f00d48912278915a8236e3bcc7b1080e0b3eaa02126539984a8e04b51ea1d7', '66d6630e41a8178d56ea2dfc58bddc986f5bf827b770f9ce71a80756d033abb1'),
        ('terminal-results-export-22', 142, 807588, 'a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d', '19968bd0ecc5fd25a3e9f2a698040f472bbb9d696bcba624ad4b03abc85d5ba7')]
    need(len(transports) == 2 and len(selected) == len({r['path'] for r in selected}) == 206, 'raw uniqueness/count differs')
    originals, expected_paths = {}, set()
    for receipt, (name, count, size, expected_sha, manifest_sha) in zip(transports, expected_transports):
        need(receipt == dict(name=name, payload_count=count, bytes=size, sha256=expected_sha, manifest_sha256=manifest_sha), 'transport receipt differs')
        path = root / (name + '-manifest.json')
        need(sha(path) == manifest_sha, 'original export manifest differs')
        manifest = read(path)
        need(len(manifest) == len({r['path'] for r in manifest}) == count, 'export manifest differs')
        originals[name] = {r['path']: r for r in manifest}
        expected_paths.update(r['path'] for r in manifest if r['path'].startswith('s3-pe64-'))
    need({r['path'] for r in selected} == expected_paths, 'raw selection differs')
    for record in selected:
        name, path = record['export'], Path(record['path'])
        need(not path.is_absolute() and '..' not in path.parts and str(path) == record['path'], 'unsafe raw path')
        need(originals[name][str(path)] == {k: record[k] for k in ['path', 'bytes', 'sha256']}, 'raw origin differs')
        raw = root / 'raw' / path
        need(raw.is_file() and not any(p.is_symlink() for p in [raw, *raw.parents])
             and raw.stat().st_size == record['bytes'] and sha(raw) == record['sha256'], 'raw bytes differ: ' + str(path))
    need({x.relative_to(root / 'raw').as_posix() for x in (root / 'raw').rglob('*') if x.is_file()} == expected_paths, 'extra/missing raw')
    source_audit = read(root / 'git-source-audit.json')
    sources = sources_from(root / 'frozen-git-sources.tar.xz')
    need(source_audit['main_commit'] == MAIN and source_audit['e203_commit'] == CHILD
         and source_audit['full_manifest_entries'] == 2713 and source_audit['full_blob_entries'] == 2712
         and source_audit['archived_source_count'] == len(sources) == 242, 'frozen source counts/pins differ')
    need({n: digest(b) for n, b in sources.items()} == source_audit['source_sha256'], 'frozen source bytes differ')
    full = read(root / 'deployment/source-files.json')
    need(full == read(root / 'raw/s3-pe64-deploy-20261103-02/source-files.json')
         and sha(root / 'deployment/source-files.json') == source_audit['full_source_manifest_sha256'], 'full source manifest differs')
    listed = {}
    for label, commit, prefix, count in [('main', MAIN, '', 1637), ('child', CHILD, SUB + '/', 1076)]:
        entries = full[label]['files']
        need(full[label]['commit'] == commit and len(entries) == len({e['path'] for e in entries}) == count, 'full source entries differ')
        for entry in entries:
            listed[prefix + entry['path']] = entry
    need(listed[SUB] == dict(path=SUB, mode='160000', git_oid=CHILD), 'child gitlink differs')
    for name, b in sources.items():
        original_name = name.replace(SUB + '/vsim/install/rtl/', SUB + '/rtl/e203/')
        need(original_name in listed and listed[original_name]['sha256'] == digest(b)
             and listed[original_name]['bytes'] == len(b), 'source not bound to full deployment: ' + name)
    package = read(root / 'deployment/package-files.json')
    need(package == read(root / 'raw/s3-pe64-deploy-20261103-02/package-files.json'), 'package manifest differs')
    for name in ['launch.py', 'README.md', 'source-files.json', 'source-identity.json']:
        raw = root / 'deployment' / name
        need(raw.stat().st_size == package[name]['bytes'] and sha(raw) == package[name]['sha256'], 'deployment original differs')
    need((root / 'deployment/launch.py').read_bytes() == sources['tools/scripts/xu_s3_pe64_server.py'], 'server launcher not frozen')
    boot = read(root / 'raw/s3-pe64-deploy-20261103-02/boot.json')
    receipt = read(root / 'deployment/packaging-receipt.json')
    need(boot['identity'] == read(root / 'deployment/source-identity.json')
         and receipt['bytes'] == boot['archive_bytes'] == 680660
         and receipt['sha256'] == boot['archive_sha256'] == 'b6252dad7bb2fad8d3ff3320863e952567613f7f65bf483a061897bbb7a3edf7', 'server package transport differs')
    contract = types.ModuleType('xu_firmware_contract')
    exec(compile(sources['tools/scripts/xu_firmware_contract.py'], '<frozen-contract>', 'exec'), contract.__dict__)
    sys.modules['xu_firmware_contract'] = contract
    soc = types.ModuleType('xu_frozen_soc')
    soc.__file__ = str(root / '_frozen/tools/scripts/e203_soc.py')
    exec(compile(sources['tools/scripts/e203_soc.py'], '<frozen-runner>', 'exec'), soc.__dict__)
    fixture = json.loads(sources['tests/e203/vectors/kwt-silence-v1.json'])
    with tempfile.TemporaryDirectory(prefix='xu-pe64-integer-') as directory:
        temp = Path(directory)
        (temp / 'tests/e203/vectors').mkdir(parents=True)
        for name in ['kwt-silence-v1.json', 'kwt-silence-v1.tar.gz']:
            (temp / 'tests/e203/vectors' / name).write_bytes(sources['tests/e203/vectors/' + name])
        soc.TESTS = temp / 'tests/e203'
        soc.load_fixture(temp / 'vectors', 12)
        integer_layers = soc.check_vectors(temp / 'vectors', 12)
    R = root / 'raw/s3-pe64-accept-02'
    state, accept = read(R / 'state.json'), read(R / 'acceptance/acceptance.json')
    names = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', *FULL]
    need(state['status'] == accept['status'] == 'VCS_ACCEPTED_NOT_RETAINED'
         and state['acceptance_status'] == accept['acceptance_status'] == 'PASS', 'terminal acceptance differs')
    need(state['main_commit'] == accept['main_commit'] == MAIN and state['e203_commit'] == accept['e203_commit'] == CHILD
         and state['verified_source_paths'] == 2713, 'accepted source pins/count differ')
    need(state['steps'] == accept['steps'] and [s['name'] for s in state['steps']] == names
         and all(s['status'] == 'PASS' for s in state['steps']), 'complete twelve steps differ')
    host, numeric = [(R / 'acceptance' / (n + '.log')).read_text() for n in ['host', 'numeric']]
    need(re.search(r'Ran 68 tests in [0-9.]+s\s+OK \(skipped=4\)\s*$', host) and state['steps'][0]['tests'] == 68
         and state['steps'][0]['skipped'] == 4, 'actual host68/skipped4 differs')
    need(re.search(r'Ran 42 tests in [0-9.]+s\s+OK\s*$', numeric), 'numeric42 differs')
    need(state['steps'][0]['required_actual_vcs'] == ['cached-wrapper', 'pe64-wide64', 'pe64-compat32', 'pe64-compat8', 'pe64-boundaries']
         and state['direct_vcs'] == accept['direct_vcs'], 'mandatory direct VCS scope differs')
    runs, log_count, source_count, rejected = {}, 0, 0, []

    def validate_log(text, tasks, schedule, variant):
        layers = soc.check_log(text, tasks)
        for layer, perf in zip(layers, soc.check_performance(text, layers, schedule, variant)):
            layer['performance'] = perf
        return layers, soc.check_autogroup_activity(text, layers, schedule), soc.check_pe_activity(text, layers, schedule, variant)

    for step in state['steps'][2:]:
        name, argv = step['name'], step['argv']
        schedule, variant = SCHEDULES.get(name, S64), VARIANTS.get(name, 'pe64')
        need(argv[argv.index('--sim') + 1] == 'vcs' and argv[argv.index('--firmware-schedule') + 1] == schedule
             and argv[argv.index('--accel-variant') + 1] == variant and '--firmware-opt=-O2' in argv
             and argv[argv.index('--firmware-experiment') + 1] == 'both-unroll-no-masks', 'step configuration differs')
        D = R / 'acceptance' / name
        j = read(D / 'result.json')
        need(j['status'] == 'PASS' and j['main_commit'] == MAIN and (name == 'vectors' or j['e203_commit'] == CHILD), 'result pin/status differs')
        need(j['simulator'] == 'vcs' and j['accel_variant'] == variant and j['firmware_schedule'] == schedule
             and j['firmware_opt'] == '-O2' and j['firmware_experiment'] == 'both-unroll-no-masks', 'actual configuration differs')
        need(j['transaction_contract'] == contract.task_contract(schedule)
             and j['contract_sha256'] == digest(sources['tools/scripts/xu_firmware_contract.py']), 'contract differs')
        if 'runner_sha256' in j:
            need(j['runner_sha256'] == digest(sources['tools/scripts/e203_soc.py']), 'runner source differs')
        for n, expected in j.get('source_sha256', {}).items():
            need(digest(sources[n]) == expected, 'measured source differs')
            source_count += 1
        for n, expected in j.get('log_sha256', {}).items():
            need((D / n).is_file() and sha(D / n) == expected, 'declared log differs: ' + name + '/' + n)
            log_count += 1
        if 'firmware_build' in j:
            need(j['firmware_build']['configuration'] == contract.configuration(schedule, '-O2', 'both-unroll-no-masks')
                 and j['firmware_sha256'] == j['firmware_build']['source_sha256'], 'firmware configuration differs')
            need(all(digest(sources['tests/e203/firmware/' + n]) == v for n, v in j['firmware_sha256'].items()), 'firmware source differs')
            need(j['firmware_elf_sha256'] == j['firmware_build']['elf_sha256']
                 and j['firmware_image_sha256'] == j['firmware_build']['image_sha256'], 'ELF/image receipt differs')
        if name == 'vectors':
            need(j['layers'] == integer_layers and j['outputs'] == 304128 and j['fixture'] == fixture, 'independent integer output recomputation differs')
        if name == 'baseline':
            need(j['tests'] == ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x'], 'legacy5 differs')
            for legacy in j['tests']:
                log = (D / (legacy + '.log')).read_text()
                invocation = json.loads(log.split('\n', 1)[0])
                need('SIM=vcs' in invocation and 'XU_ACCEL_PE64=1' in invocation and 'TEST_PASS' in log
                     and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', log), 'actual PE64 legacy differs')
        if name in ['vectors', 'doctor', 'baseline']:
            continue
        tasks = {'synthetic1': 1, 'synthetic2': 2}.get(name, 12)
        log = (D / 'simulation.log').read_text()
        need('Compiler version Q-2020.03-SP2-6_Full64; Runtime version Q-2020.03-SP2-6_Full64' in log, 'actual VCS runtime differs')
        layers, auto, pe = validate_log(log, tasks, schedule, variant)
        need(j['layers'] == layers and j['autogroup_activity'] == auto and j['pe_activity'] == pe and j['tasks'] == tasks
             and j['outputs'] == tasks * 25344 and j['write_words'] == tasks * 50688
             and len(j['source_sha256']) == 162, 'actual task/performance/activity differs')
        if tasks == 12:
            need(j['fixture'] == fixture and j['vectors'] == fixture['files'], 'fixed real12 fixture differs')
        need(step['total_cycles'] == sum(x['cycles'] for x in layers), 'step total cycles differs')
        runs[name] = j
        corruptions = [
            ('missing_TASK', re.sub(r'^TASK_PASS[^\n]*\n', '', log, count=1, flags=re.M)),
            ('duplicate_TASK', log + next(x for x in log.splitlines() if x.startswith('TASK_PASS ')) + '\n'),
            ('missing_PERF', re.sub(r'^PERF_TASK[^\n]*\n', '', log, count=1, flags=re.M)),
            ('wrong_MMIO', log.replace('mmio_writes=' + str(layers[0]['performance']['mmio_writes']), 'mmio_writes=0', 1)),
            ('wrong_shared_reads', log.replace('shared_reads=23232', 'shared_reads=23231', 1)),
            ('missing_SOC', re.sub(r'^SOC_PASS[^\n]*\n', '', log, flags=re.M)),
            ('appended_FATAL', log + '\nFATAL corruption\n'),
            ('missing_AUTO', re.sub(r'^AUTO_TASK[^\n]*\n', '', log, count=1, flags=re.M)),
            ('wrong_POP', log.replace('pops_retired=' + str(auto[0]['pops_retired']), 'pops_retired=0', 1))]
        if variant != 'pe8':
            corruptions += [('missing_PE', re.sub(r'^PE_TASK[^\n]*\n', '', log, count=1, flags=re.M)),
                ('wrong_physical_PEs', log.replace('physical_pes=' + str(pe[0]['physical_pes']), 'physical_pes=1', 1)),
                ('wrong_enabled_lane_MACs', log.replace('lane_macs=1622016', 'lane_macs=103809024', 1))]
        else:
            corruptions += [('unexpected_PE', log + 'PE_TASK layer=0 physical_pes=64 mac_beats=25344 lane_macs=1622016 useful_macs=1622016\n')]
        for label, bad in corruptions:
            need(bad != log, 'ineffective corruption')
            try:
                validate_log(bad, tasks, schedule, variant)
            except ValueError:
                rejected.append(name + '/' + label)
            else:
                raise ValueError('accepted corrupt actual log: ' + name + '/' + label)
    direct = {}
    for kind, width, expected, activity in [
        ('wide64', 64, [8, 62, 15, 15, 11031, 11031], (960, 57856)),
        ('compat32', 32, [16, 190, 27, 27, 11131, 11131], (1728, 53760)),
        ('compat8', 8, [64, 958, 99, 99, 11731, 11731], (6336, 50688)),
        ('boundary', 0, None, None)]:
        receipt = state['direct_vcs'][kind]
        need(receipt['status'] == 'PASS' and receipt['backend'] == 'vcs', 'direct VCS receipt differs')
        for base in [R / 'direct-pe64-vcs', R / 'acceptance/host-pe64-wrapper-vcs']:
            D = base / kind
            compile_meta = json.loads((D / 'compile.log').read_text().split('\n', 1)[0])
            log = (D / 'simulation.log').read_text()
            need(Path(compile_meta['argv'][0]).name == 'vcs' and 'Compiler version Q-2020.03-SP2-6_Full64' in log
                 and not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', log), 'direct actual backend/failure differs')
            for n in compile_meta['argv']:
                if str(n).startswith(state['source'] + '/'):
                    relative = n[len(state['source']) + 1:]
                    installed = relative.replace(SUB + '/rtl/e203/', SUB + '/vsim/install/rtl/')
                    need(relative in sources or installed in sources, 'direct compiled source not frozen')
            if kind == 'boundary':
                need(re.findall(r'^XU_PE64_BOUNDARY_PASS mode=(\d+) unknown_reads=14 mode_error=1 pop_retired=1$', log, re.M) == ['0', '1', '2']
                     and log.splitlines().count('XU_PE64_BOUNDARIES_PASS modes=3') == 1, 'boundary modes/error/POP differ')
            else:
                rows = re.findall(r'^XU_PE64_WRAPPER_PASS mode_lanes=' + str(width) + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)$', log, re.M)
                need(len(rows) == 1 and list(map(int, rows[0])) == expected and receipt['counts'] == expected, 'direct work/retirement differs')
                need(re.findall(r'^XU_PE64_DIRECT_ACTIVITY physical_pes=64 mac_beats=(\d+) lane_macs=(\d+)$', log, re.M)
                     == [tuple(map(str, activity))], 'direct actual enabled lane activity differs')
        for n, expected_sha in receipt['logs'].items():
            need(sha(R / 'direct-pe64-vcs' / kind / n) == expected_sha, 'direct declared log differs')
            log_count += 1
        direct[kind] = receipt
    cached = R / 'acceptance/host-wrapper-vcs'
    need('Version Q-2020.03-SP2-6_Full64' in (cached / 'compile.log').read_text()
         and re.findall(r'^XU_CACHED_WRAPPER_PASS accepted=(\d+) retired=(\d+)$', (cached / 'simulation.log').read_text(), re.M)
         == [('4909', '4909')], 'actual cached VCS wrapper differs')
    common = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256', 'versions', 'tools',
              'vectors', 'fixture', 'firmware_sha256', 'firmware_opt', 'firmware_experiment']
    for key in common:
        need(all(runs[n][key] == runs[FULL[0]][key] for n in FULL), 'five-way identity differs: ' + key)
    hashes = [runs[n]['simulator_sha256'] for n in FULL]
    need(hashes[0] == hashes[1] == hashes[2] and len(set(hashes)) == 3, 'same64/distinct32/8 simulator identity differs')
    need(all(a['performance'] == b['performance'] for a, b in zip(runs[FULL[1]]['layers'], runs[FULL[3]]['layers']))
         and all(a['performance'] == b['performance'] for a, b in zip(runs[FULL[2]]['layers'], runs[FULL[4]]['layers'])),
         'same-schedule physical controls differ')
    rows = []
    keys = ['pe64_wide_cycles', 'same64-schedule32_cycles', 'same64-schedule8_cycles', 'physical32-wide32_cycles', 'physical8-auto8_cycles']
    for layer in range(12):
        row = dict(layer=layer)
        for name, key in zip(FULL, keys):
            row[key] = runs[name]['layers'][layer]['cycles']
        rows.append(row)
    totals = {key: sum(row[key] for row in rows) for key in keys}
    need(totals == dict(zip(keys, TOTALS.values())), 'five actual full12 totals differ')
    need([r[keys[0]] for r in rows] == [941800] * 12 and [r[keys[1]] for r in rows] == [948039] + [948042] * 11
         and [r[keys[2]] for r in rows] == [986850] * 12, 'per-layer comparison differs')
    comparison = read(R / 'full12-comparison.json')
    need(comparison['status'] == 'PASS' and comparison['identities_identical'] == common and comparison['rows'] == rows
         and comparison['totals'] == totals and comparison['same_pe64_simulator_sha256'] == hashes[0]
         and comparison['physical32_simulator_sha256'] == hashes[3] and comparison['physical8_simulator_sha256'] == hashes[4]
         and comparison['result_sha256'] == {n: sha(R / 'acceptance' / n / 'result.json') for n in FULL}, 'server comparison differs from recomputation')
    for key, against in [('wide64_reduction_vs_same64_schedule32_percent', FULL[1]), ('wide64_reduction_vs_same64_schedule8_percent', FULL[2])]:
        need(comparison[key] == 100 * (TOTALS[against] - TOTALS['real12']) / TOTALS[against], 'cycle reduction arithmetic differs')
    failure = read(root / 'raw/s3-pe64-accept-01/failure.json')
    need(failure == read(root / 'raw/s3-pe64-accept-01/state.json') and failure['status'] == 'FAIL' and failure['main_commit'] == OLD
         and failure['e203_commit'] == CHILD and failure['stage'] == 'host', 'original failed campaign differs')
    old_host = (root / 'raw/s3-pe64-accept-01/acceptance/host.log').read_text()
    need("TypeError: __init__() got an unexpected keyword argument 'text'" in old_host
         and '/usr/lib64/python3.6/subprocess.py' in old_host and 'FAILED (errors=1, skipped=4)' in old_host, 'original Python3.6 failure omitted')
    need(source_audit['unchanged_child'] is True and source_audit['server01_to_02_paths'] == [
        'docs/validation/xu-score-s3-pe64-python36-20261103/README.md', 'docs/validation/xu-score-s3-pe64-python36-20261103/contract-replay.log',
        'docs/validation/xu-score-s3-pe64-python36-20261103/payload-manifest.json', 'tests/e203/test_pe64_contract.py',
        'tools/scripts/xu_prepare_pe64_deployment.py', 'tools/scripts/xu_s3_pe64_bootstrap.py']
         and sha(root / 'server01-to-02.patch') == source_audit['server01_to_02_patch_sha256'], 'server fix scope differs')
    with (root / 'per-layer-comparison.csv').open(newline='') as stream:
        csv_rows = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    need(csv_rows == rows, 'comparison CSV differs')
    expected_perf = [dict(configuration=name, layer=layer['layer'], cycles=layer['cycles'], **layer['performance'])
                     for name in FULL for layer in runs[name]['layers']]
    with (root / 'per-layer-performance.csv').open(newline='') as stream:
        perf_rows = [{k: v if k == 'configuration' else int(v) for k, v in row.items()} for row in csv.DictReader(stream)]
    need(perf_rows == expected_perf, 'performance CSV differs')
    git_replay = read(root / 'full-git-replay.json')
    need(git_replay['status'] == 'PASS' and git_replay['source_manifest_sha256'] == sha(root / 'deployment/source-files.json')
         and git_replay['counts'] == dict(main=dict(entries=1637, blobs=1636, gitlinks=1), child=dict(entries=1076, blobs=1076, gitlinks=0))
         and len(git_replay['rejected_corruptions']) == 10, 'full Git replay receipt differs')
    old_sources = sources_from(root / 'server01-compatibility-sources.tar.xz')
    need({n: digest(b) for n, b in old_sources.items()} == source_audit['old_source_sha256'], 'original compatibility source differs')
    return dict(status='VERIFIED_PE64_VCS_DEVELOPMENT_RESULTS_NOT_QUALIFIED', main_commit=MAIN, e203_commit=CHILD,
        raw_payloads=206, raw_bytes=sum(x['bytes'] for x in selected), full_manifest_entries_preparation_verified=2713,
        full_blob_entries_preparation_verified=2712, frozen_source_blobs=len(sources), measured_sources_per_simulation=162,
        source_hash_checks=source_count, declared_log_hash_checks=log_count, host=dict(tests=68, skipped=4), numeric_tests=42,
        integer_outputs_independently_recomputed=304128, full12_configurations=5, full12_outputs_reported_per_configuration=304128,
        comparison=comparison, direct=direct, rejected_actual_log_corruptions=rejected, retained=False,
        scope='Development4ns HF/66ns LF, first shared source acceptance to final output response retirement; no candidate formal-clear first-request protocol.',
        limitations=['VCS TB verifies each retired output against golden; output values were not emitted/retrieved for separate replay of actual server output bytes.',
            'Fixed golden304128 outputs were independently recomputed from frozen integer vectors; this is not official floating-point accuracy acceptance.',
            'Server ELF/image/simulator and installed vector bytes were not downloaded: their recorded SHA values are not independently rehashed here.',
            'No mapped equivalence, complete150MHz timing, same-library area, fullSoC task energy, retention or contest score is asserted.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=H)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    data = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.out:
        args.out.write_text(data)
    else:
        print(data, end='')
