# xu S3 独立64列并行候选

基点为冻结32PE主 `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114` / 子 `fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5`，主/子独立分支均为 `codex/xu-s3-pe64`。数值保持 signed16 X/W、signed40 bias、signed48结果和原99×64×256任务/向量；固定E203、互连、共享512KiB SRAM均保持。无服务器VCS、面积、时序、等价或能耗资格结论。

生产Chisel只改 `src/main/scala/GenerateRTL.scala` 的64生成器，并新增 `src/main/scala/linear/XuParallel64Core.scala`。原 `XuParallelCore.scala` 字节不变，复用其参数化 compute/bias/weight bank基础，新增独立64调度器。原32四个及旧13个生成SV、原wrapper保持字节不变；新增四个64 SV和 `xu_pe64_icb_slave.v`。平台只在原加速器插槽增添 `XU_ACCEL_PE64` 可选选择；默认和原32 define保持原实现。

W只有一套，64bank×256×16逻辑元素=32KiB。每bank仍用指定1024×16接口，两个高地址位接0，padding不可访问；64个W宏物理128KiB，padding96KiB。预期全SoC宏数384（固定320+W64），必须通过该候选真实映射确认。128深宏方案留作后续单独实验，不混入此配置。单X行缓冲、256×40逻辑bias与两槽64×48结果FIFO；不复制八套旧core，不提前装载下一任务。

旧W地址先还原column=(oldaddr>>6)*8+oldbank，再映射widebank=column%64、wideaddr=(column//64)*64+k，16384个旧地址与64×256位置双射。对同一套64lane硬件显式保留三种调度：

| 行接口 | 组数/行 | 每组实际enable lane数 | compute物理组/子块 |
|---|---:|---:|---|
| 旧8 ABI C0/C4/C8、100..13c结果 | 32 | 8 | group>>3 / group[2:0]×8 |
| 旧32 ABI D0/D4/D8、200..2fc结果 | 8 | 32 | group>>1 / group[0]×32 |
| 新64 ABI E0/E4/E8、400..5fc结果 | 4 | 64 | group / 全部64lane |

原32 CAP@07c=`58332001`保持，新64 CAP@0dc=`58364001`。旧ID/CAP、load、packed、cache、手工8group含义保持。START锁存row mode，active持续至最终POP响应退休；错误模式窗口/POP报错。FIFO head响应快照在背压时稳定，满FIFO不launch，POP不在请求接受时推进。手工8lane result selector在capture锁存，下一GROUP写不改变上次结果。

新固件schedule `bias-hw-pe64-autogroup-window` 与物理variant `--accel-variant pe64`独立。该schedule要求64；32schedule可在物理32或64上运行，旧8schedule可在8/32/64上运行。64wide每任务396 starts/dones、25344 MAC beats、12725 MMIO writes；输入/参数shared读23232、Y shared写50688、输出25344保持。所有模式真实enabled-lane MAC总数均1622016，由TB观察实际64个MacPE enable并popcount交叉核对；不能以mac_fire固定乘64掩盖冗余工作。

并行增大不会减少输入、W和Y的数量，主要可能减少启动/轮询/计算等待；共享写回和CPU搬运仍可能成为瓶颈。更宽X广播、bias读和FIFO/多路选择会增加面积与时序负担；只有同配置测量才能决定保留。

本地开发TB仍为4ns HF/66ns LF，计时首shared读接受至final-Y响应退休；它不替代正式clear/首valid REQUEST窗口及150MHz资格。实际本地direct/Chisel/host/完整layer0对照及源SHA另行冻结归档，不能按模块规模推算周期、面积或全SoC能耗。

```sh
scala-cli run . --server=false --jvm system -M GenerateRTL -- XuParallelAutoGroupCore64
scala-cli test . --server=false --jvm system --test-only linear.XuParallel64AutoGroupCoreTest
python3 -m unittest discover -s tests/e203 -p test_pe64_wrapper.py -v
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --accel-variant pe64 --firmware-schedule bias-hw-pe64-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-pe64-real1
```

同物理64对照分别改schedule为 `bias-hw-pe32-autogroup-window`、`bias-hw-autogroup-window`；物理32对照再将variant改为pe32。每次输出目录全新，所有比较使用同一工具链、数值格式/向量、等待模型与输出检查。服务器下一阶段使用实际VCS完整12层、同库全SoC映射和正式活动窗口。
