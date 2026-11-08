# S3-Y32 read-pop 开发交付证据

2026-11-08。父基线 `680be463b8c5f7140884d40ae16891c6ccc94d7a`；子基线 `f37a9701240e0875fcdbcc4ca37ef30e0e97b114`；候选 E203 提交 `6e2ec8995c92f97a0b1c45a3652f902ad43ef8e1`。

12 层分别 fresh reset，两组各核对 304,128 个输出。含清空周期 **9,416,340 → 9,150,252（−2.8258%）**；payload **7,035,504 → 6,769,416（−3.7821%）**。每层均减少 22,174 周期，清空及 clear 后间隔不变，具体见 [逐层表](layers.csv)。

实现为 lane7 Y32 读响应退休时同时 POP，减少每组显式 POP 事务。固件加载镜像完全相同，ELF 的执行头及所有 PT_LOAD 段相同；原 ELF 只有非加载的随机临时对象名不同，保留两份原 SHA。

## 文件范围

- `baseline-full12/`、`read-pop-full12/`：原生 campaign 的 plan/result/clear recipe 与全部 12 份原始运行日志；没有重写结果或虚构运行记录。
- [严格对照](read-pop-comparison.json)：相同输入、工具、加载固件、时钟、startup、编译选项、清空工作和窗口，只有明确列出的硬件 transport 差异及唯一 `+NICE_READ_POP=1` 运行参数例外。
- [源码差异](read-pop-source-differences.json)：四个被审查文件的前后 SHA。当前最终 parser 在测量快照建立后增加了 marker 检查，已对原始日志做 [离线重验](read-pop-postvalidation.json)，没有改 DUT 或重写原日志。
- [A 对照](early-pop-comparison.json)：提前 POP 只改善 FIFO 等待、总周期反增 2；已筛除且未综合。
- `checks/`：直接测试摘要、限定测试日志，以及首请求额外等待 7 拍的窗口检查。
- `sha256.json`：这些收录文件的摘要（自身与本 README 不含在清单中）。

这里是便于 Git 评审的 **紧凑证据摘录**，不是完整可独立重跑报告器的 campaign：冻结源文件、向量、ELF、仿真器和完整构建日志保留在开发工作树的 `build/writeback-20261108/`。完整可校验的两组 saved campaign 另归档到本机交付目录；不能将此摘录误当所有大文件都已入库。

## 复现

快速回归及新硬件命令见 [接口说明](../../s3-y32-read-pop.md)。基线从父 `680be46` 与子 `f37a970` 的源码快照取得，使用本分支相同 campaign runner 运行旧 `bias-hw-autogroup-y32-packed16-nice-window`；候选运行新 `…-nice-read-pop-window`。两者共同使用：

```text
--simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf-
--platform-clocks 150mhz --startup-profile external-reset
--bias-kind sram --layers 0,1,2,3,4,5,6,7,8,9,10,11
```

报告器需要两组完整原件，并为 [差异清单](read-pop-source-differences.json) 中每项传入 `--expect-source-change path=BASE_SHA:CAND_SHA`；新旧 transport 比较还须显式 `--allow-read-pop-transport`。默认不允许跨配置比较。

## 资格与风险

这轮是 Verilator 5.032 的二态开发仿真，`--assert` 开启，vendor SVA 关闭，外部 reset 刺激显式记录。150 MHz 是测试台刺激，不能证明 STA；没有运行综合、门级或功耗测量。

正式 VCS 原断言、厂商 SRAM 门级、150 MHz setup/hold、等价范围、净新增面积、全 SoC 单任务能耗和清空政策仍交整机验收负责人完成。baseline 已有时序违例，不能从本次周期收益推断时序或能耗已合格。

新增地址与原 RNE 共用数据通路；NICE 和 wrapper 必须配套部署。旧 Y32 只读窗口与显式 POP 保持兼容，旧 Y32 capability 常量不能单独识别新 transport，应以父仓 gitlink 锁定版本。
