"""Make an independently hashed, window-only derivative of a sealed R15 VCD.

Does not run an EDA tool, update an original receipt, or replace the raw VCD.
Only launch after the original power controller has naturally exited.
"""
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
import argparse
import fcntl
import hashlib
import json
import os
import re
import socket
import subprocess
import time

R = Path(__file__).resolve().parent
EXPECTED_PHYSICAL = '2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220'
VARIANTS = ('tight-O2', 'phased_64_fast4-O2', 'backoff_8_256_fast4-O2')


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def heavy_jobs():
    result = []
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if p.stat().st_uid != os.getuid():
                continue
            comm = (p / 'comm').read_text().strip()
            if comm.startswith(('simv', 'pt_shell', 'dc_shell', 'fm_shell', 'vcs')):
                result.append((p.name, comm))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('variant', choices=VARIANTS)
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--windows-manifest', type=Path,
                        help='Independent continuation input manifest under the same official root')
    args = parser.parse_args()
    assert socket.gethostname().split('.')[0] == 'RDserver04'
    assert Path.home().name == 's4_23usr'
    assert str(R) == '/tmp/xu-b41-close-20261111-r1'
    if not args.launch:
        print('PREPARED_ONLY use --launch after original power terminal state')
        return
    assert not Path('/proc/299096').exists(), 'Original power controller is active; leave it running'
    with (R / 'eda.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not heavy_jobs(), 'Same-account heavy native process active'
        G = R / 'xu-gate-20261112-r1'
        binding_path = G / (args.variant + '-full12-r15') / 'verified-binding.json'
        binding_sha = sha(binding_path)
        binding = json.loads(binding_path.read_text())
        assert (binding['tasks'], binding['warmup'], binding['physical_clears']) == (12, 1, 13)
        assert binding['pins']['physical'] == EXPECTED_PHYSICAL
        review_path = R / 'xu-gate-independent-20261113-r2' / (args.variant + '.json')
        review = json.loads(review_path.read_text())
        assert review['status'] == 'PASS_INDEPENDENT_GATE_FULL12_REVIEW'
        assert review['binding_sha256'] == binding_sha
        log_path = G / (args.variant + '-full12-r15') / 'native.log'
        assert sha(log_path) == binding['native_log_sha256'] == review['native_log_sha256']
        original_windows = (args.windows_manifest or R / 'xu-power-20261112-r1/windows.json').resolve()
        assert R in original_windows.parents, 'Manifest is outside the independent official root'
        entries = json.loads(original_windows.read_text())
        matches = [e for e in entries if e['variant'] == args.variant]
        assert len(matches) == 1
        entry = matches[0]
        assert entry['gate_log_sha256'] == binding['native_log_sha256']
        raw = G / (args.variant + '-r15-fullsoc.vcd')
        assert str(raw) == entry['vcd'] and raw.stat().st_size == binding['vcd_bytes'] == entry['vcd_bytes']
        intervals = list(map(Decimal, entry['time_intervals_ns']))
        assert len(intervals) == 48 and all(a < b for a, b in zip(intervals, intervals[1:]))
        # Preserve extra context outside every true import interval, including
        # rounding at the fs/ns conversion and the one-cycle closing edge.
        pad_fs = 20000000
        ranges = []
        for a, b in zip(intervals[::2], intervals[1::2]):
            lo = int((a * 1000000).to_integral_value(rounding=ROUND_FLOOR)) - pad_fs
            hi = int((b * 1000000).to_integral_value(rounding=ROUND_CEILING)) + pad_fs
            assert 0 < lo < hi
            if ranges and lo <= ranges[-1][1] + 1:
                ranges[-1][1] = max(hi, ranges[-1][1])
            else:
                ranges.append([lo, hi])
        out = R / 'xu-windowed-vcd-20261113-r1' / args.variant
        out.mkdir(mode=0o700, parents=True)
        source = R / 'vcd_window_extract.cpp'
        binary = out / 'extract'
        compiler = subprocess.check_output(['g++', '--version'], universal_newlines=True).splitlines()[0]
        subprocess.check_call(['g++', '-std=c++11', '-O2', str(source), '-o', str(binary)])
        (out / 'ranges.fs.tsv').write_text(''.join(str(a) + '\t' + str(b) + '\n' for a, b in ranges))
        before = raw.stat()
        print('RAW_HASH_START', args.variant, before.st_size, flush=True)
        raw_sha = sha(raw)
        assert raw_sha == binding['vcd_sha256']
        print('EXTRACT_START', args.variant, 'ranges', len(ranges), flush=True)
        started = time.time()
        partial = out / 'activity.partial.vcd'
        command = ['timeout', '-k', '30s', '2400s', 'nice', '-n', '10', str(binary),
                   str(raw), str(out / 'ranges.fs.tsv'), str(partial)]
        with (out / 'extract.log').open('x') as f:
            result = subprocess.run(command, stdout=f, stderr=subprocess.STDOUT)
        log = (out / 'extract.log').read_text()
        assert result.returncode == 0 and log.startswith('WINDOW_VCD_EXTRACT_COMPLETE '), log
        fields = dict((k, int(v)) for k, v in re.findall(r'(\w+)=(\d+)', log))
        assert fields['signals'] == 187574, 'Signal inventory differs from the sealed executable preflight'
        assert fields['windows'] == len(ranges)
        assert 0 < fields['copied_changes'] <= fields['source_changes']
        after = raw.stat()
        assert (before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns)
        assert sha(binding_path) == binding_sha and sha(log_path) == entry['gate_log_sha256']
        output_sha = sha(partial)
        ready = out / 'activity.vcd'
        partial.rename(ready)
        receipt = {
            'status': 'WINDOW_VCD_EXTRACT_COMPLETE_NOT_POWER_ACCEPTED',
            'variant': args.variant, 'source': str(raw), 'source_bytes': before.st_size,
            'source_sha256': raw_sha, 'binding_sha256': binding_sha,
            'gate_independent_review_sha256': sha(review_path),
            'native_log_sha256': entry['gate_log_sha256'],
            'output': str(ready), 'output_bytes': ready.stat().st_size,
            'output_sha256': output_sha, 'time_intervals_ns': entry['time_intervals_ns'],
            'context_pad_fs': pad_fs, 'preserved_ranges_fs': ranges,
            'all_signal_declarations_preserved': True,
            'pre_interval_state_restored_outside_import_windows': True,
            'extract_command': command, 'extract_seconds': round(time.time() - started, 3),
            'extract_summary': log.strip(), 'compiler': compiler,
            'extract_counters': fields,
            'code_sha256': sha(source), 'binary_sha256': sha(binary),
            'wrapper_sha256': sha(Path(__file__)), 'extract_log_sha256': sha(out / 'extract.log'),
            'scope': 'Only listed import windows; synthetic context outside them is not an all-time trace.'
        }
        with (out / 'receipt.json').open('x') as f:
            json.dump(receipt, f, indent=2)
            f.write('\n')
        print('WINDOW_VCD_READY', args.variant, ready.stat().st_size, output_sha, flush=True)


if __name__ == '__main__':
    main()
