# xu SRAM 联合活动观察器实现规格

这是基于实际 PT `sram-library.rpt` 的实现交接规格，状态 `SPECIFICATION_ONLY_NOT_MEASURED`、`NOT_QUALIFIED`。新增独立 helper/schema/采集目录；不改旧 baseline collector，不重标旧 SAIF，不在 DUT 上 force、加驱动或改数值。先取得真实候选的 formal clear→first source REQUEST→final Y response RETIRE 采集，再增加本观察器进行新的独立采集。

## 实际 Liberty 条件

同目录 JSON ledger 按原报告 0..120 逐条保存 121 条弧（2 leakage、119 internal）。离线 checker 从原报告重建 ledger，并对全部 256 种已知 8 位控制组合验证 42 个 CLK mode 恰好覆盖一次。

| 弧 | 数量 | 实际 when | 必须观察 |
|---|---:|---|---|
| leakage | 2 | `!RET1N`；default | RET1N 0/1/X/Z dwell；default 解释单独保留，不能重复累加两个泄漏条件 |
| CLK read | 8 | `RET1N & !CEN & GWEN & EMA==k`，k=0..7 | 共同 dwell、CLK 0→1/1→0 在各条件下的边沿 |
| CLK write | 32 | `RET1N & !CEN & !GWEN & EMA==k & EMAW==j` | 同上，EMA k=0..7、EMAW j=0..3 |
| CLK retention/standby | 2 | `!RET1N` / `RET1N & CEN` | 即使 EMA 未知也按四值逻辑判断，不把控制未知全部推成 false |
| D[i] | 32 | 每位 `!WEN[i] & !GWEN`、`WEN[i] & GWEN` | 各位 WEN/GWEN 联合 dwell、条件下 D 边沿和未知 dwell。混合组合不是这两弧已覆盖的状态 |
| Q[i] | 16 | `RET1N & GWEN` | 各位 Q 的 0/1/X/Z dwell 与边沿在该条件下的分布；when **没有 CEN**，故 standby 不能豁免未知 Q |
| RET1N | 1 | `CEN` | CEN 条件下 RET1N 边沿，含 simultaneous change |
| A[0:9], CEN, GWEN, WEN[0:15] | 28 | unconditional | 每 pin 四态 dwell、0→1/1→0 和其余四态转移 |

其它尺寸或库（例如 bias RAMSP128X16）必须重新提取自己的实际 Liberty 弧；不能套用 1024 的条件与数量。

## 观察边界与身份

每次独立新进程采一个 task。记录 main/child Git、全部测量源文件、DUT/observer/tool、数值向量、实际宏库模型、mapped inventory、宏 alias 表的 SHA/模式/字节身份与 simulator 命令。预处理 clear 的证明留在任务外；窗口开始必须是首个 source/parameter MMIO 的 **valid REQUEST 发出**，等待 ACCEPT 的拍数也在窗口内，不能延后到请求接受；结束必须是最终 Y MMIO **响应被接受（RETIRE）**，沿用正式 collector 的同一边界信号及绝对 1 fs 时间戳。每个原始窗口同时保存 start/end 的整数 ticks、delta ordinal、transaction identity；最后一区间的 dwell 在 end flush，时长与同次 SAIF 完全一致。

按实际宏的端口（不能按 wrapper 的逻辑信号代替）只读 bind。宏集合必须与该候选实际 mapped inventory 双射；目前 8PE 为 336 个，PE32 预计为 352 个，但以该候选实际清点为准。逐宏端口应为实际 67 个 pin bits，保留层次分隔和字面点的区别。采集输出与原 SAIF 分开，不覆盖 raw/normalized 文件。

## 联合统计输出

建议新 schema `xu-sram-joint-activity-v1`，整数 fs、整数事件计数；一个 manifest 加逐宏 JSONL。至少输出：

1. `control_joint_dwell`：有序 `{RET1N,CEN,GWEN,EMA[2:0],EMAW[1:0]}` 的**实际同时取值**与驻留 ticks。每位编码 0/1/X/Z，按出现的完整组合稀疏存储；不做边际概率乘法。另有每位 WEN[i]/GWEN、RET1N/GWEN、CEN/RET1N 联合 dwell，供 D/Q/RET 条件交叉核验。
2. `arc_condition_dwell[arc_id]`：true、false、unknown 三桶，各桶 ticks。使用四值逻辑运算，随后用 `===1'b1`、`===1'b0` 判三分；禁止 `if (expr)` 把 X 隐式并入 false。每弧三桶恰好等于该窗口 duration。
3. `pin_joint_dwell`：对有条件的 toggling pin，在 condition 三桶下保留 pin 值 0/1/X/Z 的 12 桶 dwell。Q 必须逐位保留（when true 但 Q 全 X 的时长须可直接报告）；unconditional pin 同样保留四桶。leakage 条件不凭空生成一个 switching pin。
4. `conditional_transitions`：每个实际端口变化分类成 16 种 previous→next 四态组合（可不写 diagonal，但不能丢掉 X/Z 变化）；同时保存 condition 的 previous/next true/false/unknown。确定 0→1、1→0 与未知相关事件分别统计，不能把未知事件变成零。每个带条件弧都要观测其 toggling pin 的变化；CLK 的42弧需要相同原始 CLK 事件的分桶，不能只看 posedge 或只在 CEN=0 时计时。
5. `simultaneous_change`：同一 timestamp 内相关控制与 toggling pin 变化时，保存源 event 的 delta ordinal、pre/post tuple 及条件两侧值，或等价的可重放紧凑 sidecar。不要由某个 Verilog active-region 回调先后次序自行选择单一“有效条件”。最终按时间戳聚合后重放；在与 PT 条件事件定义核对前，把边界歧义独立报告，不能归入已知能耗。
6. 完成标记、全部宏/弧/pin 数量、未知 dwell 与边沿总量、原始统计文件 SHA。采集器没有资格把未知变成零，也不能把从未出现条件的弧擅自判断无功耗。

事件实现需在任务开始先 snapshot 真实四态 pin，任何相关 pin 变化先以旧 joint state 累加 `[last_tick, now_tick)`，再记录真实变更。禁止周期采样代替连续 pin 观察（会漏 Q NBA 更新、异步控制和 glitches）。对同一时间的多次 delta 变化，保留发生顺序与零 dwell 事件，不能只保留最后值；应先用真实 VCS 微基准验证 monitor 对 active/NBA/read-only 区域的行为。`#0` 本身不保证已经跨过 NBA，不能作为证明。若需要 VPI，新增被动只读 callback 且冻结源/编译产物身份。

## 验证与进入能耗分析的条件

- 用确定脚本穷举 256 known control 组合，复核 42 CLK 条件为完整互斥分区；加入 RET1N=0/CEN=X、GWEN/X、EMA/X 等四态条件案例，验证 false 能遮蔽 AND 中的 X，无法判定时进入 unknown。
- 造有关联与无关联但边际完全相同的控制序列，必须产生不同 joint dwell；证明采集器没有用独立假设重建联合分布。
- 测 D 的两种匹配组合与两种混合组合；测 Q 在 CEN=1、RET1N=GWEN=1 且 X 时不能被豁免；测 RET1N/CEN 的同时间控制变化及 delta/NBA 更新；测任务边界恰好同时间的边沿。
- 每宏原始无条件 pin 四态 dwell 之和=duration；逐弧 T/F/U dwell 之和=duration；conditional pin dwell 汇总还原无条件 dwell；原始四态转移计数在所有条件边桶重建一致。与同次 raw SAIF 按**经实际工具校准的 SAIF 事件定义**核对，不能先假定 SAIF TC 的 X/Z/IG/TB 语义。发现定义不符时保留双方原件、明确未解决。
- 逐条查询实际 PT `get_switching_activity -state_condition` 的条件值与来源（含 -1/-2/UNINITIALIZED），保存实际命令及原始结果；不要先 set_case_analysis/set_switching_activity 来“补齐”证据。若 PT 的条件活动并非 measured/file，或需要联合信息而工具没有使用这份新统计，不能把旁路统计说成 PT 已使用。
- 全部336/352宏都完成并不自动等于整 SoC 能耗合格；标准单元 annotation 来源、merged net inconsistencies、未知 Q 的有条件贡献、实际库覆盖、完整150MHz资格和同配置吞吐/面积仍须各自闭合。

本规格仅补足可观察性。它不规定任意误差、不承诺 SAIF 能表达完整 joint conditional 信息，也不提供计算出来的能耗。
