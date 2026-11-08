#!/usr/bin/env python3
"""S3 full-SoC activity generation seam and generic functional prototype.

Python3.6+ for generation/protocol preparation. Use the private Python3.12 for
large native runs. No macro model, source review or functional PASS qualifies PPA.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--profile',choices=['s3-y32-bias-sram','s3-y32-bias-registers'],required=True)
    parser.add_argument('--model-kind',choices=['generic-prototype','vendor-rtl-activity'],required=True)
    parser.add_argument('--macro-model',type=Path,required=True)
    parser.add_argument('--macro-model-sha256',required=True)
    parser.add_argument('--schedule',required=True)
    parser.add_argument('--layers',default='0')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--waves',action='store_true',help='full DUT VCD including separate clear and payload windows')
    parser.add_argument('--max-cycles',type=int,default=5000000)
    parser.add_argument('--cross-prefix',default='/opt/eda/xilinx/2025.2/Vitis/gnu/riscv/lin/bin/riscv64-unknown-elf-')
    args=parser.parse_args(argv)
    repo,out=args.repo.resolve(),args.out.resolve()
    if out.exists():raise ValueError('activity output directory exists')
    sys.path.insert(0,str(repo/'tools/scripts'))
    adapter=load('_s3_activity_adapter',repo/'tools/ppa/s3_soc_activity_profile.py')
    campaign=load('_s3_activity_campaign',repo/'tools/ppa/s3_task_campaign.py')
    extension=adapter.S3ActivityExtension(repo,args.profile,args.macro_model,args.macro_model_sha256,args.model_kind,args.schedule)
    baseline=load('_s3_activity_baseline',repo/'tools/ppa/s3_soc_implementation.py')
    baseline.baseline_identity(extension.ppa,extension.freeze)
    if args.prepare_only:
        out.mkdir(parents=True);source=out/'source';source.mkdir()
        campaign.snapshot_inputs(repo,source);extension.snapshot(repo,source)
        sys.path.insert(0,str(source/'tools/scripts'));sys.path.insert(0,str(source))
        clear=load('_s3_activity_clear',source/'tools/ppa/s3_task_clear_protocol.py')
        original=(source/'tests/e203/tb_accel_soc.sv').read_text()
        text=campaign.instrument_tb(original,clear.observer_declarations())
        controls=argparse.Namespace(platform_clocks='development',first_source_stall=0,platform_assertions=True)
        text=extension.testbench(text,source,out,controls)
        (out/'tb.sv').write_text(text)
        sources=extension.sources(sorted(p for p in (source/'rtl').rglob('*') if p.suffix in ('.v','.sv'))+[out/'tb.sv'],source,out)
        (out/'rtl.f').write_text(''.join(str(p)+'\n' for p in sources))
        receipt=dict(status='GENERIC_NON_PPA_PREPARED' if args.model_kind=='generic-prototype' else 'VENDOR_RTL_ACTIVITY_PREPARED_NOT_QUALIFIED',
            runtime_python=sys.version,activity_extension=extension.metadata(source),
            generated_tb_sha256=campaign.sha(out/'tb.sv'),rtl_sources_sha256={str(p):campaign.sha(p) for p in sources},
            original_assertions_retained=True,simulation='NOT_RUN',power_area_timing='NOT_MEASURED',qualification='NOT_QUALIFIED')
        campaign.write(out/'result.json',receipt)
        print(receipt['status'],str(out/'result.json'),flush=True)
        return 0
    code=campaign.main(['--repo',str(repo),'--out',str(out),'--schedule',args.schedule,'--layers',args.layers,
        '--bias-kind','sram' if args.profile=='s3-y32-bias-sram' else 'registers','--simulator','vcs',
        '--platform-assertions','--max-cycles',str(args.max_cycles),'--cross-prefix',args.cross_prefix]+
        (['--waves'] if args.waves else []),extension=extension)
    receipt=json.loads((out/'result.json').read_text())
    receipt['activity_collection_status']=('GENERIC_NON_PPA_FUNCTIONAL_TASKS_COMPLETE' if args.model_kind=='generic-prototype'
                                         else 'VENDOR_RTL_ACTIVITY_REVIEW_PENDING') if code==0 else 'FAILED'
    receipt['qualification']='NOT_QUALIFIED'
    campaign.write(out/'result.json',receipt)
    print(receipt['activity_collection_status'],str(out/'result.json'),flush=True)
    return code


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError) as error:
        print('FAIL: '+str(error),file=sys.stderr);sys.exit(1)
