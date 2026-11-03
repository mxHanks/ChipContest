# xu 独立证据范围审查（08 / 09 / FM09 与 PE32 profile）

本审查读取本目录原始08/09/PT/FM报告、执行Tcl、state及当前工具源码，不访问服务器，不修改checker或已测32PE源码。审查时PPA工具`tools/scripts/xu_soc_ppa.py`的SHA256为`ffe6076833a97058cb9d345eee175ec5988c12c801dfb50621b059608545e698`；初版本目录checker的SHA256为`15ce2fac02d71f4ac17ab5c1b89d22d3032779eb77be73b752ebd43b12fe44e4`。后续修复应单独注明生产者身份。

## 首要发现：5项仅是analysis_coverage时序检查，不是全部constraint违例

09的十类analysis_coverage共294512项，267380项met、5项violated、27127项untested。其中setup/hold各67251项已测均met，各3790项untested；27项clock-gating hold全部met。08同一表的clock-gating hold为8 met /19 violated，故这19项确实被09消除。不能把这些表格结论扩大成完整150MHz资格。

两个版本原`constraints.rpt`还各含**56个max_capacitance和1404个min_capacitance违例pin块，共1460个电气DRC块**。它们不在上述十类analysis_coverage统计中。09报告共有1465个`(VIOLATED`字符串，其中5个来自reset removal，1460个来自电容约束。下面两个例子均保留原文：

```text
Pin: u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave/U42/ZN
    max_capacitance              0.05
  - Capacitance                  0.05
  ------------------------------
    Slack                        0.00  (VIOLATED: increase significant digits)

Pin: u_soc/u_e203_subsys_top/u_e203_subsys_main/u_e203_cpu_top/u_e203_cpu/u_e203_core/u_e203_exu/u_e203_exu_alu/U745/ZN
    Capacitance                  0.00
  - min_capacitance              0.00
  ------------------------------
    Slack                        0.00  (VIOLATED: increase significant digits)
```

`units.rpt`确认电容单位为1e-12F、时间单位1e-9s。打印的`0.00`不能推导真实值或负slack幅度，更不能改写为零违例。需要在**相同09网表、相同DB、相同原SDC与scope16**上另起只读高精度报告，例如版本支持时使用`report_constraint -all_violators -verbose -significant_digits 8`；若该版本拒绝选项，保留失败并使用支持的高精度查询，不改阈值或删除约束。本审查没有执行该后续诊断。

可在本目录只读复现分类（两个group替换运行；按pin块计数，不把capacitance和timing check混为同一种计数）：

```python
import collections, re
from pathlib import Path
text = Path('raw/full-soc-gating-margin-repair-20261103-09/constraints.rpt').read_text()
counts = collections.Counter()
for block in re.split(r'(?m)(?=^    Pin: )', text)[1:]:
    if '(VIOLATED' not in block:
        continue
    kinds = [k for k in ('max_capacitance', 'min_capacitance', 'max_transition',
                         'min_transition', 'max_fanout')
             if re.search(r'\b' + k + r'\b', block)]
    assert len(kinds) == 1
    counts[kinds[0]] += 1
assert counts == {'max_capacitance': 56, 'min_capacitance': 1404}
```

初版checker只检查十类时序表、未分类这些电气DRC，因此输出不能解释为已核完全部约束。该发现已交root补checker和说明；本文件不修改原报告。

## 实际仍未闭合的时序范围

09的五个removal负slack均从原始ERST输入到LF域异步reset端，`hold.rpt`有高精度数值：PMU `erst_reset_r_reg`为-0.12148283ns、`erst_reset_r_r_reg`为-0.11847966ns；AON `reset_n_catch_reg/reg_0/q_reg`、`reg_1/q_reg`、`reg_2/q_reg`各-0.04010564ns。两级/三级结构存在不能自行替代异步释放协议、脉宽或RDC/MTBF论证；没有因此许可宽泛reset false-path。

27127项untested的报告原因是constant_disabled17672、no_clock9129、false_paths276、no_endpoint_clock48、unknown2。no_clock的pin后缀分解为RDN8676、SDN429、E24；no_endpoint_clock为48个D检查，unknown为2个SDN检查。这是报告分类，不能把constant_disabled当成全部功能模式不可达，也不能把no_clock/unknown当作met。24个UART latch E是真正的寄存器时钟/使能检查范围，不能与先前672个SRAM CEN/RET1N控制pin的错误“clock”分类混为一谈。

09 `check-timing.rpt`还明确报告31个maximum-delay unconstrained endpoints、24个register clock pins without clocks、1个period不expandable的clock set。31项包括UART latch D、5个forwarded GPIO clock输出和2个PMU SDN端；这不是27127之外另加31个唯一物理点的结论，两类报告存在重叠。非整比HF/LF/JTAG时钟集合的展开警告需要模式/异步关系审查，不能只凭max summary打印0.000000宣布时序合格。

09 DC仅为优化增加clock-gating hold到0.12ns，最终PT仍源原0.1ns定义的SDC；原SDC SHA为`404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。但分析还显式应用scope16 proposal（SHA `45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e`）：70个精确首D异步边界及6个forwarded generated clocks。因此准确表述为“09相对08保持相同原SDC+scope16分析条件、未放宽最终gating阈值”，不能省略scope16后声称与原始零额外exception的baseline完全相同。报告使用ideal pre-CTS clock，不要求本赛题没有要求的P&R，但仍须闭合现有模式/覆盖和电气问题。

## FM09支持的是有条件的端到端mapped一致性

实际FM `verify.tcl`读取原prepared RTL、原始/08/09三份SVF及09 mapped.v，`state.json`中158份输入before/after完全相同，implementation网表SHA与09 state一致：`5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca`。原FM确实exit0、单一PASS marker、Verification SUCCEEDED。

41462 passing包括17136 BBPin、144 Port、24143 DFF、39 LAT；511 DFF为Not Compared/Unread。另有17个reference-only unmatched DFF：16个W adapter valid_read_reg及固定PMU count_reg[15]；matching摘要还单独报告144个reference-only unread points，不能与最终511表直接相加当作655个唯一点。auto_setup明确采用`verification_set_undriven_signals synthesis`与`verification_verify_directly_undriven_output false`；原日志还警告RTL解释/越界索引可能与logic simulator不同。

SRAM是black box，17136个BBPin通过验证不能证明SRAM内部状态、数值、未知值传播、byte mask、宏模型时序或功耗。`hdlin_unresolved_modules black_box`也是此会话的明确条件。应保留“在上述macro/undriven/auto_setup及未比较范围下，已匹配点的原RTL→09 mapped一致性通过”，不能改写为无条件全SoC等价或完整比赛资格。08/09的DC/PT状态和FM PASS都不替代数值/正式任务窗口/全范围能量验收。当前checker状态含CONDITIONAL和TIMING_NOT_QUALIFIED方向正确，但其初版用任意`'511' in log`检测unread计数过宽；后续宜解析最终Not Compared行和匹配类别，而非任意数字子串。

## PE32合入兼容性与实际sourceguard缺口

独立比较当前工具与28e394a：baseline、H2-only、SRAM-bias、S2b、S2c五个template与macro-check Tcl均逐字节相同，原mapping identity相同，clock-contract Tcl相同；`source_profile_identity`对子仓的完整blob/mode/replace防护AST也相同。PE32新增分支只采用自己的352宏几何和wrapper参考；未发现默认baseline被静默切到32PE的回归。新增拒绝旧profile携带XU_ACCEL_PE32 define属于显式防错，不改变默认8PE生成。

发现并在**临时独立main/child clone、dummy DB、未运行EDA**中实际重现：PE32目前只用main HEAD值匹配94ce6f0，没有对main工作树实行与child同样的完整blob/mode核验。将临时main的`tests/e203/tb_accel_soc.sv`从`always #2 clk = ~clk;`改为`#3`，再设置assume-unchanged，`git status --porcelain`为空，实际`generate(..., profile='s3-pe32')`仍返回GENERATED_NOT_QUALIFIED/352宏；inventory同时记录变后TB SHA和硬编码4ns描述，而实际TB已为6ns。

```text
main:  94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114
child: fc3977d0a6d5f85fbfd871fd9439c01c9acab5f5
原TB SHA: ea8e2b054a06c759a122e60d00938435d4cfef3f509c437313eaed44c8fd395e
变后 SHA: 1f7ef8d8969df7c59a094539d04e3753ac4dcc1b3f6649f26c4b875b779b92c6
```

重现的核心步骤是clone批准main与child到临时目录、修改上述TB、`git update-index --assume-unchanged tests/e203/tb_accel_soc.sv`，然后用当前producer的`xu_soc_implementation.generate`和明确无效的两份HOST dummy DB执行s3-pe32准备。临时树已清理，原32源码未修改。该结果证明sourceguard边界，不是server launcher绕过或任何已测硬件收益的反例。

既有三路真实VCS部署证据已另经全部2510源路径与冻结Git核对通过，不能把工具存在此隐患自动等同于服务器源码发生变化。建议下一版只对PE32增加main完整tracked blob/mode/gitlink核验、index assume/skip及git-replace独立防护，并拒绝额外active/untracked代码；旧profile生成合同继续保持。root已授权在独立PPA工作树实现此修复，运行中的6798生产者保持原样，新核验结果必须使用新输出和新工具身份。
