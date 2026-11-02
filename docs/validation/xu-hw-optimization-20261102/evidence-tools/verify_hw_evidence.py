#!/usr/bin/env python3
"""Independently audit transferred xu H1/H2 evidence using only the standard library.

No runtime modules, campaign decision functions, simulator, build or installation
commands are imported or executed. Complete logs and extracted lines are distinct
evidence classes. Missing complete logs cannot be screened locally for other errors.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

BASE = '499ba54bd57db81c058ab5efe25def226ec6dd15'
OLD_RESULT = 'docs/validation/xu-fw-optimization-20261102/server-json/acceptance/real12/result.json'
OLD_CAMPAIGN = 'docs/validation/xu-fw-optimization-20261102/server-json/experiments.json'
PHASES = ['w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other']
COUNTERS = PHASES + ['busy', 'mac_fire', 'mmio_reads', 'mmio_writes', 'shared_reads',
                     'shared_writes', 'shared_stall', 'mmio_stall', 'starts', 'dones']
FIELDS = ['layer', 'cycles'] + COUNTERS
STEPS = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']
BASE_TESTS = ['rv32ui-p-add', 'accel_mmio', 'accel_compute', 'accel_multigroup', 'accel_repeat_x']
RUNTIME_PATHS = ['src', 'tests/e203', 'tools/scripts', 'project.scala', 'tools/model/export_kwt.py', 'model']
MODES = {'B0-new-RTL': 'bias-dtcm', 'H1-bias-cache': 'bias-hw',
         'H2-result-window': 'bias-dtcm-window', 'H1H2-combined': 'bias-hw-window'}
FIXED_PATHS = ['tests/e203/vectors', 'model', 'tools/model/export_kwt.py',
               'tests/e203/firmware/main.c', 'tests/e203/firmware/start.S', 'tests/e203/firmware/link.ld']
FAILED_LOG = re.compile(r'FATAL|TEST_FAIL|%Error|Time Out|timeout', re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify_archive_binding(archive_path, directory):
    """Bind every archived original/derived byte stream to the audit input tree."""
    checked = set()
    with tarfile.open(str(archive_path)) as archive:
        for member in archive.getmembers():
            name = safe_relative(member.name).as_posix()
            require(member.isfile() and member.size <= 64 * 1024 * 1024 and name not in checked,
                    'unsafe or duplicate result archive member: ' + name)
            stream = archive.extractfile(member)
            require(stream is not None, 'unreadable result archive member: ' + name)
            data = stream.read()
            path = directory / name
            require(path.is_file() and path.stat().st_size == len(data) and
                    sha(path) == hashlib.sha256(data).hexdigest(), 'archive/input byte binding differs: ' + name)
            checked.add(name)
    require(bool(checked), 'result archive is empty')
    return dict(sha256=sha(archive_path), files_bound_to_input=len(checked), bytes_scope='all archive member bytes match audit input tree')


def safe_relative(name):
    path = Path(name)
    require(not path.is_absolute() and '..' not in path.parts, 'unsafe evidence path: ' + name)
    return path


def git_blob(repo, revision, name):
    safe_relative(name)
    return subprocess.check_output(['git', 'show', revision + ':' + name], cwd=str(repo))


def configuration(schedule):
    return dict(schedule=schedule, optimization='-O2', experiment='both-unroll-no-masks')


def record_configuration(record):
    return dict(schedule=record['firmware_schedule'], optimization=record['firmware_opt'],
                experiment=record['firmware_experiment'])


def work(schedule):
    require(schedule in MODES.values(), 'unknown hardware schedule: ' + str(schedule))
    cache = schedule.startswith('bias-hw')
    window = schedule.endswith('-window')
    # 32774 W + 12672 X + 9504 GROUP/W1C/START + bias + result-index writes.
    bias = 3 * 256 if cache else 99 * 32 * 8 * 3
    writes = 32774 + 12672 + 9504 + bias + (2 if cache else 0) + (0 if window else 99 * 256)
    return dict(w_shared_reads=16384, x_shared_reads=6336, bias_shared_reads=512,
                shared_reads=23232, shared_writes=50688, bias_mmio_writes=bias,
                mmio_writes=writes, starts=3168, dones=3168, mac_fire=202752,
                macs=1622016, outputs=25344)


def totals(result):
    return dict(cycles=sum(row['cycles'] for row in result['layers']),
                counters={key: sum(row['performance'][key] for row in result['layers']) for key in COUNTERS})


def layer_comparison(result, reference):
    require(len(result['layers']) == len(reference['layers']) == 12, 'comparison requires all twelve layers')
    return [dict(layer=a['layer'], cycles=a['cycles'], firmware_cycles=a['firmware_cycles'],
                 reference_cycles=b['cycles'], reference_firmware_cycles=b['firmware_cycles'],
                 delta_cycles=a['cycles'] - b['cycles'],
                 delta_firmware_cycles=a['firmware_cycles'] - b['firmware_cycles'])
            for a, b in zip(result['layers'], reference['layers'])]


class Audit:
    def __init__(self, directory, receipt_path, repo, extra_source_archive=None):
        self.directory, self.receipt_path, self.repo = directory, receipt_path, repo
        self.extra_source_archive = extra_source_archive
        self.sources = {}
        self.results = {}
        self.log_checks = []
        self.artifact_checks = []
        self.simulations = []
        self.vector_pool = {}
        self.source_files_checked = set()
        self.git_cache = {}
        self.transferred = read(directory / 'xu-transfer-manifest.json')
        self.campaign = read(directory / 'experiments.json')
        self.accepted = read(directory / 'acceptance/acceptance.json')
        self.receipt = read(receipt_path)
        self.extracted = {}
        for name in ['xu-simulation-pass-lines-derived.json', 'xu-selected-validation-log-lines.json']:
            path = directory / name
            if path.is_file():
                data = read(path)
                require('NOT original' in data.get('evidence_kind', '') or
                        'not original' in data.get('evidence_kind', '').lower() or
                        data.get('evidence_kind', '') in [
                            'selected exact lines only; full original logs remain on server',
                            'selected exact lines only; full-log bytes transferred only if in manifest'],
                        'log excerpt is not explicitly classified as derived: ' + name)
                for key, value in data.get('logs', {}).items():
                    if key in self.extracted:
                        previous = self.extracted[key]
                        require(previous.get('sha256') == value.get('sha256') and
                                previous.get('bytes') == value.get('bytes'), 'conflicting full-original log identity: ' + key)
                        require(previous.get('selected_exact_lines') == value.get('selected_exact_lines') or
                                not previous.get('selected_exact_lines') or not value.get('selected_exact_lines'),
                                'conflicting nonempty log excerpt: ' + key)
                        if not value.get('selected_exact_lines'):
                            continue
                    self.extracted[key] = value

    def blob_sha(self, revision, name, submodule=False):
        key = (revision, name, submodule)
        if key not in self.git_cache:
            repo = self.repo / 'third-party/e203_hbirdv2' if submodule else self.repo
            self.git_cache[key] = hashlib.sha256(git_blob(repo, revision, name)).hexdigest()
        return self.git_cache[key]

    def original(self, name):
        safe_relative(name)
        identity = self.transferred['files'].get(name)
        require(identity is not None, 'original file is not in transfer manifest: ' + name)
        path = self.directory / name
        require(path.is_file() and sha(path) == identity['sha256'] and path.stat().st_size == identity['bytes'],
                'transferred original bytes/hash mismatch: ' + name)
        self.sources[name] = identity
        return read(path)

    def log(self, name, digest, required_lines=False):
        """Return original text or explicitly derived selected lines, with distinct scope."""
        safe_relative(name)
        path = self.directory / name
        if path.is_file():
            require(sha(path) == digest, 'complete original log hash mismatch: ' + name)
            text = path.read_text(errors='replace')
            self.log_checks.append(dict(path=name, sha256=digest, bytes=path.stat().st_size,
                                        scope='complete original bytes; locally checked'))
            return text, True
        selected = self.extracted.get(name)
        if selected is not None:
            require(selected.get('sha256') == digest, 'excerpt full-original identity mismatch: ' + name)
            lines = selected.get('selected_exact_lines')
            require(isinstance(lines, list) and all(isinstance(line, str) for line in lines),
                    'malformed selected lines: ' + name)
            if not lines:
                self.log_checks.append(dict(path=name, sha256=digest, bytes=selected.get('bytes'),
                    scope='empty derived extract; full original remains on server; identity crosschecked to source receipt'))
                require(not required_lines, 'required numerical/validation lines unavailable: ' + name)
                return None, False
            self.log_checks.append(dict(path=name, sha256=digest, bytes=selected.get('bytes'),
                                        scope='derived selected exact lines; other original text unavailable locally'))
            return '\n'.join(lines) + '\n', False
        self.log_checks.append(dict(path=name, sha256=digest,
                                    scope='full original remains on server; identity crosschecked to source receipt'))
        require(not required_lines, 'required numerical/validation lines unavailable: ' + name)
        return None, False

    def receipt_case(self, record, receipt_record):
        require(record.get('status') == receipt_record.get('status'), 'receipt/result status differs')
        directory = Path(receipt_record['output']).as_posix()
        result_name = directory + '/result.json'
        if Path(directory).is_absolute():
            candidates = [name for name in self.transferred['files'] if name.endswith('/result.json') and
                          directory.endswith('/' + str(Path(name).parent))]
            require(len(candidates) == 1, 'ambiguous absolute receipt case directory')
            result_name = candidates[0]
        require(receipt_record.get('result_sha256') == sha(self.directory / result_name),
                'receipt original result hash differs: ' + result_name)
        require(receipt_record.get('log_sha256', {}) == record.get('log_sha256', {}),
                'receipt original log identities differ: ' + result_name)
        require(receipt_record.get('configuration') == record_configuration(record),
                'receipt original firmware configuration differs: ' + result_name)
        built = record.get('firmware_build')
        if built:
            pool = self.receipt['pools']['builds'][receipt_record['build_pool']]
            require(pool['configuration'] == built['configuration'] and pool['elf_sha256'] == built['elf_sha256'] and
                    pool['image_sha256'] == built['image_sha256'], 'receipt build identities differ: ' + result_name)
            require(self.receipt['pools']['firmware_sources'][pool['source_pool']] == built['source_sha256'],
                    'receipt firmware source pool differs: ' + result_name)
            require(self.receipt['pools']['memory'][pool['memory_pool']] == built['memory'],
                    'receipt static memory pool differs: ' + result_name)
        if record.get('mode') in ['real', 'synthetic'] and record.get('status') == 'PASS':
            expanded = []
            for group in receipt_record['layers']:
                for layer in group['layers']:
                    expanded.append(dict(layer=layer, cycles=group['cycles'], firmware_cycles=group['firmware_cycles'],
                                         performance=group['performance']))
            require(sorted(expanded, key=lambda row: row['layer']) == record['layers'],
                    'receipt grouped layers differ: ' + result_name)

    def validate_sources(self, result):
        origin = self.campaign['source']
        require(result['main_commit'] == origin['commit'] and result['e203_commit'] == origin['e203_commit'],
                'main/submodule runtime revisions changed')
        snapshot = origin['source_sha256']
        expected_rtl = {name for name in snapshot if name.startswith('third-party/e203_hbirdv2/rtl/e203/') and
                        Path(name).suffix in ['.v', '.sv']}
        expected_rtl.add('tests/e203/tb_accel_soc.sv')
        translated = {name.replace('/vsim/install/rtl/', '/rtl/e203/'): digest
                      for name, digest in result['source_sha256'].items()}
        require(set(translated) == expected_rtl, 'installed RTL/TB inventory differs from source snapshot')
        for name, digest in translated.items():
            require(snapshot.get(name) == digest, 'installed RTL/TB differs from snapshot: ' + name)
        fw = {Path(name).name: digest for name, digest in snapshot.items() if name.startswith('tests/e203/firmware/')}
        require(result['firmware_sha256'] == result['firmware_build']['source_sha256'] == fw,
                'compiled firmware source differs from immutable snapshot')
        require(result['runner_sha256'] == snapshot['tools/scripts/e203_soc.py'] and
                result['contract_sha256'] == snapshot['tools/scripts/xu_firmware_contract.py'],
                'measurement runner/contract source mismatch')
        environment = self.campaign['environment']
        for key in ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256', 'contract_sha256',
                    'versions', 'simulator_sha256']:
            require(result[key] == environment[key], 'runtime environment changed: ' + key)
        require({key: value['path'] for key, value in environment['tool_sha256'].items()} == result['tools'],
                'runtime executable paths differ from recorded tool hashes')
        return dict(main_commit=result['main_commit'], e203_commit=result['e203_commit'],
                    rtl_files=len(expected_rtl) - 1, rtl_tb_files=len(expected_rtl))

    def passing_simulation(self, name, record):
        require(record['simulator'] == self.campaign['simulator'], 'simulator backend changed: ' + name)
        config = record_configuration(record)
        require(config == configuration(config['schedule']) == record['firmware_build']['configuration'],
                'compiler optimization or independent hardware mode differs: ' + name)
        expected_work = work(config['schedule'])
        require(record['transaction_contract'] == expected_work, 'declared transaction contract differs: ' + name)
        tasks = record['tasks']
        require(type(tasks) is int and 1 <= tasks <= 12, 'invalid task count: ' + name)
        require(record['outputs'] == tasks * 25344 and record['write_words'] == tasks * 50688,
                'incomplete numerical output/writeback: ' + name)
        require([row['layer'] for row in record['layers']] == list(range(tasks)), 'unordered/duplicate/missing layers: ' + name)
        for row in record['layers']:
            counts, cycles = row['performance'], row['cycles']
            require(type(cycles) is int and cycles > 0 and set(counts) == set(COUNTERS), 'invalid counters: ' + name)
            require(type(row['firmware_cycles']) is int and row['firmware_cycles'] >= cycles,
                    'invalid firmware mcycle window: ' + name)
            require(all(type(value) is int and 0 <= value <= cycles for value in counts.values()), 'counter outside window: ' + name)
            require(sum(counts[key] for key in PHASES) == cycles, 'six phases do not cover window: ' + name)
            for key in ['shared_reads', 'shared_writes', 'mmio_writes', 'starts', 'dones', 'mac_fire']:
                require(counts[key] == expected_work[key], 'incorrect fixed work/transaction ' + key + ': ' + name)
            require(counts['busy'] == 215424 and counts['compute_wait'] == 218592,
                    'unchanged MAC pipeline activity/compute window differs: ' + name)
            require(counts['mmio_reads'] >= 50688 + 3168, 'result reads/status polls missing: ' + name)
        log_name = name + '/simulation.log'
        digest = record['log_sha256']['simulation.log']
        text, complete = self.log(log_name, digest, required_lines=True)
        require(not FAILED_LOG.search(text), 'failure marker in ' + ('complete log: ' if complete else 'available excerpt: ') + name)
        task_pattern = r'^TASK_PASS layer=(\d+) outputs=25344 writes=50688 cycles=(\d+) firmware_cycles=(\d+)$'
        found = re.findall(task_pattern, text, re.M)
        require(len(found) == len(re.findall(r'^TASK_PASS\b', text, re.M)) == tasks, 'malformed TASK_PASS lines: ' + name)
        require([(int(a), int(b), int(c)) for a, b, c in found] ==
                [(row['layer'], row['cycles'], row['firmware_cycles']) for row in record['layers']],
                'TASK_PASS differs from original JSON: ' + name)
        perf_pattern = r'^PERF_TASK ' + ' '.join(key + r'=(\d+)' for key in FIELDS) + r'$'
        found = re.findall(perf_pattern, text, re.M)
        require(len(found) == len(re.findall(r'^PERF_TASK\b', text, re.M)) == tasks, 'malformed PERF_TASK lines: ' + name)
        for fields, row in zip(found, record['layers']):
            require(dict(zip(FIELDS, map(int, fields))) == dict(row['performance'], layer=row['layer'], cycles=row['cycles']),
                    'PERF_TASK differs from original JSON: ' + name)
        require(re.findall(r'^SOC_PASS.*$', text, re.M) ==
                ['SOC_PASS tasks={} outputs={} writes={}'.format(tasks, tasks * 25344, tasks * 50688)],
                'incomplete SOC_PASS: ' + name)
        for log, value in record['log_sha256'].items():
            require(re.fullmatch(r'[0-9a-f]{64}', value) is not None, 'invalid full log SHA256: ' + name)
            if log != 'simulation.log':
                self.log(name + '/' + log, value)
        self.validate_sources(record)
        expected_names = {'layer_{:02d}/{}.mem'.format(i, key) for i in range(tasks) for key in ['x', 'w', 'bias', 'y']}
        require(set(record['vectors']) == expected_names, 'vector hash inventory incomplete: ' + name)
        pool = self.vector_pool.setdefault(record['mode'], {})
        for vector, digest in record['vectors'].items():
            require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None, 'invalid vector hash')
            require(vector not in pool or pool[vector] == digest, 'vectors changed between independent cases')
            pool[vector] = digest
            if record['mode'] == 'real':
                require(self.fixture['files'].get(vector) == digest, 'real fixture identity changed: ' + vector)
            path = self.directory / name / 'vectors' / vector
            if path.is_file(): require(sha(path) == digest, 'available vector bytes/hash mismatch')
        built = record['firmware_build']
        build_original = name + '/firmware-build.json'
        if build_original in self.transferred['files']:
            require(self.original(build_original) == built, 'separate original firmware build metadata differs: ' + name)
        command = built['command']
        require([arg for arg in command if re.fullmatch(r'-O\S+', arg)] == ['-O2'], 'unexpected compiler optimization options')
        require([arg for arg in command if arg.startswith('-march=')] == ['-march=rv32imac_zicsr2p0_zifencei2p0'] and
                [arg for arg in command if arg.startswith('-mabi=')] == ['-mabi=ilp32'],
                'RV32 instruction set/ABI compiler options differ')
        definitions = {'XU_FIRMWARE_BIAS_DTCM': config['schedule'].startswith('bias-dtcm'),
                       'XU_HARDWARE_BIAS_CACHE': config['schedule'].startswith('bias-hw'),
                       'XU_HARDWARE_RESULT_WINDOW': config['schedule'].endswith('-window'),
                       'XU_FIRMWARE_BIAS_UNROLL': True, 'XU_FIRMWARE_RESULT_UNROLL': True,
                       'XU_FIRMWARE_NO_MASKS': True}
        for define, value in definitions.items():
            require([arg for arg in command if arg.startswith('-D' + define + '=')] ==
                    ['-D{}={}'.format(define, int(value))], 'missing/duplicate independent compiler mode: ' + define)
        for key, filename in [('elf', 'accel_soc'), ('image', 'accel_soc.verilog')]:
            digest = built[key + '_sha256']
            require(re.fullmatch(r'[0-9a-f]{64}', digest) is not None and record['firmware_' + key + '_sha256'] == digest,
                    'firmware artifact hash metadata differs: ' + name)
            path = self.directory / name / filename
            if path.is_file(): require(sha(path) == digest, 'firmware artifact original bytes differ: ' + name)
            self.artifact_checks.append(dict(case=name, artifact=key, sha256=digest,
                scope='original bytes locally checked' if path.is_file() else 'hash crosschecked to source receipt; bytes remain on server'))
        memory = built['memory']
        frames = {frame['source'].rsplit(':', 1)[-1]: frame['bytes'] for frame in memory['stack_frames']}
        require(memory['data_bytes'] == 0 and memory['itcm_bytes'] <= 65536 and
                memory['bss_bytes'] == (2048 if config['schedule'].startswith('bias-dtcm') else 0),
                'firmware memory contract differs: ' + name)
        require(set(frames) == {'main', 'accel_linear'} and
                all(frame['kind'] == 'static' for frame in memory['stack_frames']) and
                sum(frames.values()) < memory['stack_capacity_after_bss_bytes'], 'static stack budget invalid: ' + name)
        self.simulations.append(dict(case=name, mode=record['mode'], tasks=tasks, cycles=totals(record)['cycles'],
                                     result_sha256=sha(self.directory / name / 'result.json'),
                                     original_log_sha256=record['log_sha256']['simulation.log'],
                                     complete_log_locally_checked=complete))

    def extra_interface(self):
        """Verify separately recorded supplemental checks, never merge into campaign acceptance."""
        require(self.extra_source_archive is not None, 'supplemental interface source archive is required')
        members = {}
        with tarfile.open(str(self.extra_source_archive)) as archive:
            for member in archive.getmembers():
                safe_relative(member.name)
                require(member.isfile() and member.size <= 1024 * 1024 and member.name not in members,
                        'unsafe supplemental source archive member')
                stream = archive.extractfile(member)
                require(stream is not None, 'unreadable supplemental source member')
                members[member.name] = stream.read()
        prefix = 'xu-hw-extra-interface/'
        require(all(name.startswith(prefix) for name in members), 'unexpected supplemental archive root')
        files = {name[len(prefix):]: data for name, data in members.items()}
        expected_names = {'README.md', 'run.py', 'base-tb_xu_cached_wrapper.sv', 'tb_xu_cached_wrapper_extra.sv',
                          'supplement.patch', 'manifest.json', 'local-iverilog/commands.json',
                          'local-iverilog/compile.log', 'local-iverilog/simulation.log', 'SHA256SUMS'}
        require(set(files) == expected_names, 'supplemental source archive inventory differs')
        for line in files['SHA256SUMS'].decode().splitlines():
            digest, name = line.split(None, 1)
            safe_relative(name)
            require(name in files and hashlib.sha256(files[name]).hexdigest() == digest,
                    'supplemental source archive internal SHA mismatch: ' + name)
        manifest = json.loads(files['manifest.json'].decode())
        source = self.campaign['source']
        require(manifest['frozen_root_commit'] == source['commit'], 'supplemental test uses another runtime source')
        base = files['base-tb_xu_cached_wrapper.sv']
        extra = files['tb_xu_cached_wrapper_extra.sv']
        require(base == git_blob(self.repo, source['commit'], manifest['base_tb_path']) and
                hashlib.sha256(base).hexdigest() == manifest['base_tb_sha256'] and
                hashlib.sha256(extra).hexdigest() == manifest['supplement_tb_sha256'],
                'supplemental base/modified testbench identity differs')
        patch = ''.join(difflib.unified_diff(base.decode().splitlines(True), extra.decode().splitlines(True),
                          fromfile='base-tb_xu_cached_wrapper.sv', tofile='tb_xu_cached_wrapper_extra.sv'))
        require(patch.encode() == files['supplement.patch'], 'supplemental patch does not exactly reconstruct supplied testbench')
        require(len(manifest['rtl_sources']) == 13 and len({row['path'] for row in manifest['rtl_sources']}) == 13,
                'supplemental RTL source inventory differs')
        for row in manifest['rtl_sources']:
            require(source['source_sha256'].get(row['path']) == row['sha256'],
                    'supplemental RTL input differs from runtime snapshot: ' + row['path'])
        name = 'extra-evidence/extra-interface-vcs-01'
        commands = self.original(name + '/commands.json')
        require(commands['simulator'] == 'vcs' and commands['status'] == 'PASS' and
                commands['compile_returncode'] == commands['simulation_returncode'] == 0 and
                commands['base_tb_sha256'] == manifest['base_tb_sha256'] and
                commands['supplement_tb_sha256'] == manifest['supplement_tb_sha256'],
                'supplemental VCS return codes/testbench identity differ')
        command = commands['compile_command']
        require(command[:8] == ['vcs', '-full64', '-sverilog', '-timescale=1ns/10ps', '-top',
                                'tb_xu_cached_wrapper_extra', '+define+DISABLE_SV_ASSERTION=1',
                                '-Mdir=' + commands['cwd'] + '/csrc'] and
                command[8:10] == ['-o', commands['cwd'] + '/simv'] and
                [Path(arg).name for arg in command[10:]] == ['tb_xu_cached_wrapper_extra.sv'] +
                    [Path(row['path']).name for row in manifest['rtl_sources']] and
                commands['simulation_command'] == [commands['cwd'] + '/simv'],
                'supplemental actual VCS invocation/input inventory differs')
        compile_log, compile_complete = self.log(name + '/compile.log', commands['compile_log_sha256'], True)
        text, complete = self.log(name + '/simulation.log', commands['simulation_log_sha256'], True)
        require(compile_complete and complete, 'full supplemental VCS compile/simulation logs are required')
        require('Q-2020.03-SP2-6_Full64' in text and not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', text, re.I),
                'supplemental VCS log version or failure check differs')
        require(re.findall(r'^XU_EXTRA_RO_WINDOW_PASS.*$', text, re.M) ==
                ['XU_EXTRA_RO_WINDOW_PASS words=16 writes_ignored=16'] and
                re.findall(r'^XU_EXTRA_BUSY_CACHE_CTRL_ADDR_PASS.*$', text, re.M) ==
                ['XU_EXTRA_BUSY_CACHE_CTRL_ADDR_PASS ctrl=1 addr=173 numeric_check=excluded'],
                'supplemental read-only/busy observation markers differ')
        transactions = re.findall(r'^XU_EXTRA_INTERFACE_PASS accepted=(\d+) retired=(\d+)$', text, re.M)
        require(transactions == [('4967', '4967')], 'supplemental accepted/retired transactions differ')
        return dict(status='PASS', source_archive_sha256=sha(self.extra_source_archive),
                    original_commands_sha256=sha(self.directory / name / 'commands.json'),
                    base_tb_sha256=manifest['base_tb_sha256'], supplement_tb_sha256=manifest['supplement_tb_sha256'],
                    compile_log_sha256=commands['compile_log_sha256'], simulation_log_sha256=commands['simulation_log_sha256'],
                    accepted=4967, retired=4967, patch_reconstruction_verified=True,
                    complete_original_logs_locally_checked=True,
                    scope='separate supplemental VCS interface observations; read-only result-window writes ignored; '
                          'CACHE_CTRL/ADDR accepted while busy, deliberately invalid firmware use, numerical check excluded')

    def run(self):
        for name in self.transferred['files']:
            safe_relative(name)
            identity = self.transferred['files'][name]
            path = self.directory / name
            require(path.is_file() and sha(path) == identity['sha256'] and path.stat().st_size == identity['bytes'],
                    'transferred byte integrity failed: ' + name)
        require(self.original('experiments.json') == self.campaign and
                self.original('acceptance/acceptance.json') == self.accepted, 'campaign/acceptance changed during audit')
        require(self.campaign['status'] == self.accepted['status'] == 'PASS', 'campaign or final acceptance did not pass')
        require(self.receipt.get('integrity_errors') == [] and self.receipt.get('final', {}).get('status') == 'PASS',
                'source receipt is incomplete or has integrity errors')
        require(self.receipt['campaign_sha256'] == sha(self.directory / 'experiments.json') and
                self.receipt['selection'] == self.campaign['selected'], 'source receipt campaign/selection differs')
        source = self.campaign['source']
        committed_main = subprocess.check_output(
            ['git', 'ls-tree', '-r', '--name-only', source['commit'], '--', *RUNTIME_PATHS],
            cwd=str(self.repo)).decode().splitlines()
        committed_rtl = subprocess.check_output(
            ['git', 'ls-tree', '-r', '--name-only', source['e203_commit'], '--', 'rtl'],
            cwd=str(self.repo / 'third-party/e203_hbirdv2')).decode().splitlines()
        require(set(source['source_sha256']) == set(committed_main) |
                {'third-party/e203_hbirdv2/' + name for name in committed_rtl},
                'committed runtime source inventory is incomplete or has unexpected files')
        require(self.receipt['source']['commit'] == source['commit'] and
                self.receipt['source']['manifest_sha256'] == canonical_sha(source['source_sha256']),
                'source receipt runtime snapshot identity differs')
        require(self.receipt['rtl_manifest_sha256'] == canonical_sha(self.campaign['environment']['source_sha256']),
                'source receipt RTL/TB manifest identity differs')
        link = subprocess.check_output(['git', 'ls-tree', source['commit'], '--', 'third-party/e203_hbirdv2'],
                                       cwd=str(self.repo)).decode().split()
        require(len(link) >= 3 and link[0] == '160000' and link[2] == source['e203_commit'], 'runtime E203 gitlink differs')
        for name, digest in source['source_sha256'].items():
            submodule = name.startswith('third-party/e203_hbirdv2/')
            path = name[len('third-party/e203_hbirdv2/'):] if submodule else name
            revision = source['e203_commit'] if submodule else source['commit']
            require(self.blob_sha(revision, path, submodule) == digest, 'committed runtime source/hash mismatch: ' + name)
            self.source_files_checked.add(name)
        fixed = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, '--', *FIXED_PATHS],
                                        cwd=str(self.repo)).decode().splitlines()
        require(set(fixed) == set(source['fixed_sha256']), 'fixed baseline source inventory differs')
        for name in fixed:
            require(self.blob_sha(BASE, name) == source['fixed_sha256'][name] == source['source_sha256'][name],
                    'fixed numeric/vector/startup identity differs from 499ba54: ' + name)
        self.fixture = json.loads(git_blob(self.repo, BASE, 'tests/e203/vectors/kwt-silence-v1.json').decode())
        historical = json.loads(git_blob(self.repo, BASE, OLD_RESULT).decode())
        old_environment = json.loads(git_blob(self.repo, BASE, OLD_CAMPAIGN).decode())['environment']
        old_tools = {Path(key).name: value['sha256'] for key, value in old_environment['tool_sha256'].items()}
        if self.campaign['simulator'] == 'vcs':
            new_tools = {Path(key).name: value['sha256'] for key, value in self.campaign['environment']['tool_sha256'].items()}
            for key in ['riscv64-unknown-elf-gcc', 'riscv64-unknown-elf-objcopy', 'riscv64-unknown-elf-objdump', 'vcs']:
                require(new_tools.get(key) == old_tools[key], 'server executable differs from accepted software toolchain: ' + key)
        experiments = self.campaign['experiments']
        names = [entry['name'] for entry in experiments]
        independent = ['B0-new-RTL', 'H1-bias-cache', 'H2-result-window']
        require(names in [independent, independent + ['H1H2-combined']], 'unexpected independent experiment order')
        receipt_experiments = {entry['name']: entry for entry in self.receipt['experiments']}
        for entry in experiments:
            require(entry['configuration'] == configuration(MODES[entry['name']]), 'experiment firmware mode differs')
            if entry['name'] in ['H1-bias-cache', 'H2-result-window']:
                require(entry['parent'] == 'B0-new-RTL', 'independent H1/H2 reference differs')
            if entry['status'] == 'PASS':
                require([case['workload'] for case in entry['cases']] == ['synthetic2', 'real12'], 'experiment workload scope incomplete')
            receipt_entry = receipt_experiments[entry['name']]
            require(receipt_entry['status'] == entry['status'] and receipt_entry['configuration'] == entry['configuration'],
                    'receipt experiment identity differs')
            require(len(entry['cases']) == len(receipt_entry['cases']), 'receipt experiment case count differs')
            for case, source_case in zip(entry['cases'], receipt_entry['cases']):
                name = Path(case['output']).name
                require(name == entry['name'] + '-' + case['workload'],
                        'experiment case directory/workload differs')
                path = self.directory / name / 'result.json'
                if not path.is_file():
                    require(case['status'] == entry['status'] == 'FAIL', 'passing case has no original result')
                    continue
                record = self.original(name + '/result.json')
                expected_mode, expected_tasks = {'synthetic2': ('synthetic', 2), 'real12': ('real', 12)}[case['workload']]
                require(record['mode'] == expected_mode and record['tasks'] == expected_tasks,
                        'experiment workload is incomplete or mislabeled: ' + name)
                require(case['result_sha256'] == sha(path), 'campaign case original result hash differs')
                require(record_configuration(record) == entry['configuration'], 'case uses another experiment configuration')
                self.receipt_case(record, source_case)
                if case['status'] == 'PASS':
                    require(record['status'] == 'PASS', 'campaign/result status mismatch')
                    self.passing_simulation(name, record)
                    self.results[name] = record
            if entry['status'] == 'PASS':
                record = self.results[entry['name'] + '-real12']
                require(totals(record)['cycles'] == entry['summary']['aggregate']['cycles'] and
                        totals(record)['counters'] == entry['summary']['aggregate']['counters'], 'campaign summary differs from raw case')
        baseline = self.results['B0-new-RTL-real12']
        if self.campaign['simulator'] == 'vcs':
            require([(row['cycles'], row['firmware_cycles']) for row in baseline['layers']] ==
                    [(row['cycles'], row['firmware_cycles']) for row in historical['layers']] and
                    [row['performance'] for row in baseline['layers']] ==
                    [row['performance'] for row in historical['layers']] and
                    totals(baseline)['cycles'] == 25251416 and
                    baseline['firmware_image_sha256'] == historical['firmware_image_sha256'],
                    'B0-new-RTL did not exactly reproduce original software baseline image/cycles')
        by_name = {entry['name']: entry for entry in experiments}
        winner = 'B0-new-RTL'
        for name in ['H1-bias-cache', 'H2-result-window']:
            if by_name[name]['status'] == 'PASS' and totals(self.results[name + '-real12'])['cycles'] < totals(self.results[winner + '-real12'])['cycles']:
                winner = name
        both_pass = all(by_name[name]['status'] == 'PASS' for name in ['H1-bias-cache', 'H2-result-window'])
        require(('H1H2-combined' in by_name) == both_pass, 'combination eligibility differs from independent correctness')
        if both_pass:
            combined = by_name['H1H2-combined']
            require(combined['parent'] == winner, 'combined experiment reference differs from best independent result')
            if combined['status'] == 'PASS' and totals(self.results['H1H2-combined-real12'])['cycles'] < totals(self.results[winner + '-real12'])['cycles']:
                winner = 'H1H2-combined'
        require(self.campaign['selected']['experiment'] == winner and self.campaign['selected']['configuration'] == by_name[winner]['configuration'],
                'independent strict-cycle winner differs from campaign selection')
        for entry in experiments:
            if entry['status'] != 'PASS' or entry['parent'] is None: continue
            current, reference = self.results[entry['name'] + '-real12'], self.results[entry['parent'] + '-real12']
            delta = totals(current)['cycles'] - totals(reference)['cycles']
            require(entry['comparison']['delta_cycles'] == delta and entry['comparison']['strictly_better'] == (delta < 0),
                    'campaign independent comparison decision differs')
            require(entry['comparison']['baseline_cycles'] == totals(reference)['cycles'] and
                    entry['comparison']['candidate_cycles'] == totals(current)['cycles'] and
                    abs(entry['comparison']['speedup'] - totals(reference)['cycles'] / totals(current)['cycles']) < 1e-12,
                    'campaign total-cycle comparison fields differ')
            require([row['delta_cycles'] for row in entry['comparison']['layers']] ==
                    [row['delta_cycles'] for row in layer_comparison(current, reference)], 'campaign per-layer deltas differ')
        require([(step['name'], step['status']) for step in self.accepted['steps']] == [(name, 'PASS') for name in STEPS],
                'full acceptance step sequence is incomplete')
        require(self.accepted['firmware_configuration'] == by_name[winner]['configuration'], 'final accepted config differs')
        expected_profile = 'vcs-platform' if self.campaign['simulator'] == 'vcs' else 'development-standard'
        expected_not_run = ['icarus1', 'chisel'] if self.campaign['simulator'] == 'vcs' else []
        require(self.accepted['profile'] == expected_profile and self.accepted['not_run'] == expected_not_run,
                'final acceptance backend/scope differs')
        expected_scope = ('VCS four-state development platform acceptance; Icarus and Chisel not run; '
                          'official platform/SRAM/PPA/600-sample accuracy still required')
        if self.campaign['simulator'] == 'vcs':
            require(self.accepted['scope'] == expected_scope, 'final acceptance statement of scope differs')
        receipt_acceptance = self.receipt['acceptance']
        require(receipt_acceptance['acceptance_sha256'] == sha(self.directory / 'acceptance/acceptance.json'), 'receipt final acceptance hash differs')
        supplemental_files = {}
        supplemental_manifest_sha256 = None
        if self.campaign['simulator'] == 'vcs':
            supplemental_path = self.directory / 'supplemental-originals-manifest.json'
            supplement = read(supplemental_path)
            require(supplement['schema'] == 'xu-hw-supplemental-originals-v1' and set(supplement['files']) ==
                    {'acceptance/host-wrapper-vcs/compile.log', 'acceptance/host-wrapper-vcs/simulation.log'},
                    'supplemental original log manifest inventory differs')
            for name, identity in supplement['files'].items():
                safe_relative(name)
                path = self.directory / name
                require(name not in self.transferred['files'] and path.is_file() and
                        sha(path) == identity['sha256'] and path.stat().st_size == identity['bytes'] and
                        receipt_acceptance['log_sha256'].get(name[len('acceptance/'):]) == identity['sha256'],
                        'supplemental original log bytes/receipt identity differs: ' + name)
            supplemental_files = supplement['files']
            supplemental_manifest_sha256 = sha(supplemental_path)
        acceptance_cases = {Path(item['output']).name: item for item in receipt_acceptance['cases']}
        for label in ['doctor', 'baseline', 'vectors', 'synthetic1', 'synthetic2', 'real12']:
            name = 'acceptance/' + label
            record = self.original(name + '/result.json')
            require(record['status'] == 'PASS', 'acceptance original child result failed: ' + label)
            expected_mode, expected_tasks = {
                'doctor': ('doctor', 1), 'baseline': ('baseline', 1), 'vectors': ('check-vectors', 12),
                'synthetic1': ('synthetic', 1), 'synthetic2': ('synthetic', 2), 'real12': ('real', 12)}[label]
            require(record['mode'] == expected_mode and record['tasks'] == expected_tasks and
                    record['simulator'] == self.campaign['simulator'] and
                    record['main_commit'] == source['commit'] and
                    record_configuration(record) == by_name[winner]['configuration'] and
                    record['contract_sha256'] == source['source_sha256']['tools/scripts/xu_firmware_contract.py'] and
                    record['transaction_contract'] == work(by_name[winner]['configuration']['schedule']),
                    'acceptance child workload/source/configuration differs: ' + label)
            self.receipt_case(record, acceptance_cases[label])
            if label in ['doctor', 'vectors']:
                require(record['runner_sha256'] == source['source_sha256']['tools/scripts/e203_soc.py'],
                        'acceptance validation runner differs: ' + label)
            if label in ['doctor', 'baseline']:
                require(record['e203_commit'] == source['e203_commit'], 'acceptance E203 revision differs: ' + label)
            if label == 'doctor':
                firmware_sources = {Path(key).name: digest for key, digest in source['source_sha256'].items()
                                    if key.startswith('tests/e203/firmware/')}
                require(record['firmware_sha256'] == record['firmware_build']['source_sha256'] == firmware_sources and
                        record['firmware_build']['configuration'] == by_name[winner]['configuration'],
                        'doctor compiled firmware does not match the committed selected configuration')
            if label == 'baseline':
                installed = {key.replace('/vsim/install/rtl/', '/rtl/e203/'): digest
                             for key, digest in record['source_sha256'].items()}
                expected = {key: digest for key, digest in source['source_sha256'].items()
                            if key.startswith('third-party/e203_hbirdv2/rtl/e203/') and Path(key).suffix in ['.v', '.sv']}
                require(installed == expected, 'basic SoC test installed RTL inventory differs')
            if label in ['synthetic1', 'synthetic2', 'real12']:
                require(record_configuration(record) == by_name[winner]['configuration'], 'accepted workload config differs from selected')
                self.passing_simulation(name, record)
            self.results[name] = record
        basic = self.results['acceptance/baseline']
        require(basic['tests'] == BASE_TESTS and set(basic['test_inputs']) == set(BASE_TESTS), 'basic SoC tests differ')
        baseline_pass_checks = []
        for test in BASE_TESTS:
            test_log = 'acceptance/baseline/' + test + '.log'
            text, complete = self.log(test_log, basic['log_sha256'][test + '.log'], True)
            require('TEST_PASS' in text and not re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:', text),
                    'basic SoC test does not pass available log evidence: ' + test)
            if not test.startswith('rv32'):
                require(basic['test_inputs'][test]['assembly_sha256'] == source['source_sha256']['tests/e203/' + test + '.S'],
                        'basic SoC assembly input differs from runtime snapshot: ' + test)
            baseline_pass_checks.append(dict(test=test, complete_original_locally_checked=complete,
                                             sha256=basic['log_sha256'][test + '.log']))
        checked_vectors = self.results['acceptance/vectors']
        require(checked_vectors['fixture'] == self.fixture and checked_vectors['outputs'] == 304128 and
                [row['layer'] for row in checked_vectors['layers']] == list(range(12)),
                'complete independent integer fixture validation is missing')
        for row in checked_vectors['layers']:
            require(row['outputs'] == 25344 and row['sha256'] ==
                    {name + '.mem': self.fixture['files']['layer_{:02d}/{}.mem'.format(row['layer'], name)]
                     for name in ['x', 'w', 'bias', 'y']}, 'integer-validated fixture hash inventory differs')
        final = self.results['acceptance/real12']
        chosen = self.results[winner + '-real12']
        require(final['layers'] == chosen['layers'] and final['vectors'] == chosen['vectors'] and
                final['firmware_image_sha256'] == chosen['firmware_image_sha256'], 'accepted repeat differs from chosen trial')
        for name, digest in receipt_acceptance['log_sha256'].items():
            self.log('acceptance/' + name, digest)
        counts = {}
        for label in ['host', 'numeric']:
            name = 'acceptance/' + label + '.log'
            require(name in self.transferred['files'], 'full original host/numeric log is missing')
            text, complete = self.log(name, self.transferred['files'][name]['sha256'], True)
            found = re.findall(r'Ran (\d+) tests? in ', text)
            require(complete and len(found) == 1 and re.search(r'^OK$', text, re.M), 'original unit-test log lacks complete OK: ' + label)
            counts[label] = int(found[0])
        require(counts == dict(host=49, numeric=34), 'full host/numeric suite test count differs from frozen hardware source')
        wrapper_name = 'acceptance/host-wrapper-vcs/simulation.log'
        wrapper_identity = receipt_acceptance['log_sha256'].get('host-wrapper-vcs/simulation.log')
        wrapper_evidence = False
        supplemental_interface = None
        if self.campaign['simulator'] == 'vcs':
            require(wrapper_identity is not None, 'VCS directed wrapper test log identity is missing')
            wrapper, complete = self.log(wrapper_name, wrapper_identity, True)
            require(complete, 'complete original VCS directed wrapper log is required')
            require('XU_CACHED_WRAPPER_PASS' in wrapper and not re.search(r'\b(?:FATAL|FAIL(?:ED|URE)?)\b', wrapper, re.I),
                    'VCS directed wrapper test did not pass available log evidence')
            require(re.findall(r'^XU_CACHED_WRAPPER_PASS accepted=(\d+) retired=(\d+)$', wrapper, re.M) == [('4909', '4909')],
                    'VCS directed wrapper accepted/retired transaction count differs')
            wrapper_evidence = dict(path=wrapper_name, sha256=wrapper_identity, accepted=4909, retired=4909,
                                    complete_original_locally_checked=complete)
            supplemental_interface = self.extra_interface()
        server_summary = self.original('acceptance/xu-performance.json')
        require(server_summary['source_result_sha256'] == sha(self.directory / 'acceptance/real12/result.json'),
                'server summary original source result hash differs')
        final_total = totals(final)
        require(server_summary['aggregate']['cycles'] == final_total['cycles'] and
                server_summary['aggregate']['counters'] == final_total['counters'], 'server performance aggregate differs')
        require(server_summary['frequency_mhz'] == 150 and server_summary['pes'] == 8 and
                server_summary['macs_per_task'] == 1622016 and server_summary['ops_per_mac'] == 2,
                'performance conversion frequency or work differs')
        aggregate = server_summary['aggregate']
        expected_aggregate = dict(tasks=12, macs=19464192, conditional_total_latency_ms=final_total['cycles'] / 150000,
            conditional_mean_latency_ms=final_total['cycles'] / 12 / 150000,
            conditional_tasks_per_second=12 * 150000000 / final_total['cycles'],
            conditional_gmac_per_second=19464192 / final_total['cycles'] * 150000000 / 1e9,
            conditional_gops=19464192 * 2 / final_total['cycles'] * 150000000 / 1e9,
            end_to_end_peak_fraction=final_total['counters']['mac_fire'] / final_total['cycles'])
        for key, value in expected_aggregate.items():
            require(abs(aggregate[key] - value) <= 1e-10, 'server summary conversion differs: ' + key)
        for phase in PHASES:
            require(abs(aggregate['phase_fraction'][phase] - final_total['counters'][phase] / final_total['cycles']) < 1e-12,
                    'server aggregate phase fraction differs')
        require(len(server_summary['layers']) == 12, 'server summary layer count differs')
        for expected, actual in zip(final['layers'], server_summary['layers']):
            require(all(expected[key] == actual[key] for key in ['layer', 'cycles', 'firmware_cycles']) and
                    expected['performance'] == actual['counters'], 'server summary per-layer data differs')
        improved = final_total['cycles'] < totals(baseline)['cycles']
        retained = self.campaign['simulator'] == 'vcs' and improved
        retention_status = ('retained' if improved else 'baseline-retained') if self.campaign['simulator'] == 'vcs' else 'provisional'
        require(self.campaign['retained_optimization'] == retained and
                self.campaign['retention_status'] == retention_status,
                'retention status differs from independent cycle/acceptance decision')
        selected_comparison = self.campaign['selected']['comparison']
        require(selected_comparison['baseline_cycles'] == totals(baseline)['cycles'] and
                selected_comparison['candidate_cycles'] == final_total['cycles'] and
                selected_comparison['delta_cycles'] == final_total['cycles'] - totals(baseline)['cycles'] and
                selected_comparison['strictly_better'] == improved and
                abs(selected_comparison['speedup'] - totals(baseline)['cycles'] / final_total['cycles']) < 1e-12,
                'final selected comparison differs from independent arithmetic')
        require([row['delta_cycles'] for row in selected_comparison['layers']] ==
                [row['delta_cycles'] for row in layer_comparison(final, baseline)], 'selected final layer deltas differ')
        receipt_final = self.receipt['final']
        require(receipt_final['retained_optimization'] == retained and
                receipt_final['configuration'] == by_name[winner]['configuration'] and
                receipt_final['baseline_result_sha256'] == sha(self.directory / 'B0-new-RTL-real12/result.json') and
                receipt_final['accepted_result_sha256'] == sha(self.directory / 'acceptance/real12/result.json') and
                receipt_final['acceptance_sha256'] == sha(self.directory / 'acceptance/acceptance.json') and
                receipt_final['performance_summary_sha256'] == sha(self.directory / 'acceptance/xu-performance.json'),
                'receipt final original identities/configuration differ')
        comparison = self.comparison(baseline, final, experiments, winner)
        verification = dict(status='PASS', schema='xu-hardware-independent-verification-v1',
            runtime_modules_imported=False, source_campaign_sha256=sha(self.directory / 'experiments.json'),
            source_receipt_sha256=sha(self.receipt_path), original_file_manifest_sha256=sha(self.directory / 'xu-transfer-manifest.json'),
            transferred_original_files_verified=len(self.transferred['files']), committed_runtime_source_files_verified=len(self.source_files_checked),
            supplemental_original_files_verified=len(supplemental_files),
            supplemental_original_files=supplemental_files,
            supplemental_original_manifest_sha256=supplemental_manifest_sha256,
            selected_experiment=winner, independently_selected_same_winner=True,
            final_repeat_layers_vectors_image_identical=True, final_configuration=by_name[winner]['configuration'],
            final_cycles=final_total['cycles'], baseline_cycles=totals(baseline)['cycles'],
            host_tests=counts['host'], numeric_tests=counts['numeric'], basic_soc_tests=5,
            basic_soc_log_checks=baseline_pass_checks,
            directed_wrapper_vcs=wrapper_evidence, passing_simulations=self.simulations,
            supplemental_interface_vcs=supplemental_interface,
            log_checks=self.log_checks, artifact_checks=self.artifact_checks,
            evidence_scope='exact raw JSON and full host/numeric logs verified; selected-line extracts are derived. '
                           'Numerical and direct-wrapper simulation logs were failure-screened only over locally available text. '
                           'Host/numeric checks use complete unittest summaries; intentional host negative tests may print FAIL. '
                           'Complete compile logs were byte/hash checked. Missing full originals remain on server with SHA256 '
                           'checked by source receipt and recorded by the source-verified runner.',
            ppa_scope='not audited by this performance evidence verifier', source_files=self.sources)
        return verification, comparison

    def comparison(self, baseline, final, experiments, winner):
        bt, ft = totals(baseline), totals(final)
        rows = []
        for experiment in experiments:
            entry = dict(name=experiment['name'], status=experiment['status'], configuration=experiment['configuration'],
                         reference=experiment['parent'])
            if experiment['status'] == 'PASS':
                current = self.results[experiment['name'] + '-real12']
                reference = self.results[(experiment['parent'] or 'B0-new-RTL') + '-real12']
                total = totals(current)['cycles']
                entry.update(cycles=total, delta_vs_reference=total - totals(reference)['cycles'],
                             delta_vs_baseline=total - bt['cycles'], speedup_vs_baseline=bt['cycles'] / total,
                             firmware_build=current['firmware_build'],
                             layers_vs_reference=layer_comparison(current, reference),
                             layers_vs_baseline=layer_comparison(current, baseline))
            rows.append(entry)
        def memory(record):
            value = record['firmware_build']['memory']
            frames = {item['source'].rsplit(':', 1)[-1]: item['bytes'] for item in value['stack_frames']}
            return dict(itcm_bytes=value['itcm_bytes'], bss_bytes=value['bss_bytes'], data_bytes=value['data_bytes'],
                        stack_frames_bytes=frames, static_call_chain_bytes=sum(frames.values()),
                        remaining_dtcm_bytes=value['stack_capacity_after_bss_bytes'] - sum(frames.values()),
                        elf_sha256=record['firmware_elf_sha256'], image_sha256=record['firmware_image_sha256'])
        return dict(schema='xu-hardware-independent-comparison-v1', evidence_kind='locally derived from exact server JSON; not simulation log originals',
            selected_experiment=winner, final_configuration=self.campaign['selected']['configuration'], experiments=rows,
            baseline_cycles=bt['cycles'], final_cycles=ft['cycles'], delta_cycles=ft['cycles'] - bt['cycles'],
            speedup=bt['cycles'] / ft['cycles'], cycle_reduction_fraction=(bt['cycles'] - ft['cycles']) / bt['cycles'],
            layers=layer_comparison(final, baseline),
            phases=[dict(phase=key, baseline=bt['counters'][key], final=ft['counters'][key],
                         delta=ft['counters'][key] - bt['counters'][key], final_fraction=ft['counters'][key] / ft['cycles']) for key in PHASES],
            counters=[dict(counter=key, baseline=bt['counters'][key], final=ft['counters'][key],
                           delta=ft['counters'][key] - bt['counters'][key]) for key in COUNTERS if key not in PHASES],
            memory=dict(baseline=memory(baseline), final=memory(final)),
            conditional_frequency_mhz=150, frequency_scope='conditional conversion only; physical timing closure not established',
            conditional_mean_latency_ms=ft['cycles'] / 12 / 150000,
            conditional_tasks_per_second=12 * 150000000 / ft['cycles'], mac_active_fraction=ft['counters']['mac_fire'] / ft['cycles'],
            source_sha256={name: sha(self.directory / name) for name in ['experiments.json', 'B0-new-RTL-real12/result.json',
                'acceptance/real12/result.json', 'acceptance/xu-performance.json', 'acceptance/acceptance.json']})


def markdown(report):
    lines = ['# xu H1/H2 独立复算', '', '来自原始服务器JSON的派生统计；完整日志与摘录的核验范围见server-verification.json（复核器原输出名verification.json）。', '',
             '| 实验 | 状态 | 总周期 | 独立参考 | 对参考差值 | 对B0速度比 |', '| --- | --- | ---: | --- | ---: | ---: |']
    for entry in report['experiments']:
        if entry['status'] == 'PASS':
            lines.append('| {} | PASS | {:,} | {} | {:+,} | {:.6f}× |'.format(entry['name'], entry['cycles'],
                entry['reference'] or 'B0', entry['delta_vs_reference'], entry['speedup_vs_baseline']))
        else: lines.append('| {} | FAIL | — | {} | — | — |'.format(entry['name'], entry['reference']))
    lines += ['', '最终选择：`{}`，`{}`。总周期{:,.0f}→{:,.0f}，减少{:.6f}%，速度比{:.6f}×。'.format(
        report['selected_experiment'], '/'.join(report['final_configuration'][key] for key in ['schedule', 'optimization', 'experiment']),
        report['baseline_cycles'], report['final_cycles'], 100 * report['cycle_reduction_fraction'], report['speedup']), '',
        '| layer | B0周期 | 最终周期 | 差值 |', '| --- | ---: | ---: | ---: |']
    for row in report['layers']:
        lines.append('| {} | {:,} | {:,} | {:+,} |'.format(row['layer'], row['reference_cycles'], row['cycles'], row['delta_cycles']))
    passed = [entry for entry in report['experiments'] if entry['status'] == 'PASS']
    lines += ['', '各独立实验逐层 TB / 固件 mcycle（固件窗口含固定软件指令开销）：', '',
              '| layer | ' + ' | '.join(entry['name'] for entry in passed) + ' |',
              '| --- | ' + ' | '.join('---:' for entry in passed) + ' |']
    for index in range(12):
        values = [entry['layers_vs_baseline'][index] for entry in passed]
        lines.append('| {} | '.format(index) + ' | '.join('{:,} / {:,}'.format(row['cycles'], row['firmware_cycles']) for row in values) + ' |')
    lines += ['', '| 阶段 | B0 | 最终 | 差值 | 最终占比 |', '| --- | ---: | ---: | ---: | ---: |']
    for row in report['phases']:
        lines.append('| {} | {:,} | {:,} | {:+,} | {:.6f}% |'.format(row['phase'], row['baseline'], row['final'], row['delta'], row['final_fraction'] * 100))
    lines += ['', '| 活动/事务 | B0 | 最终 | 差值 |', '| --- | ---: | ---: | ---: |']
    for row in report['counters']:
        lines.append('| {} | {:,} | {:,} | {:+,} |'.format(row['counter'], row['baseline'], row['final'], row['delta']))
    lines += ['', 'PPA未由本性能复核器审计。150MHz仅作条件换算，静态frame不代表实测运行时栈水位。']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-json', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--repo', type=Path,
                        default=next((root for root in Path(__file__).resolve().parents if (root / '.git').exists()), Path.cwd()))
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--archive-sha256')
    parser.add_argument('--extra-source-archive', type=Path,
                        help='unaltered xu-hw-extra-interface.tar.xz with source, exact patch and source manifest')
    parser.add_argument('--supplemental-archive', type=Path, action='append', default=[],
                        help='additional unchanged archive whose root paths match --server-json')
    parser.add_argument('--supplemental-archive-sha256', action='append', default=[])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        archive_checks = []
        if args.archive is not None or args.archive_sha256 is not None:
            require(args.archive is not None and args.archive_sha256 is not None, 'archive and expected SHA256 must be supplied together')
            require(sha(args.archive) == args.archive_sha256, 'original archive SHA256 differs')
            archive_checks.append(verify_archive_binding(args.archive, args.server_json))
        require(len(args.supplemental_archive) == len(args.supplemental_archive_sha256),
                'each supplemental archive requires an expected SHA256')
        for path, digest in zip(args.supplemental_archive, args.supplemental_archive_sha256):
            require(sha(path) == digest, 'supplemental original archive SHA256 differs')
            archive_checks.append(verify_archive_binding(path, args.server_json))
        verification, comparison = Audit(args.server_json, args.receipt, args.repo, args.extra_source_archive).run()
        verification['archive_sha256'] = sha(args.archive) if args.archive else None
        verification['archive_checks'] = archive_checks
        unique_logs = {item['path']: item for item in verification['log_checks']}
        verification['unique_log_scope_counts'] = {
            scope: sum(row['scope'] == scope for row in unique_logs.values())
            for scope in sorted({row['scope'] for row in unique_logs.values()})}
        for filename, value in [('verification.json', verification), ('comparison.json', comparison)]:
            with (args.out / filename).open('x') as stream: stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
        with (args.out / 'comparison.md').open('x') as stream: stream.write(markdown(comparison))
        print(json.dumps(dict(status='PASS', final_cycles=verification['final_cycles'], selected=verification['selected_experiment'],
                              simulations=len(verification['passing_simulations']), output=str(args.out)), indent=2))
        return 0
    except Exception as exc:
        with (args.out / 'verification.json').open('x') as stream:
            stream.write(json.dumps(dict(status='FAIL', error=str(exc), runtime_modules_imported=False), indent=2) + '\n')
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
