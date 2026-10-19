# ChipContest 主仓库审计与融合接口

审计日期：2026-10-17，Asia/Shanghai。只读对象：`ChipContest/`，提交 `30e737ca37bc7d3077db1877ee89072ac4dfc723`；审计开始时工作树干净。本文记录源码审查，不将静态推断写成已运行的测试结论。完整回归、E203 与器件库来源核验由本轮集成运行报告另行记录。原队友仓库不作原地修改。

## 读到的工程结构

已完整阅读 `quickstart.md`、`README.md`、`project.scala`、全部 11 个主 Scala 源文件、8 个测试源文件、`tools/scripts/area_eval.sh` 和两份基线综合日志的命令/输入/结束统计。

- `project.scala:2,10–12` 固定 Scala 2.13.18、Chisel/plugin 7.16.0、ScalaTest 3.2.20；第 3–9 行排除第三方、资源、生成文件和运行产物。
- `src/main/scala/GenerateRTL.scala:9–15,29–35` 提供六个顶层的 CIRCT 生成入口；输出在 `generated/<Top>/`。当前 Git 不携带生成 RTL，因此需要先生成再综合。
- `dotproduct/` 中 `MacPE` 执行精确 signed16×signed16 加 signed48 累加；`MacController` 为 IDLE→INIT→64 次 RUN→CAPTURE→DONE；`DotProductEngine` 提前一拍请求权重。
- `linear/LinearComputeCore.scala` 整合当前行 X、8 个权重 bank 和点积；`LinearLayerEngine.scala` 遍历 99 行、32 个组，每次输出 8 个 signed48 数。
- `memory/WeightBank.scala` 将一个 2048×16 权重 bank 拆成两块 1024×16；8 个 bank 合计 16 块行为存储。`XRowBuffer` 是 64×16 寄存器异步读。bias 不是内部存储，由外部每组提供 8×40 位。
- `third-party/e203_hbirdv2/` 作为子模块固定独立提交。quickstart 中提交 E203 后再更新主仓库 gitlink 的顺序正确；其中 `accel_icb_slave.v` 是举例，不能据此认定仓库已经实现加速器集成。

## 需要处理的问题

| 优先级 | 发现与影响 | 确切依据 | 建议 |
|---|---|---|---|
| P1 | `WeightBankArrayTest` 从写操作切换到读操作时未清写使能，产生非法同拍读写；全回归预期触发断言。 | `src/test/scala/memory/WeightBankArrayTest.scala:12–25` 最后保持 `loadWen=true` 后直接 `ren=true`；`src/main/scala/memory/WeightBank.scala:42` 明确禁止 `ren && wen`。 | 在独立修复副本中初始化全部输入，并在读前 `loadWen=false`。先保留原始失败日志，再跑修复后全回归；不能删除断言或忽略失败用例。 |
| P1 | 冻结的 `LinearComputeCore` 面积日志不是当前存储实现的证据。 | `reports/baseline/LinearComputeCore_nangate45.log:58–62,74` 读取/实例化旧 `mem_2048x16.sv`；当前 `src/main/scala/memory/WeightBank.scala:39–40` 实例化 `Sram1024x16` 两次。日志未绑定 Scala/生成 RTL/Liberty SHA。 | 重新生成固定当前提交的 RTL，在独立运行目录保存源码、RTL、工具、Liberty 哈希及完整命令。旧基线保留为历史数据。 |
| P1 | 原面积入口会把 SRAM 行为数组展开成标准单元；没有目标时钟、STA、功耗或完整新增接口预算。 | `tools/scripts/area_eval.sh:42–52` 执行普通 `synth -flatten`、`dfflibmap`、`abc`、`stat`，无 SRAM techmap、SDC、时序/功耗入口；旧完整核日志 `17940–17948` 为 0 memories、263,958 个 DFF_X1。 | 先保留存储边界做逻辑核心的同库代理对照；最终用指定宏映射，并将宏面积另计。150 MHz 必须实际 STA；面积与功耗使用同一冻结网表及完整任务窗口。 |
| P1 | 当前资源不能证实“已取得官方器件”。 | `README.md:97,131–140` 明确采用 Nangate45，并说明 SRAM 仍为行为模型；`assets/libs/` 仅找到 Nangate TT Liberty；`Sram1024x16.scala:18–31` 说明行为模型且使用 SyncReadMem。 | Nangate 只作为公开参考工艺的代理比较。继续等待组委会明确指定的标准单元/SRAM材料，不将行为模型或文件名当作工艺宏、官方面积或功耗。 |
| P2 | quickstart 的 Legacy 段不能按顺序直接复制执行。 | `quickstart.md:74–100` 使用 `third_party` 和 `~./ChipContest/...`，与实际 `third-party` 不同；`~.` 不等于用户 home。第 151 行 `cd ./third-party` 又依赖未说明的当前目录。 | 新集成入口使用明确的项目绝对路径或基于脚本目录定位。保留 Legacy 历史说明，将可运行入口集中到单一脚本。 |
| P2 | quickstart 未提供 README 所需的 JDK、Scala CLI、Chisel 仿真后端、Yosys 的版本化安装/探测入口；SDK 下载无固定提交，Ubuntu 裸机 GCC 与 SDK/newlib 的完整兼容性未验证。 | `README.md:91–100,105` 要求 Scala CLI 测试；quickstart 从仿真工具直接进入 E203/GCC/SDK，第 153 行裸 clone，无 pin/哈希。 | 固定实际工具与 SDK 版本，验证 `-march/-mabi`、multilib/newlib、链接脚本和 ELF/Verilog 格式，再称工具链可复现。 |
| P2 | SRAM 固定 1 拍、无停顿假设只适用于当前行为模型；更换宏不能只换模块名。 | `LinearComputeCore.scala:99–103,144–150` 忽略 `rvalid`，依赖提前一拍预取；`Sram1024x16.scala:33–43` 定义当前单拍有效协议。 | 真实宏需核对时钟沿、使能极性、读延迟、输出保持/未知语义和单端口排他；必要时引入 valid 流水或修改调度并重跑边界测试。 |
| P2 | 完整矩阵测试包名为 `lineear`，会让按 `linear.*` 选择测试遗漏该用例。 | `src/test/scala/linear/LinearLayerFullTest.scala:1`。 | 修复副本统一为 `linear`，回归报告列出完整 11 个测试用例身份及最终统计，不能只依据某个 `[PASS]`。 |
| P3 | 面积脚本第一行空白，shebang 位于第二行，不是有效的 execve 文件头。 | `tools/scripts/area_eval.sh:1–2`，Git 文件模式为 100755。 | 通过 `bash tools/scripts/area_eval.sh ...` 运行或在修复副本将 shebang 移到首字节；部分 shell 的自动回退不构成跨工具可靠入口。 |

上述 P1 测试问题属于源码可确定的非法激励；是否已触发、具体 Chisel/后端退出行为以本轮实际原始运行日志为准。不能把“预期失败”写作已执行 FAIL。

## 测试是否真实核对计算

当前 8 个测试文件含 11 个 ScalaTest `it`。`LinearLayerFullTest.scala:17–38` 独立以 BigInt 计算期望，`129–147` 逐项比较并确认 25,344 个输出；输入由测试台装载，DUT 自行做乘累加。未发现用测试台预计算答案直接替代 DUT 输出的代码。这是有价值的全形状功能测试，并非只有打印 PASS。

覆盖仍有明显边界：全矩阵使用很小的确定整数，只有一层任务；没有真实 KWT 12 层向量、浮点量化尺度、逐层 NRMSE、signed16/40 极值与符号扩展全集检查、计算中复位、长回压/稳定性检查、连续换参及任务缓存失效验证。现有 ChiselSim 通常由框架执行初始复位，这不等价于中途复位验证。README 对“完整矩阵通过不等于实际 SoC 搬运”的限定是正确的。

`LinearLayerEngine` 的输入接口信任上层：没有统计 X/W/bias 装载完整性，`rowLoaded` 是外部承诺；写接口被直接送入核心（第 63–71 行）。MMIO 封装需要防止忙时写权重、错误的 rowLoaded、未完成装载即启动，并提供可轮询状态/错误。当前 `done` 是单拍（第 86、135–138 行），软件接口必须保存完成状态；输出握手只证明接收器接收，不证明最后的系统内存写事务已确认。

## 与当前优化工程的差别

| 项目 | ChipContest 30e737c | 当前工程已有候选 | 融合约束 |
|---|---|---|---|
| 数值 | X/W16、bias40、累加/输出48；不含浮点编码与尺度 | `fixed16_acc48_v1` 明确 RNE、饱和输入转换、逐层尺度及精确 MAC；rowpair 内部41位精确、外部48位 | 整数核可对同一批编码值逐位比较；不得忽略 signed、bias 对齐或尺度说明。 |
| MAC/流水 | 1 行×8 列，组合乘法后累加 | 8/16 路、可选乘积流水；双行×8 列权重复用、双结果 buffer | 先保留 Chisel 原结构为交叉参考，再接入性能候选；只有指定库时序才能决定是否保留流水。 |
| X | 只存当前行64×16，异步读寄存器；逐行外部装载 | 完整99×64同步存储；rowpair按行奇偶分bank | 不能原样替换；必须选择一致的任务装载/行调度契约。单行缓冲节省内部存储，但系统搬运/CPU开销需实测。 |
| W | bank=`c%8`，bank内地址=`(c/8)*64+k`，16块1024×16行为存储 | 公开 load 接口始终 row-major `k*256+c`；banked/rowpair 内部地址为 `k*32+c/8` | 两边 bank 文件不能直接复制。用逻辑张量或显式转换器重排，并验证首末地址及group15/16边界。 |
| bias | 8×40 每组由外部直接提供，无内部完整256项缓存 | 256×40整层装载、bank存储、首项读取保持 | 接 Chisel 核必须增加 bias 缓存/预取，计入面积、装载周期及活动。 |
| 输出 | 8×48向量整组ready/valid | 单48位流，`out_index`/`out_last`，支持任意回压和有序写回 | 需串行器/结果寄存，或选择统一单字流；只有最终系统写确认后可报告任务完成。 |
| 验证 | 11 个模块/合成全矩阵用例，含一个非法激励问题 | 12层真实参数位一致、完整validation软件精度、回压/极值/复位/结构证据 | 共用固定向量及 scoreboard，保留各自原始失败/成功报告；不转移旧 PASS。 |
| 工艺/SoC | E203 fork/参考Nangate有价值，但主核未含CPU集成；SRAM行为模型 | 核心优化与证据工具较完整，尚缺正式平台/库验收 | 从队友平台复用真实版本/地址图；新增适配器与驱动，正式库未到位前仅作代理比较。 |

旧历史日志的 DotProductEngine 标准单元面积数为 22,889.832，LinearComputeCore 为 2,159,601.598019（日志末尾）。这两个数来自旧生成RTL及 Nangate 代理流程，不能与当前 rowpair 的保留RAM单元数换算比较，不能认定新增面积小于2.25 mm²。单元/DFF主导的历史面积说明首先应解决真实宏映射，再讨论增加 MAC 或进一步缩减算术位宽。

## 建议执行顺序与交接

1. 固定主仓库 SHA、子模块 SHA、工具版本、当前资源哈希；原样运行11项Scala回归和quickstart的E203默认ADD测试，保留失败。对 SDK Hello World 单独记录工具链缺项，不能以默认ADD代替自己编译的软件。
2. 在独立集成副本应用最小测试修复；生成 `LinearLayerEngine` RTL，全11项重跑并增加同当前工程的12层真实向量逐位回放。先验证不改变计算语义的融合入口。
3. 将 E203 的实际 ICB/NICE 端口、空闲地址段和总线时序固定为接口契约；引擎适配层统一逻辑 X/W/bias 装载、结果读取、busy/error/sticky done，以及32位总线对40/48位数据的拆包。不能因为名字相似复用旧FPT接口。
4. 主核保留 Chisel参考和 current banked/rowpair 候选，用同输入、同库、同SRAM边界进行代理综合比较；用同一外部接口接入CPU，避免两边各保留一套计算控制器互相重叠。
5. 组委会器件到位后替换真实宏，核对物理容量、单/双端口语义和读延迟，补综合前后等价/仿真、150 MHz STA、核心+新增接口+宏面积和完整12任务功耗。以正式结果决定最终架构。

本文尚未证明原仓库回归、融合RTL或正式PPA通过；需要由本轮新运行证据闭环。审计文件不修改 `ChipContest/`、PROGRESS、DECISION 或既有任务状态。
