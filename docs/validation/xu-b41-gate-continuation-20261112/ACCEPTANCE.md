# B41 最终验收清单

本文维护完整接续目标的证据范围。软件 RTL 通过、局部布尔证明、功能副本通过及最终物理资格分别记录；当前仍未完成最终验收。官方原件继续留在服务器，只读界面审阅。

| 要求 | 当前证据 | 状态及剩余检查 |
|---|---|---|
| 三份冻结固件、父源码及 E203 版本 | 原交接目录 `b41-strict-input-r1`、prepared、输入 SHA；父版本 96fffcb…、E203 ccdac30… | 已有冻结证据；本轮未修改输入 |
| 三固件 RTL 完整 12 任务与 warmup | `b41-full12-comparison-r1/result.json` 为 PASS_RAW_CPU64_COMPARISON；各 304,128 测量输出、25,344 warmup 输出、13 次真实清零 | 已完成，范围为开发 RTL；不代替最终门级 |
| 三份背压与六项读写故障 | `b41-followup-review-r1/result.json` 为 PASS_RAW_B41_FOLLOWUP；每次首源等待 31 拍，故障请求/响应排空、return_code=5 | 已完成，范围为开发 RTL |
| 单槽与既有后台控制器 | 旧门级和功耗均已自然结束；原功耗超时回执保留。R16 PID 156004、simv 156023 已确认持有 `eda.lock` | R14 锁范围错误曾造成短暂并发，事件原件保留。R16 连续完成两份剩余门级，功耗 PID 160819 仅等待整轮门级自然完成，尚未启动 EDA |
| 物理候选身份 | `xu-closure-20261112-r4/dc/mapped.v` SHA 2d5adc61…；DDC、SVF、DC SDC 和实际 STA SDC 分别建立索引 | 已核对，见 FINAL-ARTIFACTS.md；最终交付封存待所有必要结果齐全 |
| 原约束四工况 STA 与电气 | 四份原生回执与当前脚本/日志 SHA、原 SDC SHA 一致；所有 slack 非负，455,015 检查/工况；12 份电气原件已核对，三类违例均为 0 | 覆盖原因已逐条分类，4 个低频 unknown 和时钟展开警告仍待解释。时钟、输入输出延迟、负载及全部 DRC 已读原件，详见 STA-AUDIT.md |
| RTL 至最终候选 Formality | RTL→基线及基线→最终各 58,332 passing，无失败/中止/未验证；恢复链、脚本、日志与回执一致 | 逻辑证明已通过，18 个参考未匹配状态位、PLIC 空壳与 SRAM 技术库抽象边界已明确，源码差异已逐项核对，见 FORMAL-AUDIT.md |
| 物理网表与功能仿真副本对应关系 | 17 位复位 BDD、`xu-fm-functional-20261112-r1` 原生回执与报告 | 已完成整体对应证明：58,337 个 passing，未匹配/失败/中止/未验证均为 0；两端 SHA、脚本和日志回执绑定已核对 |
| 六处 CPU SVA、原 52 条主 TB fatal、错误处理 | 6 个冻结源位置对应 430 个展开断言；golden 与实际 muldiv 写回比较仍在。51 条原失败消息直接映射，1 条为 PPA 不含的独立夹具端口检查 | 430 个断言在真实复位到达后开启。52 项适用范围已逐条索引，端口差异有固定地址合法性证明，物理读回及 DUT 错误 fatal 保留，详见 CHECKER-MODEL-AUDIT.md；完整三固件执行终态仍待 |
| 厂商 SRAM 模型、337 个宏、装载及读回 | 厂商预检全 1,024 地址及 4 个四态未知字 PASS；模型/测试台/工具/日志 SHA 一致；最终层次展开 shared=256、ITCM/DTCM=64、internal=17 | 模型与实例数量核验已完成；三固件完整装载/真实事务/读回及窗口影响随 full12 最终核验 |
| 同一门级可执行件三固件 full12 | 同一 simv-row-r1、95 个输入 SHA；原冻结 2,000 万周期上限。tight 原 R2、phased 新 R3 独立复算均通过 | 各含 304,128 正式输出、1 warmup、13 clear、169 组宏读检查；phased 的实际门级计时与 RTL 差异见 REVIEW-CONTRACT-CORRECTION.md。08:58 backoff 为 2/12 正式任务、1 warmup，无 fatal，仍待完整终态 |
| 全 SoC 活动与同窗功耗 | 旧导入 2,400 秒超时，不作为有效功耗。评分所需 12 段 payload 流程已排队，原生执行锁范围经 AST 检查 | 门级完成后串行测三固件，保留原网表、SS 库、SDC 和完整 SoC。待覆盖、337 宏、单位及能量审阅；额外 clear+payload 功耗已从收尾依赖移除，详见 POWER-AUDIT.md |
| 逐任务能量与固件选型 | 软件操作计数仅作为背景 | 待实际 P×t 复算；不填旧硬件功耗或理想频率换算 |
| 数值格式、软件模型、转换脚本 | 原交接 PRELIM-DELIVERY 与 prelim-materials-r1，B41 精确整数范围和 RNE 合同 | 已有源材料；最终报告与版本绑定待完成 |
| 可审查初赛交付 | 原交接材料和当前诊断记录 | 待冻结最终固件与网表、完整 SHA、复现命令及作品设计报告；指南未列为本次初赛必交的 PPT/视频不阻塞本版收尾 |

服务器根目录：`/tmp/xu-b41-close-20261111-r1`。原交接资料位于本机 `docs/validation/xu-b41-handoff-20261112/`；当前观察位于同级 `xu-b41-gate-continuation-20261112/OBSERVATIONS.md`。本轮不写 GitHub 远端。
