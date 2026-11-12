#!/usr/bin/env python3
"""Check portable polling logic, screen explicit synthetic cases, build RV32 references."""
import argparse
import csv
from hashlib import sha256
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NOP_VALUES = (0, 8, 16, 32, 64, 128, 256, 512, 1024)
POLICIES = ('FFN_POLL_TIGHT', 'FFN_POLL_FIXED', 'FFN_POLL_PHASED', 'FFN_POLL_BACKOFF')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def run(command, log, *, input_text=None, timeout=30, allowed=(0,)):
    proc = subprocess.run([str(x) for x in command], input=input_text, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    log.write_text(proc.stdout)
    if proc.returncode not in allowed:
        raise RuntimeError(f'Command exited {proc.returncode}; see {log}')
    return proc


def configs():
    rows = [dict(name='tight', policy=0, initial_nops=0, max_nops=0, fast_reads=0)]
    rows += [dict(name=f'fixed_{n}', policy=1, initial_nops=n, max_nops=n, fast_reads=0)
             for n in NOP_VALUES[1:]]
    rows += [dict(name=f'phased_{n}_fast{fast}', policy=2, initial_nops=n, max_nops=n, fast_reads=fast)
             for n, fast in ((64, 4), (256, 8), (1024, 8))]
    rows += [dict(name=f'backoff_{initial}_{maximum}_fast{fast}', policy=3,
                  initial_nops=initial, max_nops=maximum, fast_reads=fast)
             for initial, maximum, fast in ((8, 64, 4), (8, 256, 4), (16, 1024, 8))]
    for row in rows:
        row.update(budget_cycles=1000000, poll_limit=1000000)
        validate_config(row)
    return rows


def validate_config(row):
    if not isinstance(row['name'], str) or not re.fullmatch('[a-z0-9_]+', row['name']):
        raise ValueError('Invalid config name')
    fields = ('policy', 'initial_nops', 'max_nops', 'fast_reads', 'budget_cycles', 'poll_limit')
    if any(type(row[key]) is not int for key in fields):
        raise ValueError('Config fields must be integer values')
    if not (0 <= row['policy'] < 4 and 0 < row['budget_cycles'] < 2**31 and
            0 < row['poll_limit'] <= 1000000 and 0 <= row['fast_reads'] < row['poll_limit']):
        raise ValueError('Invalid policy, budget or polling bound')
    if row['initial_nops'] not in NOP_VALUES or row['max_nops'] not in NOP_VALUES:
        raise ValueError('RV32 adapter does not implement this NOP count')
    if row['policy'] == 0:
        if row['initial_nops'] or row['max_nops'] or row['fast_reads']:
            raise ValueError('Tight polling cannot pause')
    elif not (0 < row['initial_nops'] <= row['max_nops']):
        raise ValueError('Pause bounds are invalid')
    elif row['policy'] in (1, 2) and row['initial_nops'] != row['max_nops']:
        raise ValueError('Only backoff varies its pause length')


def header(row):
    validate_config(row)
    return ('/* REFERENCE BUILD ONLY. Synthetic screening does not select a 64-PE config. */\n'
            f'#define FFN_MAX_PAUSE_NOPS {row["max_nops"]}\n'
            '#define FFN_CLEAR_CONFIG {1000000u, 1000000u, 0u, 0u, 0u, FFN_POLL_TIGHT}\n'
            f'#define FFN_COMPUTE_CONFIG {{{row["budget_cycles"]}u, {row["poll_limit"]}u, {row["initial_nops"]}u, '
            f'{row["max_nops"]}u, {row["fast_reads"]}u, {POLICIES[row["policy"]]}}}\n')


def check_host(out, cc):
    binary = out/'wait_model'
    base = [cc, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror']
    source = ROOT/'tests/wait_model.c'
    run([*base, '-I', ROOT/'software', source, '-o', binary], out/'host-build.log')
    positive = run([binary], out/'contracts.log')
    match = re.fullmatch(r'CONTRACT_PASS cases=(\d+) policies=4\n', positive.stdout)
    if not match or int(match[1]) != 72:
        raise ValueError('Incomplete actual-C contract coverage')
    mutations = {
        'ignore_busy': (' && !(status & FFN_BUSY)', ''),
        'ignore_error_when_done': ('if (status & FFN_ERROR)', 'if ((status & FFN_ERROR) && !(status & FFN_DONE))'),
        'accept_late_done': ('if (elapsed >= config->budget_cycles)', 'if (elapsed >= config->budget_cycles && !(status & wanted))')
    }
    original = (ROOT/'software/ffn_wait.h').read_text()
    negatives = {}
    for name, (before, after) in mutations.items():
        folder = out/name
        folder.mkdir()
        if original.count(before) != 1:
            raise ValueError(f'Negative control anchor changed: {name}')
        mutated = folder/'ffn_wait.h'
        mutated.write_text(original.replace(before, after, 1))
        target = folder/'wait_model'
        run([*base, '-I', folder, source, '-o', target], folder/'build.log')
        proc = run([target], folder/'contracts.log', allowed=(1,))
        if 'CONTRACT_FAIL ' not in proc.stdout:
            raise ValueError(f'Negative control was not detected: {name}')
        negatives[name] = dict(native_exit=proc.returncode, output=proc.stdout, source_sha256=sha(mutated))
    return binary, dict(status='PASS', cases=int(match[1]), negative_controls=negatives,
                        binary_sha256=sha(binary),
                        scope='Actual ffn_wait C logic with controlled status/clock/pause/error adapters')


def screen(out, binary, rows):
    durations = (0, 1, 8, 64, 255, 256, 257, 1024, 4096, 8192, 32768, 65536, 131072)
    costs = list(itertools.product((4, 16, 64), (1, 4), (1, 2)))
    inputs, labels = [], []
    for row in rows:
        for completion, (status_cost, cycle_cost, nop_cost) in itertools.product(durations, costs):
            inputs.append(' '.join(str(x) for x in (row['policy'], row['initial_nops'], row['max_nops'],
                          row['fast_reads'], row['budget_cycles'], row['poll_limit'], completion,
                          status_cost, cycle_cost, nop_cost)))
            labels.append((row, completion, status_cost, cycle_cost, nop_cost))
    proc = run([binary, '--screen'], out/'model-native.log', input_text='\n'.join(inputs)+'\n', timeout=60)
    lines = proc.stdout.splitlines()
    if len(lines) != len(labels):
        raise ValueError('Incomplete synthetic comparison')
    observations = []
    for line, (row, completion, status_cost, cycle_cost, nop_cost) in zip(lines, labels):
        code, time, reads, clocks, nops, max_pause = map(int, line.split())
        if code != 0 or time < completion or max_pause > row['max_nops']:
            raise ValueError('A modeled task failed or exceeded configured pause bounds')
        observations.append(dict(config=row['name'], completion_at_model_ticks=completion,
                                 status_cost=status_cost, cycle_cost=cycle_cost, nop_cost=nop_cost,
                                 observation_at_model_ticks=time, detection_delay_model_ticks=time-completion,
                                 status_reads=reads, clock_reads=clocks, paused_nops=nops, max_pause=max_pause))
    with (out/'model-observations.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(observations[0]))
        writer.writeheader()
        writer.writerows(observations)
    aggregates = []
    for row in rows:
        samples = [x for x in observations if x['config'] == row['name']]
        aggregates.append(dict(config=row['name'], config_values=row, cases=len(samples),
                               total_status_reads=sum(x['status_reads'] for x in samples),
                               total_clock_reads=sum(x['clock_reads'] for x in samples),
                               total_detection_delay_model_ticks=sum(x['detection_delay_model_ticks'] for x in samples),
                               max_detection_delay_model_ticks=max(x['detection_delay_model_ticks'] for x in samples)))
    objectives = ('total_status_reads', 'total_clock_reads', 'total_detection_delay_model_ticks',
                  'max_detection_delay_model_ticks')
    front = [a['config'] for a in aggregates if not any(
        all(b[k] <= a[k] for k in objectives) and any(b[k] < a[k] for k in objectives)
        for b in aggregates if b is not a)]
    return dict(status='PASS_SYNTHETIC_CONTROL_SCREEN', cases=len(observations),
                configurations=len(rows), aggregates=aggregates, proxy_front=front,
                production_selected_config=None, hardware_pe_count_verified=None,
                model=dict(evidence_kind='synthetic_adapter_operation_model', durations=durations,
                           status_read_costs=(4, 16, 64), clock_read_costs=(1, 4), per_nop_costs=(1, 2),
                           clock_units='model ticks, not measured CPU cycles',
                           convention='Status sampled after its modeled read cost; clock read also costs ticks',
                           omissions=['C branch and arithmetic instructions', 'real CPU pipeline and fetch',
                                      'MMIO interconnect waveform', 'SRAM activity', 'physical power']),
                scope='Uniform illustrative grid, not the official task distribution or a 64-PE benchmark')


def build_rv32(out, prefix, rows):
    source_firmware = ROOT/'software/reference_firmware'
    firmware = out/'startup'
    firmware.mkdir()
    for name in ('start.S', 'link.ld'):
        shutil.copyfile(source_firmware/name, firmware/name)
    compiler = run([prefix+'gcc', '--version'], out/'cross-version.log').stdout
    results = []
    for row in rows:
        for optimization in ('O2', 'O3', 'Os'):
            folder = out/f'{row["name"]}-{optimization}'
            folder.mkdir()
            (folder/'selected_config.h').write_text(header(row))
            binary = folder/'reference_soc'
            command = [prefix+'gcc', '-march=rv32imac_zicsr2p0_zifencei2p0', '-mabi=ilp32',
                       '-'+optimization, '-fstack-usage', '-ffreestanding', '-fno-builtin',
                       '-msmall-data-limit=0', '-nostdlib', '-nostartfiles', '-static', '-mcmodel=medany',
                       '-Wl,--no-relax', '-Wl,--build-id=none', '-Wall', '-Wextra', '-Werror',
                       '-I', folder, '-I', ROOT/'software', '-T', firmware/'link.ld',
                       firmware/'start.S', ROOT/'software/reference_driver.c', '-o', binary]
            run(command, folder/'build.log')
            dump = run([prefix+'objdump', '-d', binary], folder/'disassembly.log').stdout
            if not re.search(r'80000086\s+<write_tohost>', dump):
                raise ValueError('Reference completion symbol moved')
            if re.search(r'\bwfi\b', dump) or len(re.findall(r'\bfence\b', dump)) < 4:
                raise ValueError('Reference fence or WFI contract changed')
            size = run([prefix+'size', binary], folder/'size.log').stdout.splitlines()[-1].split()
            text_size, data_size, bss_size = map(int, size[:3])
            if data_size or bss_size or text_size >= 65536:
                raise ValueError('Reference startup/memory geometry is unsupported')
            run([prefix+'objcopy', '-O', 'verilog', binary, folder/'reference_soc.verilog'], folder/'objcopy.log')
            image = folder/'reference_soc.verilog'
            image.write_text(image.read_text().replace('@800', '@000'))
            stack = {f.name:f.read_text() for f in folder.glob('*.su')}
            results.append(dict(config=row['name'], optimization=optimization, text_bytes=text_size,
                                data_bytes=data_size, bss_bytes=bss_size, stack_usage=stack,
                                elf_sha256=sha(binary), image_sha256=sha(image),
                                selected_config_sha256=sha(folder/'selected_config.h'),
                                disassembly_sha256=sha(folder/'disassembly.log'), command=[str(x) for x in command]))
    return dict(status='PASS_REFERENCE_RV32_BUILD_ONLY', compiler=compiler, builds=results,
                startup_sha256={f.name:sha(f) for f in firmware.iterdir()},
                scope='Historical Group-y ABI reference; no CPU execution, RTL, gate-level, activity or 64-PE qualification')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--cross-prefix', default='/tmp/xu-riscv-toolchain/bin/riscv-none-elf-')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='RUNNING', evidence_scope='Portable software development only; no verified 64-PE hardware yet')
    sources = [*(p for p in sorted((ROOT/'software').rglob('*')) if p.is_file()),
               *sorted((ROOT/'tests').glob('*.c')), Path(__file__).resolve()]
    record['source_sha256'] = {str(p.relative_to(ROOT)):sha(p) for p in sources}
    save(out/'result.json', record)
    try:
        rows = configs()
        host = out/'host'
        host.mkdir()
        print('PORTABLE_HOST_CONTRACTS_START', flush=True)
        binary, contracts = check_host(host, args.cc)
        record['contracts'] = contracts
        print('PORTABLE_HOST_CONTRACTS_PASS', contracts['cases'], flush=True)
        model = out/'model'
        model.mkdir()
        print('PORTABLE_SYNTHETIC_SCREEN_START', len(rows), flush=True)
        screen_result = screen(model, binary, rows)
        save(model/'result.json', screen_result)
        record['screen_sha256'] = sha(model/'result.json')
        print('PORTABLE_SYNTHETIC_SCREEN_PASS', screen_result['cases'], flush=True)
        cross = out/'cross'
        cross.mkdir()
        print('PORTABLE_RV32_BUILD_START', len(rows)*3, flush=True)
        cross_result = build_rv32(cross, args.cross_prefix, rows)
        save(cross/'result.json', cross_result)
        record['cross_sha256'] = sha(cross/'result.json')
        if any(sha(ROOT/name) != digest for name,digest in record['source_sha256'].items()):
            raise ValueError('Source changed during validation')
        record.update(status='PASS_PORTABLE_SOFTWARE_DEVELOPMENT', actual_64pe_qualified=False,
                      production_selected_config=None)
        print('PORTABLE_RV32_BUILD_PASS', len(cross_result['builds']), flush=True)
    except Exception as error:
        record.update(status='FAIL', error=str(error))
        raise
    finally:
        save(out/'result.json', record)
    print('PORTABLE_DEVELOPMENT_END', record['status'], flush=True)


if __name__ == '__main__':
    main()
