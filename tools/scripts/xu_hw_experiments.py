#!/usr/bin/env python3
"""Run serial H1/H2 experiments against the accepted xu software baseline.

The same extended RTL is used in every case; firmware selects legacy, bias-cache,
result-window, or combined paths. VCS retention requires exact B0 image/cycles,
strict total-cycle improvement and full server acceptance. Local runs are provisional.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import e203_soc as soc
import xu_firmware_contract as contract
import xu_fw_experiments as firmware
import xu_perf_report as perf

ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = '499ba54bd57db81c058ab5efe25def226ec6dd15'
BASELINE_RESULT = 'docs/validation/xu-fw-optimization-20261102/server-json/acceptance/real12/result.json'
BASELINE_CYCLES = 25251416
RUNTIME_PATHS = ['src', 'tests/e203', 'tools/scripts', 'project.scala', 'tools/model/export_kwt.py', 'model']
FIXED_PATHS = ['tests/e203/vectors', 'model', 'tools/model/export_kwt.py',
               'tests/e203/firmware/main.c', 'tests/e203/firmware/start.S', 'tests/e203/firmware/link.ld']
sha = firmware.sha
comparison = firmware.comparison
better = firmware.better
execute = firmware.execute


def git_output(arguments, cwd=ROOT):
    # The server uses Git 1.8; use cwd rather than git -C.
    return subprocess.check_output(['git', *arguments], cwd=str(cwd))


def frozen_files(root=ROOT):
    names = git_output(['ls-tree', '-r', '--name-only', BASELINE_COMMIT, '--', *FIXED_PATHS], root).decode().splitlines()
    if not names:
        raise ValueError('accepted software baseline is unavailable')
    return {name: hashlib.sha256(git_output(['show', BASELINE_COMMIT + ':' + name], root)).hexdigest()
            for name in names}


def tracked_sources(root, paths):
    if git_output(['diff', '--name-only', 'HEAD', '--', *paths], root).strip():
        raise ValueError('tracked runtime source is dirty: ' + str(root))
    if git_output(['ls-files', '--others', '--exclude-standard', '--', *paths], root).strip():
        raise ValueError('runtime source has untracked files: ' + str(root))
    names = git_output(['ls-files', '--', *paths], root).decode().splitlines()
    return {name: sha(root / name) for name in names if (root / name).is_file()}


def source_identity():
    fixed = frozen_files()
    for name, digest in fixed.items():
        if sha(ROOT / name) != digest:
            raise ValueError('fixed vectors/numeric/startup source differs from 499ba54: ' + name)
    e203_commit = soc.verify_submodule(ROOT, soc.E203)
    main = tracked_sources(ROOT, RUNTIME_PATHS)
    rtl = tracked_sources(soc.E203, ['rtl'])
    if not main or not rtl:
        raise ValueError('runtime source inventory is incomplete')
    revision = git_output(['log', '-1', '--format=%H%n%P'], ROOT).decode().splitlines()
    return dict(commit=revision[0], parent_commits=revision[1].split() if len(revision) > 1 else [],
                e203_commit=e203_commit, fixed_baseline_commit=BASELINE_COMMIT,
                fixed_sha256=fixed,
                source_sha256=dict(main, **{'third-party/e203_hbirdv2/' + name: digest
                                           for name, digest in rtl.items()}))


def check_server_baseline(record):
    historical = json.loads(git_output(['show', BASELINE_COMMIT + ':' + BASELINE_RESULT]).decode())
    layers = record['summary']['layers']
    measured = [(row['cycles'], row['firmware_cycles']) for row in layers]
    expected = [(row['cycles'], row['firmware_cycles']) for row in historical['layers']]
    if record['summary']['aggregate']['cycles'] != BASELINE_CYCLES or measured != expected:
        raise ValueError('B0-new-RTL does not reproduce historical per-layer cycles and 25,251,416 total cycles')
    if record['cases'][-1]['firmware_build'].get('image_sha256') != historical['firmware_image_sha256']:
        raise ValueError('B0-new-RTL image differs from the accepted software baseline')
    # ELF bytes are recorded, but compiler temporary FILE symbols can change them.


class Campaign(firmware.Campaign):
    """Reuse serial execution/evidence capture; do not invoke the software source guard."""
    def __init__(self, out, sim, cross_prefix, accept=False, runner=execute):
        self.out, self.sim, self.prefix = out, sim, cross_prefix
        self.accept, self.runner = accept, runner
        self.identity = source_identity()
        self.environment = None
        self.vectors = {}
        self.report = dict(schema='xu-hardware-experiments-v1', status='RUNNING',
                           started_utc=firmware.timestamp(), simulator=sim, cross_prefix=cross_prefix,
                           baseline_commit=BASELINE_COMMIT, baseline_server_cycles=BASELINE_CYCLES,
                           source=self.identity, experiments=[], retained_optimization=False,
                           retention_status='provisional' if sim != 'vcs' else 'pending-acceptance',
                           scope='same extended RTL in all cases; independent firmware selection of bias cache '
                                 'and result window; fixed numeric/vector/work/timing boundary; 12 independent FFN1 tasks',
                           ppa_scope='runtime path isolation does not isolate gate area; compare complete old '
                                     'wrapper/core with complete new hardware under identical synthesis constraints')

    def check_source(self):
        if source_identity() != self.identity:
            raise ValueError('source or submodule changed during hardware campaign')

    def validate_case(self, result, directory, mode, tasks, config):
        if (result.get('status') != 'PASS' or result.get('mode') != mode or result.get('tasks') != tasks or
                result.get('simulator') != self.sim):
            raise ValueError('run status, workload or simulator mismatch')
        if (contract.configuration_from_result(result) != config or
                result.get('firmware_build', {}).get('configuration') != config):
            raise ValueError('requested, compiled and measured firmware configurations differ')
        if result.get('outputs') != tasks * 25344 or result.get('write_words') != tasks * 50688:
            raise ValueError('incomplete numerical output or writeback')
        logs = result.get('log_sha256', {})
        if 'simulation.log' not in logs:
            raise ValueError('original simulation log identity is missing')
        for name, digest in logs.items():
            if Path(name).name != name or sha(directory / name) != digest:
                raise ValueError('original log hash mismatch: ' + name)
        layers = soc.check_log((directory / 'simulation.log').read_text(errors='replace'), tasks)
        counters = soc.check_performance((directory / 'simulation.log').read_text(errors='replace'), layers,
                                        config['schedule'])
        for layer, measured in zip(layers, counters):
            layer['performance'] = measured
        if layers != result.get('layers'):
            raise ValueError('result differs from the complete original simulation log')
        if (result.get('main_commit') != self.identity['commit'] or
                result.get('e203_commit') != self.identity['e203_commit']):
            raise ValueError('run used a different main/submodule revision')
        sources = self.identity['source_sha256']
        for field, path in [('runner_sha256', 'tools/scripts/e203_soc.py'),
                            ('contract_sha256', 'tools/scripts/xu_firmware_contract.py')]:
            if result.get(field) != sources.get(path):
                raise ValueError('runtime measurement source identity differs: ' + field)
        rtl = result.get('source_sha256', {})
        if not rtl:
            raise ValueError('RTL/TB identities are missing')
        expected_rtl = {name for name in sources
                        if name.startswith('third-party/e203_hbirdv2/rtl/e203/') and
                        Path(name).suffix in ['.v', '.sv']}
        expected_rtl.add('tests/e203/tb_accel_soc.sv')
        if {name.replace('/vsim/install/rtl/', '/rtl/e203/') for name in rtl} != expected_rtl:
            raise ValueError('installed RTL/TB source inventory is incomplete')
        for name, digest in rtl.items():
            original = name.replace('/vsim/install/rtl/', '/rtl/e203/')
            if sources.get(original) != digest:
                raise ValueError('installed RTL/TB differs from source snapshot: ' + name)
        expected_firmware = {Path(name).name: digest for name, digest in sources.items()
                             if name.startswith('tests/e203/firmware/')}
        built = result['firmware_build']
        if built.get('source_sha256') != expected_firmware or result.get('firmware_sha256') != expected_firmware:
            raise ValueError('firmware source differs from source snapshot')
        for field, path in [('elf', directory / 'accel_soc'), ('image', directory / 'accel_soc.verilog')]:
            digest = sha(path)
            if built.get(field + '_sha256') != digest or result.get('firmware_' + field + '_sha256') != digest:
                raise ValueError('firmware ' + field + ' identity differs from original bytes')
        tools = result.get('tools', {})
        if self.prefix + 'gcc' not in tools or not all(tools.values()):
            raise ValueError('cross compiler/tool identity is incomplete')
        environment = {key: result[key] for key in ['main_commit', 'e203_commit', 'source_sha256',
                       'runner_sha256', 'contract_sha256', 'versions', 'simulator_sha256']}
        environment['tool_sha256'] = {key: dict(path=value, sha256=sha(Path(value))) for key, value in tools.items()}
        if not all(environment.values()):
            raise ValueError('runtime environment identity is incomplete')
        if self.sim == 'vcs':
            compiler = '\n'.join(environment['versions'].get(self.prefix + 'gcc', []))
            vcs = '\n'.join(environment['versions'].get('vcs', []))
            if '10.2.0-2020.12.8' not in compiler or 'Q-2020.03-SP2-6' not in vcs:
                raise ValueError('VCS campaign requires the accepted SiFive10.2/VCS Q-2020.03 server toolchain')
        if self.environment is None:
            self.environment = environment
            self.report['environment'] = environment
        elif environment != self.environment:
            raise ValueError('RTL/TB, tools, simulator or measurement identity changed between cases')
        vectors = result.get('vectors', {})
        expected_vectors = {'layer_{:02d}/{}.mem'.format(layer, name) for layer in range(tasks)
                            for name in ['x', 'w', 'bias', 'y']}
        if set(vectors) != expected_vectors:
            raise ValueError('vector identity inventory is incomplete')
        known = self.vectors.setdefault(mode, {})
        for name, digest in vectors.items():
            if sha(directory / 'vectors' / name) != digest or (name in known and known[name] != digest):
                raise ValueError('workload vector bytes differ: ' + name)
            known[name] = digest
        if mode == 'real':
            fixture = json.loads((ROOT / 'tests/e203/vectors/kwt-silence-v1.json').read_text())['files']
            if any(fixture.get(name) != digest for name, digest in vectors.items()):
                raise ValueError('real vectors differ from the fixed fixture')
        return perf.summarize(dict(result, mode='real'), 150.0)

    def run(self):
        try:
            baseline = self.required(self.trial('B0-new-RTL', contract.configuration(
                'bias-dtcm', '-O2', 'both-unroll-no-masks')))
            if self.sim == 'vcs':
                check_server_baseline(baseline)
            h1 = self.trial('H1-bias-cache', contract.configuration('bias-hw', '-O2', 'both-unroll-no-masks'), baseline)
            h2 = self.trial('H2-result-window', contract.configuration('bias-dtcm-window', '-O2', 'both-unroll-no-masks'), baseline)
            winner = baseline
            for candidate in [h1, h2]:
                if better(candidate, winner):
                    winner = candidate
            if h1['status'] == h2['status'] == 'PASS':
                combined = self.trial('H1H2-combined', contract.configuration(
                    'bias-hw-window', '-O2', 'both-unroll-no-masks'), winner)
                if better(combined, winner):
                    winner = combined
            self.report['selected'] = dict(experiment=winner['name'], configuration=winner['configuration'],
                                           comparison=comparison(winner, baseline), real12_result=winner['real12_result'])
            if self.accept:
                self.acceptance(winner)
                if self.sim == 'vcs':
                    improved = better(winner, baseline)
                    self.report.update(retention_status='retained' if improved else 'baseline-retained',
                                       retained_optimization=improved)
            self.report['status'] = 'PASS'
        except Exception as exc:
            self.report.update(status='FAIL', error=str(exc))
            if self.report.get('acceptance', {}).get('status') == 'RUNNING':
                self.report['acceptance'].update(status='FAIL', error=str(exc))
        self.report['finished_utc'] = firmware.timestamp()
        self.save()
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim', choices=['vcs', 'verilator'], default='vcs')
    parser.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    parser.add_argument('--out', required=True, type=Path, help='new output directory; must not exist')
    parser.add_argument('--accept', action='store_true', help='run full server acceptance before VCS retention')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    try:
        result = Campaign(out, args.sim, args.cross_prefix, args.accept).run()
    except Exception as exc:
        result = dict(schema='xu-hardware-experiments-v1', status='FAIL', error=str(exc),
                      retained_optimization=False, scope='hardware source preflight failed before experiments')
        (out / 'experiments.json').write_text(json.dumps(result, indent=2) + '\n')
    print('{}: {}'.format(result['status'], out / 'experiments.json'), flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
