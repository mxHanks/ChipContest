#!/usr/bin/env python3
"""Portable entry point for the selected 1064 RTL and final ECO evidence."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_name(name):
    path = PurePosixPath(name)
    require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts
            and '\\' not in name and str(path) == name, f'Unsafe path: {name!r}')
    return path


def repo_path(root, name):
    path = root.joinpath(*safe_name(name).parts)
    require(path.resolve().is_relative_to(root.resolve()), f'Path escapes repository: {name}')
    return path


def check_bytes(data, record, label):
    require(len(data) == record['bytes'] and hashlib.sha256(data).hexdigest() == record['sha256'],
            f'Byte/hash mismatch: {label}')


def candidate(root=ROOT):
    return json.loads((root / 'submission/candidate.json').read_text())


def archive_members(tar):
    members = tar.getmembers()
    names = [m.name for m in members]
    require(len(names) == len(set(names)), 'Duplicate archive member')
    for member in members:
        safe_name(member.name)
        require(member.isfile(), f'Non-regular archive member: {member.name}')
    return set(names)


def archive_delivery(root, selected):
    """Verify every catalog payload before returning the explicitly selected files."""
    evidence = selected['evidence']
    archive = repo_path(root, evidence['archive']['path'])
    check_bytes(archive.read_bytes(), evidence['archive'], 'final archive')
    delivery = {}
    with tarfile.open(archive, 'r:xz') as tar:
        names = archive_members(tar)
        require('execution-files.json' in names, 'Missing archive catalog')
        catalog = json.load(tar.extractfile('execution-files.json'))
        require(len(catalog) == evidence['catalog_files'], 'Unexpected archive catalog count')
        require(names == set(catalog) | {'execution-files.json'}, 'Archive/catalog member mismatch')
        for name, record in catalog.items():
            data = tar.extractfile(name).read()
            check_bytes(data, record, name)
            if name in evidence['delivery']:
                check_bytes(data, evidence['delivery'][name], name)
                delivery[name] = data
    allowed = {'apply/mapped.v', 'apply/mapped.sdc'}
    allowed.update('apply/' + 'seed-svf/' * depth + 'eco.svf' for depth in range(7))
    allowed.add('apply/' + 'seed-svf/' * 6 + 'seed-hold.svf')
    require(set(delivery) == set(evidence['delivery']) == allowed, 'Unexpected delivery selection')
    return delivery


def vector_delivery(root, selected):
    vectors = selected['vectors']
    archive = repo_path(root, vectors['archive']['path'])
    check_bytes(archive.read_bytes(), vectors['archive'], 'vector archive')
    delivery = {}
    with tarfile.open(archive, 'r:xz') as tar:
        names = archive_members(tar)
        expected = {vectors['member_prefix'] + name for name in vectors['delivery']}
        require({name for name in names if name.startswith(vectors['member_prefix'])} == expected,
                'Unexpected vector archive members')
        for name, record in vectors['delivery'].items():
            safe_name(name)
            data = tar.extractfile(vectors['member_prefix'] + name).read()
            check_bytes(data, record, name)
            delivery[name] = data
    require(hashlib.sha256(delivery['vectors-manifest.json']).hexdigest() == vectors['manifest_sha256'],
            'Wrong vector manifest')
    return delivery


def check_submodule(root, selected):
    rtl = selected['rtl']
    child = repo_path(root, rtl['path'])
    def git(directory, *args):
        return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()
    indexed = git(root, 'ls-files', '--stage', rtl['path']).split()
    require(len(indexed) >= 4 and indexed[0] == '160000' and indexed[1] == rtl['commit'],
            'Parent gitlink does not select the current RTL')
    require(git(child, 'rev-parse', '--show-toplevel') == str(child.resolve()),
            'RTL submodule is not initialized; run git submodule update --init --recursive')
    require(git(child, 'rev-parse', 'HEAD') == rtl['commit'], 'Wrong RTL submodule commit')
    require(not git(child, 'status', '--porcelain'), 'RTL submodule has local modifications')


def check_performance(root, selected):
    performance = selected['performance']
    for name, record in performance.items():
        check_bytes(repo_path(root, record['path']).read_bytes(), record, 'performance ' + name)
    measured = json.loads(repo_path(root, performance['result']['path']).read_text(), parse_float=Decimal)
    require(measured['status'] == 'PASS' and measured['source_drift'] == [], 'Performance run did not pass')
    results = selected['results']
    tasks = results['rtl_tasks']
    require(tasks == measured['arguments']['tasks'] == len(measured['layers']) == 12,
            'Performance task count differs')
    require(measured['arguments']['load_pipeline'] == 1 and measured['arguments']['warmup'],
            'Performance measurement mode differs')
    spec = importlib.util.spec_from_file_location('current_performance_checker',
                                                repo_path(root, performance['checker']['path']))
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    log = repo_path(root, performance['simulation_log']['path']).read_text()
    checked = checker.check_log(log, tasks, 8, warmup=True, x_macros=True)
    for field, metadata in [('total_cycles', 'rtl_cycles'), ('outputs', 'exact_y32_outputs')]:
        require(measured[field] == checked[field] == results[metadata], f'Performance {metadata} differs')
    frequency = results['assumed_frequency_hz']
    require(frequency == measured['clock']['throughput_conversion_hz'] == 150000000,
            'Performance frequency assumption differs')
    require(measured['vectors_manifest_sha256'] == selected['vectors']['manifest_sha256'],
            'Performance vector identity differs')
    rate = Decimal(str(results['conditional_tasks_per_second']))
    recorded = measured['task_per_second_at_assumed_150mhz']
    formula = Decimal(frequency) * tasks / results['rtl_cycles']
    require(rate.is_finite() and rate == recorded and abs(rate - formula) <= Decimal('1e-10'),
            'Performance throughput formula differs')


def check_area(base, results):
    rows = list(csv.DictReader((base / 'apply/area-upper-bound.tsv').read_text().splitlines(), delimiter='\t'))
    values = {row['component']: Decimal(row['area_library_units']) for row in rows}
    fields = {'ALL_FULL_SOC_STANDARD_CELLS': 'standard_cell_area_native_library_units',
              'ALL_33_INTERNAL_SRAM': 'internal_33_sram_area_native_library_units',
              'CONSERVATIVE_UPPER_BOUND': 'conservative_area_upper_bound_native_library_units'}
    require(len(rows) == len(values) == 3 and set(values) == set(fields), 'Area accounting components differ')
    for component, field in fields.items():
        area = Decimal(str(results[field]))
        require(area.is_finite() and area == values[component], f'Area metadata differs: {field}')
    require(values['CONSERVATIVE_UPPER_BOUND'] == values['ALL_FULL_SOC_STANDARD_CELLS'] + values['ALL_33_INTERNAL_SRAM'],
            'Area upper-bound formula differs')


def verify(root=ROOT, selected=None, submodule=False):
    selected = selected or candidate(root)
    evidence = selected['evidence']
    manifest_path = repo_path(root, evidence['manifest']['path'])
    check_bytes(manifest_path.read_bytes(), evidence['manifest'], 'published evidence manifest')
    manifest = json.loads(manifest_path.read_text())
    base = repo_path(root, evidence['directory'])
    for name, record in manifest.items():
        check_bytes(repo_path(base, name).read_bytes(), record, name)
    for name, record in selected['entrypoints'].items():
        check_bytes(repo_path(root, record['path']).read_bytes(), record, name)
    record = selected['vectors']['checker']
    check_bytes(repo_path(root, record['path']).read_bytes(), record, 'vector checker')
    archive_delivery(root, selected)
    review = json.loads((base / 'independent-native-review.json').read_text())
    coverage = review['coverage']
    results = selected['results']
    check_performance(root, selected)
    check_area(base, results)
    for key in ('numeric_violations', 'electrical_violations'):
        expected = results['numeric_timing_violations' if key == 'numeric_violations' else key]
        require(coverage[key] == expected == 0, f'Unexpected {key}')
    require(len(coverage['unknown_checks']) == results['unknown_checks'] == 4,
            'Unknown timing checks must remain explicit')
    report = (base / 'reload/persisted-coverage.rpt').read_text()
    totals = re.search(r'^All Checks\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)', report, re.M)
    require(totals is not None, 'Missing native STA totals')
    expected_totals = tuple(results[key] for key in ('total_checks', 'met_checks', 'numeric_timing_violations', 'untested_checks'))
    require(tuple(map(int, totals.groups())) == expected_totals, 'Native STA totals differ')
    require(len(re.findall(r'\buntested\s+unknown\s*$', report, re.M)) == results['unknown_checks'],
            'Native unknown count differs')
    drc = (base / 'reload/persisted-all_violators.rpt').read_text()
    require('Report : constraint' in drc and not re.search(r'\bVIOLATED\b', drc, re.I),
            'Native constraint report contains violations')
    proof = json.loads((base / 'mapped-structural-equivalence.json').read_text())
    require(proof['status'] == 'FINAL_MAPPED_DEAD_CONE_AND_BUFFER_EQUIVALENCE_PASS'
            and proof['preserved_original_SRAM_count'] == results['preserved_sram_macros'] == 353,
            'Mapped structural proof or SRAM count differs')
    require(review['final_mapped_sha256'] == evidence['delivery']['apply/mapped.v']['sha256'],
            'Review and final map differ')
    if submodule:
        check_submodule(root, selected)
    return {'status': 'EVIDENCE_VERIFIED_NOT_SIGNOFF', 'candidate': selected['candidate'],
            'archive_payload_files': evidence['catalog_files'],
            'submodule': 'VERIFIED' if submodule else 'NOT_CHECKED_USE_--submodule',
            'numeric_violations': 0, 'electrical_violations': 0, 'unknown_checks': 4}


def write_delivery(data, out):
    # The caller verifies the complete selection before creating any output.
    out = out.absolute()
    require(not out.exists() and not out.is_symlink(), f'Output already exists: {out}')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.mkdir()  # Atomic refusal if another process creates this path.
    try:
        for name, payload in data.items():
            target = out.joinpath(*safe_name(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(payload)
    except Exception:
        shutil.rmtree(out)
        raise
    return {'status': 'VERIFIED_DELIVERY_EXTRACTED_NOT_SIGNOFF', 'out': str(out), 'files': sorted(data)}


def unpack(root, selected, out):
    return write_delivery(archive_delivery(root, selected), out)


def execution_command(root, selected, args):
    command = [sys.executable, '-B', str(repo_path(root, selected['entrypoints'][args.action]['path']))]
    if args.action == 'cpu':
        command += ['--vectors', str(args.vectors.resolve()), '--out', str(args.out.resolve()),
                    '--tasks', str(args.tasks), '--warmup', '--load-pipeline', '1',
                    '--jobs', str(args.jobs), '--cross-prefix', args.cross_prefix]
    return command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('info', help='Show selected identities and qualification limits; no verification')
    check = commands.add_parser('verify', help='Read-only SHA and native-report verification; no EDA or network')
    check.add_argument('--submodule', action='store_true', help='Also require the exact initialized, clean RTL child')
    commands.add_parser('ingress', help='Verify selected RTL, then run current Icarus ingress regression')
    vectors = commands.add_parser('vectors', help='Recover the bound twelve-task vectors; no model/audio download')
    vectors.add_argument('--out', type=Path, default=ROOT / 'build/1064/vectors')
    vector_check = commands.add_parser('check-vectors', help='Check vector provenance and all integer MAC/Y32 values')
    vector_check.add_argument('--vectors', type=Path, required=True)
    cpu = commands.add_parser('cpu', help='Run current RTL full-task measurement; requires recovered vectors/toolchain')
    cpu.add_argument('--vectors', type=Path, required=True)
    cpu.add_argument('--out', type=Path, required=True)
    cpu.add_argument('--tasks', type=int, choices=range(1, 13), default=12)
    cpu.add_argument('--jobs', type=int, choices=(1, 2), default=2)
    cpu.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    extract = commands.add_parser('unpack-mapped', help='Verify and extract only final mapped.v, SDC and eight SVFs')
    extract.add_argument('--out', type=Path, default=ROOT / 'build/submission/current-mapped')
    args = parser.parse_args(argv)
    try:
        selected = candidate()
        if args.action == 'info':
            print(json.dumps({'status': 'IDENTITY_ONLY_NOT_CHECKED', **selected}, ensure_ascii=False, indent=2))
        elif args.action == 'verify':
            print(json.dumps(verify(submodule=args.submodule), ensure_ascii=False, indent=2))
        elif args.action == 'unpack-mapped':
            print(json.dumps(unpack(ROOT, selected, args.out), indent=2))
        elif args.action == 'vectors':
            print(json.dumps(write_delivery(vector_delivery(ROOT, selected), args.out), indent=2))
        elif args.action == 'check-vectors':
            checker = selected['vectors']['checker']
            path = repo_path(ROOT, checker['path'])
            check_bytes(path.read_bytes(), checker, 'vector checker')
            manifest = args.vectors / 'vectors-manifest.json'
            require(hashlib.sha256(manifest.read_bytes()).hexdigest() == selected['vectors']['manifest_sha256'],
                    'Wrong selected vector manifest')
            return subprocess.run([sys.executable, '-B', str(path), '--vectors', str(args.vectors.resolve())], cwd=ROOT).returncode
        else:
            verify(submodule=True)
            if args.action == 'cpu':
                manifest = args.vectors / 'vectors-manifest.json'
                require(hashlib.sha256(manifest.read_bytes()).hexdigest() == selected['vectors']['manifest_sha256'],
                        'CPU must use the selected twelve-task vector manifest')
            command = execution_command(ROOT, selected, args)
            print(json.dumps({'command': command, 'scope': 'RTL_ENGINEERING_MEASUREMENT_NOT_GATE_DELAY_SIGNOFF'}), flush=True)
            return subprocess.run(command, cwd=ROOT).returncode
        return 0
    except (ValueError, OSError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f'current: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
