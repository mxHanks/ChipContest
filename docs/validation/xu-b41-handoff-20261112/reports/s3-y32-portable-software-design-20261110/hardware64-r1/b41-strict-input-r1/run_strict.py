#!/usr/bin/env python3
"""Compile and execute the published CPU64 workload with CPU SVA enabled."""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def run(command,cwd,log,timeout):
    with log.open('x') as stream:
        stream.write(json.dumps(dict(argv=[str(x) for x in command]))+'\n')
        stream.flush()
        result=subprocess.run(command,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{log.name} exited {result.returncode}')
    return log.read_text().split('\n',1)[1]


def measurements(checker,raw,measured):
    fields=['call','layer','warmup','config_begin','clear_discovered','compute_first','compute_last',
            'discovered','report_accept','report_retire','retired','itcm_accesses','clear_reads','compute_reads']
    records=checker.records(raw,'XU_SW64',fields)
    layers=[(True,measured['warmup']['layers'][0]),*[(False,v) for v in measured['layers']]]
    if len(records)!=len(layers):
        raise ValueError('Missing per-task software timeline')
    observations=[]
    for call,(row,(warmup,layer)) in enumerate(zip(records,layers),1):
        w=layer['window']
        if row['call']!=call or row['layer']!=layer['layer'] or row['warmup']!=int(warmup):
            raise ValueError('Software timeline task identity mismatch')
        if not (w['clear_done']<=row['clear_discovered']<=row['config_begin']<=w['start']<=
                w['first_request']<=row['compute_first']<=row['compute_last']<=w['last_y_response']<
                w['done']<=row['discovered']<=row['report_accept']<=row['report_retire']):
            raise ValueError('Software timing order is inconsistent with hardware')
        observations.append(dict(**row,clear_begin=w['clear_request'],clear_end=w['clear_done'],
            start=w['start'],source_begin=w['first_request'],source_accepted=w['first_accept'],
            wb_window=layer['channel']['wb_cycles'],xy_window=layer['channel']['xy_window'],
            final_y_response=w['last_y_response'],hardware_done=w['done'],
            discovery_delay=row['discovered']-w['done'],report_delay=row['report_retire']-w['done'],
            software_control_cycles=row['report_retire']-w['clear_request']+1,
            descriptor_submission_cycles=w['start']-row['config_begin']+1))
    return observations


def main(cpu):
    prepared=json.loads((ROOT/'prepared.json').read_text())
    source=ROOT/'source'
    assert {str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}==prepared['source_sha256']
    assert sha(ROOT/'firmware/dma_day_soc.verilog')==prepared['original_firmware_image_sha256']
    assert cpu in os.sched_getaffinity(0) and len(os.sched_getaffinity(0))==3
    out=ROOT/'native-r1/campaign'
    out.mkdir()
    rtl=source/'rtl'
    files=sorted(p for p in rtl.rglob('*') if p.suffix in ('.v','.sv'))+[source/'tests/tb_dma64_soc.sv']
    filelist=out/'rtl.f'
    filelist.write_text(''.join('"'+str(p)+'"\n' for p in files))
    binary=out/'obj/dma64_soc'
    includes=[rtl/'core',rtl/'perips',rtl/'perips/apb_i2c',source/'tests']
    common=['--timing','--assert','--top-module','tb_dma64_soc','-DXU_MATRIX_DMA','-DXU_MATRIX_DMA64',
            '-DD4K_THROTTLE=7',*['-I'+str(p) for p in includes],'-f',str(filelist)]
    build=['verilator','--binary','-CFLAGS','-std=gnu++20','-j','2','-Wno-fatal',
           '-Mdir',str(binary.parent),'-o',binary.name,*common]
    assert not any('DISABLE_SV_ASSERTION' in x for x in build)
    record=dict(status='RUNNING',build_argv=build,source_sha256=prepared['source_sha256'],
                evidence_scope='Real CPU64 strict RTL; not mapped power, STA or official score',variants={})
    save(out/'result.json',record)
    try:
        print('CPU64_STRICT_PREPROCESS',flush=True)
        preprocessed=run(['verilator','-E',*common],out,out/'preprocessed.sv',120)
        assertion_count=len(re.findall(r'assert\s+property\b',preprocessed))
        if not assertion_count:
            raise ValueError('CPU assertion properties are absent after preprocessing')
        record['preprocessed_assert_property_count']=assertion_count
        record['preprocessed_sha256']=sha(out/'preprocessed.sv')
        print('CPU64_STRICT_BUILD',assertion_count,flush=True)
        run(build,out,out/'build.log',1200)
        record['simulator_sha256']=sha(binary)
        spec=importlib.util.spec_from_file_location('sealed_cpu64_checker',source/'check_results.py')
        checker=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        for name, build_receipt in prepared['software'].items():
            image = ROOT/'firmware'/name/'dma64_soc'
            if sha(image) != build_receipt['elf_sha256'] or sha(image.with_suffix('.verilog')) != build_receipt['image_sha256']:
                raise ValueError('Changed B41 replay firmware: ' + name)
            argv = ['taskset','-c',str(cpu),str(binary),f'+TESTCASE={image}',
                    f'+VECTORS={ROOT}/vectors','+TASKS=12','+ROWS=8','+WARMUP=1',
                    '+MAX_CYCLES=20000000','+FIRST_SOURCE_STALL=0','+DUMPWAVE=0']
            print('B41_CPU64_FULL12_START',name,flush=True)
            log = out/(name+'.log')
            raw = run(argv,out,log,900)
            measured = checker.check_log(raw,12,8,True)
            timeline = measurements(checker,raw,measured)
            record['variants'][name] = dict(measurements=measured,timeline=timeline,argv=argv,
                firmware_image_sha256=sha(image.with_suffix('.verilog')),log_sha256=sha(log))
            save(out/'result.json',record)
            print('B41_CPU64_FULL12_PASS',name,measured['outputs'],measured['principal_cycles'],
                  measured['including_gap_cycles'],flush=True)
        if {str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}!=prepared['source_sha256']:
            raise ValueError('Source changed during strict run')
        record['status']='PASS_STRICT_CPU64_FULL12'
        print('B41_CPU64_CAMPAIGN_PASS',len(record['variants']),flush=True)
    except Exception as error:
        record.update(status='FAIL',error=str(error))
        raise
    finally:
        save(out/'result.json',record)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim-cpu',type=int,required=True)
    main(parser.parse_args().sim_cpu)
