"""Revalidate a relocatable, explicitly selected behavioral E203 baseline.

This reader launches no processes and manufactures no baseline. Its return value
is evidence for the development simulation boundary, never official/PPA proof.
The frozen first-generation producer and its historical reports remain intact.
"""
import hashlib
from datetime import datetime
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import sram_evidence as E
import run_official_sram_contract as C
import sram_adapter_plan as PLAN
import run_sram_adapter_soc as S
import run_sram_soc as SOC
import sram_sources as SOURCES

DEFAULT_PLATFORM_MANIFEST = ROOT/'configs/e203-development-platform.json'
CONFIG = {'tasks': 12, 'backend': 'behavioral', 'frequency_mhz': 150, 'jobs': 2}
SCOPE = 'open E203 fork development integration; no official physical/PPA acceptance'
MEASUREMENT_SCOPE = ('CPU task release through final accepted mailbox response; '
                     'excludes TB backdoor preload and aborted epochs')
COMMON = ('src/rtl/memory/kwt_sram_1rw.sv', 'src/rtl/memory/kwt_sram_bank.sv',
          'src/rtl/kwt_linear_engine_rowpair_sram.sv')
SOC_SOURCES = ('sim/tb_e203_kwt_sram.sv', 'sim/kwt_shared512_checked_model.sv',
               'soc/kwt_icb_slave_sram.sv')
FW = ('soc/firmware/start.S', 'soc/firmware/kwt_smoke_sram.c',
      'soc/firmware/link.ld', 'soc/include/kwt_accel_regs.h')
PRODUCERS = ('scripts/verify/run_sram_soc.py', 'scripts/verify/run_linear.py',
             'scripts/verify/run_exported_linear.py', 'scripts/verify/run_checks.py',
             'scripts/verify/sram_evidence.py', 'scripts/verify/sram_sources.py',
             'model/fixed16_acc48.py', 'configs/sram-backends.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(path):
    return json.loads(Path(path).read_text())


def _same(left, right):
    # Python equality conflates True/1 and 150.0/150; evidence JSON must not.
    options = {'sort_keys': True, 'separators': (',', ':'), 'allow_nan': False}
    return json.dumps(left, **options) == json.dumps(right, **options)


def _absolute(path):
    path = Path(path)
    path = path if path.is_absolute() else ROOT/path
    require('..' not in path.parts, 'parent traversal is forbidden: '+str(path))
    # Check ancestors before resolve: resolve alone would hide a linked tree.
    for parent in [path, *path.parents]:
        require(not parent.is_symlink(), 'linked evidence/platform path: '+str(parent))
    require(path.resolve() == path, 'noncanonical evidence/platform path: '+str(path))
    return path


def _record(item):
    """Check actual SHA and size; old producers may add a project-relative label."""
    require(isinstance(item, dict), 'file record is not a dictionary')
    require(isinstance(item.get('path'), str) and Path(item['path']).is_absolute(),
            'file record requires an absolute path')
    path = _absolute(item['path'])
    require(isinstance(item.get('sha256'), str) and
            re.fullmatch(r'[0-9a-f]{64}', item['sha256']), 'invalid record SHA256')
    size = item.get('size_bytes', item.get('bytes'))
    require(type(size) is int and size >= 0, 'missing/invalid record byte count')
    if 'bytes' in item:
        require(type(item['bytes']) is int and item['bytes'] == size, 'conflicting byte counts')
    if 'project_relative_path' in item:
        require(path.is_relative_to(ROOT) and
                item['project_relative_path'] == path.relative_to(ROOT).as_posix(),
                'project-relative record label differs: '+str(path))
    actual = E.record(path)
    require(actual['sha256'] == item['sha256'] and actual['size_bytes'] == size,
            'file identity differs: '+str(path))
    return actual


def _records(items, label):
    require(isinstance(items, list) and items, label+' file records absent')
    values = [_record(item) for item in items]
    require(len({item['path'] for item in values}) == len(values), 'duplicate '+label+' record')
    return values


def _merge(*groups):
    return PLAN._merge(*groups)


def verify_platform(platform, *, platform_manifest=DEFAULT_PLATFORM_MANIFEST):
    """Check the exact current rtl/e203 .v tree against a portable inventory."""
    platform, manifest_path = _absolute(platform), _absolute(platform_manifest)
    require(platform.is_dir(), 'development platform directory is missing')
    manifest_record = E.record(manifest_path)
    manifest = _json(manifest_path)
    require(isinstance(manifest, dict) and
            manifest.get('schema') == 'kwt-e203-development-platform-v1',
            'invalid development platform manifest schema')
    files = manifest.get('files')
    require(isinstance(files, list) and len(files) == 136, 'platform inventory must contain 136 sources')
    records, paths = [], []
    for item in files:
        require(isinstance(item, dict) and set(item) == {'path', 'sha256', 'size_bytes'},
                'malformed platform inventory record')
        name = item['path']
        require(isinstance(name, str) and name and '\\' not in name and
                not any(part in ('', '.', '..') for part in name.split('/')),
                'unsafe platform relative path')
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and relative.parts[:2] == ('rtl', 'e203') and
                len(relative.parts) > 2 and relative.suffix == '.v',
                'platform inventory member is outside rtl/e203 Verilog sources')
        path = _absolute(platform.joinpath(*relative.parts))
        require(path.is_relative_to(platform), 'platform source escapes selected root')
        records.append(_record({**item, 'path': str(path)}))
        paths.append(path)
    require(len(set(paths)) == len(paths), 'duplicate platform inventory path')
    rtl = _absolute(platform/'rtl/e203')
    require(rtl.is_dir(), 'platform rtl/e203 directory is missing')
    entries = list(rtl.rglob('*'))
    require(not any(path.is_symlink() for path in entries), 'linked member in platform RTL tree')
    actual = {path for path in entries if path.suffix == '.v' and path.is_file()}
    require(actual == set(paths), 'actual platform Verilog set differs from inventory')
    names = {path.name for path in paths}
    for path in paths:
        for include in re.findall(r'^\s*`include\s+"([^"]+)"', path.read_text(), re.M):
            require('/' not in include and '\\' not in include and include in names,
                    'unbound platform include: '+include)
    require(E.record(manifest_path) == manifest_record, 'platform manifest changed while validating')
    dependencies = [manifest_record, *records]
    return {'manifest': dependencies[0], 'sources': sorted(paths), 'dependencies': dependencies,
            'dependency_paths': [Path(item['path']) for item in dependencies]}


def _identity(identity, out):
    require(isinstance(identity, dict) and set(identity) ==
            {'schema', 'configuration', 'inputs', 'source_id'} and
            identity['schema'] == 'kwt-sram-source-identity-v1', 'invalid baseline source identity')
    payload = {key: value for key, value in identity.items() if key != 'source_id'}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                      allow_nan=False).encode()).hexdigest()
    require(identity['source_id'] == digest, 'canonical baseline source_id differs')
    path = out/'source_identity.json'
    require(_same(_json(path), identity), 'saved baseline source identity differs')
    require(_same(identity['configuration'], CONFIG), 'baseline source configuration differs')
    records = _records(identity['inputs'], 'source identity')
    require(all(set(item) == {'path', 'sha256', 'size_bytes'} for item in identity['inputs']),
            'source identity contains noncanonical file records')
    return [E.record(path), *records]


def _native(command, argv, out, name, timeout):
    C.clean_native(command, 0)
    fields = {'schema', 'status', 'argv', 'cwd', 'host', 'supervisor', 'started_utc',
              'timeout_seconds', 'timed_out', 'interrupted', 'exit_code', 'pid',
              'process_start_ticks', 'pid_namespace', 'boot_id', 'finished_utc',
              'elapsed_seconds', 'log', 'native_state'}
    require(isinstance(command, dict) and set(command) == fields,
            'complete native state fields differ: '+name)
    require(command.get('schema') == 'kwt-sram-command-v1', 'native schema differs: '+name)
    require(command.get('argv') == list(map(str, argv)) and command.get('cwd') == str(out),
            'native argv/cwd differs: '+name)
    require(type(command.get('timeout_seconds')) is int and command['timeout_seconds'] == timeout,
            'native timeout differs: '+name)
    for key, suffix in (('log', '.log'), ('native_state', '.command.json')):
        require(command[key]['path'] == str(out/(name+suffix)), 'native evidence path differs: '+name)
        _record(command[key])
    saved = _json(command['native_state']['path'])
    require(_same(saved, {key: value for key, value in command.items() if key != 'native_state'}),
            'complete native saved state differs: '+name)
    require(isinstance(command.get('started_utc'), str) and
            isinstance(command.get('finished_utc'), str) and
            command['started_utc'] <= command['finished_utc'] and
            type(command.get('elapsed_seconds')) in (int, float) and
            math.isfinite(command['elapsed_seconds']) and command['elapsed_seconds'] >= 0,
            'native completion metadata absent: '+name)
    for key in ('started_utc', 'finished_utc'):
        require(datetime.fromisoformat(command[key]).utcoffset() is not None,
                'native timestamp lacks timezone: '+name)
    for process in (command, command['supervisor']):
        require(isinstance(process, dict) and type(process.get('pid')) is int and process['pid'] > 0 and
                isinstance(process.get('process_start_ticks'), str) and
                re.fullmatch(r'\d+', process['process_start_ticks']) and
                isinstance(process.get('pid_namespace'), str) and
                re.fullmatch(r'pid:\[\d+\]', process['pid_namespace']) and
                isinstance(process.get('boot_id'), str) and
                re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', process['boot_id']),
                'native process identity metadata absent: '+name)
    require(isinstance(command['host'], str) and command['host'], 'native host metadata absent: '+name)
    text = C.verify_native(command)
    require(not PLAN.FAILURE.search(text) and not re.search(r'\berror:', text, re.I),
            'blocking native diagnostic: '+name)
    return text


def _tools(report, commands, out):
    tools = report['tools']
    require(isinstance(tools, dict) and set(tools) == {'gcc', 'objcopy', 'verilator'},
            'baseline tool set differs')
    dependencies = []
    paths = {}
    for name, entry in tools.items():
        require(entry.get('status') == 'PASS', 'baseline tool is not PASS: '+name)
        executable = _record(entry['executable'])
        paths[name] = Path(executable['path'])
        command = entry['command']
        expected_name = str(paths[name]) if name != 'verilator' else 'verilator'
        safe_name = re.sub(r'[^A-Za-z0-9_.+-]', '_', expected_name)
        require(command.get('argv') == [str(paths[name]), '--version'] and
                command.get('cwd') == str(ROOT) and type(command.get('exit_code')) is int and
                command['exit_code'] == 0 and command.get('timed_out') is False and
                type(command.get('timeout_seconds')) is int and command['timeout_seconds'] == 15,
                'baseline tool version command differs: '+name)
        log = _record(command['log'])
        require(log['path'] == str(out/('version-'+safe_name+'.log')),
                'baseline tool version log path differs: '+name)
        require(entry.get('version') == Path(log['path']).read_text(errors='replace').strip(),
                'baseline tool version text differs: '+name)
        dependencies += [executable, log]
    require(commands[0]['argv'][0] == str(paths['gcc']) and
            commands[1]['argv'][0] == str(paths['objcopy']), 'actual compiler/objcopy identity differs')
    require(paths['objcopy'] == paths['gcc'].with_name(paths['gcc'].name.replace('gcc', 'objcopy')),
            'objcopy does not belong to the selected compiler toolchain')
    return paths, dependencies


def _vectors(report, out, input_records):
    provenance = _records(report['vector_provenance'], 'vector provenance')
    manifests = []
    for item in provenance:
        path = Path(item['path'])
        if path.suffix == '.json':
            value = _json(path)
            if isinstance(value, dict) and value.get('schema') == 'kwt_ffn_export_v1':
                manifests.append(path)
    require(len(manifests) == 1 and manifests[0].name == 'manifest.json',
            'require one original export manifest in vector provenance')
    model = SOC.L.load_module('kwt_baseline_numeric', ROOT/'model/fixed16_acc48.py')
    manifest, fresh, images = SOC.E.validate_export(manifests[0].parent, model,
                                                  source_root=ROOT/'vendor/kwt1-237e4097')
    fresh_records = _records(fresh, 'revalidated vector provenance')
    require({item['path']: item for item in fresh_records} ==
            {item['path']: item for item in provenance}, 'vector export provenance coverage differs')
    require(report.get('vector_scope') == manifest['input']['kind'], 'baseline vector scope differs')
    require(isinstance(images, list) and len(images) == 12, 'baseline exported layer set differs')
    staged, payloads = [], []
    for layer, image in enumerate(images):
        require(isinstance(image, dict) and set(image) == set(SOC.E.MEMORY_SPECS),
                'baseline image roles differ')
        for role, (bits, count) in SOC.E.MEMORY_SPECS.items():
            path = _absolute(out/'vectors'/f'layer_{layer:02d}'/(role+'.mem'))
            require(str(path) in input_records, 'staged baseline vector is not bound: '+str(path))
            record = _record(input_records[str(path)])
            payload = path.read_bytes()
            require(isinstance(image[role], bytes) and payload == image[role],
                    'staged vector bytes differ from revalidated export: '+str(path))
            try:
                words = payload.decode('ascii').splitlines()
            except UnicodeDecodeError as exc:
                raise ValueError('staged vector is not ASCII: '+str(path)) from exc
            require(len(words) == count and
                    all(re.fullmatch(r'[0-9a-fA-F]{'+str(bits//4)+'}', word) for word in words),
                    'staged vector shape/known hex differs: '+str(path))
            staged.append(record)
            payloads.append(payload)
    entries = list((out/'vectors').rglob('*'))
    require(not any(path.is_symlink() for path in entries), 'linked staged vector member')
    require({path for path in entries if path.is_file()} == {Path(item['path']) for item in staged},
            'actual staged vector file set differs')
    workload = hashlib.sha256(b''.join(payloads)).hexdigest()
    require(report.get('workload_sha256') == workload, 'baseline workload SHA256 differs')
    return staged, provenance, workload


def verify_baseline(report_path, platform, *, platform_manifest=DEFAULT_PLATFORM_MANIFEST):
    """Fail closed on incomplete, altered or different-source behavioral evidence."""
    try:
        path = _absolute(report_path)
        out = path.parent
        report_record = E.record(path)
        report = _json(path)
        require(report.get('schema') == 'kwt-sram-soc-v2' and report.get('status') == 'PASS' and
                report.get('phase') == 'complete', 'baseline is not a complete behavioral SoC PASS')
        require(report.get('configuration') == CONFIG and
                all(type(report['configuration'][key]) is int for key in ('tasks', 'frequency_mhz', 'jobs')),
                'baseline configuration differs')
        require(report.get('scope') == SCOPE and report.get('measurement_scope') == MEASUREMENT_SCOPE and
                all(report.get(key) == 'BLOCKED' for key in ('official_platform', 'timing', 'area', 'power')),
                'baseline acceptance boundary differs')
        selected = verify_platform(platform, platform_manifest=platform_manifest)
        platform = _absolute(platform)
        rtl = platform/'rtl/e203'
        core, perips = rtl/'core', rtl/'perips'
        sources = selected['sources']
        originals = [rtl/'subsys/e203_subsys_perips.v', rtl/'soc/e203_soc_top.v']
        require(all(original in sources for original in originals), 'platform patch originals absent')
        substitutions = [('kwt_icb_slave u_kwt_accel', 'kwt_icb_slave_sram #(.SRAM_BACKEND(0)) u_kwt_accel'),
                         ('kwt_shared512_model u_kwt_shared', 'kwt_shared512_checked_model u_kwt_shared')]
        generated = {}
        for original, (needle, replacement) in zip(originals, substitutions):
            target = _absolute(out/original.name)
            require(target.read_bytes() == S.patch_once(original.read_text(), needle, replacement).encode(),
                    'private behavioral platform patch differs: '+str(target))
            generated[original] = target
        backend = SOURCES.select_backend('behavioral', 'simulation', root=ROOT,
                                         config_path=ROOT/'configs/sram-backends.json')
        common = [ROOT/name for name in COMMON]
        require(backend['value'] == 0 and backend['sources'] == common, 'behavioral common sources differ')
        compile_sources = [*common, *[ROOT/name for name in SOC_SOURCES],
                           *[generated.get(source, source) for source in sources]]
        fw = [ROOT/name for name in FW]
        expected_identity = set([*[ROOT/name for name in PRODUCERS], *compile_sources, *fw,
                                 *originals, *sorted(core.glob('*.vh'))])
        identity_dependencies = _identity(report['identity'], out)
        require({item['path'] for item in report['identity']['inputs']} ==
                {str(source) for source in expected_identity}, 'mandatory baseline source identity set differs')
        inputs = _records(report['inputs'], 'baseline input')
        lookup = {item['path']: item for item in inputs}
        for item in identity_dependencies[1:]:
            require(lookup.get(item['path']) == item, 'source identity is not covered by baseline inputs')
        commands = report['commands']
        require(isinstance(commands, list) and len(commands) == 4, 'baseline must contain four native commands')
        tools, tool_dependencies = _tools(report, commands, out)
        compiler, objcopy = tools['gcc'], tools['objcopy']
        firmware_argv = [compiler, '-march=rv32imac_zicsr_zifencei', '-mabi=ilp32', '-msmall-data-limit=0',
                         '-Os', '-ffreestanding', '-fno-builtin', '-nostdlib', '-Wl,--build-id=none',
                         '-DKWT_TASKS=12', '-I'+str(ROOT/'soc/include'), '-T', fw[2], fw[0], fw[1],
                         '-o', out/'firmware.elf']
        _native(commands[0], firmware_argv, out, 'firmware', 60)
        _native(commands[1], [objcopy, '-O', 'binary', out/'firmware.elf', out/'firmware.bin'],
                out, 'objcopy', 60)
        compile_argv = ['verilator', '--binary', '--timing', '--assert', '-Wno-fatal', '-Wno-PINMISSING',
                        '-Wno-PINCONNECTEMPTY', '--top-module', 'tb_e203_kwt_sram', '--Mdir', out/'obj',
                        '-o', 'simulation', '-j', '2', '--threads', '1', '-DDISABLE_SV_ASSERTION=1',
                        '-I'+str(core), '-I'+str(perips), '-I'+str(perips/'apb_i2c'), *compile_sources]
        compile_text = _native(commands[2], compile_argv, out, 'compile', 240)
        firmware = _records(report['firmware'], 'firmware')
        require([item['path'] for item in firmware] ==
                [str(out/name) for name in ('firmware.elf', 'firmware.bin', 'firmware.hex')],
                'baseline firmware artifact set differs')
        require((out/'firmware.elf').read_bytes().startswith(b'\x7fELF'), 'baseline firmware ELF header absent')
        data = (out/'firmware.bin').read_bytes()
        require(0 < len(data) <= 65536, 'baseline firmware BIN exceeds ITCM or is empty')
        expected_hex = ''.join(f'{byte:02x}\n' for byte in data.ljust(65536, b'\0')).encode('ascii')
        require((out/'firmware.hex').read_bytes() == expected_hex, 'baseline BIN/padded HEX payload differs')
        simulation = _record(report['simulation'])
        require(simulation['path'] == str(out/'obj/simulation') and simulation['size_bytes'] > 0,
                'baseline simulation binary differs')
        staged, provenance, workload = _vectors(report, out, lookup)
        expected_inputs = {str(source) for source in expected_identity} | {str(compiler), str(objcopy)}
        expected_inputs |= {item['path'] for item in [*staged, *firmware, simulation]}
        require(set(lookup) == expected_inputs, 'complete baseline input coverage differs')
        timeout = commands[3]['timeout_seconds']
        require(type(timeout) is int and 1 <= timeout <= 1800, 'baseline simulation timeout differs')
        text = _native(commands[3], [out/'obj/simulation', f'+VECTORS={out/"vectors"}',
                                    f'+FIRMWARE={out/"firmware.hex"}', '+TASKS=12'], out, 'run', timeout)
        measured = S.accept_soc(commands[3], text, 12)
        families = [line for line in text.splitlines() if 'PASS E203_SRAM_' in line]
        require(all(line.startswith(('PASS E203_SRAM_TASK ', 'PASS E203_SRAM_RECOVERY ',
                                     'PASS E203_SRAM_SUITE ')) for line in families),
                'unknown or prefixed SoC completion family')
        require(re.fullmatch(r'- '+re.escape(str(ROOT/'sim/tb_e203_kwt_sram.sv'))+
                             r':\d+: Verilog \$finish', text.rstrip().splitlines()[-1]),
                'baseline does not end with the native testbench finish')
        for key, value in measured.items():
            require(_same(report.get(key), value), 'recomputed baseline measurement differs: '+key)
        dependencies = _merge([report_record], selected['dependencies'], identity_dependencies,
                              inputs, provenance, tool_dependencies,
                              [item for command in commands for item in
                               (command['log'], command['native_state'])])
        for item in dependencies:
            _record(item)
        require(E.record(path) == report_record, 'baseline report changed while validating')
        return {'report': report_record, 'platform_manifest': selected['manifest'],
                'dependencies': dependencies,
                'dependency_paths': [Path(item['path']) for item in dependencies],
                'sources': sources, 'compile_text': compile_text, 'firmware': firmware,
                'source_id': report['identity']['source_id'], 'workload_sha256': workload,
                'measurement': measured, 'native_commands': 4,
                'scope': SCOPE, 'measurement_scope': MEASUREMENT_SCOPE}
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError('incomplete behavioral SoC baseline evidence: '+str(exc)) from exc
