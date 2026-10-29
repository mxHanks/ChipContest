# ChipContest

基于 **Chisel + RISC-V E203** 的 AI 硬件加速器设计项目，用于嵌入式芯片与系统设计竞赛芯片设计赛道。

项目主要围绕神经网络计算加速、片上存储架构、SoC 集成、RTL 功能验证及 ASIC 面积与时序评估展开。

> **在开始 Work 之前，请先阅读 [`quickstart.md`](quickstart.md)，尤其注意环境搭建、Git Commit 和协作规范。**
>
> 对于已经通过测试的稳定功能，及时提交 Git Commit，避免多个功能混杂在同一次提交中。

## 项目目标

当前重点实现 INT16 线性层矩阵乘法加速器：

$$
Y_{99\times256}=X_{99\times64}\times W_{64\times256}+Bias
$$

主要架构：

- 8 个并行 MAC（Multiply-Accumulate，乘累加）计算单元。
- 每个 PE（Processing Element）使用 16-bit 输入、16-bit 权重和 48-bit 累加器。
- 一次执行 8 路、每路 64 项的点积运算。
- 使用 8 个 WeightBank 并行提供权重。
- 使用同步 SRAM 读取与预取机制。
- 通过外层 Controller 自动遍历 99 行和 32 个输出组。
- 计划接入 Hummingbirdv2 E203 RISC-V SoC，完成软件与硬件协同验证。

## 项目结构

```text
ChipContest/
├── assets/
│   ├── datasets/           # 数据集
│   ├── libs/               # 标准单元库、工艺相关文件
│   └── modles/             # 模型文件（现有目录名）
├── build/                  # 构建及仿真生成文件
├── generated/              # Chisel 生成的 SystemVerilog
├── project.scala           # Scala CLI 配置
├── quickstart.md           # 环境搭建和开发说明
├── reports/
│   └── baseline/           # 冻结的综合基线数据
├── runs/                   # 仿真波形及运行产物
├── src/
│   ├── main/scala/         # Chisel RTL 源代码
│   └── test/scala/         # ChiselSim / ScalaTest
├── third-party/
│   └── e203_hbirdv2/       # E203 SoC Git Submodule
└── tools/
    └── scripts/            # 综合、面积评估等工具脚本
```

### 核心模块

| 模块                | 职责                         |
|---------------------|------------------------------|
| `MacPE`             | 执行单路乘累加               |
| `MacPEArray`        | 包含 8 个并行 PE             |
| `MacController`     | 管理点积运算状态与索引       |
| `DotProductEngine`  | 组织点积运算和结果缓存       |
| `XRowBuffer`        | 缓存当前输入行               |
| `WeightBankArray`   | 8 路并行权重存储阵列         |
| `WeightBank`        | 权重地址译码和 SRAM 选择     |
| `Sram1024x16`       | 单端口 SRAM 行为模型         |
| `LinearComputeCore` | 连接存储器与点积计算引擎     |
| `LinearLayerEngine` | 自动调度行、组计算及结果握手 |

## 快速开始

### 1. 获取代码

主仓库：

```bash
git clone https://github.com/mxhanks/ChipContest.git
cd ChipContest
```

基础 E203 集成位于 `feature/e203-integration`；xu 完整矩阵与写回回归接续于 `feature/e203-xu-integration`。运行本分支新增流程时使用：

```bash
git switch feature/e203-xu-integration
git submodule update --init --recursive
```

主仓库使用 Git Submodule 管理 E203， **不要在 `third-party` 中重新克隆另一个官方 E203 仓库**。

### 2. 环境准备

主要开发环境：

- Linux（当前主要使用 Ubuntu 24.04）
- JDK / Scala CLI
- Chisel 7.16.0、Scala 2.13.18
- Icarus Verilog、GTKWave
- Yosys
- Nangate45 标准单元库（面积评估使用）

依赖版本以 `project.scala` 为准。详细安装说明请查看 [`quickstart.md`](quickstart.md)。

### 3. 运行 Chisel 功能测试

在仓库根目录执行：

```bash
scala-cli test .
```

建议修改单个模块后先运行对应测试，再执行完整回归测试。

### 4. 生成 SystemVerilog

项目使用 `GenerateRTL` 作为 RTL 生成入口。

例如：

```bash
scala-cli run . -M GenerateRTL -- LinearComputeCore
```

生成文件存放在：

```text
generated/LinearComputeCore/
```

其他顶层包括 `DotProductEngine` 和 `LinearLayerEngine`。

### 5. ASIC 面积评估

目前采用 Yosys + Nangate45 标准单元库：

```bash
./tools/scripts/area_eval.sh DotProductEngine
./tools/scripts/area_eval.sh LinearComputeCore
```

报告输出到 `reports/`。

注意：当前 `Sram1024x16` 仍为行为模型，不是真正的工艺 SRAM Macro。完整存储器若被综合为 DFF 和 MUX，所得面积不能直接作为最终芯片面积。

## 开发进度

| 项目                          | 状态   |
|-------------------------------|--------|
| 8 路 INT16 点积计算引擎       | 已验证 |
| XRowBuffer 与 WeightBankArray | 已验证 |
| 同步读取与权重预取            | 已验证 |
| 1024×16 SRAM 行为模型封装     | 已验证 |
| 自动行 / 组调度               | 已验证 |
| 99×256 完整矩阵功能回归       | 已通过 |
| 真实 KWT 模型数据逐位回归     | 单静音样本12层SoC回放通过；全量待完善 |
| E203 SoC 集成                 | 开发版完整矩阵/12层换参已验证；官方平台待适配 |
| 真实 SRAM Macro 适配          | 待完成 |
| 时序收敛、功耗及最终 PPA 报告 | 待完成 |

上表中的 Chisel 完整矩阵测试由 Testbench 提供输入行、Bias 和结果接收握手；CPU 数据搬运与共享存储写回的独立验证见下节。

### xu 集成分支

`feature/e203-xu-integration` 接续上述集成分支，增加裸机 C 驱动、完整矩阵调度、可选外部系统存储 ICB 接口和独立写回检查器。运行入口与验证范围见 [quickstart.md](quickstart.md#xu-完整矩阵与写回回归) 和 [集成说明](docs/e203-integration.md)。此路径使用开发版 512 KiB 行为共享存储；官方平台、SRAM 宏及正式 PPA 仍需材料到位后验证。

```bash
python3 -m unittest discover -s tests/e203 -p test_runner.py
python3 tools/scripts/e203_soc.py --mode baseline
python3 tools/scripts/e203_soc.py --mode synthetic --tasks 1
python3 tools/scripts/e203_soc.py --mode real --tasks 12
```

原有 Chisel/SoC 测试及其运行方式继续保留。真实回放夹具只覆盖一个 KWT 静音样本的 12 层 FFN1 输入，不能代替完整数据集精度评估。

服务器接手准备位于 `feature/e203-xu-server-prep`，在 xu 的集成基础上增加参考向量独立核算、实际工具链预检和一键验收。执行 `python3 tools/scripts/server_accept.py`，扩展四态/Chisel回归可增加 `--full`。离线交接包恢复及官方材料到位后的检查顺序见 [服务器交接说明](docs/server-handoff.md)。

## Git 协作规范

### 分支管理

- `main`：经过验证的稳定代码。
- `feature/*`：新功能，例如 `feature/e203-integration`。
- `experiment/*`：架构探索或可能回退的实验。
- `fix/*`：缺陷修复。

开发时尽量保持每次提交只涉及一个明确的改动目标。

### Commit 规范

推荐使用以下前缀：

| 前缀     | 用途           |
|----------|----------------|
| `新增：` | 新功能         |
| `修复：` | Bug 修复       |
| `重构：` | 重构           |
| `测试：` | 测试           |
| `文档：` | 文档           |
| `维护：` | 工具及工程维护 |

示例：

```bash
git add src/
git commit -m "feat: add weight prefetch control"
```

提交前至少执行相关模块的测试，重要里程碑执行完整回归。

### E203 子模块协作

E203 是一个独立 Git 仓库，具有自己的 Commit 和 Remote。

修改 E203 时：

1. 在 `third-party/e203_hbirdv2/` 内提交并推送到团队 Fork。
2. 回到 ChipContest 根目录，提交更新后的子模块引用。
3. 再推送 ChipContest 分支。

不要只提交主仓库的 Submodule 引用，却不推送对应的 E203 Commit，否则其他队友可能无法检出相同版本。

## 参考资料

- [E203 团队 Fork](https://github.com/mxhanks/e203_hbirdv2)
- [E203 官方项目](https://github.com/riscv-mcu/e203_hbirdv2)
- [Chisel 文档](https://www.chisel-lang.org/)
- [Yosys 文档](https://yosyshq.readthedocs.io/)

## 备注

本项目持续开发中。当前的数值、性能和面积基线应以仓库中已经验证的测试和报告为准；未经验证的性能目标不得直接当作最终实现结果。

第三方 IP、参考模型和工艺文件的使用，应遵守各自许可证及比赛提供文件的使用约束。
