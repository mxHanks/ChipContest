# xu S1 服务器 VCS 开发验收（2026-11-03 归档）

两条独立 S1 分支均在服务器完成八步 VCS 开发验收：host、numeric、12 层固定向量核算、doctor、5 个 legacy 用例、synthetic1、synthetic2、real12。原始执行时间为 2026-11-02；本目录于 2026-11-03 收取、独立复核并归档。两份原始 state 的结论均为 `VCS_ACCEPTED_NOT_RETAINED`，原始 acceptance 为 `PASS`。

这里沿用既有开发窗口；两条源码/固件均没有新增正式任务前全量清空流程。候选各自的正式 clear/request 窗口尚未建立，原 S0 的 clear/activity 证据不能直接标到 S1 上。本记录支持功能、固定工作量和周期比较；没有资格、正式吞吐、能量、面积、时序闭合、保留或得分结论。

## 冻结身份与实现

| 配置 | 主仓提交 | E203 子仓提交 | 固件 schedule |
| --- | --- | --- | --- |
| frozen combined 基线 | `ac85d6ae00db4fab8ba397753df1a3565c60f31f` | `f49a5fc914971426bd4530db39e270a84b41139f` | `bias-hw-window` |
| S1 H2-only | `23992eb77f2c42eaeefbe7dcbdb682aba1ef2b78` | `434628c1525931c15dfaf06b5586118eb530ccba` | `bias-dtcm-window` |
| S1 SRAM bias | `b6f5075e79eff9c14267e1ef97d90b9f8e82f23a` | `eee41507965d562066af3335192e3ef93ef36d31` | `bias-hw-window` |

H2-only 分支为 `codex/xu-s1-h2-only`，实际分叉主仓 `e998479`；SRAM 分支为 `codex/xu-s1-sram-bias`，实际分叉主仓 `da359af`。子仓都从 `f49a5fc` 分叉。对比当前 frozen `74e0118` 时，主源码/固件基础相同；整棵主仓也包含分叉后才加入的其他 S0 文档差异，不能把那些缺失记录解释为候选删除实现。

实际修改的 Chisel **主源码**：

- H2-only：`src/main/scala/GenerateRTL.scala`、`src/main/scala/linear/LinearCachedCore.scala`。测试修改 `src/test/scala/linear/LinearCachedCoreTest.scala`。
- SRAM：`src/main/scala/GenerateRTL.scala`，新增 `src/main/scala/linear/BiasSramCache.scala`、`src/main/scala/linear/LinearSramCachedCore.scala`。新增测试为 `src/test/scala/linear/BiasSramCacheTest.scala`、`src/test/scala/linear/LinearSramCachedCoreTest.scala`。

H2-only 在 elaboration 时移除完整 bias cache，保留结果窗口，CAP 为 `0x58550002`；旧 cache 地址读零、写无副作用。子仓只改 `rtl/e203/perips/LinearCachedCore.sv` 和 `accel_icb_slave.v`。SRAM 以同步读 bias 存储和预取 tile 代替寄存器 bias bank，CAP 保持 `0x58550003`；子仓新增 `BiasSramCache.sv`、`LinearSramCachedCore.sv`、`mem_32x40.sv`，并改 wrapper。完整变更路径及哈希见 `git-source-audit.json`。

signed16 X/W、signed40 bias、signed48 Y、8 PE、数值格式、固定向量和共享槽格式保持原定义。独立只读复核检查了已有生成目录：H2 的 11 份 SV、SRAM 的 13 份 SV 均与子仓提交一致；默认生成目标分别 12/12、10/10 仍与 frozen 子仓一致。此次归档没有重新生成 RTL。

## 十二层实际周期

三组均使用服务器同一 SiFive GCC-Metal **10.2.0-2020.12.8**、VCS **Q-2020.03-SP2-6_Full64**、`-O2 / both-unroll-no-masks`。候选 TB 使用 HF `always #2` 的 4ns 时钟；选用 frozen `reference4ns-real12` 基线，使旧 inclusive 窗口和时钟一致。基线 reference 与 macro 两种完整 SoC 运行的每层输出、周期和全部 PERF 计数相同，原证据位于 [`functional-server-02`](../xu-score-s0-soc-20261102/functional-server-02/README.md)。其 16,510,344 周期也与独立 [`nominal150-server-03`](../xu-score-s0-soc-20261102/nominal150-server-03/README.md) 的周期结果一致；此处不将 4ns 运行时间换算成 150MHz 正式性能。

| 层 | frozen combined | H2-only | H2 增量 | SRAM bias | SRAM 增量 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 1,375,864 | 1,932,768 | +556,904 | 1,403,752 | +27,888 |
| 1 | 1,375,860 | 1,932,770 | +556,910 | 1,403,754 | +27,894 |
| 2 | 1,375,864 | 1,932,770 | +556,906 | 1,403,754 | +27,890 |
| 3 | 1,375,860 | 1,932,770 | +556,910 | 1,403,754 | +27,894 |
| 4 | 1,375,864 | 1,932,770 | +556,906 | 1,403,754 | +27,890 |
| 5 | 1,375,860 | 1,932,770 | +556,910 | 1,403,754 | +27,894 |
| 6 | 1,375,864 | 1,932,770 | +556,906 | 1,403,754 | +27,890 |
| 7 | 1,375,860 | 1,932,770 | +556,910 | 1,403,754 | +27,894 |
| 8 | 1,375,864 | 1,932,770 | +556,906 | 1,403,754 | +27,890 |
| 9 | 1,375,860 | 1,932,770 | +556,910 | 1,403,754 | +27,894 |
| 10 | 1,375,864 | 1,932,770 | +556,906 | 1,403,754 | +27,890 |
| 11 | 1,375,860 | 1,932,770 | +556,910 | 1,403,754 | +27,894 |
| 合计 | **16,510,344** | **23,193,238** | **+6,682,894** | **16,845,046** | **+334,702** |

H2-only 窗口增加 **40.477012%**；SRAM bias 增加 **2.027226%**。每组均逐项通过 **304,128 个输出 / 608,256 个 Y 写回字**。固件 mcycle 合计分别为 16,511,202 / 23,194,293 / 16,845,909，保留其不同前后开销，不能替代上述窗口。

| 十二层阶段/工作量 | frozen combined | H2-only | SRAM bias |
| --- | ---: | ---: | ---: |
| W 装载 | 3,587,388 | 3,591,779 | 3,587,378 |
| X 装载 | 1,378,968 | 1,379,256 | 1,379,267 |
| bias 装载 | 93,312 | 6,627,180 | 93,312 |
| 计算/等待 | 2,623,104 | 2,623,104 | 2,699,136 |
| 写回 | 7,830,708 | 7,821,792 | 7,822,977 |
| 其他 | 996,864 | 1,150,127 | 1,262,976 |
| MMIO 写 | 668,640 | 1,571,784 | 668,640 |
| MMIO 读（实测） | 912,384 | 912,384 | 950,400 |
| shared 读 / 写 | 278,784 / 608,256 | 相同 | 相同 |
| START / done | 38,016 / 38,016 | 相同 | 相同 |
| busy / MAC 有效拍 | 2,585,088 / 2,433,024 | 相同 | 2,661,120 / 2,433,024 |

六阶段严格覆盖每层窗口。H2 的 DTCM bias 调度每次计算仍上传八路 bias，因而 bias 装载和 MMIO 写增加。SRAM 每 START 多两拍固定预取延迟，实测每层 busy `3,168×70=221,760`，比基线 `3,168×68=215,424` 多 6,336。`prefetches=3,168` 和额外 busy 为固定契约推导值，实测 busy 独立验证；轮询和共享背压导致总周期增量还包含其他阶段变化。

## 独立复核与证据范围

`check-evidence.py` 默认只读，重放 frozen 分支的原 `check_log`、`check_performance` 和 SRAM 固定延迟检查：

- 原传输包 **23,644 字节**，SHA-256 `96824ca873915a9c1bcb27d407c6dcd1e03d4d3ae6b94f7dbc8ef5a5cd2e3e5f`。它含 54 个 payload 加 1 个 manifest，共 55 个 regular member；逐个长度、SHA 和归档副本均一致。
- 两条八步 acceptance 均 PASS；H2 host **49** 项、SRAM host **50** 项，numeric 各 **42** 项。host 原文中的 `FAIL: /tmp/...` 来自故意破坏的负例夹具，最终 unittest 均为 `OK`，未改写这些输出。
- synthetic1、synthetic2、real12 共六次运行逐层重新解析，核对所有计数、事务契约、六阶段和输出总量；SRAM 三次运行均显式 `--bias-storage sram`，独立固定 busy 延迟通过。39 个实际日志破坏案例全部被拒绝。
- H2 **151**、SRAM **154** 个实际报告的 RTL/TB SHA 与对应主仓/子仓 Git blob 逐项一致；另核对 frozen runner、contract、固件源和实际编译命令。`frozen-git-sources/` 无损保存这些已核对源码以及所改 Chisel 和原 acceptance runner，便于离线重复检查。
- 两候选的 fixture 和 48 个 real 向量声明哈希与冻结样本一致；本地从固定向量 archive 独立重算 12 层全部 304,128 个整数 XW+b 输出。该结果是该 silence 样本的整数一致性，不能代表 600 样本浮点 NRMSE。
- SRAM 与 frozen combined 的固件源码和装载镜像哈希相同；镜像 SHA 为 `6e22a1bffbd74c5cfc9b6d8603ce71a9f413ec5d2aea5df8bf792b922461e4e1`。H2 镜像为 `67b929840a55ac7d030d035eb8dd721ffcbff71199ffdd7b735338e714c3fd4d`。全部 ELF/模拟器声明身份保存在原 result 和 `comparison.json`。

本次紧凑传输没有带回固件/模拟器二进制、服务器实际向量文件和部分 build/version 日志，故对应哈希是原报告的记录身份；没有声称对缺失字节重新计算 SHA。已带回的每份 simulation/build/sections/symbols 日志均与 result 声明哈希相同；缺失列表逐次保存在 `comparison.json`。源码快照来自可验证的冻结 Git blob，与原报告绑定。原始服务器绝对路径、版本信息、时间戳及日志字节全部保留。

H2 没有完整 bias cache，旧 S0 对 cache 的物理清空观测不再适用。SRAM contents 与 tile 没有 reset 清零；每次 cached START 的 tile 预取保证计算读取本组数据，不等于任务前完成物理清空。正式 candidate-specific clear/activity 证据仍待后续工作。

## 复现

原始八步命令完整保存在 `raw/server-export/*/state.json` 和 `acceptance/acceptance.json`。`reproduce-acceptance.py` 将这些参数仅映射到指定 frozen checkout、新输出目录和工具链位置；先检查主/子仓 HEAD。默认打印命令，加 `--run` 才执行。输出目录必须尚不存在。

```bash
python3 docs/validation/xu-score-s1-server-20261103/check-evidence.py

python3 docs/validation/xu-score-s1-server-20261103/reproduce-acceptance.py \
  --candidate h2 --source /home/mxhanks/Projects/ChipContest-xu-s1-h2-only \
  --out /tmp/xu-s1-h2-reproduce
python3 docs/validation/xu-score-s1-server-20261103/reproduce-acceptance.py \
  --candidate sram --source /home/mxhanks/Projects/ChipContest-xu-s1-sram-bias \
  --out /tmp/xu-s1-sram-reproduce
```

执行时在以上命令添加 `--run`，服务器将 `--source` 改为该分支的实际检出路径。默认 cross-prefix 是原始 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-`；更换位置时用 `--cross-prefix` 指定同版工具链。展开后的八条命令示例见 `h2-reproduction-commands.txt` 和 `sram-reproduction-commands.txt`。

H2 也可在该 frozen 分支调用 `python3 tools/scripts/server_accept.py --sim vcs --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-dtcm-window --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out "$xu_new_h2_out"`。SRAM 的 frozen `server_accept.py` 不接受也不传递 `--bias-storage`；原始验收通过定制八步命令显式附加该参数，并留下完整记录。复现 helper 保留这些实参，避免漏掉 SRAM 延迟门控。其 real12 核心命令为：

```bash
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs \
  --cross-prefix "$xu_cross_prefix" --bias-storage sram \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out "$xu_new_sram_real12_out"
```

Chisel 生成分别使用 `scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearH2OnlyCore` 和同参数的 `LinearSramCachedCore` target；生成后先与对应 frozen 子仓 SV 逐字比较。此次服务器八步 acceptance 没有重新运行 Chisel、独立 Icarus、正式 clear/activity 或候选综合/功耗流程。

`comparison.json` 保存逐层全部计数和差值，`per-layer.csv` 是周期表；`sha256.json` 绑定本目录其余所有文件。`raw/baseline-reference4ns/` 是既有 frozen 基线原文的逐字副本，`raw/server-export/` 和原传输包都保留原文。
