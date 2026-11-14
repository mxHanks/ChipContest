> 历史归档：这是 S2e 阶段原交接内容，相对链接已调整。当前 64 PE / 1064 候选请读[仓库首页](../../../README.md)。本页数字和命令仅适用于当时版本。

# ChipContest · S3-Y32 开发分支

当前协作版本的架构、复现入口和验收状态见 [S3-Y32 交接](../../s3-y32.md)。以下保留 S2e 基线的原始交接。

# ChipContest · S2e 交付版

基于 Chisel 与 E203 的八路 INT16 线性层加速器。`main` 交付当前主方案 **S2e paired-HI**，S2c 保留为测量对照。队友请先读 [HANDOFF.md](../../../HANDOFF.md)。

**交付状态：12层性能与诊断能量已审计；完整150MHz、严格门级功能和比赛能耗资格仍待完成。** 当前不能据此报最终比赛得分。

| 同一服务器、同一分析方法 | S2c 对照 | S2e 主方案 |
|---|---:|---:|
| 真实12层总周期 | 11,887,872 | **10,420,116** |
| 全SoC任务诊断能量（mJ） | 2.6384471466669330 | 2.3659452273331971 |
| 加速器面积（mm²） | 0.2948018380 | 0.3003096339 |

S2e 周期减少12.35%，吞吐增加14.09%，诊断能量减少10.33%；面积占2.25mm²上限的13.35%。能量包含当前任务窗口内的全SoC，窗口外 clear 阶段未计入；未知活动等资格问题尚未解除。逐层数据、原日志哈希和原始证据见 [两候选测量包](../../validation/xu-score-two-candidate-final-20261105/README.md)。

```bash
git clone --branch main --recurse-submodules https://github.com/mxHanks/ChipContest.git
cd ChipContest
python3 -B tools/scripts/e203_soc.py --mode doctor
python3 -B tools/scripts/e203_soc.py --mode check-vectors --tasks 12
python3 -B tools/scripts/xu_verify_handoff.py
```

依赖与运行命令见 [quickstart.md](../../../quickstart.md)。必须显式选择 S2e 固件参数，历史默认配置仍为 baseline：

```bash
python3 -B tools/scripts/e203_soc.py --mode real --tasks 12 --sim verilator \
  --firmware-schedule bias-hw-autogroup-paired-hi-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out build/s2e-real12-new
```

这是本地功能复现；表内周期来自服务器正式测量窗口，不能用本地默认时钟替换。服务器工具链、面积与能量复现入口见 [交接文档](../../../HANDOFF.md) 和 [冻结服务器工具](../../../tools/repro/server/README.md)。

源代码保留八个PE、signed16输入/权重、signed40偏置、signed48计算结果。S2c 既有 Chisel 自动组调度与两槽结果FIFO位于 `src/main/scala/linear/LinearAutoGroupCore.scala`；S2e 新增优化是 E203 手写接口 `accel_icb_slave.v` 的成对高16位读取和固件 `tests/e203/firmware/accel.c` 的对应读取/写回，**S2e 没有新增 Chisel 计算架构改动**。

`reports/baseline/`、Yosys/Nangate45 面积脚本和旧 PPA 生成器保留原有用途，不能代替这里的服务器工艺库结果。工艺库、工具许可证和访问凭据不包含在仓库中。修改子模块时先推送子仓库提交，再提交父仓库 gitlink。
