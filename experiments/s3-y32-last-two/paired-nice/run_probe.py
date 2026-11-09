#!/usr/bin/env python3
"""Run isolated pair-transfer RTL evidence; never synthesis or CPU/SoC changes.

Generated/LinearRowPairPrototype must be regenerated from the same campaign's
rowpair source. --vectors points at a validated 99x64 by64x256 task0 directory.
All subprocess commands, raw output, source identities and exit codes are saved.
"""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,re,subprocess,time


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out','--output',dest='output',type=Path,required=True)
    ap.add_argument('--repo',type=Path,required=True,help='Pinned baseline ChipContest checkout, read only')
    ap.add_argument('--generated-rowpair',type=Path,required=True,help='Generated LinearRowPairPrototype SV directory')
    ap.add_argument('--vectors',type=Path,required=True,help='Speech task0 99x64/64x256 vectors, not synthetic corner data')
    args=ap.parse_args();variant=Path(__file__).resolve().parent
    root=args.repo.resolve();out=args.output.resolve()
    vectors=args.vectors.resolve()
    if not str(vectors).isascii() or len(str(vectors))>128:
        raise ValueError('The testbench vector path must be ASCII and at most 128 bytes')
    out.mkdir(parents=True,exist_ok=False)
    rtl=root/'third-party/e203_hbirdv2/rtl/e203'
    generated=sorted(args.generated_rowpair.resolve().glob('*.sv'))
    if not generated:raise ValueError('No generated rowpair RTL')
    wrapper_names=['BiasSramPrefetch.sv','BiasBankCache.sv','LinearAutoGroupCore.sv','LinearCachedCore.sv',
                   'LinearComputeCore.sv','DotProductEngine.sv','MacController.sv','MacPEArray.sv','MacPE.sv',
                   'XRowBuffer.sv','WeightBankArray.sv','WeightBank.sv','Sram1024x16.sv','mem_1024x16.sv','accel_icb_slave.v']
    wrapper_sources=[rtl/'perips'/n for n in wrapper_names]
    legacy_modules=['tb_nice_ready_errors','tb_nice_ready_disabled','tb_nice_direct_errors',
                    'tb_ready_wrapper_disabled','tb_xu_nice_ready_wrapper']
    source=[variant/'xu_nice_drain8.v',variant/'tb_nice_pair_errors.sv',
            variant/'tb_rowpair_nice_real.sv',variant/'rowpair_direct_bridge.v',
            Path(__file__).resolve(),*generated,*[vectors/n for n in ['x.mem','w.mem','bias.mem','y32.mem']],
            *[root/'tests/e203'/(n+'.sv') for n in legacy_modules],*wrapper_sources,
            rtl/'core/e203_defines.v',rtl/'core/config.v']
    before={str(p):sha(p) for p in source};records=[]
    def run(name,cmd,marker):
        start=time.time();p=subprocess.run([str(x) for x in cmd],cwd=root,text=True,capture_output=True,timeout=180)
        (out/(name+'.log')).write_text(p.stdout+p.stderr)
        r={'name':name,'command':[str(x) for x in cmd],'returncode':p.returncode,'seconds':time.time()-start,
           'marker':marker,'marker_found':marker in p.stdout,'pass':p.returncode==0 and marker in p.stdout}
        records.append(r);return r
    flags=['iverilog','-g2012','-I'+str(rtl/'core')]
    compiles=[('unit-compile',flags+['-s','tb_nice_pair_errors','-o',out/'unit.vvp',source[1],source[0]],''),
              ('disabled-compile',flags+['-s','tb_nice_pair_errors','-Ptb_nice_pair_errors.PAIR_EN=0','-o',out/'disabled.vvp',source[1],source[0]],''),
              ('real-compile',flags+['-s','tb_rowpair_nice_real','-o',out/'real.vvp',source[2],source[3],source[0],*generated],'')]
    for module in legacy_modules:
        extras=wrapper_sources if module in ['tb_ready_wrapper_disabled','tb_xu_nice_ready_wrapper'] else []
        compiles.append((module+'-compile',flags+['-s',module,'-o',out/(module+'.vvp'),
            root/'tests/e203'/(module+'.sv'),source[0],*extras],''))
    for job in compiles:
        if not run(*job)['pass']:break
    else:
        jobs=[('unit',['vvp',out/'unit.vvp'],'NICE_PAIR_PASS cases=613 counts=64 write_error_positions=512'),
              ('disabled',['vvp',out/'disabled.vvp'],'NICE_PAIR_DISABLED_PASS no_side_effect=1')]
        for name,period,lat in [('fast',1,0),('service60',1,3),('service80',1,5),('mixed',3,2)]:
            for mode in [0,1]:
                jobs.append((f'real-{name}-{mode}',['vvp',out/'real.vvp',f'+MODE={mode}',f'+CMD_PERIOD={period}',f'+WRITE_LATENCY={lat}'],
                    'ROWPAIR_NICE_REAL_PASS rows=99 outputs=25344'))
        for mode in [0,1]:
            jobs.append((f'task0-{mode}',['vvp',out/'real.vvp',f'+MODE={mode}','+VECTOR_DIR='+str(vectors)],
                'ROWPAIR_NICE_REAL_PASS rows=99 outputs=25344'))
        for fail in [15,511]:
            jobs.append((f'real-error-{fail}',['vvp',out/'real.vvp',f'+FAIL_WRITE={fail}'],
                f'ROWPAIR_NICE_REAL_ERROR_PASS error_index={fail} writes={fail+1} responses={fail+1}'))
        legacy_markers=['NICE_READY8_PASS cases=418','NICE_READY8_DISABLED_PASS','NICE_DIRECT_ERRORS_PASS cases=19',
                        'READY_WRAPPER_DISABLED_PASS','READY_WRAPPER_PASS real_groups=32 real_y32_lanes=256']
        for module,marker in zip(legacy_modules,legacy_markers):
            jobs.append((module,['vvp',out/(module+'.vvp')],marker))
        jobs.append(('legacy-pop-race',['vvp',out/'tb_xu_nice_ready_wrapper.vvp','+POP_RACE'],'READY_POP_RACE_PASS'))
        for phase in [1,2,3]:
            jobs.append((f'legacy-reset-{phase}',['vvp',out/'tb_xu_nice_ready_wrapper.vvp',f'+RESET_PHASE={phase}'],f'DIRECT_RESET_PASS phase={phase}'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda job:run(*job),jobs))
    after={str(p):sha(p) for p in source}
    result={'vector_scope':{'corner':'synthetic extreme signed16/40 domain, positive/negative ties; vector_mode=0',
            'task0':'published speech task0 x/w/bias with 25344 y32.mem plus independent64bit MAC oracle; vector_mode=1'},
            'scope':'4-state Icarus module RTL only, real generated MAC, checked synthetic LSU sink; no CPU, MMIO, clear-window, area, STA or independent DMA claim',
            'baseline_parent':'e984bad936855debfc5fa01f04bcbc6252d59ecc','baseline_e203':'dba1b5f82395b762f126387a1840e6a843e3a01a',
            'source_before':before,'source_after':after,'source_drift':[p for p in before if before[p]!=after[p]],'runs':sorted(records,key=lambda x:x['name'])}
    matrix=[]
    pattern=re.compile(r'mode=(\d+).*?requests=(\d+).*?compute_drain_cycles=(\d+).*?cmd_period=(\d+).*?write_latency=(\d+).*?vector_mode=(\d+)')
    for r in result['runs']:
        m=pattern.search((out/(r['name']+'.log')).read_text())
        if m:matrix.append(dict(zip(['mode','requests','cycles','cmd_period','write_latency','vector_mode'],map(int,m.groups())),name=r['name']))
    result['matrix']=matrix;result['pass']=not result['source_drift'] and len(records)==31 and all(r['pass'] for r in records)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'pass':result['pass'],'source_drift':result['source_drift'],'matrix':matrix},indent=2))
    return 0 if result['pass'] else 1

if __name__=='__main__':raise SystemExit(main())
