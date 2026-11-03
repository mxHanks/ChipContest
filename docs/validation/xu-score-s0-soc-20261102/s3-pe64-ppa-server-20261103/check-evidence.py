#!/usr/bin/env python3
"""xu: replay actual PE64 library PPA bytes and semantics; never certify timing/energy."""
from decimal import Decimal
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import re

H = Path(__file__).resolve().parent
GROUP = 's3-pe64-ppa-campaign-20261103-02/'
MAIN = '3443fad8945577626d226b1cd53eadec89331a20'
CHILD = '7aae96776e116d5e95d6ebb49d29a5fccce04ab9'
TOOL = 'e19304cb3f1f45ad2b691a9e316702ff2aeea9d1'
NET = '3e503963574a49d1111facf23b04877ccffed1eb317912871cbd7796593009ce'
SDC = '404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98'
STANDARD = 'f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723'
SRAM = 'c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f'
SCOPE = 'u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave'


def need(value,message):
    if not value:
        raise ValueError(message)


def sha(data):return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii'))


def load():
    original_data=(H/'original-export-manifest.json').read_bytes()
    need(sha(original_data)=='9bb8a55aaf3ab3079c285999edd801b5354123ae8869d6d2d532ec68d5904b60','fixed original export manifest differs')
    original=json.loads(original_data)
    selected=json.loads((H/'selected-manifest.json').read_text())
    expected={x['path']:x for x in original if x['path'].startswith(GROUP)}
    need(len(original)==148 and len({x['path'] for x in original})==148,'original export path set differs')
    need(len(expected)==79 and len(selected)==79,'selected complete79 PPA payload count differs')
    raw={}
    for record in selected:
        relative=Path(record['path']);path=H/relative
        need(not relative.is_absolute() and '..' not in relative.parts and path.is_file() and not path.is_symlink(),'unsafe stored path')
        data=path.read_bytes()
        need(len(data)==record['stored_bytes'] and sha(data)==record['stored_sha256'],'stored bytes differ')
        need(record['compression'] in ['none','xz'],'unknown compression')
        data=lzma.decompress(data) if record['compression']=='xz' else data
        item=record['original'];name=item['path']
        need(name in expected and item==expected[name] and name not in raw,'original manifest record differs/duplicates')
        need(len(data)==item['bytes'] and sha(data)==item['sha256'],'original raw bytes differ')
        raw[name]=data
    need(set(raw)==set(expected),'missing selected PPA original')
    record=json.loads((H/'context/source-manifest-record.json').read_text())
    data=(H/record['path']).read_bytes();need(len(data)==record['stored_bytes'] and sha(data)==record['stored_sha256'],'frozen source manifest storage differs')
    data=lzma.decompress(data)
    need(len(data)==812262 and sha(data)==record['sha256']=='cfa51eba8f04f282f360acf8e76118939a921cab063d05e61759ded798c7301d','frozen full source manifest differs')
    frozen=json.loads(data)
    data=(H/'context/prior-area-compliance.json').read_bytes()
    need(sha(data)=='8df6f900caf17e522ee4342295480bd605a62a0c1049b4a4ed5ba2414330cf3c','prior unit proof raw differs')
    units=json.loads(data)
    return raw,frozen,units


def semantic(raw,frozen,units):
    def data(name):
        need(GROUP+name in raw,'missing mandatory raw: '+name)
        return raw[GROUP+name]
    def text(name):return data(name).decode('utf-8')
    def read(name):return json.loads(data(name))
    j,e,i,p,g,v=[read(name) for name in ['state.json','ppa/execution.json','implementation/implementation.json',
        'ppa/prepared.json','implementation/generation.json','implementation/inventory.json']]
    spec=importlib.util.spec_from_file_location('xu_actual_pe64_ppa',H/'evidence-tools/xu_soc_ppa.py')
    producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
    need(j['status']==e['status']=='EXECUTED_NOT_QUALIFIED' and j['profile']=='s3-pe64','terminal/profile status differs')
    need(len(j['steps'])==3 and [x['index'] for x in j['steps']]==[0,1,2] and all(x['status']=='PASS' and x['returncode']==0 for x in j['steps']),'three actual PPA steps differ')
    need(sha(data('ppa/execution.json'))==j['execution_sha256'] and e['dc']['returncode']==e['pt']['returncode']==0,'execution receipt differs')
    need(e['netlist_sha256']==NET and e['analysis_sdc_sha256']==SDC,'original mapped net/analysis SDC differs')
    need(e['sdc_sha256']=='4b7324c8ffe32f26186dc50a4b24e9a77a77f140ca585400f26678337dd9f408','mapped SDC receipt differs')
    need(i==p['implementation'] and {k:value for k,value in p['inventory'].items() if k!='created_utc'}=={k:value for k,value in v.items() if k!='created_utc'},'implementation/inventory copies differ')
    need([i['source_profile'],p['inventory']['source_profile'],g['accel_variant']]==['s3-pe64','s3-pe64','pe64'],'physical source profile differs')
    freeze=i['source_freeze'];profile=freeze['profile']
    need(freeze['main_commit']==v['main_commit']==MAIN and freeze['e203_commit']==v['e203_commit']==CHILD,'main/child freeze differs')
    need(g['source_profile']==profile==j['acceptance']['source_profile'],'complete profile freeze copies differ')
    for label,commit,expected_count,expected_digest in [('main',MAIN,1637,'a4587fc98a837251787aeb72eb0820be2c1899177b593fb2336d0e933ab94f42'),('child',CHILD,1076,'9de1f5aca6b0773906555316d3d6c50a719036016c471a1201ddd7f16d4d54b2')]:
        block=frozen[label];files=block['files']
        need(block['commit']==commit and len(files)==len({x['path'] for x in files})==expected_count,'complete frozen source count/identity differs')
        records={x['path']:(dict(mode=x['mode'],commit=x['git_oid']) if x['mode']=='160000' else dict(mode=x['mode'],sha256=x['sha256'])) for x in files}
        need(digest(records)==expected_digest,'full source byte/mode/gitlink manifest differs')
        need((profile['main_source_freeze']['actual_main_tree_manifest_sha256'] if label=='main' else profile['actual_child_tree_manifest_sha256'])==expected_digest,'actual server/full original source freeze differs')
    need(profile['main_source_freeze']==dict(main_commit=MAIN,approved_main_tree='03e60bf367f039a382a57c5defca814735fe1ad6',tracked_main_entries=1637,actual_main_tree_manifest_sha256='a4587fc98a837251787aeb72eb0820be2c1899177b593fb2336d0e933ab94f42'),'original main tree identity differs')
    need(profile['e203_commit']==CHILD and profile['approved_tree']=='de46845651fd746d8060f2c17699281c18aed6e1' and profile['changed_files']==producer.SOURCE_PROFILES['s3-pe64']['changed_files'],'child fixed-platform delta differs')
    need(i['defines']==producer.PE64_DEFINES and i['accelerator_configuration']==v['accelerator_configuration']==g['accelerator_configuration']==producer.PE64_CONFIGURATION,'PE64 defines/geometry/padding differ')
    expected=producer.template(v,'s3-pe64')
    need(i['memory_groups']==expected['memory_groups'] and sum(x['count'] for x in i['memory_groups'])==g['macro_total']==384,'exact384 macro groups differ')
    for key,value in [('defines_sha256',i['defines']),('accelerator_configuration_sha256',i['accelerator_configuration']),('memory_groups_sha256',i['memory_groups']),('libraries_sha256',i['libraries'])]:
        need(freeze[key]==digest(value),'freeze digest differs: '+key)
    need([(x['role'],x['sha256']) for x in i['libraries']]==[('standard_cell',STANDARD),('sram',SRAM)],'exact same-server two libraries differ')
    need(i['constraints']['sha256']==SDC and p['generated_sha256']['constraints.sdc']==SDC,'canonical analysis SDC binding differs')
    need(sha(data('implementation/implementation.json'))==g['implementation']['sha256'],'generation implementation identity differs')
    tool_hash={'tools/scripts/xu_soc_ppa.py':'35e97861af17d37ed3d5d94deb5f240f88e2ddba92afce6f1d5265a8e9c45a3f','tools/ppa/xu_soc_implementation.py':'ad07c257a969eef9438fbc868f01af9e790c4b7a117bd55bcfbcd7eb36d113d1'}
    need(j['tool_sha256']==tool_hash and p['producer_sha256']==tool_hash['tools/scripts/xu_soc_ppa.py'],'actual tool producer differs')
    for name,digest_value in tool_hash.items():need(sha((H/'evidence-tools'/Path(name).name).read_bytes())==digest_value,'archived actual producer source differs')
    source_records={x['path']:x for x in frozen['child']['files']}
    need(len(p['source_files'])==163 and len(v['platform_source'])==161,'full prepared platform source counts differ')
    checked_sources=[];unreturned_sources=[]
    for name,record in p['source_files'].items():
        if name.startswith('rtl/xu-added/'):
            expected_sha=i['added_sources'][int(Path(name).name[:3])]['sha256']
        else:
            # Prepared paths omit the fixed rtl/e203 prefix.
            child_name='rtl/e203/'+name[4:]
            expected_sha=source_records[child_name]['sha256']
            need(record['original_platform_sha256']==expected_sha,'prepared original source is not frozen Git blob')
            replacement=i['replacements'].get('third-party/e203_hbirdv2/'+child_name)
            need(record['replacement']==bool(replacement),'replacement source selection differs')
            if replacement:expected_sha=replacement['sha256']
        need(record['sha256']==expected_sha,'prepared source mapping differs')
        if GROUP+'ppa/'+name in raw:
            need(sha(data('ppa/'+name))==expected_sha,'actual returned prepared source differs')
            checked_sources.append(name)
        else:unreturned_sources.append(name)
    need(len(checked_sources)==24,'returned prepared source subset is incomplete')
    for original,record in i['replacements'].items():
        name=Path(record['path']).name
        need(sha((H/'evidence-tools'/name).read_bytes())==record['sha256'],'actual SRAM replacement adapter differs')
    reports_checked=[];reports_missing=[]
    for name,record in e['reports'].items():
        if GROUP+'ppa/'+name in raw:
            need(len(data('ppa/'+name))==record['bytes'] and sha(data('ppa/'+name))==record['sha256'],'returned actual report differs: '+name)
            reports_checked.append(name)
        else:reports_missing.append(dict(path=name,receipt=record))
    need({x['path'] for x in reports_missing}=={'clock-reports/constraints.rpt','violations.rpt'},'returned report set is incomplete')
    for name,value in p['generated_sha256'].items():
        if GROUP+'ppa/'+name in raw:need(sha(data('ppa/'+name))==value,'returned generated control differs')
    need(text('ppa/synth.tcl').count(producer.memory_checks(i))==2 and text('ppa/sta.tcl').count(producer.memory_checks(i))==1,'actual generated macro guard Tcl differs')
    need(producer.clock_contract_checks() in text('ppa/synth.tcl') and producer.clock_contract_checks() in text('ppa/sta.tcl'),'actual150MHz clock guard Tcl differs')
    for name,key,version,marker,occurrences in [('ppa/dc.log','dc','T-2022.03-SP5-5','XU_SOC_SYNTHESIS_COMPLETE_NOT_QUALIFIED',2),('ppa/pt-sta.log','pt','T-2022.03-SP5-1','XU_SOC_STA_COMPLETE_NOT_QUALIFIED',1)]:
        content=text(name)
        need(sha(data(name))==e[key]['log_sha256'] and version in content and content.splitlines().count(marker)==1,'actual DC/PT version/completion differs')
        need(not re.search(r'^\s*(?:Error:|Fatal:|FATAL:|XU_FATAL:)',content,re.M),'actual EDA fatal/error marker')
        for group,count,logical,physical,padding in [('itcm',32,524288,524288,0),('dtcm',32,524288,524288,0),('shared',256,4194304,4194304,0),('accelerator_weights',64,262144,1048576,786432)]:
            line='XU_SRAM_GROUP %s count=%d macro_ref=RAMSP1024X16 logical_bits=%d physical_bits=%d padding_bits=%d'%(group,count,logical,physical,padding)
            need(content.splitlines().count(line)==occurrences,'actual pre/post/PT macro geometry differs')
    dc_units=text('ppa/dc-units.rpt');pt_units=text('ppa/units.rpt')
    need(re.search(r'^Time_unit\s*:\s*1\.0e-09 Second\(ns\)$',dc_units,re.M) is not None and re.search(r'^Time_unit\s*:\s*1e-09 Second$',pt_units,re.M) is not None,'time unit is not ns')
    need(units['status']=='PASS' and units['conversion']=='1 mm2 = 1000000 um2' and units['unit'].startswith('micrometres squared'),'physical area unit basis differs')
    ram=units['physical_sram'];width=Decimal(str(ram['cells'][0]['width_microns']));height=Decimal(str(ram['cells'][0]['height_microns']))
    need(width*height==Decimal(str(ram['lib_cell_area']))==Decimal('9148.5247'),'exact SRAM LEF/Liberty area unit differs')
    for check in units['physical_standard_cells']['checks']:
        need(Decimal(str(check['width_microns']))*Decimal(str(check['height_microns']))==Decimal(str(check['library_report_cell_area'])),'standard-cell physical unit proof differs')
    for ref,value in [('DRNQV2_12TR40','6.064800'),('BUFV2RD_12TR40','0.957600')]:
        values=re.findall(r'^'+ref+r'\s+scc40nll_vhsc40_rvt_ss_v0p99_125c_basic\s*\n\s*(\d+\.\d+)\s+',text('ppa/references.rpt'),re.M)
        need(values and set(values)=={value},'current mapped standard reference unit differs')
    area=text('ppa/area.rpt');lines=area.splitlines();indices=[k for k,line in enumerate(lines) if line.strip()==SCOPE]
    need(len(indices)==1,'canonical complete accelerator row is missing/duplicate')
    fields=lines[indices[0]+1].split()
    need(len(fields)==6 and fields[-1]=='xu_pe64_icb_slave','canonical accelerator row design differs')
    accel_um2=Decimal(fields[0]);whole=re.findall(r'^Total cell area:\s*(\d+\.\d+)$',area,re.M)
    need(accel_um2==Decimal('918420.9509') and whole==['3989337.870903'],'actual canonical accelerator/whole area differs')
    need(re.findall(r'^Number of macros/black boxes:\s*(\d+)$',area,re.M)==['384'],'actual area report macro total differs')
    need(re.findall(r'^Macro/Black Box area:\s*(\d+\.\d+)$',area,re.M)==['3513033.375000'],'macro footprint area differs')
    need(text('ppa/timing-slack.tsv')=='delay_type\tpath_count\tworst_slack\nmax\t1\t-23.631557\nmin\t1\t-29.837738\n','original negative propagated STA differs')
    coverage=text('ppa/analysis-coverage.rpt')
    need(re.search(r'^All Checks\s+397782\s+234973\s+\([^)]*\)\s+131624\s+\([^)]*\)\s+31185\s+\([^)]*\)',coverage,re.M) is not None,'actual original timing coverage differs')
    need(e['timing_review']['qualification']=='NOT_QUALIFIED' and set(e['timing_review']['observed_issues'])=={'setup_slack_negative','hold_slack_negative','no_clock_endpoints','report_command_failures'},'original timing issues were hidden')
    need(text('ppa/clock-reports/exceptions.rpt.unavailable.txt')=='COMMAND: report_exceptions -verbose\nERROR: Errors detected during redirect\nRequired for final signoff: yes\n','actual unsupported report was hidden')
    totals={'synthetic1':941800,'synthetic2':1883600,'real12':11301600,'same64-schedule32-control-real12':11376501,'same64-schedule8-control-real12':11842200,'physical32-wide32-control-real12':11376501,'physical8-auto8-control-real12':11842200}
    need(j['acceptance']['measured_total_cycles']==totals and j['acceptance']['state_sha256']=='8ccb234c9b29f6b25640f5dd98ba0f81264a5259dae93c438ceb2195be2626c6','actual VCS prerequisite identity differs')
    accel=accel_um2/Decimal(1000000);soc=Decimal(whole[0])/Decimal(1000000);limit=Decimal('2.25')
    return dict(status='ACTUAL_PE64_SAME_LIBRARY_AREA_REVIEWED_NOT_QUALIFIED',main_commit=MAIN,e203_commit=CHILD,producer_commit=TOOL,netlist_sha256=NET,
        canonical_area=dict(scope=SCOPE,accel_um2=str(accel_um2),accel_mm2=str(accel),whole_soc_mm2=str(soc),conversion_um2_per_mm2=1000000,
            accelerator_limit_mm2=str(limit),within_accelerator_area_limit=accel<=limit,budget_percent=str(accel/limit*100),physical_sram_area_basis='Same frozen DBs; prior four standard-cell and SRAM LEF/Liberty footprint proof'),
        physical_configuration=i['accelerator_configuration'],actual_macro_counts=dict(itcm=32,dtcm=32,shared=256,accelerator_weights=64,total=384),raw_files=len(raw),
        returned_reports_checked=reports_checked,unreturned_report_receipts=reports_missing,returned_prepared_sources_checked=checked_sources,unreturned_prepared_source_receipts=unreturned_sources,
        timing=dict(status='NOT_QUALIFIED',model='Original propagated unbuffered preCTS diagnostic',setup_ns='-23.631557',hold_ns='-29.837738',total_checks=397782,met=234973,violated=131624,untested=31185),
        actual_vcs_prerequisite_total_cycles=totals,not_qualified=['FM37 is separate; no mapped consistency claim in this archive','No complete150MHz timing qualification or macro internal qualification','No candidate formal-clear/request fullSoC single-task energy; wrapper power excluded','Mapped net/SVF, commercial DB bytes, listed missing large reports, and139 prepared sources were not downloaded; identities remain server receipts'])


def audit():
    result=semantic(*load())
    state=(H/'context/vcs-acceptance-state.json').read_bytes()
    need(sha(state)=='8ccb234c9b29f6b25640f5dd98ba0f81264a5259dae93c438ceb2195be2626c6','original actual VCS acceptance state differs')
    accepted=json.loads(state)
    need(accepted['status']=='VCS_ACCEPTED_NOT_RETAINED' and accepted['main_commit']==MAIN and accepted['e203_commit']==CHILD,'actual prior VCS acceptance incomplete')
    bridge=json.loads((H/'context/vcs-prerequisite-crosscheck.json').read_text())
    need(len(bridge['checked'])==120 and len(bridge['unreturned_server_review_receipts'])==3,'VCS prerequisite crosscheck coverage differs')
    j=json.loads(load()[0][GROUP+'state.json']);reviewed=j['acceptance']['reviewed_artifacts_sha256'];base=Path(j['source']).parent
    actual={str(Path(name).relative_to(base)):value for name,value in reviewed.items()}
    combined={x['path']:x['sha256'] for x in bridge['checked']}
    combined.update({x['path']:x['server_review_sha256'] for x in bridge['unreturned_server_review_receipts']})
    need(len(combined)==123 and combined==actual,'VCS crosscheck/actual PPA gate receipt differs')
    replay=json.loads((H/'context/full-git-replay.json').read_text())
    need(replay['status']=='PASS' and replay['main_commit']==MAIN and replay['e203_commit']==CHILD and replay['source_manifest_sha256']=='cfa51eba8f04f282f360acf8e76118939a921cab063d05e61759ded798c7301d','independent original Git replay differs')
    result['vcs_prerequisite_artifact_crosscheck']=dict(returned_originals=120,unreturned_simulator_build_receipts=3,state_sha256=sha(state))
    return result


if __name__=='__main__':
    print(json.dumps(audit(),indent=2,sort_keys=True))
