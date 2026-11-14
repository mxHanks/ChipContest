"""Native wrapped coverage identities and refusal to hide unknown checks."""
from collections import Counter
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('unknown_checks', ROOT / 'experiments/s3-y32-ingress-perf/ppa/eco/unknown_checks.py')
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)


def blocks():
    # Exact original blocks, including the recovery condition's extra wrap.
    native = checks.parse_coverage(checks.DEFAULT.read_text())
    return [dict(r) for r in checks.unknowns(native).values()] + [dict(
        constrained_pin='u_fixture/other_reg/RDN(low)', related_pin='-', clock='-',
        kind='min_pulse_width', condition='-', status='untested', reason='no_clock', slack_printed_ns=None)] + [dict(
        constrained_pin='u_fixture/already_met_reg/D', related_pin='CK(rise)', clock='xu_lfextclk',
        kind='setup', condition='-', status='met', reason='-', slack_printed_ns=0.2)]


def fixture(rows, include_met=True):
    totals = Counter(r['kind'] for r in rows)
    statuses = Counter((r['kind'], r['status']) for r in rows)
    result = ['Report : analysis_coverage', 'Design : xu_soc_sysbus32_ppa_top']
    def summary(kind, count):
        return f'{kind:20} {count} {statuses[kind,"met"]} (0%) {statuses[kind,"violated"]} (0%) {statuses[kind,"untested"]} (0%)'
    for kind in sorted(checks.plan.CHECKS):
        result.append(summary(kind, totals[kind]))
    result.append(f'All Checks {len(rows)} {sum(r["status"]=="met" for r in rows)} (0%) '
                  f'{sum(r["status"]=="violated" for r in rows)} (0%) {sum(r["status"]=="untested" for r in rows)} (0%)')
    result += ['', 'Pin                  Pin     Clock     Type    Condition      Slack  Reason', '-'*80]
    for row in rows:
        if row['status'] == 'met' and not include_met:
            continue
        result += [row['constrained_pin'], ' '*21 + row['related_pin'], ' '*29 + row['clock'],
                   ' '*39 + row['kind'], ' '*47 + row['condition'],
                   ' '*59 + ('untested  ' + row['reason'] if row['status']=='untested' else str(row['slack_printed_ns'])+'  -')]
    return '\n'.join(result) + '\n'


def native_receipt(payloads):
    # Retain the actual completed final-map receipt contract in small fixtures.
    source = json.loads((checks.DEFAULT.parent/'execution.json').read_text())
    source['outputs'] = {'original-constraints-pt-add.sdc': dict(bytes=6384, sha256=checks.PT_ADD_SHA256)}
    source['outputs'].update({p.name: {k: v for k, v in checks.file_identity(p).items() if k != 'path'}
                              for p in payloads})
    return source


class UnknownCoverageTests(unittest.TestCase):
    def test_actual_full_coverage_identifies_all_four_wrapped_checks(self):
        report = checks.parse_coverage(checks.DEFAULT.read_text())
        unknown = list(checks.unknowns(report).values())
        self.assertEqual(len(unknown), 4)
        self.assertEqual(Counter(r['kind'] for r in unknown), {'setup': 2, 'recovery': 2})
        self.assertEqual(len(report['checks']), 29332)
        self.assertFalse(report['complete_identities'])
        self.assertEqual(unknown[0]['pin'], 'D')
        self.assertTrue(unknown[0]['instance'].endswith('dwakeup_deglitch/T_8_reg'))
        recovery = [r for r in unknown if r['kind']=='recovery']
        self.assertTrue(all(r['condition']=="sdf_cond(ENABLE_NOT_D===1'b1)" for r in recovery))
        self.assertTrue(all(r['clock']=='xu_lfextclk' for r in unknown))

    def test_only_explicit_met_with_all_other_identities_passes(self):
        rows = blocks()
        baseline = checks.parse_coverage(fixture(rows))
        for row in rows[:4]:
            row.update(status='met', reason='-', slack_printed_ns=0.031)
        result = checks.compare(baseline, checks.parse_coverage(fixture(rows)))
        self.assertTrue(result['closed'], result)

    def test_unknown_to_no_clock_or_disabled_is_rejected(self):
        for replacement in ['no_clock', 'constant_disabled', 'user_disabled']:
            with self.subTest(replacement=replacement):
                rows = blocks(); baseline = checks.parse_coverage(fixture(rows))
                for row in rows[:4]: row['reason'] = replacement
                self.assertFalse(checks.compare(baseline, checks.parse_coverage(fixture(rows)))['closed'])

    def test_deleted_unknown_and_lower_total_is_rejected(self):
        rows = blocks(); baseline = checks.parse_coverage(fixture(rows))
        result = checks.compare(baseline, checks.parse_coverage(fixture(rows[4:])))
        self.assertFalse(result['closed'])
        self.assertIn('check type/total counts changed', result['failures'])

    def test_same_count_replacement_identity_is_rejected(self):
        rows = blocks(); baseline = checks.parse_coverage(fixture(rows))
        for row in rows[:4]: row.update(status='met', reason='-', slack_printed_ns=0.1)
        rows[0]['constrained_pin'] += '_renamed'
        result = checks.compare(baseline, checks.parse_coverage(fixture(rows)))
        self.assertFalse(result['closed'])
        self.assertIn('native check identity set changed', result['failures'])

    def test_both_sides_renamed_unknowns_cannot_redefine_the_baseline(self):
        rows = blocks()
        rows[0]['constrained_pin'] += '_renamed'
        baseline = checks.parse_coverage(fixture(rows))
        for row in rows[:4]: row.update(status='met', reason='-', slack_printed_ns=0.1)
        with self.assertRaisesRegex(ValueError, 'exact frozen four'):
            checks.compare(baseline, checks.parse_coverage(fixture(rows)))

    def test_false_marker_timeout_or_wrong_native_stage_is_rejected(self):
        for field, value in [('completion_marker',False),('tool_timed_out',True),
                             ('schema','unrelated'),('status','FAILED'),('stage','edit')]:
            with self.subTest(field=field):
                receipt = native_receipt([]); receipt[field] = value
                with self.assertRaisesRegex(ValueError, 'schema/status/stage/marker/timeout'):
                    checks.execution_signature(receipt)

    def test_frozen_reference_cannot_be_replaced_by_a_new_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory)/'changed.rpt'
            changed.write_text(checks.DEFAULT.read_text()+'\n')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(checks.main(['--baseline',str(changed),'--require-closed']),1)
            self.assertIn('Original frozen coverage signature changed',json.loads(output.getvalue())['error'])

    def test_sdc_library_map_drift_is_rejected_even_if_clock_table_matches(self):
        for change in ['original_sdc','pt_add_input','pt_add_output','library','map']:
            with self.subTest(change=change):
                receipt = native_receipt([])
                if change in ['original_sdc','pt_add_input']:
                    name = 'reference-full-soc.sdc' if change=='original_sdc' else 'constraints-pt-add.sdc'
                    next(r for r in receipt['inputs'] if Path(r['path']).name==name)['sha256']='0'*64
                elif change=='pt_add_output': receipt['outputs']['original-constraints-pt-add.sdc']['sha256']='0'*64
                elif change=='library': receipt['libraries'][0]['sha256']='0'*64
                else: receipt['source_mapped_sha256']='0'*64
                with self.assertRaisesRegex(ValueError, 'signature'):
                    checks.execution_signature(receipt)

    def test_met_summary_without_native_identity_is_not_proof(self):
        rows = blocks(); baseline = checks.parse_coverage(fixture(rows))
        for row in rows[:4]: row.update(status='met', reason='-', slack_printed_ns=0.1)
        result = checks.compare(baseline, checks.parse_coverage(fixture(rows, include_met=False)))
        self.assertFalse(result['closed'])
        self.assertIn('candidate lacks full native check identities', result['failures'])

    def test_other_untested_reason_change_is_rejected(self):
        rows = blocks(); baseline = checks.parse_coverage(fixture(rows))
        for row in rows[:4]: row.update(status='met', reason='-', slack_printed_ns=0.1)
        rows[4]['reason'] = 'constant_disabled'
        result = checks.compare(baseline, checks.parse_coverage(fixture(rows)))
        self.assertFalse(result['closed'])
        self.assertIn('other native check states/reasons changed', result['failures'])

    def test_omitted_or_duplicate_detail_is_rejected(self):
        text = fixture(blocks())
        with self.assertRaisesRegex(ValueError, 'Unparsed native'):
            checks.parse_coverage(text.replace('untested  unknown', 'untested  no_clock', 1).replace('untested  unknown', 'unparsed', 1))
        row = text[text.index('u_fixture/other_reg/RDN(low)'):text.index('u_fixture/already_met_reg/D')]
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            checks.parse_coverage(text+row)

    def test_native_log_and_clock_output_receipt_hashes_are_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            coverage=folder/'coverage.rpt'; coverage.write_text(fixture(blocks()))
            log=folder/'native.log'; log.write_text('Warning: clocks cannot expand (PTE-052)\n')
            clocks=folder/'clocks.rpt'; clocks.write_text('Clock Period Waveform Attrs Sources\nxu_lfextclk 30517.58 {0 15258.8} {lfextclk}\nxu_plldiv_envelope\n 6.67 {0 3.33333} G {clkout}\n')
            self.assertEqual(set(checks.parse_clocks(clocks.read_text())), {'xu_lfextclk','xu_plldiv_envelope'})
            receipt=folder/'execution.json';receipt.write_text(json.dumps(native_receipt([coverage,log,clocks])))
            bound=checks.bind_native(coverage,[log],clocks,receipt)
            self.assertEqual(bound['pte_052_count'],1)
            self.assertEqual(bound['failures'],[])
            log.write_text('warning removed\n')
            with self.assertRaisesRegex(ValueError,'binding mismatch'):
                checks.bind_native(coverage,[log],clocks,receipt)

    def test_cli_closure_requires_bound_full_baseline_and_unchanged_clocks(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = blocks()
            folders = [Path(directory)/name for name in ['before','after']]
            for index, folder in enumerate(folders):
                folder.mkdir()
                if index:
                    for row in rows[:4]: row.update(status='met', reason='-', slack_printed_ns=0.04)
                (folder/'coverage.rpt').write_text(fixture(rows))
                (folder/'native.log').write_text('clean native tool execution\n')
                (folder/'clocks.rpt').write_text('xu_lfextclk 30517.58 {0 15258.8} {lfextclk}\n')
                payloads = [folder/name for name in ['coverage.rpt','native.log','clocks.rpt']]
                (folder/'execution.json').write_text(json.dumps(native_receipt(payloads)))
            before, after = folders
            args = ['--baseline',str(before/'coverage.rpt'),'--coverage',str(after/'coverage.rpt'),
                    '--baseline-details',str(before/'coverage.rpt'),
                    '--baseline-clocks',str(before/'clocks.rpt'),
                    '--baseline-execution',str(before/'execution.json'),
                    '--clocks',str(after/'clocks.rpt'),'--log',str(after/'native.log'),
                    '--execution',str(after/'execution.json'),'--require-closed']
            output = io.StringIO()
            # The compact fixture exercises CLI wiring; production always pins
            # the immutable 8.5 MB original, not this synthetic summary.
            with mock.patch.object(checks,'FROZEN_COVERAGE_SHA256',checks.file_identity(before/'coverage.rpt')['sha256']):
                with redirect_stdout(output): self.assertEqual(checks.main(args),0)
            self.assertTrue(json.loads(output.getvalue())['closed'])
            (before/'clocks.rpt').write_text('xu_lfextclk 30517.58 {0 1} {lfextclk}\n')
            output = io.StringIO()
            with mock.patch.object(checks,'FROZEN_COVERAGE_SHA256',checks.file_identity(before/'coverage.rpt')['sha256']):
                with redirect_stdout(output): self.assertEqual(checks.main(args),1)
            self.assertEqual(json.loads(output.getvalue())['status'],'INVALID_NATIVE_EVIDENCE')


if __name__ == '__main__':
    unittest.main()
