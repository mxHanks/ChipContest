# 原 1064 候选：四项 unknown 跟进

**本轮未将四项 STA unknown 闭合。** 已完成逐身份归因、同版本 PrimeTime 原生 API/文档探测、真实生产 RTL 数字边界回归，以及防止误判闭合的验收门禁。现有 1064 候选、原约束和冻结结果保持不变：0 数值时序违例、0 电气违例、4 unknown / 29332 untested。暂无板级规格，相关保证列入[异步输入合同待确认表](s3-y32-async-input-contract.md)，不代填数值。

## 四项的实际位置

以下路径相对于 `u_soc/u_e203_subsys_top/u_sirv_aon_top/u_sirv_aon_wrapper/`：

| 检查端点 | 类型 / 接收时钟 | 来源与结论 |
|---|---|---|
| `bootrom_deglitch/T_8_reg/D` | setup / LF | BOOTROM_N；现有去毛刺同步链首级 |
| `dwakeup_deglitch/T_8_reg/D` | setup / LF | DWAKEUP_N；同型同步链首级 |
| `u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN(rise)` | recovery / LF | 外部 ERST；异步置位、LF 清除 |
| `u_sirv_aon/u_sirv_pmu/erst_reset_r_r_reg/SDN(rise)` | recovery / LF | 同一 ERST 直接作用于第二级异步端，不能用内部 LF 路径替代 |

原 SDC 对这三根 pad 使用 HF launch 的全局输入延迟，实际四个接收 CK 都为 LF。HF=6.666666667ns，LF=30517.578125ns。原生 PTE-052 说明这一周期尺度下展开不足可能无法构造跨时钟 required；先前添加身份 BUF 只能改变传播和数值 min 检查，不能生成缺失的 required。

## 已完成的核查

- **RTL/映射一致归因。** 去毛刺已有 T8→T9→sync→last；PMU 为两级 ERST 异步事件保持，LF 恢复后逐拍释放。未发现可在保持功能和原约束的前提下，通过普通加寄存器、换时钟或缓冲直接消除 unknown 的接线错误。
- **原生工具探测。** 扩展检查 period/cycle/common/base/clock/resolution/precision/ratio 变量族，并用该版本有文档的 `get_app_var -list/-details` 检查注册项及用途。新发现的 `timing_max_normalization_cycles` 只控制归一化 slack 的分母；`timing_path_arrival_required_attribute_include_clock_edge` 只控制属性数值是否含时钟边沿。两者都不是 PTE-052 展开修复，未作猜测设置。没有发现已证实可用的新展开控制或单个 launch/capture 时刻枚举入口。
- **数字功能边界。** 实际编译七个生产模块，34 场景/178 断言通过，包括停钟捕获、十个释放相位、四态 X 与原因优先级。没有把数字 PASS 当成亚稳态或物理签核。
- **闭合门禁。** 精确解析跨行 coverage，绑定冻结四项完整身份、原 SDC/PT-add、双库、最终 mapped 和干净执行回执。原四项须显式成为 native met，并保持所有其它检查身份/状态及原约束一致；删行、双边改名、改为 disabled/no_clock、改 summary 或漂移约束均拒绝。14 项测试通过；现有原件仍返回 `UNKNOWN4_NOT_CLOSED`。

原生探测只运行空设计的只读查询，未重综合、未改网表、未重跑相同完整 STA 或 CPU12。前两次空设计会话有 Library Compiler 路径启动错误 PT-063，保留为诊断记录；r3 修正启动环境并绑定原 Library Compiler 路径后，2 核、RC0，实际 Error/Fatal=0，28 份 payload 全部逐 SHA/长度核验。该结果只证明空设计 API/手册探测完成，不能将其或前两次写成新完整 STA 验收。

## 为什么不能靠延迟或显示精度完成

标称 150MHz/32768Hz 的共同周期已需 1,171,875 个 HF 周期和 256 个 LF 周期；原 SDC 的十进制周期另有微小差异。提高报告位数不改变这个尺度。原约束还有相距约 0.026025ns 的 HF/LF 边沿见证；即使工具补齐展开，也可能暴露真实负裕量，不能预设 unknown 必然变成 met。该算术是诊断见证，未冒充原生 slack。

对可任意相位变化的异步输入，有限固定延迟无法保证首级永远远离采样/恢复窗口。已有多级同步链处理的是这一异步风险，其签核需要真实接口合同、工艺同步器/MTBF 与物理实现。新增例外或改变输入 launch 关系会改变验收合同，本轮没有这样处理。

## 闭合所需的下一步

1. 对原约束分析，需取得 Synopsys 对当前版本的受支持解决方法/补丁，或用已证实能完整处理这些时钟关系的工具返回真实 required/slack；保留原频率、IO、uncertainty、库和覆盖。若出现负 slack，再按真实路径修复。
2. 同时补齐 BOOTROM 稳定窗、DWAKEUP 脉宽、ERST 脉宽/撤销及 LF 停钟协议，再完成整机 CDC/RDC、同步器物理和复位脉宽验收。若采用新的异步约束，单独记录其依据与口径，不能冒称原 SDC 四项已通过。

目前这两类外部依据尚未齐备，四项明确保留未闭合。没有修改生产 RTL、原始 SDC 或当前候选 manifest，也没有更新吞吐、面积或签核结论。

## 复核命令与证据

```sh
# 报告当前四项，report 成功只表示解析成功
python3 -B experiments/s3-y32-ingress-perf/ppa/eco/unknown_checks.py report

# 当前原件应返回非零，明确未闭合
python3 -B experiments/s3-y32-ingress-perf/ppa/eco/unknown_checks.py report --require-closed

python3 -B -m unittest discover -s tests/ppa -p test_unknown_checks.py
python3 -B experiments/s3-y32-ingress-perf/ppa/eco/run_async_contract.py --out build/unknown4/digital-new
```

[本轮证据导航](validation/s3-y32-unknown4-20261114/README.md)；[当前冻结修复报告](s3-y32-ingress-perf-postfreeze-repair-20261114.md)。未来证明全部身份保持时需同一固定映射的完整 baseline 与 candidate `report_analysis_coverage -status_details {met untested violated}`，不能仅凭 met 汇总增加四项判断闭合。
