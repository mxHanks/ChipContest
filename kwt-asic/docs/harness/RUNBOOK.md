# 长流程执行与上下文恢复

本项目采用文件驱动的执行闭环，不依赖聊天记录作为唯一状态。设计参考 OpenAI 的 [Run long horizon tasks with Codex](https://developers.openai.com/blog/run-long-horizon-tasks-with-codex)：将目标、执行计划和状态持久化，每个里程碑根据验证反馈推进。这里的具体文件、脚本和任务粒度是本项目设计。

## 唯一入口与职责

| 文件 | 保存什么 | 更新频率 |
|---|---|---|
| AGENTS.md | 工作范围、恢复顺序、资源边界 | 稳定约定变化时 |
| PROGRESS.md | 当前阶段、最新证据、阻塞、最多五个下一步 | 每个里程碑与交接 |
| DECISION.md | 决策状态、原因、影响与重新考虑条件 | 做出/推翻决策时 |
| harness/tasks.json | 带依赖的任务和机器可读验收证据 | 状态变化时 |
| configs/project.json | 赛题固定参数与尚未冻结项 | 有依据才变更 |
| docs/runs/ | 对失败和有效实验的短分析 | 必要时 |
| artifacts/runs/ | 每次运行的完整命令、日志、版本、哈希、结果 | 运行器生成 |
| artifacts/checkpoints/ | 带哈希的上下文快照 | 交接前 |

PROGRESS 中 PASS 必须指向具体 result.json，不能仅引用聊天结论。tasks 中每个PASS必须同时提供 evidence 文件SHA和 source_bindings（被测源/配置的相对路径与SHA）；源码变化时resume/validate/package会拒绝沿用旧PASS，要求重跑或将任务降为TODO/IN_PROGRESS。失败历史保留；修复后创建新 run，不覆盖失败证据。正式精度、RTL、PPA 报告必须绑定同一个冻结配置和输入，不拼接结果。

## 每次恢复

```bash
source env/activate.sh
python scripts/harness.py resume
python scripts/harness.py validate
```

阅读短状态和当前任务对应的资料，确认最后一次命令是否完成、有无遗留进程、依赖是否变化。优先续做未完成工作单元。不要为“重新熟悉环境”无条件重跑全部测试，也不要从旧归档提示词恢复原FPT任务。

## 工作单元

开始时指定任务ID、修改范围、验收命令、资源限额。实现后跑最小相关检查；失败先看完整日志，再分类为代码错误/工具兼容/外部缺依赖。兼容性修复放新适配目录并记来源，不篡改 vendor。没有平台时不猜总线端口、宏时序或工艺角。

完成时更新 tasks 与 PROGRESS，记录需要重新执行的检查；决策只写依据和后果。超过一屏的日志不进状态文件。跨代理交接只给任务、所有权、输入路径和结果路径，避免重复复制文档。

## 上下文切换与归档

```bash
python scripts/harness.py checkpoint --label migration-v0.1
python scripts/harness.py package --label migration-v0.1
```

2026-10-18起，checkpoint包含白名单源文件的实际字节、短状态和完整SHA清单，写入时复核每个文件；较早checkpoint通常只有清单和少量状态文件，不能称完整源码镜像。package从本次保存的字节生成可搬迁压缩包，排除虚拟环境、下载工具、缓存、模型数据、凭据目录和大运行产物，并带文件清单。原始ZIP、PDF、vendor及轻量报告会进入包；运行证据应在 docs/runs 内留下摘要与哈希，原始日志留 artifacts，本次最小回归的24份轻量日志另复制到 docs/runs/reference-smoke-logs，路径映射和SHA见 reference-smoke-log-index.json。JSON里的绝对命令/日志路径仅追溯旧运行，迁到新目录后应重跑make host/rtl产生当地完整日志；validate检查哈希自洽，不代替重跑，也不证明新主机工具可用。当前根 `.git` 是受保护的空目录，并非可用 Git 仓库；本次不改它，使用快照/哈希替代提交。之后在正常 Git 工作区导入时可建立提交历史。

本 harness 提供恢复和记录机制，不自行启动无限循环、自动部署、每天定时任务或保证聊天结束后继续运行。需要持续开发时直接从 resume 输出的下一任务继续。

用户提供的FPT经验包已原字节留档，采用边界见[工程技能采用说明](../engineering/FPT_SKILLS_ADOPTION.md)。继续使用本harness；昂贵运行先做实际工具小例并保存阶段产物，失败后区分原生/reader/验收并恢复最窄失效阶段。综合后的旧信号名可能只剩无驱动别名，观测点须按实际网表驱动核实；不能凭名字相同把它当有效物理信号。技能来源不增加权限，不引入FPGA route/板测或第二套项目状态文件。

## 当前功能回归入口（v0.2）

`make linear`执行12组不同合成参数的完整新DUT任务，`make linear-four-state`执行Icarus两任务，`make test`检查软件契约与运行器。`make rtl`仍是导入FPT参考回归，不应替代新DUT。候选格式和lanes固定在 `configs/linear-prototype.json`，正式量化尺度尚需真实模型评估；源码或候选配置修改后重跑相应任务并更新相对SHA绑定。

KWT源码和最佳checkpoint最小子集随包保存在 `vendor/kwt1-237e4097/`，可用 `python scripts/model/fetch_kwt.py` 离线复核。真实推理使用 `scripts/setup/bootstrap_kwt.sh` 的独立旧版Python/TF环境；不要将`.venv-kwt`本机路径写成跨主机依赖。精确上游rc1缺失和兼容2.4.0差异在DECISION记录。

`make linear-real`回放随包静音导出的真实12层权重，指定新的`--source-root`后仍要求所有源文件和向量哈希相同。它无需旧版TF；重新导出用`make setup-kwt && make export-kwt`。fixture的期望值只用于TB对照，正式驱动/综合/评测适配不得读取预计算答案。单条冒烟与验证集/官方精度各有独立任务，不能互相标PASS。

## 远端执行

本轮已核实服务器可密码登录；不存储密码。不复制本机 Ubuntu 工具到 Rocky/EL8 使用。远端先检查原生工具及资源，再创建例如 `~/projects/kwt1-migration/<run-id>/` 的独立目录。同步源码清单和输入哈希，编译最多2线程，将命令、PID、host、开始时间和日志位置写入运行记录；只能管理本项目自己启动的进程。不触碰旧FPT运行目录。


SRAM长测使用`*.command.json`持久化原生退出/超时/中断及PID启动身份。PID身份同时绑定boot ID和PID namespace；在另一个namespace看不到进程时返回UNKNOWN，不据此重复启动。优先轮询同一工具session；句柄失效时再做宿主机精确可执行路径/启动身份只读检查。缺最终退出码或suite标记的partial run一律未验收，保留原文件并另写recovery-observation，不把旧RUNNING文件当作存活证明。

当前checkpoint显式包含`reports/PPA_PRELIMINARY.md`和`tech/official_sram/README.md`；不递归打包未知官方工艺包或受限文件。官方资料到位后按许可和显式清单加入相应保存策略，不能默认报告已覆盖全部外部平台/库/数据。
