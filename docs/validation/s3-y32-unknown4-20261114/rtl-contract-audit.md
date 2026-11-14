# 4 unknown：实际 RTL、映射和异步合同只读审计

范围：当前 main b275f05（候选来源 be67e5d，生产 child 5470c5650f2d11d16e7c52cc96626d21030a3973），最终映射 SHA d83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1。只读 RTL／返回映射／SDC／clock association；未改生产文件、冻结数据或 Git，未跑 EDA。已读 GLOSSARY 和 diagnosing-bugs skill。根代理已提供确定性红灯 UNKNOWN_CLOSURE FAIL4，本审计不把“看起来是同步器”当作闭合结果。

## 结论

没有找到能在保留原 SDC、外部输入语义及 LF 功能时序的前提下，通过普通 RTL 补寄存器／改时钟消除这 4 项 unknown 的真实代码错误。两个去毛刺 T_8 是已有 LF 多级同步链的首级；PMU 是 ERST 异步断言、LF 两拍释放／事件延长链，**两级**都直接受 ERST 异步置位，不能把两个 SDN 都描述成数据同步器首级。

三种外部输入在 SDC 都被建模为 HF launch，四个接收 CK 实际都是 LF。原生报告的 required 不可计算与 HF/LF 周期展开不足一致；数值／电气 ECO 和传播上界都不能生成缺失的 required。即使更强工具成功展开，也可能得到真正的负 slack，不能预设 unknown 应变成 met。

## 三个可证伪的根因假设（排序）

1. **时钟关系／工具展开限制**：如果根因是 HF launch 与 LF capture 的周期组合，换缓冲或更换相同逻辑单元不会消除 unknown；保持同网表、同原 SDC，原生工具用能够完整覆盖该关系的真实分析设置／版本时才能产生有限 required，或明确报告仍不可处理。已有长期 buffer ECO 后身份仍为原 4 项，符合预测。
2. **RTL 错接时钟或绕过同步链**：若存在错接，至少一个接收 CK 会与其链后级不一致或外部信号绕过首级直达消费逻辑。实际 RTL 和最终 mapped CK 关联均为 xu_lfextclk，去毛刺输出只来自 sync&last；此假设在四个被查点上不成立。
3. **复位／脉宽协议缺失导致实际硬件风险**：若未规定 ERST 最短低脉宽、去抖输入稳定窗和 LF 停钟行为，则 RTL 仿真即使通过也无法证明硬件无亚稳态／漏脉冲。PMU有无时钟捕获结构、去毛刺故意拒短脉冲，但最短物理脉宽及释放时序仍缺工艺合同。该假设可解释签核缺口，**不能把工具 unknown 直接证明为 RTL 功能错误**。

## 真实信号、源码行及映射

所有源码相对于仓库根 `third-party/e203_hbirdv2/rtl/e203/perips/`。映射行号指公开 `docs/validation/s3-y32-ingress-perf-native-20261114/catch3/catch3-evidence.tar.xz` 内 `apply/mapped.v`，可用统一入口解包后复核。

| 接收点 | RTL 路径与功能 | 当前最终映射 |
|---|---|---|
| bootrom_deglitch/T_8_reg/D | `sirv_aon_wrapper.v:259-264,361-363`：clock=aon_io_lfclk，io_d=~io_pads_bootrom_n_i_ival。`sirv_DeglitchShiftRegister.v:25,36-40`：T_8<=io_d。 | `sirv_DeglitchShiftRegister_1`；mapped:268338 DQV0_12TR40，CK=clock，D=已插两身份 BUF 输出。wrapper:268517-518，输入反相 U5 在268525。 |
| dwakeup_deglitch/T_8_reg/D | wrapper:267-272,354-357：clock=aon_io_lfclk，io_d=~io_pads_pmu_dwakeup_n_i_ival。同一去毛刺模块首级。 | `sirv_DeglitchShiftRegister_0`；mapped:268356 DQV0_12TR40，CK=clock，D=已插两身份 BUF 输出。wrapper:268519-520，输入反相 U6 在268526。 |
| pmu/erst_reset_r_reg/SDN | `sirv_pmu.v:309-310,328-339`：posedge erst_reset 立即置1，LF沿在无ERST时清0；first capture stage。 | mapped:262622-623，DSNQV0_12TR40，D=0，CK=clock，SDN=XU_ECO_async_edge_0011_NET。 |
| pmu/erst_reset_r_r_reg/SDN | 同一 always：ERST同样立即将第二级置1；无ERST时LF沿采erst_reset_r，第二级两拍后清0。 | mapped:262615-616，DSNQNV0_12TR40，D=erst_reset_r，CK=clock，SDN=XU_ECO_async_edge_0010_NET。其QN只是等价映射极性。 |

ERST源：wrapper:344 `erst=~io_pads_erst_n_i_ival`；:331 `aon_io_resetCauses_erst=erst`；`sirv_aon.v:3678` 直通 `pmu_io_resetCauses_erst`；`sirv_pmu.v:511-516` 经 T_381[1]/T_383 直通到 erst_reset。mapped wrapper:268524 为 pad 反相；PMU:262627 再反相到低有效 n10，之后身份 BUF 链到两个 SDN（:262646-659）。因此外部 ERST pad 释放是 recovery 检查的真实起点，不可改用内部 LF watchdog 作为替身。

实际 LF 源：wrapper:345 将 pad LF 接到 aon_io_lfextclk；`sirv_aon.v:3602` io_lfclk=io_lfextclk；wrapper:320 aon_clock=aon_io_lfclk；`sirv_aon.v:3631` pmu_clock=clock。mapped wrapper:268507-520 的 crossing_clock 同时驱动去毛刺与 AON。

原生 `catch3/reload/original-clock-association.tsv`：bootrom T8/CK 第1523行、T9第1526行；dwakeup T8第1530行、T9第1533行；PMU second CK第2990行、first CK第2991行，全部 xu_lfextclk。

DC导出 `catch3/apply/mapped.sdc:508-509,516-519` 对三个外部 pad 一律 `set_input_delay -clock xu_hfextclk -max 0.5/-min 0`；LF独立clock。**该导出SDC在188/198行会显示有限精度的6.66667/30517.6，不能据它重新创建时钟替代原生完整精度 SDC**。封存原native原约束HF 6.666666667ns、LF 30517.578125ns、uncertainty0.1ns；最终回执证明原约束身份保持。

## 去毛刺的同步与脉宽语义

`sirv_DeglitchShiftRegister.v:36-40` 是 `T8 -> T9 -> sync -> last` 四级 LF 移位；:34-35 `io_q=sync & last`。T8→T9及后续都是LF域，第一段才是异步采样边界。RTL没有ASYNC_REG属性或专门MTBF器件保证；多级拓扑存在不等同于已经完成物理CDC签核。

输入端 reset 在 wrapper 被绑为1，模块注释明确“sync reg do not need reset ... do not use it”，always没有reset条件。因此不能把它视作“reset误绑常1导致永久复位”的代码bug，更不能直接补 `if(reset)`。

忽略模拟亚稳态，稳定输入采样序列 d[n] 给出 q[n]=d[n-2]&d[n-3]：高电平需要连续两个被采到的高样本，并在第四个相关LF沿得到稳定高输出；低传播在第三个相关LF沿使AND变低。该输出不是通用短脉冲捕获器。bootrom最终影响 wrapper:384-386 pc_rtvec（0x1000或0x20000000）；dwakeup经wrapper:322、AON:3634进入PMU唤醒。增加级数会改变启动选择／唤醒延迟，切换到HF会改变滤波时间数量级，均不是零功能影响的修补。

可能另有启动合同需验证：同步寄存器无初始化，稳定 strap 需要足够LF沿才确定；AON ResetCatchAndSync本身3级释放。不能仅由代码推断所有启动时序有bug，但必须以启动／复位相位测试确认 pc_rtvec 被消费时已稳定，尤其active bootrom strap。此项尚无失败重现，不作为已证实根因。

## PMU 捕获、释放与重叠原因

`sirv_pmu.v:313-339` 写明两DFF用于无时钟时捕获reset，直到clock到来才清除。ERST有效立即使两个状态为1；ERST撤销后第1个LF沿first=0、second仍1，第2个LF沿second=0。ERST保持时两个都维持1。无LF时不能改成纯同步reset，否则短ERST会完全丢失；去掉第二级async set会改变无时钟时第二级立即置位的语义。

第二级输出在:358-379用于POR>ERST>WDOG优先级、rstcause set/clear；rstcause寄存器:382-398故意无直接reset。PMU内部core_reset另来自T356（:444-445），与这两个原因捕获状态不是同一信号。将ERST先通过现有AON reset释放链再送PMU会把看见的ERST与POR/WDOG合并，可能破坏原因归属。

现有AON reset路径 wrapper:346-348 将ERST|WDOG|POR送 `sirv_ResetCatchAndSync`；该模块:34-49为3级异步清0、LF移入1，反相作为异步断言／同步撤销的AON reset。这个机制保护下游域释放；它不消除PMU自身两个ERST SDN的外部异步撤销检查。

## 三种候选修法、影响及适用边界

| 方案 | 行动 | 功能影响／原约束结果 | 必需验收 |
|---|---|---|---|
| A：同网表、原SDC，补完整原生关系分析（优先诊断） | 查明当前PT对这4项无法构造required的确切原因，使用原生有文档且可验证的展开／分析控制或支持该关系的工具；也可先建立精确相位／边沿枚举作独立反证，再对照原生返回。不能把手算上界塞作STA slack。 | RTL／频率／约束零改动；可能把unknown转为真实负slack，不能承诺转为met。仍无法展开则保持4unknown。原约束将异步pad描述为HF同步launch，未必符合实际外部协议。 | 新完整STA+coverage/untested身份差分，4项均须真实finite required/slack且与指定launch/capture边沿一致；保留PTE-052和失败记录；已知0数值/0DRC不得倒退；若生成负slack走真实修复。 |
| B：补真实CDC/RDC合同并按异步边界签核（功能保持方向） | 保留原采样时钟和链级数，为T8/T9/sync链、ERST双异步置位链补确切外部稳定/脉宽/释放协议、工艺同步器属性与布局/MTBF约束；对已证明的异步边界提供精确到pin、类型、条件的工程签核裁定。 | 一般不改变逻辑功能；ASYNC_REG/dont_touch本身不会改变这4项required。原STA约束原件继续留存并继续报告4unknown；若采用任何新的STA异步例外，必须作为另一份有合同依据的新约束与签核口径，不得宣称“原SDC下unknown=0”。 | CDC/RDC结构/重汇聚/扇出检查、物理两级间延迟/MTBF、外部pad稳定窗、ERST最短脉宽与无LF捕获、所有原因优先级及释放相位测试；合同必须可由板级/测试环境保证。无证据false_path不属此方案。 |
| C：确需新外部协议时修改接口/捕获架构（有功能影响） | 若外部pad实际上必须按HF同步更新而不是异步，则建立明确握手／稳定窗，使跨域信息在LF可验证窗口被消费；对ERST用专门事件保持+同步释放接口并保证无LF捕获，避免直接用“采样两次”替代reset事件。用正式CDC/reset宏也必须保留其异步功能和工艺模型。 | 改变接收协议、最短脉宽、启动/唤醒/复位延迟，可能改变原因优先级；不能沿用1064最终网表证明。只要仍有HF→LF第一次异步采样，在原SDC仍可能保留unknown；普通新增FF并不消除这一事实。 | 先有能重现具体协议失败的相位/短脉冲仿真或形式性质，再改RTL；接口/固件/板级合同匹配；RTL→mapped正式等价或清楚列功能差异、fresh综合/STA/面积、CPU12吞吐及GPIO实际路径重测。未找到真实失败前不建议修改。 |

对于“外部输入可任意相位变化且仍须LF采样”的需求，不存在通过有限固定延迟让首级永远满足setup/recovery的确定性证明。已有同步链正是对该物理事实的架构处理；不能以该事实为由随意删除检查，也不能把未知required当0或拿LF内部路径替代HF外部上下文。

## 最小下一步

先实施A的只读原生诊断，同时准备B所需明确合同和边界测试；不动生产RTL。对每次结果运行根代理红灯门禁，要求未知4项逐身份归零或被明确报告为仍未闭合，不可只看report_timing返回成功。只有证明是代码／接口缺陷才进入C。
