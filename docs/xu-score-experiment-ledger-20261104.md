# xu：优化实验与资格证据台账

目标沿用[xu-score-optimization-plan.md](xu-score-optimization-plan.md)：通过资格门槛后，以同一冻结配置的吞吐、全SoC单任务能量、加速器面积比较评分和非支配候选。面积上限为 **2.25mm²**。本台账汇总已取回的实际原件，不替代各独立分支，不宣布最终选型或完整比赛资格。

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
| S2d 双X缓冲 | 11859141 | 0.3036302710 | [S2d验收](validation/xu-score-s2d-server-20261103/README.md) |
| S3 32PE / 1024宏 | 11376501 | 0.5186033811 | [32PE面积](validation/xu-score-s0-soc-20261102/pe32-area-server-20261103/README.md) |
| S3 64PE / 1024宏 | 11301600 | 0.9184209509 | [64PE周期](validation/xu-score-s0-soc-20261102/s3-pe64-server-20261103/README.md)、[面积](validation/xu-score-s0-soc-20261102/s3-pe64-ppa-server-20261103/README.md) |
| S3 紧凑32PE / 128宏 | 11376501 | 尚未收取终态报告 | [指定宏VCS及三配置对照](validation/xu-score-s3-pe32-bank128-server-20261103/README.md) |

64PE比32PE周期减少0.658383%，原综合面积增加77.095%左右。64PE面积占预算40.8187%，预算还有余量，但当前每层writeback约占70.66%，继续只增加输出列PE的实际边际收益已小。双缓冲本次比S2c慢0.143%左右且面积增加约2.995%；这些是已测周期/面积取舍，尚不能在缺少全SoC能量时完整判定三维支配关系。

紧凑32PE的逻辑W保持32KiB，物理W由原64KiB降到32KiB。它在同主仓、同wide固件image下与原32PE逐层周期相同；宏外围/选择逻辑的成本必须等真实综合报告，不能按容量减半推算面积或能耗。

## 改动的生产Chisel

每项都在独立功能分支；生成RTL和测试改动详见该项原件入口。

| 候选 | 生产Chisel文件 | 行为变化 |
|---|---|---|
| S1 H2-only | `GenerateRTL.scala`、`linear/LinearCachedCore.scala` | 真正移除elaboration中的完整bias cache |
| S1 SRAM bias | `GenerateRTL.scala`、新增`linear/BiasSramCache.scala`和`linear/LinearSramCachedCore.scala` | 同步SRAM bias存储及tile预取 |
| S2a/S2b | 无新增Chisel改动 | stream/packed MMIO与固件调度变化在接口RTL中实施 |
| S2c | `GenerateRTL.scala`、新增`linear/LinearAutoGroupCore.scala` | 外层group调度、两槽8×48结果FIFO，按POP响应退休释放 |
| S2d | `GenerateRTL.scala`、新增`linear/LinearBufferedComputeCore.scala`及`linear/LinearDoubleBufferCore.scala` | 两套X行缓冲/描述符，保持单个8PE和W阵列 |
| S3 32PE | `GenerateRTL.scala`、新增`linear/XuParallelCore.scala` | 单32PE/32bank、显式旧8lane mask和wide调度、两槽32×48结果FIFO |
| S3 64PE | `GenerateRTL.scala`、新增`linear/XuParallel64Core.scala` | 单64PE/64bank、8/32/64宽调度与真实lane使能；复用原参数化组件 |
| 紧凑32PE | `GenerateRTL.scala`、`linear/XuParallelCore.scala`、新增`memory/Sram128x16.scala` | 每bank4片128×16，保持注册返回选片和1周期读延迟 |

文件路径相对于各候选的`src/main/scala/`。紧凑32PE生产代码起于`c684402`，最终冻结main为`f75880d4f06ccb7f1c16115bee501f53d9a2abb7`、child为`52cfbea1f79f10e44f7d1696f54015797f886b96`；其实际VCS/逐层/原件SHA交付提交为`360ddae`。64PE冻结main为`3443fad8945577626d226b1cd53eadec89331a20`、child为`7aae96776e116d5e95d6ebb49d29a5fccce04ab9`，实际五配置VCS提交`5ee9680`，面积原件提交`214dbc9`。

## 资格与能量的实际状态

- 数值：固定整数格式与RTL逐位对照，以及可获得验证集的浮点误差评估已有独立证据。未公布的官方600样本不能冒充已测；静音12层不冒充完整encoder或全验证集。
- 原网表数字逻辑综合一致性：baseline、S1、S2b/c/d和32PE已有各自完整Formality原件。SRAM内部是黑盒、unread/unmatched及undriven假设均披露。64PE、后续修复网表和紧凑32PE须以自己的网表/完整SVF链证明，不能借用旧网结果。
- 150MHz：已有源推导有限CDC/forwarded-clock场景下的真实PT检查及映射修复。最近已取回的baseline定点驱动修复49将56项max-cap降到0；1404项min-cap、5项reset removal及27127项untested仍保留。完整时序资格未闭合，原始全propagated未CTS视图的负slack也没有被改写。
- 能量：正式活动窗口按任务前清空、first source REQUEST→final Y response RETIRE构造；baseline已有12任务记录。S2c全12活动、候选joint观察和PT条件弧入口正在补齐。原PT48入口实际return0，但父脚本误匹配Tcl回显形成FAIL，后审单独记录，不覆盖原状态。S2c joint36交易描述字符串损坏，336宏的整数计数主体可独立审查；12.3GB同刻事件sidecar仍在服务器，尚未本地重放。
- 原wrapper平均功耗和当前单macro诊断功率都不代入比赛全SoC单任务能耗评分。未知Q不直接赋0或0.5；满足指定宏真实hold前提的稳定未知Q可关闭其Q-edge能量，绝对状态对下游标准单元的影响另行分析。

## 接续顺序

1. 恢复服务器访问后先取已启动job的终态和原件：64PE完整FM、S2d/32PE修复FM、紧凑32PE三库PPA及S2c全12活动；不因观察中断重启。
2. 执行已具体化的1404全输出无接收单元清理和完整SVF链FM，逐项核查新增上游悬空；再对具体reset支路做独立时序实验，保留原SDC和所有未测范围。
3. 复用joint36有效计数主体、独立交易log与服务器sidecar流式审查，完成条件活动/未知边界的实际PT消费；用同一候选最终网表测全SoC任务能量。
4. 依据同配置(T,E,A)和资格证据形成非支配集合，再决定保留与评分敏感性。尚无最终比赛最高分结论。
