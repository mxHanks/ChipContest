#!/usr/bin/env python3
"""xu: verify exported FM16/17 and repair19/21 records without qualifying them."""
import argparse
import collections
import hashlib
import json
import lzma
from pathlib import Path, PurePosixPath
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPORT_SHA = 'a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d'
SOURCE_MANIFEST_SHA = '19968bd0ecc5fd25a3e9f2a698040f472bbb9d696bcba624ad4b03abc85d5ba7'
SDC_SHA = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
SCOPE_SHA = '45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e'
CASES = {
    's2d': dict(fm='s2d-formality-campaign-20261103-16', repair='s2d-hold-gating-repair-20261103-19',
                original='025240541e4c58318c9fa44e816b54cbcc78f29cd8b5ea8672343a3840118137',
                repaired='7f1c1efaa27d9eb06a6e8a1979d43df3b7a0eaadb992c1096c4bf36f19477bab',
                passing=[17136, 0, 0, 0, 144, 26121, 39, 43440], frozen=158, unmatch=17, macros=336,
                source_count=155, untested=27237, cap=87, mincap=1404, noclock=9239,
                disabled=17672, rdn=8786, dc_slack='-366.31', whole_area='3387946.249303', accel_area='311751.6765',
                main='3af4db98b893edd2103771fa132d69350b82ba96', child='dd692c190dadafd9baa6dffe8514a3f684e7fbf5'),
    'pe32': dict(fm='pe32-formality-campaign-20261103-17', repair='pe32-hold-gating-repair-20261103-21',
                 original='ca1d17a9adcd1a15e7b69758754e68d962c7535d8f2b31407c47d9bd136014c8',
                 repaired='8aa1d86f72e4752e35a117ffa5359cd4cb76f1fc11130f3f178693ed584b8bbb',
                 passing=[17952, 0, 0, 0, 144, 29623, 39, 47758], frozen=161, unmatch=33, macros=352,
                 source_count=158, untested=28610, cap=51, mincap=1410, noclock=9220,
                 disabled=19064, rdn=8767, dc_slack='-366.30', whole_area='3615601.175056', accel_area='539763.4679',
                 main='94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114', child='fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5')}
CHECKS = 'setup hold recovery removal min_period min_pulse_width clock_gating_setup clock_gating_hold out_setup out_hold'.split()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unique(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'duplicate JSON key')
        out[key] = value
    return out


def jload(data):
    return json.loads(data, object_pairs_hook=unique)


def safe_path(root, relative):
    p = PurePosixPath(relative)
    need(isinstance(relative, str) and not p.is_absolute() and '..' not in p.parts
         and str(p) == relative and relative != '.', 'unsafe archive path')
    f = root
    for part in p.parts:
        f = f / part
        need(not f.is_symlink(), 'symlink in archive path')
    need(f.is_file(), 'archive file missing')
    return f


def load(root=HERE):
    manifest = jload((root / 'selected-manifest.json').read_bytes())
    need(manifest['schema'] == 'xu-selected-server-evidence-v1', 'archive schema differs')
    exported = (root / 'source-export-manifest.json').read_bytes()
    need(sha(exported) == SOURCE_MANIFEST_SHA, 'original export manifest differs')
    origin = jload(exported)
    need(len(origin) == 142 and len({x['path'] for x in origin}) == 142, 'export payload count differs')
    source = manifest['source_export']
    need(source == dict(name='terminal-results-export-22.tar.xz', bytes=807588,
                        sha256=EXPORT_SHA, manifest_sha256=SOURCE_MANIFEST_SHA, payload_count=142),
         'export identity differs')
    originals = {e['path']: e for e in origin}
    groups = {c[k] for c in CASES.values() for k in ['fm', 'repair']}
    expected = {name for name in originals if name.split('/')[0] in groups}
    need(len(expected) == 60 and {e['path'] for e in manifest['selected_files']} == expected,
         'selected payload coverage differs')
    need(len(manifest['selected_files']) == 60 and len(manifest['context_files']) == 9,
         'selected/context count differs')
    raw, stored_seen = {}, set()
    for e in manifest['selected_files'] + manifest['context_files']:
        need(e['path'] not in raw and e['stored_path'] not in stored_seen, 'duplicate selected path')
        stored_seen.add(e['stored_path'])
        need(e['stored_path'] in ['raw/' + e['path'], 'raw/' + e['path'] + '.xz'], 'stored naming differs')
        b = safe_path(root, e['stored_path']).read_bytes()
        need(len(b) == e['stored_bytes'] and sha(b) == e['stored_sha256'], 'stored raw bytes differ')
        b = lzma.decompress(b) if e['stored_path'].endswith('.xz') else b
        need(len(b) == e['bytes'] and sha(b) == e['sha256'], 'expanded raw bytes differ')
        if e in manifest['selected_files']:
            need(originals[e['path']] == {k: e[k] for k in ['path', 'bytes', 'sha256']}, 'export origin differs')
        else:
            need(safe_path(ROOT, e['source_local_path']).read_bytes() == b, 'prior committed context differs')
        raw[e['path']] = b
    actual = {str(f.relative_to(root)) for f in (root / 'raw').rglob('*') if f.is_file()}
    need(actual == stored_seen, 'unmanifested/missing raw file')
    return raw, manifest


def analyze(raw):
    def text(name):
        return raw[name].decode()
    results = {}
    need(sha(raw['context/xu-timing-scope-proposal-16.tcl']) == SCOPE_SHA, 'timing scope differs')
    for tag, c in CASES.items():
        fm, timing = c['fm'], c['repair']
        fs = jload(raw[fm + '/state.json'])
        need(fs['status'] == 'EXECUTED_REVIEW_PENDING_NOT_QUALIFIED' and len(fs['runs']) == 1,
             'FM terminal state differs')
        r = fs['runs'][0]
        need(r['candidate'] == tag and r['command'] == ['fm_shell', '-f', 'verify.tcl']
             and r['returncode'] == 0 and r['status'] == 'VERIFIED_REVIEW_PENDING_NOT_QUALIFIED',
             'FM execution differs')
        frozen = r['frozen_before']
        need(frozen == r['frozen_after'] and len(frozen) == c['frozen'], 'FM frozen inputs differ')
        for name, value in frozen.items():
            need(name == value['path'] and re.fullmatch('[0-9a-f]{64}', value['sha256'])
                 and isinstance(value['bytes'], int) and value['bytes'] > 0, 'malformed frozen input')
        prefix = 'context/' + tag + '/'
        prepared = jload(raw[prefix + 'ppa/prepared.json'])
        execution = jload(raw[prefix + 'ppa/execution.json'])
        impl = jload(raw[prefix + 'implementation/implementation.json'])
        need(prepared['implementation'] == impl, 'prepared implementation differs')
        sf = impl['source_freeze']
        need(sf['main_commit'] == c['main'] and sf['e203_commit'] == c['child'], 'candidate source differs')
        need(impl['defines'] == ['SYNTHESIS', 'DISABLE_SV_ASSERTION=1'] + (['XU_ACCEL_PE32=1'] if tag == 'pe32' else []),
             'candidate defines differ')
        need(sum(g['count'] for g in impl['memory_groups']) == c['macros'], 'candidate SRAM count differs')
        ppa_path = r['ppa_execution']['path'].rsplit('/', 1)[0]
        need(execution['netlist_sha256'] == c['original'] and execution['analysis_sdc_sha256'] == SDC_SHA,
             'original PPA identity differs')
        need(sha(raw[prefix + 'ppa/execution.json']) == r['ppa_execution']['sha256'], 'FM/PPA receipt link differs')
        for suffix in ['mapped.v', 'default.svf', 'rtl.f']:
            need(ppa_path + '/' + suffix in frozen, 'FM input missing from freeze')
        need(frozen[ppa_path + '/mapped.v']['sha256'] == c['original'], 'FM verified wrong netlist')
        need(sha(raw[prefix + 'ppa/rtl.f']) == frozen[ppa_path + '/rtl.f']['sha256']
             == prepared['generated_sha256']['rtl.f'], 'FM source list identity differs')
        sources = [x.strip() for x in text(prefix + 'ppa/rtl.f').splitlines() if x.strip() and not x.startswith('+')]
        need(len(sources) == c['source_count'] and len(set(sources)) == len(sources), 'RTL source count differs')
        need(set(frozen) == set(sources) | {ppa_path + '/' + s for s in ['mapped.v', 'default.svf', 'rtl.f']},
             'FM freeze does not cover exact source list')
        for name, src in prepared['source_files'].items():
            staged = ppa_path + '/' + name
            need(staged in frozen and frozen[staged]['sha256'] == src['sha256'], 'staged RTL/PPA identity differs')
        log_path = fm + '/' + tag + '/fm.log'
        log = text(log_path)
        need(sha(raw[log_path]) == r['log']['sha256'] and len(raw[log_path]) == r['log']['bytes'], 'FM log identity differs')
        need(log.splitlines().count('XU_FULL_SOC_FORMALITY_PASS') == 1 and 'Verification SUCCEEDED' in log
             and f"{c['passing'][-1]} Passing compare points" in log, 'FM completion missing')
        rows = re.findall(r'^Passing \(equivalent\)\s+((?:\d+\s+){7}\d+)\s*$', log, re.M)
        unread = re.findall(r'^\s*Unread\s+((?:\d+\s+){7}\d+)\s*$', log, re.M)
        need(len(rows) == len(unread) == 1 and list(map(int, rows[0].split())) == c['passing']
             and list(map(int, unread[0].split())) == [0, 0, 0, 0, 0, 511, 0, 511], 'FM category totals differ')
        need(f"{c['unmatch']}(0) Unmatched reference(implementation) compare points" in log
             and 'verification_set_undriven_signals synthesis' in log
             and 'verification_verify_directly_undriven_output false' in log
             and 'is a black box' in log, 'conditional FM scope missing')
        verify = text(fm + '/' + tag + '/verify.tcl')
        need('set synopsys_auto_setup true' in verify and 'set hdlin_unresolved_modules black_box' in verify
             and f'read_verilog -i {{{ppa_path}/mapped.v}}' in verify
             and f'set_svf {{{ppa_path}/default.svf}}' in verify, 'FM script inputs differ')
        need(('XU_ACCEL_PE32=1' in verify) == (tag == 'pe32'), 'FM variant differs')
        db_paths = re.findall(r'^read_db -technology_library \{([^}]+)\}$', verify, re.M)
        need(db_paths == [lib['path'] for lib in impl['libraries']], 'FM library paths differ')
        expected_defines = ' '.join(impl['defines'])
        need(f'read_sverilog -r -define {{{expected_defines}}}' in verify
             and f'-f {ppa_path}/rtl.f}}' in verify, 'FM reference configuration differs')
        unmatched = text(fm + '/' + tag + '/unmatched.rpt')
        points = re.findall(r'^  Ref  DFF\s+(\S+)\s*$', unmatched, re.M)
        need(len(points) == c['unmatch'] and len(set(points)) == len(points), 'unmatched report count differs')
        need(sum(x.endswith('/valid_read_reg') for x in points) == c['unmatch'] - 1
             and sum(x.endswith('/count_reg[15]') for x in points) == 1, 'unmatched scope differs')
        state = jload(raw[timing + '/state.json'])
        need(state['status'] == 'EXECUTED_NOT_QUALIFIED' and state['mapped_netlist_sha256'] == c['repaired'],
             'repair terminal/netlist identity differs')
        need(len(state['runs']) == 2, 'repair execution count differs')
        for run, tool, script, name, marker in [
            (state['runs'][0], 'dc_shell', 'repair.tcl', 'dc.log', 'XU_FULL_SOC_HOLD_REPAIR_DC_DONE_NOT_QUALIFIED'),
            (state['runs'][1], 'pt_shell', 'sta.tcl', 'pt.log', 'XU_FULL_SOC_HOLD_REPAIR_PT_DONE_NOT_QUALIFIED')]:
            need(run['tool'] == tool and run['returncode'] == 0 and run['marker_count'] == 1 and not run['errors'],
                 'repair tool failed')
            need(sha(raw[timing + '/' + name]) == run['log_sha256']
                 and sha(raw[timing + '/' + script]) == run['script_sha256'], 'repair script/log identity differs')
            need(text(timing + '/' + name).splitlines().count(marker) == 1, 'repair marker differs')
        for name, report in state['reports'].items():
            b = raw[timing + '/' + name]
            need(len(b) == report['bytes'] and sha(b) == report['sha256'], 'repair report identity differs')
        inputs = state['input_sha256']
        need(inputs[ppa_path + '/mapped.v'] == c['original'], 'repair input is not original FM netlist')
        need(next(v for k, v in inputs.items() if k.endswith('/constraints.sdc')) == SDC_SHA
             and next(v for k, v in inputs.items() if k.endswith('/xu-ts16.tcl')) == SCOPE_SHA,
             'repair SDC/scope differs')
        for lib in impl['libraries']:
            need(inputs[lib['path']] == lib['sha256'], 'recorded library identity differs')
        repair = text(timing + '/repair.tcl')
        sta = text(timing + '/sta.tcl')
        need('set_clock_gating_check -hold 0.12 [all_clocks]' in repair
             and 'compile -incremental_mapping -only_hold_time' in repair
             and 'set_clock_gating_check' not in sta and 'read_verilog mapped.v' in sta
             and 'set_propagated_clock' not in sta, 'repair/final STA clock scope differs')
        for script in [repair, sta]:
            need('constraints.sdc}' in script and 'xu-ts16.tcl}' in script
                 and f'full-SoC SRAM total must be exactly {c["macros"]}' in script, 'STA macro/scope assertion missing')
        coverage = text(timing + '/analysis-coverage.rpt')
        table = {}
        for line in coverage.splitlines():
            match = re.fullmatch(r'(\w+)\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)', line)
            if match and match[1] in CHECKS:
                need(match[1] not in table, 'duplicate coverage summary')
                table[match[1]] = dict(zip(['total', 'met', 'violated', 'untested'], map(int, match.groups()[1:])))
        need(set(table) == set(CHECKS) and all(r['total'] == r['met'] + r['violated'] + r['untested'] for r in table.values()),
             'coverage summary incomplete/nonconserving')
        need(sum(x['violated'] for x in table.values()) == table['removal']['violated'] == 5
             and sum(x['untested'] for x in table.values()) == c['untested'], 'residual timing coverage differs')
        need(table['clock_gating_hold'] == table['clock_gating_setup'] == dict(total=27, met=27, violated=0, untested=0),
             'gate check coverage differs')
        detail = coverage[coverage.index('\nu_soc/'):].lstrip('\n')
        records = []
        for block in re.split(r'(?m)(?=^\S)', detail):
            if not block or block == '1\n':
                continue
            need(block.startswith(('u_soc/', 'u_shared/')), 'unknown coverage detail')
            pin = block.splitlines()[0].strip()
            reason = re.search(r'untested\s+(\S+)', block)
            check = re.search(r'\b(' + '|'.join(CHECKS) + r')\b', block)
            need(reason is not None and check is not None, 'malformed coverage detail')
            records.append((pin, check[0], reason[1]))
        detail_checks = collections.Counter(x[1] for x in records)
        need(all(detail_checks[k] == table[k]['untested'] for k in CHECKS), 'coverage detail/summary differs')
        reasons = dict(collections.Counter(x[2] for x in records))
        need(len(records) == c['untested'] and reasons == dict(no_clock=c['noclock'], constant_disabled=c['disabled'],
             false_paths=276, unknown=2, no_endpoint_clock=48), 'untested reasons differ')
        roles = collections.Counter((reason, pin.rsplit('/', 1)[-1].split('(')[0]) for pin, check, reason in records
                                    if reason in ['no_clock', 'no_endpoint_clock', 'unknown'])
        need(roles == collections.Counter({('no_clock', 'RDN'): c['rdn'], ('no_clock', 'SDN'): 429,
             ('unknown', 'SDN'): 2, ('no_clock', 'E'): 24, ('no_endpoint_clock', 'D'): 48}), 'unresolved pin roles differ')
        constraints = text(timing + '/constraints.rpt')
        electrical = collections.Counter()
        for block in constraints.split('    Pin: ')[1:]:
            kind = re.findall(r'^\s*(?:-\s*)?(max_capacitance|min_capacitance)\s+', block, re.M)
            need(len(kind) == 1 and '(VIOLATED)' in block, 'electrical report block differs')
            electrical[kind[0]] += 1
        need(electrical == collections.Counter(max_capacitance=c['cap'], min_capacitance=c['mincap'])
             and len(re.findall(r'^  slack \(VIOLATED', constraints, re.M)) == 5, 'constraint violations differ')
        need(state['timing'] == text(timing + '/timing-slack.tsv')
             == 'delay_type\tpath_count\tworst_slack\nmax\t1\t0.000000\nmin\t1\t-0.121483\n', 'timing extrema differ')
        qor = text(timing + '/qor.rpt')
        need("Timing Path Group 'xu_hfextclk'" in qor and re.search(r'Critical Path Slack:\s+' + re.escape(c['dc_slack']), qor),
             'negative DC forwarded GPIO timing omitted')
        need('io_pads_gpioA_o_oval[27]' in text(timing + '/dc-violations.rpt') and c['dc_slack'] in text(timing + '/dc-violations.rpt'),
             'DC negative timing endpoint differs')
        check = text(timing + '/check-timing.rpt')
        need('31 endpoints which are not constrained' in check and '24 register clock pins with no clock' in check,
             'unconstrained UART/forwarded-clock scope omitted')
        area_report = text(timing + '/area.rpt')
        need('Total cell area:               ' + c['whole_area'] in area_report, 'repaired area differs')
        accel_line = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave\n'
        need(re.search(re.escape(accel_line) + r'\s+' + re.escape(c['accel_area']) + r'\s+', area_report),
             'repaired accelerator hierarchy area differs')
        results[tag] = dict(original_netlist_sha256=c['original'], repaired_netlist_sha256=c['repaired'],
            original_netlist_fm=dict(passing=c['passing'][-1], bbpin=c['passing'][0], unread=511,
                unmatched_reference=c['unmatch'], frozen_record_count=c['frozen']),
            coverage=table, untested_reasons=reasons, electrical_violation_pin_blocks=dict(electrical),
            dc_hfextclk_critical_slack_ns=c['dc_slack'], pt_ideal_envelope_extrema_ns=dict(max=0, min=-0.121483),
            repaired_full_soc_cell_area_um2=c['whole_area'],
            repaired_accelerator_hierarchical_cell_area_um2=c['accel_area'],
            repaired_netlist_equivalence='NOT_PROVEN_BY_ORIGINAL_NETLIST_FM',
            library_input_provenance='DB hashes present in PPA/repair receipts, but absent from FM before/after freeze; no local DB bytes')
    return dict(status='CONDITIONAL_ORIGINAL_NETLIST_FM_VERIFIED_REPAIRED_TIMING_NOT_QUALIFIED', candidates=results,
                limitations=['SRAM internals are black boxes; auto setup undriven assumptions and unread/unmatched points remain.',
                             'FM source/netlist/SVF stability is a server receipt assertion; large source/netlist/SVF bytes are not bundled locally.',
                             'Repaired nets differ from original nets verified by FM16/17; no transfer of that equivalence result.',
                             'Pre-CTS ideal clock and finite forwarded clock scope only; negative DC GPIO timing, reset violations, electrical violations and untested checks remain.',
                             'No full-SoC task energy qualification or score is asserted.'])


def audit(root=HERE):
    raw, manifest = load(root)
    result = analyze(raw)
    result.update(raw_files=len(raw), raw_bytes=sum(len(x) for x in raw.values()),
                  selected_export_files=len(manifest['selected_files']), context_files=len(manifest['context_files']))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=HERE)
    args = parser.parse_args()
    print(json.dumps(audit(args.root), indent=2, sort_keys=True))
