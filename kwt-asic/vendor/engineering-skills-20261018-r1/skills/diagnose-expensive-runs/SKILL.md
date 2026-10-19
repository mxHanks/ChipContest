---
name: diagnose-expensive-runs
description: "Prepare, inspect, diagnose, or recover expensive local/remote builds, simulations, experiments, or training runs when process ownership, native exits, frozen inputs, checkpoints, or contradictory results matter. Use to avoid duplicate runs and unjustified retries; not for ordinary quick commands."
---

# 长任务与失败诊断

目标是获得最小充分证据并复用合格阶段，按当前用户授权推进。具体硬件、线程、并发额度、内存阈值、重试次数由项目配置确定，不继承技能来源项目的历史值。

## 接管前先辨认任务

先读准确plan、claim、stage状态、终态与日志，再在执行主机核对controller、native子树及出生身份。进程状态与输入身份分别核验；PID、静默、经过时间、SSH失败、不可见列表都不能证明停机。缺可见性写UNKNOWN，不据此停止或重启。

按操作风险取得主机/用户、boot-id或启动时间、命令身份、父子/组关系；Linux核对/proc与所有可见cgroup祖先，Windows用执行主机原生身份API。详见[运行与资源](references/run-identity-and-resources.md)。不自动触碰已有运行。

## 为新昂贵运行建立最小合同

复用现有runner和计划格式。记录精确输入/工具/配置、源选择、工作量、自检与原生退出要求、唯一输出目录、资源/角色准入、停止条件。仅在存在资源争用或重复风险时用对应作用域的锁；不能将本项目忙进程白名单推广为全局绕过。

在廉价实际用例中先确认最易失败的外部边界：参数解析、top/路径、生成/复制顺序、report属性/JSON格式、native0但fatal或早停。测试替身不替代外部工具资格。检查脚本import、entry与真实字段可避免昂贵结果被后处理错误误拒绝。详见[控制器资格](references/controller-and-reader.md)。

稳定绑定必要输入后再启动；运行期间冻结相关字节。立即捕获每阶段原生退出，依赖失败不继续下游。昂贵阶段一完成就保存checkpoint/不可变产物，再做报告查询或断言，防止分析错误迫使重做计算。日志、manifest和原始终态均保留。

## 区分失败发生在哪一层

分别报告原生阶段结果、runner/reader结果、要求的验收状态。native0可能包含fatal或不完整自检；外层失败也可能发生在计算已正确完成之后。发生冲突先保存现场，再用同一原始证据诊断。

若只是读取器格式/计数/字段错误，修订全新只读reader并验证正常及拒绝案例；通过后只重读，不编辑冻结runner、原日志或原失败终态。缺数值、自检、身份或必要预冻结时不能补猜、倒填或普遍忽略错误。独立审查需绑定精确证据及明确的异常范围。

## 下个实验必须改变认知

写出假设、保持条件、唯一改动（或明确混杂因素）、预期、否证条件、代价和停止/转向条件。一个有理由的重试可以有效；同点稳定失败、重复零收益时停止策略矩阵，转真实栈/core、最小实际工具探针、实际关键路径或受支持版本依据。不要把同一症状武断归因于缺DLL、内存不足或RTL错误。

只有身份、工具/配置、完整性和阶段前提仍成立，才从checkpoint恢复最窄无效阶段；不要顺带重跑已接受数值/综合。改变约束必须有接口语义依据，不能用放宽容差/false-path掩盖问题。变更源码则重新判断后续接受范围。

使用[实验与验收](references/experiments-and-acceptance.md)及按需填写的[运行记录模板](assets/RUN_RECORD.template.json)、[实验模板](assets/EXPERIMENT.template.md)。监控按状态变化或合理退避更新，不反复轮询静默日志，不从最后进度推完成百分比。后台监控/定时任务仅在用户要求时建立。
