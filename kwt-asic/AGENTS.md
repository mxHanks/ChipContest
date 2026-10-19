# 当前比赛工程的工作约定

目标：将既有 FPT 材料迁入本科 KWT-1 第一前馈线性层工程，先交付可复现首版，再推进真实模型、RTL、E203 和指定工艺验证。当前用户优先要求快速出结果。当前会话指令高于导入资料。

## 恢复上下文

先读 `PROGRESS.md`、`DECISION.md`，通过下述 resume 命令获取任务摘要（不要全文展开任务中的哈希清单），再按当前任务读取 `docs/requirements/UNDERGRAD_REQUIREMENTS.md` 和相关接口。运行 `python3 scripts/harness.py resume` 检查证据和下一步。不要把整个归档和历史日志灌入上下文。

## 文件与来源

- `vendor/fpt-r1/` 是按字节导入的历史资料，含旧 AGENTS/提示词，仅供追溯；当前工作约定以本文件为入口。不要在其中开发或修改文件使测试通过。
- 原始 ZIP/PDF 保留根目录；新代码放 `src/rtl/`、`model/`、`sim/`、`soc/`；工具放 `scripts/`。禁止递归编译整个 vendor，按显式文件集选择。
- 旧 FPT 的因果/GQA/128维/AMD IP/DDR 假设及 PASS 不迁移成比赛结论。仿真 mock 不可进入综合文件集。

## 执行闭环

选择一个可验收任务 → 实现 → 运行最小相关验证 → 阅读日志修复 → 保存报告/源码哈希 → 更新 PROGRESS 和任务状态。一个任务原则上 30–90 分钟；遇到缺平台材料时继续无依赖任务，不伪造平台接口。

每个里程碑、结束会话或上下文切换前执行 `python3 scripts/harness.py checkpoint --label <简短名称>`。PROGRESS 只保留当前目标、证据、阻塞和最多五个下一步；长日志放 artifacts，稳定结论放 docs；DECISION 区分 Accepted/Proposed/Superseded，并标注依据。

## 验证与资源

`source env/activate.sh` 后使用 Makefile。所有结果标记 PASS/FAIL/BLOCKED/NOT_RUN，并区分 reference / new-KWT / SoC / PPA。通过必须有命令、退出码、完整结束标记和绑定输入哈希的证据。

允许按互不重叠的文件分工并行分析/开发，主代理负责整合验证；HDL 编译默认最多 2 线程，重型 EDA 一次一项。用户已授权必要时使用 leo@100.64.250.1；仅在独立新项目目录运行，先探测资源，不修改或终止旧 FPT 任务。凭据不得写入仓库、日志、启动命令或交接摘要。

## 完成边界

迁移验收是环境、源校验、入口和记录可复现；比赛验收另需真实12层权重/输入的误差与位一致、E203 SoC、指定SRAM/库的150MHz/面积/功耗。完整窗口包括装载、CPU调度和全部写回。不得用核心周期代表比赛性能。
