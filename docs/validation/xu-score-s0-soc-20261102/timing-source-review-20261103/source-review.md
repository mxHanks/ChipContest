# xu S0 全 SoC 150 MHz 下一步时序审核（只读，2026-11-03）

结论：现有证据仍不支持全 SoC 150 MHz 资格。最小推进顺序是先修复报告完整性/分类，再分别处理真实 SRAM 最短路径、clock gate 检查、UART 条件透明路径，最后闭合外部 reset 的释放合同或经过证明的同步边界审查。不能用一个最小 slack 数字替代这些不同的检查。

本次没有访问服务器，没有改平台/Chisel/SDC/生产工具，没有应用任何例外。只在本 build 目录增加了 UART 源提取和一个有限 Boolean SAT 证明。08 hold-repair 的最新状态来自主任务反馈；本次直接读到了 15/07 的部分实际 PT 原文及 08 launcher，没有取得 08 全套原始报告，故不推断 08 已修复了哪些具体端点。

## 证据身份与阶段

| 对象 | 身份或实际结果 |
| --- | --- |
| 原 full-SoC mapped 网表 | `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`（08 launcher 的强制输入守卫；本地没有重取完整网表） |
| 实际 analysis SDC / `tools/ppa/xu_full_soc.sdc` | `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`；HF 精确 6.666666667 ns、LF 30517.578125 ns、JTAG 100 ns |
| `build/xu-score-s0/xu-timing-scope-proposal-16.tcl` | `45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e` |
| 原 ideal hold 报告已取回片段 | `build/xu-score-s0/full-soc-audit-15-private/full-soc-audit-15/ideal-hold.rpt.first.txt`，SHA `7d2d59334b434e97a6fe3e2a503e4924573cc7f12da0e1abf6e5769de600473f` |
| 原 ideal analysis coverage 片段 | 同目录 `ideal-analysis-coverage.rpt.first.txt`，SHA `028c7753381a08a647bdbfe37c46eaeb4afb6b4b7f724171cfd8d0a186d5d021` |
| 07 实际 CDC/forwarded 诊断 | `build/xu-score-resume-20261103/resume-export-01/full-soc-pt-cdc-forwarded-07/state.json`：两次 PT returncode 0、各自唯一完成标记；只为 `EXECUTED_AUDIT_NOT_QUALIFIED` |
| 07 CDC+forwarded 的真实 min/max | `.../cdc_forwarded/timing-slack.tsv`：max `0.000000`、min `-0.121483`；该 0 不是正 setup margin，也不能证明所有 checks met |

15 的原 ideal coverage 是历史诊断：242 hold 违例、5 removal 违例、27 gating-hold 违例、24 UART latch no_clock；setup/hold/min-period/min-pulse-width 合计还有大量 untested。不能把这些历史数目写成 08 的当前数目。All-propagated 的未 CTS clock tree 与 ideal pre-CTS 是不同阶段；前者的巨大未缓冲 clock delay 不是实际 CTS 结果，后者也不免除 hold/gating/reset/pulse/untested 检查。

比赛不要求 P&R 时，可以建立明确的 library/corner-bound ideal-clock pre-CTS 验收范围。但须固定该范围，同时诚实保留未 CTS/无寄生限制；不能取 ideal setup、propagated hold 或另一网表功耗拼接成一个“通过”配置。

## 1. ERST removal：能证明捕获结构，不能证明释放时刻

确切连接是：

1. `sirv_aon_wrapper.v:344`：`erst = ~io_pads_erst_n_i_ival`。
2. 同文件 331 行：`aon_io_resetCauses_erst = erst`；`sirv_aon.v` 继续把该信号接至 PMU cause 输入。
3. `sirv_pmu.v:309–338,511–516`：两级 `erst_reset_r` / `erst_reset_r_r` **均直接由 raw ERST 异步置 1**；非 reset 的 LF 上升沿令一级为 0、二级取旧一级。
4. `sirv_pmu.v:358–401`：一级只向二级传递，二级参与 reset-cause 优先/保持逻辑和 LF 寄存器更新。

`sirv_aon_wrapper.v:235–250,346–353` 另有 3 级 `aonrst_catch` 和 cross-reset catch。`sirv_ResetCatchAndSync.v:34–49` 的移位实现可证明理想数字同步释放，但它们没有串在上述 raw reset-cause 两级之前。不能据“平台已有 reset synchronizer”就认为这两个具体 SDN 已同步释放。

实际 PT 原文给出：

| 端点 | 库单元 | pad→SDN min 到达 | removal+uncertainty 要求 | slack |
| --- | --- | --- | --- | --- |
| `.../u_sirv_pmu/erst_reset_r_reg/SDN` | `DSNQV0_12TR40` | 0.12784207 ns | 0.14932489+0.1 ns | −0.12148283 ns |
| `.../u_sirv_pmu/erst_reset_r_r_reg/SDN` | `DSNQNV0_12TR40` | 0.12784207 ns | 0.14632173+0.1 ns | −0.11847966 ns |

报告将外部 pad 的 min 输入延时 0 相对 HF，和 LF 捕获沿比较；这来自现有工程 envelope，不是板级相位承诺。现有 `docs/platform-interface.md:95`、TB `#120`（新 harness 还用过固定 `#200`）只描述一次仿真释放。`docs/xu-full-soc-clock-review.md` 及 SDC 85–95 行也明确说 I/O 默认 max=.5/min=0 不是外部 reset release 合同。本次在平台 `doc/source/*.rst`、README、现有接口/时钟文档中没有找到相对 LF 的外部释放时刻、最小 pulse、抖动或 slew 上界；这只是本次本地检索范围的结论，不能断言官方其它资料不存在。

可做但尚未做的数字证明：原样提取这两级及 cause 消费者，证明异步 assert 后保持、raw ERST 稳定释放后两 LF 边沿传播、只有二级被消费、reset-cause 优先级，以及短脉冲/重新 assert 情形。即使全部通过，也不模拟 metastability、MTBF、库最小异步 pulse 或 removal。把 `erst_reset_r_r` 叫“第二级”并不能自动免除其自身 raw SDN release 风险。

最小可验收闭合有两种需要真实依据的路线：

- **外部合同路线**：获得比赛/实际接口已经约定的 raw ERST pulse 宽度、deassert 相对 LF 的合法区间和不确定性、所有相关域的释放关系。按该事实建立独立 reset view，逐条验证实际 min/max、recovery/removal/pulse，并证明所约束的波形确实由环境满足。不能为消除 −.121 ns 临时抬高 min input delay；对任意异步相位，单纯增加固定组合延迟也不能保证避开每次 LF aperture。
- **同步边界路线**：若验收政策允许把这对指定端点当作同步器异步捕获边界，先提供精确 mapped fan-in/fan-out、两级拓扑、只由二级消费、库异步捕获/pulse 数据、最小级间稳定时间及要求的可靠性依据；记录每一项剩余风险和仅两个 SDN 边界的适用范围。只有经这个边界审查后才能讨论点例外，保持所有 downstream recovery/removal、其它 raw reset 接收者与原始报告。当前证据不够，不应立即应用。

降低 HF 频率、把 reset 固定 inactive、只看任务启动后的静态模式，都不能代替这项 reset 资格。

## 2. SRAM：有真实同沿最短路径，宏控制 role 仍需实际库原文

07 原 hold 报告明确显示 `w_data_reg_reg[8/9/10]` 同一个 HF 沿更新权重宏 D：TCQ 0.36172572 ns；RAMSP1024X16 的 library hold 0.37472191 ns，加 0.1 ns uncertainty 得 0.47472191 ns；slack −0.11299620 ns。它是数据保持检查，不能归为 async first-D 或因为写数据正确就 false-path。增加一个逻辑周期或降低频率也不是这种同沿 hold 的直接修复。

`xu_weight_sram_adapter.sv` 保持 `.CLK(RW0_clk)`、`.CEN(~RW0_en)`、`.GWEN(~RW0_wmode)`、WEN 全 0、EMA=010、EMAW=00、RET1N=1。`xu_sirv_sram_adapter.sv` 为 TCM/shared 产生银行 CEN 和逐字节 WEN，GWEN=~we。不能改变这些极性或静态模式来让不适用的 arc 消失；EMA/EMAW 的真实工作角资格仍需库资料。

本地实际库存只有 full_name/direction/libcell，不包含完整 timing arc。现有 `all_registers -clock_pins` 曾把 336 宏的 CEN/RET1N 共 672 项也枚举，另有 24 真正 UART E。**名字或方向不能证明这 672 个控制引脚都是“假时钟”或无检查**。需要从准确 linked DB 对应的 `.lib` 导出：

- RAM cell 的 `ff/latch/statetable`（实际存在者）、所有 signal pin role/clock 属性；
- CEN/RET1N/GWEN/WEN/A/D/EMA/EMAW 的所有 timing groups，逐组包含 `related_pin`、`timing_type`、`timing_sense`、完整 `when`、rise/fall constraints、模板与 index；
- CLK 最小 period/pulse、retention/enable 的 recovery/removal/hold/setup 等实际 arcs；
- units、PVT、EMA/EMAW 模式条件、模型中 specify/timing-check 启用方式及编译警告。

先读安装版 `man report_lib` 确认详细 timing-arc 导出命令，不能猜参数。原始 `.lib` 的有限结构/条件提取也可在服务器只读完成，完整厂商库留私有目录。根据真实 role 再把原 endpoint 表分类为 periodic-clock / asynchronous-or-control-check / real-unclocked-latch，原 696 项原文和计数保持，不简单减去 672 后宣布通过。

最小修复步骤：先取 08 的完整 constraints/coverage 和所有仍负 hold endpoint，按实际 pin、arc、clock、when 分类；若数据 hold 仍负，在相同约束、受保护宏和固定 RTL 下做 **新网表** 的综合 min-delay 修复/合法缓冲。按实际目标角修复全部相关端点，重跑 setup/hold/gating/pulse、完整宏清单、全 SoC equivalence 和真实 VCS。是否可以采用所选 fast/min corner 应由比赛工艺要求决定；当前单个 SS 库角的结果不能泛称全 PVT。

08 已用了 `set_fix_hold` 和 `compile -incremental_mapping -only_hold_time`，但命令存在本身不是修复证明。其最终 worst min 仍由 reset 主导，也不能反推所有 SRAM 已修好；必须比较逐类完整端点。

## 3. Clock gates：保留真实 latch/AND 和 0.1 ns 工程检查

固定非 FPGA `e203_clkgate.v:43–51` 是低电平透明 `enb` latch，再 `clk_out=enb & clk_in`。GFCM 也是该门控加 OR，来源选择经各自同步链。数字结构支持“enable 在高相位保持”的设计意图；它不证明映射 latch-Q/AND 的延迟满足当前 0.1 ns gating 契约。

15 的 27 gating-hold 违例、07 片段的 CPU/TCM/PWM/GFCM AND 输入 `U2/A1` 必须单独看全路径。下一次导出每类最差门的 enable startpoint、透明 latch D/E/Q、AND clock/enable pin、相关 clock edge、物理 cell 与库 arc、setup/hold 要求来源、slew/fanout。要区分库 ICG timing check 与 SDC 自加 .1ns，但不能看到自加就直接删除；它是当前冻结合同的一部分。

若合法综合映射/hold buffer/真实 library ICG 能在固定平台 RTL 不变下解决，生成独立映射网表，并证明该门的功能与全 SoC 等价；记录新增 cell/clock load 的面积功耗。具体 DC 识别/映射选项须以服务器安装版手册为准，本报告不猜 `-gate_clock` 是否会替换现有门。若诊断降低自加 check，只能作为分离原因的额外 view，原合同失败仍保留，不能覆盖正式 view。

对门控 bypass、test_mode、divider 程序模式及 GFCM 切换分别保留源/生成钟波形和 min pulse；固定 `clock_en=1`、删门、造 clock、全域 async group 都不能作为通用修复。

## 4. UART：完成了一个真实 Boolean 证明，透明传播的物理时序仍未闭合

源码 `apb_uart.v:161–212` 对 `fifo_tx_data` 缺默认赋值；仅在 `PSEL && PENABLE && PWRITE && THR && !DLAB` 时赋 PWDATA，同时 fifo_tx_valid=1。FIFO `io_generic_fifo.v:60–68,83–88` 仅在 valid&&!full 时写入、增加输入指针。三个 UART 因而各有 8 位 latch，共 24 个 E 无周期钟；不能生成一个 150 MHz clock 到 E。

本次实际运行了只读 Yosys 0.52 源提取和 SAT：

- `build/xu-score-resume-20261103/uart-source-extract-02/` 使用原五个 UART `.v`，设 **APB_ADDR_WIDTH=32**，与 `e203_subsys_perips.v:1100–1109` 的实际参数一致。原源码不改。
- `proc` 确认一个 8 位 `$dlatch`，D 精确为 PWDATA[7:0]；EN 的 polarity 为 0。保留 source SHA、工具版本和 `uart-proc.json`。
- `prove-enable.py` 从 JSON 精确复制 EN 与 fifo_tx_valid 的 21 个组合单元 cone，把所有当前寄存器状态作任意 primary input，SAT 无 reset/APB 假设证明 **latch open iff fifo_tx_valid**。没有忽略未知 cell、没有把 latch 的延迟当零加入 SAT；这个 cone 本来不包含 latch 数据状态。
- `enable-proof.json` 是 `BOOLEAN_ENABLE_RELATION_PROVED_NOT_TIMING_QUALIFIED`；实际日志 `prove-enable.log` SHA `65ae81f7eaaefef8a7ae71b438296c9f73452840b5aa789dddee8955570a4f43`，Yosys 证明 SUCCESS，returncode=0。原始 JSON SHA `6f06602a9d78a3540cfbee0b9f4dd6831a802b9f6a7f6da203b2f93746351fe3`。01 是默认 12 位参数的先行提取，保留；02 才对应 SoC 的 32 位参数。

这只是组合关系证明，**没有证明** full FIFO/串口行为等价、X 语义、映射延迟、setup/hold 或物理透明 latch 资格。不能据此移除 24 个 E/D 端点。它使下一步的条件透明审查有了具体依据：当 FIFO 确实消费时 latch 必然打开，关闭时旧数据不会被 valid 消费。

APB 数据来自内部 ICB，不是板级异步输入。`sirv_gnrl_icb2apb`（`general/sirv_gnrl_icbs.v:1444–1457`）把 addr/read/wdata **组合直通**，PSEL=cmd_valid；enable 是寄存器，cmd_ready 仅在 access 阶段给出。桥本身没有锁存 payload。因此仍需在固定 CPU/fabric 的真实 valid/ready 协议下证明 cmd 在 ready 前保持，PADDR/PWDATA/PWRITE 在 setup→access 稳定；不能凭“APB”名字假设环境。bridge 用 bus_rst_n，UART 用 rst_n，两者 reset 关系也应进入证明。

最小后续组合式验收：

1. 原固定 bridge+UART+FIFO 的 bounded/inductive miter：任意合法 ICB stall/back-to-back、THR/DLAB、满 FIFO、clear 和 reset；证明每个实际 FIFO 写入的数据就是当前请求字节，invalid 的旧 latch 内容不影响可观察状态。证明必须包括真实 reset/valid 关系，不把所有 transaction case 掉。
2. 服务器提取 24 latch 的实际 D/E/Q 与所有 fan-out，验证 FIFO 是唯一消费路径，并绑定映射后证明；检查其 D→Q transparent arc 和控制生成延迟。
3. 在实际工具支持的条件透明分析中覆盖所有有效 UART access，检查 **上游 ICB payload 寄存器→latch D→Q→FIFO data register** 的完整 150 MHz setup/hold，以及 access-enable/valid 控制的实际到达。必要的合法条件 views 保留每个分支/转换，不能只用 idle view。先验证 PT 如何处理 E=active 的 latch，不能造 E 时钟，也不能先删除 latch checks 再宣称可观察路径安全。
4. 若这类组合式时序/形式化边界不能被验收方法接受，则固定 RTL 的通用全 SoC STA 资格仍未解决；需要官方平台/验收方法说明，不能擅改 UART 默认赋值再说平台未变。

## 5. 报告与例外完整性是先决条件

`xu_full_soc_clock_review.tcl:21` 仍调用安装版不支持的 `report_exceptions -verbose`，旧报告失败应原样保留；未来新 collector 可用已实际执行过的 `report_exceptions` 等价导出，并保留命令身份和 exceptions 原文。不要把 required report 的 `.unavailable.txt` 当空报告通过。

`xu-timing-scope-proposal-16.tcl` 的 70 处精确 source→first-D cuts（64 GPIO、4 LF→PWM、2 deglitch）均 fail-closed count=1，不切 stage2/3 或 reset SDN。只能按各自源码/CDC 证据审核；双级结构不自动证明 MTBF、脉冲捕获。6 个 forwarded-output clocks 实际解决了原 GPIOA[27] inspect clock 被当普通数据的最差 setup，但必须保留 GPIO 数据分支、output enable/负载及 selector transition；`io_pads_gpioA_o_oval[28]` 转发 POR 不是钟。不能 false-path 整个 GPIO pad。

下一次报告至少逐一保存：完整 setup/hold 端点、recovery/removal、clock-gating setup/hold、min period/pulse、unconstrained endpoints、untested 原因、原与新增 clocks/波形、exceptions/case、所有 selector 数目。每项注明原/source、macro control、静态常量、无时钟、无适用 arc 或真实缺约束。Historical 15 的 28 个 unconstrained maximum endpoints 不是同类：包含 24 UART D、2 ERST SDN、2 deglitch D；不能整表一键豁免。

## 最小执行清单与完成标准

1. 从 08 取齐全量 retained constraints/coverage/具体残留端点；修正未来 collector 的命令兼容并保留原始错误，完成 696 项角色分类所需的真实库导出。
2. 以同一 netlist+SDC 建立可审查的 pre-CTS timing 范围：所有原始 view、有限 CDC 边界、GPIO/inspect 两种功能，明确 provisional I/O 和 reset 合同尚缺。
3. 用新综合网表修复真实 SRAM/data/gate min-delay，完整 equivalence+实际 VCS，不能以 reset WNS 遮住其它端点变化。
4. 闭合 UART 的有效消费/透明传播证明及全路径时序；使用本次 Boolean 结果作为子引理，不能作为资格结论。
5. 根据已有或获得的真实 reset 释放合同/同步边界可靠性依据，逐点处理两个 PMU SDN 及其它 RDC/pulse 项。缺外部相位/可靠性依据的地方明确仍需外部协议，不捏造契约。
6. 只在各检查和每类 untested 都有实例级依据、工艺/库角/模型身份完整且固定源的功能证明通过后，才可以陈述对应范围 150 MHz 合格。随后同一最终网表重新取面积和全 SoC 能量；本次审核不授予任何 PASS。

源提取重放（新目录运行，保留本目录原始输出）：参照 `uart-source-extract-02/extract.ys` 用原五源和实际32位参数执行 Yosys，再运行该目录 `prove-enable.py` 的拷贝；`prove-enable.py` 的日志以 x 模式创建，现有结果不会被覆盖。生产源码 SHA 包含在 `uart-source-extract-02/result.json`，模型/厂商库没有复制进来。
