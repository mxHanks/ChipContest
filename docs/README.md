# 文档与证据导航

当前候选为 64 PE / 原 32 位 SystemBus / 1064 修复版。评审请从[仓库首页](../README.md)和[交付入口](../submission/README.md)开始。

| 内容 | 入口 |
|---|---|
| 当前最终结果、时序修复与未闭合事项 | [最终修复报告](s3-y32-ingress-perf-postfreeze-repair-20261114.md) |
| 最终完整 STA、面积、一致性和归档 | [catch3 原件](validation/s3-y32-ingress-perf-native-20261114/catch3/) |
| 12 task 周期与逐位输出 | [性能收据](validation/s3-y32-ingress-perf-native-20261113/timing-final/performance-result.json)、[仿真日志](validation/s3-y32-ingress-perf-native-20261113/timing-final/performance-simulation.log) |
| 入口流水与实验实现 | [当前实现说明](../experiments/s3-y32-ingress-perf/README.md) |
| 原始性能/综合阶段报告 | [2026-11-13 报告](s3-y32-ingress-perf-synthesis-report-20261113.md)；时序状态以最终修复报告为准 |
| 操作与接手 | [快速开始](../quickstart.md)、[HANDOFF](../HANDOFF.md) |
| 旧候选、原交接与分支恢复 | [历史导航](history/README.md) |

`validation/` 按候选与日期封存原件，原路径、SHA 清单和失败记录保持可追溯。旧报告描述各自当时状态，不能与当前结果拼接；`rejected-r2/` 是失败诊断，不能计作最终 clean 执行。公开原件可通过 `python3 -B tools/current.py verify --submodule` 核对，该命令不替代重新运行 EDA 或完整签核。
