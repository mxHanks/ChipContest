# 当前工程交接 · 1064 修复候选

`main` 采用原 1064 候选的 catch3 修复结果。统一操作见[快速开始](quickstart.md)，面向评审的结果见[首页](README.md)，机器身份入口为 [candidate.json](submission/candidate.json)。

## 固定身份

| 对象 | 身份 |
|---|---|
| 修复完成的来源提交 | `be67e5d745cd7123e0def870f26be9a84263d759` |
| 生产 RTL 子模块 | `5470c5650f2d11d16e7c52cc96626d21030a3973` |
| 最终 mapped.v SHA256 | `d83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1` |
| 最终证据包 SHA256 | `a0870cf043543db0d1ef4eb3c56fc0fafc8ca624578bfc63dc49ba5d4670a6a0` |

README/入口整理后的父提交是交付集成身份，测量来源仍按上述固定提交和原始收据追溯。生产核心与 DMA 位于 E203 子模块 `rtl/e203/perips/`；入口为 `rtl/e203/subsys/xu_systembus_ingress32.v`。验证实现位于 [experiments/s3-y32-ingress-perf](experiments/s3-y32-ingress-perf/README.md)。

## 已完成与保留项

12 task RTL 实测 1691172 cycles / 304128 Y32 PASS，150 MHz 条件下 1064.350640 task/s。原约束、原库下最终完整 STA 为 0 数值时序违例、0 电气违例，仍有 4 unknown / 29332 untested。全 SoC 标准单元面积 357030.3072、加内部 33 SRAM 保守上界 658931.612862，均为原库单位。

最终映射经过 DC 回放、fresh PT、原件逐 SHA 回收及严格 mapped→mapped 结构证明。修复是映射 ECO，性能 RTL 与固件未改；不能把原始综合输出、23:50 冻结版或 GPIO 存储整合候选作为当前最终映射。完整依据与剩余项见[最终修复报告](docs/s3-y32-ingress-perf-postfreeze-repair-20261114.md)。

后续资格工作应先明确异步输入与释放的 CDC/RDC 合同，再核实 4 unknown 及 catch 的外部 required time；不能靠新增 false path、multicycle 或异步 clock group 宣称原有问题已通过。仍需 RTL→mapped FM、严格 mapped 带延迟任务、复位脉宽/亚稳态、物理多角、功耗、生产 loader/存储规则和官方 600 样本验收。当前没有最终比赛分数。

## 接手与协作

```sh
git submodule update --init --recursive
python3 -B tools/current.py verify --submodule
```

检查失败时先核对提交、子模块和原件，不覆盖冻结目录。新实验使用新的 `build/` 输出目录；保留输入、实际 argv、工具版本、失败原件和哈希。工艺库、许可证与 DDC 不在公开包内，原 EDA 工具含旧实验依赖，不应直接在空 build 中运行后将结果称为最终 ECO。

当前源码包含跨目录复用，`experiments/` 和旧生成源不能因名称为历史而直接删除。历史入口集中在[历史导航](docs/history/README.md)，本轮分支归档与恢复见[归档清单](docs/history/branch-archive-20261114.md)。新工作可按需建立 `codex/` 分支；修改子模块时先推送子仓，再更新父仓 gitlink。

本次仅整理父仓分支；其它工作树及其未提交文件、本地产物和用户资产保留。旧 S2e 原交接已移至[历史归档](docs/history/s2e-20261105/HANDOFF.md)。

四项 unknown 的最新诊断、数字回归与板级待确认项见[2026-11-14 跟进](docs/s3-y32-ingress-perf-unknown4-followup-20261114.md)。本轮仍未闭合，不改变当前候选身份或结果。
