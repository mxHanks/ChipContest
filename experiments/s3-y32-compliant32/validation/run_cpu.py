#!/usr/bin/env python3
"""Frozen-source original32 SystemBus/64PE realCPU development verification.

Full timing starts at input/parameter source loading OFFER; official SDK/STA/
power/600audio certification is separate. No source tensors use TCM backdoors.
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
DEADLINE = None


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


def snapshot_sources(out):
    source=out/'source';source.mkdir();rtl=source/'rtl';shutil.copytree(E203/'rtl/e203',rtl)
    tests=source/'tests';tests.mkdir();firmware=tests/'firmware';firmware.mkdir()
    for name in ['start.S','link.ld']:shutil.copy2(TESTS/'firmware'/name,firmware/name)
    shutil.copy2(HERE/'sysbus32_main.c',tests/'dma_day_main.c')
    shutil.copy2(HERE/'tb_sysbus32_soc.sv',tests/'tb_sysbus32_soc.sv')
    for name in ['run_cpu.py','check_results.py']:shutil.copy2(HERE/name,source/name)
    # CPU boot retains the existing behavioral ITCM model. Shared SRAM uses
    # the exact PPA macro adapter, locally renamed to prevent replacing CPU RAM.
    # The only two transforms are module type identifiers; retain byte receipts.
    originals={}
    for origin,name,before,after in [
      (ROOT/'tools/ppa/xu_shared_icb_sram.sv','xu_shared_icb_sram.sv','sirv_sim_ram #','xu_compliance_shared_sram #'),
      (ROOT/'tools/ppa/xu_sirv_sram_adapter.sv','xu_compliance_shared_sram.sv','module sirv_sim_ram #','module xu_compliance_shared_sram #')]:
        text=origin.read_text()
        if text.count(before)!=1:raise ValueError('adapter rename seam differs')
        target=rtl/'perips'/name;target.write_text(text.replace(before,after))
        originals[name]=dict(origin=str(origin),origin_sha256=sha(origin),replacement=[before,after],transformed_sha256=sha(target))
    shutil.copy2(ROOT/'tools/ppa/generic_ramsp_non_ppa.sv',rtl/'perips/generic_ramsp_non_ppa.sv')
    generator_path=ROOT/'experiments/s3-y32-4k/validation/generate_observer.py'
    shutil.copy2(generator_path,source/'generate_observer.py')
    generator=load_module('c32_observer',source/'generate_observer.py')
    observer=tests/'sysbus32_physical_observer.svh'
    generator.generate(observer,mode='cpu',owners_idle="!`DMA.pending && !`DMA.locked && !`CORE.io_active && !`CORE.io_outValid",snapshot_zero="(`DMA.w_low === 0) && (`DMA.bias_low === 0) && (`DMA.y_payload === 0) && (`DMA.bias_data === 0) && (`DMA.bias_addr === 0) && (`DMA.lock_data === 0) && (`DMA.lock_addr === 0) && (`DMA.pending_index === 0) && (`DMA.lock_index === 0) && (`DMA.run_x === 0) && (`DMA.run_w === 0) && (`DMA.run_b === 0) && (`DMA.run_y === 0)")
    for p in [observer,tests/'tile_physical_observer.sv']:p.write_text(p.read_text().replace('D4K','C32'))
    shutil.copy2(tests/'tile_physical_observer.sv',rtl/'perips/tile_physical_observer.sv')
    manifest={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
    write_json(out/'source-manifest.json',dict(files=manifest,typename_only_shared_macro_transforms=originals))
    return source,manifest


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--tasks',type=int,default=1);parser.add_argument('--rows',type=int,choices=[1,8],default=8)
    parser.add_argument('--cross-prefix',default='riscv64-unknown-elf-');parser.add_argument('--jobs',type=int,default=2)
    parser.add_argument('--warmup',action='store_true');parser.add_argument('--first-source-stall',type=int,default=0)
    parser.add_argument('--first-load-stall',type=int,default=0)
    parser.add_argument('--max-cycles',type=int,default=20000000);parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--replay-from',type=Path);parser.add_argument('--deadline',help='Optional timezone-qualified deadline; historical experiment cutoffs are not reused')
    args=parser.parse_args(argv)
    if not 1<=args.tasks<=12 or not 1<=args.jobs<=2:parser.error('tasks1..12 and jobs1..2 required')
    out=args.out.resolve()
    if out.exists():parser.error('evidence output must be new')
    deadline=datetime.fromisoformat(args.deadline) if args.deadline else None
    if deadline and (deadline.tzinfo is None or datetime.now(timezone.utc)>=deadline):parser.error('invalid/reached deadline')
    out.mkdir(parents=True)
    report=dict(schema='s3-compliant32-cpu-v1',status='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},main=git_identity(ROOT),e203=git_identity(E203),runner_sha256=sha(Path(__file__)),official_qualification='NOT_VERIFIED',clock=dict(hf_period_fs=6666666,lf_period_fs=30517578126,throughput_conversion_hz=150000000,scope='stimulus only; no achieved STA frequency'))
    write_json(out/'result.json',report)
    try:
        if deadline and datetime.now(timezone.utc)>=deadline:raise RuntimeError('deadline reached')
        vectors=args.vectors.resolve();report['vectors_manifest_sha256']=sha(vectors/'vectors-manifest.json')
        verify=ROOT/'experiments/s3-y32-compliant32/numeric/verify_vectors.py'
        run([sys.executable,'-B',verify,'--vectors',vectors,'--receipt',out/'vector-audit.json'],ROOT,out/'vector-audit.log')
        report['vectors']=check_vectors(vectors,args.tasks)
        report['vector_byte_sha256']={str(p.relative_to(vectors)):sha(p) for p in sorted(vectors.rglob('*')) if p.is_file()}
        report['numeric_tool_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sorted(verify.parent.glob('*.py'))}
        report['model_sha256']={p.name:sha(p) for p in [ROOT/'model/fixed16_acc48.py',ROOT/'model/s3_y32.py']}
        binary_dir=out/'simulator';binary_dir.mkdir()
        if args.replay_from:
            replay=args.replay_from.resolve();prev=json.loads((replay/'result.json').read_text())
            if prev.get('schema')!='s3-compliant32-cpu-v1' or prev.get('status')!='PASS' or not prev.get('physical_clear') or not prev.get('simulator_sha256'):raise ValueError('replay must be functionally PASS, not build-only')
            source=out/'source';shutil.copytree(replay/'source',source)
            manifest={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
            if manifest!=prev['source_sha256']:raise ValueError('replay source drift')
            shutil.copytree(replay/'firmware',out/'firmware');report['firmware']=prev['firmware'].copy();report['firmware']['elf']=str(out/'firmware/dma_day_soc');report['tools']=prev['tools']
            for p,key in [('dma_day_soc','elf_sha256'),('dma_day_soc.verilog','image_sha256')]:
                if sha(out/'firmware'/p)!=report['firmware'][key]:raise ValueError('replay firmware drift')
            binary=binary_dir/'sysbus32_soc';shutil.copy2(replay/'simulator/sysbus32_soc',binary)
            if sha(binary)!=prev['simulator_sha256']:raise ValueError('replay simulator drift')
            report['replay']=dict(parent=str(replay),parent_result_sha256=sha(replay/'result.json'))
        else:
            source,manifest=snapshot_sources(out);report['firmware']=compile_firmware(source/'tests',out/'firmware',args.cross_prefix)
            rtl=source/'rtl';sources=sorted(p for p in rtl.rglob('*') if p.suffix in ['.v','.sv'])+[source/'tests/tb_sysbus32_soc.sv']
            filelist=out/'rtl.f';filelist.write_text(''.join(str(p)+'\n' for p in sources))
            includes=[rtl/'core',rtl/'perips',rtl/'perips/apb_i2c',source/'tests']
            defines=['-DDISABLE_SV_ASSERTION=1','-DXU_MATRIX_DMA','-DXU_MATRIX_DMA_SYSBUS32','-DXU_SYSBUS_TEST_LOADER']
            binary=binary_dir/'sysbus32_soc'
            command=['verilator','--binary','--timing','--assert','-CFLAGS','-std=gnu++20','-j',str(args.jobs),'-Wno-fatal','--top-module','tb_sysbus32_soc','-Mdir',binary_dir,'-o','sysbus32_soc',*defines,*['-I'+str(p) for p in includes],'-f',filelist]
            report['tools']={}
            for tool in ['verilator',args.cross_prefix+'gcc',args.cross_prefix+'objcopy',args.cross_prefix+'objdump','g++']:
                done=subprocess.run([tool,'--version'],capture_output=True,text=True);report['tools'][tool]=dict(path=shutil.which(tool),version=(done.stdout+done.stderr).splitlines()[:4])
            report['source_sha256']=manifest;write_json(out/'result.json',report)
            run(command,out,out/'simulator-build.log',timeout=7200)
        report['source_sha256']=manifest;report['simulator_sha256']=sha(binary);write_json(out/'result.json',report)
        if args.build_only:
            report.update(status='BUILD_PASS_ONLY',scope='No runtime correctness or timing proof');return 0
        if deadline and datetime.now(timezone.utc)>=deadline:raise RuntimeError('deadline reached before simulation')
        runtime=[binary,f'+TESTCASE={out}/firmware/dma_day_soc',f'+VECTORS={vectors}',f'+TASKS={args.tasks}',f'+ROWS={args.rows}',f'+WARMUP={int(args.warmup)}',f'+FIRST_SOURCE_STALL={args.first_source_stall}',f'+FIRST_LOAD_STALL={args.first_load_stall}',f'+MAX_CYCLES={args.max_cycles}']
        print(f'RUNNING original32 SystemBus realCPU tasks={args.tasks} evidence={out}',flush=True)
        log=run(runtime,out,out/'simulation.log',timeout=7200)
        checker=load_module('c32_frozen_checker',source/'check_results.py');report.update(checker.check_log(log,args.tasks,args.rows,args.warmup))
        # Independent runner checks bind actual runtime claims to this invocation,
        # including when replaying a frozen older checker/binary.
        for record in report['layers']+report.get('warmup',{}).get('layers',[]):
            channel=record['channel']
            if channel.get('forced_wait')!=args.first_source_stall or channel.get('forced_load_wait')!=args.first_load_stall:raise ValueError('replay/log stall settings differ from requested parameters')
            ep=record.get('endpoint',{})
            if ep.get('source_reads')!=15040 or ep.get('source_writes')!=15040 or ep.get('outstanding') not in [0,1]:raise ValueError('replay endpoint contract predates complete transaction classification')
            if ep.get('requests',-1)-ep.get('responses',-1)!=ep['outstanding']:raise ValueError('replay endpoint ownership differs')
            win=record['window']
            if not win['clear_done']<win['load_begin']:raise ValueError('task source loaded before physical clear')
            if record['total']!=win['last_y_response']-win['clear_request']+1:raise ValueError('conservative full task boundary differs')
        actual={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
        if actual!=manifest:raise RuntimeError('frozen source changed')
        if sha(vectors/'vectors-manifest.json')!=report['vectors_manifest_sha256']:raise RuntimeError('vector manifest changed')
        if {str(p.relative_to(vectors)):sha(p) for p in sorted(vectors.rglob('*')) if p.is_file()}!=report['vector_byte_sha256']:raise RuntimeError('vector byte content changed')
        report.update(status='PASS',source_drift=[],performance_scope='complete12 local development' if args.tasks==12 else 'partial local development, no complete12 performance proof')
        print(f'C32_CPU_PASS tasks={args.tasks} total={report["total_cycles"]} outputs={report["outputs"]}',flush=True);return 0
    except Exception as exc:
        report.update(status='FAIL',error=str(exc),traceback=traceback.format_exc());print(f'C32_CPU_FAIL {exc}; evidence={out}',file=sys.stderr,flush=True);return 1
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();write_json(out/'result.json',report)

if __name__=='__main__':sys.exit(main())
