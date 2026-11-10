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

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
E203 = ROOT / 'third-party/e203_hbirdv2'
TESTS = ROOT / 'tests/e203'
DEADLINE = '2026-11-10T23:59:00+08:00'


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


def check_log(log, tasks, rows, warmup=False, checker_path=None):
    checker=load_module('d4k_result_checker',checker_path or HERE/'check_results.py')
    return checker.check_log(log,tasks,rows,warmup)


def snapshot_sources(out: Path, generated: list[Path], extras: list[Path], observer: Path|None):
    source=out/'source';source.mkdir()
    rtl=source/'rtl';shutil.copytree(E203/'rtl/e203',rtl)
    tests=source/'tests';tests.mkdir()
    shutil.copy2(HERE/'tb_dma64_soc.sv',tests/'tb_dma64_soc.sv')
    firmware=tests/'firmware';firmware.mkdir()
    for name in ['start.S','link.ld']:
        shutil.copy2(TESTS/'firmware'/name,firmware/name)
    shutil.copy2(HERE/'dma64_main.c',tests/'dma_day_main.c')
    shutil.copy2(Path(__file__),source/'run_cpu.py')
    shutil.copy2(HERE/'check_results.py',source/'check_results.py')
    overrides=[]
    for directory in generated:
        for path in sorted(directory.rglob('*')):
            if path.suffix not in ['.v','.sv','.vh','.svh'] or not path.is_file():continue
            same=list(rtl.rglob(path.name))
            if len(same)>1:raise ValueError('ambiguous source '+path.name)
            destination=same[0] if same else rtl/'perips'/path.name
            if destination.exists():overrides.append(dict(path=str(destination.relative_to(source)),old_sha256=sha(destination),new_sha256=sha(path),origin=str(path)))
            shutil.copy2(path,destination)
    for path in extras:
        target=rtl/'perips'/path.name
        if target.exists():raise ValueError('extra source already exists '+str(target))
        shutil.copy2(path,target)
    # Exact 256-macro shared endpoint, not a behavioral ideal sink.
    for name in ['xu_dma64_shared_arb.sv','xu_shared_icb_sram64.sv']:
        origin=HERE.parent/'fabric'/name
        target=rtl/'perips'/name
        if target.exists() and sha(target)!=sha(origin):raise ValueError('fabric source differs '+name)
        shutil.copy2(origin,target)
    shutil.copy2(ROOT/'tools/ppa/generic_ramsp_non_ppa.sv',rtl/'perips/generic_ramsp_non_ppa.sv')
    generator=load_module('d4k_observer_generator',HERE/'generate_observer.py')
    generator.generate(tests/'dma64_physical_observer.svh',mode='cpu',
        owners_idle="!`DMA.pending && !`DMA.locked && !`CORE.io_active && !`CORE.io_outValid",
        snapshot_zero="(`DMA.y_payload === 0) && (`DMA.bias_data === 0) && (`DMA.bias_addr === 0) && (`DMA.lock_data === 0) && (`DMA.lock_addr === 0) && (`DMA.pending_index === 0) && (`DMA.lock_index === 0) && (`DMA.run_x === 0) && (`DMA.run_w === 0) && (`DMA.run_b === 0) && (`DMA.run_y === 0)")
    shutil.copy2(tests/'tile_physical_observer.sv',rtl/'perips/tile_physical_observer.sv')
    manifest={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    write_json(out/'source-manifest.json',dict(files=manifest,overrides=overrides))
    return source,manifest


def validate_replay_arguments(args, replay):
    """Runtime modes may change; frozen compile-time endpoint settings may not."""
    parent=replay['arguments']
    if args.throttle != int(parent['throttle']):
        raise ValueError('replay throttle differs from the frozen compile-time endpoint; use a fresh build')
    if args.sim != parent['sim']:
        raise ValueError('replay simulator differs from the frozen executable')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--tasks',type=int,default=1)
    parser.add_argument('--rows',type=int,choices=[1,8],default=8)
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
    if args.replay_from:
        try: validate_replay_arguments(args,json.loads((args.replay_from.resolve()/'result.json').read_text()))
        except (OSError,ValueError,KeyError) as exc: parser.error(str(exc))
    out=args.out.resolve()
    if out.exists(): parser.error('evidence output must be new')
    deadline=datetime.fromisoformat(args.deadline)
    if datetime.now(timezone.utc)>=deadline: parser.error('deadline reached; no new experiment')
    out.mkdir(parents=True)
    report=dict(schema='s3_parallel4k_cpu_v1',status='RUNNING',
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
            if replay['status']!='PASS' or not replay.get('simulator_sha256') or not replay.get('physical_clear') or replay.get('outputs',0)!=int(replay.get('arguments',{}).get('tasks',0))*25344:
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
            sources=sorted(p for p in rtl.rglob('*') if p.suffix in ['.v','.sv'])+[source/'tests/tb_dma64_soc.sv']
            filelist=out/'rtl.f';filelist.write_text(''.join(str(p)+'\n' for p in sources))
            includes=[rtl/'core',rtl/'perips',rtl/'perips/apb_i2c',source/'tests']
            defines=['-DDISABLE_SV_ASSERTION=1','-DXU_MATRIX_DMA','-DXU_MATRIX_DMA64',f'-DD4K_THROTTLE={args.throttle}']
            if args.sim=='verilator':
                binary=binary_dir/'dma_day_soc'
                command=['verilator','--binary','--timing','--assert','-CFLAGS','-std=gnu++20',
                         '-j',str(args.jobs),'-Wno-fatal','--top-module','tb_dma64_soc',
                         '-Mdir',binary_dir,'-o','dma_day_soc',*defines,
                         *(['--trace'] if args.waves else []),*['-I'+str(p) for p in includes],'-f',filelist]
                runtime=[str(binary)]
            else:
                binary=binary_dir/'dma_day_soc.vvp'
                command=['iverilog','-g2012','-s','tb_dma64_soc',*defines,
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
                    f'+ROWS={args.rows}',f'+WARMUP={int(args.warmup)}',f'+THROTTLE={args.throttle}',f'+FIRST_SOURCE_STALL={args.first_source_stall}',
                    f'+MAX_CYCLES={args.max_cycles}',f'+DUMPWAVE={int(args.waves)}']
        print(f'RUNNING real CPU tasks={args.tasks} rows={args.rows} evidence={out}',flush=True)
        log=run(runtime,out,out/'simulation.log',timeout=min(7200,max(1,(deadline-datetime.now(timezone.utc)).total_seconds())))
        report.update(check_log(log,args.tasks,args.rows,args.warmup,source/'check_results.py'))
        report['each_layer_target_met']=all(x['principal']<=37500 for x in report['layers'])
        report['full12_target_met']=(args.tasks==12 and args.warmup and report['principal_cycles']<=450000 and report['each_layer_target_met'])
        if any(layer['window']['first_accept']-layer['window']['first_request']<args.first_source_stall for layer in report['layers']):
            raise ValueError('first source VALID timing omitted forced wait')
        actual={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
        if actual!=manifest: raise RuntimeError('frozen simulation source changed during run')
        report.update(status='PASS',source_drift=[],physical_clear_proof='mandatory read-only physical observer records',
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
