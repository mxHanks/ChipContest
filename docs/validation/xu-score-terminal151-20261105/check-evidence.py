#!/usr/bin/env python3
"""Independent local byte/report audit of actual151; starts no EDA process."""
import argparse
from collections import Counter
import csv
from decimal import Decimal
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

HERE=Path(__file__).resolve().parent
ARCHIVE='xu-server-control-terminal-20261105-151.tar.xz'
ARCHIVE_SHA='84ad6475f61d14f68f51c52a4f2ecac4ae26aa43fe4c48227e579b435c1235ff'
B='/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/'
P130='s2e-full-soc-power12-20261105-130/'
P134='s2e-own-timing-repair-20261105-134/'
P142='full-soc-rdc-next-20261105-142/'
P132='full-soc-coverage-rdc-20261105-132/'
P116='full-soc-timing-combined-20261105-116/'
DIAGNOSTIC='PARTIAL_MODEL_DIAGNOSTIC_NOT_ENERGY_QUALIFIED'
RESET_BASE='u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/'
RESET_SINKS=[(RESET_BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_reg','SDN'),
             (RESET_BASE+'u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg','SDN')]+[
             (RESET_BASE+'aonrst_catch/reset_n_catch_reg/reg_%d/q_reg'%i,'RDN') for i in range(3)]


def need(ok,message):
    if not ok:raise ValueError(message)


def ident(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def file_ident(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return dict(bytes=Path(path).stat().st_size,sha256=h.hexdigest())


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def package(path,digest,size,count=None,total=None,keep=lambda name:True,no_vendor=False):
    need(file_ident(path)==dict(bytes=size,sha256=digest),'original package identity differs: '+str(path))
    identities={};contents={};manifest=None
    with tarfile.open(str(path),'r:xz') as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            need(member.isfile() and not p.is_absolute() and '..' not in p.parts and
                 member.name not in identities and 'private-manuals' not in p.parts and
                 'private-docs' not in p.parts,'unsafe/duplicate/private package member: '+member.name)
            if no_vendor:
                need(p.suffix not in ('.v','.sv','.vh','.svh','.lib','.db'),
                     'vendor/design body unexpectedly included in151: '+member.name)
            h=hashlib.sha256();length=0;chunks=[]
            retain=keep(member.name) or member.name=='manifest.json'
            stream=archive.extractfile(member)
            for block in iter(lambda:stream.read(1048576),b''):
                h.update(block);length+=len(block)
                if retain:chunks.append(block)
            need(length==member.size,'truncated package member')
            identities[member.name]=dict(bytes=length,sha256=h.hexdigest())
            if retain:
                data=b''.join(chunks)
                if member.name=='manifest.json':manifest=json.loads(data)
                else:contents[member.name]=data
    identities.pop('manifest.json',None)
    if count is not None:need(len(identities)==count,'package payload count differs')
    if total is not None:need(sum(r['bytes'] for r in identities.values())==total,'package payload bytes differ')
    if manifest is not None:
        need(len(manifest)==len(identities) and {r['path'] for r in manifest}==set(identities),'package manifest file set differs')
        for r in manifest:need(identities[r['path']]=={k:r[k] for k in ('bytes','sha256')},'payload hash differs: '+r['path'])
    elif count is not None:raise ValueError('package manifest absent')
    return contents,identities


def tsv(raw):
    rows=list(csv.DictReader(io.StringIO(raw.decode()),delimiter='\t'))
    need(all(None not in row and all(v is not None for v in row.values()) for row in rows),'malformed TSV row')
    return rows


def no_native_errors(raw):
    return not re.search(r'^\s*(?:Error:|Error-\[|Fatal:|XU_FATAL:)',raw,re.M)


def untested(raw):
    text=raw.decode() if isinstance(raw,bytes) else raw
    blocks=[];current=None
    for line in text.splitlines():
        if line and not line[0].isspace():
            if current is not None:blocks.append(current)
            current=[line]
        elif current is not None:current.append(line)
    if current is not None:blocks.append(current)
    owned=[]
    for block in blocks:
        if not block[0].startswith(('u_soc/','u_shared/')):continue
        rest=' '.join(' '.join(block[1:]).split())
        need(re.search(r'\buntested\s+(?:constant_disabled|false_paths|no_endpoint_clock|no_clock|unknown)\b',rest),
             'untested detail lacks exact pin/reason ownership')
        owned.append((block[0].split()[0],rest))
    need(len(owned)==len(re.findall(r'\buntested\s+(?:constant_disabled|false_paths|no_endpoint_clock|no_clock|unknown)\b',text))==27124,
         'all27124 untested rows must remain visible')
    return Counter(owned)


def strip_date(raw):
    return '\n'.join(line for line in raw.decode().splitlines() if not re.match(r'^Date\s*:',line))


def observation(raw):
    text=raw.decode();unconstrained=text.count('(Path is unconstrained)')
    starts=re.findall(r'^\s*Startpoint:\s*(.+)$',text,re.M)
    ends=re.findall(r'^\s*Endpoint:\s*(.+)$',text,re.M)
    slacks=re.findall(r'^\s*slack\s+\(([^)]+)\)\s+([^\s]+)',text,re.M)
    empty=bool(re.search(r'^\s*No constrained paths\.\s*$',text,re.M))
    status=('UNCONSTRAINED_PATH_DISPLAY_ONLY_NOT_RECOVERY_PROOF' if unconstrained else
            'PATH_TEXT_PRESENT_DIAGNOSTIC_ONLY' if starts and ends else
            'NO_PATH_UNKNOWN' if empty else 'UNRECOGNIZED_REPORT_UNKNOWN')
    return dict(status=status,unconstrained_markers=unconstrained,startpoints=starts,endpoints=ends,
                reported_slacks=[list(x) for x in slacks],no_constrained_paths=empty,qualification='NOT_QUALIFIED')


def audit(payload,identities,history132,history116):
    json_at=lambda name:json.loads(payload[name])
    local_checked=set()
    def receipt(record,required=True):
        need(record['path'].startswith(B),'unexpected server output scope')
        name=record['path'][len(B):]
        if name not in identities:
            need(not required,'required original body missing: '+name)
            return False
        need(identities[name]=={k:record[k] for k in ('bytes','sha256')},'server receipt/local original bytes differ: '+name)
        local_checked.add(name);return True
    def native(run,marker):
        need(run['returncode']==0 and run.get('marker_count',1)==1 and not run.get('errors',[]),'native receipt failed')
        receipt(run['log']);receipt(run['script'])
        text=payload[run['log']['path'][len(B):]].decode()
        need(sum(line.strip()==marker for line in text.splitlines())==1 and no_native_errors(text),'native log marker/error check failed')
        return dict(tool=run.get('tool','pt'),returncode=0,marker_count=1,log_sha256=run['log']['sha256'],script_sha256=run['script']['sha256'])

    execution=json_at(P130+'execution.json');prepared=json_at(P130+'prepared.json')
    need(execution['status']=='EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING' and execution['qualification']=='NOT_QUALIFIED' and
         execution['taskset_complete'] is True and execution['requested_task_ids']==list(range(12)) and
         [t['task_id'] for t in execution['tasks']]==list(range(12)) and [t['task_id'] for t in prepared['tasks']]==list(range(12)),
         'complete original twelve-task130 terminal required')
    inputs=execution['input_sha256_before']
    need(len(inputs)==554 and inputs==execution['input_sha256_after']==prepared['input_sha256'],'130 complete input before/after differs')
    need(execution['prepared']==execution['prepared_after'] and execution['pt']==execution['pt_after'] and
         execution['source_context_after']==prepared['source_context'] and
         execution['capture_tool_context_after']==prepared['original_capture_tool_context'],'130 immutable producer/tool/capture receipts differ')
    receipt(execution['prepared'])
    need(prepared['netlist']['sha256']=='0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0',
         '130 must use own89 S2e mapping, not116 or later repair')
    csv_rows=[];energies=[];powers=[]
    for task,plan in zip(execution['tasks'],prepared['tasks']):
        i=task['task_id'];directory=P130+'task_%02d/'%i
        need(task['status']=='EXECUTED_DIAGNOSTIC_REVIEW_PENDING' and
             task['frozen_inputs_before_after_rehashed_sha256']==canonical(inputs),'per-task130 immutable input rehash differs')
        run=task['execution'];need(run['returncode']==0,'130 PT failed');receipt(run['log'])
        rawlog=payload[directory+'pt.log'].decode()
        count=sum(line.strip()==plan['completion_marker'] for line in rawlog.splitlines())
        need(count==1 and no_native_errors(rawlog),'130 native PT completion marker/error differs')
        for name in ('power.rpt','units.rpt','tool-version.rpt'):receipt(task['reports'][name])
        receipt(plan['script']);receipt(task['diagnostic']['report'])
        need(payload[directory+'tool-version.rpt'].decode().strip()=='T-2022.03-SP5-1','130 native tool version differs')
        powertext=payload[directory+'power.rpt'].decode()
        need(re.search(r'^Design\s*:\s*xu_soc_ppa_top\s*$',powertext,re.M) and
             re.search(r'Dynamic Power Units\s*=\s*1 W',powertext) and
             re.search(r'Leakage Power Units\s*=\s*1 W',powertext),'130 full-SoC native power units/design differ')
        components={}
        for key,label in [('switching_power_w','Net Switching Power'),('internal_power_w','Cell Internal Power'),
                          ('leakage_power_w','Cell Leakage Power'),('total_power_w','Total Power')]:
            found=re.findall(r'^\s*'+label+r'\s*=\s*([-+0-9.eE]+)',powertext,re.M)
            need(len(found)==1,'ambiguous native power component')
            components[key]=str(Decimal(found[0]))
        diag=task['diagnostic'];need(components==diag['power_components'] and diag['status']==DIAGNOSTIC and
                                    diag['qualification']=='NOT_QUALIFIED','130 raw power/diagnostic components differ')
        window=plan['activity_window'];duration=window['end']['tick']-window['begin']['tick']
        elapsed=window['end']['cycle']-window['begin']['cycle']
        need(duration==window['duration_ticks']==5788953333333 and elapsed==window['formal_elapsed_cycles']==868343 and
             window['formal_inclusive_cycles']==elapsed+1 and
             abs(Fraction(duration)-Fraction(elapsed*20000000,3))<=1,'130 own nominal150 physical interval differs')
        seconds=Decimal(duration)*Decimal('1e-15');power=Decimal(components['total_power_w']);energy=power*seconds
        need(Decimal(diag['duration_seconds'])==seconds and Decimal(diag['diagnostic_energy_j'])==energy,'130 diagnostic energy multiplication differs')
        unknown=diag['measured_input_unknown_summary']
        need(unknown==plan['measured_summary'] and unknown['duration_ticks']==duration and
             unknown['pin_count']==22512 and unknown['q_pin_count']==5376 and unknown['q_tx_positive']==5280 and
             unknown['q_tx_full_window']==4256,'130 measured unknown summary receipts differ')
        energies.append(energy);powers.append(power)
        csv_rows.append(dict(task_id=i,formal_elapsed_cycles=elapsed,formal_inclusive_cycles=elapsed+1,duration_fs=duration,
            duration_seconds=str(seconds),reported_total_power_w=str(power),diagnostic_energy_j=str(energy),
            q_tx_positive_reported=unknown['q_tx_positive'],q_tx_full_window_reported=unknown['q_tx_full_window'],
            native_returncode=run['returncode'],native_marker_count=count,power_report_sha256=task['reports']['power.rpt']['sha256'],
            native_log_sha256=run['log']['sha256'],inputs_before_after_sha256=canonical(inputs),qualification='NOT_QUALIFIED'))
    summary=execution['diagnostic_summary']
    need(Decimal(summary['arithmetic_mean_reported_power_w'])==sum(powers)/Decimal(12) and
         Decimal(summary['sum_diagnostic_energy_j'])==sum(energies) and summary['total_elapsed_cycles']==10420116,
         '130 aggregate diagnostic arithmetic differs')

    timing=json_at(P134+'state.json')
    need(timing['status']=='FAILED_NOT_QUALIFIED' and timing['qualification']=='NOT_QUALIFIED' and
         timing['error']=='Error: field larger than field limit (131072)' and
         '_csv.Error: field larger than field limit (131072)' in timing['traceback'] and
         "proposal=plan(out/'posthold-inventory')" in timing['traceback'],'134 exact parser failure differs')
    need(len(timing['frozen_before'])==204 and timing['frozen_before']==timing['frozen_after'] and
         not timing['frozen_input_errors'],'134 immutable input capture differs')
    need(len(timing['runs'])==5 and 'repair_plan' not in timing,'134 failure must precede repair-plan/FM completion')
    native134=[]
    for run in timing['runs']:
        script=Path(run['script']['path']).name
        marker=('XU_S2E_TIMING134_PT_DONE_NOT_QUALIFIED' if run['tool']=='pt' else
                'XU_S2E_TIMING134_HOLD_DONE_NOT_QUALIFIED' if script=='repair.tcl' else
                'XU_S2E_TIMING134_INVENTORY_DONE_NOT_QUALIFIED')
        native134.append(native(run,marker))
    omitted=json_at('live151-observation.json')['omitted_large_text']
    need([(Path(r['path']).parent.name,r['bytes'],r['sha256']) for r in omitted]==[
        ('original-inventory',98866265,'7c7f86330c889c21f9c6229a99067d424e0d9305759ff7ff419eff68ee429a8d'),
        ('posthold-inventory',99406716,'2d7e3518ee0db58b25e71f97e2eb6688b410b85328014929561b96dd9e29946c')],
        '134 explicit large-body omission inventory differs')
    need(all(Path(r['path']).name=='native-cells.tsv' and r['path'][len(B):] not in identities for r in omitted),
         'omitted native cell bodies must not be represented as locally returned')

    rdc=json_at(P142+'state.json');analysis=json_at(P142+'analysis.json')
    need(rdc['status']=='EXECUTED_SAME116_READ_ONLY_RECOVERY_VISIBILITY_NOT_QUALIFIED' and rdc['qualification']=='NOT_QUALIFIED' and
         len(rdc['frozen_before'])==len(rdc['frozen_after']) and rdc['frozen_before']==rdc['frozen_after'] and
         rdc['frozen_inputs_unchanged'] and rdc['frozen_capture_complete'] and not rdc['frozen_after_observation_errors'],
         '142 original same116 terminal/freeze differs')
    need(len(rdc['runs'])==1,'142 one read-only native process required')
    native142=native(rdc['runs'][0],'XU_RDC142_SAME116_READ_ONLY_VISIBILITY_DONE_NOT_QUALIFIED')
    for record in rdc['outputs'].values():receipt(record)
    need(len(rdc['outputs'])==36 and rdc['parent116']['mapped']['sha256']=='16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292',
         '142 output count/same116 mapped identity differs')
    receipt(rdc['analysis'])
    need(untested(history116[P116+'analysis-coverage.rpt'])==untested(history132[P132+'coverage-final.rpt'])==
         untested(payload[P142+'coverage-initial.rpt'])==untested(payload[P142+'coverage-final.rpt']),
         '116/132/142 complete27124 untested row multiset differs')
    for kind in ('case','exceptions','clocks'):
        initial=payload[P142+kind+'-initial.rpt'];final=payload[P142+kind+'-final.rpt']
        historical=history132[P132+(kind+'.rpt' if kind=='clocks' else kind+'-final.rpt')]
        need(strip_date(initial)==strip_date(final)==strip_date(historical),'142 '+kind+' changed or differs from132')
    need(tsv(payload[P142+'report-display-policy.tsv'])==[
        dict(field='original',value='false'),dict(field='active',value='true'),dict(field='restored',value='false')],
        '142 DISPLAY restoration differs')
    arcs=tsv(payload[P142+'reset-ck-async-arcs.tsv']);oldarcs=tsv(history132[P132+'reset-design-arcs.tsv'])
    need(len(arcs)==10 and len({r['scope'] for r in arcs})==10,'142 ten unique native CK/async arcs required')
    arcfields=('from_pin','to_pin','sense','when','sdf_cond','is_disabled','is_user_disabled','is_db_inherited_disabled')
    for row in arcs:
        need(row['from_pin']==row['owner']+'/CK' and row['to_pin'].rsplit('/',1)[-1] in ('SDN','RDN') and
             row['scope']=='|'.join(row[k] for k in ('owner','index','from_pin','to_pin')) and
             all(row[k]=='false' for k in ('is_disabled','is_user_disabled','is_db_inherited_disabled')) and
             any(tuple(row[k] for k in arcfields)==tuple(old[k] for k in arcfields) for old in oldarcs),
             '142 exact enabled CK/async arc differs from132')
    for owner,pin in RESET_SINKS:
        owned=[r for r in arcs if r['owner']==owner and r['to_pin']==owner+'/'+pin]
        need(len(owned)==2 and {r['sense'] for r in owned}=={'setup_rise_clk_rise','hold_rise_clk_rise'},
             '142 each exact reset owner needs both enabled CK/async senses')
    commands=tsv(payload[P142+'query-commands.tsv'])
    need(len(commands)==21 and len(analysis['reports'])==7,'14221 queries/seven source controls required')
    need({(r['source_kind'],r['index']) for r in analysis['reports']}==
         {('HF_RESET',i) for i in range(5)}|{('ANY_ENDPOINT_SOURCE',i) for i in range(2)},
         '142 exact seven source/endpoint controls differ')
    independent=[]
    for report in analysis['reports']:
        i,kind=report['index'],report['source_kind'];tag=kind.lower()+'-'+str(i)
        historical=P132+('unconstrained-hf-%d-recovery.rpt'%i if kind=='HF_RESET' else 'any_endpoint_source-%d-recovery.rpt'%i)
        observed_history=observation(history132[historical]);need(observed_history==report['historical132'],'142 historical raw control differs')
        variants={}
        for variant in ('original132_filtered','matched_filtered','unfiltered'):
            name=tag+'-'+variant+'.rpt';raw=payload[P142+name]
            matching=[r for r in commands if r['index']==str(i) and r['source_kind']==kind and r['variant']==variant]
            need(len(matching)==1 and matching[0]['report']==name,'142 original command identity differs')
            command=matching[0]['command'];native_command=matching[0]['native_invocation']
            need(command.startswith('report_timing ') and '-delay_type max' in command and no_native_errors(raw.decode()),'142 invalid query/report')
            owner,pin=RESET_SINKS[i]
            expected='report_timing'+(' -from io_pads_aon_erst_n_i_ival' if kind=='HF_RESET' else '')+' -to '+owner+'/'+pin+' -delay_type max'
            if variant=='original132_filtered':expected+=' -slack_lesser_than 1000000 -max_paths 10 -significant_digits 8 -path_type full_clock_expanded'
            else:expected+=' -exceptions all'+(' -slack_lesser_than 1000000' if variant=='matched_filtered' else '')
            need(command==expected,'142 query changed exact source/endpoint/options')
            if variant=='unfiltered':
                need(command.endswith(' -delay_type max -exceptions all') and
                     not any(flag in command or flag in native_command for flag in ('-slack_lesser_than','-max_paths','-nworst')),
                     '142 unfiltered query changed more than the display/slack experiment')
            elif variant=='matched_filtered':
                need(command.endswith(' -delay_type max -exceptions all -slack_lesser_than 1000000'),
                     '142 matched filtered options differ')
            observed=observation(raw);need(observed==report['variants'][variant]['observation'],'142 independent raw report observation differs')
            receipt(report['variants'][variant]['report']);variants[variant]=observed
        need(variants['matched_filtered']['status']==variants['original132_filtered']['status']=='NO_PATH_UNKNOWN' and
             variants['unfiltered']['unconstrained_markers']==1 and not variants['unfiltered']['reported_slacks'] and
             report['visibility_verdict']=='FILTER_HID_UNCONSTRAINED_DISPLAY_ONLY_NOT_RECOVERY_PROOF' and
             report['recovery_qualification']=='NOT_PROVEN','142 display visibility must not become recovery proof')
        need(variants['unfiltered']['endpoints']==[RESET_SINKS[i][0]],'142 native display endpoint differs from exact query owner')
        independent.append(dict(index=i,source_kind=kind,endpoint=variants['unfiltered']['endpoints'][0],
            matched_filtered='NO_PATH_UNKNOWN',unfiltered='UNCONSTRAINED_PATH_DISPLAY_ONLY_NOT_RECOVERY_PROOF',
            finite_recovery_slacks=0,recovery_qualification='NOT_PROVEN'))
    need(analysis['query_count']==21 and analysis['untested_rows']==27124 and analysis['async_ck_check_arcs']==10 and
         analysis['full_untested_multiset_equal_116_132_initial_final'] is True and
         analysis['case_exceptions_clocks_same_as132_and_unchanged'] is True and
         analysis['qualification']=='NOT_QUALIFIED' and rdc['summary']==dict(recovery_qualification='NOT_PROVEN',report_queries=21,
         untested_rows=27124,visibility_gaps=7),'142 aggregate analysis differs')
    observations=json_at('live151-observation.json')['observations']
    need(len(observations)==4 and [r['alive_now'] for r in observations]==[False,False,False,True] and
         observations[3]['pid']==159584 and 'xu_experiment' in observations[3]['command'],
         '151 historical live/terminal observation differs')
    result=dict(schema='xu-terminal151-independent-audit-v1',qualification='NOT_QUALIFIED',
        archive_payload_files=len(identities),archive_payload_bytes=sum(r['bytes'] for r in identities.values()),
        locally_matched_server_output_receipts=len(local_checked),
        power130=dict(status=execution['status'],native_tasks=12,native_returncodes=[0]*12,native_marker_counts=[1]*12,
            server_input_before_after_records=len(inputs),server_input_before_after_equal=True,
            input_map_sha256=canonical(inputs),reported_power_mean_w=str(sum(powers)/Decimal(12)),
            sum_diagnostic_energy_j=str(sum(energies)),formal_elapsed_total_cycles=sum(r['formal_elapsed_cycles'] for r in csv_rows),
            original_inclusive_cycles_per_task=868344,formal_elapsed_cycles_per_task=868343,duration_fs_per_task=5788953333333,
            unknown_q_receipts_per_task=dict(tx_positive=5280,tx_full_window=4256,total_q=5376),
            unknown_summary_scope='Prepared/execution receipts agree; original SAIF and native pin reports are not in151.',
            arithmetic_scope='Rounded native full-SoC power multiplied by physical task duration; no contest energy or score.'),
        timing134=dict(status=timing['status'],error=timing['error'],server_input_before_after_records=204,
            server_input_before_after_equal=True,completed_native_runs=native134,omitted_large_text=omitted,
            completion_scope='Five native commands passed; Python failed before repair-plan/final PT/full FM. No timing closure.'),
        rdc142=dict(status=rdc['status'],native_run=native142,server_input_before_after_records=len(rdc['frozen_before']),
            server_input_before_after_equal=True,full116_132_142_untested_multiset_equal=True,untested_rows=27124,
            unchanged_case_exceptions_clocks=True,enabled_async_ck_arcs=10,queries=21,visibility_gaps=7,reports=independent,
            recovery_qualification='NOT_PROVEN'),
        historical_process_observation=observations,
        limitations=['No numerical qualification, complete150MHz timing closure, or contest energy/score follows.',
            '554/204/142 server input before/after receipts are equal; not all source/library bodies were returned locally.',
            '130 original measured SAIF, native pin reports, and other detailed reports remain server-side with receipt hashes.',
            'Both134 native-cells.tsv bodies were deliberately omitted; their returned hashes are not independent local body validation.',
            '134 parser failure and every prior unknown/untested check are retained.',
            'The live151 process observation is historical, not a current liveness check.'])
    return result,csv_rows


def csv_bytes(rows):
    text=io.StringIO();writer=csv.DictWriter(text,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows);return text.getvalue().encode()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write-results',action='store_true');args=parser.parse_args()
    if not args.write_results:
        manifest=json.loads((HERE/'input-manifest.json').read_text())
        for name,expected in manifest['files'].items():need(file_ident(HERE/name)==expected,'local delivery changed: '+name)
    payload,identities=package(HERE/ARCHIVE,ARCHIVE_SHA,672360,191,50892386,no_vendor=True)
    history132,_=package(HERE.parent/'xu-score-coverage132-server135-20261105/xu-server-coverage-power-progress-20261105-135.tar.xz',
        '7972967f569bdc76794e79fe8a112d43fb9ce0bd8d3c85aed8c589f9d5c1c19f',2730552,165,181183292,
        keep=lambda name:name.startswith(P132))
    history116,_=package(HERE.parent/'xu-score-timing116-terminal122-20261105/xu-server-terminal-20261105-122.tar.xz',
        '654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50',1283388,
        keep=lambda name:name.startswith(P116))
    result,rows=audit(payload,identities,history132,history116)
    outputs={'analysis151.json':(json.dumps(result,sort_keys=True,indent=2)+'\n').encode(),
             's2e-power130-layers.csv':csv_bytes(rows)}
    for name,data in outputs.items():
        path=HERE/name
        if args.write_results:
            need(not path.exists(),'new result output required: '+name);path.write_bytes(data)
        else:need(path.read_bytes()==data,'saved independent result differs: '+name)
    print(json.dumps(dict(status='ACTUAL151_ORIGINAL_BYTES_AND_DIAGNOSTIC_REPORTS_VERIFIED_NOT_QUALIFIED',
                         payload_files=len(identities),power_tasks=len(rows),timing134='FAILED_CSV_FIELD_LIMIT',
                         rdc142_visibility_gaps=7,qualification='NOT_QUALIFIED'),sort_keys=True))


if __name__=='__main__':main()
