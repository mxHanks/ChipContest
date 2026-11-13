# 原1064候选：继续时序修复检查点

本记录延续[22:55最终报告](s3-y32-ingress-perf-final-timing-report-20261113.md)。目标仍为原1064.35 task/s候选，RTL保持`5470c565`。按用户23:50截止要求，**23:48:46冻结async r5（含cleanup r3）**；2,036,672字节回传包在**23:49:57.970**完整落盘并通过传输整包SHA，解包与64份负载文件逐SHA/长度核验于23:50:08完成。冻结后仅补充核验和报告，不修改候选或重跑EDA。

## 冻结结果

| 项目 | 冻结数据 |
|---|---:|
| 数值时序违例 | **3**（前轮7，原映射467） |
| hold／removal违例 | **0／3** |
| setup/recovery unknown | **4**，保留原未测状态 |
| total／met／untested | 328981／299646／29332 |
| 电气违例 | **292**，无新增或恶化 |
| 标准单元面积 | **356901.9888 原库单位** |
| 内部33 SRAM面积 | 301901.305662 原库单位 |
| 保守上界 | **658803.294462 原库单位** |
| 12任务RTL周期／假定150MHz吞吐 | 1691172／**1064.350640 task/s** |

吞吐复测沿用22:40:41–22:50:08的实际CPU12运行，304128个Y32逐位PASS；此次未更改RTL及编译执行源，ECO没有改变周期性能。不能将条件150MHz吞吐写为时序签核吞吐；没有新mapped带延迟任务仿真，也没有官方mm²换算。

四端点工程修复新增12颗原生身份BUF：两个AON D各2颗，两个PMU SDN各4颗。最终完整STA裕量依次为**0.055039、0.055039、0.077078、0.080822 ns**；最大检查仍UNKNOWN。diagnose/edit/DC apply/fresh PT reload均RC0，源漂移、原生工具错误、缺失输出均为空；完整coverage没有新违例或新untested，电气逐身份无新增/恶化。353 SRAM保留，35颗空clock BUF已移除，保留1525颗clock BUF、根叶扇出18。

- 冻结mapped.v SHA256：`9b1c0688139e15decdeb0a08b31b50f600bfc3f1fe93056d520ccf3ee501e2e8`。
- 原件包SHA256：`5905db8f5e53c0a85c9a66192841111b822ec84d646083967db1e09898ba00e8`。
- [回收与冻结回执](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/freeze-recovery.json)、[原生轻量证据包](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/frozen-2350-evidence.tar.xz)、[新PT完整coverage](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/async5/reload/persisted-coverage.rpt)、[完整电气报告](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/async5/reload/persisted-all_violators.rpt)。

**未纳入冻结**：reset r1的17根／128组批量试验仍停留在等待只读catch诊断的协调阶段，原生probe/split未执行，已停止其协调器。三个catch的外部最大传播新诊断没有完成回执；这是实际流程阻塞。不能将其静态计划写成已实施修复。剩余3个catch removal、4个unknown、292个复位电气违例均未闭合。

## 核验及未闭合项

冻结后独立严格mapped→mapped结构证明**PASS**：收缩当前2350颗原生I→Z身份缓冲后，保留原始叶单元的层级身份、类型、参数、端口、位宽及完整连接分区相同。精确1796颗原死单元白名单重新证明，其中36颗状态单元；全部353 SRAM保留。删除实际SRAM和篡改其类型的负向检查均被拒绝。此证明不能替代RTL→mapped FM或物理时钟／复位签核。[严格证明原件](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/mapped-structural-equivalence.json)。

仍有3项reset-catch removal（均为aonrst_catch RDN，slack均为−0.04010564ns），4项setup/recovery unknown，以及292项复位网电气违例（16项max-cap、276项max-transition）。未知和no_clock/constant_disabled逐检查原因未新增或改变；没有增加false path、multicycle、异步时钟组、ideal network，也未改变频率或IO预算。

真实异步输入或复位释放若能以任意相位到达接收边沿，增加固定延迟只会平移相位，仍可能落进setup/hold或recovery/removal窗口。实际最大传播时间有数值不能为UNKNOWN的required time建立裕量；“不超过基线＋0.5ns”只是工程试验保护，不构成异步、RDC、外部断言脉宽、物理PVT/偏斜资格。本次也没有SPEF、CTS、布局后多角时序、官方面积mm²、功耗或600样本最终评测证明。

独立原生回执与报告审查确认5份clean回执、64份负载文件、原SDC／PT兼容SDC、双库和祖先链身份一致；292项DRC的pin／type／slack与cleanup r3逐项相同。26343行时钟关联表的行顺序变化不改变语义。[独立审查记录](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/independent-native-review.json)、[交付清单](validation/s3-y32-ingress-perf-native-20261113/timing-frozen-2350/manifest.json)。

原生最终DDC留存于`/tmp/codex-ingress1064-async-edge-20261113-r5/apply/mapped.ddc`；回传包包含实际最终Verilog、SDC、各级自身与祖先SVF及报告，排除工艺库。原约束以原始SDC SHA、PT三处-add兼容转换SHA和实际执行输入绑定核验；DC导出的mapped.sdc是独立输出，不能用其文本SHA冒充原始SDC SHA。

## 修复过程和实际阻塞

r3延迟试验在最终完整STA中被拒绝：PMU局部裕量0.038940ns回落至0.023155ns。r4改为每次插入full更新并跨4端点迭代，但尚未修改的相邻PMU最大到达从0.627842降至0.619017ns，被原“必须不减小”的下限拒绝。r5将最大传播限定为非负且不超过基线＋0.5ns，保留独立最小裕量、每端点8颗／总32颗预算和完整STA／DRC保护，最终实际使用12颗并通过DC和新PT。

clock cleanup r2因`all_connected`对pin返回net而拒绝；r3先取得唯一local net，再执行`all_connected -leaf`递归验证，并用父单元is_hierarchical区分边界和真实叶输入。分两波删除34＋1颗新增时钟BUF，原生逐波无观察性保护和完整保留时钟关联检查通过。该中间阶段仍7项数值违例；随后async r5将其中4项修复，冻结结果为3项。

复位分组工具已完成本地预检、封包传送及实际网表重绑定功能：17根、128组，每组1至16负载；1477接收端只是静态目录。原生查询限定17根的worst64上下文，并有完整coverage与DRC逐身份保护。截止冻结，其协调器因等待catch只读诊断而未启动原生probe／split，已停止，不把工具准备或静态组数记作修复完成。三个catch的新传播诊断没有完成回执，后续须先排除此流程阻塞。

## 冻结后的交付规则

23:57检查点已被用户23:50回收冻结要求取代。当前候选数据保持冻结，本次仅补充原件哈希、严格证明和交付清单。剩余复位修复必须使用新的实验／候选和独立报告，不能覆盖本次冻结数据或将未闭合项改记通过。
