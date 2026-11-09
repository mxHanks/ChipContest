# S3-Y32 next-bias demand：紧凑 Git 证据

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
