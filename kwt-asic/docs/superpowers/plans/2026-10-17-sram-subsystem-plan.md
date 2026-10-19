# KWT-1 + E203 SRAM 子系统增量实施计划

> 2026-10-18：本文件保留10月17日审计时的计划和勾选状态；部分步骤现已完成。当前入口为 [10月18日剩余计划](2026-10-18-sram-remaining-plan.md)，不要据本文件旧状态重复修复或重跑。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 用户本轮要求先交付计划；以下未勾选项尚未执行。恢复实施时由主代理顺序整合，独立代理只做不冲突的审查；重型EDA一次一项。

**Goal:** 在保留功能和数值契约的前提下完成可替换SRAM子系统、真实分层回归和诚实的早期PPA，为官方宏接入保留清晰边界。

**Architecture:** 保留rowpair和旧ICB基线，完善现有 `kwt_linear_engine_rowpair_sram → kwt_sram_bank → kwt_sram_1rw` 候选。四后端显式切换，共享SRAM与内部存储分开；优先修接口结构/验证口径，再优化有证据的控制时序。

**Tech Stack:** SystemVerilog、Python标准库、Icarus、Verilator（编译最多2线程）、Yosys0.33/ABC、Nangate45 typical参考库、项目本地OpenSTA2.0.17、固定RISC-V裸机工具链。参考工具/库不是官方工艺。

**Spec:** [2026-10-17-sram-subsystem-design.md](../specs/2026-10-17-sram-subsystem-design.md)；用户完整请求是需求来源，正式赛题以根目录PDF及 `docs/requirements/UNDERGRAD_REQUIREMENTS.md` 为准。

## Global Constraints

- 计算：`Y[99,256]=X[99,64]×W[64,256]+B[256]`；12层逐任务重新装载，不跨性能任务复用旧参数。
- 保持X/W signed16、bias signed40、内部41位精确累加、外部signed48；不改Golden、舍入或模型。
- 目标150MHz；`A_core_logic + A_new_interface + ΣA_internal_SRAM < 2.25 mm²`。复用平台面积另列；系统窗口功耗不得遗漏E203/共享SRAM。
- 官方模型、PVT/标准单元、宏Liberty/面积/功耗尚缺，正式PPA为BLOCKED；未知量用null，不能按零。
- 原RTL、vendor、队友原仓库、历史日志不覆盖；新增候选可独立回退。根目录无有效Git，不执行init/commit/push；每阶段用SHA checkpoint保存，后续有效Git环境再按授权提交。
- 本轮计划不启动新实现/实验，不重跑无关全量模型评估；恢复实施后仅运行与本步源码变化对应的检查。
- 官方宏若延迟/端口不满足当前一拍契约，回到设计决策，不以假valid或假时序例外掩盖。

## Review Focus

1. START和COMMIT解码互斥时仍有结构反馈：P2必须消除环并证明拒绝命令无握手副作用。
2. 逻辑深度小于物理容量时padding地址/高位切片/连续跨片读取：P3/P5必须验证返回片选、全位0/1、首尾及hole拒绝。
3. 在途复位、输出HI响应背压与最终ACK时序：P7按posedge真实握手验收，不能仅观察valid/ready电平。
4. 中断/缺结果/脚本SHA变化：P1/P6/P7的运行器要保存可恢复状态并拒绝虚假PASS，不重复启动疑似存活的重任务。
5. 黑盒切边导致虚假Slack或漏算接口：P4/P8必须报告宏清单/切边覆盖/含接口逻辑面积；工具exit0不等于Timing PASS。

---

## 阶段总览

| 阶段 | 当前事实 | 待验收产物 |
|---|---|---|
| P0 工程审计 | 已有静态审计，本轮新增源码/证据复核 | 精确当前状态、问题和边界 |
| P1 基线冻结 | 原源码/checkpoint保留；部分长任务无最终状态 | 统一source/run manifest和恢复规则 |
| P2 Wrapper与接口边界 | wrapper候选已存在；含ICB结构FAIL | 无组合环、协议兼容的候选 |
| P3 Behavioral | 51单元案例/7匹配有证据 | 保留当前PASS，补bank非法逻辑地址/使能覆盖 |
| P4 Black Box | core-only历史映射通过；含接口失败 | 当前脚本、含接口全逻辑结构/映射 |
| P5 FF兼容性 | 双后端功能通过；全FF结构展开通过 | 原版/行为/FF对照和明确FF指标范围 |
| P6 Linear回归 | 12个新核心运行PASS，整体汇总未最终完成 | 可独立验收的核心回归总报告 |
| P7 E203 SoC | 新12任务无最终报告；旧基线只有开发单任务证据 | 协议负例、复位恢复、12层CPU任务和准确开发窗口 |
| P8 PPA初评 | 逻辑面积有局部参考值，setup/hold均有违例 | 同源含接口映射、控制扇出诊断、可覆盖STA和限制 |
| P9 官方接入准备 | 手册/配置占位已存在，实际宏BLOCKED | 完整所需文件清单和替换检查表 |
| P10 最终审计 | 尚未达到全部可实现门槛 | README/PROGRESS/DECISION/独立审查/证据归档 |

## 文件职责与修改范围

| 文件 | 现状/下一步职责 |
|---|---|
| `src/rtl/kwt_linear_engine_rowpair.sv`、`soc/kwt_icb_slave.sv` | 原基线，保留字节 |
| `src/rtl/kwt_linear_engine_rowpair_sram.sv` | 已有候选；先不改MAC/FSM，仅必要时局部控制优化 |
| `src/rtl/memory/kwt_sram_1rw.sv`、`kwt_sram_1rw_blackbox.sv` | 已有原语后端及错误检测；非官方pin定义 |
| `src/rtl/memory/kwt_sram_bank.sv` | 已有深度/宽度组合，保持返回选择时序 |
| `soc/kwt_icb_slave_sram.sv` | P2最小切断合法性检查反馈，不改寄存器地址/协议 |
| `sim/tb_kwt_icb_slave_sram.sv`、`scripts/verify/run_sram_icb.py` | 计划新增，复用原ICB TB并绑定真实新核心 |
| `sim/tb_e203_kwt_sram.sv` | 计划新增，保留原TB；修正起止事件并加入恢复场景 |
| `sim/kwt_shared512_checked_model.sv` | 已有保守aligned32模型，不改E203核 |
| `scripts/verify/run_sram_{engine,regression,soc}.py` | 已有；补独立核心汇总、持久状态、产物SHA及准确范围 |
| `scripts/synth/run_memory_{blackbox,partial_sta,ff_reference}.py` | 已有；冻结后重新执行，含接口/覆盖/hold必报 |
| `configs/sram-backends.json`、`tech/official_sram/` | 目前说明/占位；补唯一可验证source identity与官方配置校验 |
| `tests/test_sram_evidence.py` | 计划新增：防缺报告/错误marker/变化源/未建模宏虚假通过 |
| `docs/SRAM_AUDIT.md`、`reports/PPA_PRELIMINARY.md`、`docs/OFFICIAL_SRAM_INTEGRATION.md` | 补本轮现况，保留历史失败，区分计划与事实 |
| `Makefile`、`README.md`、`PROGRESS.md`、`DECISION.md`、`harness/tasks.json` | 当前入口已存在；按真实新证据维护，最多五项下一步 |

## P0 / P1：收口审计、冻结来源与运行边界

**Interfaces:** 读取原checkpoint及所有现有结果；产出 `docs/runs/sram-plan-audit-20261017.json`、本计划和一次checkpoint。后续运行用同一配置产生 `source_identity.json`，包含top、backend、PIPE_MUL、RESULT_BUFFERS、显式源集、工具/数据/配置SHA。

- [x] 核对根目录Git状态、两份队友仓库状态和原checkpoint；不覆盖已有修改。
- [x] 核对20逻辑bank/415744bit、72容量原语/462848bit及系统共享/TCM边界。
- [x] 逐项区分原始测试日志与缺失的SoC/整体结果；复核已完成运行的源、向量、日志和结束标记。
- [ ] 在恢复实施时先检查旧run真实进程/退出记录；旧handle失效且无终态报告则记未验收，不能假设仍活跃或重复启动。
- [ ] 为run_sram_soc/regression补 `run_state.json`（含PID、进程启动身份、阶段、命令、时间）及原生退出记录；中断写未完成状态，stdout逐阶段flush。状态文件不是进程存活证明。
- [ ] 测试 `tests.test_sram_evidence` 的缺report、退出非零、有marker但截断、重复marker、输入SHA变更场景；均不得返回PASS。
- [ ] Checkpoint：`python3 scripts/harness.py checkpoint --label sram-p1-identity`，确认原基线SHA未变。

## P2：先修复ICB组合环，再进行性能实验

**Files:** 修改 `soc/kwt_icb_slave_sram.sv`；新增候选ICB TB/runner，原adapter/TB保留。

**Interfaces:** 仍使用现有32位ICB单outstanding和 `0x10042000/4KiB` 寄存器协议；保留LO/HI原子输出、WRITEBACK_ACK和load/start语义。

- [ ] 在当前未修代码上复现：`python3 scripts/synth/run_memory_blackbox.py --include-interface --timeout 120`；预期 `check -assert` 因组合环FAIL，保存新原生日志。
- [ ] 复用原ICB TB建立 `tb_kwt_icb_slave_sram`，以真实候选核心检查合法staging、COMMIT、START与非法命令无load/start握手；不mock MAC。
- [ ] 在候选adapter中令装载检查使用独立reset/idle/error条件（建议 `engine_rst_n && !engine_busy && !engine_error`），只替换staging/COMMIT分支对engine_load_ready的反馈依赖。通过offset互斥证明这些分支下start_valid为0；保留真正load_ready握手及START优先约定。
- [ ] 新增 `make test-icb`，runner要求原生exit0、唯一 `ICB_ADAPTER_PASS`、1完整/1abort任务、实际输出计数和hold检查；分别运行行为与FF后端。
- [ ] 再运行含接口结构检查：无logic loop、多驱动、未解析模块；20bank/72boxes/16MAC全部保留。若失败先定位，不继续重型映射。
- [ ] 保存红/绿证据、来源身份与checkpoint；这一步只改变候选adapter，核心旧证据仍须按实际源码影响判断。

## P3 / P5：完成存储契约和FF对照边界

**Interfaces:** 同一 `kwt_sram_bank/1rw` 的一拍同步接口；0行为/2FF使用相同外部请求，黑盒不参与功能仿真。

- [x] 当前51案例/7组匹配已有可追溯证据，保留HEX完整/缺失/短/X、未写读、原语非法读写/冲突、Q保持和reset保留。
- [x] bank测试覆盖所有地址前/后向读取和所有数据位0/1；覆盖1023/1024、2047/2048、3071/3072及41位高切片。
- [ ] 在bank TB增加逻辑hole（如3136深度的地址3136）、bank级同拍跨深度片读写、未知使能负例；期望非零退出和指定diagnostic。原语检测不能替代被bank译码吞掉的非法请求检查。
- [ ] 若上述测试暴露译码吞请求，再最小修改bank检查，重跑 `make test-memory` 和受影响核心配置；没有失败则不改实现。
- [x] 全FF结构展开已有结果：429231 register bits、memory cell=0、exit0；保留该参考，不重跑相同实验获取相同信息。
- [ ] 全FF门级面积/STA仍NOT_RUN；仅在比较确有需要且资源预算允许时显式 `ALLOW_FULL_FF=1` 并有界运行，不外推单个128×16面积，也不把FF数字当真实宏PPA。

## P4：含接口Black Box预综合与映射

**Interfaces:** top=`kwt_icb_slave_sram`，backend=1；输出完整新增标准逻辑网表、72个未建模宏清单和面积范围。

- [ ] P2通过后，冻结当前脚本并运行 `make synth-logic`。不得用旧脚本SHA的core-only结果替代本步。
- [ ] 检查20逻辑bank、50×128×16+22×1024×16、16个signed16×16资源、无剩余memory/意外大FF阵列、无未解析逻辑；核对输入/输出端口没有悬空。
- [ ] 映射报告分别列核心、新增ICB、bank译码/输出mux；总标准逻辑必须覆盖这些新增部分，内部宏面积为null。
- [ ] 确认BEHAVIORAL在综合下拒绝、BLACKBOX功能仿真拒绝、OFFICIAL缺Adapter拒绝，源集不会重复定义。
- [ ] 保存当前脚本、RTL、库、网表、统计和原生log SHA；后续STA只读取这份被接受的映射报告。

## P6：核心回归独立收尾

**Files:** 已有核心runner/bench不因整体SoC缺结果重写；regression补每个子阶段持久汇总。

- [x] 8组 `PIPE_MUL=0/1 × RESULT_BUFFERS=1/2 × backend=行为/FF`，每组6任务已完成；12层双后端和四态极值也已完成。
- [x] 原rowpair与两后端同向量对照、5份比较报告已复核；新候选共76任务/1926144输出，不包含原版对照的额外12任务。
- [ ] 将核心矩阵汇总独立写入可验收报告，不依赖后续SoC成功才落盘；汇总重新核对完整log/源/向量SHA，不只信status字符串。
- [ ] 恢复执行后，只有源码/bench/runner实际改变的部分重跑；默认随源码静音12层与已选真实语音12层分清，不声称全validation RTL。
- [ ] `make test`、`make harness`通过；更新S2与精确范围、保存checkpoint。

## P7：E203开发联调、复位恢复和真实结束事件

**Files:** 新TB `sim/tb_e203_kwt_sram.sv`，修改候选SoC runner及Makefile；不改E203核和原TB，不覆盖旧融合副本。

**Interfaces:** 每任务6336 X+16384 W+256 bias提交，25344个结果、50688个aligned32写回；完成必须在posedge接受最后必要响应后确认。

- [ ] 新TB先暴露旧窗口漏配置/末响应过早问题，记录起点/写回/ACK的原生posedge事件编号；不能在negedge仅观察valid&&ready就finish。
- [ ] 开发窗口从CPU任务释放与调度开始，含KIND/ADDR、输入/参数搬运、总线等待、计算和写回ACK；共享区backdoor预装载和平台复位另列为排除项，不命名为正式比赛完整窗口。
- [ ] 加入确定性的运行中soft abort、pending响应复位及重新完整装载恢复；错误状态/重复START/非法COMMIT至少在ICB层有覆盖，SoC层报告其实际执行子集。
- [ ] 运行 `make test-soc`（2任务）验证新TB/runner，再 `make test-soc-full`（12层）。每个结果逐字对Golden、顺序/mask/数量、最终写回和ACK响应都检查；CPU代码核对协议、索引/错误/完成，数值逐字比较由独立TB负责。
- [ ] 编译最多2线程；单次仿真上限1800秒。到时保存真实timeout并诊断；不立即重复相同长测。每任务打印并flush进度，人工中断保留证据。
- [ ] 记录simulation、ELF、BIN、HEX、向量、平台补丁/源和日志SHA；全部输入结束时复核。仅在完整原生exit0与任务/suite计数相符后将开发SoC标PASS。
- [ ] 正式共享装载接口及官方计时起止未核定，保留BLOCKED；官方到位后计入平台真实装载过程，不能将backdoor加载当零时间/零活动。

## P8：参考PPA和时序瓶颈优化

**Interfaces:** 只接收当前含接口映射报告；原宏切边清单、参考SDC、工具状态/时序状态分别输出。

- [ ] 先用当前脚本重跑P4映射和 `make sta-logic MAPPING_REPORT=<新result.json>`，旧报告的脚本SHA不能通过当前校验。
- [ ] 报告setup WNS/TNS、hold最差Slack和check coverage；核对72宏/432端口组及所有未约束项。旧setup -22.923624ns、hold -0.004303ns保留为失败基线。
- [ ] 从真实netlist提取控制网fanout、pin cap、transition及前20条路径；确认INV499 sink/NOR472 sink问题在新含接口网表中的对应关系。
- [ ] 唯一受控实验：同RTL/库/STA假设下运行 `--buffered-reference --map-logic --include-interface`，对比面积、buffer/drive、fanout、setup/hold及电气违例。该选项已写入但尚无被接受结果，不能先称有效。
- [ ] 如映射层不足，选择一个有最大影响的控制扇出类别做局部寄存/使能分区；先证明周期/valid语义，再按P3/P6/P7影响范围重验。预计收益、资源/延迟、风险和回滚依据先写DECISION；不同时修改MAC与缓存策略。
- [ ] 增加已映射标准逻辑与相同宏切口RTL的可覆盖等价检查（按匹配端口保留宏语义边界）；若工具/模型不支持，明确NOT_RUN，不拿RTL仿真代替完整综合后功能。
- [ ] 可覆盖路径必须setup/hold都达门槛才叫局部时序PASS；即使通过仍不能叫完整150MHz。正式宏clock-to-Q/setup/hold/input cap及功耗缺失继续BLOCKED。
- [ ] 更新 `reports/PPA_PRELIMINARY.md`：含接口标准逻辑面积、FF结构、原生局部STA、活动范围、未建模部分；总面积/功耗/能耗不补零、不伪造。

## P9：官方接入准备与外部依赖

- [ ] 保持官方包原字节，接收项为功能Verilog、端口/时序手册、setup/hold/power Liberty、官方面积表、标准单元库/PVT和平台装载/计时规范；LEF等按工具需要补。
- [ ] 在 `tech/official_sram/` / `configs/sram-backends.json` 绑定显式文件清单、角/许可/SHA。校验缺文件、角不一致、重复模块时必须BLOCKED/FAIL。
- [ ] 官方Adapter只处理真实极性、mask、测试pin和Q保持/延迟；实际需求超出一拍1RW时先更新设计决策，不能假设所有宏都满足当前接口。
- [ ] 更新 `docs/OFFICIAL_SRAM_INTEGRATION.md` 与全部回归/面积公式/活动覆盖清单；真实官方代码与数据未到，不编写猜测引脚实现。
- [ ] 官方发布后重跑三后端功能、完整SoC、前后功能、全路径setup/hold/有效约束、总增量面积及完整12任务VCD/SAIF功耗，达全部门槛才改变正式PPA状态。

## P10：最终验收与上下文交接

- [ ] 生成需求到证据矩阵，逐项列PASS/FAIL/BLOCKED/NOT_RUN；原始完整log在artifacts，docs只保留轻量索引/SHA和解释。
- [ ] 独立审查覆盖新ICB修复、bank边界、负例/复位、全部核心/SoC计数、工具成功但时序失败的判定以及总面积范围。
- [ ] README确保 `test-memory/test-linear/test-linear-ff/test-icb/test-soc/test-soc-full/regress/synth-logic/sta-logic` 的存在/依赖/范围准确；所有命令串行协调重EDA，工具缺失明确退出。
- [ ] `make harness`验证来源/证据，`python3 scripts/harness.py checkpoint --label sram-subsystem-reviewed`；根目录无Git就不声称已commit。
- [ ] PROGRESS最多五项下一步，DECISION区分Accepted/Proposed；官方验收BLOCKED不妨碍已完成的功能版本交付，但不得称全部比赛达标。

## 优先顺序、时间与停止条件

恢复实施顺序：**P1来源/运行状态 → P2组合环/ICB协议 → P4含接口映射 → P7准确SoC验收 → P8真实扇出优化/局部STA → P9/P10文档收口**。P3/P5/P6已有证据先审计复用，只有新改动影响时重跑；P9的资料整理可独立完成。

不依赖官方文件的收尾预计约1–2个工程日：接口/协议/证据约半天，SoC/参考映射/STA诊断约半天到一天，独立审查归档约半天。这个估计不是时序收敛承诺；当前已知局部时序失败，若必须设计级修改应重新评估。12任务SoC时间受仿真模型开销影响，以单次1800秒上限和实际进度为准，不重复等待失效会话。

官方到位前无法保证150MHz完整时序、总面积<2.25mm²或完整系统功耗，也无法给出可信正式验收工期。缺材料之外若连续两次同类尝试无信息增益，停止该方法、保留证据并换诊断路径；重大接口/数值/资源改动单独决策。本轮到此交付计划，不执行这些未勾选修改。
