"""Copy immutable compact evidence; --final requires owner-confirmed completed runs."""
from pathlib import Path
import argparse,hashlib,json,shutil,time

ROOT=Path(__file__).resolve().parents[3]
BUILD=ROOT/"build/bias-demand-20261109"
OUT=ROOT/"docs/validation/s3-y32-bias-demand-20261109"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final",action="store_true")
    parser.add_argument("--skip-portable",action="store_true",help="collect frozen raw/proofs while final package receipts are pending")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    mappings=[]
    skipped=[]
    def copy(source,rel):
        if source.is_symlink():
            skipped.append({"path":str(source),"reason":"symlink fixture or local path alias"});return
        a=source.stat()
        data=source.read_bytes()
        b=source.stat()
        if (a.st_size,a.st_mtime_ns)!=(b.st_size,b.st_mtime_ns):
            raise RuntimeError("source changed while reading: "+str(source))
        target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        sha=hashlib.sha256(data).hexdigest()
        assert digest(target)==sha
        mappings.append({"destination":str(rel),"original_absolute_path":str(source.resolve()),"bytes":len(data),"sha256":sha})
    def tree(source,rel):
        if not source.exists():return
        for p in sorted(source.rglob("*")):
            q=p.relative_to(source)
            if any(x in q.parts for x in ("__pycache__",".scala-build",".bsp","relocation-check","generated")):continue
            if p.is_symlink():skipped.append({"path":str(p),"reason":"symlink fixture or local path alias"});continue
            if p.is_file():copy(p,rel/q)
    campaigns={"baseline-packed-full12":ROOT/"build/packed-clear-20261109/packed-full12","pilot-task0":BUILD/"pilot-task0","selected-full12":BUILD/"full12"}
    top_names={"plan.json","result.json","clear-recipe.json","s3_clear_main.c","tb.sv","s3_clear_observer.svh","rtl.f"}
    campaign_status={}
    for name,source in campaigns.items():
        if name=="selected-full12" and not args.final:
            campaign_status[name]="PENDING_OWNER_FINAL_FREEZE";continue
        result=json.loads((source/"result.json").read_text())
        if result["status"]!="DEVELOPMENT_PASS_POLICY_PENDING":raise RuntimeError("campaign incomplete: "+str(source))
        campaign_status[name]={"status":result["status"],"original_layers":result["original_layers"],"cache_policy":result["cache_policy"],"fifo_payload_physical_zero":result["fifo_payload_physical_zero"]}
        for p in sorted(source.iterdir()):
            if p.is_file() and not p.is_symlink() and (p.name in top_names or p.suffix in (".log",".su")):
                copy(p,Path("campaigns")/name/p.name)
        for p in sorted(source.glob("task-*/simulation.log")):
            copy(p,Path("campaigns")/name/p.parent.name/p.name)
    if args.final:
        for p in sorted(BUILD.iterdir()):
            if p.is_file() and p.suffix in (".json",".log",".patch",".md"):
                copy(p,Path("summaries")/p.name)
        for name in ("review","rtl-checks","integrated-rtl-checks","verification"):
            tree(BUILD/name,Path("proofs" if name!="verification" else "verification")/name if name!="verification" else Path("verification"))
        # Packaging receipts are compact; archives, extracted trees and copies of
        # complete campaign sources are intentionally omitted here.
        handoff=BUILD/"handoff"
        if handoff.exists() and not args.skip_portable:
            for p in sorted(handoff.iterdir()):
                if p.is_file() and p.suffix in (".json",".log",".md",".sha256",".py"):
                    copy(p,Path("portable-package")/p.name)
    copy(Path(__file__),Path("assemble_compact.py"))
    (OUT/".gitattributes").write_text("* -text\n")
    readme="""# S3-Y32 next-bias demand：紧凑 Git 证据

本目录按原字节保存真实 SoC 基线、先导、集成完整 12 层的 plan/result、清零 recipe、生成 C/TB、rtl.f、原始逐层 simulation.log、工具版本及编译日志。`provenance.json` 给出每个文件的原绝对路径与 SHA256；`SHA256SUMS` 可检查本紧凑目录字节。

- `campaigns/baseline-packed-full12` 原始目录：`/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/packed-clear-20261109/packed-full12`。
- `campaigns/pilot-task0` 原始目录：`/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/bias-demand-20261109/pilot-task0`。
- `campaigns/selected-full12` 原始目录：`/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/bias-demand-20261109/full12`。
- `summaries`：环境、源冻结、源 diff、root 汇总与命令收据。
- `proofs`：独立代码审查、限定 RTL 回归、集成测试、生成收据和初始失败原件。
- `verification`：严格比较工具与源 pairs、成功比较、预期拒绝的负例及真实修改字节；被省略的 symlink fixture 指向完整原件。
- `portable-package`：若另行提供，仅为完整包的封存与重验证收据；这些本身不是完整包。本轮最终封包 SHA 及 seal 身份保留在外层 handoff，避免 archive 与紧凑目录互相包含形成循环。

状态以 `collection-summary.json` 为准。失败、NOTPASS、预期拒绝、测试夹具修复日志都保留，不能仅凭文件名或 grep 到 PASS 判定成功；`failure-log-index.json` 只用于定位，需按测试上下文理解。初始运行失败没有被成功结果覆盖。

成功状态仍是 `DEVELOPMENT_PASS_POLICY_PENDING`。清零 policy 是 `REVIEW_PENDING`，FIFO payload physical zero 是 `UNPROVEN`。本轮不把逻辑无效化称为物理清零；W/X/bias 清零按既有真实清零接口验证。150 MHz 只是测试台时钟刺激，Verilator 二态结果不证明综合面积、STA 频率、能耗、VCS/门级或官方成绩。

本紧凑目录有意省略原 campaign 的 ELF、加载 image、原生 soc_sim、完整 source/RTL 与向量快照和 C++ 编译中间件，**不能独立严格复验或重跑仿真**。负例目录中可以保留被故意修改的 ELF/image/vector 字节，用途仅为证明 verifier 拒绝该变异；不代表完整成功原件。完整原件与独立严格复验入口在 `/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/bias-demand-20261109/handoff/README.md` 所述 portable archive 中。

`.gitattributes` 禁用换行转换。复制脚本检查读取期间大小/mtime 与目标 SHA，不改原件。只有 owner 确认完整 campaign、strict 比较、报告、封包收据完成后，才执行 `python3.12 -E -B assemble_compact.py --final`。首次准备阶段不复制活动 full12、root 汇总和最终封包收据。最终 raw/proofs 收齐后可以使用 `--final --skip-portable`，封包 SHA 与独立重验收据由外层 handoff 单独锁定。
"""
    (OUT/"README.md").write_text(readme)
    (OUT/"provenance.json").write_text(json.dumps({"campaign_path_map":{k:str(v) for k,v in campaigns.items()},"files":mappings,"skipped":skipped},indent=2,ensure_ascii=False)+"\n")
    failure=[]
    for p in sorted(OUT.rglob("*.log")):
        hits=[{"line":i,"text":line[:800]} for i,line in enumerate(p.read_text(errors="replace").splitlines(),1) if any(k in line for k in ("FAIL","FATAL","AssertionError","Traceback","NOTPASS","KeyError"))]
        if hits:failure.append({"file":str(p.relative_to(OUT)),"classification":"RAW_FAILURE_OR_EXPECTED_REJECTION_REQUIRES_CONTEXT","matches":hits})
    (OUT/"failure-log-index.json").write_text(json.dumps(failure,indent=2)+"\n")
    classifications={"status":"ORIGINAL_FAILURES_PRESERVED_NOT_COUNTED_AS_PASS","notpass":[{"path":"proofs/rtl-checks/schedule-run1-console.log","reason":"Fixture referenced firtool-eliminated request-ready pin; compile failed."},{"path":"proofs/rtl-checks/schedule-run2-console.log","reason":"Two real simulations passed, but Python incorrectly expected two clocks instead of one."},{"path":"proofs/rtl-checks/schedule-run3-console.log","reason":"Baseline path selected integrated candidate; baseline behavioral check failed."},{"path":"verification/baseline-negative-checks-02.log","reason":"Old harness expected a different rejection; not counted as final negative-test PASS."}],"expected_rejections":"Final negative-check result.json files preserve per-case actual/expected rejection and mutated bytes; intentional corruption is not candidate performance evidence.","final_pass":"Use completed campaign result.json and strict comparison status with pinned artifacts, plus schedule-run4, independent and integrated receipts. grep PASS alone is insufficient."}
    (OUT/"evidence-classifications.json").write_text(json.dumps(classifications,indent=2)+"\n")
    summary={"phase":"FINAL_OWNER_CONFIRMED" if args.final else "PREPARED_FINAL_PENDING","campaigns":campaign_status,"portable_receipts_policy":"EXTERNAL_HANDOFF_NO_MUTUAL_ARCHIVE_REFERENCE" if args.skip_portable else "SNAPSHOT_INCLUDED_IF_PRESENT","copied_files":len(mappings),"copied_bytes":sum(p["bytes"] for p in mappings),"full_independent_revalidation":False,"reason":"Original campaign ELF/image/native simulator/source/vectors intentionally omitted; use portable archive.","failure_logs":len(failure),"recorded_unix":time.time()}
    (OUT/"collection-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    pins={str(p.relative_to(OUT)):digest(p) for p in sorted(OUT.rglob("*")) if p.is_file() and p.name not in ("SHA256SUMS","sha256.json")}
    (OUT/"sha256.json").write_text(json.dumps(pins,indent=2)+"\n")
    sum_pins=dict(pins);sum_pins["sha256.json"]=digest(OUT/"sha256.json")
    (OUT/"SHA256SUMS").write_text("".join(v+"  "+k+"\n" for k,v in sorted(sum_pins.items())))
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
