# 决策记录

当前日期：2026-10-18，Asia/Shanghai。这是本工程唯一当前决策记录；`vendor/fpt-r1/DECISIONS.md` 是原包历史。

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

## D013 — Accepted：以独立候选和同输入实测开展核心优化

保留原迁移RTL；新增opt的bias首读保持/可选乘积寄存级，以及banked的显式独立存储bank。固定16/16/40/48数值语义，比较8/16路和PIPE_MUL=0/1。当前16组功能回归、10组结构综合已有绑定证据，见`docs/optimization/OPTIMIZATION_V1.md`。Yosys发现原二维数组会合并为多端口存储，banked已消除此结构问题；仍未完成指定宏映射。

Accept的是实验方法与独立候选，正式架构仍为Proposed：流水在统一频率下多排空周期，必须由指定工艺时序及完整窗口能耗决定保留与否。逻辑读量、结构单元数不等于mW/mm²；面积必须同时统计核心、新增接口、内部宏，项目目标严格小于2.25 mm²。正式平台和工艺缺项继续明确标记，不以通用综合代替比赛验收。

## D014 — Accepted：双行复用以后台串行结果写及同MAC对照验证

新增独立rowpair候选，2行×8列共16MAC，41位内部精确累加并符号扩展到原48位接口。采用16项快照和后台每拍单字写，让下一tile计算与结果转存重叠；单/双buffer、乘积流水开/关四种组合均验证。18组回归与4组结构综合证据见docs/runs/optimization-v2；双buffer流水108,299核心周期，相比同16MAC单行流水减少16.62%。选择串行后台写的依据是指定最浅128字宏下，16路浅bank并行存储会造成结果容量浪费。

接受的是独立实验和精确算术实现，正式架构仍待指定库PPA与SoC。单buffer双行较单行16列慢，W读下降不能单独当效率提升；X读、新增结果RAM活动和快照/队列开销必须一并核算。内部41位证明对全部合法16位X/W、40位bias及0–64项部分和成立，不基于样本截断。

## D015 — Accepted：使用固定原版采样的完整validation作开发数值证据

已按固定源码AudioProcessor的整体随机流建立划分，保存glob枚举和最终validation清单；4,445样本、12层在同一固定图批处理，首样本逐位对照规范Python整数模型，逐样本误差平方和重新聚合。silence按原版get_data返回全零，不能解码占位的训练WAV。尺度仍由权重/LN参数上界选取，不以测试集调参。

最大层NRMSE0.0132799%、最差样本层0.0195401%、零裁剪，证据见docs/runs/optimization-v1/validation-full.json。只接受开发精度PASS，保留TF2.4.0兼容替代的限制；官方600任务、指定环境和最终数值冻结尚未完成。后续位宽优化另立候选，并按精度扣分与实际PPA共同选择，不能只看3%合格线。

## D016 — Accepted：队友 ChipContest/E203 融合采用独立适配层

2026-10-17 已读取并按 quickstart 运行队友 `ChipContest`（30e737ca）及 E203 Fork（35e7c960）。原 E203 ADD 测试通过；原 Chisel 回归为10成功/1失败，失败来自 `WeightBankArrayTest` 未清 `loadWen` 的测试激励。融合副本修复该激励并增加真实 KWT 12层回放，13项测试、304,128个signed48输出、回压和复位边界通过。原仓库不原地修改。

采用独立 `kwt_icb_slave`，不把业务FSM塞进E203核心；o15开发地址0x10042000/4KiB，输入staging、48位结果LO/HI、sticky状态和WRITEBACK_ACK均固定在 `docs/integration/ICB_CONTRACT.md`。使用 `kwt_linear_engine_rowpair` 和开发512KiB行为共享模型完成1个任务的CPU装载、启动、读出和完整写回：25,344输出，窗口1,670,319周期，PASS marker。该结果是开放Fork开发平台证据，不是组委会E203、真实SRAM或正式PPA证据。

ChipContest的Nangate45 Liberty仅用于公开参考库对照；`area_eval.sh`在Yosys0.33 ABC阶段超时，且无SDC/SRAM宏/功耗。历史2.1596mm²日志使用旧RTL并把存储展开为DFF/MUX，不能迁移成比赛面积结论。官方器件仍未取得，M5保持BLOCKED。

## D017 — Proposed：先收口存储隔离与接口证据，再推进时序优化

2026-10-17用户明确要求先计划模式核对框架和审计。采用保留原rowpair/adapter、完善现有独立SRAM候选的增量方案；一拍1RW契约不改，官方Adapter缺失时拒绝，72片只是容量模板。当前单元及76任务核心证据可复核，不能迁为新12任务SoC或正式PPA通过。

优先修候选ICB的request_ok/start_valid/load_ready结构组合环，补协议/复位/错误恢复，再生成当前脚本含接口网表及局部STA。旧局部setup/hold均FAIL，高扇出控制有实证，先测映射缓冲再考虑最小RTL优化。新SoC长测缺最终结果，且原TB计时/结束边沿有缺口；旧开发单任务周期不作为正式全窗口评分数据。

设计及执行计划：`docs/superpowers/specs/2026-10-17-sram-subsystem-design.md`、`docs/superpowers/plans/2026-10-17-sram-subsystem-plan.md`。依据：`docs/runs/sram-plan-audit-20261017.json`及原生日志。本轮只新增/更新审计计划和状态文档，没有实施这些修复；Proposed不表示用户已批准最终架构或新结果已经产生。根目录无有效Git，继续使用SHA checkpoint，不虚称已commit。


## D018 — Accepted：以当前同源证据更新状态，保留历史计划和失败

2026-10-18复核确认：ICB解环/双后端协议、bank未知使能检查、67单元案例、独立核心18阶段和含接口无缓冲映射已有完整原生证据，绑定SHA一致。10月17日计划中的“尚未修复/未完成汇总”不再代表当前状态；旧文件作为历史保留，不重复启动已验证实验。当前计划索引改为`docs/superpowers/plans/2026-10-18-sram-remaining-plan.md`，给负责人看的记录为`docs/USER_CHANGELOG.md`。

局部STA工具status=PASS只表示流程完成，setup/hold实测均FAIL；ABC exit0也可能因内部命令失败而无输出。接受必须同时核对真实退出、诊断、完整标记、产物和SHA。核心PASS不扩展为SoC或正式PPA，原源文件和失败记录均保留。

## D019 — Proposed：下一批先接通SoC验收，再做受控映射优化

依据当前实际源码，新SoC validator及恢复固件尚未被main接入，新TB缺失；先补posedge响应计数、准确开发窗口、soft abort/外部reset和完整重新装载，再2任务/12层。参考ABC仅在map与buffer间补cleanup并验证实际全网；此修复目前只有最小fixture证据，不能先称全网或时序通过。

保持20bank和现有一拍同步契约，不同时改MAC、精度、缓存或E203核心；后端源集/持久证据实际入口统一后再最终审查。官方宏若时序不同再集中适配并重验。该条是当前修改计划，不表示剩余工作已执行、最终微架构已冻结或正式PPA已接受。


## D020 — Accepted：SoC验收绑定实际响应、恢复和运行前产物

新候选SoC使用独立TB/恢复固件。完成必须由posedge实际响应消费证明，统计全部输出写响应、ACK和最终邮箱；窗口从CPU任务释放开始但明确排除TB backdoor预装载。CPU soft abort与在途外部reset真实执行，中断epoch不计入正常任务。两任务已通过；首个12层run缺终态保持未验收，新的总入口继续执行，不能合并partial结果凑PASS。

源码/向量及ELF/BIN/HEX/simulation在消费前记录SHA，结束重新检查；总回归核对请求配置及每条原生命令/设计计数。PID身份包含namespace，不据另一sandbox的不可见PID判停；中断只清理本任务及已确认身份的派生进程。

## D021 — Accepted：参考setup改善与hold/removal失败分开判定

同RTL/库/SDC下，ABC map后加cleanup并使用buffer/upsize/dnsize，实际全网映射通过；标准逻辑面积0.056997416mm²，覆盖setup最差+4.652084ns。data hold=-0.013133ns、内部soft_reset removal=-0.255385ns仍FAIL，不新增例外或改uncertainty掩盖。官方宏边界仍未建模，不声称完整150MHz或总面积达标。

后续同步clear/最小延迟修复仅是候选，不在本阶段同时重写MAC或改变一拍接口。参考诊断见`docs/optimization/SRAM_TIMING_ANALYSIS.md`，官方PPA继续BLOCKED。


## D022 — Accepted：纠正参考互连假设，保留未证明的综合网表结论

电气复核确认Nangate45库默认5K_hvratio_1_1 wire load实际被OpenSTA采用；旧pin-only/NONE元数据错误。脚本改为显式绑定原模型并记录，重跑时序数值未变；不改原报告、不移除负载获取PASS。175项主机检查通过，真实12层SoC总入口20阶段已完成。

标准逻辑共同宏切口证明两次120秒均未完整接受，保留NOT_PROVEN，下一步切换有效信号感知/门级功能回放，不以RTL回归或局部等价点代替综合后功能。正式PPA仍因官方材料缺失BLOCKED，参考min检查仍FAIL，不能宣布全项目完成。

## D023 — Proposed：以当前框架收口门级功能，再分离处理最小延迟

用户要求先完成框架审计和修改计划。当前计划入口改为`docs/SRAM_CURRENT_PLAN.md`；保留原计划、已接受功能以及失败。20bank/一拍1RW/数值/ICB契约继续复用，不同时重写MAC、缓存、E203或Golden。

最新门级尝试编译原生exit0，但UNOPTFLAT导致验收FAIL、仿真NOT_RUN；实际按位结构切开DFF/同步宏后无环，报警对应`y_snapshot`符号扩展别名。计划先以最小fixture确认表示/调度问题，再修TB采样/未知值/末响应及恢复覆盖，运行1层和12层同源回放；结构无环不等于功能证明。随后才根据真实data hold/removal尝试最小参考修复，保持SDC；官方接入依赖真实包。

本轮178项主机测试通过，只新增审计/计划和记录，没有实施上述RTL/门级修复。Proposed表示实施方案，不意味着正式架构冻结或结果已PASS。依据`docs/runs/sram-framework-audit-20261018.json`。

## D024 — Accepted：按项目边界复用FPT工程技能，不继承历史结论

用户提供`FPT_ENGINEERING_SKILLS_20261018_r1.zip`和`WORKFLOWS_CN.md`并要求学习复用。38文件/37内置摘要、CRC和源目录字节均核验，原样留档于`vendor/engineering-skills-20261018-r1/`。采用engineering-continuity的增量接续、diagnose-expensive-runs的实际小探针/窄恢复、fpga-change-evidence的来源链与分级结论；ASIC继续沿用当前harness、SDC、标准单元和SRAM口径。causal审查仅用于真实工作抑制路径，AMD FPGA工具流程不进入当前ASIC实施。

实际应用：先用三版小例核定split_var，再用四态21例验证检查器；昂贵全网失败后用同TB双RTL小回放与实际网表驱动定位，不重复形式超时或直接重写核心。资料导入不新增设计PASS，也不解除官方材料阻塞。未执行包内安装、不写.agents或全局目录。详情`docs/engineering/FPT_SKILLS_ADOPTION.md`，原生校验`docs/runs/fpt-engineering-skills-import-20261018.json`。

## D025 — Accepted：综合网表的观测点必须有实际驱动

首次有split_var的全网回放在恢复通过后，因TB观察`mapped_dut.engine_y_ready`而失败。实际mapped.json显示该名字只剩bit49604无驱动别名，功能网络已优化到其他连接；同TB两个RTL完整1任务通过，排除了原始握手假设的普遍失败。

保留原网表和失败记录，改为观察实际保留的`rsp_pop_y`触发器、外部响应握手及`output_count`真实变更；所有被TB使用的mapped状态先核驱动。不能通过强驱动遗留别名、修改Golden或禁用有效计数获得PASS。该决定修复观测方法，尚不代表下一次网表回放已通过；证据`artifacts/diagnostics/20261018-mapped-pop-timing/observability.json`与`rtl-pair/result.json`。

## D026 — Accepted：门级功能按场景接受，窄reader恢复不重做计算

真实1层、12层参考标准单元零延迟回放通过，12层304128输出与恢复/错误/末响应检查完整；私有Golden单bit负例在准确位置拒绝。接受的是同参考Liberty/同网表/共同逻辑1RW模型的所测功能，不是所有输入形式证明、全网四态或官方宏/150MHz结论。

初次复用在仿真前因bytes/size_bytes元数据差异被拒绝。生产脚本及失败记录保持原样；独立reader只规范等值长度键，并核相对路径别名指同文件，其余mandatory source、原生构建/探针、模型recipe、binary、SHA全部保留。经独立只读审查后复用同一binary完成12层，不重复综合/编译。索引`docs/runs/sram-mapped-functional-20261018.json`，最终192主机检查及静态入口通过。

## D027 — Proposed：电气修复后仍负，下一步优先定点最小延迟候选

独立宏切口视图将reset驱动从BUF_X1改BUF_X8/X16，原143负载、SDC和wire-load保持，输出电容回到新驱动上限、RN slew从0.845563降至0.108889/0.056443ns；removal改善但仍-0.095160/-0.069030ns，data hold仍-0.013133ns。这两份仅诊断，不晋升完整候选；production RTL/原mapped结果未改。

下一步在独立完整保宏网表评估合法定点buffer/分支树及data-hold修复，保存中间身份并重新功能/STA验收；不靠继续增驱动、降低uncertainty或加例外获取PASS。同步clear涉及软件abort逐拍副作用，作为更高成本备选。依据`docs/optimization/SRAM_MIN_DELAY_OPTIONS.md`及两份reset-reference报告；官方工艺/宏仍缺失。

## D028 — Accepted（参考范围）：定点技术网表ECO，不改RTL/SDC换取正值

D027的最小候选已执行：完整独立网表增加9个真实BUF_X1、reset BUF_X1→X16，后针对11个同网transition违例仅改一处NOR4_X1→X2。原72宏、16MAC、所有外部端口及计算RTL/Golden保留；SDC逐字节相同。图投影证明范围仅至第二候选，第三步以绑定Liberty同函数及逐pin检查单独接受。三轮中间失败及生成器兼容错误保留，原版不覆盖。

最终候选真实1/12层回放均PASS，12层304128输出及恢复/背压/实际响应检查完成；202主机检查通过。参考setup+4.652084ns、data hold+0.001379ns、removal+0.055262ns，参考transition/clock检查0违例。46035标准单元、0.057011514mm²标准逻辑，相对原版+14.098μm²；counter历史报告继承的11.438μm²只属于第一步，不能误当累计值。

接受的是参考库/ideal clock/原统计wireload/宏切口和所测零延迟场景；hold余量仅1.379ps，宏负载/时序/面积/功耗、正式PVT/平台及全输入形式均未补齐。未知项不补零，正式150MHz/PPA仍BLOCKED；官方源或重新映射后须重新生成并验证ECO，不能照搬当前buffer级数。依据`docs/optimization/SRAM_REFERENCE_ECO.md`及`docs/runs/sram-reference-eco-20261018.json`。

## D029 — Accepted（已知参考负载）：全网电容失败后再增量修复并重新验收

D028之后的全网48378标准输出扫描发现4驱动/8极性电容超限，故不接受第三候选完整参考电气。实际匿名网到完整cell由bit/源负载pin签名核对，plan绑定原报告及完整expected_cell。第四候选仅2个NOR3及2个NOR4的X1→X2，同库函数及全部连接保持；标准逻辑累计+17.822μm²、总0.057015238mm²，不含宏。原cap失败和解析格式失败保留，不删数据换结果。

第四候选新STA与全网电气、1层及12层功能全部重新执行，304128输出通过；原SDC下setup/hold/removal仍+4.652084/+0.001379/+0.055262ns。48378输出/32类上限已知cap零违例，包含上游负载变化；transition/clock零报告违例。推广为有界`make check-reference-electrical STA_REPORT=...`并实跑，日志固定artifacts/runs；204主机测试及静态入口通过，索引`docs/runs/sram-reference-cap-closure-20261018.json`。

仅接受参考宏切口已知负载、已覆盖时序和所测功能；182宏输入负载、1152宏输出驱动未知，不把缺失值补零。hold仅1.379ps，正式PVT/完整150MHz/面积功耗继续BLOCKED，全输入形式仍NOT_PROVEN。开发源码包与原始EDA/平台/库分开统计，旧614文件/202测试的恢复结果只属于当时包，不用它冒充后加脚本已验收。

## D030 — Accepted（材料工具范围）：官方输入按用途分阶段，保留冻结开发链

收口审计发现旧官方分支将功能仿真与全部PPA文件绑定、综合共用功能源、跨角色同库被拒绝，且现有CLI未开放official。新增`official-sram-package.json`及独立预检/Make入口，按simulation/synthesis/timing/ppa给出所需材料和不同源集；同一Liberty可跨角色复用并去重依赖，RTL重复仍按实际编译集合拒绝。

不修改冻结旧选择器、Make或回归producer，避免把新增准入逻辑误归入既有功能证据；也不设置旧READY。文件身份/分类通过只叫FILES_VERIFIED，不证明来源真实性、模块/端口/宏功能/PVT或PPA。外部授权技术文件按许可受控导入后才能预检，不用软链接绕过路径边界，不自动打包官方blob。

22新增工具测试、9原生CLI及全226主机检查通过，含缺包、私有分类夹具、错误SHA、NUL/超长路径；真实材料各阶段BLOCKED。父级v3在命令前绑定源身份，v2和宿主日志名失败保留，不追补旧预冻结声明。644个唯一文件复核含旧596不变，索引`docs/runs/official-sram-intake-20261018.json`。下一阶段仍须真实Adapter/官方回归接线及指定工艺验收，S5不变为PASS。


## D031 — Accepted（入口资格化范围）：先验证逻辑Adapter接线，官方身份不由夹具代替

在不改冻结核心/ICB/SoC/根Make与原Wrapper的情况下，新增独立BACKEND=3原语/bank入口，消费D030的simulation文件计划。当前包未提供时返回BLOCKED且0条HDL命令；开发夹具必须显式选用，普通清单出现夹具路径/标记拒绝，SYNTHESIS也拒绝，不推测官方宏引脚。

实际Icarus完成3种合法容量原语及5种现有bank形状，8场景/23177数据检查、15类准确FATAL拒绝；故意坏数据在首读失败，缺/重复Adapter实际编译失败。检查器先按独立10项测试实现，审查发现预期FATAL混入其他错误仍可接受，再补2项/12污染激励并修复。全238主机检查及make verify通过；完整原生8 CLI资格化在final-v2。final-v1父reader对早期拒绝identity字段的假设导致FAIL，原结果保留，生产入口现在记录初始及完整来源范围。

外部include/运行时数据/SDF/DPI消费尚无辅助文件清单，普通源集保守拒绝相应标记；此门槛不是HDL语法或安全证明。所测场景尚不包含同址不同值覆写和reset期间持续enable，后续专门补齐，不把本轮称完整官方SRAM验收。原核心/ICB/CPU及指定工艺未跑，official_validation=NOT_RUN、official_ppa=BLOCKED，真实包仍须Adapter及对应受影响依赖链回归。入口说明`docs/OFFICIAL_SRAM_CONTRACT_RUNNER.md`，原生记录`artifacts/diagnostics/20261018-official-contract/final-v2/result.json`。


## D032 — Accepted（开发定向范围）：补不同值覆写与reset门控，保留全部冻结实现

D031明确的两个覆盖缺口以独立TB/runner补测，不改原Wrapper/核心/Golden/旧runner。对3种合法原语和5种实际bank，验证首末及物理tile边界两侧A→全宽~A改写、reset期间连续高写/读使能、三种释放首拍以及无posedge短reset。先取得已知Q，再用四态比较，不假定初始payload为0。

实际默认行为/FF 16案例720分组检查，显式加开发Adapter共24案例1080检查，8组三后端MATCH；每后端360按固定N公式验计数。三份私有原语分别注入丢弃二次写、reset写/读门控泄漏，均真实编译成功后在准确功能阶段native exit1。8项新工具检查及全246主机测试、静态入口通过；独立审查重算全部40正常case签名及来源/原生状态。

旧830来源和索引本体与上一checkpoint相同，新索引`docs/runs/sram-update-reset-20261018.json`核1096唯一文件。故障只覆盖unit16×128/BACKEND3，短reset数字行为不证明工艺脉宽/恢复移除，签名不替代逐位数据断言。本轮没有官方材料、核心/CPU/综合或PPA新验收；official_validation=NOT_RUN、official_ppa=BLOCKED。说明`docs/SRAM_UPDATE_RESET_VALIDATION.md`。该决定是测试覆盖增量，不修改数值、接口或架构目标。


## D033 — Accepted（开发功能）：同源原语前置后接通Adapter核心/ICB入口

旧selector的官方READY/PPA材料耦合保持原字节，新增独立helper/producer消费simulation文件计划。必须有同清单/Adapter SHA的完整原语报告，重新核canonical source_id、必需源/工具、8正常15拒绝、33准确native命令及全部binary/log/state；文件存在或PASS字符串不能替代此门槛。默认缺包、缺前置、坏前置均在EDA前拒绝。

实际BACKEND3开发夹具完成12真实权重静音smoke304128结果（Verilator两态）、2signed41端点50688结果（Icarus四态）；原Golden/RTL及原TB保持，逐输出/顺序/装载/队列背压和复位守恒保留。ICB旧TB零X/W+signed bias由新四态top增强，真实posedge累计25348输出、193939命令/193938响应、86保持和1条reset丢弃；原marker的字面输出数不作为独立观测。X响应和提前finish两个实际小探针都由新monitor准确拒绝。

262主机检查和静态入口通过；16新工具检查不依赖artifacts，微型格式样本明确不作硬件结果。独立审查核前置/向量/原生命令/来源，新索引`docs/runs/sram-adapter-system-20261018.json`1346唯一文件含旧1096不变。84条原宽度/unsigned警告保留并分类，不宣称lint clean；没有改原源消警告。真实供应商模型未提供，official_validation=NOT_RUN、official_ppa=BLOCKED、cpu_soc=NOT_RUN。零乘积ICB不是实际模型12层总线任务；14核心任务不当14官方性能任务。说明`docs/SRAM_ADAPTER_SYSTEM.md`。


## D034 — Accepted（开发CPU功能范围）：同输入前置接入，原平台保持冻结

新增独立CPU入口和完整核心/ICB证据reader，不改原CPU/驱动/RTL/Golden/TB或已接受runner。新入口先再验同Adapter全部原语、核心/ICB原生链，固定136份平台源，只生成外设BACKEND3和checked共享模型两份私有副本。缺包/缺前置/坏前置在工具执行前停止，不将开发夹具或FILES_VERIFIED当真实宏功能。

第一轮过严ELF全文件一致检查在CPU编译前失败：仅GCC随机临时对象名的非装载字符串不同，CPU使用BIN/HEX完全一致。现分别绑定新ELF/BIN/HEX，在objcopy及仿真消费前复核，实际装载内容仍必须匹配。第二轮编译成功后，告警reader误把后续make/g++归入UNOPTFLAT块，CPU未跑；修为完整诊断行及缩进续行，加回归测试。旧失败/原源码保留，测试历史字节按已绑定SHA恢复，未追补预冻结。没有重复已经完成的CPU长测。

平台原有2 UNOPTFLAT和15 LATCH不修改或屏蔽；只允许这两类完整诊断与冻结基线一致，其余告警记录分类。该接受限定为相同开放Fork的功能开发，不能称无环、lint干净、全CPU四态或物理时序通过。

首次完整新CPU仿真原生exit0：12层304128结果逐位一致、275712装载、608256写响应、12 ACK及soft abort/pending响应外部reset恢复，开发窗口21261300周期；旧语音与新静音输入不同，相同形状/固件下周期相同，非隔离后端A/B。281主机检查及静态入口通过；原始证据`artifacts/diagnostics/20261018-adapter-soc/final-v3/result.json`和`060322…adapter-soc-494a788d/result.json`。这里只接受固定真实静音smoke/两态开发SoC，不是官方600样本、正式全装载性能或指定SRAM/PVT/面积/功耗通过。独立审查`docs/reviews/20261018-sram-adapter-soc-review.md`与1830文件来源索引`docs/runs/sram-adapter-soc-20261018.json`已保存，含旧1346不变。


## D035 — Accepted（同机开发重建范围）：显式新基线与相对路径平台清单，保留冻结入口

为解决新机器缺本地历史artifact的问题，新增版本化CPU入口，而不改D034的producer/1830来源。新入口显式接收当前baseline report、platform及compiler/objcopy；平台136份源以相对路径/SHA/尺寸核验精确集合，而非仅核数量或重写旧报告绝对路径。仅预检时明确CPU功能NOT_RUN，不能将preflight的工具PASS提升为CPU PASS。

先在独立平台目录实际重新生成12层行为基线，再以相同静音workload运行新Adapter入口，完整保留原生退出、同源原语/核心ICB前置、固件负载和告警诊断门槛。两次完整运行用途分别为新的基线和新入口验收，顺序执行；运行未结束前不记作通过。正式SRAM/平台/PPA缺口不因入口迁移解除。

D035执行结果（2026-10-19复核）：新行为基线与v2 Adapter各12层完整原生exit0、各304128输出/608256写响应/12ACK和恢复通过；48实际向量同workload、开发窗口均21261300周期。6CLI门槛、324主机检查及独立审查通过，2159文件索引含旧1830不变。说明`docs/SRAM_CPU_REBUILD.md`，审查`docs/reviews/20261018-portable-cpu-review.md`。入口/preflight/源码包恢复与另一OS/官方SRAM/指定PPA分别验收，不将同机实验扩大为正式合规。

## D036 — Proposed（GitHub交接）：主仓库独立子项目，保留E203子模块与现有Chisel工程

用户要求先列清上传内容、目标及操作方法，本轮不执行远端写入。依据本地干净`ChipContest`/E203 gitlink和quickstart，建议新增`kwt-asic/`，由`feature/kwt-sram-handoff-20261019`审查合入；不覆盖主仓库同名src/scripts/Makefile，也不采用已被忽略的migration-v0.2目录。当前E203接线由脚本在自有副本应用，故无需为这次源码交接更新子模块；未来直接纳入Fork则先推子模块commit再更新主仓库gitlink。

逐文件清单667项保留相对布局、Golden/向量、固件、检查器和必要只读来源；不传工具、平台副本、数据集和原始run，根ZIP/PDF不作为本次代码交接必需项。旧参考综合库路径硬编码仍在，本轮仅说明本机忽略的目录别名，不修改冻结producer或称全部旧默认值自动兼容。独立目录实际324主机检查和static原生exit0；首次helper因Path分段排序/字符串排序不一致，在复制/测试前拒绝，统一新清单的字符串排序后通过，失败留存。GitHub页面读取失败，不声明远端当前版本；无clone、commit、push、CPU/EDA新运行。方案与命令见`docs/handoff/GITHUB_HANDOFF_20261019.md`；官方宏/正式平台/PPA状态不变。
