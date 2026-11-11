# 2026-11-11 面积优化定稿证据

本轮选择B（ACC41＋引擎结果41＋FIFO41），固定源码父`96fffcb2a4b2492fd2cfdecb88e164d2c67881ae`、硬件子`ccdac30d92ecf40f14d0b78879b8711fb0b1cdd1`。完整12任务304128个Y32逐位正确，主周期428915拍，每层及全部工作/等待计数与原48位版本相同。保守同条件计费面积从523712.858238降至504395.193438库单位，减少3.6886%。**时序未闭合，实际150MHz、2.25mm²与正式资格未认证。**

[选定方案与软件交接](../../s3-y32-area-opt-handoff.md) · [结果](../../s3-y32-area-opt-results.md) · [状态](../../s3-y32-area-opt-status.md)。源码与文档发布状态见handoff；历史测量保留原父子身份，由安装回执桥接到当前源码，不改写历史结果。

## 主交付

所有本目录文件的字节数和完整SHA见`SHA256.json`。README和SHA256.json不参与自身递归哈希，旧证据字节未改。

| 文件 | 内容 |
|---|---|
| `sim-candidates-r1.tar.gz` | 607文件仿真delta；A/B生成源、默认与特化SV、完整模块/DMA/CPU日志、ELF/image、数值/AST/几何证明和REPLAY入口 |
| `candidate-a-ppa-inputs-r3.tar.xz` / `candidate-b-ppa-inputs-r3.tar.xz` | 实际242项服务器输入；原SDC、158条编译源、同库/宏/compile策略；两份大XML仅在服务器运输时省略，本地完整保留 |
| `r5-mini-native.tar.gz` / `r5-leaf-native.tar.xz` | 原48位基线metadata、完整32.5MB leaf清单和DC面积/日志/引用报告，保留R5原FAILED/1与owner-stop |
| `pt-r4-native.tar.xz` | 基线全部46项PT输出，逐SHA/bytes核验 |
| `candidate-native-reports-r4.tar.xz` | A/B完整leaf、所需DC报告、所有各45项PT输出及串行链原件；2532604B，SHA `fd235de2b63b06b321d9940641937e1a29a35c6497ca6ba3ed89687be13fd763` |
| `final-tools-r2.tar.xz` | 224项工具与最终审计/比较/选型/安装/清理回执；307384B，SHA `f063892d2f0a83c90cc337d62d0d67adb9a81ea1b2430393010b23ffffae73f9` |
| `final-supplement-r1.tar.xz` | 67项补充；完整PPA输入恢复工具及实际恢复/审计重放、r4运输脚本/索引/20片回执；84308B，SHA `364f656ea1808e4762498d5e3b4629048c601fdd406023f41e430fbe349f8b48` |
| `selection.json` / `selected-install-identity.json` / `selected-commit-review.json` | B选择依据、165份现有RTL与真实CPU源逐SHA绑定、父仅5生成器＋gitlink/子仅1tile的独立提交审查 |
| `a/b-native-area-review.json` / `a/b-native-pt-review.json` / `a/b-native-comparison.json` | 独立逐叶重算、全部PT身份/违例核验、范围外逻辑正增长保守加计；文件实际前缀为`a-`或`b-` |
| `native-pt-drc-triage-r2.json` | DRC逐pin完整分类，包含带低打印精度notice的违例，不将其当零slack忽略 |
| `ppa-input-archive-replay.json` | 仅用交付archive恢复baseline209和A/B各243完整输入，重放三份面积审计实际通过 |
| `vnc-v5-restoration.json` | 自有manager292673退出、SendCutText恢复0的原生VNC读回记录；不发布屏幕截图或凭据 |

完整仿真delta为14917124B，SHA`885d595a33b6dbfb682f5e9555f15872ac63521654bcf0a3b36556cabbd028bd`。它的共享来源是仓库原发布包`docs/validation/s3-y32-4k-20261110/frozen-delivery.tar.gz`，5656296B，SHA`464bea138c254d842b1db656da0e8feb42e04e509f9ab85d92e0cd30736b543f`。

## 复现路径

1. 从新目录安全解压仿真delta，执行其`REPLAY.py`核对所有文件身份。结合原发布包，`--prepare-only`可恢复与实测逐SHA相同的A/B CPU源码/向量；该过程已实际通过。显式`--run`才启动新仿真，须遵守截止和新输出目录检查。
2. 将`final-tools-r2`和`final-supplement-r1`解压后保留完整仓库相对层级。补充包`build/area-opt-20261111/replay-inputs/README.md`给出fresh consumer精确命令：只用上述归档及15份baseline metadata恢复baseline209、A/B各243与实际r3各242输入。原package-files.json SHA和每个文件SHA均已实际重现，无额外文件。
3. 安全解压候选native报告包，保持`a/dc`、`a/pt`、`b/dc`、`b/pt`结构。baseline原件用已交付mini＋leaf合并，保留原身份和原FAILED/1。运行工具包`audit_native_area.py`、`audit_candidate_pt.py`和`compare_area_report.py`，按恢复工具README和原审计命令指定路径。它们是文件审计，不运行EDA。实际三份面积审计已使用恢复树重放通过，PT各45项与baseline46项也已完整核验。
4. `selected-install-identity.json`及`selected-commit-review.json`保存本轮已实际执行的父子提交、生成源与CPU源码身份核验。`independent_commit_review.py`是该次历史只读审查脚本：硬编码当时build输入路径和不可覆盖输出，供查阅审查逻辑；不是fresh checkout直接重跑入口，包内已有回执也会触发拒绝覆盖。原始命令、工具/库/时钟、固件/向量SHA、范围证明和失败记录均保留，不以当前HEAD覆盖测量时元数据。

## 明确缺项

A/B各584项DC输出中51项已回传，包括完整leaf及必要面积报告；mapped.v/ddc、WORK、SVF等其他输出仍仅由服务器原始execution记录钉SHA/bytes，**未在本地验证网表字节，未运行映射后形式等价**。r4薄包没有这些文件，不宣称全部DC输出已返回。两候选全部各45项PT输出完整返回；PT绑定真实映射和同库、原约束，采集成功不代表时序通过。

基线/A/B各211项coverage违例、27911项未测。B setup−10.11695099ns、hold−0.13472039ns；B DRC maxcap/mincap/maxtransition为92/1449/276。674个辅助CEN/RET1N逐项分类、337实际CLK均关联，原计数与其他未测检查保留。实际150MHz未通过，4196.64task/s只是仿真周期按150MHz换算。库面积量纲、官方SRAM计价和宽口平台资格未确认，不能把库单位直接当mm²或宣称比赛2.25mm²合格。

## 历史记录

早期DC前端失败保存在`native-frontend-failures.tar.gz`。原R5映射后额外报告查询卡住，负责人仅停止经UID/cwd/进程组核验的自有DC组；FAILED/退出码1和Signal15日志保持，后续只读PT未改写旧状态。旧大包102/3745块中断、候选r3第2片25/32块中断及VNC握手超时均保留。

`progress-tools-r1.tar.xz`、`ppa-tools-r1.tar.xz`及`publication-progress-r1.json`是当时未选型的历史进度快照，不替代最终包。最终r4为20份小分片，分片与整包SHA全部通过，所有sender最终ACK均原生核对。临时SendCutText已恢复0，自有manager已退出；没有重启VNC或终止他人作业。新实验截止2026-11-11 23:59上海。
