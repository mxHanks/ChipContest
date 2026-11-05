#!/usr/bin/env python3
"""Collect twelve fresh-process full-SoC task activity windows for one exact candidate."""
import argparse
from decimal import Decimal
from fractions import Fraction
import inspect
import json
from pathlib import Path
import re
import shutil
import sys
import traceback
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import context145 as context
import observer145 as observer
import macro145
require,identity,sha,write_json=context.require,context.identity,context.sha,context.write_json
SCOPE='tb_xu_soc_ppa.dut'
TERMINAL='COLLECTED_12_REVIEW_PENDING_NOT_QUALIFIED'


def unchanged(records):
    for record in records:
        require(identity(record['path'])==record,'run input changed: '+record['path'])


def check_native_freeze(configuration, binary, frozen):
    """Final task-input receipt must include the actual native compile chain."""
    native=configuration.get('native_compiler')
    require(isinstance(native,dict),'native compiler identity missing')
    for record in (native['executable'],native['version_log'],binary):
        require(record in frozen,'native tool/version/binary omitted or changed in final frozen input set: '+record['path'])


def materialize_task(vectors,destination,task_id,validated):
    require(validated['layer']==task_id,'task vector identity differs')
    target=destination/'layer_00';target.mkdir(parents=True,exist_ok=False)
    files=[]
    for tensor in ('x','w','bias','y'):
        source=vectors/('layer_%02d'%task_id)/(tensor+'.mem')
        original=identity(source)
        require(original['sha256']==validated['sha256'][tensor+'.mem'],'original vector changed')
        local=target/(tensor+'.mem');shutil.copyfile(str(source),str(local));copied=identity(local)
        require(copied['sha256']==original['sha256'],'materialization differs')
        files.append(dict(tensor=tensor,original=original,materialized=copied))
    record=dict(schema='xu-soc-single-task-input-v1',global_task_id=task_id,original_layer='layer_%02d'%task_id,
                simulator_layer='layer_00',mapping='four original tensors copied byte-for-byte; TASKS=1',files=files)
    write_json(destination/'input-manifest.json',record)
    return record


def compile_firmware(ctx,out,prefix):
    main=ctx.soc.TESTS/'firmware/main.c'
    wrapper=out/'xu_clear145_main.c';wrapper.write_text(observer.firmware_wrapper(main,ctx.id))
    target=out/'accel_soc'
    inputs=[identity(p) for p in sorted((ctx.soc.TESTS/'firmware').iterdir()) if p.is_file()]+[identity(wrapper)]
    tools=[]
    for name in ('gcc','objcopy','objdump'):
        executable=shutil.which(prefix+name);require(executable,'tool unavailable: '+prefix+name)
        # Tool paths may be symlinks; bind their resolved executable bytes.
        tools.append(identity(Path(executable).resolve()))
    ctx.soc.run([prefix+'gcc','--version'],out,out/'gcc-version.log')
    command=[prefix+'gcc','-march=rv32imac_zicsr2p0_zifencei2p0','-mabi=ilp32','-O2']+ctx.contract.compiler_defines(ctx.configuration)+[
        '-fstack-usage','-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-nostartfiles','-static',
        '-mcmodel=medany','-Wl,--no-relax','-T',str(ctx.soc.TESTS/'firmware/link.ld'),
        str(ctx.soc.TESTS/'firmware/start.S'),str(wrapper),str(ctx.soc.TESTS/'firmware/accel.c'),'-o',str(target)]
    ctx.soc.run(command,out,out/'firmware-build.log')
    ctx.soc.run([prefix+'objcopy','-O','verilog',str(target),str(target)+'.verilog'],out,out/'objcopy.log')
    image=Path(str(target)+'.verilog');image.write_text(image.read_text().replace('@800','@000'))
    dump=ctx.soc.run([prefix+'objdump','--disassemble-all',str(target)],out,out/'firmware.dump')
    require(re.search(r'80000086\s+<write_tohost>',dump),'completion symbol differs')
    ctx.soc.run([prefix+'objdump','-h',str(target)],out,out/'firmware-sections.log')
    ctx.soc.run([prefix+'objdump','-t',str(target)],out,out/'firmware-symbols.log')
    unchanged(inputs+tools)
    record=dict(configuration=ctx.configuration,command=command,cwd=str(out),inputs=inputs,toolchain=tools,
                compiler_version=identity(out/'gcc-version.log'),frozen_main=identity(main),wrapper=identity(wrapper),
                elf=identity(target),image=identity(image),completion_address='0x80000086')
    write_json(out/'firmware-build.json',record)
    return image,record


def collect_sources(ctx,build,models):
    excluded={'sirv_sim_ram.v','mem_1024x16.sv','mem_128x16.sv','mem_32x40.sv'}
    sources=sorted(p for p in ctx.base.RTL.rglob('*') if p.suffix in ('.v','.sv') and p.name not in excluded)
    required=['xu_sirv_sram_adapter.sv','xu_weight_sram_adapter.sv','xu_shared_icb_sram.sv','xu_soc_ppa_top.sv']
    if ctx.id=='s1_sram_bias':required.append('xu_bias_sram_adapter.sv')
    if ctx.id=='compact32_128':required.append('xu_weight128_sram_adapter.sv')
    sources += [context.ASSETS/name for name in required]+models
    recipe_path=build/'clear-recipe.mem'
    recipe_path.write_text(''.join('%03x%08x\n'%item for item in observer.recipe(ctx.id)))
    tb=build/'tb_xu_profile145.sv';tb.write_text(observer.generate_tb(ctx,recipe_path));sources.append(tb)
    refs=sorted({g['macro_ref'] for g in ctx.candidate['ppa']['memory_groups']})
    probes=build/'xu_probes145.sv';probes.write_text(macro145.render_probes(refs));sources.append(probes)
    return sources,recipe_path,tb,probes


def _one(log,pattern,message):
    found=re.findall(pattern,log,re.M);require(len(found)==1,message)
    return found[0]


def checked_log(ctx,log,task_id):
    failures=re.findall(r'^.*(?:FATAL|TEST_FAIL|%Error|Time Out|timeout|Error-\[).*$',log,re.M|re.I)
    require(not failures,'simulation diagnostic: '+(failures[0] if failures else ''))
    layers=ctx.soc.check_log(log,1)
    parameters=inspect.signature(ctx.soc.check_performance).parameters
    kwargs={'accel_variant':ctx.variant} if 'accel_variant' in parameters else {}
    layers[0]['performance']=ctx.soc.check_performance(log,layers,ctx.schedule,**kwargs)[0]
    extra={}
    for function in ('check_autogroup_activity','check_doublebuf_activity','check_pe_activity'):
        if hasattr(ctx.soc,function):
            method=getattr(ctx.soc,function)
            kwargs={'accel_variant':ctx.variant} if 'accel_variant' in inspect.signature(method).parameters else {}
            extra[function]=method(log,layers,ctx.schedule,**kwargs)
    legacy=ctx.base.check_windows(log,layers)[0]
    lf=_one(log,r'^XU_LF145 nominal_hz=32768 checked_edges=(\d+) max_phase_error_fs=1$','missing LF phase checks')
    require(int(lf)>0,'no LF edge observed')
    request=_one(log,r'^XU_SOURCE_REQUEST145 task=(\d+) cycle=(\d+) tick=(\d+) clear_writes=(\d+) setup_writes=(\d+)$','missing REQUEST')
    accept=_one(log,r'^XU_SOURCE_ACCEPT145 task=(\d+) cycle=(\d+) tick=(\d+)$','missing ACCEPT')
    require(int(request[0])==int(accept[0])==task_id,'global task differs')
    begin=dict(cycle=int(request[1]),tick=int(request[2]))
    accepted=dict(cycle=int(accept[1]),tick=int(accept[2]))
    require(accepted=={k:legacy['begin'][k] for k in ('cycle','tick')},'source accept differs from original TB')
    end={k:legacy['end'][k] for k in ('cycle','tick')}
    elapsed=end['cycle']-begin['cycle'];wait=accepted['cycle']-begin['cycle']
    require(elapsed>=0 and wait>=0 and abs(Fraction(end['tick']-begin['tick'])-Fraction(elapsed*20000000,3))<=1,
            'REQUEST/end physical span differs from nominal150')
    require(abs(Fraction(accepted['tick']-begin['tick'])-Fraction(wait*20000000,3))<=1,'initial wait span differs')
    expected='XU_WINDOW145 task=%d request_cycle=%d accept_cycle=%d end_cycle=%d initial_wait=%d legacy_cycles=%d formal_inclusive=%d formal_elapsed=%d'%(
        task_id,begin['cycle'],accepted['cycle'],end['cycle'],wait,layers[0]['cycles'],elapsed+1,elapsed)
    require(re.findall(r'^XU_WINDOW145.*$',log,re.M)==[expected],'formal inclusive cycle accounting differs')
    for kind,point in (('BEGIN',begin),('END',end)):
        require(re.findall(r'^XU_ACTIVITY_'+kind+r'.*$',log,re.M)==['XU_ACTIVITY_%s task=%d tick=%d'%(kind,task_id,point['tick'])],
                'activity global boundary differs')
    clear_begin=_one(log,r'^XU_CLEAR_BEGIN145 task=(\d+) cycle=(\d+) tick=(\d+)$','missing clear begin')
    clear_end=_one(log,r'^XU_CLEAR_LAST145 task=(\d+) cycle=(\d+) tick=(\d+) writes=(\d+)$','missing clear end')
    require(int(clear_begin[0])==int(clear_end[0])==task_id and int(clear_begin[1])<=int(clear_end[1])<begin['cycle'] and
            int(clear_begin[2])<=int(clear_end[2])<begin['tick'] and int(clear_end[3])==int(request[3])==len(observer.recipe(ctx.id)),
            'clear/REQUEST ordering or count differs')
    manual=ctx.id in ('baseline_h1_h2','s1_h2_only','s1_sram_bias')
    require(int(request[4])==(2 if manual else 0),'pre-source setup count differs')
    reset=_one(log,r'^XU_RESET145 task=(\d+) edges=(\d+) first_tick=(\d+) last_tick=(\d+) ready_cycle=(\d+) ready_tick=(\d+)$','missing actual reset proof')
    require(int(reset[0])==task_id and int(reset[1])>0 and int(reset[2])<=int(reset[3])<int(reset[5])<=int(clear_begin[2]) and
            int(reset[4])<=int(clear_begin[1]),'actual reset readiness ordering differs')
    bias=0 if ctx.id=='s1_h2_only' else 256;xclear=128 if ctx.id=='s2d' else 64
    upload='XU_UPLOAD145 task=%d w=16384 x=6336 bias=%d actual_clear_w=16384 actual_clear_x=%d actual_clear_bias=%d checked_data=1'%(task_id,bias,xclear,bias)
    require(re.findall(r'^XU_UPLOAD145.*$',log,re.M)==[upload],'actual fixture/clear commit proof absent')
    window=dict(begin=begin,end=end,duration_ticks=end['tick']-begin['tick'],timescale_seconds='1e-15',
                interval='first valid input/parameter source REQUEST through final Y response RETIRE; physical [begin,end)',
                formal_elapsed_cycles=elapsed,formal_inclusive_cycles=elapsed+1,first_source_accept=accepted,
                initial_source_wait_cycles=wait,legacy_accept_window=legacy,legacy_task_pass_inclusive_cycles=layers[0]['cycles'],
                pretask_clear=dict(begin=dict(cycle=int(clear_begin[1]),tick=int(clear_begin[2])),
                    last_write=dict(cycle=int(clear_end[1]),tick=int(clear_end[2])),accepted_writes=int(clear_end[3]),
                    task_setup_writes_before_source=int(request[4]),activity_status='outside task SAIF; no clear phase SAIF measured'),
                accelerator_reset_readiness=dict(actual_reset_clock_edges=int(reset[1]),first_reset_tick=int(reset[2]),
                    last_reset_tick=int(reset[3]),first_ready_cycle=int(reset[4]),first_ready_tick=int(reset[5]),actual_reset_pin='ACCEL.rst_n'))
    return layers[0],window,extra


def inspect_activity(ctx,path,window,inventory):
    observed=ctx.reader.read_saif(path)
    require(Decimal(observed['duration_seconds'])==Decimal(window['duration_ticks'])*Decimal('1e-15'),'SAIF duration differs from REQUEST/end')
    prefix=SCOPE.replace('.','/')+'/'
    signals=observed['signals']
    require(all(s['path'].startswith(prefix) for s in signals),'SAIF objects outside DUT')
    clocks=[s for s in signals if s['path']==prefix+'hfextclk']
    edges=Decimal(observed['duration_seconds'])*Decimal(300000000)
    require(clocks and all(abs(Decimal(s['TC'])-edges)<=2 and s['TX']==0 and s.get('TZ',0)==0 for s in clocks),'source clock activity differs')
    coverage={}
    for group,fragment in dict(cpu='/u_e203_cpu_top/',accelerator='/u_accel_icb_slave/',interconnect='/u_e203_biu/',
                               shared='/u_shared/',itcm='/u_e203_itcm_ram/',dtcm='/u_e203_dtcm_ram/').items():
        selected=[s for s in signals if fragment in s['path']]
        require(len(selected)>1,'missing scope '+group)
        toggles=sum(s['TC'] for s in selected)
        require(toggles>0 or group=='dtcm' and ctx.id!='s1_h2_only','scope idle without supported declaration: '+group)
        if not toggles:
            for macro in inventory['macros']:
                if macro['group']!='dtcm':continue
                for pin,level in (('CEN',1),('CLK',0),('RET1N',1)):
                    found=[s for s in signals if s['path']==macro['instance'].replace('.','/')+'/'+pin]
                    require(found and all(s['TC']==s['TX']==s.get('TZ',0)==s.get('TB',0)==0 and s['T%d'%level]==observed['duration_ticks'] for s in found),
                            'DTCM static control differs: '+macro['instance']+'/'+pin)
        coverage[group]=dict(signal_count=len(selected),total_toggles=toggles,
            unknown_bit_ticks=sum(s.get(k,0) for s in selected for k in ('TX','TZ','TB')),
            state='OBSERVED_ACTIVITY' if toggles else 'OBSERVED_KNOWN_STATIC_DISABLED')
    return dict(identity(path),timescale_seconds=observed['timescale_seconds'],duration_ticks=observed['duration_ticks'],
                duration_seconds=observed['duration_seconds'],signal_count=len(signals),scope_presence=coverage,
                source_clock=clocks,mapped_coverage_status='REVIEW_PENDING')


def physical_check(ctx,log,inventory,window):
    macros={m['probe_scope']:m for m in inventory['macros']}
    groups={g['name']:g for g in inventory['memory_groups']}
    clear={};payload={};counts={0:0,1:0}
    pattern=r'^XU_MACRO_WRITE145 ref=(\w+) scope=(\S+) tick_fs=(\d+) stage=(\d+) addr=([0-9a-fA-FxXzZ]+) data=([0-9a-fA-FxXzZ]+) mask=([0-9a-fA-FxXzZ]+)$'
    lines=re.findall(pattern,log,re.M)
    require(len(lines)==len(re.findall(r'^XU_MACRO_WRITE145\b',log,re.M)),'malformed physical macro write')
    for ref,scope,tick,stage,address,data,mask in lines:
        require(scope in macros and macros[scope]['ref_name']==ref,'unlisted physical macro write')
        macro=macros[scope];group=macro['group'];stage=int(stage);tick=int(tick)
        require(group in ('accelerator_weights','accelerator_bias') and stage in (0,1),'physical accelerator write outside clear/payload')
        require(not re.search('[xz]',address+data+mask,re.I),'unknown physical write pin')
        address,data,mask=map(lambda s:int(s,16),(address,data,mask))
        require(mask and mask<=65535 and address<(1<<macro['pin_widths']['A']),'invalid physical write geometry')
        if stage==0:
            require(tick<window['begin']['tick'] and data&mask==0,'nonzero/late physical clear')
        else:require(window['begin']['tick']<=tick<window['end']['tick'],'payload macro write outside formal interval')
        target=clear if stage==0 else payload
        key=(scope,address);old=target.get(key,0)
        require(not old&mask,'duplicate physical byte/bit write')
        target[key]=old|mask;counts[stage]+=1
    coverage={}
    for group in ('accelerator_weights','accelerator_bias'):
        if group not in groups:continue
        members=[m for m in inventory['macros'] if m['group']==group]
        bits=sum(mask.bit_count() if hasattr(mask,'bit_count') else bin(mask).count('1') for (scope,_),mask in clear.items() if macros[scope]['group']==group)
        payload_bits=sum(bin(mask).count('1') for (scope,_),mask in payload.items() if macros[scope]['group']==group)
        require(bits==payload_bits==groups[group]['logical_bits'],'physical logical reachable-bit coverage incomplete: '+group)
        for macro in members:
            addresses={a for (scope,a) in clear if scope==macro['probe_scope']}
            actual_masks={mask for (scope,_),mask in clear.items() if scope==macro['probe_scope']}
            depth=32 if group=='accelerator_bias' else 128 if ctx.id=='compact32_128' else 512 if ctx.id=='pe32' else 256 if ctx.id=='pe64' else 1024
            require(addresses==set(range(depth)),'physical reachable address coverage differs: '+macro['instance'])
            require(actual_masks in ({65535},{255}) and (group=='accelerator_bias' or actual_masks=={65535}),'physical clear mask differs')
            require({(a,mask) for (scope,a),mask in clear.items() if scope==macro['probe_scope']}==
                    {(a,mask) for (scope,a),mask in payload.items() if scope==macro['probe_scope']},'payload physical bits differ from clear coverage')
        coverage[group]=dict(macros=len(members),logical_reachable_bits=bits,clear_observed=True,fresh_payload_observed=True,
                             padding_policy='unreachable SRAM padding is not claimed cleared')
    # Every actual X storage write must have exactly one 1fs-later real storage echo.
    xbuffers={x['probe_scope']:x for x in inventory['x_buffers']}
    events={kind:re.findall(r'^XU_X_'+kind+r'145 scope=(\S+) tick_fs=(\d+) stage=(\d+) addr=(\d+) data=([0-9a-fA-F]+)$',log,re.M)
            for kind in ('WRITE','ECHO')}
    require(len(events['WRITE'])==len(events['ECHO']) and events['WRITE'],'missing X storage echoes')
    xclear={scope:set() for scope in xbuffers};xpayload=[]
    for write,echo in zip(events['WRITE'],events['ECHO']):
        scope,tick,stage,address,data=write
        require(scope in xbuffers and echo[0]==scope and int(echo[1])==int(tick)+1 and echo[2:]==write[2:],'X storage echo differs')
        stage,address,data=int(stage),int(address),int(data,16)
        require(stage in (0,1),'X write after formal end')
        if stage==0:
            require(data==0 and address not in xclear[scope] and int(tick)<window['begin']['tick'],'duplicate/nonzero/late X clear')
            xclear[scope].add(address)
        else:
            require(window['begin']['tick']<=int(tick)<window['end']['tick'],'X payload outside interval')
            xpayload.append((scope,address,data))
    require(all(addresses==set(range(64)) for addresses in xclear.values()) and len(xpayload)==6336,'X actual storage coverage incomplete')
    if ctx.id=='s2d':
        ordered=sorted(xbuffers)
        for index,(scope,address,_) in enumerate(xpayload):
            require(scope==ordered[(index//64)%2] and address==index%64,'DB actual X bank ownership differs')
    return dict(schema='xu-physical-clear145-v1',status='OBSERVED_REVIEW_PENDING_NOT_QUALIFIED',macro_groups=coverage,
                macro_clear_events=counts[0],macro_payload_events=counts[1],x_buffers=len(xbuffers),x_clear_words=64*len(xbuffers),
                x_payload_words=6336,x_storage_echoes=len(events['ECHO']),physical_zero_clear_observed=True,
                all_fixture_commits_inside_window=True,fifo_payload_policy='logical ownership reset; unowned payload storage is not claimed reset')


def run(args):
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    report=dict(schema='xu-profile-activity145-v1',status='RUNNING',qualification='NOT_QUALIFIED',profile=args.profile,
                tasks=[],requested_task_ids=list(range(12)),taskset_complete=False,
                limitations=['RTL activity; no power/energy/timing/contest qualification',
                'ownFM remains conditional; SRAM internal behavior black-boxed',
                'unreachable physical SRAM padding and FIFO payload bits are not claimed cleared'])
    write_json(out/'result.json',report)
    try:
        ctx=context.Context(args.profile,args.source_root)
        adoption=ctx.adoption(args.freeze_receipt,args.adoption_receipt,args.netlist,args.constraints)
        refs={g['macro_ref'] for g in ctx.candidate['ppa']['memory_groups']}
        model_pairs=[('RAMSP1024X16',args.vendor_model1024.resolve())]
        if 'RAMSP128X16' in refs:
            require(args.vendor_model128,'RAMSP128X16 vendor model required for this profile')
            model_pairs.append(('RAMSP128X16',args.vendor_model128.resolve()))
        models=[p for _,p in model_pairs]
        vendor_models=[context.check_vendor_model(ref,model) for ref,model in model_pairs]
        vectors=args.vectors.resolve() if args.vectors else out/'original-vectors'
        fixture_manifest=ctx.soc.TESTS/'vectors/kwt-silence-v1.json'
        fixture_archive=ctx.soc.TESTS/'vectors/kwt-silence-v1.tar.gz'
        fixture=json.loads(fixture_manifest.read_text())
        require(sha(fixture_archive)==fixture['archive_sha256'],'original fixture archive differs')
        if args.vectors is None:
            require(ctx.soc.load_fixture(vectors,12)==fixture,'extracted fixture metadata differs')
        validated=ctx.soc.check_vectors(vectors,12)
        context.check_fixture_manifest(fixture,validated)
        fwdir=out/'firmware';fwdir.mkdir();firmware,fw=compile_firmware(ctx,fwdir,args.cross_prefix)
        build=out/'simulator';build.mkdir()
        sources,recipe_path,tb,probes=collect_sources(ctx,build,models)
        filelist=build/'rtl.f';filelist.write_text('\n'.join(str(p) for p in sources)+'\n')
        defines=[x for x in ctx.candidate['ppa']['defines'] if x!='SYNTHESIS']
        command=ctx.base.build_command('vcs','macro',build,filelist,True,'nominal150')
        command[0]=args.vcs;command.insert(1,'-debug_region+cell')
        for define in defines:
            if '+define+'+define not in command:command.insert(1,'+define+'+define)
        producer=[identity(p) for p in sorted(HERE.glob('*.py'))]+[identity(HERE/name) for name in
                  ('inventory137.snapshot.json','queue-plan138.snapshot.json','assets.sha256.json')]
        config=dict(profile=ctx.id,source_context=ctx.source,source_registry=ctx.candidate['source'],adoption=adoption,
                    source_profile=ctx.candidate['profile'],firmware_configuration=ctx.configuration,
                    schedule=ctx.schedule,physical_variant=ctx.variant,memory_groups=ctx.candidate['ppa']['memory_groups'],
                    nominal_hz=150000000,lf_hz=32768,precision_fs=1,activity_scope=SCOPE,
                    process_policy='fresh process per original task; TASKS=1; source REQUEST/final Y response RETIRE',
                    clear_accepted_writes=len(observer.recipe(ctx.id)),clear_recipe=identity(recipe_path),
                    original_tb=identity(ctx.base.TB),candidate_contract=identity(ctx.contract.__file__),candidate_soc_helper=identity(ctx.soc.__file__),
                    firmware=fw,fixture=fixture,fixture_manifest=identity(fixture_manifest),fixture_archive=identity(fixture_archive),
                    vendor_models=vendor_models,original_task_vectors=validated,rtl_sources=[identity(p) for p in sources],
                    producer_sources=producer,frozen_common_assets=ctx.assets,filelist=identity(filelist),simulator_defines=['ARM_UD_MODEL']+defines,
                    build_command=command,pin_probe=identity(probes))
        if not args.prepare_only:
            executable=shutil.which(args.vcs);require(executable,'VCS unavailable')
            native_executable=identity(Path(executable).resolve())
            ctx.soc.run([args.vcs,'-ID'],build,build/'vcs-version.log',args.build_timeout)
            unchanged([native_executable])
            config['native_compiler']=dict(executable=native_executable,version_log=identity(build/'vcs-version.log'),
                                          version_command=[args.vcs,'-ID'])
        else:config['native_compiler']=None
        report.update(configuration=config,configuration_sha256=context.canonical(config),source_context=ctx.source)
        frozen=config['rtl_sources']+producer+ctx.assets+fw['inputs']+fw['toolchain']+[
            config[k] for k in ('clear_recipe','original_tb','candidate_contract','candidate_soc_helper','filelist','fixture_manifest','fixture_archive')]+[
            fw[k] for k in ('compiler_version','elf','image')]+[identity(args.freeze_receipt),identity(args.adoption_receipt),identity(args.netlist),identity(args.constraints)]
        if config['native_compiler']:
            frozen += [config['native_compiler'][k] for k in ('executable','version_log')]
        tasks=[]
        for task_id in range(12):
            dest=out/('task_%02d'%task_id);dest.mkdir()
            inputs=materialize_task(vectors,dest/'vectors',task_id,validated[task_id]);tasks.append((task_id,dest))
            frozen.append(identity(dest/'vectors/input-manifest.json'))
            frozen += [f[k] for f in inputs['files'] for k in ('original','materialized')]
        ctx.recheck();unchanged(frozen)
        report['inputs_manifest_sha256']=context.canonical(frozen)
        write_json(out/'frozen-inputs.json',frozen);report['frozen_inputs']=identity(out/'frozen-inputs.json')
        write_json(out/'result.json',report)
        if args.prepare_only:
            report['status']='PREPARED_NOT_SIMULATED_NOT_QUALIFIED';write_json(out/'result.json',report);return report
        log=ctx.soc.run(command,build,build/'build.log',args.build_timeout)
        require(not re.search(r'Error-\[|undefined system task|unknown system task',log,re.I),'VCS compile failed')
        binary=build/'soc';report['binary']=identity(binary);frozen.append(report['binary'])
        ctx.recheck();unchanged(frozen)
        check_native_freeze(config,report['binary'],frozen)
        # Persist the final set, including the actual compiler and executable;
        # verification must recheck the same set used around every task.
        write_json(out/'frozen-inputs.json',frozen)
        report['inputs_manifest_sha256']=context.canonical(frozen)
        report['frozen_inputs']=identity(out/'frozen-inputs.json')
        report['build_log']=identity(build/'build.log')
        write_json(out/'result.json',report)
        for task_id,dest in tasks:
            report['current_task_id']=task_id;write_json(out/'result.json',report)
            ctx.recheck();unchanged(frozen)
            argv=[str(binary),'+TESTCASE='+str(firmware),'+VECTORS='+str(dest/'vectors'),'+TASKS=1',
                  '+XU_GLOBAL_TASK='+str(task_id),'+MAX_CYCLES='+str(args.max_cycles),'+DUMPWAVE=0']
            log=ctx.soc.run(argv,dest,dest/'simulation.log',args.run_timeout)
            ctx.recheck();unchanged(frozen)
            layer,window,extra=checked_log(ctx,log,task_id)
            inventory=macro145.parse_inventory(log,config['memory_groups'],expected_x_count=2 if ctx.id=='s2d' else 1)
            write_json(dest/'actual_macro_inventory.json',inventory)
            physical=physical_check(ctx,log,inventory,window)
            normalized=dest/'task-normalized.saif'
            normalization=macro145.normalize(dest/'task.saif',normalized,inventory,ctx.reader,ctx.alias_helpers)
            write_json(dest/'task-normalization.json',normalization)
            saif=inspect_activity(ctx,normalized,window,inventory)
            result=dict(schema='xu-profile-task-activity145-v1',status='COLLECTED_REVIEW_PENDING_NOT_QUALIFIED',qualification='NOT_QUALIFIED',
                        task_id=task_id,profile=ctx.id,configuration_sha256=report['configuration_sha256'],layer=layer,extra_activity=extra,
                        activity_window=window,run_command=argv,input_manifest=identity(dest/'vectors/input-manifest.json'),
                        boundary_log=identity(dest/'simulation.log'),raw_saif=identity(dest/'task.saif'),saif=saif,normalization=normalization,
                        normalization_receipt=identity(dest/'task-normalization.json'),actual_macro_inventory=identity(dest/'actual_macro_inventory.json'),
                        physical_clear=physical)
            ctx.recheck();unchanged(frozen);write_json(dest/'result.json',result)
            report['tasks'].append(result);write_json(out/'result.json',report)
        report.update(status=TERMINAL,taskset_complete=True)
        report.pop('current_task_id',None);ctx.recheck();unchanged(frozen);write_json(out/'result.json',report)
        return report
    except BaseException as exc:
        report.update(status='FAIL_REVIEW_REQUIRED_NOT_QUALIFIED',error=str(exc),error_type=type(exc).__name__)
        write_json(out/'result.json',report)
        (out/'exception.log').write_text(traceback.format_exc())
        raise


def verify_result(activity_root, expected_profile=None, replay_normalization=True):
    """Independently recheck the complete task set and original raw evidence.

    No native tool is started. Normalization replay uses a fresh scratch output;
    original task outputs are never edited or reused as proof of their contents.
    """
    root=Path(activity_root).resolve()
    report=json.loads((root/'result.json').read_text())
    require(report.get('schema')=='xu-profile-activity145-v1' and report.get('status')==TERMINAL,
            'complete 145 terminal receipt required')
    profile=report['profile'];require(expected_profile is None or profile==expected_profile,'activity profile differs')
    require(report.get('taskset_complete') is True and report.get('requested_task_ids')==list(range(12)) and
            [t['task_id'] for t in report.get('tasks',[])]==list(range(12)), 'exactly original task IDs 0..11 required')
    config=report['configuration'];require(context.canonical(config)==report['configuration_sha256'],'configuration hash differs')
    ctx=context.Context(profile,report['source_context']['root'])
    require(ctx.source==report['source_context']==config['source_context'],'source context differs')
    require(config['memory_groups']==ctx.candidate['ppa']['memory_groups'] and config['schedule']==ctx.schedule and
            config['physical_variant']==ctx.variant,'candidate geometry/schedule differs')
    adoption=config['adoption']
    require(ctx.adoption(adoption['freeze']['path'],adoption['own_fm']['path'],adoption['selected_mapped']['path'],
                         adoption['analysis_sdc']['path'])==adoption,'adoption changed')
    require(identity(root/'frozen-inputs.json')==report['frozen_inputs'],'input manifest changed')
    frozen=json.loads((root/'frozen-inputs.json').read_text())
    require(context.canonical(frozen)==report['inputs_manifest_sha256'],'input set hash differs');unchanged(frozen)
    check_native_freeze(config,report['binary'],frozen)
    require(identity(root/'simulator/build.log')==report['build_log'],'native compile log changed')
    require(sha(root/'simulator/soc')==report['binary']['sha256'],'simulator binary changed')
    for expected_id,task in enumerate(report['tasks']):
        directory=root/('task_%02d'%expected_id)
        require(json.loads((directory/'result.json').read_text())==task,'per-task/top-level receipt differs')
        require(task.get('schema')=='xu-profile-task-activity145-v1' and task.get('status')=='COLLECTED_REVIEW_PENDING_NOT_QUALIFIED' and
                task['profile']==profile and task['configuration_sha256']==report['configuration_sha256'],'task identity differs')
        for key in ('input_manifest','boundary_log','raw_saif','normalization_receipt','actual_macro_inventory'):
            item=task[key]
            require(Path(item['path']).resolve().is_relative_to(directory) if hasattr(Path('.'),'is_relative_to') else
                    str(Path(item['path']).resolve()).startswith(str(directory)+'/'),'task evidence path outside task directory')
            require(identity(item['path'])==item,'task evidence changed: '+key)
        log=Path(task['boundary_log']['path']).read_text()
        layer,window,extra=checked_log(ctx,log,expected_id)
        require((layer,window,extra)==(task['layer'],task['activity_window'],task['extra_activity']),'raw task log recomputation differs')
        inventory=macro145.parse_inventory(log,config['memory_groups'],expected_x_count=2 if profile=='s2d' else 1)
        require(inventory==json.loads(Path(task['actual_macro_inventory']['path']).read_text()),'raw elaboration inventory differs')
        require(physical_check(ctx,log,inventory,window)==task['physical_clear'],'physical clear recomputation differs')
        require(inspect_activity(ctx,Path(task['saif']['path']),window,inventory)==task['saif'],'normalized SAIF inspection differs')
        require(json.loads(Path(task['normalization_receipt']['path']).read_text())==task['normalization'],'normalization receipt differs')
        if replay_normalization:
            with tempfile.TemporaryDirectory(prefix='xu145-replay-') as temp:
                replay=macro145.normalize(Path(task['raw_saif']['path']),Path(temp)/'normalized.saif',inventory,ctx.reader,ctx.alias_helpers)
                require(replay['normalized_saif']['sha256']==task['saif']['sha256'],'raw SAIF normalization replay differs')
    ctx.recheck();unchanged(frozen)
    return dict(schema='xu-profile-activity145-verification-v1',status='VERIFIED_12_REVIEW_PENDING_NOT_QUALIFIED',
                profile=profile,activity_result=identity(root/'result.json'),tasks=12,normalization_replayed=replay_normalization,
                selected_mapped=adoption['selected_mapped'],source_context=ctx.source)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='mode');p=sub.add_parser('run')
    p.add_argument('--profile',choices=sorted(context.SCHEDULES),required=True)
    for name in ('source-root','freeze-receipt','adoption-receipt','vendor-model1024','netlist','constraints','out'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--vendor-model128',type=Path);p.add_argument('--vectors',type=Path)
    p.add_argument('--vcs',default='vcs');p.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    p.add_argument('--max-cycles',type=int,default=4000000);p.add_argument('--build-timeout',type=int,default=1800)
    p.add_argument('--run-timeout',type=int,default=7200);p.add_argument('--prepare-only',action='store_true')
    check=sub.add_parser('verify');check.add_argument('--activity-root',type=Path,required=True)
    check.add_argument('--profile',choices=sorted(context.SCHEDULES));check.add_argument('--receipt',type=Path)
    args=parser.parse_args();require(args.mode in ('run','verify'),'choose run or verify')
    if args.mode=='verify':
        result=verify_result(args.activity_root,args.profile)
        if args.receipt:
            require(not args.receipt.exists(),'verification receipt must be new');write_json(args.receipt,result)
        print(json.dumps(result,sort_keys=True));return
    require(min(args.max_cycles,args.build_timeout,args.run_timeout)>0,'positive limits required')
    result=run(args);print(json.dumps(dict(status=result['status'],profile=result['profile'],tasks=len(result['tasks'])),sort_keys=True))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as exc:
        print('FAIL: '+str(exc),file=sys.stderr);sys.exit(1)
