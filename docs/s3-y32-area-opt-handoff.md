# 64PE面积优化 B 方案 handoff

2026-11-11。本轮选定 **B：ACC41＋引擎结果41＋结果FIFO41**，用于保持仿真周期并减少映射面积。完整12任务与原48位版逐层周期、输出和事务完全一致；同条件保守计费面积减少 **3.69%**。这是本轮源码选型，**时序尚未闭合，实际150MHz、2.25mm²和正式比赛资格未认证**。

## 固定版本与软件整合

| 用途 | 父仓库提交 | E203硬件子提交 |
|---|---|---|
| 本轮B源码 | `96fffcb2a4b2492fd2cfdecb88e164d2c67881ae` | `ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1` |
| 原48位回退 | `d60e0e00d79051747b8adcfa39fca273a6e7e309` | `a80dd184536e0f2312c62768d5acf4ba1b01c34e` |

父子分支均为`codex/s3-y32-area-opt-20261111`。[父源码96fffcb](https://github.com/mxHanks/ChipContest/commit/96fffcb2a4b2492fd2cfdecb88e164d2c67881ae)与[子源码ccdac30](https://github.com/mxHanks/e203_hbirdv2/commit/ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1)已推送并经远端head逐项核验；先前`ef57994`是实验进度节点，未安装B，不能把它当本轮B源码。

按固定源码提交检出（最后的文档提交可以更新，源提交与gitlink保持）：

```sh
git clone --branch codex/s3-y32-area-opt-20261111 --recurse-submodules https://github.com/mxHanks/ChipContest.git
cd ChipContest
git checkout 96fffcb2a4b2492fd2cfdecb88e164d2c67881ae
git submodule update --init --recursive
git -C third-party/e203_hbirdv2 rev-parse HEAD
```

最后应为`ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1`。安装tile SHA256必须为`710b8e180652f49751769e152a3b3a9e6a35ba622fb4c3e2385dc5ffab241fcb`。独立安装审计已将新父子提交与真实CPU测试源码绑定，165份现有RTL逐SHA匹配；没有重写历史测量JSON的旧父子身份。

软件沿用[原64PE接口与启动说明](s3-y32-4k-handoff.md)，其中旧版本号作回退。本轮没有描述符、MMIO、布局、固件或CPU/LSU/BIU改动。保留`XU_MATRIX_DMA`和`XU_MATRIX_DMA64`、0x10042300基址、8字节地址对齐、CTRL=1真实清零、CTRL=0x802八行模式、CAPABILITY=0x00084001；99行尾部为3行。输入/权重signed16、bias signed40、公开raw48与最终Y32/RNE(acc/512)语义保持。提交前fence、错误排空和全部输出写响应退休后才完成的规则保持。

每任务真实source读7520次（4096W＋256bias＋3168X）、Y写12672次、3168次POP、26624个MAC有效周期。八行共享W16宏与bias1宏；共享512KiB、ITCM和DTCM容量及总337宏不增加。物理清零仍写18176个16bit地址/任务，并清空ACC/结果/FIFO/cache/DMA状态，不使用valid失效代替实际写零。

## 改动和验证结果

只改子仓一份`rtl/e203/perips/LinearTileDmaCore.sv`，父仓改对应五份生成器源码。累加器、引擎结果与FIFO的48→41收窄均有全signed16/signed40输入范围证明；公开raw48以符号扩展恢复，最终舍入位置保持。声明状态累计减少1792位（224B），SRAM容量/数量、2KiB X双缓冲和总线调度不变。原generic叶模块、旧构建和默认48位生成保持；仿真observer、PPA声明前移main副本均未安装。

完整12任务304128个Y32逐位一致，payload416579拍＋真实clear12336拍＝**428915拍**；gap516单列，含gap429431拍，固件同步全区间429720拍。第0层35742拍，其余11层各35743拍，全部与回退相同。单行224994拍、source-stall31控制35772拍也相同。极值/RNE、背压、首次读写错误与排空、在途复位恢复和全物理清零均通过。固件image逐字节相同，ELF临时非分配STT_FILE名6字符差异经独立窄范围审计保留。

| 同条件计费面积（库单位） | 回退48位 | A（未选） | B（选定） |
|---|---:|---:|---:|
| 标准逻辑 | 368187.943200 | 359610.081600 | 348816.652800 |
| 内部17 SRAM | 155524.915038 | 155524.915038 | 155524.915038 |
| 原计费合计 | 523712.858238 | 515134.996638 | 504341.567838 |
| 范围外逻辑正增长保守加计 | — | 70.224000 | 53.625600 |
| 保守合计 | 523712.858238 | 515205.220638 | **504395.193438** |
| 比回退减少 | — | 1.6245% | **3.6886%** |

没有以全SoC面积作节省分母。B标准逻辑减少5.2613%，主要收益来自引擎与FIFO/核心控制。A同样周期不增，但面积更大且transition违例更多，因此不选。完整leaf、组件分类、范围外逻辑变化与同一映射PT均已独立审计。

PT setup：基线−10.66794014ns，A−10.53013802ns，B−10.11695099ns，均为GFCM调试时钟到GPIOA[27]；hold均−0.13472039ns，位于bias SRAM。三者各211个coverage违例（178hold＋5removal＋27门控hold＋1输出setup），27911未测，**不能宣称时序通过**。B DRC maxcap/mincap/maxtransition为92/1449/276，基线98/1505/276；低打印精度标记仍作为违例保留。674个辅助CEN/RET1N与337个实际CLK关联已逐项分类，未豁免任何路径。

4196.64task/s仅按假定150MHz换算。库面积量纲和官方SRAM计价未确认，不能直接把库单位标为mm²或宣称2.25mm²合格；映射后形式等价和官方宽口平台资格也未验证。

## 证据和复现

见[结果](s3-y32-area-opt-results.md)、[状态](s3-y32-area-opt-status.md)、[全部归档与SHA](validation/s3-y32-area-opt-20261111/README.md)。保留原48位发布包、607文件仿真delta、A/B真实242项PPA输入、完整baseline leaf/PT、A/B完整leaf/DC所需报告和全部PT输出、独立比较、选型与安装身份收据。

A/B报告r4包2532604B，SHA`fd235de2b63b06b321d9940641937e1a29a35c6497ca6ba3ed89687be13fd763`，20片与整包均已验证。两候选各584项DC输出中51项已本地逐字节核验，含完整leaf及所需面积报告；其余WORK、SVF、mapped.v/ddc等保留远端SHA/bytes，未作本地网表字节或映射后等价声明。PT各45项输出完整核验。旧大包及VNC中断记录保留，r4取证没有重跑综合。R5旧collector FAILED/退出码1也保持，后续PT不改写原失败。

重新生成选定B时明确使用三个41参数，默认48仍服务回退：

```sh
scala-cli run project.scala src/main/scala experiments/s3-y32-4k/core --server=false --jvm system -M GenerateTileCore -- NEW_OUTPUT_DIR 41 41 41
```

按归档generation-result.json的concat_order，以一个额外换行连接四个特化片段，逐SHA匹配后才可覆盖安装；不要用无分隔的shell cat或默认48参数替代选定版本。原始工具/时钟/运行命令和固件身份都在封存包中。输入恢复工具只用已发布归档，已实际恢复baseline209和A/B各243输入并重放面积审计。

本轮临时VNC设置已原生读回核验：SendCutText恢复0，自有manager292673已退出；辅助连接已关闭。后续优先处理已定位的时序违例、覆盖/CDC/复位契约和官方面积计价；新实验截止2026-11-11 23:59上海，不能把本轮面积选型当作这些缺项已经通过。
