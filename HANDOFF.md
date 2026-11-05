# ChipContest 队友交接 · 2026-11-05

## 交付决定与入口

交付 **S2e paired-HI 为主方案，S2c 为唯一对照**。其余候选不追加评测。按项目所有者确认，当前S2e如实合入main；资格缺口继续公开保留。原始工作目录是 `/home/mxhanks/Projects/ChipContest`。额外22个工作树在交付核验和推送后永久删除，不建立外部归档；父仓库分支历史及本次S2e子仓提交保留；其他本地实验子仓/ignored结果随目录永久删除，交付所需证据放在本仓库。

入口：[快速开始](quickstart.md)、[原始两候选证据与逐层CSV](docs/validation/xu-score-two-candidate-final-20261105/README.md)、[冻结服务器复现工具](tools/repro/server/README.md)。

## 实际结果与边界

| 指标 | S2c own9c16 | S2e final155 |
|---|---:|---:|
| 真实12层总周期 | 11,887,872 | 10,420,116 |
| 每层周期 | 990,656 | 868,343 |
| 全SoC任务诊断能量/mJ | 2.6384471466669330 | 2.3659452273331971 |
| 加速器面积/mm² | 0.2948018380 | 0.3003096339 |

S2e周期−12.3466673%、相同任务吞吐+14.0857933%、诊断能量−10.3281174%、面积+1.8683045%。S2e占2.25mm²加速器面积预算13.3471%。面积对应各自测能网表，不混用wrapper面积与全SoC功耗。数字从native报告舍入功耗乘实际fs窗口重算，长小数不意味着额外测量精度。

状态：**AUDITED / DIAGNOSTIC / NOT_QUALIFIED**。不能上报比赛最终能耗或8T+8E+4A总分。两组采用同一404c7d SDC与45037c forwarded-clock scope，但分析方法相同不证明完整150MHz已闭合。

当前未解除的问题：

1. 严格mapped VCS中原mandatory fatal仍存在（bias_commit等四态问题）；`+notimingcheck`下公共输出通过只属于诊断。必须保留完整原TB的私有断言、clear与FIFO检查，不能删fatal或以HOST+4结束代替验收。
2. 每层5280个SRAM Q存在TX，4256个Q整窗TX。`x_probability=0`、TC=0和shadow probe不能证明物理Q已知，条件/内部功耗及修补逻辑活动仍待审查。
3. 原公共时序方法中仍有27217 untested、31 unconstrained及UART/clock/pulse/PLIC等缺口；S2c还有40项时序违例（8hold、5removal、27clock-gating hold）。S2e own155完整FM 42338点通过不等于上述时序/功能资格通过。
4. 当前SAIF窗口是首个源数据请求至最终Y写响应退休，**pretask clear在窗外**。现有全SoC任务诊断能量不包含该阶段，不能宣称完整比赛单任务能耗合格。
5. 2026-11-02开发软件数值评测覆盖4445个样本×12个独立FFN1，最坏aggregate NRMSE约0.01328069%、最坏sample/layer约0.01954010%；官方600样本和完整encoder未完成；这不是4445条S2e RTL逐条仿真。原始数值检查见 [数值证据](docs/validation/xu-score-s0-numeric-20261102/README.md)，mapped公共诊断与私有门槛见 [141原件](docs/validation/xu-score-resource-function141-20261105/README.md)。

## 改了哪些代码

- S2c既有Chisel：`src/main/scala/linear/LinearAutoGroupCore.scala` 自动组调度及两槽结果FIFO；`GenerateRTL.scala`增加相应生成入口。此前缓存核心与bias bank代码仍在源树，具体硬件行为见 [S2c设计说明](docs/xu-s2c-autogroup.md)。
- **S2e没有新Chisel计算架构修改。** E203子模块 `rtl/e203/perips/accel_icb_slave.v` 增加capability `0x0e0=0x58480001`、四个paired-HI读口 `0x140+4*p`，一次返回相邻两个结果的高16位，维持旧HI读口语义、背压快照和显式POP所有权。
- `tests/e203/firmware/accel.c` 使用 `bias-hw-autogroup-paired-hi-window`，每相邻两结果读两次LO32和一次packed-HI，独立符号扩展后按原canonical Y顺序写回。每层结果读取由50688字降为38016字，输出数、写回数、输入/权重/偏置不变。
- 被动TB/契约增加读口与计数检查。保持八个PE、signed16输入/权重、signed40偏置、signed48计算/结果、原SRAM几何与数值向量。32/64PE不纳入当前交付方案。

细节见 [S2e协议说明](docs/xu-s2e-paired-hi.md)。

## 源码、网表与证据身份

生产源码来自测得的父提交 `5bf123bfead8f2a37f97f3234d4e40ce8201aae9`，E203子提交 `a0767db69628ef30e53de2d1e93dd0360c0ccf76`，后者已发布到团队子仓库的 `codex/xu-s2e-paired-hi`。当前main在原remote-main历史之上导入选定生产文件，并通过一次保留树的merge接上S2e历史，使strict入口所需旧固件提交可在新克隆中读取；没有覆盖远端既有main历史。源码逐文件身份见 [source-identity.json](docs/handoff-evidence/source-identity.json)。新交付提交哈希是集成身份，不能冒称历史测量提交哈希。

S2e测能目标为own155最终网表SHA256 `3440182eca862290a874bedc4eb3f94168681a7028d584d15217a13dbeafa794`；其捕获活动仍来自own89/120原始映射 `0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0`。155经历独立时序修补与有序三SVF的完整FM链。**源代码重生成RTL不会直接得到155修补后网表**；必须沿原服务器89→134失败保留→155修补链复现，不能将两个映射视作同字节文件。S2c测能绑定自己的own9c16网表。native面积/FM原件在 [handoff-evidence](docs/handoff-evidence/)。

原始171包SHA256 `2f46075e337a21608faf8dc4f4308e90a31c610e6dd5d1dec4a4fb7bb17ae515`，412payload/353192073B；191包SHA256 `44770417f09a4244cbeea5690b4f21923e5d641de365094010ca7eeaf7c998b3`，392payload/367456367B。压缩包及逐层pt.log/power.rpt哈希已随main交付。数值/141的交付README已更新当前路径，外层清单相应重建并保留original清单；native包和历史审计正文未修改。超大pin报告正文、库、SAIF等仍在原服务器；本地包的hash-only项是服务器流式哈希回执，不能称为本机重读全部原报告。

```bash
python3 -B tools/scripts/xu_verify_handoff.py
```

该便携复核只依赖本仓库和Python标准库，独立检查原包、逐层周期/能量、实际Tcl方法、native日志及面积绑定。历史179/205审计输出原样保存；其中179关于旧57方法不一致的警告仍是历史事实，新205使用190共同方法完成最终对照。便携核验不代替重新运行EDA。

## 原服务器接手

原件根目录：`/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102`。不要清理服务器原件或覆盖任何已运行目录。以下是已有结果，不需重新启动：

| 内容 | 根目录内路径 |
|---|---|
| S2e最终map/面积/STA/FM | `s2e-own-timing-repair-20261105-155` |
| S2e task0 / 全12层功耗 | `s2e-final155-power-preflight-20261105-166` / `s2e-final155-power12-20261105-166` |
| S2c task0 / 全12层功耗 | `s2c-common-scope-preflight-20261105-190` / `s2c-common-scope-power12-20261105-190` |
| 持久队列与事件 | `unified-experiment-control-20261105-150` |

服务器同一工具链：DC2022.03SP5-5、PT2022.03SP5-1、FM2020.09SP5、VCS2020.03SP2-6、SiFive GCC10.2。面积使用服务器原工艺库；库路径和SHA在prepared/input receipts中，未把第三方库、模型、手册或密码放入仓库。

只读查看统一总控：

```bash
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status
```

不要运行旧 `upgrade/start` 配置来重登记八候选。后续新实验只保留S2e/S2c，先核查已有registration和真实进程，沿现有单原生槽位总控依赖顺序登记。许可证总配额未知，当前checkout不能当作余量，不擅自提高并发。

已有diagnostic207中S2c查询完成，S2e因cached handle查询失败；失败属于待修复诊断，不是资格成功。后续214/216本地探索没有经过完整服务器验收，不作为交付通过证据。服务器复现工具与原实际命令JSON见 [tools/repro/server](tools/repro/server/README.md)；这些工具刻意锁定原服务器文件身份，不能在缺少工艺库/网表/SAIF的普通新克隆中直接跑出PPA。

接手顺序建议：先便携验包及本地功能回归；再原服务器完整RTL VCS；随后解决严格mapped fatal、未知Q与clear窗口；再完成两图同配置完整150MHz资格；最后重测全SoC完整任务能耗并按8T+8E+4A评分。每项新实验保留原失败，使用新namespace/输出目录，记录冻结输入、逐层周期、面积、能量、原日志SHA及实际argv。

## 目录清理

所有额外工作树永久删除，无外部归档。原始目录内的赛题指南PDF、原有assets/模型/库、本交付源码及关键证据保留。清理实际名单与验证结果在 `docs/handoff-evidence/cleanup.json`（最终清理后写入）。本机既有2026-11-06 01:00 CST关机安排未改动；服务器独立运行不依赖本机继续在线。
