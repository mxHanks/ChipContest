# B41 门级接续观察记录

2026-11-12，官方 RDserver04、s4_23usr、工作区 3。本文为界面读取后整理的观察记录，原生日志和证明回执保留在官方服务器；没有将官方工程文件下载到本机。当前三份固件门级和功耗仍未通过。

官方根目录：`/tmp/xu-b41-close-20261111-r1`。下文路径均相对该目录。

## 版本与证据边界

- 物理候选：`xu-closure-20261112-r4/dc/mapped.v`，SHA256 `2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220`。本轮未修改该文件。
- 独立功能副本：`xu-gate-reset-20261112-r1/mapped-functional-reset-r1.v`，SHA256 `2d2a23089d62d7c3c27e98ef20fc156dc15df7a260927d106ba5490806523a0c`。它基于此前的功能仿真副本，对 14 个触发器 D 引脚增加复位屏蔽。
- 官方标准单元库的 Boolean BDD 证明：14 个 D 引脚在复位有效时恒为 0，其他状态与输入自由，312 个 BDD 节点。证明回执 `xu-gate-reset-20261112-r1/reset-proof.json`。此局部证明不等同于最终全设计 Formality 验收。
- 冻结 RTL、固件、向量、原 CPU 检查器、物理观察器断言和错误退出逻辑保留。最终功能、活动与物理网表的对应关系仍须完整审阅。

## 已观察到的失败与推进

| 回归 | 原生结果 | 下一项证据 |
|---|---|---|
| 原 r13 | 复位有效，但控制位为 X，CPU checker 135 失败 | 追踪重汇合逻辑并完成 14 位复位证明 |
| reset-r1 | 17.811 秒；checker 135 不再失败；物理清零观察失败 | 数据清零和 owner 均通过，snapshotZero 失败；部分未使用别名为 Z |
| reset-r2 | 18.018 秒；首次物理清零通过；首次 DMA 请求触发 fabric identity | 读取总线与内部别名，核对实际仲裁器连接 |
| reset-r3 | 20.814 秒；越过 fabric identity；首次 Y 写触发 Y mismatch，index=x；0 任务、0 warmup | 读取失败前地址、计数和数据，尚未确定根因 |

这些仿真在 `$fatal` 时的进程退出码仍可能为 0；验收必须检查原生日志，不以退出码代替通过。

首次物理清零日志确认：18,176 次 16 位写（W=16,384、BIAS=768、X=1,024），1,027 个物理周期，数据、地址、FIFO、累加器、结果、owner 与物理快照检查通过。

## 观察映射的连接证明

1. 快照原引用 556 个逻辑位。综合后其中 72 位无任何非声明引用；独立观察映射保留其余 484 位，对保留位继续检查四态零值。没有给 DUT 的空洞别名强制赋值。回执：`xu-gate-reset-20261112-r1/snapshot-mapping-r1.json`。
2. 原始 DMA 内部地址别名带 Z，而实际仲裁器地址正常。网表逐级连接证明：20 个地址信号位从 DMA 连到仲裁器，12 个被优化位在仲裁器接常量 0；8 位写掩码在仲裁器接常量 1，DMA 空洞端口不再使用。
3. `tb_dma64_soc_mapped_r2.sv` 将这两处总线观察映射到上述实际连接。完整 32 位地址和 8 位掩码比较、原对齐检查、85 处 `$fatal` 调用原文保留。回执：`xu-gate-reset-20261112-r1/dma-bus-mapping-r1.json`。
4. 测试台 SHA256：`f0e72340e4dd31181801b3a570d334d86c72633bdc9cb0fcb51a97ec0f417fe2`。独立编译 `xu-gate-20261112-r1/compile-bus-r1`，40.800 秒、退出 0；可执行件 `xu-gate-reset-20261112-r1/simv-bus-r1`。

## 当前诊断问题

首次 Y 写在 `16619381671395 fs` 触发 `Y mismatch layer=0 index=x`，数据与期望均显示 X。按以下顺序取证：

1. 实际物理地址生成或核心行/组索引为 X；读取请求地址、run_y、y_address、run_row、core_out_row/group 和计数器。
2. 仍有综合后的观察别名空洞；仅在实际连接证明支持时修正观察映射。
3. 测试台索引或装载逻辑有问题；核对实际地址确定且输入装载一致后再评估。

原生 UCLI 已在 `16619381 ns` 读到实际地址 `a0020X00`、`run_row=0`、`core_out_group=0`、`core_out_row=X`、`pop_count=1`、`issued_rows=8`，且 Y 载荷未知。原生复位采样在 `8000000 ns` 确认 `reset=1`、`n606=n605=1`，但 `io_outRow` 与其 D 引脚 `n8701` 仍为 X。FIFO 首个存储结果 `results_0_0_0=0x55b19` 为已知值。

既有服务器证明工具扩展到三个 `outputRow_reg[0..2]`，17 位均证明复位 D 恒为 0，仍为 312 个 BDD 节点。新副本 `xu-gate-reset-20261112-r2/mapped-functional-reset-r2.v` SHA256 `d8e1c611016b0baa943115078ad49f6e0a147980a7e9fe13df5d3e5827da95ac`，证明回执保存在同目录；独立编译 `compile-row-r1` 为 41.623 秒、退出 0。短回归 r4 在 90.016 秒到预设时限退出 124，无 fatal、无 checker 135；心跳确认已执行 4,008 笔 Y 写，仍 0 完整任务、0 warmup。

完整控制器 `xu-run-gate-reset-r14.py` 已启动，2026-11-12 23:25 服务器时间确认 PID 278002 和 simv PID 278006 存活。预检绑定新副本、同一可执行件、测试台、CPU 检查器、三固件映像及 95 个运行输入。可执行件 SHA256 `1845483bafd5c8fdd6e16111a5a03eefdb275c8817306978e87851f6f9da64fa`。预检回执 `xu-gate-20261112-r1/full12-r14-preflight.json`；当前日志 `xu-gate-20261112-r1/tight-O2-full12-r14/native.log`；活动路径 `xu-gate-20261112-r1/tight-O2-r14-fullsoc.vcd`。三固件串行复用同一可执行件，每份验证 12 任务、1 warmup、13 clear、无 fatal 后，给既有功耗控制器交接单槽，再继续下一份。全 SoC 功耗仍待原生结果和覆盖/单位审阅。

不得跳过输出检查、屏蔽 X、强制初始化控制状态，或把未完成的门级结果输入功耗验收。

## 连接与任务

VNC 中断后确认本机转发进程消失，中转机既有 PID 11512 仍监听 127.0.0.1:19523。仅恢复相同回环转发；RFB 003.008 握手通过，用户已重新登录。2026-11-12 23:13 服务器时间，功耗等待控制器 PID 299096 为 Ss，仍 `WAIT_GATE tight-O2`；本账号没有 EDA 重任务。未重启控制器。

后续必须继续完成三固件各完整 12 任务及 warmup、同窗全 SoC 活动与功耗、有效覆盖和单位审阅、单任务能量选型，以及最终 STA、Formality、电气与初赛材料核验。

## 物理原件审阅进展

已核对 `xu-fm-final-20261112-r6/receipt.json` 的 complete=true、native_exit=0，且 run.tcl/native.log 的 SHA 与回执一致。原生日志为 58,332 个 passing compare points，无 failing、aborted、unverified。比较端为 RTL 已证明的双角基线 24de7510… 至最终物理 2d5adc61…。

另有 1 个未匹配实现黑盒及 5 个输入引脚，实例为 PLIC 的 `flop_o_irq.plic_irq_prio_dffr`。实际模块 `sirv_gnrl_dffr_DW3` 是空壳，声明 qout[2:0] 输出；实际实例只接 dnxt/clk/rst_n，qout 没有接出。该结构范围必须保留，不将其误写为 SRAM 缺失或全无黑盒。RTL 到双角基线的原始终态与最终完整范围仍需继续核对。

四工况候选 result.json 为 PASS_IDEAL_FOUR_SCENARIOS，四角 maxcap/mincap/maxtransition 均记 0。原件包含 455,015 个时序检查，27,908/27,914 个 untested，不能只以汇总状态认定覆盖完整；下一步逐份核对 native receipt、约束 SHA、check_timing 和 coverage。

## R14 控制器修正事件

2026-11-12 23:38 服务器时间，原生确认 R14 simv 278006 存活，warmup=1、正式 task=1、无 fatal；VCD 约 15 GiB，剩余空间 854.5 GiB。整体等价此前确未启动，因此仅启动一次 PID 295350。

随后发现 R14 新增锁块之后的原循环体未正确缩进，锁只覆盖了预检，导致该 FM 与旧门级有过并发。核对时 FM 已自然结束并返回 FUNCTIONAL_COPY_EQUIVALENT，未执行任何停止原门级或原功耗控制器的操作。原始记录完整保留。

已启动 `xu-hold-existing-gate-r14.py`，守护 PID 304683 持有原 eda.lock，并绑定旧控制器 278002、timeout 278005、simv 278006 的进程开始标识，等待它们自然排空。

新控制器 `xu-run-gate-reset-r15.py` 为 6,669 字节，SHA256 `e628acc007aa8ab969b6f2476ee2067cf62e882df50c0860c4d9767b0486ccdb`。AST 已确认实际 run 调用位于目录锁内；增强的同账号重任务检测已实测识别 simv-row-r1。另将旧脚本 2,000,000 的 MAX_CYCLES 恢复为冻结 run_strict.py 和原测试台使用的 20,000,000；全部功能检查、12 任务、warmup、13 clear、无 fatal 及输入/网表哈希仍保留。

## R14 终态与 R15 接续

服务器 23:51 核对旧控制器 278002、simv 278006、守护 304683 均已退出。R14 原生 warmup=1、正式任务=3，随后在 21344474532219 fs 触发 SoC timeout（layer=3、state=0、reads=7520、writes=12672）；进程退出 0 但含 fatal，控制器的 12 任务断言失败。原件保留，部分 VCD 不进入功耗验收。

R15 于 23:51:47 启动，控制器 PID 316319、timeout 316329、simv 316330。现场读到 `+TASKS=12 +ROWS=8 +WARMUP=1 +MAX_CYCLES=20000000`，95 个输入与物理、功能、可执行件、测试台、CPU 检查器 SHA 预检通过。`/proc/316319/fd/3` 指向原 eda.lock；仿真期间非阻塞抢锁返回 BlockingIOError，输出 `PASS_DIRECTORY_LOCK_HELD_DURING_NATIVE_RUN`。功耗等待 PID 299096 保持存活。

## 整体功能副本等价范围闭合

`xu-fm-functional-20261112-r1` 原生运行 207.438 秒，complete=true、native_exit=0。当前脚本与日志 SHA 和回执一致，物理 2d5adc61… 与功能副本 d8e1c611… 的前后 SHA 一致。原生日志 58,337 个 passing compare points；unmatched、failing、aborted、unverified 均为 0。证明覆盖历史 r23 Boolean 变换及本轮 17 位复位屏蔽。回执 SHA256 `ddf122fe16b380ee21752699f5e5d2c1db42387d16ff32dd4b3da13e76012a04`。原工具结果中的审阅待办字段不回写；本文记录其后完成的人工范围核对。并发事件保留于上文，不重复运行以覆盖历史。

## R15 首份完整门级通过

服务器 2026-11-13 00:48 确认 tight-O2 的 12 个 D4K_TASK_PASS、D4K_SOC_PASS 和绑定文件存在。最初独立读取遇到尚未写完的空绑定 JSON；保留原文件，封存完成后重读。00:49 独立脚本 `xu-review-gate-full12-r1.py` 输出 PASS_INDEPENDENT_GATE_FULL12_REVIEW：正式输出 304,128，clear 13，宏读检查 169。12 个窗口复算 payload=416,580、clear=12,336、principal=428,916、gap=528 周期，日志内 firmware_cycles 合计 429,744。

官方独立回执 `xu-gate-independent-20261113-r1/tight-O2.json` SHA256 `1c91297b765b337dd2bd02b0432aed63686b8812d70d6a805b71ec23115be834`。波形 97,571,429,543 字节，控制器流式 SHA256 `44caf59b71ace97b6c7d32f947783e894727761d97be65cd4a7dcab743f28c64`；独立审阅只检查其大小与绑定，后续 payload 脚本再独立流式验证 SHA。

00:50 原功耗控制器 PID 299096 的 timeout/PT 子进程为 45461/45462/45476，PT 正在运行；R15 PID 316319 等待 WAIT_EXISTING_POWER tight-O2。原功耗 windows.json 的 gate_log_sha256 与封存绑定相同，尚无 output_sha256。没有重启或抢占原控制器；此时其余两份 full12 及全部功耗验收仍未完成。

## 真实终态与本版收尾接续 · 2026-11-13 08:24

上文为各历史时点的观察，当前以本节和 PROGRESS.md 为准。

tight 的扩展独立复算 r2 已通过，回执 `xu-gate-independent-20261113-r2/tight-O2.json`，SHA256 `f75f69aea0c3e9959ea92aa07e8d7e6cc5f0faad42f7ddebdd0f6407d5ee4a4e`。逐次核对 13 个软件时间轴、清零脏前态、物理夹具事务及 169 组宏读；实际软件控制窗口合计 429,864 周期，与冻结 RTL 一致。r1 的 429,744 是 TB firmware_cycles，旧命名差异由 r2 明确区分，原件保留。

07:38 经原生进程表与 `/proc` 确认旧 PID 299096、316319 及 PT 子进程全部自然退出，无 EDA 重任务且原锁可取得。原功耗回执为 native_exit=124、complete=false、seconds=2400.007，SHA256 `bd765e8f210b9faf07e9e6e92ada22d31f81ce133b6b0d97eebf9d55940eb479`。R15 随后因旧功耗 `/proc` 路径消失而退出；另外两份固件当时尚未启动。没有重新运行 tight 或终止旧进程。

原波形 97,571,429,543 字节的独立流式 SHA 已匹配 `44caf59b71ace97b6c7d32f947783e894727761d97be65cd4a7dcab743f28c64`。提取原型在随后的 `$dumpoff` 指令按设计拒绝并自然退出 1，没有成功的 activity.vcd 或回执，未用于功耗。由于 TB 原本仅在正式任务清零至最后 Y 后一周期启用 dump，已停止额外裁剪开发。

按用户优先完成本版的要求，已保留必要完整门级、评分窗口功耗、最后时序范围说明与交付，跳过重复等价、电气、面积验证和可选 clear+payload 功耗。新 R16 在服务器本地从原 R15 适配，SHA256 `c44f7a62da04ce9dbb4b52fec6023c1e4d9d265cd59fe479bffb0b0f4e28ee0a`；独立预检复核 95 个输入、五项 pin 及 tight 的完整绑定和独立 r2 审阅后，复用已通过结果，连续执行剩余两份。全部原断言、错误出口和 2,000 万周期上限保留，AST 确认实际 run 在原 eda.lock 内。

08:04:53 启动 R16 PID 156004。08:05 确认 simv PID 156023 正常运行且原锁实际持有。08:24:26 再读同一进程：RN、累计 CPU 19:31；phased 为 5/12 正式任务、1 warmup、无 fatal，backoff 尚未启动。该轮属于已核实实际进程仍在推进的等待，部分任务不标为完整通过。

08:28:11 再次读取同一 simv PID 156023：RN、累计 CPU 23:15，phased 已推进至 6/12 正式任务和 1 warmup，仍无 fatal。功耗 PID 160819 为 Ss，最新日志继续等待 R16 自然完成。未重启任何作业，也未把该部分结果记为完整通过。

必要 payload 功耗已排队 PID 160819，入口 `xu-b41-power-payload-r3.py`，SHA256 `46e2c0586463fdbcc7fbc3d47ae99b7e30706a327787c4c429d8e9b87f0629d5`。它绑定 R16 的具体进程开始标识，等待整轮门级自然完成后再独立复算并测量三固件；输出 `xu-power-payload-20261113-r3`。厂商 SAIF 与原生 VCD 的边界活动属性不一致、转换失败或 DURATION 不符时保留原件并回退直接 VCD，不修正计数。原生运行在锁内，上限扩为 14,400 秒；覆盖、337 宏与单位仍须实际审阅。

最后的固定任务工作点补查已排队 PID 173281，等待 R16、功耗均自然终态和实际 EDA 排空后执行未改的 `xu-workload-qualification-r1.py`。只补充任务期间 bootrom_n=0、dwakeup_n=1、erst_n=1 的范围，原约束、原网表与原四工况报告保留；启动异步释放范围另列。08:19:54 已核实该队列只等待，当前没有新 PT 并发。全部功耗、能量选型与最终交付仍待完成。

## 第二份原生 full12 终态 · 08:44

phased_64_fast4-O2 于服务器 08:43:36 正常 `$finish`，12 个正式任务、1 warmup、13 clear 和 D4K_SOC_PASS 均通过，无 fatal。原 `result.json` 为 exit_code=0、seconds=2323.5280339717865，SHA256 `ce42996183ad3be34661704b27ddf403825d022c3f0ef0a1250a3b033b1f06ba`；native.log SHA256 `331e7d25b1843376b6a00687884924900e5809e032cee42649f3f7d47dcf0d86`。

08:44:46 原生 simv 已自然退出，R16 PID 156004 为 R，正在计算 94,355,730,661 字节 VCD 的流式 SHA。verified-binding.json 已通过 exclusive 创建，但当时仍为 0 字节，因为整个绑定字典须在 SHA 完成后写入；文件存在不能作为封存完成证据。不提前读取 JSON，不重复启动或中断当前控制器。后续待绑定封存后独立 r2 复算并核对第三份实际启动。

## 第二份完整验收与第三份接续 · 08:58

08:47:44 确认 phased 绑定已封存为 796 字节，第三份 backoff 已由同一 R16 自动启动，simv PID 195929。phased VCD SHA256 为 `7797a235563c964901210617b19ceb88822866b2e8b3538447a934d9d277c7cb`，绑定 SHA256 `df94133f1a396df1404c8f7c0dbb415e45124abc98475c43a37f659cc75911f7`。

原独立 R2 在额外的跨模型汇总常量比较处失败。只读诊断确认全部原生/冻结解析不变量已通过；软件观测时间与 RTL 略有差异，计数与固件身份一致。R3 保留全部原检查和预算，把跨模型汇总作为测量差异记录，再以同一原件重放通过。完整变更、失败记录及来源指针见 [复算合同修正](REVIEW-CONTRACT-CORRECTION.md)。门级网表、测试台、固件、原断言与 CPU SVA 均未修改。

phased R3 回执 SHA256 `8a95f116ae1a42d55a38400c85f1425f22e54b55c1cda137e477638086fd251f`，输出/清零/宏读分别为 304,128、13、169；payload=416,580、clear=12,336、principal=428,916、gap=756、固件报告 firmware_cycles=429,984、外部软件控制=430,104。原 RTL 对应 payload=416,568、软件控制=430,128，分别保留，不混作门级测量。

08:58:20 实际核对 backoff simv PID 195929 为 RN、CPU 10:57，2/12 正式任务及 warmup 已通过，无 fatal；独立 R3 复算队列 PID 203683 为 Ss，等待该绑定封存。必要功耗与最后时序范围补查仍分别等待整轮门级及功耗自然终态，没有增加 EDA 并发。
