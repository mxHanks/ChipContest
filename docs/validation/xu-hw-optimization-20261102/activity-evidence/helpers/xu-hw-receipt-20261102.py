#!/usr/bin/env python3
"""Export a derived xu campaign receipt for a screenshot-only transfer (Python 3.6+).

This is compressed evidence derived from existing files, never a simulator log or
an independent validation run. Hashes of JSON manifests use sorted keys and compact
separators; hashes of files always cover their original bytes.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib

SCHEMA = 'xu-hw-campaign-derived-receipt-v1'
PHASES = ['w_load', 'x_load', 'bias_load', 'compute_wait', 'writeback', 'other']
REQUIRED_STEPS = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def manifest(value):
    return digest(encoded(value))


def read_json(path):
    data = path.read_bytes()
    return json.loads(data.decode('utf-8')), digest(data)


def grouped(layers):
    """Merge only layers with identical TB cycles, firmware cycles AND counters."""
    result, positions = [], {}
    for layer in layers:
        value = dict(cycles=layer.get('cycles'), firmware_cycles=layer.get('firmware_cycles'),
                     performance=layer.get('performance', layer.get('counters')))
        key = encoded(value)
        if key not in positions:
            positions[key] = len(result)
            result.append(dict(value, layers=[]))
        result[positions[key]]['layers'].append(layer['layer'])
    return result


class Exporter:
    def __init__(self, directory):
        self.directory = directory.resolve()
        self.errors = []
        self.pools = dict(firmware_sources=[], builds=[], memory=[])

    def intern(self, pool, value):
        if value is None:
            return None
        values = self.pools[pool]
        if value not in values:
            values.append(value)
        return values.index(value)

    def error(self, message):
        self.errors.append(message)

    def relative(self, path):
        try:
            return str(path.relative_to(self.directory))
        except ValueError:
            return str(path)

    def verify(self, path, expected=None, required=False):
        if not path.is_file():
            if required:
                self.error('missing file: ' + str(path))
            return None
        actual = sha(path)
        if expected is not None and actual != expected:
            self.error('hash mismatch: ' + str(path))
        return actual

    def build(self, result):
        built = result.get('firmware_build')
        if not built:
            return None
        source = built.get('source_sha256', result.get('firmware_sha256'))
        value = dict(configuration=built.get('configuration'),
                     elf_sha256=built.get('elf_sha256', result.get('firmware_elf_sha256')),
                     image_sha256=built.get('image_sha256', result.get('firmware_image_sha256')),
                     source_pool=self.intern('firmware_sources', source),
                     source_manifest_sha256=manifest(source),
                     memory_pool=self.intern('memory', built.get('memory')))
        return self.intern('builds', value)

    @staticmethod
    def configuration(result):
        return dict(schedule=result.get('firmware_schedule', 'baseline'),
                    optimization=result.get('firmware_opt', '-Os'),
                    experiment=result.get('firmware_experiment', 'none'))

    def result(self, directory, expected=None, configuration=None, recorded_status=None, workload=None):
        path = directory / 'result.json'
        record = dict(output=self.relative(directory), recorded_status=recorded_status, workload=workload)
        if not path.is_file():
            record['status'] = 'NOT_AVAILABLE'
            if recorded_status == 'PASS':
                self.error('passing case has no result.json: ' + str(directory))
            return record
        result, actual = read_json(path)
        if expected is not None and expected != actual:
            self.error('result hash differs from campaign: ' + str(path))
        config = self.configuration(result)
        if configuration is not None and config != configuration:
            self.error('case configuration mismatch: ' + str(path))
        record.update(status=result.get('status'), mode=result.get('mode'), tasks=result.get('tasks'),
                      configuration=config, result_sha256=actual, simulator=result.get('simulator'),
                      outputs=result.get('outputs'), write_words=result.get('write_words'),
                      build_pool=self.build(result),
                      source_manifest_sha256=manifest(result.get('source_sha256', {})),
                      vector_manifest_sha256=manifest(result.get('vectors', {})),
                      layers=grouped(result.get('layers', [])),
                      log_sha256={name: self.verify(directory / name, value, required=True)
                                  for name, value in sorted(result.get('log_sha256', {}).items())})
        for name in ['main_commit', 'e203_commit', 'runner_sha256', 'contract_sha256', 'simulator_sha256', 'error']:
            if name in result:
                record[name] = result[name]
        if result.get('layers') and all(type(x.get('cycles')) is int for x in result['layers']):
            record['total_cycles'] = sum(x['cycles'] for x in result['layers'])
        if result.get('mode') in ['real', 'synthetic'] and result.get('status') == 'PASS':
            build = result.get('firmware_build', {})
            if (not build.get('source_sha256') or not build.get('memory') or
                    any(not re.fullmatch(r'[0-9a-f]{64}', str(build.get(name, '')))
                        for name in ['elf_sha256', 'image_sha256'])):
                self.error('passing simulation has incomplete firmware build identity/memory: ' + str(path))
            tasks = result.get('tasks')
            layers = result.get('layers', [])
            if (type(tasks) is not int or not 1 <= tasks <= 12 or
                    [row.get('layer') for row in layers] != list(range(tasks)) or
                    result.get('outputs') != tasks * 25344 or result.get('write_words') != tasks * 50688):
                self.error('incomplete passing numerical case: ' + str(path))
            if 'simulation.log' not in result.get('log_sha256', {}):
                self.error('passing simulation has no log identity: ' + str(path))
            for row in layers:
                counters = row.get('performance', {})
                required = dict(mac_fire=202752, starts=3168, dones=3168, shared_writes=50688,
                                shared_reads=73408 if config['schedule'] == 'baseline' else 23232)
                if (any(counters.get(k) != v for k, v in required.items()) or
                        any(type(counters.get(p)) is not int for p in PHASES) or
                        sum(counters.get(p, 0) for p in PHASES) != row.get('cycles')):
                    self.error('invalid fixed work/phase counters: ' + str(path))
        return record

    def acceptance(self, campaign):
        state = campaign.get('acceptance', {})
        directory = Path(state.get('output', str(self.directory / 'acceptance')))
        receipt = dict(recorded_status=state.get('status', 'NOT_RUN'), output=self.relative(directory))
        path = directory / 'acceptance.json'
        if not path.is_file():
            if state.get('status') == 'PASS':
                self.error('missing passing acceptance.json')
            return receipt
        actual, digest_value = read_json(path)
        receipt.update(status=actual.get('status'), acceptance_sha256=digest_value,
                       profile=actual.get('profile'), firmware_configuration=actual.get('firmware_configuration'),
                       scope=actual.get('scope'), not_run=actual.get('not_run'),
                       steps=[{key: step[key] for key in ['name', 'status', 'error'] if key in step}
                              for step in actual.get('steps', [])],
                       cases=[], log_sha256={}, json_sha256={})
        for step in actual.get('steps', []):
            source = directory / step['name']
            if step.get('status') == 'PASS':
                self.verify(directory / (step['name'] + '.log'), required=True)
            if (source / 'result.json').is_file():
                receipt['cases'].append(self.result(source, recorded_status=step.get('status'),
                    configuration=actual.get('firmware_configuration') if step['name'] not in ['baseline', 'vectors'] else None))
        for path in sorted(directory.rglob('*.log')):
            name = str(path.relative_to(directory))
            receipt['log_sha256'][name] = self.verify(path, state.get('log_sha256', {}).get(name))
        for path in sorted(directory.rglob('*.json')):
            name = str(path.relative_to(directory))
            receipt['json_sha256'][name] = self.verify(path, state.get('result_sha256', {}).get(name))
        receipt['driver_log_sha256'] = {path.name: self.verify(path, state.get('driver_log_sha256', {}).get(path.name))
            for path in [self.directory / 'acceptance.log', self.directory / 'acceptance-summary.log'] if path.is_file()}
        for name in ['error', 'failed_step']:
            if name in actual:
                receipt[name] = actual[name]
        summary_path = directory / 'xu-performance.json'
        if summary_path.is_file():
            summary, summary_sha = read_json(summary_path)
            result_path = directory / 'real12/result.json'
            if result_path.is_file() and summary.get('source_result_sha256') != sha(result_path):
                self.error('final performance summary source_result_sha256 mismatch')
            receipt['performance_summary'] = dict(sha256=summary_sha, source_result_sha256=summary.get('source_result_sha256'),
                frequency_mhz=summary.get('frequency_mhz'), frequency_status=summary.get('frequency_status'),
                aggregate=summary.get('aggregate'))
        return receipt

    def export(self):
        campaign_path = self.directory / 'experiments.json'
        campaign, campaign_sha = read_json(campaign_path)
        source, environment = campaign.get('source', {}), campaign.get('environment', {})
        source_files = source.get('source_sha256', {})
        source_rtl = environment.get('source_sha256', {})
        receipt = dict(schema=SCHEMA, evidence_kind='compressed derived receipt; not original logs or an independent rerun',
                       hash_rules='files: exact original bytes; manifests: ASCII JSON, sorted keys, separators comma/colon',
                       exported_utc=datetime.now(timezone.utc).isoformat(),
                       source_campaign=str(campaign_path), campaign_sha256=campaign_sha,
                       campaign_status=campaign.get('status'), simulator=campaign.get('simulator'),
                       retention_status=campaign.get('retention_status'),
                       baseline_commit=campaign.get('baseline_commit'),
                       baseline_server_cycles=campaign.get('baseline_server_cycles'),
                       started_utc=campaign.get('started_utc'), finished_utc=campaign.get('finished_utc'),
                       source=dict(commit=source.get('commit'), parent_commits=source.get('parent_commits'),
                                   manifest_sha256=manifest(source_files),
                                   measurement_files_sha256={name: value for name, value in source_files.items()
                                       if name.startswith('tools/scripts/') or name.endswith('tb_accel_soc.sv')}),
                       environment={key: value for key, value in environment.items() if key != 'source_sha256'},
                       rtl_manifest_sha256=manifest(source_rtl),
                       selection=campaign.get('selected'), experiments=[], pools=self.pools,
                       integrity_errors=self.errors, final=None)
        for experiment in campaign.get('experiments', []):
            entry = {key: experiment[key] for key in ['name', 'parent', 'status', 'configuration', 'decision', 'error']
                     if key in experiment}
            entry['source_commit'] = experiment.get('source', {}).get('commit')
            entry['source_parent_commits'] = experiment.get('source', {}).get('parent_commits')
            entry['source_manifest_sha256'] = manifest(experiment.get('source', {}).get('source_sha256', {}))
            entry['comparison'] = {key: value for key, value in experiment.get('comparison', {}).items() if key != 'layers'}
            entry['cases'] = []
            for case in experiment.get('cases', []):
                directory = Path(case['output'])
                row = self.result(directory, case.get('result_sha256'), experiment.get('configuration'),
                                  case.get('status'), case.get('workload'))
                log = self.directory / (directory.name + '.log')
                row['driver_log_sha256'] = self.verify(log, case.get('driver_log_sha256'), case.get('status') == 'PASS')
                entry['cases'].append(row)
            receipt['experiments'].append(entry)
        receipt['acceptance'] = self.acceptance(campaign)
        acceptance = receipt['acceptance']
        accepted_cases = {row['output'].rsplit('/', 1)[-1]: row for row in acceptance.get('cases', [])}
        real12, synthetic2 = accepted_cases.get('real12', {}), accepted_cases.get('synthetic2', {})
        steps = acceptance.get('steps', [])
        selected = campaign.get('selected', {})
        selected_experiment = next((x for x in receipt['experiments'] if x['name'] == selected.get('experiment')), {})
        selected_case = next((x for x in selected_experiment.get('cases', [])
                              if x.get('mode') == 'real' and x.get('tasks') == 12), {})
        if campaign.get('status') == 'PASS' and acceptance.get('status') == 'PASS':
            if acceptance.get('firmware_configuration') != selected.get('configuration'):
                self.error('acceptance configuration differs from the selected campaign configuration')
            if selected_case.get('layers') != real12.get('layers'):
                self.error('accepted layer measurements differ from the selected experiment')
        complete = (campaign.get('status') == 'PASS' and campaign.get('acceptance', {}).get('status') == 'PASS' and
                    acceptance.get('status') == 'PASS' and [x.get('name') for x in steps] == REQUIRED_STEPS and
                    all(x.get('status') == 'PASS' for x in steps) and
                    real12.get('status') == 'PASS' and real12.get('mode') == 'real' and real12.get('tasks') == 12 and
                    synthetic2.get('status') == 'PASS' and synthetic2.get('mode') == 'synthetic' and synthetic2.get('tasks') == 2 and
                    selected_experiment.get('status') == 'PASS' and selected_case.get('status') == 'PASS' and
                    bool(acceptance.get('performance_summary')) and not self.errors)
        if complete:
            baseline = next((x for x in receipt['experiments'] if x['name'] == 'B0-new-RTL'), {})
            baseline_case = next((x for x in baseline.get('cases', []) if x.get('mode') == 'real' and x.get('tasks') == 12), {})
            receipt['final'] = dict(status='PASS', retained_optimization=campaign.get('retained_optimization', False),
                comparison=campaign.get('selected', {}).get('comparison'),
                configuration=campaign.get('selected', {}).get('configuration'),
                baseline_layers=baseline_case.get('layers'), accepted_layers=real12.get('layers'),
                baseline_result_sha256=baseline_case.get('result_sha256'),
                accepted_result_sha256=real12.get('result_sha256'), acceptance_sha256=acceptance.get('acceptance_sha256'),
                performance_summary_sha256=acceptance['performance_summary']['sha256'])
        else:
            receipt['completion_note'] = 'PARTIAL: no final result declared; inspect campaign/acceptance status and integrity_errors'
        if campaign.get('error'):
            receipt['campaign_error'] = campaign['error']
        return receipt


def configuration_text(config):
    return '/'.join(str(config.get(name, '?')) for name in ['schedule', 'optimization', 'experiment'])


def layer_text(values):
    return ','.join(str(x) for x in values)


def show(receipt, part, experiment_name=None):
    print('DERIVED RECEIPT schema={} campaign={} simulator={} retention={} final={}'.format(
        receipt['schema'], receipt['campaign_status'], receipt.get('simulator'), receipt.get('retention_status'),
        'PASS' if receipt.get('final') else 'NOT_DECLARED'))
    if part in ['all', 'experiments']:
        for experiment in receipt['experiments']:
            if experiment_name and experiment['name'] != experiment_name:
                continue
            comparison = experiment.get('comparison', {})
            print('EXP {} parent={} status={} config={} total={} delta={} strict={}'.format(
                experiment['name'], experiment.get('parent'), experiment['status'], configuration_text(experiment['configuration']),
                comparison.get('candidate_cycles'), comparison.get('delta_cycles'), comparison.get('strictly_better')))
            print(' DECISION ' + experiment.get('decision', experiment.get('error', '-')))
            for case in experiment['cases']:
                print(' CASE {} {} recorded={} tasks={} outputs={} writes={} total={} build={}'.format(
                    case.get('workload'), case.get('status'), case.get('recorded_status'), case.get('tasks'),
                    case.get('outputs'), case.get('write_words'), case.get('total_cycles'), case.get('build_pool')))
                for group in case.get('layers', []):
                    print('  LAYERS {} cycles={} firmware_cycles={} {}'.format(layer_text(group['layers']), group['cycles'],
                        group['firmware_cycles'], ' '.join('{}={}'.format(key, value) for key, value in sorted((group['performance'] or {}).items()))))
    if part in ['all', 'final']:
        acceptance = receipt.get('acceptance', {})
        print('ACCEPT status={} recorded={} steps={}'.format(acceptance.get('status'), acceptance.get('recorded_status'),
            ' '.join(x['name'] + ':' + x['status'] for x in acceptance.get('steps', []))))
        print('SELECTION ' + json.dumps(receipt.get('selection'), sort_keys=True, separators=(',', ':')))
        print('FINAL ' + json.dumps(receipt.get('final'), sort_keys=True, separators=(',', ':')))
        for index, memory in enumerate(receipt['pools']['memory']):
            print('MEMORY {} {}'.format(index, json.dumps(memory, sort_keys=True, separators=(',', ':'))))
        for error in receipt['integrity_errors']:
            print('INTEGRITY_ERROR ' + error)
    if part in ['all', 'hashes']:
        print('CAMPAIGN_SHA256 ' + receipt['campaign_sha256'])
        print('SOURCE ' + json.dumps(receipt['source'], sort_keys=True, separators=(',', ':')))
        print('RTL_MANIFEST_SHA256 ' + receipt['rtl_manifest_sha256'])
        for index, sources in enumerate(receipt['pools']['firmware_sources']):
            print('FIRMWARE_SOURCES {} {}'.format(index, json.dumps(sources, sort_keys=True, separators=(',', ':'))))
        for index, build in enumerate(receipt['pools']['builds']):
            print('BUILD {} {}'.format(index, json.dumps(build, sort_keys=True, separators=(',', ':'))))
        for experiment in receipt['experiments']:
            if experiment_name and experiment['name'] != experiment_name:
                continue
            for case in experiment['cases']:
                print('HASH {} {} result={} driver={} logs={}'.format(experiment['name'], case.get('workload'),
                    case.get('result_sha256'), case.get('driver_log_sha256'), json.dumps(case.get('log_sha256'), sort_keys=True, separators=(',', ':'))))
        acceptance = receipt.get('acceptance', {})
        print('ACCEPTANCE_JSON_SHA256 ' + str(acceptance.get('acceptance_sha256')))
        print('ACCEPTANCE_JSONS ' + json.dumps(acceptance.get('json_sha256'), sort_keys=True, separators=(',', ':')))
        print('ACCEPTANCE_LOGS ' + json.dumps(acceptance.get('log_sha256'), sort_keys=True, separators=(',', ':')))


def write_new(path, value):
    with path.open('xb') as stream:
        stream.write(value)


def progress(directory, mode, tasks):
    """Observe files in place; absent result.json remains unfinished even at 12/12."""
    path = directory / 'simulation.log'
    log = path.read_text(errors='replace') if path.is_file() else ''
    passed = [int(x) for x in re.findall(r'^TASK_PASS layer=(\d+)\b', log, re.M)]
    result_path = directory / 'result.json'
    result = {}
    if result_path.is_file():
        try:
            result, unused = read_json(result_path)
        except ValueError:
            pass
    status = result.get('status', 'UNFINISHED')
    if status == 'PASS' and (result.get('mode') != mode or result.get('tasks') != tasks or passed != list(range(tasks))):
        status = 'INCOMPLETE'
    failure = bool(re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout', log, re.I))
    return dict(mode=mode, tasks=tasks, status=status, layers=passed,
                soc_pass=bool(re.search(r'^SOC_PASS\b', log, re.M)), failure_marker=failure,
                output=str(directory), error=result.get('error'))


def status(directory):
    directory = directory.resolve()
    campaign, unused = read_json(directory / 'experiments.json')
    print('CAMPAIGN status={} retention={} selected={} receipt=NOT_WRITTEN'.format(
        campaign.get('status'), campaign.get('retention_status'), campaign.get('selected', {}).get('experiment', '-')))
    print('ROOT ' + str(directory))
    if campaign.get('error'):
        print('ERROR ' + str(campaign['error'])[:240])
    for experiment in campaign.get('experiments', []):
        candidates = {Path(case['output']) for case in experiment.get('cases', [])}
        candidates.update(path for path in directory.glob(experiment['name'] + '-*') if path.is_dir())
        observations = []
        for path in sorted(candidates):
            match = re.search(r'-(synthetic|real)(\d+)$', path.name)
            if match:
                observations.append(progress(path, match.group(1), int(match.group(2))))
        observations.sort(key=lambda x: (0 if x['mode'] == 'synthetic' else 1, x['tasks']))
        total = experiment.get('summary', {}).get('aggregate', {}).get('cycles', '-')
        brief = ' '.join('{}{}:{}/{}/{}'.format(x['mode'], x['tasks'], len(x['layers']), x['tasks'], x['status'])
                         for x in observations) or 'NOT_STARTED'
        print('{} status={} config={} total={} {}'.format(experiment['name'], experiment.get('status'),
            configuration_text(experiment.get('configuration', {})), total, brief))
        for observation in observations:
            if observation['status'] != 'PASS' or observation['failure_marker']:
                print(' CURRENT {} TASK_PASS={} count={}/{} SOC_PASS={} failure_marker={}'.format(observation['output'],
                    layer_text(observation['layers']) or '-', len(observation['layers']), observation['tasks'],
                    observation['soc_pass'], observation['failure_marker']))
                if observation['error']:
                    print('  ERROR ' + str(observation['error'])[:240])
    acceptance = campaign.get('acceptance')
    if acceptance is not None:
        source = Path(acceptance.get('output', str(directory / 'acceptance')))
        actual = {}
        if (source / 'acceptance.json').is_file():
            actual, unused = read_json(source / 'acceptance.json')
        recorded = {step['name']: step.get('status') for step in actual.get('steps', [])}
        states = []
        for name in REQUIRED_STEPS:
            stage = recorded.get(name)
            if stage is None:
                stage = 'LOG_PRESENT' if (source / (name + '.log')).is_file() else 'NOT_STARTED'
            states.append(name + ':' + stage)
        print('ACCEPT status={} observed={} {}'.format(acceptance.get('status'), actual.get('status', 'UNFINISHED'), ' '.join(states)))
        for name, mode, tasks in [('synthetic1', 'synthetic', 1), ('synthetic2', 'synthetic', 2), ('real12', 'real', 12)]:
            if (source / name).is_dir():
                observation = progress(source / name, mode, tasks)
                print(' ACCEPT_CASE {} result={} TASK_PASS={} count={}/{} SOC_PASS={} failure_marker={}'.format(name,
                    observation['status'], layer_text(observation['layers']) or '-', len(observation['layers']), tasks,
                    observation['soc_pass'], observation['failure_marker']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command')
    export_parser = commands.add_parser('export', help='snapshot existing campaign into a new derived receipt')
    export_parser.add_argument('campaign', type=Path)
    export_parser.add_argument('--out', type=Path)
    status_parser = commands.add_parser('status', help='observe campaign rows and live TASK_PASS progress; writes no files')
    status_parser.add_argument('campaign', type=Path)
    show_parser = commands.add_parser('show', help='print compact human-readable evidence')
    show_parser.add_argument('receipt', type=Path)
    show_parser.add_argument('--part', choices=['all', 'experiments', 'final', 'hashes'], default='all')
    show_parser.add_argument('--experiment')
    compact_parser = commands.add_parser('compact', help='print exact receipt bytes as numbered zlib/base64 chunks')
    compact_parser.add_argument('receipt', type=Path)
    compact_parser.add_argument('--chunk-size', type=int, default=900)
    compact_parser.add_argument('--first', type=int, default=1)
    compact_parser.add_argument('--last', type=int)
    unpack_parser = commands.add_parser('unpack', help='reconstruct a receipt from transcribed XU_RCPT lines')
    unpack_parser.add_argument('chunks', type=Path)
    unpack_parser.add_argument('--out', type=Path, required=True)
    unpack_parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if args.command == 'export':
        destination = args.out or args.campaign / 'receipt.json'
        receipt = Exporter(args.campaign).export()
        raw = encoded(receipt) + b'\n'
        write_new(destination, raw)
        print('RECEIPT {} sha256={} bytes={} final={} integrity_errors={}'.format(destination, digest(raw), len(raw),
            'PASS' if receipt.get('final') else 'NOT_DECLARED', len(receipt['integrity_errors'])))
    elif args.command == 'status':
        status(args.campaign)
    elif args.command == 'show':
        receipt, unused = read_json(args.receipt)
        show(receipt, args.part, args.experiment)
    elif args.command == 'compact':
        if not 64 <= args.chunk_size <= 4000 or args.first < 1:
            parser.error('chunk-size must be 64..4000 and first must be positive')
        raw = args.receipt.read_bytes()
        compressed = zlib.compress(raw, 9)
        payload = base64.b64encode(compressed).decode('ascii')
        chunks = [payload[i:i + args.chunk_size] for i in range(0, len(payload), args.chunk_size)]
        last = min(args.last or len(chunks), len(chunks))
        print('XU_RCPT_META schema={} sha256={} raw_bytes={} compressed_bytes={} chunks={} chunk_chars={}'.format(
            SCHEMA, digest(raw), len(raw), len(compressed), len(chunks), args.chunk_size))
        for index in range(args.first - 1, last):
            print('XU_RCPT {:03d}/{:03d} {}'.format(index + 1, len(chunks), chunks[index]))
    elif args.command == 'unpack':
        matches = re.findall(r'^XU_RCPT\s+(\d+)/(\d+)\s+([A-Za-z0-9+/=]+)\s*$', args.chunks.read_text(), re.M)
        if not matches:
            raise ValueError('no XU_RCPT chunks found')
        count = int(matches[0][1])
        indexed = {int(index): payload for index, total, payload in matches}
        if len(matches) != count or len(indexed) != count or set(indexed) != set(range(1, count + 1)) or any(int(total) != count for index, total, payload in matches):
            raise ValueError('missing, duplicate or inconsistent chunks')
        payload = ''.join(indexed[i] for i in range(1, count + 1))
        raw = zlib.decompress(base64.b64decode(payload, validate=True))
        if digest(raw) != args.sha256 or json.loads(raw.decode()).get('schema') != SCHEMA:
            raise ValueError('receipt SHA256 or schema mismatch')
        write_new(args.out, raw)
        print('RECONSTRUCTED_DERIVED_RECEIPT {} sha256={}'.format(args.out, digest(raw)))
    else:
        parser.error('choose export, status, show, compact or unpack')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, zlib.error) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
