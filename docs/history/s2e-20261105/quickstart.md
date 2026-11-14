> 历史归档：这是 S2e 阶段原交接内容，相对链接已调整。当前 64 PE / 1064 候选请读[仓库首页](../../../README.md)。本页数字和命令仅适用于当时版本。

# S2e 快速开始

完整状态与后续验收顺序见 [HANDOFF.md](../../../HANDOFF.md)。当前 `main` 已包含 S2e，无需切换旧 `feature/*` 分支。

## 获取与依赖

```bash
git clone --branch main --recurse-submodules https://github.com/mxHanks/ChipContest.git
cd ChipContest
# 已有克隆：
git submodule update --init --recursive
```

本地使用 Python3、JDK/Scala CLI、Verilator及C++编译器、Icarus (`iverilog`/`vvp`)、RISC-V裸机 gcc/objcopy/objdump。Scala/Chisel/ScalaTest 版本由 `project.scala` 固定；服务器严格入口使用原 SiFive GCC10.2 与 VCS2020.03-SP2-6。不要用本地新版工具输出替换已冻结服务器测量。

```bash
python3 -B tools/scripts/e203_soc.py --mode doctor
python3 -B -m unittest discover -s tests/e203 -p 'test_*.py'
python3 -B -m unittest discover -s tests/numeric
python3 -B -m unittest discover -s tests/host
python3 -B tools/scripts/e203_soc.py --mode check-vectors --tasks 12
scala-cli test . --server=false --jvm system
```

主机测试中主动构造的缺工具/FAIL日志是负向测试；以 unittest 最终退出码与结果为准。`doctor` 检查子模块、实际编译器和仿真器。

## S2e 功能复现

输出目录必须是新目录：

```bash
python3 -B tools/scripts/e203_soc.py --mode real --tasks 12 --sim verilator \
  --firmware-schedule bias-hw-autogroup-paired-hi-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out build/s2e-real12-new
```

预期 `SOC_PASS tasks=12 outputs=304128 writes=608256`。每层检查全部25,344个signed48结果、50,688个canonical Y字写回；S2e结果读取计数为25,344个旧LO字与12,672个packed-HI字。既有入口默认仍为baseline；省略固件选项不会运行S2e。

同一S2e RTL上的旧读回对照可将schedule改为 `bias-hw-autogroup-window`，使用另一个新输出目录。这是传输机制对照；最终表格的S2c面积与能量绑定其自己的网表，不能直接借用S2e网表。

数值夹具位于 `tests/e203/vectors/`，固定格式为X/W signed16、bias signed40、Y signed48。`check-vectors`是整数参考校验，不等于官方600样本/完整encoder精度验收。

## Chisel 与原始测量核验

```bash
scala-cli run . -M GenerateRTL -- LinearAutoGroupCore
python3 -B tools/scripts/xu_verify_handoff.py
```

S2e使用既有自动组计算核心；`GenerateRTL` 无参数的历史默认顶层不是S2e SoC。生成RTL也不等于运行完整SoC验收。原始包单独安全解包命令见 [证据说明](../../validation/xu-score-two-candidate-final-20261105/README.md)。

## 服务器 VCS

在原服务器、干净检出本次交付提交及正确子模块后：

```bash
python3 -B tools/scripts/xu_s2e_server_accept.py \
  --expected-main "$(git rev-parse HEAD)" \
  --expected-e203 a0767db69628ef30e53de2d1e93dd0360c0ccf76 \
  --cross-prefix "$HOME/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-" \
  --out "$HOME/Desktop/s2e-vcs-handoff-NEW"
```

该入口拒绝不同版本工具、脏源码和不完整12层结果，也会核对192种旧固件配置的镜像一致性。它属于RTL开发验收；严格mapped功能、完整150MHz、clear/未知活动及全SoC能耗资格另见HANDOFF待办。

## 协作

先在 `third-party/e203_hbirdv2` 提交并推送，再在父仓库提交gitlink；不能只推父仓库。新工作建议用 `codex/` 功能分支，验证后正常合入main。冻结测量原件不可覆盖；新实验使用新输出目录，保留失败日志及哈希。
