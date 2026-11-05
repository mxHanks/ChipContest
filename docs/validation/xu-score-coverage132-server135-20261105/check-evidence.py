#!/usr/bin/env python3
"""Independent byte/report audit of actual132; no EDA, remote access or waiver."""
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE = Path(__file__).resolve().parent
ARCHIVE = 'xu-server-coverage-power-progress-20261105-135.tar.xz'
ARCHIVE_SHA = '7972967f569bdc76794e79fe8a112d43fb9ce0bd8d3c85aed8c589f9d5c1c19f'
PREFIX = 'full-soc-coverage-rdc-20261105-132/'
STATUS = 'EXECUTED_SAME116_READ_ONLY_COVERAGE_RDC_NOT_QUALIFIED'
STATE_SHA = '2f6b6147e384851f194c1f46cb21dfb8c574d1ea3abab136f80d32bd2a21a5b5'
WORKER_SHA = 'd40a163adf3fe13cbce0a9ecee9258929a07eb53068781a7ce9054694c152f91'
BASE = 'u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
CELLS = [BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg', BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg']
CELLS += [BASE+'aonrst_catch/reset_n_catch_reg/reg_%d/q_reg'%i for i in range(3)]
OUTPUTS = ['Q', 'QN', 'Q', 'Q', 'Q']
ASYNC = ['SDN', 'SDN', 'RDN', 'RDN', 'RDN']
MODES = {'RET1N':'1', 'EMA[2]':'0', 'EMA[1]':'1', 'EMA[0]':'0', 'EMAW[1]':'0', 'EMAW[0]':'0'}
ACTIVE = 'RET1Neq1aEMA2eq0aEMA1eq1aEMA0eq0aEMAW1eq0aEMAW0eq0aCENeq0'
TYPES = r'setup|hold|recovery|removal|min_period|min_pulse_width|clock_gating_setup|clock_gating_hold|out_setup|out_hold'


def need(ok, message):
    if not ok: raise ValueError(message)


def ident(data):
    return {'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()}


def records(data):
    result=list(csv.DictReader(io.StringIO(data.decode()), delimiter='\t'))
    need(all(None not in row and all(value is not None for value in row.values()) for row in result), 'truncated TSV row')
    return result


def original135():
    raw=(HERE/ARCHIVE).read_bytes()
    need(ident(raw)=={'bytes':2730552,'sha256':ARCHIVE_SHA}, 'original135 archive differs')
    identities={}; kept={}; original=None
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:xz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            need(member.isfile() and not path.is_absolute() and '..' not in path.parts and
                 member.name not in identities and 'private-manuals' not in path.parts, 'unsafe/duplicate/private135 member')
            data=archive.extractfile(member).read(); identities[member.name]=ident(data)
            if member.name=='manifest.json': original=json.loads(data)
            elif member.name.startswith(PREFIX) or '/' not in member.name or member.name.startswith('full-soc-coverage-rdc-launch-20261105-132/'):
                kept[member.name]=data
    identities.pop('manifest.json')
    need(original is not None and len(original)==len(identities)==165 and
         sum(row['bytes'] for row in identities.values())==181183292, 'original135 inventory count/bytes differ')
    need({row['path'] for row in original}==set(identities), 'original135 inventory differs')
    for row in original:
        need(identities[row['path']]=={key:row[key] for key in ('bytes','sha256')}, 'original135 payload differs: '+row['path'])
    need(not any(row['path'].startswith(PREFIX) for row in json.loads(kept['omitted135-bodies.json'])), '132 body omitted')
    return kept


def sibling122():
    path=HERE.parent/'xu-score-timing116-terminal122-20261105/xu-server-terminal-20261105-122.tar.xz'
    raw=path.read_bytes(); need(ident(raw)=={'bytes':1283388,'sha256':'654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50'}, 'original sibling122 differs')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:xz') as archive:
        return {m.name:archive.extractfile(m).read() for m in archive if m.isfile()}


def blocks(text):
    result=[]; current=None
    for line in text.splitlines():
        if line and not line[0].isspace():
            if current is not None: result.append(current)
            current=[line]
        elif current is not None: current.append(line)
    if current is not None: result.append(current)
    return [block for block in result if block[0].startswith(('u_soc/','u_shared/'))]


def untested(text):
    rows=[]
    for block in blocks(text):
        pin=block[0].split()[0]; rest=' '.join(' '.join(block[1:]).split())
        need(re.search(r'\b(?:'+TYPES+r')\b',rest) is not None and re.search(r'\buntested\s+(?:constant_disabled|false_paths|no_endpoint_clock|no_clock|unknown)\b',rest) is not None, 'unowned untested detail')
        rows.append((pin,rest))
    need(len(rows)==len(re.findall(r'\buntested\s+(?:constant_disabled|false_paths|no_endpoint_clock|no_clock|unknown)\b',text))==27124, 'untested row ownership differs')
    return collections.Counter(rows)


def audit(payload):
    get=lambda name:payload[PREFIX+name]
    text=lambda name:get(name).decode()
    state=json.loads(get('state.json'))
    need(ident(get('state.json'))['sha256']==STATE_SHA and state['status']==STATUS and state['qualification']=='NOT_QUALIFIED', 'actual132 terminal differs')
    need(len(state['frozen_before'])==359 and state['frozen_before']==state['frozen_after'] and
         state['frozen_inputs_unchanged'] is True and not state['frozen_after_observation_errors'], 'actual132 complete freeze differs')
    need(state['producer']['sha256']==WORKER_SHA and state['producer']['bytes']==39436, 'actual132 frozen producer differs')
    need(state['original_failed126']['sha256']=='e6b6bd0ede831b18db2ed30633802ac88db8035e8198edf38f66fd18c88237fa', 'original126 failure identity differs')
    need({key:row['sha256'] for key,row in state['parent'].items()}=={
        'state':'7da5adb892fcaa33b5876e4f8dcbd9467a09dd8b40687476de529d1f7bf3c84f',
        'mapped':'16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292',
        'svf':'2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a'}, 'same116 parent differs')
    expected={'installed-docs.tcl':'XU_COVERAGE132_INSTALLED_DOCS_DONE_NOT_QUALIFIED', 'diagnosis.tcl':'XU_COVERAGE132_SAME116_READ_ONLY_DIAGNOSTIC_DONE_NOT_QUALIFIED'}
    native=[]
    need(len(state['runs'])==2, 'two native PT processes required')
    for run,(name,marker) in zip(state['runs'],expected.items()):
        need(run['returncode']==0 and run['marker_count']==1 and not run['errors'] and Path(run['script']['path']).name==name, 'actual native132 receipt failed')
        for kind in ('script','log'):
            receipt=run[kind]; need(ident(get(Path(receipt['path']).name))=={key:receipt[key] for key in ('bytes','sha256')}, 'native actual script/log bytes differ')
        log=text(Path(run['log']['path']).name)
        need(sum(line.strip()==marker for line in log.splitlines())==1 and not re.search(r'^\s*(?:Error:|Error-|Fatal:|XU_FATAL:)',log,re.M), 'actual native log failed')
        native.append({'script':name,'returncode':0,'marker_count':1,'script_sha256':run['script']['sha256'],'log_sha256':run['log']['sha256']})
    need(len(state['outputs'])==83 and {name[len(PREFIX):] for name in payload if name.startswith(PREFIX)}==set(state['outputs'])|{'state.json'}, 'complete132 output inventory differs')
    for name,receipt in state['outputs'].items():
        need(ident(get(name))=={key:receipt[key] for key in ('bytes','sha256')}, 'actual132 output receipt differs: '+name)
    parent=sibling122(); original_coverage=parent['full-soc-timing-combined-20261105-116/analysis-coverage.rpt'].decode()
    need(untested(original_coverage)==untested(text('coverage-initial.rpt'))==untested(text('coverage-final.rpt')), 'original/initial/final27124 full row multiset differs')
    for name in ('case','exceptions'):
        strip_date=lambda s:re.sub(r'^Date\s*:.*\n','',s,flags=re.M)
        need(strip_date(text(name+'-initial.rpt'))==strip_date(text(name+'-final.rpt')), 'native '+name+' changed')
    display=records(get('report-display-policy.tsv'))
    need(display==[{'field':'original','value':'false'},{'field':'restored','value':'false'}], 'report DISPLAY not restored')
    modes=records(get('macro-mode-pins.tsv')); byname=collections.defaultdict(dict)
    for row in modes:
        need(row['pin'] not in byname[row['macro']], 'duplicate macro mode pin'); byname[row['macro']][row['pin']]=row
    need(len(modes)==2688 and len(byname)==336, 'actual macro mode inventory differs')
    for macro,pins in byname.items():
        need(set(pins)==set(MODES)|{'CEN','CLK'} and all(pins[p]['constant_value']==v and pins[p]['user_case_value']=='' for p,v in MODES.items()), 'actual physical constant mode differs')
    period=collections.defaultdict(list)
    for block in blocks(text('period-all-status.rpt')):
        pin=block[0].split()[0]; rest=' '.join(' '.join(block[1:]).split())
        m=re.fullmatch(r'-\s+(\S+)\s+min_period\s+sdf_cond\(([^()]*)\)\s+(untested|[-+]?\d+(?:\.\d+)?)\s+(constant_disabled|-)',rest)
        need(m is not None and pin.endswith('/CLK') and pin[:-4] in byname, 'unparsed native period row')
        clock,condition,slack,reason=m.groups()
        if slack=='untested': need(clock=='-' and reason=='constant_disabled', 'inactive period reason differs')
        else: need(math.isfinite(float(slack)) and float(slack)>0 and reason=='-', 'native positive MET required')
        period[pin[:-4]].append((clock,condition,slack))
    expected_conditions={'RET1Neq1aEMA2eq%daEMA1eq%daEMA0eq%daEMAW1eq%daEMAW0eq%daCENeq0'%(a,b,c,d,e) for a in (0,1) for b in (0,1) for c in (0,1) for d in (0,1) for e in (0,1)}
    active_clocks=collections.Counter(); per_clock=[]
    for macro,pins in byname.items():
        rs=period[macro]; inactive=[r for r in rs if r[2]=='untested']; active=[r for r in rs if r[2]!='untested']
        clocks=pins['CLK']['clocks'].split()
        need(len(inactive)==31 and {r[1] for r in inactive}==expected_conditions-{ACTIVE}, 'per-macro31 inactive modes differ')
        need(all(r[1]==ACTIVE for r in active) and collections.Counter(r[0] for r in active)==collections.Counter(clocks), 'native per-clock active MET differs')
        active_clocks.update(r[0] for r in active); per_clock.append(len(active))
    need(active_clocks=={'xu_hfextclk':336,'xu_plldiv_envelope':80} and sorted(per_clock)==[1]*256+[2]*80, 'native active clock distribution differs')
    need(re.search(r'^min_period\s+10832\s+416\s+\(\s*4%\)\s+0\s+\(\s*0%\)\s+10416\s+\(\s*96%\)',text('period-all-status.rpt'),re.M), 'native period summary differs')
    arcs=records(get('macro-clock-arcs.tsv')); per_arc=collections.defaultdict(list)
    for row in arcs: per_arc[row['owner']].append(row)
    need(set(per_arc)==set(byname) and len(arcs)==12768, 'macro arc inventory differs')
    for macro,rs in per_arc.items():
        ps=[r for r in rs if r['sense']=='clock_min_period']
        need(len(rs)==38 and len(ps)==32 and sum(r['is_disabled']=='true' for r in ps)==31 and
             all(r['is_user_disabled']=='false' and r['is_db_inherited_disabled']=='false' for r in rs), 'native macro mode arc enabled/disabled differs')
    properties=records(get('reset-pin-properties.tsv')); reset_arcs=records(get('reset-design-arcs.tsv'))
    need(len(properties)==360 and len(reset_arcs)==60 and len(records(get('reset-lib-arcs.tsv')))==60, 'reset property/arc inventory differs')
    for i,cell in enumerate(CELLS):
        need({row['pin'] for row in properties if row['index']==str(i)}=={cell+'/'+p for p in ('D','CK',OUTPUTS[i],ASYNC[i])}, 'actual132 exact reset output differs')
        need(len([r for r in reset_arcs if r['owner']==cell])==12, 'reset native arc owner differs')
    consumers=records(get('reset-q-consumers.tsv'))
    need(len(consumers)==2 and {(r['index'],r['driver'],r['consumer'],r['sequential_or_endpoint']) for r in consumers}=={
        ('0',CELLS[0]+'/Q',CELLS[1]+'/D','true'),('4',CELLS[4]+'/Q',CELLS[3]+'/D','true')}, 'true first-stage structural consumer differs')
    paths=records(get('reset-timing-paths.tsv')); need(len(paths)==26, 'reset query count differs')
    expected_queries={(str(i),source,check) for i in range(5) for source in ('HF_RESET','ANY_ENDPOINT_SOURCE') for check in ('recovery','removal')}|{(str(i),'LF_WATCHDOG',check) for i in range(2,5) for check in ('recovery','removal')}
    need({(r['index'],r['source_kind'],r['check']) for r in paths}==expected_queries, 'reset query exact source/check inventory differs')
    for row in paths:
        tag='%s-%s-%s.rpt'%(row['source_kind'].lower(),row['index'],row['check']); report=text(tag)
        absent=row['check']=='recovery' and (row['source_kind']=='HF_RESET' or (row['source_kind']=='ANY_ENDPOINT_SOURCE' and int(row['index'])<2))
        if absent: need(row['count']=='0' and row['status']=='NO_PATH_UNKNOWN' and row['worst_slack']=='UNKNOWN' and 'No constrained paths.' in report, 'missing recovery incorrectly promoted')
        else:
            need(row['count']=='1' and row['status']=='PATH_PRESENT_DIAGNOSTIC_ONLY' and float(row['worst_slack'])>0, 'native R/R result differs')
            values=re.findall(r'slack \((\w+)\)\s+([-+\d.]+)',report)
            need(values and all(s=='MET' for s,_ in values) and abs(float(values[0][1])-float(row['worst_slack']))<0.000002, 'native R/R report/TSV mismatch')
    stage_slacks={}
    for i in range(3):
        for delay in ('min','max'):
            name='stage-%d-%s.rpt'%(i,delay); values=re.findall(r'slack \((\w+)\)\s+([-+\d.]+)',text(name))
            need(len(values)==1 and values[0][0]=='MET' and float(values[0][1])>0, 'native ordinary stage path missing/failed')
            stage_slacks[name]=values[0][1]
    for i in range(5):
        need('No constrained paths.' in text('unconstrained-hf-%d-recovery.rpt'%i) and 'slack (MET)' not in text('unconstrained-hf-%d-recovery.rpt'%i), 'unconstrained display wrongly promoted')
    unknown=records(get('unknown-queries.tsv'))
    need(len(unknown)==8 and all(r['status']=='ABSENT_NATIVE_ATTRIBUTE' and r['detail']=='NOT_INFERRED' for r in unknown), 'absent native attributes hidden')
    collections_rows=records(get('collection-observations.tsv'))
    need(len(collections_rows)==31330 and all((int(r['count'])==0 and r['status']=='EMPTY_COLLECTION' and r['names']=='') or (int(r['count'])>0 and r['status']=='NONEMPTY' and r['names']!='') for r in collections_rows), 'native collection emptiness differs')
    warning_codes=collections.Counter(re.findall(r'\(([A-Z]+-\d+)\)',text('diagnosis.log')))
    need(warning_codes['ATTR-1']==10000 and warning_codes['PTE-079']==68 and warning_codes['PTE-052']==1 and warning_codes['PTE-060']==18, 'original warning inventory differs')
    observe=json.loads(payload['live135-observation.json'])
    observed=[r for r in observe['observed'] if r['prefix']==PREFIX.rstrip('/')]
    need(len(observed)==1 and observed[0]['status']==STATUS and observed[0]['pid_alive_now'] is False, 'actual132 terminal observation differs')
    return {'status':'ACTUAL132_SAME116_READ_ONLY_NATIVE_TERMINAL_INDEPENDENTLY_VERIFIED', 'qualification':'NOT_QUALIFIED',
        'archive_payload_files':165,'archive_payload_bytes':181183292,'native132_output_files':84,
        'native_runs':native,'server_frozen_before_after_identity_records':359,
        'physical_macro_count':336,'physical_mode_pin_rows':2688,'inactive_period_checks':10416,
        'active_period_met_checks':416,'active_period_clocks':dict(active_clocks),
        'macro_active_clock_multiplicity':{'one_clock':256,'two_clocks':80},
        'macro_clock_arcs':12768,'original_initial_final_untested_rows':27124,
        'case_exceptions_unchanged_after_removing_dates':True,'report_display_original_restored':'false',
        'structural_first_stage_consumers':consumers,'reset_path_queries':paths,'ordinary_stage_slacks_ns':stage_slacks,
        'unconstrained_display_hf_recovery_reports_still_no_path':5,'absent_native_attributes':unknown,
        'native_warning_code_counts':dict(warning_codes),
        'limitations':['359 frozen receipts equal on server; local archive does not contain all359 source/library bodies.',
          '10000 ATTR-1 full_name warnings on timing_arc scope naming; owner/index/from/to arc TSV retained, generic collection scope is not full identity.',
          'Five HF and two PMU any-source recovery queries remain unknown, even with DISPLAY true; INFINITY/empty values are not finite safety margins.',
          '27124 untested, conditional reset pulse/skew, arbitrary async release, metastability, UART and150MHz qualification remain open.',
          'Companion128/130 original bytes verified only; no functional or power semantic claim.']}


def main():
    manifest=json.loads((HERE/'input-manifest.json').read_text())
    for name,expected in manifest['files'].items(): need(ident((HERE/name).read_bytes())==expected, 'local delivery differs: '+name)
    result=audit(original135())
    need(result==json.loads((HERE/'analysis132.json').read_text()), 'saved independent132 analysis differs')
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__': main()
