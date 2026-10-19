# SRAM候选参考时序：缓冲映射与剩余违例

日期：2026-10-18。范围为`kwt_icb_slave_sram`新增标准逻辑，72个SRAM宏切边未建模；**局部Timing FAIL，正式150MHz/PPA BLOCKED**。下述结果不证明完整系统时序，也不是官方工艺评分。

## 同源对照和实测变化

五份RTL的SHA逐一相同；将输入快照文件名归一后，hierarchical.json和blackbox-structure.json完全一致。数值、MAC、bank、接口和时钟目标没有修改。参考Liberty、工具版本和SDC假设相同；变化是ABC使用BUF_X2/10fF边界假设及cleanup/buffer/upsize/dnsize，不能把结果归因于减少功能。

| 项目 | 无缓冲参考 | 有缓冲参考 |
|---|---:|---:|
| 新增标准逻辑面积 | 0.055476428mm² | 0.056997416mm² |
| 标准单元数 | 44120 | 46026 |
| BUF_X1 | 0 | 1557 |
| opaque SRAM | 72 | 72 |
| setup最差Slack | -22.790979ns | +4.652084ns |
| setup WNS / TNS | -22.790979 / -22493.648438ns | 0 / 0ns |
| data hold最差Slack | -0.004303ns | -0.013133ns |
| 已报告reset removal最差Slack | +0.427610ns | -0.255385ns |
| 局部时序状态 | FAIL | FAIL |

增加标准逻辑面积0.001520988mm²，约2.74%；这是同范围参考映射开销，不含宏且不是正式总面积。最差setup改善27.443063ns，WNS指标改善22.790979ns；WNS在所有setup为正时钳为0，不应混用两种数值。

证据：无缓冲mapping=`20261018T020610.045677Z-sram-blackbox-173fe72f`，STA=`20261018T020713.509216Z-sram-partial-sta-2fe2e15f`；有缓冲mapping=`20261018T022812.829729Z-sram-blackbox-501ae448`，分类后的STA=`20261018T024917.037967Z-sram-partial-sta-de192ce7`，均在artifacts/runs。轻量同源记录为`docs/runs/sram-buffered-comparison-20261018.json`。

## 工具失败与修复

旧buffered profile失败于ABC的`buffer`命令：映射网络有无fanout组合节点。ABC可返回0，却无output.blif和内层完成标记；不能只靠原生exit0验收。保留实际网络诊断及两门最小复现，在map后、buffer前插入`cleanup`，维持驱动/负载和其余步骤。新实际全网原生exit0、内外标记及网表完整，72宏保留。新增检查拒绝内部Error、缺内层标记和重复标记。

原诊断：`artifacts/diagnostics/20261018T020921Z-abc-constr/`；修复后的全网结果与旧失败目录分开，未覆盖原始日志。

## 剩余问题的真实类别

### 1. 内部soft reset解除路径的removal

实际边界网表：`_91695_`的Q为`soft_reset`，QN经NAND/INV/BUF驱动`u_engine.rst_n`；例如`_89728_`的RN接该复位，Q是`u_engine.read_all_issued`。对应RTL为adapter内`engine_rst_n = rst_n && !soft_reset`及core异步复位寄存器。它是寄存器驱动的内部复位路径，不能因外部reset未约束而豁免。

静态网表中该`u_engine.rst_n`网直接驱动143个输入引脚（134个DFFR RN、8个AND3 A2、1个NAND3 A2），参考Liberty输入电容之和约247.364177fF，不含互连；详见`docs/runs/sram-buffered-fanout-20261018.json`。read_valid网当前直接sink已降至3个，但仍有直接寄存器data hold路径。

最差报告中到RN的数据到达1.084264ns，包含0.912561ns BUF延迟；库removal time为1.239648ns，加0.1ns uncertainty，所需1.339648ns，Slack=-0.255385ns。报告列出的前20条removal路径均失败，涉及20个端点；`group_count=20`只是一组样本上限，不能称全部端点仅20个。

### 2. 普通寄存器数据hold

最差为`_91682_`的Q=`u_engine.read_valid`直接到`_91677_`的D，后者Q=`u_engine.accumulate_valid`，Slack=-0.013133ns。当前报告的20条hold路径中3条失败。这里确有普通数据hold问题，因此不能把所有min违例都解释成reset removal。

### 3. 不完整边界

72宏的432端口组没有真实clock-to-Q/setup/hold/input-cap弧；1153输入/2436输出缺delay、2436未约束端点是显式切口及外部reset边界。理想时钟、库内统计wire-load模型（无布局提取寄生）、0.1ns uncertainty、普通IO延迟0.5/0.1ns、10fF输出负载均为开发假设。局部setup变正并不包含SRAM数据路径，也不证明外部复位安全。

新报告分别输出`reference_min_worst_slack_ns`、`reference_data_hold_worst_slack_ns`及类别统计；兼容旧字段`reference_hold_worst_slack_ns`仍代表全部min检查，必须读取其scope说明。setup、data hold或removal任一失败均保持Timing FAIL。

## 后续候选与取舍

| 候选 | 预计作用/收益 | 资源/延迟与风险 | 验证和回滚 |
|---|---|---|---|
| 在支持最小延迟修复的映射/实现流程中做hold及reset网络电气修复 | 针对已定位的短data路径和reset驱动；收益需真实工具确认 | 可能增加buffer/改变slew；目前缺官方角和互连，无法报物理收益 | 保持RTL和SDC，独立网表/STA；保留当前两份mapping回退 |
| 将内部软件abort改为明确同步clear，外部reset仍单独处理 | 可去掉软件reset驱动大量异步RN的removal路径；属于待验证设计候选 | 可能影响abort响应、valid清除和首任务周期；不能顺手修改数据算法 | 先冻结新候选、定义周期契约，协议/核心/SoC恢复重验，再综合；原adapter/core不覆盖 |
| 对直接valid寄存器路径做有证据的单元映射修复 | 针对约13ps参考data hold违例 | 不能用RTL`#delay`或虚假约束；setup与hold须共同复查 | 同源局部STA与功能等价，失败弃用候选 |

当前优先完成源集/SoC/回归和同源交付，再决定是否进行独立reset候选。没有证据要求重写MAC或降低150MHz目标。不得通过减uncertainty、加false path或忽略removal使本结果变绿；真实官方宏/工艺到位后必须重新综合并做完整验收。


## 互连假设纠正（后续电气复核）

参考库实际声明`default_wire_load : "5K_hvratio_1_1"`，OpenSTA默认采用它。旧报告JSON的“NONE; pin-capacitance only”及旧文档“无wire parasitics”描述有误；原文件保留，本节纠正口径，不更改原始报告。脚本现显式绑定原有模型并记录其名称，未通过移除wire load改善Slack。

重跑证据为`20261018T031137.428349Z-sram-partial-sta-70ca061a/result.json`。setup +4.652084ns、data hold -0.013133ns、removal -0.255385ns均与默认模型的旧结果一致。`reset_net.rpt`明确列出引脚电容247.363998fF、估计线电容121.879639fF、总369.243652fF及143负载；`minimum_electrical.rpt`显示该buffer输出slew为0.845563ns。它来自统计估算，仍非实际布局/提取，正式工艺/PVT和SRAM数据未齐。

额外报告初次命令误将get_nets对象传给旧版report_net所需字符串，工具exit0仍打印Error，验收器正确拒绝；原诊断目录`artifacts/diagnostics/sram-reference-electrical-20261018`保留为失败，修正命令已在上述正式局部STA重跑通过。
