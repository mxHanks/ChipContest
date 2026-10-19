#!/usr/bin/env python3
"""Portable BACKEND3 CPU entry with an explicit current baseline and platform.

The accepted v1 producer and evidence are unchanged. Preflight success is only
input acceptance; CPU functional PASS still requires a complete new native run.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
import run_sram_adapter_soc as S
import sram_soc_baseline as BASE
E,C,PLAN,SYSTEM,SOC,PRIOR=S.E,S.C,S.PLAN,S.SYSTEM,S.SOC,S.PRIOR
FW=S.FW
accept_soc=S.accept_soc
patch_once=S.patch_once
native_saved=S.native_saved
firmware_argv=S.firmware_argv
check_firmware_payload=S.check_firmware_payload
compare_platform_warnings=S.compare_platform_warnings
PLATFORM_MANIFEST=ROOT/'configs/e203-development-platform.json'
COMPLETE='KWT_SRAM_ADAPTER_SOC_V2_COMPLETE'


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=ROOT/'configs/official-sram-package.json')
    p.add_argument('--system-report',type=Path,help='complete same-input BACKEND3 core+ICB report')
    p.add_argument('--baseline-report',type=Path,help='complete locally generated behavioral CPU12 report; no historical default')
    p.add_argument('--platform',type=Path,default=ROOT/'integration/ChipContest/third-party/e203_hbirdv2')
    p.add_argument('--compiler',type=Path,default=ROOT/'.tools/teammate/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc')
    p.add_argument('--objcopy',type=Path,help='defaults to compiler sibling with gcc suffix replaced by objcopy')
    p.add_argument('--preflight-only',action='store_true',help='verify current inputs/prerequisites without building or running HDL')
    p.add_argument('--development-adapter',action='store_true',help='explicit logical fixture, not official macro')
    p.add_argument('--timeout',type=int,default=1800)
    args=p.parse_args(argv)
    platform=args.platform.resolve(); compiler=args.compiler.resolve()
    objcopy=(args.objcopy.resolve() if args.objcopy else compiler.with_name(compiler.name.removesuffix('gcc')+'objcopy'))
    baseline_path=args.baseline_report.resolve() if args.baseline_report else None
    if not 1<=args.timeout<=1800: p.error('timeout must be 1..1800 seconds')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-adapter-soc-v2-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    r={'schema':'kwt-sram-adapter-soc-v2','status':'FAIL','started_utc':E.now(),
       'scope':'development_logical_adapter_open_e203' if args.development_adapter else 'supplied_model_open_e203_functional',
       'official_validation':'NOT_RUN','official_platform':'BLOCKED','official_ppa':'BLOCKED',
       'timing':'NOT_RUN','area':'NOT_RUN','power':'NOT_RUN',
       'configuration':{'backend':3,'tasks':12,'frequency_mhz':150,'jobs':2,'timeout_seconds':args.timeout,
                        'platform':str(platform),'baseline_report':str(baseline_path) if baseline_path else None,
                        'compiler':str(compiler),'objcopy':str(objcopy),'preflight_only':args.preflight_only},
       'commands':[],'runtime_inputs':[],'generated_inputs':[],'firmware':[],'binaries':[],
       'tool_scope':'project Verilator runtime, GCC/objcopy binaries, host make/g++; not a complete compiler/OS image',
       'semantics':'two-state Verilator; inherited fork SVA disabled; procedural scoreboard active'}
    inputs=[Path(__file__),Path(S.__file__),Path(BASE.__file__),PLATFORM_MANIFEST,Path(E.__file__),Path(C.__file__),Path(PLAN.__file__),Path(PRIOR.__file__),
            Path(SYSTEM.__file__),Path(SOC.__file__),Path(SOC.L.__file__),Path(SOC.E.__file__),
            Path(SOC.C.__file__),ROOT/'model/fixed16_acc48.py']
    r['identity']=E.source_identity(inputs,r['configuration'],out/'runner_identity.json')
    def native(argv,name,timeout):
        command=E.run_command(argv,out,out/(name+'.log'),timeout,2)
        r['commands'].append(command)
        E.write_json(out/'result.json',r)
        C.clean_native(command,0)
        text=native_saved(command)
        if PLAN.FAILURE.search(text): raise ValueError('failure diagnostic: '+name)
        return command,text
    try:
        plan=PLAN.plan_inputs(args.manifest,development=args.development_adapter)
        r['plan']={k:v for k,v in plan.items() if k not in ('sources','dependency_paths')}
        r['selected_sources']=list(map(str,plan['sources']))
        inputs += plan['dependency_paths']
        r['identity']=E.source_identity(list(dict.fromkeys(inputs)),r['configuration'],out/'plan_identity.json')
        if plan['status']!='FILES_VERIFIED': r['status']=plan['status']; return finish(r,out)
        if args.system_report is None:
            r.update(status='BLOCKED',error='same-input complete core+ICB report is required before CPU build')
            return finish(r,out)
        prior=PRIOR.verify_system_report(args.system_report,plan,args.manifest,development=args.development_adapter)
        r['system_prerequisite']={k:v for k,v in prior.items() if k!='dependency_paths'}
        inputs += prior['dependency_paths']
        if baseline_path is None:
            r.update(status='BLOCKED',error='explicit locally generated behavioral CPU12 baseline report required; no implicit historical path')
            return finish(r,out)
        baseline=BASE.verify_baseline(baseline_path,platform,platform_manifest=PLATFORM_MANIFEST)
        inputs += [Path(x['path']) for x in baseline['dependencies']]
        r['platform_baseline']=E.record(baseline_path)
        r['platform_sources']=list(map(str,baseline['sources']))
        rtl=platform/'rtl/e203'; core=rtl/'core'; perips=rtl/'perips'
        base=[ROOT/'src/rtl/memory/kwt_sram_1rw.sv',ROOT/'src/rtl/memory/kwt_sram_bank.sv',
              ROOT/'src/rtl/kwt_linear_engine_rowpair_sram.sv',ROOT/'soc/kwt_icb_slave_sram.sv',
              ROOT/'sim/tb_e203_kwt_sram.sv',ROOT/'sim/kwt_shared512_checked_model.sv']
        inputs += [*base,*FW,*plan['sources'],*SYSTEM.tool_inputs(),compiler,objcopy,
                   ROOT/'sim/vectors/kwt-silence-v1/manifest.json']
        r['identity']=E.source_identity(list(dict.fromkeys(path.resolve() for path in inputs)),r['configuration'],out/'source_identity.json')
        r['identity_scope']='original inputs/tools/prerequisite bytes bound before private patches, vector preparation or builds'
        E.verify_records(r['identity']['inputs'])
        if args.preflight_only:
            r.update(status='PASS',phase='preflight-complete',acceptance='PREFLIGHT_ONLY',development_cpu_functional='NOT_RUN',
                     supplied_model_functional='NOT_RUN',preflight_scope='current sources and complete prerequisites only; no tools/HDL executed')
            return finish(r,out)
        replacements={rtl/'subsys/e203_subsys_perips.v':('kwt_icb_slave u_kwt_accel','kwt_icb_slave_sram #(.SRAM_BACKEND(3)) u_kwt_accel'),
                      rtl/'soc/e203_soc_top.v':('kwt_shared512_model u_kwt_shared','kwt_shared512_checked_model u_kwt_shared')}
        generated={}
        for original,(needle,replacement) in replacements.items():
            target=out/original.name
            target.write_text(patch_once(original.read_text(),needle,replacement))
            generated[original]=target; r['generated_inputs'].append(E.record(target))
        sources=[*base,*plan['sources'],*[generated.get(path,path) for path in baseline['sources']]]
        if len(set(sources))!=len(sources): raise ValueError('duplicate compilation source')
        r['compiled_sources']=list(map(str,sources))
        for tool,name in ((ROOT/'.tools/bin/verilator','verilator'),(compiler,'gcc'),(objcopy,'objcopy')):
            native([tool,'--version'],name+'-version',20)
        model=SOC.L.load_module('kwt_adapter_soc_numeric',ROOT/'model/fixed16_acc48.py')
        manifest,provenance,images=SOC.E.validate_export(ROOT/'sim/vectors/kwt-silence-v1',model,source_root=ROOT/'vendor/kwt1-237e4097')
        E.verify_records(r['identity']['inputs']+provenance)
        r['runtime_inputs'] += [E.record(x['path']) for x in provenance]
        r['runtime_inputs'] += SOC.stage_verified_vectors(images,out/'vectors')
        r['workload_sha256']=hashlib.sha256(b''.join(image[k] for image in images for k in ('x','w','bias','y'))).hexdigest()
        r['baseline_workload_sha256']=baseline['workload_sha256']
        r['same_workload_as_baseline']=r['workload_sha256']==baseline['workload_sha256']
        r['cycle_comparison_scope']='same shape/software; workload identity is recorded explicitly, never inferred from equal cycles'
        r['vector_scope']=manifest['input']['kind']
        E.verify_records(r['identity']['inputs']+r['runtime_inputs']+r['generated_inputs'])
        native(firmware_argv(compiler,out),'firmware',60)
        r['firmware'].append(E.record(out/'firmware.elf'))
        E.verify_records(r['firmware'])
        native([objcopy,'-O','binary',out/'firmware.elf',out/'firmware.bin'],'objcopy',60)
        r['firmware'].append(E.record(out/'firmware.bin'))
        E.verify_records(r['firmware'])
        data=(out/'firmware.bin').read_bytes()
        if not data or len(data)>65536: raise ValueError('firmware is empty or exceeds ITCM')
        (out/'firmware.hex').write_text(''.join(f'{byte:02x}\n' for byte in data.ljust(65536,b'\0')))
        r['firmware'].append(E.record(out/'firmware.hex'))
        check_firmware_payload(r['firmware'],baseline['firmware'])
        r['firmware_comparison']='fresh BIN and padded CPU HEX identical; ELF independently bound, non-loadable strings may differ'
        argv=[ROOT/'.tools/bin/verilator','--binary','--timing','--assert','-Wno-fatal','-Wno-PINMISSING','-Wno-PINCONNECTEMPTY',
              '--top-module','tb_e203_kwt_sram','--Mdir',out/'obj','-o','simulation','-j','2','--threads','1',
              '-DDISABLE_SV_ASSERTION=1','-I'+str(core),'-I'+str(perips),'-I'+str(perips/'apb_i2c'),*sources]
        E.verify_records(r['identity']['inputs']+r['generated_inputs']+r['runtime_inputs']+r['firmware'])
        command,text=native(argv,'compile',240)
        r['warning_review']=compare_platform_warnings(text,baseline['compile_text'],out,baseline_path.parent)
        r['binaries'].append(E.record(out/'obj/simulation'))
        r['phase']='cpu-simulation'; r['status']='RUNNING'; E.write_json(out/'result.json',r)
        E.verify_records(r['identity']['inputs']+r['generated_inputs']+r['runtime_inputs']+r['firmware']+r['binaries'])
        command,text=native([out/'obj/simulation',f'+VECTORS={out/"vectors"}',f'+FIRMWARE={out/"firmware.hex"}','+TASKS=12'],'run',args.timeout)
        r.update(accept_soc(command,text,12))
        r.update(status='PASS',phase='complete',development_cpu_functional='PASS',
                 supplied_model_functional='NOT_RUN' if args.development_adapter else 'PASS',
                 measurement_scope='CPU task release through accepted final mailbox response; excludes TB preload and interrupted epochs')
    except FileNotFoundError as exc:r.update(status='BLOCKED',error=str(exc))
    except (OSError,ValueError,KeyError,TypeError) as exc:r.update(status='FAIL',error=type(exc).__name__+': '+str(exc))
    return finish(r,out)


def finish(report,out):
    try:
        E.verify_records(report['identity']['inputs']+report['generated_inputs']+report['runtime_inputs']+report['firmware']+report['binaries'])
        for command in report['commands']: native_saved(command)
    except (OSError,ValueError,KeyError) as exc:report.update(status='FAIL',evidence_error=str(exc))
    report['finished_utc']=E.now(); E.write_json(out/'result.json',report)
    print(COMPLETE)
    print(json.dumps({'status':report['status'],'official_validation':'NOT_RUN','report':str(out/'result.json')}))
    return 0 if report['status']=='PASS' else 2 if report['status']=='BLOCKED' else 1


if __name__=='__main__':raise SystemExit(main())
