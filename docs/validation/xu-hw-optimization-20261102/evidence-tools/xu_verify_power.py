#!/usr/bin/env python3
"""Independent activity, exact power-unit and window-energy evidence audit."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def one(pattern, text):
    found = re.findall(pattern, text, re.M)
    require(len(found) == 1, 'missing or ambiguous power metric: '+pattern)
    return float(found[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root = args.report
    evidence = root/'activity-evidence'
    manifest = json.loads((evidence/'supplemental-originals-manifest.json').read_text())
    for name, item in manifest['files'].items():
        payload = (evidence/name).read_bytes()
        require(sha(payload) == item['sha256'] and len(payload) == item['bytes'], 'original activity artifact differs: '+name)
    activity = json.loads((evidence/'activity-power-02/paired-power-summary.json').read_text())
    precise_raw = (evidence/'power-exact-state.json').read_bytes()
    precise = json.loads(precise_raw.decode())
    require(precise['status'] == 'PASS', 'exact activity power did not complete')
    paired = json.loads((root/'ppa/paired-exact-summary.json').read_text())
    historical = json.loads((root.parent/'xu-fw-optimization-20261102/server-json/acceptance/real12/result.json').read_text())
    final = json.loads((root/'server-json/acceptance/real12/result.json').read_text())
    results = {}
    for name, reference in [('baseline', historical), ('candidate', final)]:
        case = activity['cases'][name]
        run = json.loads((evidence/'activity-02'/name/'result.json').read_text())
        require(run['status'] == 'PASS' and run['tasks'] == 1 and run['mode'] == 'real' and run['simulator'] == 'vcs', 'activity run scope differs')
        require(run['layers'] == [reference['layers'][0]] == case['layers'], 'waves changed complete counters/cycles/results')
        require(run['firmware_image_sha256'] == reference['firmware_image_sha256'] == case['firmware_image_sha256'], 'waves changed firmware image')
        require(case['source_netlist_sha256'] == paired['cases'][name]['netlist_sha256'] and
                case['source_sdc_sha256'] == paired['cases'][name]['sdc_sha256'], 'power used another mapped netlist or constraints')
        scale = case['scale']
        require(scale['raw_clock_ns'] == 4 and scale['original_timescale'] == '10ps' and scale['timescale_preserved'], 'raw clock/time unit differs')
        require(scale['event_lines_preserved'] and scale['unchanged_lines_sha256'] == scale['derived_unchanged_lines_sha256'], 'frequency transform changed non-timestamp events')
        require(scale['max_rounding_error_ticks'] <= .5, 'timestamp rounding error exceeds bound')
        begin, end = scale['raw_window_ticks']
        ticks = [(5*value+1)//3 for value in [begin,end]]
        require(ticks == scale['derived_window_ticks'], '5/3 timestamp conversion differs')
        require(end-begin == (run['layers'][0]['cycles']-1)*400, 'inclusive cycle count differs from edge-to-edge waveform window')
        duration_ns = (ticks[1]-ticks[0])*.01
        require(abs(duration_ns-(scale['derived_window_ns'][1]-scale['derived_window_ns'][0])) < 1e-6, 'time window conversion differs')
        log = (evidence/'activity-02'/name/'simulation.log').read_bytes()
        require(sha(log) == run['log_sha256']['simulation.log'] == scale['simulation_log_sha256'], 'activity simulation log identity differs')
        for key in ['raw', 'derived']:
            source = manifest['waveforms'][scale[key]]
            require(source['sha256'] == scale[key+'_sha256'] and source['bytes'] == scale[key+'_bytes'], 'waveform byte identity differs')
        exact = precise['cases'][name]
        reports = exact['reports']
        for filename, item in dict(reports, **{'power.tcl':exact['tcl'], 'pt.log':exact['log']}).items():
            payload = (evidence/'power-exact-reports'/name/filename).read_bytes()
            require(sha(payload) == item['sha256'] and payload == item['text'].encode(), 'exact power original bytes differ')
        text = reports['power-exact.rpt']['text']
        require('Dynamic Power Units = 1 W' in text and 'Leakage Power Units = 1 W' in text, 'actual report power units are not explicit Watts')
        require('<no wire load model is set>' in text, 'interconnect assumption differs')
        total = one(r'^Total Power\s*=\s*(\S+)', text)
        internal = one(r'^\s*Cell Internal Power\s*=\s*(\S+)', text)
        switching = one(r'^\s*Net Switching Power\s*=\s*(\S+)', text)
        leakage = one(r'^\s*Cell Leakage Power\s*=\s*(\S+)', text)
        # Reported component/total values are independently rounded by PT.
        require(abs(total-internal-switching-leakage) < 1e-9, 'power components differ from total')
        old_tcl = (evidence/'activity-power-02'/name/'power.tcl').read_text()
        comparable = old_tcl.replace('man report_switching_activity > man-report-switching-activity.txt\n','').replace('report_power > power.rpt','report_power -verbose -significant_digits 8 > power-exact.rpt')
        require(exact['tcl']['text'] == comparable, 'exact unit rerun changed workload/RTL/SDC/time inputs')
        log = exact['log']['text']
        require('XU_ACTIVITY_POWER_PASS' in log.splitlines() and not re.search(r'^Error:',log,re.M), 'exact power tool reported an error')
        coverage = reports['activity-after-propagation.rpt']['text']
        require(coverage == case['reports']['activity-after-propagation.rpt']['text'].replace('Date   : '+re.search(r'^Date   : (.*)$',case['reports']['activity-after-propagation.rpt']['text'],re.M)[1],
                  'Date   : '+re.search(r'^Date   : (.*)$',coverage,re.M)[1]), 'exact report rerun changed activity coverage')
        rows = re.findall(r'^\s*(Nets|Primary Input|Sequential|Memory)\s+(\d+\(.*)$',coverage.split('Static Probability Overview')[0],re.M)
        activity_rows = {kind:body for kind,body in rows}
        require(len(rows) == len(activity_rows) == 4, 'missing or ambiguous activity coverage rows')
        clock = one(r'^clock_network\s+\S+\s+\S+\s+\S+\s+(\S+)',text)
        results[name] = dict(power_w=total,power_mw=total*1000,internal_power_w=internal,switching_power_w=switching,leakage_power_w=leakage,
                             clock_pin_internal_power_w=clock,clock_group_fraction=clock/total,
                             window_duration_ns=duration_ns,window_cycles_inclusive=run['layers'][0]['cycles'],
                             estimated_window_energy_j=total*duration_ns*1e-9,estimated_window_energy_uj=total*duration_ns*.001,
                             activity_coverage_rows=activity_rows,raw_vcd_sha256=scale['raw_sha256'],derived_vcd_sha256=scale['derived_sha256'],
                             power_report_sha256=reports['power-exact.rpt']['sha256'])
    b,a=results['baseline'],results['candidate']
    output=dict(status='PASS',scope='independent original-artifact, actual-unit, source/activity/time identity and numerical audit; no EDA rerun',
                precise_source_sha256=sha(precise_raw),original_artifacts_verified=len(manifest['files']),cases=results,
                comparison=dict(average_power_ratio=a['power_w']/b['power_w'],energy_ratio=a['estimated_window_energy_j']/b['estimated_window_energy_j'],
                                average_power_reduction=False,estimated_window_energy_reduction=False),
                limits=['Averaged RTL VCD activity mapped/propagated into pre-layout gate netlists; not measured silicon or glitch-aware gate waveform',
                        'Large raw/derived VCD bytes remain on server; local audit crosschecks hashes and source transformation metadata, not all waveform bytes',
                        'Only one real layer0 workload per side; not whole SoC or dataset power',
                        'No wire-load model or extracted RC, ideal clock, unqualified SRAM adapter and remaining timing violations',
                        'Energy uses explicit PT edge-to-edge activity span, one cycle shorter than inclusive performance count'])
    with args.out.open('x') as stream:stream.write(json.dumps(output,indent=2,sort_keys=True)+'\n')
    print('PASS: actual power {:.6f} -> {:.6f} mW; energy ratio {:.6f}'.format(b['power_mw'],a['power_mw'],output['comparison']['energy_ratio']))


if __name__ == '__main__':
    main()
