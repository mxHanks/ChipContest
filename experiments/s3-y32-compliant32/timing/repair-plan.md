# 64PE合规32位版本的时序修复计划

2026-11-13。本文只读检查已有原件，未访问服务器、未启动EDA、未改RTL。
旧64PE B报告用于确定修复种类，不能替代新32位SystemBus配置的实际计时。
新映射的层次、门名、负载、路径和违例数量都必须重新测量，禁止把旧ECO cell名
直接套到新网表。下一次集中作业应同时具备“基线—真实修复—重载复核”三段，
而非只产生一份未修复的失败报告。

## 已证明事实与尚待验证

旧B的实际PT报告为`build/area-opt-20261111/native/reports-r4/extracted/b/pt/`。
原始coverage455190项，211违例、27911未测；不能借用原48位baseline469690项总数。
完整211项的准确pin、原件行号、原始块SHA及详细路径cell/pin已生成：

- `build/compliance-64pe-20261113/timing/old-b-catalog-r2/native-b-211-catalog.json`
- 同目录`native-b-211-pins.tsv`及四类唯一pin文本。
- 重现：`python3 experiments/s3-y32-compliant32/timing/catalog_native_b.py --out NEW_DIRECTORY`。

| 类别 | coverage违例 | 唯一端点 | 已证明根因/观测 | 状态 |
|---|---:|---:|---|---|
| bias D hold |32|16|0.35932803ns到达，要求0.49404842ns；最差−0.13472039ns|真实最小延迟不足；可优先物理缓冲|
| GPIO首级hold |128|64|外部GPIO→`r_gpio_sync0_reg[*]/D`|输入契约/异步首级需审查，不能按同步普通数据盲修|
| LF→PWM首级hold |8|4|`r_ls_clk_sync_reg[0]/D`，HF及同根generatedHF重复|异步根关系/同步链证据不足|
| QSPI hold |6|3|`mac/phy/buffer_reg[0,2,3]/D`|源同步/协议min-max契约待证|
| AON pad首级hold |2|2|bootrom/dwakeup deglitch `T_8_reg/D`|异步/启动strap合同待证|
| JTAG hold |2|2|`jtagStateReg_reg[0]/D`、`shiftReg_reg[40]/D`|10MHz工程假设及数据launch合同待证|
| clock-gating hold |27|15|latchQ→AND A1仅约0.11ns，gatinghold0.1＋uncertainty0.1|真实enable分支最小延迟不足|
| AON removal |5|5|原始异步reset释放至PMU两SDN及catch三RDN；最差约−0.12ns|不能用普通数据hold缓冲冒充任意相位安全释放|
| debug out_setup |1|1|GFCM U8/Z驱动37785负载/27.20527267pF，U8延迟10.14552307ns，GPIOA27 WNS−10.11695099ns|真实高扇出实现成本；建树待测|

`hold.rpt`只打印50条路径，不足以替代178项全集；完整枚举从coverage提取，
总数严格核验为178＋27＋5＋1。32个bias项是16端点在相关HF/generatedHF上下文，
不是32个不同数据位。27个gating项也只有15个A1端点。

## 先实现可以不改变架构行为的物理ECO

### bias SRAM最短路径

旧锚点：`u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_xu_matrix_dma/u_core/bias/`。
最差两条`writeWord_reg[1]`、`[5]`经`U751/U750`（CLKINV0）及
`U397/U396`（NOR2CV0）至`memory/mem_ext/macro/D[1]/D[5]`。
实际修复应针对新映射的16个精确SRAM D负载，而不是在RTL写可被优化掉的恒等逻辑。

已有**局部真实可行证据**：16PE旧`pt-bias-hold-eco-r2`以同库/同0.1ns约束，
在16个D负载各串3颗`BUFV2_12TR40`，合计48颗、每颗库面积0.9576，
新加逻辑面积45.9648库单位。`reports/after-insert-047-bias-min.rpt`
最差bias slack实测**＋0.03719347ns**。这证明方法曾有效，不能证明新32位映射有效。
原作业最后执行不支持的`write_verilog PATH`发生CMD-012而失败，未导出可用候选、
未做映射等价、未获得完整after全局时序，所以不能把该失败标记改成成功。

新修复回路：每次从新网表查询实际`get_timing_paths -delay_type min -to EXACT_D`
小于+0.03ns的负载；单负载一次`insert_buffer`，核对返回非空、库ref/函数、
完整cell/net新名称及面积；更新计时后再决定是否加下一颗，最多8轮且area有界。
对16位全部rise/fall、HF/generatedHF检查最小/最大路径，不能只修最差bit。
结束应bias hold≥0（建议+0.03ns guard）且SRAM setup没有新增负值。
库的其他合格buffer/delay cell可根据真实min/max表筛选，不能把固定三颗当作保证。

### clock-gating enable分支

15个精确A1列表见`clock_gating_hold-unique-pins.txt`。其中8个位于CPU层次内：
CPU clk_ctrl的LSU/IFU/EXU/BIU/ITCM/DTCM六门与ITCM/DTCM控制器两门；
另7个在外围（GFCM两门、PLL-divider一门、PWM四门）。

**当前不可改`e203/core/e203_clkgate.v`或任何CPU/LSU/BIU RTL。**
可行边界是逻辑功能不变的映射实现：在精确`enb_reg/Q→U2/A1`数据分支添加
经库表征的非反相缓冲，保留`U2/A2`时钟分支及所有门控检查；CPU功能网表
叶子/连接在收缩新增buffer后必须与原网表完全相同。若连映射CPU层次buffer也
不被允许，则这8项修复为外部平台实现依赖，不能擅自改CPU或宣布全SoC闭合。

原有`pt_gating_hold_eco_r1.tcl`是准备脚本，未找到成功原生执行收据，
因此此类修改目前**只有方案，没有实测修复结果**。每条enable最小延迟需增加
约0.09ns但必须保留gate setup正裕量、波形/高低脉宽/门控切换与test_mode行为。
不能把`set_clock_gating_check -hold`降为0，不能减uncertainty，不能把gate pin设理想。
ICG替换属于更大实现变更，必须有库gate polarity/test latch波形证明与等价，非首选。

### debug clock输出/高扇出网络

旧B根为GFCM `U8/Z`（BUFV32），37785个负载共27.20527267pF；
GPIOA27经过`u_e203_subsys_main/U64/A2→Z`（AO22V12）输出。
这是同一真实clocknet承受整SoC负载，单独改GPIO mux缓冲不能解除根负载。
在实际映射网络建立真实、经库表征的层次buffer tree，并保留debug输出、
所有原叶CLK clock association及参数化时钟/门控模式，才可能同时降低slew/DRC和WNS。

旧clocktree R1实际失败NED-022：多层次逻辑net的16个load导致多个buffer，
自定义唯一名称只允许单buffer，**未产生有效候选**。
R2去掉自定义名后返回大量真实buffer，但无法减少下一层load数，
触发`clock tree load count did not decrease`；同样失败，没有after时序。
不能再次全层次blind chunk，也不能把API返回非空当树已建好。

准备的`pt_clock_tree_eco_r3_draft.tcl`按**本地net segment+owner current_instance**
逐组选择同一局部网的sink、每层严格减少fanout，记录真实buffer和net；
它仍是未执行草稿且写死旧16PE identities/旧1.25面积cap，须针对新32配置重写守卫。
建议在集中作业内先以独立小逻辑/单个本地segment验证API语义，再处理根树：
单段、最多16sink、唯一所有权、实际电容受限，不在同一次调用混入层次segment；
空返回、load不下降、对象迁移、重复sink、clock association丢失即停止并保留失败。
新增buffer的全球面积全部保守计入候选，不能藏在复用CPU/固定外围面积之外。
不使用`set_ideal_network`掩盖原生负载，不删debug clock output、不改输出延迟。

## reset及异步边界：不能仅靠延迟修复

5个removal都由原始`io_pads_aon_erst_n_i_ival`启动，精确落在：

- `u_sirv_aon/.../u_sirv_pmu/erst_reset_r_reg/SDN`
- 同PMU `erst_reset_r_r_reg/SDN`
- `aonrst_catch/reset_n_catch_reg/reg_{0,1,2}/q_reg/RDN`

完整层次以catalog文本为准。`sirv_pmu.v:328–338`显示两级PMU寄存器都
直接受raw `erst_reset`异步置位，不存在“第二级天然已同步、不用检查”的理由。
外部reset任意相位释放，单纯加0.12ns延迟只移动危险窗口，不建立安全释放。
首先需要真实外部reset断言脉宽/释放/时钟停止合同，以及现有catch/sync链所有权。
如果平台允许，只在外围建立异步断言、同步释放的复位所有权；保持PMU resetcause、
短脉冲捕获、warm/cold启动、停钟恢复和任务在途清理语义，不改CPU reset内部控制。
这样的功能RTL修改需要phase sweep、复位/CDC验证和完整CPU12任务重验。
首级亚稳态边界只能被精确分类并给出CDC证明，不能以整组async falsepath获得PASS。

178hold里大多数是异步/外部/源同步首级，而非bias。GPIO有两级同步，PWM
LF→HF三段，AON deglitch四段的旧只读catalog可辅助，但不证明所有新路径没有旁路。
QSPI/JTAG必须单独提供参考时钟/launch边沿和板级min/max，不能把I/O min改成有利数字。
HF和generatedHF有共同物理根，**禁止二者异步分组**。独立HF/LF/JTAG跨域也必须
按具体控制同步链和bundled-data稳定窗口审查，不能一刀切clock_groups。
新网表要枚举所有clockpair max/min及untested原因，扩大到完整端点而非50条样本。

## 下一次集中DC＋PT作业的具体执行闸门

1. 冻结合规32位候选RTL/固件/向量/完整加载计时证据；加入新`w_low/bias_low`
   真实清零检查。保持CPUcore/LSU/BIU不变。采用相同指定标准单元/SRAM库、PVT、
   6.666666667ns HF、原IO/uncertainty/gating合同，保留LF/JTAG及HF envelope。
2. **修改网表前先核对导出API。** 本地已有native `insert_buffer`和`write_changes`
   manual；`write_verilog`缺manual且旧位置参数失败。使用实际`help -verbose`
   确认可用语法。文档规定`write_changes -format ptsh|dctcl -output FILE`可导出ECO
   增量。不能在上千次修改后才首次尝试导出；先验证空变更及单buffer保存/重载。
   推荐PT导出原生dctcl增量→同job DC载入同mapped.ddc应用增量并导出新mapped.v/ddc→
   新PT进程重载实际候选网表。完整网表导出链和对象身份不成立时禁止继续大树。
3. 一次DC建立新实际映射，保留set_fix_hold原始请求，真实baseline PT报告全setup、
   hold、removal、gating、pulse、DRC、clockpair、unconstrained、coverage及宏CLK关联。
   `set_fix_hold`曾在旧DC运行仍留下违例，不能当成功保证。
4. 同集中作业中先处理debug真实负载/网络和DRC，再bias D有界minimum-delay、
   gate enable分支；每阶段记录before/after和新增面积，重新检查所有setup/hold/gating。
   不把修bias32项当整211已修。无法完成CDC/reset契约时保持相应明确未通过。
5. 导出ECO后在新工具进程重载；同时验证每原始叶子/type/port/连接，
   新增buffer function=I、无额外驱动/环/遗漏，证明buffer收缩后结构等价。
   `check_buffer_equivalence.py`只支持已原生证明BUFV2/BUFV4，且不是RTL到mapping的
   完整形式等价。最后还需原RTL→最终mapped等价或可信同配置门级数值/协议验证。
6. 闸门：零未解释setup/hold/removal/gating/pulse/DRC违例；全宏实际CLK有时钟；
   27911旧untested逐类有可复查来源，所有unknown/unconstrained解决；没有新增约束豁免。
   无unsupported静默默认0。正裕量和完整覆盖应一致，不能仅看最差路径或report收集成功。
   每个阶段新增面积都应在比赛计费范围内，mm²换算/官方SRAM计价另行确认。

以上修复有不同确定性：bias方法已有旧实例局部正裕量证据；clocktree API/拓扑、
gating ECO、reset/CDC契约及新32位整体时序均待实测。不能预报此次一定150MHz通过，
也不能为了“必须交付成功”放宽验收标准。
