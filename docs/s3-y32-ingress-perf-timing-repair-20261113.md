# 1064.35 task/s 候选时序修复记录

本记录对应原始入口优化候选、N3 开发综合配置 `sysbus32-x-sram-353-dev-n3`。原始性能窗口为 12 项任务共 1,691,172 cycles，按 150 MHz 条件换算 1064.350640 task/s。本轮只对映射网表作非反相缓冲 ECO；当前尚未完成全部时序、电气及覆盖闭合，吞吐仍是条件测量。

## 已持久化的 hold 修复

615 个原生库 `BUFV2_12TR40` 已通过 PT 修改、原生 `write_changes -format dctcl` 导出、DC 读取原 DDC 回放并生成自身 SVF、全新 PT 进程重载复验。三个阶段均 returncode 0，源漂移、原生工具错误和缺失输出均为零。作业使用 8 核上限，原 SDC、库、宏数量及原有时钟关联保持。

| 完整 PT 检查 | 原网表 | 持久化 hold 候选 |
|---|---:|---:|
| setup（寄存器） | 0 | 0 |
| hold | 434 | 2 |
| clock-gating hold | 27 | 0 |
| removal | 5 | 5 |
| output setup | 1 | 1 |
| 违例检查合计 | 467 | **8** |
| met | 299482 | 299941 |
| untested | 29335 | 29335 |
| 全部检查 | 329284 | 329284 |

修复对象共 232 个唯一端点，最小目标 hold 余量 **+0.034452 ns**、目标 setup 余量 **+0.177250 ns**。每个端点均查询原生 launch/capture clock、rise/fall 的 min/max 路径，并保留完整全局报告。增量更新用于逐颗试验；批次结束和全新 PT 重载执行完整更新。

独立 Yosys 缓冲收缩检查已对原始网表和 DC 持久化网表通过：615 个新增单元均为同库原生证明 I→Z 的 BUFV2；所有原始叶单元、端口、参数及收缩后的连接分区保持。该证据是 mapped→mapped 结构一致性，不代替 RTL→mapped FM、门级延迟仿真或物理时序签核。

## 面积和剩余问题

| 面积口径 | 原库单位 |
|---|---:|
| 全 SoC 标准单元 | 357619.231200 |
| 33 个加速器内部 SRAM | 301901.305662 |
| 保守上界：全 SoC 标准单元 + 33 内部宏 | **659520.536862** |
| 相对原映射新增 | **588.924000** |

353 个实际 SRAM 宏保持不变。上述保守上界不与加速器归属范围小计相加；本轮尚未建立官方 mm² 换算，不能据此宣称通过 2.25 mm² 门槛。

剩余 8 项为：AON 的 bootrom/dwakeup 去毛刺输入 2 项 hold；PMU 与 AON reset catch 的 5 项 removal；GPIO A27 的 1 项 output setup（−5.26054335 ns）。这两项 AON setup 和两项 PMU recovery 原本为 unknown，仍未变成通过。原 PT 的 HF/LF waveform-expansion 警告、29335 项未测检查和无 SPEF 的工程模型限制继续保留。

电气违例仍为 1973 项：max-cap 67、min-cap 1416、transition 490。当前 hold 候选尚未修复这些电气问题。

## 后续原生试验

当前继续处理 GFCM U8 的 21592 负载时钟树，以及普通控制网的高扇出。已准备同一 local net/owner 的四负载探针和分层缓冲方案；四负载探针只验证实际连线、根扇出和原时钟关联，并记录真实电容/转换时间；它从 21592 减到 21589 个负载，但电容 16.317097→16.321159、转换 12.092101→12.095113 ns，未达到电气改善目标。完整分层树从同一修复种子重新开始，必须实际降低根电容且不恶化转换时间后才接受。理想时钟根的 DRC 属性为空，改用已原生查询确认的 `net.total_capacitance_max` 和 GPIO 实际路径点的 `transition` 测量，不用空值代替零。

死逻辑清理计划已由完整映射结构和原生叶单元清单核对：1796 个不可观察叶单元（含 36 个状态单元），保留全部 353 个 SRAM。原生删除前须逐波验证实际输出无叶输入或顶层端口负载；此处只记录准备完成，尚未声称清理或后续时钟/电气修复完成。

## 原件与身份

- [复核 JSON](validation/s3-y32-ingress-perf-native-20261113/timing-hold-r5/review.json)
- [原生全违例报告](validation/s3-y32-ingress-perf-native-20261113/timing-hold-r5/persisted-all_violators.rpt)
- [逐端点余量及插入数](validation/s3-y32-ingress-perf-native-20261113/timing-hold-r5/endpoint-summary.tsv)
- [独立缓冲收缩证明](validation/s3-y32-ingress-perf-native-20261113/timing-hold-r5/mapped-buffer-equivalence.json)
- [持久化面积](validation/s3-y32-ingress-perf-native-20261113/timing-hold-r5/area-upper-bound.tsv)

原网表 SHA256：`882b160f2dfde6a9593f63212ae173fc96bb00b6212c56d304a6e6e80ae4e56e`。

持久化 hold 网表 SHA256：`1e0ca5d1281ff3e296204c75abbf07fa7732628523feab8b1be6289cb7cfc048`。

本地返回包 SHA256：`0916f9d87b86954d0eb749c741d8d0d339fa3bc2572c32eb25e92dfcef8536ec`；本次返回的 38 个文件均核对归档目录 SHA/长度，返回的执行输出再与各原生 execution receipt 核对。原始失败记录及被停止的全量逐颗更新试验保留，未覆盖原综合或原 PT 失败目录。
