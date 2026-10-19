# SRAM 最小延迟候选：先修电气，再判断 hold/removal

日期：2026-10-18。**计划B只读分析；候选全部 NOT_RUN。** 本次仅核现有结果、Liberty、RTL及本地工具帮助，没有运行综合/STA/布局布线，也没有修改生产 RTL、SDC、Golden 或既有网表。当前参考 Timing 仍为 FAIL，正式工艺/PPA 仍为 BLOCKED。门级功能计划A由主代理单独进行。

## 1. 已核实基线与次序

输入为 `artifacts/runs/20261018T031137.428349Z-sram-partial-sta-70ca061a/`，其父映射为 `20261018T022812.829729Z-sram-blackbox-501ae448`；背景见 `SRAM_TIMING_ANALYSIS.md`。本轮 `source env/activate.sh && python3 scripts/harness.py resume` 原生退出0，任务/证据完整性 PASS，不增加设计验收。

| 已存实测 | 数值/位置 | 含义 |
|---|---|---|
| reset 驱动 | `_75076_/Z`，BUF_X1；143负载，其中134个DFFR RN、9个组合门输入 | 真实网络，不是外部无约束 reset 的借口 |
| reset 总电容 | rise 369.243652fF，fall 364.237061fF | rise含247.363998fF pin + 121.879639fF统计wire；不得删wire取PASS |
| BUF_X1 输出上限 | max_capacitance=60.653700fF | rise负载为上限的6.09倍；连库负载表也已越界 |
| reset 输出/RN输入 rise slew | 0.845563ns | 库default_max_transition=0.198535ns，约超4.26倍；DFFR RN removal/recovery表的两个slew轴上限均为0.198535ns |
| 当前 removal | arrival 1.084264ns，library removal 1.239648ns，uncertainty 0.1ns，slack -0.255385ns | 这是既有报告的真实FAIL，但包含电气超限和表外计算，不能直接当作需补255ps的可靠物理目标 |
| 普通 data hold | `_91682_/Q` → `_91677_/D`，read_valid → accumulate_valid，slack -0.013133ns | Q和D slew 0.009463ns、net 4.623806fF；确有独立普通数据hold问题 |
| setup | 最差 +4.652084ns | 仅覆盖标准逻辑；不是所有路径都可花掉4.65ns，新增单元须逐路径复核 |

数据hold路径的arrival为0.089508ns，要求0.102641ns（0.1ns uncertainty + 0.002641ns库hold）。reset路径中的BUF延迟为0.912546ns；负载和RN slew越界，会同时改变传播延迟和removal要求。更强驱动虽加快reset到达，也会缩小slew相关removal要求，**slack改善方向和大小必须重算**。 当前ideal clock的0 slew也低于库constraint表的最小采样0.00117378ns，这是既有参考clock假设，应单列限制；本轮先消除可修的reset大幅上界越界，不修改SDC来制造完整查表/正式覆盖。不能仅凭“加速reset会恶化hold”或“加buffer必好”决定。

实施顺序：**固定来源 → 小切片验证网表编辑/回写/再读取 → reset max-cap/slew与查表范围 → 重新分类min → 必要的data hold修复 → 最后判断是否值得同步clear设计候选**。现有报告只各抽样20条路径；不得把20或3条违例当成全网总数。

## 2. 工具能力已核实，未宣称自动hold修复

本地OpenSTA为2.0.17；`.tools/opensta/usr/bin/sta -no_init -no_splash -exit /dev/stdin`执行命令帮助及Tcl `info commands`/`info body`，原生退出0并见 `KWT_LOCAL_STA_HELP_COMPLETE` / `KWT_LOCAL_STA_IMPLEMENTATION_HELP_COMPLETE`。可重现的查询如下，仅读帮助，不读全网：

```tcl
foreach name {insert_buffer replace_cell write_verilog fix_hold report_check_types} {
  puts "$name exists=[llength [info commands $name]]"
  if {[llength [info commands $name]]} { help $name }
}
```

已确认合法接口为：

```text
insert_buffer buffer_name buffer_cell net load_pins buffer_out_net_name
replace_cell instance lib_cell
write_verilog [-sort] filename
```

`load_pins`逐项按名称解析，不要把不兼容对象类型误传为字符串；`replace_cell`端口不等价会返回0，必须检查返回值及实际单元。`fix_hold`不存在。OpenSTA可作已指定单元/连接的ECO编辑和分析工具，**没有被证明具有自动hold/物理实现修复器**。本地 `report_check_types`帮助支持 `-max_transition -recovery -removal -min_delay`，未列出 `-max_capacitance`；不能照搬新版/其他工具参数。电容须从 `report_net -connections -verbose` 与Liberty对应输出pin上限逐网比较，rise/fall均检查。既有runner拒绝Error和缺完成标记的规则要保留。

ABC为1.01（本地version记录编译Apr 1 2024）。逐条执行 `.tools/synth/usr/bin/yosys-abc -c 'buffer -h'`、`upsize -h`、`dnsize -h`、`stime -h`、`help -a`：原生退出0。帮助说明buffer做buffering/sizing，`-S`目标slew单位ps（默认100），`-N`默认最大fanout10；upsize沿临界路径增尺寸，dnsize在维持delay下降尺寸。这些不是已验证的min-delay约束/hold优化。

一个额外可控变量：上述四命令均有 `-c`“using wire-loads if specified”，默认no。当前生产映射脚本使用裸 `buffer / upsize -D 6667 / dnsize -D 6667 / stime -p`；STA显式用 `5K_hvratio_1_1`。因此“小例中启用 `-c` 与现状对照”值得验证，但还不能断言它一定采用相同模型或解决reset。ABC边界BUF_X2/10fF假设也不能替代真实134个RN输入。当前脚本及报告不改；不得直接全网加 `-c` 后宣布hold修复。

## 3. 最小合法单元映射/电气对照实验（待执行）

先不改RTL。所有试验放独立新目录，复制冻结的输入并绑定SHA；不得覆盖原mapping。先以小网表复现驱动链 `_91695_/QN → NAND2_X1 → INV_X1 → BUF_X1 → 143个实际类型sink`，保持134个DFFR RN及9个原组合门输入的真实pin-cap。保留上游真实扇出分支的负载，明确小切片截断处；不能只造143个“空引脚”再拿数值当全网结果。小切片只验证编辑、查表/单位、连接、导出/重读与趋势；其统计wireload因网络范围改变可能不同，不能要求重现全网数值。

先验证替换/插入小例能完成“read→link→SDC→edit→write_verilog→fresh read→link→同SDC→report”。检查实例唯一、单驱动、每个sink恰接一次、无浮空/短接、极性不变、组合真值一致；对小例做reset与valid时序的零延迟功能回放。若后续全网使用OpenSTA导出网表，还须确认完整72个宏实例、端口及参数未丢失；在宏切口boundary网表上做的ECO不能直接冒充完整可仿真/综合网表。

| 试验 | 只改变的变量 | 已知代价，均为参考标准单元 | 接受门槛/回滚 |
|---|---|---|---|
| E0基线 | 冻结现网/小切片；same SDC + same wireload | 0 | 记录rise/fall cap、slew、removal/recovery/pulse width及setup/data hold；基线完整后才比较 |
| E1单级增驱动 | `_75076_`从BUF_X1替换为BUF_X8，必要时另测X16 | X8输出max_cap 484.009fF，area从0.798到3.458μm²（+2.660）；X16上限965.576fF，+5.852μm² | 当前总cap落在X8 cap范围内只是筛选；还要检查新输入cap、上游INV、两极性slew及RN表范围。失败独立候选弃用 |
| E2分支树 | 143个sink按真实pin-cap确定性分成8组，约17–18个/组；根候选BUF_X4，8个叶BUF_X2 | 相对原单BUF_X1，约+9.576μm²；8条新分支，根/叶均需重算统计wirecap | 每条根/叶网maxcap与slew均合法；核全143个负载，不能遗漏9个组合门输入。不能把原369fF简单除8估算通过 |
| E3映射口径小例 | 仅小例对照现ABC命令与 `buffer -c / upsize -c -D 6667 / dnsize -c -D 6667 / stime -c -p` | 单元数/area由实际输出报告，不能先报收益 | 证明库wire模型可用、流程标记和输出完整；检查边界RN真实负载是否仍被切成10fF。若未反映真实负载，此候选不升级 |
| H1定点data hold | 电气合法后，仅给 `_91677_/D` 单独支路插一个BUF_X1；其他read_valid sink不动；必要时独立比较两级或合法专用delay cell | 一个BUF_X1=0.798μm²；额外功耗/延迟必须实测，不预测mW | 读新网表确认不被后续cleanup移走；新hold及相关setup、输入/输出slew一起验收，不改RTL周期。未过则回退 |

参考Liberty BUF输入cap X1/X2/X4/X8/X16分别0.974659/1.779209/3.401892/6.585178/12.410827fF；输出max_cap分别60.653700/121.155000/242.310000/484.009000/965.576000fF。较强driver会反过来增加上游负载；只看最终一根网不够。面积仅是Liberty area之差，不能当布局后面积、官方面积或功耗。

在E0/E1小例通过导出和重读后，以下仅为**待执行ECO示意**，不表示本次已运行：

```tcl
# Only after read_liberty/read_verilog/link/read_sdc in a new candidate.
if {![replace_cell _75076_ BUF_X8]} { error "reset driver replacement rejected" }
# H1 belongs to a separate candidate, not silently bundled with E1.
insert_buffer kwt_hold_valid BUF_X1 {u_engine.read_valid} {_91677_/D} kwt_hold_valid_net
write_verilog -sort candidate.v
```

实例和网名必须在每份候选中重新核实际驱动，不能跨重新综合沿用编号。正式执行时E1与H1分目录，保留中间诊断并重读导出网表；语义/接口来源链须回到未切宏全网。不能使用RTL `#delay`、无硬件意义恒等表达式、“keep”空延迟、修改Liberty数值、取消wireload/uncertainty或添加false path掩盖违例。

## 4. 同步clear仅在以下条件满足后立独立候选

若电气合法后软件reset的removal仍失败，或可靠buffer方案成本/风险不合适，再比较明确同步clear。当前 `engine_rst_n = rst_n && !soft_reset` 同时负责core状态异步清除、bank/primitive rd_valid清除与请求门控；只把core的一个always块改同步是不完整的。应保留外部 `rst_n` 的异步复位语义，将软件abort作为同步clear送达core状态、流水valid、队列、读返回valid、bank标签使用条件和装载状态，禁止清SRAM payload/Q。bank的returned_tile原本不复位，继续由valid隔离，不能为“统一reset”扩散改动。

必须先写清逐拍契约：abort命令接受沿A，adapter在A后拉高注册clear；接收模块在A+1采到clear并优先清状态，A至A+1期间抑制load/start、SRAM读写、输出提交和已取消流水副作用；clear拉高期间继续禁止接新命令，响应背压不能丢失abort自身那一个响应。即使A+1响应立即被消费，下一次命令也只能在清除已完成后接受。若希望同A沿即同步清除，必须单独评估组合命令解码到core的路径，不能引入request_ready组合环或私自更改现有周期口径。

验证须覆盖abort恰逢最后输出、乘法流水在途、结果writer活动、读返回在途、HI响应背压、连续任务，以及在途外部reset后的完整重装载。clear应高于正常状态推进；无任务输出误提交、无额外load/start、payload不清且旧valid不泄露。现有MAC41/输出48数值、20bank、一拍1RW、ICB寄存器/ACK语义、Golden保持同一契约；若清除完成或可接命令周期变化，必须在新候选契约及开发完整窗口中明示并重新测量。

代价是新clear扇出、D侧MUX/门控、可能增加setup路径及控制功耗，可能需要额外一拍隔离；去掉某些内部RN并不自动减面积或修好data hold。外部reset仍需恢复/移除、电气与释放规范；同步clear不能让缺失的外部reset约束或官方宏时序自动通过。功能上先做小控制试验/定向恢复，再协议和核心回归、1层→12层门级及开发SoC；完成后才能评估同SDC局部STA。候选失败或无可信收益即弃用，保留现行adapter/core和所有既有报告。

## 5. 后续验收与来源

每次实际运行仍要求完整命令、原生exit、唯一结束标记、完整日志、运行前后输入SHA；工具exit0且打印Error不能接受。候选需分别给tool/结构、功能、reset电气、setup、data hold、removal/recovery/pulse-width状态，未运行标NOT_RUN，未覆盖标BLOCKED/UNMODELED；不能只填一个PASS。成功的小ECO只支持“同参考库、ideal clock、统计wireload下所覆盖标准逻辑”的结论。共享宏零延迟功能模型不能证明SRAM真实弧、正式150MHz、布局寄生、总面积/功耗或全装载评分。

本次关键冻结来源：

- `result.json` SHA256 `c787626ba5c07019055906a7cd39e9ff86985575d0d18c166cccbe9e87c41f2f`。
- `reference.sdc` SHA256 `c00fe97dfa716517db4cf3d6150aa8d5cf7d3987ad77389ed747dbd2b4276aab`；period6.666666667ns、uncertainty0.1ns、ideal clock、5K_hvratio_1_1不变。
- `reset_net.rpt` SHA256 `33c18a087787656f1966b7b69aed1fd255d25a1fc246749a9c01118c492462e2`；`minimum_electrical.rpt` SHA256 `92cff6050ab3c39358b085c268f4efc7aa0209ed557bdf68452f48994a6f40b7`。
- `ChipContest/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib` SHA256 `8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1`，time_unit=1ns、capacitive_load_unit=(1,ff)。
- 上述工具help在当前本地二进制上直接核对；OpenSTA/ABC并无已验证的自动hold修复能力。本次计划没有新时序/物理PASS。checkpoint由主代理在整合里程碑统一执行，避免与正在运行的计划A并发改任务状态。
