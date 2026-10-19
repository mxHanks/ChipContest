# 依赖与验证边界

## 本包可独立进行的操作

`tools/verify_bundle.py` 检查归档文件SHA-256、复制来源索引、文件集成员、重复模块定义、已声明module依赖和Python语法。该检查是静态完整性检查，不是Verilog elaboration或语义证明。`tools/run_host_checks.py` 只运行数值辅助函数与现成的C快照一致性fixture；不启动EDA、网络访问或远端任务。

HDL文件集记录于 `metadata/dependencies.json`，从包根使用 `filesets/*.f`。仿真模型仅用于行为参考。各组的top与源集合已列明；当前打包主机PATH没有Verilator/Icarus，故本次不报告新RTL仿真PASS。未来应在新工作区配置Verilator/C++并审查实际编译诊断，保留必要四态检查。

## 未打包且需要另行取得

| 依赖 | 用途/状态 |
|---|---|
| 组委会E203 SoC工程与软件环境 | 尚未提供；System Bus/NICE协议和可接入点待检查，不能假定兼容原AXI64 |
| 比赛标准单元库、SRAM宏及模型 | 尚未提供；用于映射面积、时序、仿真与功耗 |
| KWT指定权重、源码与Speech Commands V2 | 未下载；按固定提交/划分提取数据，保存版本和SHA |
| 新前馈RTL、偏置/量化实现、E203驱动、SDC | TODO；本包没有虚构占位实现 |
| Verilator/Icarus及C++工具链 | HDL参考测试所需；本次本地主机仅执行Python/GCC辅助检查 |
| AMD Floating-Point/XPM | 只有历史接口包装器与行为模型；不属于比赛最终实现，未分发AMD库 |

`reference/fpt/python/flash_attention_tile_model.py` 中的位级转换辅助函数可直接导入。其完整Attention/board-vector CLI还依赖未收集的旧Golden数据，本包不把该CLI作为运行入口。`reference/fpt/tests/check_cats_r4_fp32_reference.py` 的纯数值函数可导入，旧Windows CLI仅作方法参考。

`reference/fpt/docs/` 保留历史接口说明，里面的绝对路径/外部链接仅用于追溯，部分目标不在本包。它们不参与包内检查，也不代表本比赛实现或完整FPT发布。

## 验收层级

| 项目 | 本包含义 |
|---|---|
| 文件校验/迁移复核 | 以包旁 `.verification.json` 和SHA文件为准 |
| Python数值辅助/C快照 | 以本次报告host检查为准，仅主机软件 |
| KWT完整软件数值模型/误差 | NOT_RUN，尚未实现 |
| 新比赛RTL仿真/SoC仿真 | NOT_RUN |
| 比赛综合/150MHz/面积/功耗 | NOT_RUN |
| FPGA实现/Bitstream/硬件 | N/A（赛题不要求）；原FPT状态不转移到本题 |

最终参赛验收必须以新设计的同一冻结配置评测；FPT的历史数值或综合结果只说明来源背景。原FPT当前存在活动运行的历史记录，本次未连接、修改、迁移或重启该运行。
