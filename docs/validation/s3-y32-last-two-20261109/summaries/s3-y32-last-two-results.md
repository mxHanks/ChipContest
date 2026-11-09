# S3-Y32 后续数据流最后两项：真实原型与验证

2026-11-09。用户指定继续“两行×八列／DMA＋41位内部累加”。两项均已推进到可运行RTL与数值/协议验证；**当前已测8PE开发版本最优仍为12层5,874,840拍**。41位完整SoC周期没有变化；两行方案只有模块/专用搬运fixture测量，未接入CPU/MMIO，不更新整任务最优纪录。

基线父仓`e984bad936855debfc5fa01f04bcbc6252d59ecc`、E203 `dba1b5f82395b762f126387a1840e6a843e3a01a`。新分支`codex/s3-y32-last-two`。独立acc41/rowpair/dma sandbox保存原始命令、源SHA、所有先导/失败及最终证据；既往封存材料未改写。

## 41位内部累加

通用MacPE、Array、Engine、ComputeCore、AutoGroupCore增加可选参数，**默认仍48位**。显式`LinearAutoGroupCore41`只将八个ACC缩到41，乘法保持16×16，resultReg和FIFO、公开结果仍48位；41位通过符号扩展输出。固定64项DotProductEngine拒绝40位配置；通用MacPE允许40仅用于明确反例，不把64项界扩张为任意长累加。

对所有signed16×signed16输入，单乘积界为[−1,073,709,056,1,073,741,824]；signed40 bias为[−549,755,813,888,549,755,813,887]。任意n∈[0,64]前缀界按bias+n个独立乘积归纳，最宽为 **[−618,473,193,472,618,475,290,623]**，落在signed41内。40位不够：最大bias＋1一步即溢出。65个前缀界是完整域整数证明；真实生成的48/41/40 RTL另做36类场景、3345次边沿检查，包括极端、混合符号、ties、396停顿、4reset和INIT优先级。默认48还测600项连续累加；既有READY真实MAC/背压/错误/旧POP/复位回归通过。

同条件fresh-process CPU/RTL先单层，再重新编译完整12层，**304,128输出逐位一致**。171个测量源仅MacPE.sv变化，全部任务记录逐字段与基线相同：

| 指标 | 默认48位 | 可选41位 |
|---|---:|---:|
| 每层payload | 422,768 | 422,768 |
| 每层真实clear | 66,802 | 66,802 |
| 每层主口径和 | 489,570 | 489,570 |
| full12主口径和 | 5,874,840 | 5,874,840 |
| full12输出 | 304,128 | 304,128 |

gap每层102另列，首请求等待1已计入payload。MAC、NICE、总线事务、阶段、stall、READY等待和绝对窗口均相同。独立严格单层/完整12对12、两轮各20损坏证据负例通过；另验证3个逐层保护负例。保留源码/ELF/image/生成C/TB/工具/时钟/复位/clear/原始数值marker等完整检查，不允许跨层差异相消。

八个ACC原始寄存位 **384→328，省56bit**。没有综合，不能据此宣称标准单元面积、频率或功耗改善。作为显式可选特化交付，默认生产installed RTL保持48位。

## 两行×八列真实核心

新增独立`LinearRowPairPrototype`：两个8PE引擎共享唯一八bank WeightBankArray和BiasSramPrefetch，两个64×INT16 X缓冲；第二行额外128B X。两个pair槽共192B raw48结果，输出次序row0/group0、row1/group0、row0/group1…；没有整行1KiB Y缓存。99行尾部只计算和输出row0。完整束快照后才允许POP，head在背压下稳定，INIT边沿仍消费自己的bias tag。

对照“单行”是同一个原型的secondRow=0，**不是正式8PE SoC基线**。五种消费停顿×单/双行共10场景，每场景实际采集25,344个RTL raw48，与原speech task0 y.mem逐值/文件SHA一致。C++另从采样raw48做RNE核对y32.mem；此处C++转换不是RTL RNE证明，后述真实NICE组合单独验证RTL RNE。

| 每束额外消费停顿 | 单行active＋Xload | 双行active＋Xload | 模块降低 |
|---:|---:|---:|---:|
| 0 | 224,631 | 116,635 | 48.077% |
| 31 | 227,700 | 119,704 | 47.429% |
| 60 | 230,571 | 204,601 | 11.263% |
| 80 | 272,448 | 267,744 | 1.727% |
| 255 | 826,848 | 822,144 | 0.569% |

两侧Xload均6,336拍。此停顿是C++ sink控制变量，不是测量到的NICE平均服务。每case另有16,387拍模块真实clear和18,432拍W/bias公开口load，JSON另列含它们的完整模块窗口；该窗口不使用CPU、packed MMIO或真实总线服务，不能与SoC489,570拍比较。

W实际16bit宏读取 **1,622,016→819,200，减少49.495%**；bias宏读76,032→38,400。99行形成49个完整pair和1个尾行，32×50=1,600次launch；有用MAC总量仍25,344×64，尾部第二引擎不输出。消费变慢时，FIFO满等待上升并掩盖大部分计算并行收益，读取减少不等于整任务加速。

每场景另验证512合法端点、三类reset和恢复、尾行及真实clear。test-only只读bind直接观察17个SRAM宏RW0端口，逐物理地址验证每次W16,384/Bias768零写与两X端口128零写；dirty前态由公开口逐址写非零。只读检查X128、ACC16、engine result16、FIFO32寄存器的非零前态及clearDone全零。没有force、deposit、层次写或FIFO预置。模块clear观察不升级正式clear政策或旧SoC FIFO物理清零状态。实际输出翻bit、源SHA篡改、clear marker丢失的3负例均拒绝。

## 跨行专用NICE搬运与DMA边界

实验独立funct7=0x25，`PAIR_ENABLE`默认关闭。沿现有256bit快照和32bit串行LSU，按列组交错搬两行，第二目的地址固定＋1024字节；尾行禁止第二路。新descriptor包含group、count、second_row和每束READY预算。status bit30标识pair route、bit11标识row身份；旧0x20/23/24遇pair route在任何snapshot/POP/Y写前拒绝，0x25遇旧wrapper或禁用参数也零副作用拒绝。每束完整snapshot后下一拍POP，每写等响应，末响应退休后completion；任何首次错误中止整指令，不重试部分写。

613项协议场景包括64种count/tail、512个写响应错误位置、live/captured错row和cap丢失、13复位及背压。31次native编译/运行覆盖旧READY/direct真实wrapper回归、合成极端/ties向量及实际speech task0，单/双行各25,344个Y32精确。实际NICE+8拍单RNE桥+双行MAC组合：snapshot/POP均3,168，Y写/响应均25,344；请求/完成由99降50。真实MAC写错误15和511停止在对应响应，没有后续搬运。

| 模拟sink命令周期／响应延迟 | 单行compute＋drain | 双行compute＋drain | 模块降低 |
|---|---:|---:|---:|
| 1／0，合成端点 | 221,760 | 119,840 | 45.960% |
| 1／3，合成端点 | 224,136 | 195,128 | 12.942% |
| 1／5，合成端点 | 250,272 | 245,568 | 1.880% |
| 3／2，speech task0 | 224,136 | 195,130 | 12.941% |

这是Icarus模块fixture的计算启动到最后写响应窗口，**不含CPU指令退休、X/W/bias加载、清零或真实fabric**，不能替代SoC收益。正式CPU/MMIO wrapper、固件cap/指令调用和同条件全任务测量仍未实现，实验variant只放在experiments，不写回E203生产RTL。组合fixture本身没有执行模块clear；真实clear由上述核心probe另证，二者范围分开。

它是**专用跨行NICE搬运，不是独立DMA master**。E203现LSU固定AGU/NICE两请求方，NICE持有期间限制CPU数据请求；额外DMA master需要新的总线入口/仲裁、响应归属及未完成事务的错误/复位和内存可见性合同，超出本轮不改CPU/LSU/BIU/仲裁/在途的边界。代码与实测支持沿现有master继续研究；不能冒称新增DMA带宽或CPU并发。

## 集成、复现与交付

正式源码只增加默认不变的参数链、显式生成入口和独立rowpair class。全新source-only目录从最终合并Scala生成默认48/可选41/rowpair，分别12/12/11个SV与各自实测SHA全部匹配。正式installed171输入逐SHA与当前8PE基线相同，E203 gitlink保持dba1b5f。主工作区HEAD/status保持。

可运行入口均要求新输出目录，避免覆盖证据：

```sh
python3.12 -E -B experiments/s3-y32-last-two/acc41/run_acc41.py --repo "$PWD" --out /absolute/new-acc41-check
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearRowPairPrototype
python3.12 -E -B experiments/s3-y32-last-two/rowpair/run_rowpair.py --repo "$PWD" --vectors /absolute/task0-vectors --out /absolute/new-rowpair-check
python3.12 -E -B experiments/s3-y32-last-two/rowpair/verify_rowpair.py /absolute/new-rowpair-check
python3.12 -E -B experiments/s3-y32-last-two/paired-nice/run_probe.py --repo "$PWD" --generated-rowpair generated/LinearRowPairPrototype --vectors /absolute/task0-vectors --out /absolute/new-pair-check
```

向量目录包含x.mem/w.mem/bias.mem/y.mem/y32.mem，SHA见冻结来源；paired fixture使用ASCII路径且最多128字节，runner前置拒绝超长路径。可选41完整SoC复验必须在隔离副本中安装`generated/LinearAutoGroupCore41/MacPE.sv`，再按前轮原packed-clear/READY/150MHz/external-reset完整12层命令运行，不覆盖正式48位生产文件。

[计划](s3-y32-last-two-plan.md)、[实验说明](../experiments/s3-y32-last-two/README.md)、[紧凑证据](validation/s3-y32-last-two-20261109/README.md)及`build/last-two-20261109/handoff/README.md`记录原始来源、复验、提交/归档SHA与回退。回退在干净副本切父仓e984bad，E203无需切换。未综合、推送、PR、官方EDA或外发。

## 保留的限制和诊断

初版比较器只检查汇总相等，独立审查后增加逐层totals/window/clear相等；初稿和先导receipt标NOTFINAL。双行先导driver/observer更新前的证据按各自真实SHA保留，最终引用final-numeric；旧final因driver SHA变化而拒绝，不将该拒绝算最终PASS。源／raw输出／clear损坏负例和所有native失败原件保留。永久runner增加路径/冻结TB保护后在新目录重跑，未覆盖先前记录。

DEVELOPMENT_PASS_POLICY_PENDING、clear REVIEW_PENDING、旧SoC FIFO payload physical zero UNPROVEN不变。Verilator两态开发证据、Icarus行为SRAM与Chisel断言均不替代厂商宏、正式VCS/门级、STA、面积、能耗或比赛资格；150MHz仍只是前轮CPU TB刺激。本轮无PPA结论。
