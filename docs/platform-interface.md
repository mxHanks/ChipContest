# xu 平台接口契约与接入检查表

适用基线：主仓 `ddcf6cc5ea9119b3dd162249be8c4521eef45da2`、E203 子模块 `e36d34a52e6eef93fd0bdfed1b13009e1056bea3`。本轮保留 8 PE、signed16 X/W、signed40 bias、signed48 result 和现有 MMIO ABI。本文依据仓库内固件、`tb_accel_soc.sv` 和 E203 RTL 描述当前开发接口；不把它当成已核实的 2026 官方 SDK、宏或装载接口说明。维护标识：xu。

## 计算和文件边界

```text
Y[r,c] = bias[c] + sum(k=0..63, X[r,k] * W[k,c])
r=0..98, c=0..255
```

各项均为补码有符号整数，运算不作中间舍入或饱和；48 位覆盖当前完整输入范围。尺度、量化和浮点误差口径见 [数值契约](numeric-contract.md)，接口中没有尺度寄存器。

每个任务位于 `layer_00` 至 `layer_11` 的一个目录中：

| 文件 | 字数 × 位宽 | 线性次序 | 每行 hex 位数 |
| --- | --- | --- | --- |
| `x.mem` | 6336 × signed16 | `r*64+k` | 4 |
| `w.mem` | 16384 × signed16 | `k*256+c`，不转置 | 4 |
| `bias.mem` | 256 × signed40 | `c` | 10 |
| `y.mem` | 25344 × signed48 | `r*256+c` | 12 |

每行一个固定宽补码 hex 字，无地址标记、注释或未知态。`y.mem` 只进入检查器；不得装进 CPU 可读共享区或用作硬件输出。现有 `--mode real` 的数据是历史 KWT checkpoint 的单个静音波形、12 个独立 FFN1 任务，不能称为官方评测数据、全验证集或完整编码器推理。

## MMIO ABI

基址 `0x10042000`，通过 `e203_subsys_perips.v` 的 ICB o15 接入，解码窗口为 `[0x10042000,0x10043000)`（4 KiB），从机按地址低 12 位选择寄存器。下表偏移均为字节。软件统一使用 **4 字节对齐的 32 位读写，写掩码 `4'b1111`**。地址/索引只保留表中的低位，不检查越界；不得依赖截断作为合法输入检查。

| 偏移 | 寄存器 | 读写与有效位 |
| --- | --- | --- |
| `0x00` | ID | RO，`0xACCE2030` |
| `0x04` | SCRATCH | RW，32 位，按字节掩码更新 |
| `0x08` | CTRL | 读为 0；写 bit0=1 发起一组计算，busy 时忽略 |
| `0x0C` | STATUS | 读 bit0=busy、bit1=sticky done；写 bit1=1 清 done（W1C） |
| `0x10` | GROUP | RW，低 5 位，0..31 |
| `0x14` | X_ADDR | RW，低 6 位，0..63 |
| `0x18` | X_DATA | 写低 16 位并产生 X 装载脉冲；读为最近写入值的零扩展 |
| `0x1C` | W_BANK | RW，低 3 位，0..7 |
| `0x20` | W_ADDR | RW，低 11 位，0..2047 |
| `0x24` | W_DATA | 写低 16 位并产生 W 装载脉冲；读为最近写入值的零扩展 |
| `0x28` | BIAS_INDEX | RW，低 3 位，选择 8 个 bias 槽之一 |
| `0x2C` | BIAS_LO | RW，所选 bias 的 bits31:0，按字节掩码更新 |
| `0x30` | BIAS_HI | RW，低 8 位为所选 bias 的 bits39:32；仅 mask[0] 控制更新，读时高 24 位为 0 |
| `0x34` | RESULT_INDEX | RW，低 3 位，选择 8 个 PE 结果之一 |
| `0x38` | RESULT_LO | RO，所选结果的 bits31:0 |
| `0x3C` | RESULT_HI | RO，低 16 位为结果的 bits47:32；高 16 位为 0 |

只有 SCRATCH、BIAS_LO、BIAS_HI 实现了上述字节掩码；其他可写寄存器实际忽略 `cmd_wmask`，包括 CTRL/STATUS 和 X/W 装载。因此当前契约不提供通用 byte/halfword MMIO 写语义。未实现地址读 0、写忽略，`rsp_err` 恒为 0，不能靠总线错误发现错误地址。

X/W 的符号位是 bit15；零扩展的读回槽仍要按 signed16 解码。bias 符号位是 bit39，即 BIAS_HI 的 bit7；result 符号位是 bit47，即 RESULT_HI 的 bit15。**RESULT_HI 本身不符号扩展**。现有固件将它转为 `(uint32_t)(int32_t)(int16_t)hi`，再与低 32 位形成显式 signed64 槽；BIAS_HI 写入仅取高字低 8 位。

ICB 命令仅在 `cmd_valid && cmd_ready` 时接受；响应仅在 `rsp_valid && rsp_ready` 时退休。MMIO 从机为一个响应槽，`cmd_ready = !rsp_valid || rsp_ready`，允许旧响应退休同拍接受新命令，受阻时保持响应。命令接受、写入生效和响应退休是不同事件。该加速器没有 DMA、IRQ 或自动共享存储搬运；CPU 负责全部装载和写回。

## 存储布局与 bank 变换

开发共享存储基址 `0xA0000000`，容量 `0x80000`（512 KiB），地址区间为 `[0xA0000000, 0xA0080000)`。表中范围为相对基址的半开区间：

| 偏移范围 | 内容与地址公式 |
| --- | --- |
| `[0x00000,0x06300)` | X：6336 个 32 位槽，`4*(r*64+k)`，低 16 位有效 |
| `[0x08000,0x18000)` | W：16384 个 32 位槽，`0x08000+4*(k*256+c)`，低 16 位有效 |
| `[0x18000,0x18800)` | bias：256 个 64 位槽，`0x18000+8*c`，低字后高字；高字为高 8 位的符号扩展 |
| `[0x20000,0x51800)` | Y：25344 个 signed64 槽，`0x20000+8*(r*256+c)`，低字后符号扩展高字 |
| `0x7F000` | host[0]：任务数 1..12，启动前装载 |
| `0x7F004` | host[1]：固件写入完成序号 `layer+1`，只在完整写回之后 |
| `0x7F008` | host[2]：固件写入本任务低 32 位 `mcycle` 差值，开发统计 |

TB 将 X/W 的文件字零扩展到 32 位槽。CPU 仅传低 16 位，故共享槽高位不参与计算。bias 和 Y 都用独立低/高 32 位访问，不依赖 C 的非对齐 64 位访问。

CPU 按以下关系把行优先 W 转为硬件 bank 布局，**不能直接把 `w.mem` 顺序写入单个 bank**：

```text
bank = c % 8
group = c / 8
addr = group*64 + k             # 等价于 {group[4:0], k[5:0]}
bank[bank][addr] = W[k*256+c]
```

每 bank 为 2048×16，现有 `WeightBank` 由两片 `Sram1024x16` 组成，addr[10] 选片、addr[9:0] 为片内地址；读出选片信号延迟一拍匹配同步读。8 bank 共 32 KiB 权重，不能混同外部 512 KiB 共享存储。XRowBuffer 只容纳当前行 64×16；每组的 8 个 bias 放在 MMIO 内部寄存器。计算期间不得同时改 GROUP、X、W 或 bias；当前从机没有为这些写入提供 busy 保护。

## 调度、复位与完成条件

`accel_linear()` 的调用者应遵循现有顺序：

1. 核对 ID，确认 STATUS.busy=0；每个独立任务重新装载全部 8 bank 的 W。
2. 每行写入 64 个 X；对每个 group 写入对应 8 个 bias，设置 GROUP。
3. 写 STATUS=2 清除旧 done，再写 CTRL=1；轮询 STATUS.done。START 本身也清 done，但调用者保留显式 W1C，防止把前次完成误当本次完成。
4. 本组 done 后设置 RESULT_INDEX=0..7，逐个读取低/高结果，按行优先顺序写入 Y；一任务共 99×32=3168 次 START、25344 结果、50688 个 32 位写字。
5. `fence iorw,iorw` 后返回。主程序记录 host[2]，再写 host[1] 完成序号并执行 fence。返回 -1/-2/-3 分别表示 ID 错误、进入时 busy、轮询超限；这些路径不得发布成功 ACK。

STATUS.done 只代表当前 **8 结果计算组**完成，不代表一整层或共享存储写回完成。完整任务验收必须同时满足：50688 个 Y 写字全部按地址递增、全掩码、与整数 golden 逐字一致，且最后一个 Y 写响应已经退休，之后才能接受本任务的 host[1]。只看最后一条写请求被接受、done 或固件进入结束循环都不充分。

开发 TB 对共享存储保持最多一个未退休请求，允许响应退休同拍接受新请求；响应退休不能依赖“下一条命令已接受”。它注入周期性 backpressure，检查 outstanding 范围和孤立响应。每次加载任务将整个 Y 区写成 `0xDEADBEEF`，防止前任务结果残留被当成成功。

复位为 E203 低有效 `rst_n`，进入 Chisel core 时取反为高有效 reset。复位清控制/索引/bias/done/busy；不能假定 X/W 行为 RAM 内容被清零。TB 在初始化装载固件与首任务后于 `#120` 释放外部复位。**12 任务连续运行，中间不复位 SoC**；只有当前任务完整写回且 ACK 合法，TB 才同步装入下一任务 X/W/bias/golden 并重新毒化 Y。各层输入来自各自 FFN1 输入，不将上一层 Y 接作下一层 X。真实板级主机若异步装载下一任务，还须另加输入就绪握手；现有开发 host 协议没有该握手。

全程完成还要求固件提交到 `0x80000086` 的 `write_tohost`，寄存器 gp=1，检查器 completed=tasks；日志需恰好包含有序的各层 TASK_PASS 和匹配总数的 SOC_PASS。12 任务总数为 304128 结果、608256 写字。

## 装载与计时边界

当前裸机入口是 `tests/e203/firmware/start.S`、`main.c`、`accel.c` 与 `link.ld`：ITCM `0x80000000/64 KiB` 放指令，DTCM `0x90000000/64 KiB` 放栈/BSS；启动不复制初始化 `.data`，链接脚本要求其为空。开发脚本把 ELF 转为 `.verilog` 并调整装载地址，TB 直接写 ITCM 仿真层级。这不是可移植的官方固件/参数装载入口。

| 统计 | 当前边界与限制 |
| --- | --- |
| TB `cycles` | 每任务首次共享输入/参数读取被接受，到最后 Y 写响应退休，含 CPU、MMIO 装载、计算、总线等待和写回；`last-first+1` |
| `firmware_cycles` | `main.c` 中调用 `accel_linear()` 前后读取低 32 位 mcycle 的差；包含 ID/busy 检查和末尾 fence，起止事件与 TB 不同 |
| 正式性能/功耗 | 必须以已核实官方装载、时钟、输入就绪和输出完成规则重新定义并实测；现有统计不能直接替代 |

文件读取、TB 预装共享 RAM、ITCM 直接装载和任务间主机换数据均在上述 TB 计时之外。TB 的外部 clk 周期为 4 ns，仅为开发激励，不是 150 MHz 时序收敛证据。正式报告须明确是否及如何计入参数装载、CPU/互连/存储等待与完整写回，不得只报告 MAC 核心周期；库、PVT/RC、面积和功耗范围另需官方材料核实。

## 源文件清单与正式工程接入

当前完整开发矩阵由 `tools/scripts/e203_soc.py:matrix_sources()` 收集 `vsim/install/rtl` 下全部 **`.v` 和 `.sv`**，另加 `tests/e203/tb_accel_soc.sv`，不混入旧 `install/tb/tb_top.v`。`make clean && make install` 刷新安装副本。VCS 使用 `-sverilog`；正式工程也必须明确启用 SystemVerilog，不能只收集 `.v`。

正式源清单以实际平台 top 和 E203 依赖为基础，至少核对以下新增/变更项；这是一份接入核对表，正式签核 manifest 尚待官方工程确认：

| 范围 | 路径（相对 `third-party/e203_hbirdv2/`） |
| --- | --- |
| SoC 外部共享 ICB 与 MMIO 接入 | `rtl/e203/soc/e203_soc_top.v`、`rtl/e203/subsys/e203_subsys_perips.v` |
| MMIO 从机 | `rtl/e203/perips/accel_icb_slave.v` |
| 计算链 | `rtl/e203/perips/LinearComputeCore.sv`、`DotProductEngine.sv`、`MacController.sv`、`MacPEArray.sv`、`MacPE.sv`（后四项同目录） |
| 存储链 | `rtl/e203/perips/XRowBuffer.sv`、`WeightBankArray.sv`、`WeightBank.sv`、`Sram1024x16.sv`、`mem_1024x16.sv`（后四项同目录） |
| 当前目录内另有模型 | `rtl/e203/perips/mem_2048x16.sv`；开发通配清单会收入，但当前 LinearComputeCore 层级没有实例化它 |
| 头文件/基础依赖 | 保留 E203 core/fab/general/mems/perips/subsys 的实际依赖和 `e203_defines.v` 等 include 路径；不可只编译上面的加速器文件 |
| 仅测试 | `tests/e203/tb_accel_soc.sv`、向量、检查器和 TB 的 512 KiB RAM；不进入芯片综合 |

`e203_soc_top` 必须显式选择 `EXTERNAL_SYSMEM=1` 并连接 `ext_sysmem_*` 命令/响应全通道；默认 0 保留旧应答器，不能代表真实共享存储已接通。正式 SRAM/接口替换应保留同步读延迟、使能、单端口互斥和返回稳定性，并重新检查 bank 跨片地址 1023/1024。

现有 `e203_soc.core` 的显式 fileset 未列入 accel 从机和上述 `.sv` 计算链；旧 FPGA `ddr200t/mcu200t` 的 `prologue*.tcl` 递归匹配 `*.v`，同样漏 `.sv`。这些入口未经本轮修订/构建验收，不能因为开发 VCS 源集完整就宣称 FuseSoC/FPGA/正式综合入口已覆盖。`mem_1024x16.sv` 是行为存储模型；官方宏包装器、引脚与极性、时序和综合替换方式尚未核实，不可猜测宏接口或把行为模型当工艺宏。

## 服务器优先验收与待接入项

截至本轮交接，已实际登录服务器并确认干净基线工作副本及 Python 3.6.8、Git 1.8.3、glibc 2.17、GCC 4.8、JRE 8。VCS 2020 smoke 实际 PASS。原 full 入口曾在 host 检查因两个较新 API 失败；兼容适配后，服务器 host 19 项、numeric 34 项、check-vectors 12 层实际 PASS。VCS 原 SoC 五项、合成完整单层和真实静音 12 层均实际通过，共核对 304128 个真实结果与 608256 次写字；JRE 8 或本地主机旧日志不能证明服务器 Chisel/正式回归通过。连接凭据不属于仓库交接材料。

优先在服务器执行（RV 工具链前缀替换为实际已安装位置，输出目录必须不存在）：

```bash
python3 tools/scripts/e203_soc.py --mode doctor --sim vcs --cross-prefix /实际RV工具链/bin/riscv-none-elf-
python3 tools/scripts/server_accept.py --sim vcs --cross-prefix /实际RV工具链/bin/riscv-none-elf-
```

一键 VCS 路线依次执行 host、numeric、12 层整数向量核算、doctor、原 SoC 五项、synthetic1、real12；每步保留命令、版本、源/固件/向量哈希及完整日志。它不运行 Icarus/Chisel，不能与 `--full` 合用，也不自动获得官方认证。新开发向量先 `--mode check-vectors --tasks 12 --vectors /目录`，再用 `--mode vectors --sim vcs --tasks 12 --vectors /目录` 做 RTL 回放。

- [x] VCS 开发平台验收完成，服务器保留新报告；结果与两个实际失败负例见 [2026-11-01 验证记录](validation/platform-vcs-20261101/README.md)。这是当前行为存储与开发装载路径的通过记录。
- [ ] 获得并固定 2026 官方 SDK/平台工程版本，核实复位向量、启动/链接、MMIO/共享地址与参数/程序装载入口；目前尚无已核实对应信息。
- [ ] 核实正式主机装载/任务就绪握手、计时起止、输出接收及总线响应退休规则，重新运行 12 独立任务连续验收。
- [ ] 核实官方 SRAM 宏/模型的确切名称、端口、容量、读延迟、控制极性和综合映射；以宏仿真替换行为模型后重新逐字比对。
- [ ] 核实标准单元库、PVT/RC 角、时钟/IO 约束、活动/功耗范围；形成正式源 manifest 并覆盖 `.sv`，重新完成综合、时序、面积和功耗。

现有开发回放、历史静音软件精度、官方数据精度、工艺宏功能和正式 PPA 分别保留证据边界；任何一项的 PASS 都不能替代其余项目。
