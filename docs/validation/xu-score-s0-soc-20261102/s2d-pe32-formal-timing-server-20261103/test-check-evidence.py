#!/usr/bin/env python3
"""xu: corruption and receipt-resigned semantic checks for this actual archive."""
import copy
import importlib.util
import json
import lzma
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('xu_fm22_check', HERE / 'check-evidence.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def main():
    original, manifest = check.load()
    check.analyze(original)
    rejections = []

    def reject(label, call, expected=None):
        try:
            call()
        except (ValueError, lzma.LZMAError) as exc:
            if expected is not None:
                assert expected in str(exc), (label, str(exc))
            rejections.append(label)
        else:
            raise AssertionError('accepted corruption: ' + label)

    # Storage identity and path handling, with byte-for-byte restoration after each test.
    with tempfile.TemporaryDirectory(prefix='xu-fm22-negative-') as directory:
        root = Path(directory) / 'archive'
        shutil.copytree(HERE, root, ignore=shutil.ignore_patterns('__pycache__'))
        for entry in manifest['selected_files'] + manifest['context_files']:
            path = root / entry['stored_path']
            data = path.read_bytes()
            path.write_bytes(data + b'\n')
            reject('stored-byte-corruption:' + entry['path'], lambda: check.load(root), 'stored raw bytes differ')
            path.write_bytes(data)
        mpath = root / 'selected-manifest.json'
        data = mpath.read_bytes()
        altered = copy.deepcopy(manifest)
        altered['selected_files'].append(altered['selected_files'][0])
        mpath.write_bytes(encode(altered))
        reject('duplicate-selected-entry', lambda: check.load(root), 'selected/context count differs')
        altered = copy.deepcopy(manifest)
        altered['selected_files'][0]['stored_path'] = '../escape'
        mpath.write_bytes(encode(altered))
        reject('path-escape', lambda: check.load(root), 'stored naming differs')
        mpath.write_bytes(data)
        path = root / manifest['selected_files'][0]['stored_path']
        data = path.read_bytes()
        path.unlink()
        path.symlink_to(HERE / manifest['selected_files'][0]['stored_path'])
        reject('symlink-payload', lambda: check.load(root), 'symlink in archive path')
        path.unlink()
        path.write_bytes(data)
        extra = root / 'raw/extra-unmanifested.txt'
        extra.write_text('unmanifested')
        reject('unmanifested-payload', lambda: check.load(root), 'unmanifested/missing raw file')
        extra.unlink()
        sm = root / 'source-export-manifest.json'
        data = sm.read_bytes()
        sm.write_bytes(data + b'\n')
        reject('original-manifest-corruption', lambda: check.load(root), 'original export manifest differs')
        sm.write_bytes(data)
        check.load(root)

    for tag, config in check.CASES.items():
        fm = config['fm']
        repair = config['repair']
        state_key = fm + '/state.json'
        repair_key = repair + '/state.json'

        def fm_state(label, mutate, reason):
            raw = dict(original)
            state = check.jload(raw[state_key])
            mutate(state)
            raw[state_key] = encode(state)
            reject(tag + ':' + label, lambda: check.analyze(raw), reason)

        fm_state('nonterminal-fm', lambda s: s.update(status='RUNNING'), 'FM terminal state differs')
        fm_state('failed-fm-exit', lambda s: s['runs'][0].update(returncode=1), 'FM execution differs')
        fm_state('changed-frozen-input', lambda s: next(iter(s['runs'][0]['frozen_after'].values())).update(sha256='0' * 64), 'FM frozen inputs differ')

        def fm_log(label, before, after, reason):
            raw = dict(original)
            key = fm + '/' + tag + '/fm.log'
            assert before in raw[key]
            raw[key] = raw[key].replace(before, after, 1)
            state = check.jload(raw[state_key])
            state['runs'][0]['log'].update(bytes=len(raw[key]), sha256=check.sha(raw[key]))
            raw[state_key] = encode(state)
            reject(tag + ':' + label, lambda: check.analyze(raw), reason)

        fm_log('missing-pass-marker', b'\nXU_FULL_SOC_FORMALITY_PASS\n', b'\nXU_FORMALITY_UNFINISHED\n', 'FM completion missing')
        fm_log('passing-count-mismatch', f"{config['passing'][-1]} Passing compare points".encode(), b'1 Passing compare points', 'FM completion missing')
        fm_log('undriven-assumption-omitted', b'verification_set_undriven_signals synthesis', b'verification_set_undriven_signals retained', 'conditional FM scope missing')
        fm_log('direct-undriven-unproven-hidden', b'verification_verify_directly_undriven_output false', b'verification_verify_directly_undriven_output omitted', 'conditional FM scope missing')
        fm_log('unread-count-mismatch', b'     511       0     511', b'     510       0     510', 'FM category totals differ')

        def repair_state(label, mutate, reason):
            raw = dict(original)
            state = check.jload(raw[repair_key])
            mutate(state)
            raw[repair_key] = encode(state)
            reject(tag + ':' + label, lambda: check.analyze(raw), reason)

        repair_state('claim-qualified-repair', lambda s: s.update(status='QUALIFIED'), 'repair terminal/netlist identity differs')
        repair_state('wrong-repair-net', lambda s: s.update(mapped_netlist_sha256=config['original']), 'repair terminal/netlist identity differs')
        repair_state('failed-pt-exit', lambda s: s['runs'][1].update(returncode=1), 'repair tool failed')
        repair_state('wrong-library-identity', lambda s: s['input_sha256'].update({next(k for k in s['input_sha256'] if k.endswith('xu-ramsp1024x16-ss-0p99v-125c.db')): '0' * 64}), 'recorded library identity differs')

        def report(label, filename, before, after, reason, script_index=None):
            raw = dict(original)
            key = repair + '/' + filename
            assert before in raw[key], label
            raw[key] = raw[key].replace(before, after, 1)
            state = check.jload(raw[repair_key])
            if script_index is None:
                state['reports'][filename] = dict(bytes=len(raw[key]), sha256=check.sha(raw[key]))
            else:
                state['runs'][script_index]['script_sha256'] = check.sha(raw[key])
            raw[repair_key] = encode(state)
            reject(tag + ':' + label, lambda: check.analyze(raw), reason)

        report('weaken-final-gating-constraint', 'sta.tcl', b'read_verilog mapped.v', b'read_verilog mapped.v\nset_clock_gating_check -hold 0 [all_clocks]', 'repair/final STA clock scope differs', 1)
        report('wrong-synthesis-margin', 'repair.tcl', b'set_clock_gating_check -hold 0.12', b'set_clock_gating_check -hold 0.01', 'repair/final STA clock scope differs', 0)
        report('hidden-untested-reason', 'analysis-coverage.rpt', b'untested  no_clock', b'untested  fake_reason', 'untested reasons differ')
        report('hidden-clockless-latch', 'check-timing.rpt', b'24 register clock pins with no clock', b'0 register clock pins with no clock', 'unconstrained UART/forwarded-clock scope omitted')
        report('hidden-dc-negative-timing', 'qor.rpt', config['dc_slack'].encode(), b'   0.00', 'negative DC forwarded GPIO timing omitted')
        report('missing-electrical-violation', 'constraints.rpt', b'min_capacitance', b'min_capacitance_omitted', 'electrical report block differs')
    print(json.dumps(dict(status='PASS', positive_actual_archive=True, rejected=len(rejections), cases=rejections), indent=2))


if __name__ == '__main__':
    main()
