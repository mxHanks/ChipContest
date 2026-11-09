# S3-Y32：内部就绪等待优化

日期2026-11-09。用户要求继续上一轮goal；[计划](s3-y32-ready-plan.md)以已封存的8PE stream＋bias pipeline为基线，独立测试删除每组ROW_STATUS总线查询。新方案单层payload429,697→425,539；相同真实clear198,403后628,100→623,942，净省4,158拍／**0.6619965%**。这包含新指令前后同步开销，不能用查询次数乘延迟推算收益。

最终集成12层全部通过，共304,128输出。全12含clear为7,487,304拍，较上一版再减少0.6619965%。本轮不综合，不给面积／时序／能耗收益结论。

## 基线与唯一设计变化

父基线`d6bea15b641cbe9b29c440f261636ab50a934ca2`、E203`5907a769c76e0e938a9deb7d85143d9a66cf4bc1`。原完整12层每层429,697＋198,403，gap102；合计7,537,200。最终源保持原8PE、INT16、signed48累加与Y32 RNE、1024×16 bias SRAM、256bit direct payload、8lane snapshot和32bit共享总线。CPU／LSU／BIU／仲裁／在途配置、数值模型、输入／golden和真实clear配方不变。

当前逐字写回状态机已经在前响应退休边沿直接转SEND_WRITE，下一拍即准备下一写，没有可删除的NEXT空拍。响应与下一命令同边沿交换会新增组合控制路径，本轮不实现。选择优化每层仍有的4,752次状态总线读。

新独立`custom3/funct3=7/funct7=0x24`沿用0x23的32B对齐目的、group[4:0]、count_minus1[9:5]和22bit limit[31:10]；count为同一行1..32组，完整地址span仍在Y范围。旧0x20／0x23的编码、错误及退休poll响应预算均保留。

已有xu_direct_status线路在claim低时提供真实row状态，bit31仅在DIRECT_ENABLE且direct_enabled时宣告新的live协议；claim高仍输出原锁存bundle metadata。无新增CPU／总线端口。0x24接受及每次READY_WAIT都检查live-cap，旧wrapper或cap丢失返回1。

READY_WAIT不claim FIFO、不读LSU、不POP。valid0持续等预算，即使STARTROW尚未反映为active，避免启动延迟误判；valid1才查active和group，错误7／6。limit是每组READY_WAIT驻留edge预算，ready在最后允许edge优先于timeout5，每组重装。就绪后仍先snapshot8、下一edge commit POP、串行8个写各等响应；组尾末响应后才转下一组，最后末响应后才completion。首次错误终止全指令／任务，已POP／部分写不能retry。

新增原始控制寄存仅1bit ready_mode；state仍4bit、复用既有27bit计数器。wrapper新增live状态组合选择，无新存储器。此处是源级结构计数，不代表映射面积／STA／功耗结论。

## 启动排序修正与固件兼容

首轮`ready-task0`被新加入的STARTROW响应退休检查拦下，未算PASS。新指令不经首次LSU状态查询，不能继续依赖旧轮询的串行化作用。仅在XU_NICE_READY分支的custom之前新增`fence iorw,iorw`；原custom之后的fence、memory clobber和非零返回立即失败均保留。E203现有disp fence路径要求OITF empty，未修改CPU控制。检查保持“真实STARTROW响应先退休，随后接受NICE”，没有放宽观察边界。

`XU_NICE_READY`要求DRAINN／DIRECT／DRAIN8。真实ELF解析确认唯一0x24、非x0返回寄存器以及紧邻前后fence。最新C在宏关闭／显式0时与冻结旧stream的实际加载binary和Verilog image逐字一致；三种缺少依赖宏编译拒绝。初次宏对照误要求含随机GCC临时.o名称的整个ELF字节一致，失败原件保留；正式校验针对实际加载段，同时独立核验ELF→image，未删实际代码检查。

## 单层实测

同条件Verilator5.032二态开发、`--assert`保留Chisel断言、150MHz／32.768kHz外部刺激、external-pad-double-reset、RV GCC14.2、fresh process及真实物理清空。150MHz只表示测试台刺激。

| 指标 | 已封存stream＋bias | READY＋前fence |
|---|---:|---:|
| payload | 429,697 | 425,539 |
| true clear | 198,403 | 198,403 |
| payload＋clear | 628,100 | 623,942 |
| clear后首请求gap | 102 | 102 |
| 请求／响应／OITF | 99 | 99 |
| snapshot／POP | 3,168 | 3,168 |
| Y32写／逐位输出 | 25,344 | 25,344 |
| NICE状态查询 | 4,752 | 0 |
| MMIO读总数 | 4,754 | 2 |
| READY_WAIT驻留edge | — | 23,859 |
| 有效就绪事件 | — | 3,168 |

两次其他MMIO读仍保留，被删除的是ROW_STATUS查询。零poll没有消除计算等待，内部等待占23,859个edge。阶段计数可能重分类，不能把compute_wait下降单独当收益。

最终单层phase为W114,713／X71,280／bias10,760／compute_wait9,603／writeback196,713／other22,470，总和425,539。starts／dones3,168、MAC有效202,752与原8PE相同；source_drift为空。

独立严格比较先核验原baseline全12层再显式project原层0，与单层候选比较。精确170源SHA、8项reviewed sourcepairs（accel.h只可注释差异）、两侧ELF加载段及image、命令／工具／时钟／外部复位、输入／golden、clear C与完整请求至末响应窗口均验证。单层证据没有冒充full12。

## 最终集成12层

最终主树源码的新编译／新进程回归完整通过12层，304,128个输出逐位一致，source_drift为空；每层相同clear198,403和gap102，全部READY_TASK与LSU／OITF／末响应检查保留。

| 原层 | payload | true clear | payload＋clear | 状态查询 | 输出 |
|---|---:|---:|---:|---:|---|
| 0 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 1 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 2 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 3 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 4 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 5 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 6 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 7 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 8 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 9 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 10 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| 11 | 425,539 | 198,403 | 623,942 | 0 | PASS |
| **合计** | **5,106,468** | **2,380,836** | **7,487,304** | **0** | **304,128／304,128** |

相对已封存stream＋bias的7,537,200，净减 **49,896拍／0.6619965%**，payload减少0.9676586%。clear后首请求gap仍合计1,224拍，按原口径另列；计入gap也净省49,896拍。由上一轮同口径原8PE direct的7,819,944计算，累计净减332,640拍／**4.2537389%**。

最终独立严格12层对12层比较通过，16项损坏证据负例全按预期拒绝；170个测量输入与修正单层、最终集成及full12 snapshot逐SHA匹配。两边实际ELF→image分别核验，新增4B前fence及0x24是明确审查过的固件变化；同步成本已经在payload中。最终比较与负例收据随紧凑Git证据保存。

## 交付和回退

E203本地提交`0f852a35741881400a7e10b4760bdb8f300245ae`只改变NICE和accelerator wrapper两个RTL文件；父仓gitlink同时锁定配套固件／契约。父仓最终提交、两份增量Git bundle、便携归档SHA、搬迁后校验和回退命令见`build/ready-20261109/handoff/README.md`。

[紧凑Git证据](validation/s3-y32-ready-20261109/README.md)保存原始plan/result/clear recipe／任务日志、源码pins／pairs、比较器／负例、限定回归和失败诊断；大包保存完整source／vectors／ELF／加载image／soc_sim／构建命令。保留原未加前fence的FAIL，后续通过不覆盖失败原件。原始postflow交付未改写，新分支`codex/s3-y32-ready`可独立回退到本轮前的父`d6bea15`／E203`5907a76`。

复现完整同条件回归：

```sh
python3.12 -E -B tools/ppa/s3_task_campaign.py \
  --repo "$PWD" --out /absolute/path/to/new-ready-campaign \
  --bias-kind sram \
  --schedule bias-hw-autogroup-y32-packed16-nice-direct-stream-ready-window \
  --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset \
  --layers 0,1,2,3,4,5,6,7,8,9,10,11
```

本轮全程未综合、未推送、未改主工作区；新指令需要匹配的live-cap wrapper/NICE/固件，旧0x20/0x23保留。正式资格与PPA仍待团队验收。

## 限定验证

- 新418单元场景覆盖全部count、全部32组的错误／超时、32×8写错误、8次cap丢失、12复位及预算边界／重装；NICE和wrapper编译时禁用检查通过。
- 真实MAC wrapper32组／256lane、独立RNE数值端点／正负ties、背压、末响应、3复位通过。旧MMIO POP响应滞留时，claim等待其退休后重新检查新metadata，错组返回6，零direct POP／Y写。
- 旧0x23 stream118场景及真实MAC／3复位、旧0x20 direct19场景及真实MAC／3复位、read-pop61场景及真实别名／ABI通过。
- 主树19项固件契约与15项campaign检查通过；独立RTL与observer／固件审查无阻断问题。
- 独立比较器16项真实证据损坏负例通过：source/hash／白名单／漏pair、ELF-image、READY缺失／重复／非零poll、数值覆盖、selector、clear C、tensor、partial禁止冒充full12、header声明变动和旧stream零poll拒绝。

旧首次未加前fence的SoC失败、宏对照初次非加载ELF差异、负例工具临时目录跨文件系统硬链接／错误字符串诊断均保留，不算PASS，不修改原仿真工件。正式VCS／门级、STA、面积、能耗及清空政策资格仍待团队验收；原policy REVIEW_PENDING、FIFO payload physical zero UNPROVEN原义不变。
