# AI engine 优化：基准、验证工具与选择依据

查阅日期：2026-10-15（Asia/Shanghai）。本文是优化执行依据；工具能力来自一手文档，工程现状来自当前源码与报告。工具安装/运行状态以实际新日志为准，本文不新增功能、SoC 或 PPA 的 PASS。

## 1. 先固定真正影响评分的基准

主 benchmark 是赛题指定 `ARM-software/keyword-transformer@237e4097afd4f6851e0b82f0a8d65c2dfe8eae30` 的 KWT-1 `best_weights`，Speech Commands V2、12 个真实层任务，每任务 `Y[99,256]=X[99,64]×W[64,256]+b[256]`。当前固定源在 `vendor/kwt1-237e4097/`，复核入口 `python3 scripts/model/fetch_kwt.py`。[固定官方源](https://github.com/ARM-software/keyword-transformer/tree/237e4097)

**来源中的维度陷阱：**同提交 README 表格将 KWT-1 的 mlp-dim 写为 128，但其实际 `flags.txt` 为 256；本项目以赛题、实际 flags 和 checkpoint 张量一致的 `64→256` 为准，不照抄 README 表格。[官方 flags](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/models_data_v2_12_labels/kwt1/flags.txt)

| 基准层级 | 数据与用途 | 通过能够证明什么 |
|---|---|---|
| B0 整数定向/随机 | 极值、抵消、零输入、非零偏置、首末 k、99 行、12 次换参；固定 seed | 精确算术、流水标签与协议正确；不代表真实精度 |
| B1 真实权重冒烟 | 已有 `sim/vectors/kwt-silence-v1`，12 层、304,128 个输出 | 导出和硬件链路可重复；单条静音不能代表语音分布或典型功耗 |
| B2 开发精度/活动 | 固定训练标定清单；固定验证样本，覆盖十个关键词、unknown、silence | 层级 NRMSE、裁剪、真实活动趋势；先小样本调试，再完成验证划分评估 |
| B3 完整系统性能 | 同一冻结配置，12 层分别取固定真实输入/各自参数，每任务清空缓存 | E203 装载至最后写回的总周期、逐任务误差与同窗口功耗 |
| B4 正式验收 | 组委会选取的 600 条样本及正式性能任务 | 正式成绩；本地样本集不能提前宣称替代这一关 |

MLPerf Tiny 的 KWS 使用 DS-CNN，与本题 KWT 第一线性层的形状、量化和计时边界不同。可借鉴其固定质量门槛、可复现测量及同时报告时延/能耗的方法，不能用其模型、准确率或跑分替代比赛 benchmark。[MLCommons 官方介绍](https://mlcommons.org/2025/09/mlperf-tiny-v1-3-tech/)、[规则](https://github.com/mlcommons/tiny/blob/master/benchmark/MLPerfTiny_Rules.adoc)

## 2. 数据与精度约束

- 下载源由固定上游 README 指向 [`speech_commands_v0.02.tar.gz`](https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz)；记录归档 SHA256、解压文件清单与采样脚本版本。[上游下载及环境说明](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/README.md)
- 沿用固定源码 `which_set`：文件名去掉 `_nohash_` 后缀再哈希，同一说话人的相关录音保持同划分；flags 的 validation/testing 各为 10%。unknown/silence 的构造、随机种子和标签顺序也沿用代码，记录最终样本 manifest；不要直接换成另一框架默认划分。[固定数据代码](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/kws_streaming/data/input_data.py)
- 训练划分仅作无梯度标定；验证划分用于调试与比较；测试划分不用于选择量化、架构或阈值。不重训、微调、蒸馏或改模型结构。
- 每层 X 从该层 Attention、残差、第一处 LayerNorm 之后提取，12 层各用自己的 X/W/b。推理关闭随机增强和 Dropout；固定预处理、TF/NumPy 版本及样本身份。
- 已有兼容环境是 TF CPU 2.4.0，上游要求 2.4.0rc1；保持差异记录并核对官方允许环境，不能将兼容导出称为完整官方环境复现。
- 每层累计全部样本全部元素的平方误差和参考平方和：`NRMSE_l=sqrt(SSE_l/N_l)/max(sqrt(REFSQ_l/N_l),1e-8)`；12 层最大值 ≤3%，且每个性能任务单独 ≤3%。另外要求解码结果有限及 RTL 与软件位级模型逐位一致。
- 比较架构时先保持 `fixed16_acc48_v1` 不变；若减位宽、改截断或舍入，必须另建格式版本并重新通过精度关。不得混用两个格式的延迟与功耗。

赛题规则与印刷页码见 [需求追溯](../requirements/UNDERGRAD_REQUIREMENTS.md)：数据/精度 U14–U23，计时及 PPA U24–U30。

## 3. 工具组合：先复用已有闭环，再按缺口补充

| 工具及文档版本 | 在本项目中的具体用途 | 适用边界 |
|---|---|---|
| Verilator，本地 5.020；查阅固定 v5.020 文档 | `--lint-only` 检查位宽/驱动；`--assert`、覆盖率、VCD；现有大矩阵回归 | 仿真耗时不是芯片周期；2-state 模型不能代替四态复位检查；不要为提速关闭断言。[运行与覆盖](https://raw.githubusercontent.com/verilator/verilator/v5.020/docs/guide/simulating.rst)、[命令](https://raw.githubusercontent.com/verilator/verilator/v5.020/docs/guide/exe_verilator.rst) |
| Icarus，本地 12.0；查阅在线命令参考 | `-g2012` 显式文件集、`vvp` 四态回归，重点测流水未初始化、复位和回压 | 在线文档含新版本选项；只使用本地帮助确认支持的参数。门级时序能力不代替官方 STA。[官方命令文档](https://steveicarus.github.io/iverilog/usage/command_line_flags.html) |
| cocotb，可选；固定查阅 2.0.0 | 需要复杂总线随机激励时，用 Python scoreboard 对接现有数值模型 | 当前 SV TB 已可用，不为引入框架重写闭环；安装前核对仿真器兼容版本。[官方 2.0 文档](https://docs.cocotb.org/en/v2.0.0/) |
| Yosys + ABC；查阅 Yosys 0.70 文档 | 保留 SRAM 宏边界的结构综合、乘法器/加法器/寄存器/多路器统计；有库时作 `dfflibmap`、`abc -liberty` | 泛化门数不是 mm²；不得把 SRAM 全展开成 FF 的结果当正式面积；实际工具版本另记。[技术映射文档](https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_passes_techmap.html) |
| OpenSTA；查阅官方 master README | 指定 Liberty + 映射网表 + 有效 SDC 查最大/最小路径、约束覆盖、slack；定位乘法/加法/寻址/扇出 | 需要真实库、角、负载、互连条件和 SRAM 时序弧；工具可运行不等于 150 MHz 合格。[官方仓库](https://github.com/parallaxsw/OpenSTA) |
| SBY/SymbiYosys；查阅在线 reference | 对局部控制证明回压稳定、输出不丢不重、计数界限、reset 清 valid、first/last 标签对齐 | BMC 到有限深度不是无限证明；活性要求明确环境公平性；超时必须记 UNKNOWN。[官方参考](https://yosyshq.readthedocs.io/projects/sby/en/latest/reference.html) |
| EQY / Yosys equivalence；查阅 Yosys 0.70 | 同周期 RTL/综合网表等价；局部 MAC 的符号位/截断重写等价 | 插入流水会改变延迟，须事务级对齐或证明局部转换；不能直接比较同周期输出。不可忽略未知宏而宣称全设计证明。[EQY](https://github.com/YosysHQ/eqy)、[等价命令](https://yosyshq.readthedocs.io/projects/yosys/en/stable/cmd/index_passes_equiv.html) |

**正式验收优先使用组委会指定的综合/时序/功耗流程和库。** 目前未取得完整指定材料；开源工具用于提前发现结构问题和可复核的代理比较，不给指定工艺的面积、功耗保证。`SBY`、`EQY`、OpenSTA 等新增工具是否可用须重新探测，本文没有安装它们。

功耗流程：同一冻结网表在完整任务窗口记录 VCD/SAIF，核对层级映射和活动覆盖，再输入官方功耗工具；库提供内部/开关/漏电模型，SRAM 模型提供读/写/待机条件。OpenSTA 当前官方仓库列出 VCD/SAIF 输入，可作为辅助分析，但必须检查所用版本的实现和报告范围。无延迟 RTL VCD 会遗漏门内毛刺；波形 toggle 数、宏读使能次数均只能作活动代理，不能直接换算 mW。[OpenSTA 输入格式](https://raw.githubusercontent.com/parallaxsw/OpenSTA/master/README.md)

## 4. 可立即执行的对照矩阵

每次只改一个主要因素；下表是建议实验，不表示所有版本已经实现。全版本用同一输入/格式/总线等待序列/复位规则和 150 MHz 目标，编译至多 2 线程，重型综合一次一项。

| 实验 | 相对基线改动 | 主假设与必须新增检查 |
|---|---|---|
| V0 | 当前单行 ×8 lane，组合乘法接累加 | 记录基线算术、RAM 与控制面积/延迟；完整周期分解 |
| V1 | V0 只增加乘积流水寄存器 | 分离乘法和累加组合路径；同步延迟 valid/first/last/bias，检查首末 k 和 drain；比较 FF/时钟负载增加 |
| V2 | V0 只改 16 lane | 测翻倍 MAC 对总周期的收益；检查 W bank/输出 mux/负载；统计真实 SRAM 宏取整成本 |
| V3 | V2 加同样乘积流水 | 与 V1 比 lane，与 V2 比流水；保持 initiation interval=1，记录流水填充/排空损失 |
| V4 | 选定 V0–V3 后，仅在需要时读 bias | 当前每个点积重复读 64 次相同偏置；候选每 tile 首次读取并保持，核对读延迟和数据稳定；确认读使能映射到宏 CE |
| V5 | 选定计算核心，加入输出缓冲并重叠下一 tile | 查写回拥塞是否主瓶颈；核对容量、回压、顺序与最后提交；收益须覆盖新增缓冲/接口功耗面积 |
| V6，后续 | 与单行16 lane同16 MAC的双行 ×8 lane | 比较 W 广播复用收益，覆盖第99行尾行和行优先重排；同MAC数消除“只增加资源”的混淆 |

流水化主要服务时序；比赛固定 150 MHz 时，若基线已满足时序且周期不变，它不会自动提高吞吐，反而可能增加填充周期及寄存器功耗。先用路径报告确认瓶颈，再决定插在哪里。

宏配置按实际实例统计：W 共16,384个16位字；8 bank时每 bank 2,048字，可研究两个1,024深度宏或一个4,096深度宏，16 bank时每 bank 1,024字。最便宜组合取决于指定宏面积/端口/时序，不能只按有效bit数排名。偏置40位和输出48位必须计入16位宏拼宽、深度取整、译码与读选择逻辑；不要漏掉稀疏小bank的浪费。

## 5. 指标、瓶颈定位与选择门槛

记录至少：`config/source/data/tool/lib hashes`、完整命令/退出码、位一致结果、逐层及逐任务NRMSE、总周期、load/compute/drain/output-wait/CPU-bus分类、MAC有效周期、X/W/B/Y读写量、标准单元/宏面积、关键路径/slack、功耗分项与活动覆盖。计数分类若有重叠必须说明，不能把重叠窗口直接相加。

- 正式 `T_total` 从每任务数据/参数开始装载至全部结果实际写回，包含 CPU 调度、总线等待和参数装载；任务间 TB 复位时间排除。核心 `done` 必须经过写回完成确认，不能提前停表。
- `throughput=N_tasks/T_total`；`energy_per_task=P_average*T_total/N_tasks`。面积预算只计新增，但功耗包括 E203、加速器、互连和 SRAM 的动态与静态，未覆盖模块不可按零处理。
- `A_incremental=A_accelerator_logic+A_interface_logic+ΣA_internal_SRAM_macro`，避免漏项/重复；新增打包、缓冲、控制、时钟门控单元都计入。复用 E203/512 KiB共享SRAM/固定总线外设单列，不计增量预算。保守设计目标 `<2.25 mm²`，有效 150 MHz SDC 约为 6.667 ns。
- 资格通过后本科效率分为 `8·T/T_best + 8·E_best/E + 4·A_best/A`；对手最优值未知，保留吞吐/能耗/面积 Pareto 候选，不宣称某配置必得满分。功能40、SoC/综合/复现20、自主创新20也必须完整交付。[本地赛题追溯](../requirements/UNDERGRAD_REQUIREMENTS.md)

| 观测到的瓶颈 | 需要的证据 | 下一步优先试验 |
|---|---|---|
| 乘法→累加路径违例 | 指定角最差路径、寄存器起止、cell/net延迟占比 | 乘积流水；如果累加反馈本身仍违例，再研究加法结构/交错部分和，并证明位一致 |
| 地址/读选择/广播路径违例 | memory输出、mux深度、fanout报告 | 预译码、地址寄存、分bank，控制高扇出；不盲目加MAC |
| MAC空闲而加载/写回占多数 | 完整窗口周期分类、总线握手与带宽 | 批量驱动、搬运/计算重叠、输出缓冲；先证明接口约束允许 |
| 面积主要在RAM/填充 | 逐宏类型/数量/利用率+外围单元面积 | 宏组合和bank重排、共享小存储；不能删除必要存储或用黑盒零面积 |
| 功耗主要在时钟/无效访存 | 真实活动下功耗分项、宏读写/CE、有效MAC率 | bias首读保持、寄存器CE、操作数隔离；工艺允许时用合法ICG，禁止手写组合门控时钟 |

当前最快复现入口：`source env/activate.sh`，依次运行 `make linear`、`make linear-four-state`、`make linear-real`、`make test`；新增参数化实验使用实际 runner 的 `--help` 和新报告记录，不借旧 PASS。最终配置必须同时通过真实精度、位一致、指定 SRAM/工艺、150 MHz、增量面积和同窗口功耗关。
