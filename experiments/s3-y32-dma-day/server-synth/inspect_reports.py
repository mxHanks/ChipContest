#!/usr/bin/env python3
"""Read-only audit of returned candidate DC artifacts; never invokes EDA.

Use --root /returned/candidate --out /new/review.json. Missing or partial
artifacts remain missing; this tool never turns DC screening into STA signoff.
"""
import argparse
from collections import Counter
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re

EXPECTED = dict(cpu=1,peripheral_dma=1,arbiter=1,original_peripheral_fabric=1,
    old_accelerator=0,rowpair_core=1,engine0=1,engine1=1,
    itcm=32,dtcm=32,shared=256,weights=16,bias=1,all_ramsp=337)
MAIN = 'u_soc/u_e203_subsys_top/u_e203_subsys_main'
DMA = MAIN+'/u_e203_subsys_perips/u_xu_matrix_dma/'
ARB = MAIN+'/u_xu_dma_shared_arb/'
NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
ROOT_OUTPUTS = ['precheck.rpt','postcheck.rpt','dc-units.rpt','area.rpt',
    'references.rpt','qor.rpt','clocks.rpt','dc-setup.rpt','dc-hold.rpt',
    'dc-violations.rpt','mapped.v','mapped.ddc','mapped.sdc','default.svf',
    'leaf-inventory.tsv','leaf-area-summary.txt']
CLOCK_REPORTS = ['check_timing.rpt','clocks.rpt','setup.rpt','hold.rpt',
    'constraints.rpt','exceptions.rpt','case_analysis.rpt','analysis_coverage.rpt',
    'recovery.rpt','removal.rpt','gating_setup.rpt','gating_hold.rpt',
    'pulse_width.rpt','async_pin_max.rpt','async_pin_min.rpt']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def scalar_fields(text):
    # The legacy clock reporter prints literal \\n / \\t in some versions.
    text = text.replace('\\n','\n').replace('\\t','\t')
    return dict(re.findall(r'^([A-Z_]+)=(.*)$',text,re.M))


def area_fields(text):
    labels = ['Number of cells','Number of combinational cells','Number of sequential cells',
              'Number of macros/black boxes','Combinational area','Buf/Inv area',
              'Noncombinational area','Macro/Black Box area','Total cell area']
    result = {}
    for label in labels:
        values = re.findall(r'^\s*'+re.escape(label)+r':\s*('+NUMBER+r')\s*$',text,re.M)
        if values: result[label] = float(values[-1])
    return result


def timing_fields(text):
    slacks = [float(v) for v in re.findall(r'\bslack\s*\([^\n)]*\)\s*('+NUMBER+r')',text,re.I)]
    return dict(reported_path_count=len(re.findall(r'^\s*Startpoint:',text,re.M)),
        slack_count=len(slacks),worst_reported_slack=min(slacks) if slacks else None,
        violated_reported_paths=sum(x<0 for x in slacks),
        no_paths=bool(re.search(r'no\s+(?:constrained\s+)?paths',text,re.I)),
        scope='DC report only; finite reported paths do not prove complete coverage or STA closure')


def inspect_final_seal(root, seal_path, manifest, required_artifacts, execution):
    result = dict(path=str(seal_path),present=seal_path.is_file(),valid=False,
        missing=[],drift=[],unsealed_required=[],identity_matches=False)
    if not result['present']:
        result['status']='NOT_RETURNED'
        return result
    result['sha256']=sha(seal_path)
    seal=json.loads(seal_path.read_text())
    files=seal.get('files',{})
    unsafe=[]
    for name,record in files.items():
        rel=Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            unsafe.append(name)
            continue
        path=root/rel
        if not path.is_file(): result['missing'].append(name)
        elif path.stat().st_size!=record.get('bytes') or sha(path)!=record.get('sha256'):
            result['drift'].append(name)
    required=set(manifest)|set(required_artifacts)|{'package-files.json','source-identity.json'}
    for name in CLOCK_REPORTS:
        for suffix in ['', '.unavailable.txt']:
            rel='dc-clock-reports/'+name+suffix
            if (root/rel).is_file(): required.add(rel)
    result.update(file_count=len(files),unsafe_paths=unsafe,
        unsealed_required=sorted(required-set(files)),
        identity_matches=bool(seal.get('schema')=='xu-server-final-artifact-seal-v1' and
            (root/'execution.json').is_file() and (root/'package-files.json').is_file() and
            seal.get('execution_sha256')==sha(root/'execution.json') and
            seal.get('input_manifest_sha256')==sha(root/'package-files.json') and
            seal.get('execution_status')==execution.get('status')))
    result['valid']=bool(files) and result['identity_matches'] and not any(
        result[n] for n in ['missing','drift','unsafe_paths','unsealed_required'])
    result['status']='VERIFIED_FINAL_BYTES' if result['valid'] else 'PARTIAL_OR_INVALID'
    return result


def inspect(root, seal_path=None):
    root = Path(root).resolve()
    names = ['execution.json','source-identity.json','package-files.json','synth.tcl',
      'constraints.sdc','dc.log','SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt','SYNTHESIS_FAILED.txt',
      'precheck.rpt','postcheck.rpt','dc-units.rpt','area.rpt','references.rpt','qor.rpt',
      'clocks.rpt','dc-setup.rpt','dc-hold.rpt','dc-violations.rpt','mapped.v','mapped.ddc',
      'mapped.sdc','default.svf','leaf-inventory.tsv','leaf-area-summary.txt',
      'dc-clock-reports/review_status.txt','dc-clock-reports/check_timing.rpt',
      'dc-clock-reports/clock_endpoints.tsv','dc-clock-reports/analysis_coverage.rpt',
      'dc-clock-reports/exceptions.rpt','dc-clock-reports/case_analysis.rpt']
    names = list(dict.fromkeys(names + ['dc-clock-reports/'+n+suffix
        for n in CLOCK_REPORTS for suffix in ['', '.unavailable.txt']]))
    artifacts = {n:dict(bytes=(root/n).stat().st_size,sha256=sha(root/n))
                 for n in names if (root/n).is_file()}
    def read(name):
        return (root/name).read_text(errors='replace') if (root/name).is_file() else ''
    def getjson(name):
        text = read(name)
        return json.loads(text) if text else {}
    execution = getjson('execution.json')
    identity = getjson('source-identity.json')
    manifest = getjson('package-files.json')
    manifest_sha256 = sha(root/'package-files.json') if manifest else None
    manifest_identity_matches = bool(manifest_sha256 and
        execution.get('input_manifest_sha256') == manifest_sha256)
    source_missing = [n for n in manifest if not (root/n).is_file()]
    source_drift = [n for n,h in manifest.items() if (root/n).is_file() and sha(root/n)!=h]
    recorded_outputs = execution.get('outputs',{})
    output_drift = [n for n,v in recorded_outputs.items() if (root/n).is_file() and sha(root/n)!=v.get('sha256')]
    recorded_outputs_missing = [n for n in recorded_outputs if not (root/n).is_file()]
    required_artifacts = ROOT_OUTPUTS + ['dc.log','execution.json',
        'SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt','dc-clock-reports/review_status.txt',
        'dc-clock-reports/clock_endpoints.tsv']
    required_artifacts_missing = [n for n in required_artifacts
        if not (root/n).is_file() or not (root/n).stat().st_size]
    clock_reports_unreturned = [n for n in CLOCK_REPORTS
        if not (root/'dc-clock-reports'/n).is_file() and
           not (root/'dc-clock-reports'/(n+'.unavailable.txt')).is_file()]
    final_seal=inspect_final_seal(root,Path(seal_path).resolve() if seal_path else
        root.parent/'final-files.json',manifest,required_artifacts,execution)
    # run_once records launcher.log, then appends its final status after writing
    # execution.json. Preserve that original receipt and prove this exact append;
    # only a separately verified final seal can reconcile it for completeness.
    launcher_finalization=dict(status='NOT_OBSERVED',reconciled_by_final_seal=False)
    launcher_record=recorded_outputs.get('launcher.log',{})
    launcher_path=root/'launcher.log'
    if launcher_path.is_file() and launcher_record and 'launcher.log' in output_drift:
        content=launcher_path.read_bytes()
        suffix=(execution.get('status','')+'\n').encode()
        prefix=content[:-len(suffix)] if suffix and content.endswith(suffix) else None
        exact=prefix is not None and len(prefix)==launcher_record.get('bytes') and \
            hashlib.sha256(prefix).hexdigest()==launcher_record.get('sha256')
        launcher_finalization=dict(status='EXACT_FINAL_STATUS_APPEND' if exact else 'UNEXPLAINED_DRIFT',
            original_receipt_sha256=launcher_record.get('sha256'),final_sha256=sha(launcher_path),
            reconciled_by_final_seal=bool(exact and final_seal['valid']),
            explanation='Runner snapshots launcher.log before printing its final status; original receipt is retained unchanged')
    outputs_match_final=not output_drift or (output_drift==['launcher.log'] and
        launcher_finalization['reconciled_by_final_seal'])
    log = read('dc.log')
    counts = {}
    for label,actual,expected in re.findall(r'DMA_SYNTH_COUNT (\w+) actual=(\d+) expected=(\d+)',log):
        counts.setdefault(label,[]).append(dict(actual=int(actual),expected=int(expected)))
    hierarchy = {label:dict(expected=value,observations=counts.get(label,[]),
       before_and_after_seen=len(counts.get(label,[]))>=2,
       exact_all_seen=bool(counts.get(label)) and all(x['actual']==value and x['expected']==value for x in counts[label]))
       for label,value in EXPECTED.items()}
    hierarchy_complete = all(x['before_and_after_seen'] and x['exact_all_seen'] for x in hierarchy.values())
    warning_text = '\n'.join(read(n) for n in ['dc.log','precheck.rpt','postcheck.rpt','area.rpt','dc-setup.rpt','dc-hold.rpt','dc-violations.rpt','dc-clock-reports/check_timing.rpt'])
    warnings = [s.strip() for s in warning_text.splitlines() if re.match(r'\s*Warning:',s)]
    errors = [s.strip() for s in warning_text.splitlines() if re.match(r'\s*(?:Error:|DMA_SERVER_SYNTH_FAILED:)',s)]
    codes = Counter(re.findall(r'\(([A-Z]+-\d+)\)', '\n'.join(warnings)))
    timing_information = sorted(set(s.strip() for s in warning_text.splitlines() if 'TIM-099' in s or re.search(r'clock pins driven by multiple clocks',s,re.I)))
    risk_lines = [s for s in warnings if re.search(r'unconstrain|no clock|clock.*(?:gating|multiple)|expansion limit|resolve reference|black.box|unmapped|timing loop|combinational loop|high.fanout',s,re.I)]
    # These are review findings, never automatically waived as historical.
    timing_coverage_risks = [s for s in risk_lines if re.search(r'unconstrain|no clock|expansion limit|clock.*(?:gating|multiple)',s,re.I)]
    endpoint_fields = scalar_fields(read('dc-clock-reports/review_status.txt'))
    timing = dict(setup=timing_fields(read('dc-setup.rpt')),hold=timing_fields(read('dc-hold.rpt')),
        clock_review_fields=endpoint_fields,multiple_clock_information=timing_information,coverage_risk_warning_lines=sorted(set(timing_coverage_risks)),
        check_timing_present=bool(read('dc-clock-reports/check_timing.rpt')),
        analysis_coverage_present=bool(read('dc-clock-reports/analysis_coverage.rpt')),
        standalone_STA='NOT_RUN_BY_THIS_FLOW',formal_timing_qualification='NOT_VERIFIED')
    if any(v['violated_reported_paths'] for v in [timing['setup'],timing['hold']]):
        timing['dc_screening']='VIOLATIONS_REPORTED'
    elif not timing['setup']['slack_count'] or not timing['hold']['slack_count']:
        timing['dc_screening']='MISSING_FINITE_SETUP_OR_HOLD_PATHS'
    elif timing_coverage_risks or endpoint_fields.get('NO_CLOCK_ENDPOINTS') not in ['0']:
        timing['dc_screening']='NONNEGATIVE_REPORTED_PATHS_WITH_COVERAGE_GAPS'
    else: timing['dc_screening']='NONNEGATIVE_REPORTED_PATHS_ONLY_REVIEW_REQUIRED'
    area = area_fields(read('area.rpt'))
    summary = scalar_fields(read('leaf-area-summary.txt'))
    leaf_counts = Counter();leaf_sums = Counter();components = {}
    leaf_rows = []
    if read('leaf-inventory.tsv'):
        rows = csv.DictReader(io.StringIO(read('leaf-inventory.tsv')),delimiter='\t')
        for row in rows:
            leaf_rows.append(row)
            category = row['classification'];value = Decimal(row['area_library_units'])
            leaf_counts[category]+=1;leaf_sums[category]+=value
            name=row['instance'];component=('dma' if name.startswith(DMA) else 'arbiter' if name.startswith(ARB) else 'shared' if name.startswith('u_shared/') else 'cpu' if name.startswith(MAIN+'/u_e203_cpu_top/') else 'other_soc')
            item=components.setdefault(component,dict(leaf_count=0,standard_cell_count=0,sram_count=0,standard_cell_area=Decimal(0),sram_area=Decimal(0)))
            item['leaf_count']+=1
            if category=='SRAM':item['sram_count']+=1;item['sram_area']+=value
            elif category=='standard_cell':item['standard_cell_count']+=1;item['standard_cell_area']+=value
    for item in components.values():
        item.update(standard_cell_area=float(item['standard_cell_area']),sram_area=float(item['sram_area']))
    macro_rows = [x for x in leaf_rows if x['classification']=='SRAM']
    observed_total = sum(leaf_sums.values(),Decimal(0)) if leaf_rows else None
    report_total = area.get('Total cell area')
    area.update(scope='FULL_DIGITAL_SOC_INCLUDING_337_SRAM_MACROS',
        unit='library_area_units_pending_library_unit_review',leaf_summary=summary,
        leaf_counts=dict(leaf_counts),leaf_sums={k:float(v) for k,v in leaf_sums.items()},
        leaf_sum_total=float(observed_total) if observed_total is not None else None,
        leaf_report_total_agree=bool(observed_total is not None and report_total is not None and abs(float(observed_total)-report_total)<=max(0.01,abs(report_total)*1e-7)),
        exact_macro_leaves=len(macro_rows)==337 and all(x['reference']=='RAMSP1024X16' for x in macro_rows),
        components=components,baseline_comparison='NOT_AVAILABLE',area_25pct_budget='UNVERIFIED',
        physical_die_area='NOT_MEASURED')
    marker = 'DMA_SERVER_SYNTH_COMPLETE_UNQUALIFIED' in read('SYNTHESIS_COMPLETE_NOT_QUALIFIED.txt')
    mapped = bool(artifacts.get('mapped.v',{}).get('bytes')) and bool(artifacts.get('mapped.ddc',{}).get('bytes'))
    completion_checks = dict(completion_marker=marker,
        execution_finished=execution.get('status')=='SYNTHESIS_COMPLETE_NOT_QUALIFIED' and
            execution.get('returncode')==0 and execution.get('completion_marker') is True,
        execution_source_drift_empty=execution.get('source_drift')==[],
        manifest_identity_matches=manifest_identity_matches,
        inputs_complete=bool(manifest) and not source_drift and not source_missing,
        recorded_outputs_complete=bool(recorded_outputs) and not recorded_outputs_missing and outputs_match_final,
        final_seal_valid_if_present=not final_seal['present'] or final_seal['valid'],
        required_artifacts_returned=not required_artifacts_missing,
        clock_report_collection_returned=not clock_reports_unreturned,
        mapped_outputs_present=mapped,hierarchy_complete=hierarchy_complete,
        leaf_area_reconciles=area['leaf_report_total_agree'],
        exact_macro_leaves=area['exact_macro_leaves'])
    completion = all(completion_checks.values())
    return dict(schema='xu-dma-server-artifact-review-v1',status='SYNTHESIS_ARTIFACTS_COMPLETE_REVIEW_REQUIRED' if completion else 'PARTIAL_OR_FAILED_ARTIFACTS',
      root=str(root),artifacts=artifacts,missing_artifacts=[n for n in names if n not in artifacts and n!='SYNTHESIS_FAILED.txt'],
      recorded_output_drift=output_drift,recorded_outputs_missing=recorded_outputs_missing,
      final_seal=final_seal,launcher_receipt_finalization=launcher_finalization,
      completion_checks=completion_checks,required_artifacts_missing=required_artifacts_missing,
      clock_reports_unreturned=clock_reports_unreturned,
      source=dict(identity=identity.get('portability_overlay'),subsystem_overlay=identity.get('subsystem_declaration_overlay'),manifest_present=bool(manifest),missing=source_missing,drift=source_drift,
                  manifest_sha256=manifest_sha256,execution_manifest_sha256=execution.get('input_manifest_sha256'),manifest_identity_matches=manifest_identity_matches,
                  main_commit=identity.get('main_commit'),child_commit=identity.get('child_commit')),
      execution=dict(status=execution.get('status'),returncode=execution.get('returncode'),completion_marker=marker,mapped_outputs_present=mapped),
      hierarchy=hierarchy,area=area,timing=timing,
      diagnostics=dict(error_lines=errors,warning_count_including_repeated_reports=len(warnings),warning_codes=dict(codes),risk_lines=sorted(set(risk_lines))),
      qualification=dict(mapped_whole_soc_functional_equivalence='NOT_RUN',SRAM_PVT_EMA_eligibility='NOT_REVIEWED',power='NOT_RUN',official_contest_eligibility='NOT_VERIFIED'),
      limitations=['DC artifact review is not standalone PrimeTime STA or formal qualification',
       'Area includes original CPU/peripheral fabric, full shared storage, DMA/core and macros; DMA component area is separately classified',
       'No area delta, 25pct-budget judgment or old area substitution without a valid same-condition matching baseline',
       'Parser reports finite printed path slacks only; check_timing/coverage/clock-gating/reset/cross-domain findings require human review'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--seal',type=Path,help='External final-files.json; defaults to parent of candidate');a=p.parse_args()
    if a.out.exists():raise ValueError('refuse overwrite: '+str(a.out))
    report=inspect(a.root,a.seal);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(status=report['status'],out=str(a.out),area=report['area'].get('Total cell area'),dc_screening=report['timing']['dc_screening'],qualification='NOT_VERIFIED')))
if __name__=='__main__':main()
