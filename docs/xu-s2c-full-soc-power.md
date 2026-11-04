# xu 原始 S2c 全 12 task PrimeTime 功耗实测入口

`tools/ppa/xu_s2c_full_soc_power.py` 消费实际完成的 `s2c-formal-activity12-20261103-23`。这是独立的新入口；baseline power runner、candidate collector、原 Context 和 normalizer 均保持原字节。它不重新仿真，不用 wrapper 或单宏 fixture 代替 CPU、互连、SRAM、加速器的完整 mapped SoC。

执行必须在原服务器能够读取原始 24 份 raw/normalized SAIF、48 个张量及 materialized 副本、source checkout、原 producer checkout、完整 inventory provenance、netlist 和 DB 的环境。输出目录必须全新。`B` 表示原 campaign 根目录 `xu-score-optimization-20261102`，工具 checkout 必须 clean 且 commit 后再执行：

```bash
bash tools/ppa/run_xu_s2c_full_soc_power.sh \
  "$B" "$B/s2c-full-soc-power12-20261104-57" \
  /eda/synopsys/prime/prime_2022.03-SP5-1/bin/pt_shell
```

shell 继承已配置 license/PATH 和 `SYNOPSYS_LC_ROOT`，如该变量存在就明确传入 `--lc-root`。可单独执行 `prepare` 与 `run` 子命令；没有默认 task 子集，必须完整 0..11。所有 Git 命令通过 subprocess `cwd` 调用，兼容服务器旧 Git，不使用 `git -C`；Python 使用 3.6 支持的标准库接口。

准备阶段逐一检查原 capture producer 为 `5e75581319f926642ee7dc214ad825f3564a8e39`、配置 SHA 为 `5b5cf619e8b0e5c2fc050abe8b589d5f7544a98eed174f4fc979bffe60fa6018`、source 为冻结 S2c 及实际 child profile、nominal150/LF32768/1fs 且无 `INITIALIZE_MEMORY`。旧 normalizer 从原 producer 路径加载，并保留它自己的旧 Context；新功耗工具单独记录当前真实 tool context，不把新 checkout 冒充原 collector。

全 12 原始 log 被原 candidate checker 重读，各层 result/window/autogroup、33697 CPU clear、fresh process、原始 task 张量和输入集合 hash 均核对。每份 raw SAIF 都用原 normalizer 重新执行，逐 bit comparison、unknown dwell、time base 与 normalized SHA 必须一致；重新解析完整归一化 SAIF 检查原 scope/宏清单。随后只在 private bridge module 中显式组成 S2c mapping API，按实际 inventory 把 336 宏、22512 bit pins 做严格名称双射，保留每个 pin 的全部原始统计和 X/Z/B dwell。baseline bridge 文件不修改。

唯一允许的原 mapped netlist SHA 为 `9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`，inventory SHA 为 `721ce0773570c54a8757a32165a47f399cd5c1ee9e3a57eab612dbeeeea15d8d`，SDC SHA 为 `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。实际 SS DB 为标准单元 `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723` 和 1024x16 SRAM `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`；inventory 原导出前后输入 identity、原 TSV/JSON 全部 pin/name/ref/libcell 对应也须一致。

每 task 启动独立 `pt_shell -f power.tcl`，完整读取原 mapped netlist、原分析 SDC 和两份原 DB。Tcl 复用已有 clock/memory/retained CPU、accelerator、interconnect 检查和 averaged `read_saif` 报告，保留 read/inconsistent、所有 file/default/propagated/no_switching reports、before/after 全 22512 pin attributes、逐宏功耗、完整 SoC/hierarchy 功耗、实际 Liberty power-arcs/library reports，以及单独 `update-power.rpt`。任何 PT error、非零返回、缺 report、缺/重 pin 或宏、缺/重 completion marker、输入变更均失败。大 reports 保留原文，不能只 export 摘要。

`execution.json` 在每次 PT 返回时先保存 tool receipt，再审查 reports；同时保存所有输入与产物的 SHA256、实际 PT command/version/executable，以及原输入 before/after identity。每 task 的 `diagnostic` 从原 full-SoC `power.rpt` 提取显式 W 单位的原生报告值，乘以日志中的 `6604373333334 × 1e-15` 秒，并明确记录 report 原生舍入精度。12 task 全完成后提供这 12 个报告值的算术平均功率和诊断能量之和；没有比赛 score 计算。

成功状态 `EXECUTED_12_TASKS_DIAGNOSTIC_REVIEW_PENDING` 只说明完整 PT 测量执行完成。所有诊断均保持 `PARTIAL_MODEL_DIAGNOSTIC_NOT_ENERGY_QUALIFIED` / `NOT_QUALIFIED`：mapped annotation/defaults、SAIF 单位与工具转换、SRAM 条件边沿/when/internal_power、Q 绝对状态未知以及原 mapped timing/electrical 资格仍需审查。没有将 unknown、hold 宏或未注释活动视为零，也没有将 actual48 API agreement 当成 power engine 条件语义证明。

本机已用真实既有 baseline `power.rpt` 验证 W 单位/数值解析和 Decimal 乘窗计算，完成 Python compile/CLI 及 shell syntax 检查。这里没有执行服务器 PT 或读到缺失的 SAIF。baseline `test_xu_soc_saif_power.py` 需要工具 checkout 中未初始化的第三方 submodule，`setUpClass` 缺 `core/config.v`，因此 0 tests，未记为通过。全 12 实际 log/receipt 的离线核对与限制见 `docs/validation/xu-score-s2c-activity12-review-20261104/README.md`。
