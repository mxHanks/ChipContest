#!/usr/bin/env python3
"""Replay actual compact-W32 local evidence, without a physical qualification claim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--raw', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root, raw = args.root.resolve(), args.raw.resolve()
    require(not args.out.exists(), 'output must be new')
    sys.path.insert(0, str(root / 'tools/scripts'))
    import e203_soc as soc

    manifest = load(raw / 'manifest.json')
    actual = {p.relative_to(raw).as_posix() for p in raw.rglob('*') if p.is_file()}
    require(actual == set(manifest) | {'manifest.json'}, 'raw payload set differs')
    for name, record in manifest.items():
        path = raw / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and
                not path.is_symlink(), 'invalid raw path: ' + name)
        require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'],
                'raw identity differs: ' + name)
    identity = load(raw / 'identity.json')
    require(identity['production_main'] == 'c684402dc38bcc4437bf822f24d9ea4f401e1da3' and
            identity['child'] == '52cfbea1f79f10e44f7d1696f54015797f886b96' and
            identity['main_clean'] and identity['child_clean'], 'source provenance differs')
    source_files = load(raw / 'source-files.json')
    for name, record in source_files.items():
        path = root / name
        if record['git_mode'] == '120000':
            require(path.is_symlink(), 'missing source symlink: ' + name)
            data = os.readlink(path).encode()
            require(os.readlink(path) == record['link_target'], 'source link differs: ' + name)
        else:
            require(path.is_file() and not path.is_symlink(), 'source must be regular: ' + name)
            data = path.read_bytes()
            require(bool(path.stat().st_mode & 0o111) == (record['git_mode'] == '100755'),
                    'source executable mode differs: ' + name)
        require(len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'],
                'source bytes differ: ' + name)

    schedule = 'bias-hw-pe32-autogroup-window'

    def read_run(name, variant):
        directory = raw / name
        report = load(directory / 'result.json')
        text = (directory / 'simulation.log').read_text().split('\n', 1)[1]
        layers = soc.check_log(text, 1)
        for layer, performance in zip(layers, soc.check_performance(text, layers, schedule, variant)):
            layer['performance'] = performance
        require(report['status'] == 'PASS' and report['main_commit'] == identity['production_main'] and
                report['e203_commit'] == identity['child'] and report['simulator'] == 'verilator' and
                report['tasks'] == 1 and report['accel_variant'] == variant and
                report['firmware_schedule'] == schedule and report['layers'] == layers,
                'run identity/counters differ: ' + name)
        require(report['pe_activity'] == soc.check_pe_activity(text, layers, schedule, variant) and
                report['autogroup_activity'] == soc.check_autogroup_activity(text, layers, schedule),
                'actual PE/FIFO work differs: ' + name)
        require(report['firmware_opt'] == '-O2' and
                report['firmware_experiment'] == 'both-unroll-no-masks', 'compiler flags differ')
        for key, path in [('runner_sha256', 'tools/scripts/e203_soc.py'),
                          ('contract_sha256', 'tools/scripts/xu_firmware_contract.py')]:
            require(sha(root / path) == report[key], 'runner/contract differs')
        for path, digest in report['source_sha256'].items():
            prefix = 'third-party/e203_hbirdv2/vsim/install/rtl/'
            source = (root / 'third-party/e203_hbirdv2/rtl/e203' / path[len(prefix):]
                      if path.startswith(prefix) else root / path)
            require(sha(source) == digest, 'measured RTL differs: ' + path)
        for path, digest in report['log_sha256'].items():
            require(sha(directory / path) == digest, 'measured log differs: ' + path)
        for path, digest in report['firmware_sha256'].items():
            require(sha(root / 'tests/e203/firmware' / path) == digest, 'firmware source differs')
        require(sha(directory / 'accel_soc') == report['firmware_elf_sha256'] and
                sha(directory / 'accel_soc.verilog') == report['firmware_image_sha256'], 'firmware output differs')
        vector_check = soc.check_vectors(directory / 'vectors', 1)
        require(vector_check[0]['outputs'] == 25344, 'independent signed integer reference incomplete')
        for path, digest in report['vectors'].items():
            require(sha(directory / 'vectors' / path) == digest == report['fixture']['files'][path],
                    'fixture tensor differs: ' + path)
        return report

    compact = read_run('real1-bank128', 'pe32-bank128')
    original = read_run('real1-old32', 'pe32')
    common = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256',
              'versions', 'tools', 'vectors', 'fixture', 'firmware_sha256', 'firmware_opt',
              'firmware_experiment', 'firmware_image_sha256', 'layers', 'autogroup_activity', 'pe_activity']
    for key in common:
        require(compact[key] == original[key], 'memory-only control differs: ' + key)
    require(compact['simulator_sha256'] != original['simulator_sha256'], 'physical variants share a simulator')

    for kind, prefix, expected in [('wide', 'XU_PE32_WRAPPER_PASS', (16, 27)),
                                    ('compat', 'XU_PE32_COMPAT_WRAPPER_PASS', (64, 99))]:
        text = (raw / 'host-final-direct-bank128' / kind / 'simulation.log').read_text().split('\n', 1)[1]
        matches = re.findall(prefix + r' rows=2 groups=(\d+) lanes=512 overlap=(\d+) launches=(\d+) dones=(\d+) accepted=(\d+) retired=(\d+)', text)
        require(len(matches) == 1, 'direct completion missing or duplicate: ' + kind)
        groups, overlap, launches, dones, accepted, retired = map(int, matches[0])
        require((groups, launches, dones) == (expected[0], expected[1], expected[1]) and
                overlap > 0 and accepted == retired, 'direct work/retirement differs: ' + kind)
        require(re.findall(r'XU_PE32_DIRECT_ACTIVITY physical_pes=32 mac_beats=(\d+) lane_macs=(\d+)', text) ==
                ([('1728', '53760')] if kind == 'wide' else [('6336', '50688')]), 'direct physical work differs')
        require(not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text), 'direct failure marker')
    bank = (raw / 'direct/bank-generated/simulation.log').read_text().split('\n', 1)[1]
    marker = 'XU_PE32_BANK128_PASS logical_words=512 depths=4 writes=520 reads=524 unknown_reads=4 selected_enable=1 latency=1'
    require(bank.count(marker) == 1 and not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', bank),
            'actual four-depth single-RW test incomplete')
    require(re.search(r'Ran 69 tests in [^\n]+\n\nOK \(skipped=2\)\s*$', (raw / 'host-final.log').read_text()),
            'host completion differs')
    require(re.search(r'Ran 42 tests in [^\n]+\n\nOK\s*$', (raw / 'numeric.log').read_text()), 'numeric completion differs')
    require('Tests: succeeded 1, failed 0' in (raw / 'chisel-bank.log').read_text() and
            'All tests passed.' in (raw / 'chisel-bank.log').read_text(), 'Chisel bank test incomplete')
    negative = (raw / 'missing-server-model-negative.log').read_text()
    require('FAILED (failures=1)' in negative and 'server bank128 wrapper acceptance requires' in negative,
            'mandatory vendor-model failure gate missing')
    legacy = load(raw / 'legacy5-bank128/result.json')
    require(legacy['status'] == 'PASS' and legacy['main_commit'] == identity['production_main'] and
            legacy['e203_commit'] == identity['child'] and legacy['accel_variant'] == 'pe32-bank128' and
            legacy['tests'] == ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x'],
            'actual legacy5 incomplete')
    for name in legacy['tests']:
        text = (raw / 'legacy5-bank128' / (name + '.log')).read_text()
        require('TEST_PASS' in text and 'XU_ACCEL_PE32=1' in text and 'XU_ACCEL_PE32_BANK128=1' in text and
                not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', text), 'legacy physical variant/completion differs')
    old = load(raw / 'original-generated-bytes.json')
    for path, digest in old['sha256'].items():
        data = subprocess.check_output(['git', 'show', old['original_child'] + ':' + path],
                                       cwd=root / 'third-party/e203_hbirdv2')
        require(hashlib.sha256(data).hexdigest() == digest == sha(root / 'third-party/e203_hbirdv2' / path),
                'original generated RTL differs: ' + path)
    mapped = set()
    for old_bank in range(8):
        for old_addr in range(2048):
            col, k = (old_addr >> 6) * 8 + old_bank, old_addr & 63
            bank, address = col & 31, ((col >> 5) << 6) | k
            mapped.add((bank, address >> 7, address & 127))
    require(len(mapped) == 16384 and mapped == {(b, d, a) for b in range(32) for d in range(4) for a in range(128)},
            'full legacy W address mapping is not bijective')
    result = dict(status='LOCAL_SCREEN_PASS_NOT_QUALIFIED', production_main=identity['production_main'],
        child=identity['child'], scope='local GCC14.2/Verilator5.032, one real layer00, historical HF4ns/LF66ns; not formal-clear/request or physical qualification',
        rows=[dict(variant=r['accel_variant'], cycles=r['layers'][0]['cycles'],
                   performance=r['layers'][0]['performance'], simulator_sha256=r['simulator_sha256'])
              for r in (compact, original)], cycle_difference=compact['layers'][0]['cycles']-original['layers'][0]['cycles'],
        common_identity=common, source_files=len(source_files), original_files=len(old['sha256']), raw_payloads=len(manifest),
        logical_w_bytes=32768, physical_w_bytes=32768, macro_geometry='32 banks x 4 depths x 128x16 single-RW',
        expected_full_soc_macros={'RAMSP128X16':128, 'RAMSP1024X16':320},
        host_tests=69, skipped_designated_model_tests=2, numeric_tests=42, chisel_bank_tests=1,
        independently_recomputed_outputs=2*25344, legacy_cases=5, retained=False,
        not_qualified=['actual designated SRAM model VCS', 'same-toolchain full12', 'mapped consistency',
                       'complete150MHz STA', 'same-library area', 'fullSoC task energy', 'retention'])
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'cycle_difference', 'raw_payloads', 'independently_recomputed_outputs')}))


if __name__ == '__main__':
    main()
