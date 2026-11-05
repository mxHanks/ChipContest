#!/usr/bin/env python3
"""Recompute the two-candidate comparison from returned, frozen evidence.

This is a derived comparison, not a new EDA execution or qualification grant.
Every candidate's area and energy remain bound to its own mapped identity.
"""
import argparse
import csv
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

HERE=Path(__file__).resolve().parent
ACCEL='u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'
C='9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892'
E='0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0'
F='3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794'
SDC='404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(name):return json.loads((HERE/'inputs'/name).read_text())
def rows(name):
    with (HERE/'inputs'/name).open() as stream:return list(csv.DictReader(stream))
def area(name,receipt):
    raw=(HERE/'inputs'/name).read_bytes()
    assert len(raw)==receipt['bytes'] and sha(raw)==receipt['sha256']
    values=re.findall(r'^'+re.escape(ACCEL)+r'\n\s+([0-9.]+)\s',raw.decode(),re.M)
    assert len(values)==1
    return D(values[0])/D(1000000)


def compute():
    manifest=json.loads((HERE/'source-manifest.json').read_text())
    assert len(manifest)==12 and len({r['path'] for r in manifest})==12
    assert {str(p.relative_to(HERE)) for p in (HERE/'inputs').iterdir()}=={r['path'] for r in manifest}
    for record in manifest:
        path=PurePosixPath(record['path'])
        assert not path.is_absolute() and '..' not in path.parts
        raw=(HERE/record['path']).read_bytes()
        assert len(raw)==record['bytes'] and sha(raw)==record['sha256']
    cx,ex,px,fx=load('s2c-area-execution.json'),load('s2e89-execution.json'),load('s2e130-execution.json'),load('s2e155-state.json')
    prep=load('s2e130-prepared.json');review=load('s2c-power-review.json')
    assert cx['netlist_sha256']==review['same_original_mapped_netlist_sha256']==C
    assert ex['netlist_sha256']==prep['netlist']['sha256']==E
    assert cx['analysis_sdc_sha256']==ex['analysis_sdc_sha256']==prep['analysis_sdc']['sha256']==SDC
    assert px['status']=='EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and px['taskset_complete'] is True
    assert px['input_sha256_before']==px['input_sha256_after']==prep['input_sha256']
    assert px['prepared']==px['prepared_after'] and px['prepared']['sha256']==sha((HERE/'inputs/s2e130-prepared.json').read_bytes())
    ca=area('s2c-area.rpt',cx['reports']['area.rpt']);ea=area('s2e89-area.rpt',ex['reports']['area.rpt'])
    assert fx['status']=='EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED'
    final=next(r for k,r in fx['final_outputs'].items() if k.endswith('/mapped.v'))
    assert final['sha256']==F and F!=E
    farea=next(r for k,r in fx['reports'].items() if k.endswith('/area.rpt'))
    fa=area('s2e155-area.rpt',farea)
    assert fx['frozen_before']==fx['frozen_after'] and fx['frozen_input_errors']==[]
    c,e,cycles=rows('s2c-power.csv'),rows('s2e-power.csv'),rows('formal-cycles.csv')
    assert len(c)==len(e)==len(cycles)==len(px['tasks'])==12
    paired=[]
    for number,(a,b,w,native) in enumerate(zip(c,e,cycles,px['tasks'])):
        assert int(a['task_id'])==int(b['task_id'])==int(w['layer'])==native['task_id']==number
        assert a['qualification']==b['qualification']=='NOT_QUALIFIED'
        assert int(a['formal_elapsed_cycles'])==int(w['s2c_elapsed_cycles'])==990656
        assert int(b['formal_elapsed_cycles'])==int(w['s2e_elapsed_cycles'])==868343
        assert a['duration_fs']==w['s2c_duration_fs']=='6604373333334'
        assert b['duration_fs']==w['s2e_duration_fs']=='5788953333333'
        assert D(a['duration_seconds'])==D(a['duration_fs'])*D('1e-15') and D(b['duration_seconds'])==D(b['duration_fs'])*D('1e-15')
        assert D(a['diagnostic_energy_j'])==D(a['duration_seconds'])*D(a['total_power_w'])
        assert D(b['diagnostic_energy_j'])==D(b['duration_seconds'])*D(b['reported_total_power_w'])
        assert native['execution']['returncode']==int(b['native_returncode'])==0 and int(b['native_marker_count'])==1
        assert native['execution']['log']['sha256']==b['native_log_sha256']
        assert native['diagnostic']['report']['sha256']==b['power_report_sha256']
        assert native['diagnostic']['power_components']['total_power_w']==b['reported_total_power_w']
        assert int(a['unknown_q_bits'])==int(b['q_tx_positive_reported'])==5280
        assert int(a['all_window_unknown_q_bits'])==int(b['q_tx_full_window_reported'])==4256
        paired.append(dict(layer=number,s2c_elapsed_cycles=int(a['formal_elapsed_cycles']),s2e_elapsed_cycles=int(b['formal_elapsed_cycles']),
            saved_cycles=int(a['formal_elapsed_cycles'])-int(b['formal_elapsed_cycles']),
            s2c_reported_power_w=a['total_power_w'],s2e_reported_power_w=b['reported_total_power_w'],
            s2c_diagnostic_energy_j=a['diagnostic_energy_j'],s2e_diagnostic_energy_j=b['diagnostic_energy_j'],
            s2c_duration_fs=a['duration_fs'],s2e_duration_fs=b['duration_fs'],
            s2c_vcs_log_sha256=w['s2c_log_sha256'],s2e_vcs_log_sha256=w['s2e_log_sha256'],
            s2c_pt_log_sha256=a['pt_log_sha256'],s2e_pt_log_sha256=b['native_log_sha256'],
            s2c_power_report_sha256=a['power_report_sha256'],s2e_power_report_sha256=b['power_report_sha256'],qualification='NOT_QUALIFIED'))
    cc=sum(r['s2c_elapsed_cycles'] for r in paired);ec=sum(r['s2e_elapsed_cycles'] for r in paired)
    ce=sum(D(r['s2c_diagnostic_energy_j']) for r in paired);ee=sum(D(r['s2e_diagnostic_energy_j']) for r in paired)
    assert cc==review['sum_formal_elapsed_cycles']==11887872 and ec==10420116
    assert ce==D(review['sum_diagnostic_energy_j']) and ee==D(px['diagnostic_summary']['sum_diagnostic_energy_j'])
    summary=dict(schema='xu-s2c-s2e-comparison165-v1',qualification='NOT_QUALIFIED',retained_profiles=['s2e','s2c'],
        original_map_comparison=dict(
            s2c=dict(mapped_sha256=C,elapsed_cycles12=cc,diagnostic_energy12_j=str(ce),accelerator_area_mm2=str(ca)),
            s2e=dict(mapped_sha256=E,elapsed_cycles12=ec,diagnostic_energy12_j=str(ee),accelerator_area_mm2=str(ea)),
            cycle_reduction_percent=str((1-D(ec)/D(cc))*100),diagnostic_energy_reduction_percent=str((1-ee/ce)*100),
            accelerator_area_increase_percent=str((ea/ca-1)*100)),
        newer_s2e155=dict(mapped_sha256=F,accelerator_area_mm2=str(fa),area_limit_mm2='2.25',within_area_limit=fa<=D('2.25'),
            diagnostic_energy12_j=None,energy_status='SAME_FINAL155_MAP_NOT_YET_MEASURED',timing_qualification='NOT_QUALIFIED'),
        limitations=['Original-map energy is diagnostic only; unknown Q, SRAM conditional power and coverage remain unresolved.',
                     '155 final map area must not be paired with130 original89 energy.',
                     'This comparison rechecks frozen returned CSV/receipts/reports; original native evidence verification is documented upstream.',
                     'Full150MHz, mapped runtime, official numerical workload and final score eligibility remain unproven.'])
    return summary,paired


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    summary,paired=compute()
    if args.write:
        (HERE/'comparison.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
        with (HERE/'per-layer.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(paired[0]));writer.writeheader();writer.writerows(paired)
    else:
        assert json.loads((HERE/'comparison.json').read_text())==summary
        with (HERE/'per-layer.csv').open() as stream:actual=list(csv.DictReader(stream))
        assert actual==[{k:str(v) for k,v in row.items()} for row in paired]
    print(json.dumps(summary,indent=2,sort_keys=True))


if __name__=='__main__':main()
