# 当前进度

更新时间：2026-10-15，Asia/Shanghai。当前交付：**migration-v0.2 可运行迁移首版**。已从资料搬迁推进到新前馈RTL、位级模型、真实checkpoint输入导出和完整矩阵回放。

## 已完成与证据

| 范围 | 状态 | 可复核结果/证据 |
|---|---|---|
| 赛题、目录、FPT来源 | PASS | 31项页码追溯；60个导入文件字节一致；docs/runs/import-manifest.json |
| 项目内环境与harness | PASS | Icarus12/Verilator5.020/Python3.12；旧模型独立Python3.8.20/TFcpu2.4.0；docs/runs/environment-v0.2.json、legacy-environment.json |
| 官方固定源码/最佳权重 | PASS | 完整提交237e4097afd4f6851e0b82f0a8d65c2dfe8eae30，104文件8,011,892字节；docs/runs/kwt-vendor-manifest.json |
| 候选软件/新RTL功能 | PASS | fixed16_acc48_v1、默认8lane、完整99×64×256+b；12组合成任务304,128输出逐位一致；docs/runs/linear-verilator/result.json |
| 新RTL四态 | PASS | Icarus两任务50,688输出、复位/回压/换参等；docs/runs/linear-iverilog/result.json |
| 实际模型恢复及导出 | PASS | 162变量逐值等于checkpoint；12层正确位置输入；docs/runs/kwt-silence-export.json |
| 真实12层权重静音RTL | PASS | 304,128输出逐位一致，最新回放5.157秒；docs/runs/linear-real/result.json |
| 静音单样本数值 | PASS（仅冒烟） | 最大层NRMSE=0.0195108%，各层X/W/bias裁剪均0；尺度由权重及LN参数选取，不按样本调参 |
| 工具与数值自检 | PASS | 57项；docs/runs/v0.2-tool-checks.json、tests-v0.2.log |
| v0.2换目录复现 | PASS | 新目录离线重建工具、核对官方源、合成/真实权重RTL及57项自检；13.999秒；docs/runs/v0.2-relocation-check.json |
| 正式数据精度/E203/PPA | NOT_RUN / BLOCKED | 验证集、官方平台、库和SRAM宏仍需补齐 |

源码改动会使任务图中的旧PASS失效；状态和证据SHA在harness/tasks.json。当前原始日志在artifacts，轻量副本和可移植静音fixture已纳入源码。旧v0.1和旧失败记录保留，不覆盖新证据。

## 重要边界

TensorFlow精确2.4.0rc1本次无法取得，2.4.0正式版为显式兼容环境，未称完整复现官方评估。单条零波形不代表验证集/600样本3%达标。核心周期不是比赛端到端性能；SRAM目前为同步推断数组，E203、指定宏/工艺综合和150MHz/面积/功耗尚未验收。服务器已核实可登录，本版回归均在本地完成，凭据未保存。

## 团队推进安排

三人剩余20天的建议分工、阶段目标和交接约束见 [TEAM_PLAN_20_DAYS.md](docs/TEAM_PLAN_20_DAYS.md)：A主责E203/驱动/端到端集成，B主责RTL/指定SRAM/综合PPA，C主责真实数据精度/位级验证/复现。内部排期2026-10-15至11-03，不代表官方截止日期；仅新增规划，现有验收状态不变。

冲奖最终作品建议见 [FINAL_WORK_PROPOSAL.md](docs/FINAL_WORK_PROPOSAL.md)：以正式SoC/精度/PPA合格基线为前提，评估双行权重复用和保持行优先的计算—写回重叠，设置同16个MAC的对照。方案及49.5%内部W读量减少均为待验证设计/推导，未新增RTL或成绩。

工程图册已绘制：[五页图册与编辑入口](docs/diagrams/README.md)，首页为项目工程总流程，随后展开三人交接、系统数据通路、候选微架构和验证交付闭环；提供PDF、SVG、PNG及可编辑draw.io。已逐页检查版面、箭头、状态边界和文件完整性，图中明确区分现有8路基线、正式待验收与优化候选；图册检查不增加硬件验收PASS。

## 继续工作（最多五项）

1. 运行make linear-real复现当前真实12层静音回放；改代码后运行相关回归并刷新证据。
2. 取得Speech Commands V2固定划分，用训练集标定/验证集评估，冻结候选尺度与正式环境。
3. 提供组委会E203/SDK/接口和内存地址图，完成总线或NICE、驱动及SoC联调。
4. 提供指定标准单元库与SRAM模型，完成映射、综合前后功能、150MHz/面积和总窗口性能/功耗。
5. 在同一配置及真实数据上比较lane数、权重复用、装载/计算重叠的收益。

恢复入口：source env/activate.sh && python scripts/harness.py resume。快速使用：make linear、make linear-four-state、make linear-real、make test。迁移步骤见README，设计说明见docs/design/MIGRATION_V0_2.md；源码检查点/归档位于artifacts/checkpoints/、artifacts/releases/。
