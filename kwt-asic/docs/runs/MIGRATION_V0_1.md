# migration-v0.1 验证记录

日期：2026-10-14，Asia/Shanghai。范围是导入的FPT参考资产和迁移工具，不是新KWT比赛验收。

## 实际结果

`source env/activate.sh && python3 scripts/verify/run_checks.py --tier rtl --jobs 2` 返回0。

- Run ID：`20261014T145158.643282Z-417300cf`。
- 总耗时：12.501秒，包含静态/host/默认RTL编译与仿真。
- 原始输出：`artifacts/runs/20261014T145158.643282Z-417300cf/`。
- 24份轻量原始日志副本：`docs/runs/reference-smoke-logs/`，映射与SHA见 `reference-smoke-log-index.json`；不打包生成的C++模型和可执行文件。
- 可搬迁结果副本：`docs/runs/reference-smoke-result.json`。其中历史绝对路径指向当次机器，是来源记录；在新工作区重跑会生成新路径和报告。
- 完整性：59个SHA记录、35个源文件、11组文件集；额外逐字节核对60个ZIP成员以及两份PDF一致。
- 软件：65,280个有限BF16往返、6个RNE边界、11个Fraction FP32向量；C快照一致性16例。

| 参考RTL组 | 场景 | 工具 | 结果 |
|---|---:|---|---|
| reset_edges | 1 | Icarus12.0四态 | PASS |
| async_fifo | 1 | Icarus12.0四态 | PASS |
| slot_bank | 1 | Verilator5.020双态 | PASS |
| service_observer | 默认+completed_overflow | Verilator5.020双态 | PASS |
| service_counter_adapter | 默认+registered_producers | Verilator5.020双态 | PASS |

未选择的6组（QK服务、QK请求缓冲、QK调度、banked owner、bank bridge、FP32向量）仍为 NOT_RUN；不因为文件集存在就报PASS。Verilator编译的警告保留在原compile.log，PASS只说明选定行为场景成功，不代表lint无警告或综合通过。

## 环境修复

首次 PATH 没有 Linux HDL 工具。已下载 Ubuntu Icarus12.0、Verilator5.020并解压到`.tools/eda`；使用包装器定位Icarus后端和Verilator include/bin。初次Verilator版本检查暴露可重定位路径问题，已在bootstrap中创建项目内后端链接，后续版本查询及实际编译通过。没有修改原FPT代码。

## 已知缺项

新KWT数值模型/RTL、真实权重输入、完整12层误差、E203驱动/SoC、指定库/宏综合与PPA均未验收。已读取的固定上游配置与指南一致为64/256/12；真实checkpoint形状仍需实际加载核对。完整数据下载和旧TensorFlow兼容环境留给下一工作单元。

最小检查在当前环境可数十秒内重跑；新RTL、工具适配和失败定位的主动工作才是工期主体。估时和明天目标见 `docs/MIGRATION_PLAN.md`。

## 可搬迁性复核

将源码候选包解到全新 `/tmp/kwt-relocation-*/`，复制已验证SHA的软件包缓存，在新位置执行bootstrap、make rtl、harness validate及12项自检，全部退出0，总耗时13.904秒。证据为 `relocation-check.json` 和 `relocation-0.log` 至 `relocation-3.log`。最终归档仅增加这份复核证据和最终状态，运行时代码不变。最终压缩文件另由harness逐文件核对清单并生成SHA256SUMS。
