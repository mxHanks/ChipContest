#!/usr/bin/env python3
"""xu independently re-sign transport/receipt fields, then challenge PPA semantics."""
import copy
import importlib.util
import json
from pathlib import Path

H=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('xu_pe64_area_recheck',H/'check-evidence.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
RAW,FROZEN,UNITS=audit.load()


def read(raw,name):return json.loads(raw[audit.GROUP+name])
def put(raw,name,value):raw[audit.GROUP+name]=(json.dumps(value,indent=2)+'\n').encode()
def replace(raw,name,left,right):
    key=audit.GROUP+name
    assert left in raw[key],(name,left)
    raw[key]=raw[key].replace(left,right)


def resign(raw):
    """Bypass only easy receipt mismatch; physical/profile checks must still reject."""
    p=read(raw,'ppa/prepared.json');i=read(raw,'implementation/implementation.json');g=read(raw,'implementation/generation.json')
    for key,value in [('defines_sha256',i['defines']),('accelerator_configuration_sha256',i['accelerator_configuration']),('memory_groups_sha256',i['memory_groups']),('libraries_sha256',i['libraries'])]:
        i['source_freeze'][key]=audit.digest(value)
    put(raw,'implementation/implementation.json',i)
    p['implementation']=i
    v=read(raw,'implementation/inventory.json')
    v.update(main_commit=i['source_freeze']['main_commit'],e203_commit=i['source_freeze']['e203_commit'],accelerator_configuration=i['accelerator_configuration'])
    put(raw,'implementation/inventory.json',v)
    p['inventory']=v
    g['accelerator_configuration']=i['accelerator_configuration']
    for name in p['generated_sha256']:
        if audit.GROUP+'ppa/'+name in raw:p['generated_sha256'][name]=audit.sha(raw[audit.GROUP+'ppa/'+name])
    put(raw,'ppa/prepared.json',p)
    g['implementation']['sha256']=audit.sha(raw[audit.GROUP+'implementation/implementation.json'])
    put(raw,'implementation/generation.json',g)
    e=read(raw,'ppa/execution.json');j=read(raw,'state.json')
    for name,record in e['reports'].items():
        key=audit.GROUP+'ppa/'+name
        if key in raw:record.update(bytes=len(raw[key]),sha256=audit.sha(raw[key]))
    for name,key in [('ppa/dc.log','dc'),('ppa/pt-sta.log','pt')]:
        if audit.GROUP+name in raw:e[key]['log_sha256']=audit.sha(raw[audit.GROUP+name])
    put(raw,'ppa/execution.json',e);j['execution_sha256']=audit.sha(raw[audit.GROUP+'ppa/execution.json']);put(raw,'state.json',j)


def change_json(raw,name,mutate):
    value=read(raw,name);mutate(value);put(raw,name,value)


def main():
    positive=audit.semantic(RAW,FROZEN,UNITS)
    assert positive['canonical_area']['accel_mm2']=='0.9184209509'
    assert positive['canonical_area']['accelerator_limit_mm2']=='2.25'
    cases=[]
    def add(name,mutate):cases.append((name,mutate))
    add('area/local_cell_area_substituted',lambda r,f,u:replace(r,'ppa/area.rpt',b'918420.9509',b'6398.3639'))
    add('area/wholeSoC_scope_substituted',lambda r,f,u:replace(r,'ppa/area.rpt',audit.SCOPE.encode()+b'\n',b'u_shared\n'))
    add('area/mm2_treated_as_library_area',lambda r,f,u:replace(r,'ppa/area.rpt',b'918420.9509',b'0.9184209509'))
    add('area/wholeSoC_value_changed',lambda r,f,u:replace(r,'ppa/area.rpt',b'3989337.870903',b'918420.9509'))
    add('area/duplicate_complete_row',lambda r,f,u:r.__setitem__(audit.GROUP+'ppa/area.rpt',r[audit.GROUP+'ppa/area.rpt']+audit.SCOPE.encode()+b'\n 918420.9509 23.0 6398.3639 3359.8991 0.0000 xu_pe64_icb_slave\n'))
    add('macro/area_count_changed',lambda r,f,u:replace(r,'ppa/area.rpt',b'Number of macros/black boxes:             384',b'Number of macros/black boxes:             320'))
    add('macro/footprint_removed',lambda r,f,u:replace(r,'ppa/area.rpt',b'3513033.375000',b'0.000000'))
    add('macro/DC_W64_changed',lambda r,f,u:replace(r,'ppa/dc.log',b'XU_SRAM_GROUP accelerator_weights count=64',b'XU_SRAM_GROUP accelerator_weights count=32'))
    add('macro/PT_W64_changed',lambda r,f,u:replace(r,'ppa/pt-sta.log',b'XU_SRAM_GROUP accelerator_weights count=64',b'XU_SRAM_GROUP accelerator_weights count=32'))
    add('macro/generation_total_changed',lambda r,f,u:change_json(r,'implementation/generation.json',lambda v:v.update(macro_total=352)))
    add('macro/resigned_weight_padding_zero',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['accelerator_configuration'].update(weight_padding_bytes=0)))
    add('macro/resigned_memory_count_changed',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['memory_groups'][-1].update(count=32)))
    add('identity/main_pin_changed',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['source_freeze'].update(main_commit='0'*40)))
    add('identity/child_pin_changed',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['source_freeze'].update(e203_commit='0'*40)))
    add('identity/resigned_define_PE32',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['defines'].__setitem__(2,'XU_ACCEL_PE32=1')))
    add('identity/frozen_main_blob_changed',lambda r,f,u:f['main']['files'][0].update(sha256='0'*64))
    add('identity/frozen_main_mode_changed',lambda r,f,u:f['main']['files'][0].update(mode='100755' if f['main']['files'][0]['mode']=='100644' else '100644'))
    add('identity/frozen_main_gitlink_changed',lambda r,f,u:next(x for x in f['main']['files']if x['mode']=='160000').update(git_oid='0'*40))
    add('identity/frozen_child_blob_changed',lambda r,f,u:f['child']['files'][0].update(sha256='0'*64))
    add('identity/source_adapter_bytes_changed',lambda r,f,u:replace(r,'ppa/rtl/perips/mem_1024x16.sv',b'RAMSP1024X16',b'RAMSP128X16'))
    add('identity/standard_library_changed',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['libraries'][0].update(sha256='0'*64)))
    add('identity/SRAM_library_role_changed',lambda r,f,u:change_json(r,'implementation/implementation.json',lambda v:v['libraries'][1].update(role='standard_cell')))
    add('identity/netlist_changed',lambda r,f,u:change_json(r,'ppa/execution.json',lambda v:v.update(netlist_sha256='0'*64)))
    add('identity/analysisSDC_changed',lambda r,f,u:change_json(r,'ppa/execution.json',lambda v:v.update(analysis_sdc_sha256='0'*64)))
    add('identity/producer_changed',lambda r,f,u:change_json(r,'state.json',lambda v:v['tool_sha256'].update({'tools/scripts/xu_soc_ppa.py':'0'*64})))
    add('units/PT_time_changed',lambda r,f,u:replace(r,'ppa/units.rpt',b'1e-09 Second',b'1e-06 Second'))
    add('units/DC_time_changed',lambda r,f,u:replace(r,'ppa/dc-units.rpt',b'1.0e-09 Second(ns)',b'1.0e-06 Second(us)'))
    add('units/physical_micron_dimension_changed',lambda r,f,u:u['physical_sram']['cells'][0].update(width_microns=.08246))
    add('units/physical_area_label_changed',lambda r,f,u:u.update(unit='millimetres squared'))
    add('units/conversion_changed',lambda r,f,u:u.update(conversion='1 mm2 = 1000 um2'))
    add('units/standard_cell_dimension_changed',lambda r,f,u:u['physical_standard_cells']['checks'][0].update(width_microns=570))
    for name in ['ppa/area.rpt','ppa/dc.log','ppa/pt-sta.log','ppa/units.rpt','ppa/analysis-coverage.rpt','ppa/timing-slack.tsv','ppa/setup.rpt','ppa/rtl/perips/XuParallelComputeCore64.sv']:
        add('completeness/missing_'+name,lambda r,f,u,name=name:r.pop(audit.GROUP+name))
    add('timing/hidden_original_negative_slack',lambda r,f,u:replace(r,'ppa/timing-slack.tsv',b'-23.631557',b'0.000000'))
    add('timing/hidden_untested_checks',lambda r,f,u:replace(r,'ppa/analysis-coverage.rpt',b'31185 (  8%)',b'0 (  0%)'))
    add('timing/qualified_status_forged',lambda r,f,u:change_json(r,'ppa/execution.json',lambda v:v['timing_review'].update(qualification='PASS')))
    add('timing/unsupported_report_hidden',lambda r,f,u:r.__setitem__(audit.GROUP+'ppa/clock-reports/exceptions.rpt.unavailable.txt',b''))
    add('execution/live_step_forged_as_terminal',lambda r,f,u:change_json(r,'state.json',lambda v:v['steps'][-1].update(status='RUNNING')))
    add('prerequisite/truncated_control_cycles',lambda r,f,u:change_json(r,'state.json',lambda v:v['acceptance']['measured_total_cycles'].update({'physical8-auto8-control-real12':986850})))
    rejected=[]
    for name,mutate in cases:
        raw=dict(RAW);frozen=copy.deepcopy(FROZEN);units=copy.deepcopy(UNITS)
        mutate(raw,frozen,units);resign(raw)
        try:audit.semantic(raw,frozen,units)
        except ValueError as error:rejected.append(dict(case=name,rejection=str(error)))
        else:raise AssertionError('semantic mutation accepted: '+name)
    print(json.dumps(dict(status='ALL_SEMANTIC_MUTATIONS_REJECTED',cases=len(rejected),rejections=rejected,
        scope='In-memory altered raw/context data with available transport/execution/generated-control hashes re-signed; no EDA rerun or real input alteration'),indent=2))


if __name__=='__main__':main()
