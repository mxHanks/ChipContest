#!/usr/bin/env python3
"""Same-input BACKEND=3 CPU replay on the prepared open E203 development fork.

Requires independently revalidated primitive/core/ICB evidence. The physical
macro, official platform and PPA remain unverified. No checkout is patched.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import sram_evidence as E
import run_official_sram_contract as C
import sram_adapter_plan as PLAN
import run_sram_adapter_system as SYSTEM
import run_sram_soc as SOC
import sram_adapter_system_evidence as PRIOR

COMPLETE = 'KWT_SRAM_ADAPTER_SOC_COMPLETE'
BASELINE = ROOT/'artifacts/runs/20261018T025544.222797Z-sram-soc-356e16e2/result.json'
PLATFORM = ROOT/'integration/ChipContest/third-party/e203_hbirdv2'
FW = [ROOT/name for name in ('soc/firmware/start.S', 'soc/firmware/kwt_smoke_sram.c',
                             'soc/firmware/link.ld', 'soc/include/kwt_accel_regs.h')]


def accept_soc(command, text, tasks=12):
    """Reject malformed/extra families and early finish before old arithmetic."""
    C.clean_native(command, 0)
    for family, count in (('PASS E203_SRAM_TASK ', tasks), ('PASS E203_SRAM_RECOVERY ', 1),
                          ('PASS E203_SRAM_SUITE ', 1)):
        if sum(family in line for line in text.splitlines()) != count:
            raise ValueError('extra/missing SoC completion family: '+family)
    if PLAN.FAILURE.search(text): raise ValueError('failure diagnostic in SoC log')
    if len(re.findall(r'^- .*: Verilog \$finish$', text, re.M)) != 1:
        raise ValueError('missing/duplicate native Verilog finish')
    return SOC.validate_soc_log(text, tasks)


def patch_once(text, needle, replacement):
    if text.count(needle) != 1: raise ValueError('prepared platform substitution is not unique: '+needle)
    return text.replace(needle, replacement)


def warning_blocks(text, kind, run):
    # Only the diagnostic and its indented continuation belong to a warning;
    # trailing make/g++ output is a separate native build stage.
    blocks = re.findall(r'^%Warning-'+re.escape(kind)+r':[^\n]*(?:\n[ \t]+[^\n]*)*',text,re.M)
    return [block.rstrip().replace(str(run), '$RUN') for block in blocks]


def compare_platform_warnings(text, baseline_text, run, baseline_run):
    """Grandfather only exact unchanged platform loop/latch diagnostics.

    This is a simulation qualification boundary, not a loop-free/clean-lint
    claim. New loop/latch diagnostics or changed paths fail closed; original RTL is bound.
    """
    result = {}
    for kind in ('UNOPTFLAT', 'LATCH'):
        actual = warning_blocks(text, kind, run)
        before = warning_blocks(baseline_text, kind, baseline_run)
        if not before or actual != before:
            raise ValueError('platform '+kind+' diagnostics differ from frozen baseline')
        result[kind] = {'count': len(actual), 'status': 'UNCHANGED_DEVELOPMENT_LIMITATION',
                        'blocks_sha256': hashlib.sha256('\n'.join(actual).encode()).hexdigest()}
    result['all_warning_counts'] = dict(Counter(re.findall(r'^%Warning-([^:]+):', text, re.M)))
    return result


def native_saved(command):
    text = C.verify_native(command)
    saved = json.loads(Path(command['native_state']['path']).read_text())
    if saved != {k:v for k,v in command.items() if k!='native_state'}:
        raise ValueError('native saved state differs')
    return text


def baseline_inputs():
    """Freeze the existing platform set and warning context, never glob new RTL."""
    r = json.loads(BASELINE.read_text())
    if (r.get('schema') != 'kwt-sram-soc-v2' or r.get('status') != 'PASS' or
        r.get('configuration') != {'tasks':12,'backend':'behavioral','frequency_mhz':150,'jobs':2}):
        raise ValueError('development baseline identity/configuration differs')
    dependencies = PLAN._identity(r['identity'], BASELINE.parent/'source_identity.json')
    if r['identity']['configuration'] != r['configuration'] or len(r['commands']) != 4:
        raise ValueError('baseline native/source configuration differs')
    dependencies.append(E.record(BASELINE))
    for command in r['commands']:
        C.clean_native(command,0); native_saved(command)
        dependencies += [command['log'],command['native_state']]
    accept_soc(r['commands'][-1], native_saved(r['commands'][-1]), 12)
    # Old additional labels do not replace SHA/size checks.
    for item in r['inputs'] + r['vector_provenance']:
        actual = E.record(item['path'])
        if actual['sha256'] != item['sha256'] or actual['size_bytes'] != item.get('size_bytes',item.get('bytes')):
            raise ValueError('baseline consumed bytes differ: '+item['path'])
        dependencies.append(actual)
    rtl = PLATFORM/'rtl/e203'
    sources = sorted(Path(item['path']) for item in r['identity']['inputs']
                     if Path(item['path']).is_relative_to(rtl) and Path(item['path']).suffix=='.v')
    if len(sources)!=136 or len(set(sources))!=136:
        raise ValueError('baseline platform file set differs')
    lookup = {item['path']:item for item in r['identity']['inputs']}
    for path in FW:
        if lookup.get(str(path)) != E.record(path): raise ValueError('firmware source differs from baseline')
    # Include directives in this fork use .v headers already in the explicit set.
    # Any newly added local include must be reviewed rather than silently read.
    names = {p.name for p in sources}
    for path in sources:
        for include in re.findall(r'^\s*`include\s+"([^"]+)"',path.read_text(),re.M):
            if '/' in include or include not in names:
                raise ValueError('unbound platform include: '+include)
    return {'dependencies':PLAN._merge(dependencies), 'sources':sources,
            'compile_text':native_saved(r['commands'][2]), 'firmware':r['firmware']}


def firmware_argv(compiler, out):
    return [str(compiler),'-march=rv32imac_zicsr_zifencei','-mabi=ilp32','-msmall-data-limit=0','-Os',
            '-ffreestanding','-fno-builtin','-nostdlib','-Wl,--build-id=none','-DKWT_TASKS=12',
            '-I'+str(ROOT/'soc/include'),'-T',str(FW[2]),str(FW[0]),str(FW[1]),'-o',str(out/'firmware.elf')]


def check_firmware_payload(firmware, baseline):
    # ELF retains its own complete identity. GCC's random temporary object name
    # may change its non-loadable string table. The actual CPU consumes HEX;
    # fresh objcopy BIN and exact padded HEX must match the accepted payload.
    if len(firmware)!=3 or len(baseline)!=3:raise ValueError('firmware artifact set incomplete')
    for index,name in ((1,'firmware.bin'),(2,'firmware.hex')):
        item,before=firmware[index],baseline[index]
        if Path(item['path']).name!=name or Path(before['path']).name!=name or (
            item['sha256'],item['size_bytes']) != (before['sha256'],before['size_bytes']):
            raise ValueError('rebuilt CPU payload differs from accepted firmware: '+name)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=ROOT/'configs/official-sram-package.json')
    p.add_argument('--system-report',type=Path,help='complete same-input BACKEND3 core+ICB report')
    p.add_argument('--development-adapter',action='store_true',help='explicit logical fixture, not official macro')
    p.add_argument('--timeout',type=int,default=1800)
    args=p.parse_args(argv)
    if not 1<=args.timeout<=1800: p.error('timeout must be 1..1800 seconds')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-adapter-soc-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    r={'schema':'kwt-sram-adapter-soc-v1','status':'FAIL','started_utc':E.now(),
       'scope':'development_logical_adapter_open_e203' if args.development_adapter else 'supplied_model_open_e203_functional',
       'official_validation':'NOT_RUN','official_platform':'BLOCKED','official_ppa':'BLOCKED',
       'timing':'NOT_RUN','area':'NOT_RUN','power':'NOT_RUN',
       'configuration':{'backend':3,'tasks':12,'frequency_mhz':150,'jobs':2,'timeout_seconds':args.timeout},
       'commands':[],'runtime_inputs':[],'generated_inputs':[],'firmware':[],'binaries':[],
       'tool_scope':'project Verilator runtime, GCC/objcopy binaries, host make/g++; not a complete compiler/OS image',
       'semantics':'two-state Verilator; inherited fork SVA disabled; procedural scoreboard active'}
    inputs=[Path(__file__),Path(E.__file__),Path(C.__file__),Path(PLAN.__file__),Path(PRIOR.__file__),
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
        baseline=baseline_inputs(); inputs += [Path(x['path']) for x in baseline['dependencies']]
        r['platform_baseline']=E.record(BASELINE)
        r['platform_sources']=list(map(str,baseline['sources']))
        rtl=PLATFORM/'rtl/e203'; core=rtl/'core'; perips=rtl/'perips'
        base=[ROOT/'src/rtl/memory/kwt_sram_1rw.sv',ROOT/'src/rtl/memory/kwt_sram_bank.sv',
              ROOT/'src/rtl/kwt_linear_engine_rowpair_sram.sv',ROOT/'soc/kwt_icb_slave_sram.sv',
              ROOT/'sim/tb_e203_kwt_sram.sv',ROOT/'sim/kwt_shared512_checked_model.sv']
        compiler=ROOT/'.tools/teammate/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc'
        objcopy=compiler.with_name('riscv-none-elf-objcopy')
        inputs += [*base,*FW,*plan['sources'],*SYSTEM.tool_inputs(),compiler,objcopy,
                   ROOT/'sim/vectors/kwt-silence-v1/manifest.json']
        r['identity']=E.source_identity(list(dict.fromkeys(path.resolve() for path in inputs)),r['configuration'],out/'source_identity.json')
        r['identity_scope']='original inputs/tools/prerequisite bytes bound before private patches, vector preparation or builds'
        E.verify_records(r['identity']['inputs'])
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
        r['warning_review']=compare_platform_warnings(text,baseline['compile_text'],out,BASELINE.parent)
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
