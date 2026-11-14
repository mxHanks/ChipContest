# 历史候选与恢复导航

当前交付入口是[仓库首页](../../README.md)及 [submission/](../../submission/README.md)。以下只用于理解演进、查证当时结果或恢复历史，不是当前复现默认项。

| 阶段 | 资料 | 与当前版本的关系 |
|---|---|---|
| S2e / S2c，8 PE | [原首页](s2e-20261105/README.md)、[原快速开始](s2e-20261105/quickstart.md)、[原交接](s2e-20261105/HANDOFF.md) | 2026-11-05 交付口径，已由 64 PE 候选替代 |
| S3-Y32 初期 | [开发交接](../s3-y32.md) | 早期 8 PE / NICE 路径 |
| 64 位端点探索 | [s3-y32-4k](../../experiments/s3-y32-4k/README.md) | 不是当前原 32 位 SystemBus 设计 |
| 504 task/s 同口径基线 | [compliant32](../../experiments/s3-y32-compliant32/README.md) | 当前流水优化的比较基线；数值工具仍被复用 |
| 1064 入口流水与初次综合 | [原报告](../s3-y32-ingress-perf-synthesis-report-20261113.md) | 性能可追溯，最终时序以 catch3 为准 |
| 父仓分支整理 | [原 tip 与恢复方法](branch-archive-20261114.md) | 归档为标签，main 保留当前选择 |

历史实验源码与冻结证据保留原路径；当前工具仍复用其中一部分。目录保留不表示其 README 的数字、默认参数或候选选择仍适用。恢复历史时请在独立目录检出相应归档标签并初始化对应子模块。
