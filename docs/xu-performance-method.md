# xu 开发平台性能测量方法

本方法用于现有 E203 + MMIO 加速器的服务器 VCS 开发回放。硬件保持 8 PE、signed16 输入/权重、signed40 bias、signed48 结果与现有 MMIO ABI；新增计数器只在 `tests/e203/tb_accel_soc.sv` 中观察握手和计算活动，不驱动 DUT。平台接口和数值定义分别见 [接口契约](platform-interface.md) 与 [数值契约](numeric-contract.md)。每次运行的数据、代码身份和结果应在对应验证记录中保存。

## 工作负载与计时窗口

`--mode real --tasks 12` 使用历史 KWT checkpoint 的**单个静音样本夹具**，回放 12 个独立 FFN1 任务。每个任务计算 `Y[99,256] = X[99,64] × W[64,256] + bias[256]`，共 25,344 个结果、50,688 个 32 位输出写字，执行 3,168 组计算。12 任务连续运行，中间不复位；每任务重新装载权重，各层使用自己的 X，上一任务的 Y 不作为下一任务的 X。这份工作负载不能代表完整 encoder、样本集精度或官方评测。

主性能计数为 TB 的 `last_cycle - first_cycle + 1`，包含首尾两拍：

- 起点：本任务第一次共享输入/参数读命令被接受，即 `cmd_valid && cmd_ready`；当前检测地址为 `[0xA0000000, 0xA0018800)`，现有固件在其中读取 X、W 与 bias。
- 终点：最后一个 Y 写响应被接受，即 `rsp_valid && rsp_ready`，所有输出已逐字匹配整数 golden。最后写命令被接受与最后写响应退休是不同事件。

该窗口包含 CPU 指令执行、共享存储读取、MMIO 装载与轮询、计算、总线等待和输出写回。TB 文件读取、共享 RAM 预装载、ITCM 直接装载、任务间主机更换数据以及最后写回后的完成 ACK 均在窗口之外。`firmware_cycles` 是 `accel_linear()` 调用前后的低 32 位 `mcycle` 差值，含 ID/busy 检查及末尾 fence；它的起止事件与 TB 不同，应单列，不能互换。

开发共享存储为 TB 的 512 KiB 行为 RAM，最多一个未退休请求；`cmd_ready = (!rsp_valid || rsp_ready) && (cycles % 7 != 0)`。因此每逢全局周期号为 7 的倍数时禁止接受新命令，响应可独立退休。这是固定的开发背压模型，不是工艺 SRAM 的延迟或官方共享存储性能。其相位随全局周期延续，任务间不会重新从零开始。

## 阶段与旁路计数

每个窗口周期恰好归入以下一项。阶段是调度区间，包含该区间中的软件指令和总线间隙，不能解释为纯存储传输或纯运算耗时。触发新阶段的命令接受当拍归新阶段；结束响应或 `core_done` 当拍仍归原阶段，下一拍回到 `other`，同拍若接受新阶段命令则优先进入新阶段。

| 字段 | 开始或重新进入条件 | 结束条件 |
| --- | --- | --- |
| `w_load` | 共享 W 读接受，或 W_BANK/W_ADDR/W_DATA 写接受 | bank 7、地址 2047 的最后 W_DATA 写响应退休 |
| `x_load` | 共享 X 读接受，或 X_ADDR/X_DATA 写接受 | 每行地址 63 的 X_DATA 写响应退休 |
| `bias_load` | 共享 bias 读接受，或 BIAS_INDEX/BIAS_LO/BIAS_HI 写接受 | 每组 index 7 的 BIAS_HI 写响应退休 |
| `compute_wait` | busy=0 时 CTRL.bit0=1 的 START 写接受 | `core_done`，不延长到软件轮询读到 done |
| `writeback` | RESULT_INDEX 写接受 | 每组第 8 个结果的高 32 位 Y 写响应退休 |
| `other` | 窗口中未归入上述阶段的周期 | 后续阶段开始 |

TB 维护与单槽响应对应的结束标记，先处理旧响应退休，再记录同拍接受的新命令。每任务检查六阶段之和等于窗口周期数；各阶段比例为 `phase_cycles / cycles`。

以下计数与阶段区间**重叠**，不能再与六阶段相加：

| 字段 | 含义 |
| --- | --- |
| `busy` | 窗口内 MMIO 从机 busy 为 1 的周期数 |
| `mac_fire` | 8 个 PE 共享 enable 为 1 的周期数；每拍执行 8 个 signed16 MAC |
| `starts` / `dones` | 被接受的有效 START 数 / `core_done` 周期数 |
| `mmio_reads` / `mmio_writes` | 加速器 MMIO 读/写命令接受次数 |
| `shared_reads` / `shared_writes` | 开发共享存储读/写命令接受次数 |
| `mmio_stall` / `shared_stall` | 相应端点出现命令 valid 且非 ready，或响应 valid 且非 ready 的周期数；同端点同拍两者均阻塞也只计一次 |

当前固定调度每任务应有 3,168 次 START/done、202,752 个 `mac_fire` 周期、73,408 次共享读与 50,688 次共享写。读数由 W 16,384、X 6,336 和各组反复读取的 bias 50,688 次组成。`busy` 是从机状态观测，`compute_wait` 还计入接受 START 的那一拍，二者边界不同。

## 吞吐、峰值与频率换算

令 `C` 为任务实测窗口周期，`f` 为条件换算频率（Hz），`M = 99 × 64 × 256 = 1,622,016 MAC`。采用 1 MAC = 2 ops 的口径，bias 初始化不另计 op：

| 指标 | 公式 |
| --- | --- |
| 条件任务延迟 | `C / f` 秒 |
| 条件任务吞吐 | `f / C` 任务/秒 |
| 条件有效计算吞吐 | `M × f / C / 10^9` GMAC/s；GOPS 为此值的 2 倍 |
| 8 PE 理想峰值 | `8 × f / 10^9` GMAC/s；仅指每 PE 每拍一个 MAC 的算术上限 |
| 端到端吞吐相对峰值 | `M / (8 × C)` |
| MAC 活跃占比 | `mac_fire / C`；只有实际计数通过检查后才报告为活动测量 |
| busy 占比 | `busy / C` |

当前每个有效 MAC 拍均为 8 PE 同时工作，所以 `mac_fire × 8 = M`，实测 MAC 活跃占比应与端到端吞吐相对峰值一致。纯 MAC 理想周期为 202,752，尚未计入控制状态、软件及数据搬运。多任务汇总使用总 MAC 数除以总周期，不对各层吞吐作算术平均；12 任务的总延迟是各测量窗口之和，不含被排除的任务间主机装载时间。

默认以 **150 MHz 作条件换算**，理想峰值为 1.2 GMAC/s（2.4 GOPS）。该频率不是本方法已经证明的物理工作频率：TB 外部时钟周期为 4 ns，当前 PLL bypass 路径使 CPU 与加速器使用同频 hfclk，这只说明开发仿真的时钟关系。150 MHz 时序闭合须另有源文件、库、PVT/RC 和约束一致的综合/时序证据。VCS 日志的主机 CPU time 是仿真成本，不是芯片任务延迟。

本方法不提供 CPU-only 加速比、功耗或能效：尚无同口径 CPU-only 对照，也未用覆盖 CPU、互连和存储的活动数据完成该范围的功耗分析。已有周期回放不替代这些测量。

## 服务器复现与结果保存

以下为 **Bash** 示例，从独立工作副本执行。`xu_run_out` 必须是尚不存在的新目录，报告输出文件也必须不存在；重复实验应更换名称。

```bash
xu_eval_root=/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex
xu_rv_prefix="$xu_eval_root/sifive-rv32-c/bin/riscv64-unknown-elf-"
xu_run_out="$xu_eval_root/xu-performance-fresh-01"
cd "$xu_eval_root/ChipContest"

python3 tools/scripts/e203_soc.py --sim vcs --mode real --tasks 12 \
  --cross-prefix "$xu_rv_prefix" --out "$xu_run_out"

python3 tools/scripts/xu_perf_report.py \
  --result "$xu_run_out/result.json" --frequency-mhz 150 \
  --out "$xu_run_out/performance-150mhz.json"
```

仅当第一条命令成功且 `result.json` 为 real/PASS 时生成性能摘要。`simulation.log` 保留有序 `TASK_PASS`、`PERF_TASK` 与 `SOC_PASS`；运行器检查结果/写字总数、各阶段求和、MAC 数及事务数。摘要记录原始 result 文件的 SHA256 和频率的条件属性。应一起保存 `result.json`、`simulation.log`、构建/版本日志和摘要，代码变动时按运行文件哈希识别执行版本。

运行器和摘要脚本仅需 Python 标准库，兼容服务器 Python 3.6；不需要 TensorFlow 或重新导出夹具。服务器已验证的环境和工具链来源见 [服务器验收记录](validation/platform-vcs-20261101/README.md)。复现此前服务器周期应继续使用 **SiFive GCC-Metal 10.2.0-2020.12.8 CentOS6** 的原发行二进制/头文件子集，以及对应 VCS 环境。该子集仅支持本工程 freestanding 固件，不代表完整 SDK/Newlib。

RISC-V GCC/binutils 的版本会影响固件指令、调度和最终周期，即使 C 源、RTL 和数值结果相同也可能产生不同性能。不得将本机其他 GCC 版本的周期与服务器数字混为同一基线。运行器记录交叉编译器版本、固件 ELF/镜像、向量、TB/RTL 和运行脚本哈希；核对这些身份后再比较。主机 GCC/g++ 用于构建仿真器，与生成 RISC-V 固件的交叉编译器应分别记录。
