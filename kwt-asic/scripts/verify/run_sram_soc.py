#!/usr/bin/env python3
"""Build firmware and replay the SRAM-backed engine on the prepared open E203 fork.

Only two generated source copies are rebound; no E203 checkout is modified.
This is development integration, not the committee platform or physical SRAM.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import run_linear as L
import run_exported_linear as E
import sram_evidence as NATIVE
import sram_sources as SOURCES
C = L.COMMON


def stage_verified_vectors(images, target):
    """Replay exactly validate_export's bytes, independent of manifest paths."""
    target=Path(target)
    target.mkdir(parents=True,exist_ok=False)
    records=[]
    for layer,image in enumerate(images):
        directory=target/f'layer_{layer:02d}'
        directory.mkdir()
        for key in ('x','w','bias','y'):
            payload=image[key]
            if not isinstance(payload,bytes) or not payload:
                raise ValueError('verified image bytes missing: '+key)
            path=directory/(key+'.mem')
            path.write_bytes(payload)
            records.append(NATIVE.record(path))
    return records


def validate_soc_log(log, tasks):
    keys=('task','outputs','load_commits','start','first_config','first_x','last_write_rsp','ack_rsp','end',
          'window_cycles','core_cycles','output_write_responses','ack_responses')
    pattern=r'^PASS E203_SRAM_TASK '+' '.join(k+r'=(\d+)' for k in keys)+r'$'
    matches=re.findall(pattern,log,re.M)
    if len(matches)!=tasks:raise ValueError('missing or duplicate complete SoC tasks')
    measured=[dict(zip(keys,map(int,x))) for x in matches]
    previous_end=-1
    for i,x in enumerate(measured):
        if (x['task']!=i or x['outputs']!=25344 or x['load_commits']!=22976 or
            x['output_write_responses']!=50688 or x['ack_responses']!=1):
            raise ValueError('SoC load/output/response conservation mismatch')
        if not (previous_end<x['start']<=x['first_config']<=x['first_x']<x['last_write_rsp']<x['ack_rsp']<x['end']):
            raise ValueError('SoC task configuration/writeback/ACK response ordering mismatch')
        if x['window_cycles']!=x['end']-x['start']+1 or not 0<x['core_cycles']<=x['window_cycles']:
            raise ValueError('SoC development window arithmetic mismatch')
        previous_end=x['end']
    recovery=re.findall(r'^PASS E203_SRAM_RECOVERY soft_aborts=1 hard_resets=1 pending_response_reset=1$',log,re.M)
    suite=re.findall(r'^PASS E203_SRAM_SUITE tasks=(\d+) outputs=(\d+) development_window_cycles=(\d+) platform=open_fork_development$',log,re.M)
    if len(recovery)!=1 or len(suite)!=1:raise ValueError('missing/duplicate recovery or complete suite marker')
    total=sum(x['window_cycles'] for x in measured)
    if list(map(int,suite[0]))!=[tasks,tasks*25344,total]:raise ValueError('SoC suite totals mismatch')
    return {'per_task':measured,'development_window_cycles':total,'outputs':tasks*25344,
            'recovery':{'soft_aborts':1,'hard_resets':1,'pending_response_reset':1}}


def accept_soc_command(command, tasks, inputs=()):
    NATIVE.verify_records(inputs)
    error=NATIVE.completion_error(command,[])
    if error:raise ValueError('SoC native execution rejected: '+error)
    return validate_soc_log(Path(command['log']['path']).read_text(),tasks)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform', type=Path, default=ROOT/'integration/ChipContest/third-party/e203_hbirdv2')
    p.add_argument('--vectors-dir', type=Path, default=ROOT/'sim/vectors/kwt-silence-v1')
    p.add_argument('--tasks', type=int, choices=range(1,13), default=2)
    p.add_argument('--backend', choices=('behavioral','ff'), default='behavioral')
    p.add_argument('--timeout', type=int, default=1800)
    a = p.parse_args()
    if a.timeout <= 0: p.error('timeout must be positive')
    out=ROOT/'artifacts/runs'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-sram-soc-'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True,exist_ok=False)
    r={'schema':'kwt-sram-soc-v2','status':'RUNNING','scope':'open E203 fork development integration; no official physical/PPA acceptance',
       'configuration':{'tasks':a.tasks,'backend':a.backend,'frequency_mhz':150,'jobs':2},
       'official_platform':'BLOCKED','timing':'BLOCKED','area':'BLOCKED','power':'BLOCKED','inputs':[],'commands':[]}
    try:
        backend=SOURCES.select_backend(a.backend,'simulation')
        rtl=a.platform.resolve()/'rtl/e203'
        core=rtl/'core'; perips=rtl/'perips'
        # Deliberately scoped to the prepared E203 tree; never vendor/FPT.
        platform_sources=sorted(rtl.rglob('*.v'))
        original_perips=rtl/'subsys/e203_subsys_perips.v'
        original_soc=rtl/'soc/e203_soc_top.v'
        if not platform_sources or not original_perips.is_file():
            raise FileNotFoundError('prepared E203 fusion copy missing; see docs/integration/FUSION_RUN.md')
        text=original_perips.read_text()
        needle='kwt_icb_slave u_kwt_accel'
        if text.count(needle)!=1: raise ValueError('prepared o15 source identity differs')
        patched_perips=out/'e203_subsys_perips.v'
        text=text.replace(needle,f"kwt_icb_slave_sram #(.SRAM_BACKEND({backend['value']})) u_kwt_accel")
        patched_perips.write_text(text)
        text=original_soc.read_text()
        if text.count('kwt_shared512_model u_kwt_shared')!=1: raise ValueError('prepared shared source differs')
        patched_soc=out/'e203_soc_top.v'
        patched_soc.write_text(text.replace('kwt_shared512_model u_kwt_shared','kwt_shared512_checked_model u_kwt_shared'))
        sources=[*backend['sources'],ROOT/'sim/tb_e203_kwt_sram.sv', ROOT/'sim/kwt_shared512_checked_model.sv', ROOT/'soc/kwt_icb_slave_sram.sv']
        sources += [patched_perips if f==original_perips else patched_soc if f==original_soc else f for f in platform_sources]
        fw=[ROOT/'soc/firmware/start.S',ROOT/'soc/firmware/kwt_smoke_sram.c',ROOT/'soc/firmware/link.ld',ROOT/'soc/include/kwt_accel_regs.h']
        dependencies=[Path(__file__),Path(L.__file__),Path(E.__file__),Path(C.__file__),ROOT/'model/fixed16_acc48.py',*sources,*fw,original_perips,original_soc,*sorted(core.glob('*.vh'))]
        dependencies+=[Path(NATIVE.__file__),*backend['dependencies']]
        r['identity']=NATIVE.source_identity(list(dict.fromkeys(dependencies)),r['configuration'],out/'source_identity.json')
        r['inputs']=r['identity']['inputs'][:]
        model=L.load_module('kwt_sram_soc_numeric',ROOT/'model/fixed16_acc48.py')
        manifest,provenance,images=E.validate_export(a.vectors_dir.resolve(),model,source_root=ROOT/'vendor/kwt1-237e4097')
        r['vector_provenance']=provenance
        r['vector_scope']=manifest['input']['kind']
        r['workload_sha256']=hashlib.sha256(b''.join(image[k] for image in images[:a.tasks] for k in ('x','w','bias','y'))).hexdigest()
        r['inputs']+=stage_verified_vectors(images[:a.tasks],out/'vectors')
        compiler=ROOT/'.tools/teammate/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc'
        objcopy=compiler.with_name('riscv-none-elf-objcopy')
        if not compiler.is_file():
            found=shutil.which('riscv64-unknown-elf-gcc') or shutil.which('riscv-none-elf-gcc')
            if not found: raise FileNotFoundError('RISC-V bare-metal compiler missing')
            compiler=Path(found); objcopy=compiler.with_name(compiler.name.replace('gcc','objcopy'))
        r['tools']={name:C.tool_info(str(tool),out,2) for name,tool in [('gcc',compiler),('objcopy',objcopy),('verilator','verilator')]}
        r['inputs'] += [L.file_record(compiler),L.file_record(objcopy)]
        NATIVE.write_json(out/'result.json',r)
        commands=[([str(compiler),'-march=rv32imac_zicsr_zifencei','-mabi=ilp32','-msmall-data-limit=0','-Os','-ffreestanding','-fno-builtin','-nostdlib',
                     '-Wl,--build-id=none',f'-DKWT_TASKS={a.tasks}','-I'+str(ROOT/'soc/include'),'-T',str(fw[2]),str(fw[0]),str(fw[1]),'-o',str(out/'firmware.elf')],'firmware.log',60),
                  ([str(objcopy),'-O','binary',str(out/'firmware.elf'),str(out/'firmware.bin')],'objcopy.log',60)]
        for argv,log,timeout in commands:
            cmd=NATIVE.run_command(argv,out,out/log,timeout,2);r['commands'].append(cmd)
            if cmd['exit_code'] or cmd['timed_out'] or cmd['interrupted']: raise ValueError('firmware build failed')
        data=(out/'firmware.bin').read_bytes()
        if len(data)>65536: raise ValueError('firmware exceeds ITCM')
        (out/'firmware.hex').write_text(''.join(f'{b:02x}\n' for b in data.ljust(65536,b'\0')))
        compile_argv=['verilator','--binary','--timing','--assert','-Wno-fatal','-Wno-PINMISSING','-Wno-PINCONNECTEMPTY',
                      '--top-module','tb_e203_kwt_sram','--Mdir',str(out/'obj'),'-o','simulation','-j','2','--threads','1','-DDISABLE_SV_ASSERTION=1',
                      '-I'+str(core),'-I'+str(perips),'-I'+str(perips/'apb_i2c'),*map(str,sources)]
        cmd=NATIVE.run_command(compile_argv,out,out/'compile.log',240,2);r['commands'].append(cmd)
        if cmd['exit_code'] or cmd['timed_out'] or cmd['interrupted']: raise ValueError('SoC compile failed')
        r['firmware']=[L.file_record(out/name) for name in ('firmware.elf','firmware.bin','firmware.hex')]
        r['simulation']=L.file_record(out/'obj/simulation')
        r['inputs'] += [*r['firmware'],r['simulation']]
        r['phase']='simulation';NATIVE.write_json(out/'result.json',r)
        argv=[str(out/'obj/simulation'),f'+VECTORS={out/"vectors"}',f'+FIRMWARE={out/"firmware.hex"}',f'+TASKS={a.tasks}']
        cmd=NATIVE.run_command(argv,out,out/'run.log',a.timeout,2);r['commands'].append(cmd)
        measured=accept_soc_command(cmd,a.tasks,r['inputs'])
        r.update(status='PASS',phase='complete',**measured,
                 measurement_scope='CPU task release through final accepted mailbox response; excludes TB backdoor preload and aborted epochs')
    except FileNotFoundError as exc:
        r.update(status='BLOCKED',error=str(exc))
    except Exception as exc:
        r.update(status='FAIL',error=f'{type(exc).__name__}: {exc}')
    finally:
        try:NATIVE.verify_records(r['inputs']+r.get('vector_provenance',[]))
        except (ValueError,OSError) as exc:r.update(status='FAIL',error=str(exc))
        NATIVE.write_json(out/'result.json',r)
    print(json.dumps({'status':r['status'],'report':str(out/'result.json'),'error':r.get('error')}))
    return {'PASS':0,'FAIL':1,'BLOCKED':2}[r['status']]


if __name__=='__main__': raise SystemExit(main())
