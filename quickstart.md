# 1064 修复候选：快速开始

当前入口为 `tools/current.py`，固定选择 [submission/candidate.json](submission/candidate.json)。技术结果见[仓库首页](README.md)，工程身份与待办见[交接](HANDOFF.md)。

## 获取与依赖

```sh
git clone --branch main --recurse-submodules https://github.com/mxHanks/ChipContest.git
cd ChipContest
git submodule update --init --recursive
```

| 操作 | 所需环境 |
|---|---|
| 原件校验、向量/网表提取、整数向量验证 | Linux、Python 3.10+ 标准库、Git |
| ingress 回归 | 另需 Icarus Verilog（`iverilog`、`vvp`） |
| CPU 完整任务 | 另需 Verilator 5+、GNU C++20、Make、RISC-V bare-metal GCC/binutils |

默认交叉前缀为 `riscv64-unknown-elf-`，目标为 RV32 `ilp32`，需支持 `rv32imac_zicsr2p0_zifencei2p0`。已有 CPU 性能收据使用 Verilator 5.032、GCC 14.2 和 g++ 15.2；其他工具版本应保留实际日志及版本，不直接冒称原实测环境。普通 RTL 复现无需 Scala、TensorFlow、音频资产或 EDA 许可证。

## 先验证交付内容

```sh
python3 -B tools/current.py verify --submodule
python3 -B tools/current.py ingress
python3 -B tools/current.py vectors --out build/1064/vectors
python3 -B tools/current.py check-vectors --vectors build/1064/vectors
```

预期：`EVIDENCE_VERIFIED_NOT_SIGNOFF` 且子模块 `VERIFIED`；入口回归的 1000 笔 fabric 探针接收跨度 1997、退休跨度 2002 cycles；向量检查为 12 tasks、304128 outputs，raw MAC 和 Y32 均精确一致。`info` 仅显示候选身份，不做验收。省略 `verify --submodule` 的选项时，输出会明确标记 RTL 未检查。

`vectors` 从仓库已有紧凑证据包选择性恢复向量，先核对归档及文件 SHA；不会运行旧候选。所有生成目录须不存在，重复操作请换新目录。

## 运行当前 RTL

单任务检查与完整十二任务任选其一；首次执行会编译仿真器：

```sh
# 单任务不能代替完整验收
python3 -B tools/current.py cpu --vectors build/1064/vectors --out build/1064/task0 --tasks 1 --jobs 2

# 完整复现；不依赖前一个单任务目录
python3 -B tools/current.py cpu --vectors build/1064/vectors --out build/1064/full12 --tasks 12 --jobs 2
```

统一入口强制 warmup 与 `--load-pipeline 1`，编译并行度支持 1 或 2；可用 `--cross-prefix /path/to/riscv64-unknown-elf-` 指定工具链。运行会保留输出、源码/固件/二进制身份、完整日志和 `result.json`。

已发布实测为 12 task、304128 个正确 Y32、1691172 cycles。换算公式为 `150000000 × 12 / total_cycles`，得到条件吞吐 1064.350640 task/s。计时包含 clear 和实际源加载；任务前暖机/poison、任务后参考读回在窗外。它是原 SystemBus loader 的 RTL 测量，生产 GPIO 和最终 mapped 带延迟任务另需验收。

## 查看最终映射

```sh
python3 -B tools/current.py unpack-mapped --out build/1064/final-mapped
```

该命令安全恢复最终 mapped Verilog、DC 导出的 mapped.sdc 和 8 份 SVF，并拒绝覆盖旧目录。最终 [catch3 原件](docs/validation/s3-y32-ingress-perf-native-20261114/catch3/) 包含 DC/PT 报告和严格结构证明。验据不启动 EDA；有许可环境的重跑还需要原工艺 DB、工具版本及 ECO 依赖链。当前不提供从空 build 一步生成最终 ECO 的承诺。

历史 S2e 命令见[归档快速开始](docs/history/s2e-20261105/quickstart.md)，仅用于对应旧版本。
