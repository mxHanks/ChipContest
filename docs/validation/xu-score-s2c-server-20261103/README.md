# xu S2c 自动分组与结果 FIFO：服务器验收

冻结主提交 **`d276b55ffecbe8d620f9a361bf5d0859299ba7b5`**、E203 子提交 **`49a9436e01ea8ceeead94242e4a99c16e31a0865`** 在原服务器通过三个强制 direct VCS、八步开发验收和同 RTL packed-control-real12。自动分组实际12层总周期 **11,842,200**，同 RTL packed 对照 **14,532,449**，减少 **2,690,249（18.512014045258304%）**。两次均检查全部 **304,128** 个输出与 **608,256** 个 Y 写字。该结果是开发平台完整 VCS 验收，尚不能作为比赛资格、能耗或最终得分结论。

## 改了哪些 Chisel

相对 S2b `a2a1f076`，生产 Chisel 恰好两个文件：

- `src/main/scala/GenerateRTL.scala`：增加可选 `LinearAutoGroupCore` 生成器入口，默认生成器保持原样。
- 新增 `src/main/scala/linear/LinearAutoGroupCore.scala`：复用原 `LinearComputeCore` 和 `BiasBankCache`，增加一行内 group 0..31 自动调度，以及两槽、每槽8×48位结果 FIFO。仅在 POP 响应退休时释放 head；FIFO满则阻止继续启动计算，结果读回可与下一组计算重叠。

另增测试 `src/test/scala/linear/LinearAutoGroupCoreTest.scala`；生成的新 RTL 为 `third-party/e203_hbirdv2/rtl/e203/perips/LinearAutoGroupCore.sv`。手写 `accel_icb_slave.v` 增加 AUTO_CAP、STARTROW、STATUS、POP 和结果 FIFO 窗口，固件逐行启动并消费32组结果。原8PE、signed16 X/W、signed40 bias、signed48结果、32KiB逻辑 W、共享槽和固定向量保持；尚未增加 PE、双 X bank 或 DMA。

初次主 `0d1f6e9f1b0b6efb2207f99fcef78597855eb5c0` / 子 `dd149bb34aa1c3feca066ffbf9bdd3311f4b954c` 的 direct-autogroup VCS 编译实际失败：`row_start_accept` 引用的五个信号尚未声明，共5个 `Error-[IND]`。原失败 state 和 compile log 原文保留在 `raw/s2c-accept-01/`。最终子提交 `49a9436` **只移动完全相同的四行 wire 初始化声明到输入定义之后**；检查器逐字验证移除该块及新增分隔空行后，其余 wrapper 字节相同。没有改变条件或 Chisel。成功验收绑定新主/子，不重新标记原失败目录。

## 实际十二层比较

| 层 | 同 RTL packed 周期 | 自动分组周期 | 自动分组减 packed |
| --- | ---: | ---: | ---: |
| 0 | 1,211,034 | 986,850 | -224,184 |
| 1 | 1,211,035 | 986,850 | -224,185 |
| 2 | 1,211,038 | 986,850 | -224,188 |
| 3 | 1,211,038 | 986,850 | -224,188 |
| 4 | 1,211,038 | 986,850 | -224,188 |
| 5 | 1,211,038 | 986,850 | -224,188 |
| 6 | 1,211,038 | 986,850 | -224,188 |
| 7 | 1,211,038 | 986,850 | -224,188 |
| 8 | 1,211,038 | 986,850 | -224,188 |
| 9 | 1,211,038 | 986,850 | -224,188 |
| 10 | 1,211,038 | 986,850 | -224,188 |
| 11 | 1,211,038 | 986,850 | -224,188 |
| 合计 | **14,532,449** | **11,842,200** | **-2,690,249** |

十二层均实际运行，未用一层乘12代替。两种 schedule 的主/子、152个实测 RTL/TB 源、runner、contract、固件源、工具版本、固定 fixture、48个向量声明哈希、模拟器声明 SHA 和优化参数逐项相同；schedule分别为 `bias-hw-pack32-window` / `bias-hw-autogroup-window`。工具链为同一 **SiFive GCC-Metal 10.2.0-2020.12.8**、**VCS Q-2020.03-SP2-6_Full64**、`-O2 / both-unroll-no-masks`。

| 十二层阶段/工作量 | packed | 自动分组 | 差值 |
| --- | ---: | ---: | ---: |
| W 装载周期 | 2,202,069 | 2,202,036 | -33 |
| X 装载周期 | 854,170 | 853,008 | -1,162 |
| bias 装载周期 | 93,276 | 93,288 | +12 |
| compute/wait 阶段周期 | 2,623,104 | 539,352 | -2,083,752 |
| 写回阶段周期 | 7,803,382 | 7,996,440 | +193,058 |
| 其他阶段周期 | 956,448 | 158,076 | -798,372 |
| MMIO 读 | 912,384 | 655,776 | -256,608 |
| MMIO 写 | 260,808 | 185,964 | -74,844 |
| shared 读 / 写 | 278,784 / 608,256 | 相同 | 0 |
| START / done | 38,016 / 38,016 | 相同 | 0 |
| busy / MAC 有效拍 | 2,585,088 / 2,433,024 | 相同 | 0 |
| shared 背压周期 | 103,913 | 143,736 | +39,823 |

六阶段互斥且逐层总和等于窗口；`compute_wait` 不是全部计算周期。auto每层99行、3168次已退休 POP、计算与写回重叠157,014周期、FIFO满等待484,210周期，均来自实际 AUTO_TASK。重叠不能再加到窗口或阶段之和中。固件 mcycle 合计 packed为14,533,218、auto为11,843,041，单独保留，不替代硬件窗口。`per-layer.csv` 和 `comparison.json` 保存逐层全部计数。

## 验收与独立复核

三个 mandatory direct VCS 均有完整 compile/simulation 原文及声明 SHA：autogroup rows/groups/lanes=2/64/512、overlap=958、launches/dones=99/99、accepted/retired=11719/11719；packed计数9653/9653/16457次内部写/W16390/X67/33次start；stream计数17828/17828/16454次写/W16387/X67/33次start。三者不能由辅助测试skip替代。

九步顺序为 host、numeric、vectors、doctor、baseline、synthetic1、synthetic2、real12、packed-control-real12。host报告 Ran57、skipped3（54项执行，三个 Icarus 辅助测试跳过），numeric42项通过，cached辅助测试另有实际 VCS `accepted=retired=4909` 日志；host原文中的预期错误来自拒绝测试，最终 unittest 为OK。baseline五程序为 `rv32ui-p-add / accel_mmio / accel_compute / accel_multigroup / accel_repeat_x`。Chisel没有在该服务器验收运行，不能把本地历史 Chisel 结果算作这里的服务器步骤。

`check-evidence.py` 已实际运行：123个唯一选中 raw 的路径、长度、SHA逐项匹配完整239项原始manifest；冻结源 archive 215项摘要全部匹配；各次SoC实测152个源、runner/contract/固件源与冻结字节逐项相符，完整部署manifest为2384项。四次SoC运行（synthetic1/2、真实12层、同RTL packed真实12层）全部TASK/PERF/SOC/AUTO和声明运行日志摘要重验。注入64种缺失/重复TASK、PERF、SOC、AUTO，错误MMIO/shared/MAC/START/done计数、少一次POP、零重叠或FATAL，全部拒绝。从仓库固定 `kwt-silence-v1` archive 独立重算304,128个 XW+b 整数结果，并核验fixture及48个张量声明摘要。原始比较文件的两份result SHA、全部逐层差值、总和与百分比独立重算一致。

另用 `check-integrity-negatives.py` 在临时副本分别改动raw字节、添加raw文件、改选中摘要、改冻结源摘要、重复export路径和改主提交，六次均因各自预期的完整性错误被拒绝。`integrity-negatives.json`保存实际拒绝原因，原文件没有修改。

原传输 archive：**95,472 bytes**，SHA256 **`5cb9b56becb29d139e5db62a5d3a7d203f14355130126b534e1135eaedb35bcc`**。本目录选择123个相关原文件，保留原时间、绝对路径、错误和空白，未拼接同名截断日志。`sha256.json`覆盖其余交付文件；`audit.log`记录只读复核输出。

未取回服务器 ELF、装载镜像、模拟器二进制或实际服务器向量字节；其SHA是原始结果记录的身份，不声称本地重新哈希这些二进制。仓库固定向量原 archive 已独立核验。TB为4ns HF/66ns LF，窗口为首shared读**接受**到最终Y响应退休，预装载和能力探测在窗口外；候选正式物理clear、首请求窗口、150MHz映射等价/STA及全SoC任务能耗仍需另测。该真实样本12层夹具不是官方600样本精度验收；同库PPA另存，不在此拼接评分，也未决定保留候选。

## 复现命令

根仓库离线复核，派生输出可写到临时目录：

```bash
python3 docs/validation/xu-score-s2c-server-20261103/check-evidence.py \
  --out /tmp/xu-s2c-recheck.json --csv /tmp/xu-s2c-recheck.csv
python3 docs/validation/xu-score-s2c-server-20261103/check-integrity-negatives.py
```

服务器须独立 checkout 上述冻结主/子，并使用同版本工具链；所有输出目录必须全新。原cross-prefix如下，`xu_new_s2c_out`须改为新的绝对路径。三个direct的精确argv也在 `raw/s2c-accept-02/direct-*-vcs/compile.log` 首行，运行目录及二进制argv在simulation.log首行。以下命令显式执行三个后端及两种schedule：

```bash
set -e
xu_cross_prefix=/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-
xu_new_s2c_out=/absolute/new/xu-s2c-reproduction
xu_source="$PWD"
xu_modules=(BiasBankCache.sv LinearAutoGroupCore.sv LinearCachedCore.sv \
  LinearComputeCore.sv DotProductEngine.sv MacController.sv MacPEArray.sv \
  MacPE.sv XRowBuffer.sv WeightBankArray.sv WeightBank.sv Sram1024x16.sv \
  mem_1024x16.sv accel_icb_slave.v)
for xu_kind in autogroup packed stream; do
  xu_direct="$xu_new_s2c_out/direct-$xu_kind-vcs"
  mkdir -p "$xu_direct"
  xu_inputs=("$xu_source/tests/e203/tb_xu_${xu_kind}_wrapper.sv")
  for xu_module in "${xu_modules[@]}"; do
    xu_inputs+=("$xu_source/third-party/e203_hbirdv2/rtl/e203/perips/$xu_module")
  done
  vcs -full64 -sverilog -timescale=1ns/10ps -top "tb_xu_${xu_kind}_wrapper" \
    +define+DISABLE_SV_ASSERTION=1 -Mdir="$xu_direct/csrc" \
    -o "$xu_direct/simv" "${xu_inputs[@]}" >"$xu_direct/compile.log" 2>&1
  "$xu_direct/simv" >"$xu_direct/simulation.log" 2>&1
done
env XU_WRAPPER_SIM=vcs XU_WRAPPER_LOG_DIR="$xu_new_s2c_out/host-wrapper-vcs" \
  python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-hw-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out "$xu_new_s2c_out/autogroup"
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs \
  --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-hw-pack32-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out "$xu_new_s2c_out/packed-control-real12"
```

命令成功仍须核对各日志、源身份、配置、全部工作量和两次实际12层结果；stdout末尾PASS不足以替代这些检查。原部署全部步骤argv在 `raw/s2c-accept-02/state.json`。含clone/fetch及2384源校验的冻结部署脚本在 `frozen-git-sources.tar.xz` 的 `deployment/launch.py`；其增量bundle依赖原服务器 `ChipContest-s2c-01`，此证据archive不包含这些bundle。
