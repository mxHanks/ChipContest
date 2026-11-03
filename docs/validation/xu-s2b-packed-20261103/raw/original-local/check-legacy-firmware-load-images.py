#!/usr/bin/env python3
"""Compare S2a HEAD and current legacy load images using the installed RV32 compiler."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import types

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / 'tools/scripts/xu_firmware_contract.py').is_file())
OUT = Path(__file__).resolve().parent
ARTIFACTS = OUT / 'legacy-firmware-load-image-equality'
ARTIFACTS.mkdir(parents=True, exist_ok=True)
PREFIX = 'riscv64-unknown-elf-'


def run(command, cwd=None):
    return subprocess.check_output(command, cwd=cwd or ROOT, text=True, stderr=subprocess.STDOUT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


head = run(['git', 'rev-parse', '3c13930']).strip()
prior = types.ModuleType('s2a_contract')
exec(run(['git', 'show', head + ':tools/scripts/xu_firmware_contract.py']), prior.__dict__)
spec = importlib.util.spec_from_file_location('current_contract', ROOT / 'tools/scripts/xu_firmware_contract.py')
current = importlib.util.module_from_spec(spec)
spec.loader.exec_module(current)

frozen = ARTIFACTS / 'sources-head'
updated = ARTIFACTS / 'sources-current'
frozen.mkdir(exist_ok=True)
updated.mkdir(exist_ok=True)
for name in run(['git', 'ls-tree', '-r', '--name-only', head, 'tests/e203/firmware']).splitlines():
    source = Path(name)
    relative = source.relative_to('tests/e203/firmware')
    old_path = frozen / relative
    new_path = updated / relative
    old_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(subprocess.check_output(['git', 'show', head + ':' + name], cwd=ROOT))
    shutil.copyfile(ROOT / source, new_path)

report = dict(status='RUNNING', base_commit=head,
              base_reference='S2a commit before packed firmware changes',
              current_commit=run(['git', 'rev-parse', 'HEAD']).strip(),
              timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              scope='Loadable binary equality for every pre-pack32 schedule; no cycle or RTL equivalence claim',
              comparison_format='riscv64-unknown-elf-objcopy -O binary',
              compiler=shutil.which(PREFIX + 'gcc'),
              compiler_version=run([PREFIX + 'gcc', '--version']).splitlines()[0],
              objcopy_version=run([PREFIX + 'objcopy', '--version']).splitlines()[0],
              source_snapshots={label: {str(p.relative_to(directory)): sha(p)
                                       for p in sorted(directory.rglob('*')) if p.is_file()}
                                for label, directory in [('HEAD', frozen), ('current', updated)]},
              comparisons=[])
report['changed_source_files'] = [name for name, digest in report['source_snapshots']['HEAD'].items()
                                  if report['source_snapshots']['current'][name] != digest]
for schedule in prior.SCHEDULES:
    for optimization, experiment in [('-Os', 'none'), ('-O2', 'both-unroll-no-masks')]:
        config = prior.configuration(schedule, optimization, experiment)
        old_defines = prior.compiler_defines(config)
        new_defines = current.compiler_defines(config)
        assert old_defines == new_defines, config
        comparison = dict(configuration=config, compiler_defines_identical=True, images={})
        for label, sources, defines in [('HEAD', frozen, old_defines), ('current', updated, new_defines)]:
            directory = ARTIFACTS / schedule / (optimization[1:] + '-' + experiment) / label
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / 'accel_soc.elf'
            binary = directory / 'accel_soc.bin'
            command = [PREFIX + 'gcc', '-march=rv32imac_zicsr2p0_zifencei2p0', '-mabi=ilp32',
                       optimization, *defines, '-fstack-usage', '-ffreestanding', '-fno-builtin',
                       '-msmall-data-limit=0', '-nostdlib', '-nostartfiles', '-static',
                       '-mcmodel=medany', '-Wl,--no-relax', '-T', str(sources / 'link.ld'),
                       *[str(sources / name) for name in ['start.S', 'main.c', 'accel.c']],
                       '-o', str(target)]
            (directory / 'compiler.log').write_text(run(command, directory))
            objcopy = [PREFIX + 'objcopy', '-O', 'binary', str(target), str(binary)]
            (directory / 'objcopy.log').write_text(run(objcopy, directory))
            comparison['images'][label] = dict(compiler_command=command, objcopy_command=objcopy,
                                                cwd=str(directory), elf_sha256=sha(target),
                                                binary_path=str(binary), binary_sha256=sha(binary),
                                                binary_bytes=binary.stat().st_size)
        old_image = Path(comparison['images']['HEAD']['binary_path'])
        new_image = Path(comparison['images']['current']['binary_path'])
        comparison['loadable_bytes_identical'] = old_image.read_bytes() == new_image.read_bytes()
        report['comparisons'].append(comparison)
        assert comparison['loadable_bytes_identical'], config
        print(f'{schedule} {optimization} {experiment}: equal {new_image.stat().st_size} bytes {sha(new_image)}', flush=True)
report.update(status='PASS', comparison_count=len(report['comparisons']),
              compiler_invocations=2 * len(report['comparisons']), all_loadable_images_identical=True)
path = OUT / 'legacy-firmware-load-image-equality.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS {len(report["comparisons"])} comparison pairs; {path}', flush=True)
