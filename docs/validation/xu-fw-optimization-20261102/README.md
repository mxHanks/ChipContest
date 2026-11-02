# xu 固件软件优化实验 — 2026-11-02

**软件阶段完成，完整服务器 VCS 验收 PASS。最终保留 `bias-dtcm / -O2 / both-unroll-no-masks`：真实12层总周期由 28,416,892 降为 25,251,416，减少 3,165,476（11.139417%），加速比 1.125358×。RTL、MMIO ABI、数值格式、向量和计时口径保持不变；硬件扩展留待后续。**

服务器执行代码为 `8a7640787423a73a0751454de47893406f85e604`，campaign 已带 `--accept` 完成。优化范围是现有 8 PE 平台上的固件装载与回读；总周期严格降低并通过完整 VCS 验收才算有效优化。本地单层数据不外推成服务器 12 层收益。

## 冻结身份与工作树

- 性能基线：`f0f27b4f1e182dce32136313b57252d39f4df1cd`。新工作树从 `codex/xu-platform-eval` 的计划提交 `c08cac3` 创建，分支为 `codex/xu-optimize-fw`，目录为 `/home/mxhanks/Projects/ChipContest-xu-optimize-fw`。`c08cac3` 相对性能基线仅新增计划文档。
- 原 `/home/mxhanks/Projects/ChipContest` 和交接树 `/home/mxhanks/Projects/ChipContest-platform-eval` 保留；代码、构建与本轮交付只写独立功能树。原服务器副本及历史日志保持只读。
- E203 gitlink 与独立子模块仓库 HEAD 均固定为 `e36d34a52e6eef93fd0bdfed1b13009e1056bea3`；计算 RTL、MMIO ABI、signed16 X/W、signed40 bias、signed48 Y、向量及数值模型保持基线身份。
- 夹具 archive SHA256：`ab9fe42d42324cabdd5912d7b2a2bee1c0fa8b9a55d5ca217da21a57f07c57f4`。已核对 archive 与 manifest，并逐一核对其中 48 个 mem 文件。
- [历史执行源 manifest](../xu-performance-20261102/runtime-source-manifest.json) 的四个文件哈希与优化前工作树一致。[历史收据](../xu-performance-20261102/observed-receipt.json) SHA256 为 `861d8c57204d811c166e62efbab2c0cb73b61213e60d79242bd9ef5ebb77ae79`；展开后逐层、阶段及总计与[历史派生报告](../xu-performance-20261102/derived-performance.json)一致，重算得到 **28,416,892 周期**。

工作负载为单个静音样本夹具的12个独立FFN1任务，每任务 `Y[99,256] = X[99,64] × W[64,256] + bias[256]`。计时仍从首次共享输入/参数读接受，到最后 Y 写响应退休；缓存复制、DTCM 写入与任务准备均在该窗口内。完整 W 装载后、首行 X 装载前复制缓存，因此原窗口外的首个 W_BANK/W_ADDR 两笔写继续在窗口外。单行 X 缓冲和 8 个 bias 槽决定仍采用 row→group 调度；任务间不复位 SoC，每任务重新装载 W/X/bias。共享行为 RAM、全局 modulo-7 背压、TB 时钟及 ITCM 装载方式均不变。

## 独立实现与判定规则

提交父链与实验比较对象分列：E2b 虽在 E2a 提交之后，运行时用不同宏选择，两者均独立比较同一 E1 配置。E3 使用同一源码和展开配置，只改变优化选项；E4 固定 E3 胜出配置，只删除三个写口的冗余掩码。

| 阶段 | 实现提交 / Git 父提交 | 唯一主要变化与配置 | 比较对象 | 当前结论 |
| --- | --- | --- | --- | --- |
| E0 | `697d300` / `c08cac3` | 共享调度/工作量契约，显式编译配置，构建与日志身份 | 历史 baseline | 服务器 real12 PASS，28,416,892周期；逐层及 baseline 镜像身份相同 |
| E0 补强 | `5059053` / `9d282ca`；`ff1587d` / `5059053` | 显式报告完整性、历史兼容；串行实验、择优与完整验收驱动 | 不改变固件路径 | 已实现，含失败与退化用例 |
| E1 | `9d282ca` / `697d300` | `bias-dtcm / -Os / none`；512 个 uint32 原始字，每任务刷新 | baseline / -Os / none | 服务器 synthetic2、real1、real12 PASS；总周期26,417,830，进入下一阶段 |
| E2a | `4344a10` / `ff1587d` | 仅展开固定 8 次 bias MMIO 装载；`bias-unroll` | E1 | 服务器 synthetic2、real12 PASS；25,719,194周期，独立改善 |
| E2b | `e046920` / `4344a10` | 仅展开固定 8 次结果回读/写回；`result-unroll` | E1 | 服务器 synthetic2、real12 PASS；25,915,589周期，独立改善 |
| E2 组合 | 同一源码宏选择 | E2a、E2b 各自改善后组合为 `both-unroll` | E2a，两个独立项中较优者 | 服务器 synthetic2、real12 PASS；25,347,370周期，优于两个独立项 |
| E3 | 固定 `8a76407` 源码，无源码补丁 | 固定 `bias-dtcm / both-unroll`，比较 `-Os/-O2/-O3` | 同配置 -Os | 三种选项 synthetic2、real12 PASS；-O2与-O3同为25,276,893周期，平局保持先测的-O2 |
| E4 | `8a76407` / `e046920` | 仅删除 X/W 低16位与 bias 高字低8位软件掩码；`both-unroll-no-masks` | E3 -O2 / both-unroll | 服务器 synthetic2、real12 PASS；25,251,416周期，通过完整验收并最终保留 |

E1 缓存保留全部 signed40 原始低/高字；共享源、MMIO 和 Y 仍为 volatile，缓存位于未初始化 BSS。bias 写入仍按 INDEX→LO→HI；结果仍按 INDEX→LO 读/Y 低字写→HI 读/符号扩展/Y 高字写，bank 为 0–7，Y 地址行优先递增。RESULT_HI 的 `(uint32_t)(int32_t)(int16_t)` 扩展、W1C/START/轮询超时、末尾 fence 及写回退休后 ACK 均保留。E4 依据固定 RTL 写口截断位宽实施，不删除 RESULT_HI 的符号扩展。

| 每任务契约 | baseline | bias-dtcm |
| --- | ---: | ---: |
| W / X 共享读 | 16,384 / 6,336 | 相同 |
| bias 共享读 | 50,688 | 512 |
| 共享读总计 | 73,408 | 23,232 |
| Y 共享写字 | 50,688 | 50,688 |
| bias MMIO 写 / 全部窗口内 MMIO 写 | 76,032 / 156,326 | 相同 |
| START / done | 3,168 / 3,168 | 相同 |
| MAC 有效拍 / MAC 数 | 202,752 / 1,622,016 | 相同 |

MMIO 轮询读次数按实际结果记录。驱动拒绝未知或错配配置、漏层/重复/乱序、错误输出/写回/MAC/事务数、阶段和错误及日志失败标记。完整 12 层须逐字核对 304,128 个结果与 608,256 次输出写字。

## 本地实测：SiFive GCC10 + Verilator

本地交叉编译器为原发行版子集 **SiFive GCC-Metal 10.2.0-2020.12.8**，不是系统默认 GCC14；后者的数据未混入本表。仿真器为 Verilator 5.032，主机 g++ 为 15.2.0。本地 prefix 为 `/tmp/chipcontest-riscv-tools/sifive-rv32-c/bin/riscv64-unknown-elf-`。子集 manifest SHA256 为 `ac6313ec47249b56990cec81bc3bb2aae2b1aa48188a0f2d04e8bd4e78c2c9bd`，其中 2,241 个文件哈希已核对；原 SiFive 发行包 SHA256 为 `de2bb188300dc38d74103516ce5cfd1060dfd105e8a408e9e3991512cf27285e`。

| 实跑项目 | 执行 Git HEAD | 配置 | 层 / TB 周期 | 输出 / 写字 | 结果 |
| --- | --- | --- | --- | --- | --- |
| E0 前 real1 | `c08cac3` | baseline / -Os / none | layer0：2,368,078 | 25,344 / 50,688 | PASS，与历史 layer0 相同 |
| E1 synthetic2 | `9d282ca` | bias-dtcm / -Os / none | layer0、1：各 2,201,485 | 50,688 / 101,376 | PASS，两层 bias 不同，连续刷新 |
| E1 real1 | `5059053` | bias-dtcm / -Os / none | layer0：2,201,485 | 25,344 / 50,688 | PASS |
| E2a real1 | `8a76407` | bias-dtcm / -Os / bias-unroll | layer0：2,143,266 | 25,344 / 50,688 | PASS |
| E2b real1 | `8a76407` | bias-dtcm / -Os / result-unroll | layer0：2,159,637 | 25,344 / 50,688 | PASS |
| E3/E4 边界组合 synthetic2 | `8a76407` | bias-dtcm / -O3 / both-unroll-no-masks | layer0：2,104,281；layer1：2,104,285 | 50,688 / 101,376 | PASS，本地正确性压力检查 |
| 固定真实向量独立整数核算 | `697d300` | 无 RTL 仿真 | 完整 12 层 | 304,128 个结果 | PASS |

本地 E1 相对 E0 单层减少 166,593 周期（7.034946%，1.075673×）；E2a 相对 E1 再减少 58,219 周期（2.644533%，1.027164×）。这些是 **Verilator 的单层比较**，不能作为最终服务器收益。E0/E1 固件 mcycle 比 TB 窗口多 72 拍，E2a 多 83 拍；比较仍使用同定义的 TB 窗口。

| layer0 观测 | E0 | E1 | E2a |
| --- | ---: | ---: | ---: |
| w_load | 316,782 | 316,781 | 316,323 |
| x_load | 121,474 | 121,539 | 121,522 |
| bias_load | 785,467 | 601,332 | 553,458 |
| compute_wait | 218,592 | 218,592 | 218,592 |
| writeback | 804,476 | 802,758 | 802,196 |
| other | 121,287 | 140,483 | 131,175 |
| shared_reads | 73,408 | 23,232 | 23,232 |
| mmio_reads | 69,696 | 72,864 | 72,864 |
| shared_stall / mmio_stall | 24,011 / 0 | 9,984 / 0 | 9,616 / 0 |

三者的 shared_writes=50,688、mmio_writes=156,326、starts=dones=3,168、mac_fire=202,752、busy=215,424 相同。六阶段覆盖总窗口；阶段含软件与总线间隙，DTCM 访问不触发阶段切换，因此不能把阶段差直接解释成被消除的纯传输时间。

## 48 配置编译与空间审查

固定最终 C 源码 `8a76407`，用同一 SiFive GCC10 子集编译 `2 调度 × 3 优化等级 × 8 展开/掩码配置`，共 **48/48 doctor PASS**；该项仅编译与反汇编，不运行仿真或 make install。全部 `.data=0`，符合启动代码不复制初始化 DTCM 数据的链接约束；baseline BSS=0，bias-dtcm BSS=2,048 字节。

| 代表配置 | ITCM 字节 | BSS 字节 | main + accel 静态 frame 字节 | 减 BSS、16字节栈顶预留和调用链后的 DTCM 字节 |
| --- | ---: | ---: | ---: | ---: |
| baseline / -Os / none | 598 | 0 | 32 + 16 | 65,472 |
| bias-dtcm / -Os / none | 630 | 2,048 | 32 + 16 | 63,424 |
| bias-dtcm / -Os / bias-unroll | 804 | 2,048 | 32 + 48 | 63,392 |
| bias-dtcm / -Os / result-unroll | 842 | 2,048 | 32 + 32 | 63,408 |
| bias-dtcm / -Os / both-unroll | 972 | 2,048 | 32 + 32 | 63,408 |
| bias-dtcm / -O2 / none | 638 | 2,048 | 32 + 32 | 63,408 |
| bias-dtcm / -O3 / none | 978 | 2,048 | 32 + 48 | 63,392 |
| bias-dtcm / -Os / no-masks | 608 | 2,048 | 32 + 16 | 63,424 |

48 配置 ITCM 范围为 572–978 字节，最小剩余 ITCM=64,558 字节；main 静态 frame 恒为32字节，accel 为16/32/48字节，最大调用链80字节，最小剩余 DTCM=63,392字节。上述数值来自 GCC `.su` 和已知 main→accel_linear 调用链，未测运行时栈水位。所有反汇编保留 RESULT_HI 的 signed16→signed32 移位对及最终 fence。

GCC10 `-O3` 自动展开两个8次循环；同一调度、同一掩码状态下，none/bias-unroll/result-unroll/both-unroll 四配置生成完全相同的镜像。优化等级与代码体积不能代替总周期比较。

最终源码的 baseline/-Os/none ELF SHA256 仍为 `02cdd79ef8884f04f7e8efe1eaaa4faf7c0311064a7d06bccc3187cbd58387b3`，镜像 SHA256 仍为历史 `4932e8d8f62cdd2732d894abc4c7008809283fe3de29445de90ec764cd12f32e`。完整矩阵位于 `/home/mxhanks/Projects/ChipContest-xu-optimize-fw/build/xu-opt-local/compile-matrix.json`，SHA256 为 `5743920f79d6aae4288f5017578fee31e4f52f05e220a6142688f0d06b7276d9`，逐配置含命令、ELF/image/源码/日志/反汇编哈希与空间数据。

矩阵已归档为 [compile-matrix.json](compile-matrix.json)；全部 48 组原始构建日志、反汇编、静态栈和结果存于 [compile-evidence.tar.gz](compile-evidence.tar.gz)，SHA256 为 `64e4ae47f573eeb8339b46c377f97e7402ebaa0a3e5a34e04d6a2bd3cab04d77`。

## 服务器实验与完整验收结果

服务器独立代码副本为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/ChipContest`；当前 campaign 输出为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/xu-vcs-campaign-01`。交叉工具仍使用历史 SiFive 子集，VCS 仍为 Q-2020.03-SP2-6；当前运行的实际版本与逐文件身份以本次 `experiments.json`、子步骤 `result.json` 及版本日志为准。

新副本从历史主仓 `clone --no-hardlinks` 后取得增量 bundle，检出独立分支上的 `8a76407`。bundle 覆盖 `ddcf6cc..8a76407`，SHA256 为 `f10cd9dc9d4a579f5eec34ee8c6d444ece983ac8de89f48bfba01c1da3fd6f97`。子模块独立复制并核对固定 gitlink。复制时须用 `cp -a` 或 Python `copytree(..., symlinks=True)` 保留链接；本次新副本曾发现4项 symlink 类型差异，已在新副本内用固定 HEAD 恢复并通过干净性检查后才启动 driver。

| 项目 | 实测结果 |
| --- | --- |
| fresh E0 real12 历史逐层、固件周期、镜像身份 | PASS，总周期 28,416,892；逐层与镜像身份检查通过 |
| E1 synthetic2 → real1 → real12 | 全 PASS；real12 总周期 26,417,830，减少 1,999,062（7.034767%），1.075671×；共享读 278,784 / 输出写字 608,256 |
| E2a、E2b 独立 synthetic2/real12 | 全 PASS；E2a 总周期25,719,194；E2b 总周期25,915,589；两者分别优于同一E1参考 |
| E2 胜出项组合 | synthetic2、real12 PASS；25,347,370周期，优于较快的独立E2a |
| E3 同源码 -Os/-O2/-O3 | 全部 synthetic2、real12 PASS；-Os为25,347,370，-O2与-O3均为25,276,893；-O3平局未替换-O2 |
| E4 同选项去掩码 | synthetic2、real12 PASS；25,251,416周期，较E3 -O2再减少25,477周期 |
| host / numeric / vectors / doctor / 原SoC5项 / synthetic1 / synthetic2 / real12 | 全部 PASS：host 38/38、numeric 34/34、12层整数向量核算、实际固件 doctor、原SoC 5/5、synthetic1、连续 synthetic2、real12 |
| 最终保留调度 / 优化等级 / 实验配置 | `bias-dtcm / -O2 / both-unroll-no-masks` |
| 最终real12总周期 / 相对基线加速比 | 25,251,416 / 1.125358×；比基线减少3,165,476周期（11.139417%）；完整验收已确认 |
| 最终事务、阶段、MAC 活跃占比与空间 | 12层 MAC有效拍2,433,024，MAC活跃占比9.635198%；共享读278,784，输出写字608,256；ITCM962字节/BSS2,048字节/静态调用链栈80字节；见下表 |
| 保留 / 放弃理由，包括无收益与失败实验 | 保留E1缓存、E2双展开、E3 -O2和E4去掩码；-O3与-O2逐层及镜像相同，平局保持-O2。无失败实验；E3-Os重复参考无变化 |

以下为本次服务器各实验真实12层窗口总周期。E1–E4 每项均通过 synthetic2 与 real12，E1另通过real1；此表记录实验正确性与性能，完整验收已通过。速度比统一用 `28,416,892 / 本项总周期` 计算；差值按各自独立实验参考计算。

| 实验 | 配置（均为bias-dtcm，E0除外） | real12总周期 | 独立比较参考 | 对参考周期差 | 相对baseline速度比 | 当前实验判定 |
| --- | --- | ---: | --- | ---: | ---: | --- |
| E0 | baseline / -Os / none | 28,416,892 | 历史baseline | 0 | 1.000000× | PASS，复现冻结基线 |
| E1 | -Os / none | 26,417,830 | E0 | -1,999,062 | 1.075671× | PASS，进入E2 |
| E2a | -Os / bias-unroll | 25,719,194 | E1 | -698,636 | 1.104890× | PASS，独立改善 |
| E2b | -Os / result-unroll | 25,915,589 | E1 | -502,241 | 1.096517× | PASS，独立改善 |
| E2组合 | -Os / both-unroll | 25,347,370 | E2a | -371,824 | 1.121098× | PASS，组合改善 |
| E3-Os | -Os / both-unroll | 25,347,370 | E2组合 | 0 | 1.121098× | PASS，固定源码重复参考 |
| E3-O2 | -O2 / both-unroll | 25,276,893 | E3-Os | -70,477 | 1.124224× | PASS，进入E4 |
| E3-O3 | -O3 / both-unroll | 25,276,893 | E3-Os | -70,477 | 1.124224× | PASS，与-O2平局，未替换 |
| E4 | -O2 / both-unroll-no-masks | 25,251,416 | E3-O2 | -25,477 | 1.125358× | PASS，最终保留 |

以下逐层周期来自本次服务器原始结果 JSON；fresh E0逐层复现历史基线，最终完整验收与E4实验逐层完全相同：

| layer | 历史 baseline TB 周期 | 本次 fresh E0 | 最终 TB 周期 | 最终−baseline |
| --- | ---: | ---: | ---: | ---: |
| 0 | 2,368,078 | 2,368,078 | 2,104,281 | -263,797 |
| 1 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 2 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 3 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 4 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 5 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 6 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 7 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 8 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 9 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 10 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 11 | 2,368,074 | 2,368,074 | 2,104,285 | -263,789 |
| 合计 | **28,416,892** | **28,416,892** | **25,251,416** | **-3,165,476** |

本次总周期严格低于28,416,892，且完整服务器验收通过。相同或更差均不保留；所有候选无收益时回退 baseline。driver 在没有 VCS 或未完成 `--accept` 时不标记 `retained_optimization=true`。150 MHz 只作条件换算，不代表物理时序闭合；此夹具不代表完整 encoder、官方成绩、样本集精度、新面积/功耗或 CPU-only 加速比。

## 最终阶段、事务与空间

总周期减少 **11.139417%**，速度比 **1.125358×**；MAC活跃占比由 **8.561893%** 到 **9.635198%**。条件150MHz平均延迟由 **15.787162ms** 到 **14.028564ms**，任务吞吐由 **63.342606** 到 **71.283131任务/s**。

| 阶段 | baseline周期 | final周期 | 差值 | final占比 |
| --- | ---: | ---: | ---: | ---: |
| w_load | 3,801,373 | 3,587,532 | -213,841 | 14.207251% |
| x_load | 1,457,688 | 1,378,091 | -79,597 | 5.457480% |
| bias_load | 9,425,593 | 6,627,180 | -2,798,413 | 26.244786% |
| compute_wait | 2,623,104 | 2,623,104 | +0 | 10.387948% |
| writeback | 9,653,690 | 9,618,070 | -35,620 | 38.089230% |
| other | 1,455,444 | 1,417,439 | -38,005 | 5.613305% |

| 活动/事务 | baseline | final | 差值 |
| --- | ---: | ---: | ---: |
| busy | 2,585,088 | 2,585,088 | +0 |
| mac_fire | 2,433,024 | 2,433,024 | +0 |
| mmio_reads | 836,352 | 912,384 | +76,032 |
| mmio_writes | 1,875,912 | 1,875,912 | +0 |
| shared_reads | 880,896 | 278,784 | -602,112 |
| shared_writes | 608,256 | 608,256 | +0 |
| shared_stall | 288,088 | 92,024 | -196,064 |
| mmio_stall | 0 | 0 | +0 |
| starts | 38,016 | 38,016 | +0 |
| dones | 38,016 | 38,016 | +0 |

| 空间 | baseline | final |
| --- | ---: | ---: |
| ELF文件字节 | 5,504 | 5,896 |
| ITCM字节 | 598 | 962 |
| 剩余ITCM字节 | 64,938 | 64,574 |
| .data字节 | 0 | 0 |
| BSS字节 | 0 | 2,048 |
| main+accel静态frame字节 | 48 | 80 |
| 减BSS/栈顶预留/调用链后DTCM字节 | 65,472 | 63,392 |

最终每层 firmware mcycle 比TB窗口多79拍（layer0为2,104,360，其余各2,104,364）；性能比较仍用TB窗口。全部阶段求和覆盖总窗口，活动/事务计数与阶段重叠，不再次相加。MMIO轮询读随软件变化，未固定到基线；bias MMIO写仍为每任务76,032。静态栈来自GCC `.su` 和 main→accel调用链，未测运行时水位。

## 复现命令

实际执行代码提交固定为 `8a7640787423a73a0751454de47893406f85e604`；后续报告提交仅新增证据和说明。从交付分支新克隆时，先检出此代码提交并初始化固定子模块，再运行下列命令。在旧Git服务器可使用 `git clone --no-hardlinks --no-checkout` 创建独立副本后 `git checkout --detach 8a7640787423a73a0751454de47893406f85e604`；离线复制子模块应使用 `cp -a` 保留链接和独立仓库。

以下服务器命令使用新输出目录；不得与其他会操作同一子模块安装目录的任务并行。完整 campaign 会自行串行运行各候选、选出总周期较低者、执行完整验收并显式生成性能摘要：

```bash
cd /storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/ChipContest
xu_cross_prefix=/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-
xu_campaign_out=/storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/xu-vcs-campaign-repro-01
test "$(git rev-parse HEAD)" = 8a7640787423a73a0751454de47893406f85e604
python3 tools/scripts/xu_fw_experiments.py \
  --sim vcs --cross-prefix "$xu_cross_prefix" \
  --out "$xu_campaign_out" --accept
```

单独复现最终保留版本可使用下面的已测配置。验收与摘要均使用新目录：

```bash
xu_final_schedule=bias-dtcm
xu_final_opt=-O2
xu_final_experiment=both-unroll-no-masks
xu_accept_out=/storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/xu-vcs-final-repro-01
python3 tools/scripts/server_accept.py \
  --sim vcs --cross-prefix "$xu_cross_prefix" --out "$xu_accept_out" \
  --firmware-schedule "$xu_final_schedule" --firmware-opt="$xu_final_opt" \
  --firmware-experiment "$xu_final_experiment"
python3 tools/scripts/xu_perf_report.py \
  --result "$xu_accept_out/real12/result.json" --frequency-mhz 150 \
  --out "$xu_accept_out/xu-performance.json"
```

本地基本检查和已测单层路径可在新目录复现：

```bash
cd /home/mxhanks/Projects/ChipContest-xu-optimize-fw
xu_local_prefix=/tmp/chipcontest-riscv-tools/sifive-rv32-c/bin/riscv64-unknown-elf-
python3 -m unittest discover -s tests/e203 -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode check-vectors --tasks 12 \
  --out build/xu-opt-local/repro-vectors12
python3 tools/scripts/e203_soc.py --mode synthetic --tasks 2 --sim verilator \
  --cross-prefix "$xu_local_prefix" --firmware-schedule bias-dtcm \
  --firmware-opt=-Os --firmware-experiment none \
  --out build/xu-opt-local/repro-e1-synthetic2
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --cross-prefix "$xu_local_prefix" --firmware-schedule bias-dtcm \
  --firmware-opt=-Os --firmware-experiment bias-unroll \
  --out build/xu-opt-local/repro-e2a-real1
```

48 配置可仅通过 doctor 复编，不触发仿真或安装：

```bash
xu_compile_out=build/xu-opt-local/repro-compile-matrix
mkdir "$xu_compile_out"
for xu_schedule in baseline bias-dtcm; do
  for xu_opt in Os O2 O3; do
    for xu_experiment in none bias-unroll result-unroll both-unroll \
        no-masks bias-unroll-no-masks result-unroll-no-masks both-unroll-no-masks; do
      python3 tools/scripts/e203_soc.py --mode doctor --sim vcs \
        --cross-prefix "$xu_local_prefix" --firmware-schedule "$xu_schedule" \
        --firmware-opt="-$xu_opt" --firmware-experiment "$xu_experiment" \
        --out "$xu_compile_out/$xu_schedule-$xu_opt-$xu_experiment"
    done
  done
done
```

## 日志哈希与证据边界

本地原始结果位于 `/home/mxhanks/Projects/ChipContest-xu-optimize-fw/build/xu-opt-local/`。以下均从实际文件重算；E0 的旧结果 JSON 没有 `log_sha256` 字段，因此其日志哈希由文件单独计算。后续结果 JSON 自带构建、仿真、工具版本等全部 `.log` 哈希。

| 本地目录 | result.json SHA256 | simulation.log SHA256 |
| --- | --- | --- |
| e0-before-real1 | `fe90ce7f4370dbb5d5e23778fa7ad88309e3cb9501a76ebd78ee6d25a061ea16` | `d62aa1d359c663fae7dcbdfca64090199e8a577a0bd16bdd96bfabfa42446ad0` |
| e1-synthetic2 | `d9842dcda641bfea2f591d97aa68239b4ad47b6974972f4b5773372ed320fb97` | `7f3a12d94bffef4c92f3723817bfa62b97b2a4e9865a132c7f3e2f6b103b4262` |
| e1-real1 | `d63f927806a94d7b981bdcf08ee39e65258547ac10880172ff70c84b29211b50` | `1598d7501ee5bb8bf03ce59d6d02dd5fc6b424ad0fc958ac7b3b3caeada59636` |
| e2a-real1 | `56c060de470bdbad14ea1a2d206153cd0ea23b314871089272d66a9f7ed63db5` | `c52389f901aceb64e0dabe483fc287f8ea833a00d1b07a1a376672e313f51f66` |

本地原始日志与结果已归档为 [local-evidence.tar.gz](local-evidence.tar.gz)，SHA256 为 `e3f0d39f8746edfa02a013e33495177463ba575c3441a155cfd4d3360c1929da`；[逐文件 SHA256](local-evidence-sha256.json) 可核对解包内容。 E2b 与 E3/E4 本地组合的附加回放日志存于 [local-extra-evidence.tar.gz](local-extra-evidence.tar.gz)，SHA256 为 `30335a5d917d2d63e15566b3b122c3436b031baf98cb7a78f21b67aa44997484`；[逐文件 SHA256](local-extra-evidence-sha256.json)。固定向量核算 `result.json` SHA256 为 `5743ecfb19f4b7117f1f226b4bf43c4c62e17e1a79e1d1a592079be1a6077c7f`。

服务器 FTP 拒绝 RETR，本轮通过已授权的VNC可见屏幕传递字节：ANSI颜色网格每页CRC核验，合并后校验完整SHA256。原始JSON与host/numeric日志是逐字节副本；传输manifest、观测收据及两个日志摘录JSON属于派生证据。完整VCS日志原文仍留服务器，原始result记录其完整SHA256。摘录只能复核所提取行，不能独立证明其它区域无失败标记；完整日志检查由已核对身份的原runner/driver执行，源端收据再核对原文件SHA。

- [原始JSON与日志副本包](xu-raw-results-lite-01.tar.xz)：29份原始文件的bytes/SHA均通过manifest核对；SHA256为 `cd390656786a61b58617f47753184f4200f73bf4ce091cc6a8b2af7084ee465d`。解包后的 [原始实验报告](server-json/experiments.json)、[验收报告](server-json/acceptance/acceptance.json)、[最终real12结果](server-json/acceptance/real12/result.json)、[服务器性能摘要](server-json/acceptance/xu-performance.json)、[host日志](server-json/acceptance/host.log)、[numeric日志](server-json/acceptance/numeric.log) 可直接审查。
- [观测收据](observed-receipt.json)：SHA256为 `87ef22f9348489a416bd4072fb91d5d98b52fbdd8fdd8c202212239fdfdbd744`，`final.status=PASS`、`integrity_errors=[]`。
- [本地独立复核](verification.json)、[派生性能汇总](derived-performance.json)、[逐实验逐层比较](comparison.json) 与[可读比较表](comparison.md)：复算21次仿真的精确PASS行与结果字段，核对当前RTL/TB/固件哈希、服务器与本地同款SiFive编译的ELF/镜像一致、最终验收与E4逐层一致、服务器摘要复算一致。
- [原始文件传输manifest](server-json/xu-transfer-manifest.json) 本身是派生清单；[仿真精确PASS行摘录](server-json/xu-simulation-pass-lines-derived.json)、[验收日志行摘录](server-json/xu-selected-validation-log-lines.json) 明确不冒充完整日志。每个原始结果JSON内 `log_sha256` 包含该运行全部构建、版本与仿真日志哈希。
- 屏幕证据见 [完整PASS](screens/server-pass.png)、[源端收据生成](screens/receipt-export.png) 和 [传输帧清单](screen-transfer-manifest.json)。[全部交付文件SHA256](evidence-sha256.json) 可核对归档文件。

原始服务器输出目录为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-fw-optimization-20261102/xu-vcs-campaign-01`。最终日志原文为其中 `acceptance/real12/simulation.log`；其他实验和验收子目录也保留原文、构建日志和版本日志。

| 原始文件 | SHA256 |
| --- | --- |
| `experiments.json` | `fc87e5d0b5bcd29118e96942b45769b0f45df15a924feb49e59d2398a4bbfe22` |
| `acceptance/acceptance.json` | `ea458063dbe1c47e91a9732e7d43cd658fe3e1c833c9c2e989758c686d4866f3` |
| `acceptance/real12/result.json` | `fa1422c9ae2eb1cf4ed0d2d3434afe008fb2256849617eee0914c3ebedced611` |
| `acceptance/real12/simulation.log` | `b53e8a028ad71966dca7ab6e6886e44f8cbb5e2d634fe78bc3d365314a6e6464` |
| `acceptance/xu-performance.json` | `191923e446b333bebd9bc5a9d75bdf122165718da8f024e0107f959901404078` |
| 最终固件ELF | `c66d554422a394c6c1dc3fd08808f102e0101d8e9d6f496a64e03f59fa8932ad` |
| 最终固件镜像 | `73f5aa7dd9d67e05288e33971617c90565be49eb3a7528841659753f1ae35c46` |

完整RTL/TB/向量/固件/runner/contract/工具版本与可执行文件身份见 [原始实验报告的environment/source](server-json/experiments.json) 及 [最终result](server-json/acceptance/real12/result.json)。TB SHA仍为 `08af453d542ec3b24673f05e5a404c83165ac6e33e875e3930265a967016fe99`；runner SHA为 `92ea23d75912771f54817c79651a49a42adf1ae1a6eae421da4d83d7e65fbdce`。

证据复核可在新的临时目录执行，输出目录和派生文件必须尚不存在：

```bash
xu_evidence=docs/validation/xu-fw-optimization-20261102
xu_verify_out=$(mktemp -d /tmp/xu-fw-evidence-XXXXXX)
python3 "$xu_evidence/evidence-tools/xu_verify_results.py" \
  "$xu_evidence/xu-raw-results-lite-01.tar.xz" "$xu_verify_out/server-json"
```

[收据生成器](evidence-tools/xu_receipt.py)、[原始文件打包器](evidence-tools/xu_package_results.py) 和[可见屏幕传输/还原工具](evidence-tools/xu_screen_transfer.py) 随证据归档。前两者及屏幕emit仅用Python标准库；本地图片decode使用Pillow，未保存任何连接凭据。

本轮无失败实验；E3-Os重复参考无收益，E3-O3与-O2平局而未替换。未运行的范围为Icarus/Chisel、完整encoder、浮点validation/官方600样本精度、工艺SRAM/PPA/面积功耗与CPU-only对照。本轮未实施硬件缓存、地址自增、连续结果窗口、DMA或PE扩展。
