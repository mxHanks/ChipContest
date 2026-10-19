# KWT-1 + E203 SRAM：当前框架与剩余修改计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 本计划已于2026-10-18执行至完整开发SoC及回归收口；当前结果见末节。未勾选项不得当作已完成。主代理整合，辅助代理只读审查，重型EDA一次一项。

**Goal:** 保留现有计算和接口契约，完成可替换SRAM子系统的开发验收，并明确官方宏尚缺时的PPA边界。

**Architecture:** E203通过32位ICB驱动独立adapter；原双行×8列计算候选通过20个逻辑bank访问可替换1RW后端。共享512KiB属于平台，内部bank、张量地址和宏实例分开管理；不重写E203/MAC，不改变Golden。

**Tech Stack:** 项目本地Icarus12.0、Verilator5.020（编译最多2线程）、Yosys0.33/ABC、OpenSTA2.0.17；Nangate45 typical只作参考，RISC-V裸机工具链用于开发Fork联调。

**Spec:** [存储设计](../specs/2026-10-17-sram-subsystem-design.md)、[当前审计](../../SRAM_AUDIT.md)；本计划更新10/17计划的执行状态，保留旧计划和失败记录。

## 固定边界

- 计算保持99×64输入、64×256权重、256 bias和99×256输出，12层逐任务重新装载。
- X/W signed16、bias signed40、内部精确41位、输出signed48；不改变数值格式、舍入或软件模型。
- 目标150MHz；官方PDF面积上限为≤2.25mm²，本项目沿用更严格的<2.25mm²目标。新增逻辑、接口、内部SRAM全部计入；复用平台单列。
- 一拍同步读、无读Q保持、reset不清payload、每bank同拍读写禁止。官方宏不满足此契约时先设计Adapter并重新验证，不能只移动valid。
- 官方端口/时序/Liberty/面积/功耗和正式平台未齐；完整时序、面积、功耗为BLOCKED，不以黑盒缺项的零成本或正Slack替代。
- 原RTL、Golden、原固件、vendor及队友原仓库保留。根目录不是有效Git，不执行init/commit；使用SHA checkpoint回滚。当前计划整理不启动新RTL/EDA实验。

## 当前框架

```text
E203 CPU / 固件
 ├─ 512KiB共享区：当前层X/W/B、完整Y、任务邮箱
 ├─ 既有ITCM / DTCM：不属于AI内部SRAM
 └─ 32位ICB → kwt_icb_slave_sram：staging、START、Y_LO/HI、ACK
                  ↓
     kwt_linear_engine_rowpair_sram：16 MAC / 调度 / 结果队列
                  ↓
     20个逻辑bank → kwt_sram_bank：片选、宽度拼接、返回选择
                  ↓
     kwt_sram_1rw：统一一拍1RW契约
        ├─ BEHAVIORAL：功能仿真
        ├─ FF_FALLBACK：原行为对照、显式FF综合
        ├─ BLACKBOX：只综合周边逻辑
        └─ OFFICIAL_MACRO：等待真实Adapter和工艺文件
```

内部payload为50.75KiB，容量模板为72片/56.5KiB；后者不是已实装官方宏。完整Y驻留共享区，内部只缓存最多4行结果，不新增全矩阵副本。

## 已做与未做

| 阶段 | 当前状态 | 已有证据或剩余门槛 |
|---|---|---|
| P0 审计 | PASS | PDF重核、源码/容量/端口审计、当前证据SHA复核 |
| P1 基线与执行记录 | 局部PASS | 原492文件无缺失；原RTL/Golden/固件未变；原生退出/中断记录13项测试通过；统一配置入口仍待收口 |
| P2 Wrapper/ICB | PASS：开发协议 | 已切断组合反馈；双后端各1完整+1abort，含回压/错误访问；不等于CPU SoC验收 |
| P3 Behavioral | PASS | 67案例：25正常、42预期拒绝；7组行为/FF匹配；新增bank未知使能直接检查 |
| P4 Blackbox | PASS：参考逻辑 | 含接口72个opaque/16MAC；44,120标准单元、0.055476428mm²，不含SRAM/E203 |
| P5 FF对照 | PASS：功能/结构 | 原版/行为/FF对照；历史全FF结构429,231寄存位，26,801个宽字RTLIL mux；非门级面积 |
| P6 核心回归 | PASS | 18子阶段；新核心76任务/1,926,144输出，另原版12任务；本次未包含SoC |
| P7 E203 SoC | PASS：开发12层 | 新TB/固件/validator接通，304128输出及真实写响应/复位恢复通过；非官方平台 |
| P8 参考PPA | 映射PASS，Timing FAIL | 有缓冲setup最差+4.652084ns；data hold -0.013133ns、removal -0.255385ns；默认wire load已显式记录 |
| P9 官方接入 | 手册已有；实装BLOCKED | 不能猜测官方pin/碰撞行为/PPA；等待外部包 |
| P10 收口 | IN_PROGRESS | 仍需新SoC、受控映射验证、来源入口、最终审查 |

完整索引：[当前审计JSON](../../runs/sram-current-audit-20261018.json)。这些状态按范围独立判定，不能把子项PASS合并为项目全部通过。

## Review Focus

1. 最后命令被接受不等于最后响应被消费：SoC按posedge握手验收。
2. 合法向量路径不能被TB硬编码目录替换：只回放校验器返回的已验证字节。
3. abort/硬复位后的半个任务不得并入正常任务统计或留下旧数据。
4. ABC可能exit0但内部命令失败：必须同时检查诊断、输出、完成标记和SHA。
5. 局部STA工具PASS与Timing PASS分开；setup、hold及未建模边界均须报告。

## 下一批1：接通新的SoC验收链（优先）

**Files:** 新建`sim/tb_e203_kwt_sram.sv`；修改`scripts/verify/run_sram_soc.py`、`tests/test_sram_soc.py`；接入已有`soc/firmware/kwt_smoke_sram.c`。原TB和原固件保留。

**Consumes:** 已通过ICB协议候选、经过`validate_export`校验的向量字节、现有开放E203融合副本。

**Produces:** 逐任务配置/写回/ACK/最终邮箱响应的真实接受时间；明确为`development_window_cycles`，共享区TB预装载不算官方装载性能。

- [x] 先增加向量暂存测试：manifest使用非默认相对路径仍回放校验后的数据；路径替换/篡改必须拒绝。
- [x] 新TB在posedge记录command和response，核对每任务22,976次load commit、25,344输出、50,688次输出写响应和1次ACK响应。
- [x] 开发窗口从CPU任务释放开始，覆盖初始配置、搬运、计算、回压和最后邮箱响应；最后输出写响应 < ACK响应 < 任务结束。
- [x] CPU执行一次忙时soft abort；正常任务运行到共享响应等待时注入一次现有外部reset，证明pending/response清除并重跑完整任务。中断epoch单列且不计入完成任务。
- [x] runner切换新TB/固件/top，真正调用`validate_soc_log`；记录ELF/BIN/HEX/simulation/向量SHA，失败也检查源变化。
- [x] 先`make test-soc`跑2任务，再`make test-soc-full`跑12层；必须原生exit0、唯一suite/recovery marker、全部输出逐位一致。旧TB通过不能代替本项。

**预估：** 约0.5–1工程日；仿真每次最多1800秒，失败先定位，不能重复盲跑12层。

## 下一批2：修参考缓冲映射，再判断是否需要RTL优化

**Files:** `scripts/synth/run_memory_blackbox.py`、`scripts/synth/run_memory_partial_sta.py`、相应主机测试、`reports/PPA_PRELIMINARY.md`。本批先不改核心RTL。

**依据：** 实际ABC网络在`buffer`阶段遇到无fanout节点；原生exit0但没有output.blif。两门最小复现仅加`cleanup`后通过，修复后的实际网络尚未跑。

- [x] 固定已有约束/驱动/负载，在`map`后、`buffer`前插入`cleanup`；保存原失败，给脚本阶段/输出校验加失败回归。
- [x] 只启动一次有界含接口`--buffered-reference --map-logic --include-interface`实验，核对72宏保留、逻辑输出和完整工具结束。
- [x] 以当前同RTL/同top/同库/同SDC的无缓冲参考作对照，运行局部STA，比较setup/hold、fanout/cap/slew、buffer数和逻辑面积。
- [ ] 若ABC/映射仍失败，继续诊断工具/源集，不进入RTL优化。取得有效网表和STA后若时序仍失败，才从真实路径选影响最大的一类控制网络，在独立候选局部优化；先记录周期/接口/资源/验证/回滚代价，不同时改缓存和MAC。
- [x] setup或hold任一失败均保持Timing FAIL；1153输入、2436输出缺delay和2436未约束端点必须按宏/reset边界解释，不隐藏。
- [ ] 标准逻辑与相同宏切口RTL的可覆盖等价检查单独开展；若无法建立可靠语义，明确NOT_RUN，不能用RTL回归冒充综合网表验证。

**预估：** 工具修复与参考对照约0.25–0.5工程日；设计级时序优化另评估，不承诺官方150MHz收敛。

## 下一批3：统一入口、回归和审查

**Files:** `configs/sram-backends.json`、相关runner、`Makefile`、`README.md`、`harness/tasks.json`及文档。

- [x] 后端配置成为可验证的显式源集入口；防止脚本与JSON脱节、重复模块、官方缺项静默回退。
- [x] `make regress`纳入ICB协议阶段；状态区分RUNNING/FAIL/PASS。SoC实际使用持久终态检查，总回归读取并核验子report的status/证据/哈希，不能只相信stdout的PASS摘要，也不能把初始运行状态当算法FAIL。
- [x] 增加或保留工具非零退出、重复/缺标记、输入变化、setup/hold双门槛及覆盖检查；按修改影响运行最小测试，再跑总入口。
- [x] 独立审查新SoC边沿、复位恢复、数据来源、同源综合和PPA范围；重要问题修复后重新验证。
- [x] 更新用户可读`docs/USER_CHANGELOG.md`、PROGRESS、DECISION及官方接入手册；每里程碑运行harness校验与SHA checkpoint。当前`scripts/harness.py`源树不含`reports/`、`tech/`：需补显式、许可允许的文件归档、归档成员测试及恢复核验；本次先单独保存这两处文档，不宣称技术包已纳入自动快照。

**预估：** 约0.25–0.5工程日。当前条件下开发版本剩余约1–2工程日；这是范围估计，不是正式比赛验收承诺。

## 下一批4：官方文件到位后（BLOCKED）

- [ ] 获取官方功能模型、端口/读延迟/碰撞/极性说明，宏Liberty/面积/功耗表、标准单元库/PVT及正式E203/装载规范；按需LEF等工艺文件。
- [ ] 只在`tech/official_sram/`及Adapter/配置接入，核实容量组合和实际面积，不伪造接口或价格为零的宏。
- [ ] 重跑行为/FF/官方模型、完整12层SoC及综合前后功能，再做完整setup/hold/覆盖、全部新增面积、完整任务窗口功耗和能耗。
- [ ] 确认官方延迟仍能满足上层一拍契约；如不满足，独立评审Adapter/FSM修改并重新验证首尾数据、连续任务和吞吐。

官方材料尚未发布时无法给出可信的正式验收耗时；等待不阻止前三批工作。

## 执行与回滚

原设计与候选使用不同顶层和显式源集。每批先记录当前SHA，先复现问题再最小修复；失败日志保留。重大数值/接口/资源变更另立决策。连续两次同类尝试无信息增益则换诊断方法。无有效Git时以checkpoint恢复受影响文件，不整体覆盖用户修改。

本文件是已完成审计后的**剩余工作计划**；新SoC、新缓冲映射、局部时序优化和官方宏接入均未被本文宣称完成。


## 2026-10-18执行收口：当前剩余工作

已完成真实make regress20子阶段、175主机测试、67存储案例、核心76新任务、12层CPU完整开发写回及恢复；当前源码可恢复快照/异目录主机检查已执行。原始证据见`docs/runs/sram-implementation-20261018.json`。

尚未完成：①综合前后标准逻辑功能一致性，已有两次有界共同宏切口证明超时，NOT_PROVEN；应切换有效信号感知的miter/门级功能回放，不重复原尝试。②参考data hold与内部soft-reset removal FAIL，任何候选须保持SDC并独立验证，不能豁免。③官方平台/宏/工艺/完整PPA仍BLOCKED。

补充纠正：库默认统计wire-load此前已被OpenSTA实际使用，现显式绑定并修正元数据，数值未变；当前不能称pin-only。harness现保存白名单源字节并显式收录PPA报告/技术README，原官方材料仍未纳入，不夸大完整外部镜像范围。勾选只代表该开发任务已执行，不代表整个比赛验收完成。
