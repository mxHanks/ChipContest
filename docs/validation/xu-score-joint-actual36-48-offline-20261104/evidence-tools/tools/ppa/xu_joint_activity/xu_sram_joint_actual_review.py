#!/usr/bin/env python3
"""xu strict-byte offline review of actual36 body and actual48 API evidence.

The malformed original transaction header is retained as bytes. Numeric metadata
is inspected separately; no replacement header or repaired capture is produced.
The unavailable 12.3 GB simultaneous sidecar is never inferred from projections.
"""
import argparse,hashlib,importlib.util,json,lzma,re
from pathlib import Path

HERE=Path(__file__).resolve().parent
P36='s2c-joint-activity-task00-20261103-36/'
MODEL_SHA='81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51'
REPORT_SHA='f1d18b00fece31f942a514505d808e704179c3a99437aebb9abf152823757ba7'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

audit=load('xu_actual_joint_integer_auditor',HERE/'xu_sram_joint_audit.py')
require=audit.require

def digest(data):return hashlib.sha256(data).hexdigest()
def parse(data):return json.loads(data.decode('ascii'),object_pairs_hook=audit.unique_json)

class ManifestInput:
    def __init__(self,root,manifest):
        self.root=Path(root);self.records={};self.observed={}
        for r in parse(Path(manifest).read_bytes()):
            name=r['path'];require(name not in self.records and not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe/duplicate manifest path')
            self.records[name]=r
    def __call__(self,name):
        require(name in self.records,'input absent from original export manifest '+name)
        p=self.root/name
        if not p.exists():p=Path(str(p)+'.xz')
        require(p.is_file() and not p.is_symlink(),'regular original/payload file required '+name)
        stored=p.read_bytes();data=lzma.decompress(stored) if p.suffix=='.xz' else stored;r=self.records[name]
        require(len(data)==r['bytes'] and digest(data)==r['sha256'],'original export bytes/SHA mismatch '+name)
        self.observed[name]=dict(logical_path=name,bytes=len(data),sha256=digest(data),stored_path=str(p.resolve()),stored_bytes=len(stored),stored_sha256=digest(stored))
        return data
    def verify_all(self):
        for name in sorted(self.records):self(name)

def stats_parts(data):
    lines=data.splitlines();require(len(lines)==338,'actual336 capture must contain 338 lines')
    raw=lines[0];numeric={}
    for name in ('task_id','start_tick','end_tick','duration_ticks','timescale_fs','begin_callback_ordinal','end_callback_ordinal','macro_count','pin_bits_per_macro','liberty_arc_count'):
        fields=re.findall(rb'"'+name.encode('ascii')+rb'":([0-9]+)(?=[,}])',raw)
        require(len(fields)==1,'numeric header field missing/ambiguous '+name);numeric[name]=audit.number(int(fields[0]))
    require(raw.startswith(b'{"schema":"xu-sram-joint-projections-v1",'),'actual schema bytes differ')
    require(numeric['task_id']==0 and numeric['timescale_fs']==1 and numeric['macro_count']==336 and numeric['pin_bits_per_macro']==67 and numeric['liberty_arc_count']==121,'actual header geometry differs')
    require(numeric['end_tick']-numeric['start_tick']==numeric['duration_ticks']>0,'actual header span differs')
    identities=re.search(rb',"begin_transaction":(.*),"end_transaction":(.*),"macro_count":',raw)
    require(identities is not None,'actual transaction byte partition missing')
    try:raw.decode('utf-8');utf8=dict(valid=True)
    except UnicodeDecodeError as e:utf8=dict(valid=False,invalid_start=e.start,invalid_end=e.end,reason=e.reason)
    rows=[parse(b) for b in lines[1:-1]];footer=parse(lines[-1]);require(footer['complete'] is True and footer['macro_count']==336,'actual completion footer differs')
    return numeric,rows,footer,dict(raw_header_hex=raw.hex(),raw_header_bytes=len(raw),raw_header_sha256=digest(raw),utf8=utf8,
        begin_transaction_json_bytes_hex=identities[1].hex(),end_transaction_json_bytes_hex=identities[2].hex(),
        begin_transaction_observed=parse(identities[1]),
        status='ORIGINAL_TRANSACTION_IDENTITY_INVALID_NOT_REPAIRED',
        policy='Numeric metadata and 336 ASCII body objects are audited separately. Original transaction strings do not qualify; no replacement stats/header is emitted.')

def binary(dwell,transitions):
    return not any(dwell[2:]) and not any(v for i,v in enumerate(transitions) if i//4>1 or i%4>1)

def classify_hold(macros,duration):
    rows=[]
    for macro in macros:
        reasons=[]
        for pin in ('CEN','RET1N'):
            if macro['pin_dwell'][pin]!=[0,duration,0,0] or any(macro['pin_transitions'][pin]):reasons.append(pin+'_NOT_CONST_KNOWN_1_INCLUDING_ZERO_DWELL_EDGES')
        for pin in audit.CONTROL+['CLK']:
            if not binary(macro['pin_dwell'][pin],macro['pin_transitions'][pin]):reasons.append(pin+'_UNKNOWN_STATE_OR_ZERO_DWELL_EDGE')
        closed=[];unknown=[]
        if not reasons:
            arcs=[a for a in macro['arcs'] if a['toggling_pin'] and a['toggling_pin'].startswith('Q[')]
            require(len(arcs)==16 and all(a['kind']=='internal' and a['when']=='RET1N & GWEN' for a in arcs),'fixed actual Q16 arc set differs')
            for arc in arcs:
                pin=arc['toggling_pin'];d=macro['pin_dwell'][pin]
                require(not any(macro['pin_transitions'][pin]) and d.count(duration)==1,'measured Q contradicts hold premise')
                state='01xz'[d.index(duration)]
                require(state!='z','held Q Z not justified as arbitrary binary initial state')
                closed.append(arc['arc_id'])
                if state=='x':unknown.append(pin)
        rows.append(dict(macro=macro['macro'],hold_premises_satisfied=not reasons,rejection_reasons=reasons,closed_Q_internal_arc_ids=closed,stable_absolute_unknown_Q_pins=unknown))
    return dict(status='CONDITIONAL_FIXED_VENDOR_DIGITAL_HOLD_CLASSIFICATION',model_sha256=MODEL_SHA,actual_library_report_sha256=REPORT_SHA,
        proven_hold_macros=sum(r['hold_premises_satisfied'] for r in rows),closed_Q_internal_arcs=sum(len(r['closed_Q_internal_arc_ids']) for r in rows),
        stable_absolute_unknown_Q_pins=sum(len(r['stable_absolute_unknown_Q_pins']) for r in rows),rows=rows,
        proof='For frozen ARM_UD_MODEL normal power pins, constant known CEN=RET1N=1 and binary controls including zero-dwell edges prevent every Q assignment. Any initial binary Q is held, so the 16 internal Q edge energies are zero. The model identity and variant are recorded, not distributed.',
        absolute_state_policy='No absolute Q probability, SP0.5, unknown-zero, downstream-cell leakage/internal or whole-SoC energy is inferred.')

def one_line(log,pattern,message):
    rows=re.findall(pattern,log,re.M);require(len(rows)==1,message);return rows[0]

def q_initial_resolution_bounds(macros):
    rise=fall=x0=x1=0;rows=[];unresolved=[];all_true=True
    for macro in macros:
        for arc in macro['arcs']:
            pin=arc['toggling_pin']
            if not pin or not pin.startswith('Q['):continue
            v=macro['pin_transitions'][pin];rise+=v[1];fall+=v[4];x0+=v[8];x1+=v[9]
            bad=sum(n for i,n in enumerate(v) if n and (i//4>1 or i%4>1) and i not in (8,9))
            if bad:unresolved.append(dict(macro=macro['macro'],pin=pin,other_nonbinary_edges=bad))
            all_true &= all(a==b==1 for a,b,_,_,_ in arc['conditional_transitions'])
            if v[8] or v[9]:rows.append(dict(macro=macro['macro'],pin=pin,arc_id=arc['arc_id'],X_to_0=v[8],X_to_1=v[9],additional_rise_bounds=[0,v[9]],additional_fall_bounds=[0,v[8]]))
    return dict(status='CONDITIONAL_DIGITAL_INITIAL_RESOLUTION_COUNT_BOUNDS_NOT_POWER',known_binary_rise=rise,known_binary_fall=fall,
        observed_X_to_0=x0,observed_X_to_1=x1,other_nonbinary_edge_pins=unresolved,all_observed_Q_edge_condition_endpoints_true=all_true,
        conditional_rise_bounds=[rise,rise+x1] if not unresolved else None,conditional_fall_bounds=[fall,fall+x0] if not unresolved else None,
        unknown_initial_resolution_bits=sum(bool(r['X_to_0'] or r['X_to_1']) for r in rows),rows=rows,
        required_proof=['All physical addresses that can feed these reads have valid initialization/clear provenance in the same fresh process.',
            'Frozen vendor model plus binary-control observation proves at most one initial-state resolution per listed bit, and excludes hidden read assignments while digital Q remains X.',
            'Actual callback and sidecar same-timestamp controls qualify the effective library condition; observed before/after true is retained but not promoted to that proof.'],
        energy_next_step='For each listed mapped macro/Q arc, query the actual Liberty rise/fall energy tables with qualified slew/load bounds. Additional energy is [0, X_to_1*max_rise_energy + X_to_0*max_fall_energy]; sum per arc. Keep known-count energy and downstream absolute-state bounds separate. No half probability is assigned.')

def review36(read_input):
    raw=read_input(P36+'task_00/task-joint.stats.jsonl');meta,records,footer,header=stats_parts(raw)
    ledger_bytes=audit.LEDGER.read_bytes();require(digest(ledger_bytes)==audit.LEDGER_SHA256,'frozen ledger bytes differ')
    ledger=parse(ledger_bytes);require(ledger['report_sha256']==REPORT_SHA and len(ledger['arcs'])==121,'mature actual ledger differs')
    names=[r['macro'] for r in records];require(len(names)==len(set(names))==336,'actual336 membership differs')
    macros=[audit.audit_macro(r,meta['duration_ticks'],ledger['arcs']) for r in records]
    binding=parse(read_input(P36+'simulator/joint-binding.json'))
    require(set(names)=={r['rtl_instance'] for r in binding['pairs']} and binding['macro_count']==336,'exact RTL/mapped binding differs')
    run=parse(read_input(P36+'result.json'));freeze=parse(read_input(P36+'input-freeze.json'))
    require(run['status']=='FAIL' and 'invalid start byte' in run['error'] and run['tasks']==[],'historical failure receipt differs')
    require('+define+ARM_UD_MODEL' in run['build_command'] and not any('POWER_PINS' in x or 'INITIALIZE_MEMORY' in x for x in run['build_command']),'actual vendor variant differs')
    models=[r for r in freeze['files'] if r['path'].endswith('/RAMSP1024X16.v')]
    require(len(models)==1 and models[0]['sha256']==MODEL_SHA,'frozen vendor model identity differs')
    matching=[]
    for r in freeze['files']:
        if P36 in r['path']:
            rel=P36+r['path'].split(P36,1)[1]
            if rel not in getattr(read_input,'records',{}):continue
            b=read_input(rel)
            require(digest(b)==r['sha256'] and len(b)==r['bytes'],'exported frozen source differs '+rel);matching.append(rel)
    log=read_input(P36+'task_00/simulation.log').decode('ascii')
    begin=tuple(map(int,one_line(log,r'^XU_JOINT_BEGIN task=(\d+) tick=(\d+) macros=(\d+) callback_ordinal=(\d+)$','joint begin missing/duplicate')))
    end=tuple(map(int,one_line(log,r'^XU_JOINT_COMPLETE task=(\d+) tick=(\d+) duration_ticks=(\d+) macros=(\d+) simultaneous_records=(\d+) NOT_QUALIFIED$','joint complete missing/duplicate')))
    require(begin==(0,meta['start_tick'],336,meta['begin_callback_ordinal']) and end==(0,meta['end_tick'],meta['duration_ticks'],336,footer['simultaneous_records']),'stats/log span or count differs')
    request=tuple(map(int,one_line(log,r'^XU_SOURCE_REQUEST task=0 cycle=(\d+) tick=(\d+)$','source request missing/duplicate')))
    window=tuple(map(int,one_line(log,r'^XU_TASK_WINDOW task=0 request_cycle=(\d+) accept_cycle=(\d+) end_cycle=(\d+) initial_wait_cycles=0 legacy_inclusive_cycles=(\d+) formal_inclusive_cycles=(\d+) formal_elapsed_cycles=(\d+)$','actual source/final task window missing')))
    require(request==(window[0],meta['start_tick']) and window[0]==window[1] and window[2]-window[0]==window[-1] and window[3]==window[4]==window[-1]+1,'source window cycle accounting differs')
    require(re.search(r'^XU_ACTIVITY_END task=0 tick='+str(meta['end_tick'])+'$',log,re.M) and re.search(r'^TASK_PASS layer=0 outputs=25344 writes=50688 cycles='+str(window[3])+r' firmware_cycles=\d+$',log,re.M) and re.search(r'^SOC_PASS tasks=1 outputs=25344 writes=50688$',log,re.M),'task/SoC/boundary pass missing')
    require(not re.search(r'^(?:XU_JOINT_REJECT|XU_JOINT_INCOMPLETE|FATAL|TEST_FAIL)(?: |:|$)',log,re.M),'actual rejection log')
    clear=one_line(log,r'^XU_TASK_CLEAR_OBSERVED.*$','clear observation missing')
    require(clear=='XU_TASK_CLEAR_OBSERVED writes=33697 w=16384 bias=256 legacy_bias=8 x=64 drained=1 cache_enable=0 idle=1 source_request=1 task_setup_writes=0 actual_commits=1 fifo_reset_empty=1','actual pretask clear differs')
    saif=read_input(P36+'task_00/task.saif')
    require(len(re.findall(rb'\(TIMESCALE 1 fs\)',saif))==1 and re.findall(rb'\(DURATION ([0-9]+)\.00\)',saif)==[str(meta['duration_ticks']).encode('ascii')],'native SAIF duration/timescale differs')
    tb=read_input(P36+'simulator/tb_xu_s2c_joint_task_activity.sv').decode('ascii')
    require(tb.count('$xu_sram_joint_register(')==336 and 'final response transaction identity differs' in tb and '$sformatf("source_request cycle=' in tb and '$sformatf("final_y_retire cycle=' in tb,'actual generated transaction guards differ')
    hold=classify_hold(macros,meta['duration_ticks'])
    summary=[]
    for arc in ledger['arcs']:
        rows=[m['arcs'][arc['arc_id']] for m in macros]
        summary.append(dict(arc_id=arc['arc_id'],kind=arc['kind'],pin=arc['toggling_pin'],when=arc['when'],
            condition_dwell_false_true_unknown=[sum(r['condition_dwell_false_true_unknown'][i] for r in rows) for i in range(3)],
            true_condition_unknown_pin_ticks=sum(sum(r['pin_joint_dwell'][1][2:]) for r in rows if r['pin_joint_dwell']),
            conditional_transition_records=sum(len(r['conditional_transitions']) for r in rows)))
    joint=dict(schema='xu-actual36-body-expanded-integer-audit-v1',status='336_BODY_INTEGER_INVARIANTS_PASS_HEADER_AND_SIDECAR_UNQUALIFIED',numeric_window_metadata=meta,macros=macros)
    receipt=dict(schema='xu-actual36-offline-review-v1',status='ACTUAL_TASK_PASS_BODY336_INTEGER_PASS_TRANSACTION_HEADER_INVALID_SIDECAR_ABSENT',
        original_failure_preserved=dict(status=run['status'],error=run['error']),header=header,numeric_window_metadata=meta,
        macro_count=336,pin_bits=22512,arc_count_per_macro=121,total_arc_instances=40656,projection_instances=11424,
        exact_mapped_binding=True,native_saif_duration_ticks=meta['duration_ticks'],formal_elapsed_cycles=window[-1],
        actual_source_request_cycle=window[0],actual_end_cycle=window[2],pretask_clear_observed=clear,exported_freeze_matches=sorted(set(matching)),
        frozen_file_count=len(freeze['files']),actual_model_declared_identity=models[0],arc_summary=summary,Q_hold=hold,Q_initial_resolution=q_initial_resolution_bounds(macros),
        missing_evidence=dict(simultaneous_sidecar_present_locally=False,expected_simultaneous_records=footer['simultaneous_records'],server_reported_sidecar_bytes=12303644205,
            consequences=['No 24,674,210-row simultaneous replay, boundary initial-state flow audit, or cross-port same-timestamp classification.',
                'No after-run complete-file freeze record is available in the 24-file export.',
                'Original source/final transaction identity strings failed and are not repaired from expected values.']),
        qualification='Body projection conservation and exact ledger expansion only. Native SAIF per-pin equivalence, full callback scheduling, conditional PT consumption, downstream absolute-state bounds and whole-SoC task energy remain open.')
    return receipt,joint

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw-dir',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expanded-out',type=Path,required=True);p.add_argument('--vendor-model',type=Path);a=p.parse_args()
    require(not a.out.exists() and not a.expanded_out.exists(),'new receipt paths required')
    source=ManifestInput(a.raw_dir,a.manifest);source.verify_all();before=dict(source.observed)
    r36,expanded=review36(source);pt=load('xu_actual48_api_review',HERE/'xu_pt_joint_actual48_review.py');r48=pt.review(source)
    ledger=parse(audit.LEDGER.read_bytes());projection=parse(source('pt-joint-state-condition-20261103-48/measured-joint-projection.json'))
    require(all(tuple(a[k] for k in ('arc_id','kind','toggling_pin','when'))==tuple(b[k] for k in ('arc_id','kind','toggling_pin','when')) for a,b in zip(ledger['arcs'],projection['arcs'])),'actual48 projection differs from mature121arc ledger')
    r48['mature_ledger_arc_metadata_exact_match']=True
    result=dict(schema='xu-actual36-48-offline-review-v1',status='OFFLINE_REVIEW_COMPLETE_NOT_WHOLE_SOC_ENERGY',actual36=r36,actual48=r48)
    if a.vendor_model:
        b=a.vendor_model.read_bytes();require(digest(b)==MODEL_SHA,'private fixed vendor model bytes differ');result['private_model_verified']=dict(path=str(a.vendor_model.resolve()),bytes=len(b),sha256=digest(b),published=False)
    source.verify_all();require(source.observed==before,'payload changed during review');result['verified_inputs']=list(source.observed.values())
    a.expanded_out.write_bytes(lzma.compress((json.dumps(expanded,sort_keys=True,separators=(',',':'))+'\n').encode('ascii')))
    result['expanded_integer_audit']=dict(path=str(a.expanded_out.resolve()),bytes=a.expanded_out.stat().st_size,sha256=digest(a.expanded_out.read_bytes()),encoding='xz compressed ASCII JSON; not a repaired capture')
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],actual36=r36['status'],actual48=r48['status'],hold_macros=r36['Q_hold']['proven_hold_macros'],closed_Q_arcs=r36['Q_hold']['closed_Q_internal_arcs']),sort_keys=True))

if __name__=='__main__':main()
