# xu 全数字SoC时钟与150MHz约束审查

本交接建立可执行SDC及审查入口，固定平台RTL未改。当前没有DC/PT全SoC结果，不能据此声称150MHz、hold、recovery/removal或比赛资格通过。`clock-review.json`的`status=REVIEWED`只表示本文件所述约束/源码范围已审查；`sta_status=NOT_RUN_NO_DC_PT_RESULT`是独立且必须保留的状态。

## 实际时钟与复位拓扑

PPA顶层为`xu_soc_ppa_top`，完整SoC在`u_soc`下，保持原有真实pad接口；512KiB共享SRAM在`u_shared`，其时钟为顶层`hfextclk`，复位为外部`io_pads_aon_erst_n_i_ival`。因此共享SRAM与内部`hfclk`间的真实接口路径仍需计时；不能只分析加速器wrapper。

以下来自当前RTL，不采用模块名或注释暗示的模拟行为：

| 范围 | 实际实现与SDC处理 |
| --- | --- |
| `hfextclk` | 150MHz目标，周期6.666666667ns。SoC旧注释的16MHz不作为本次目标。 |
| `e203_subsys_pll` | `FPGA_SOURCE`两个分支均assign直通。M/N/OD没有数字倍频作用，不虚构模拟PLL时钟。 |
| `e203_subsys_pllclkdiv` | `divby1=1`放行源时钟；否则每`2*(div+1)`个源周期放行一个源高脉冲。`div=0..63`对应除2..128，高脉宽恒为半个源周期，不是50%占空比除频。 |
| `e203_subsys_gfcm` | 两路同步选择、latch/AND门控再OR；`pllbypass=1`选原始HF。模式切换有停钟/获取过程，静态generated clock不证明切换安全。 |
| `e203_clkgate` | 非FPGA分支为低电平透明latch加AND。CPU IFU/EXU/LSU/BIU/ITCM/DTCM门控保持时钟传播与gating检查，不固定门控使能。 |
| `lfextclk`、AON | 32.768kHz，周期30517.578125ns。`sirv_aon.io_lfclk=io_lfextclk`，用于AON、跨域接口、去毛刺与复位/PMU流程。 |
| JTAG | 独立`xu_jtag_tck`，工程假设10MHz/100ns，正负沿状态均保留；不把JTAG跨域全切除。 |
| 其他外设 | GPIO/QSPI/UART等真实pad仍保留；外设内以HF寄存器+使能实现的SCK不是另造内部clock。所有叶级clock pin以实际综合网表审查。 |
| 复位 | HF/PLL各有异步assert、同步release链；main复位经`u_main_ResetCatchAndSync_2_1`，core复位再进入实际reset control。AON的复位/交叉复位均保留。数字`porrst_n`本身恒1，不能据此声称模拟POR已验证。 |

选择/分频寄存器在`u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_sirv_hclkgen_regs`：

- HCLKGEN基址`0x10008000`；`PLLCFG+0x008` bit18=`pllbypass`，复位1。
- `PLLOUTDIV+0x00c` bit8=`plloutdivby1`，复位1；bit5:0=`plloutdiv`，复位0。
- `start.S`只设置栈、清BSS并调用`main`；当前`main.c/accel.c/accel.h`任务地址为共享区`0xa0000000`和加速器`0x10042000`，未写上述时钟寄存器。这支持当前固件稳定任务的reset-bypass范围，不能推广为任意固件、debug写入或启动过程证明。软件二进制与总线trace仍须随正式任务冻结。

## SDC模式与保守范围

入口为`tools/ppa/xu_full_soc.sdc`。默认`XU_CLOCK_MODE=envelope`，三种模式如下：

| 模式 | 寄存器case analysis | divider clock | 可支持的结论范围 |
| --- | --- | --- | --- |
| `envelope`（默认） | 无 | `xu_plldiv_envelope`为150MHz源脉冲上界 | 所有实际divider输出脉冲都是源脉冲子集，按最快频率分析。会对慢分频保守；不放宽周期、不删除时钟控制寄存器路径。对模式切换仅保守计时，不是功能/CDC证明。 |
| `reset_bypass` | 具体寄存器bank输出：bypass=1、by1=1、div=0 | `xu_plldiv_by1`，1:1 | 仅当前不编程PRCI的稳定任务模式；不代替envelope结果，不覆盖复位释放或选择切换。 |
| `divider` | 同一bank输出：bypass=0、by1=0、div=`XU_PLL_DIV` | `xu_plldiv_static`，`-edges {1 2 4*(div+1)+1}` | 静态分频0..63，保留源高脉宽；初始相位由复位/计数状态决定，不声称覆盖启动瞬态。 |

固定平台`e203_soc_top`原本将`test_mode`接0，SDC没有额外case。除表中明确寄存器输出外，不case reset、GPIO、debug straps、外设使能、clock-gate enable或CPU状态。没有`set_false_path`、`set_multicycle_path`、`set_clock_groups`、`set_disable_timing`或reset idealization。HF/LF/JTAG无确定物理相位关系，本版故意保留跨域STA路径以便逐条审查；异步跨域的数值slack不能单独证明CDC安全，也不能用全域false path消除问题。

外部I/O默认max=0.5ns/min=0ns、transition=0.1ns、output load=0.01库单位，JTAG数据max=5ns；clock uncertainty/transition=0.1ns，clock-gating setup/hold=0.1ns。这是可重放的**工程输入假设**，不是赛题给定的板级合同。SDC变量可在source前覆盖I/O值。异步reset/wakeup/straps也有输入约束并保留路径，但这种相对HF的输入延时不建立异步reset释放保证。正式结论仍需真实外部条件、指定库单位、SRAM PVT/EMA/EMAW时序资格；不能把未建模外部/宏条件解释为零代价。

## 实际DC/PT接入

先对`xu_soc_ppa_top`完整analyze/elaborate/link，再source SDC。综合至少保留`u_soc`到HCLKGEN/divider以及寄存器bank这些被selector引用的层级；可用`compile_ultra -no_autoungroup`，或者显式`set_ungroup ... false`并关闭所需边界优化。该选择需要记录；不要通过更换宽泛selector让空集合静默成功。SDC对必要clock ports/pins要求精确匹配一个对象，缺失即error。

DC使用ideal source clock约束进行综合。PT读同一冻结mapped netlist及mapped SDC后，按实际阶段设置`set_propagated_clock [all_clocks]`并`update_timing`；如果是重新读本源SDC，可在source前设`XU_PROPAGATE_CLOCKS=1`。真实STA必须核对输出的master/generated关系及波形，而非只相信source无报错。没有布局布线/SPEF时，应披露标准单元/宏时序加综合互连估算的前物理范围。

审查采集器为`tools/ppa/xu_full_soc_clock_review.tcl`。读mapped SDC后使用：

```tcl
set XU_CLOCK_MODE envelope
set XU_PLL_DIV 0
set XU_CLOCK_REVIEW_DIR reports/xu-clock-review
set_propagated_clock [all_clocks]
update_timing
source /absolute/replay/tools/ppa/xu_full_soc_clock_review.tcl
```

采集clock、setup/hold、全部violators、exceptions/case、PT analysis coverage，以及recovery/removal、gating setup/hold、min pulse width、async pin max/min路径。`clock_endpoints.tsv`列出全部寄存器clock pin与所有`RAMSP*`宏CLK上的clock。版本不支持的report不会被伪造为空报告：留下`.unavailable.txt`和`REPORT_COMMAND_FAILURES`，应在目标工具查man并重跑等效报告。DC没有PT专属报告时，PT阶段仍需补齐。

`review_status.txt`总是`REVIEW_REQUIRED`，采集器不自动宣布收敛。必须审查至少：

1. 所有真实CPU/互连/加速器/ITCM/DTCM/shared/internal-SRAM clock pin都有合理的源和频率；无漏掉的生成时钟或泛化零活动。
2. setup与hold都合格，短脉宽、clock-gating检查、recovery/removal不被禁用；保留最大/最小路径和库/角身份。
3. 每一类untested检查有具体实例、原因和下一步：常量/优化掉的真实端点、无适用库检查、未建模约束、空clock集合、CDC第一拍及异步reset释放不能混为一类。现阶段没有任何已批准的untested例外。
4. HF/LF/JTAG跨域按同步器第一拍、握手/队列与reset crossing逐项审查。若以后建立定点例外，必须绑定具体pin与结构/协议证据，同时保留例外前后报告，不能一次性切掉外围。
5. envelope和允许的任务静态模式报告分开冻结；不能用静态mode关闭难路径后覆盖envelope失败。

## 本地可回放验证

在仓根执行：

```bash
python3 tools/ppa/xu_review_full_soc_clocks.py \
  --out build/xu-full-soc-clock-review --run-rtl
```

工具输出绑定源文件/SDC SHA256的`clock-review.json`、Tcl mock及原始编译/仿真log。Tcl mock执行3模式×64参数组合，验证分支、case数量、脉冲edges与缺失pin拒绝，仅使用模拟collection API，**不验证Synopsys真实selector或时序语义**。Icarus读取未经修改的非FPGA平台RTL，验证by1、全部64分频、真实寄存器复位默认值，以及PLL/GFCM的bypass、by1、除2/4/128稳定模式。无论哪个测试成功，都不替代DC/PT、模拟PLL、metastability、reset/mode-transition安全或全SoC功能证明。

`tests/e203/tb_accel_soc.sv`原激励HF=4ns、LF=66ns。将LF改为名义30517.578125ns会把以LF计数的去毛刺/启动/复位时长放大约462.388倍，还会改变HF/LF跨域相位。计分任务窗口从开始装载到最后写回，启动不一定落入该窗口，但AON交互和阶段相位可能改变实际周期。必须真实回放对比首任务启动与每任务first-input/final-response窗口，不能仅换算频率或推断所有周期不变；本clock单元测试不提供这个对比。
