# 四工况原约束 STA 审阅

官方原件保留在 `/tmp/xu-b41-close-20261111-r1/xu-closure-20261112-r4`，本文件为界面读取后的审阅记录。物理候选 SHA256：`2d5adc613980dc21dc1f0aaa398045252911a5c67594349630ff35d78688a220`。原兼容约束 SHA256：`404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。

四份 native receipt 均 complete=true、native_exit=0；当前 run.tcl、native.log SHA 与回执一致，回执 SHA 与 result.json 绑定一致。脚本读取同一物理网表与原 SDC。before-slack.tsv 全部非负。报告为理想时钟综合后分析；原约束覆盖警告尚未关闭，不能只据汇总状态宣称最终资格完成。

| 工况 | setup 最小 slack/ns | hold 最小 slack/ns | 违例数 | 全部检查 | 未测试 |
|---|---:|---:|---:|---:|---:|
| SS envelope | 0 | 0.16696212 | 0 | 455,015 | 27,908 |
| FF envelope | 0.46407256 | 0.00027448 | 0 | 455,015 | 27,908 |
| SS reset_bypass | 0 | 0.16696212 | 0 | 455,015 | 27,914 |
| FF reset_bypass | 0.46407256 | 0.00027448 | 0 | 455,015 | 27,914 |

## 逐条解析的未测试分类

已逐条解析四份 before-coverage.rpt，所有原因计数与汇总未测试数完全一致。第一次解析器仅接受 u_soc 层次，漏掉 u_shared，已修正并重新验证总数；原报告未修改。

| 原因与类型 | envelope（SS/FF 相同） | reset_bypass（SS/FF 相同） |
|---|---:|---:|
| no_clock / min_pulse_width | 10,149 | 10,148 |
| constant_disabled / setup | 3,654 | 3,657 |
| constant_disabled / hold | 3,654 | 3,657 |
| constant_disabled / min_period | 10,447 | 10,447 |
| constant_disabled / min_pulse_width | 0 | 1 |
| unknown / setup | 2 | 2 |
| unknown / recovery | 2 | 2 |

no_clock 均为异步控制引脚上的低脉宽检查：envelope 为 RDN(low)=9,706、SDN(low)=443；reset_bypass 为 RDN(low)=9,705、SDN(low)=443。不存在被此分类隐藏的普通数据 setup/hold；异步控制脉宽的环境假设仍须结合原约束与复位来源审阅。

四工况未知端点和类型完全相同，规范化列表摘要前 16 位 `f29ee2e805752fc4`：

- AON wrapper 的 `dwakeup_deglitch/T_8_reg/D`：xu_lfextclk，setup。
- AON wrapper 的 `bootrom_deglitch/T_8_reg/D`：xu_lfextclk，setup。
- AON PMU 的 `erst_reset_r_reg/SDN(rise)`：xu_lfextclk，recovery，条件 `ENABLE_NOT_D===1'b1`。
- AON PMU 的 `erst_reset_r_r_reg/SDN(rise)`：同上。

before-check_timing.rpt 列出 4 个未约束最大延迟端点：上述两个去毛刺 D 和两个 PMU SDN，后者报告表中有重复。另有 1 组不可展开时钟：hfextclk、jtag_tck、lfextclk、plldiv_envelope；周期约为 6.67、100、30517.58、6.67 ns。不可展开警告与未知检查之间的因果关系尚未证明，不作推断闭合。

## 尚待完成

1. 核对源时钟、生成时钟、输入输出延迟、例外及复位环境。
2. 对四个 unknown 检查追踪实际连接并给出可审查的覆盖解释；需要原生诊断时，等待门级与功耗单槽空闲。
3. 结合完整门级和功耗结果完成同版本最终审阅。

## 电气与面积原件审阅完成

四工况共 12 份 max_capacitance、min_capacitance、max_transition 原报告已逐份核对正确的 report_constraint 类型、全违例模式、设计名、正常报告头及无错误；12 份原件的 VIOLATED 条目均为 0。脚本通过 foreach typ 逐一调用各项检查，不能用仅搜索字面固定命令的解析器判断脚本缺项。官方审阅回执 `xu-electrical-audit-20261113-r1.json` 绑定 12 份报告 SHA、同一物理网表和原 SDC SHA。报告末尾的 1 是命令返回值，不是违例计数。

面积另由当前最终网表层次展开和官方 LEF 几何独立复算：1,022 个模块定义、206,980 个叶实例、352 种引用全部有 LEF；337 个 SRAM 为 shared=256、ITCM/DTCM=64、internal=17。LEF 总面积 3,580,429.62550 μm²、新增范围 508,327.10390 μm²；原生库报告为 3,580,429.52912 / 508,327.099038，差异分别小于 0.2 / 0.02 μm²。原生 DC 回执 complete=true、exit=0，当前脚本与日志 SHA 一致。

只排除 320 个复用 SRAM 宏、保守地计入全部 SoC 标准单元，新增面积上界为 652,901.72150 μm²（0.65290172150 mm²），仍低于指南 2.25 mm²。该上界避免遗漏新增时钟缓冲等可能落在复用层次下的单元；它与实际新增计价范围分别记录。面积为单元/宏之和，不含利用率与布线。官方独立回执 `xu-final-area-audit-20261113-r1.json` 保存当前输入 SHA。

已完整读取原 SDC：高频周期 6.666666667 ns、低频 30517.578125 ns、JTAG 100 ns；envelope 建立同源 divide_by=1 的生成时钟，reset_bypass 对旁路及分频寄存器作静态模式约束。时钟 uncertainty/transition/gating check 均为 0.1 ns；普通 I/O max/min 为 0.5/0 ns，JTAG max 为 5 ns，输出负载 0.01 库单位。无新增 false path 或 multicycle 例外，当前 propagate_clocks=0。

## 四个 unknown 的结构定位

冻结源 sirv_DeglitchShiftRegister.v 的 T_8 直接寄存 io_d，其后为 T_9、sync、last；wrapper 将两个 io_d 分别连接反相的 bootrom_n 和 pmu_dwakeup_n 外部 pad，时钟为 LF。因此两个 setup unknown 位于异步输入的首级捕获。

冻结源 sirv_pmu.v 的 erst_reset_r / erst_reset_r_r 是带共同异步置位的两级低频同步器，置位来源最终为反相的外部 erst_n pad。两个 recovery unknown 就落在这两个异步置位引脚。上述源文件属于逐文件 SHA 已匹配的 162 项，未作本轮修改。

原生手册 check_timing.2 经去除终端 overstrike 格式后已核对：unexpandable_clocks 针对存在跨域路径的相关时钟组检查周期是否可展开；异步域未正确区分也会触发此警告。这解释了待核查方向，尚不单凭该说明将四项判为通过。

后续原生诊断保持原 SDC 和四工况原件，读取这四个引脚的实际输入锥与时钟，并按正式任务中固定的 bootrom、dwakeup、erst 引脚工作点做独立补充审阅。该补充不覆盖或改写原始 unknown 记录，不把启动期间的异步复位要求等同于稳态任务时序。
