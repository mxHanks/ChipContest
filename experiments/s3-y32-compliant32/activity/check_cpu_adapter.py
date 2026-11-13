#!/usr/bin/env python3
"""Replay the existing SRAM contract suites with sealed adapter and generic model.

This is a four-state functional comparison, not a vendor model qualification.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(schema='compliant32-generic-cpu-sram-adapter-contract-v1', status='RUNNING',
                  started_at=datetime.now(timezone.utc).isoformat(), runner_sha256=sha(Path(__file__)),
                  scope='Four-state generic macro model, exact sealed PPA CPU adapter vs frozen original behavioral model; no vendor timing/power claim', suites={})
    try:
        pinned = json.loads((package / 'package-files.json').read_text())
        source = out / 'source'
        source.mkdir()
        inputs = {
            'adapter.sv': package / 'source/rtl/general/sirv_sim_ram.v',
            'generic_model.sv': package / 'local-only/generic_ramsp_non_ppa.sv',
            'original.v': ROOT / 'build/compliant32-20261113/cpu-xmacro-task0-r1/source/rtl/general/sirv_sim_ram.v',
            'tb_xu_sram_adapter.sv': ROOT / 'tools/ppa/tb_xu_sram_adapter.sv',
            'tb_xu_sram_geometry.sv': ROOT / 'tools/ppa/tb_xu_sram_geometry.sv',
        }
        for name in ('source/rtl/general/sirv_sim_ram.v', 'local-only/generic_ramsp_non_ppa.sv'):
            if sha(package / name) != pinned[name]:
                raise ValueError('sealed package input drift: ' + name)
        for name, path in inputs.items():
            shutil.copy2(path, source / name)
        original = (source / 'original.v').read_text()
        if original.count('module sirv_sim_ram ') != 1:
            raise ValueError('reference module rename seam differs')
        (source / 'reference.sv').write_text(original.replace('module sirv_sim_ram ', 'module xu_reference_sirv_sim_ram '))
        report['input_origins'] = {name: dict(path=str(path), sha256=sha(path)) for name, path in inputs.items()}
        report['source_sha256'] = {path.name: sha(path) for path in source.iterdir()}
        report['package_files_sha256'] = sha(package / 'package-files.json')
        for label, top, marker, count in [
            ('exhaustive2048', 'tb_xu_sram_adapter', 'XU_SRAM_ADAPTER_CONTRACT_PASS ', 2),
            ('platform_geometry', 'tb_xu_sram_geometry', 'XU_SRAM_GEOMETRY_PASS ', 6),
        ]:
            directory = out / label
            directory.mkdir()
            binary = directory / 'simulation.vvp'
            commands = [
                ['iverilog', '-g2012', '-s', top, '-o', str(binary), str(source / 'generic_model.sv'),
                 str(source / 'adapter.sv'), str(source / 'reference.sv'), str(source / (top + '.sv'))],
                ['vvp', str(binary)],
            ]
            for stage, command in zip(('compile', 'simulation'), commands):
                with (directory / (stage + '.log')).open('w') as stream:
                    stream.write(json.dumps(dict(command=command)) + '\n')
                    stream.flush()
                    subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=600)
            log = (directory / 'simulation.log').read_text()
            if log.count(marker) != count:
                raise ValueError('suite completion differs: ' + label)
            report['suites'][label] = dict(status='PASS', commands=commands,
                binary_sha256=sha(binary), logs={path.name: sha(path) for path in directory.glob('*.log')})
        if report['source_sha256'] != {path.name: sha(path) for path in source.iterdir()}:
            raise ValueError('source drift during contract checks')
        report['status'] = 'PASS_GENERIC_FUNCTIONAL_CONTRACT_NOT_VENDOR_QUALIFIED'
    except Exception as error:
        report.update(status='FAIL', error=str(error))
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(report['status'])


if __name__ == '__main__':
    main()
