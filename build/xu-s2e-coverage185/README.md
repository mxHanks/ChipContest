# xu185：S2e own155 覆盖缺口的原件分类

对 own155 原始报告逐条分类，**没有解除任何资格门**，没有改图、SDC、时钟方法、模型、TB 或生产代码，也没有新 EDA/远程操作。
原包159与125全部成员都已按原 manifest 重核，52份155/25份120实际消费正文的精确SHA列在 `inputs185.json`。
原生警告原文和行号完整保存在 `native-diagnostics185.json`；原包不变。

| 原生 reason | 条数 | 真实分类 |
|---|---:|---|
| constant_disabled | 17,672 | min_period 10,416；setup/hold各3,628 |
| no_clock | 9,219 | **全部是 min_pulse_width**：RDN(low) 8,766、SDN(low) 429、UART E(high) 24 |
| false_paths | 276 | 70个不同D端点的setup/hold及不同clock检查；每个端点都出现在本图exceptions报告 |
| no_endpoint_clock | 48 | 24个UART D各setup/hold一项 |
| unknown | 2 | 两个PMU SDN(rise) recovery，相关CK(rise)、xu_lfextclk、ENABLE_NOT_D条件 |

**纠正“9219缺钟”的粗略描述：这不是9219个寄存器CK缺少时钟。**
`check_timing`实际列出的寄存器缺钟是24个UART `fifo_tx_data_reg[0..7]/E`，分别位于UART0/1/2。
同24个cell的D还占48个no_endpoint_clock。
159没有返回final mapped/native-cells正文，现有E命名不足以独立确认这24个cell的精确ref和latch属性；后继native查询需补证。

27217条检查全部保留在 `untested185.csv`，包含原pin、类型、reason、condition、clock、层级、源行和原块SHA；不按端点去重，也不把名字中的字面点转成层级。
original-inventory、posthold-inventory与final三阶段未测检查多重集合完全相同（新增/减少均0）。
这说明现有修复没有消除这些覆盖缺口，不能据此豁免。

constant_disabled中的10,416个min_period检查覆盖336个SRAM宏、每宏31个条件分支。
这只给出当前原生分析模式下的禁用事实；原报告不包含全部可达模式和每项active条件的完整证明，不能自动视为合格。
false_paths也只核对到本图异常端点存在，没有取得CDC/模式正确性豁免。

31个最大延迟未约束端点已核实为24个UART D、2个PMU SDN、5个GPIOA输出。
5个GPIO输出同时出现在本图forwarded-clock source与5条UITE-485拒绝output-delay警告中，属于可核对的关联，仍不能自动豁免端点约束。
两项PMU recovery unknown与五项HF_RESET定向零路径部分重叠，不能重复计成七个coverage未知。
五个原HF recovery报告均为 `No constrained paths.`；相同选择的removal有路径，另外三个LF watchdog recovery也有路径。
原查询带slack filter且采用默认受约束可见性，零路径不证明不存在物理检查，也不证明recovery通过。

3个PLIC Q输出的native min_capacitance仍失败：load=0 pF，limit=0.000500000024 pF，slack=-0.000500000024 pF。
`check_timing`的“1项period不可展开”是**一个含四个时钟的clock set**：HF、JTAG、LF和PLL envelope；PTE-052/PTE-016原文保留。
此外32条PT警告中，18条PTE-060表示指定pin对没有推导clock-gating check，不能因表内27项gating check均met便忽略；6条UITE-416 invalid-start-point同样保留。

RDN(low)、SDN(low)、E(high)三类的原报告只有 `min_pulse_width/no_clock` 标识，没有返回逐ref/libpin的数值库宽度或hold表值，因此数值明确为null，未套用别图VCS的10ps。
实际120的12层RTL原件均记录内部 `ACCEL.rst_n` 在实际ACCEL clock上4594次采样为asserted，首末采样跨度30,620,000,000 fs，并检查空FIFO readiness。
它能证明该RTL观察点的reset readiness；**不能证明final155全部RDN/SDN/E的连续物理脉宽、库min-width检查，更不能等价于相对每个本地clock的recovery/removal。**
正式SAIF窗口在reset/clear之后，不能补出启动阶段的全部异步pin波形；UART E高脉宽也不由accelerator reset证据覆盖。

`targets185.json`给出后继最小只读查询的精确UART E/D、两PMU SDN、五HF源/目的、GPIO、PLIC pin，以及own155 `3440182e…`、自己SDC `404c7de9…`、`45037c4a…` scope方法和两库身份。
后继只应在同图/同方法上枚举native ref、库pin/arc、clock/case/constant及实际driver，区分active/untested条件，查询原选择与无filter可见性。
timing_arc按owner/index/from/to记录，不访问不支持的full_name。此处只提出查询，未实现或运行。

复现（仅本地，输出可指定新目录）：

```sh
python3 -B build/xu-s2e-coverage185/analyze185.py
```

所有分类继续标为 `NOT_QUALIFIED`；完整功能、150MHz、存储及能耗资格仍需独立补齐。
