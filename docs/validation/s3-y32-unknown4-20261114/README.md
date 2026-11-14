# 四项 unknown：原生诊断与数字合同证据

状态：**UNKNOWN4_NOT_CLOSED**。本目录补充诊断和可复现数字验证，不替代[当前 catch3 最终原件](../s3-y32-ingress-perf-native-20261114/catch3/)，不修改该目录及其 manifest。生产 RTL、映射、SDC、吞吐和面积结论保持不变。

| 文件 | 内容 / 实际结论 |
|---|---|
| [unknown4-audit.json](unknown4-audit.json) | 原四项精确身份；原 frozen PT 日志/时钟 SHA 绑定，检出 1 条 PTE-052，明确未闭合 |
| [frozen-native/](frozen-native/) | 本轮回收的旧最终 PT 日志与时钟报告，逐字节匹配原 catch3/execution 输出哈希；不是新 STA |
| [native-discovery-r3/](native-discovery-r3/) | 原生 T-2022.03 空设计 API/手册探测，2核、RC0、Error/Fatal0；28份payload逐SHA核验 |
| [native-discovery/](native-discovery/) / [native-discovery-r2/](native-discovery-r2/) | 前两轮诊断，保留 PT-063 启动错误；不计为 clean EDA 验收 |
| [async-contract/result.json](async-contract/result.json) / [simulation.log](async-contract/simulation.log) | 固定 RTL、真实七个生产模块：34场景/178断言通过，仍非CDC/RDC或物理签核 |
| [selection-negatives/](selection-negatives/) | 错误/脏子模块的编译前拒绝回执（进程内身份mock，未污染实际子模块） |
| [rejected-test-oracle/](rejected-test-oracle/) | 首次数字测试失败：测试把WDOG原因编码错写11，实际为10；改正测试后新目录通过，生产RTL未改 |
| [rtl-contract-audit.md](rtl-contract-audit.md) | 接收链与外源路径、可选处理方式及功能影响 |
| [pt-resolution-audit.md](pt-resolution-audit.md) | 原周期/边沿与同版本工具能力审查；以r3实际man补充判断 |
| [final-independent-review.md](final-independent-review.md) | 门禁负例、r3原件与最新数字receipt的独立复核 |

新发现 `timing_max_normalization_cycles` 只限制归一化slack分母；`timing_path_arrival_required_attribute_include_clock_edge` 只控制path属性是否包含clockedge。没有找到可据此改变原时钟展开限制的有效设置，本轮未设置这些变量。

每个native归档内的 `execution-files.json` 绑定其payload长度和SHA256。数字仿真器二进制未重复入库，可用公开runner编译；其实际哈希保留在receipt。`SHA256SUMS` 核对本目录公开文件，不包含自身。

复核与下一步见[跟进报告](../../s3-y32-ingress-perf-unknown4-followup-20261114.md)和[板级合同待确认表](../../s3-y32-async-input-contract.md)。原检查详细身份含met的完整baseline/candidate尚未重采，本轮没有任何将unknown转为met的原生证据。
