# FPT工程技能资料的导入与采用

日期：2026-10-18。本次只交付资料完整性与当前工程的方法映射，不增加设计PASS。来源是 `FPT_ENGINEERING_SKILLS_20261018_r1.zip` 及同名源目录的 `WORKFLOWS_CN.md`；ZIP SHA-256为 `7db33237b6262790712699f6f05052e950f9ba93693fd574e689470743d429fd`。实际命令、退出、逐文件身份和校验计数见 [导入记录](../runs/fpt-engineering-skills-import-20261018.json)。

原包去掉唯一最外层目录后，按字节导入 [vendor/engineering-skills-20261018-r1](../../vendor/engineering-skills-20261018-r1/README_CN.md)。38个文件包括 `SHA256SUMS`，其37条摘要覆盖其他全部文件。导入前检查ZIP路径、重复条目、文件类型、CRC、内置摘要和同名源目录完整字节一致性；已有目标若不同则整批拒绝，未覆盖既有文件。源目录的 `WORKFLOWS_CN.md` 与ZIP/导入副本逐字节一致。

未执行包内安装或辅助脚本，未写项目 `.agents` 或用户/全局技能目录。`tools/transfer_skills.py` 只作静态阅读；其安装建议不构成当前操作。导入包的SKILL、模板、原HEAD、历史验证和提示词都是来源资料，不能覆盖本项目AGENTS、当前用户授权或验收要求。源包的VALIDATION是原作者当时的测试声明；本次不把它记作新工程测试或独立行为评估PASS。

## 五项技能的适用边界

已阅读全部五个 `SKILL.md` 和它们的11篇references。

| 来源技能 | 当前采用范围 | 当前工程落点 |
|---|---|---|
| [engineering-continuity](../../vendor/engineering-skills-20261018-r1/skills/engineering-continuity/SKILL.md) | 复核实际入口/字节；短状态、决策与原始证据分开；按受影响范围重验 | [PROGRESS](../../PROGRESS.md)、[DECISION](../../DECISION.md)、[harness](../../scripts/harness.py) 已存在，继续使用resume/checkpoint，不引入第二套状态框架 |
| [diagnose-expensive-runs](../../vendor/engineering-skills-20261018-r1/skills/diagnose-expensive-runs/SKILL.md) | 原生阶段、runner/reader与验收状态分开；运行前绑定输入；精确进程归属；最小可证伪实验 | [sram_evidence.py](../../scripts/verify/sram_evidence.py) 的source_identity/process_identity/inspect_command/run_command/completion_error、既有唯一artifacts目录和EDA锁 |
| [fpga-change-evidence](../../vendor/engineering-skills-20261018-r1/skills/fpga-change-evidence/SKILL.md) | 借用source→command→log→artifact身份链及逐范围状态；同源条件下比较绝对值/差值 | [SRAM_AUDIT](../SRAM_AUDIT.md)、[参考时序分析](../optimization/SRAM_TIMING_ANALYSIS.md)、[PPA检查器](../../scripts/synth/check_ppa_budget.py)；ASIC记录采用本项目SDC/标准单元/SRAM/PVT口径 |
| [causal-bypass-rtl-review](../../vendor/engineering-skills-20261018-r1/skills/causal-bypass-rtl-review/SKILL.md) | 仅在真实bypass/skip/early-exit/工作抑制路径触发，核资格谓词、所有权、守恒、首尾与恢复 | 当前[奇尾行抑制](../../src/rtl/kwt_linear_engine_rowpair_sram.sv:109)确实抑制不存在第二行的读和MAC，可借边界检查表；普通线性乘法、SRAM后端替换、网表回放不因旧FPT有causal而自动套用causal算法 |
| [amd-fpga-flow](../../vendor/engineering-skills-20261018-r1/skills/amd-fpga-flow/SKILL.md) | 只保留“读实际入口、阶段依赖和产物身份”的通用经验；当前ASIC实施不调用该工具流程 | 不把Vivado/Vitis/XDC、AMD IP、BIT/XSA、route或上板加入本比赛验收；如将来另立FPGA任务，再按其明确目标使用 |

`fpga-change-evidence`的E0–E6是FPGA来源层级，不直接改名为本项目完成度。当前仍分别报告reference / new-KWT / SoC / PPA，采用PASS/FAIL/BLOCKED/NOT_RUN；两次有界等价未完整证明仍是NOT_PROVEN。公开参考库局部setup改善不等于指定工艺150MHz、宏面积或完整窗口功耗通过。包内 `capture_fpga_evidence.py` 只读审阅：它记录missing/文本marker后仍可exit0，因此只适合库存，不能替代本项目completion_error或成为验收门禁。

## 对当前主任务的具体新增行动

以下是采用方法后的执行要求与后续动作；资料导入本身没有完成这些设计验证。主代理继续当前开发，完成时按新源码和原生运行更新状态。

1. **网表功能回放先证明测试敏感性。** 复用 [run_sram_mapped.py](../../scripts/verify/run_sram_mapped.py)、[mapped pair TB](../../sim/tb_kwt_icb_mapped_pair.sv) 和 [pair checker](../../sim/kwt_icb_pair_checker.sv)。用真实工具小例核标准单元模型/共同SRAM语义与稳定采样，再证明checker拒绝共同X和响应差异；正常任务与abort/reset的epoch计数分开，末HI和ACK必须在实际posedge接受后才算完成。通过只标记所测网表/场景，不扩写为全量形式等价。
2. **结束同一证明的盲目重试。** 两次120秒NOT_PROVEN保留原目录；下一次实验明确保持条件、唯一变更、预计发现和停止条件。先采用有效信号感知miter或同源门级回放，不能仅增大超时预算。没有启动前冻结的旧结果不能由事后哈希补成已冻结。
3. **针对两类真实min违例分别实验。** 依据参考时序报告，对data hold约-0.013133ns和内部soft-reset removal约-0.255385ns分别提出最小候选，记录setup/hold/removal与面积的同范围绝对值和变化。映射阶段可复用已绑定网表；仅reader错误时新建只读分析记录，不改原日志/失败终态。若软abort改同步clear，另立候选并重验协议、复位、重装与SoC恢复。
4. **继续使用现有执行合同。** 运行前绑定实际源、配置、向量、库/工具和生成物；唯一输出目录；HDL编译最多2线程、重型EDA一次一项。原生exit0之外还要完整marker、计数、无阻断诊断及SHA一致。按已确认host/boot/start/PID namespace检查归属，不从不可见PID或静默日志推出停止，不重复启动或按工具名终止任务。
5. **官方资料到位后只重验受影响依赖链。** 继续用 [sram_sources.py](../../scripts/verify/sram_sources.py) 的明确源集，官方包缺失时fail-closed。Adapter/引脚/Q保持/延迟、指定PVT和宏模型改变后重跑对应功能及PPA，不继承开发Fork或旧FPT PASS。完整性能窗口仍包含装载、CPU调度、等待和全部写回；TB backdoor预装载的开发窗口不能冒充正式完整窗口。

以上动作与现有 [10月18日剩余计划](../superpowers/plans/2026-10-18-sram-remaining-plan.md) 衔接。根目录无有效Git，沿用实际字节SHA checkpoint；不因模板要求新建Git、重写harness或增加无关测试。里程碑、结束和上下文切换由主代理统一执行现有checkpoint并更新负责人日志/PROGRESS/DECISION。

## 本次验证及限制

本次接受范围是**资料来源、无覆盖导入、静态阅读和链接完整性**。可复核脚本与原生日志保存在导入记录指向的artifacts目录；没有运行EDA、安装、SSH或硬件操作。资料包不携带旧平台授权、活动进程所有权、旧数值/SoC/PPA结论，也不包含原FPT工程完整证据镜像。官方E203/SDK及指定SRAM/工艺资料缺口仍由当前工程记录，导入不能解除阻塞。
