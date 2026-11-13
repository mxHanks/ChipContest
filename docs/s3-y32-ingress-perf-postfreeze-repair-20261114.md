# 原1064候选：冻结后的复位修复

本轮从已冻结映射SHA `9b1c0688139e15decdeb0a08b31b50f600bfc3f1fe93056d520ccf3ee501e2e8`继续，所有新实验使用20261114独立目录。23:50冻结数据、回执和报告保持原状。频率、IO、uncertainty、库及原SDC不变，每个原生阶段限8核。

## 当前状态

新候选的原生DC回放、新PT完整重载、75份回传文件SHA／长度验证及独立严格mapped结构证明均已通过。**292项电气违例全部消除**；仍有3项catch removal和4项unknown，本轮尚未时序闭合。没有改动原SDC、库、RTL、频率或IO预算。

| 项目 | 冻结版 | reset3新候选 |
|---|---:|---:|
| 数值时序违例 | 3 | **3** |
| unknown／untested | 4／29332 | **4／29332** |
| 电气违例（max-cap／max-transition） | 16／276 | **0／0** |
| 标准单元面积（原库单位） | 356901.9888 | **357024.5616** |
| 全SoC标准单元＋内部33 SRAM上界 | 658803.294462 | **658925.867262** |
| 保留实际SRAM | 353 | **353** |

新增128颗身份BUF，按17条复位分布网分组，新增标准单元面积122.5728原库单位。完整328981项检查保持总量及逐检查身份；全部29335条未测／违例明细与冻结版一致，没有把unknown计为met。独立收缩2478颗原生I→Z缓冲后，完整原始网络分区一致；1796颗死叶白名单、36颗死状态、353 SRAM及实际SRAM负向检查通过。

12任务RTL复测维持1691172 cycles／304128个Y32逐位PASS，**1064.350640 task/s仅以150MHz为条件**；当前RTL／执行源未变，未另跑mapped带延迟任务仿真。面积仍是原库单位，未完成官方mm²换算。

- 新mapped.v SHA256：`b8d18954b2bc9737d725e312335ec89ea9f6041bcb6d52ecc37e9ebd2b5a2888`。
- 回传包SHA256：`a8235d41fc47c52d111839fa664d89d1463813c0043e612ae1fe1f869df8b1a8`。
- [独立回执审查](validation/s3-y32-ingress-perf-native-20261114/reset3/independent-native-review.json)、[新PT完整coverage](validation/s3-y32-ingress-perf-native-20261114/reset3/reload/persisted-coverage.rpt)、[电气报告](validation/s3-y32-ingress-perf-native-20261114/reset3/reload/persisted-all_violators.rpt)、[严格结构证明](validation/s3-y32-ingress-perf-native-20261114/reset3/mapped-structural-equivalence.json)、[回传原件](validation/s3-y32-ingress-perf-native-20261114/reset3/reset3-api-evidence.tar.xz)。

3个catch端点的新外源max查询均返回0路径，明确记录为缺少传播证明；聚合pin到达不能替代外源证明。下一步逐段读取原生timing arc的双极性max延迟，用原IO预算和受限传播上界保护新的catch试验，原required未知状态继续保留。

## 已排除流程阻塞

旧协调器把17条下游复位分布网试验绑定到无关catch只读诊断，使无关诊断的未完成状态阻塞批量修复；新实验直接以已完成的冻结apply／reload为输入。

新r2复现服务器Python兼容错误：`gzip.compress`不支持`mtime`关键字，网表重绑定解析完成却无法写出封包。改用`io.BytesIO`和`gzip.GzipFile(filename='',mtime=0)`，保留确定性压缩与每份输入SHA封存。旧封包及失败目录保留，新r3通过真实服务器重绑定并进入原生probe。

## 验收口径

每条根按min／max、rise／fall及原有时钟查询有限worst64上下文，272种组合；1477接收端仅用作静态身份目录。完整coverage保持类型总量、数值违例身份和untested身份／原因；所有电气违例逐pin／type比较，禁止新增或恶化。0条路径保持无证据状态，worst64截断单独记录。原生DC回放保留自身及祖先SVF，随后以新PT进程重载；最终映射仍需独立完整连接分区证明、353 SRAM及1796死叶白名单核验。

三个catch外源最大传播的只读API补查与编辑流程分开执行，先读取原生`get_timing_arcs`、`report_delay_calculation`手册和arc属性，再作有限路径查询。任何实际到达数值都不能把unknown required time改记通过。
