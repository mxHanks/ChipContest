# 声算 FPT：KWT-1 本科比赛迁移工程

当前SRAM框架、十项审计回答和修改顺序见 [当前审计与计划](docs/SRAM_CURRENT_PLAN.md)；负责人可直接阅读 [修改与决策记录](docs/USER_CHANGELOG.md)。开发回归20阶段及12层CPU联调已通过；独立[参考网表ECO](docs/optimization/SRAM_REFERENCE_ECO.md)的最终12层零延迟回放完成，304128输出逐位一致，含恢复/背压和错误检查。原SDC下已覆盖setup/data hold/removal为正；48378标准输出的已知电容、转换时间/时钟检查通过。hold余量仅1.379ps；182条宏负载及1152宏输出驱动未知，正式工艺/功耗未验证，不能称完整150MHz达标。形式整体证明仍NOT_PROVEN，官方PPA继续BLOCKED。[FPT经验采用说明](docs/engineering/FPT_SKILLS_ADOPTION.md)解释实际复用方法与边界。

首版历史基线 **migration-v0.2**（下段描述首版时点，后续验收以PROGRESS为准）：已实现完整 `99×64 · 64×256 + bias` 的前馈线性层 RTL、位级软件模型、装载/输出流接口与回归。默认8lane、候选格式fixed16_acc48_v1；12组不同合成参数的304,128个输出逐位通过，Icarus四态补测也通过。实际模型精度、E203 集成与指定工艺 PPA 各自需要后续证据。实时状态见 [PROGRESS.md](PROGRESS.md)。

当前另有保留基线的双行16-MAC优化候选、真实validation开发精度及开放E203开发接入。SRAM重构新增独立存储接口、16位容量拼接、行为/FF/黑盒/官方Adapter入口；复现与证据边界见 [SRAM子系统](docs/SRAM_SUBSYSTEM.md)、[存储审计](docs/SRAM_AUDIT.md) 和 [初步PPA](reports/PPA_PRELIMINARY.md)。快速入口：`make test-memory`、`make test-linear`、`make test-soc`、`make synth-logic`；完整回归为 `make regress`。官方宏尚未取得，正式PPA仍为BLOCKED。

官方文件接收前可运行`make -f scripts/official-sram.mk inspect-official-sram SRAM_STAGE=simulation`。新[分阶段材料预检](docs/OFFICIAL_SRAM_INPUT_READINESS.md)区分功能模型、综合源与各PPA角色，当前空清单返回BLOCKED。文件核验通过也不设置旧官方后端READY；官方Adapter及原语/CPU回归还需实际接通并验收。

新增[原语/bank契约入口](docs/OFFICIAL_SRAM_CONTRACT_RUNNER.md)：`source env/activate.sh && python3 -B scripts/verify/run_official_sram_contract.py`。它消费simulation材料计划，当前缺包exit2/BLOCKED；显式开发资格化已验证8场景/23,177检查与15类非法请求拒绝。夹具不代表官方宏，核心/ICB/CPU及PPA仍需真实包后接通。

[覆写与复位门控补测](docs/SRAM_UPDATE_RESET_VALIDATION.md)：`source env/activate.sh && python3 -B scripts/verify/run_sram_update_reset.py --development-adapter`。当前8形状×3开发后端24场景/1080分组检查通过，三类私有错误准确检出；官方模型与PPA验收仍待材料。

[Adapter核心/ICB入口](docs/SRAM_ADAPTER_SYSTEM.md)已接通simulation源计划和同源原语前置，再跑BACKEND3完整计算/协议。开发资格化：14核心任务354816输出、四态ICB实际25348输出/86保持/1reset丢弃；真实宏、CPU/官方SoC及PPA仍待材料。

2026-10-17历史计划审计曾发现组合环和缺失SoC证据，原记录保留；10月18日已修接口并完成12层开发SoC、同源参考网表回放及有界参考时序修复。当前状态见上述审计与计划；[原框架与设计](docs/superpowers/specs/2026-10-17-sram-subsystem-design.md)、[原分阶段计划](docs/superpowers/plans/2026-10-17-sram-subsystem-plan.md)保留供追溯，不覆盖后续执行结果。

## 快速开始

当前机器已经安装项目内环境：

```bash
source env/activate.sh
python scripts/harness.py resume
make doctor
make host
make linear
make linear-four-state
make linear-real
make test
```

新 Ubuntu 24.04 x86_64 工作区先执行 `make setup`，需要网络和系统已有 Python3/venv、gcc/g++、make、dpkg-deb、apt-get；下载两个固定版本 Ubuntu 包到 `.tools/`，校验 SHA，不使用 sudo、不改全局环境。其他系统使用原生 Icarus/Verilator/C++ 后执行 `make doctor`。原始bundle工具和 harness 仅依赖 Python 标准库，主机C测试需要 GCC。详见 [env/README.md](env/README.md)。

## 目录

```text
AGENTS.md / PROGRESS.md / DECISION.md    工作约定、当前状态、决策
harness/tasks.json                     任务依赖和证据索引
configs/project.json                   固定赛题参数与待选设计项
docs/requirements/                     PDF摘录及需求追溯
docs/harness/                          长流程运行手册
docs/runs/                             随源码保留的轻量验证证据
vendor/fpt-r1/                         原样保留的60个导入文件
src/rtl/ / model/ / sim/                当前RTL候选、数值模型、仿真
soc/ / constraints/                    E203集成、宏和综合约束入口
scripts/setup/ / env/                  项目内工具安装与激活
scripts/env/ / scripts/verify/         侦察和分层验证
scripts/harness.py                     恢复、检查点、可迁移归档
data/                                 外部权重和数据约定
artifacts/runs/                        每次独立运行的命令、日志和结果
artifacts/checkpoints/ / releases/     上下文快照与源码发布包
```

根目录原 ZIP/PDF 保留；导入目录中的旧提示词只作为来源资料。不要修改原文件，也不要编译整个 vendor 目录；显式文件集负责隔离仿真mock与厂商包装器。已有 `.git` 是受保护空目录，不是可工作的Git仓库；本次以SHA清单和压缩快照保留版本，没有提交历史。

官方固定提交的104个推理源码/最佳checkpoint文件在 `vendor/kwt1-237e4097/`，含上游Apache-2.0许可证；清单与每文件SHA见 `docs/runs/kwt-vendor-manifest.json`。`python3 scripts/model/fetch_kwt.py` 可离线复核；丢失文件时 `make fetch-kwt` 从固定URL补齐。原FPT参考在独立的 `vendor/fpt-r1/`，两者不混编。

## 验证含义

| 命令 | 证明的范围 |
|---|---|
| `make verify` | 59个哈希记录、35个源文件、11个文件集及Python语法 |
| `make host` | 上述检查 + FPT有限BF16/FP32辅助函数和16例C快照一致性 |
| `make rtl` | 上述检查 + 默认5组参考RTL的7个场景 |
| `make linear` | 新DUT完整矩阵12组不同合成参数、逐位对照及回压/复位/连续任务 |
| `make linear-four-state` | 新DUT两组完整任务的Icarus四态补测 |
| `make linear-real` | 固定最佳checkpoint、单条静音的12层真实输入/参数，304,128输出逐位核对；无需TF重导出 |
| `make test` | 软件编码/数值/误差统计与运行器防假阳性自检 |
| `make harness` | 任务依赖、状态与证据文件SHA自洽 |
| `make checkpoint` / `make package` | 保存状态/源码清单，生成并复核可迁移归档 |

参考RTL与新RTL分别报告；以上功能通过没有给出E203、150MHz、面积或功耗结论。具体场景、工具版本和日志在 `docs/runs/` 及 `artifacts/runs/`。新算子设计、容量和周期含义见 [v0.2交接](docs/design/MIGRATION_V0_2.md)。

## 下一阶段

赛题要求本科实现 `99×64 · 64×256 + bias` 并轮换12层参数。完整要求、验证路径、估时见 [需求追溯](docs/requirements/UNDERGRAD_REQUIREMENTS.md) 与 [迁移计划](docs/MIGRATION_PLAN.md)。本版已经具备64维点积/完整矩阵功能和可重装参数接口；后续用指定权重、正确层输入和数据划分评估精度，组委会平台、库和SRAM资料到齐后接E203与综合。

旧KWT功能环境单独使用Python3.8.20：`bash scripts/setup/bootstrap_kwt.sh`。精确TensorFlow2.4.0rc1本次无法获取，当前采用CPU2.4.0正式版兼容环境并锁定全部依赖；其结果必须注明版本差异与样本范围，不能当作官方全量评估复现。

本版已完整恢复并逐值确认162个模型变量，导出各层正确位置的前馈输入，真实12层参数的RTL对照通过。单条静音样本最大层NRMSE为0.01951%，所有层量化裁剪均为0；正式验证集/600条精度尚未评估。已验证的静音回归向量在 `sim/vectors/kwt-silence-v1/`，可离线回放；`make setup-kwt && make export-kwt`从checkpoint重新生成新导出目录。

运行记录、恢复和源码变化后PASS失效机制见 [RUNBOOK](docs/harness/RUNBOOK.md)。本轮已实现可运行功能首版，完整本地参赛验收仍需真实数据和官方平台/工艺材料。


[Adapter CPU入口](docs/SRAM_ADAPTER_SOC.md)已完成开放E203开发12层回归：304128结果、608256写响应及abort/reset恢复通过，相同形状/固件的开发窗口同为21261300周期，但旧语音与新静音输入不同，非隔离后端A/B。执行`python3 -B scripts/verify/run_sram_adapter_soc.py --development-adapter --system-report <同输入核心及ICB报告>`；真实包模式去掉开发选项并传`--manifest`。缺包/坏前置不启动HDL，原CPU/固件/RTL保留；平台既有告警、两态仿真与非正式计时边界见说明。


跨目录重建CPU链使用[新工作区重建说明](docs/SRAM_CPU_REBUILD.md)和`run_sram_adapter_soc_v2.py`，显式传`--baseline-report`、`--platform`及必要的编译工具路径。平台136份源按相对路径/SHA核验，不搬改旧PASS路径。`--preflight-only`只接受输入与前置，CPU仍NOT_RUN；完整新运行结果见PROGRESS。旧v1入口及其历史证据保持冻结。


最新开发交接包：[CPU v2源码包](artifacts/releases/20261019T012341Z-3268eb-sram-development-cpu-v2-20261019/sram-development-cpu-v2-20261019.tar.gz)，666文件；逐文件SHA、独立目录恢复及324主机检查/静态入口通过，收据`docs/runs/portable-cpu-release-20261019.json`。工具、平台、数据集和原始run不随源码打包；完整CPU需接收者按重建说明生成本机新证据，官方SRAM/平台/PPA仍等待材料。
