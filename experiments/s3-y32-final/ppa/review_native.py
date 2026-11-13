#!/usr/bin/env python3
"""Verify returned native identities and summarize exact final374 DC/PT evidence.

Read-only report replay. Collection completion and numerical summaries are never
STA, area-in-mm2, RTL equivalence, power or contest qualification by themselves.
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from controls import check_inputs, check_cpu_full12, DEFINES, PROFILE

TOP='xu_soc_sysbus32_ppa_top'
LIBS={'standard_cell':'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723',
      'sram':'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'}
CHECKS={'setup','hold','recovery','removal','min_period','min_pulse_width',
        'clock_gating_setup','clock_gating_hold','out_setup','out_hold'}

def need(v,m):
    if not v: raise ValueError(m)

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def identity(p):return {'bytes':p.stat().st_size,'sha256':sha(p)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native',type=Path,required=True,help='returned candidate directory')
    p.add_argument('--inputs',type=Path,required=True,help='exact local sealed source package')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--allow-omitted-alib-cache',action='store_true',
        help='allow only native DC alib-52/*.db.alib cache omission; preserve its original receipt identity, never omit reports/netlists')
    a=p.parse_args();need(not a.out.exists(),'refuse report overwrite')
    b=a.native;source=a.inputs
    check_inputs(source);cpu_binding=check_cpu_full12(source)
    dc=json.loads((b/'execution.json').read_text());pt=json.loads((b/'pt/execution.json').read_text())
    m=json.loads((source/'package-files.json').read_text())
    need(sha(b/'package-files.json')==sha(source/'package-files.json')==dc['manifest_sha256']==pt['manifest_sha256'],'package/DC/PT binding')
    for n,h in m.items():
        q=Path(n);need(not q.is_absolute() and '..'not in q.parts,'unsafe source path')
        need((source/q).is_file() and not (source/q).is_symlink() and sha(source/q)==h,'source identity:'+n)
    verified={};omitted={}
    for tag,root,r,status in [('dc',b,dc,'SYNTHESIS_COMPLETE_NOT_QUALIFIED'),('pt',b/'pt',pt,'PT_REPORT_COLLECTION_COMPLETE_NOT_QUALIFIED')]:
        need(r['status']==status and r['returncode']==0 and r['completion_marker'] is True and r['source_drift']==[] and r['native_tool_errors']==[] and not r['missing_required_outputs'],'native collection incomplete:'+tag)
        need(r['hardware_profile']==PROFILE and r['defines']==DEFINES and r['cpu_full12_binding']==cpu_binding,'final production/CPU binding:'+tag)
        need(r['max_cores']==2 and r['top']==TOP and {x['role']:x['sha256']for x in r['libraries']}==LIBS,'tool/top/library/resource identity:'+tag)
        for n,item in r['outputs'].items():
            q=Path(n);need(not q.is_absolute()and '..'not in q.parts,'unsafe output name')
            f=root/q
            if f.is_file():
                need(not f.is_symlink() and identity(f)==item,'native output identity:'+tag+':'+n)
                verified[tag+':'+n]=item
            else:
                alib_cache=(tag=='dc' and len(q.parts)==2 and q.parts[0]=='alib-52'
                    and re.fullmatch(r'[A-Za-z0-9_.+-]+\.db\.alib',q.name) is not None)
                need(tag=='dc' and (q.parts[0] in {'WORK','source','local-only'}
                    or (a.allow_omitted_alib_cache and alib_cache)),
                    'missing returned evidence:'+tag+':'+n)
                omitted[tag+':'+n]=item
    need(pt['source_dc']['execution_sha256']==sha(b/'execution.json'),'PT source receipt')
    for n,item in pt['source_dc']['outputs'].items():need(identity(b/n)==item,'PT mapped binding:'+n)
    need('final.svf' in dc['outputs'] and identity(b/'final.svf')==dc['outputs']['final.svf'] and (b/'final.svf').stat().st_size>0,'final map own real SVF')
    need('final.svf' in pt['source_dc']['outputs'],'PT own-map SVF binding')
    reportlist = (b/'pt/required-reports.list').read_text().splitlines()
    need(reportlist and len(reportlist)==len(set(reportlist)), 'unique native required-report catalogue')
    for name in reportlist:
        need(name.startswith('reports/') and name in pt['outputs'] and (b/'pt'/name).stat().st_size>0,
             'required native report absent or unbound:'+name)
    coverage=(b/'pt/reports/coverage.rpt').read_text()
    need(re.search(r'^Design\s*:\s*'+TOP+r'\s*$',coverage,re.M),'coverage wholeSoC top')
    pat=r'^\s*(\w+|All Checks)\s+(\d+)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s+(\d+)\s+\([^)]*\)\s*$'
    rows={name:dict(zip(['total','met','violated','untested'],map(int,values))) for name,*values in re.findall(pat,coverage,re.M)}
    need(set(rows)==CHECKS|{'All Checks'},'complete native coverage types')
    for name,row in rows.items():need(row['total']==row['met']+row['violated']+row['untested'],'coverage row reconciliation:'+name)
    for k in ['total','met','violated','untested']:need(sum(rows[n][k]for n in CHECKS)==rows['All Checks'][k],'coverage all check reconciliation:'+k)
    reasons={n:len(re.findall(r'\buntested\s+'+re.escape(n)+r'\b',coverage))for n in sorted(set(re.findall(r'\buntested\s+(\S+)',coverage)))}
    def paths(name):
        text=(b/'pt/reports'/name).read_text()
        vals=[Decimal(x) for x in re.findall(r'^\s*slack\s+\((?:MET|VIOLATED)\)\s+(\S+)\s*$',text,re.M)]
        need(vals and all(x.is_finite()for x in vals),'no finite diagnostic paths:'+name)
        return dict(reported_paths=len(vals),worst_reported_slack_ns=str(min(vals)),scope='top-N diagnostic only; full coverage and all-violators retained')
    constraints=(b/'pt/reports/all_violators.rpt').read_text();drc={}
    for block in re.split(r'(?m)^    Pin:',constraints)[1:]:
        kind=re.search(r'\b(max_capacitance|min_capacitance|max_transition|min_transition)\b',block)
        need(kind is not None and '(VIOLATED' in block,'unclassified electrical violation block')
        key=kind[1];drc[key]=drc.get(key,0)+1
    drc['timing_path_rows']=len(re.findall(r'(?m)^\s*slack \(VIOLATED',constraints))
    need(sum(drc.values())==constraints.count('(VIOLATED'),'all-violators row classification incomplete')
    area={};counts={};macros={};names=set();charged=Decimal(0);std=Decimal(0);internal=Decimal(0)
    with (b/'leaf-inventory.tsv').open() as f:
        for row in csv.DictReader(f,delimiter='\t'):
            name=row['instance'];need(name not in names,'duplicate leaf');names.add(name)
            v=Decimal(row['area_library_units']);need(v.is_finite()and v>=0,'invalid leaf area')
            cls=row['classification'];counts[cls]=counts.get(cls,0)+1;area[cls]=area.get(cls,Decimal(0))+v
            scope=row['charged_scope']
            if scope!='none':charged+=v
            if cls=='standard_cell':std+=v
            if row['reference']=='RAMSP1024X16':
                if '/u_e203_itcm_ram/' in name:g='itcm'
                elif '/u_e203_dtcm_ram/' in name:g='dtcm'
                elif name.startswith('u_shared/storage/'):g='shared'
                elif '/u_core/weights/' in name:g='weights'
                elif '/u_core/biasMemory/' in name:g='bias'
                elif '/u_core/xSets' in name:g='X'
                elif '/u_core/resultSlices' in name:g='result'
                else:raise ValueError('unclassified SRAM:'+name)
                macros[g]=macros.get(g,0)+1
                if g in {'weights','bias','X','result'}:internal+=v
    need(macros==dict(itcm=32,dtcm=32,shared=256,weights=16,bias=1,X=16,result=21),'exact374 macro scope')
    report=(b/'area.rpt').read_text();total=re.search(r'^Total cell area:\s*(\S+)',report,re.M)
    need(total and abs(sum(area.values())-Decimal(total[1]))<Decimal('.01'),'area native report reconciliation')
    clk=list(csv.DictReader((b/'pt/reports/clock_endpoints.tsv').open(),delimiter='\t'))
    srams=[x for x in clk if x['kind']=='SRAM'];need(len(srams)==374 and len({x['pin']for x in srams})==374,'all actual374 SRAM clock pins')
    unknown=[x for x in clk if int(x['clock_count'])==0]
    uncertain_negative_zero = bool(re.search(r'(?m)^\s*slack \(VIOLATED\)\s+-0(?:\.0+)?\s*$',constraints))
    sram_no_clock = [x for x in srams if int(x['clock_count'])==0]
    has_reported_violations = any(drc.values())
    record=dict(schema='final-dma4-storage374-native-report-review-v1',status='NATIVE_EVIDENCE_VERIFIED_NOT_QUALIFIED',
        package_sha256=sha(source/'package-files.json'),dc_execution=identity(b/'execution.json'),pt_execution=identity(b/'pt/execution.json'),
        verified_native_outputs=verified,omitted_non_evidence_outputs=omitted,verified_local_sealed_inputs=len(m),
        omitted_cache_policy=dict(alib_explicitly_allowed=a.allow_omitted_alib_cache,
            allowed_alib_pattern='DC-only alib-52/[A-Za-z0-9_.+-]+.db.alib; original native SHA256 and bytes retained above',
            reports_netlists_receipts_may_be_omitted=False),
        setup=paths('setup.rpt'),hold=paths('hold.rpt'),coverage=rows,untested_reasons=reasons,
        all_violator_rows_by_section=drc,leaf_counts=counts,macro_groups=macros,
        area_library_units={k:str(v)for k,v in area.items()},charged_named_area_library_units=str(charged),
        conservative_all_soc_standard_plus54internal_library_units=str(std+internal),internal54_area_library_units=str(internal),
        clock_endpoints=dict(rows=len(clk),sram_CLK_count=374,unassociated_raw_rows=unknown),
        timing_verdict='NOT_CLOSED' if rows['All Checks']['violated'] or has_reported_violations else 'REQUIRES_COVERAGE_CLOCK_CDC_RESET_AND_ELECTRICAL_REVIEW',
        timing_gate_passed=False, own_svf=identity(b/'final.svf'), cpu_full12_binding=cpu_binding,
        unresolved_gate_reasons=[reason for condition, reason in [(bool(rows['All Checks']['violated']), 'native coverage has violated checks'),
            (has_reported_violations, 'native all-violators report is nonempty'), (bool(rows['All Checks']['untested']), 'untested coverage requires clock/CDC/reset explanation'),
            (bool(sram_no_clock), 'actual SRAM CLK lacks clock'), (uncertain_negative_zero, 'negative zero display is ambiguous')] if condition] +
            ['coverage and CDC/reset review has no final signed disposition'],
        official_mm2_verdict='NOT_VERIFIED_LIBRARY_DIMENSION_AND_OFFICIAL_MACRO_PRICE_REQUIRED',
        missing_qualification=['RTL-to-mapped functional consistency','valid full150MHz closure','area units and official macro price','fullSoC same-config power/energy','final organizer sample evaluation'])
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:record[k]for k in ['status','timing_verdict','charged_named_area_library_units','conservative_all_soc_standard_plus54internal_library_units','setup','hold','coverage']},sort_keys=True))

if __name__=='__main__':main()
