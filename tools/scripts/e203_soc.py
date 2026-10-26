#!/usr/bin/env python3
"""Reproducible C-role development SoC checks; Python standard library only."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
E203 = ROOT / 'third-party/e203_hbirdv2'
TESTS = ROOT / 'tests/e203'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, cwd, logfile, timeout=1800):
    with logfile.open('w') as log:
        log.write(json.dumps([str(c) for c in command]) + '\n')
        log.flush()
        env = dict(os.environ, PWD=str(Path(cwd).resolve()))
        result = subprocess.run(command, cwd=cwd, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'command exit {result.returncode}: {logfile}')
    return logfile.read_text(errors='replace')


def read_mem(path, bits, count):
    words = path.read_text().split()
    if len(words) != count or any(not re.fullmatch(r'[0-9a-fA-F]{%d}' % (bits//4), w)
                                  for w in words):
        raise ValueError(f'invalid {bits}-bit vector: {path}, expected {count} words')
    values = [int(w, 16) for w in words]
    return [n - (1 << bits) if n & (1 << (bits-1)) else n for n in values]


def check_log(log, tasks):
    if re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout', log, re.I):
        raise ValueError('simulation reported failure')
    found = re.findall(r'TASK_PASS layer=(\d+) outputs=25344 writes=50688 cycles=(\d+) firmware_cycles=(\d+)', log)
    if [int(x[0]) for x in found] != list(range(tasks)):
        raise ValueError('missing, duplicate or unordered layer completion')
    end = f'SOC_PASS tasks={tasks} outputs={tasks*25344} writes={tasks*50688}'
    if log.count(end) != 1:
        raise ValueError('missing complete SoC result marker')
    return [dict(layer=int(a), cycles=int(b), firmware_cycles=int(c)) for a,b,c in found]


def build_key(report, sim, waves):
    identity=[report['source_sha256'],report['versions'],report['runner_sha256'],sim,waves]
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]


def synthetic(directory, tasks):
    for layer in range(tasks):
        dest = directory / f'layer_{layer:02d}'
        dest.mkdir(parents=True)
        x = [(r*3+k*5+layer*7)%31-15 for r in range(99) for k in range(64)]
        w = [(k*3+c*7+layer*11)%29-14 for k in range(64) for c in range(256)]
        x[0:2] = [-32768, 32767]
        w[0:256] = [-32768 if c%2 else 32767 for c in range(256)]
        bias = [(c-128)*(1 << 31)+layer for c in range(256)]
        y = [bias[c]+sum(x[r*64+k]*w[k*256+c] for k in range(64))
             for r in range(99) for c in range(256)]
        for name, values, bits in [('x',x,16),('w',w,16),('bias',bias,40),('y',y,48)]:
            (dest/f'{name}.mem').write_text(''.join(f'{v&((1<<bits)-1):0{bits//4}x}\n' for v in values))


def compile_firmware(out, prefix):
    target = out/'accel_soc'
    sources = [TESTS/'firmware'/name for name in ['start.S','main.c','accel.c']]
    run([prefix+'gcc','-march=rv32imac_zicsr_zifencei','-mabi=ilp32',
         '-Os','-ffreestanding','-fno-builtin','-msmall-data-limit=0',
         '-nostdlib','-nostartfiles','-static','-mcmodel=medany','-Wl,--no-relax',
         '-T',str(TESTS/'firmware/link.ld'),*[str(p) for p in sources],'-o',str(target)],
        ROOT,out/'firmware-build.log')
    run([prefix+'objcopy','-O','verilog',str(target),str(target)+'.verilog'],ROOT,out/'objcopy.log')
    image = Path(str(target)+'.verilog')
    image.write_text(image.read_text().replace('@800','@000'))
    dump = run([prefix+'objdump','--disassemble-all',str(target)],ROOT,out/'firmware.dump')
    if not re.search(r'80000086\s+<write_tohost>', dump):
        raise ValueError('firmware completion address is not 0x80000086')
    return target


def baseline(out, prefix):
    vsim=E203/'vsim'
    results=[]
    inputs={}
    for name in ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x']:
        if name.startswith('rv32'):
            target=E203/'riscv-tools/riscv-tests/isa/generated'/name
        else:
            target=out/name
            run([prefix+'gcc','-march=rv32imac_zicsr_zifencei','-mabi=ilp32',
                 '-nostdlib','-nostartfiles','-static','-mcmodel=medany','-Wl,--no-relax',
                 '-T',str(E203/'riscv-tools/riscv-tests/env/p/link.ld'),
                 str(TESTS/(name+'.S')),'-o',str(target)],ROOT,out/(name+'-build.log'))
            run([prefix+'objcopy','-O','verilog',str(target),str(target)+'.verilog'],ROOT,out/(name+'-objcopy.log'))
            image=Path(str(target)+'.verilog')
            image.write_text(image.read_text().replace('@800','@000'))
        log=run(['make','run_test','SIM=iverilog','DUMPWAVE=0','TESTCASE='+str(target)],
                vsim,out/(name+'.log'))
        if 'TEST_PASS' not in log or re.search(r'TEST_FAIL|Time Out|FATAL|ERROR:',log):
            raise ValueError(f'baseline did not pass: {name}')
        results.append(name)
        inputs[name]={'image_sha256':sha(Path(str(target)+'.verilog'))}
        if not name.startswith('rv32'):
            inputs[name]['assembly_sha256']=sha(TESTS/(name+'.S'))
            inputs[name]['elf_sha256']=sha(target)
        print('PASS '+name,flush=True)
    return {'tests':results,'test_inputs':inputs}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['doctor','baseline','synthetic','real','vectors'],default='synthetic')
    parser.add_argument('--tasks',type=int,choices=range(1,13),default=1)
    parser.add_argument('--vectors',type=Path)
    parser.add_argument('--sim',choices=['verilator','iverilog'],default='verilator')
    parser.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--waves',action='store_true')
    parser.add_argument('--max-cycles',type=int,default=200000000)
    args=parser.parse_args()
    if args.max_cycles < 1:
        parser.error('--max-cycles must be positive')
    out=(args.out or ROOT/'build/e203'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    out.mkdir(parents=True,exist_ok=False)
    report={'status':'RUNNING','mode':args.mode,'tasks':args.tasks,
            'scope':'development platform; TB shared-memory preload excluded; no official PPA/accuracy claim'}
    try:
        required=['git','make','iverilog','vvp',args.cross_prefix+'gcc',args.cross_prefix+'objcopy',args.cross_prefix+'objdump']
        if args.sim=='verilator' and args.mode!='baseline':
            required+=['verilator','g++']
        report['tools']={name:shutil.which(name) for name in required}
        missing=[n for n,p in report['tools'].items() if p is None]
        if missing: raise RuntimeError('missing tools: '+', '.join(missing))
        report['versions']={}
        for name in ['iverilog',args.cross_prefix+'gcc','verilator','g++']:
            if shutil.which(name):
                report['versions'][name]=run([name,'-V' if name=='iverilog' else '--version'],ROOT,out/(name.replace('/','_')+'-version.log')).splitlines()[1:3]
        report['main_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        report['e203_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=E203,text=True).strip()
        if args.mode=='doctor':
            report['status']='PASS'
        else:
            # Always refresh the installed RTL, following the repository quickstart.
            run(['make','clean'],E203/'vsim',out/'clean.log')
            run(['make','install'],E203/'vsim',out/'install.log')
            installed=E203/'vsim/install/rtl'
            report['source_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sorted(installed.rglob('*')) if p.suffix in ['.v','.sv']}
            if args.mode=='baseline':
                report.update(baseline(out,args.cross_prefix))
            else:
                if args.mode=='synthetic':
                    directory=out/'vectors'
                    synthetic(directory,args.tasks)
                elif args.mode=='real':
                    directory=out/'vectors'
                    directory.mkdir()
                    archive=TESTS/'vectors/kwt-silence-v1.tar.gz'
                    manifest=json.loads((TESTS/'vectors/kwt-silence-v1.json').read_text())
                    if sha(archive)!=manifest['archive_sha256']: raise ValueError('fixture archive hash mismatch')
                    # Only regular expected tensor members; no arbitrary archive paths.
                    with tarfile.open(archive) as tar:
                        for layer in range(args.tasks):
                            dest=directory/f'layer_{layer:02d}'
                            dest.mkdir()
                            for name in ['x','w','bias','y']:
                                member=tar.getmember(f'layer_{layer:02d}/{name}.mem')
                                if not member.isfile(): raise ValueError('non-file fixture member')
                                data=tar.extractfile(member).read()
                                key=f'layer_{layer:02d}/{name}.mem'
                                if hashlib.sha256(data).hexdigest()!=manifest['files'][key]:
                                    raise ValueError('fixture tensor hash mismatch: '+key)
                                (dest/(name+'.mem')).write_bytes(data)
                    report['fixture']=manifest
                else:
                    if args.vectors is None: raise ValueError('--vectors is required')
                    directory=args.vectors.resolve()
                report['vectors']={}
                for layer in range(args.tasks):
                    for name,bits,count in [('x',16,6336),('w',16,16384),('bias',40,256),('y',48,25344)]:
                        path=directory/f'layer_{layer:02d}'/(name+'.mem')
                        read_mem(path,bits,count)
                        report['vectors'][str(path.relative_to(directory))]=sha(path)
                firmware=compile_firmware(out,args.cross_prefix)
                report['firmware_sha256']={p.name:sha(p) for p in (TESTS/'firmware').iterdir() if p.is_file()}
                report['firmware_elf_sha256']=sha(firmware)
                report['firmware_image_sha256']=sha(Path(str(firmware)+'.verilog'))
                report['runner_sha256']=sha(Path(__file__))
                installed=E203/'vsim/install/rtl'
                sources=sorted([p for p in installed.rglob('*') if p.suffix in ['.v','.sv']])
                sources+=[TESTS/'tb_accel_soc.sv']
                report['source_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sources}
                key=build_key(report,args.sim,args.waves)
                cache=ROOT/'build/e203'/('sim-'+key)
                cache.mkdir(parents=True,exist_ok=True)
                filelist=cache/'rtl.f'
                filelist.write_text('\n'.join(str(p) for p in sources)+'\n')
                includes=[str(installed/p) for p in ['core','perips','perips/apb_i2c']]
                if args.sim=='verilator':
                    binary=cache/'accel_soc'
                    if not binary.exists():
                        run(['verilator','--binary','--timing',*(['--trace'] if args.waves else []),'-j','2','-Wno-fatal',
                             '--top-module','tb_accel_soc','-Mdir',str(cache),'-o','accel_soc',
                             '-DDISABLE_SV_ASSERTION=1',*['-I'+p for p in includes],'-f',str(filelist)],
                            ROOT,out/'simulator-build.log')
                    command=[str(binary)]
                else:
                    binary=cache/'accel_soc.vvp'
                    run(['iverilog','-g2012','-s','tb_accel_soc','-DDISABLE_SV_ASSERTION=1',
                         *['-I'+p for p in includes],'-o',str(binary),'-f',str(filelist)],ROOT,out/'simulator-build.log')
                    command=['vvp',str(binary)]
                report['simulator_sha256']=sha(binary)
                print(f'Running {args.mode}: {args.tasks} tasks; logs: {out}',flush=True)
                log=run(command+[f'+TESTCASE={firmware}',f'+VECTORS={directory}',
                        f'+TASKS={args.tasks}',f'+DUMPWAVE={int(args.waves)}',
                        f'+MAX_CYCLES={args.max_cycles}'],out,out/'simulation.log',7200)
                report['layers']=check_log(log,args.tasks)
                report['outputs']=args.tasks*25344
                report['write_words']=args.tasks*50688
            report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL'
        report['error']=str(exc)
        print(str(exc),file=sys.stderr)
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{report["status"]}: {out / "result.json"}',flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
