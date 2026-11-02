# xu H1/H2 硬件优化实验 — 2026-11-02

**功能和周期验收完成，服务器完整 VCS 验收 PASS。保留 `bias-hw-window / -O2 / both-unroll-no-masks`：真实12层总周期从 25,251,416 降至 16,510,344，减少 8,741,072（34.616166%），加速比 1.529430×。新增 Chisel 全层 bias 缓存与 E203 Verilog MMIO 固定结果窗口，8 PE 与精确数值计算保持不变。**

服务器SMIC40 RVT SS/0.99V/125°C工艺库评估：完整候选加速器（含16个权重SRAM宏）综合面积 **0.293988516 mm²**，占用户更正后2.25 mm²限额的 **13.0662%**。实际活动驱动的平均功耗与单层能量均上升，详见下文；当前交付是周期优化候选，尚未完成物理签核。

本轮基线是已完成软件优化的 B0；早期 `f0f27b4` 的28,416,892周期只作软件历史参考，不作本轮硬件收益分母。主指标来自完整平台任务窗口，包含本任务 bias 缓存上传、CPU搬运与控制成本，最终重复验收逐层复现选中实验。该夹具是单个真实 checkpoint silence 样本的12个独立 FFN1 层，不代表完整 encoder 或官方600样本准确率。

## 冻结身份与工作树

- 独立工作树：`/home/mxhanks/Projects/ChipContest-xu-optimize-hw`，分支 `codex/xu-optimize-hw`；由软件交付 `499ba54bd57db81c058ab5efe25def226ec6dd15` 创建。
- 本次全部服务器实验的执行源码固定为 **`97b35421dfbbfa8f4d495b6927a7c66610ff8206`**，E203 gitlink 为 **`f49a5fc914971426bd4530db39e270a84b41139f`**。后续报告提交只补充证据，不改变本次执行身份。
- 软件 B0 执行源码为 `8a7640787423a73a0751454de47893406f85e604`，旧 E203 为 `e36d34a52e6eef93fd0bdfed1b13009e1056bea3`；B0 固定配置为 `bias-dtcm / -O2 / both-unroll-no-masks`。
- 固定 signed16 X/W、signed40 bias、signed48 Y、8 PE、99行×32组×64 MAC拍、原48个向量文件、W bank映射、共享RAM、全局 modulo-7 背压、ITCM装载和Y响应退休后ACK。每任务仍重新装载全部W/X/bias，层间不复位。
- 原工作树复核仍干净：`ChipContest` 为 `c71a0eaae45efa4d5df599aa14076241854c4503`，`ChipContest-platform-eval` 为 `c08cac39a110eff9c334bb16ad9d482cb80d6174`，`ChipContest-xu-optimize-fw` 为 `499ba54bd57db81c058ab5efe25def226ec6dd15`。原服务器副本与历史结果保留。

| 提交 | 内容 |
| --- | --- |
| `d265f3455c1667e272646686a6251274da11b9a6` | H1/H2计划与固定边界 |
| `e49427f64fb24320ff86a0f5371a20ac938af5ef` | Chisel完整bias缓存、兼容MMIO结果窗口及子模块gitlink |
| `b81f4b402b19cf817ca51d90442b869f8287ef9c` | 独立硬件campaign与B0兼容验收 |
| `97b35421dfbbfa8f4d495b6927a7c66610ff8206` | 独立固件路径、事务/阶段验收与窗口活动采集 |
| 子模块 `f49a5fc914971426bd4530db39e270a84b41139f` | 生成RTL与ICB包装实现，分支 `codex/xu-optimize-hw` |

计划见 [xu-hardware-optimization-plan.md](../../xu-hardware-optimization-plan.md)，原软件基线见[软件阶段交付](../xu-fw-optimization-20261102/README.md)。

## 实现与独立判定

H1在Chisel中新增 `BiasBankCache` 与 `LinearCachedCore`。缓存使用8 bank×32项×40 bit的 `Reg`，逻辑容量1,280字节，数据不复位；缓存使能复位为0，旧8槽bias路径继续可用。固件在全部W装载后、首行X装载前关闭缓存路径，显式上传256列共512个共享读字、768笔ADDR/LO/HI写，再写使能。两笔CACHE_CTRL写均位于任务窗口内。每组由GROUP选择8个偏置，原点积核、MAC有效拍和结果链不变；H1不再分配2KiB bias DTCM副本。

缓存使能会跨调用保持；从新缓存模式切回旧固件前，须显式写 `CACHE_CTRL=0` 或复位。旧ABI兼容以复位默认状态和上述调用协议为前提，不保证无复位时任意profile切换。

H2新增16个固定地址的只读结果别名，避免每个输出先写RESULT_INDEX。旧RESULT_INDEX/LO/HI继续可用；窗口不自增、不弹出、不暗含START/ACK，写入无作用。固件仍逐lane执行低字读/写、高字读/符号扩展/写，保持全部Y顺序和退休口径。

| 新偏移 | 含义 |
| --- | --- |
| `0x040 / 0x044 / 0x048 / 0x04c` | CACHE_CTRL、CACHE_ADDR、CACHE_LO、CACHE_HI；显式列地址与字节掩码 |
| `0x050` | 只读能力值 `0x58550003`；新固件拒绝能力不匹配的旧RTL |
| `0x080 + lane*8 / 0x084 + lane*8` | lane0–7结果低32位/高16位零扩展；高字仍由固件符号扩展 |

原 `0x000–0x03c` 地址语义保持兼容。新控制寄存器没有busy硬件写保护，软件须在计算期间保持模式/参数稳定；补充定向测试明确观察该行为，并在违反约束后立即复位，不把该次结果当作正确数值证明。原9份计算核SV与memory实现保持字节一致，新增功能由Chisel源生成，不用手改生成RTL代替实现。

所有性能实验使用同一份完整扩展RTL。B0关闭缓存并用旧结果口，H1仅启用缓存，H2仅启用窗口，再测试组合；这是运行路径隔离，**不是门电路隔离**。H1/H2均与同一B0比较，组合再比较较优单项；仅真实12层总周期严格降低且完整VCS验收通过才保留。完整旧包装与完整新包装的面积差异单独报告。

### 具体Chisel改动

| 文件 | 本次改动及作用 |
| --- | --- |
| [BiasBankCache.scala](../../../src/main/scala/linear/BiasBankCache.scala) | 新增256×40 bit（1,280字节）bias缓存；8 bank×32组，5位逐字节写掩码，按group同时输出8路signed40偏置，支持单列读回。数据不复位，每任务完整刷新。 |
| [LinearCachedCore.scala](../../../src/main/scala/linear/LinearCachedCore.scala) | 新增缓存包装，在原8路bias输入与完整缓存输出间选择；实例化原LinearComputeCore，透传X/W、start/done和result。 |
| [GenerateRTL.scala](../../../src/main/scala/GenerateRTL.scala) | 加入BiasBankCache、LinearCachedCore两个生成目标，原默认生成目标不变。 |
| [BiasBankCacheTest.scala](../../../src/test/scala/linear/BiasBankCacheTest.scala)、[LinearCachedCoreTest.scala](../../../src/test/scala/linear/LinearCachedCoreTest.scala) | 新增全bank/group、字节掩码、符号极值、两任务刷新、旧路径/缓存路径及完整点积结果测试。 |

原LinearComputeCore、8 PE、乘加流水、16/40/48位数值格式没有修改。缓存开关的复位默认0、MMIO上传寄存器和H2固定结果窗口解码实现于E203的`rtl/e203/perips/accel_icb_slave.v`，并非Chisel中增加了结果窗口；子模块安装两份Chisel生成SV后改为实例化LinearCachedCore。固件另配套新增上传/窗口读取调度。

## 服务器实验与最终验收

执行副本：`/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ChipContest`。

输出根：`/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/xu-vcs-hw-campaign-01`。串行使用同一服务器 SiFive GCC-Metal10.2.0-2020.12.8、VCS Q-2020.03-SP2-6、Python3.6.8与主机GCC4.8.5，不并发改写同一安装目录。

B0-new-RTL的12层TB周期、固件mcycle、全部阶段统计与历史B0逐层一致，总周期精确重现25,251,416；加载镜像SHA仍为 `73f5aa7dd9d67e05288e33971617c90565be49eb3a7528841659753f1ae35c46`，本次ELF也与历史一致。随后各独立项和组合均通过synthetic2及真实12层：

| 实验 | schedule | 对比父项 | synthetic2 / real12 | real12总周期 | 相对B0周期下降 | 相对B0加速比 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| B0 | `bias-dtcm` | 历史软件B0重放 | PASS / PASS | 25,251,416 | 0.000000% | 1.000000× |
| H1 | `bias-hw` | B0-new-RTL | PASS / PASS | 18,271,573 | 27.641392% | 1.382006× |
| H2 | `bias-dtcm-window` | B0-new-RTL | PASS / PASS | 23,457,855 | 7.102814% | 1.076459× |
| H1+H2 | `bias-hw-window` | H1-bias-cache | PASS / PASS | 16,510,344 | 34.616166% | 1.529430× |

组合比更优的独立H1再减少1,761,229周期，最终完整验收复跑与组合逐层TB/mcycle/阶段和事务一致。`retention_status=retained`、`retained_optimization=true`。四个实验没有失败项或无收益项。

### 逐层总周期与固件mcycle

每个单元为 `TB周期 / 固件mcycle`；后三列只对TB总周期做差，均以B0为参考。主窗口从首次共享输入/参数读取接受，到最后Y写响应退休；原首两笔W_BANK/W_ADDR写沿用旧边界排除。固件mcycle覆盖固件调用，和TB窗口边界不同，不能混用。

| 层 | B0 TB / fw | H1 TB / fw | H2 TB / fw | H1+H2 TB / fw | ΔH1 | ΔH2 | ΔH1+H2 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 2,104,281 / 2,104,360 | 1,522,632 / 1,522,715 | 1,954,822 / 1,954,910 | 1,375,864 / 1,375,935 | -581,649 | -149,459 | -728,417 |
| 1 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,823 / 1,954,910 | 1,375,860 / 1,375,932 | -581,654 | -149,462 | -728,425 |
| 2 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,864 / 1,375,935 | -581,654 | -149,464 | -728,421 |
| 3 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,860 / 1,375,932 | -581,654 | -149,464 | -728,425 |
| 4 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,864 / 1,375,935 | -581,654 | -149,464 | -728,421 |
| 5 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,860 / 1,375,932 | -581,654 | -149,464 | -728,425 |
| 6 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,864 / 1,375,935 | -581,654 | -149,464 | -728,421 |
| 7 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,860 / 1,375,932 | -581,654 | -149,464 | -728,425 |
| 8 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,864 / 1,375,935 | -581,654 | -149,464 | -728,421 |
| 9 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,860 / 1,375,932 | -581,654 | -149,464 | -728,425 |
| 10 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,864 / 1,375,935 | -581,654 | -149,464 | -728,421 |
| 11 | 2,104,285 / 2,104,364 | 1,522,631 / 1,522,714 | 1,954,821 / 1,954,908 | 1,375,860 / 1,375,932 | -581,654 | -149,464 | -728,425 |
| 合计 | 25,251,416 / 25,252,364 | 18,271,573 / 18,272,569 | 23,457,855 / 23,458,900 | 16,510,344 / 16,511,202 | -6,979,843 | -1,793,561 | -8,741,072 |

机器可读比较及所有实验原始结果分别见 [comparison.json](comparison.json)、[comparison.md](comparison.md)、[server-json/experiments.json](server-json/experiments.json) 与[最终验收real12](server-json/acceptance/real12/result.json)。

### 阶段、事务与数值工作量

以下阶段均为12层求和。TB只扩展新缓存地址和固定窗口的事件归因，不驱动DUT；缓存上传/使能计入bias阶段，窗口读启动writeback。阶段包含CPU指令、握手与间隙，不能解释为纯总线传输或纯计算耗时。

| 阶段 | B0 | H1 | H2 | H1+H2 | 最终占比 |
| --- | ---: | ---: | ---: | ---: | ---: |
| w_load | 3,587,532 | 3,591,769 | 3,587,533 | 3,587,388 | 21.728124% |
| x_load | 1,378,091 | 1,379,256 | 1,378,477 | 1,378,968 | 8.352146% |
| bias_load | 6,627,180 | 93,312 | 6,627,168 | 93,312 | 0.565173% |
| compute_wait | 2,623,104 | 2,623,104 | 2,623,104 | 2,623,104 | 15.887640% |
| writeback | 9,618,070 | 9,625,176 | 7,821,792 | 7,830,708 | 47.429103% |
| other | 1,417,439 | 958,956 | 1,419,781 | 996,864 | 6.037815% |

| 窗口内事务 / 工作量（12层） | B0 | H1 | H2 | H1+H2 |
| --- | ---: | ---: | ---: | ---: |
| mmio_writes | 1,875,912 | 972,768 | 1,571,784 | 668,640 |
| mmio_reads | 912,384 | 912,384 | 912,384 | 912,384 |
| shared_reads | 278,784 | 278,784 | 278,784 | 278,784 |
| shared_writes | 608,256 | 608,256 | 608,256 | 608,256 |
| shared_stall | 92,024 | 98,581 | 120,891 | 130,320 |
| mmio_stall | 0 | 0 | 0 | 0 |
| starts | 38,016 | 38,016 | 38,016 | 38,016 |
| dones | 38,016 | 38,016 | 38,016 | 38,016 |
| busy | 2,585,088 | 2,585,088 | 2,585,088 | 2,585,088 |
| mac_fire | 2,433,024 | 2,433,024 | 2,433,024 | 2,433,024 |

每任务MMIO写由156,326降至55,720：H1用768笔缓存上传写和2笔使能控制写替代76,032笔旧bias写，H2去掉25,344笔RESULT_INDEX写。共享读每任务仍23,232，全部源参数每任务刷新，收益不是少读真实输入。MMIO读包含实际STATUS轮询，不用静态公式代替实测。能力检查同原ID/busy检查位于首W读之前，不混入窗口事务；其固件指令仍反映在调用mcycle和加载镜像身份中。

四配置均校验304,128个输出、608,256个Y写字、38,016次start/done、2,433,024个MAC有效拍、19,464,192次MAC；compute_wait总周期始终2,623,104。精确整数结果、Y顺序与最终响应退休均不变。

### 固件空间与条件性能

| 配置 | ITCM .text字节 | .data / BSS字节 | main / accel_linear静态栈帧 | DTCM在BSS后可用字节 |
| --- | ---: | ---: | ---: | ---: |
| B0 | 962 | 0 / 2048 | 32 / 48 | 63,472 |
| H1 | 758 | 0 / 0 | 32 / 32 | 65,520 |
| H2 | 942 | 0 / 2048 | 32 / 32 | 63,472 |
| H1+H2 | 722 | 0 / 0 | 32 / 16 | 65,520 |

最终ITCM剩余64,814字节，BSS从2,048降至0，main+accel_linear静态帧合计从80降至48字节。这里是GCC静态函数帧，没有实测栈水位。硬件新增1,280字节Reg逻辑容量不属于DTCM BSS，也不等于新增SRAM宏。

以下仅按假设150MHz换算，未声称物理150MHz时序闭合：

| 指标 | B0 | H1+H2 |
| --- | ---: | ---: |
| 12层窗口总延时 | 168.342773 ms | 110.068960 ms |
| 平均每任务延时 | 14.028564 ms | 9.172413 ms |
| 任务吞吐 | 71.283131 task/s | 109.022562 task/s |
| 有效MAC吞吐 | 0.115622 GMAC/s | 0.176836 GMAC/s |
| 按2 ops/MAC换算 | 0.231245 GOPS | 0.353673 GOPS |
| MAC有效拍 / 总窗口 | 9.635198% | 14.736362% |

## 完整验收与本地证据的范围

[acceptance.json](server-json/acceptance/acceptance.json) 的 `profile=vcs-platform`、八个步骤全部PASS：host49项（含真实VCS direct-wrapper）、numeric34项、固定真实向量12层整数核算、doctor、原SoC五项、synthetic1、连续synthetic2、real12。原SoC五项为 `rv32ui-p-add / accel_mmio / accel_compute / accel_multigroup / accel_repeat_x`。direct-wrapper接受/退休均4,909次；另行完整VCS补充接口检查接受/退休均4,967次，原始[编译/运行命令与状态](server-json/extra-evidence/extra-interface-vcs-01/commands.json)及[日志](server-json/extra-evidence/extra-interface-vcs-01/simulation.log)随包保留。

服务器验收明确 `not_run=[icarus1,chisel]`。本地另行做过Chisel13项和Icarus定向验证，不能填成VCS步骤已运行。Chisel逐测试39份原始日志已归档；13/13与75秒汇总来自此前工具stdout观察收据，原汇总stdout没有重定向保存。见[本地完整摘要](local-screening-summary.md)、[Chisel覆盖摘要](xu-local-evidence-summary.md)、[本地独立核验](local-verification.json)。本地另有7次SoC筛选/10任务均PASS，使用GCC14/Verilator，与服务器SiFive10/VCS性能不混算。

补充接口覆盖结果RO窗口全部16字写忽略、CACHE_CTRL/CACHE_ADDR的busy写行为，且明确排除违规参数切换期间的数值检查。基础wrapper还覆盖缓存全列/组边界/字节掩码、旧路径、结果窗口与旧索引交错、背压和同拍退休/接受。Chisel缓存/包装测试覆盖signed40极值、两任务刷新与group0/15/16/31，原完整99×256层结果回归通过。

[服务器独立核验](server-verification.json)已PASS：主包38份原始文件、补包2份wrapper原日志，214个提交运行源文件及11次数值仿真记录均通过；最终逐层、向量和加载image与选中实验一致。原数值全文日志留服务器，核验明确区分6条完整原文、22条非空派生摘录、130条仅有源端全文哈希的空摘录。完整日志失败扫描仍由源码身份已核对的服务器运行器承担。审计另用1个阳性控制和16个故意损坏反例核对拒绝行为，记录见[独立审核工具与命令](evidence-tools/independent-audit-README.md)。

## 同库完整包装面积与时序

本次用相同SS标准单元/SRAM库和相同clock/IO约束，对**完整旧accelerator wrapper/core**与**完整新wrapper/core**做paired综合与STA；不包含CPU、系统互联或共享RAM。旧RTL取软件B0执行源码，候选取97b3542/f49a5fc。两项能力在候选门电路中同时存在，不能把运行期H1/H2独立开关当作各自硬件面积增量。

原始精确报告文本及SHA见 [paired-exact-summary.json](ppa/paired-exact-summary.json)，本地对源端报告原始字节的SHA核验见 [report-byte-verification.json](ppa/report-byte-verification.json)。原始单位报告未建立area单位；随后已从同服务器工艺LEF核对4种标准单元及SRAM的物理宽×高，确认数值单位为µm²。源端物理单位收据按用户先前2.5 mm²生成，保持原字节；[当前限额记录](area-requirement.json)和独立预算核验已按最新更正的2.25 mm²重新计算。完整新加速器为 **0.293988516 mm²**，满足用户最新指定的 **2.25 mm²** 综合面积上限，占13.0662%，余量1.956011484 mm²。详见[面积评估](area-assessment.md)、[物理单位收据](area-compliance.json)和[独立预算核验](area-limit-verification.json)。下表原始数值保留为µm²。

| 项目 | 完整旧包装 | 完整新包装 | 差值 |
| --- | ---: | ---: | ---: |
| 总cell area | 181530.844586 | 293988.515714 | +112457.671128 |
| SRAM macro area | 146376.390625 | 146376.390625 | +0.000000 |
| 非macro cell area | 35154.453961 | 147612.125089 | +112457.671128 |
| SRAM宏数量 | 16 | 16 | 0 |
| 最差setup slack（ns） | +0.002345 | +0.002921 | +0.000576 |
| 最差hold slack（ns） | -0.115133 | -0.118136 | -0.003003 |

总cell area增加61.949622%，增量112,457.671128全部来自非macro单元；16个 `RAMSP1024X16` 宏面积146,376.390625保持不变。256×40 cache实际为Reg和读选择逻辑，未映射成新增SRAM。面积代价明显，不把周期收益解释为面积收益。 按本次完整包装面积与12层窗口周期简单相乘，area×cycles比B0增加约5.89%；该派生量仅说明面积与延迟的取舍，不是本轮预设评分函数。最终组合按计划的周期/正确性门槛保留为性能候选，不能据此称为面积最优或完整SoC/PPA签核通过。

库为 `scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db` 和 `RAMSP1024X16_ss_0p99v_0p99v_125c`；同一实验SRAM adapter沿用EMA=010、EMAW=00，PVT资格尚未建立。约束为6.666666667ns周期、clock uncertainty/transition各0.1ns、输入/输出delay各0.5ns、输入transition0.1ns、输出load0.01pF、复位输入false path。

DC报告明确 `Net Interconnect area undefined (No wire load specified)`；未读入布局布线RC/SPEF，不能将manifest中的通用wire-load说明当作实际已启用wire-load模型。PT仍各有256项hold violated，setup/hold各416项untested，且recovery/removal等检查未测；最差hold分别为−0.115133ns和−0.118136ns。因此即使setup为微小正slack，也不构成物理时序闭合或官方signoff。

### 保留的排障记录

以下为流程装配或派生处理问题，原输出保留，未归入已通过的四项性能实验：

- `baseline-ss-01` 的首次PT启动出现 `PT-063`（未配置Library Compiler路径）；在 `pt-baseline-fixed-01` 设置LC环境后对同一netlist/SDC重新运行，后续paired exact审计无工具Error。
- `candidate-ss-01` 的分析源表遗漏 `BiasBankCache.sv`，link失败；`candidate-ss-02` 加入两份新SV后完成DC/PT，未修改硬件源码。
- `activity-01` 的旧TB观察补丁匹配失败，未启动数值仿真。`activity-02` 的两侧real1数值回放均PASS；候选的慢速逐行gzip派生受控停止，保留partial和状态，再使用新名称的buffered派生工具及新输出完成后续分析。停止的是派生产物处理，不是VCS结果校验。

### 功耗

**真实工作负载驱动的估算已经完成；平均功耗和单层能量均变差，不能声称节能。** 同一标准单元/SRAM库、约束和完整加速器范围，旧RTL/软件B0与新RTL/组合固件分别回放真实layer0，各自整数结果、全部层计数器和加载镜像与正式验收逐项一致。两侧原始VCS均为4ns时钟；保留10ps timescale，把所有时间戳按5/3缩放到150MHz，非时间戳行SHA一致且不删事件，最大舍入误差1/3 tick。该转换是分析条件，不是物理频率测量。

PT使用 `power_analysis_mode=averaged`、`read_vcd -rtl` 和明确的加速器层级/任务时间窗口，读取同一paired综合的mapped netlist/SDC。`activity-power-exact-01` 复跑仅把功耗报告改为 `report_power -verbose -significant_digits 8`，实际报告明确 `Dynamic Power Units = 1 W`、`Leakage Power Units = 1 W`，避免从默认library单位猜测。

| 实测活动输入下的估算 | 旧硬件 + 软件B0 | 新硬件 + H1+H2 |
| --- | ---: | ---: |
| Cell internal power | 2.655571 mW | 11.454602 mW |
| Net switching power | 0.205575 mW | 0.362009 mW |
| Cell leakage power | 0.333364 mW | 0.468792 mW |
| Total power | **3.194510 mW** | **12.285402 mW** |
| 其中clock_network分组（含寄存器时钟引脚） | 1.878897 mW | 10.292712 mW |
| PT显式窗口时长 | 14.02853333 ms | 9.17242000 ms |
| 窗口功耗×时长估算能量 | **44.814287 µJ** | **112.686867 µJ** |

平均功耗为旧版3.845786倍，单层窗口能量为2.514530倍。大部分功耗增量归在工具的clock_network组，和新增大量寄存器的代价一致；该组含寄存器时钟引脚，不能解释成已布置时钟树的实测功耗。此结果支持后续研究缓存实现/时钟使能，但本轮没有再修改冻结硬件。

原始报告的net活动覆盖为：旧版17,350条中3,147（18.14%）直接VCD、12,492（72.00%）传播、1,439（8.29%）隐含、272（1.57%）默认；新版74,154条中10,281（13.86%）直接、55,537（74.89%）传播、8,064（10.87%）隐含、272（0.37%）默认。主输入73/73与memory输出256/256均直接覆盖；sequential直接覆盖由2,241/2,262（99.07%）变为8,644/12,511（69.09%），候选另3,850（30.77%）传播。保留原始覆盖报告，不把传播/default当作直接波形观测。

窗口按首尾边沿差计算，比性能的inclusive周期数少一拍，能量明确采用PT实际时长。功耗只覆盖单个真实layer0、加速器wrapper，属于RTL活动映射/传播到综合门表的布局前平均估算；不是全SoC、完整样本集、带毛刺门级仿真或硅片测量。未指定wire-load，未提取RC，时钟理想，SRAM adapter资格、hold违例与未测时序仍限制签核。

原始活动/日志/方法包见 [hw-final-artifacts-01.tar.xz](artifacts/hw-final-artifacts-01.tar.xz)（97份原文加manifest）；[精确功耗收据](activity-evidence/power-exact-state.json)与[独立核验](power-verification.json)包含具体输入SHA、两侧原文单位/数值和能量复算，核验PASS。大VCD保留服务器，仓库只保留其SHA、转换元数据与完整小日志；本地审计未独立读取全部大波形。详见[功耗复现与证据](power-reproduction.md)。

`ppa-verification.json`及原始paired收据中的“area units未确认 / vectorless probe”描述的是较早面积/STA阶段，当时确实不能作mm²或工作负载功耗结论；后续分别由物理LEF证明、实际VCS活动和明确W单位的PT报告补足。历史收据保留，不改写成新证据。

## 固定执行源码的复现命令

所有正式重现必须检出执行源码97b3542，不以未来README/证据提交的HEAD替代。实际服务器副本由旧固件副本 `clone --no-hardlinks --no-checkout` 后取得主仓增量bundle，子模块独立clone并取子bundle，核对两仓干净、固定HEAD与gitlink后才运行。主部署bundle SHA为 `ce1fa1cb5c12708b788a146d02844f6047737bbb862a62a05252807ecaeb53d6`。

交付的[子模块增量bundle](artifacts/xu-hw-e203-f49a5fc.bundle) SHA为 `e8fe26006aec48c11e91caf368d940723b176bafee17e3c3f7134e55feb64dd4`，可在该子提交尚未推送时离线恢复。它需要旧子提交e36d34a的前置对象，不能在空仓中直接使用；从旧E203克隆后再verify/fetch。本次服务器Desktop原始bundle和交付副本字节一致。以下在同服务器已有本次主仓的环境，从新目录重建可执行副本：

```bash
xu_source_repo=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ChipContest
xu_old_sub=/storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/ChipContest/third-party/e203_hbirdv2
xu_repro_repo=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-reproduce-01/ChipContest
xu_sub_bundle=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-e203-f49a5fc.bundle

git clone --no-hardlinks --no-checkout "$xu_source_repo" "$xu_repro_repo"
cd "$xu_repro_repo"
git checkout --detach 97b35421dfbbfa8f4d495b6927a7c66610ff8206
git clone --no-hardlinks --no-checkout "$xu_old_sub" third-party/e203_hbirdv2
cd third-party/e203_hbirdv2
git bundle verify "$xu_sub_bundle"
git fetch "$xu_sub_bundle" codex/xu-optimize-hw:refs/heads/codex/xu-optimize-hw
git checkout --detach f49a5fc914971426bd4530db39e270a84b41139f
cd "$xu_repro_repo"
git submodule init
git status --porcelain
git ls-tree HEAD third-party/e203_hbirdv2
```

上述主仓独立clone、旧E203加增量bundle恢复步骤已在本机新临时目录实测通过，214个运行源字节/集合和两仓干净性均一致；该检查只验证源码可恢复，不声称重跑服务器VCS。确认HEAD/gitlink正确且工作区干净；全部输出目录须尚不存在。若离线复制已初始化子模块，使用 `cp -a` 或 `copytree(..., symlinks=True)` 保留链接和独立仓库。使用与实际JSON相同的cross-prefix和参数，重新运行串行campaign并自动完成最终验收：

```bash
xu_hw_prefix=/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-
xu_hw_out=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-reproduce-01/xu-vcs-hw-campaign-01
cd "$xu_repro_repo"
/bin/python3 tools/scripts/xu_hw_experiments.py --sim vcs \
  --cross-prefix "$xu_hw_prefix" --out "$xu_hw_out" --accept
```

该driver按B0→H1→H2→组合串行执行各synthetic2和real12，先证明B0的历史逐层周期和加载镜像一致，再按严格总周期选择。最终调用的实参形态直接对应[原始experiments.json的acceptance.command与summary_command](server-json/experiments.json)；如只需单独复验选中配置，另用新的输出目录：

```bash
xu_hw_accept_out=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-reproduce-01/xu-vcs-accept-only-01
/bin/python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix "$xu_hw_prefix" --out "$xu_hw_accept_out" \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks
/bin/python3 tools/scripts/xu_perf_report.py \
  --result "$xu_hw_accept_out/real12/result.json" --frequency-mhz 150 \
  --out "$xu_hw_accept_out/xu-performance.json"
```

本地Chisel复现命令为 `scala-cli test . --server=false`，生成缓存包装为 `scala-cli run . --server=false -M GenerateRTL -- LinearCachedCore`；项目固定Scala2.13.18、Chisel7.16.0/插件和ScalaTest3.2.20。完整本地筛选及证据复核命令见[本地摘要](local-screening-summary.md)。补充接口包解压后按其README运行 `run.py --repo ... --sim vcs --out ...`，会先校验13份RTL SHA；使用本次服务器安装的VCS。

本次同库综合/STA的完整新输出复现流程、源恢复、Library Compiler环境和实际DC/PT命令见[PPA复现](ppa-reproduction.md)。[复现归档](artifacts/xu-ppa-reproducibility.tar.xz)SHA为 `784ca438ee2c381e67755191a76b3d487ff51c81b6b43312bc0c72bae614743b`，含104份原始脚本/约束/报告/失败记录及严格清单；工艺库、厂家模型和工具手册全文不随仓库发布。

## 日志哈希与证据边界

原始性能/验收全文日志留在服务器输出根的各实验及acceptance子目录；最终原文为 `acceptance/real12/simulation.log`。FTP拒绝RETR后，经已授权VNC可见颜色网格传送原始文件字节，逐页CRC与整体SHA核验。原始JSON和host/numeric及补充接口小日志是字节副本；传输manifest、PASS行摘录、观察收据和派生比较必须按其证据类型理解。

完整原始日志的失败标记扫描由固定身份runner/driver在服务器执行。摘录只能证明提取行，不独立证明其它区域无失败；server-verification对取回的JSON/摘录/原始小日志与源身份、SHA做复核，不将摘录伪称完整日志。源码、源端收据与实际部署身份一起构成证据链。

| 原始文件 / 产物 | SHA256 |
| --- | --- |
| `experiments.json` | `efd768271e1916de73fecac7469fca77eca0855b55648f5ac5c65eada3541aac` |
| `acceptance/acceptance.json` | `037f66ab147db8028823da71cbd882cc11e0b5ad5cdbd03d16e737766bdfc416` |
| `acceptance/real12/result.json` | `a5acfdeb0e1d11baf6245a481302fa26a589a90c98e673b19a3440dee886131c` |
| `acceptance/xu-performance.json` | `0742690df78ef43343975b8450d5a16b5ff86599e4123c2fbdf0dde7d5f64e82` |
| `B0-new-RTL-real12/simulation.log` | `d56d6a6fe41fd97a61c61bc9997ea68fdf34394592dd5a8af91bad79789154b5` |
| `H1-bias-cache-real12/simulation.log` | `2c25a9ecec73c2261df11d978929450fe90d8ef35bfb0c6e2c889b8822126243` |
| `H2-result-window-real12/simulation.log` | `e45f38982ee91949a963dc9b88f5055d58bde3e85df331d1532351b5cc00d202` |
| `H1H2-combined-real12/simulation.log` | `24932d70968353ef5356b7e6fa702ccf905e95c9a47b8b0e178739584bb90216` |
| `acceptance/real12/simulation.log` | `c7c36af0a716dfd90c542d9051efaafa553e4048dabae5f77cf8f5d143d840cd` |
| `最终固件ELF` | `3ebce7dfe768ae98556500d408e3a564ebb590a31ddf48f49bd164741d0b0395` |
| `最终固件加载image` | `6e22a1bffbd74c5cfc9b6d8603ce71a9f413ec5d2aea5df8bf792b922461e4e1` |
| `固定真实向量archive` | `ab9fe42d42324cabdd5912d7b2a2bee1c0fa8b9a55d5ca217da21a57f07c57f4` |
| `paired-exact-summary.json` | `3c20a1b677bc88ffa772f9a18734aacd35847dde60f6bfdccf31fd9764b53ed9` |
| `area-compliance.json` | `8df6f900caf17e522ee4342295480bd605a62a0c1049b4a4ed5ba2414330cf3c` |
| `hw-final-artifacts-01.tar.xz` | `936201546c84ca002e97f139f8c9b946ae897a7adb47d300ee9c5f4c7c91b7cd` |
| `power-exact-state.json` | `9418210a2a834d795d0877d8157106b3b7f638f71e819e10ee6799ff4364b6ed` |
| `baseline/power-exact.rpt` | `72fc05d08cd584e8f7aa5343190ee40989adeed75c73e77fd5494589482c8295` |
| `candidate/power-exact.rpt` | `048ad016adf4369d813216d453b710019fea0875dd4c6c75ad3110bf621d7470` |

全部构建/版本/仿真日志SHA见各原始result的 `log_sha256` 和[experiments.json](server-json/experiments.json)；下列关键运行源SHA来自同一冻结源清单：

| 源文件 | SHA256 |
| --- | --- |
| `src/main/scala/linear/BiasBankCache.scala` | `9ab99e1ea8e7ac04c40cae7af937ea11d42da75d5943a4ade7287a3beda53477` |
| `src/main/scala/linear/LinearCachedCore.scala` | `b34f2dbe5aff890df16b62307e8ccca8234d0604ccc1c9d7c74ef02093f9eb8f` |
| `tests/e203/firmware/accel.c` | `080262f875884ca31bcc179895604252aaef527b76f491199d562d3c879bee2e` |
| `tests/e203/tb_accel_soc.sv` | `bba0248513ca2dfe67be907306417bf6eb2c34d45603a7c55a33b5a062d2fc44` |
| `third-party/e203_hbirdv2/rtl/e203/perips/accel_icb_slave.v` | `7ad5eb72b46629ca70c97e0efcab03d8772de41c911ee16612ee46c74c6c2d21` |
| `tools/scripts/e203_soc.py` | `18628dd4a7ec0896d735ba54405434adfe81b7aabfb14295df96439aee50f3d4` |
| `tools/scripts/xu_hw_experiments.py` | `7f3e43d0876edd4610c5340341f16655fb1f37ad268aa189562f65e359e6d21c` |

[全部冻结运行源身份](evidence-tools/runtime-source-97b3542.json)包含Chisel、生成/安装RTL、TB、固件、脚本、数值模型和向量哈希；原始environment另记录编译器、objcopy、VCS、Git与make可执行文件SHA。SiFive GCC可执行文件SHA仍为 `1094274e53a2732173d4c765c9c0739a9d21fce999eca291ec4a340d47969369`。

本地归档见[三包SHA清单](local-artifacts/archives-sha256.json)：原7run全部JSON/日志/firmware.dump/ELF/image/SU包、Chisel逐测试原始日志包及补充接口包，均有严格内层SHA256SUMS。取回服务器原始JSON、小日志、传输manifest/派生摘录、PPA精确报告和本地证据分别保留，不能混合各自覆盖范围。

服务器[原始JSON/小日志包](artifacts/hw-results-01.tar.xz)SHA为 `dde3b57a8a440d4140909ec6696d6b2f5d863cd40143025f4390663e8970538b`；[源端派生收据](observed-receipt.json)SHA为 `7a82e72824312a81cf3f92375e2d049cb093e992a5f7ed38ca7b73040e46e72c`。wrapper全文日志补包保留独立补充manifest，未修改原始传输manifest；全部交付文件的最终清单见[evidence-sha256.json](evidence-sha256.json)，[交付核验汇总](delivery-verification.json)分别记录功能/性能、面积限额和功耗的结论。

本轮未实施DMA、X/W地址自增、硬件外层调度或PE扩展；尚不能据此给出完整SoC面积/功耗、布局布线时序收敛、CPU-only加速比或官方样本集精度。可见传输逐页重解码、CRC及最终字节核验见[transfer-verification.json](transfer-verification.json)：7份完整文件、84帧全部PASS。
