# 决策记录

当前日期：2026-10-15，Asia/Shanghai。这是本工程唯一当前决策记录；`vendor/fpt-r1/DECISIONS.md` 是原包历史。

## D001 — Accepted：本科第一前馈线性层

依据：用户提供赛题及复用包，包已明确本科范围。目标为99×64输入、64×256权重、256偏置，支持12层参数更新。先做好必做1–3项；完整Attention/GELU/第二线性层不进入首版关键路径。需求来源见需求追溯；用户变更组别时复议。

## D002 — Accepted：迁移基线与新设计分阶段交付

本次交付 `migration-v0.1`：环境、资产、运行入口、参考验证、harness、来源与缺项。原包本身没有新KWT硬件，不能把目录改名等同算子迁移。新软件/RTL闭环作为下一阶段，完成后独立命名版本。赶明天结果时保留最小检查，暂不以全量精度/综合阻塞文件迁移。

## D003 — Accepted：原始资产不可变，逐项复用

60个归档文件全部原样提取到 `vendor/fpt-r1/`，原ZIP/PDF保留。源映射及SHA在原包metadata和当前 `docs/runs/import-manifest.json`。不沿用旧因果/GQA/DDR/AMD约束；只借鉴控制、缓冲、数值方法与验证思路。需要改造的模块另存新src并记来源。FPT未提供统一LICENSE，保留原注释，不宣称已有开源授权。

## D004 — Accepted：项目内轻量工具，模型环境分层

Python3.12标准库、GCC/G++13.3、Icarus12.0、Verilator5.020用于本轮。仿真器从Ubuntu软件包提取至 `.tools/`，SHA固定；不改全局环境。旧KWT `237e4097` requirements指定 TensorFlow2.4.0rc1/NumPy1.19.5；后续为它单独建立兼容环境并锁定依赖，当前 `.venv` 不声称能跑真实KWT。依据：[指定版 requirements](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/requirements.txt)、[README环境说明](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/README.md)。

## D005 — Accepted：按证据推进，状态短、日志长

PROGRESS保存当前短状态，tasks保存依赖与证据SHA，DECISION记原因，artifacts保存原命令日志；每次里程碑留checkpoint。原始运行不覆盖，失败和修复分开。PASS分资产/主机/参考RTL/新RTL/真实精度/SoC/PPA；不得跨范围推广。

## D006 — Accepted：服务器按需使用

用户本轮授权SSH及提供登录信息；已只读验证连接和资源。首轮轻量测试在本地，后续重工作在独立远端项目目录执行。不得修改旧FPT活动任务；凭据不持久化。不因历史包内“不要连接服务器”的提示词否定当前用户授权。

## D007 — Proposed：新算子结构与数值

正式参赛数值配置、权重复用/双缓冲和lane数优化仍待真实精度及工艺证据。System Bus/NICE需取得平台接口再定。以下D008只确定可运行的功能候选，不代表正式数值/PPA冻结。

## D008 — Accepted：首版功能候选 fixed16_acc48_v1

为尽快形成完整算子闭环，使用16位X/W、40位bias、48位精确累加和输出，默认8lane。64项点积的合法范围足以由48位表示，MAC中间不截断；浮点到整数按显式2的幂尺度RNE后饱和。数据/权重/偏置均由硬件接收、计算并逐字输出，参考软件只生成期望值。以完整99×256输出、边界及回压/复位验证功能，真实KWT误差另验。详见 `docs/design/NUMERIC_CONTRACT.md` 与 `configs/linear-prototype.json`。

此选择可被真实误差/面积结果推翻，届时新增格式版本并重跑；不在同一报告中混用格式。内部同步数组目前为推断RAM，尚需映射指定16位SRAM宏。输出流接口待官方E203平台接入。

## D009 — Accepted：固定官方KWT子集进入迁移包

官方源码及best_weights固定完整提交 `237e4097afd4f6851e0b82f0a8d65c2dfe8eae30`，104文件共8,011,892字节，Git blob ID和SHA256复核。按原字节放入 `vendor/kwt1-237e4097/`，包含Apache-2.0许可证与原注释，清单在 `docs/runs/kwt-vendor-manifest.json`。不打包其余模型、训练日志和Speech Commands大数据；固定下载/离线复核入口是 `scripts/model/fetch_kwt.py`。

## D010 — Accepted：旧版推理功能环境明确标记差异

上游要求的TensorFlow2.4.0rc1在本次官方PyPI查询中不存在，未能安装。已在项目内隔离Python3.8.20、tensorflow-cpu2.4.0正式版、NumPy1.19.5、TensorFlow Addons0.12.1和protobuf3.20.3，用于checkpoint加载、张量核对及功能导出。实际全部依赖锁在 `env/requirements-kwt.lock`，重建命令为 `bash scripts/setup/bootstrap_kwt.sh`。

任何此环境的结果必须带版本差异和样本范围说明，不能称精确复现rc1的官方全量评估；正式精度冻结前需比较官方允许的环境与预处理。零波形静音只验证导出链，不作为训练标定/验证集替代。

## D011 — Proposed：三人20天并行推进与交接责任

2026-10-15用户要求依据三人能力和当前进展制定方向、职责与交接约束，具体分工由团队自行推进。建议A负责E203/驱动/集成及端到端测量，B负责现有核心/指定SRAM/综合PPA，C负责真实数据精度/位级验证/复现。以migration-v0.2为共同基线，D12目标补齐必做验收，D13–16有条件优化，D17–20冻结与交付；缺官方材料时继续无依赖工作并调整排期，不以临时模型冒充正式验收。计划中的D1–20为10月15日至11月3日的内部安排，不确认官方截止日。

详见 `docs/TEAM_PLAN_20_DAYS.md`。Proposed表示团队尚未实际认领姓名、确认材料到位与阶段承诺，不改变D007的正式数值/架构待验证状态，也不增加任务PASS。

## D012 — Proposed：冲奖候选围绕指定SRAM下的复用与计算—写回重叠

2026-10-15用户要求以本科国家一等奖为目标提出最终作品方案。建议在当前8路基线上形成正式E203/真实精度/工艺闭环，再评估2行×8列的16-MAC候选，用W广播降低任务内权重读取；采用行重排缓冲维持现有输出顺序，再用双缓冲重叠计算和写回。单行16列作为同MAC数对照，单/双结果缓冲比较重叠机制。不得将W读量推导当成整机能耗收益，不允许跨性能任务缓存参数获取正式收益。

候选尚未实现，数值正式配置仍待验证，面积/时序/能耗须由实际平台和指定宏决定。D12未取得资格基线则停止新增架构开发，D16未验证或无可信收益的候选不进入提交。详见 `docs/FINAL_WORK_PROPOSAL.md`；这是冲刺方向，不是奖项承诺或对当前PASS范围的扩大。
