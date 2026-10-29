# xu：E203 开发平台集成

本工作沿用 README 的 Chisel 8 路 INT16/48 位累加器及 `feature/e203-integration`，保留原 ICB ABI 和计算核心。新代码分支统一为 `feature/e203-xu-integration`（主仓库、E203 Fork 各自独立）。没有合入另一条 kwt-asic 硬件路线。

## 已接通的链路

真实 E203 CPU 执行 `tests/e203/firmware/` 裸机程序，从共享存储器读取 X/W/bias，经现有 `0x10042000` MMIO 装载加速器。CPU 依次调度 99 行 × 32 组，每组由 RTL 完成 8 个长度 64 的点积；CPU 将结果完整写回共享存储器。软件不计算参考矩阵，测试平台不代算硬件结果。

E203 子模块 `e203_soc_top` 新增 `EXTERNAL_SYSMEM` 参数和外部系统存储 ICB 端口。默认值 0 保持旧板级/原测试平台的零响应行为，新增测试平台选择 1，实际连接单 outstanding、支持等待的 512 KiB 行为存储。此模型仅用于开发验证；不是官方 SRAM 宏或官方平台认证，也不进入芯片综合源集。

## Linux 环境

与 quickstart 一致，需 Git、Make、Icarus Verilog 12、RISC-V GCC/binutils、Python3。完整矩阵默认使用 Verilator（需支持 `--binary --timing`）和 C++ 编译器；主机检查无需第三方 Python 包。Chisel 源回归使用 project.scala 指定的 Scala 2.13.18、Chisel 7.16.0 和 ScalaTest 3.2.20；不为适配机器而升级项目语言。

```bash
git clone --recurse-submodules --branch feature/e203-xu-integration https://github.com/mxHanks/ChipContest.git
cd ChipContest
python3 tools/scripts/e203_soc.py --mode doctor
python3 -m unittest discover -s tests/e203 -p test_runner.py
python3 tools/scripts/e203_soc.py --mode baseline
python3 tools/scripts/e203_soc.py --mode synthetic --tasks 1
python3 tools/scripts/e203_soc.py --mode real --tasks 12
scala-cli test . --server=false --jvm system
```

每次运行新建 `build/e203/<UTC时间>/`；`--out` 可指定尚不存在的目录。既有目录不会被覆盖。日志和 `result.json` 保留实际命令、版本、固件/RTL/向量哈希与每层周期。失败退出非零，日志中的完整完成标志、层号及输出/写回数量必须一致。缺工具、坏向量或异常结束都不能算 PASS。

运行器每次按 quickstart 执行 `make clean`、`make install` 刷新安装副本。baseline 再使用仓库 `make run_test SIM=iverilog` 跑原 ADD 和四项汇编测试；完整矩阵使用相同已安装 RTL 及独立 `tb_accel_soc`。仿真器编译缓存绑定源文件/工具身份，输入和固件每次重新准备。

`--sim iverilog` 可对完整矩阵使用四态仿真；默认 Verilator 是两态开发验证，不能替代四态检查。`--waves` 生成输出目录内的 VCD，适合单任务调试。`--max-cycles` 可限制仿真周期，外层另有墙钟超时。工具链名称不同时使用 `--cross-prefix /实际路径/riscv-none-elf-`。

旧 main quickstart 的 SDK Hello World 属于 Legacy 参考。当前 Ubuntu GCC 的 ISA 命名要求显式 `RISCV_ARCH=rv32imac_zicsr_zifencei`；SDK 还依赖含 Newlib/`nosys.specs` 的完整裸机工具链。新 xu 固件为 freestanding，不依赖 libc 或修改 SDK 源码，使用同样的显式 ISA 与 ilp32 ABI。官方 SDK 到位后在驱动外层适配启动/链接；不能把 SDK 示例构建失败隐藏为通过。

本次亦按 Legacy 路径克隆 Hbird SDK，固定提交 `0e0e9083569721578c42f07a95b05a26c0760db6`。Ubuntu GCC 原命令因旧 ISA 名称、缺少 Newlib 失败；改用经发布方 SHA256 核验的 xPack RISC-V GCC 15.2.0-1 完整工具链，且仅在命令行显式补充 ISA 后，Hello World 的 `dasm` 目标实际构建成功，生成 ELF、dump、dasm、hex、map 和 verilog。没有修改 SDK 源码，也未将“编译成功”称为 Hello World 仿真通过。

```bash
cd third-party/hbird-sdk/application/baremetal/helloworld
make clean
make CORE=e203 DOWNLOAD=ilm COMPILE_PREFIX=/实际工具链/bin/riscv-none-elf- \
  NEWLIB=normal RISCV_ARCH=rv32imac_zicsr_zifencei dasm
```

工具链来源为 [xPack 官方 v15.2.0-1 发布](https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v15.2.0-1)。工具和 SDK 不打包进本仓库；xu 默认回归继续使用 Ubuntu 的 freestanding 工具链。

## 数据约定和来源

每层一个 `layer_00` 至 `layer_11` 子目录：

| 文件 | 字数 × 位宽 | 次序 |
| --- | --- | --- |
| x.mem | 6336 × signed16 | `row*64+k` |
| w.mem | 16384 × signed16 | `k*256+col` |
| bias.mem | 256 × signed40 | 输出列 |
| y.mem | 25344 × signed48 | `row*256+col`，仅检查器可见 |

每行一个固定宽十六进制补码，无地址标记。运行前严格检查字数、宽度和合法字符。CPU 将 W 变换到 `bank=col%8, addr=(col/8)*64+k`。bias 拆为低 32 位、高 8 位；结果拼接为 signed48 后显式符号扩展到 signed64，顺序写低/高两个 32 位字。

`--mode synthetic` 生成分层不同的合成向量，包含 INT16 极值、负数和超过 32 位的正负偏置/结果。它不证明浮点精度。

`--mode real` 使用 `tests/e203/vectors/kwt-silence-v1.tar.gz` 的 48 个原始 mem 文件。它们逐字节取自 ChipContest 提交 `c2e58fd9de4c653c4d7822ee5e79e4f06761edb1` 的 `kwt-asic/sim/vectors/kwt-silence-v1/`，保留原导出 manifest、日志、KWT Apache 2.0 许可证和逐文件 SHA。固定上游 KWT 提交为 `237e4097afd4f6851e0b82f0a8d65c2dfe8eae30`。这是一个真实 checkpoint 的静音样本、12 层独立 FFN1 输入的整数回放，不是全验证集或官方600样本精度验收，也不是十二层编码器推理。

A 交付新向量后直接运行：

```bash
python3 tools/scripts/e203_soc.py --mode vectors --vectors /数据目录 --tasks 12
```

## 开发共享存储映射

基址 `0xA0000000`，容量 `0x80000`。此地址是开发配置，官方平台地址需按实际工程适配。

| 偏移 | 内容 |
| --- | --- |
| 0x00000 | X，单元素32位槽的低16位 |
| 0x08000 | W，单元素32位槽的低16位 |
| 0x18000 | bias，单元素64位槽 |
| 0x20000 | Y，25344个 signed64 槽 |
| 0x7F000 | 主机任务数（1—12） |
| 0x7F004 | CPU 完整写回后的层完成 ACK |
| 0x7F008 | CPU mcycle 差值（开发统计） |

测试平台从文件装载输入和参考值，不把 y.mem 放进 CPU 可读内存。输出区每层覆盖为毒值。检查器在实际 ICB 写请求接受时检查地址、顺序、掩码和每个结果字，在最后输出写响应被接受后才允许层 ACK。每层必须收到 50688 个正确写字；12层共304128个结果、608256次写字。ACK 后才替换下一层输入，不在层间复位 SoC，驱动重新装载全部权重/输入/bias 并清除旧 done。

开发周期从首次 CPU 读取共享输入/参数计到最后结果写响应接受，包含 MMIO、计算、CPU、总线等待与写回；TB 预装载和官方加载接口不在此窗口内，不能作为比赛正式吞吐量。测试时钟沿用上游开发仿真约定，不是150 MHz时序达标证据。官方库、宏模型、功耗及正式计时待材料到位后执行。

## 官方服务器接手顺序

1. 从上述固定分支及子模块提交重建；先 doctor、主机检查、baseline。
2. 跑一层 synthetic，再跑真实12层；保留新机器自己的日志和哈希，不沿用本机 PASS。
3. 将官方平台系统存储接口接到同一驱动地址配置，核对官方装载及写回窗口，重新运行上述检查。
4. B 交付宏/综合网表后，运行对应功能回归和活动导出；指定库下150 MHz、增量面积及完整功耗另行验收。

所有修改按 README 的双仓库顺序提交：E203 新功能分支先提交并推送，再在主仓库的新功能分支提交对应 gitlink。禁止把未推送的子模块引用交给队友。

## 本次实际验证

2026-10-26 验证记录见 [结果索引](validation/e203-xu-20261026/summary.json)。保留原始 JSON、结束日志和失败负例，未将历史 PASS 改名作为本机结果。

- 原 ADD 与四项汇编用例：5/5 通过。
- 原 Chisel 测试：8 个 suite、11/11 通过，含完整99×256和SRAM跨片边界。
- 主机运行器检查：7/7 通过，含缺工具、坏形状、失败命令、完成标志和缓存身份。
- 合成极值12层及真实静音12层：两次各304128输出、608256次写字，层间不复位，逐字匹配。
- 故意修改首个参考输出：实际仿真报 result mismatch，退出失败；Icarus强制小周期上限同样正确失败。
- 从GitHub重新克隆主仓库及已发布E203子模块，在Linux新目录构建并完成真实单层25344输出；不依赖原工作目录缓存。
- Legacy SDK Hello World：完整工具链下构建/dasm通过，未宣称仿真通过。

原 Chisel 回归曾有一项测试在读阶段保留写使能而触发单端口冲突断言；本次仅修正测试激励，未删除断言或修改计算RTL。独立审查发现并复现的共享存储响应退休问题已修复，并由 outstanding 断言与完整回归验证。
