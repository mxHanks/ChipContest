#!/usr/bin/env python3
"""Build immutable CPU64 profiles and check the new error-drain seam."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil

from run_validation import configs, header, run, save

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def build(out,prefix,software_source=None,names=None):
    out.mkdir(parents=True,exist_ok=False)
    source=out/'software'
    shutil.copytree(software_source or ROOT/'software',source)
    test=out/'drain_model.c'
    shutil.copyfile(ROOT/'tests/drain_model.c',test)
    host=['cc','-std=c11','-O2','-Wall','-Wextra','-Werror']
    binary=out/'drain_model'
    run([*host,'-I',source,test,'-o',binary],out/'drain-build.log')
    positive=run([binary],out/'drain-contract.log')
    if positive.stdout!='DRAIN_CONTRACT_PASS cases=9\n':
        raise ValueError('Error-drain coverage incomplete')
    original=(source/'ffn_error_drain.h').read_text()
    negative={}
    for name,before,after in [
        ('ignore_drain_busy','if (!(status & FFN_BUSY))','if ((status & FFN_ERROR) || !(status & FFN_BUSY))'),
        ('republish_error','const uint32_t status = FFN_WAIT_READ_STATUS();',
         'const uint32_t status = FFN_WAIT_READ_STATUS(); FFN_WAIT_REPORT_ERROR();')]:
        folder=out/name;folder.mkdir()
        assert original.count(before)==1
        (folder/'ffn_error_drain.h').write_text(original.replace(before,after,1))
        shutil.copyfile(source/'ffn_wait.h',folder/'ffn_wait.h')
        program=folder/'drain_model'
        run([*host,'-I',folder,test,'-o',program],folder/'build.log')
        observed=run([program],folder/'run.log',allowed=(1,))
        assert 'DRAIN_FAIL' in observed.stdout
        negative[name]=dict(native_exit=observed.returncode,output=observed.stdout)
    rows={x['name']:x for x in configs()}
    selected=['tight','fixed_32','fixed_64','fixed_256','phased_64_fast4','backoff_8_256_fast4']
    builds={}
    startup=source/'reference_firmware'
    def compile_one(name,config,optimization,driver):
        if names and name not in names:
            return
        folder=out/name;folder.mkdir()
        selected_header=folder/'selected_config.h'
        selected_header.write_text(config)
        target=folder/'dma64_soc'
        command=[prefix+'gcc','-march=rv32imac_zicsr2p0_zifencei2p0','-mabi=ilp32','-'+optimization,
                 '-fstack-usage','-ffreestanding','-fno-builtin','-msmall-data-limit=0','-nostdlib','-nostartfiles',
                 '-static','-mcmodel=medany','-Wl,--no-relax','-Wl,--build-id=none','-Wall','-Wextra','-Werror',
                 '-I',folder,'-I',source,'-T',startup/'link.ld',startup/'start.S',driver,'-o',target]
        run(command,folder/'build.log')
        dump=run([prefix+'objdump','-d',target],folder/'disassembly.log').stdout
        assert re.search(r'80000086\s+<write_tohost>',dump) and not re.search(r'\bwfi\b',dump)
        assert len(re.findall(r'\bfence\b',dump))>=4
        size=run([prefix+'size',target],folder/'size.log').stdout.splitlines()[-1].split()
        text_bytes,data,bss=map(int,size[:3]);assert data==bss==0 and text_bytes<65536
        run([prefix+'objcopy','-O','verilog',target,folder/'dma64_soc.verilog'],folder/'objcopy.log')
        image=folder/'dma64_soc.verilog';image.write_text(image.read_text().replace('@800','@000'))
        builds[name]=dict(optimization=optimization,text_bytes=text_bytes,elf_sha256=sha(target),image_sha256=sha(image),
            selected_config_sha256=sha(selected_header),source_sha256=sha(driver),
            stack_usage={f.name:f.read_text() for f in folder.glob('*.su')},command=[str(x) for x in command])
    for name in selected:
        config=header(rows[name]).replace('REFERENCE BUILD ONLY. Synthetic screening does not select a 64-PE config.',
             'CPU64 development candidate; immutable offline config, not a final power-selected configuration.')
        compile_one(name+'-O2',config,'O2',source/'dma64_driver.c')
    # A compiler/driver control isolates the change from the published GCC14 ELF.
    published=ROOT/'hardware64-r1/extracted/delivery-final-r2/cpu/source/tests/dma_day_main.c'
    shutil.copyfile(published,out/'published_driver.c')
    compile_one('published-gcc15-O2',header(rows['tight']),'O2',out/'published_driver.c')
    for optimization in ('O3','Os'):
        compile_one('fixed_64-'+optimization,header(rows['fixed_64']),optimization,source/'dma64_driver.c')
    # Test a distinct CLEAR strategy; compute strategy remains identical.
    clear=header(rows['fixed_64']).replace('{1000000u, 1000000u, 0u, 0u, 0u, FFN_POLL_TIGHT}',
             '{1000000u, 1000000u, 8u, 8u, 0u, FFN_POLL_FIXED}')
    compile_one('clear8_compute64-O2',clear,'O2',source/'dma64_driver.c')
    if names and set(builds)!=set(names):
        raise ValueError('Unknown or duplicate selected build names')
    groups={}
    for name,row in builds.items():groups.setdefault(row['image_sha256'],[]).append(name)
    record=dict(status='PASS_CPU64_TARGET_BUILDS_ONLY',host_drain_cases=9,negative_controls=negative,
        compiler=run([prefix+'gcc','--version'],out/'compiler.log').stdout,builds=builds,
        identical_loaded_image_groups=list(groups.values()),
        source_sha256={str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file()},
        scope='Real a80dd18 ABI, static adapters and existing wait source; compile/host seam only. CPU64 execution and physical energy pending.')
    save(out/'result.json',record)
    print(json.dumps(dict(status=record['status'],host_drain_cases=9,
        builds={k:dict(text_bytes=v['text_bytes'],image_sha256=v['image_sha256']) for k,v in builds.items()},
        identical_loaded_image_groups=record['identical_loaded_image_groups']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cross-prefix',default='/tmp/xu-riscv-toolchain/bin/riscv-none-elf-')
    parser.add_argument('--software-source',type=Path)
    parser.add_argument('--names',nargs='+')
    args=parser.parse_args()
    build(args.out.resolve(),args.cross_prefix,args.software_source,args.names)
