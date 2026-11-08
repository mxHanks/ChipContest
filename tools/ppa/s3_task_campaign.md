# S3 fresh-reset CPU/RTL campaign

这是自有 Linux 的开发功能／周期入口。每层一个新原生进程，以冻结的12层夹具逐层映射到单任务 `layer_00`；记录原层号与全部原始tensor SHA。它不是 mapped、STA、SRAM内部功耗或官方缓存政策验收入口。

在已加载 VCS 的独立目录运行；CPU affinity、nice和内存上限由外层控制器设置。输出目录必须不存在：

```bash
python3.12 -E -B tools/ppa/s3_task_campaign.py \
  --repo /absolute/frozen-S3-repo \
  --out /absolute/new-campaign \
  --bias-kind sram \
  --schedule bias-hw-autogroup-y32-packed16-nice-window \
  --layers 0,1,2,3,4,5,6,7,8,9,10,11 \
  --platform-clocks 150mhz \
  --platform-assertions
```

`--repo` 必须已经安装实际选用的 RTL。`--bias-kind` 用来核对实际能力和清空路径，不会替换硬件。寄存器控制输入应先明确安装生成的 `LinearAutoGroupCoreRegisters` 整套依赖，再选择 `--bias-kind registers --schedule bias-hw-autogroup-paired-hi-window`。这是新ABI控制配置，不能冒充原历史S2e。

显式选择 Verilator 可进行二态开发对照，同样支持 `--platform-clocks 150mhz` 和每层 fresh reset。下面的 `--repo` 可以指向不可变的基线目录；runner 始终快照该目录的输入，输出写入新的 `--out`：

```bash
python3 -E -B tools/ppa/s3_task_campaign.py \
  --repo /absolute/frozen-S3-repo \
  --out /absolute/new-verilator-campaign \
  --bias-kind sram --simulator verilator \
  --cross-prefix /absolute/riscv-toolchain/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset --layers 0
```

Verilator 复用 `--binary --timing -CFLAGS -std=gnu++20 -j 2 -Wno-fatal`，增加必需的 `--assert` 来启用原 Chisel／过程断言；`--waves` 增加 `--trace`。原厂商 SVA 仍由 `-DDISABLE_SV_ASSERTION=1` 关闭，不能与 `--platform-assertions` 同用。该入口**只有二态开发证据，不是 VCS 通过、四态未知值审计、门级或正式验收**。`plan.json` 和 `result.json` 的 `simulator_evidence` 明确记录这些边界。

## 显式启动协议

默认 `--startup-profile historical` 保持原 TB 的单次外部复位释放及计数起点。Verilator 5.032 的二态默认初始化不会产生初始 X→0 异步 reset 边沿；本设计门控 EXU 时钟下的 NICE tag FIFO 因此可能保留全零 one-hot 指针，第一条请求虽有 `wen` 仍丢失 tag。该失败不能计为 RTL 或固件优化失败，也不能忽略断言。诊断中只增加 `--x-initial-edge` 会触发本机 timing scheduler 内部错误，runner 不使用它。

`--startup-profile external-reset` **只允许 Verilator**，明确选择 `external-pad-double-reset-v1`。在原 120 时间单位首次释放后，只读等待真实 CPU `rst_core` 为 1，于下一个 HF 下降沿重新拉低外部 pad `rst_n`，保持 **120ns**；确认真实 CPU reset 已低，再释放外部 pin。预热期间出现任何 source、NICE、MMIO 或共享总线请求立即失败。没有 force、层次赋值或私有 RAM 初始化，原断言与观察器始终保留。

每层仍使用新原生进程。只有最后外部复位释放后才启动 `cycles`；真实 CPU 执行原清空配方后才进入原 payload 窗口。预热有独立 10ms watchdog，原 `--max-cycles` 超时检查保留。每个任务必须记录有序的三条 `S3_STARTUP_PROFILE`，解析器核对真实 CPU reset 的 1→0、至少 120ns 的实测低脉冲，以及 `cycle=0` 的新计数起点。`startup_configuration` 记录协议和边界，`startup_observations` 保存逐任务实测记录；对照必须使用相同启动 profile，历史结果不能与二次复位结果直接混比。

## 时钟与断言

默认 `--platform-clocks development` 保留历史 TB `#2`／`#33` 声明及其精度继承，适用于已有周期开发对照；其名义 HF250MHz、LF约15.15MHz，不能直接作为正式150MHz／32.768kHz功耗活动。

`150mhz` 只在生成 TB 的显式 seam 改时钟和精度：`timescale 1ns/1fs`、HF半周期3.333333333ns、LF半周期15258.7890625ns。生成时保留其余原文字与全部断言，并用 `$realtime` 量测实际周期。1fs下的实测舍入为：

| 时钟 | 实际半周期 | 实际周期 | 实测频率 |
|---|---:|---:|---:|
| HF | 3.333333000ns | 6.666666000ns | 150,000,015.000001490Hz |
| LF | 15,258.789063000ns | 30,517.578126000ns | 32,767.999998926Hz |

每个任务日志必须有两条 `S3_CLOCK_PROFILE`，解析器检查实际舍入与频率，不把目标频率当测量值。外部时钟刺激正确仍不证明综合网表满足150MHz。

默认断言模式延续旧开发命令的 `DISABLE_SV_ASSERTION=1`（VCS 用 `+define+`，Icarus／Verilator 用 `-D`），报告明确标为历史平台SVA关闭；Chisel和过程断言仍保留，Verilator 显式启用 `--assert`。`--platform-assertions` **仅允许VCS**，移除此define，要求完整平台RTL包含原 `general/sirv_gnrl_xchecker.v`。不改厂商SVA正文，不用Icarus或Verilator冒充完整平台SVA验证。解析器在native退出0、甚至出现SOC_PASS时，仍将VCS `Error:`／`Error `行或Verilator `%Error` 判失败。

## 清空与测量窗口

清空使用 [s3_task_clear_protocol.md](s3_task_clear_protocol.md) 的公共MMIO配方，先执行真实CPU清空，再调用SHA冻结的原main。首个真实ACCEL请求或source请求触发观察器，此后逐拍连续检查；不会因芯片根reset先释放、外设时钟尚未启动而检查未初始化同步状态，也不会等idle“变好”再放行。source先到仍因清空覆盖不全失败。

payload从首次source **request**开始，包含其接受前的等待，到最后Y写响应退休。`--first-source-stall 7` 是显式首请求等待负载；该等待必须出现在 `WINDOW_TASK`，不能用accept作为起点遗漏。`clear_cycles`与clear写数单独记录。clear后冻结main原有ABI预检另计，不能预加载本任务参数。

原数值、mask、地址／值覆盖、FIFO、POP、NICE/OITF/rd、总周期分段及最终响应检查全部保留。生成TB只插入被动清空声明、分流clear/payload observer调用、强制TASKS=1，以及显式选中的时钟精度seam；没有DUT force或私有数据写。

## 原件和资格范围

保存全部冻结源码和SHA、原12层向量身份、生成C与TB、RISC ELF／反汇编、独立模拟器、完整命令、工具版本、每层日志、clear／payload窗口及计数。RISC ELF 保持 `accel_soc`；VCS 使用 `simv`、Icarus 使用 `soc.vvp`、Verilator 使用 `verilator-obj/soc_sim`，不能让模拟器 `-o` 覆盖RISC镜像。报告同时记录 ELF 与模拟器路径及各自 SHA256。

`versions` 记录运行中的 Python、RISC GCC／objcopy／objdump、宿主 GCC 和所选模拟器；Verilator 另记录宿主 G++ 和 Make，Icarus 另记录 vvp。每个 `steps` 项保存原始 argv、工作目录、`command_sha256` 和日志 SHA256。命令 SHA 使用 argv 字符串列表的 UTF-8 JSON（`separators=(',', ':')`、`ensure_ascii=True`），保留参数边界，无 shell 拼接。失败保留原生输出，不覆盖或关闭断言重试。

`DEVELOPMENT_PASS_POLICY_PENDING`只表示该冻结配置的开发功能／周期通过。FIFO payload物理清零仍为 `UNPROVEN`，缓存政策 `REVIEW_PENDING`。`--waves`会采完整TB包括clear，仍须独立检查同窗映射、SRAM功耗模型、覆盖、STA及全部正式资格后才能用于能量和评分。
