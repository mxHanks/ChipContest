#!/usr/bin/env python3
"""Immutable compact evidence copy. --final requires owner-confirmed report/Git identity.

Without --final, write only a candidate plan under compact-preparation. Never
modify source proofs. Exclude handoff to prevent archive/receipt recursion.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,time


def sha(data):return hashlib.sha256(data).hexdigest()

def read_stable(p):
    a=p.stat();data=p.read_bytes();b=p.stat()
    if (a.st_size,a.st_mtime_ns)!=(b.st_size,b.st_mtime_ns):raise RuntimeError('Source changed while reading: '+str(p))
    return data


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--final',action='store_true')
    ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3]);args=ap.parse_args()
    root=args.repo.resolve();build=root/'build/last-two-20261109';prep=build/'compact-preparation'
    out=root/'docs/validation/s3-y32-last-two-20261109';prep.mkdir(parents=True,exist_ok=True)
    candidates={};skipped=[];raw=[]
    prune={'obj','verilator-obj','__pycache__','.scala-build','.bsp','.git','.cache','chisel','source','original-vectors','task0-vectors'}
    binary={'.vvp','.o','.a','.so','.pyc','.class','.jar','.tar','.gz','.xz','.zip','.bin','.elf'}
    def add(p,destination,category):
        if p.is_symlink():skipped.append({'original_absolute_path':str(p.absolute()),'reason':'SYMLINK_NOT_FOLLOWED','link_target':os.readlink(p)});return
        if not p.is_file():return
        data=read_stable(p);key=str(destination)
        record={'destination':key,'original_absolute_path':str(p.absolute()),'bytes':len(data),'sha256':sha(data),'category':category}
        if key in candidates and candidates[key]!=record:raise RuntimeError('Destination collision: '+key)
        candidates[key]=record
    def tree(base,destination,category,verification=False):
        if not base.exists():return
        for folder,dirs,files in os.walk(base,followlinks=False):
            f=Path(folder)
            for d in list(dirs):
                p=f/d
                if p.is_symlink():
                    skipped.append({'original_absolute_path':str(p.absolute()),'reason':'SYMLINK_DIRECTORY_NOT_FOLLOWED','link_target':os.readlink(p)});dirs.remove(d)
                elif d in prune and not (verification and d=='source'):
                    skipped.append({'original_absolute_path':str(p.absolute()),'reason':'OMITTED_DIRECTORY_'+d});dirs.remove(d)
            for name in sorted(files):
                p=f/name;rel=p.relative_to(base)
                if p.is_symlink():add(p,Path(destination)/rel,category);continue
                if p.suffix in binary:
                    skipped.append({'original_absolute_path':str(p.absolute()),'reason':'COMPILED_BINARY_OR_ARCHIVE_OMITTED'});continue
                if p.suffix=='.mem' and not verification:
                    data=read_stable(p);raw.append({'original_absolute_path':str(p.absolute()),'bytes':len(data),'sha256':sha(data),'reason':'RAW_CAPTURE_OMITTED_FULL_PORTABLE_ARCHIVE_HAS_BYTES'});continue
                # Deliberately mutated ELF/image/vector/source bytes in verifier
                # negatives are evidence, not complete successful campaign inputs.
                if not verification and p.suffix not in {'.json','.log','.md','.txt','.py','.sv','.v','.svh','.scala','.c','.h','.f','.su','.patch','.sha256'} and name!='SHA256SUMS':
                    skipped.append({'original_absolute_path':str(p.absolute()),'reason':'NON_COMPACT_ARTIFACT_OMITTED'});continue
                add(p,Path(destination)/rel,category)
    campaigns={'baseline-bias-demand-full12':root/'build/bias-demand-20261109/full12',
               'acc41-task0':build/'acc41-task0','acc41-full12':build/'acc41-full12'}
    status={}
    required={'plan.json','result.json','clear-recipe.json','s3_clear_main.c','tb.sv','s3_clear_observer.svh','rtl.f'}
    for label,base in campaigns.items():
        j=json.loads(read_stable(base/'result.json'));status[label]={k:j.get(k) for k in ['status','original_layers','cache_policy','fifo_payload_physical_zero','source_drift']}
        if j['status']!='DEVELOPMENT_PASS_POLICY_PENDING' or j.get('source_drift')!=[]:raise RuntimeError('Campaign not frozen PASS: '+label)
        for p in sorted(base.iterdir()):
            if p.is_file() and (p.name in required or p.suffix in {'.log','.su'}):add(p,Path('campaigns')/label/p.name,'ORIGINAL_CAMPAIGN_COMPACT_ARTIFACT')
        missing=[n for n in required if not(base/n).is_file()]
        if missing:raise RuntimeError('Missing campaign metadata '+label+':'+str(missing))
        for p in sorted(base.glob('task-*/simulation.log')):add(p,Path('campaigns')/label/p.parent.name/p.name,'ORIGINAL_CAMPAIGN_TASK_RAW_LOG')
        if len(list(base.glob('task-*/simulation.log')))!=len(j['original_layers']):raise RuntimeError('Wrong task log count: '+label)
    for d in ['acc41-checks','rowpair-checks','dma-checks','integrated-acc41-replay','integrated-acc41-replay-final',
              'integrated-paired-nice-replay','integrated-paired-nice-replay-final','integrated-rowpair-replay']:
        tree(build/d,Path('proofs')/d,'ORIGINAL_PROOF_OR_REPLAY')
    tree(build/'verification',Path('verification'),'VERIFIER_NEGATIVE_OR_PIN',verification=True)
    for p in sorted(build.iterdir()):
        if p.is_file() and p.suffix in {'.json','.log','.md','.patch','.txt'}:add(p,Path('summaries')/p.name,'ROOT_SUMMARY_COMMAND_FREEZE_OR_REVIEW')
    for n in ['s3-y32-last-two-results.md','s3-y32-last-two-plan.md']:
        add(root/'docs'/n,Path('summaries')/n,'OWNER_CONFIRMED_REPORT_OR_PLAN')
    add(Path(__file__).resolve(),Path('assemble_compact.py'),'COMPACT_COLLECTION_PROGRAM')
    identity=json.loads(read_stable(build/'implementation-git-identity.json'))
    report=root/'docs/s3-y32-last-two-results.md'
    if sha(read_stable(report))!=identity['report_sha256']:raise RuntimeError('Final report differs from confirmed Git identity')
    skipped.append({'original_absolute_path':str(build/'handoff'),'reason':'HANDOFF_ARCHIVES_SCRIPTS_AND_RECEIPTS_OMITTED_TO_AVOID_MUTUAL_REFERENCE'})
    plan={'phase':'FINAL_OWNER_CONFIRMED' if args.final else 'PREPARED_FINAL_COPY_PENDING',
          'owner_identity':identity,'campaigns':status,'files':sorted(candidates.values(),key=lambda x:x['destination']),
          'omitted_raw_captures':raw,'skipped':skipped,'copied_files':len(candidates),'copied_bytes':sum(x['bytes'] for x in candidates.values())}
    (prep/'candidate-plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n')
    if not args.final:
        print(json.dumps({k:plan[k] for k in ['phase','copied_files','copied_bytes']},indent=2));return
    if out.exists():raise RuntimeError('Refusing to overwrite compact evidence: '+str(out))
    stage=prep/('stage-'+str(time.time_ns()));stage.mkdir()
    for rec in plan['files']:
        p=Path(rec['original_absolute_path']);data=read_stable(p)
        if sha(data)!=rec['sha256'] or len(data)!=rec['bytes']:raise RuntimeError('Source changed after inventory: '+str(p))
        target=stage/rec['destination'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        if sha(target.read_bytes())!=rec['sha256']:raise RuntimeError('Copy mismatch '+str(target))
    # A later write to an already-copied proof is caught before sealing.
    for rec in plan['files']:
        if sha(read_stable(Path(rec['original_absolute_path'])))!=rec['sha256']:raise RuntimeError('Source changed during collection: '+rec['original_absolute_path'])
    (stage/'.gitattributes').write_text('* -text\n')
    readme=f'''# S3-Y32 后续两项：紧凑 Git 证据

本目录保存最后两项计划的原始证据，实施提交为 `{identity['implementation_parent']}`，E203 保持 `{identity['e203_unchanged']}`。`provenance.json` 按每个复制文件记录原绝对路径、原字节数与 SHA256；`SHA256SUMS` 校验本目录字节。采集器在复制前后检查源文件 SHA，原 proof 不会被改写。

- `campaigns/baseline-bias-demand-full12`：8 PE 当前基线完整12层。
- `campaigns/acc41-task0`、`campaigns/acc41-full12`：41位累加候选的先导及完整12层。
- 各 campaign 保留原 plan/result、clear recipe、生成 C/TB/清零 observer、rtl.f、逐层 simulation.log、版本和编译日志。
- `proofs`：41位范围/逐前缀证明、真实数值、双行模块、可选 strided NICE 的最终与历史回归，以及集成源重生成和独立审查收据。
- `verification`：严格比较器、冻结 source pairs/pins、最终比较与真实变异负例；早期 NOTFINAL 草稿和失败原件均保留。所有 symlink fixture 本身及其指向目标都不会复制。
- `summaries`：root 命令/源冻结/最终结论审查、Git身份和已提交报告/计划的原字节。
- `omitted-raw-captures.json`：未复制的大 raw48/Y32 mem 文件的原绝对路径、字节数和 SHA；其原字节在完整 portable 包中。

`failure-log-index.json` 只是定位索引；命中 FAIL/FATAL/NOTFINAL 的行既可能是预期负例，也可能是已修复的夹具失败，不会自动计为性能或正确性通过。`evidence-classifications.json` 分开说明最终通过、草稿和预期拒绝。任何 grep 到 PASS 都不足以替代最终 result/strict comparison。

41位候选未获得本任务周期收益；双行/strided NICE 是模块原型而非 CPU/SoC 速度或独立 DMA 证明。当前8PE生产基线保持原字节。仿真状态仍是 DEVELOPMENT_PASS_POLICY_PENDING，真实清零 policy 为 REVIEW_PENDING，FIFO payload physical zero 仍是 UNPROVEN。无综合、面积、STA、功耗、VCS/门级或官方验收声明。

这里有意省略成功 campaign 的完整向量、ELF、加载 image、原生 soc_sim、完整 source/RTL、生成编译中间件、.vvp/.o/.cache，以及大 raw capture。verification 中故意变异的部分 ELF/image/vector/source 字节只用于证明负例被拒绝，不能作为成功 campaign 的完整输入。因此本目录不能独立重跑仿真或严格复验。完整 portable 原件和独立复验入口由外层 `{build/'handoff/README.md'}` 交付；handoff 脚本、archive 和封包收据不进入本目录，避免循环引用。
'''
    (stage/'README.md').write_text(readme)
    (stage/'provenance.json').write_text(json.dumps({'campaign_path_map':{k:str(v) for k,v in campaigns.items()},'owner_identity':identity,'files':plan['files'],'skipped':skipped},indent=2,ensure_ascii=False)+'\n')
    (stage/'omitted-raw-captures.json').write_text(json.dumps(raw,indent=2)+'\n')
    failure=[];draft=[]
    tokens=re.compile(r'FAIL|FATAL|NOTFINAL|NOTPASS|Traceback|AssertionError|FileNotFoundError|KeyError|Unable to open input file|error:|Error:')
    for p in sorted(stage.rglob('*')):
        if not p.is_file() or p.suffix not in {'.log','.json','.md'}:continue
        if p.name in {'provenance.json','omitted-raw-captures.json'}:continue
        lines=p.read_text(errors='replace').splitlines();hits=[{'line':i,'text':line[:800]} for i,line in enumerate(lines,1) if tokens.search(line)]
        if hits:failure.append({'file':str(p.relative_to(stage)),'classification':'RAW_FAILURE_EXPECTED_REJECTION_OR_DRAFT_REQUIRES_CONTEXT','matches':hits})
        if any('NOTFINAL' in line for line in lines):draft.append(str(p.relative_to(stage)))
    (stage/'failure-log-index.json').write_text(json.dumps(failure,indent=2)+'\n')
    classifications={'status':'INITIAL_FAILURES_AND_NOTFINAL_PRESERVED_NEVER_PROMOTED_TO_PASS',
        'notfinal_mentions_requires_context':draft,'known_superseded_drafts':['verification/compare_acc41-initial.py'],'superseded_comparator':'verification/compare_acc41-initial.py is an initial draft; use final compare_acc41.py and final receipts.',
        'expected_rejections':'verification/*-negatives* result.json files preserve actual/expected rejection. Mutated artifacts are not performance evidence.',
        'fixture_failures':['proofs/dma-checks/rowpair-real-compile.log: initial wire declaration syntax failure',
            'proofs/dma-checks/portable-driver-failed-config-path.log: guessed e203_config.v path did not exist; final uses core/config.v',
            'proofs/acc41-checks/review/final-integration-code-review-first-fixture-failure.log: first review fixture failure, superseded by final receipt'],
        'final_pass':'Use confirmed campaign result.json, *comparison-final.json / full12 comparison, integrated *-final replay results, final proof summary and independent review receipts; historical PASS strings alone are insufficient.'}
    (stage/'evidence-classifications.json').write_text(json.dumps(classifications,indent=2)+'\n')
    summary={'phase':'FINAL_OWNER_CONFIRMED','implementation_git_identity':identity,'campaigns':status,
             'copied_source_files':len(plan['files']),'copied_source_bytes':plan['copied_bytes'],'omitted_raw_captures':len(raw),
             'failure_or_draft_index_entries':len(failure),'notfinal_mention_files_requires_context':len(draft),'full_independent_revalidation':False,
             'handoff_policy':'EXTERNAL_HANDOFF_NO_ARCHIVE_OR_RECEIPT_MUTUAL_REFERENCE','recorded_unix':time.time()}
    (stage/'collection-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    pins={str(p.relative_to(stage)):sha(p.read_bytes()) for p in sorted(stage.rglob('*')) if p.is_file()}
    (stage/'sha256.json').write_text(json.dumps(pins,indent=2)+'\n');pins['sha256.json']=sha((stage/'sha256.json').read_bytes())
    (stage/'SHA256SUMS').write_text(''.join(value+'  '+name+'\n' for name,value in sorted(pins.items())))
    out.parent.mkdir(parents=True,exist_ok=True);stage.rename(out)
    (prep/'final-copy-receipt.json').write_text(json.dumps({'destination':str(out),'collection_summary':summary,
       'sha256sums_sha256':sha((out/'SHA256SUMS').read_bytes()),'provenance_sha256':sha((out/'provenance.json').read_bytes())},indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
