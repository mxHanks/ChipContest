# S3-Y32 第二轮四项实验：紧凑证据

2026-11-08。主基线 `562a8c9`／E203 `6e2ec89`，选中候选 E203 `d74d520`。对应[实测报告](../../s3-y32-writeback-v2-results.md)与[接口说明](../../writeback-v2/direct-channel.md)。

内部结果通道 12 层 payload＋physical clear：**9,150,252→7,819,944 拍（−14.5385%）**；多组 drainN 单独对照为 8,892,456 拍（−2.8174%）。每层输出均逐位核对；两项收益没有相加。轮询退避与 CPU 展开没有整任务加速。

## 内容

- `baseline-full12/`、`direct-full12/`、`burst-full12/`：原生 plan/result/clear recipe 与全部 36 份原始任务日志。`direct-legacy-task0/` 保存旧冻结固件在新 DUT 上通过的原件。
- [逐层表](layers.csv)、[严格 direct 对照](direct-comparison.json)、[精确源码差异](direct-source-differences.json)、[原日志复验](direct-postvalidation-receipt.json)。比较例外仅支持显式、有向 read-pop→direct；工具、输入、时钟、启动、clear 和其余命令约束仍保留。不同加载固件各自核验 ELF／镜像，启用指令和 capability 变化显式记录。
- `direct-proof/`：旧契约／加载镜像兼容性、源码 SHA、错误／背压／复位和旧端口夹具修复回归。`checks/` 保存限定单元测试，`direct-first-stall7/` 保存额外边界回放。
- `direct-task0/`、`direct-task0-diagnostic/` 保留两次失败，`direct-task0-phase/` 为修正新 profile 观察器后的通过测量。未把失败算 PASS。
- `poll/` 保存 0/2/8/13 参数测量与首个 defparam 编译失败、单元测试、诊断和可回退补丁。
- `cpu-*/`、`cpu-experiments.json`、两个 `cpu-unroll*.patch` 保存三组同条件单层测量及唯一固件差分。
- `burst-summary.json`、`burst-review.patch` 和 `burst-unit/` 保存独立备选。该补丁基于本轮 read-pop baseline，不能直接当作 direct 叠加补丁。
- `integrated-production-source-check.json` 核对最终 DUT／固件 170 个测量源与集成版本一致。兼容性测试夹具和报告器不在 DUT 性能快照内。
- `sha256.json` 覆盖本目录收录文件（不含自身与本 README）。原始 result、日志不经重写。完整归档的 4,204 个文件、15 组 campaign 已独立解包核验；最终归档报告器还对解包后的两组 full12 严格复算，逐层、总计、源码变化与固件身份均与原对照一致，见 `archive-verification.json` 与 `relocated-direct-comparison-receipt.json`。

这里是便于 Git 评审的紧凑摘录，**不包含所有大文件，不能单独运行严格 campaign loader**。完整 saved campaign 包含冻结源、向量、ELF／镜像、原生模拟器、完整构建命令及日志，归档在本机工作树 `build/writeback-v2-20261108/handoff/`；该目录还包含父子增量 Git bundle、SHA 清单和解包验证说明。

## 复现

主硬件路径为 `tools/ppa/s3_task_campaign.py`，使用以下共同参数；`--out` 必须为新目录，`--repo` 指向对应冻结 checkout：

```text
--bias-kind sram --simulator verilator
--cross-prefix /usr/bin/riscv64-unknown-elf-
--platform-clocks 150mhz --startup-profile external-reset
--layers 0,1,2,3,4,5,6,7,8,9,10,11
```

基线 schedule 为 `bias-hw-autogroup-y32-packed16-nice-read-pop-window`；选中候选为 `bias-hw-autogroup-y32-packed16-nice-direct-window`。drainN 独立沙盒的 schedule 为 `bias-hw-autogroup-y32-packed16-nice-drainn-read-pop-window`。

对两份**完整** campaign 使用 `tools/analysis/s3_writeback_report.py BASE CAND --allow-direct-transport`，并为 source-differences 中每个文件逐项提供 `--expect-source-change PATH=BASE_SHA:CAND_SHA`。原 CLI argv 见 `direct-comparison.log`。loader 支持按原路径前缀映射到解包目录，原始结果内的绝对路径不需要改写；解包验证收据保存在交付目录。

## 有限验证与未通过项

Verilator 5.032 二态、`--assert` 开启、vendor SVA 关闭；显式外部 pad 双复位，未改核内复位逻辑或 force 状态。这里不包含综合、STA、门级、功耗或正式资格结果。

register capability 夹具缺失，未运行；VCS 路线测试因本机无 VCS 未执行。host gate 可编译但出现响应断言，未改 wrapper 的 baseline 得到同时间同失败，未计 PASS。详见 `checks/legacy-direct-compatibility/summary.json`，其中 8 个通过项与失败／缺夹具分别标记。

正式 SRAM/FIFO 清空政策仍为 `REVIEW_PENDING`／`UNPROVEN`；新增快照寄存器复位不代表已有物理 payload 已完成清零验收。正式 VCS、厂商 SRAM 门级、150 MHz setup/hold、净面积和能耗等待整机验收。
