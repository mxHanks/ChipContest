# unknown4 本轮独立复核

结论：**门禁修复与数字功能证据复核通过；4项STA unknown仍未闭合。** 没有发现新的、已获原生文档证明的共同基周期展开控制。r1/r2启动日志存在PT-063，不能称为clean原生环境执行；其已成功输出的原厂man与变量发现可用于诊断。**r3已回收并独立补核：28份payload全部SHA/长度正确，rc=0、native_tool_errors=[]，实际native.log没有Error/Fatal，2核，仍未加载设计或改约束。** 两份关键变量man与r2逐字节相同，文档终结判据不变。

本复核只读现有证据、代码及限定单测；没有运行EDA、CPU12或重跑数字bench，没有改源/Git。本文件是唯一写入。

## 原生文档终结判据

- r2的28份catalog负载已独立逐SHA/长度全部通过。10份man的discovery-status均为0，包括新增两变量。
- `timing_max_normalization_cycles`默认4，原生手册明确限制的是**normalized slack的分母**：允许传播时间最多取该值乘launch clock period。它依赖已经存在的absolute slack，不能扩展PTE-052共同基周期，也不能让缺失的required出现。故不值得将其改大再重跑当前设计。
- `timing_path_arrival_required_attribute_include_clock_edge`默认false，只决定path的arrival/required属性是否加launch/capture clock edge时间；true时可与report_timing显示值一致。它不是计算时钟关系的开关，不能把unknown转换成有效slack。
- 注册变量列表与原生`-details`未找到有文档支持的其他有效clock展开控制。get_timing_paths/report_timing的极性selector、start_end_pair、PBA不构成新的完整事件展开机制。没有证明未公开功能永远不存在；当前可用文档范围内，继续猜变量/重复同一STA没有新依据。
- r1/r2 `native.log`均保留PT-063（Library Compiler路径未设置）。这是未加载设计/库的文档发现，手册仍完整输出，不能据此声称完整EDA环境检查通过。r3已修正启动环境并收紧Error/Fatal判定；独立核实实际日志Error/Fatal为0，probe.tcl SHA与当前源码一致，仍仅作空设计发现。r1/r2原件保留且不算clean。

## unknown门禁三项修复：复验通过

`unknown_checks.py`已做到：原四项identity五元组固定，原冻结coverage文件SHA固定；baseline与candidate都要真实clean reload schema/status/marker、timeout=false及rc/errors校验；原始SDC、PT兼容SDC输入/实际输出、双库及指定最终mapped签名一致。舍入clock报告现在只是辅助核对，不再独自承担原约束身份。

本次仅独立运行以下4个针对性测试，**全部通过（0.259秒）**，没有重复其余已运行的常规测试：

1. `test_both_sides_renamed_unknowns_cannot_redefine_the_baseline`：双边改名不能偷换原四unknown。
2. `test_false_marker_timeout_or_wrong_native_stage_is_rejected`：false marker/timeout/错误schema、status、stage均拒绝。
3. `test_sdc_library_map_drift_is_rejected_even_if_clock_table_matches`：相同clock文本下SDC、PT-add输入/输出、库或map漂移均拒绝。
4. `test_frozen_reference_cannot_be_replaced_by_a_new_baseline`：冻结原coverage不能被新baseline替换。

完整14项是主代理/实现代理的既有测试范围；本次独立复验没有把4项写成独立重跑14项。当前原件仍4unknown，不能报UNKNOWN4_NATIVE_COVERAGE_CLOSED。

## 生产RTL数字合同bench：仅数字功能范围通过

独立阅读 `run_async_contract.py` / `tb_async_contract.sv`，与最新 `async-contract-run/selected-final/result.json` 及simulation.log核对（旧final receipt仅作历史）：

- 编译实际生产deglitch、reset-catcher、完整sirv_pmu及真实子模块，共7份生产源；加TB/runner共9源的SHA/长度全部与当前文件相符，输出二进制/编译日志/仿真日志哈希也全部匹配。最新runner还绑定18798字节candidate manifest SHA 787d54b5…，固定当前候选及RTL commit，并拒绝脏子模块；运行后再次核manifest、源及child身份无漂移。最新receipt SHA为 `bf3f963c63f79f23ba8c2d729a24e3dc5568f41608a35a9da774b19cb4693509`。子模块为5470c565，工作区干净。未发现替身PMU、force、初始化后门或X→0转换。
- 真实final日志34个CASE index严格为1..34，唯一PASS标记为178 checks、10 release phases、4 stopped pulses、14 priority masks；HF/LF边沿926972/199。与receipt逐项一致。
- 验证包括真实初态X、短脉冲过滤/稳定输入延迟、X传播及恢复、LF停摆时ERST数字事件捕获、复位原因优先级/保留和重叠释放。主要断言观察public输出；PMU内部两级只用于明确的捕获/释放行为。
- receipt、runner docstring、TB注释和最终日志均明确**数字四态功能合同，不是CDC/RDC或STA闭合**。1fs脉冲只是数字事件，不是板级最小复位脉宽；接近LF边沿的offset是事件排序测试，不是recovery/removal或亚稳态证据。确定性数字时钟与10个offset不能穷尽物理任意相位或建立MTBF。bench没有改原SDC、生产RTL、最终map或冻结吞吐。

## 文档草案事实快审

`docs/s3-y32-async-input-contract.md` 与 `docs/s3-y32-ingress-perf-unknown4-followup-20261114.md` 已只读核对：当前候选、原SDC与吞吐/面积未变，0数值/0DRC/4unknown/29332untested口径正确；明确用户暂无板级规格，所有脉宽、稳定窗、停钟、CDC/RDC与物理保证均标待确认，不代填数值，不把数字PASS或归一化变量写成原STA四项已met。未发现需要阻止交付的事实矛盾。

## 本轮结束边界

用户已确认暂无板级规格，因此应整理待确认的异步输入稳定窗口、ERST断言最小脉宽、LF可停摆范围、上电/POR与test-mode、接收端允许采样/释放行为及CDC/RDC验证依据。没有这些外部事实与工具支持，4unknown保留未闭合；不能由数字bench、归一化slack、属性显示或新增例外代替。

## 审查身份

```json
{
  "experiments/s3-y32-ingress-perf/ppa/eco/unknown_checks.py": "4dcf6a3d596d46aedfdcfd941d3c553e8ddf1e29d4154f22f7ff0cacbb2b34c2",
  "tests/ppa/test_unknown_checks.py": "af598de6f5f69e5950f6a43297485477c39dc3c09fe82917acd75cef0b4f30f5",
  "experiments/s3-y32-ingress-perf/ppa/eco/run_async_contract.py": "a92efc9a2eb496ec34f8634c37a260614d6631392365075d0084e486241a56e8",
  "experiments/s3-y32-ingress-perf/ppa/eco/tb_async_contract.sv": "2a40ce19cf3babe6c290612990d1287757c13e9aeee15d776f969fea1468d2a4",
  "r3/execution.json": "8c07f783a0f0ca9f28843652d29192b5230552fabcca88419acd317c46453aac",
  "r3/manual-timing_max_normalization_cycles.rpt": "3d219c643b5cb46b85334c93f804bfed05dcd1e4f7185a84ac1d42939ecb23d8",
  "r3/manual-timing_path_arrival_required_attribute_include_clock_edge.rpt": "c954f37a36650248b7ed897edfbe48d09850c93605c457d77a776cc2d5a977a9",
  "r3/probe.tcl": "026647cee078158d0d6db156cd099dc28a2ef4b1bf0187519b18914d2856e52e",
  "r3/native.log": "5263516c0ebf313cdef8431f6935989053e44da96ef70921146ad24e0da50cd4",
  "digital-selected-final-result.json": "bf3f963c63f79f23ba8c2d729a24e3dc5568f41608a35a9da774b19cb4693509"
}
```
