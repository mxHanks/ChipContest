#!/usr/bin/env python3
"""Independently audit TASK/PERF/SOC records without importing runtime drivers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tarfile
import tempfile

SOURCE_COMMIT = '97b35421dfbbfa8f4d495b6927a7c66610ff8206'
E203_COMMIT = 'f49a5fc914971426bd4530db39e270a84b41139f'
PHASES = ['w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other']
MMIO_WRITES = {'bias-dtcm': 156326, 'bias-hw': 81064,
               'bias-dtcm-window': 130982, 'bias-hw-window': 55720}
PERF_FIELDS = {'layer', 'cycles', *PHASES, 'busy', 'mac_fire', 'mmio_reads',
               'mmio_writes', 'shared_reads', 'shared_writes', 'shared_stall',
               'mmio_stall', 'starts', 'dones'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def independent_contract(schedule):
    require(schedule in MMIO_WRITES, 'unknown hardware screening schedule')
    return dict(w_shared_reads=64*256, x_shared_reads=99*64,
                bias_shared_reads=256*2, shared_reads=64*256+99*64+256*2,
                shared_writes=99*256*2,
                bias_mmio_writes=256*3 if schedule.startswith('bias-hw') else 99*32*8*3,
                mmio_writes=MMIO_WRITES[schedule], starts=99*32, dones=99*32,
                mac_fire=99*32*64, macs=99*64*256, outputs=99*256)


def parse_event(line):
    tokens = line.split()
    values = {}
    for token in tokens[1:]:
        parts = token.split('=')
        require(len(parts) == 2 and re.match(r'^\d+$', parts[1]),
                'malformed event token: ' + token)
        require(parts[0] not in values, 'duplicate event field: ' + parts[0])
        values[parts[0]] = int(parts[1])
    return tokens[0], values


def validate_run(result, log, schedule, mode, tasks, source_commit=SOURCE_COMMIT):
    """Return independently parsed counters; errors fail closed."""
    require(not re.search(r'(?im)\b(?:TASK_FAIL|SOC_FAIL|FATAL|FAIL(?:ED|URE)?|mismatch|timeout)\b|^%Error', log),
            'failure marker in original simulation log')
    events = [parse_event(line) for line in log.splitlines()
              if line.startswith(('TASK_PASS ', 'PERF_TASK ', 'SOC_PASS '))]
    require([item[0] for item in events] == ['TASK_PASS', 'PERF_TASK']*tasks+['SOC_PASS'],
            'missing, duplicated, or unordered TASK/PERF/SOC events')
    require(result.get('status') == 'PASS' and result.get('mode') == mode and
            result.get('simulator') == 'verilator' and result.get('tasks') == tasks,
            'result run identity differs')
    require(result.get('main_commit') == source_commit and result.get('e203_commit') == E203_COMMIT,
            'result source commit differs from frozen run')
    expected_config = dict(schedule=schedule, optimization='-O2', experiment='both-unroll-no-masks')
    require(result.get('firmware_schedule') == schedule and result.get('firmware_opt') == '-O2' and
            result.get('firmware_experiment') == 'both-unroll-no-masks' and
            result.get('firmware_build', {}).get('configuration') == expected_config,
            'requested, compiled, and measured firmware profiles differ')
    contract = independent_contract(schedule)
    require(result.get('transaction_contract') == contract, 'transaction contract differs')
    layers = []
    for layer in range(tasks):
        task = events[2*layer][1]
        perf = events[2*layer+1][1]
        require(set(task) == {'layer', 'outputs', 'writes', 'cycles', 'firmware_cycles'},
                'TASK fields differ')
        require(set(perf) == PERF_FIELDS, 'PERF fields differ')
        require(task['layer'] == perf['layer'] == layer, 'layer sequence differs')
        require(task['cycles'] == perf['cycles'] > 0 and task['firmware_cycles'] >= task['cycles'],
                'cycle fields differ')
        require(task['outputs'] == contract['outputs'] and task['writes'] == contract['shared_writes'],
                'TASK output/write counts differ')
        require(sum(perf[name] for name in PHASES) == perf['cycles'], 'phase sum differs')
        require(perf['mac_fire'] <= perf['busy'] <= perf['cycles'], 'activity bounds differ')
        require(perf['busy'] == 99*32*68, 'unchanged core busy cycle count differs')
        for field in ['mac_fire', 'starts', 'dones', 'mmio_writes', 'shared_reads', 'shared_writes']:
            require(perf[field] == contract[field], 'work counter differs: ' + field)
        require(all(type(value) is int and 0 <= value <= perf['cycles'] for value in perf.values()),
                'counter is invalid or exceeds measured task window')
        counters = {key: value for key, value in perf.items() if key not in ['layer', 'cycles']}
        layers.append(dict(layer=layer, cycles=task['cycles'],
                           firmware_cycles=task['firmware_cycles'], performance=counters))
    final = events[-1][1]
    require(final == dict(tasks=tasks, outputs=tasks*contract['outputs'],
                          writes=tasks*contract['shared_writes']), 'SOC totals differ')
    require(result.get('layers') == layers and result.get('outputs') == final['outputs'] and
            result.get('write_words') == final['writes'], 'result JSON differs from raw log')
    return dict(status='PASS', tasks=tasks, outputs=final['outputs'], write_words=final['writes'],
                layers=layers, independent_transaction_contract=contract)



RUNTIME_PATHS = ['src', 'tests/e203', 'tools/scripts', 'project.scala',
                 'tools/model/export_kwt.py', 'model']
CASES = [('B0-real1', 'bias-dtcm', 'real', 1),
         ('H1-synthetic2', 'bias-hw', 'synthetic', 2), ('H1-real1', 'bias-hw', 'real', 1),
         ('H2-synthetic2', 'bias-dtcm-window', 'synthetic', 2),
         ('H2-real1', 'bias-dtcm-window', 'real', 1),
         ('H1H2-synthetic2', 'bias-hw-window', 'synthetic', 2),
         ('H1H2-real1', 'bias-hw-window', 'real', 1)]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_runtime_sources(repo, snapshot):
    """Allow report-only HEAD changes; freeze every runtime byte and source set."""
    def git(arguments, directory=repo):
        return subprocess.check_output(['git', *arguments], cwd=str(directory)).decode().strip()
    sources = snapshot['source_sha256']
    for name, expected in sources.items():
        path = repo/name
        require(path.is_file() and sha256(path) == expected, 'frozen runtime source differs: ' + name)
    expected_main = {name for name in sources if not name.startswith('third-party/')}
    actual_main = set(git(['ls-files', '--', *RUNTIME_PATHS]).splitlines())
    require(actual_main == expected_main, 'tracked runtime source file set differs')
    require(not git(['ls-files', '--others', '--exclude-standard', '--', *RUNTIME_PATHS]),
            'untracked runtime source files')
    submodule = repo/'third-party/e203_hbirdv2'
    require(git(['rev-parse', '--show-toplevel'], submodule) == str(submodule.resolve()),
            'E203 is not an initialized independent submodule')
    require(git(['rev-parse', 'HEAD'], submodule) == snapshot['e203_commit'],
            'E203 submodule commit differs')
    pin = git(['ls-tree', 'HEAD', 'third-party/e203_hbirdv2']).split()
    require(pin[:1] == ['160000'] and pin[2:3] == [snapshot['e203_commit']],
            'E203 gitlink differs')
    expected_rtl = {name for name in sources if name.startswith('third-party/')}
    actual_rtl = {path.relative_to(repo).as_posix() for path in (submodule/'rtl/e203').rglob('*')
                  if path.is_file() and path.suffix in ['.v', '.sv']}
    require(expected_rtl == actual_rtl, 'E203 RTL source file set differs')
    return dict(status='PASS', source_files=len(sources),
                frozen_runtime_commit=snapshot['commit'],
                current_main_commit=git(['rev-parse', 'HEAD']), e203_commit=snapshot['e203_commit'],
                criterion='runtime file hashes and source sets; current HEAD may include report-only changes')


def checked_archive(archive, target, prefix):
    """Reject unsafe/unlisted/duplicate archive entries before reading evidence."""
    with tarfile.open(str(archive), 'r:xz') as stream:
        members = stream.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), 'duplicate archive entry')
        for member in members:
            name = Path(member.name)
            require(not name.is_absolute() and '..' not in name.parts and
                    name.parts[:1] == (prefix,) and (member.isfile() or member.isdir()),
                    'unsafe archive entry: ' + member.name)
        for member in members:
            if member.isdir():
                (target/member.name).mkdir(parents=True, exist_ok=True)
            else:
                path = target/member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(stream.extractfile(member).read())
    root = target/prefix
    manifest = {}
    for line in (root/'SHA256SUMS').read_text().splitlines():
        require(re.fullmatch(r'[0-9a-f]{64}  [^\r\n]+', line), 'malformed SHA256SUMS line')
        digest, name = line.split('  ', 1)
        require(name not in manifest and not Path(name).is_absolute() and '..' not in Path(name).parts,
                'duplicate or unsafe manifest path')
        manifest[name] = digest
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*')
              if path.is_file() and path != root/'SHA256SUMS'}
    require(actual == set(manifest), 'archive files differ from strict inner manifest')
    for name, digest in manifest.items():
        require(sha256(root/name) == digest, 'archive inner hash differs: ' + name)
    return root, dict(sha256=sha256(archive), bytes=archive.stat().st_size,
                      ordinary_files_including_manifest=len(manifest)+1,
                      strict_inner_sha256='PASS')


def synthetic_vector_hashes(tasks):
    """Recompute the documented fixed synthetic cases with Python integers."""
    hashes = {}
    for layer in range(tasks):
        x = [(row*3+k*5+layer*7)%31-15 for row in range(99) for k in range(64)]
        w = [(k*3+column*7+layer*11)%29-14 for k in range(64) for column in range(256)]
        x[:2] = [-32768, 32767]
        w[:256] = [32767 if column%2 == 0 else -32768 for column in range(256)]
        bias = [(column-128)*2**31+layer for column in range(256)]
        y = [bias[column]+sum(x[row*64+k]*w[k*256+column] for k in range(64))
             for row in range(99) for column in range(256)]
        for name, values, bits in [('x', x, 16), ('w', w, 16), ('bias', bias, 40), ('y', y, 48)]:
            payload = ''.join(format(value % 2**bits, '0{}x'.format(bits//4))+'\n'
                              for value in values).encode()
            hashes['layer_{:02d}/{}.mem'.format(layer, name)] = hashlib.sha256(payload).hexdigest()
    return hashes


def verify_firmware(directory, result, snapshot, schedule):
    """Hash raw products and independently compare ELF allocated bytes to image bytes."""
    elf_path, image_path = directory/'accel_soc', directory/'accel_soc.verilog'
    require(sha256(elf_path) == result['firmware_elf_sha256'] == result['firmware_build']['elf_sha256'],
            'firmware ELF hash differs')
    require(sha256(image_path) == result['firmware_image_sha256'] == result['firmware_build']['image_sha256'],
            'firmware image hash differs')
    require(json.loads((directory/'firmware-build.json').read_text()) == result['firmware_build'],
            'firmware build JSON differs')
    expected_sources = {Path(name).name: digest for name, digest in snapshot['source_sha256'].items()
                        if name.startswith('tests/e203/firmware/')}
    require(result['firmware_sha256'] == result['firmware_build']['source_sha256'] == expected_sources,
            'firmware source hash differs')
    command = result['firmware_build']['command']
    require(json.loads((directory/'firmware-build.log').read_text().splitlines()[0]) == command,
            'firmware command differs from raw build log')
    defines = set(item for item in command if item.startswith('-D'))
    expected_defines = {
        '-DXU_FIRMWARE_BIAS_DTCM=' + str(int(schedule.startswith('bias-dtcm'))),
        '-DXU_HARDWARE_BIAS_CACHE=' + str(int(schedule.startswith('bias-hw'))),
        '-DXU_HARDWARE_RESULT_WINDOW=' + str(int(schedule.endswith('-window'))),
        '-DXU_FIRMWARE_BIAS_UNROLL=1', '-DXU_FIRMWARE_RESULT_UNROLL=1', '-DXU_FIRMWARE_NO_MASKS=1'}
    require(defines == expected_defines and len(defines) == len([x for x in command if x.startswith('-D')]),
            'firmware compile defines differ')
    require([item for item in command if re.match(r'^-O', item)] == ['-O2'] and
            '-march=rv32imac_zicsr2p0_zifencei2p0' in command and '-mabi=ilp32' in command and
            '-fstack-usage' in command, 'firmware compiler options differ')
    elf = elf_path.read_bytes()
    require(elf[:7] == b'\x7fELF\x01\x01\x01', 'firmware is not ELF32 little-endian')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', elf)
    require(header[2] == 243, 'firmware machine is not RISC-V')
    shoff, shentsize, shnum, shstrndx = header[6], header[11], header[12], header[13]
    require(shentsize == 40 and shnum > shstrndx, 'unexpected ELF section table')
    sections = [struct.unpack_from('<IIIIIIIIII', elf, shoff+index*shentsize)
                for index in range(shnum)]
    string_section = sections[shstrndx]
    strings = elf[string_section[4]:string_section[4]+string_section[5]]
    named = {}
    expected_bytes = {}
    for section in sections:
        name = strings[section[0]:].split(b'\0', 1)[0].decode()
        named[name] = section
        if section[1] == 1 and section[2] & 2:
            address = section[3]
            # Frozen runner remaps objcopy @800... to @000... for ITCM loading.
            if address >> 20 == 0x800:
                address -= 0x80000000
            for offset, value in enumerate(elf[section[4]:section[4]+section[5]]):
                require(address+offset not in expected_bytes, 'overlapping allocated ELF sections')
                expected_bytes[address+offset] = value
    image_bytes = {}
    address = None
    for token in image_path.read_text().split():
        if token.startswith('@'):
            require(re.fullmatch(r'@[0-9a-fA-F]+', token), 'bad image address')
            address = int(token[1:], 16)
        else:
            require(address is not None and re.fullmatch(r'[0-9a-fA-F]{2}', token), 'bad image data')
            require(address not in image_bytes, 'duplicate firmware image address')
            image_bytes[address] = int(token, 16)
            address += 1
    require(expected_bytes == image_bytes, 'ELF allocated bytes differ from loaded firmware image')
    memory = result['firmware_build']['memory']
    require(memory['itcm_bytes'] == named['.text'][5] == len(image_bytes), 'firmware code size differs')
    require(memory['bss_bytes'] == named.get('.bss', [0]*10)[5] and
            memory['data_bytes'] == named.get('.data', [0]*10)[5] == 0,
            'firmware data/BSS size differs')
    frames = []
    for path in sorted(directory.glob('*.su')):
        for line in path.read_text().splitlines():
            source, size, kind = line.rsplit('\t', 2)
            frames.append(dict(source=source, bytes=int(size), kind=kind))
    require(frames and memory['stack_frames'] == frames and all(row['kind'] == 'static' for row in frames),
            'archived GCC stack frames differ')
    require(re.search(r'80000086\s+<write_tohost>', (directory/'firmware.dump').read_text()),
            'firmware completion address differs')
    return dict(elf_sha256=sha256(elf_path), image_sha256=sha256(image_path),
                image_bytes_verified_against_elf=len(image_bytes), bss_bytes=memory['bss_bytes'],
                itcm_bytes=memory['itcm_bytes'], static_function_stack_frames=frames)


def verify_bundle(evidence, repo):
    snapshot = json.loads((evidence/'evidence-tools/runtime-source-97b3542.json').read_text())
    report = dict(status='RUNNING', evidence_kind='independent audit of archived raw local evidence',
                  scope='local GCC14 / Verilator / Icarus; no server real12 performance or physical PPA claim',
                  source=verify_runtime_sources(repo, snapshot), archives={}, runs=[])
    archive_specs = [('xu-hw-local-evidence.tar.xz', 'xu-hw-local-evidence'),
                     ('xu-hw-extra-interface.tar.xz', 'xu-hw-extra-interface'),
                     ('xu-hw-local-screening.tar.xz', 'xu-hw-local-screening')]
    outer = json.loads((evidence/'local-artifacts/archives-sha256.json').read_text())
    require(set(outer) == {item[0] for item in archive_specs}, 'outer archive file set differs')
    with tempfile.TemporaryDirectory(prefix='xu-local-audit-') as temporary:
        roots = {}
        for filename, prefix in archive_specs:
            archive = evidence/'local-artifacts'/filename
            require(sha256(archive) == outer[filename]['sha256'] and
                    archive.stat().st_size == outer[filename]['bytes'], 'outer archive hash differs: '+filename)
            root, record = checked_archive(archive, Path(temporary), prefix)
            roots[prefix] = root
            report['archives'][filename] = record
        raw = roots['xu-hw-local-screening']
        local_check = json.loads((raw/'local-check.json').read_text())
        require(local_check['status'] == 'PASS' and local_check['source'] == snapshot,
                'original local campaign source identity differs')
        require([row['name'] for row in local_check['runs']] == [row[0] for row in CASES],
                'original local campaign case order differs')
        reference = json.loads((raw/'source-vector-references.json').read_text())
        require(reference['frozen_runtime_commit'] == snapshot['commit'] and
                reference['e203_commit'] == snapshot['e203_commit'] and
                reference['source_sha256'] == snapshot['source_sha256'],
                'archived source reference manifest differs')
        vector_archive = repo/'tests/e203/vectors/kwt-silence-v1.tar.gz'
        require(sha256(vector_archive) == snapshot['fixed_sha256'][vector_archive.relative_to(repo).as_posix()],
                'fixed real vector archive differs')
        real_hashes = {}
        with tarfile.open(str(vector_archive), 'r:gz') as stream:
            names = set()
            for member in stream.getmembers():
                require(member.isfile() and member.name not in names, 'unexpected vector archive entry')
                names.add(member.name)
                real_hashes[member.name] = hashlib.sha256(stream.extractfile(member).read()).hexdigest()
        require(reference['real_archive_sha256'] == sha256(vector_archive) and
                reference['real_archive_member_sha256'] == real_hashes, 'vector reference manifest differs')
        synthetic_hashes = synthetic_vector_hashes(2)
        common = None
        for index, (label, schedule, mode, tasks) in enumerate(CASES):
            directory = raw/label
            result = json.loads((directory/'result.json').read_text())
            log = (directory/'simulation.log').read_text()
            validation = validate_run(result, log, schedule, mode, tasks)
            original = local_check['runs'][index]
            require(original['status'] == 'PASS' and original['result_sha256'] == sha256(directory/'result.json') and
                    original['log_sha256'] == result['log_sha256'] and
                    original['firmware_image_sha256'] == result['firmware_image_sha256'] and
                    original['cycles'] == [row['cycles'] for row in validation['layers']],
                    'original campaign record differs: ' + label)
            for name, digest in result['log_sha256'].items():
                require(Path(name).name == name and sha256(directory/name) == digest,
                        'original run log hash differs: ' + label + '/' + name)
            # Cached builds omit simulator-build.log from result.log_sha256; it
            # remains byte-preserved and covered by the archive's strict manifest.
            for name, digest in result['source_sha256'].items():
                source_name = name.replace('third-party/e203_hbirdv2/vsim/install/rtl/',
                                           'third-party/e203_hbirdv2/rtl/e203/')
                require(snapshot['source_sha256'].get(source_name) == digest,
                        'measured RTL/TB source differs: ' + name)
            expected_installed = {name.replace('third-party/e203_hbirdv2/rtl/e203/',
                                               'third-party/e203_hbirdv2/vsim/install/rtl/')
                                  for name in snapshot['source_sha256'] if name.startswith('third-party/')}
            require(set(result['source_sha256']) == expected_installed | {'tests/e203/tb_accel_soc.sv'},
                    'measured RTL/TB source set differs')
            require(result['contract_sha256'] == snapshot['source_sha256']['tools/scripts/xu_firmware_contract.py'] and
                    result['runner_sha256'] == snapshot['source_sha256']['tools/scripts/e203_soc.py'],
                    'transaction contract / runner source differs')
            identity = (result['versions'], result['tools'], result['source_sha256'], result['simulator_sha256'])
            require(common is None or common == identity, 'local tool/simulator/RTL identities changed between cases')
            common = identity
            expected_vectors = {name: digest for name, digest in
                                (real_hashes if mode == 'real' else synthetic_hashes).items()
                                if int(name.split('/')[0].split('_')[1]) < tasks}
            require(result['vectors'] == reference['run_vector_sha256'][label] == expected_vectors,
                    'run vector bytes differ from fixed real archive or independently recomputed synthetic case')
            if mode == 'real':
                require(result['fixture']['archive_sha256'] == sha256(vector_archive) and
                        result['fixture']['files'] == real_hashes, 'real fixture provenance differs')
            firmware = verify_firmware(directory, result, snapshot, schedule)
            if label == 'B0-real1':
                require(firmware['image_sha256'] == '1e038157321ac5891329762064d7da77125fbf0134dfe29600e94105b5acefd8',
                        'B0 frozen GCC14 software baseline image differs')
            report['runs'].append(dict(name=label, result_sha256=sha256(directory/'result.json'),
                                       simulation_log_sha256=sha256(directory/'simulation.log'),
                                       mode=mode, firmware_schedule=schedule, firmware=firmware, **validation))
        report['tool_versions'] = common[0]
        require(re.search(r'^Ran 49 tests in [0-9.]+s\n\nOK\s*$', (raw/'host-tests.log').read_text(), re.M),
                'original host test summary differs')
        require(re.search(r'^Ran 34 tests in [0-9.]+s\n\nOK\s*$', (raw/'numeric-tests.log').read_text(), re.M),
                'original numeric test summary differs')
        report['host_tests'] = dict(tests=49, status='PASS', log_sha256=sha256(raw/'host-tests.log'))
        report['numeric_tests'] = dict(tests=34, status='PASS', log_sha256=sha256(raw/'numeric-tests.log'))
        chisel = roots['xu-hw-local-evidence']
        observation = json.loads((chisel/'xu-chisel-observation-receipt.json').read_text())
        raw_test_files = [path for path in (chisel/'chiselsim').rglob('*') if path.is_file()]
        require(len(raw_test_files) == 39 and observation['observed_summary'] ==
                dict(tests=13, succeeded=13, failed=0, suites=10, duration_seconds=75),
                'Chisel observation/raw file count differs')
        require({row['path'] for row in observation['files']} ==
                {path.relative_to(chisel).as_posix() for path in raw_test_files},
                'Chisel raw per-test file set differs from observation receipt')
        for row in observation['files']:
            require(sha256(chisel/row['path']) == row['sha256'] and
                    (chisel/row['path']).stat().st_size == row['bytes'],
                    'Chisel raw per-test file differs from observation receipt')
        for record in observation['rtl']:
            require(snapshot['source_sha256'][record['path']] == record['sha256'],
                    'Chisel generated RTL receipt differs')
        direct_log = (chisel/'direct-wrapper-iverilog/simulation.log').read_text()
        require(re.search(r'^XU_CACHED_WRAPPER_PASS accepted=4909 retired=4909\s*$', direct_log, re.M),
                'original direct wrapper PASS differs')
        report['chisel'] = dict(tests_observed_passed=13, suites_observed=10,
                               aggregate_stdout='not originally saved; observation receipt only',
                               preserved_raw_per_test_files=39,
                               raw_per_test_file_semantics='compile / protocol execution script / simulator console output; empty console files preserved')
        report['direct_wrapper_iverilog'] = dict(status='PASS', accepted=4909, retired=4909,
                                                 simulation_log_sha256=sha256(chisel/'direct-wrapper-iverilog/simulation.log'))
        extra = roots['xu-hw-extra-interface']
        manifest = json.loads((extra/'manifest.json').read_text())
        require(manifest['frozen_root_commit'] == SOURCE_COMMIT and manifest['base_tb_sha256'] ==
                snapshot['source_sha256']['tests/e203/tb_xu_cached_wrapper.sv'] and
                sha256(extra/'base-tb_xu_cached_wrapper.sv') == manifest['base_tb_sha256'] and
                sha256(extra/'tb_xu_cached_wrapper_extra.sv') == manifest['supplement_tb_sha256'],
                'supplemental interface TB provenance differs')
        for record in manifest['rtl_sources']:
            require(snapshot['source_sha256'][record['path']] == record['sha256'],
                    'supplemental interface RTL source differs')
        for kind in ['compile', 'simulation']:
            require(sha256(extra/'local-iverilog'/(kind+'.log')) == manifest['local_run'][kind+'_log_sha256'] and
                    manifest['local_run'][kind+'_returncode'] == 0, 'supplemental interface original log differs')
        extra_log = (extra/'local-iverilog/simulation.log').read_text()
        require('EXTRA_INTERFACE_PASS' in extra_log and not re.search(r'\bFAIL|FATAL|ERROR', extra_log),
                'supplemental interface did not pass')
        report['supplemental_interface_iverilog'] = dict(status='PASS', scope=manifest['scope'],
            simulation_log_sha256=sha256(extra/'local-iverilog/simulation.log'))
    report.update(status='PASS', runs_verified=len(CASES), tasks_verified=sum(row[3] for row in CASES),
                  independence='does not import runtime runner, contract, campaign, or retention decision functions',
                  limits=['Local one-real-layer screening cannot substitute for same-server real12 VCS retention.',
                          'Hash / event auditing verifies preserved artifacts and recorded counters, not a second independent RTL simulation.',
                          'No VCS result, physical area, power, timing closure or accuracy evaluation is inferred here.',
                          'Chisel aggregate stdout is an observation receipt, never claimed as an archived original stdout.'])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result')
    parser.add_argument('--log')
    parser.add_argument('--schedule', choices=sorted(MMIO_WRITES))
    parser.add_argument('--mode', choices=['real', 'synthetic'])
    parser.add_argument('--tasks', type=int)
    parser.add_argument('--evidence', help='verify all local archives in this evidence directory')
    parser.add_argument('--repo', help='frozen runtime checkout; later report-only commits are accepted')
    parser.add_argument('--out', help='write derived verification JSON here')
    args = parser.parse_args()
    if args.evidence:
        require(args.repo is not None, '--evidence requires --repo')
        report = verify_bundle(Path(args.evidence).resolve(), Path(args.repo).resolve())
    else:
        require(all(value is not None for value in [args.result, args.log, args.schedule, args.mode, args.tasks]),
                'single-run verification requires --result --log --schedule --mode --tasks')
        report = validate_run(json.loads(Path(args.result).read_text()),
                              Path(args.log).read_text(), args.schedule, args.mode, args.tasks)
    payload = json.dumps(report, indent=2, ensure_ascii=False)+'\n'
    if args.out:
        Path(args.out).write_text(payload)
    else:
        print(payload, end='')


if __name__ == '__main__':
    main()
