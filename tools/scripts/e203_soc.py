#!/usr/bin/env python3
"""Reproducible xu development SoC checks; Python standard library only."""
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
import xu_firmware_contract as contract

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
        result = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'command exit {result.returncode}: {logfile}')
    # Keep invocation metadata in the saved log, outside parsed process output.
    return logfile.read_text(errors='replace').split('\n',1)[1]


def read_mem(path, bits, count):
    words = path.read_text().split()
    if len(words) != count or any(not re.fullmatch(r'[0-9a-fA-F]{%d}' % (bits//4), w)
                                  for w in words):
        raise ValueError(f'invalid {bits}-bit vector: {path}, expected {count} words')
    values = [int(w, 16) for w in words]
    return [n - (1 << bits) if n & (1 << (bits-1)) else n for n in values]


def load_fixture(directory, tasks):
    archive=TESTS/'vectors/kwt-silence-v1.tar.gz'
    manifest=json.loads((TESTS/'vectors/kwt-silence-v1.json').read_text())
    if sha(archive)!=manifest['archive_sha256']:
        raise ValueError('fixture archive hash mismatch')
    with tarfile.open(archive) as tar:
        for layer in range(tasks):
            dest=directory/f'layer_{layer:02d}'
            dest.mkdir(parents=True)
            for name in ['x','w','bias','y']:
                key=f'layer_{layer:02d}/{name}.mem'
                member=tar.getmember(key)
                if not member.isfile(): raise ValueError('non-file fixture member')
                data=tar.extractfile(member).read()
                if hashlib.sha256(data).hexdigest()!=manifest['files'][key]:
                    raise ValueError('fixture tensor hash mismatch: '+key)
                (dest/(name+'.mem')).write_bytes(data)
    return manifest


def check_vectors(directory, tasks):
    """Independent unbounded-integer reference; never supplies CPU/RTL results."""
    if not 1 <= tasks <= 12: raise ValueError('invalid task count')
    layers=[]
    for layer in range(tasks):
        source=directory/f'layer_{layer:02d}'
        x=read_mem(source/'x.mem',16,6336)
        w=read_mem(source/'w.mem',16,16384)
        bias=read_mem(source/'bias.mem',40,256)
        y=read_mem(source/'y.mem',48,25344)
        for row in range(99):
            for col in range(256):
                expected=bias[col]+sum(x[row*64+k]*w[k*256+col] for k in range(64))
                if expected!=y[row*256+col]:
                    raise ValueError(f'vector mismatch layer={layer} row={row} col={col}: '
                                     f'expected {expected}, got {y[row*256+col]}')
        layers.append({'layer':layer,'outputs':25344,
                       'sha256':{p.name:sha(p) for p in sorted(source.glob('*.mem'))}})
    return layers


def check_log(log, tasks):
    if re.search(r'FATAL|TEST_FAIL|%Error|Time Out|timeout', log, re.I):
        raise ValueError('simulation reported failure')
    found = re.findall(r'^TASK_PASS layer=(\d+) outputs=25344 writes=50688 cycles=(\d+) firmware_cycles=(\d+)$', log,re.M)
    if ([int(x[0]) for x in found] != list(range(tasks)) or
            len(found)!=len(re.findall(r'^TASK_PASS\b',log,re.M))):
        raise ValueError('missing, duplicate or unordered layer completion')
    end = f'SOC_PASS tasks={tasks} outputs={tasks*25344} writes={tasks*50688}'
    if re.findall(r'^SOC_PASS.*$',log,re.M) != [end]:
        raise ValueError('missing complete SoC result marker')
    return [dict(layer=int(a), cycles=int(b), firmware_cycles=int(c)) for a,b,c in found]


def check_performance(log, layers, schedule='baseline'):
    """Require complete observer records in addition to numerical completion."""
    contract.configuration(schedule)
    fields = contract.PERFORMANCE_FIELDS
    pattern = r'^PERF_TASK ' + ' '.join(name + r'=(\d+)' for name in fields) + r'$'
    found = re.findall(pattern, log, re.M)
    if len(found) != len(layers) or len(found) != len(re.findall(r'^PERF_TASK\b', log, re.M)):
        raise ValueError('missing or malformed performance records')
    records = [dict(zip(fields, map(int, row))) for row in found]
    for row, layer in zip(records, layers):
        if row['layer'] != layer['layer'] or row['cycles'] != layer['cycles']:
            raise ValueError('performance window or layer differs from task completion')
        contract.validate_performance({k: v for k, v in row.items()
                                       if k not in ['layer', 'cycles']}, row['cycles'], schedule)
    return [{k: v for k, v in row.items() if k not in ['layer', 'cycles']} for row in records]


def check_sram_bias_latency(counters, schedule):
    """S1 retains 68 wrapper busy cycles, plus two per cached START.

    This checks a fixed hardware latency; polling/MMIO totals stay measured and
    the existing transaction/numeric contract must be checked independently.
    """
    contract.configuration(schedule)
    cached = schedule.startswith('bias-hw')
    starts = 99 * 32
    expected_busy = starts * (70 if cached else 68)
    if counters['busy'] != expected_busy:
        raise ValueError('SRAM candidate busy cycles differ from fixed latency')
    return dict(prefetches=starts if cached else 0,
                extra_busy_cycles=starts * 2 if cached else 0,
                expected_busy=expected_busy)


def build_key(report, sim, waves):
    identity=[report['source_sha256'],report['versions'],report['runner_sha256'],
              report.get('tools',{}),sim,waves]
    return hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]


def required_tools(mode, sim, prefix):
    if mode=='check-vectors': return ['git']
    tools=['git',prefix+'gcc',prefix+'objcopy']
    if mode!='baseline': tools.append(prefix+'objdump')
    if mode=='doctor': return tools
    tools.append('make')
    if sim=='vcs': tools.append('vcs')
    elif sim=='iverilog' or mode=='baseline': tools+=['iverilog','vvp']
    else: tools+=['verilator','g++']
    return tools


def matrix_sources(installed):
    # Legacy install/tb contains tb_top and must not join this independent TB.
    return sorted(p for p in installed.rglob('*') if p.suffix in ['.v','.sv'])+[TESTS/'tb_accel_soc.sv']


def vcs_build_command(cache, filelist, includes, waves):
    return ['vcs','-full64','-sverilog','-timescale=1ns/10ps',
            '-top','tb_accel_soc','+define+DISABLE_SV_ASSERTION=1',
            *(['-debug_access+all'] if waves else []),
            *['+incdir+'+str(p) for p in includes],'-f',str(filelist),
            '-Mdir='+str(cache/'csrc'),'-o',str(cache/'accel_soc')]


def build_simulator(sim, cache, filelist, includes, waves, out):
    binary=cache/('accel_soc.vvp' if sim=='iverilog' else 'accel_soc')
    if sim=='vcs':
        # A failed VCS link can leave a binary behind. Only reuse a completed build.
        receipt=cache/'vcs-build.json'
        valid=False
        if binary.is_file() and receipt.is_file():
            try:
                valid=json.loads(receipt.read_text())['binary_sha256']==sha(binary)
            except (ValueError,KeyError,TypeError):
                pass
        if not valid:
            if receipt.exists(): receipt.unlink()
            run(vcs_build_command(cache,filelist,includes,waves),cache,out/'simulator-build.log')
            receipt.write_text(json.dumps({'binary_sha256':sha(binary)})+'\n')
        return binary,[str(binary)]
    if sim=='verilator':
        if not binary.exists():
            run(['verilator','--binary','--timing',*(['--trace'] if waves else []),'-j','2','-Wno-fatal',
                 '--top-module','tb_accel_soc','-Mdir',str(cache),'-o','accel_soc',
                 '-DDISABLE_SV_ASSERTION=1',*['-I'+str(p) for p in includes],'-f',str(filelist)],
                ROOT,out/'simulator-build.log')
        return binary,[str(binary)]
    run(['iverilog','-g2012','-s','tb_accel_soc','-DDISABLE_SV_ASSERTION=1',
         *['-I'+str(p) for p in includes],'-o',str(binary),'-f',str(filelist)],ROOT,out/'simulator-build.log')
    return binary,['vvp',str(binary)]


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


def firmware_memory(sections, symbols, stack_files):
    sizes = {name: int(size, 16) for name, size in
             re.findall(r'^\s*\d+\s+(\.[\w.]+)\s+([0-9a-fA-F]+)\s', sections, re.M)}
    addresses = {}
    for line in symbols.splitlines():
        fields = line.split()
        if fields and fields[-1] in ['__bss_start', '__bss_end', '__stack_top']:
            addresses[fields[-1]] = int(fields[0], 16)
    if set(addresses) != {'__bss_start', '__bss_end', '__stack_top'}:
        raise ValueError('firmware memory symbols are missing')
    if sizes.get('.data', 0) != 0:
        raise ValueError('startup does not copy initialized DTCM data')
    frames = []
    for path in stack_files:
        for line in path.read_text().splitlines():
            source, size, kind = line.rsplit('\t', 2)
            frames.append(dict(source=source, bytes=int(size), kind=kind))
    available = addresses['__stack_top'] - addresses['__bss_end']
    if not frames or available <= 0 or any(f['kind'] != 'static' for f in frames):
        raise ValueError('firmware stack usage is unavailable or DTCM is exhausted')
    return dict(itcm_bytes=sizes.get('.text', 0), itcm_capacity_bytes=65536,
                itcm_remaining_bytes=65536 - sizes.get('.text', 0),
                data_bytes=sizes.get('.data', 0), bss_bytes=sizes.get('.bss', 0),
                dtcm_capacity_bytes=65536, stack_top=addresses['__stack_top'],
                stack_capacity_after_bss_bytes=available, stack_top_guard_bytes=16,
                stack_frames=frames, max_static_stack_frame_bytes=max(f['bytes'] for f in frames),
                stack_usage_scope='GCC static per-function frames; runtime high-water mark not measured')


def compile_firmware(out, prefix, schedule='baseline', optimization='-Os', experiment='none', report=None):
    target = out/'accel_soc'
    config = contract.configuration(schedule, optimization, experiment)
    sources = [TESTS/'firmware'/name for name in ['start.S','main.c','accel.c']]
    command = [prefix+'gcc','-march=rv32imac_zicsr2p0_zifencei2p0','-mabi=ilp32',
         optimization,*contract.compiler_defines(config),'-fstack-usage',
         '-ffreestanding','-fno-builtin','-msmall-data-limit=0',
         '-nostdlib','-nostartfiles','-static','-mcmodel=medany','-Wl,--no-relax',
         '-T',str(TESTS/'firmware/link.ld'),*[str(p) for p in sources],'-o',str(target)]
    run(command,out,out/'firmware-build.log')
    run([prefix+'objcopy','-O','verilog',str(target),str(target)+'.verilog'],ROOT,out/'objcopy.log')
    image = Path(str(target)+'.verilog')
    image.write_text(image.read_text().replace('@800','@000'))
    dump = run([prefix+'objdump','--disassemble-all',str(target)],ROOT,out/'firmware.dump')
    if not re.search(r'80000086\s+<write_tohost>', dump):
        raise ValueError('firmware completion address is not 0x80000086')
    sections = run([prefix+'objdump','-h',str(target)],ROOT,out/'firmware-sections.log')
    symbols = run([prefix+'objdump','-t',str(target)],ROOT,out/'firmware-symbols.log')
    identity = dict(configuration=config, command=[str(c) for c in command], cwd=str(out),
                    source_sha256={p.name:sha(p) for p in (TESTS/'firmware').iterdir() if p.is_file()},
                    elf_sha256=sha(target), image_sha256=sha(image),
                    memory=firmware_memory(sections, symbols, sorted(out.glob('*.su'))))
    (out/'firmware-build.json').write_text(json.dumps(identity,indent=2)+'\n')
    if report is not None:
        report.update(firmware_build=identity, firmware_sha256=identity['source_sha256'],
                      firmware_elf_sha256=identity['elf_sha256'],
                      firmware_image_sha256=identity['image_sha256'])
    return target


def verify_submodule(root, submodule):
    # git -C in an empty submodule directory otherwise silently finds the parent.
    if not (submodule/'.git').exists():
        raise ValueError('E203 submodule is not initialized; run git submodule update --init --recursive')
    top=subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=submodule,universal_newlines=True).strip()
    if Path(top).resolve()!=submodule.resolve():
        raise ValueError('E203 submodule is not initialized as its own repository')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=submodule,universal_newlines=True).strip()
    pin=subprocess.check_output(['git','ls-tree','HEAD',submodule.relative_to(root).as_posix()],
                                cwd=root,universal_newlines=True).split()
    if len(pin)<3 or pin[0]!='160000' or pin[2]!=commit:
        raise ValueError('E203 commit does not match the main repository gitlink')
    return commit


def baseline(out, prefix, sim='iverilog'):
    vsim=E203/'vsim'
    results=[]
    inputs={}
    for name in ['rv32ui-p-add','accel_mmio','accel_compute','accel_multigroup','accel_repeat_x']:
        if name.startswith('rv32'):
            target=E203/'riscv-tools/riscv-tests/isa/generated'/name
        else:
            target=out/name
            run([prefix+'gcc','-march=rv32imac_zicsr2p0_zifencei2p0','-mabi=ilp32',
                 '-nostdlib','-nostartfiles','-static','-mcmodel=medany','-Wl,--no-relax',
                 '-T',str(E203/'riscv-tools/riscv-tests/env/p/link.ld'),
                 str(TESTS/(name+'.S')),'-o',str(target)],ROOT,out/(name+'-build.log'))
            run([prefix+'objcopy','-O','verilog',str(target),str(target)+'.verilog'],ROOT,out/(name+'-objcopy.log'))
            image=Path(str(target)+'.verilog')
            image.write_text(image.read_text().replace('@800','@000'))
        log=run(['make','run_test','SIM='+sim,'DUMPWAVE=0','TESTCASE='+str(target)],
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
    parser.add_argument('--mode',choices=['doctor','baseline','synthetic','real','vectors','check-vectors'],default='synthetic')
    parser.add_argument('--tasks',type=int,choices=range(1,13),default=1)
    parser.add_argument('--vectors',type=Path)
    parser.add_argument('--sim',choices=['verilator','iverilog','vcs'],default='verilator')
    parser.add_argument('--cross-prefix',default='riscv64-unknown-elf-')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--waves',action='store_true')
    parser.add_argument('--accel-waves',action='store_true',
                        help='dump accelerator-only VCD during measured task windows for activity analysis')
    parser.add_argument('--bias-storage', choices=['reg', 'sram'], default='reg',
                        help='identify the installed xu candidate; sram adds a fixed busy-cycle check')
    parser.add_argument('--max-cycles',type=int,default=200000000)
    contract.add_arguments(parser)
    args=parser.parse_args()
    if args.max_cycles < 1:
        parser.error('--max-cycles must be positive')
    if args.waves and args.accel_waves:
        parser.error('choose --waves or --accel-waves')
    trace_enabled = args.waves or args.accel_waves
    out=(args.out or ROOT/'build/e203'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')).resolve()
    out.mkdir(parents=True,exist_ok=False)
    selected_sim='iverilog' if args.mode=='baseline' and args.sim=='verilator' else args.sim
    report={'status':'RUNNING','mode':args.mode,'tasks':args.tasks,'simulator':selected_sim,
            'bias_storage':args.bias_storage,
            'firmware_schedule':args.firmware_schedule,'firmware_opt':args.firmware_opt,
            'firmware_experiment':args.firmware_experiment,
            'transaction_contract':contract.task_contract(args.firmware_schedule),
            'contract_sha256':sha(Path(contract.__file__)),
            'wave_scope':'accelerator measured windows' if args.accel_waves else 'full TB' if args.waves else 'none',
            'scope':'development platform; TB shared-memory preload excluded; no official PPA/accuracy claim'}
    try:
        required=required_tools(args.mode,selected_sim,args.cross_prefix)
        report['tools']={name:shutil.which(name) for name in required}
        missing=[n for n,p in report['tools'].items() if p is None]
        if missing: raise RuntimeError('missing tools: '+', '.join(missing))
        report['versions']={}
        for name in ['iverilog',args.cross_prefix+'gcc','verilator','g++','vcs']:
            if name in report['tools']:
                flag='-ID' if name=='vcs' else '-V' if name=='iverilog' else '--version'
                version=run([name,flag],ROOT,out/(name.replace('/','_')+'-version.log')).splitlines()
                report['versions'][name]=version if name=='vcs' else version[:3]
        if selected_sim=='vcs' and args.mode not in ['doctor','check-vectors']:
            for name in ['gcc','g++']:
                if shutil.which(name):
                    report['versions'][name]=run([name,'--version'],ROOT,out/(name+'-version.log')).splitlines()[:3]
        report['main_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,universal_newlines=True).strip()
        if args.mode!='check-vectors': report['e203_commit']=verify_submodule(ROOT,E203)
        if args.mode=='check-vectors':
            directory=args.vectors.resolve() if args.vectors else out/'vectors'
            if args.vectors is None: report['fixture']=load_fixture(directory,args.tasks)
            report['layers']=check_vectors(directory,args.tasks)
            report['outputs']=args.tasks*25344
            report['runner_sha256']=sha(Path(__file__))
            report['scope']='exact integer XW+b check; no RTL or floating-point accuracy claim'
            report['status']='PASS'
        elif args.mode=='doctor':
            firmware=compile_firmware(out,args.cross_prefix,args.firmware_schedule,
                                      args.firmware_opt,args.firmware_experiment,report)
            report['runner_sha256']=sha(Path(__file__))
            report['scope']='development toolchain/submodule preflight; actual RV32 firmware build; no simulation'
            report['status']='PASS'
        else:
            # Always refresh the installed RTL, following the repository quickstart.
            run(['make','clean'],E203/'vsim',out/'clean.log')
            run(['make','install'],E203/'vsim',out/'install.log')
            installed=E203/'vsim/install/rtl'
            report['source_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sorted(installed.rglob('*')) if p.suffix in ['.v','.sv']}
            if args.mode=='baseline':
                report.update(baseline(out,args.cross_prefix,selected_sim))
            else:
                if args.mode=='synthetic':
                    directory=out/'vectors'
                    synthetic(directory,args.tasks)
                elif args.mode=='real':
                    directory=out/'vectors'
                    report['fixture']=load_fixture(directory,args.tasks)
                else:
                    if args.vectors is None: raise ValueError('--vectors is required')
                    directory=args.vectors.resolve()
                report['vectors']={}
                for layer in range(args.tasks):
                    for name,bits,count in [('x',16,6336),('w',16,16384),('bias',40,256),('y',48,25344)]:
                        path=directory/f'layer_{layer:02d}'/(name+'.mem')
                        read_mem(path,bits,count)
                        report['vectors'][str(path.relative_to(directory))]=sha(path)
                firmware=compile_firmware(out,args.cross_prefix,args.firmware_schedule,
                                          args.firmware_opt,args.firmware_experiment,report)
                report['runner_sha256']=sha(Path(__file__))
                installed=E203/'vsim/install/rtl'
                sources=matrix_sources(installed)
                report['source_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sources}
                key=build_key(report,selected_sim,trace_enabled)
                cache=ROOT/'build/e203'/('sim-'+key)
                cache.mkdir(parents=True,exist_ok=True)
                filelist=cache/'rtl.f'
                filelist.write_text('\n'.join(str(p) for p in sources)+'\n')
                includes=[str(installed/p) for p in ['core','perips','perips/apb_i2c']]
                binary,command=build_simulator(selected_sim,cache,filelist,includes,trace_enabled,out)
                report['simulator_sha256']=sha(binary)
                print(f'Running {args.mode}: {args.tasks} tasks; logs: {out}',flush=True)
                log=run(command+[f'+TESTCASE={firmware}',f'+VECTORS={directory}',
                        f'+TASKS={args.tasks}',f'+DUMPWAVE={2 if args.accel_waves else int(args.waves)}',
                        f'+MAX_CYCLES={args.max_cycles}'],out,out/'simulation.log',7200)
                report['layers']=check_log(log,args.tasks)
                for layer, counters in zip(report['layers'], check_performance(log, report['layers'],args.firmware_schedule)):
                    layer['performance'] = counters
                    if args.bias_storage == 'sram':
                        layer['sram_bias_contract'] = check_sram_bias_latency(
                            counters, args.firmware_schedule)
                report['outputs']=args.tasks*25344
                report['write_words']=args.tasks*50688
            report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL'
        report['error']=str(exc)
        print(str(exc),file=sys.stderr)
    report['log_sha256']={p.name:sha(p) for p in sorted(out.glob('*.log'))}
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{report["status"]}: {out / "result.json"}',flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
