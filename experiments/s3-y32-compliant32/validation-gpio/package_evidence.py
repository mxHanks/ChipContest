#!/usr/bin/env python3
"""Package completed production GPIO task0/full12/wait31 evidence, without PPA claims."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {str(path.relative_to(directory)): sha(path) for path in sorted(directory.rglob('*'))
            if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--followups', type=Path, required=True)
    parser.add_argument('--vectors', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    base, followups, vectors, out = [value.resolve() for value in
                                    (args.base, args.followups, args.vectors, args.out)]
    if out.exists():
        parser.error('delivery output must be new')
    original = json.loads((base / 'result.json').read_text())
    chain = json.loads((followups / 'receipt.json').read_text())
    if (original.get('status') != 'PASS' or original.get('outputs') != 25344 or
            chain.get('status') != 'PASS' or chain.get('base_result_sha256') != sha(base / 'result.json')):
        raise ValueError('completed and bound GPIO task0/followups required')
    if inventory(base / 'source') != original['source_sha256']:
        raise ValueError('original source changed')
    if inventory(vectors) != original['vector_byte_sha256']:
        raise ValueError('original vectors changed')
    for name, key in [('dma_day_soc', 'elf_sha256'), ('dma_day_soc.verilog', 'image_sha256')]:
        if sha(base / 'firmware' / name) != original['firmware'][key]:
            raise ValueError('original firmware changed')
    if sha(base / 'simulator/sysbus32_gpio_soc') != original['simulator_sha256']:
        raise ValueError('original simulator changed')
    cases = ['full12', 'dma-first-wait31', 'load-first-wait31']
    results = {}
    for name in cases:
        run = followups / name
        result = json.loads((run / 'result.json').read_text())
        if (result.get('status') != 'PASS' or result['simulator_sha256'] != original['simulator_sha256'] or
                result['source_sha256'] != original['source_sha256'] or
                result['vectors_manifest_sha256'] != original['vectors_manifest_sha256'] or
                result.get('storage_binding') != original.get('storage_binding') or
                result['firmware']['elf_sha256'] != original['firmware']['elf_sha256'] or
                result['firmware']['image_sha256'] != original['firmware']['image_sha256'] or
                sha(run / 'result.json') != chain['results'][name]['result_sha256']):
            raise ValueError('followup frozen identity differs: ' + name)
        if result['outputs'] != (304128 if name == 'full12' else 25344):
            raise ValueError('followup output scope differs: ' + name)
        results[name] = result
    out.mkdir(parents=True)
    bundle = out / 'gpio-frozen'
    bundle.mkdir()
    shutil.copytree(base / 'source', bundle / 'source')
    shutil.copytree(base / 'firmware', bundle / 'firmware')
    shutil.copytree(vectors, bundle / 'vectors')
    evidence = bundle / 'evidence'
    evidence.mkdir()
    for name in ['result.json', 'simulation.log', 'simulation.process.json', 'simulator-build.log',
                 'simulator-build.process.json', 'source-manifest.json', 'rtl.f']:
        shutil.copy2(base / name, evidence / name)
    shutil.copy2(followups / 'receipt.json', evidence / 'followups-receipt.json')
    for label, run_directory in [('task0', base), ('followups', followups)]:
        supervisor = run_directory.with_name(run_directory.name + '-supervisor')
        if supervisor.exists():
            state = json.loads((supervisor / 'state.json').read_text())
            if state.get('status') != 'PASS':
                raise ValueError('present supervisor is not terminal PASS: ' + label)
            shutil.copytree(supervisor, evidence / ('supervisor-' + label))
    for name in cases:
        destination = evidence / 'followups' / name
        destination.mkdir(parents=True)
        for item in ['result.json', 'simulation.log', 'simulation.process.json']:
            shutil.copy2(followups / name / item, destination / item)
        shutil.copy2(followups / (name + '.driver.log'), destination / 'driver.log')
    shutil.copy2(HERE / 'reproduce_frozen.py', bundle / 'reproduce_frozen.py')
    (bundle / 'README.md').write_text(
        '# Production GPIO functional evidence\n\n'
        'Generic SRAM models, original two-owner 32-bit SystemBus, CPU GPIO/LSU/BIU loader.\n'
        'All tensor values enter only existing GPIO pads. Only firmware initializes ITCM.\n'
        'task0, full12 and both wait31 cases used one identical proven binary and firmware.\n'
        'Timing spans first GPIO data through last Y response; conservative clear-through-Y is also reported.\n'
        'This bundle does not establish area, STA, mapped functional equivalence, power or formal contest qualification.\n\n'
        'Verify exact files, integer MAC/RNE and raw logs:\n\n'
        '```bash\n'
        'python3 -B reproduce_frozen.py --bundle . --verify-only --case full12\n'
        '```\n\n'
        'Choose `task0`, `full12`, `dma-first-wait31` or `load-first-wait31`. '
        'For a new local build/simulation, replace `--verify-only` with `--out /absolute/new/directory`.\n')
    (bundle / 'files.json').write_text(json.dumps(inventory(bundle), indent=2, sort_keys=True) + '\n')
    verified = {}
    for name in ['task0', *cases]:
        done = subprocess.run([sys.executable, '-B', str(bundle / 'reproduce_frozen.py'),
            '--bundle', str(bundle), '--verify-only', '--case', name], capture_output=True, text=True, check=True)
        verified[name] = json.loads(done.stdout)
    archive = out / 'gpio-frozen.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        stream.add(bundle, arcname=bundle.name)
    receipt = dict(status='PASS_FROZEN_FILES_INTEGER_ORACLE_AND_RAW_LOG_REPLAY_NOT_NEW_SIMULATION',
        packager_sha256=sha(Path(__file__)), reproducer_sha256=sha(HERE / 'reproduce_frozen.py'),
        base_result_sha256=sha(base / 'result.json'), followups_receipt_sha256=sha(followups / 'receipt.json'),
        source_files=len(original['source_sha256']), configuration=original['x_sram_configuration'],
        storage_binding=original.get('storage_binding'), full12_outputs=results['full12']['outputs'],
        full12_total_cycles=results['full12']['total_cycles'],
        full12_gpio_input_to_y_cycles=results['full12']['gpio_input_to_y_cycles'],
        verified=verified, archive=str(archive), archive_sha256=sha(archive),
        files_sha256=sha(bundle / 'files.json'))
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: receipt[key] for key in ['status', 'full12_outputs', 'full12_total_cycles', 'archive_sha256']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
