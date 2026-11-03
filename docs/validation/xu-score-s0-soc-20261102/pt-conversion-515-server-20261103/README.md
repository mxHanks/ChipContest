# xu 实际 PT TC515 反例探针03

状态：`ACTUAL_COUNTEREXAMPLES_REVIEWED_POLICY_UNRESOLVED`、`NOT_QUALIFIED`。服务器实际 PrimeTime `T-2022.03-SP5-1` 新进程已退出0，12项合成 SAIF 查询全部完成；12个原始文件、76,910字节均按服务器原导出 manifest 验证。该实验补充[探针01/02](../pt-conversion-probes-server-20261103/README.md)，不改写其输入、原结果或资格状态。

| 合成 stats 对照 | 输入 pin / 输出 pin 的实际 simple rate | source |
|---|---:|---|
| TC514，已知 dwell | A[0] / Q[0] 均 `5.62422e-05` | file |
| TC515，已知 dwell | A[1] / Q[1] 均 `5.63517e-05` | file |
| TC516，已知 dwell | A[2] / Q[2] 均 `5.64611e-05` | file |
| TC515，TX=1000 | A[3] / Q[3] 均 `5.63517e-05` | file |
| 4个实际 partial-X Q stats 的合成重放 | Q[4..7] 均 `5.63517e-05` | file |

所有 case 的 duration=9,139,040,000,000 ticks、timescale=1fs、库时间单位=1ns；四态 dwell 均恰好等于 duration，IG均为0。各 case 的 glitch 查询为0/file。四个实际 Q witness 都有正 TX **和正已知 dwell**，不是 full-X；stats 复制后被重放到同一个实际链接宏的 Q[4..7]，没有再次执行原任务，也不能用作新的任务活动测量。

关键结果是旧的分阶段 binary32 假说：`f32(f32(f32(TC)/f32(duration))*1e6)` 再六位打印，在本组 TC515 会预测 `5.63516e-05`，与实际 `5.63517e-05` 不同。它在01/02的93项跨单位对照都吻合，在03只有4/12项吻合。对照已经排除了“只因输入/输出方向不同”或“只因出现TX”这两种局部解释。直接精确十进制、仅最终一次binary32、先换算物理时长后binary32的模型在03为12/12，但它们在01的TC8157已有实际反例，因此也不能改称普遍转换规则。`summary.json` 保留全部模型预测及反例；没有增加容差或拼接按TC取巧的规则。

原实际 witness stats 来源是 P6 原准备工件所冻结的 `measured-sram-pins.json`（8,583,046字节，SHA `7fb095ed51ea9b37f40350302b40a8a717c39f77e641ecd30fba63c7bc35e82c`）；本目录无损 gzip 保存全部22,512项，逐项证实四个原路径和统计值。**服务器03 producer直接硬编码了这些stats，并未自行读取/冻结该文件**；本地离线审核独立补证与原冻结源相同，不能把它说成probe03自身完成的源不变性检查。源是原任务 SAIF 派生的 pin 统计，本目录未重新传回或重哈希原25MB raw SAIF。

服务器作业目录为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/pt-activity-conversion-515-probe-20261103-03`。导出 `xu-s3-timing-probe-export-20261103-12.tar.xz` 为279,572字节，SHA `5330f5c8b03d9a8f8077f1dbc51908881bb9d472ebad3c3b4fd73d81aa180336`；`original-export-manifest.json` 保留174项原导出记录，`selected-manifest.json` 仅选本作业。`recorded-producers` 与实际server receipt的8959字节/SHA一致；其原始输出和空白未修改。

离线检查复用并冻结01/02归档中的实际 mapped inventory、prepared、power Tcl原件。实际 mapped.v SHA `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`、相同SS DB链接前缀与01/02相同。原SDC身份亦相同，但探针没有加载SDC、创建clock、update_power或覆盖switching activity。缺失大型DB/netlist的本地副本时，不声称在本目录再次重哈希服务器大文件。

重放离线审核（从功能树根目录）：

```sh
python3 docs/validation/xu-score-s0-soc-20261102/pt-conversion-515-server-20261103/check-evidence.py
python3 docs/validation/xu-score-s0-soc-20261102/pt-conversion-515-server-20261103/check-negative-cases.py
```

原实际命令是到 `tc515-witness-fs` 目录执行 `pt_shell -f probe.tcl`。同服务器重跑必须使用全新目录副本并保留原绝对输入，不覆盖本次原件。此证据仍没有闭合转换策略、条件功耗、全SoC能耗、完整150MHz或任何评分；后续继续实际工具对照和[联合活动观察器](../pt-conversion-probes-server-20261103/joint-observer-spec.md)。
