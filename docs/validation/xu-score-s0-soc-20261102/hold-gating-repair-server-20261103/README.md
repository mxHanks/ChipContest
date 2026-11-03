# xu 全SoC hold / 门控修复及条件等价

本轮在同服务器 SMIC SS 标准单元库与指定 RAMSP1024X16 库上完成两次增量综合。08 消除了已测试 SRAM/数据 hold 违例；09 进一步消除了全部已测试的门控 hold 违例。09 映射网表又完成真实 Formality 条件一致性验证。**完整150MHz资格仍未通过**：不能把 `analysis_coverage` 的十类检查概括为全部约束检查。

| 实际检查 | 08 数据hold修复 | 09 增加门控hold余量 |
| --- | ---: | ---: |
| setup / hold | 各67251 met、0 violated、3790 untested | 相同 |
| clock_gating_setup | 27 met / 0 violated | 相同 |
| clock_gating_hold | 8 met / 19 violated | 27 met / 0 violated |
| recovery | 17601 met / 0 violated / 2 untested | 相同 |
| removal | 17598 met / 5 violated | 相同 |
| 十类检查总计 | 267361 met / 24 violated / 27127 untested | 267380 met / 5 violated / 27127 untested |
| `report_constraint` 电气DRC pin块 | max_capacitance 56、min_capacitance 1404 | 相同 |

旧报告只按低精度打印电容数值，明确写有 `VIOLATED: increase significant digits`。其中 `0.00` 不能视为零或合格。已另开原09网表/原约束的高精度诊断，结果不改写本批原件。08的19项门控hold检查在约束报告中对应10条路径，计数单位不同；09的5项removal对应5条路径。

剩余5项removal在固定平台复位链：PMU `erst_reset_r_reg` / `erst_reset_r_r_reg` 的 SDN，以及 AON reset catcher 的3个 RDN。最差约−0.12148283ns。没有放宽复位约束、删除这些检查或把结构同步器当成RDC/MTBF证明。当前没有从代码中找到足以消除这些检查的完整外部复位相位/脉宽合同。

逐条解析全部27127条未测检查，得到：constant_disabled 17672、no_clock 9129、false_paths 276、no_endpoint_clock 48、unknown 2。9129条no_clock为8676个RDN、429个SDN、24个UART锁存器E上的min_pulse_width；另48条是24个UART锁存器D的setup/hold无终点clock，2条unknown是上述PMU SDN recovery。这只是原报告原因/引脚分类，不是豁免。常量条件需结合实际库弧和网表控制值审查；复位脉宽、UART透明期与异步边界仍须闭合。不得把696个no_clock warning直接认成696个时钟：该历史警告同时包含宏控制引脚和真实锁存器使能。

## 输入、约束与修复

基准全SoC映射网表来自 `full-soc-campaign-03-ppa/ppa-ss-01`（SHA `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`），不是wrapper。原analysis SDC保持 SHA `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。有限范围clock实验脚本 SHA `45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e`：70个结构定位的首级同步D输入cut及6个转发输出clock；未增加reset、SRAM、门控或UART豁免。其来源审查另见相邻 `timing-source-review-20261103`，不凭该脚本自动宣布所有跨域合法。

两次均采用布局前ideal clock模型；不能把未布CTS的全网propagated-clock大电容延迟当成已实现CTS。09仅在DC优化中把gate hold目标保守设为0.12ns，最终PT仍使用原0.1ns约束。没有修改RTL或Chisel；只是库支持的增量映射/缓冲插入，不产生手写组合门时钟。

08映射SHA `b77b8bb33cda339a4165f9d6ceb04d06ef833b6d586f0a5c15c3166e41d96988`，09映射SHA `5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca`。09报告的完整数字SoC面积3.368137335901mm²；加速器层级292397.3039µm²，即0.2923973039mm²（四位报告精度）。这是该修复映射自己的面积，不能与后续S2c/32PE的周期、活动或功耗拼接。正式2.25mm²预算不包含固定CPU、512KiB共享SRAM及原外设；该层级面积也不代表完整参赛资格。

## 实际一致性范围

`full-soc-gating-formality-20261103-09` 从原reference RTL读入，依次加载原综合、08修复、09修复三个SVF，验证的是09映射SHA。真实 `fm_shell` 退出0，`Verification SUCCEEDED` / `XU_FULL_SOC_FORMALITY_PASS` 各一次；41462个passing点由17136 BBPin、144 Port、24143 DFF、39 LAT构成。执行前后reference文件列表、RTL、实现网表及三个SVF记录相同。

证明保留原条件：`synopsys_auto_setup`、synthesis未驱动信号解释、`verification_verify_directly_undriven_output false`，511 unread及17个reference unmatched比较点。SRAM内部是黑盒，FM不证明宏内部行为；mapped-memory功能/掩码/延迟需另证。原 `unmatched.rpt`、完整 `fm.log` 和verify Tcl均保存，不能将这项写成无条件完整门级证明。

## 原件和复现

本目录54个原始文件共28277584字节；大文件用XZ无损保存，其展开字节与服务器原manifest逐一相同。空白、警告和失败项均保留。原件来自已严格校验的export10（291288字节，SHA `f78ba592a0ce0ef285dbafdce5368eb636b36cfdfd7d36e9a688d9a8bed479a9`）与export12（279572字节，SHA `5330f5c8b03d9a8f8077f1dbc51908881bb9d472ebad3c3b4fd73d81aa180336`）；全原manifest亦保存。

本地检查不运行EDA，核对原始存储/展开/manifest SHA、实际DC/PT/FM状态与脚本/日志、输入链和覆盖条目守恒：

```sh
python3 docs/validation/xu-score-s0-soc-20261102/hold-gating-repair-server-20261103/check-evidence.py
```

同服务器 Synopsys DC T-2022.03-SP5-5、PT T-2022.03-SP5-1、FM R-2020.09-SP5，在全新工作目录中按 `raw/.../repair.tcl` → `sta.tcl` → `verify.tcl` 重放；其中相对 `mapped.v` 必须指向该次DC的输出，绝对SDC、库和reference路径在原Tcl中可审阅。`evidence-tools` 保存原启动脚本，默认历史输出已存在会拒绝；复测必须换新输出路径而非覆盖原件。大网表、DB和SVF没有本地重新下载，其哈希由真实服务器回执记录支持，本目录不冒充本地重哈希。
