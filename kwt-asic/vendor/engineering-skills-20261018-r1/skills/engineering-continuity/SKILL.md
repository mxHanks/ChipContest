---
name: engineering-continuity
description: "Resume, hand off, or iteratively change a substantial engineering project when dirty sources, candidate versions, previous evidence, or cross-session state must remain consistent. Use for multi-stage development and reproducible workspace migration; skip ceremony for a small isolated edit."
---

# 可靠开发与项目接续

把一次改动收敛为可核验的工作单元；减少重复调查和重复构建。遵循当前用户目标和工程规范。下列方法按风险选用，不自动要求提交、冻结整个仓库或增加审批。

## 恢复事实

读项目规则、当前状态和相关决策，再核仓库根、分支/HEAD、工作区与暂存差异、近期提交。只读受影响模块的接口、实际源清单和测试。无Git时记录文件身份，不为满足流程强建Git。

有同名候选或overlay时，以实际构建入口解析出的源路径/哈希确认版本；HEAD不能标识未提交字节。文档落后于原始证据时记录差异，不回滚新文件去迎合旧哈希。历史PID和“运行中”文字不能证明当前存活；需要操作长任务时转读本项目运行记录，或使用可用的长任务诊断技能。

## 推进一个可验收单元

在现有状态文件或工作记录中写清：目标、影响模块、预计编辑、保留的接口/数值/事务不变量、完成判据、验证方法、依赖。普通小修可用几行描述，不必生成整套文档。

性能或故障假设应可证伪：观测是什么、改哪一个因素、预期哪项指标变化、什么结果否定它。并发工作应有独立写入边界；代理数量、资源与提交权限沿用本项目要求，不从此技能推断。

先读关键路径或实际瓶颈，再做局部可回滚改动。多文件接口改动保持原子性。参考模型、TB和DUT若共享同一个待证实假设，另找独立计数、向量或实际工具小探针核对，避免同错相抵。

## 选择能证明结果的验证

从廉价检查到受影响的集成检查；复用源/工具/配置/覆盖一致的合格阶段。只增加能发现目标缺陷的正例、负例或恢复例，不为可逆小编辑机械加测试。

验证优化时同时检查结果、工作量守恒和完成边界。例如请求已发出、下游已接受、事务已提交是三个事件；局部快不能推出端到端快。回压、半完成、多路独立握手及故障后的下一任务，往往比再加正常向量更能暴露接口问题。

通过状态附带范围：模型/本机软件/RTL/真实IP/综合/实现/实测各自记录。未运行或缺依赖写NOT_RUN/BLOCKED；native0、PASS文本或产物存在均不能单独接受结果。改动后的证据失效范围见[验证与复用](references/verification-and-reuse.md)。

## 留下可直接继续的状态

沿用项目现有文件；缺少且任务确有跨会话需求时，参考[状态与交接](references/state-and-handoff.md)。

- 当前快照保留事实、证据位置、问题和少量可执行下一步；原始迭代留报告。
- 持久决策区分Proposed/Accepted/Superseded；未证实假设不升级为决策。
- 输出交接包含未提交字节、外部依赖和已存在运行的所有权。跨路径解压并校验，才能声称迁移包独立可用。
- Git检查点仅在已有授权且边界安全时执行，显式暂存并审阅差异；无授权时保留未提交工作并记录。

可按需改写[项目规则模板](assets/AGENTS.template.md)、[当前状态模板](assets/PROGRESS.template.md)、[决策模板](assets/DECISIONS.template.md)和[交接模板](assets/HANDOFF.template.md)。不覆盖已有文件，也不把模板字段当成必须全部填写的表单。
