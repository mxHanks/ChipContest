#!/usr/bin/env python3
"""Review LF-contract native receipts and exact input-delay changes, without EDA.

Coverage is accepted only from lf_contract_coverage.py with matching report
digests. This is a new external contract, never original-SDC or CDC/RDC signoff.
Numeric exact-source paths and fresh exported-SDC replay remain separate gates.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SPEC = importlib.util.spec_from_file_location('lf_receipt_checks', HERE / 'unknown_checks.py')
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)
TOOL_SHA = 'afdcfa7071f86d229ed3b4481f67adefd1c51bb0288b7e7d370213a43b70c9ef'
HIERARCHY_SHA = '8465d9b61c98fd44a8d72161ac1f9918235b1b5a5703d3be4c04860981923544'
COMMON_SHA = '95213a81ca010e2db5b8b66ddfb460d6a0c766192f8c83b830f1b8569fcdaba8'
DATA_PORTS = ('io_pads_bootrom_n_i_ival', 'io_pads_aon_pmu_dwakeup_n_i_ival')
RESET_PORT = 'io_pads_aon_erst_n_i_ival'
ALLOWED_POLARITIES = {(p, e) for p in DATA_PORTS for e in ('rise', 'fall')} | {(RESET_PORT, 'rise')}
AON = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
TARGETS = [(DATA_PORTS[0], AON + 'bootrom_deglitch/T_8_reg/D'),
           (DATA_PORTS[1], AON + 'dwakeup_deglitch/T_8_reg/D')]
TARGETS += [(RESET_PORT, AON + 'u_sirv_aon/u_sirv_pmu/' + name + '/SDN')
            for name in ('erst_reset_r_reg', 'erst_reset_r_r_reg')]
TARGETS += [(RESET_PORT, AON + 'aonrst_catch/reset_n_catch_reg/reg_' + str(i) + '/q_reg/RDN')
            for i in range(3)]
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
DELAY_ROW = re.compile(r'^\s*(' + NUMBER + r'|--)\s+(' + NUMBER + r'|--)\s+('
                       + NUMBER + r'|--)\s+(' + NUMBER + r'|--)\s+(\S+)')


def record(path):
    path = Path(path)
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
            size += len(data)
    return dict(path=str(path.resolve()), bytes=size, sha256=digest.hexdigest())


def require(value, message):
    if not value:
        raise ValueError(message)


def matches(path, entry):
    actual = record(path)
    require(all(actual[k] == entry[k] for k in ('bytes', 'sha256')),
            'Receipt/catalog bytes or SHA mismatch: ' + str(path))
    return actual


def parse_ports(text):
    """Keep each pad polarity and related clock, including multi-clock rows."""
    header = re.search(r'(?m)^ Input Port\s+Rise\s+Fall\s+Rise\s+Fall.*\n-+\n', text)
    require(header, 'Missing native report_port input-delay table')
    ports = {}
    current = None
    for line in text[header.end():].splitlines():
        if line.strip() == '1':
            continue
        if line and not line[0].isspace():
            fields = line.split(maxsplit=1)
            current = fields[0]
            require(current not in ports, 'Duplicate port block: ' + current)
            ports[current] = {'rise': [], 'fall': []}
            line = fields[1] if len(fields) == 2 else ''
        row = DELAY_ROW.match(line)
        if row:
            require(current is not None, 'Delay without native port')
            values = row.groups()
            for polarity, left, right in (('rise', 0, 2), ('fall', 1, 3)):
                low, high = values[left], values[right]
                require((low == '--') == (high == '--'),
                        'Partial min/max input delay: ' + current + '/' + polarity)
                if low != '--':
                    ports[current][polarity].append((float(low), float(high), values[4]))
        elif line.strip():
            require(set(line.split()) <= {'--'}, 'Unparsed native port row: ' + line)
    require(ports, 'No native port delays parsed')
    for polarities in ports.values():
        for polarity in polarities:
            require(len(polarities[polarity]) == len(set(polarities[polarity])),
                    'Duplicate native input delay')
            polarities[polarity].sort()
    return ports


def compare_ports(before, after):
    require(set(before) == set(after), 'Input port set changed')
    changes = []
    for port in sorted(before):
        for polarity in ('rise', 'fall'):
            if before[port][polarity] != after[port][polarity]:
                changes.append(dict(port=port, polarity=polarity,
                                    before=before[port][polarity], after=after[port][polarity]))
    require({(x['port'], x['polarity']) for x in changes} == ALLOWED_POLARITIES,
            'Input delay changes are not exactly the permitted five pad polarities')
    for port in (*DATA_PORTS, RESET_PORT):
        for polarity in ('rise', 'fall'):
            require(before[port][polarity] == [(0.0, 0.5, 'xu_hfextclk')],
                    'Original target input delay differs: ' + port + '/' + polarity)
            expected = ([(1.0, 2.0, 'xu_lfextclk(f)')] if (port, polarity) in ALLOWED_POLARITIES
                        else [(0.0, 0.5, 'xu_hfextclk')])
            require(after[port][polarity] == expected,
                    'Revised input delay differs: ' + port + '/' + polarity)
    return dict(input_port_count=len(before), changed_polarities=changes,
                erst_fall_original_hf_delay_preserved=True, all_other_polarities_equal=True)


def active_sdc(text):
    return [' '.join(line.split()) for line in text.replace('\\\n', ' ').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def overlay_review(text):
    # Exact executable-text allowlist also checks the pad-count/clock guards;
    # comments and whitespace may change without accepting new Tcl behavior.
    expected = '''set xu_lf_v1_clock [get_clocks -quiet xu_lfextclk]
if {[sizeof_collection $xu_lf_v1_clock] != 1 ||
abs([get_attribute $xu_lf_v1_clock period] - 30517.578125) > 0.000001} {
error {LF contract v1 requires the original 32.768 kHz clock}
}
set xu_lf_v1_data [get_ports -quiet {io_pads_bootrom_n_i_ival io_pads_aon_pmu_dwakeup_n_i_ival}]
set xu_lf_v1_reset [get_ports -quiet io_pads_aon_erst_n_i_ival]
if {[sizeof_collection $xu_lf_v1_data] != 2 || [sizeof_collection $xu_lf_v1_reset] != 1} {
error {LF contract v1 requires exactly the three named input pads}
}
remove_input_delay $xu_lf_v1_data
set_input_delay -clock xu_lfextclk -clock_fall -min 1.0 $xu_lf_v1_data
set_input_delay -clock xu_lfextclk -clock_fall -max 2.0 $xu_lf_v1_data
remove_input_delay -rise $xu_lf_v1_reset
set_input_delay -clock xu_lfextclk -clock_fall -rise -add_delay -min 1.0 $xu_lf_v1_reset
set_input_delay -clock xu_lfextclk -clock_fall -rise -add_delay -max 2.0 $xu_lf_v1_reset'''
    require(active_sdc(text) == active_sdc(expected), 'Overlay executable text differs from reviewed v1 allowlist')
    return dict(only_input_delay_commands_mutate_design_constraints=True,
                no_exceptions_case_analysis_clock_groups_multicycle_or_ideal_network_added=True)


def export_comparison(before, after):
    # Ignore the exact three target ports' input-delay commands only. The port
    # audit separately requires all five changes and preserved ERST falling.
    def retained(text):
        return Counter(line for line in active_sdc(text)
                       if not (line.startswith('set_input_delay ')
                               and any('{'+port+'}' in line for port in (*DATA_PORTS, RESET_PORT))))
    require(retained(before) == retained(after),
            'Exported constraints changed beyond the three whitelisted input pads')
    return dict(all_other_exported_constraint_commands_identical=True)


def numeric_paths(run_dir, prefix):
    """Require the exact pad to pin paths, both delays, LF fall to LF rise."""
    result = []
    for index, (port, pin) in enumerate(TARGETS):
        for delay in ('min', 'max'):
            name = f'{prefix}-target-{index}-{delay}.rpt'
            text = (Path(run_dir) / name).read_text()
            paths = re.split(r'(?m)^  Startpoint:', text)[1:]
            require(len(paths) == (2 if index < 2 else 1), 'Missing/excess exact-source paths: ' + name)
            slacks, arrivals, required = [], [], []
            source_edges = []
            for part in paths:
                require(part.split()[0] == port, 'Wrong source pad: ' + name)
                require(re.search(r'(?m)^  Endpoint:\s+' + re.escape(pin.rsplit('/', 1)[0]) + r'\s*$', part),
                        'Wrong exact endpoint: ' + name)
                require(re.search(r'(?m)^  Path Type:\s+' + delay + r'\s*$', part), 'Wrong path delay type: ' + name)
                require(re.findall(r'clock (\S+) \((rise|fall) edge\)', part)
                        == [('xu_lfextclk', 'fall'), ('xu_lfextclk', 'rise')], 'Wrong launch/capture clock edges: ' + name)
                edge = re.search(r'input external delay\s+(' + NUMBER + r')\s+(' + NUMBER + r')\s+([rf])', part)
                require(edge and float(edge[1]) == (1.0 if delay == 'min' else 2.0), 'Wrong external delay: ' + name)
                source_edges.append(edge[3])
                require(pin + ' (' in part, 'Exact constrained pin absent from path: ' + name)
                slack = re.findall(r'slack \(MET\)\s+(' + NUMBER + r')', part)
                require(len(slack) == 1 and float(slack[0]) > 0, 'Missing/nonpositive numeric MET slack: ' + name)
                arrival = re.findall(r'(?m)^  data arrival time\s+(' + NUMBER + r')\s*$', part)
                needed = re.findall(r'(?m)^  data required time\s+(' + NUMBER + r')\s*$', part)
                require(len(arrival) == 2 and len(needed) == 2, 'Numeric arrival/required absent: ' + name)
                slacks.append(float(slack[0])); arrivals.append(float(arrival[0])); required.append(float(needed[0]))
            require(set(source_edges) == ({'r', 'f'} if index < 2 else {'r'}), 'Source polarity mismatch: ' + name)
            result.append(dict(report=name, paths=len(paths), source=port, target=pin, delay_type=delay,
                               source_polarities=sorted(source_edges), slack_ns=slacks,
                               arrival_ns=arrivals, required_ns=required))
    return dict(reports=14, paths=sum(x['paths'] for x in result),
                minimum_slack_ns=min(min(x['slack_ns']) for x in result), details=result)


def review(run_dir, coverage_path, source_dir=None):
    run_dir = Path(run_dir)
    source_dir = Path(source_dir) if source_dir else run_dir.parent / 'src'
    errors, evidence, limitations = [], {}, []

    def stage(name, function):
        try:
            evidence[name] = function()
        except (ValueError, KeyError, OSError, TypeError) as error:
            errors.append(name + ': ' + str(error))

    receipt = json.loads((run_dir / 'execution.json').read_text())

    def receipt_review():
        require(receipt.get('schema') == 'lf-input-contract-native-v1'
                and receipt.get('status') == 'COLLECTED_REQUIRES_REVIEW'
                and receipt.get('returncode') == 0
                and receipt.get('native_tool_errors') == []
                and not receipt.get('timed_out', False)
                and receipt.get('netlist_modified') is False
                and receipt.get('constraint_revision') == 'team-lf-input-v1', 'Unclean or wrong native receipt')
        require(receipt.get('tool', {}).get('sha256') == TOOL_SHA, 'Native PT binary differs')
        require({x['role']: x['sha256'] for x in receipt['libraries']} == checks.LIBRARIES,
                'Original library roles/digests differ')
        require(len(receipt['libraries']) == 2, 'Library entry count differs')
        expected = {'mapped.v': checks.MAPPED_SHA256, 'reference-full-soc.sdc': checks.ORIGINAL_SDC_SHA256,
                    'hierarchy_contract.tcl': HIERARCHY_SHA, 'common.tcl': COMMON_SHA}
        inputs = {Path(x['path']).name: x for x in receipt['inputs']}
        require(len(inputs) == len(receipt['inputs']) == 8, 'Unexpected/duplicate input entries')
        for name, digest in expected.items():
            require(inputs[name]['sha256'] == digest, 'Original input differs: ' + name)
        for entry in receipt['libraries']:
            require(inputs[Path(entry['path']).name]['sha256'] == entry['sha256'], 'Input/library binding differs')
        for name in ('common.tcl', 'pt_lf_contract.tcl', 'xu_lf_input_contract_v1.sdc'):
            matches(source_dir / name, inputs[name])
            local = (ROOT / 'tools/ppa' / name if name.endswith('.sdc') else HERE / name)
            require(record(local)['sha256'] == inputs[name]['sha256'],
                    'Executed source differs from repository: ' + name)
        require(record(source_dir / 'run_lf_contract_native.py')['sha256']
                == record(HERE / 'run_lf_contract_native.py')['sha256'], 'Returned native driver differs')
        require(record(run_dir / 'original-constraints-pt-add.sdc')['sha256'] == checks.PT_ADD_SHA256,
                'PT portability SDC differs')
        require(record(run_dir / 'config.tcl')['sha256'] == receipt['config_sha256'], 'Config digest differs')
        config = (run_dir / 'config.tcl').read_text()
        require(all(x['path'] in config and x['sha256'] in config for x in receipt['inputs']),
                'Config does not bind each recorded input path/digest')
        require((run_dir / 'LF_CONTRACT_COLLECTION_COMPLETE.txt').read_text().strip()
                == 'COLLECTED_NOT_TIMING_CLOSURE_NOT_QUALIFIED', 'Completion marker differs')
        log = (run_dir / 'native.log').read_text()
        require(not re.search(r'(?m)^\s*(?:Error|Fatal)\s*:', log), 'Native log has Error/Fatal')
        require(receipt.get('max_cores') == 8 and len(receipt.get('affinity', [])) == 8,
                'Unexpected core/affinity receipt')
        return dict(receipt=record(run_dir / 'execution.json'), native_error_fatal_count=0,
                    original_map_sdc_hierarchy_libraries_bound=True, netlist_modified=False)

    stage('receipt_and_inputs', receipt_review)

    def outputs_review():
        outputs = receipt['outputs']
        require(set(outputs) == {p.name for p in run_dir.iterdir() if p.is_file() and p.name != 'execution.json'},
                'Run file set differs from native receipt')
        for name, item in outputs.items():
            require(Path(name).name == name, 'Non-flat/unsafe native output name')
            matches(run_dir / name, item)
        for name in (run_dir / 'required-reports.list').read_text().splitlines():
            require(name in outputs and outputs[name]['bytes'] > 0, 'Missing/empty required report: ' + name)
        return dict(output_files_verified=len(outputs), all_bytes_sha256_match=True)

    stage('output_catalog', outputs_review)
    stage('overlay', lambda: overlay_review((source_dir / 'xu_lf_input_contract_v1.sdc').read_text()))
    stage('input_delay_difference', lambda: compare_ports(parse_ports((run_dir / 'original-ports.rpt').read_text()),
                                                         parse_ports((run_dir / 'revised-ports.rpt').read_text())))

    def clock_review():
        before = checks.parse_clocks((run_dir / 'original-clocks.rpt').read_text())
        after = checks.parse_clocks((run_dir / 'revised-clocks.rpt').read_text())
        require(before == after and set(before) == {'xu_hfextclk', 'xu_lfextclk', 'xu_jtag_tck', 'xu_plldiv_envelope'},
                'Four native clock definitions changed')
        require(re.sub(r'(?m)^Date\s*:.*\n', '', (run_dir / 'original-clocks.rpt').read_text())
                == re.sub(r'(?m)^Date\s*:.*\n', '', (run_dir / 'revised-clocks.rpt').read_text()),
                'Native clock source/master/modification changed')
        return dict(four_clock_reports_identical_except_date=True,
                    exact_periods_bound_by_original_sdc_and_unchanged_overlay=True)

    stage('clocks', clock_review)

    def violations_review():
        for name in ('original-constraints.rpt', 'revised-all_violators.rpt', 'revised-exceptions.rpt'):
            text = (run_dir / name).read_text()
            split = re.split(r'(?m)^\*{10,}\s*$', text)
            require(len(split) == 3 and split[-1].strip() == '1',
                    'Nonempty/unparsed native violations or exceptions: ' + name)
        return dict(original_and_revised_all_violators_empty=True, revised_native_exceptions_empty=True)

    stage('native_violations_and_exceptions', violations_review)

    def coverage_review():
        data = coverage_path if isinstance(coverage_path, dict) else json.loads(Path(coverage_path).read_text())
        require(data.get('schema') == 'ingress1064-lf-contract-full-coverage-difference-v1'
                and data.get('coverage_transition_pass') is True and data.get('failures') == []
                and data.get('original_sdc_verdict') == 'UNCHANGED_UNKNOWN4_NOT_CLOSED',
                'Missing/failed full-identity coverage review')
        matches(run_dir / 'original-coverage.rpt', data['baseline_full'])
        matches(run_dir / 'revised-coverage-all.rpt', data['candidate_full'])
        require(data['parser']['sha256'] == record(HERE / 'unknown_checks.py')['sha256'], 'Coverage parser changed')
        return dict(review=(dict(recomputed_in_process=True) if isinstance(coverage_path, dict) else record(coverage_path)), complete_native_check_identities=True,
                    exactly_four_unknown_to_met=True, summary=data['current_summary']['All Checks'])

    stage('coverage', coverage_review)

    def partial_input_review():
        text = (run_dir / 'revised-check_timing.rpt').read_text()
        warning = re.search(r'(?im)^Warning:.*partially defined input delays', text)
        if warning:
            # PrimeTime diagnoses each clock association separately. The exact
            # port audit must prove no physical pad polarity was removed; only
            # then can the single split-reference warning be retained openly.
            require('input_delay_difference' in evidence,
                    'Partial input warning without accepted complete pad-polarity audit')
            block = re.search(r'(?ms)^Ports\n-+\n(.*?)\n\n', text[warning.end():])
            require(block and block[1].split() == [RESET_PORT]
                    and 'There is 1 port with partially defined input delays' in warning[0],
                    'Unexpected native partial_input_delay port/count')
        return dict(no_partial_input_delay_warning=not bool(warning),
                    retained_erst_split_clock_reference_warning=bool(warning),
                    all_pad_polarities_proven_complete_by_report_port=True,
                    other_check_timing_warnings=[line for line in text.splitlines() if line.startswith('Warning:')])

    stage('check_timing_partial_input', partial_input_review)
    stage('numeric_exact_source_paths', lambda: numeric_paths(run_dir, 'revised'))
    original_export = run_dir / 'original-export.sdc'
    if original_export.exists():
        stage('all_other_exported_constraints', lambda: export_comparison(original_export.read_text(),
                                                                         (run_dir / 'revised-export.sdc').read_text()))
    else:
        limitations.append('No pre-overlay native export/mode reports; unchanged exception/case/disabled commands '
                           'are established by sealed original/common/overlay source, not a native before-after mode-report diff.')
    limitations += ['Fresh exported-SDC reload requires separate accepted evidence.',
                    'ERST falling HF delay is diagnostic continuity, not proof of arbitrary-phase assertion CDC/RDC legality.',
                    'Original frozen SDC retains four unknown checks. This new LF contract does not close that result.']
    return dict(schema='ingress1064-lf-contract-native-receipt-review-v1',
                status=('LF_CONTRACT_RECEIPTS_COVERAGE_PORTS_PASS_PATH_REPLAY_REQUIRED' if not errors
                        else 'REJECTED_NATIVE_LF_CONTRACT_EVIDENCE'),
                receipt_coverage_ports_pass=not errors, failures=errors, evidence=evidence, limitations=limitations,
                qualification='NEW_INPUT_CONTRACT_ONLY_NOT_ORIGINAL_SDC_OR_CDC_RDC_SIGNOFF',
                original_sdc_verdict='UNCHANGED_UNKNOWN4_NOT_CLOSED')


def audit(rootdir, export_dir=None, coverage_path=None):
    """Recompute coverage and native review for a safely extracted archive root."""
    rootdir = Path(rootdir)
    run_dir = rootdir / 'run' if (rootdir / 'run').is_dir() else rootdir
    spec = importlib.util.spec_from_file_location('lf_full_coverage_audit', HERE / 'lf_contract_coverage.py')
    coverage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(coverage)
    result = review(run_dir, coverage_path if coverage_path is not None else
                    coverage.audit(run_dir / 'original-coverage.rpt', run_dir / 'revised-coverage-all.rpt'))
    if export_dir is not None:
        try:
            result['evidence']['export_replay'] = export_review(run_dir, export_dir)
        except (ValueError, OSError, KeyError, TypeError) as error:
            result['failures'].append('export_replay: ' + str(error))
        result['receipt_coverage_ports_pass'] = not result['failures']
        result['status'] = ('LF_CONTRACT_NATIVE_AND_EXPORT_REPLAY_PASS' if not result['failures']
                            else 'REJECTED_NATIVE_LF_CONTRACT_EVIDENCE')
    return result


def export_review(native_run, export_dir):
    export_dir = Path(export_dir)
    if (export_dir / 'run').is_dir():
        export_dir /= 'run'
    receipt = json.loads((export_dir / 'execution.json').read_text())
    prior = json.loads((native_run / 'execution.json').read_text())
    require(receipt.get('schema') == 'lf-input-contract-export-replay-v1'
            and receipt.get('status') == 'COLLECTED_REQUIRES_REVIEW'
            and receipt.get('returncode') == 0 and receipt.get('native_tool_errors') == []
            and not receipt.get('timed_out', False), 'Wrong/unclean export-replay receipt')
    require(receipt['prior_execution_sha256'] == record(native_run / 'execution.json')['sha256']
            and receipt['exported_sdc_sha256'] == record(native_run / 'revised-export.sdc')['sha256'],
            'Export replay does not bind this native run/export')
    require(receipt['tool'] == prior['tool'] and receipt['libraries'] == prior['libraries'],
            'Export replay tool/libraries differ')
    require(receipt['script_sha256'] == record(HERE / 'pt_lf_contract_export.tcl')['sha256']
            and receipt['driver_sha256'] == record(HERE / 'run_lf_contract_export_native.py')['sha256'],
            'Export replay script/driver differ')
    require(receipt['script_sha256'] == record(export_dir.parent / 'probe.tcl')['sha256']
            and receipt['driver_sha256'] == record(export_dir.parent / 'driver.py')['sha256'],
            'Returned export source differs from execution receipt')
    require(record(export_dir / 'config.tcl')['sha256'] == receipt['config_sha256'], 'Export config digest differs')
    outputs = receipt['outputs']
    require(set(outputs) == {p.name for p in export_dir.iterdir() if p.is_file() and p.name != 'execution.json'},
            'Export output file set differs')
    for name, entry in outputs.items():
        require(Path(name).name == name, 'Unsafe export output name')
        matches(export_dir / name, entry)
    require((export_dir / 'LF_CONTRACT_EXPORT_COLLECTION_COMPLETE.txt').read_text().strip()
            == 'COLLECTED_NOT_TIMING_CLOSURE_NOT_QUALIFIED', 'Export completion marker differs')
    require(not re.search(r'(?m)^\s*(?:Error|Fatal)\s*:', (export_dir / 'native.log').read_text()),
            'Export native log has Error/Fatal')
    for name in (export_dir / 'required-reports.list').read_text().splitlines():
        require(name in outputs and outputs[name]['bytes'] > 0, 'Missing export required report: ' + name)
    require(parse_ports((export_dir / 'exported-ports.rpt').read_text())
            == parse_ports((native_run / 'revised-ports.rpt').read_text()), 'Export input-delay semantics differ')
    require(checks.parse_clocks((export_dir / 'exported-clocks.rpt').read_text())
            == checks.parse_clocks((native_run / 'revised-clocks.rpt').read_text()), 'Export printed clock semantics differ')
    native_cov = checks.parse_coverage((native_run / 'revised-coverage.rpt').read_text())
    export_cov = checks.parse_coverage((export_dir / 'exported-coverage.rpt').read_text())
    require(native_cov['summary'] == export_cov['summary'] and native_cov['design'] == export_cov['design']
            and checks.states(native_cov) == checks.states(export_cov) and not checks.unknowns(export_cov),
            'Export coverage summary/non-met identities differ or unknown remains')
    require(re.sub(r'(?m)^Date\s*:.*\n', '', (native_run / 'revised-all_violators.rpt').read_text())
            == re.sub(r'(?m)^Date\s*:.*\n', '', (export_dir / 'exported-all_violators.rpt').read_text()),
            'Export native electrical/timing violations differ')
    return dict(receipt=record(export_dir / 'execution.json'), output_files_verified=len(outputs),
                original_run_and_export_sha_bound=True, coverage_summary_and_nonmet_identities_equal=True,
                port_polarities_and_printed_clocks_equal=True, numeric_paths=numeric_paths(export_dir, 'exported'),
                limitation='write_sdc decimal serialization is replayed as exported; original exact clock source remains separately SHA-bound.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path)
    parser.add_argument('--native-dir', type=Path)
    parser.add_argument('--export-dir', type=Path)
    parser.add_argument('--coverage-review', type=Path)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    try:
        require(bool(args.run_dir) != bool(args.native_dir), 'Specify exactly one --native-dir or --run-dir')
        if args.native_dir or not args.coverage_review:
            result = audit(args.native_dir or args.run_dir, args.export_dir, args.coverage_review)
        else:
            require(args.export_dir is None, '--export-dir requires recomputed audit via --native-dir')
            result = review(args.run_dir, args.coverage_review, args.source_dir)
    except (ValueError, OSError, KeyError, TypeError) as error:
        result = dict(status='INVALID_NATIVE_RECEIPT_EVIDENCE', receipt_coverage_ports_pass=False, failures=[str(error)])
    if args.out:
        require(not args.out.exists(), 'Refuse to overwrite native review')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['receipt_coverage_ports_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
