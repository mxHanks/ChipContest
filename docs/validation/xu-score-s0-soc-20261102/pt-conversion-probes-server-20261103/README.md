# xu 实际 PT 转换探针 01 / TB02

状态：`ACTUAL_PROBES_REVIEWED_POLICY_UNRESOLVED`，`NOT_QUALIFIED`。本目录保存实际服务器 PrimeTime `T-2022.03-SP5-1` 的合成 SAIF 转换试验，回答“数值查询如何表示输入统计”的局部问题；这些合成计数不能作为任务活动或任务能耗。

7 个独立 PT 进程均退出 0，完成标记各出现一次。01 的 6 组加 TB02 共 97 个查询；74 个原始文件共 544,148 字节逐一匹配服务器导出 manifest。所有对象来自实际链接的同一个 `RAMSP1024X16`，01/02 所选 31 个或 1 个对象均为输入 pin，不能外推输出 pin、其它宏或所有未知态行为。

## 实际发现

| 检查 | 观察 | 可支持的结论与限制 |
|---|---|---|
| 时间单位 | `report_units` 为 1 ns；三组 SAIF 分别 1 fs / 1 ps / 1 ns，整数 duration 均为 9,139,040,000,000 | 查询率随实际时长缩放；三组不是同一个物理时长。fs 组长 9.13904 ms。 |
| 精度边界 | fs、TC=8157 实测 `0.000892544`，直接十进制六位或仅最终一次 binary32 舍入为 `0.000892545` | “直接精确实数后六位打印”不能解释全部实际输出。 |
| 分阶段假说 | `f32(f32(f32(TC)/f32(duration))*unit_scale)` 再六位打印吻合三组全部 93 项 | 只是有限样本上的诊断模型；不证明内部算法唯一、不成为允许误差或正确性判据。 |
| 计数不可逆 | TC 为 2^24−1、2^24、2^24+1 时均打印同值；2^25 附近亦然 | 六位查询不能精确恢复整数 TC。完整原始 SAIF 仍是计数依据。 |
| TX | partial-X 查询 SP 与 `T1/(T0+T1)` 打印值相符；full-X 输入 TC=0 仍返回 SP=`0.5`、TR=`0`、source=`file` | `file` 或数值零不证明信号有已知逻辑活动。原始 TX 必须保留，不能算成已知零。 |
| TZ | TZ=duration//7 的输入查询 SP=`0.388889`，与已知 dwell 比相符，非 T1/总时长 | 一个样例支持排除 TZ 的条件比例；不能证明所有未知处理。 |
| IG | TC=101、IG=37 时 simple TR=`1.10515e-05`，glitch=`2.02428e-06` | 该样例与 IG/(2×实际时长) 的库单位打印率相符，simple rate 未把 IG 直接相加；样本不足以制定普遍转换政策。 |
| TB01 负例 | T0+T1+TX+TZ+TB 比 duration 多 37 ticks，PT 仍接受并退出 0 | 工具接受不验证 SAIF dwell 合法性。原件不修补，本地严格 SAIF 读取器应拒绝。 |
| TB02 修正 | T0 减 37 后 dwell 恰等于 duration，PT 仍输出同样六位值 | 37 ticks 太小，打印精度不足以区分 TB 的处理方式；TB 解释尚未闭合。 |

`summary.json` 保存每项原始 stats、查询字符串、来源及模型吻合情况；不同模型不一致的结果也完整保留。`liberty-arc-observer-plan.json` 与 [joint-observer-spec.md](joint-observer-spec.md) 是后续只读联合活动观察器的**规格**，尚未实施或测量。

## 来源和不变性

服务器基目录为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102`。两个实际作业为 `pt-activity-conversion-probe-20261103-01`、`pt-activity-conversion-tb-probe-20261103-02`。原始导出 `xu-conversion-gating-export-20261103-11.tar.xz` 为 249,704 字节，SHA-256：`6c6e8b2ede4d1462ed25296e4e09e0212ac77c23a1b136a94a6ae6beec6d4ee1`。本目录的 `original-export-manifest.json` 是其中全体 196 个 payload 的原 manifest；`selected-manifest.json` 只选上述两作业。传输后逐项核对原字节，未改动日志空白。

`recorded-producers` 的两个 Python 文件与各自服务器 receipt 的 producer 字节、SHA 完全一致。小型原始 `prepared.json`、`power.tcl` 及无损 gzip 压缩的实际全量 mapped inventory 保存在 `recorded-frozen-inputs`，用于复核原链接前缀、336 宏/22,512 个 pin、实际对象顺序/方向和服务器冻结身份。SRAM 功耗弧报告来自独立导出07（148,636 字节；SHA `088d83d9ea693f21a175b3b00e2df435658182ef1fc19c5e187a1c29cafb6426`）；该报告原字节 SHA 为 `f1d18b00fece31f942a514505d808e704179c3a99437aebb9abf152823757ba7`，其原 manifest 条目亦保留。

实际 mapped.v SHA 为 `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`。原 analysis SDC SHA 为 `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`，仅记录原配置身份；**探针没有加载 SDC、创建 clock、执行 update_power、覆盖 switching activity 或 set_case_analysis**。每组从原 power.tcl 中截至 clock 设置之前的实际链接前缀开始；每组为新 PT 进程。DB、mapped.v 等大文件未在本目录重归档，其字节身份由实际执行 receipt 和原 prepared 记录支持，本地检查不声称重新读取了服务器大文件。

没有从这些试验推出完整 pin 转换策略、Liberty 条件功耗、全 SoC 能耗、150 MHz 资格或比赛评分。输出 pin TC515 与真实未知 Q 的专门探针03由后续独立证据包承接；本目录不把未来结果写回既有 01/02 输入。

## 重放

在本功能树根目录执行离线严格检查：

```sh
python3 docs/validation/xu-score-s0-soc-20261102/pt-conversion-probes-server-20261103/check-evidence.py
python3 docs/validation/xu-score-s0-soc-20261102/pt-conversion-probes-server-20261103/check-negative-cases.py
```

在同服务器工具链环境，`cd` 到相应组目录后 `pt_shell -f probe.tcl` 即为 receipt 中的原命令；必须将输出指向全新副本，以免覆盖原件。原 Tcl 的绝对 mapped.v、DB 和 SAIF 路径在 `probe.tcl` 中可审阅。顶层 producer 无参数会创建固定目录，历史目录已存在时会拒绝；复测应先审阅并改为新的独立输出目录，不能删除本次目录来重跑。
