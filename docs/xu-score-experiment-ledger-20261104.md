# xu：优化实验与资格证据台账

目标沿用[xu-score-optimization-plan.md](xu-score-optimization-plan.md)：通过资格门槛后，以同一冻结配置的吞吐、全SoC单任务能量、加速器面积比较评分和非支配候选。面积上限为 **2.25mm²**。本台账汇总已取回的实际原件，不替代各独立分支，不宣布最终选型或完整比赛资格。

2026-11-05用户最终确定只保留 **S2e主方案、S2c对照**，其余候选停止追加评测，历史代码与日志全部保留。
这取代此前仅暂停32/64PE、保留compact的中间决定。后续遵循[两组收敛计划](xu-two-candidate-plan-20261105.md)，
当前[165逐层/原图同口径对比](validation/xu-score-two-candidate165-20261105/README.md)已完成；155最新图能量待独立重测。
下表继续保存历史事实，不因选型改变而删除。

2026-11-05 16:08 CST追加事实：[170/172启动观察](validation/xu-score-queue170-observation-20261105/README.md)
核实原153总控PID27671真实存活、164完整24报告审计终态、S2c167 PID172967真实RUNNING_CHILD；
S2e166同155图单层预检和成功后12层均已登记等待。仅新增验收/调度脚本，无生产Chisel改动。
这是UI观察；171原JSON/native包仍需取回独立核验。155新图能量仍为空，不能更新评分结论。

## 已核实的开发周期和同库面积

周期列是原开发VCS窗口的12个独立固定FFN1任务，保持signed16 X/W、signed40 bias、signed48 Y和向量；这些开发运行的HF4ns/LF66ns不能与后来正式150MHz/LF绝对相位、任务前清空的活动窗口混比。面积列取各自实际综合原网表的完整新增加速器/接口/内部宏层级；固定CPU、共享SRAM和总线外设不计入2.25mm²限额。修复后的网表另有面积和证明身份，不能自动替换表中原网表身份。

| 独立候选 | 真实12层开发总周期 | 加速器面积mm² | 当前实际原件入口 |
|---|---:|---:|---|
| H1+H2固定起点 | 16510344 | 0.2857860337 | [全SoC面积和FM](validation/xu-score-s0-soc-20261102/formality-and-area-server-20261103/README.md) |
| S1 移除完整bias cache | 23193238 | 0.1785626035 | [S1验收](validation/xu-score-s1-server-20261103/README.md) |
| S1 SRAM bias | 16845046 | 0.2469499369 | [S1面积](validation/xu-score-s0-soc-20261102/formality-and-area-server-20261103/README.md) |
| S2a 顺序stream写 | 15361356 | 尚无独立面积结果 | [同一S2a接口的双调度验收](validation/xu-score-s2a-server-20261103/README.md) |
| S2b packed W/X | 14532449 | 0.2869364304 | [S2b验收](validation/xu-score-s2b-server-20261103/README.md) |
| S2c 自动分组+结果FIFO | 11842200 | 0.2948018380 | [S2c验收](validation/xu-score-s2c-server-20261103/README.md) |
| S2e 高位合并读回 | 10420140 | 约0.2950004（原报告精度） | [同RTL对照/完整VCS](validation/xu-score-s2e-server-20261104/README.md)、[自己网表实际面积及42,338点原生FM成功](validation/xu-score-server-core107-20261104/README.md) |
| S2d 双X缓冲 | 11859141 | 0.3036302710 | [S2d验收](validation/xu-score-s2d-server-20261103/README.md) |
| S3 32PE / 1024宏 | 11376501 | 0.5186033811 | [32PE面积](validation/xu-score-s0-soc-20261102/pe32-area-server-20261103/README.md) |
| S3 64PE / 1024宏 | 11301600 | 0.9184209509 | [64PE周期](validation/xu-score-s0-soc-20261102/s3-pe64-server-20261103/README.md)、[面积](validation/xu-score-s0-soc-20261102/s3-pe64-ppa-server-20261103/README.md) |
| S3 紧凑32PE / 128宏 | 11376501 | 0.5752035631 | [指定宏VCS及三配置对照](validation/xu-score-s3-pe32-bank128-server-20261103/README.md)、[三库448宏面积](validation/xu-score-s0-soc-20261102/pe32-bank128-area-server-20261104/README.md) |

64PE比32PE周期减少0.658383%，原综合面积增加77.095%左右。64PE面积占预算40.8187%，预算还有余量，但当前每层writeback约占70.66%，继续只增加输出列PE的实际边际收益已小。双缓冲本次比S2c慢0.143%左右且面积增加约2.995%；这些是已测周期/面积取舍，尚不能在缺少全SoC能量时完整判定三维支配关系。

紧凑32PE的逻辑W保持32KiB，物理W由原64KiB降到32KiB。它在同主仓、同wide固件image下与原32PE逐层周期相同；实际三库综合加速器面积却增加10.913963%，占预算25.564603%。448个实际宏由320个1024×16和128个128×16组成。宏外围/选择逻辑不能忽略，容量减半没有带来本次总面积下降；能量仍须独立测量。

## 改动的生产Chisel

每项都在独立功能分支；生成RTL和测试改动详见该项原件入口。

| 候选 | 生产Chisel文件 | 行为变化 |
|---|---|---|
| S1 H2-only | `GenerateRTL.scala`、`linear/LinearCachedCore.scala` | 真正移除elaboration中的完整bias cache |
| S1 SRAM bias | `GenerateRTL.scala`、新增`linear/BiasSramCache.scala`和`linear/LinearSramCachedCore.scala` | 同步SRAM bias存储及tile预取 |
| S2a/S2b/S2e | 无新增Chisel改动 | stream/packed MMIO及paired-HI读回与固件调度变化在接口RTL中实施 |
| S2c | `GenerateRTL.scala`、新增`linear/LinearAutoGroupCore.scala` | 外层group调度、两槽8×48结果FIFO，按POP响应退休释放 |
| S2d | `GenerateRTL.scala`、新增`linear/LinearBufferedComputeCore.scala`及`linear/LinearDoubleBufferCore.scala` | 两套X行缓冲/描述符，保持单个8PE和W阵列 |
| S3 32PE | `GenerateRTL.scala`、新增`linear/XuParallelCore.scala` | 单32PE/32bank、显式旧8lane mask和wide调度、两槽32×48结果FIFO |
| S3 64PE | `GenerateRTL.scala`、新增`linear/XuParallel64Core.scala` | 单64PE/64bank、8/32/64宽调度与真实lane使能；复用原参数化组件 |
| 紧凑32PE | `GenerateRTL.scala`、`linear/XuParallelCore.scala`、新增`memory/Sram128x16.scala` | 每bank4片128×16，保持注册返回选片和1周期读延迟 |

文件路径相对于各候选的`src/main/scala/`。紧凑32PE生产代码起于`c684402`，最终冻结main为`f75880d4f06ccb7f1c16115bee501f53d9a2abb7`、child为`52cfbea1f79f10e44f7d1696f54015797f886b96`；其实际VCS/逐层/原件SHA交付提交为`360ddae`。64PE冻结main为`3443fad8945577626d226b1cd53eadec89331a20`、child为`7aae96776e116d5e95d6ebb49d29a5fccce04ab9`，实际五配置VCS提交`5ee9680`，面积原件提交`214dbc9`。

## 资格与能量的实际状态

- 数值：固定整数格式与RTL逐位对照，以及可获得验证集的浮点误差评估已有独立证据。未公布的官方600样本不能冒充已测；静音12层不冒充完整encoder或全验证集。
- 原网表数字逻辑综合一致性：baseline、S1、S2b/c/d和32PE已有各自完整Formality原件。[完整终态归档](validation/xu-score-s0-soc-20261102/candidate-formal-completion-20261104/README.md)确认S2d修复网表43440点、32PE修复网表47758点和64PE原网表55537点全部验证成功；SRAM内部黑盒、511 unread及17/33/65 reference unmatched保留。[新增实际证明](validation/xu-score-cleanup50-bank128-formal-server-20261104/README.md)确认紧凑32PE自己的三库/164RTL/own SVF证明52334点PASS、346输入before-after相同；清理50亦41462点PASS、176输入相同，508 unread。没有借用旧网结果证明新网。
- 150MHz：有限CDC/forwarded-clock场景下，baseline修复49已将56项max-cap降至0；无负载清理分支50→63→73→79→95将min-cap1404→187→53→33→20→17，仍有5项reset removal及27124项untested。另一分支50→reset61实际插入40个库反相器，5项removal消失、最差min slack+0.00601495ns，但仍187项min-cap和2项PMU recovery unknown；[该61网表完整FM亦PASS41462点](validation/xu-score-server-export78-20261104/README.md)，217输入不变。两个分支不能拼接成同网表通过。完整时序资格仍未闭合，[实际79/86原件](validation/xu-score-server-export91-20261104/README.md)保留20项min-cap、五HF recovery缺路径及两条诊断错误；[实际95原件](validation/xu-score-server-export103-20261104/README.md)进一步确认17项min-cap、0 max-cap和5项reset removal，最终清理链仍无独立FM。原全propagated未CTS负slack未改写。
- 能量：正式窗口按任务前清空、first source REQUEST→final Y response RETIRE构造；baseline和[S2c均已完成完整12任务](validation/xu-score-s2c-full-soc-power-server-20261104/README.md)。S2c正式elapsed总11887872（990656/任务），对应原网表9c16的12次全SoC PT已实际完成：报告均值34.766666…mW，P×窗口合计2.7553445546669448mJ，仅诊断，不能代入评分。net活动file34.24%、propagated59.18%、default0.78%、implied5.80%；32.67%是至少一次toggle的覆盖，不能当file注释率。[实际107终态](validation/xu-score-server-core107-20261104/README.md)确认93已流式读取24份原生报告、12任务/540,288个pin block；原native报告约805MB/份和12 mapped SAIF正文未返回，本地尚未重放全部compact行，不能由终态标签推导能量资格。S2c joint36交易字符串损坏原件保留；12.3GB sidecar已有服务器完整流式SHA和672原始边界审查PASS，但稀疏子集仍不是完整波形或能量资格。
- 原wrapper平均功耗和当前单macro诊断功率都不代入比赛全SoC单任务能耗评分。未知Q不直接赋0或0.5；满足指定宏真实hold前提的稳定未知Q可关闭其Q-edge能量，绝对状态对下游标准单元的影响另行分析。

## 接续顺序

1. 已取回全部上述终态原件。继续追查HF→LF复位恢复路径为何未形成，实际只读86已确认外部HF reset到全部5端点均缺recovery，而LF watchdog到3个AON端点有路径；PTE-052边沿展开警告仍待证伪。逐批核查实际95余下17项无负载输出；保留原库、SDC及未测范围，不靠豁免取得通过。
2. 已在独立S2e工作树实现两个结果高16位合并读回，保持原48bit数学值、64bit符号扩展Y内存、旧全部ABI及同RTL旧固件对照；无Chisel改动。[同一服务器GCC10.2/VCS完整验收](validation/xu-score-s2e-server-20261104/README.md)已实际完成：同新RTL调度对照11842200→10420140，减少12.0084106%；271项runtime身份不变、192旧配置image一致。[实际107原件](validation/xu-score-server-core107-20261104/README.md)已确认S2e自己的加速器面积约0.2950004mm²、own-SVF原生FM 42,338点成功；原driver因成功marker尾随换行误判，原FAIL状态保留，[后继109独立审计已实际完成](validation/xu-score-server-progress114-20261105/README.md)，原FAIL收据保留，181项原件身份和4138项验收文件重新哈希，未重跑DC/FM。159项证明输入before/after相同；SRAM黑盒、511 unread和17 reference unmatched不隐藏。完整150MHz和全SoC能量仍未通过，未借用S2c结果。
3. 复用joint36整数主体及实际流式审查，补数字hold证明、首次未知边沿和标准单元下游能量包络；同时调查mapped门级全SoC活动采集以减少映射/传播不确定性。[实际同库VCS结构探测97](validation/xu-score-mapped-structure-server-20261104/README.md)已核对336宏/22512pin/288预加载句柄，仍仅1fs元数据探测；[实际101](validation/xu-score-server-export103-20261104/README.md)澄清148项共省略952端口全为output，无解析出的遗漏input/inout；两个UDP中一组token不同，调用/行为仍需独立108审查，不能当task00或能量通过。新整数事务API已真实VCS一宏验证，但不等于新全SoC采集通过。
4. 依据同配置(T,E,A)和资格证据形成非支配集合，再决定保留与评分敏感性。尚无最终比赛最高分结论。


## 2026-11-05关机前续接记录

本机按用户要求在2026-11-05 01:00 CST关机，服务器分离进程继续；此处不将未完成实验标为通过。

- [112实际全报告重放](validation/xu-score-native-audit118-20261105/README.md)已完成12任务、24阶段、540288 pin记录、19326860762B原生报告和131728568B compact；本地另独立核对8对原始样本和全汇总关系。全部22512 pins的native x_probability为0，然而每阶段5280个Q在输入SAIF有TX>0，其中4256个整窗TX、native SP=0.5/TR=0；物理未知Q及其下游能量尚未解决，不晋升正式能量。
- [S2e实际task00采集](validation/xu-score-s2e-task00-119-20261105/README.md)已完成。nominal150/LF32768、任务前33697次清零、first source REQUEST至final Y RETIRE elapsed868343/inclusive868344、5788953333333fs；25344输出/50688Y写、3168 POP、25344旧LO加12672 packed-HI实际读。原SAIF SHA5390a5698d41d4734ae218e93c410076e0dd55f9c2e68dfc5cee764e2f7969c7，normalized SHA7d91fc3e15f3abe42c6f3e7572e46f41ad34f3afb6cd4db91be41827f32294d2；22512bit映射和114927非alias保真独立重算通过。只证明活动采集，不证明正式功耗。
- S2e完整12任务活动已启动，服务器目录`s2e-formal-activity12-20261105-120`，采集进程PID18987。00:50时`/proc/18987/cmdline`真实存在；121快照仅RUNNING，不把12个预建task目录当12任务完成。不能因观察超时重启。
- [111/115原始失败审计](validation/xu-score-mapped-audit115-20261105/README.md)确认公共门级任务在首REQUEST前480ns触发unknown_shared_handshake，VCS Fatal返回0，而原driver先抛退出码分类错误。111失败完整保留；115重哈希636输入前后相同。不能改成公共任务完成。
- 117原生同检查模式被动回调实际采集完成，121已取回其完整log/453 events/状态；目标notifier变化后Q变X，但部分握手瞬态X更早，尚无完整连接因果证明。无force、DUT FF/Q写入或timing检查压制。
- [116本地工具](validation/xu-score-timing116-local-20261105/README.md)实际部署并启动PID25920。在同一baseline95派生映射组合有界清理和40个native反相器，再重跑自己的DC/PT/FM；121快照DC/PT已执行、FM仍RUNNING，不能宣布最终通过，也不能借作S2e时序证明。

本轮改动为采集/审计工具与证据；没有新Chisel修改。最终比赛资格、同配置全SoC能量和最终(T,E,A)选型仍未完成。


## 2026-11-05上午取回的完整终态

关机前记录是当时快照，以下补充已取回的终态，不改写原运行中或失败原件。

- [actual116同一最终映射DC/PT/FM](validation/xu-score-timing116-terminal122-20261105/README.md)已完成，DC/PT/FM各rc0且唯一marker，自己的完整FM41,462点成功。最终mapped SHA `16d29dea71ed2668b33c893e1a38be01a6eea02ca190ba8aabcb4658fe610292`，own repair SVF SHA `2574d971c759fc2650ed660b52b6219928c54117be156cdf616ccbea10f1d90a`；组合删除47个native证明非时序且无接收者的单元，五reset端点共插入40个CLKINV。274份冻结输入before/after相同；min-cap、max-cap、removal违例均为0。仍有27,124 untested、2个PMU recovery UNKNOWN、5个HF recovery定向查询缺路径、9,126脉宽及10,416宏条件周期未测；最差报告setup为clock-gate latch的0ns。该网表是baseline116方法实验，不能借作S2e资格或宣布完整150MHz通过。122原包1,283,388B，SHA `654e1c7b3a4d22f41810b0d3a7c1a73de9707f79e879b254e558374cf5dd6c50`，121项37,978,683B全部校验。
- [actual120完整12任务活动及125逐bit独立复核](validation/xu-score-s2e-activity120-server125-20261105/README.md)已完成，原顶层状态`COLLECTED_12_TASKS_REVIEW_PENDING`。每层elapsed868,343，总10,420,116；inclusive合计10,420,128。相同正式窗口S2c为11,887,872，减少12.3466673%；不混用开发窗口10,420,140/11,842,200。逐层CSV保存原12日志/24SAIF完整SHA。完整125原包8,171,768B，SHA `ebfba2f46193dca30362ccce4fbbe602be238abd21a316240da0da2f828fbf10`，88项465,539,700B无省略。独立实际重读12对SAIF，270,144个macro pin-bit与1,379,124条非alias信号逐项核对；原未知TX/TZ/TB保留。own89/109身份绑定及清零/窗口/向量层映射通过复核，仍只证明RTL活动采集和原件保真，不是mapped活动、功耗或比赛资格。交付提交`8c16b8c`。

本轮仍无新Chisel修改。下一步在S2e自己原映射测量全SoC功耗，同时对baseline116做只读覆盖/RDC审查；不同网表的资格不互借。

## 2026-11-05新增资格诊断与批量安排

- [132完整只读覆盖/RDC](validation/xu-score-coverage132-server135-20261105/README.md)及两份真实Tcl/analysis已独立逐字节复现，提交`6eb1410`。416 active min-period MET，10416项属于常量禁用模式；27124 untested保持相同。5HF及2PMU any-source recovery仍未形成可报告路径，10000条timing_arc full_name属性警告、PTE边沿展开警告均保留，不能宣布完整150MHz。
- [141完整原件](validation/xu-score-resource-function141-20261105/README.md)，提交`9891813`：128使用原111同binary/TB/vector/clock/reset，仅追加`+notimingcheck`，公共门级任务完成25344输出/50688Y写/elapsed990656；原60私有检查门槛仍Fatal。636输入服务器before/after相同，不升级完整功能、时序或能量资格。133对目标S2c网表只读定位58名称端点、1表达式物理操作数候选、1待对应，实际解除0项门槛。
- own S2e时序134工具已独立冻结并上传，20项host检查及服务器完整readonly/preflight通过；尚未执行DC/PT/FM，不能借116的修复图/证明链。S2e130原进程继续自己的12任务全SoC功耗，在141快照时current_task_id=4，尚无最终能量结论。
- 用户授权将其余8个有独立mapped原件的候选全部排队，候选内按依赖顺序执行，S2e原任务及S2c资格工作保留。137身份草案提交`1bd053d`，候选为H1+H2、两种S1、S2b、S2d、32PE、64PE、compact32/128；S2a缺独立mapped，未猜入。资源初查96核、约709GiB可用内存及1.54TB工作盘余量；许可证总配额/余量仍未知，不据已有checkout推断多席位。138可执行冻结/依赖队列准备中，未把准备完成写成服务器入队或能量完成。

各候选仍需同配置的正式吞吐、全SoC单任务能量、面积与完整验收；所有失败和运行中快照保留，暂不计算比赛最终得分。这轮没有新增生产Chisel改动。

## 2026-11-05统一总控实际上线

用户要求额度耗尽后仍能自动续跑。`f8c6875`统一入口150已在服务器分离运行，PID159584真实核验；
接续原S2e130、已完成138，随后按依赖自动运行S2e134和独立baseline142。
`state.json`/`SUMMARY.md`/append-only events持久保存，冻结输入/注册/worker，文件锁防重复总控，
缺进程且回执不全时保留孤儿待审，不自动重启。

[149原件归档](validation/xu-score-queue-control149-20261105/README.md)96载荷5719875B全部核验，
原包SHA `60c25e5ddcd243a924adf00278aacd47c546ed9aa33693aed9794642094b84e4`。
138八项实际freeze/adopt全部完成，before==after且errors为空；各自FM成功点31213—55537。
S2d/32PE选修复图，与历史面积图不同，后续必须同图重测面积；SRAM内部仍未证明。
149快照130已进入task11、11项执行回执，原PID135097仍alive，未重复启动。
143/144查询仅反映当前checkout、总配额未知，继续本用户原生实验上限1。
145正式活动、146全SoC能量/面积、147私有检查将通过150登记真实worker，未完成适配的阶段仍如实待执行。
当前全部保持`NOT_QUALIFIED`，生产Chisel/RTL无新改动。

## 2026-11-05统一批次154实际登记

[151完整终态](validation/xu-score-terminal151-20261105/README.md)独立复核130的12层原PT、134的CSV字段失败及142的21份报告。
S2e总10420116周期，诊断平均35.3333mW、12层2.454516mJ；未知SRAM Q/条件功耗仍未解除，不能评分。
134五native成功后Python字段131072上限失败；142仍7个recovery展示缺口与27124 untested。

已交付145/146/147/153/155/156及唯一入口[154](../build/xu-campaign-batch154/README.md)，
提交`6bb9540`、`c4ce764`、`c6a0fee`、`5a15ae0`、`ec916c4`、`fba98a6`、`5d87300`。
154实际在服务器完成完整bundle哈希校验、原控制目录快照及153迁移，20新任务全部现场重哈希后原子登记，
保留原4项共24节点。11:20原生槽位由155 PID228701占用（包括重哈希空档），其余按依赖等待。
固定同一服务器VCS/SiFive绝对路径及工具SHA；当前许可证余量未知，native cap1。
后续独立候选失败不覆盖，success依赖失败明确阻断，最后自动生成同图面积/诊断能量/逐层周期/日志SHA报告。
所有任务仍是诊断/证据续行，不代表比赛资格；当前生产Chisel未新增修改。
