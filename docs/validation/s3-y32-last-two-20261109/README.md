# S3-Y32 后续两项：紧凑 Git 证据

本目录保存最后两项计划的原始证据，实施提交为 `ee0ad1a30ee4dce654c7d10646a4bc3399cb071a`，E203 保持 `dba1b5f82395b762f126387a1840e6a843e3a01a`。`provenance.json` 按每个复制文件记录原绝对路径、原字节数与 SHA256；`SHA256SUMS` 校验本目录字节。采集器在复制前后检查源文件 SHA，原 proof 不会被改写。

- `campaigns/baseline-bias-demand-full12`：8 PE 当前基线完整12层。
- `campaigns/acc41-task0`、`campaigns/acc41-full12`：41位累加候选的先导及完整12层。
- 各 campaign 保留原 plan/result、clear recipe、生成 C/TB/清零 observer、rtl.f、逐层 simulation.log、版本和编译日志。
- `proofs`：41位范围/逐前缀证明、真实数值、双行模块、可选 strided NICE 的最终与历史回归，以及集成源重生成和独立审查收据。
- `verification`：严格比较器、冻结 source pairs/pins、最终比较与真实变异负例；早期 NOTFINAL 草稿和失败原件均保留。所有 symlink fixture 本身及其指向目标都不会复制。
- `summaries`：root 命令/源冻结/最终结论审查、Git身份和已提交报告/计划的原字节。
- `omitted-raw-captures.json`：未复制的大 raw48/Y32 mem 文件的原绝对路径、字节数和 SHA；其原字节在完整 portable 包中。

`failure-log-index.json` 只是定位索引；命中 FAIL/FATAL/NOTFINAL 的行既可能是预期负例，也可能是已修复的夹具失败，不会自动计为性能或正确性通过。`evidence-classifications.json` 分开说明最终通过、草稿和预期拒绝。任何 grep 到 PASS 都不足以替代最终 result/strict comparison。

41位候选未获得本任务周期收益；双行/strided NICE 是模块原型而非 CPU/SoC 速度或独立 DMA 证明。当前8PE生产基线保持原字节。仿真状态仍是 DEVELOPMENT_PASS_POLICY_PENDING，真实清零 policy 为 REVIEW_PENDING，FIFO payload physical zero 仍是 UNPROVEN。无综合、面积、STA、功耗、VCS/门级或官方验收声明。

这里有意省略成功 campaign 的完整向量、ELF、加载 image、原生 soc_sim、完整 source/RTL、生成编译中间件、.vvp/.o/.cache，以及大 raw capture。verification 中故意变异的部分 ELF/image/vector/source 字节只用于证明负例被拒绝，不能作为成功 campaign 的完整输入。因此本目录不能独立重跑仿真或严格复验。完整 portable 原件和独立复验入口由外层 `/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/last-two-20261109/handoff/README.md` 交付；handoff 脚本、archive 和封包收据不进入本目录，避免循环引用。
