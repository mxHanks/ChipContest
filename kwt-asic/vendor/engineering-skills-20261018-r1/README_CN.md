# FPT开发经验与可迁移技能包

日期：2026-10-18。用于下一个软件、RTL或嵌入式项目。内容来自FPT实际开发、失败和交接记录；保留可迁移方法，去掉原项目固定芯片、路径、线程、代理数和历史运行授权。

## 包里有什么

| 技能 | 何时用 |
|---|---|
| `engineering-continuity`（新） | 接续复杂项目、候选版本辨识、增量开发、验证和交接 |
| `diagnose-expensive-runs`（新） | 长构建/仿真/实验、进程归属、冻结输入、失败诊断、checkpoint复用 |
| `amd-fpga-flow`（原有，移植适配） | Vivado/Vitis工程与跨阶段一致性；不需要其他可选技能也能使用 |
| `fpga-change-evidence`（原有） | 明确区分功能、综合、物理、制品与硬件证据 |
| `causal-bypass-rtl-review`（原有） | 确实有bypass/skip/early-exit优化时审查协议、计数和恢复；普通矩阵乘不必触发 |

通用工作流和项目教训见 [WORKFLOWS_CN.md](WORKFLOWS_CN.md)。可直接用于新会话的提示词见 [START_NEXT_PROJECT_CN.md](START_NEXT_PROJECT_CN.md)。两个新技能分别带状态/决策/交接和运行/实验模板，按需取用。

## 迁移到新工作区

解压ZIP后，在本包根目录先校验：

```bash
python3 tools/transfer_skills.py verify
```

预览通用技能安装（项目路径换成实际新目录）：

```bash
python3 tools/transfer_skills.py install --project /path/to/new-project --profile general
```

执行安装：

```bash
python3 tools/transfer_skills.py install --project /path/to/new-project --profile general --apply
```

`general`安装两项新技能；`fpga`安装全部五项。工具要求目标项目目录已存在，写入目标的`.agents/skills/`；默认dry-run，不创建目录；已有同名技能完全一致时跳过，不一致时整批拒绝，不覆盖用户文件。它不创建Git仓库、不复制AGENTS或修改全局设置。Windows可用Python启动命令和带引号的目标路径。

也可以手动复制所需的`skills/技能名/`目录到新工程的`.agents/skills/`。当前官方说明该路径用于仓库技能发现；更新通常会自动检测，未出现时重启Codex。已有用户级同名技能不会被合并，避免重复安装。依据：[OpenAI官方技能文档](https://learn.chatgpt.com/docs/build-skills)。

安装后可显式要求：`使用 $engineering-continuity 接续这个工程`，或`使用 $diagnose-expensive-runs 分析这次长任务失败`。技能可按任务描述自动选用；新技能没有设置显式调用限制。

## 与前一个比赛复用包配合

将本包的`fpga`技能装到已解压的本科比赛工作区即可。原比赛源码复用包保持原SHA；技能另行安装，不重封旧包。比赛只要求综合时，不因导入技能增加route或上板任务。两套材料分别负责“复用什么代码”和“怎样可靠地推进开发”。

当前FPT的`.agents`目录受写保护，所以本次新技能保存在这份独立迁移包内，尚未安装到当前工程或全局目录。包完整性、安装正负检查和技能验证结果见包旁verification.json。模板仅为起点，不能代替新项目真实状态。
