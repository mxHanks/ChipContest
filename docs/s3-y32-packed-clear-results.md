# S3-Y32：公共PACK32真实清零优化

2026-11-09。用户要求继续上一轮goal。本轮选择复用现有PACK32公共MMIO接口，减少任务前真实清零的CPU／总线调度。没有改变RTL或矩阵数值。正式单层实测clear198,403→66,802拍，payload425,539→425,540拍，合计623,942→492,342，净减131,600拍／**21.0917040%**。

这里的21.09%是**计入任务前真实清零**的开发测试口径收益；不是矩阵payload或MAC吞吐提升。payload源/硬件均不变，实测反而多1拍，已完整计入。官方clear计分政策仍REVIEW_PENDING，FIFO payload physical zero仍UNPROVEN，不因新结果提高资格状态。最终集成12层全部通过，总周期5,908,104，304,128输出逐位一致。

## 固定基线与范围

父基线`51a021c8bfc9649e2be4be1292735181f7a551e8`、E203`0f852a35741881400a7e10b4760bdb8f300245ae`；父分支`codex/s3-y32-packed-clear`。固定READY/stream/bias的8PE方案，原12层304,128输出、含clear总7,487,304拍。全部153个RTL文件、原scalar helper、payload main/accel.c/header、contract/parser、原payload TB、数值模型、向量与golden逐字保持。

探索不综合、不改CPU／LSU／BIU／仲裁／在途配置、不推送，主工作区和前轮封存证据未改写。原scalar默认仍保留，新增`--clear-profile packed16-mmio`显式选择。新profile快照由原170源加1个新helper组成，源差异只允许campaign.py和新增helper。

## 新配方与实际物理工作

所有操作仍走公共32bit MMIO，清空过程不读取任务X/W/bias源或参数旧值；HOST[0]只是单任务控制。先验证ID、旧cap、fresh STATUS、bias cap、STREAM_CAP和PACKED_CAP，共6读；未知cap拒绝，不猜测语义。

CACHE_CTRL=0，W_CURSOR=0后执行8192次W_PACK32=0；原bias SRAM clear768字＋两槽640bit路径和legacy8×40bit写零保持；X_CURSOR=0后32次X_PACK32=0。每个packed命令按现有硬件分两拍复用scalar端口，第二次实际写完成后才发布响应。结尾`fence iorw,iorw`，先读STREAM_STATUS=0检查sticky error／pending，再读STATUS=0作为最终clear proof；首source请求前所有clear／preflight响应、实际端口和NICE必须排空。

| 单层SRAM模式 | 原scalar | packed16-mmio |
|---|---:|---:|
| clear MMIO写 | 32,930 | 8,252 |
| clear MMIO读 | 5 | 8 |
| clear命令／响应 | 32,935 | 8,260 |
| W实际16bit写边沿 | 16,384 | 16,384 |
| X实际16bit写边沿 | 64 | 64 |
| bias SRAM实际16bit写 | 768 | 768 |
| legacy bias值／staging原始bit | 8／640 | 8／640 |

减少的是MMIO手续，物理工作没有减少。pack后的W cursor=16384／X cursor=64，旧legacy地址选择寄存器末值也可能不同；冻结payload在W/X上传之前明确cursor=0，不读取旧legacy pointer。pending／最终响应检查仍完整，不把“寄存器后态不全同”混作减少工作。

W逻辑位置p映射bank=p[2:0]、地址={p[7:3],p[13:8]}；偶数pair的两次写位于相邻bank同地址。宏half是地址bit10，即cursor[7]，并非按cursor8192分界。新observer逐edge检查真实core io、16个W SRAM宏RW0_en/wmode/addr/data、one-hot cardinality和全部唯一地址；X检查实际xBuffer写口；bias检查真实768宏写和staging后态。每次pack response退休要求对应两次实际写均完成，不能用命令数×2填coverage。

completion proof和首source VALID边沿均要求core／物理端口idle及所有位值为零。source检测不等ready，包含首次等待。原payload／LSU／OITF／NICE／数值／末响应断言原字节保持，仅替换专用preclear observer。

## 真实非零前态探针与错误验证

wrapper探针通过独立的scalar公共MMIO路径把全部W/X/bias/legacy写非零，逐16W宏和所有X／bias位置只读检查前态，禁止force或层次赋值。bias padding先经公共BIAS_CLEAR置已知值，再通过40bit ABI填有效位；padding高8bit无法经公开ABI填非零，不冒称有该前态。新clear仍对完整16bit零写，后态768word全16bit检查。

两槽bias staging经public manual group0/1真实取数填非零后再arm清零，16×40bit全部实际擦除；legacy8×40bit同样前后态检查。随后重新从6个ABI读执行完整新配方，验证零写边沿／唯一覆盖／末响应和后态。fresh process零初始化没有代替非零前态证明。

探针覆盖漏写、重复／错地址、非零高半、mask/cap错误、早proof／早source、响应背压、reset边界与错误原子性。另在隔离副本注入真实RTL故障：漏bank7零写、漏X0写、漏legacy高8bit写；实际边沿或非零后态检查均拒绝。生产RTL字节未变，mutant不计候选硬件。最终6个unittest方法完成（其中1个可选寄存bias变体显式skip）；22个真实wrapper模式含5个正例和17个拒绝，再加3个真实漏写fault mutant均符合预期。寄存bias选项未获本轮完整RTL／SoC验证，正式结果只来自SRAM模式。收据随证据目录保存。

## 同条件单层结果

Verilator5.032二态开发、`--assert`保留Chisel断言、150MHz／32.768kHz刺激、external-pad-double-reset、RV GCC14.2、fresh process、相同原层0／golden。150MHz只表示测试台时钟刺激。

| 指标 | READY＋scalar clear | READY＋PACK32 clear |
|---|---:|---:|
| payload | 425,539 | 425,540 |
| true clear | 198,403 | 66,802 |
| payload＋clear | 623,942 | 492,342 |
| clear至首source gap | 102 | 102 |
| 首source VALID等待 | 0 | 1 |
| Y32逐位输出 | 25,344 | 25,344 |
| NICE请求／snapshot/POP／Y写 | 99／3,168／25,344 | 相同 |
| ROW_STATUS查询 | 0 | 0 |

clear减少131,601拍／66.3301462%，payload多1拍，主指标净省131,600拍。新clear代码长度改变真实请求相位，首source等待从0变1，被原完整窗口纳入；没有padding调相位或减去等待。payload各阶段仅W load／shared stall相应多1，其余阶段相同；不能把清零收益包装成MAC速度提升。

先导`packed-task0`使用较早observer，结果一致但不冒充最终代码。正式`packed-final-task0`使用加入逐pack退休检查的最终helper SHA`fbd013b9b0c8de9f7c2d6e0c76cc8676aaabf6436b5835f2a8046072d589533d`，source_drift为空，171源精确匹配。所有原件分目录保留，不覆盖。

## 独立严格证据

比较器先完整核验固定READY baseline12层，再明确project原层0用于单层筛选。原170源除campaign外全固定；候选171源只允许新增packed helper。payload和硬件工作计数、输入／golden、编译／仿真工具、时钟／外部复位、窗口语义保持。实际phase/stall/READY_WAIT／payload时间差透明保留。

两份clear C分别用已pin旧／新helper和冻结main精确重生成，明确允许策略差异，没有删掉清空代码后假称相同；生成TB使用独立pin的旧instrument／clock／reset函数重生成，原payload observer全部保留。两侧ELF到实际ITCM image逐字核验；clear代码变化及payload地址重排明确记录。

旧scalar历史raw只记录逐地址MMIO，并未采样过新16宏edge；其物理工作由旧exact C／原observer／不变RTL和既有probe闭合。candidate新增直接core／宏边沿实测，报告不把新观测倒填到旧日志中。

正式单层13项真实保存证据损坏负例全部拒绝，包括改RTL／旧helper／tensor、漏循环C、额外nop、关闭原payload observer、削弱physical observer、加载image字节、漏macro marker、早proof、policy提升、错误时序和重复marker。最终完整12层严格比较与13项损坏证据负例均已通过。

## 最终集成完整12层

最终主树新编译、每层fresh process回归通过12层，**304,128输出逐位一致**，source_drift为空。全层相同实际clear工作、NICE／LSU／OITF／末Y响应检查，首source真实等待每层1拍，gap仍102拍。

| 原层 | payload | true clear | payload＋clear | 输出 |
|---|---:|---:|---:|---:|
| 0 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 1 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 2 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 3 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 4 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 5 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 6 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 7 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 8 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 9 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 10 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| 11 | 425,540 | 66,802 | 492,342 | 25,344／25,344 |
| **合计** | **5,106,480** | **801,624** | **5,908,104** | **304,128／304,128** |

与READY＋scalar clear的7,487,304相比，净减 **1,579,200拍／21.0917040%**。分开看，clear减少1,579,212拍，payload增加12拍。clear到首请求gap均1,224拍，沿原口径另列；若一起计入两侧总量，净减少仍1,579,200拍。

相对最初8PE direct同口径总7,819,944，本轮最终5,908,104累计减少24.4482569%；这包含多轮payload改进与本轮清零改进，仍不能称为MAC吞吐提升或官方分数提升。

最终严格12对12比较通过；两侧ELF／image、生成C／TB、工具／时钟／复位、输入／golden、完整工作量／窗口与政策字段均核验。13项损坏证据负例全部拒绝。新profile171源与正式单层、集成源码及完整12层快照逐SHA一致，全部153RTL及原helper／payload源码不变。

## 交付与回退

父仓实现／测试／报告和紧凑证据分别本地提交，gitlink仍锁定E203`0f852a35741881400a7e10b4760bdb8f300245ae`，本轮没有E203新提交。父最终提交、增量Git bundle、便携归档SHA、新路径核验及回退命令由`build/packed-clear-20261109/handoff/README.md`锁定。

[紧凑Git证据](validation/s3-y32-packed-clear-20261109/README.md)保留原plan/result/clear recipe／任务logs、工具与源pins／pairs、严格比较／负例、helper probes／故障注入及失败诊断；完整便携包保留source／vectors／ELF／image／soc_sim／构建命令。原先导及中间helper按各自真实SHA分类，不当作最终版本PASS。

复现最终同条件12层（默认scalar不变，必须显式选择新profile）：

```sh
python3.12 -E -B tools/ppa/s3_task_campaign.py \
  --repo "$PWD" --out /absolute/path/to/new-packed-clear-campaign \
  --bias-kind sram --clear-profile packed16-mmio \
  --schedule bias-hw-autogroup-y32-packed16-nice-direct-stream-ready-window \
  --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset \
  --layers 0,1,2,3,4,5,6,7,8,9,10,11
```

回退只需父仓回到`51a021c8bfc9649e2be4be1292735181f7a551e8`；E203原提交保持。主工作区和既有封存证据不改写，未综合／未推送。

## 保留失败与资格限制

初版fixture遗漏direct端口、Python预期PASS marker拼写等失败原log保留；修正fixture不改生产RTL或清零逻辑。最终helper增加逐pack退休检查后另目录重跑，旧helper的PASS只作先导，不能混作最终版本证明。

本轮未综合、未运行正式VCS／门级、STA、面积和能耗；SRAM行为模型不替代厂商宏。clear政策REVIEW_PENDING和FIFO payload physical zero UNPROVEN保留原义。交付只完成开发证据，正式是否计入clear及资格由团队验收。
