# SRAM 隔离候选的初步综合与 PPA 边界

> **2026-10-18当前结论：**独立参考网表ECO及最终12层门级回放通过，46,035标准单元、0.057015238mm²标准逻辑面积（不含SRAM）；同原SDC覆盖setup最差+4.652084ns、data hold+0.001379ns、reset removal+0.055262ns。48378标准输出的已知cap/transition/clock检查通过；182宏负载及1152宏输出驱动未知。原版负Slack及所有失败保留。此为公开库/ideal clock/统计wireload下的宏切口参考结果，hold裕量很小；正式150MHz/总面积/功耗仍BLOCKED。

> **2026-10-17计划审计更新：**下文最初表格记录核心范围的历史映射；当前含接口综合仍因组合环FAIL。后续全FF结构展开和局部STA已有结果，见本文末尾更新；旧mapping/STA脚本之后有修改，不能把旧结果当当前脚本验收。正式PPA仍BLOCKED。

当前候选的简表如下；后续章节的旧值属于各自历史版本。

| 项目 | 原缓冲映射 | 最终独立参考ECO |
|---|---:|---:|
| 标准单元 | 46026 | 46035 |
| 不透明SRAM原语 | 72 | 72 |
| 标准逻辑面积（μm²） | 56997.416 | 57015.238 |
| setup最差Slack（ns） | +4.652084 | +4.652084 |
| data hold最差Slack（ns） | -0.013133 | +0.001379 |
| reset removal最差Slack（ns） | -0.255385 | +0.055262 |
| 最终网表真实12层输出 | 已有304128输出回放 | 新网表重新回放304128输出通过 |

完整网表ECO增加9个BUF_X1、一处BUF_X1→X16、3个NOR4和2个NOR3从X1→X2，逻辑面积累计+17.822μm²。第三候选全网cap曾4驱动/8极性失败，第四候选重新扫描48378标准输出/32类上限，已知cap/transition/clock零违例，最小已知电容余量0.362942570fF；182宏负载/1152宏输出驱动仍未知，不据此声称完整电气通过。Nangate45 typical（1.1V/25°C）、OpenSTA2.0.17、原6.666666667ns/0.1ns uncertainty与5K_hvratio_1_1统计wireload不变；这不是提取寄生或官方PVT。宏边界1153输入位缺delay、2436输出位/端点不完整约束仍按原口径保留，不能把部分参考WNS/TNS=0推广为全路径通过。完整SRAM面积、宏驱动/输入电容、动态与漏电功耗仍未知。

索引：[第四候选及已知电容收口](../docs/runs/sram-reference-cap-closure-20261018.json)，[历史第三候选](../docs/runs/sram-reference-eco-20261018.json)保留；[方法与复现入口](../docs/optimization/SRAM_REFERENCE_ECO.md)。当前204主机测试和静态入口通过，正式Make电气入口实跑通过。门级使用相同Liberty功能模型/逻辑SRAM契约、Verilator两态零延迟，正式宏与全输入形式结论不由此成立。

日期：2026-10-17。对象：`kwt_linear_engine_rowpair_sram`，`PIPE_MUL=1`、`RESULT_BUFFERS=2`、`SRAM_BACKEND=1`。**完整引擎 Black Box 结构：PASS；参考标准单元映射：PASS；官方面积、完整150 MHz时序和功耗：BLOCKED。** Black Box不包含面积/时序/功耗表，缺失项保持null，不按零计。

## 本轮已执行结果

运行命令：

```bash
source env/activate.sh
python3 scripts/synth/run_memory_blackbox.py --map-logic --timeout 300
```

证据：[结果JSON](../artifacts/runs/20261017T142301.674275Z-sram-blackbox-c7383994/result.json)、[结构日志](../artifacts/runs/20261017T142301.674275Z-sram-blackbox-c7383994/prepare.log)、[映射日志](../artifacts/runs/20261017T142301.674275Z-sram-blackbox-c7383994/mapping.log)、同目录 `hierarchical.json`、`blackbox-structure.json`、`mapped.v`、`mapped.json`。结果保存源/脚本/工具/库的SHA、完整命令、原生退出码及日志SHA；结构和映射均exit=0，均有唯一完成标记及Yosys完整结束行。

| 项目 | 实测/核验值 | 范围 |
|---|---:|---|
| Yosys | 0.33，git 2584903a060 | 项目本地工具 |
| 逻辑 bank | 20 | 2 X + 8 W + 8 bias + 2 result |
| 逻辑存储容量 | 415,744 bit / 50.75 KiB | 不含E203共享SRAM |
| 保留不透明原语 | 72 | 50×128×16 + 22×1024×16 |
| 配置存储容量 | 462,848 bit / 56.5 KiB | 候选拼接容量，不是物理面积 |
| 结构乘法器 | 16个signed16×16→32 | 数值/计算资源未缩减 |
| 结构寄存器 | 2,102 bit | opaque SRAM外的控制/流水/结果快照等 |
| 映射标准单元 | 41,683 | 不含72个opaque SRAM |
| 映射DFF | 1,961 DFF_X1 + 134 DFFR_X1 | 标准单元级统计，不能等同结构寄存器位数 |
| 映射MUX2 | 511 | 不含宏内部选择逻辑 |
| 参考逻辑面积 | 51,844.73 µm² = 0.05184473 mm² | 计算/控制及bank译码/返回mux，不含SRAM和ICB接口 |
| 未映射逻辑/意外存储展开 | 0 / 未发现 | 脚本拒绝残留`$mem`、容量错误、丢失opaque及大量FF |
| 完整时序/功耗 | BLOCKED / NOT_RUN | 未提供宏Liberty和活动功耗流程 |

映射采用队友仓库已审计的 `NangateOpenCellLibrary_typical.lib`，SHA256=`8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1`，typical、1.10 V、25 °C。[库和单位依据](../docs/integration/LIBRARY_AUDIT.md) 解释µm²换算依据。它是参考标准单元库，尚未被确认为组委会指定工艺。ABC命令为 `abc -fast -D 6667 -liberty ...`；6667 ps只是映射目标，**不是SDC、STA或150 MHz通过证据**。未使用假SRAM Liberty、零延迟弧或额外false path。

映射日志的8类扫描触发器表达式解析警告来自Yosys 0.33读库时跳过不支持的scan表达式；最终网表没有使用这些扫描单元，所有实际标准单元均能在已审计库中解析，`check -assert`通过。`Area ... unknown`对应已列出的72个SRAM Black Box，是预期缺模型，故仅报告标准逻辑面积，不把该报告的Chip area称为完整加速器面积。

## FF_FALLBACK及原实现边界

原 `kwt_linear_engine_rowpair.sv` 完整保留；新的FF后端也保留并可独立仿真。当前原rowpair的双结果缓冲结构证据 [原始结构报告](../artifacts/runs/20261015T101004.417222Z-rowpair-structure-d65ce7e8/result.json) 为415,744 bit逻辑存储、2,086 bit非存储寄存器。该流程保留RAM，**没有运行当前全容量FF+MUX标准单元映射**，因此不在这里编造当前FF面积/Slack。若将这些逻辑存储完整展开，至少需相应有效负载位的存储元件，另有地址译码与读mux；新拼接版的未用填充位可能被优化，不能简单把配置bit数当最终DFF数。

队友原始历史 `LinearComputeCore_nangate45.log` 测得263,958 DFF_X1、295,146 MUX2_X1、参考面积2.159601598 mm²，说明其完整权重FF映射的规模；这份报告工具为Yosys0.52、范围和RTL不同，且缺完整同源绑定，**不用于计算本轮面积改善比例**。[历史报告审计](../docs/integration/LIBRARY_AUDIT.md)

解决的问题是防止正式早期综合意外将几十万bit载荷展开成FF/MUX，保留可检查的宏边界并映射周边逻辑。收益不是“面积已降低到0.0518 mm²”；真实总面积仍要加官方内部SRAM、新增ICB/搬运接口及全部新增逻辑，且不能与复用E203/512KiB共享SRAM混计。

## 尚不可验证及下一步

| 缺失项 | 当前状态 | 取得后操作 |
|---|---|---|
| 官方16×128/1024/4096宏模型、端口/延迟/冲突规范 | BLOCKED | 填充adapter，三后端等价与全矩阵/12层/SoC回归 |
| 官方SRAM面积、功耗及setup/hold Liberty | BLOCKED | 按72实例或重新核实的布局计面积；全路径STA；完整窗口功耗 |
| 正式标准单元库/PVT、正式I/O/负载/互连/时钟条件 | BLOCKED | 指定工艺同源综合与150MHz setup/hold/覆盖验收 |
| 本轮参考静态时序 | NOT_RUN（工具部署另行记录） | 只分析可覆盖逻辑路径，独立列未建模宏路径和约束覆盖 |
| 同综合网表VCD/SAIF与SRAM活动 | NOT_RUN | 完整装载—CPU调度—计算—全部写回窗口，分域动态/漏电 |

不得从正的局部Slack推导全系统时序，也不得从逻辑面积直接与2.25 mm²比较。正式面积门槛见[面积预算](../docs/optimization/SRAM_AREA_BUDGET.md)，完整证据门槛见[PPA接收契约](../docs/optimization/PPA_INPUT_CONTRACT.md)，官方接入按[迁移手册](../docs/OFFICIAL_SRAM_INTEGRATION.md)执行。

自动化入口 `make synth-memory-blackbox` 只做完整top结构；`make synth-logic` 加参考逻辑映射。输出使用唯一目录，不覆盖旧证据；行为后端在综合时故意失败；官方adapter缺失时不得回退到FF或行为实现。

## 计划审计补充：真实失败和已完成FF结构

本节来自现有原始日志与SHA的只读复核，本轮不执行新EDA。当前 `make synth-logic` 已选择含ICB接口；原core-only的0.05184473mm²不覆盖该新增接口，更不包含SRAM，不计算其与2.25mm²的剩余预算。

- **含接口结构FAIL**：`artifacts/runs/20261017T142838.405967Z-sram-blackbox-9f144c6d/result.json`，原生exit1。反馈链为request_ok→start_valid→load_ready→request_ok；计划最小修复候选adapter，保留旧源和失败记录。
- **全FF结构PASS**：`artifacts/runs/20261017T143003.767607Z-sram-ff-reference-aa213bf0/result.json`，exit0/71.279s/无timeout，429231 register bits、0 memory cells，Yosys日志峰值1893.26MB。只展开并统计RTLIL，没有全核标准单元映射面积/时序或功耗。
- **单原语FF映射PASS**：`artifacts/runs/20261017T142749.864494Z-sram-ff-reference-fa89f2b6/result.json`，128×16、7823标准cell、0.017232012mm²。不能线性外推全核或当真实SRAM面积。
- **局部STA工具完成、时序FAIL**：`artifacts/runs/20261017T142935.792193Z-sram-partial-sta-a094c9c2/result.json`；OpenSTA2.0.17项目本地工具，Nangate45 typical。setup WNS=-22.923624ns/TNS=-22525.019531ns；原始hold.rpt最差-0.004303ns，旧result没有汇总hold。新脚本已加入hold/coverage校验但尚未执行，需先重新mapping绑定。
- **瓶颈证据**：read_valid FF→INV→NOR2→乘积寄存器保持MUX→DFF。INV/NOR输出分别499/472个sink pin，NOR延迟23.657425ns；先检查驱动/负载与缓冲映射，尚无证据要求更改乘法算法。

参考STA使用6.666666667ns、0.1ns clock uncertainty、普通I/O max/min delay 0.5/0.1ns、输入transition0.1ns、输出load10fF、理想clock；该历史条目原把互连描述为无wire parasitics，后续电气复核确认实际使用库默认统计wire-load，纠正见末节。这些是开发假设。72宏切口共432端口组，SRAM delay/cap、reset recovery/removal未建模，报告明确列1153个输入和2436个输出缺delay及2436个未约束端点，未添加false/multicycle path。即使后续局部转正，完整150MHz仍BLOCKED。

当前构建入口还包括 `make synth-ff-reference`、显式opt-in的 `make synth-ff-full-reference ALLOW_FULL_FF=1`、`make sta-logic MAPPING_REPORT=<新含接口mapping报告>`。脚本或RTL变化后先生成新网表，不能机械修改旧manifest来绕过来源检查。修改计划见 `docs/superpowers/plans/2026-10-17-sram-subsystem-plan.md`。


## 2026-10-18：当前含接口参考结果

当前top为`kwt_icb_slave_sram`，PIPE_MUL=1、RESULT_BUFFERS=2、BLACKBOX；原候选组合环已消除。工具/库沿用Yosys0.33、ABC、OpenSTA2.0.17和Nangate45 typical，均为参考环境。

| 项目 | 当前实测结果 | 证据 |
|---|---:|---|
| 结构/映射 | PASS / PASS | `20261018T020610.045677Z-sram-blackbox-173fe72f/result.json` |
| opaque原语 / MAC | 72 / 16 | 50×128×16+22×1024×16，未展开内部payload |
| 标准单元 / 参考逻辑面积 | 44120 / 0.055476428mm² | 含新增ICB、核心、bank译码/返回选择；不含宏和复用平台 |
| setup WNS / TNS | -22.790979ns / -22493.648438ns | `20261018T020713.509216Z-sram-partial-sta-2fe2e15f/result.json` |
| hold最差Slack | -0.004303ns | 同一局部STA，Timing FAIL |
| 缺input/output delay；未约束端点 | 1153 / 2436；2436 | 显式宏/reset切边，不能视为完整150MHz路径覆盖 |
| 官方SRAM面积/访问时间/功耗 | null / 未建模 / null | 官方文件缺失，正式PPA BLOCKED |

独立复核以上两个报告的26/19个带SHA文件记录均一致。局部STA脚本status=PASS表示工具和报告流程完成，`covered_path_status=FAIL`才是时序判断；不能据原生exit0宣称150MHz通过。

另一个`fast-buffered-reference`实验 `20261018T020758.384301Z-sram-blackbox-8eb64395`映射FAIL。保留实际ABC网络的有界诊断证明：约束可解析，map完成，但buffer遇到dangling node，ABC可exit0而无output.blif/完成标记；两门最小复现插入cleanup后通过，修复后的实际网络NOT_RUN。诊断位于 `artifacts/diagnostics/20261018T020921Z-abc-constr/`，不能将最小fixture通过当全网时序改善。

下一步仅修映射前清理与终态检查，再在相同top/RTL/库/约束下比较buffer和setup/hold。不得拿旧core-only面积与当前含接口面积直接计算优化收益。全FF结构指标仍仅为FF对照，正式宏成本不可推算。


## 2026-10-18后续：缓冲映射修复与分类STA

修复后的实际全网mapping为`20261018T022812.829729Z-sram-blackbox-501ae448/result.json`，内外完成标记、原生exit0、mapped.json/v和72宏全部核实，未改RTL/Golden/SDC。1557个BUF_X1，总46026标准单元、0.056997416mm²参考逻辑面积；相比同源无缓冲增加约2.74%，不含真实宏成本。

分类STA为`20261018T024917.037967Z-sram-partial-sta-de192ce7/result.json`：setup WNS/TNS均0，最差Slack+4.652084ns；普通data hold最差-0.013133ns；全部min最差-0.255385ns来自内部soft_reset到core异步RN的removal。前20条removal全部违例，20条data hold中3条违例；这是报告截取数量，不是完整端点总数。工具流程PASS与Timing FAIL分开。

旧`reference_hold_worst_slack_ns`字段实际包含全部min检查，新报告额外给`reference_data_hold_worst_slack_ns`、`reference_min_worst_slack_ns`及类别；不能因setup转正就忽略hold/removal，也不能把所有min违例误称普通data hold。没有增加false/multicycle path或降低uncertainty。

同源证明及路径解释见 [参考时序分析](../docs/optimization/SRAM_TIMING_ANALYSIS.md)、`docs/runs/sram-buffered-comparison-20261018.json`。宏时序/输入电容、外部reset、寄生与正式PVT仍不完整；真实SRAM面积/功耗保持null，完整150MHz/总面积/能耗仍BLOCKED。


### 参考互连元数据纠正

OpenSTA实际采用库默认`5K_hvratio_1_1`统计wire load，旧JSON的pin-only/NONE描述错误；它不是提取互连。脚本已显式绑定同一个模型，`20261018T031137.428349Z-sram-partial-sta-70ca061a`重新执行PASS，setup/hold/removal数值未变且Timing仍FAIL。实际reset网143负载，pin cap约247.364fF、估计wire cap约121.880fF、总约369.244fF、slew0.845563ns。所有正式PPA结论仍BLOCKED。不得引用旧元数据称这些结果无任何线负载。

## 2026-10-18：门级功能接受范围与reset驱动探针

原缓冲网表的1层/12层同源功能回放已实际通过，12层304128输出逐位一致，包含abort/reset恢复、错误响应、末HI/ACK背压；私有Golden单bit错误被精确拒绝。该结果使用同Liberty零延迟标准单元功能模型和共同逻辑1RW模型，不是宏延迟、形式全输入或时序证明。索引见`docs/runs/sram-mapped-functional-20261018.json`。

reset BUF_X1的369.244fF负载大于库max_cap60.6537fF、原slew0.845563ns越过RN约束表范围。`run_sram_reset_probe.py`在独立**宏切口时序视图**作一处合法BUF强度替换，导出candidate.v后新进程重读，SDC、uncertainty、wire-load及负载均保持：

| 视图 | reset BUF max_cap fF | reset RN rise slew ns | removal最差 ns | data hold最差 ns | 标准单元面积差 μm² |
|---|---:|---:|---:|---:|---:|
| 原BUF_X1 | 60.6537 | 0.845563 | -0.255385 | -0.013133 | 0 |
| BUF_X8探针 | 484.009 | 0.108889 | -0.095160 | -0.013133 | +2.660 |
| BUF_X16探针 | 965.576 | 0.056443 | -0.069030 | -0.013133 | +5.852 |

两探针覆盖setup最差仍+4.652084ns；reset电容在新driver上限内、RN上升slew回到约束表范围，但removal与data hold继续FAIL。ideal clock的0 slew等参考假设也不能视为完整物理条件。单元面积差来自同参考Liberty，不代表新加速器总面积或官方面积。

证据为`20261018T040432.535073Z-reset-reference-5ae8d33c/result.json`和`20261018T040520.521420Z-reset-reference-aa8e440c/result.json`。两者tool status PASS仅表示受控诊断成功，**未创建/接受完整含宏mapped候选、未执行候选功能回放、未解决Timing FAIL**。后续先评估定点物理最小延迟修复及完整网表重绑，不盲目增驱动或为过关修改SDC；正式PPA仍BLOCKED。
