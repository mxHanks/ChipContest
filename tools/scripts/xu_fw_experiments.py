#!/usr/bin/env python3
"""Run serial, independent xu firmware experiments with immutable evidence directories.

VCS uses the historical server toolchain and must reproduce f0f27b4's baseline.
Verilator results are provisional. Only a strict improvement that also completes
--accept under VCS is declared retained. Requires Python 3.6 or newer.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import e203_soc as soc
import xu_firmware_contract as contract
import xu_perf_report as perf

ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = 'f0f27b4f1e182dce32136313b57252d39f4df1cd'
BASELINE_CYCLES = 28416892
E203_COMMIT = 'e36d34a52e6eef93fd0bdfed1b13009e1056bea3'
_FROZEN_FILES = None


def git_output(arguments, cwd=ROOT):
    return subprocess.check_output(['git', *arguments], cwd=str(cwd))


def frozen_files():
    global _FROZEN_FILES
    if _FROZEN_FILES is None:
        paths = ['tests/e203/tb_accel_soc.sv', 'tests/e203/vectors', 'model',
                 'src/main/scala', 'tools/model/export_kwt.py',
                 *['tests/e203/firmware/' + name for name in ['start.S', 'main.c', 'accel.h', 'link.ld']]]
        names = git_output(['ls-tree', '-r', '--name-only', BASELINE_COMMIT, '--', *paths]).decode().splitlines()
        if not names:
            raise ValueError('frozen performance baseline is unavailable')
        _FROZEN_FILES = {name: hashlib.sha256(git_output(['show', BASELINE_COMMIT + ':' + name])).hexdigest()
                         for name in names}
    return _FROZEN_FILES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def source_identity():
    fixed = frozen_files()
    for name, digest in fixed.items():
        if sha(ROOT / name) != digest:
            raise ValueError('fixed TB/RTL/ABI/vector/numeric source differs from f0f27b4: ' + name)
    if soc.verify_submodule(ROOT, soc.E203) != E203_COMMIT:
        raise ValueError('E203 gitlink differs from the frozen baseline')
    if git_output(['diff', '--name-only', 'HEAD', '--'], cwd=soc.E203).strip():
        raise ValueError('E203 has tracked modifications; fixed RTL is required')
    files = list((ROOT / 'tests/e203/firmware').iterdir())
    files += [ROOT / name for name in [
        'tests/e203/tb_accel_soc.sv', 'tests/e203/vectors/kwt-silence-v1.tar.gz',
        'tests/e203/vectors/kwt-silence-v1.json', 'tools/scripts/e203_soc.py',
        'tools/scripts/server_accept.py', 'tools/scripts/xu_firmware_contract.py',
        'tools/scripts/xu_perf_report.py', 'tools/scripts/xu_fw_experiments.py']]
    files += [ROOT / name for name in fixed]
    revision = subprocess.check_output(['git', 'log', '-1', '--format=%H%n%P'],
                                       cwd=str(ROOT), universal_newlines=True).splitlines()
    return dict(commit=revision[0], parent_commits=revision[1].split() if len(revision) > 1 else [],
                source_sha256={str(p.relative_to(ROOT)): sha(p)
                               for p in sorted(files) if p.is_file()})


def firmware_arguments(config):
    return ['--firmware-schedule', config['schedule'],
            '--firmware-opt=' + config['optimization'],
            '--firmware-experiment', config['experiment']]


def execute(command, logfile, timeout):
    """Each invocation owns a new log; no parallel make install calls are made."""
    with logfile.open('x') as stream:
        stream.write(json.dumps(command) + '\n')
        stream.flush()
        result = subprocess.run(command, cwd=str(ROOT), stdout=stream,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError('command exit {}: {}'.format(result.returncode, logfile))


def comparison(candidate, reference):
    """A tie never wins. Decisions use all twelve measured TB windows."""
    current, previous = candidate['summary'], reference['summary']
    total, before = current['aggregate']['cycles'], previous['aggregate']['cycles']
    return dict(reference=reference['name'], baseline_cycles=before, candidate_cycles=total,
                delta_cycles=total - before, speedup=before / total,
                strictly_better=total < before,
                layers=[dict(layer=a['layer'], reference_cycles=b['cycles'],
                             candidate_cycles=a['cycles'], delta_cycles=a['cycles'] - b['cycles'])
                        for a, b in zip(current['layers'], previous['layers'])])


def better(candidate, reference):
    return candidate['status'] == 'PASS' and comparison(candidate, reference)['strictly_better']


def check_server_baseline(record):
    receipt = json.loads(git_output(['show', BASELINE_COMMIT + ':docs/validation/xu-performance-20261102/observed-receipt.json']).decode())
    expected = {}
    for group in receipt['groups']:
        for layer in group['layers']:
            expected[layer] = (group['cycles'], group['firmware_cycles'])
    measured = [(row['cycles'], row['firmware_cycles']) for row in record['summary']['layers']]
    if (record['summary']['aggregate']['cycles'] != BASELINE_CYCLES or
            measured != [expected[layer] for layer in range(12)]):
        raise ValueError('server baseline does not reproduce historical per-layer cycles and 28,416,892 total cycles')
    built = record['cases'][-1]['firmware_build']
    if built.get('image_sha256') != receipt['firmware_image_sha256']:
        raise ValueError('server baseline firmware image differs from the frozen historical image')


class Campaign:
    def __init__(self, out, sim, cross_prefix, accept=False, runner=execute):
        self.out, self.sim, self.prefix = out, sim, cross_prefix
        self.accept, self.runner = accept, runner
        self.identity = source_identity()
        self.environment = None
        self.firmware_sources = None
        self.vectors = {}
        self.report = dict(schema='xu-firmware-experiments-v1', status='RUNNING',
                           started_utc=timestamp(), simulator=sim, cross_prefix=cross_prefix,
                           baseline_commit=BASELINE_COMMIT, baseline_server_cycles=BASELINE_CYCLES,
                           source=self.identity, experiments=[],
                           retention_status='provisional' if sim != 'vcs' else 'pending-acceptance',
                           retained_optimization=False,
                           scope='fixed RTL, MMIO ABI, numeric format, vectors and timing window; '
                                 '12 independent FFN1 tasks; 150 MHz conversions are conditional')

    def save(self):
        (self.out / 'experiments.json').write_text(json.dumps(self.report, indent=2, sort_keys=True) + '\n')

    def check_source(self):
        if source_identity() != self.identity:
            raise ValueError('source changed during campaign; use a new output directory after fixing source')

    def validate_case(self, result, directory, mode, tasks, config):
        if (result.get('status') != 'PASS' or result.get('mode') != mode or
                result.get('tasks') != tasks or result.get('simulator') != self.sim):
            raise ValueError('run status, workload or simulator mismatch')
        if contract.configuration_from_result(result) != config:
            raise ValueError('run firmware configuration differs from requested configuration')
        if result.get('firmware_build', {}).get('configuration') != config:
            raise ValueError('missing or mismatched compiled firmware configuration')
        if result.get('outputs') != tasks * contract.OUTPUTS_PER_TASK or result.get('write_words') != tasks * 50688:
            raise ValueError('incomplete numerical output or writeback count')
        logs = result.get('log_sha256', {})
        if 'simulation.log' not in logs:
            raise ValueError('simulation log identity is missing')
        for name, digest in logs.items():
            if Path(name).name != name or sha(directory / name) != digest:
                raise ValueError('log hash mismatch: ' + name)
        # Re-parse the original log, including failure markers and ordered completions.
        log = (directory / 'simulation.log').read_text(errors='replace')
        layers = soc.check_log(log, tasks)
        counters = soc.check_performance(log, layers, config['schedule'])
        for layer, measured in zip(layers, counters):
            layer['performance'] = measured
        if layers != result.get('layers'):
            raise ValueError('result layers differ from the original simulation log')

        identity_fields = ['main_commit', 'e203_commit', 'source_sha256', 'runner_sha256',
                           'contract_sha256', 'versions', 'simulator_sha256']
        environment = {key: result[key] for key in identity_fields}
        if not all(environment.values()) or environment['e203_commit'] != E203_COMMIT:
            raise ValueError('incomplete source/tool identity or incorrect E203 pin')
        if environment['main_commit'] != self.identity['commit']:
            raise ValueError('runner used a different source revision')
        tools = result.get('tools', {})
        if self.prefix + 'gcc' not in tools:
            raise ValueError('cross compiler identity is missing')
        environment['tool_sha256'] = {key: dict(path=value, sha256=sha(Path(value)))
                                      for key, value in tools.items()}
        if self.sim == 'vcs':
            compiler = '\n'.join(environment['versions'].get(self.prefix + 'gcc', []))
            vcs = '\n'.join(environment['versions'].get('vcs', []))
            if '10.2.0-2020.12.8' not in compiler or 'Q-2020.03-SP2-6' not in vcs:
                raise ValueError('VCS campaign requires the frozen SiFive 10.2/VCS Q-2020.03 server toolchain')
        if self.environment is None:
            self.environment = environment
            self.report['environment'] = environment
        elif environment != self.environment:
            raise ValueError('toolchain, simulator, RTL/TB or runner identity changed during campaign')
        firmware_sources = result['firmware_build'].get('source_sha256')
        if not firmware_sources:
            raise ValueError('compiled firmware source hashes are missing')
        expected_sources = {Path(name).name: digest for name, digest in self.identity['source_sha256'].items()
                            if name.startswith('tests/e203/firmware/')}
        if firmware_sources != expected_sources:
            raise ValueError('compiled firmware source hashes differ from the initial source snapshot')
        if self.firmware_sources is None:
            self.firmware_sources = firmware_sources
        elif firmware_sources != self.firmware_sources:
            raise ValueError('firmware source changed between experiments')
        vectors = result.get('vectors')
        if not vectors:
            raise ValueError('vector hashes are missing')
        expected_vectors = {'layer_{:02d}/{}.mem'.format(layer, name)
                            for layer in range(tasks) for name in ['x', 'w', 'bias', 'y']}
        if set(vectors) != expected_vectors:
            raise ValueError('missing or unexpected workload vector hashes')
        if mode in self.vectors:
            if any(self.vectors[mode].get(key) != digest for key, digest in vectors.items()):
                raise ValueError('workload vectors changed between experiments')
        else:
            self.vectors[mode] = vectors
        # The summarizer also rechecks phases, fixed work and positive cycle counts.
        measured = dict(result, mode='real')
        summary = perf.summarize(measured, 150.0)
        return summary

    def trial(self, name, config, parent=None, real1=False):
        record = dict(name=name, configuration=config, parent=parent['name'] if parent else None,
                      source=self.identity, status='RUNNING', cases=[])
        self.report['experiments'].append(record)
        self.save()
        workloads = [('synthetic', 2), ('real', 1), ('real', 12)] if real1 else [('synthetic', 2), ('real', 12)]
        if name == 'E0-baseline':
            workloads = [('real', 12)]
        try:
            for mode, tasks in workloads:
                self.check_source()
                label = '{}-{}{}'.format(name, mode, tasks)
                directory = self.out / label
                logfile = self.out / (label + '.log')
                command = [sys.executable, str(ROOT / 'tools/scripts/e203_soc.py'),
                           '--sim', self.sim, '--cross-prefix', self.prefix,
                           '--mode', mode, '--tasks', str(tasks), '--out', str(directory),
                           *firmware_arguments(config)]
                case = dict(workload=mode + str(tasks), command=command, output=str(directory), status='RUNNING')
                record['cases'].append(case)
                if directory.exists():
                    raise ValueError('experiment output already exists: ' + str(directory))
                self.runner(command, logfile, 14400)
                result_path = directory / 'result.json'
                case['result_sha256'] = sha(result_path)
                result = json.loads(result_path.read_text())
                summary = self.validate_case(result, directory, mode, tasks, config)
                self.check_source()
                case.update(status='PASS', result_sha256=sha(result_path), driver_log_sha256=sha(logfile),
                            log_sha256=result['log_sha256'], firmware_build=result['firmware_build'])
                if mode == 'real' and tasks == 12:
                    record['summary'] = summary
                    record['real12_result'] = str(result_path)
            record['status'] = 'PASS'
        except Exception as exc:
            record.update(status='FAIL', error=str(exc))
            if record['cases']:
                case = record['cases'][-1]
                case.update(status='FAIL', error=str(exc))
                directory = Path(case['output'])
                case['log_sha256'] = {p.name: sha(p) for p in sorted(directory.glob('*.log'))}
                result_path = directory / 'result.json'
                if result_path.is_file():
                    case['result_sha256'] = sha(result_path)
                if logfile.is_file():
                    case['driver_log_sha256'] = sha(logfile)
        if parent is not None and record['status'] == 'PASS':
            record['comparison'] = comparison(record, parent)
            record['decision'] = 'improved' if record['comparison']['strictly_better'] else 'rejected: no strict cycle improvement'
        elif record['status'] == 'FAIL':
            record['decision'] = 'rejected: correctness or identity check failed'
        self.save()
        return record

    @staticmethod
    def required(record):
        if record['status'] != 'PASS':
            raise RuntimeError('{} failed: {}'.format(record['name'], record.get('error')))
        return record

    def acceptance(self, winner):
        self.check_source()
        directory = self.out / 'acceptance'
        command = [sys.executable, str(ROOT / 'tools/scripts/server_accept.py'),
                   '--sim', self.sim, '--cross-prefix', self.prefix, '--out', str(directory),
                   *firmware_arguments(winner['configuration'])]
        record = dict(command=command, output=str(directory), status='RUNNING')
        self.report['acceptance'] = record
        self.save()
        result_path = directory / 'acceptance.json'
        try:
            self.runner(command, self.out / 'acceptance.log', 172800)
            accepted = json.loads(result_path.read_text())
            expected = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']
            if (accepted.get('status') != 'PASS' or [step['name'] for step in accepted['steps']] != expected or
                    any(step.get('status') != 'PASS' for step in accepted['steps'])):
                raise ValueError('full development acceptance did not pass every required step')
            if accepted.get('firmware_configuration') != winner['configuration']:
                raise ValueError('acceptance firmware configuration differs from selected candidate')
            for name, mode, tasks in [('synthetic2', 'synthetic', 2), ('real12', 'real', 12)]:
                source = directory / name
                measured = self.validate_case(json.loads((source / 'result.json').read_text()), source,
                                              mode, tasks, winner['configuration'])
                if name == 'real12' and measured['layers'] != winner['summary']['layers']:
                    raise ValueError('accepted real12 measurement differs from the selected experiment')
            summary_command = [sys.executable, str(ROOT / 'tools/scripts/xu_perf_report.py'),
                               '--result', str(directory / 'real12/result.json'), '--frequency-mhz', '150',
                               '--out', str(directory / 'xu-performance.json')]
            record['summary_command'] = summary_command
            self.runner(summary_command, self.out / 'acceptance-summary.log', 180)
            self.check_source()
            record['status'] = 'PASS'
        finally:
            record['log_sha256'] = {str(p.relative_to(directory)): sha(p)
                                    for p in sorted(directory.rglob('*.log'))}
            record['driver_log_sha256'] = {p.name: sha(p) for p in [self.out / 'acceptance.log',
                                                   self.out / 'acceptance-summary.log'] if p.is_file()}
            record['result_sha256'] = {str(p.relative_to(directory)): sha(p)
                                       for p in sorted(directory.rglob('*.json'))}
            self.save()

    def run(self):
        try:
            baseline = self.required(self.trial('E0-baseline', contract.configuration()))
            if self.sim == 'vcs':
                check_server_baseline(baseline)
            e1 = self.required(self.trial('E1-bias-dtcm', contract.configuration('bias-dtcm'), baseline, real1=True))
            a = self.trial('E2a-bias-unroll', contract.configuration('bias-dtcm', '-Os', 'bias-unroll'), e1)
            b = self.trial('E2b-result-unroll', contract.configuration('bias-dtcm', '-Os', 'result-unroll'), e1)
            winner = e1
            for candidate in [a, b]:
                if better(candidate, winner):
                    winner = candidate
            if better(a, e1) and better(b, e1):
                combined = self.trial('E2-combined', contract.configuration('bias-dtcm', '-Os', 'both-unroll'), winner)
                if better(combined, winner):
                    winner = combined
            source_winner = winner
            # Repeat -Os as part of E3 so all three options use the same source and replay scope.
            e3 = self.required(self.trial('E3-Os', dict(source_winner['configuration']), source_winner))
            for optimization in ['-O2', '-O3']:
                config = dict(source_winner['configuration'], optimization=optimization)
                candidate = self.trial('E3-' + optimization[1:], config, e3)
                if better(candidate, winner if winner['name'].startswith('E3-') else e3):
                    winner = candidate
            if not winner['name'].startswith('E3-'):
                winner = e3
            experiment = winner['configuration']['experiment']
            config = dict(winner['configuration'], experiment='no-masks' if experiment == 'none' else experiment + '-no-masks')
            e4 = self.trial('E4-no-masks', config, winner)
            if better(e4, winner):
                winner = e4
            if not better(winner, baseline):
                winner = baseline
            self.report['selected'] = dict(experiment=winner['name'], configuration=winner['configuration'],
                                           comparison=comparison(winner, baseline),
                                           real12_result=winner['real12_result'])
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
        self.report['finished_utc'] = timestamp()
        self.save()
        return self.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim', choices=['vcs', 'verilator'], default='vcs')
    parser.add_argument('--cross-prefix', default='riscv64-unknown-elf-')
    parser.add_argument('--out', required=True, type=Path, help='new output directory; must not exist')
    parser.add_argument('--accept', action='store_true', help='run full development acceptance on the winner and generate its performance summary')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = Campaign(out, args.sim, args.cross_prefix, args.accept).run()
    print('{}: {}'.format(result['status'], out / 'experiments.json'), flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
