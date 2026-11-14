# 4 unknown：PrimeTime 原约束解析能力审查

当前结论：**没有找到已证实可用、保持原时钟/IO/例外语义不变、直接将4项unknown变成真实required/slack的T-2022.03入口。** 此结论不等于数学上证明所有隐藏功能不存在；值得执行一次更完整的空设计原生API/变量发现，发现有原厂文档支持的有效控制项后才进入设计级验证。重复现有STA、修改报告精度或只开启unconstrained报告不会建立required time。

本审查只读当前main（检查时14b2ed5）、既有本地原件和Synopsys官方公开材料，没有运行远程EDA，没有改RTL、SDC、代码或Git。主代理已复现UNKNOWN_CLOSURE=FAIL4；该反馈作为症状基线。本文件不是新原生签核。

## 已有一手证据与数值

1. **同版本原生PTE-052手册**（T-2022.03-SP5-1）说明：工具先按真实路径及传递关系构造相关时钟集合，计算共同基周期；当最小时钟最多1000次展开仍短于最大时钟周期时，无法按单周期规则算出某些跨时钟路径约束。手册没有给出提高1000/101限额的变量；其建议的异步false-path处理会改变当前验收语义，不能自动应用。
2. 已回收的 `printvar *waveform*` 只出现CCS波形计算、功耗波形和脉宽变量；`printvar *expand*` 未命中。**这只是这些匹配式未找到，不足以证明其他命名或未公开变量绝不存在。** CCS Advanced Waveform Propagation处理模拟波形畸变，与寻找两个时钟共同周期不是同一功能。Synopsys官方对AWP的说明也是低电压/小几何下的波形畸变建模：[官方说明](https://www.synopsys.com/blogs/chip-design/primetime-technologies-digital-design.html)。
3. 原SDC文件 `tools/ppa/xu_full_soc.sdc` 与基线SHA c15ede0f 完全相同；其HF period=6.666666667ns、waveform={0 3.3333333335}，LF period=30517.578125ns、waveform={0 15258.7890625}，JTAG period=100ns、waveform={0 50}；PLL envelope与HF同周期。所有primary clock在0ns有上升沿，原始setup/hold uncertainty均为0.1ns，原IO max=0.5/min=0。HF/LF比约4577.636719。即使把集合缩成HF/LF两者，**一个LF周期仍超过1000个HF周期**，所以仅移除JTAG或消除某个额外门控关系不足以解决根本尺度问题。原 `mapped.sdc` 导出只显示6.66667、30517.6等舍入值，不应重新读取它来声称保持原约束；原始参考SDC SHA为 `c15ede0fc2c65771f87e2d6aee763b4ea0d53934868ca807b4785c36182fce7c`，实际PT三处-add兼容转换SHA为 `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。
4. 旧async5原生 `edge-arrivals.tsv` 已在报告开关为true时，取到AON两个D的rise/fall最大到达0.673506/0.701467ns，PMU两个SDN约0.8418/0.8828ns；slack仍UNKNOWN。这些数据证明unconstrained报告开关确实生效，**再开一次同样开关不是未试修复**。catch3又独立验证分段arc上界，但它不生成HF→LF required/slack。

### 精确十进制、标称频率与binary64

以下来自本地Python `Fraction` / binary64精确分数运算，不是PT内部计算结果：

| 项目 | 数值/含义 |
|---|---|
| SDC精确十进制LF/HF | 30517578125000 / 6666666667 |
| 标称150MHz和32768Hz共同周期 | 7.8125ms = 1,171,875 HF周期 + 256 LF周期，两个计数均超1000/101 |
| SDC十进制HF在上述标称周期的累积差 | +0.000390625ns（0.390625ps），所以标称频率LCM不能冒充SDC精确LCM |
| HF解析为binary64 | 7505999379326127 / 1125899906842624 ns，误差约+3.2364e−16ns |
| LF解析为binary64 | 1953125 / 64 ns，恰好可表示 |
| HF单ULP / LF单ULP | 8.88e−16ns / 3.64e−12ns，远小于0.1ns uncertainty |

因此必须区分**工具主动近似共同周期**、**报告小数截断**和**double二进制表示误差**。PTE-052手册允许内部对浮点period作调整，但未披露其舍入算法。本地binary64算术不能证明PT内部一定使用该存储或精度；它足以排除“把显示位数调高就让周期比从4577降到1000以内”的推断。

原SDC还有具体边沿见证：LF第11沿为335693.359375ns，其前HF第50354沿为335693.333350118ns，间隔0.026024882ns。仅减去max IO 0.5ns和uncertainty 0.1ns，在暂设传播和库check为0的算术示意中已得−0.573975118ns。这**不是原生slack**；真实库setup/recovery可能含有符号和条件，必须使用真实检查弧。它提醒：成功展开很可能暴露真实负slack，不能预设unknown消失后就是MET。

## 新假说：按优先级与可证伪预测

| 假说 | 唯一值得尝试的新证据 | 成立/否证标准 |
|---|---|---|
| H1：合法限额控制项采用period/cycle/base等名字，旧匹配漏掉 | 一次空设计 `printvar` 的period/cycle/common/base/clock/resolution/precision/ratio族，加同版本man核对 | 只有注册项及其原生文档明确控制clock共同基周期展开才成立。普通Tcl `set` 成功、CMD-041新变量、CCS/PBA波形变量、报告小数变量均不成立 |
| H2：报告选择器/异常解释能揭示另一项真正缺失约束，PTE并非唯一原因 | 在H1文档发现轮同时取得 `man get_timing_paths`、`man report_timing`、`man report_analysis_coverage`；设计级只选4源/端点，读取unconstrained原因属性/`-exceptions all`（仅man证实的选项） | 若出现可修正的工具加载/关联错误，必须先核实其与原SDC合同一致。若required仍unknown且只有展开原因，则该报告法仅完成归因，不是闭合 |
| H3：文档存在指定单个launch/capture事件并保持全局周期检查完备的方法 | 查实际get_timing_paths/report_timing man是否提供这样的事件选择，并说明覆盖所有相关边沿的方法 | `-rise_from/-fall_from/-rise_to/-fall_to`只是极性/clock选择，`-start_end_pair`只是路径枚举，`-pba_mode`只是路径延迟重算；这些名字本身不能视为事件展开功能。没有明确文档即不执行猜测参数 |
| H4：原生数值精度/原SDC加载存在问题 | 查 `man report_default_significant_digits`、`man write_sdc`；原生period/waveform按API允许最高精度导出，同时核原约束SHA | 只修显示不会修分析。即使得出理想有理比，1000/101尺度限制仍存在；所以至多是诊断完善，不是主要修复方向 |

## 可执行最小probe建议

### A：一次空设计原生发现；主代理已准备批量执行

不加载网表，不编译，不设置任何猜测变量。用原PT版本/二进制SHA、2核上限，收集以下输出及非支持命令错误：

```tcl
foreach pattern {*period* *cycle* *common* *base* *clock* *resolution* *precision* *ratio*} {
  printvar $pattern
}
foreach topic {PTE-052 get_timing_paths report_timing report_analysis_coverage get_app_var report_default_significant_digits create_clock write_sdc} {
  man $topic
}
help *clock*
```

若某个命令/变量不受支持，记录后停止该分支；不要改成普通 `set` 伪造。probe仅打印应用变量族，不应导出环境变量、许可证或凭据。`get_app_var`手册用于确认能否列出尚未匹配的注册变量。原厂手册和注册变量名未给出可调上限时，H1在此版本的可用公开API范围内判否，不再反复启动相同查询。

### B：仅在A发现新信息后的一次4端点设计级probe

固定当前最终mapped `d83acb49...`、双库、原始SDC及其PT兼容转换SHA；不写任何约束、例外、case、时钟/频率/相位/IO变更。精确4端点为wrapper的bootrom_deglitch/T_8_reg/D、dwakeup_deglitch/T_8_reg/D，以及u_sirv_aon/u_sirv_pmu/erst_reset_r_reg/SDN和erst_reset_r_r_reg/SDN。对应外源分别是bootrom、dwakeup和ERST。

- 若H1找到原生文档支持的纯分析限额，只变更该一项；立即记录原值/新值与文档，并取4条真实max路径、required、slack、launch/capture事件和完整coverage，观察是否得到数值。成功条件是原有checks身份保留且真实required/slack可算，**不是要求结果预先为正**。如果生成负slack，应报告新暴露的实际违例，再处理设计/接口。
- 若没有新限额但H2的未约束原因尚不明，只做每端点1条max路径、无slack filter的异常解释及path属性读取；先查native timing_path属性目录，不猜 `endpoint_unconstrained_reason` 等属性是否存在。对于找不到路径的检查保持UNKNOWN，不用0代替。
- min、LF内部recovery、pin聚合arrival及native arc求和均不得替代精确外源HF→LF max检查。
- 只做诊断时不重跑CPU12、不重复DC综合/回放；分析设置要恢复原值，另存证据，冻结最终候选不变。

## 不应作为修复的替代路线

- 新增false path、异步clock group、multicycle、ideal network，或移除原有clock-gating检查：改变约束覆盖，不能满足本次原合同。
- `set_max_delay -datapath_only`、添加虚拟同频参考clock、重定输入delay到LF：是在建立新的required合同，不是恢复原有合同。
- 单独HF场景/LF场景、删除真实时钟后证明各自通过：丢失跨域检查。
- CCS waveform propagation、PBA或提高报告precision：没有原厂文档说明它们能提高周期展开上限，不能凭名称类比。
- 把HF编码成长superperiod和很多脉冲，或用shifted/superimposed clocks模拟单次事件：即使物理边沿集合可能可构造等价，仍改变原clock.period/波形语义与min-period/跨沿枚举，且未获同版本工具完备性证明；不能在当前冻结合同下直接接受。仅可作为另立的形式等价分析研究，不能作为本轮捷径。

## 明确阻塞与下一步

若A没有找到有原生文档的限额/事件分析入口，B也确认原因仍为跨HF/LF基周期展开，则**现有PT版本在现行SDC下缺少已证实的完整required-time计算途径**。下一步需要Synopsys对T-2022.03的支持说明/补丁或具备文档能力的新版本，在原约束不变下重算；或者由项目明确真实异步接口合同，按CDC/RDC、MTBF、复位脉宽/释放验证制定新的合规验收。这些需要外部事实，不是再加几颗buffer能补足的证据。

Synopsys官方列有[Cross-Clocking Reporting与GCA约束错误分析功能](https://www.synopsys.com/implementation-and-signoff/signoff/primetime/tool-demos.html)，但公开页没有给出扩展1000/101限制的命令；[同版本T-2022.03课程目录](https://training.synopsys.com/learn/course/external/view/elearning/1001/PrimeTimeFoundation)也只证明有检查未测时序、时钟关系、PBA等方法培训，不证明任何具体override。网上第三方转载/论坛搜索命中未作为命令有效性依据。

## 本地原件定位与哈希

同版本原生手册/发现目录：
`/home/mxhanks/.codex/worktrees/s3-y32-ingress-perf/ChipContest/docs/validation/s3-y32-ingress-perf-native-20261113/timing-final/flow-notes/discovery/discover-clock-r7/`

```json
{
  "pte052-manual.rpt": "787103e798dfa0d8967a1fb98c6dc03cb89e29b568708b8189eeeaeb330a3ee5",
  "waveform-discovery.rpt": "315c48dcd595640479978c9d44883abf7832a23aafe60f66f63ca5cab176f65d",
  "expansion-discovery.rpt": "79c8e2b9c780e6c6e5805c2ea2ce70a1a6e454df8fb9bfa2682b1efa87630fac"
}
```

其余一手依据：`.../timing-frozen-2350/async5/reload/edge-arrivals.tsv`、`.../parallel-reset-gpio-handoff/ANALYSIS.md`（旧原件解释与算术见证，非新native结果）、当前main `...native-20261114/catch3/reload/persisted-coverage.rpt`。

## 新回收空设计发现与门禁独立审查（同日追加）

原生新发现目录为 `build/unknown4-20261114/native-discovery/extracted/`：25份catalog文件独立逐SHA/长度核验通过，rc=0、2核、未加载设计，8份man全部status0。以下信息为真实原生T-2022.03-SP5-1输出，不是网页推断。

- `timing_max_normalization_cycles = "4"` 确为旧 `*expand*/*waveform*` 探测漏掉的变量。**仍须其原生man/`get_app_var ... -details`证实用途，不能按normalization/cycles名字把它当PTE-052展开限额。** 当前get_timing_paths/report_timing文档有normalised-slack功能，说明它以已存在的绝对slack除理想允许传播时间来排序；如果该变量手册只描述该归一化指标，它不能生成缺失的required/slack。
- `get_app_var`手册明确支持 `-list` 和 `-details`；后者可给注册类型、默认值、help与合法range，因此补查该变量时可一次记录man+details，不设置变量。
- 两份路径man列出的rise/fall selector是事件极性/clock选择，`-start_end_pair`是每源终点对枚举，PBA是已搜集路径的delay重算。未出现可指定任意launch/capture绝对时间编号、并保证完整周期枚举的参数。
- `report_default_significant_digits`只控制报告显示，合法0..13，部分报告不响应；`write_sdc`实际syntax没有 `-significant_digits`，不得猜用。
- `create_clock`文档支持一period内多个脉冲，同时定义period为完整波形重复周期；这并不证明重编码superperiod后原约束和check身份不变，仍不能直接作为当前合同修复。

### unknown_checks.py / tests/ppa/test_unknown_checks.py

独立运行已有10tests全部通过。候选单边把原unknown改名、删除、只提高MET summary或改为no_clock/disabled，均会被现有测试正确拒绝。但还有三项必要补强：

1. **固定原4身份的baseline绑定**：compare只要求传入baseline恰有4unknown，未核对它们是否为DEFAULT原件的4身份。已用内存fixture复现：将baseline四端点全部追加 `_renamed_baseline`，candidate按同样新名MET，`compare(...)["closed"]`返回true。应将baseline unknown identity五元组与固定原始4项严格等集，并增加双边重命名负例。
2. **真实clean执行状态**：bind_native仅校rc=0/run_requested/三个错误空数组，遗漏schema/status/stage、completion_marker和tool_timed_out。已用临时fixture复现schema=wrong/status=NATIVE_STAGE_FAILED/tool_timed_out=true/completion_marker=false仍返回failures=[]。应要求实际受支持的执行schema及完整clean状态，且baseline/candidate都要检验。
3. **约束身份不能由舍入clock文本替代**：parse_clocks只比显示出来的period/waveform字符串；6.67等报告精度会隐藏细小改动，也未绑定原SDC/PT-add、双库、指定baseline/map身份。应从clean receipt inputs及原生实际SDC输出核对原始SDC c15ede…、PT兼容404c…、双库及正确候选链；clock表只作补充。否则人为修改IO预算但仍有相同clock报告，也可能被称作原约束闭合。

以上发现只修改本审查文件，没有改代码、Git或操作远程。
