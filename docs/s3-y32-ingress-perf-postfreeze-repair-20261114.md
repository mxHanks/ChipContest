# 原1064候选：冻结后数值时序与电气违例清零

本轮新候选已完成原生DC回放、全新PT完整STA、原件回收和两次独立严格mapped结构证明。**数值时序违例3→0，电气违例292→0；仍有4项unknown，未达到完整时序／异步签核。**原SDC、原库、RTL、频率、IO及uncertainty预算保持不变；每阶段限8核。此前23:50冻结版及报告未覆盖，所有新实验单独保存。

## 最终数据

| 项目 | 23:50冻结版 | reset3中间版 | catch3最终工程候选 |
|---|---:|---:|---:|
| 数值时序违例 | 3 | 3 | **0** |
| 电气违例：max-cap／max-transition | 16／276 | 0／0 | **0／0** |
| unknown／全部untested | 4／29332 | 4／29332 | **4／29332** |
| 全部检查／met | 328981／299646 | 328981／299646 | **328981／299649** |
| 全SoC标准单元面积（原库单位） | 356901.9888 | 357024.5616 | **357030.3072** |
| 标准单元＋内部33 SRAM保守上界 | 658803.294462 | 658925.867262 | **658931.612862** |
| 实际SRAM保留数 | 353 | 353 | **353** |

reset3新增128颗身份BUF，按17条下游复位分布网、每组1至16负载切分，消除全部292项DRC。catch3对3个AON `aonrst_catch/reset_n_catch_reg/reg_{0,1,2}/q_reg/RDN`各加2颗身份BUF，共6颗；最终最小slack均由约−0.040106ns改善到**＋0.067213ns**。相比冻结版，新版标准单元面积增加128.3184原库单位；这些口径不是官方mm²。

既有12任务RTL复测为1691172 cycles、304128个Y32逐位PASS，按假定150MHz换算**1064.350640 task/s**。本轮只改映射ECO／实验工具，未改编译RTL、固件和性能执行源，周期结果复用既有实际测量；未重新声称执行CPU12，也没有mapped带延迟任务仿真。unknown和异步资格仍未闭合，吞吐继续是条件测量。

## 最终原件与身份

- 最终mapped.v SHA256：`d83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1`。
- catch3回传包：1923272字节，SHA256 `a0870cf043543db0d1ef4eb3c56fc0fafc8ca624578bfc63dc49ba5d4670a6a0`；80份负载文件逐SHA／长度通过。
- 最终DDC留存原生目录`/tmp/codex-ingress1064-catch-arc-20261114-r3/apply/mapped.ddc`，输出身份由DC回执及fresh PT输入绑定核验；原件包返回实际Verilog、SDC、8份自身／祖先SVF和报告，不含工艺DB。
- [最终完整coverage](validation/s3-y32-ingress-perf-native-20261114/catch3/reload/persisted-coverage.rpt)、[最终电气报告](validation/s3-y32-ingress-perf-native-20261114/catch3/reload/persisted-all_violators.rpt)、[最终面积](validation/s3-y32-ingress-perf-native-20261114/catch3/apply/area-upper-bound.tsv)、[最终原件包](validation/s3-y32-ingress-perf-native-20261114/catch3/catch3-evidence.tar.xz)、[最终独立审查](validation/s3-y32-ingress-perf-native-20261114/catch3/independent-native-review.json)、[交付清单](validation/s3-y32-ingress-perf-native-20261114/catch3/manifest.json)。
- [reset3中间原件](validation/s3-y32-ingress-perf-native-20261114/reset3/reset3-api-evidence.tar.xz)的SHA256为`a8235d41fc47c52d111839fa664d89d1463813c0043e612ae1fe1f869df8b1a8`，中间映射SHA为`b8d18954b2bc9737d725e312335ec89ea9f6041bcb6d52ecc37e9ebd2b5a2888`。

## 验收依据

最终diagnose、edit、DC apply、fresh PT reload四阶段均RC0，漂移、原生工具错误及必需输出缺失为零。原始SDC及三处PT `-add`兼容转换SHA、标准单元／SRAM双库身份、源V／DDC输入字节和祖先链均已核对。完整29332条未测明细与reset3逐身份、条件和原因严格等集，4项unknown保持原身份；没有将未测检查计作通过。26343个寄存器／宏时钟端点关联保持语义一致。

独立严格mapped→mapped证明**PASS**：收缩当前2484颗原生函数I→Z身份BUF后，所有保留原始叶单元的层级身份、类型、参数、端口、位宽及完整连接分区相同；精确1796颗死叶白名单和其中36颗死状态重证、353 SRAM保留。删除实际SRAM或篡改其类型的负向检查均被拒绝。[严格证明原件](validation/s3-y32-ingress-perf-native-20261114/catch3/mapped-structural-equivalence.json)。该证明不能替代RTL→mapped FM或物理签核。

catch工程传播上界从原SDC的ERST max IO delay0.5ns出发，逐段读取实际启用的net／cell timing arc双极性最大延迟；每端点由原5段变为9段。正、负、非单调弧分别组合输入极性，独立审查重新累加通过。最终rise／fall上界由**0.621707／0.660418ns**变为**0.736334／0.799307ns**，增加0.114627／0.138889ns，均低于0.5ns保护预算；每端点新增2颗，未超8颗预算。此值是当前库及网络模型下的传播上界，不能代替required time或max slack。[逐段原生弧数据](validation/s3-y32-ingress-perf-native-20261114/catch3/reload/native-arc-delays.tsv)。

## 仍未闭合

报告保留4项unknown：bootrom／dwakeup去毛刺首级T_8_reg/D的两个setup，以及PMU `erst_reset_r_reg/SDN`、`erst_reset_r_r_reg/SDN`的两个recovery。HF 6.666666667ns与LF 30517.578125ns的周期比约4577.64；原生PTE-052文档说明，展开范围不足时无法计算跨这些时钟的有效required time。原生变量发现没有找到可用的整数展开控制量，继续重复相同STA不会将其变成已证明的裕量。

上述4项之外，三个catch的外部HF→LF最大上下文仍未取得原生required；本次只建立受限传播上界，不能以内部分支的LF watchdog路径代替外部recovery资格。固定延迟不能证明任意异步到达相位安全。要完成这部分验收，需要明确并验证异步输入／释放的CDC/RDC时序合同；本轮未增加false path、multicycle、异步clock group或ideal network来使其消失。

外部复位断言脉宽、亚稳态、PVT／物理偏斜、SPEF／CTS／布局后多角时序、官方面积mm²、功耗与600样本最终评测仍未由本轮证明。当前结论是**已报告的数值违例和电气违例清零，工程映射一致性通过；完整时序资格仍未闭合**。

## 流程修复与失败记录

新实验首先解除17根下游复位分布网对无关catch只读诊断的等待依赖。reset r2原生复现服务器旧Python不支持`gzip.compress(mtime=...)`；改用`io.BytesIO`＋`gzip.GzipFile(filename='',mtime=0)`后，新r3重新解析实际冻结网表并封存输入哈希，原生4负载probe、128组split、DC和新PT均通过。旧封包、失败目录及冻结原件保留。

catch r1／r2在诊断阶段保护性拒绝，没有修改网表。原始native行证明net arc存在且`is_disabled=false`，但其`is_user_disabled`和`sense`为空；原过滤器错误排除了这些弧。r3仅以真实启用状态和精确from／to筛选网络弧，物理线按非反相传播；单元弧仍要求明确sense和有限非负延迟，未知延迟不按0处理。[失败诊断原件](validation/s3-y32-ingress-perf-native-20261114/catch3/rejected-r2/native-tail-arc-diagnostic.tsv)单独标记，未混入最终四份clean回执。

新catch runner还将untested保护从集合包含收紧为身份／原因完全相等；真实原件自对照通过，修改unknown原因的负例被拒绝。本轮没有全量重综合或1477端点逐项扫描。
