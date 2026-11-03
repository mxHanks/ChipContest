# xu S2d 同库全 SoC 综合面积与原始时序报告

状态：**EVIDENCE_CHECKED_NOT_QUALIFIED**。服务器实际 DC/PT 已完成，能确认同库加速器面积为 **0.303630271 mm²**，占 2.25 mm² 上限的 **13.49%**。全数字 SoC cell area 为 **3.374602731896 mm²**；此数包含固定 CPU、ITCM/DTCM、共享 RAM 等，不是比赛加速器面积。`report_area` 的 `Total area: undefined` 仍保留，未将 cell area 宣称为布局后 core/die area。

实际源码为主仓 `3af4db98b893edd2103771fa132d69350b82ba96`、子仓 `dd692c190dadafd9baa6dffe8514a3f684e7fbf5`，工具 producer 为 `cf836cf677d120d046d366c4b4b0a0bc33ba48ff`。本批使用独立目录 `s2d-ppa-campaign-20261103-02`，原目录 `-01` 的 CLI 失败完整保留。首批工具已实现 Python profile，但 CLI 的显式 choices 遗漏 `s2d-doublebuf`，因此在启动 DC 前报 invalid choice；修复后新目录重跑，不能将首批记录改成成功。

S2d 的实际硬件改动是此前的 `src/main/scala/GenerateRTL.scala`、新增 `src/main/scala/linear/LinearBufferedComputeCore.scala` 与新增 `src/main/scala/linear/LinearDoubleBufferCore.scala`。它在单 8 PE、单份 32KiB W 存储上增加两份 X bank、行描述符和结果 FIFO 调度，保持旧 auto 通路供同 RTL 对照。对应子仓精确允许 delta 为 `LinearAutoGroupCore.sv`、`LinearBufferedComputeCore.sv`、`LinearDoubleBufferCore.sv` 和 `accel_icb_slave.v`。本证据提交没有新增 Chisel 或改动硬件。

同一服务器 SS 工艺库的 SHA 仍为：标准单元 `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723`、RAMSP1024×16 `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`；未引入 bias 专用宏库。实际 DC pre/post 和 PT link 后的宏标记均核对为 ITCM 32、DTCM 32、shared 256、W 16，合计 **336 个宏**。W 逻辑与物理容量均为 32KiB，没有新增 W padding。

`area.rpt` 中 `u_accel_icb_slave` 整个层级为 **303630.2710 μm²**，包含 wrapper、调度、偏置/X/结果缓冲、计算单元和 W 宏；全 SoC 总 cell area 为 **3374602.731896 μm²**。相对同库 S2c 的 0.294801838 mm²，S2d 面积增加 **2.9947%**。此前独立完整 VCS 验收的真实 12 层周期为 11859141，同 RTL auto 对照为 11842200，S2d 多 16941 周期、慢 0.143056%；逐层和原始日志见 [S2d 完整服务器性能证据](../../xu-score-s2d-server-20261103/README.md)。本候选目前没有吞吐或面积优势，全 SoC 单任务能量尚未测定，不能据此声称最终 Pareto 去留。

本批原始 SDC 为完整 envelope 约束 SHA `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`，PT 仍使用未做 CTS 的 propagated clock 分析。原 setup slack **−20.981373 ns**、hold **−22.642344 ns** 均保留；不将这些路径当作已经完成后续时钟/CDC/hold 修复的结果，也不因此宣称架构不可能在 150MHz 工作。其完整 analysis coverage 为总 314592、met 246839、violated 40790、untested 26963，其中：

| 检查 | violated | untested |
|---|---:|---:|
| setup | 22172 | 3654 |
| hold | 11956 | 3652 |
| recovery / removal | 0 / 737 | 2 / 0 |
| min period / pulse width | 0 / 5756 | 10416 / 9239 |
| clock gating setup / hold | 25 / 3 | 0 / 0 |
| output setup / hold | 141 / 0 | 0 / 0 |

本批 `check-timing.rpt` 直接报告 **24 个 UART latch E 无时钟**，不沿用旧批次的 696 统计。原 collector 的 `report_exceptions -verbose` 在当前 PT 中不支持，`Error: unknown option '-verbose' (CMD-010)` 原文保留。DC/PT 退出码为 0 和完成 marker 只证明工具执行；本批仍不满足完整 150MHz 资格。

mapped netlist 的服务器执行 receipt 为 SHA **`025240541e4c58318c9fa44e816b54cbcc78f29cd8b5ea8672343a3840118137`**。本归档未复制 `mapped.v`、`mapped.sdc` 或商业 DB 字节，因此不能将 receipt 身份称为本地重新计算该文件的哈希。S2d 专用综合前后等价、候选完整 150MHz 和全 SoC 单任务能量不由本归档证明；后续结果须使用独立原始证据。

证据来源及边界：

- export15 整包 **603824 B**，SHA-256 **`75d76d05b6492ebc79442b51c90bb9a1fe2b8cae39fa866747f17ecafe61cf98`**。只选择其中 S2d terminal 的 52 个原始 payload，共 32484937 B；DRC 修复作业属于其他实验，不混入本批。
- export12 选择原 S2d CLI 失败的 3 个文件；export13 选择实际 S2d prepared RTL 的 18 个文件。这些文件都先按各自原 manifest 独立核验，再与本批 final prepared source hash 比较。未复制 PE32 dc.log 或其他候选文件。
- `selected-manifest.json` 保存 73 个选中原始文件的 SHA/长度、各自来源和 9 个 producer 自有资产的 Git 对象内容身份；三份原 manifest 保留原文并由 checker 固定其 SHA。原始空白和错误文本未改动。
- final prepared 总计 155 个源文件：153 个平台源文件，加两个 full-SoC top/shared 源文件。本地候选完整 1423 个主仓 blob、1068 个子仓 entries 和 153 项平台 manifest 均核对通过；其中 18 个服务器实际 prepared 源文件有本地原始字节，其余 137 项由服务器 prepared receipt 记录，不宣称已全部导回。本地源码一致性不能替代映射等价。
- `execution.json` 中 29 项本地已导回 report receipt 的 SHA/长度通过。未导回的 4 项报告仍列在 `review.json`，包括约 293MB 的 clock constraints 和约 14MB 的 violations；它们只有服务器 receipt，不能宣称已本地重算。主要 coverage/setup/hold/area 和实际 DC/PT logs 已完整导回。
- `check_evidence.py` 固定原 manifest 和 producer 的身份，核验源 freeze、库、宏几何、Tcl/source list、实际完成 marker、report/log SHA、面积和时序失败；11 个实际损坏/重签 manifest 的负向检查均拒绝。结果见 `review.json`，不输出资格 PASS。

本地复核（`--out` 要求新文件；不传 `--out` 只输出审查结果）：

```bash
python3 docs/validation/xu-score-s0-soc-20261102/s2d-area-server-20261103/check_evidence.py \
  --candidate /home/mxhanks/Projects/ChipContest-xu-s2d-doublebuf --self-test
```

如要同时重算整包哈希，增加 `--archive15 /absolute/ppa-drc-export-15.tar.xz`。不提供 `--candidate` 时仍可独立核验归档原始文件与固定身份，输出会明确 `local_candidate: null`，不会声称当前工作树再次通过。

服务器同库复现（在 producer `cf836cf` checkout 运行，输出目录必须新建，DB 留在服务器）：

```bash
xu_src="$HOME/Desktop/xu-score-optimization-20261102/ChipContest-s2d-01"
xu_run="$HOME/Desktop/xu-score-optimization-20261102/s2d-ppa-reproduce-new"
xu_std="$HOME/Desktop/xu-work/xu-libs/xu-ss-extract/S40/smic/SCC40NLL_VHSC40_RVT_V0.1/SCC40NLL_VHSC40_RVT_V0p1/liberty/1.1v/scc40nll_vhsc40_rvt_ss_v0p99_125c_basic.db"
xu_ram="$HOME/Desktop/xu-work/xu-libs/xu-ramsp1024x16-ss-0p99v-125c.db"
python3 tools/ppa/xu_soc_implementation.py --root "$xu_src" --profile s2d-doublebuf \
  --out "$xu_run/implementation" \
  --standard-cell-db "$xu_std" \
  --standard-cell-sha256 f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723 \
  --sram-db "$xu_ram" \
  --sram-sha256 c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f
python3 tools/scripts/xu_soc_ppa.py prepare --root "$xu_src" \
  --implementation "$xu_run/implementation/implementation.json" \
  --out "$xu_run/ppa" --allow-unqualified-mapping
python3 tools/scripts/xu_soc_ppa.py run --root "$xu_src" --out "$xu_run/ppa"
```

这组命令只复现原始 development 综合/PT 范围，结果仍须按实际日志审核；不能绕过后续映射一致性、时序、电气和全 SoC 能耗门槛。
