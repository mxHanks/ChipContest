#!/usr/bin/env python3
"""Frozen-source real-CPU checks for the independent peripheral DMA candidate.

Each invocation writes a new evidence directory. The simulator compiles copied
RTL, never live files; original baseline tests and install caches stay intact.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
E203 = ROOT / 'third-party/e203_hbirdv2'
TESTS = ROOT / 'tests/e203'
DEADLINE = '2026-11-09T23:59:00+08:00'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def run(command, cwd: Path, logfile: Path, timeout=3600):
    command = [str(x) for x in command]
    with logfile.open('w') as log:
        log.write(json.dumps(dict(command=command, cwd=str(cwd))) + '\n')
        log.flush()
        result = subprocess.run(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT,
                                env=dict(os.environ, PWD=str(cwd)), timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'command exit {result.returncode}: {logfile}')
    return logfile.read_text(errors='replace').split('\n', 1)[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_identity(directory: Path):
    def get(*args):
        return subprocess.check_output(['git', *args], cwd=directory, text=True).strip()
    return dict(head=get('rev-parse', 'HEAD'), branch=get('branch', '--show-current'),
                status=get('status', '--short'), diff_sha256=hashlib.sha256(
                    subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=directory)).hexdigest())


def compile_firmware(source: Path, out: Path, prefix: str):
    out.mkdir()
    target = out / 'dma_day_soc'
    command = [prefix+'gcc', '-march=rv32imac_zicsr2p0_zifencei2p0', '-mabi=ilp32',
               '-O2', '-fstack-usage', '-ffreestanding', '-fno-builtin',
               '-msmall-data-limit=0', '-nostdlib', '-nostartfiles', '-static',
               '-mcmodel=medany', '-Wl,--no-relax', '-Wl,--build-id=none',
               '-T', source/'firmware/link.ld', source/'firmware/start.S',
               source/'dma_day_main.c', '-o', target]
    run(command, out, out/'build.log')
    run([prefix+'objcopy', '-O', 'verilog', target, str(target)+'.verilog'], out, out/'objcopy.log')
    image = Path(str(target)+'.verilog')
    image.write_text(image.read_text().replace('@800', '@000'))
    dump = run([prefix+'objdump', '--disassemble-all', target], out, out/'disassembly.log')
    if not re.search(r'80000086\s+<write_tohost>', dump):
        raise ValueError('firmware completion symbol moved')
    if len(re.findall(r'\bfence\b', dump)) < 2:
        raise ValueError('firmware lacks submission/completion fences')
    sections = run([prefix+'objdump', '-h', target], out, out/'sections.log')
    if re.search(r'^\s*\d+\s+\.data\s+0*[1-9a-f]', sections, re.M):
        raise ValueError('startup does not initialize .data')
    return dict(elf=str(target), elf_sha256=sha(target), image_sha256=sha(image),
                command=[str(x) for x in command],
                source_sha256={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
                stack_usage={p.name:p.read_text() for p in sorted(out.glob('*.su'))})


def read_signed(path: Path, bits: int, count: int):
    words = path.read_text().split()
    if len(words) != count or any(not re.fullmatch('[0-9a-fA-F]{%d}' % (bits//4), x) for x in words):
        raise ValueError(f'invalid vector {path}')
    result=[]
    for word in words:
        value=int(word,16)
        result.append(value-(1<<bits) if value & (1<<(bits-1)) else value)
    return result


def check_vectors(directory: Path, tasks: int):
    """Independent integer MAC and RNE check. Reference never enters DUT paths."""
    result=[]
    for layer in range(tasks):
        folder=directory/f'layer_{layer:02d}'
        x=read_signed(folder/'x.mem',16,6336)
        w=read_signed(folder/'w.mem',16,16384)
        b=read_signed(folder/'bias.mem',40,256)
        raw=read_signed(folder/'y.mem',48,25344)
        y=read_signed(folder/'y32.mem',32,25344)
        for row in range(99):
            for col in range(256):
                i=row*256+col
                value=b[col]+sum(x[row*64+k]*w[k*256+col] for k in range(64))
                q,r=divmod(value,512)
                q += int(r>256 or (r==256 and q&1))
                if raw[i] != value or y[i] != q:
                    raise ValueError(f'independent golden mismatch layer={layer} row={row} col={col}')
        result.append(dict(layer=layer, outputs=25344,
                           sha256={p.name:sha(p) for p in sorted(folder.glob('*.mem'))}))
    return result


def parse_records(log: str, marker: str, fields):
    pattern=r'^'+marker+' '+r' '.join(x+r'=(\d+)' for x in fields)+r'$'
    records=[dict(zip(fields,map(int,row))) for row in re.findall(pattern,log,re.M)]
    if len(records) != len(re.findall(r'^'+marker+r'\b',log,re.M)):
        raise ValueError(f'malformed {marker} record')
    return records


def check_records(log: str, tasks: int, dual: int, prefix="DMA"):
    if re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout|^Error(?:\s|:)',log,re.I|re.M):
        raise ValueError('simulation contains a failure marker')
    fields=['layer','dual','outputs','payload','clear','principal','gap','including_gap','firmware_cycles','start_to_done']
    layers=parse_records(log,prefix+'_TASK_PASS',fields)
    windows=parse_records(log,prefix+'_WINDOW',['layer','first_request','endpoint_request','first_accept','last_y_response','clear_request','clear_done','start','done'])
    counts=parse_records(log,prefix+'_COUNTS',['layer','reads','w_reads','bias_reads','x_reads','writes','write_responses','requests','responses','pops','macs','mmio_reads','mmio_writes'])
    channels=parse_records(log,prefix+'_CHANNEL',['layer','wb_cycles','xy_window','endpoint_stall','dma_stall','source_stall','write_stall','accept_interval_sum','accept_intervals','max_accept_interval','response_latency_sum','max_response_latency','max_outstanding'])
    if any(len(records)!=tasks for records in [layers,windows,counts,channels]):
        raise ValueError('missing or duplicate layer evidence')
    for i,(item,window,count,channel) in enumerate(zip(layers,windows,counts,channels)):
        if any(record['layer']!=i for record in [item,window,count,channel]):
            raise ValueError('unordered layers')
        if item['dual']!=dual or item['outputs']!=25344:
            raise ValueError('mode or output scope mismatch')
        if item['payload']!=window['last_y_response']-window['first_request']+1:
            raise ValueError('payload timing boundary mismatch')
        if item['clear']!=window['clear_done']-window['clear_request']+1:
            raise ValueError('clear timing boundary mismatch')
        if item['principal']!=item['payload']+item['clear']:
            raise ValueError('principal sum mismatch')
        if item['gap']!=window['first_request']-window['clear_done']-1:
            raise ValueError('gap timing boundary mismatch')
        if item['including_gap']!=item['principal']+item['gap']:
            raise ValueError('gap sum mismatch')
        if not (window['clear_request']<=window['clear_done']<window['start']<=window['first_request']<=window['endpoint_request']<=window['first_accept']<=window['last_y_response']<window['done']):
            raise ValueError('incorrect clear/payload/completion order')
        expected=dict(reads=15040,w_reads=8192,bias_reads=512,x_reads=6336,writes=25344,
                      write_responses=25344,requests=40384,responses=40384,pops=3168,
                      macs=102400 if dual else 202752)
        if any(count[k]!=v for k,v in expected.items()):
            raise ValueError('transaction/computation counts differ')
        if channel['max_outstanding']!=1:
            raise ValueError('shared endpoint outstanding configuration changed')
        item.update(window=window,counters=count,channel=channel,task_per_second_at_150mhz=150000000/item['principal'],including_gap_task_per_second_at_150mhz=150000000/item['including_gap'])
    principal=sum(x['principal'] for x in layers)
    including_gap=sum(x['including_gap'] for x in layers)
    return dict(layers=layers,outputs=tasks*25344,principal_cycles=principal,
                payload_cycles=sum(x['payload'] for x in layers),
                clear_cycles=sum(x['clear'] for x in layers),gap_cycles=sum(x['gap'] for x in layers),
                including_gap_cycles=including_gap,
                task_per_second_at_150mhz=150000000*tasks/principal,
                including_gap_task_per_second_at_150mhz=150000000*tasks/including_gap,
                full12_performance_target_met=tasks==12 and principal<=1800000)


def check_log(log: str, tasks: int, dual: int, warmup: bool=False):
    result=check_records(log,tasks,dual)
    end=f'DMA_SOC_PASS tasks={tasks} dual={dual} outputs={tasks*25344} writes={tasks*25344}'
    if re.findall(r'^DMA_SOC_PASS.*$',log,re.M)!=[end]:
        raise ValueError('missing complete real-CPU result')
    if re.findall(r'^DMA_STARTUP external_double_reset=1 held_ns=120\.000000 clock_period_fs=6666666$',log,re.M)==[]:
        raise ValueError('external reset/clock identity absent')
    clocks=parse_records(log,'DMA_CLOCK',['measured_hf_period_fs','measured_lf_period_fs','hf_edges','lf_edges'])
    if len(clocks)!=1 or clocks[0]['measured_hf_period_fs']!=6666666 or clocks[0]['measured_lf_period_fs']!=30517578126 or clocks[0]['hf_edges']<2 or clocks[0]['lf_edges']<2:
        raise ValueError('measured clock identity differs')
    result['measured_clock']=clocks[0]
    if warmup:
        result['warmup']=check_records(log,1,dual,'DMA_WARMUP')
        result['warmup']['scope']='public fulltask0 preconditioning; checked but excluded from counted principal'
        if re.findall(r'^DMA_WARMUP_DONE.*$',log,re.M)!=['DMA_WARMUP_DONE tasks=1 outputs=25344 excluded_principal=1']:
            raise ValueError('missing verified public warmup')
    elif re.search(r'^DMA_WARMUP',log,re.M):
        raise ValueError('unexpected warmup')
    return result


def check_physical_clear(log: str, tasks: int, warmup: bool):
    starts=parse_records(log,'DMA_PHYSICAL_CLEAR_BEGIN',['call','warmup','nonzero_W','nonzero_BIAS','nonzero_X','observed_last_public_writes'])
    ends=parse_records(log,'DMA_PHYSICAL_CLEAR_PASS',['call','warmup','W','BIAS','X','total16bit_writes','physical_cycles','X_REGS','ACC','ENGINE_RESULT','FIFO','BIAS_CACHE','DMA_SNAPSHOT','all_addresses','all_payload_zero'])
    if len(starts)!=tasks+int(warmup) or len(ends)!=len(starts):
        raise ValueError('missing or duplicate physical clear proof')
    for i,(start,end) in enumerate(zip(starts,ends)):
        expected_warmup=int(warmup and i==0)
        if start['call']!=i+1 or end['call']!=i+1 or start['warmup']!=expected_warmup or end['warmup']!=expected_warmup:
            raise ValueError('physical clear task ownership mismatch')
        expected=dict(W=16384,BIAS=768,X=256,total16bit_writes=17408,X_REGS=256,ACC=16,
                      ENGINE_RESULT=16,FIFO=32,BIAS_CACHE=16,DMA_SNAPSHOT=1,all_addresses=1,all_payload_zero=1)
        if any(end[k]!=v for k,v in expected.items()) or start['observed_last_public_writes']!=1:
            raise ValueError('physical address/payload coverage differs')
        if i>0 and any(start[k]<=0 for k in ['nonzero_W','nonzero_BIAS','nonzero_X']):
            raise ValueError('counted clear lacks publicly produced dirty state')
        end['dirty_before']=start
    return ends


def snapshot_sources(out: Path, generated: list[Path], extras: list[Path], observer: Path|None):
    source=out/'source';source.mkdir()
    rtl=source/'rtl';shutil.copytree(E203/'rtl/e203',rtl)
    tests=source/'tests';tests.mkdir()
    shutil.copy2(TESTS/'tb_dma_day_soc.sv',tests/'tb_dma_day_soc.sv')
    firmware=tests/'firmware';firmware.mkdir()
    for name in ['start.S','link.ld']:
        shutil.copy2(TESTS/'firmware'/name,firmware/name)
    shutil.copy2(TESTS/'dma_day_main.c',tests/'dma_day_main.c')
    shutil.copy2(Path(__file__),source/'run_soc.py')
    overrides=[]
    for directory in generated:
        for path in sorted(directory.rglob('*')):
            if path.suffix not in ['.v','.sv','.vh','.svh'] or not path.is_file(): continue
            same=list(rtl.rglob(path.name))
            if len(same)>1: raise ValueError(f'ambiguous generated source {path.name}')
            destination=same[0] if same else rtl/'perips'/path.name
            if destination.exists(): overrides.append(dict(path=str(destination.relative_to(source)),old_sha256=sha(destination),new_sha256=sha(path),origin=str(path)))
            shutil.copy2(path,destination)
    for path in extras:
        destination=rtl/'perips'/path.name
        if destination.exists(): raise ValueError(f'extra source already exists: {destination}')
        shutil.copy2(path,destination)
    if observer:
        target=tests/'dma_physical_observer.svh';shutil.copy2(observer,target)
        tb=tests/'tb_dma_day_soc.sv'
        text=tb.read_text()
        text=text.replace('\nendmodule\n','\n`include "dma_physical_observer.svh"\nendmodule\n')
        tb.write_text(text)
    manifest={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    write_json(out/'source-manifest.json',dict(files=manifest,overrides=overrides))
    return source,manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--tasks',type=int,default=1)
    parser.add_argument('--dual',type=int,choices=[0,1],default=1)
    parser.add_argument('--generated-dir',type=Path,action='append',default=[])
    parser.add_argument('--extra-source',type=Path,action='append',default=[])
    parser.add_argument('--observer',type=Path)
    parser.add_argument('--replay-from',type=Path,help='reuse a completed PASS snapshot, firmware, and exact simulator binary')
    parser.add_argument('--vectors',type=Path,help='frozen extracted legacy vectors (all12 identity checked)')
    parser.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    parser.add_argument('--sim',choices=['verilator','iverilog'],default='verilator')
    parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--throttle',type=int,default=7)
    parser.add_argument('--first-source-stall',type=int,default=0)
    parser.add_argument('--max-cycles',type=int,default=20000000)
    parser.add_argument('--waves',action='store_true')
    parser.add_argument('--warmup',action='store_true',help='check one public task0 before counted task0; all counted clears then have prior task state')
    parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--firmware-only',action='store_true')
    parser.add_argument('--deadline',default=DEADLINE)
    args=parser.parse_args(argv)
    if not 1<=args.tasks<=12: parser.error('tasks must be1..12')
    if args.replay_from and (args.generated_dir or args.extra_source or args.observer or args.firmware_only):
        parser.error('replay inherits the sealed RTL/observer/firmware; source overrides are forbidden')
    out=args.out.resolve()
    if out.exists(): parser.error('evidence output must be new')
    deadline=datetime.fromisoformat(args.deadline)
    if datetime.now(timezone.utc)>=deadline: parser.error('deadline reached; no new experiment')
    out.mkdir(parents=True)
    report=dict(schema='s3_dma_day_cpu_v1',status='RUNNING',
                started_at=datetime.now(timezone.utc).isoformat(),deadline=args.deadline,
                arguments={k:str(v) if isinstance(v,Path) else [str(x) for x in v] if isinstance(v,list) else v for k,v in vars(args).items()},
                main=git_identity(ROOT),e203=git_identity(E203),runner_sha256=sha(Path(__file__)),
                scope='development real-CPU/peripheral DMA/fabric simulation; no PPA, STA, or official qualification',
                clock=dict(timescale='1ns/1fs',hf_period_fs=6666666,lf_period_fs=30517578126,
                           throughput_conversion_hz=150000000,scope='clock stimulus; not achieved STA frequency'))
    write_json(out/'result.json',report)
    try:
        replay=None
        if args.replay_from:
            replay_path=args.replay_from.resolve()
            replay=json.loads((replay_path/'result.json').read_text())
            if replay['status']!='PASS' or not replay.get('simulator_sha256'):
                raise ValueError('replay requires a completed PASS simulator identity')
            source=out/'source';shutil.copytree(replay_path/'source',source)
            manifest={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
            if manifest!=replay['source_sha256']: raise ValueError('replay source drift')
            shutil.copytree(replay_path/'firmware',out/'firmware')
            report['firmware']=replay['firmware'].copy()
            report['firmware']['elf']=str(out/'firmware/dma_day_soc')
            if sha(out/'firmware/dma_day_soc')!=report['firmware']['elf_sha256'] or sha(out/'firmware/dma_day_soc.verilog')!=report['firmware']['image_sha256']:
                raise ValueError('replay firmware/image drift')
            write_json(out/'source-manifest.json',dict(files=manifest,inherited_from=str(replay_path)))
            report['replay']=dict(parent=str(replay_path),parent_result_sha256=sha(replay_path/'result.json'))
        else:
            source,manifest=snapshot_sources(out,args.generated_dir,args.extra_source,args.observer)
            report['firmware']=compile_firmware(source/'tests',out/'firmware',args.cross_prefix)
        report['source_sha256']=manifest
        if args.firmware_only:
            report.update(status='PASS',scope='firmware build only; no simulation')
            return 0
        exporter=load_module('dma_day_export',ROOT/'tools/model/export_s3_vectors.py')
        vectors=out/'vectors'
        exporter.export_vectors(args.vectors or ROOT/'tests/e203/vectors/kwt-silence-v1.tar.gz',vectors,args.tasks,True)
        report['vectors']=check_vectors(vectors,args.tasks)
        report['vector_export']={p.name:sha(p) for p in [vectors/'profile.json',vectors/'export-manifest.json']}
        if replay:
            binary_dir=out/'simulator';binary_dir.mkdir()
            suffix='dma_day_soc' if args.sim=='verilator' else 'dma_day_soc.vvp'
            inherited=args.replay_from.resolve()/'simulator'/suffix
            if not inherited.exists() or sha(inherited)!=replay['simulator_sha256']:
                raise ValueError('replay simulator missing or changed')
            binary=binary_dir/suffix;shutil.copy2(inherited,binary)
            report['tools']=replay['tools']
            report['simulator_sha256']=sha(binary)
            report['replay']['simulator_sha256']=sha(binary)
            runtime=[str(binary)] if args.sim=='verilator' else ['vvp',str(binary)]
            write_json(out/'result.json',report)
        else:
            binary_dir=out/'simulator';binary_dir.mkdir()
            rtl=source/'rtl'
            sources=sorted(p for p in rtl.rglob('*') if p.suffix in ['.v','.sv'])+[source/'tests/tb_dma_day_soc.sv']
            filelist=out/'rtl.f';filelist.write_text(''.join(str(p)+'\n' for p in sources))
            includes=[rtl/'core',rtl/'perips',rtl/'perips/apb_i2c',source/'tests']
            defines=['-DDISABLE_SV_ASSERTION=1','-DXU_MATRIX_DMA']
            if args.sim=='verilator':
                binary=binary_dir/'dma_day_soc'
                command=['verilator','--binary','--timing','--assert','-CFLAGS','-std=gnu++20',
                         '-j',str(args.jobs),'-Wno-fatal','--top-module','tb_dma_day_soc',
                         '-Mdir',binary_dir,'-o','dma_day_soc',*defines,
                         *(['--trace'] if args.waves else []),*['-I'+str(p) for p in includes],'-f',filelist]
                runtime=[str(binary)]
            else:
                binary=binary_dir/'dma_day_soc.vvp'
                command=['iverilog','-g2012','-s','tb_dma_day_soc',*defines,
                         *['-I'+str(p) for p in includes],'-o',binary,'-f',filelist]
                runtime=['vvp',str(binary)]
            report['tools']={}
            for tool in [args.sim,args.cross_prefix+'gcc',args.cross_prefix+'objcopy',args.cross_prefix+'objdump','g++']:
                if shutil.which(tool):
                    result=subprocess.run([tool,'-V' if tool=='iverilog' else '--version'],capture_output=True,text=True)
                    report['tools'][tool]=dict(path=shutil.which(tool),version=(result.stdout+result.stderr).splitlines()[:4])
            write_json(out/'result.json',report)
            run(command,out,out/'simulator-build.log',timeout=min(7200,max(1,(deadline-datetime.now(timezone.utc)).total_seconds())))
            report['simulator_sha256']=sha(binary)
        if args.build_only:
            report.update(status='PASS',scope='firmware and simulator build only; no runtime verification')
            return 0
        if datetime.now(timezone.utc)>=deadline: raise RuntimeError('deadline reached before simulation start')
        runtime += [f'+TESTCASE={out}/firmware/dma_day_soc',f'+VECTORS={vectors}',f'+TASKS={args.tasks}',
                    f'+DUAL={args.dual}',f'+WARMUP={int(args.warmup)}',f'+THROTTLE={args.throttle}',f'+FIRST_SOURCE_STALL={args.first_source_stall}',
                    f'+MAX_CYCLES={args.max_cycles}',f'+DUMPWAVE={int(args.waves)}']
        print(f'RUNNING real CPU tasks={args.tasks} dual={args.dual} evidence={out}',flush=True)
        log=run(runtime,out,out/'simulation.log',timeout=min(7200,max(1,(deadline-datetime.now(timezone.utc)).total_seconds())))
        report.update(check_log(log,args.tasks,args.dual,args.warmup))
        if any(layer['window']['first_accept']-layer['window']['first_request']<args.first_source_stall for layer in report['layers']):
            raise ValueError('first source VALID timing omitted forced wait')
        if (source/'tests/dma_physical_observer.svh').exists():
            report['physical_clear']=check_physical_clear(log,args.tasks,args.warmup)
        actual={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
        if actual!=manifest: raise RuntimeError('frozen simulation source changed during run')
        report.update(status='PASS',source_drift=[],physical_clear_proof='see physical observer records' if (source/'tests/dma_physical_observer.svh').exists() else 'observer required separately',
                      performance_scope='complete12' if args.tasks==12 else 'single-layer or partial; not whole12 performance proof')
        print(f'DMA_CPU_PASS tasks={args.tasks} principal={report["principal_cycles"]} outputs={report["outputs"]}',flush=True)
        return 0
    except Exception as exc:
        report.update(status='FAIL',error=str(exc),traceback=traceback.format_exc())
        print(f'DMA_CPU_FAIL: {exc}; evidence={out}',file=sys.stderr,flush=True)
        return 1
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        write_json(out/'result.json',report)


if __name__=='__main__':
    sys.exit(main())
