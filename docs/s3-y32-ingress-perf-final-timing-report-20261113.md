# 原 1064 候选：最终时序修复与复测报告

本轮最终 STA、映射后结构一致性检查和 12 任务吞吐复测均已完成；**150 MHz 完整时序验收仍未通过**。原生时序违例从 **467 降到 7**，电气违例从 **1973 降到 292**。本报告对应用户指定的原 1064.35 task/s 候选，RTL 子提交 `5470c5650f2d11d16e7c52cc96626d21030a3973`，64 PE、353 个实际 SRAM，其中内部 33 个；最终整理时间为北京时间 2026-11-13 22:55。

## 吞吐和面积

| 项目 | 本轮最终结果 |
|---|---:|
| 完整任务／逐位核对的 Y32 | 12／304128，PASS |
| 总任务窗口周期 | **1691172 cycles** |
| 平均每任务 | 140931 cycles |
| 按假定 150 MHz 换算吞吐 | **1064.350640 task/s** |
| 全 SoC 标准单元面积 | **356924.013600 原库单位** |
| 内部 33 SRAM 面积 | 301901.305662 原库单位 |
| 保守上界：全 SoC 标准单元＋内部 33 宏 | **658825.319262 原库单位** |

复测实际运行于北京时间 **22:40:41–22:50:08**。所有编译使用的 RTL、testbench、固件及运行器字节均与复用模型的源快照一致；非编译输出检查器后来加强了多请求在途检查，当前运行器另有独立核对。复测为完整 RTL 周期测量；原生 ECO 后的网表另经下述结构证明，尚未运行 mapped 带延迟任务仿真。吞吐依然以 150 MHz 为条件，不能作为已签核芯片吞吐。与原约 500 档基线的 504.3868 task/s 相比，入口优化的吞吐为其 2.1102 倍；本轮 ECO 未进一步改变任务周期。

面积比原映射保守上界 658931.612862 减少 **106.293600 原库单位**。该口径含全 SoC 标准单元，并非加速器归属面积；官方 mm² 换算尚未核定，不能宣称通过 2.25 mm²。原件见[最终面积表](validation/s3-y32-ingress-perf-native-20261113/timing-final/apply/area-upper-bound.tsv)、[本轮性能结果](validation/s3-y32-ingress-perf-native-20261113/timing-final/performance-result.json)及[实际复测日志](validation/s3-y32-ingress-perf-native-20261113/timing-final/performance-simulation.log)。

## 最终 STA 与修改

保持原 SDC、库及频率、IO、uncertainty、门控预算不变，依次完成 hold r5 → clock r7 → electrical r7 → prune r5。每次修改均通过原生 DC 回放、生成自身 SVF，再由新 PT 进程重载。最终及普通电气阶段的 5 份执行回执均 rc0，工具错误、源漂移及缺失输出为零；8 核上限。未添加 false path、multicycle、异步时钟组或 ideal network 来隐藏问题。

| 完整检查 | 原映射 | 最终组合 |
|---|---:|---:|
| 总检查 | 329284 | 328981 |
| met | 299482 | 299642 |
| hold 违例 | 434 | **2** |
| clock-gating hold 违例 | 27 | **0** |
| removal 违例 | 5 | **5** |
| output setup 违例 | 1 | **0** |
| 时序违例合计 | 467 | **7** |
| untested | 29335 | 29332 |

总检查减少 303 项来自精确删除白名单中的 36 个不可观察状态单元：setup/hold 各减少 72 项、recovery/removal 各减少 6 项、pulse-width 减少 147 项。未测原因仍逐行解释为 `no_clock=10245`、`constant_disabled=19083`、`unknown=4`；未把未测检查计作通过。

615 个 hold 身份缓冲修复同步数据和门控保持问题。随后 1560 个分层时钟缓冲将 GFCM U8 根实际叶负载从 21592 降到 18，根电容 16.317097→0.014539，GPIO 路径根转换时间 12.092101→0.019452 ns，消除了 A27 output setup 违例。普通控制网另外加入 198 个身份缓冲；原生全分组阶段逐根确认电容下降、转换时间不退。最后按逐波原生可观察性保护检查删除 1796 个原始死单元，其中 36 个为状态单元。

| 电气违例 | 原映射 | 最终组合 |
|---|---:|---:|
| max-capacitance | 67 | **16** |
| min-capacitance | 1416 | **0** |
| max-transition | 490 | **276** |
| 合计 | 1973 | **292** |

剩余全部 292 项均精确匹配原复位网的驱动或负载引脚目录；最差 max-cap slack 为 −0.00326933 原生电容单位，transition slack 为 −0.00672734 ns。完整原件见[最终 coverage](validation/s3-y32-ingress-perf-native-20261113/timing-final/reload/persisted-coverage.rpt)和[最终 all_violators](validation/s3-y32-ingress-perf-native-20261113/timing-final/reload/persisted-all_violators.rpt)。

## 最终一致性和交付身份

独立严格检查 **PASS**：重新证明精确 1796 个删除单元的不可观察性；收缩同库原生函数证明为 I→Z 的 **2373 个 BUFV2** 后，所有保留原始叶单元的原生层级身份、类型、参数、端口、位宽及完整连接分区相同，**353 个 SRAM 全部保留**。删除实际 SRAM 或篡改单元类型的负向检查均被拒绝。原生最终 PT 同时核对了保留时钟关联，只有已证明删除的 36 个状态单元允许消失。此为 mapped→mapped 结构一致性，不能替代 RTL→mapped FM 或时钟/复位物理签核。

- 最终 mapped.v SHA256：`3ae73f916f02491f4e154eb1b2b7b0938e95158a934ca80da37a51c09faedf30`。
- 最终原生 PT 回执 SHA256：`bf1fae84eb0d47277a334267288bf0dde1c3eb6d78405ea050c8940a77e76147`。
- 最终回传包：46 个负载文件逐 SHA/长度和原生执行输出核验；SHA256 `6b4e1e184b0938c9553fe41b5c15aa597170e98270f7379cbb8773719b6254d2`。
- [严格结构证明](validation/s3-y32-ingress-perf-native-20261113/timing-final/mapped-structural-equivalence.json)、[最终复核 JSON](validation/s3-y32-ingress-perf-native-20261113/timing-final/review.json)、[完整轻量原件包](validation/s3-y32-ingress-perf-native-20261113/timing-final/native-final-evidence.tar.xz)、[文件清单](validation/s3-y32-ingress-perf-native-20261113/timing-final/manifest.json)。

最终 DDC、SDC、各阶段自身及祖先 SVF 的原生输出身份均保留。为收尾速度，DDC 大文件留在原生目录 `/tmp/codex-ingress1064-eco-prune-20261113-r5/combined-apply/mapped.ddc`；本地原件包包含实际最终 Verilog、SDC、SVF 链和报告，不包含工艺 DB。

## 未闭合说明

剩余 7 项为 AON 两个去毛刺首级 D 的 hold，以及 AON/PMU 五个异步复位 removal；另外两个去毛刺 setup 和两个 PMU recovery 仍为 unknown。原生 PTE-052 文档及变量发现已收集，未找到可用的整数展开控制量；未修改原时钟关系。固定延迟不能证明任意异步相位安全，未用局部 LF 路径替代外部 HF→LF 的未知最大检查。

可选的最终时钟输出检查脚本在启动 PT 前，因死状态删除后存在 **34 个静态零负载缓冲输出**而拒绝；该额外检查未通过，不能宣称最终每个时钟输出仍满足 1～32 负载。最终静态根扇出仍为 18；上述完整最终 STA、保留时钟关联检查及严格连接证明已经独立完成。为集中完成用户要求的收尾，未重跑综合，未启动 1477 个复位端点扩展查询，也未继续未经最大路径验证的延迟 ECO。[静态检查记录](validation/s3-y32-ingress-perf-native-20261113/timing-final/final-static-clock-review.json)保留该限制。

本轮没有 SPEF、CTS、后布局多角时序、CDC/RDC/亚稳态及外部复位脉宽签核；官方面积、完整生产加载入口、600 样本最终评测和功耗资格也未由本轮证明。交付结论是 **工程修复与复测完成，时序和电气仍未全部闭合**。
