"""Exercise experiment selection with fake processes, never a simulator or make install."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/scripts'))
import xu_fw_experiments as experiments


class FakeProcesses:
    def __init__(self, totals=None, failed=None, corrupt=None, shifted_baseline=False):
        self.commands = []
        self.totals = dict({'E0-baseline': 28416892, 'E1-bias-dtcm': 20000000,
                            'E2a-bias-unroll': 19000000, 'E2b-result-unroll': 18000000,
                            'E2-combined': 18500000, 'E3-Os': 18000000,
                            'E3-O2': 17000000, 'E3-O3': 17000000,
                            'E4-no-masks': 17000000}, **(totals or {}))
        self.failed, self.corrupt = failed, corrupt
        self.shifted_baseline = shifted_baseline
        self.config_totals = {}
        self.source = experiments.source_identity()

    @staticmethod
    def value(command, name):
        return command[command.index(name) + 1]

    def config(self, command):
        return dict(schedule=self.value(command, '--firmware-schedule'),
                    optimization=next(x.split('=', 1)[1] for x in command if x.startswith('--firmware-opt=')),
                    experiment=self.value(command, '--firmware-experiment'))

    def result(self, directory, mode, tasks, config, total, sim):
        directory.mkdir()
        layers, lines = [], []
        for index in range(tasks):
            cycles = total // 12 + (total % 12 if index == 0 else 0)
            if self.shifted_baseline and config['schedule'] == 'baseline':
                cycles += -1 if index == 0 else 1 if index == 1 else 0
            counters = dict(w_load=cycles - 202752, x_load=0, bias_load=0, compute_wait=202752,
                            writeback=0, other=0, busy=202752, mac_fire=202752,
                            mmio_reads=60000, mmio_writes=156326,
                            shared_reads=73408 if config['schedule'] == 'baseline' else 23232,
                            shared_writes=50688, shared_stall=0, mmio_stall=0,
                            starts=3168, dones=3168)
            layer = dict(layer=index, cycles=cycles, firmware_cycles=cycles + 72, performance=counters)
            layers.append(layer)
            lines.append('TASK_PASS layer={} outputs=25344 writes=50688 cycles={} firmware_cycles={}'.format(
                index, cycles, cycles + 72))
            values = dict(counters, layer=index, cycles=cycles)
            lines.append('PERF_TASK ' + ' '.join(key + '=' + str(values[key])
                                               for key in experiments.contract.PERFORMANCE_FIELDS))
        lines.append('SOC_PASS tasks={} outputs={} writes={}'.format(tasks, tasks * 25344, tasks * 50688))
        log = directory / 'simulation.log'
        log.write_text('\n'.join(lines) + '\n')
        firmware_sources = {Path(name).name: digest for name, digest in self.source['source_sha256'].items()
                            if name.startswith('tests/e203/firmware/')}
        record = dict(status='PASS', mode=mode, tasks=tasks, simulator=sim,
                      outputs=tasks * 25344, write_words=tasks * 50688, layers=layers,
                      firmware_schedule=config['schedule'], firmware_opt=config['optimization'],
                      firmware_experiment=config['experiment'],
                      firmware_build=dict(configuration=config, source_sha256=firmware_sources,
                          image_sha256='4932e8d8f62cdd2732d894abc4c7008809283fe3de29445de90ec764cd12f32e'),
                      main_commit=self.source['commit'], e203_commit=experiments.E203_COMMIT,
                      source_sha256={'rtl.sv': 'frozen-rtl'}, runner_sha256='runner',
                      contract_sha256='contract', simulator_sha256='simulator',
                      versions={'test-gcc': ['SiFive GCC-Metal 10.2.0-2020.12.8'],
                                'vcs': ['Q-2020.03-SP2-6']},
                      tools={'test-gcc': sys.executable},
                      vectors={'layer_{:02d}/{}.mem'.format(i, name): mode + str(i) + name
                               for i in range(tasks) for name in ['x', 'w', 'bias', 'y']},
                      log_sha256={'simulation.log': experiments.sha(log)})
        (directory / 'result.json').write_text(json.dumps(record))
        return record

    def __call__(self, command, logfile, timeout):
        self.commands.append(command)
        logfile.write_text(json.dumps(command) + '\n')
        script = Path(command[1]).name
        directory = Path(self.value(command, '--out'))
        if script == 'xu_perf_report.py':
            source = json.loads(Path(self.value(command, '--result')).read_text())
            directory.write_text(json.dumps(experiments.perf.summarize(source, 150)))
            return
        config, sim = self.config(command), self.value(command, '--sim')
        if script == 'server_accept.py':
            directory.mkdir()
            names = ['host', 'numeric', 'vectors', 'doctor', 'baseline', 'synthetic1', 'synthetic2', 'real12']
            (directory / 'acceptance.json').write_text(json.dumps(dict(status='PASS',
                firmware_configuration=config, steps=[dict(name=name, status='PASS') for name in names])))
            total = self.config_totals[json.dumps(config, sort_keys=True)]
            self.result(directory / 'synthetic2', 'synthetic', 2, config, total, sim)
            self.result(directory / 'real12', 'real', 12, config, total, sim)
            return
        mode, tasks = self.value(command, '--mode'), int(self.value(command, '--tasks'))
        name = directory.name.rsplit('-', 1)[0]
        self.config_totals[json.dumps(config, sort_keys=True)] = self.totals[name]
        result = self.result(directory, mode, tasks, config, self.totals[name], sim)
        if name == self.failed:
            result['status'] = 'FAIL'
            (directory / 'result.json').write_text(json.dumps(result))
            raise RuntimeError('fake candidate failure')
        if self.corrupt:
            self.corrupt(name, result)
            (directory / 'result.json').write_text(json.dumps(result))


class FirmwareExperimentTests(unittest.TestCase):
    def run_campaign(self, processes, sim='vcs', accept=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        campaign = experiments.Campaign(Path(temporary.name), sim, 'test-', accept, runner=processes)
        return campaign.run(), processes

    def test_independent_order_strict_selection_and_full_acceptance(self):
        report, processes = self.run_campaign(FakeProcesses(), accept=True)
        self.assertEqual(report['status'], 'PASS', report.get('error'))
        self.assertTrue(report['retained_optimization'])
        self.assertEqual(report['retention_status'], 'retained')
        records = {row['name']: row for row in report['experiments']}
        self.assertEqual([case['workload'] for case in records['E1-bias-dtcm']['cases']],
                         ['synthetic2', 'real1', 'real12'])
        for name in ['E2a-bias-unroll', 'E2b-result-unroll']:
            self.assertEqual(records[name]['parent'], 'E1-bias-dtcm')
            self.assertEqual([c['workload'] for c in records[name]['cases']], ['synthetic2', 'real12'])
        self.assertFalse(records['E2-combined']['comparison']['strictly_better'])
        for name, optimization in [('E3-Os', '-Os'), ('E3-O2', '-O2'), ('E3-O3', '-O3')]:
            self.assertEqual(records[name]['configuration'], dict(schedule='bias-dtcm',
                             optimization=optimization, experiment='result-unroll'))
        self.assertEqual(records['E4-no-masks']['configuration'], dict(schedule='bias-dtcm',
                         optimization='-O2', experiment='result-unroll-no-masks'))
        self.assertFalse(records['E4-no-masks']['comparison']['strictly_better'])
        self.assertEqual(report['selected']['experiment'], 'E3-O2')
        self.assertEqual(report['acceptance']['status'], 'PASS')
        self.assertEqual(Path(processes.commands[-1][1]).name, 'xu_perf_report.py')
        outputs = [processes.value(c, '--out') for c in processes.commands]
        self.assertEqual(len(outputs), len(set(outputs)))
        self.assertEqual([row['name'] for row in report['experiments']],
                         ['E0-baseline', 'E1-bias-dtcm', 'E2a-bias-unroll', 'E2b-result-unroll',
                          'E2-combined', 'E3-Os', 'E3-O2', 'E3-O3', 'E4-no-masks'])

    def test_ties_do_not_combine_and_verilator_is_always_provisional(self):
        totals = {'E2a-bias-unroll': 20000000, 'E2b-result-unroll': 20000000,
                  'E3-Os': 20000000, 'E3-O2': 20000000, 'E3-O3': 20000000,
                  'E4-no-masks': 20000000}
        report, unused = self.run_campaign(FakeProcesses(totals), sim='verilator')
        self.assertEqual(report['status'], 'PASS', report.get('error'))
        self.assertNotIn('E2-combined', [x['name'] for x in report['experiments']])
        self.assertEqual(report['selected']['experiment'], 'E3-Os')
        self.assertEqual(report['selected']['configuration']['experiment'], 'none')
        self.assertEqual(report['retention_status'], 'provisional')
        self.assertFalse(report['retained_optimization'])

    def test_candidate_failure_is_rejected_and_has_hashes(self):
        report, unused = self.run_campaign(FakeProcesses(failed='E2a-bias-unroll'))
        self.assertEqual(report['status'], 'PASS', report.get('error'))
        records = {x['name']: x for x in report['experiments']}
        self.assertNotIn('E2-combined', records)
        self.assertEqual(records['E2a-bias-unroll']['status'], 'FAIL')
        case = records['E2a-bias-unroll']['cases'][0]
        self.assertEqual(len(case['result_sha256']), 64)
        self.assertEqual(len(case['driver_log_sha256']), 64)
        self.assertIn('simulation.log', case['log_sha256'])
        self.assertEqual(records['E2b-result-unroll']['parent'], 'E1-bias-dtcm')
        self.assertEqual(report['retention_status'], 'pending-acceptance')

    def test_server_baseline_mismatch_stops_before_cache_experiment(self):
        report, processes = self.run_campaign(FakeProcesses({'E0-baseline': 28416893}))
        self.assertEqual(report['status'], 'FAIL')
        self.assertIn('baseline does not reproduce', report['error'])
        self.assertEqual(len(processes.commands), 1)

    def test_changed_rtl_or_vectors_rejects_candidate(self):
        for field in ['source_sha256', 'vectors']:
            def corrupt(name, result):
                if name == 'E1-bias-dtcm':
                    result[field] = {'changed': 'changed'}
            report, unused = self.run_campaign(FakeProcesses(corrupt=corrupt))
            self.assertEqual(report['status'], 'FAIL')
            self.assertFalse(report['retained_optimization'])

    def test_historical_baseline_image_and_individual_layers_are_required(self):
        def corrupt(name, result):
            if name == 'E0-baseline':
                result['firmware_build']['image_sha256'] = 'different-image'
        for processes in [FakeProcesses(corrupt=corrupt), FakeProcesses(shifted_baseline=True)]:
            report, unused = self.run_campaign(processes)
            self.assertEqual(report['status'], 'FAIL')
            self.assertEqual(len(report['experiments']), 1)

    def test_no_improvement_accepts_the_baseline_without_claiming_optimization(self):
        totals = {name: 28416892 for name in FakeProcesses().totals}
        report, processes = self.run_campaign(FakeProcesses(totals), accept=True)
        self.assertEqual(report['status'], 'PASS', report.get('error'))
        self.assertEqual(report['selected']['experiment'], 'E0-baseline')
        self.assertEqual(report['retention_status'], 'baseline-retained')
        self.assertFalse(report['retained_optimization'])
        accepted_command = next(c for c in processes.commands if Path(c[1]).name == 'server_accept.py')
        self.assertEqual(processes.config(accepted_command), experiments.contract.configuration())

    def test_verilator_acceptance_never_declares_retained(self):
        report, unused = self.run_campaign(FakeProcesses(), sim='verilator', accept=True)
        self.assertEqual(report['status'], 'PASS', report.get('error'))
        self.assertEqual(report['retention_status'], 'provisional')
        self.assertFalse(report['retained_optimization'])

    def test_failed_acceptance_keeps_available_evidence_hashes(self):
        fake = FakeProcesses()
        def fail_acceptance(command, logfile, timeout):
            fake(command, logfile, timeout)
            if Path(command[1]).name == 'server_accept.py':
                raise RuntimeError('fake acceptance failed')
        report, unused = self.run_campaign(fail_acceptance, accept=True)
        self.assertEqual(report['status'], 'FAIL')
        self.assertEqual(report['acceptance']['status'], 'FAIL')
        self.assertIn('acceptance.log', report['acceptance']['driver_log_sha256'])
        self.assertIn('acceptance.json', report['acceptance']['result_sha256'])
        self.assertIn('real12/simulation.log', report['acceptance']['log_sha256'])
        self.assertFalse(report['retained_optimization'])


if __name__ == '__main__':
    unittest.main()
