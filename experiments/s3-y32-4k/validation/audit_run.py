#!/usr/bin/env python3
"""Read-only, independently gated selection audit of a completed local CPU run."""
from pathlib import Path
import argparse,hashlib,importlib.util,json

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(run,baseline):
    record=json.loads((run/'result.json').read_text())
    if record.get('status')!='PASS' or not record.get('physical_clear'):
        raise ValueError('requires completed real-CPU/physical-clear PASS')
    actual={p.relative_to(run/'source').as_posix():sha(p) for p in sorted((run/'source').rglob('*')) if p.is_file()}
    if actual!=record['source_sha256']:raise ValueError('source identity drift')
    for path,key in [('firmware/dma_day_soc','elf_sha256'),('firmware/dma_day_soc.verilog','image_sha256')]:
        if sha(run/path)!=record['firmware'][key]:raise ValueError('firmware identity drift')
    if sha(run/'simulator/dma_day_soc')!=record['simulator_sha256']:raise ValueError('simulator identity drift')
    cpu=[]
    for item in json.loads(baseline.read_text())['production']:
        if not item['path'].startswith('rtl/e203/core/'):continue
        path=run/'source/rtl'/Path(item['path']).relative_to('rtl/e203')
        if sha(path)!=item['sha256']:raise ValueError('CPU core changed '+item['path'])
        cpu.append(item['path'])
    if len(cpu)!=42:raise ValueError('CPU pinned-file scope differs')
    for layer in record['vectors']:
        for name,digest in layer['sha256'].items():
            if sha(run/'vectors'/f"layer_{layer['layer']:02d}"/name)!=digest:raise ValueError('vector identity drift')
    checker=Path(__file__).with_name('check_results.py')
    spec=importlib.util.spec_from_file_location('selection_checker',checker);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    args=record['arguments'];tasks=int(args['tasks']);rows=int(args['rows']);warmup=bool(args['warmup'])
    result=module.check_log((run/'simulation.log').read_text(),tasks,rows,warmup)
    if any(x['window']['first_accept']-x['window']['first_request']<int(args['first_source_stall']) for x in result['layers']):
        raise ValueError('forced first-source wait omitted')
    return dict(schema='s3_4k_cpu_selection_audit_v1',status='PASS_FUNCTION_AND_IDENTITY',
        run=str(run),raw_log_sha256=sha(run/'simulation.log'),result_sha256=sha(run/'result.json'),
        checker_sha256=sha(checker),auditor_sha256=sha(Path(__file__)),
        cpu_core_files_pinned_unchanged=len(cpu),source_files=len(actual),
        firmware_sha256=record['firmware']['elf_sha256'],image_sha256=record['firmware']['image_sha256'],
        simulator_sha256=record['simulator_sha256'],
        **result,area_status='UNMEASURED_CANDIDATE',sta_status='UNVERIFIED_150MHZ',
        formal_platform_eligibility='UNVERIFIED_SHARED64_INTERFACE',
        qualification='local functional/cycle evidence only; throughput uses assumed150MHz')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('audit output must be new; do not overwrite evidence')
    result=audit(a.run.resolve(),a.baseline.resolve());a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ['status','outputs','principal_cycles','including_gap_cycles','task_per_second_at_assumed_150mhz','full12_target_met','cpu_core_files_pinned_unchanged']},sort_keys=True))
